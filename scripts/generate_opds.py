import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import quote
import xml.etree.ElementTree as ET

DOCS_DIR = Path("docs")
LIBRARY_FILE = DOCS_DIR / "library.json"
SETTINGS_FILE = Path("data") / "settings.json"
OPDS_ROOT_FILE = DOCS_DIR / "opds.xml"
OPDS_DIR = DOCS_DIR / "opds"
DEFAULT_SITE_URL = "https://savv666.github.io/Epub-Server/"

ATOM = "http://www.w3.org/2005/Atom"
ET.register_namespace("", ATOM)


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_iso(value: str | None) -> str:
    if not value:
        return now_iso()
    text = str(value).strip()
    if not text:
        return now_iso()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except ValueError:
        return now_iso()


def site_url() -> str:
    custom = os.getenv("SITE_URL", "").strip()
    if custom:
        return custom.rstrip("/") + "/"
    repo = os.getenv("GITHUB_REPOSITORY", "").strip()
    if "/" in repo:
        owner, name = repo.split("/", 1)
        return f"https://{owner}.github.io/{name}/"
    return DEFAULT_SITE_URL


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "item"


def cover_mime(url: str) -> str | None:
    ext = Path(url.lower()).suffix
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }.get(ext)


def abs_url(base: str, rel: str) -> str:
    return base.rstrip("/") + "/" + rel.lstrip("/")


def entry_id(feed_name: str, novel_slug: str, epub_path: str) -> str:
    key = f"{feed_name}|{novel_slug}|{epub_path}"
    return "urn:epub-server:" + hashlib.sha256(key.encode("utf-8")).hexdigest()


def add_text(parent, name: str, value: str):
    ET.SubElement(parent, f"{{{ATOM}}}{name}").text = value


def add_link(parent, **attrs):
    ET.SubElement(parent, f"{{{ATOM}}}link", attrs)


def build_feed(title: str, feed_id: str, updated: str, kind: str):
    feed = ET.Element(f"{{{ATOM}}}feed")
    add_text(feed, "title", title)
    add_text(feed, "id", feed_id)
    add_text(feed, "updated", updated)
    add_link(feed, rel="self", href=feed_id, type=f"application/atom+xml;profile=opds-catalog;kind={kind}")
    return feed


def download_records(library: dict):
    records = []
    novels = library.get("novels", []) if isinstance(library, dict) else []
    for novel in novels:
        title = novel.get("title") or novel.get("name") or novel.get("slug") or "Unknown Novel"
        slug = novel.get("slug") or slugify(str(title))
        status = str(novel.get("status", ""))
        source = novel.get("source") or novel.get("site") or novel.get("website") or "Unknown Source"
        cover = novel.get("cover") or novel.get("cover_path") or ""
        created = novel.get("created_at")
        updated = novel.get("last_updated")
        for d in novel.get("downloads", []):
            epub = d.get("epub") or d.get("epub_path") or d.get("path") or ""
            if not epub:
                continue
            rec = {
                "novel_title": title,
                "novel_slug": slug,
                "status": status,
                "source": str(source),
                "cover": str(cover),
                "summary": str(d.get("summary") or d.get("description") or novel.get("summary") or ""),
                "epub": str(epub),
                "start": int(d.get("start_chapter") or d.get("chapter_start") or 0),
                "end": int(d.get("end_chapter") or d.get("chapter_end") or 0),
                "updated": ensure_iso(d.get("created_at") or updated or created),
                "created_raw": d.get("created_at") or updated or created or now_iso(),
            }
            records.append(rec)
    records.sort(key=lambda x: x["updated"], reverse=True)
    return records


def write_xml(path: Path, root):
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def main():
    base = site_url()
    settings = load_json(SETTINGS_FILE, {})
    latest_limit = int(settings.get("opds_latest_limit", 50) or 50)
    all_limit = int(settings.get("opds_all_limit", 0) or 0)
    library = load_json(LIBRARY_FILE, {})

    OPDS_DIR.mkdir(parents=True, exist_ok=True)
    for old in OPDS_DIR.rglob("*.xml"):
        old.unlink()

    records = download_records(library)
    generated = 0

    nav = build_feed("OPDS Catalogue", abs_url(base, "opds.xml"), now_iso(), "navigation")
    for name, label in [
        ("latest.xml", "Latest EPUB Batches"),
        ("novels.xml", "Novels"),
        ("sites.xml", "Source Sites"),
        ("status-built.xml", "Built/Complete"),
        ("status-partial.xml", "Partial/Locked/Failed"),
        ("all-epubs.xml", "All EPUB Batches"),
    ]:
        e = ET.SubElement(nav, f"{{{ATOM}}}entry")
        add_text(e, "title", label)
        add_text(e, "id", abs_url(base, f"opds/{name}"))
        add_text(e, "updated", now_iso())
        add_link(e, rel="subsection", href=abs_url(base, f"opds/{name}"), type="application/atom+xml;profile=opds-catalog;kind=acquisition" if name != "novels.xml" and name != "sites.xml" else "application/atom+xml;profile=opds-catalog;kind=navigation")
    write_xml(OPDS_ROOT_FILE, nav)

    def make_acq(path: Path, title: str, items: list[dict]):
        nonlocal generated
        feed = build_feed(title, abs_url(base, str(path).replace("docs/", "")), now_iso(), "acquisition")
        for r in items:
            e = ET.SubElement(feed, f"{{{ATOM}}}entry")
            rng = f"Ch {r['start']}-{r['end']}" if r["start"] or r["end"] else "EPUB"
            add_text(e, "title", f"{r['novel_title']} - {rng}")
            add_text(e, "id", entry_id(title, r["novel_slug"], r["epub"]))
            add_text(e, "updated", r["updated"])
            add_text(e, "author", r["source"])
            add_text(e, "summary", r["summary"] or f"{r['novel_title']} from {r['source']}")
            epub_url = abs_url(base, r["epub"])
            add_link(e, rel="http://opds-spec.org/acquisition", href=epub_url, type="application/epub+zip")
            if r["cover"]:
                c_url = abs_url(base, r["cover"])
                c_type = cover_mime(r["cover"])
                if c_type:
                    add_link(e, rel="http://opds-spec.org/image", href=c_url, type=c_type)
                    add_link(e, rel="http://opds-spec.org/image/thumbnail", href=c_url, type=c_type)
        write_xml(path, feed)
        generated += 1

    make_acq(OPDS_DIR / "latest.xml", "Latest EPUB Batches", records[:latest_limit])
    make_acq(OPDS_DIR / "all-epubs.xml", "All EPUB Batches", records[:all_limit] if all_limit > 0 else records)

    novels_nav = build_feed("Novels", abs_url(base, "opds/novels.xml"), now_iso(), "navigation")
    by_novel = {}
    for r in records:
        by_novel.setdefault(r["novel_slug"], []).append(r)
    for slug, items in sorted(by_novel.items()):
        items.sort(key=lambda x: x["start"])
        novel_path = OPDS_DIR / "novels" / f"{quote(slug)}.xml"
        make_acq(novel_path, f"{items[0]['novel_title']} EPUBs", items)
        e = ET.SubElement(novels_nav, f"{{{ATOM}}}entry")
        add_text(e, "title", items[0]["novel_title"])
        add_text(e, "id", abs_url(base, f"opds/novels/{quote(slug)}.xml"))
        add_text(e, "updated", items[0]["updated"])
        add_link(e, rel="subsection", href=abs_url(base, f"opds/novels/{quote(slug)}.xml"), type="application/atom+xml;profile=opds-catalog;kind=acquisition")
    write_xml(OPDS_DIR / "novels.xml", novels_nav)
    generated += 1

    sites_nav = build_feed("Source Sites", abs_url(base, "opds/sites.xml"), now_iso(), "navigation")
    by_site = {}
    for r in records:
        by_site.setdefault(slugify(r["source"]), []).append(r)
    for site_slug, items in sorted(by_site.items()):
        site_path = OPDS_DIR / "sites" / f"{site_slug}.xml"
        make_acq(site_path, f"{items[0]['source']} EPUBs", items)
        e = ET.SubElement(sites_nav, f"{{{ATOM}}}entry")
        add_text(e, "title", items[0]["source"])
        add_text(e, "id", abs_url(base, f"opds/sites/{site_slug}.xml"))
        add_text(e, "updated", items[0]["updated"])
        add_link(e, rel="subsection", href=abs_url(base, f"opds/sites/{site_slug}.xml"), type="application/atom+xml;profile=opds-catalog;kind=acquisition")
    write_xml(OPDS_DIR / "sites.xml", sites_nav)
    generated += 1

    built = [r for r in records if any(k in r["status"].lower() for k in ["built", "complete"])]
    partial = [r for r in records if any(k in r["status"].lower() for k in ["partial", "lock", "fail", "error"]) ]
    make_acq(OPDS_DIR / "status-built.xml", "Built/Complete EPUBs", built)
    make_acq(OPDS_DIR / "status-partial.xml", "Partial/Problem EPUBs", partial)

    print("Generated docs/opds.xml")
    print(f"Generated {generated} OPDS feeds")
    print(f"OPDS root URL: {abs_url(base, 'opds.xml')}")


if __name__ == "__main__":
    main()
