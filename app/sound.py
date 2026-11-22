"""Sound playback on the PC speakers with random rotation."""
from __future__ import annotations

import logging
import random
import threading
from pathlib import Path
from typing import Dict, List, Optional

from .config import SOUND_CATEGORIES, SOUNDS_DIR

log = logging.getLogger("krshibandhu.sound")
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".flac"}


class SoundLibrary:
    def __init__(self, root: Path = SOUNDS_DIR):
        self.root = root
        for c in SOUND_CATEGORIES:
            (root / c).mkdir(parents=True, exist_ok=True)

    def files(self, category: str) -> List[Path]:
        d = self.root / category
        if not d.is_dir():
            return []
        return sorted(p for p in d.iterdir() if p.suffix.lower() in AUDIO_EXT)

    def listing(self) -> Dict[str, List[str]]:
        return {c: [p.name for p in self.files(c)] for c in SOUND_CATEGORIES}

    def pick(self, categories: List[str], avoid: Optional[str] = None) -> Optional[Path]:
        pool = [f for c in categories for f in self.files(c)]
        if not pool:
            return None
        choices = [f for f in pool if f.name != avoid] or pool
        return random.choice(choices)


class SoundPlayer:
    def __init__(self, library: SoundLibrary):
        self.library = library
        self.volume = 0.9
        self._last: Optional[str] = None
        self._lock = threading.Lock()
        self.available = False
        try:
            import pygame
            pygame.mixer.init()
            self._pg = pygame
            self.available = True
        except Exception as e:  # no audio device etc.
            log.warning("Audio unavailable: %s", e)
            self._pg = None

    def set_volume(self, percent: int):
        self.volume = max(0, min(100, percent)) / 100.0

    def play_categories(self, categories: List[str]) -> Optional[str]:
        f = self.library.pick(categories, avoid=self._last)
        if f is None:
            log.warning("No sound files for categories %s", categories)
            return None
        return self.play_file(f)

    def play_file(self, path: Path) -> Optional[str]:
        with self._lock:
            self._last = path.name
            if not self.available:
                log.info("(silent) would play %s", path.name)
                return f"{path.parent.name}/{path.name}"
            try:
                snd = self._pg.mixer.Sound(str(path))
                snd.set_volume(self.volume)
                snd.play()
            except Exception as e:
                log.error("Failed to play %s: %s", path, e)
                return None
            return f"{path.parent.name}/{path.name}"

    def stop(self):
        if self.available:
            self._pg.mixer.stop()


class NullPlayer(SoundPlayer):
    """Records calls instead of playing audio (tests)."""

    def __init__(self, library: SoundLibrary):
        self.library = library
        self.volume = 0.9
        self._last = None
        self._lock = threading.Lock()
        self.available = False
        self._pg = None
        self.played: List[str] = []

    def play_file(self, path: Path):
        self._last = path.name
        name = f"{path.parent.name}/{path.name}"
        self.played.append(name)
        return name
