"""Start KrshiBandhu:  .venv\\Scripts\\python run.py  [--port 8000] [--no-browser]"""
from __future__ import annotations

import argparse
import logging
import threading
import webbrowser

import uvicorn


def main():
    ap = argparse.ArgumentParser(description="KrshiBandhu farm guardian dashboard")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    from app.main import create_app

    url = f"http://{args.host}:{args.port}"
    print(f"\n  KrshiBandhu running at {url}\n  Press Ctrl+C to stop.\n")
    if not args.no_browser:
        threading.Timer(2.0, lambda: webbrowser.open(url)).start()
    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
