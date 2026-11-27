---
name: podcast
description: Turn the book into a narrated podcast — one episode per chapter. Picks and tunes the narrator voice with audio samples, adapts each chapter into a script written for the ear (author approves every script), then renders MP3 episodes and an RSS feed. 100% free and open source — Piper TTS (offline) + ffmpeg. No API keys, no paid services.
---

# Skill: Podcast

> **Language**: `book.config.json → language`. Author may write in any language; always reply in the configured one. Default: English.

Usage:
- `/podcast` — full flow (voice → plan → scripts → audio), resumes where it left off
- `/podcast voice` — choose or change the narrator voice and character voices
- `/podcast jingle` — compose or change the intro jingle (step 1c)
- `/podcast script [chapter]` — adapt one chapter into an episode script
- `/podcast build [episode]` — render audio for one or all approved scripts
- `/podcast feed` — generate `podcast/feed.xml` for Spotify / Apple Podcasts

Format: **narrated**. One narrator reads the book, with light adaptation for listening. The chapters in `chapters/` are never modified.

---

## Prerequisites

Check both, and if something is missing give the install command and stop:
```bash
python3 -c "import piper, numpy"   # pip install piper-tts numpy
ffmpeg -version                     # apt install ffmpeg · brew install ffmpeg · winget install ffmpeg
```
Source text: `manuscript/[title]-final.md` if it exists (split by `# ` headings), otherwise the chapters in `chapters/` in outline order. If a chapter is still `draft`, warn the author once: the podcast is best made from integrated text.

---

## Step 1 — Voice

Run this on the first use, if `book.config.json → podcast.voice` is empty, or on `/podcast voice`.

### 1a. Narrator
1. List the voices available for the book's language:
   ```bash
   python3 export_podcast.py voices it
   ```
   Recommend 2 or 3 of them, preferring `medium` or `high` quality. Defaults by language: `it_IT-paola-medium`, `en_US-lessac-medium`, `es_ES-davefx-medium`, `fr_FR-siwis-medium`, `de_DE-thorsten-medium`, `pt_BR-faber-medium`. For a multi-speaker voice, use `VOICE:ID` to pick a speaker (for example `en_US-libritts_r-medium:42`).
2. Render a sample of each voice from a real passage of the book (2 or 3 sentences from the first chapter, so the author hears their own prose):
   ```bash
   python3 export_podcast.py sample it_IT-paola-medium it_IT-riccardo-x_low --text "…passage…"
   ```
   Output: `podcast/samples/[voice].mp3`. Ask the author to listen and pick one.
3. Tune the voice with the author, rendering a new sample after each change:
   - **Speed** (`speed`): `1.0` is natural, `0.9` is slower and suits narrative, `1.1` is faster and suits manuals.
   - **Pauses** (`sentence_pause`, `paragraph_pause`, in seconds): longer pauses give a calmer, more literary feel.
4. Save the choices to `book.config.json → podcast`.

### 1b. Character voices (optional; suggest only for the fiction, fable, children's-book and biography presets)
If the book has dialogue and profiled characters in `characters/`, ask whether the main characters should have their own voice. For each one, render a sample with a line of that character's dialogue, then save it:
```json
"voices": { "MARIO": { "voice": "it_IT-riccardo-x_low", "speed": 1.05 } }
```
Default is no character voices: the narrator reads everything, like a classic audiobook.

### 1c. Intro jingle (optional)
Ask whether the author wants an intro jingle. The voice starts over the jingle's tail; `intro_overlap` sets how many seconds of overlap, default 1.5. Offer three options:

**A. Composed jingle (default, offline, no license issues).** The script composes an original 6–9 second sting with no samples. The style comes from the preset: essay and biography → `warm`, manual → `upbeat`, fiction → `mysterious`, fable and children's book → `playful`. The seed is derived from the title, so each book gets its own jingle and the same seed always gives the same result.
```bash
python3 export_podcast.py jingle                          # style from preset
python3 export_podcast.py jingle --style upbeat --seed 7  # another variation
python3 export_podcast.py jingle --seconds 5              # shorter
```
Extra style `grime`: a 140 bpm grime beat (half-time snare, eskibeat square bass, triplet hat rolls) under an eerie sci-fi whistle with vibrato and echo. The lead melody is original. Never reproduce a copyrighted theme, even if the author asks for "the X-Files one": take inspiration from the mood only.
```bash
python3 export_podcast.py jingle --style grime --seed 2 --seconds 9
```
**Seamless loop with real instruments (`grime-loop`).** Use this style when the author wants a beat that works on continuous repeat, like a hip hop or grime instrumental. The whistle is the lead and always sits on top: the rest of the mix ducks under it. It is the only synthesized part, with a clean digital sound: almost no vibrato and a short glide, plus a bit-crushed 8-bit delay. The loop uses the dorian minor mode with an i–IV–i–bVII progression, which sounds hip hop rather than horror. Drums, clap, hi-hats, crash, ratchet, piano 7th chords and piano bass are real recordings from the **VCSL** (Versilian Community Sample Library, CC0, https://github.com/sgossner/VCSL). They are downloaded on first use into `podcast/music/kit/vcsl/` (~25 MB). Reverb and echo tails wrap around to the start, so the loop has no gap or fade at the seam. The same seed keeps the same key, melodic contour and bass pattern as `grime`.
```bash
python3 export_podcast.py jingle --style grime-loop --seed 1            # 8 bars ≈ 13.7 s
python3 export_podcast.py jingle --style grime-loop --seed 1 --bars 16
python3 export_podcast.py jingle --style grime-loop --seed 1 --bpm 150   # faster (default 140)
python3 export_podcast.py jingle --style grime-loop --seed 1 --bpm 150 --bed 0.4   # instruments in the background (1.0 = default, 0.25 = barely there)
```
For continuous play, deliver the **WAV**. MP3 adds encoder padding and leaves a tiny gap at each repeat. When the loop is used as `intro_music`, the episode fades it out under the voice automatically. The author's own `kick.*`, `snare.*` and `hat.*` in `podcast/music/kit/` replace the VCSL ones.

If the author dislikes the synthesized drums, there are two alternatives. The same seed keeps the same melody and bass in both:
- `--drums none`: whistle, pad and bass only.
- `--drums kit`: real drum samples from `podcast/music/kit/` (`kick.*`, `snare.*`, `hat.*`, any audio format). A missing piece falls back to the synth. Suggest CC0 one-shots from Freesound (license filter: Creative Commons 0) or the author's own samples. Never download them on the author's behalf.
Output: `podcast/music/jingle-[style]-[seed].wav`. The author listens and asks for "another one" (new seed) or "more cheerful" (new style) until they like it.

**B. AI-generated music (ACE-Step, Apache-2.0, open source, local).** Requires a GPU with about 8 GB of VRAM, or an Apple Silicon Mac. Do not install it for the author. If they already have it, or want to install it themselves (https://github.com/ace-step/ACE-Step), write the prompt for them from `book.config.json` (genre, tone, target reader, premise):
- **Tags**: comma-separated genre, instruments, mood and BPM, for example `cinematic, piano, soft strings, warm, hopeful, 85 bpm, instrumental, podcast intro`.
- **Lyrics**: `[instrumental]`.
- **Duration**: 10–15 seconds, so the author can trim it.
After generation, the file goes in `podcast/music/`. Do not suggest MusicGen: its weights are non-commercial (CC-BY-NC).

**C. The author's own file**, or CC0 music (for example Freesound with the CC0 filter). Never download music on the author's behalf without asking.

Save the path in `podcast.intro_music`. For the outro, reuse the same file or leave it `null`.

---

## Step 2 — Episode plan

Propose one episode per chapter. Merge very short chapters (under ~800 words) and split very long ones (over ~6,000 words, roughly 40 minutes), using a scene or section break as the split point. Show the plan:

```
PODCAST PLAN — [title]
  Ep 1  Introduzione                 ~1,900 words · ~13 min
  Ep 2  Cap. 1 — [title]             ~3,400 words · ~23 min
  …
```
Estimate about 150 words per minute at `speed` 1.0. Wait for the author's confirmation, then save the plan to `podcast/plan.md` with a status per episode (`todo`, `script`, `approved`, `rendered`).

---

## Step 3 — Script (one episode at a time)

Write `podcast/scripts/episode-NN.md`:

```markdown
---
episode: 2
title: "Capitolo 1 — [title]"
description: "[1-2 sentences for the podcast app, no spoilers]"
source: chapters/01-slug.md
status: script
---
[Opening: 1-2 sentences. Book title, episode number, chapter title. From episode 2 on, add one sentence recalling where the previous episode left off.]

[pause 1]

# [Chapter title]

[Adapted text]

[pause 1.5]

[Closing: 1 sentence anticipating the next episode, with no spoilers.]
```

### Adaptation rules (narrated format: stay close to the text)
The author's voice comes first: keep their sentences, rhythm and vocabulary. Only change what does not work for the ear:
- **Visual structure**: turn lists into spoken sentences ("ci sono tre ragioni. La prima…"). Describe a table in words or drop it. Put footnotes inline or drop them.
- **Visual references**: rewrite "vedi sopra", "nella figura", "nella tabella seguente" or drop them.
- **Pronunciation**: spell out numbers, dates, symbols and abbreviations when the TTS could misread them ("€ 1.500" → "millecinquecento euro", "ecc." → "eccetera", "cap. 3" → "capitolo tre"). Spell out acronyms if they should be read letter by letter.
- **Sentences that are too long**: a sentence over ~45 words may be split at a natural point. Never change its meaning.
- **Dialogue**: with character voices, put `[voice NAME]` before the line and `[narrator]` after it. The attribution ("disse Mario") stays with the narrator.
- **Pauses**: `[pause 1]` at scene breaks, `[pause 2]` at major turns.
- Apply `style-rules.md` only to the text you add (opening, closing, rewritten lists).

### Approval
Show the author:
1. The opening and closing lines.
2. A compact list of every change from the original (`3.4 elenco → frase`, `5.2 "€ 1.500" → "millecinquecento euro"`). This is the list of changes, not the whole script.

When the author approves, set `status: approved` in the script and update `podcast/plan.md`. Nothing goes to audio before approval.

---

## Step 4 — Audio

```bash
python3 export_podcast.py build                   # all scripts
python3 export_podcast.py build episode-02.md     # one episode
```
Output: `podcast/episodes/episode-NN.mp3`, mono at 96 kbps, which is the standard for spoken-word podcasts, with ID3 tags (title, book, author, track). The first run downloads the Piper voices into `podcast/voices/` (~60 MB each). Rendering then works offline.

Before rendering, check that every `[voice NAME]` used in the scripts is defined in `podcast.voices`. After rendering, report the duration of each episode and suggest listening to the first 2 minutes of episode 1 before publishing.

When the author reports a word that is mispronounced, fix the spelling in the script and re-render only that episode. Do not change the chapter. Write the fix to the `## Pronunciation` section of `podcast/plan.md`, so later scripts apply it automatically.

---

## Step 5 — Feed (optional)

```bash
python3 export_podcast.py feed
```
Ask for `podcast.base_url`, the public folder where the MP3s will be hosted. Free options: GitHub Releases, the Internet Archive, or the author's own site. The skill generates `podcast/feed.xml`, ready to submit to Spotify for Creators, Apple Podcasts and other directories. Remind the author to add a 3000×3000 cover image in their hosting or directory.

---

## Config reference (`book.config.json → podcast`)

```json
"podcast": {
  "voice": "it_IT-paola-medium",
  "speaker": null,
  "speed": 0.95,
  "sentence_pause": 0.35,
  "paragraph_pause": 0.9,
  "voices": {},
  "intro_music": null,
  "outro_music": null,
  "intro_overlap": 1.5,
  "bitrate": "96k",
  "base_url": ""
}
```

---

## Closing

> Podcast ready: [N] episodes, [total] minutes, in `podcast/episodes/`.
> Next: listen to episode 1, then `/podcast feed` when you're ready to publish.
