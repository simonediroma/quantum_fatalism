#!/usr/bin/env python3
"""Genera la pagina unica del sito: docs/index.html

  python3 build_sito.py

Tutto il contenuto è scritto nell'HTML (puntate, schede del grafo, punti aperti):
il JavaScript serve solo a disegnare il grafo e a navigare tra le schede.

Sorgenti: sito.yaml (testi), podcast/scripts/episode-*.md e podcast/episodes.json
(puntate), grafo/schede/** (grafo). Lo richiama anche export_podcast.py.
"""
import json
import re
import shutil
import sys
from html import escape as e
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
sys.path.insert(0, str(ROOT / "grafo"))
import build_grafo  # noqa: E402

TIPI = ["personaggio", "organizzazione", "oggetto", "luogo", "concetto", "termine", "evento"]
PLUR = {"personaggio": "Personaggi", "organizzazione": "Organizzazioni", "oggetto": "Oggetti", "luogo": "Luoghi",
        "concetto": "Concetti", "termine": "Termini", "evento": "Eventi"}


def puntate():
    durate = json.loads((ROOT / "podcast" / "episodes.json").read_text(encoding="utf-8"))
    out = []
    for f in sorted((ROOT / "podcast" / "scripts").glob("episode-*.md")):
        if not (DOCS / "episodes" / (f.stem + ".mp3")).exists():
            continue
        testa = f.read_text(encoding="utf-8").split("---")[1]
        meta = yaml.safe_load(testa)
        sec = durate.get(f.stem, {}).get("seconds", 0)
        out.append({"file": f"episodes/{f.stem}.mp3", "titolo": meta.get("title", f.stem),
                    "testo": meta.get("description", ""), "minuti": round(sec / 60)})
    return out


def fonte(f):
    return f' <span class="fonte">({e(re.sub(r"c(\d+):", r"cap. \1, r. ", f))})</span>' if f else ""


def main():
    cfg = yaml.safe_load((ROOT / "sito.yaml").read_text(encoding="utf-8"))
    nodi = build_grafo.carica()
    caps = build_grafo.capitoli_info()
    if build_grafo.errori:
        sys.exit("Errori nelle schede: esegui prima grafo/build_grafo.py")

    archi = []  # (da, a, genere)  0 relazione · 1 evento-entità · 2 catena di eventi
    for i, n in nodi.items():
        for r in n.get("relazioni", []):
            archi.append((i, r["verso"], 0))
        if n["tipo"] == "evento":
            archi += [(i, x, 1) for x in n.get("coinvolti", [])]
            if n.get("dove"):
                archi.append((i, n["dove"], 1))
            archi += [(x, i, 2) for x in n.get("dopo", [])]
    eventi = sorted((n for n in nodi.values() if n["tipo"] == "evento"), key=lambda x: x["ordine"])
    n_aperti = {i: len(n.get("aperti", [])) for i, n in nodi.items()}
    tot_aperti = sum(n_aperti.values())

    def link(i):
        n = nodi[i]
        b = f'<span class="badge" title="punti aperti">{n_aperti[i]}</span>' if n_aperti[i] else ""
        return f'<a href="#scheda={i}" data-id="{i}">{e(n["nome"])}</a>{b}'

    def elenco(titolo, voci, cls=""):
        if not voci:
            return ""
        righe = "".join(
            f'<li>{"<b>Cap. %s</b> — " % v["cap"] if v.get("cap") else ""}{e(v["testo"])}{fonte(v.get("fonte"))}</li>'
            for v in voci)
        return f'<h4>{titolo}</h4><ul class="{cls}">{righe}</ul>'

    def scheda(n):
        i, t = n["id"], n["tipo"]
        h = [f'<article class="scheda" id="s-{i}"><div class="tipo t-{t}">{t}</div><h3>{e(n["nome"])}</h3>']
        if t == "evento":
            fuori = "" if n.get("in_scena", True) else " · fuori scena"
            h.append(f'<div class="meta">Cap. {n["capitolo"]} — {e(caps[n["capitolo"]]["titolo"])} · {e(n["quando"])}{fuori}</div>')
        else:
            alias = "Detto anche: " + ", ".join(map(e, n["alias"])) + " · " if n.get("alias") else ""
            h.append(f'<div class="meta">{alias}capitoli {", ".join(map(str, n.get("capitoli", [])))}</div>')
        h.append(f'<p>{e(n.get("sintesi", "").strip())}</p>')
        if n.get("aperti"):
            h.append(f'<div class="aperti"><h4>Punti aperti ({len(n["aperti"])})</h4><ul>'
                     + "".join(f'<li>{e(a["testo"])}</li>' for a in n["aperti"]) + "</ul></div>")
        if t == "evento":
            prima = ", ".join(link(x) for x in n.get("dopo", [])) or "—"
            poi = ", ".join(link(x["id"]) for x in eventi if i in x.get("dopo", [])) or "—"
            dove = f'<li>Dove: {link(n["dove"])}</li>' if n.get("dove") else ""
            h.append(f'<h4>Dove e chi</h4><ul>{dove}<li>Coinvolti: {", ".join(link(x) for x in n.get("coinvolti", []))}</li></ul>')
            h.append(f'<h4>Catena</h4><ul><li>Viene da: {prima}</li><li>Porta a: {poi}</li></ul>')
        h.append(elenco("Caratteristiche", n.get("caratteristiche")))
        h.append(elenco("Fatti", n.get("fatti")))
        h.append(elenco("Stato, capitolo per capitolo", n.get("stato")))
        h.append(elenco("Cosa il testo non dice", n.get("non_detto"), "nondetto"))
        h.append(elenco("Osservazioni di lettura", n.get("note"), "nondetto"))
        usc = [(r["verso"], r) for r in n.get("relazioni", [])]
        ent = [(j, r) for j, m in nodi.items() for r in m.get("relazioni", []) if r["verso"] == i]
        if usc or ent:
            righe = [f'<li>{e(r["tipo"])} {link(a)}{" — " + e(r["nota"]) if r.get("nota") else ""}{fonte(r.get("fonte"))}</li>'
                     for a, r in usc]
            righe += [f'<li>{link(j)} <span class="meta">{e(r["tipo"])}</span> questa scheda{fonte(r.get("fonte"))}</li>'
                      for j, r in ent]
            h.append(f'<h4>Relazioni</h4><ul>{"".join(righe)}</ul>')
        if t != "evento":
            miei = [x for x in eventi if i in x.get("coinvolti", []) or x.get("dove") == i]
            if miei:
                h.append(f'<h4>Catena degli eventi ({len(miei)})</h4><ul>'
                         + "".join(f'<li><span class="meta">cap. {x["capitolo"]}</span> {link(x["id"])}</li>' for x in miei)
                         + "</ul>")
        h.append("</article>")
        return "".join(h)

    # --- sezioni --------------------------------------------------------
    lib, gr = cfg["libro"], cfg["grafo"]
    dl = lib.get("download") or {}
    scarica = ""
    if dl.get("sorgente") and (ROOT / dl["sorgente"]).exists():
        dest = DOCS / dl["pubblicato"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / dl["sorgente"], dest)
        scarica = (f'<p><a class="bottone" href="{e(dl["pubblicato"])}" download>{e(dl["etichetta"])}</a></p>'
                   f'<p class="meta">{e(dl.get("nota", ""))}</p>')

    personaggi = "".join(
        f'<a class="carta" href="#scheda={p["id"]}" data-id="{p["id"]}"><span class="ruolo">{e(p["ruolo"])}</span>'
        f'<h3>{e(nodi[p["id"]]["nome"])}</h3><p>{e(p["testo"])}</p><span class="vai">Apri la scheda nel grafo →</span></a>'
        for p in cfg["personaggi"])

    eps = puntate()
    podcast = "".join(
        f'<li><h3>{e(p["titolo"])}</h3><p>{e(p["testo"])}</p>'
        f'<div class="audio"><audio controls preload="none" src="{e(p["file"])}"></audio>'
        f'<span class="meta">{p["minuti"]} min</span></div></li>' for p in eps)

    opz = "".join(f'<option value="{k}">Capitolo {k} — {e(c["titolo"])}</option>' for k, c in caps.items())
    per_cap = "".join(
        f'<div class="capev" data-cap="{k}"{"" if k == 1 else " hidden"}>' + "".join(
            f'<a class="riga" href="#scheda={x["id"]}" data-id="{x["id"]}"><b>{e(x["nome"])}</b>'
            f'<small>{e(x["quando"])}{"" if x.get("in_scena", True) else " · fuori scena"}</small>{e(x.get("sintesi", ""))}</a>'
            for x in eventi if x["capitolo"] == k) + "</div>" for k in caps)
    con_aperti = sorted((n for n in nodi.values() if n.get("aperti")), key=lambda n: -len(n["aperti"]))
    lista_aperti = "".join(
        f'<h4><a class="t-{n["tipo"]}" href="#scheda={n["id"]}" data-id="{n["id"]}">{e(n["nome"])}</a>'
        f'<span class="badge">{len(n["aperti"])}</span></h4>'
        + "".join(f'<a class="riga ap" href="#scheda={n["id"]}" data-id="{n["id"]}">{e(a["testo"])}</a>' for a in n["aperti"])
        for n in con_aperti)
    tutte = "".join(
        f'<h3 class="gruppo t-{t}">{PLUR[t]}</h3>' + "".join(
            scheda(n) for n in sorted((n for n in nodi.values() if n["tipo"] == t),
                                      key=lambda n: n.get("ordine", n["nome"].lower()) if t == "evento" else n["nome"].lower()))
        for t in TIPI)
    partenze = "".join(f"<li>{link(i)}</li>" for i in gr["partenze"] if i in nodi)
    chip = " ".join(f'<button class="chip{" off" if t == "evento" else ""}" data-t="{t}"><i class="b-{t}"></i>{PLUR[t]}</button>'
                    for t in TIPI)
    dati = json.dumps({
        "nodi": [[i, TIPI.index(n["tipo"]), n["nome"], n_aperti[i], " ".join(n.get("alias", []))] for i, n in nodi.items()],
        "archi": [[a, b, k] for a, b, k in archi if a in nodi and b in nodi]},
        ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    titolo = f'{cfg["titolo"]}: {cfg["sottotitolo"]}'
    piccola = DOCS / "cover-720.jpg"
    if not piccola.exists():
        from PIL import Image
        Image.open(DOCS / "cover.jpg").convert("RGB").resize((720, 720), Image.LANCZOS).save(piccola, quality=82)
    pagina = (ROOT / "sito" / "pagina.html").read_text(encoding="utf-8")
    valori = {
        "TITOLO": e(titolo), "NOME": e(cfg["titolo"]), "SOTTOTITOLO": e(cfg["sottotitolo"]), "AUTORE": e(cfg["autore"]),
        "OCCHIELLO": e(cfg["occhiello"]), "FRASE": e(cfg["frase"]),
        "LIBRO_TITOLO": e(lib["titolo"]), "LIBRO": "".join(f"<p>{e(p)}</p>" for p in lib["paragrafi"]), "SCARICA": scarica,
        "PERSONAGGI": personaggi,
        "PODCAST_TITOLO": e(cfg["podcast"]["titolo"]), "PODCAST_TESTO": e(cfg["podcast"]["testo"]),
        "N_PUNTATE": str(len(eps)), "PODCAST": podcast,
        "GRAFO_TITOLO": e(gr["titolo"]), "GRAFO_TESTO": e(gr["testo"]), "SPOILER": e(gr["spoiler"]),
        "GRAFO_APERTI": e(gr["aperti"] if tot_aperti else "Nessuna incongruenza aperta: quelle trovate nel testo sono state sistemate. Se ne emergono di nuove, i nodi interessati avranno il bordo arancione."), "N_SCHEDE": str(len(nodi)), "N_EVENTI": str(len(eventi)),
        "N_APERTI": str(tot_aperti),
        "APERTI_TXT": f"{tot_aperti} punt{'o' if tot_aperti == 1 else 'i'} apert{'o' if tot_aperti == 1 else 'i'}",
        "CON_APERTI_TXT": f"{len(con_aperti)} sched{'a' if len(con_aperti) == 1 else 'e'}", "N_CON_APERTI": str(len(con_aperti)), "N_CAP": str(len(caps)),
        "CHIP": chip, "OPZIONI_CAP": opz, "PER_CAP": per_cap, "LISTA_APERTI": lista_aperti,
        "PARTENZE": partenze, "SCHEDE": tutte, "DATI": dati,
    }
    pagina = re.sub(r"\{\{(\w+)\}\}", lambda m: valori[m.group(1)], pagina)
    (DOCS / "index.html").write_text(pagina, encoding="utf-8")
    vecchio = DOCS / "grafo"
    if vecchio.exists():  # l'esploratore separato è confluito nella pagina unica
        shutil.rmtree(vecchio)
    print(f"OK: docs/index.html ({len(pagina) // 1024} KB) · {len(eps)} puntate · {len(nodi)} schede · {tot_aperti} punti aperti")


if __name__ == "__main__":
    main()
