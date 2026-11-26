#!/usr/bin/env python3
"""EPUB del saggio (skill /ghost-writer:export-epub), con ebooklib.

  python3 export_epub.py .            italiano: saggio.md → manuscript/l-universo-a-minima-energia.epub
  python3 export_epub.py . --lang en  inglese:  essay.md → manuscript/the-universe-at-minimum-energy.epub

Copertina (podcast/cover/cover.jpg), frontespizio, indice, un file XHTML per capitolo.
Usa il parser di export_pdf.py.
"""
import sys
import uuid
from pathlib import Path

from ebooklib import epub

from export_pdf import SOURCES, author_of, inline_markup, load_config, output_name, parse_book

CSS = """
body { font-family: serif; line-height: 1.5; margin: 0 4%; }
h1 { font-weight: normal; font-size: 1.6em; margin: 0.2em 0 1em; }
p.part { color: #666; margin: 2em 0 0; font-size: 0.95em; }
h2 { font-size: 1.05em; margin: 1.6em 0 0.5em; }
p { text-align: justify; margin: 0 0 0.7em; }
blockquote { font-style: italic; margin: 1.5em 2em; }
code { font-family: monospace; font-size: 0.95em; }
.title { text-align: center; margin-top: 30%; }
.title h1 { font-size: 2em; margin-bottom: 0.3em; }
.title p { text-align: center; }
.small { font-size: 0.85em; text-align: center; color: #555; }
"""

def html_inline(text):
    return inline_markup(text).replace("<b>", "<strong>").replace("</b>", "</strong>").replace("<i>", "<em>").replace("</i>", "</em>")

def blocks_html(blocks):
    out = []
    for kind, *rest in blocks:
        if kind == "p":
            out.append(f"<p>{html_inline(rest[0])}</p>")
        elif kind == "h":
            out.append(f"<h2>{html_inline(rest[0])}</h2>")
        elif kind == "quote":
            out.append("<blockquote>" + "<br/>".join(html_inline(l) for l in rest[0]) + "</blockquote>")
        elif kind == "li":
            out.append(f"<p>{rest[0]}. {html_inline(rest[1])}</p>")
    return "\n".join(out)

def export_epub(project_dir, lang="it"):
    project_dir = Path(project_dir)
    config = load_config(project_dir)
    book_md = parse_book(project_dir / SOURCES[lang])
    author = author_of(config)
    book = epub.EpubBook()
    book.set_identifier(f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, 'fatalismoquantico.it/' + lang)}")
    book.set_title(book_md["title"])
    book.set_language(lang)
    book.add_author(author)
    book.add_metadata("DC", "description", book_md["subtitle"])
    book.add_metadata("DC", "rights", f"© {author} · {config.get('license', '')}")
    cover = project_dir / "podcast" / "cover" / "cover.jpg"
    if cover.exists():
        book.set_cover("cover.jpg", cover.read_bytes())
    css = epub.EpubItem(uid="css", file_name="style.css", media_type="text/css", content=CSS)
    book.add_item(css)

    def page(name, title, body):
        item = epub.EpubHtml(title=title, file_name=name, lang=lang)
        item.content = f"<html><head><title>{title}</title></head><body>{body}</body></html>"
        item.add_item(css)
        book.add_item(item)
        return item

    front = "".join(f"<p>{html_inline(t[1])}</p>" for t in book_md["front"] if t[0] == "p")
    epigraph = "".join(blocks_html([t]) for t in book_md["front"] if t[0] == "quote")
    credits = "".join(f'<p class="small">{html_inline(l)}</p>' for l in book_md["credits"])
    title_page = page("title.xhtml", book_md["title"],
                      f'<div class="title"><h1>{html_inline(book_md["title"])}</h1><p><em>{html_inline(book_md["subtitle"])}</em></p>'
                      f'<p>{author}</p>{front}</div>{epigraph}')
    chapters = []
    for i, ch in enumerate(book_md["chapters"], 1):
        label = f"{ch['part']} — {ch['title']}" if ch["title"] else ch["part"]
        body = f'<p class="part">{html_inline(ch["part"])}</p><h1>{html_inline(ch["title"])}</h1>{blocks_html(ch["blocks"])}'
        if i == len(book_md["chapters"]):
            body += f"<hr/>{credits}"
        chapters.append(page(f"c{i:02d}.xhtml", label, body))
    book.toc = chapters
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", title_page] + chapters
    out = project_dir / output_name(book_md, "epub")
    out.parent.mkdir(exist_ok=True)
    epub.write_epub(str(out), book)
    print(f"EPUB: {out.relative_to(project_dir)}")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    lang = args[args.index("--lang") + 1] if "--lang" in args else "it"
    export_epub(args[0] if args and not args[0].startswith("--") else ".", lang)
