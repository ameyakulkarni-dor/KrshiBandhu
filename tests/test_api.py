import time

import pytest
from fastapi.testclient import TestClient

from app.camera import FakeCamera
from app.engine import Engine
from app.main import create_app
from conftest import ScriptedDetector, det


@pytest.fixture
def setup(tmp_env, frame):
    detector = ScriptedDetector()
    holder = {}

    def factory():
        e = Engine(tmp_env["store"], FakeCamera([frame], fps=20), lambda: detector,
                   tmp_env["player"], tmp_env["storage"])
        holder["engine"] = e
        return e

    app = create_app(factory)
    with TestClient(app) as client:
        deadline = time.time() + 5
        while holder["engine"].status != "running" and time.time() < deadline:
            time.sleep(0.05)
        yield client, holder["engine"], detector, tmp_env


def wait_for(cond, timeout=4):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.05)
    return False


def test_status_and_index(setup):
    client, engine, _, _ = setup
    r = client.get("/api/status").json()
    assert r["status"] == "running" and r["armed"] is True
    assert client.get("/").status_code == 200
    assert client.get("/static/js/app.js").status_code == 200


def test_auto_scare_end_to_end(setup):
    client, engine, detector, env = setup
    detector.next = [det("boar", 0.8)]
    assert wait_for(lambda: env["player"].played)
    assert env["player"].played[0].split("/")[0] in ("tiger", "leopard")
    ev = client.get("/api/events").json()["items"][0]
    assert ev["animal"] == "boar" and ev["sound"] and ev["snapshot"]
    assert client.get(f"/snapshots/{ev['snapshot']}").status_code == 200
    stats = client.get("/api/stats").json()
    assert stats["per_animal"]["boar"] >= 1


def test_plays_sound_even_with_person_present(setup):
    client, engine, detector, env = setup
    detector.next = [det("boar"), det("person")]
    assert wait_for(lambda: client.get("/api/events").json()["total"] >= 1)
    assert wait_for(lambda: len(env["player"].played) >= 1)
    assert env["player"].played[0].split("/")[0] in ("tiger", "leopard")


def test_person_blocks_sound_when_veto_enabled(setup):
    client, engine, detector, env = setup
    client.put("/api/settings", json={"person_veto": True})
    env["player"].played.clear()
    detector.next = [det("boar"), det("person")]
    assert wait_for(lambda: client.get("/api/events").json()["total"] >= 2)
    assert env["player"].played == []


def test_disarm(setup):
    client, engine, detector, env = setup
    assert client.post("/api/arm", json={"armed": False}).json()["armed"] is False
    detector.next = [det("deer")]
    assert wait_for(lambda: client.get("/api/events").json()["total"] >= 1)
    time.sleep(0.5)
    assert env["player"].played == []
    assert client.get("/api/events").json()["items"][0]["suppressed"] == "disarmed"


def test_settings_roundtrip(setup):
    client, engine, _, env = setup
    r = client.put("/api/settings", json={"cooldown_s": 45, "volume": 30, "mapping": {"bird": ["hawk"]}})
    assert r.status_code == 200
    s = client.get("/api/settings").json()
    assert s["cooldown_s"] == 45 and s["volume"] == 30 and s["mapping"]["bird"] == ["hawk"]
    assert engine.trigger.cooldown_s == 45
    assert abs(engine.player.volume - 0.3) < 1e-6
    assert client.put("/api/settings", json={"volume": 999}).status_code == 422


def test_manual_play(setup):
    client, engine, _, env = setup
    r = client.post("/api/play", json={"animal": "bird"})
    assert r.status_code == 200 and r.json()["played"].startswith(("hawk", "eagle"))
    assert client.post("/api/play", json={"animal": "dragon"}).status_code == 400
    assert client.post("/api/play", json={"category": "human"}).status_code == 404   # no files


def test_sound_upload_and_delete(setup):
    client, engine, _, env = setup
    r = client.post("/api/sounds/eagle", files={"file": ("my eagle!.mp3", b"ID3data", "audio/mpeg")})
    assert r.status_code == 200
    lib = client.get("/api/sounds").json()
    assert any(f.startswith("my eagle") for f in lib["eagle"])
    name = [f for f in lib["eagle"] if f.startswith("my eagle")][0]
    assert client.post("/api/sounds/eagle", files={"file": ("x.exe", b"MZ", "application/octet-stream")}).status_code == 400
    assert client.delete(f"/api/sounds/eagle/{name}").status_code == 200
    assert client.delete("/api/sounds/eagle/..%2F..%2Fsettings.json").status_code == 404


def test_websocket_receives_detections(setup):
    client, engine, detector, _ = setup
    detector.next = [det("monkey")]
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "status"
        for _ in range(20):
            m = ws.receive_json()
            if m["type"] == "detections" and m["detections"]:
                assert m["detections"][0]["label"] == "monkey"
                break
        else:
            pytest.fail("no detections message")


def test_live_snapshot(setup):
    client, *_ = setup
    r = client.get("/api/snapshot.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"


def test_feed_frame_client(setup, frame):
    import cv2
    client, engine, detector, _ = setup
    detector.next = [det("boar", 0.75)]
    _, buf = cv2.imencode(".jpg", frame)
    r = client.post("/api/feed_frame", content=buf.tobytes(), headers={"content-type": "image/jpeg"})
    assert r.status_code == 200
    res = r.json()
    assert "detections" in res
    assert res["detections"][0]["label"] == "boar"
