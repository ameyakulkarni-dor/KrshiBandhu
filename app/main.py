"""FastAPI application: REST API, MJPEG stream, WebSocket and static dashboard."""
from __future__ import annotations

import asyncio
import base64
import logging
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import ANIMALS, SNAPSHOT_DIR, SOUND_CATEGORIES, STATIC_DIR, SettingsStore
from .engine import Engine
from .notifier import send_telegram

log = logging.getLogger("krshibandhu")
SAFE_NAME = re.compile(r"[^A-Za-z0-9_.\- ]+")


class ArmBody(BaseModel):
    armed: bool


class PlayBody(BaseModel):
    animal: Optional[str] = None
    category: Optional[str] = None


def default_engine_factory() -> Engine:
    from .camera import Camera
    from .detector import Detector
    from .notifier import TelegramNotifier
    from .sound import SoundLibrary, SoundPlayer
    from .storage import Storage

    store = SettingsStore()
    s = store.get()
    storage = Storage()
    storage.cleanup(s.retention_days)
    player = SoundPlayer(SoundLibrary())
    notifier = TelegramNotifier(
        lambda: (store.get().telegram_enabled, store.get().telegram_token, store.get().telegram_chat_id),
        on_sent=storage.mark_notified)
    return Engine(store, Camera(s.camera_index), Detector, player, storage, notifier)


def create_app(engine_factory: Callable[[], Engine] = default_engine_factory) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = engine_factory()
        app.state.engine = engine
        engine.start(asyncio.get_running_loop())

        async def housekeeping():
            while True:
                await asyncio.sleep(6 * 3600)
                engine.storage.cleanup(engine.store.get().retention_days)

        task = asyncio.create_task(housekeeping())
        yield
        task.cancel()
        engine.stop()

    app = FastAPI(title="KrshiBandhu", lifespan=lifespan)

    def eng() -> Engine:
        return app.state.engine

    # ---------------- status / control ----------------
    @app.get("/api/status")
    def status():
        return eng().status_dict()

    @app.post("/api/arm")
    def arm(body: ArmBody):
        s = eng().store.update(armed=body.armed)
        eng().apply_settings(s)
        eng().broadcast({"type": "status", **eng().status_dict()})
        return {"armed": s.armed}

    @app.post("/api/play")
    def play(body: PlayBody):
        if body.animal and body.animal not in ANIMALS:
            raise HTTPException(400, "Unknown animal")
        if body.category and body.category not in SOUND_CATEGORIES:
            raise HTTPException(400, "Unknown sound category")
        sound = eng().manual_play(body.animal, body.category)
        if not sound:
            raise HTTPException(404, "No sound files available for this selection")
        return {"played": sound}

    @app.post("/api/stop-sound")
    def stop_sound():
        eng().player.stop()
        return {"ok": True}

    # ---------------- settings ----------------
    @app.get("/api/settings")
    def get_settings():
        data = eng().store.get().model_dump()
        data["animals"] = ANIMALS
        data["sound_categories"] = SOUND_CATEGORIES
        return data

    @app.put("/api/settings")
    def put_settings(changes: dict):
        try:
            s = eng().store.update(**changes)
        except Exception as e:
            raise HTTPException(422, str(e))
        eng().apply_settings(s)
        return s.model_dump()

    @app.get("/api/cameras")
    def cameras():
        from .camera import list_cameras_info
        current = eng().store.get().camera_index
        found = list_cameras_info()
        found_indices = {c["index"] for c in found}
        if current not in found_indices:
            found.insert(0, {"index": current, "name": f"Camera {current}"})
        found.sort(key=lambda x: x["index"])
        return {"cameras": found, "current": current}

    @app.post("/api/telegram/test")
    def telegram_test():
        s = eng().store.get()
        ok, msg = send_telegram(s.telegram_token, s.telegram_chat_id,
                                "✅ KrshiBandhu test alert - Telegram is working!")
        if not ok:
            raise HTTPException(400, msg)
        return {"ok": True}

    # ---------------- sounds ----------------
    @app.get("/api/sounds")
    def sounds():
        return eng().player.library.listing()

    @app.get("/api/sounds/{category}/{name}")
    def sound_file(category: str, name: str):
        if category not in SOUND_CATEGORIES:
            raise HTTPException(404)
        p = (eng().player.library.root / category / name).resolve()
        if p.parent != (eng().player.library.root / category).resolve() or not p.exists():
            raise HTTPException(404)
        return FileResponse(p)

    @app.post("/api/sounds/{category}")
    async def upload_sound(category: str, file: UploadFile = File(...)):
        if category not in SOUND_CATEGORIES:
            raise HTTPException(400, "Unknown category")
        name = SAFE_NAME.sub("_", Path(file.filename or "sound.mp3").name)
        if Path(name).suffix.lower() not in {".mp3", ".wav", ".ogg", ".flac"}:
            raise HTTPException(400, "Only MP3, WAV, OGG or FLAC files are allowed")
        data = await file.read()
        if len(data) > 15 * 1024 * 1024:
            raise HTTPException(400, "File too large (max 15 MB)")
        dest = eng().player.library.root / category / name
        dest.write_bytes(data)
        return {"saved": f"{category}/{name}"}

    @app.post("/api/sounds/{category}/{name}/play")
    def play_sound(category: str, name: str):
        p = eng().player.library.root / category / name
        if category not in SOUND_CATEGORIES or not p.exists():
            raise HTTPException(404)
        return {"played": eng().player.play_file(p)}

    @app.delete("/api/sounds/{category}/{name}")
    def delete_sound(category: str, name: str):
        p = (eng().player.library.root / category / name).resolve()
        if category not in SOUND_CATEGORIES or p.parent != (eng().player.library.root / category).resolve() or not p.exists():
            raise HTTPException(404)
        p.unlink()
        return {"deleted": f"{category}/{name}"}

    # ---------------- events / stats ----------------
    @app.get("/api/events")
    def events(limit: int = 50, offset: int = 0, animal: Optional[str] = None):
        return eng().storage.list_events(min(limit, 500), max(offset, 0), animal or None)

    @app.get("/api/stats")
    def stats(range: str = "24h"):
        hours = {"24h": 24, "7d": 168, "30d": 720}.get(range, 24)
        return eng().storage.stats(hours)

    @app.get("/snapshots/{day}/{name}")
    def snapshot(day: str, name: str):
        root = eng().storage.snapshot_dir.resolve()
        p = (root / day / name).resolve()
        if root not in p.parents or not p.exists():
            raise HTTPException(404)
        return FileResponse(p)

    # ---------------- live ----------------
    @app.get("/api/stream")
    def stream():
        def gen():
            boundary = b"--frame\r\n"
            while True:
                jpg = eng().stream_frame()
                if jpg is None:
                    time.sleep(0.3)
                    continue
                yield boundary + b"Content-Type: image/jpeg\r\nContent-Length: " + \
                    str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n"
                time.sleep(1 / 15)
        return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

    @app.get("/api/snapshot.jpg")
    def live_snapshot():
        jpg = eng().stream_frame(85)
        if jpg is None:
            raise HTTPException(503, "No camera frame yet")
        from fastapi import Response
        return Response(jpg, media_type="image/jpeg")

    @app.post("/api/feed_frame")
    async def feed_frame(request: Request):
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
            b64_img = data.get("image", "")
            if "," in b64_img:
                b64_img = b64_img.split(",", 1)[1]
            try:
                raw = base64.b64decode(b64_img)
            except Exception:
                raise HTTPException(400, "Invalid base64 payload")
        else:
            raw = await request.body()

        if not raw:
            raise HTTPException(400, "Empty image frame payload")

        nparr = np.frombuffer(raw, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if frame is None:
            raise HTTPException(400, "Failed to decode image")

        res = eng().process_client_frame(frame)
        return res

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        q = eng().subscribe()

        async def send_loop():
            await websocket.send_json({"type": "status", **eng().status_dict()})
            while True:
                try:
                    msg = await asyncio.wait_for(q.get(), timeout=5)
                except asyncio.TimeoutError:
                    msg = {"type": "status", **eng().status_dict()}
                await websocket.send_json(msg)

        async def receive_loop():
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "frame":
                    b64_img = data.get("image", "")
                    if "," in b64_img:
                        b64_img = b64_img.split(",", 1)[1]
                    try:
                        raw = base64.b64decode(b64_img)
                        nparr = np.frombuffer(raw, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if frame is not None:
                            eng().process_client_frame(frame)
                    except Exception as e:
                        log.debug("Failed decoding client frame: %s", e)

        send_task = asyncio.create_task(send_loop())
        receive_task = asyncio.create_task(receive_loop())
        try:
            done, pending = await asyncio.wait(
                [send_task, receive_task],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            eng().unsubscribe(q)

    # ---------------- static ----------------
    @app.get("/")
    def index():
        return FileResponse(STATIC_DIR / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


# Export top-level "app" for Vercel, Gunicorn, Uvicorn, and ASGI servers
app = create_app()
