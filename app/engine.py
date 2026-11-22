"""Engine: wires camera -> detector -> trigger -> sound / storage / alerts."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Callable, Dict, List, Optional, Set

import cv2
import numpy as np

from .config import SNAPSHOT_DIR, Settings, SettingsStore
from .detector_types import Detection
from .sound import SoundPlayer
from .storage import Storage
from .trigger import TriggerEngine

log = logging.getLogger("krshibandhu.engine")

COLORS = {"nilgai": (40, 120, 230), "boar": (30, 60, 200), "deer": (0, 165, 255),
          "monkey": (0, 200, 200), "bird": (60, 200, 60), "cattle": (200, 120, 40),
          "dog": (180, 60, 180), "person": (230, 230, 230)}


def draw_detections(frame: np.ndarray, dets: List[Detection]) -> np.ndarray:
    out = frame.copy()
    for d in dets:
        x1, y1, x2, y2 = d.box
        c = COLORS.get(d.label, (0, 255, 0))
        cv2.rectangle(out, (x1, y1), (x2, y2), c, 3)
        txt = f"{d.label} {d.confidence:.0%}"
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(out, (x1, max(0, y1 - th - 10)), (x1 + tw + 8, y1), c, -1)
        cv2.putText(out, txt, (x1 + 4, y1 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    return out


class Engine:
    def __init__(self, store: SettingsStore, camera, detector_factory: Callable[[], object],
                 player: SoundPlayer, storage: Storage, notifier=None):
        self.store = store
        self.camera = camera
        self.detector_factory = detector_factory
        self.detector = None
        self.player = player
        self.storage = storage
        self.notifier = notifier
        self.trigger = TriggerEngine()
        self.status = "starting"          # starting | loading_model | running | error
        self.error: Optional[str] = None
        self.fps = 0.0
        self.last_detections: List[Detection] = []
        self.last_trigger: Optional[Dict] = None
        self._last_person_log = 0.0
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._subscribers: Set[asyncio.Queue] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._sub_lock = threading.Lock()
        self.apply_settings(store.get())

    # ---------- lifecycle ----------
    def start(self, loop: Optional[asyncio.AbstractEventLoop] = None):
        self._loop = loop
        self.camera.start()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="engine", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.camera.stop()

    def apply_settings(self, s: Settings):
        self.trigger.configure(s.window, s.hits, s.cooldown_s, s.armed, s.enabled_animals, s.person_veto)
        self.player.set_volume(s.volume)
        self.camera.low_light = s.low_light
        if getattr(self.camera, "index", s.camera_index) != s.camera_index and hasattr(self.camera, "switch"):
            if self._thread is not None:
                self.camera.switch(s.camera_index)
            else:
                self.camera.index = s.camera_index

    # ---------- pub/sub for websocket ----------
    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        with self._sub_lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue):
        with self._sub_lock:
            self._subscribers.discard(q)

    def broadcast(self, msg: Dict):
        if self._loop is None:
            return
        with self._sub_lock:
            subs = list(self._subscribers)
        for q in subs:
            def _put(q=q):
                if q.full():
                    try:
                        q.get_nowait()
                    except Exception:
                        pass
                q.put_nowait(msg)
            try:
                self._loop.call_soon_threadsafe(_put)
            except RuntimeError:
                pass

    def status_dict(self) -> Dict:
        s = self.store.get()
        return {"status": self.status, "error": self.error, "armed": s.armed,
                "fps": round(self.fps, 1), "camera_connected": bool(getattr(self.camera, "connected", False)),
                "camera_index": s.camera_index, "audio": self.player.available,
                "last_trigger": self.last_trigger,
                "detections": [d.to_dict() for d in self.last_detections]}

    # ---------- main loop ----------
    def _load_detector(self) -> bool:
        self.status = "loading_model"
        self.broadcast({"type": "status", **self.status_dict()})
        try:
            self.detector = self.detector_factory()
            if hasattr(self.detector, "warmup"):
                self.detector.warmup()
            self.status = "running"
            self.error = None
            return True
        except Exception as e:
            log.exception("Detector failed to load")
            self.status = "error"
            self.error = f"Model failed to load: {e}"
            return False

    def _run(self):
        if not self._load_detector():
            self.broadcast({"type": "status", **self.status_dict()})
            return
        last_id = -1
        t_last = time.time()
        while not self._stop.is_set():
            fid, frame = self.camera.read()
            if frame is None or fid == last_id:
                time.sleep(0.02)
                continue
            last_id = fid
            s = self.store.get()
            try:
                dets = self.detector.detect(frame, s.confidence)
            except Exception as e:
                log.exception("Detection error")
                self.error = str(e)
                time.sleep(0.5)
                continue
            now = time.time()
            dt = now - t_last
            t_last = now
            self.fps = 0.8 * self.fps + 0.2 * (1.0 / dt) if dt > 0 else self.fps
            self.last_detections = dets
            self.process(frame, dets, now, s)

    def process(self, frame, dets: List[Detection], now: float, s: Optional[Settings] = None):
        """Handle one analysed frame. Separated from _run for testability."""
        s = s or self.store.get()
        decision = self.trigger.update(dets, now)
        self.broadcast({"type": "detections", "detections": [d.to_dict() for d in dets],
                        "fps": round(self.fps, 1), "person": decision.person_present,
                        "armed": s.armed, "camera_connected": bool(getattr(self.camera, "connected", False))})

        annotated = None

        def snap():
            nonlocal annotated
            if annotated is None and frame is not None:
                annotated = draw_detections(frame, dets)
            return self.storage.save_snapshot(annotated, now)

        if decision.fire:
            animal = decision.fire
            cats = s.mapping.get(animal, [])
            sound = self.player.play_categories(cats) if cats else None
            ev = self.storage.add_event("animal", animal, decision.confidence, sound, snap(), None, now)
            self.last_trigger = ev
            self.broadcast({"type": "event", "event": ev})
            self._notify(ev, animal, sound, None)

        for animal in decision.log_animals:
            conf = max((d.confidence for d in dets if d.label == animal), default=0.0)
            ev = self.storage.add_event("animal", animal, conf, None, snap(), decision.suppressed_reason, now)
            self.broadcast({"type": "event", "event": ev})
            self._notify(ev, animal, None, decision.suppressed_reason)

        if any(d.label == "person" for d in dets) and now - self._last_person_log >= 60:
            self._last_person_log = now
            conf = max(d.confidence for d in dets if d.label == "person")
            ev = self.storage.add_event("person", "person", conf, None, snap(), None, now)
            self.broadcast({"type": "event", "event": ev})
            if s.person_alert:
                self._notify(ev, "person", None, None)

    def _notify(self, ev: Dict, animal: str, sound, suppressed):
        if self.notifier is None or not ev:
            return
        photo = self.storage.snapshot_dir / ev["snapshot"] if ev.get("snapshot") else None
        self.notifier.notify(ev["id"], animal, sound, photo, suppressed)

    # ---------- manual ----------
    def manual_play(self, animal: Optional[str] = None, category: Optional[str] = None) -> Optional[str]:
        s = self.store.get()
        if category:
            cats = [category]
        elif animal:
            cats = s.mapping.get(animal, [])
        else:
            return None
        sound = self.player.play_categories(cats)
        if sound:
            ev = self.storage.add_event("manual", animal, 0.0, sound, None, None)
            self.broadcast({"type": "event", "event": ev})
        return sound

    def stream_frame(self, quality: int = 70) -> Optional[bytes]:
        _, frame = self.camera.read()
        if frame is None:
            return None
        frame = draw_detections(frame, self.last_detections)
        h, w = frame.shape[:2]
        if w > 960:
            frame = cv2.resize(frame, (960, int(h * 960 / w)))
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
        return buf.tobytes() if ok else None
