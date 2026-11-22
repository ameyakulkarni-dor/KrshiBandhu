"""Trigger engine: decides when to fire a scare sound. Pure logic, no I/O."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Iterable, List, Optional, Set

from .detector_types import Detection


@dataclass
class TriggerDecision:
    fire: Optional[str] = None            # animal to scare, if any
    confidence: float = 0.0
    person_present: bool = False
    suppressed_reason: Optional[str] = None   # 'person' | 'disarmed' | 'cooldown' | None
    log_animals: List[str] = field(default_factory=list)   # newly confirmed animals (for logging when not firing)


class TriggerEngine:
    def __init__(self, window: int = 3, hits: int = 1, cooldown_s: float = 20,
                 global_cooldown_s: float = 4, person_memory: int = 5, person_veto: bool = False):
        self.window = window
        self.hits = hits
        self.cooldown_s = cooldown_s
        self.global_cooldown_s = global_cooldown_s
        self.person_memory = person_memory
        self.person_veto = person_veto
        self.history: Deque[Set[str]] = deque(maxlen=window)
        self.person_history: Deque[bool] = deque(maxlen=person_memory)
        self.last_fire: Dict[str, float] = {}
        self.last_any_fire: float = float("-inf")
        self.last_logged: Dict[str, float] = {}
        self.armed = True
        self.enabled: Optional[Set[str]] = None

    def configure(self, window: int, hits: int, cooldown_s: float, armed: bool,
                  enabled: Optional[Iterable[str]] = None, person_veto: bool = False):
        if window != self.window:
            self.history = deque(list(self.history)[-window:], maxlen=window)
        self.window = window
        self.hits = min(hits, window)
        self.cooldown_s = cooldown_s
        self.armed = armed
        self.enabled = set(enabled) if enabled is not None else None
        self.person_veto = person_veto

    def update(self, detections: List[Detection], now: float) -> TriggerDecision:
        labels = {d.label for d in detections}
        best_conf: Dict[str, float] = {}
        for d in detections:
            best_conf[d.label] = max(best_conf.get(d.label, 0.0), d.confidence)

        person_now = "person" in labels
        self.person_history.append(person_now)
        animals = {l for l in labels if l != "person"}
        if self.enabled is not None:
            animals &= self.enabled
        self.history.append(animals)

        decision = TriggerDecision(person_present=any(self.person_history))

        # Animals confirmed by the voting window.
        counts: Dict[str, int] = {}
        for frame in self.history:
            for a in frame:
                counts[a] = counts.get(a, 0) + 1
        confirmed = [a for a, c in counts.items() if c >= self.hits and a in animals]
        if not confirmed:
            return decision

        # Log-worthy confirmations (rate limited by cooldown even when not firing)
        for a in confirmed:
            if now - self.last_logged.get(a, float("-inf")) >= max(self.cooldown_s, 1):
                decision.log_animals.append(a)

        if decision.person_present and self.person_veto:
            decision.suppressed_reason = "person"
            self._mark_logged(decision.log_animals, now)
            return decision
        if not self.armed:
            decision.suppressed_reason = "disarmed"
            self._mark_logged(decision.log_animals, now)
            return decision

        if now - self.last_any_fire < self.global_cooldown_s:
            decision.suppressed_reason = "cooldown"
            decision.log_animals = []
            return decision

        ready = [a for a in confirmed
                 if now - self.last_fire.get(a, float("-inf")) >= self.cooldown_s]
        if not ready:
            decision.suppressed_reason = "cooldown"
            decision.log_animals = []
            return decision

        target = max(ready, key=lambda a: best_conf.get(a, 0.0))
        self.last_fire[target] = now
        self.last_any_fire = now
        decision.fire = target
        decision.confidence = best_conf.get(target, 0.0)
        decision.log_animals = [a for a in decision.log_animals if a != target]
        self._mark_logged([target] + decision.log_animals, now)
        return decision

    def _mark_logged(self, animals: List[str], now: float):
        for a in animals:
            self.last_logged[a] = now

    def reset(self):
        self.history.clear()
        self.person_history.clear()
