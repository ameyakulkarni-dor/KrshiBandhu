"""SQLite event storage, snapshots and statistics."""
from __future__ import annotations

import shutil
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import cv2

from .config import DB_FILE, SNAPSHOT_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,            -- animal | person | manual
    animal TEXT,
    confidence REAL,
    sound TEXT,
    snapshot TEXT,
    suppressed TEXT,               -- why no sound: person | disarmed | NULL
    notified INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""


class Storage:
    def __init__(self, db_path: Path = DB_FILE, snapshot_dir: Path = SNAPSHOT_DIR):
        self.db_path = db_path
        self.snapshot_dir = snapshot_dir
        db_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def save_snapshot(self, frame, ts: Optional[float] = None) -> Optional[str]:
        if frame is None:
            return None
        ts = ts or time.time()
        dt = datetime.fromtimestamp(ts)
        day = self.snapshot_dir / dt.strftime("%Y-%m-%d")
        day.mkdir(parents=True, exist_ok=True)
        name = dt.strftime("%H%M%S_") + f"{int((ts % 1) * 1000):03d}.jpg"
        path = day / name
        cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return f"{day.name}/{name}"

    def add_event(self, kind: str, animal: Optional[str] = None, confidence: float = 0.0,
                  sound: Optional[str] = None, snapshot: Optional[str] = None,
                  suppressed: Optional[str] = None, ts: Optional[float] = None) -> Dict:
        ts = ts or time.time()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events(ts, kind, animal, confidence, sound, snapshot, suppressed) "
                "VALUES (?,?,?,?,?,?,?)",
                (ts, kind, animal, confidence, sound, snapshot, suppressed))
            self._conn.commit()
            eid = cur.lastrowid
        return self.get_event(eid)

    def mark_notified(self, eid: int):
        with self._lock:
            self._conn.execute("UPDATE events SET notified=1 WHERE id=?", (eid,))
            self._conn.commit()

    def get_event(self, eid: int) -> Dict:
        with self._lock:
            row = self._conn.execute("SELECT * FROM events WHERE id=?", (eid,)).fetchone()
        return dict(row) if row else {}

    def list_events(self, limit: int = 50, offset: int = 0, animal: Optional[str] = None) -> Dict:
        where, args = "", []
        if animal:
            where = "WHERE animal=?" if animal != "person" else "WHERE kind='person'"
            if animal != "person":
                args.append(animal)
        with self._lock:
            total = self._conn.execute(f"SELECT COUNT(*) FROM events {where}", args).fetchone()[0]
            rows = self._conn.execute(
                f"SELECT * FROM events {where} ORDER BY ts DESC LIMIT ? OFFSET ?",
                args + [limit, offset]).fetchall()
        return {"total": total, "items": [dict(r) for r in rows]}

    def stats(self, hours: int = 24) -> Dict:
        since = time.time() - hours * 3600
        with self._lock:
            per_animal = self._conn.execute(
                "SELECT COALESCE(animal, kind) AS a, COUNT(*) FROM events "
                "WHERE ts>=? AND kind!='manual' GROUP BY a", (since,)).fetchall()
            sounds = self._conn.execute(
                "SELECT COUNT(*) FROM events WHERE ts>=? AND sound IS NOT NULL", (since,)).fetchone()[0]
            rows = self._conn.execute(
                "SELECT ts FROM events WHERE ts>=? AND kind='animal'", (since,)).fetchall()
        # hourly buckets (local time)
        bucket_hours = hours if hours <= 48 else 24
        buckets: Dict[str, int] = {}
        if hours <= 48:
            start = datetime.fromtimestamp(since).replace(minute=0, second=0, microsecond=0)
            for i in range(bucket_hours + 1):
                buckets[(start + timedelta(hours=i)).strftime("%d %b %H:00")] = 0
            for (ts,) in rows:
                k = datetime.fromtimestamp(ts).strftime("%d %b %H:00")
                if k in buckets:
                    buckets[k] += 1
        else:
            start = datetime.fromtimestamp(since).date()
            days = hours // 24
            for i in range(days + 1):
                buckets[(start + timedelta(days=i)).strftime("%d %b")] = 0
            for (ts,) in rows:
                k = datetime.fromtimestamp(ts).strftime("%d %b")
                if k in buckets:
                    buckets[k] += 1
        # hour-of-day distribution (for spotting raid times)
        hod = [0] * 24
        for (ts,) in rows:
            hod[datetime.fromtimestamp(ts).hour] += 1
        pa = {a: c for a, c in per_animal}
        return {
            "per_animal": pa,
            "timeline": {"labels": list(buckets.keys()), "values": list(buckets.values())},
            "hour_of_day": hod,
            "total_animals": sum(c for a, c in pa.items() if a != "person"),
            "total_persons": pa.get("person", 0),
            "sounds_played": sounds,
        }

    def cleanup(self, retention_days: int):
        cutoff = datetime.now() - timedelta(days=retention_days)
        for d in self.snapshot_dir.iterdir():
            if d.is_dir():
                try:
                    if datetime.strptime(d.name, "%Y-%m-%d") < cutoff:
                        shutil.rmtree(d, ignore_errors=True)
                except ValueError:
                    continue
        with self._lock:
            self._conn.execute("DELETE FROM events WHERE ts<?", (cutoff.timestamp(),))
            self._conn.commit()

    def close(self):
        with self._lock:
            self._conn.close()
