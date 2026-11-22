"""Start KrshiBandhu:  .venv\\Scripts\\python run.py  [--port 8000] [--no-browser]"""
from __future__ import annotations

import argparse
import logging
import os
import threading
import webbrowser

import uvicorn


def main():
    default_host = os.environ.get("HOST", "0.0.0.0")
    default_port = int(os.environ.get("PORT", 8000))

    ap = argparse.ArgumentParser(description="KrshiBandhu farm guardian dashboard")
    ap.add_argument("--host", default=default_host, help=f"Host address (default: {default_host})")
    ap.add_argument("--port", type=int, default=default_port, help=f"Port (default: {default_port})")
    ap.add_argument("--no-browser", action="store_true", default=os.environ.get("NO_BROWSER", "").lower() in ("1", "true"))
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from app.main import app

    local_display_url = f"http://{'127.0.0.1' if args.host == '0.0.0.0' else args.host}:{args.port}"
    print(f"\n=======================================================")
    print(f"  🌾 KrshiBandhu AI Farm Guardian is Running")
    print(f"  🌐 Local URL:     {local_display_url}")
    print(f"  📱 Network/Cloud: http://0.0.0.0:{args.port} (or your domain/IP)")
    print(f"  Press Ctrl+C to stop.")
    print(f"=======================================================\n")

    if not args.no_browser and os.environ.get("HEADLESS", "").lower() not in ("1", "true"):
        def try_open():
            try:
                webbrowser.open(local_display_url)
            except Exception:
                pass
        threading.Timer(2.0, try_open).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
