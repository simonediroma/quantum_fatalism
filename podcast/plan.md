# Piano podcast — L'universo a minima energia

Formato: narrato, una voce. Categoria del feed: Society & Culture / Philosophy. Motore: ElevenLabs (`eleven_v4`), voce Mr. Magoo (`13Cuh3NuYvWOVQtLbRN8`, scelta dell'autore dopo i campioni), stability 0,5, similarity_boost 0,75, style 0, speed 1,0. Audio in cache in `podcast/cache/`, committata in git (scelta dell'autore): un paragrafo che non cambia non consuma crediti, anche in una sessione nuova.
Nessuna musica: niente jingle né outro, scelta dell'autore (è un saggio di filosofia, non intrattenimento). Bitrate 96k.
Fonte: `chapters/` (copia identica di `saggio.md`, una sezione per file, tutti `complete`). I copioni si rigenerano con `python3 export_podcast.py scripts`; `python3 export_podcast.py check` segnala i copioni non allineati. Descrizione, riassunto iniziale (`recap`) e gancio finale (`teaser`) vivono nel frontmatter di ogni copione.

## Episodi (confermati dall'autore)

Regola della skill: le sezioni sotto le ~800 parole si accorpano. Stima a 150 parole al minuto.

| Ep | Sezioni | Parole | Durata | Stato |
|---|---|---|---|---|
| 1 | Introduzione — La luce, la sfera e il costo del pensiero + Capitolo I — La fisica dell'equilibrio | 1.592 | ~11 min | approvato |
| 2 | Capitolo II — L'osservatore e la realtà | 1.379 | ~9 min | approvato |
| 3 | Capitolo III — Le epifanie: segnali del campo | 1.073 | ~7 min | approvato |
| 4 | Capitolo IV — Il campo condiviso: la fisica delle relazioni | 1.136 | ~8 min | approvato |
| 5 | Capitolo V — La geometria del destino + Conclusione — L'arte di scorrere | 1.044 | ~7 min | approvato |
| 6 | Appendice II — Friston + Appendice III — Lo spazio latente e la geometria dell'informazione | 1.634 | ~11 min | approvato |

Totale: sei episodi, circa 53 minuti.

**Appendice I (bibliografia): esclusa**, scelta dell'autore. Gli accorpamenti sono in `book.config.json → podcast.episodes`.

## Pronunciation

Con ElevenLabs i nomi propri e i termini inglesi restano come nel testo; da verificare al primo ascolto.

| Nel testo | Nel copione | Motivo |
|---|---|---|
| Rimandi di sezione (`sezione 2.2`, `1.3`, `5.2.`) | sezione due punto due | altrimenti "due.due" o "due due" |
| Titoli di paragrafo `#### 1.1 La palla sulla collina` | [pause 1] La palla sulla collina. | il numero si toglie, il titolo si legge |
| `Capitolo II`, `Appendice III`, `Capitolo V` | Capitolo due, Appendice tre, Capitolo cinque | numeri romani |
| `XVII secolo`, `XIX secolo` | diciassettesimo secolo, diciannovesimo secolo | numeri romani |
| `anni 2000` | anni duemila | numeri in lettere |
| `` `U = mgh` `` | U uguale emme gi acca | formula |
| Elenco numerato in 3.1 (`1. **Epifanie chiare**: …`) | Primo: epifanie chiare. Accompagnate da… Secondo: … Terzo: … | elenco → frasi |
| Epigrafi (`> *"La natura non fa mai nulla di superfluo."* — Aristotele`) | La natura non fa mai nulla di superfluo. Aristotele. | citazione letta, poi l'autore |
| Free Energy Principle, surprisal, Garbage Collection, ethernet | invariati | termini tecnici del saggio |
| Friston, Fermat, Riemann, Mandelbrot, Amari, Shun-ichi, Kingma, Welling, Arvanitidis, Busemeyer, Bruza, Tversky, Shafir, Da Costa, Parr, Sengupta | invariati | verificare al primo ascolto |
| Ted Chiang, *Arrival*, Philip K. Dick, *VALIS*, Asimov, Lao Tzu, wu wei, Sama, Shiva Nataraja | invariati | verificare al primo ascolto (VALIS: "Valis") |

## Regole del romanzo non applicabili

Lo script viene da mantra-prompting. Nel saggio non ci sono Morse, box di sistema, pannelli, onomatopee né Demolition Log: le regole relative vanno tolte dal generatore, e i suoni d'ambiente (`[sfx …]`) non si usano.

## Copertina

`podcast/cover/cover.jpg`, 3000×3000, generata da `podcast/cover/make_cover.py` (solo Pillow e font di sistema): griglia curvata da un pozzo di potenziale, la geodetica che la attraversa, titolo e autore. Va copiata in `docs/cover.jpg` al passo del sito.

## Aperto

- **GitHub Pages** sulla cartella `docs/`: la attiva l'autore. `build_sito.py` va semplificato (personaggi e grafo non esistono nel saggio).
