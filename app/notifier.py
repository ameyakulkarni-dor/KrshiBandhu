"""Telegram notifier running on a background thread with rate limiting."""
from __future__ import annotations

import logging
import queue
import threading
import time
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

import httpx

log = logging.getLogger("krshibandhu.telegram")

EMOJI = {"nilgai": "🐂", "boar": "🐗", "deer": "🦌", "monkey": "🐒", "bird": "🦜",
         "cattle": "🐄", "dog": "🐕", "person": "🧍"}
NAMES = {"nilgai": "Nilgai (Blue bull)", "boar": "Wild boar", "deer": "Deer / Blackbuck",
         "monkey": "Monkey", "bird": "Parrot / bird", "cattle": "Stray cattle",
         "dog": "Dog / jackal", "person": "Person"}


def send_telegram(token: str, chat_id: str, text: str, photo: Optional[Path] = None,
                  timeout: float = 15) -> Tuple[bool, str]:
    if not token or not chat_id:
        return False, "Token or chat ID missing"
    base = f"https://api.telegram.org/bot{token}"
    try:
        if photo and photo.exists():
            with photo.open("rb") as fh:
                r = httpx.post(f"{base}/sendPhoto", data={"chat_id": chat_id, "caption": text},
                               files={"photo": (photo.name, fh, "image/jpeg")}, timeout=timeout)
        else:
            r = httpx.post(f"{base}/sendMessage", data={"chat_id": chat_id, "text": text},
                           timeout=timeout)
        ok = r.status_code == 200 and r.json().get("ok", False)
        return ok, ("sent" if ok else r.text[:200])
    except Exception as e:
        return False, str(e)


class TelegramNotifier:
    def __init__(self, get_config: Callable[[], Tuple[bool, str, str]],
                 on_sent: Optional[Callable[[int], None]] = None, min_interval_s: float = 120):
        self.get_config = get_config
        self.on_sent = on_sent
        self.min_interval_s = min_interval_s
        self._last: Dict[str, float] = {}
        self._q: "queue.Queue" = queue.Queue(maxsize=50)
        self._t = threading.Thread(target=self._run, name="telegram", daemon=True)
        self._t.start()

    def notify(self, event_id: int, animal: str, sound: Optional[str], photo: Optional[Path],
               suppressed: Optional[str] = None):
        enabled, token, chat = self.get_config()
        if not enabled or not token or not chat:
            return
        now = time.time()
        if now - self._last.get(animal, 0) < self.min_interval_s:
            return
        self._last[animal] = now
        when = time.strftime("%d %b %H:%M")
        text = f"{EMOJI.get(animal, '⚠️')} {NAMES.get(animal, animal)} detected at {when}"
        if sound:
            text += f"\n🔊 Played: {sound}"
        elif suppressed == "person":
            text += "\n(no sound - person in frame)"
        elif suppressed == "disarmed":
            text += "\n(no sound - system disarmed)"
        text += "\n— KrshiBandhu"
        try:
            self._q.put_nowait((event_id, token, chat, text, photo))
        except queue.Full:
            log.warning("Telegram queue full, dropping alert")

    def _run(self):
        while True:
            eid, token, chat, text, photo = self._q.get()
            ok, msg = send_telegram(token, chat, text, photo)
            if ok and self.on_sent:
                self.on_sent(eid)
            elif not ok:
                log.warning("Telegram send failed: %s", msg)
