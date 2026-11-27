#!/usr/bin/env python3
"""PDF del saggio (skill /ghost-writer:export-pdf), con ReportLab.

  python3 export_pdf.py .            italiano: saggio.md → manuscript/l-universo-a-minima-energia.pdf
  python3 export_pdf.py . --lang en  inglese:  essay.md → manuscript/the-universe-at-minimum-energy.pdf

A4, serif (Liberation Serif, stesse metriche di Times New Roman), 11 pt, giustificato.
Copertina, indice con numeri di pagina, un capitolo per pagina, piè di pagina con titolo e numero.
Il parser del markdown (parse_book) è condiviso con export_epub.py.
"""
import json
import re
import sys
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

SOURCES = {"it": "saggio.md", "en": "essay.md"}
FONT_DIR = Path("/usr/share/fonts/truetype/liberation")


# ─── Markdown → struttura del libro ──────────────────────────────────────────

def slug(text):
    t = text.lower().replace("'", "-")
    t = re.sub(r"[àá]", "a", t); t = re.sub(r"[èé]", "e", t); t = re.sub(r"[ìí]", "i", t)
    t = re.sub(r"[òó]", "o", t); t = re.sub(r"[ùú]", "u", t)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")

def parse_book(md_path):
    """→ {title, subtitle, front: [blocks], chapters: [{part, title, blocks}], credits: [lines]}
    blocks: ("p", text) · ("h", text) · ("quote", [lines]) · ("li", n, text)."""
    text = Path(md_path).read_text(encoding="utf-8")
    body, _, credits = text.rpartition("\n---\n")
    credits = [l.strip() for l in credits.strip().splitlines() if l.strip()]
    if not all(l.startswith("*") for l in credits):          # nessun blocco di crediti finale
        body, credits = text, []
    book = {"title": "", "subtitle": "", "front": [], "chapters": [], "credits": credits}
    cur = None
    for para in re.split(r"\n\s*\n", body.strip()):
        lines = [l for l in para.splitlines() if l.strip()]
        first = lines[0].strip()
        if first == "---":
            continue
        if first.startswith("# "):
            book["title"] = first[2:].strip()
            for l in lines[1:]:
                if l.startswith("## "):
                    book["subtitle"] = l[3:].strip()
            continue
        if first.startswith("## "):
            cur = {"part": first[3:].strip(), "title": "", "blocks": []}
            book["chapters"].append(cur)
            rest = lines[1:]
            if rest and rest[0].startswith("### "):
                cur["title"] = rest[0][4:].strip()
            continue
        if first.startswith("### ") and cur is not None and not cur["title"] and not cur["blocks"]:
            cur["title"] = first[4:].strip(); continue
        target = cur["blocks"] if cur is not None else book["front"]
        if first.startswith("#"):
            target.append(("h", re.sub(r"^#+\s*", "", first)))
        elif first.startswith(">"):
            target.append(("quote", [re.sub(r"^\s*>\s?", "", l) for l in lines]))
        elif re.match(r"^\d+\.\s", first):
            m = re.match(r"^(\d+)\.\s+(.*)$", " ".join(l.strip() for l in lines))
            target.append(("li", int(m.group(1)), m.group(2)))
        else:
            target.append(("p", " ".join(l.strip() for l in lines)))
    return book

def inline_markup(text):
    """Markdown in linea → markup minimale (b, i, code), già con escape XML."""
    t = escape(text)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*(.+?)\*\*(?!\*)", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    return t

def load_config(project_dir):
    return json.loads((Path(project_dir) / "book.config.json").read_text(encoding="utf-8"))

def author_of(config):
    a = config.get("author")
    return a.get("name") if isinstance(a, dict) else (a or "")

def output_name(book, ext):
    return f"manuscript/{slug(book['title'])}.{ext}"


# ─── PDF ─────────────────────────────────────────────────────────────────────

def export_pdf(project_dir, lang="it"):
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.fonts import addMapping
    from reportlab.platypus import (BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer)
    from reportlab.platypus.tableofcontents import TableOfContents

    project_dir = Path(project_dir)
    config = load_config(project_dir)
    book = parse_book(project_dir / SOURCES[lang])
    author = author_of(config)

    for name, f in [("Serif", "LiberationSerif-Regular.ttf"), ("Serif-Bold", "LiberationSerif-Bold.ttf"),
                    ("Serif-Italic", "LiberationSerif-Italic.ttf"), ("Serif-BoldItalic", "LiberationSerif-BoldItalic.ttf"),
                    ("Mono", "LiberationMono-Regular.ttf")]:
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / f)))
    addMapping("Serif", 0, 0, "Serif"); addMapping("Serif", 1, 0, "Serif-Bold")
    addMapping("Serif", 0, 1, "Serif-Italic"); addMapping("Serif", 1, 1, "Serif-BoldItalic")

    S = {
        "cover_title": ParagraphStyle("ct", fontName="Serif", fontSize=30, leading=36, alignment=TA_CENTER),
        "cover_sub": ParagraphStyle("cs", fontName="Serif-Italic", fontSize=15, leading=20, alignment=TA_CENTER),
        "cover_author": ParagraphStyle("ca", fontName="Serif", fontSize=14, leading=18, alignment=TA_CENTER),
        "small_c": ParagraphStyle("sc", fontName="Serif", fontSize=9.5, leading=13, alignment=TA_CENTER),
        "part": ParagraphStyle("pt", fontName="Serif", fontSize=12, leading=16, alignment=TA_LEFT, spaceAfter=4, textColor="#666666"),
        "chapter": ParagraphStyle("ch", fontName="Serif", fontSize=20, leading=25, alignment=TA_LEFT, spaceAfter=18),
        "h": ParagraphStyle("h", fontName="Serif-Bold", fontSize=12, leading=16, spaceBefore=12, spaceAfter=6),
        "body": ParagraphStyle("b", fontName="Serif", fontSize=11, leading=15.5, alignment=TA_JUSTIFY, spaceAfter=7, firstLineIndent=0),
        "li": ParagraphStyle("li", fontName="Serif", fontSize=11, leading=15.5, alignment=TA_JUSTIFY, spaceAfter=6, leftIndent=18, bulletIndent=4),
        "quote": ParagraphStyle("q", fontName="Serif-Italic", fontSize=11, leading=15.5, alignment=TA_LEFT, leftIndent=36, rightIndent=36, spaceAfter=14),
        "toc_title": ParagraphStyle("tt", fontName="Serif", fontSize=20, leading=25, spaceAfter=18),
    }
    toc_title = "Indice" if lang == "it" else "Contents"

    def para(text, style):
        t = inline_markup(text).replace("<code>", '<font face="Mono">').replace("</code>", "</font>")
        return Paragraph(t, style)

    class BookDocument(BaseDocTemplate):
        def __init__(self, filename, **kw):
            super().__init__(filename, pagesize=A4, leftMargin=2.6 * cm, rightMargin=2.6 * cm,
                             topMargin=2.5 * cm, bottomMargin=2.5 * cm, title=book["title"], author=author, **kw)
            frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
            self.addPageTemplates([PageTemplate("cover", [frame]), PageTemplate("page", [frame], onPage=self.footer)])

        def footer(self, canvas, doc):
            canvas.saveState()
            canvas.setFont("Serif-Italic", 8.5); canvas.setFillColor("#777777")
            canvas.drawString(self.leftMargin, 1.4 * cm, book["title"])
            canvas.drawRightString(A4[0] - self.rightMargin, 1.4 * cm, str(doc.page))
            canvas.restoreState()

        def afterFlowable(self, f):
            if isinstance(f, Paragraph) and getattr(f, "_toc", None):
                self.notify("TOCEntry", (0, f._toc, self.page))

    from reportlab.platypus import NextPageTemplate
    story = [Spacer(1, 6 * cm), para(book["title"], S["cover_title"]), Spacer(1, 0.6 * cm),
             para(book["subtitle"], S["cover_sub"]), Spacer(1, 2.4 * cm), para(author, S["cover_author"]),
             Spacer(1, 7 * cm), para(f"© {author} · {config.get('license', '')}", S["small_c"]),
             NextPageTemplate("page"), PageBreak()]
    for kind, *rest in book["front"]:
        if kind == "quote":
            story += [Spacer(1, 5 * cm)] + [para(l, S["quote"]) for l in rest[0]] + [PageBreak()]
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("t0", fontName="Serif", fontSize=11, leading=17, leftIndent=0)]
    story += [para(toc_title, S["toc_title"]), toc, PageBreak()]
    for ch in book["chapters"]:
        story.append(para(ch["part"], S["part"]))
        title = para(ch["title"], S["chapter"])
        title._toc = escape(f"{ch['part']} — {ch['title']}" if ch["title"] else ch["part"])
        story.append(title)
        for kind, *rest in ch["blocks"]:
            if kind == "p":
                story.append(para(rest[0], S["body"]))
            elif kind == "h":
                story.append(para(rest[0], S["h"]))
            elif kind == "quote":
                story += [para(l, S["quote"]) for l in rest[0]]
            elif kind == "li":
                story.append(Paragraph(inline_markup(rest[1]), S["li"], bulletText=f"{rest[0]}."))
        story.append(PageBreak())
    if book["credits"]:
        story += [Spacer(1, 8 * cm)] + [para(l, S["small_c"]) for l in book["credits"]]
    out = project_dir / output_name(book, "pdf")
    out.parent.mkdir(exist_ok=True)
    BookDocument(str(out)).multiBuild(story)
    print(f"PDF: {out.relative_to(project_dir)}")
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    lang = args[args.index("--lang") + 1] if "--lang" in args else "it"
    export_pdf(args[0] if args and not args[0].startswith("--") else ".", lang)
