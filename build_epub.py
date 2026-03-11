import os
import feedparser
import requests
from ebooklib import epub
from bs4 import BeautifulSoup

DOCS_DIR = "docs"

def fetch_article(url):
    r = requests.get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    text = []
    for p in soup.find_all("p"):
        t = p.get_text().strip()
        if t:
            text.append(t)

    return "<p>" + "</p><p>".join(text) + "</p>"

def build_epub(feed_path, output_path):

    feed = feedparser.parse(feed_path)

    book = epub.EpubBook()
    book.set_title(feed.feed.title)
    book.set_language("en")

    chapters = []

    for entry in reversed(feed.entries):

        content = fetch_article(entry.link)

        c = epub.EpubHtml(
            title=entry.title,
            file_name=f"{entry.title}.xhtml"
        )

        c.content = f"<h1>{entry.title}</h1>{content}"

        book.add_item(c)
        chapters.append(c)

    book.toc = chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    book.spine = ["nav"] + chapters

    epub.write_epub(output_path, book)

def main():

    for folder in os.listdir(DOCS_DIR):

        feed_path = os.path.join(DOCS_DIR, folder, "feed.xml")

        if not os.path.exists(feed_path):
            continue

        output = os.path.join(DOCS_DIR, folder, "book.epub")

        print("Building", folder)

        build_epub(feed_path, output)

if __name__ == "__main__":
    main()
