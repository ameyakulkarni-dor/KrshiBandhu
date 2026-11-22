"""Lightweight shared types (no heavy imports)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass
class Detection:
    label: str                 # canonical label, e.g. 'boar', 'person'
    confidence: float
    box: Tuple[int, int, int, int] = (0, 0, 0, 0)   # x1, y1, x2, y2
    prompt: str = ""           # raw prompt that matched, e.g. 'wild boar'

    def to_dict(self):
        return {"label": self.label, "confidence": round(self.confidence, 3),
                "box": list(self.box), "prompt": self.prompt}
