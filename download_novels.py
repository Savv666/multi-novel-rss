#!/usr/bin/env python3
import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

DOCS_DIR = Path("docs")
INPUT_FILE = Path("novel-links.txt")
META_FILE = DOCS_DIR / "library.json"
MANUAL_DIR = Path("manual-books")

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"^https?://", "", text)
    text = re.sub(r"^www\.", "", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:80] if text else "novel"

def slug_from_url(url: str) -> str:
    p = urlparse(url)
    path = p.path.strip("/")
    if path:
        parts = path.split("/")
        if p.netloc.endswith("royalroad.com") and len(parts) >= 3 and parts[0] == "fiction":
            return slugify(parts[2])
        if p.netloc.endswith("scribblehub.com") and len(parts) >= 2 and parts[0] == "series":
            return slugify(parts[-1])
        return slugify(parts[0])
    return slugify(p.netloc)

def read_links():
    if not INPUT_FILE.exists():
        return []
    links = []
    for line in INPUT_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        links.append(line)
    seen = set()
    result = []
    for link in links:
        if link not in seen:
            seen.add(link)
            result.append(link)
    return result

def ensure_dirs():
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / ".nojekyll").write_text("", encoding="utf-8")

def file_size_mb(path: Path) -> float:
    return round(path.stat().st_size / (1024 * 1024), 2) if path.exists() else 0.0

def extract_metadata(epub_path: Path):
    try:
        from ebooklib import epub
        import ebooklib
        book = epub.read_epub(str(epub_path))
        title = None
        titles = book.get_metadata("DC", "title")
        if titles:
            title = titles[0][0]
        if not title:
            title = epub_path.stem.replace("-", " ").title()
        chapter_count = None
        try:
            chapter_count = len(list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)))
        except Exception:
            pass
        return title, chapter_count
    except Exception:
        return epub_path.stem.replace("-", " ").title(), None

def extract_cover(epub_path: Path, out_path: Path):
    try:
        from ebooklib import epub
        import ebooklib
        book = epub.read_epub(str(epub_path))
        for item in book.get_items_of_type(ebooklib.ITEM_IMAGE):
            name = item.get_name().lower()
            if "cover" in name or "cvr" in name:
                out_path.write_bytes(item.get_content())
                return True
    except Exception:
        pass
    return False

def download_one(url: str, slug: str):
    folder = DOCS_DIR / slug
    folder.mkdir(parents=True, exist_ok=True)
    epub_path = folder / "book.epub"
    cover_path = folder / "cover.jpg"

    cmd = [
        "fanficfare",
        "-f", "epub",
        "-o", "include_images=true",
        "-o", f"output_filename={epub_path}",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    success = epub_path.exists()

    title = slug.replace("-", " ").title()
    chapter_count = None
    cover_url = None
    if success:
        title, chapter_count = extract_metadata(epub_path)
        if extract_cover(epub_path, cover_path):
            cover_url = f"{slug}/cover.jpg"

    return {
        "slug": slug,
        "title": title,
        "source_url": url,
        "source_site": urlparse(url).netloc.replace("www.", ""),
        "epub_url": f"{slug}/book.epub" if success else None,
        "cover_url": cover_url,
        "chapter_count": chapter_count,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "size_mb": file_size_mb(epub_path),
        "status": "ok" if success else "failed",
        "log_excerpt": ((result.stdout or "") + "\n" + (result.stderr or ""))[-1500:],
        "manual": False,
    }

def import_manual_books():
    items = []
    if not MANUAL_DIR.exists():
        return items
    for epub in sorted(MANUAL_DIR.glob("*.epub")):
        slug = slugify(epub.stem)
        folder = DOCS_DIR / slug
        folder.mkdir(parents=True, exist_ok=True)
        target_epub = folder / "book.epub"
        shutil.copy2(epub, target_epub)
        cover = folder / "cover.jpg"
        title, chapter_count = extract_metadata(target_epub)
        cover_url = f"{slug}/cover.jpg" if extract_cover(target_epub, cover) else None
        items.append({
            "slug": slug,
            "title": title,
            "source_url": "",
            "source_site": "manual",
            "epub_url": f"{slug}/book.epub",
            "cover_url": cover_url,
            "chapter_count": chapter_count,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "size_mb": file_size_mb(target_epub),
            "status": "ok",
            "log_excerpt": "Imported from manual-books/",
            "manual": True,
        })
    return items

def main():
    ensure_dirs()
    items = []
    for url in read_links():
        slug = slug_from_url(url)
        try:
            items.append(download_one(url, slug))
        except Exception as e:
            items.append({
                "slug": slug,
                "title": slug.replace("-", " ").title(),
                "source_url": url,
                "source_site": urlparse(url).netloc.replace("www.", ""),
                "epub_url": None,
                "cover_url": None,
                "chapter_count": None,
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "size_mb": 0.0,
                "status": "failed",
                "log_excerpt": str(e),
                "manual": False,
            })
    items.extend(import_manual_books())
    META_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {META_FILE} with {len(items)} items.")

if __name__ == "__main__":
    main()
