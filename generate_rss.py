#!/usr/bin/env python3
import json
import time
from datetime import datetime
from pathlib import Path
from feedgen.feed import FeedGenerator

DOCS_DIR = Path("docs")
META_FILE = DOCS_DIR / "library.json"

def to_rfc822(ts: str) -> str:
    try:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S UTC")
        return dt.strftime("%a, %d %b %Y %H:%M:%S GMT")
    except Exception:
        return time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime())

def build_feed(item: dict):
    slug = item["slug"]
    title = item.get("title") or slug
    fg = FeedGenerator()
    fg.title(f"{title} Updates")
    fg.link(href=item.get("epub_url") or item.get("source_url") or "", rel="self")
    fg.description(f"Automatic updates for {title}.")
    fg.language("en")

    fe = fg.add_entry()
    fe.title(f"Latest update for {title}")
    fe.link(href=item.get("epub_url") or item.get("source_url") or "")
    updated_at = item.get("updated_at") or time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    fe.guid(f"{slug}-{updated_at.replace(' ', 'T')}", permalink=False)
    fe.pubDate(to_rfc822(updated_at))

    desc = []
    if item.get("chapter_count") is not None:
        desc.append(f"Chapters: {item['chapter_count']}")
    desc.append(f"Size: {item.get('size_mb', 0)} MB")
    desc.append(f"Status: {item.get('status', 'unknown')}")
    if item.get("manual"):
        desc.append("Source: manual EPUB")
    fe.description("; ".join(desc))

    out_dir = DOCS_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    fg.rss_file(str(out_dir / "feed.xml"))

def main():
    if not META_FILE.exists():
        print("No library metadata found; skipping RSS generation.")
        return
    items = json.loads(META_FILE.read_text(encoding="utf-8"))
    for item in items:
        try:
            build_feed(item)
        except Exception as e:
            print(f"Failed to build feed for {item.get('slug')}: {e}")
    print("RSS feeds generated.")

if __name__ == "__main__":
    main()
