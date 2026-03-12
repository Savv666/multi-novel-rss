#!/usr/bin/env python3
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from ebooklib import epub

DOCS_DIR = Path("docs")
TIMEOUT = 30
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

# Only rebuild if feed exists. If True, always rebuild full EPUB from feed.
ALWAYS_REBUILD = True


def safe_get(url: str) -> str:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def clean_text_lines(lines):
    cleaned = []
    for line in lines:
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        cleaned.append(line)
    return cleaned


def extract_title_from_html(soup: BeautifulSoup, fallback: str) -> str:
    for tag in ["h1", "h2", "title"]:
        el = soup.find(tag)
        if el:
            txt = el.get_text(" ", strip=True)
            if txt:
                return txt
    return fallback


def extract_content_generic(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # Remove script/style/nav/header/footer
    for tag in soup(["script", "style", "nav", "header", "footer", "noscript"]):
        tag.decompose()

    paragraphs = []
    for p in soup.find_all(["p"]):
        txt = p.get_text(" ", strip=True)
        if txt:
            paragraphs.append(txt)

    if not paragraphs:
        raw = soup.get_text("\n", strip=True)
        paragraphs = [x.strip() for x in raw.splitlines() if x.strip()]

    paragraphs = clean_text_lines(paragraphs)

    # Keep a reasonable amount, avoiding huge junk blocks
    paragraphs = [p for p in paragraphs if len(p) > 1]

    if not paragraphs:
        return "<p>No content extracted.</p>"

    return "".join(f"<p>{p}</p>" for p in paragraphs)


def sort_entries(entries):
    def chapter_num(title):
        m = re.search(r"\bchapter\s+(\d+)\b", title or "", re.I)
        return int(m.group(1)) if m else -1

    return sorted(
        entries,
        key=lambda e: (chapter_num(getattr(e, "title", "")), getattr(e, "title", "")),
    )


def build_book_from_feed(feed_path: Path):
    parsed = feedparser.parse(str(feed_path))
    if not parsed.entries:
        print(f"No entries in {feed_path}, skipping.")
        return

    slug = feed_path.parent.name
    feed_title = getattr(parsed.feed, "title", slug.replace("-", " ").title())

    out_epub = feed_path.parent / "book.epub"
    cover_path = feed_path.parent / "cover.jpg"

    book = epub.EpubBook()
    book.set_identifier(slug)
    book.set_title(feed_title)
    book.set_language("en")

    entries = sort_entries(parsed.entries)

    chapters = []
    for idx, entry in enumerate(entries, start=1):
        url = getattr(entry, "link", None)
        title = getattr(entry, "title", f"Chapter {idx}")

        if not url:
            continue

        try:
            html = safe_get(url)
            content_html = extract_content_generic(html)
        except Exception as e:
            content_html = f"<p>Failed to fetch content.</p><p>{str(e)}</p>"

        file_name = f"chapter-{idx}.xhtml"
        chapter = epub.EpubHtml(title=title, file_name=file_name, lang="en")
        chapter.content = f"<h1>{title}</h1>{content_html}"
        book.add_item(chapter)
        chapters.append(chapter)

    if not chapters:
        print(f"No chapter content for {feed_path}, skipping EPUB.")
        return

    book.toc = tuple(chapters)
    book.spine = ["nav"] + chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # Optional cover if already present
    if cover_path.exists():
        try:
            book.set_cover("cover.jpg", cover_path.read_bytes())
        except Exception:
            pass

    epub.write_epub(str(out_epub), book)
    print(f"Wrote {out_epub}")


def main():
    if not DOCS_DIR.exists():
        print("docs directory not found.")
        return

    feeds = list(DOCS_DIR.glob("*/feed.xml"))
    if not feeds:
        print("No feed.xml files found under docs/*/")
        return

    for feed_path in feeds:
        try:
            build_book_from_feed(feed_path)
        except Exception as e:
            print(f"Failed building EPUB for {feed_path}: {e}")


if __name__ == "__main__":
    main()
