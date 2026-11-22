"""Camera capture thread with latest-frame semantics and low-light boost."""
from __future__ import annotations

import glob
import logging
import os
import subprocess
import sys
import threading
import time
from typing import Any, Dict, List, Optional

import cv2
import numpy as np

log = logging.getLogger("krshibandhu.camera")


def enhance_low_light(frame: np.ndarray, gamma: float = 1.6) -> np.ndarray:
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8)).apply(l)
    out = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)
    table = np.array([((i / 255.0) ** (1.0 / gamma)) * 255 for i in range(256)]).astype("uint8")
    return cv2.LUT(out, table)


def list_cameras_info(max_index: int = 4) -> List[Dict[str, Any]]:
    friendly_names: List[str] = []

    # Windows: try querying PnP Camera names
    if sys.platform == "win32":
        try:
            ps_cmd = "Get-PnpDevice -Class Camera | Where-Object Status -eq 'OK' | Select-Object -ExpandProperty FriendlyName"
            out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_cmd], text=True, timeout=4)
            friendly_names = [line.strip() for line in out.strip().splitlines() if line.strip()]
        except Exception:
            pass
    elif sys.platform.startswith("linux"):
        # Linux: check /sys/class/video4linux
        v4l_devices = sorted(glob.glob("/sys/class/video4linux/video*"))
        for v in v4l_devices:
            name_file = os.path.join(v, "name")
            if os.path.exists(name_file):
                try:
                    friendly_names.append(open(name_file).read().strip())
                except Exception:
                    pass

    found: List[Dict[str, Any]] = []
    # Test video capture indices
    backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
    for i in range(max_index + 1):
        cap = cv2.VideoCapture(i, backend)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(i)
        if cap is not None and cap.isOpened():
            ok, _ = cap.read()
            if ok:
                name = friendly_names[i] if i < len(friendly_names) else f"Device {i}"
                found.append({"index": i, "name": f"Camera {i} ({name})"})
            cap.release()
    return found


def list_cameras(max_index: int = 4) -> List[int]:
    """Compatibility wrapper returning list of integer camera indices."""
    return [c["index"] for c in list_cameras_info(max_index)]


class Camera:
    """Continuously grabs frames; consumers get only the most recent one."""

    def __init__(self, index: int = 0, width: int = 1280, height: int = 720):
        self.index = index
        self.width, self.height = width, height
        self._frame: Optional[np.ndarray] = None
        self._frame_id = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._switch_index: Optional[int] = None
        self.connected = False
        self.low_light = False

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def switch(self, index: int):
        with self._lock:
            self.index = index
            self._switch_index = index

    def _open(self, idx: int):
        backend = cv2.CAP_DSHOW if sys.platform == "win32" else cv2.CAP_ANY
        cap = cv2.VideoCapture(idx, backend)
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(idx)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        return cap

    def push_frame(self, frame: np.ndarray):
        """Allows feeding frames directly from a remote browser webcam or client."""
        if self.low_light:
            frame = enhance_low_light(frame)
        with self._lock:
            self._frame = frame
            self._frame_id += 1
        self.connected = True

    def _run(self):
        cap = None
        active_idx = self.index
        while not self._stop.is_set():
            # Check if camera switch was requested
            if self._switch_index is not None and self._switch_index != active_idx:
                if cap is not None:
                    cap.release()
                    cap = None
                active_idx = self._switch_index
                self._switch_index = None
                log.info("Switching capture to camera index %s", active_idx)

            if cap is None or not cap.isOpened():
                cap = self._open(active_idx)
                if not cap.isOpened():
                    self.connected = False
                    log.warning("Camera %s not available, retrying...", active_idx)
                    time.sleep(1.5)
                    continue
            ok, frame = cap.read()
            if not ok:
                self.connected = False
                cap.release()
                cap = None
                time.sleep(0.5)
                continue
            self.connected = True
            if self.low_light:
                frame = enhance_low_light(frame)
            with self._lock:
                self._frame = frame
                self._frame_id += 1
        if cap is not None:
            cap.release()
        self.connected = False

    def read(self):
        with self._lock:
            return self._frame_id, (None if self._frame is None else self._frame.copy())


class FakeCamera(Camera):
    """Feeds static images (for tests / demos without a webcam)."""

    def __init__(self, frames: List[np.ndarray], fps: float = 10):
        super().__init__()
        self.frames = frames
        self.fps = fps

    def _run(self):
        i = 0
        while not self._stop.is_set():
            with self._lock:
                self._frame = self.frames[i % len(self.frames)]
                self._frame_id += 1
            self.connected = True
            i += 1
            time.sleep(1 / self.fps)
