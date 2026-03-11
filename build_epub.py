import os
import json
import requests
import feedparser
from ebooklib import epub
from bs4 import BeautifulSoup

DOCS_DIR = "docs"
NOVELS_FILE = "novels.json"

# Change this if your GitHub username or repo name is different
BASE_URL = "https://savv666.github.io/multi-novel-rss"


def fetch_article(url):
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    text = []
    for p in soup.find_all("p"):
        t = p.get_text().strip()
        if t:
            text.append(t)

    if not text:
        body_text = soup.get_text("\n", strip=True)
        text = [line.strip() for line in body_text.splitlines() if line.strip()][:50]

    return "<p>" + "</p><p>".join(text) + "</p>"


def safe_filename(name: str) -> str:
    bad_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*']
    for ch in bad_chars:
        name = name.replace(ch, "_")
    return name[:120]


def build_epub(feed_path, output_path):
    feed = feedparser.parse(feed_path)

    if not feed.entries:
        print(f"No entries found in {feed_path}, skipping EPUB build.")
        return False

    title = getattr(feed.feed, "title", "Novel Book")

    book = epub.EpubBook()
    book.set_identifier(output_path)
    book.set_title(title)
    book.set_language("en")

    chapters = []

    # reversed so older chapters appear first in the EPUB
    for idx, entry in enumerate(reversed(feed.entries), start=1):
        entry_title = getattr(entry, "title", f"Chapter {idx}")
        entry_link = getattr(entry, "link", "")

        try:
            content = fetch_article(entry_link) if entry_link else "<p>No chapter link found.</p>"
        except Exception as e:
            content = f"<p>Failed to fetch chapter content.</p><p>{str(e)}</p>"

        file_name = safe_filename(f"chapter_{idx}_{entry_title}.xhtml")

        c = epub.EpubHtml(
            title=entry_title,
            file_name=file_name
        )

        c.content = f"<h1>{entry_title}</h1>{content}"

        book.add_item(c)
        chapters.append(c)

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav"] + chapters

    epub.write_epub(output_path, book)
    return True


def load_slugs():
    if not os.path.exists(NOVELS_FILE):
        return []

    with open(NOVELS_FILE, "r", encoding="utf-8") as f:
        novels = json.load(f)

    return [n["slug"] for n in novels if "slug" in n]


def write_epub_links_file(slugs):
    txt_path = os.path.join(DOCS_DIR, "epub-links.txt")
    md_path = os.path.join(DOCS_DIR, "epub-links.md")

    txt_lines = []
    md_lines = ["# EPUB Links", ""]

    for slug in slugs:
        epub_path = os.path.join(DOCS_DIR, slug, "book.epub")
        if os.path.exists(epub_path):
            url = f"{BASE_URL}/{slug}/book.epub"
            txt_lines.append(f"{slug}: {url}")
            md_lines.append(f"- {slug}: {url}")

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(txt_lines) + ("\n" if txt_lines else ""))

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    print(f"Wrote {txt_path}")
    print(f"Wrote {md_path}")


def main():
    os.makedirs(DOCS_DIR, exist_ok=True)

    slugs = load_slugs()

    for slug in slugs:
        feed_path = os.path.join(DOCS_DIR, slug, "feed.xml")
        if not os.path.exists(feed_path):
            print(f"Feed not found for {slug}, skipping.")
            continue

        output_path = os.path.join(DOCS_DIR, slug, "book.epub")
        print(f"Building EPUB for {slug}")
        build_epub(feed_path, output_path)

    write_epub_links_file(slugs)


if __name__ == "__main__":
    main()
