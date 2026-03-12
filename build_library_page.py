#!/usr/bin/env python3
import json
import time
from pathlib import Path
from jinja2 import Template

DOCS_DIR = Path("docs")
META_FILE = DOCS_DIR / "library.json"
OUTPUT_FILE = DOCS_DIR / "index.html"

HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Novel Library</title>
  <style>
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#0f1115; color:#fff; }
    .wrap { max-width:1100px; margin:0 auto; padding:20px; }
    h1 { margin:0 0 16px; font-size:32px; }
    .topbar { position:sticky; top:0; background:#0f1115; padding:12px 0; z-index:10; }
    .search { width:100%; padding:14px 16px; border-radius:14px; border:1px solid #2b2f36; background:#171a20; color:#fff; font-size:16px; box-sizing:border-box; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); gap:18px; margin-top:20px; }
    .card { background:#171a20; border:1px solid #262b33; border-radius:18px; overflow:hidden; box-shadow:0 6px 24px rgba(0,0,0,.25); display:flex; flex-direction:column; }
    .cover { width:100%; aspect-ratio:3/4; background:#222831; object-fit:cover; }
    .cover-placeholder { width:100%; aspect-ratio:3/4; display:flex; align-items:center; justify-content:center; background:#222831; color:#9aa4b2; font-size:14px; }
    .content { padding:14px; display:flex; flex-direction:column; gap:8px; }
    .title { font-size:18px; font-weight:700; line-height:1.3; }
    .meta { color:#b2bcc8; font-size:14px; line-height:1.5; }
    .status-ok { color:#57d38c; } .status-failed { color:#ff7b72; }
    .buttons { display:flex; gap:10px; margin-top:8px; flex-wrap:wrap; }
    .btn { display:inline-block; text-decoration:none; padding:10px 12px; border-radius:12px; background:#2d6cdf; color:white; font-size:14px; font-weight:600; }
    .btn.secondary { background:#2a2f37; }
    .pill { display:inline-block; padding:4px 8px; border-radius:999px; font-size:12px; background:#2a2f37; color:#d4d9df; }
    .footer { color:#96a0ad; font-size:13px; margin-top:24px; }
    .hidden { display:none !important; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <h1>Novel Library</h1>
      <input id="search" class="search" placeholder="Search novels..." />
    </div>
    <div class="grid" id="grid">
      {% for item in items %}
      <div class="card" data-search="{{ (item.title ~ ' ' ~ item.source_site ~ ' ' ~ item.slug)|lower }}">
        {% if item.cover_url %}
          <img class="cover" src="{{ item.cover_url }}" alt="{{ item.title }}">
        {% else %}
          <div class="cover-placeholder">No cover</div>
        {% endif %}
        <div class="content">
          <div class="title">{{ item.title }}</div>
          <div class="meta">Source: {{ item.source_site }}</div>
          <div class="meta">Chapters: {{ item.chapter_count if item.chapter_count is not none else 'Unknown' }}</div>
          <div class="meta">Size: {{ '%.2f' % item.size_mb }} MB</div>
          <div class="meta">Updated: {{ item.updated_at }}</div>
          <div class="meta">Status: <span class="{{ 'status-ok' if item.status == 'ok' else 'status-failed' }}">{{ item.status }}</span></div>
          <div>{% if item.manual %}<span class="pill">Manual EPUB</span>{% else %}<span class="pill">Auto</span>{% endif %}</div>
          <div class="buttons">
            {% if item.epub_url %}<a class="btn" href="{{ item.epub_url }}">Download EPUB</a>{% endif %}
            {% if item.source_url %}<a class="btn secondary" href="{{ item.source_url }}">Source</a>{% endif %}
            <a class="btn secondary" href="{{ item.slug }}/feed.xml">RSS</a>
          </div>
        </div>
      </div>
      {% endfor %}
    </div>
    <div class="footer">
      Add auto-download links in <code>novel-links.txt</code>.<br>
      Put your own EPUBs in <code>manual-books/</code> for sites that do not download cleanly.<br>
      Auto-generated {{ now }}.
    </div>
  </div>
  <script>
    const input = document.getElementById('search');
    const cards = Array.from(document.querySelectorAll('.card'));
    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      for (const card of cards) {
        const hay = card.dataset.search || '';
        card.classList.toggle('hidden', q && !hay.includes(q));
      }
    });
  </script>
</body>
</html>
"""

def main():
    items = []
    if META_FILE.exists():
        items = json.loads(META_FILE.read_text(encoding="utf-8"))
    items.sort(key=lambda x: (x.get("title") or "").lower())
    html = Template(HTML_TEMPLATE).render(items=items, now=time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()))
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"Wrote {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
