# Piano podcast — L'universo a minima energia

Formato: narrato, una voce. Motore: ElevenLabs (`eleven_v4`), voce Dimitri (`irpmjMzI7WEB83hTpOZA`), stability 0,5, similarity_boost 0,75, style 0, speed 1,0. Audio in cache in `podcast/cache/`.
Intro: `podcast/music/*.wav` da generare con `export_podcast.py jingle --style grime-loop --seed 1 --bpm 150 --bed 0.25`, intro_overlap 1,5. Nessuna outro. Bitrate 96k.
Fonte: `chapters/` (copia identica di `saggio.md`, una sezione per file, tutti `complete`). I copioni si rigenerano con `python3 export_podcast.py scripts`; `python3 export_podcast.py check` segnala i copioni non allineati. Descrizione, riassunto iniziale (`recap`) e gancio finale (`teaser`) vivono nel frontmatter di ogni copione.

## Episodi (proposta)

Regola della skill: le sezioni sotto le ~800 parole si accorpano. Stima a 150 parole al minuto.

| Ep | Sezioni | Parole | Durata | Stato |
|---|---|---|---|---|
| 1 | Introduzione — La luce, la sfera e il costo del pensiero + Capitolo I — La fisica dell'equilibrio | 1.592 | ~11 min | todo |
| 2 | Capitolo II — L'osservatore e la realtà | 1.379 | ~9 min | todo |
| 3 | Capitolo III — Le epifanie: segnali del campo | 1.073 | ~7 min | todo |
| 4 | Capitolo IV — Il campo condiviso: la fisica delle relazioni | 1.136 | ~8 min | todo |
| 5 | Capitolo V — La geometria del destino + Conclusione — L'arte di scorrere | 1.044 | ~7 min | todo |
| 6 | Appendice II — Friston + Appendice III — Lo spazio latente e la geometria dell'informazione | 1.634 | ~11 min | todo |

Totale: sei episodi, circa 53 minuti.

**Appendice I (bibliografia, 556 parole): esclusa.** È un elenco di autori e opere, pensato per la pagina. Alternativa: episodio 7 a sé, o accorpata al 6.

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
| Elenco numerato in 3.1 (`1. **Epifanie chiare**: …`) | Il primo livello: le epifanie chiare. … Il secondo… Il terzo… | elenco → frasi |
| Epigrafi (`> *"La natura non fa mai nulla di superfluo."* — Aristotele`) | La natura non fa mai nulla di superfluo. Aristotele. | citazione letta, poi l'autore |
| Free Energy Principle, surprisal, Garbage Collection, ethernet | invariati | termini tecnici del saggio |
| Friston, Fermat, Riemann, Mandelbrot, Amari, Shun-ichi, Kingma, Welling, Arvanitidis, Busemeyer, Bruza, Tversky, Shafir, Da Costa, Parr, Sengupta | invariati | verificare al primo ascolto |
| Ted Chiang, *Arrival*, Philip K. Dick, *VALIS*, Asimov, Lao Tzu, wu wei, Sama, Shiva Nataraja | invariati | verificare al primo ascolto (VALIS: "Valis") |

## Regole del romanzo non applicabili

Lo script viene da mantra-prompting. Nel saggio non ci sono Morse, box di sistema, pannelli, onomatopee né Demolition Log: le regole relative vanno tolte dal generatore, e i suoni d'ambiente (`[sfx …]`) non si usano.

## Da confermare prima dei copioni

- Accorpamenti degli episodi e esclusione dell'Appendice I.
- Categoria del feed: nel config c'è Fiction / Science Fiction, come da istruzioni; per un saggio la proposta è Society & Culture / Philosophy.
- Descrizione del podcast (due righe): nel config c'è il segnaposto "DA CONFERMARE".
- Pubblicazione su GitHub Pages di questo repository (`simonediroma.github.io/quantum_fatalism`): `base_url`, `feed_url`, `link` e `cover_url` sono impostati così. La copertina (3000×3000) non esiste ancora.
- Il sito: `build_sito.py` di mantra-prompting si appoggia a personaggi e grafo, che il saggio non ha; va semplificato prima del passo 5.
