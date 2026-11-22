import time
from datetime import datetime, timedelta

import numpy as np

from app.storage import Storage


def test_events_and_filter(tmp_path):
    st = Storage(tmp_path / "db", tmp_path / "snaps")
    st.add_event("animal", "boar", 0.8, "tiger/t.mp3")
    st.add_event("animal", "deer", 0.7, None, suppressed="person")
    st.add_event("person", "person", 0.9)
    all_ = st.list_events()
    assert all_["total"] == 3
    assert all_["items"][0]["kind"] == "person"   # newest first
    assert st.list_events(animal="boar")["total"] == 1
    assert st.list_events(animal="person")["total"] == 1


def test_stats(tmp_path):
    st = Storage(tmp_path / "db", tmp_path / "snaps")
    now = time.time()
    for _ in range(3):
        st.add_event("animal", "boar", 0.8, "tiger/a.mp3", ts=now)
    st.add_event("animal", "bird", 0.6, None, ts=now)
    st.add_event("person", "person", 0.9, ts=now)
    st.add_event("manual", "boar", 0, "tiger/a.mp3", ts=now)
    st.add_event("animal", "boar", 0.8, "x", ts=now - 3 * 86400)   # outside 24h
    s = st.stats(24)
    assert s["per_animal"] == {"boar": 3, "bird": 1, "person": 1}
    assert s["total_animals"] == 4 and s["total_persons"] == 1
    assert s["sounds_played"] == 4     # 3 auto + 1 manual
    assert sum(s["timeline"]["values"]) == 4
    assert sum(s["hour_of_day"]) == 4
    assert st.stats(168)["total_animals"] == 5


def test_snapshot_and_cleanup(tmp_path):
    st = Storage(tmp_path / "db", tmp_path / "snaps")
    rel = st.save_snapshot(np.zeros((50, 50, 3), np.uint8))
    assert (tmp_path / "snaps" / rel).exists()
    old_day = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")
    (tmp_path / "snaps" / old_day).mkdir()
    st.add_event("animal", "boar", 0.5, ts=time.time() - 40 * 86400)
    st.cleanup(30)
    assert not (tmp_path / "snaps" / old_day).exists()
    assert (tmp_path / "snaps" / rel).exists()
    assert st.list_events()["total"] == 0
