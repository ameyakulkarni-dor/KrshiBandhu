from app.trigger import TriggerEngine
from conftest import det


def run(engine, frames, start=0.0, step=0.25):
    out = []
    for i, f in enumerate(frames):
        out.append(engine.update(f, start + i * step))
    return out


def test_fires_after_3_of_5():
    e = TriggerEngine(window=5, hits=3, cooldown_s=20)
    res = run(e, [[det("boar")], [], [det("boar")], [det("boar")]])
    assert [r.fire for r in res] == [None, None, None, "boar"]


def test_no_fire_with_too_few_hits():
    e = TriggerEngine(window=5, hits=3, cooldown_s=20)
    res = run(e, [[det("boar")], [], [], [det("boar")], [], []])
    assert all(r.fire is None for r in res)


def test_cooldown_blocks_then_releases():
    e = TriggerEngine(window=5, hits=3, cooldown_s=20, global_cooldown_s=0)
    fires = []
    for i in range(200):   # 50 seconds at 4 fps
        r = e.update([det("deer")], i * 0.25)
        if r.fire:
            fires.append(i * 0.25)
    assert len(fires) == 3
    assert fires[1] - fires[0] >= 20 and fires[2] - fires[1] >= 20


def test_person_does_not_veto_by_default():
    e = TriggerEngine(window=5, hits=3, cooldown_s=20, person_veto=False)
    res = run(e, [[det("boar"), det("person")]] * 5)
    assert any(r.fire == "boar" for r in res)


def test_person_vetoes_sound_when_enabled():
    e = TriggerEngine(window=5, hits=3, cooldown_s=20, person_veto=True)
    res = run(e, [[det("boar"), det("person")]] * 5)
    assert all(r.fire is None for r in res)
    assert res[-1].suppressed_reason == "person"
    assert res[2].log_animals == ["boar"]   # still logged once


def test_person_memory_keeps_veto_briefly_when_enabled():
    e = TriggerEngine(window=5, hits=3, cooldown_s=20, person_memory=5, person_veto=True)
    run(e, [[det("person")]])
    res = run(e, [[det("boar")]] * 3, start=1)
    assert all(r.fire is None for r in res)
    res = run(e, [[det("boar")]] * 3, start=3)  # person now out of memory
    assert any(r.fire == "boar" for r in res)


def test_disarmed_never_fires_but_logs():
    e = TriggerEngine(window=5, hits=3, cooldown_s=20)
    e.configure(5, 3, 20, armed=False)
    res = run(e, [[det("monkey")]] * 6)
    assert all(r.fire is None for r in res)
    assert sum(len(r.log_animals) for r in res) == 1
    assert res[-1].suppressed_reason == "disarmed"


def test_picks_highest_confidence_and_global_cooldown():
    e = TriggerEngine(window=3, hits=2, cooldown_s=20, global_cooldown_s=4)
    res = run(e, [[det("deer", .5), det("boar", .9)]] * 2)
    assert res[1].fire == "boar"
    # deer is confirmed too, but global cooldown prevents back-to-back sounds
    r = e.update([det("deer", .5)], 1.0)
    assert r.fire is None
    r = e.update([det("deer", .5)], 5.0)
    assert r.fire == "deer"


def test_disabled_animal_ignored():
    e = TriggerEngine(window=5, hits=3, cooldown_s=20)
    e.configure(5, 3, 20, armed=True, enabled=["boar"])
    res = run(e, [[det("bird")]] * 5)
    assert all(r.fire is None for r in res)


def test_window_reconfigure_keeps_recent_history():
    e = TriggerEngine(window=5, hits=3, cooldown_s=20)
    run(e, [[det("boar")], [det("boar")]])
    e.configure(3, 3, 20, armed=True)
    r = e.update([det("boar")], 1.0)
    assert r.fire == "boar"
