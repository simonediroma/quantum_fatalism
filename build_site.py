#!/usr/bin/env python3
"""Il sito del libro (skill /ghost-writer:site): una pagina pre-generata per lingua, pronta per GitHub Pages.

  python3 build_site.py            costruisce ogni site*.yaml (site.yaml → docs/, site.it.yaml → docs/it/)
  python3 build_site.py --check    controlla configurazione, file e schede; non scrive nulla

Sezioni: apertura (copertina, occhiello, titolo, frase), il libro con i download, idee chiave,
podcast (episodi + feed, se la pagina ha `podcast`), grafo (schede da graph/cards, se la pagina ha `graph`).
Tutto il contenuto è nell'HTML; il JavaScript serve solo a disegnare il grafo e a navigare le schede.
Nessuna risorsa esterna (font, script), salvo Cloudflare Web Analytics se `analytics.cloudflare_token`
è impostato nel site*.yaml: lo script di Cloudflare non usa cookie.
"""
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
TYPES = {"concepts": ("Concetti", "Concepts"), "terms": ("Termini", "Terms"), "theses": ("Tesi", "Theses"),
         "sources": ("Fonti", "Sources"), "people": ("Persone", "People")}
LABELS = {
    "it": {"listen": "Ascolta", "feed": "Feed RSS per le app di podcast", "minutes": "min", "search": "Cerca…",
           "text": "Nel testo", "not_said": "Il testo non dice", "open": "Punti aperti", "notes": "Note",
           "relations": "Relazioni", "cited_by": "Citata da", "chapter": "Capitolo", "all": "Tutti i capitoli",
           "open_all": "Tutti i punti aperti", "close": "Chiudi", "license": "Licenza", "cover": "Copertina"},
    "en": {"listen": "Listen", "feed": "RSS feed for podcast apps", "minutes": "min", "search": "Search…",
           "text": "In the text", "not_said": "The text does not say", "open": "Open points", "notes": "Notes",
           "relations": "Relations", "cited_by": "Cited by", "chapter": "Chapter", "all": "All chapters",
           "open_all": "All open points", "close": "Close", "license": "License", "cover": "Cover"},
}
e = html.escape


def load(path):
    return yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}

def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    return (yaml.safe_load(m.group(1)) or {}) if m else {}

def md_inline(text):
    t = e(text)
    t = re.sub(r"\*\*(.+?)\*\*(?!\*)", r"<strong>\1</strong>", t)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", t)

def duration(mp3):
    try:
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp3)],
                             capture_output=True, text=True, check=True).stdout
        return round(float(out) / 60)
    except Exception:
        return None


# ─── Dati ────────────────────────────────────────────────────────────────────

def cards():
    out = {}
    for p in sorted((ROOT / "graph" / "cards").glob("*/*.yaml")):
        out[p.stem] = {"type": p.parent.name, **load(p)}
    return out

def chapter_titles():
    state = load(ROOT / "graph" / "chapters.yaml") if (ROOT / "graph" / "chapters.yaml").exists() else {}
    return {int(k): v.get("title", "") for k, v in state.items()}

def src_chapters(src):
    return [int(m.group(1)) for m in re.finditer(r"c(\d+):", str(src or ""))]

def episodes():
    out = []
    for s in sorted((ROOT / "podcast" / "scripts").glob("episode-*.md")):
        meta = frontmatter(s.read_text(encoding="utf-8"))
        mp3 = ROOT / "podcast" / "episodes" / f"{s.stem}.mp3"
        if mp3.exists():
            out.append({"stem": s.stem, "mp3": mp3, "title": meta.get("title", s.stem),
                        "description": meta.get("description", ""), "minutes": duration(mp3)})
    return out


# ─── Sezioni ─────────────────────────────────────────────────────────────────

def section_hero(cfg, prefix):
    sw = cfg.get("switch")
    switch = f'<a class="switch" href="{e(sw["href"])}" hreflang="{"it" if sw["label"] == "Italiano" else "en"}">{e(sw["label"])}</a>' if sw else ""
    return f"""<header class="hero">{switch}
  <img class="cover" src="{prefix}cover-720.jpg" width="360" height="360" alt="{e(LABELS[cfg['lang']]['cover'])}: {e(cfg['title'])}">
  <div><p class="kicker">{e(cfg.get('kicker', ''))}</p><h1>{e(cfg['title'])}</h1>
  <p class="subtitle">{e(cfg.get('subtitle', ''))}</p><p class="tagline">{e(cfg.get('tagline', ''))}</p>
  <p class="author">{e(cfg.get('author', ''))}</p></div></header>"""

def section_book(cfg, files):
    b = cfg.get("book", {})
    paras = "".join(f"<p>{md_inline(p)}</p>" for p in b.get("paragraphs", []))
    btns = "".join(f'<a class="btn" href="{e(files[d["file"]])}" download>{e(d["label"])}</a>' for d in b.get("downloads", []))
    note = f'<p class="note">{e(b["note"])}</p>' if b.get("note") else ""
    return f'<section id="book"><h2>{e(b.get("title", ""))}</h2>{paras}<div class="btns">{btns}</div>{note}</section>'

def section_featured(cfg, all_cards):
    items = []
    for f in cfg.get("featured", []):
        name = f.get("name") or all_cards.get(f.get("id"), {}).get("name", f.get("id"))
        link = f' data-card="{e(f["id"])}"' if f.get("id") in all_cards and cfg.get("graph") else ""
        tag = "button" if link else "div"
        items.append(f'<{tag} class="idea"{link}><span class="role">{e(f.get("role", ""))}</span>'
                     f'<strong>{e(name)}</strong><span>{e(f.get("text", ""))}</span></{tag}>')
    if not items:
        return ""
    return f'<section id="ideas"><h2>{e(cfg.get("featured_title", ""))}</h2><div class="ideas">{"".join(items)}</div></section>'

def section_podcast(cfg, eps, L):
    p = cfg.get("podcast")
    if p and eps:
        li = "".join(f'<li><h3>{e(x["title"])}</h3><p>{e(x["description"])}'
                     f'{f" · {x[chr(109)+chr(105)+chr(110)+chr(117)+chr(116)+chr(101)+chr(115)]} {L[chr(109)+chr(105)+chr(110)+chr(117)+chr(116)+chr(101)+chr(115)]}" if x["minutes"] else ""}</p>'
                     f'<audio controls preload="none" src="episodes/{x["stem"]}.mp3"></audio></li>' for x in eps)
        return (f'<section id="podcast"><h2>{e(p["title"])}</h2><p>{e(p.get("text", ""))}</p>'
                f'<p><a href="feed.xml">{e(L["feed"])}</a></p><ol class="eps">{li}</ol></section>')
    n = cfg.get("podcast_notice")
    if n:
        return f'<section id="podcast"><h2>{e(n["title"])}</h2><p>{e(n["text"])}</p><a class="btn" href="{e(n["link"])}">{e(n["label"])}</a></section>'
    return ""

def card_article(cid, c, all_cards, back, L, lang):
    tname = TYPES[c["type"]][0 if lang == "it" else 1]
    parts = [f'<p class="ctype">{e(tname)}</p><h3>{e(c.get("name", cid))}</h3>']
    if c.get("aliases"):
        parts.append(f'<p class="alias">{e(", ".join(c["aliases"]))}</p>')
    if c.get("summary"):
        parts.append(f'<p>{e(c["summary"])}</p>')
    def block(field, label):
        items = c.get(field) or []
        if not items:
            return ""
        lis = []
        for it in items:
            if isinstance(it, dict):
                src = f' <span class="src" title="{e(str(it.get("quote", "")))}">{e(str(it["source"]))}</span>' if it.get("source") else ""
                lis.append(f"<li>{e(it.get('text', ''))}{src}</li>")
        return f"<h4>{e(label)}</h4><ul>{''.join(lis)}</ul>"
    parts += [block("traits", L["text"]), block("not_said", L["not_said"]), block("open", L["open"]), block("notes", L["notes"])]
    if c.get("relations"):
        rel = "".join(f'<li>{e(r.get("type", ""))} → <button data-card="{e(r["to"])}">{e(all_cards[r["to"]].get("name", r["to"]))}</button></li>'
                      for r in c["relations"] if r["to"] in all_cards)
        parts.append(f"<h4>{e(L['relations'])}</h4><ul>{rel}</ul>")
    if back.get(cid):
        bl = "".join(f'<li><button data-card="{e(s)}">{e(all_cards[s].get("name", s))}</button> ({e(t)})</li>' for s, t in back[cid])
        parts.append(f"<h4>{e(L['cited_by'])}</h4><ul>{bl}</ul>")
    chs = sorted({n for f in ("traits", "relations") for it in c.get(f) or [] if isinstance(it, dict) for n in src_chapters(it.get("source"))})
    cls = "card open" if c.get("open") else "card"
    return f'<article class="{cls}" id="card-{e(cid)}" data-type="{e(c["type"])}" data-ch="{" ".join(map(str, chs))}" hidden>{"".join(parts)}</article>'

def section_graph(cfg, all_cards, L, lang):
    g = cfg.get("graph")
    if not g or not all_cards:
        return ""
    upto = g.get("up_to_chapter")
    if upto:
        all_cards = {k: v for k, v in all_cards.items()
                     if any(n <= upto for f in ("traits", "relations") for it in v.get(f) or [] if isinstance(it, dict) for n in src_chapters(it.get("source")))}
    back = {}
    edges = []
    for cid, c in all_cards.items():
        for r in c.get("relations") or []:
            if r["to"] in all_cards:
                back.setdefault(r["to"], []).append((cid, r.get("type", "")))
                edges.append([cid, r["to"]])
    nodes = [{"id": k, "n": v.get("name", k), "t": v["type"], "o": bool(v.get("open"))} for k, v in all_cards.items()]
    titles = chapter_titles()
    chopts = "".join(f'<option value="{n}">{e(L["chapter"])} c{n} · {e(t)}</option>' for n, t in sorted(titles.items()) if not upto or n <= upto)
    legend = "".join(f'<span class="lg t-{t}">{e(TYPES[t][0 if lang == "it" else 1])}</span>' for t in TYPES)
    arts = "".join(card_article(k, v, all_cards, back, L, lang) for k, v in all_cards.items())
    opens = [(k, it) for k, v in all_cards.items() for it in v.get("open") or [] if isinstance(it, dict)]
    open_list = "".join(f'<li><button data-card="{e(k)}">{e(all_cards[k].get("name", k))}</button>: {e(it.get("text", ""))}</li>' for k, it in opens)
    data = json.dumps({"nodes": nodes, "edges": edges, "start": g.get("start", [])}, ensure_ascii=False)
    return f"""<section id="graph"><h2>{e(g.get('title', ''))}</h2><p>{e(g.get('text', ''))}</p>
<p class="note">{e(g.get('open_notice', ''))}</p>
<div class="gtools"><input id="gsearch" type="search" placeholder="{e(g.get('search_placeholder', L['search']))}" autocomplete="off">
<select id="gch"><option value="">{e(L['all'])}</option>{chopts}</select></div>
<div class="legend">{legend}</div>
<div class="gwrap"><svg id="gsvg" viewBox="0 0 1000 700" role="img" aria-label="{e(g.get('title', ''))}"></svg>
<div id="gpanel" hidden><button id="gclose" aria-label="{e(L['close'])}">×</button><div id="gbody"></div></div></div>
<div id="gcards">{arts}</div>
<details class="opens"><summary>{e(L['open_all'])} ({len(opens)})</summary><ul>{open_list}</ul></details>
<script type="application/json" id="gdata">{data}</script></section>"""


CSS = """
:root{--bg:#0e111c;--fg:#efece2;--mut:#a8b0c4;--acc:#e8a84c;--line:#3c4a6e;--card:#151a29}
@media (prefers-color-scheme:light){:root{--bg:#f7f5ef;--fg:#1b1d24;--mut:#575d6e;--acc:#a8650a;--line:#c5cadb;--card:#ffffff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.6 Georgia,'Times New Roman',serif}
main{max-width:880px;margin:0 auto;padding:0 16px 64px}a{color:var(--acc)}h1,h2,h3{font-weight:normal;line-height:1.2}
.hero{position:relative;display:grid;gap:24px;align-items:center;padding:48px 0 24px}
@media(min-width:720px){.hero{grid-template-columns:320px 1fr}}
.cover{width:100%;max-width:360px;height:auto;border-radius:6px;box-shadow:0 10px 40px #0006}
.switch{position:absolute;top:12px;right:0;font:14px system-ui,sans-serif;border:1px solid var(--line);padding:4px 12px;border-radius:99px;text-decoration:none}
.kicker{font:13px system-ui,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:var(--acc);margin:0}
h1{font-size:clamp(2rem,6vw,3rem);margin:.2em 0}.subtitle{font-style:italic;color:var(--mut);margin:0 0 1em}
.tagline{font-size:1.15em}.author{font:15px system-ui,sans-serif;letter-spacing:.08em;text-transform:uppercase;color:var(--mut)}
section{padding:32px 0;border-top:1px solid var(--line)}h2{font-size:1.6rem;margin:0 0 .6em}
.btns{display:flex;flex-wrap:wrap;gap:10px;margin:1em 0}.btn{display:inline-block;font:15px system-ui,sans-serif;background:var(--acc);color:#111;text-decoration:none;padding:10px 16px;border-radius:6px}
.note{font:14px system-ui,sans-serif;color:var(--mut)}
.ideas{display:grid;gap:12px}@media(min-width:720px){.ideas{grid-template-columns:1fr 1fr}}
.idea{display:flex;flex-direction:column;gap:4px;text-align:left;font:inherit;color:inherit;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px}
button.idea{cursor:pointer}button.idea:hover{border-color:var(--acc)}
.role{font:12px system-ui,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:var(--acc)}
.eps{padding-left:1.2em}.eps li{margin:0 0 1.4em}.eps h3{font-size:1.05rem;margin:0}.eps p{margin:.2em 0 .5em;color:var(--mut);font-size:.95em}audio{width:100%}
.gtools{display:flex;flex-wrap:wrap;gap:8px;margin:.5em 0}.gtools input,.gtools select{font:15px system-ui,sans-serif;padding:8px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--fg);flex:1;min-width:0}
.legend{display:flex;flex-wrap:wrap;gap:12px;font:13px system-ui,sans-serif;color:var(--mut);margin:.5em 0}.lg:before{content:"";display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;background:var(--c)}
.t-concepts{--c:#6ea8ff}.t-terms{--c:#e8a84c}.t-theses{--c:#e06c8c}.t-sources{--c:#6ee7a0}.t-people{--c:#b79cff}
.gwrap{position:relative;background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}
#gsvg{width:100%;height:auto;display:block;touch-action:manipulation}#gsvg line{stroke:var(--line);stroke-width:1}
#gsvg circle{stroke:var(--bg);stroke-width:2;cursor:pointer}#gsvg circle.open{stroke:#ff8a3d;stroke-width:3}
#gsvg text{font:12px system-ui,sans-serif;fill:var(--fg);pointer-events:none}#gsvg .dim{opacity:.15}#gsvg .hl circle{stroke:var(--acc);stroke-width:4}
#gpanel{position:absolute;inset:auto 0 0 0;max-height:75%;overflow:auto;background:var(--bg);border-top:2px solid var(--acc);padding:12px 16px}
@media(min-width:720px){#gpanel{inset:0 0 0 auto;width:48%;max-height:none;border-top:0;border-left:2px solid var(--acc)}}
#gclose{float:right;font-size:24px;background:none;border:0;color:var(--fg);cursor:pointer}
.card h3{margin:.1em 0}.card h4{font:13px system-ui,sans-serif;text-transform:uppercase;letter-spacing:.08em;color:var(--acc);margin:1em 0 .3em}
.card ul{padding-left:1.1em;margin:0}.card li{margin:.25em 0;font-size:.95em}.ctype,.alias{font:13px system-ui,sans-serif;color:var(--mut);margin:0}
.src{font:12px ui-monospace,monospace;color:var(--mut);white-space:nowrap}.card button,.opens button{font:inherit;color:var(--acc);background:none;border:0;padding:0;cursor:pointer;text-decoration:underline}
.card.open h3:after{content:" ●";color:#ff8a3d}.opens{margin-top:1em;font-size:.95em}
footer{border-top:1px solid var(--line);padding:24px 0;font:14px system-ui,sans-serif;color:var(--mut)}
"""

JS = r"""
(function(){
const D=JSON.parse(document.getElementById('gdata').textContent),svg=document.getElementById('gsvg');
const W=1000,H=700,NS='http://www.w3.org/2000/svg',col={concepts:'#6ea8ff',terms:'#e8a84c',theses:'#e06c8c',sources:'#6ee7a0',people:'#b79cff'};
const N=D.nodes.map((n,i)=>({...n,x:W/2+Math.cos(i*2.4)*(120+i*3),y:H/2+Math.sin(i*2.4)*(90+i*2.2),vx:0,vy:0})),idx={};N.forEach((n,i)=>idx[n.id]=i);
const E=D.edges.map(([a,b])=>[idx[a],idx[b]]),deg=N.map(()=>0);E.forEach(([a,b])=>{deg[a]++;deg[b]++});
for(let it=0;it<400;it++){const k=1-it/400;
 for(let i=0;i<N.length;i++)for(let j=i+1;j<N.length;j++){let dx=N[i].x-N[j].x,dy=N[i].y-N[j].y,d2=dx*dx+dy*dy+0.01,f=2600/d2;N[i].vx+=dx*f/Math.sqrt(d2);N[i].vy+=dy*f/Math.sqrt(d2);N[j].vx-=dx*f/Math.sqrt(d2);N[j].vy-=dy*f/Math.sqrt(d2)}
 E.forEach(([a,b])=>{let dx=N[b].x-N[a].x,dy=N[b].y-N[a].y,d=Math.sqrt(dx*dx+dy*dy)+0.01,f=(d-90)*0.02;N[a].vx+=dx/d*f;N[a].vy+=dy/d*f;N[b].vx-=dx/d*f;N[b].vy-=dy/d*f});
 N.forEach(n=>{n.vx+=(W/2-n.x)*0.004;n.vy+=(H/2-n.y)*0.004;n.x+=n.vx*k*0.5;n.y+=n.vy*k*0.5;n.vx*=0.6;n.vy*=0.6;n.x=Math.max(30,Math.min(W-30,n.x));n.y=Math.max(20,Math.min(H-20,n.y))})}
const lines=E.map(([a,b])=>{const l=document.createElementNS(NS,'line');l.setAttribute('x1',N[a].x);l.setAttribute('y1',N[a].y);l.setAttribute('x2',N[b].x);l.setAttribute('y2',N[b].y);svg.appendChild(l);return l});
const gs=N.map((n,i)=>{const g=document.createElementNS(NS,'g'),c=document.createElementNS(NS,'circle'),t=document.createElementNS(NS,'text');
 c.setAttribute('cx',n.x);c.setAttribute('cy',n.y);c.setAttribute('r',6+deg[i]*1.6);c.setAttribute('fill',col[n.t]);if(n.o)c.classList.add('open');
 t.setAttribute('x',n.x+9+deg[i]);t.setAttribute('y',n.y+4);t.textContent=n.n;g.appendChild(c);g.appendChild(t);g.addEventListener('click',()=>show(n.id));svg.appendChild(g);return g});
const panel=document.getElementById('gpanel'),body=document.getElementById('gbody');
function focus(ids){const s=new Set(ids);gs.forEach((g,i)=>g.classList.toggle('dim',ids.length&&!s.has(N[i].id)));lines.forEach((l,j)=>{const[a,b]=E[j];l.classList.toggle('dim',ids.length&&!(s.has(N[a].id)&&s.has(N[b].id)))})}
function show(id){const a=document.getElementById('card-'+id);if(!a)return;body.innerHTML=a.innerHTML;panel.hidden=false;gs.forEach((g,i)=>g.classList.toggle('hl',N[i].id===id));
 const nb=[id];E.forEach(([x,y])=>{if(N[x].id===id)nb.push(N[y].id);if(N[y].id===id)nb.push(N[x].id)});focus(nb);
 if(!document.getElementById('graph').contains(document.activeElement))document.getElementById('graph').scrollIntoView({behavior:'smooth'})}
document.getElementById('gclose').onclick=()=>{panel.hidden=true;focus([]);gs.forEach(g=>g.classList.remove('hl'))};
document.addEventListener('click',ev=>{const b=ev.target.closest('[data-card]');if(b){ev.preventDefault();show(b.dataset.card)}});
document.getElementById('gsearch').oninput=ev=>{const q=ev.target.value.trim().toLowerCase();focus(q?N.filter(n=>n.n.toLowerCase().includes(q)||n.id.includes(q)).map(n=>n.id):[])};
document.getElementById('gch').onchange=ev=>{const c=ev.target.value;focus(c?N.filter(n=>(document.getElementById('card-'+n.id).dataset.ch||'').split(' ').includes(c)).map(n=>n.id):[])};
if(D.start&&D.start.length)focus(D.start.concat(N.filter(n=>E.some(([a,b])=>(D.start.includes(N[a].id)&&N[b].id===n.id)||(D.start.includes(N[b].id)&&N[a].id===n.id))).map(n=>n.id)));
})();
"""


def build_page(cfg_path, check=False):
    cfg = load(cfg_path)
    lang = cfg.get("lang", "it")
    L = {**LABELS[lang], **(cfg.get("labels") or {})}
    out = ROOT / cfg.get("output", "docs")
    prefix = "../" * (len(Path(cfg.get("output", "docs")).parts) - 1)
    problems, warns = [], []
    all_cards = cards() if cfg.get("graph") else {}
    for f in cfg.get("featured", []):
        if f.get("id") and cfg.get("graph") and f["id"] not in all_cards:
            warns.append(f"featured: id '{f['id']}' non è nel grafo")
    files = {}
    for d in cfg.get("book", {}).get("downloads", []):
        src = ROOT / d["file"]
        if not src.exists():
            problems.append(f"download mancante: {d['file']}")
        files[d["file"]] = f"download/{src.name}"
    cover = ROOT / "podcast" / "cover" / "cover.jpg"
    if not cover.exists():
        warns.append("copertina mancante: podcast/cover/cover.jpg")
    eps = episodes() if cfg.get("podcast") else []
    if cfg.get("podcast") and not (ROOT / "podcast" / "feed.xml").exists():
        warns.append("podcast/feed.xml mancante: lancia `python3 export_podcast.py feed`")
    for w in warns:
        print(f"⚠️  {cfg_path.name}: {w}")
    if problems:
        sys.exit("\n".join(f"❌ {cfg_path.name}: {p}" for p in problems))
    if check:
        print(f"✅ {cfg_path.name}: ok")
        return
    out.mkdir(parents=True, exist_ok=True)
    for d in cfg.get("book", {}).get("downloads", []):
        (out / "download").mkdir(exist_ok=True)
        shutil.copy2(ROOT / d["file"], out / files[d["file"]])
    if prefix == "" and cover.exists():
        shutil.copy2(cover, out / "cover.jpg")
        try:
            from PIL import Image
            Image.open(cover).resize((720, 720), Image.LANCZOS).save(out / "cover-720.jpg", quality=85)
        except ImportError:
            shutil.copy2(cover, out / "cover-720.jpg")
    if cfg.get("cname"):
        (out / "CNAME").write_text(cfg["cname"] + "\n", encoding="utf-8")
    if eps:
        (out / "episodes").mkdir(exist_ok=True)
        for x in eps:
            shutil.copy2(x["mp3"], out / "episodes" / x["mp3"].name)
        if (ROOT / "podcast" / "feed.xml").exists():
            shutil.copy2(ROOT / "podcast" / "feed.xml", out / "feed.xml")
    alt = cfg.get("switch")
    alt_link = f'<link rel="alternate" hreflang="{"it" if alt and alt["label"] == "Italiano" else "en"}" href="{e(alt["href"])}">' if alt else ""
    feed_link = '<link rel="alternate" type="application/rss+xml" href="feed.xml">' if eps else ""
    graph_html = section_graph(cfg, all_cards, L, lang)
    token = (cfg.get("analytics") or {}).get("cloudflare_token")
    analytics = ("<!-- Cloudflare Web Analytics --><script type='module' src='https://static.cloudflareinsights.com/beacon.min.js' "
                 f"data-cf-beacon='{{\"token\": \"{e(token)}\"}}'></script><!-- End Cloudflare Web Analytics -->") if token else ""
    page = f"""<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(cfg['title'])} — {e(cfg.get('author', ''))}</title>
<meta name="description" content="{e(cfg.get('tagline', ''))}">
<meta property="og:title" content="{e(cfg['title'])}"><meta property="og:description" content="{e(cfg.get('tagline', ''))}">
<meta property="og:image" content="{prefix}cover-720.jpg">{alt_link}{feed_link}
<link rel="icon" href="{prefix}cover-720.jpg"><style>{CSS}</style></head>
<body><main>
{section_hero(cfg, prefix)}
{section_book(cfg, files)}
{section_featured(cfg, all_cards)}
{section_podcast(cfg, eps, L)}
{graph_html}
<footer>© {e(cfg.get('author', ''))} · {e(L['license'])} CC BY-NC-ND 4.0 · <a href="https://github.com/simonediroma/quantum_fatalism">GitHub</a></footer>
</main>{f'<script>{JS}</script>' if graph_html else ''}{analytics}</body></html>
"""
    (out / "index.html").write_text(page, encoding="utf-8")
    size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
    print(f"OK: {(out / 'index.html').relative_to(ROOT)} ({len(page) // 1024} KB) · {len(eps)} puntate · "
          f"{len(all_cards)} schede · cartella {size // (1024 * 1024)} MB")


if __name__ == "__main__":
    check = "--check" in sys.argv
    configs = sorted(ROOT.glob("site*.yaml"), key=lambda p: (p.name != "site.yaml", p.name))
    if not configs:
        sys.exit("Nessun site.yaml.")
    for c in configs:
        build_page(c, check)
    if not check:
        print("Sito ricostruito: commit e push di docs/ per pubblicarlo.")
