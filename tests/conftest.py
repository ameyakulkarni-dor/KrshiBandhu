import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import SettingsStore  # noqa: E402
from app.detector_types import Detection  # noqa: E402
from app.sound import NullPlayer, SoundLibrary  # noqa: E402
from app.storage import Storage  # noqa: E402


class ScriptedDetector:
    """Returns whatever detections are currently scripted."""

    def __init__(self):
        self.next = []

    def detect(self, frame, conf=0.35):
        return [d for d in self.next if d.confidence >= conf]


@pytest.fixture
def tmp_env(tmp_path):
    sounds = tmp_path / "sounds"
    lib = SoundLibrary(sounds)
    for cat in ["tiger", "leopard", "hawk"]:
        for i in range(2):
            (sounds / cat / f"{cat}_{i}.mp3").write_bytes(b"ID3fake")
    store = SettingsStore(tmp_path / "settings.json")
    storage = Storage(tmp_path / "db.sqlite", tmp_path / "snaps")
    return {"store": store, "storage": storage, "lib": lib, "player": NullPlayer(lib), "tmp": tmp_path}


def det(label, conf=0.8):
    return Detection(label, conf, (10, 10, 100, 100), label)


@pytest.fixture
def frame():
    return np.zeros((120, 160, 3), dtype=np.uint8)
