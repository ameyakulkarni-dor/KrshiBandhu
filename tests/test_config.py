import json
import time

from app.config import DEFAULT_MAPPING, Settings, SettingsStore


def test_defaults():
    s = Settings()
    assert s.confidence == 0.20 and s.hits == 1 and s.window == 3 and s.cooldown_s == 20
    assert s.person_veto is False
    assert s.mapping == DEFAULT_MAPPING


def test_roundtrip(tmp_path):
    p = tmp_path / "s.json"
    st = SettingsStore(p)
    st.update(volume=40, cooldown_s=30, language="hi")
    st2 = SettingsStore(p)
    s = st2.get()
    assert (s.volume, s.cooldown_s, s.language) == (40, 30, "hi")
    assert json.loads(p.read_text())["volume"] == 40


def test_hits_clamped_to_window():
    s = Settings(window=4, hits=9)
    assert s.hits == 4


def test_invalid_mapping_categories_removed():
    s = Settings(mapping={"boar": ["tiger", "dragon"]})
    assert s.mapping["boar"] == ["tiger"]
    assert s.mapping["deer"] == DEFAULT_MAPPING["deer"]


def test_out_of_range_rejected(tmp_path):
    st = SettingsStore(tmp_path / "s.json")
    try:
        st.update(volume=500)
        assert False, "should fail"
    except Exception:
        pass
    assert st.get().volume == 90


def test_corrupt_file_falls_back(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{not json")
    assert SettingsStore(p).get().volume == 90
