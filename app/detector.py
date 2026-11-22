"""YOLO-World open-vocabulary detector mapped to canonical farm animals."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Tuple

from .config import DATA_DIR
from .detector_types import Detection

log = logging.getLogger("krshibandhu.detector")

# Text prompts -> canonical class. Several prompts improve recall for rare species.
PROMPTS: Dict[str, List[str]] = {
    "nilgai": ["nilgai", "blue bull antelope", "antelope"],
    "boar": ["wild boar", "pig"],
    "deer": ["deer", "blackbuck", "spotted deer"],
    "monkey": ["monkey", "macaque", "langur"],
    "bird": ["parrot", "bird"],
    "cattle": ["cow", "buffalo", "bull"],
    "dog": ["dog", "jackal", "fox"],
    "person": ["person"],
}


def flatten_prompts(prompts: Dict[str, List[str]] = PROMPTS) -> Tuple[List[str], List[str]]:
    labels, canon = [], []
    for c, ps in prompts.items():
        for p in ps:
            labels.append(p)
            canon.append(c)
    return labels, canon


def best_per_class(dets: List[Detection]) -> List[Detection]:
    """Keep detections, but drop duplicate boxes of same canonical class that overlap heavily."""
    dets = sorted(dets, key=lambda d: d.confidence, reverse=True)
    kept: List[Detection] = []
    for d in dets:
        if any(k.label == d.label and _iou(k.box, d.box) > 0.5 for k in kept):
            continue
        kept.append(d)
    return kept


def _iou(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1, ix2, iy2 = max(ax1, bx1), max(ay1, by1), min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = (ax2 - ax1) * (ay2 - ay1) + (bx2 - bx1) * (by2 - by1) - inter
    return inter / union if union > 0 else 0.0


class Detector:
    def __init__(self, weights: str = "yolov8s-worldv2.pt", imgsz: int = 480):
        from ultralytics import YOLOWorld  # heavy import, deferred

        models_dir = DATA_DIR / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        local = models_dir / weights
        self.imgsz = imgsz
        self.labels, self.canon = flatten_prompts()
        self.model = YOLOWorld(str(local) if local.exists() else weights)
        if not local.exists():
            try:
                Path(weights).replace(local) if Path(weights).exists() else None
            except Exception:
                pass
        self.model.set_classes(self.labels)
        log.info("YOLO-World ready with %d prompts", len(self.labels))

    def warmup(self):
        import numpy as np
        self.model.predict(np.zeros((self.imgsz, self.imgsz, 3), dtype="uint8"),
                           imgsz=self.imgsz, verbose=False)

    def detect(self, frame, conf: float = 0.35) -> List[Detection]:
        r = self.model.predict(frame, imgsz=self.imgsz, conf=conf, verbose=False)[0]
        out: List[Detection] = []
        if r.boxes is None:
            return out
        for xyxy, c, k in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), r.boxes.cls.tolist()):
            k = int(k)
            if k >= len(self.canon):
                continue
            out.append(Detection(self.canon[k], float(c), tuple(int(v) for v in xyxy), self.labels[k]))
        return best_per_class(out)
