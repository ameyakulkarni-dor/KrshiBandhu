"""Detector smoke test: run YOLO-World on sample animal photos.

Usage: .venv\\Scripts\\python tests\\smoke_detector.py [--download]
--download fetches sample photos from Wikimedia Commons into tests/samples/.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SAMPLES = ROOT / "tests" / "samples"

QUERIES = {  # expected canonical label -> commons search
    "deer": "Chital deer Axis axis",
    "boar": "Wild boar Sus scrofa",
    "monkey": "Rhesus macaque",
    "bird": "Rose-ringed parakeet",
    "cattle": "Cow India street",
    "nilgai": "Nilgai Boselaphus tragocamelus",
    "dog": "Golden jackal Canis aureus",
}


def download():
    import httpx
    SAMPLES.mkdir(parents=True, exist_ok=True)
    ua = {"User-Agent": "KrshiBandhu/1.0 (test samples)"}
    with httpx.Client(headers=ua, timeout=60, follow_redirects=True) as c:
        for label, q in QUERIES.items():
            if any(SAMPLES.glob(f"{label}.*")):
                continue
            r = c.get("https://commons.wikimedia.org/w/api.php", params={
                "action": "query", "format": "json", "generator": "search",
                "gsrsearch": f"{q} filetype:bitmap", "gsrnamespace": 6, "gsrlimit": 5,
                "prop": "imageinfo", "iiprop": "url", "iiurlwidth": 800})
            pages = sorted(r.json().get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0))
            for p in pages:
                info = (p.get("imageinfo") or [{}])[0]
                url = info.get("thumburl") or info.get("url")
                if url and url.lower().split("?")[0].endswith((".jpg", ".jpeg", ".png")):
                    (SAMPLES / f"{label}.jpg").write_bytes(c.get(url).content)
                    print("downloaded", label)
                    break


def main():
    if "--download" in sys.argv:
        download()
    import cv2
    from app.detector import Detector

    t0 = time.time()
    d = Detector()
    d.warmup()
    print(f"model ready in {time.time() - t0:.1f}s")
    ok = 0
    files = sorted(SAMPLES.glob("*.jpg"))
    for f in files:
        img = cv2.imread(str(f))
        t = time.time()
        dets = d.detect(img, 0.2)
        ms = (time.time() - t) * 1000
        labels = [(x.label, x.prompt, round(x.confidence, 2)) for x in dets]
        hit = any(x.label == f.stem for x in dets)
        ok += hit
        print(f"{'PASS' if hit else 'MISS'} {f.stem:8s} {ms:6.0f} ms  {labels}")
    print(f"\n{ok}/{len(files)} samples detected with the expected label")


if __name__ == "__main__":
    main()
