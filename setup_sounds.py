"""Download freely-licensed predator / deterrent sounds from Wikimedia Commons.

Usage:  .venv\\Scripts\\python setup_sounds.py [--per-category 3] [--force]

Only files with free licences (CC0, Public domain, CC-BY, CC-BY-SA) are kept.
Attribution is written to sounds/CREDITS.md.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent
SOUNDS = ROOT / "sounds"
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "KrshiBandhu/1.0 (farm animal deterrent; educational)"}

QUERIES = {
    "tiger": ["tiger roar", "tiger growl", "Panthera tigris sound"],
    "leopard": ["leopard growl", "leopard sound", "Panthera pardus sound"],
    "dogs": ["dog barking", "dogs barking", "barking dog"],
    "hawk": ["hawk call", "red-tailed hawk", "Buteo call"],
    "eagle": ["eagle call", "bald eagle call", "eagle scream"],
    "human": ["man shouting", "shout", "yelling voice"],
}
ALLOWED_EXT = {".ogg", ".oga", ".wav", ".mp3", ".flac"}
FREE = re.compile(r"(cc0|public domain|pd|cc[- ]by(-sa)?)", re.I)


def search(client: httpx.Client, q: str, limit: int = 25):
    r = client.get(API, params={
        "action": "query", "format": "json", "generator": "search",
        "gsrsearch": f"{q} filetype:audio", "gsrnamespace": 6, "gsrlimit": limit,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata|mediatype",
    })
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    return sorted(pages.values(), key=lambda p: p.get("index", 0))


def strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-category", type=int, default=3)
    ap.add_argument("--force", action="store_true", help="download even if category already has files")
    args = ap.parse_args()

    credits = ["# Sound credits\n", "Downloaded from Wikimedia Commons under free licences.\n"]
    total = 0
    with httpx.Client(headers=UA, timeout=60, follow_redirects=True) as client:
        for cat, queries in QUERIES.items():
            d = SOUNDS / cat
            d.mkdir(parents=True, exist_ok=True)
            existing = [p for p in d.iterdir() if p.suffix.lower() in ALLOWED_EXT]
            if existing and not args.force:
                print(f"[{cat}] already has {len(existing)} file(s), skipping (use --force)")
                continue
            got, seen = 0, set()
            credits.append(f"\n## {cat}\n")
            for q in queries:
                if got >= args.per_category:
                    break
                try:
                    results = search(client, q)
                except Exception as e:
                    print(f"[{cat}] search failed for '{q}': {e}")
                    continue
                for p in results:
                    if got >= args.per_category:
                        break
                    info = (p.get("imageinfo") or [{}])[0]
                    url, size = info.get("url"), info.get("size", 0)
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    ext = Path(url).suffix.lower()
                    if ext not in ALLOWED_EXT or size > 8_000_000 or size < 5_000:
                        continue
                    meta = info.get("extmetadata", {})
                    lic = strip_html(meta.get("LicenseShortName", {}).get("value", ""))
                    if not FREE.search(lic):
                        continue
                    artist = strip_html(meta.get("Artist", {}).get("value", "unknown"))[:80]
                    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", Path(url).name)
                    if ext == ".oga":
                        safe = safe[:-4] + ".ogg"
                    dest = d / safe
                    try:
                        data = client.get(url).content
                        dest.write_bytes(data)
                    except Exception as e:
                        print(f"[{cat}] download failed {url}: {e}")
                        continue
                    got += 1
                    total += 1
                    page = info.get("descriptionurl", "")
                    credits.append(f"- `{safe}` — {artist} — {lic} — {page}\n")
                    print(f"[{cat}] + {safe}  ({lic})")
            if got == 0:
                print(f"[{cat}] nothing found - add your own MP3 via the dashboard Settings > Sound library")

    if total:
        (SOUNDS / "CREDITS.md").write_text("".join(credits), encoding="utf-8")
    print(f"\nDone. {total} file(s) downloaded into {SOUNDS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
