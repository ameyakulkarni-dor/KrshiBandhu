"""Settings model and JSON persistence."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Dict, List

from pydantic import BaseModel, Field, field_validator

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SOUNDS_DIR = BASE_DIR / "sounds"
STATIC_DIR = BASE_DIR / "static"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
SETTINGS_FILE = DATA_DIR / "settings.json"
DB_FILE = DATA_DIR / "krshibandhu.db"

# Canonical animals the system knows about (person is special: never scared).
ANIMALS: List[str] = ["nilgai", "boar", "deer", "monkey", "bird", "cattle", "dog"]
SOUND_CATEGORIES: List[str] = ["tiger", "leopard", "dogs", "hawk", "eagle", "human"]

DEFAULT_MAPPING: Dict[str, List[str]] = {
    "nilgai": ["tiger", "leopard"],
    "deer": ["tiger", "leopard"],
    "boar": ["tiger", "leopard"],
    "cattle": ["tiger", "leopard"],
    "monkey": ["leopard", "dogs"],
    "bird": ["hawk", "eagle"],
    "dog": ["tiger", "human"],
}


class Settings(BaseModel):
    camera_index: int = Field(0, ge=0, le=10)
    confidence: float = Field(0.20, ge=0.05, le=0.95)
    window: int = Field(3, ge=1, le=30)
    hits: int = Field(1, ge=1, le=30)
    cooldown_s: int = Field(20, ge=0, le=600)
    volume: int = Field(90, ge=0, le=100)
    low_light: bool = False
    armed: bool = True
    person_veto: bool = False
    person_alert: bool = False
    mapping: Dict[str, List[str]] = Field(default_factory=lambda: {k: list(v) for k, v in DEFAULT_MAPPING.items()})
    enabled_animals: List[str] = Field(default_factory=lambda: list(ANIMALS))
    telegram_enabled: bool = False
    telegram_token: str = ""
    telegram_chat_id: str = ""
    retention_days: int = Field(30, ge=1, le=365)
    language: str = "en"

    @field_validator("hits")
    @classmethod
    def _hits_le_window(cls, v, info):
        window = info.data.get("window", 5)
        return min(v, window)

    @field_validator("mapping")
    @classmethod
    def _valid_mapping(cls, v):
        out = {}
        for animal in ANIMALS:
            cats = [c for c in v.get(animal, DEFAULT_MAPPING[animal]) if c in SOUND_CATEGORIES]
            out[animal] = cats
        return out

    @field_validator("enabled_animals")
    @classmethod
    def _valid_animals(cls, v):
        return [a for a in v if a in ANIMALS]

    @field_validator("language")
    @classmethod
    def _valid_lang(cls, v):
        return v if v in ("en", "hi") else "en"


class SettingsStore:
    """Thread-safe settings holder persisted to JSON."""

    def __init__(self, path: Path = SETTINGS_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._settings = self._load()

    def _load(self) -> Settings:
        if self.path.exists():
            try:
                return Settings(**json.loads(self.path.read_text(encoding="utf-8")))
            except Exception:
                pass
        return Settings()

    def get(self) -> Settings:
        with self._lock:
            return self._settings.model_copy(deep=True)

    def update(self, **changes) -> Settings:
        with self._lock:
            data = self._settings.model_dump()
            data.update({k: v for k, v in changes.items() if k in data})
            self._settings = Settings(**data)
            self._save()
            return self._settings.model_copy(deep=True)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self._settings.model_dump_json(indent=2), encoding="utf-8")
