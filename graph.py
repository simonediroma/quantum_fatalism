#!/usr/bin/env python3
"""Il grafo del libro (skill /ghost-writer:graph).

Schede YAML in graph/cards/<type>/<id>.yaml, costruite solo da ciò che dicono i capitoli
`status: complete`. Ogni fonte è "cN:riga" (o "cN:a-b") con una citazione esatta della riga.

  python3 graph.py start                 cosa c'è da analizzare (capitoli NEW / TO RE-ANALYZE)
  python3 graph.py check                 stato dei capitoli
  python3 graph.py find <nome>           schede per nome o alias
  python3 graph.py find --chapter N      schede toccate dal capitolo N
  python3 graph.py apply patch.txt       applica una patch alle schede
  python3 graph.py commit N [N …]        riancora le fonti, salva snapshot e versione, ricostruisce le viste
  python3 graph.py validate              controlla le schede (sola lettura)
  python3 graph.py build                 validate + rigenera viste, INDEX.md e graph.json
  python3 graph.py migrate <dir>         conversione da un grafo legacy (non presente in questo progetto)
  python3 graph.py fill-quotes <file>    completa le citazioni dopo una migrazione

Solo libreria standard + PyYAML.
"""
import difflib
import json
import re
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("PyYAML mancante: pip install pyyaml")

ROOT = Path(__file__).resolve().parent
CHAPTERS = ROOT / "chapters"
GRAPH = ROOT / "graph"
CARDS = GRAPH / "cards"
VIEW = GRAPH / "view"
SNAP = GRAPH / "snapshots"
STATE = GRAPH / "chapters.yaml"
START = GRAPH / ".start.json"

# Tipi del preset essay (presets/essay.md → graph adaptations).
TYPES = {"concepts": "Concetti", "terms": "Termini", "theses": "Tesi", "sources": "Fonti", "people": "Persone"}
LIST_FIELDS = ("traits", "state", "not_said", "open", "notes", "relations", "facts")
SRC_RE = re.compile(r"^c(\d+):(\d+)(?:-(\d+))?$")


# ─── Capitoli ────────────────────────────────────────────────────────────────

def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    return (yaml.safe_load(m.group(1)) or {}) if m else {}

def chapters():
    out = {}
    for f in sorted(CHAPTERS.glob("[0-9][0-9]-*.md")):
        text = f.read_text(encoding="utf-8")
        meta = frontmatter(text)
        title = " — ".join(x for x in (meta.get("part"), meta.get("title")) if x)
        out[int(f.name[:2])] = {"file": f.name, "title": title, "status": meta.get("status", "draft"),
                                "version": str(meta.get("version", "1.0")), "text": text}
    return out

def load_state():
    return (yaml.safe_load(STATE.read_text(encoding="utf-8")) or {}) if STATE.exists() else {}

def save_state(state):
    STATE.write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=True), encoding="utf-8")

def snapshot_lines(n):
    p = SNAP / f"c{n:02d}.md"
    return p.read_text(encoding="utf-8").split("\n") if p.exists() else None

def chapter_state(n, ch, state):
    st = state.get(n)
    if ch["status"] != "complete":
        return "SUSPENDED" if st else "draft"
    if not st:
        return "TO ANALYZE"
    if str(st.get("analyzed_version")) != ch["version"]:
        return "TO RE-ANALYZE"
    snap = snapshot_lines(n)
    if snap is not None and "\n".join(snap) != ch["text"]:
        return "NOTE: text changed without a version bump"
    return "up to date"


# ─── Schede ──────────────────────────────────────────────────────────────────

def card_files():
    return sorted(CARDS.glob("*/*.yaml"))

def load_card(path):
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

def all_cards():
    return {f"{p.parent.name}/{p.stem}": (p, load_card(p)) for p in card_files()}

def q(v):
    return json.dumps(v, ensure_ascii=False)

def flow(d):
    parts = []
    for k, v in d.items():
        if isinstance(v, list):
            v = "[" + ", ".join(q(x) if not isinstance(x, (int, float)) else str(x) for x in v) + "]"
        elif isinstance(v, bool):
            v = "true" if v else "false"
        elif isinstance(v, (int, float)):
            v = str(v)
        else:
            v = q(v)
        parts.append(f"{k}: {v}")
    return "{" + ", ".join(parts) + "}"

def dump_card(card):
    lines = []
    for k, v in card.items():
        if k in LIST_FIELDS:
            if not v:
                continue
            lines.append(f"{k}:")
            lines += [f"  - {flow(x) if isinstance(x, dict) else q(x)}" for x in v]
        elif isinstance(v, list):
            lines.append(f"{k}: [" + ", ".join(q(x) if isinstance(x, str) else str(x) for x in v) + "]")
        else:
            lines.append(f"{k}: {q(v) if isinstance(v, str) else v}")
    return "\n".join(lines) + "\n"

def save_card(path, card):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_card(card), encoding="utf-8")

def entries(card):
    for field in LIST_FIELDS:
        for e in card.get(field) or []:
            if isinstance(e, dict):
                yield field, e

def refs(entry):
    src = entry.get("source")
    if not src:
        return []
    srcs = [s.strip() for s in str(src).split(",")]
    quotes = entry.get("quote")
    quotes = quotes if isinstance(quotes, list) else [quotes] * len(srcs)
    return list(zip(srcs, quotes))

def quote_at(lines, a, b, quote):
    return any(quote and quote in lines[i - 1] for i in range(a, b + 1) if 0 < i <= len(lines))


# ─── Controlli ───────────────────────────────────────────────────────────────

def validate(quiet=False, text_of=None):
    """text_of(n) → righe del capitolo n contro cui validare (default: snapshot)."""
    errors = []
    cards = all_cards()
    ids = {k.split("/")[1] for k in cards}
    state = load_state()
    for key, (path, card) in cards.items():
        if card.get("id") != path.stem:
            errors.append(f"{key}: id '{card.get('id')}' diverso dal nome del file")
        if path.parent.name not in TYPES:
            errors.append(f"{key}: tipo '{path.parent.name}' non previsto dal preset")
        for field, e in entries(card):
            if field == "relations" and e.get("to") not in ids:
                errors.append(f"{key}: relazione verso id inesistente '{e.get('to')}'")
            for src, quote in refs(e):
                m = SRC_RE.match(src)
                if not m:
                    errors.append(f"{key}: fonte malformata '{src}'"); continue
                n, a, b = int(m.group(1)), int(m.group(2)), int(m.group(3) or m.group(2))
                if n not in state:
                    errors.append(f"{key}: la fonte {src} cita un capitolo non analizzato"); continue
                lines = text_of(n) if text_of else snapshot_lines(n)
                if not quote:
                    errors.append(f"{key}: fonte {src} senza citazione")
                elif lines is not None and not quote_at(lines, a, b, quote):
                    errors.append(f"{key}: citazione non trovata in {src}: «{quote}»")
    if not quiet:
        print("\n".join(errors) if errors else f"OK: {len(cards)} schede valide")
    return errors

def lost_sources(n, new_lines):
    lost = []
    for key, (path, card) in all_cards().items():
        for field, e in entries(card):
            for src, quote in refs(e):
                m = SRC_RE.match(src)
                if m and int(m.group(1)) == n and not any(quote and quote in l for l in new_lines):
                    lost.append((key, src, quote))
    return lost


# ─── Comandi ─────────────────────────────────────────────────────────────────

def cmd_check():
    chs, state = chapters(), load_state()
    for n, ch in chs.items():
        print(f"c{n:<3} {chapter_state(n, ch, state):<45} v{ch['version']:<6} {ch['title']}")

def cmd_start():
    chs = chapters()
    if not GRAPH.exists():
        if not any(c["status"] == "complete" for c in chs.values()):
            print("Grafo non ancora creato: nessun capitolo complete."); return
        for d in (CARDS, VIEW, SNAP):
            d.mkdir(parents=True, exist_ok=True)
        for t in TYPES:
            (CARDS / t).mkdir(exist_ok=True)
        save_state({})
        print("Grafo creato in graph/.")
    state = load_state()
    todo = {}
    for n, ch in chs.items():
        s = chapter_state(n, ch, state)
        if s == "TO ANALYZE":
            todo[n] = "NEW"
            print(f"NEW  c{n} v{ch['version']}  {ch['file']}  — leggere tutto il capitolo")
        elif s == "TO RE-ANALYZE":
            todo[n] = "RE"
            old, new = snapshot_lines(n) or [], ch["text"].split("\n")
            print(f"TO RE-ANALYZE  c{n} v{state[n]['analyzed_version']} → v{ch['version']}  {ch['file']}")
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=old, b=new).get_opcodes():
                if tag == "equal":
                    continue
                for i in range(i1, i2):
                    print(f"  - old c{n}:{i + 1}  {old[i][:120]}")
                for j in range(j1, j2):
                    print(f"  + new c{n}:{j + 1}  {new[j][:120]}")
            for key, src, quote in lost_sources(n, new):
                print(f"  LOST {key}  {src}  «{quote}»")
    if not todo:
        print("Grafo aggiornato.")
    START.write_text(json.dumps({"todo": todo}), encoding="utf-8")

def cmd_find(args):
    cards = all_cards()
    if args and args[0] == "--chapter":
        n = int(args[1])
        for key, (path, card) in cards.items():
            if any(SRC_RE.match(s) and int(SRC_RE.match(s).group(1)) == n
                   for _, e in entries(card) for s, _ in refs(e)) or n in (card.get("chapters") or []):
                print(path.relative_to(ROOT))
        return
    needle = " ".join(args).lower()
    for key, (path, card) in cards.items():
        names = [card.get("id", ""), card.get("name", "")] + list(card.get("aliases") or [])
        if any(needle in str(x).lower() for x in names):
            print(path.relative_to(ROOT))

def cmd_apply(patch_file):
    card, path = None, None
    def flush():
        if card is not None:
            save_card(path, card)
    for raw in Path(patch_file).read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.startswith("#"):
            continue
        if line.startswith("@ "):
            flush()
            key = line[2:].strip()
            path = CARDS / f"{key}.yaml"
            card = load_card(path) if path.exists() else {"id": path.stem}
            continue
        m = re.match(r"^(-?)(\w+)(\+?):\s*(.*)$", line)
        if not m or card is None:
            sys.exit(f"Riga di patch non valida: {line}")
        remove, field, add, value = m.group(1), m.group(2), m.group(3), yaml.safe_load(m.group(4))
        if remove:
            card[field] = [e for e in card.get(field) or []
                           if not str(e.get("text", e) if isinstance(e, dict) else e).startswith(str(value))]
        elif add or field in LIST_FIELDS:
            card.setdefault(field, [])
            card[field].append(value)
        else:
            card[field] = value
    flush()
    print("Patch applicata.")

def cmd_commit(ns):
    chs, state = chapters(), load_state()
    for n in ns:
        if n not in chs or chs[n]["status"] != "complete":
            sys.exit(f"c{n}: capitolo inesistente o non complete")
    current = {n: chs[n]["text"].split("\n") for n in ns}
    # 1. riancora le fonti spostate sui capitoli in commit
    moved = 0
    for key, (path, card) in all_cards().items():
        changed = False
        for field, e in entries(card):
            new_srcs = []
            for src, quote in refs(e):
                m = SRC_RE.match(src)
                if m and int(m.group(1)) in ns:
                    n, a, b = int(m.group(1)), int(m.group(2)), int(m.group(3) or m.group(2))
                    lines = current[n]
                    if not quote_at(lines, a, b, quote):
                        hits = [i + 1 for i, l in enumerate(lines) if quote and quote in l]
                        if hits:
                            best = min(hits, key=lambda h: abs(h - a))
                            src = f"c{n}:{best}"; moved += 1; changed = True
                new_srcs.append(src)
            if e.get("source") and changed:
                e["source"] = ", ".join(new_srcs)
        if changed:
            save_card(path, card)
    # 2. valida contro il testo corrente (capitoli in commit) o lo snapshot (gli altri)
    staged = {**state, **{n: {"file": chs[n]["file"], "title": chs[n]["title"], "analyzed_version": chs[n]["version"]} for n in ns}}
    STATE_BAK = dict(state)
    save_state(staged)
    errors = validate(quiet=True, text_of=lambda n: current[n] if n in current else snapshot_lines(n))
    if errors:
        save_state(STATE_BAK)
        print("\n".join(errors))
        sys.exit("Commit annullato: nessuna modifica a snapshot e versioni.")
    for n in ns:
        (SNAP / f"c{n:02d}.md").write_text(chs[n]["text"], encoding="utf-8")
    build(quiet=True)
    n_cards = len(card_files())
    opens = sum(len(c.get("open") or []) for _, (p, c) in all_cards().items())
    vers = ", ".join(f"c{n} v{chs[n]['version']}" for n in ns)
    print(f"Grafo sincronizzato ({vers}): {n_cards} schede, {moved} fonti riancorate · punti aperti: {opens}.")
    if START.exists():
        START.unlink()


# ─── Viste ───────────────────────────────────────────────────────────────────

def cited_chapters(card):
    ns = set(card.get("chapters") or [])
    for _, e in entries(card):
        for s, _ in refs(e):
            m = SRC_RE.match(s)
            if m:
                ns.add(int(m.group(1)))
    return sorted(ns)

def build(quiet=False):
    errors = validate(quiet=True)
    if errors:
        print("\n".join(errors))
        sys.exit("Build interrotto: correggi le schede.")
    cards = all_cards()
    state = load_state()
    by_id = {k.split("/")[1]: k for k in cards}
    back = {k: [] for k in cards}
    edges = []
    for key, (path, card) in cards.items():
        for r in card.get("relations") or []:
            tgt = by_id[r["to"]]
            back[tgt].append((key, r.get("type", "")))
            edges.append({"from": key.split("/")[1], "to": r["to"], "type": r.get("type", ""), "source": r.get("source", "")})
    if VIEW.exists():
        shutil.rmtree(VIEW)
    for key, (path, card) in cards.items():
        t, cid = key.split("/")
        out = [f"# {card.get('name', cid)}", f"*{TYPES.get(t, t)[:-1] if t != 'theses' else 'Tesi'}* · capitoli {', '.join(map(str, cited_chapters(card)))}", ""]
        if card.get("aliases"):
            out.append("Anche: " + ", ".join(card["aliases"]) + "\n")
        if card.get("summary"):
            out.append(card["summary"] + "\n")
        labels = {"traits": "Nel testo", "state": "Sviluppo", "facts": "Fatti", "not_said": "Il testo non dice",
                  "open": "Punti aperti", "notes": "Note"}
        for field, label in labels.items():
            items = card.get(field) or []
            if items:
                out.append(f"## {label}")
                for e in items:
                    if isinstance(e, dict):
                        src = f" — `{e['source']}`" if e.get("source") else ""
                        out.append(f"- {e.get('text', '')}{src}")
                    else:
                        out.append(f"- {e}")
                out.append("")
        if card.get("relations"):
            out.append("## Relazioni")
            for r in card["relations"]:
                tk = by_id[r["to"]]
                name = cards[tk][1].get("name", r["to"])
                out.append(f"- {r.get('type', '')} → [{name}](../{tk}.md)" + (f" — `{r['source']}`" if r.get("source") else ""))
            out.append("")
        if back[key]:
            out.append("## Citata da")
            for src_key, typ in back[key]:
                out.append(f"- [{cards[src_key][1].get('name', src_key)}](../{src_key}.md) ({typ})")
            out.append("")
        p = VIEW / f"{key}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(out), encoding="utf-8")
    chs = chapters()
    for n in state:
        touched = [k for k, (p, c) in cards.items() if n in cited_chapters(c)]
        lines = [f"# Capitolo c{n}: {state[n].get('title', '')}", f"Versione analizzata: {state[n].get('analyzed_version')}", ""]
        for t in TYPES:
            ks = [k for k in touched if k.startswith(t + "/")]
            if ks:
                lines.append(f"## {TYPES[t]}")
                lines += [f"- [{cards[k][1].get('name', k)}](../{k}.md)" for k in ks]
                lines.append("")
        p = VIEW / "chapters" / f"{n:02d}.md"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("\n".join(lines), encoding="utf-8")
    idx = ["# Indice del grafo", "", f"{len(cards)} schede · {len(edges)} relazioni · capitoli analizzati: {', '.join(f'c{n}' for n in sorted(state))}", ""]
    for t, label in TYPES.items():
        ks = [k for k in cards if k.startswith(t + "/")]
        if ks:
            idx.append(f"## {label}")
            idx += [f"- [{cards[k][1].get('name', k)}](view/{k}.md) — {cards[k][1].get('summary', '')}" for k in ks]
            idx.append("")
    opens = [(k, e) for k, (p, c) in cards.items() for e in c.get("open") or []]
    idx.append("## Punti aperti")
    idx += [f"- [{cards[k][1].get('name', k)}](view/{k}.md): {e.get('text', e) if isinstance(e, dict) else e}" for k, e in opens] or ["- nessuno"]
    (GRAPH / "INDEX.md").write_text("\n".join(idx) + "\n", encoding="utf-8")
    nodes = [{"id": k.split("/")[1], "type": k.split("/")[0], "name": c.get("name", ""), "summary": c.get("summary", ""),
              "chapters": cited_chapters(c), "open": len(c.get("open") or [])} for k, (p, c) in cards.items()]
    (GRAPH / "graph.json").write_text(json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False, indent=1), encoding="utf-8")
    if not quiet:
        print(f"OK: {len(cards)} schede, {len(edges)} relazioni, viste rigenerate.")


def cmd_migrate(args):
    src = Path(args[0]) if args else ROOT / "grafo"
    if not src.exists():
        sys.exit(f"Nessun grafo legacy in {src}: niente da migrare.")
    sys.exit("La migrazione dal formato legacy non è implementata in questa versione di graph.py.")


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "check"
    if cmd == "start":
        cmd_start()
    elif cmd == "check":
        cmd_check()
    elif cmd == "find":
        cmd_find(a[1:])
    elif cmd == "apply":
        cmd_apply(a[1])
    elif cmd == "commit":
        cmd_commit([int(x.lstrip("c")) for x in a[1:]])
    elif cmd == "validate":
        sys.exit(1 if validate() else 0)
    elif cmd == "build":
        build()
    elif cmd in ("migrate", "fill-quotes"):
        cmd_migrate(a[1:])
    else:
        print(__doc__)
