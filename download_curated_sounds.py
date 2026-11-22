import httpx
import time
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOUNDS = ROOT / "sounds"
API = "https://commons.wikimedia.org/w/api.php"

# Strict Wikimedia User-Agent format: AppName/Version (https://...; contact@...)
HEADERS = {
    "User-Agent": "KrshiBandhuApp/1.0 (https://github.com/krshibandhu; farm.deterrent.app@gmail.com) httpx/0.28"
}

ITEMS = [
    ("dogs", "File:Seis perros ladrando.wav"),
    ("dogs", "File:A dog making noises and barking.flac"),
    ("hawk", "File:Accipiter cooperii - Cooper's Hawk XC483616.mp3"),
    ("hawk", "File:Parabuteo unicinctus - Harris's Hawk XC202066.mp3"),
    ("eagle", "File:Yellowstone sound library - Bald Eagle - 001.mp3"),
    ("eagle", "File:Yellowstone sound library - Bald Eagle - 002.mp3"),
    ("human", "File:Scream-c.wav"),
    ("human", "File:Scream-e.wav"),
]

def clean_name(title: str) -> str:
    name = title.replace("File:", "")
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name)
    return name

def main():
    # Remove files that are HTML error responses (< 10000 bytes)
    for p in SOUNDS.rglob("*"):
        if p.is_file() and p.stat().st_size < 10000:
            print(f"Removing corrupted file: {p.name}")
            p.unlink()

    with httpx.Client(headers=HEADERS, timeout=60, follow_redirects=True) as client:
        for cat, title in ITEMS:
            time.sleep(3)
            cat_dir = SOUNDS / cat
            cat_dir.mkdir(parents=True, exist_ok=True)
            fname = clean_name(title)
            dest = cat_dir / fname
            if dest.exists() and dest.stat().st_size > 10000:
                print(f"[{cat}] Already exists: {fname}")
                continue
            try:
                r = client.get(API, params={
                    "action": "query",
                    "format": "json",
                    "titles": title,
                    "prop": "imageinfo",
                    "iiprop": "url|size"
                })
                pages = r.json().get("query", {}).get("pages", {})
                for p in pages.values():
                    url = (p.get("imageinfo") or [{}])[0].get("url")
                    if not url:
                        continue
                    time.sleep(3)
                    resp = client.get(url)
                    if len(resp.content) > 10000:
                        dest.write_bytes(resp.content)
                        print(f"[{cat}] Successfully saved {fname} ({len(resp.content)} bytes)")
                    else:
                        print(f"[{cat}] Got small/error response for {fname} ({len(resp.content)} bytes)")
            except Exception as e:
                print(f"[{cat}] Error {title}: {e}")

if __name__ == "__main__":
    main()
