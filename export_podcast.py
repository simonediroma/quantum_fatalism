#!/usr/bin/env python3
"""
Ghost Writer — Podcast Export Script
Turns the episode scripts in podcast/scripts/ into MP3 episodes, using
Piper (free, offline neural TTS) or ElevenLabs (paid API) + ffmpeg.

Usage:
  python3 export_podcast.py voices [lang]          # list voices (Piper catalog, or your ElevenLabs voices)
  python3 export_podcast.py sample VOICE [...]     # download voice(s), render a short sample
  python3 export_podcast.py scripts [NN...]        # rebuild podcast/scripts/ from chapters/ (keeps
                                                   # description/recap/teaser/status of each script)
  python3 export_podcast.py check                  # exit 1 if a script is out of sync with its chapter
  python3 export_podcast.py sfx [names...]         # render the sound-effect palette to podcast/sfx/ (+ palette.mp3)
  python3 export_podcast.py cost [scripts...]      # characters build would send to ElevenLabs, net of the cache
  python3 export_podcast.py build [scripts...]     # render episodes (default: all scripts)
  python3 export_podcast.py feed                   # write podcast/feed.xml (RSS)
  python3 export_podcast.py jingle [--style S] [--seconds N] [--seed N] [--drums synth|kit|none]
                                   [--bars N] [--bpm N] [--bed 0.4]  # --style grime-loop: seamless beat,
                                                   # real samples; --bed = instruments level
                                                   # compose an intro jingle (podcast/music/)

Script tags (one per line):
  [pause 2]            silence, in seconds
  [voice NAME]         switch to a voice defined in podcast.voices (dialogue, characters)
  [narrator]           back to the narrator voice
  [sfx NAME]           sound effect between sentences; [sfx NAME under] = quiet bed under the next paragraph
  [sfx morse TESTO]    real Morse beeps (old-radio tone) for TESTO; add "under" to play it under the next paragraph

Requires: pip install piper-tts numpy · ffmpeg in PATH
ElevenLabs: set podcast.engine = "elevenlabs", podcast.voice = a voice_id, and the
ELEVENLABS_API_KEY environment variable (or, in a cloud session, a network secret
for api.elevenlabs.io sent as the xi-api-key header). Rendered audio is cached in
podcast/cache/ so re-rendering an unchanged paragraph costs no credits.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import wave
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from xml.sax.saxutils import escape

import numpy as np


DEFAULT_VOICES = {
    "it": "it_IT-paola-medium",
    "en": "en_US-lessac-medium",
    "es": "es_ES-davefx-medium",
    "fr": "fr_FR-siwis-medium",
    "de": "de_DE-thorsten-medium",
    "pt": "pt_BR-faber-medium",
}

DEFAULT_PODCAST = {
    "engine": "piper",        # "piper" (free, offline) or "elevenlabs" (paid API)
    "model": "eleven_multilingual_v2",  # ElevenLabs model id
    "stability": 0.5,         # ElevenLabs voice settings
    "similarity_boost": 0.75,
    "style": 0.0,
    "voice": None,            # Piper voice id (e.g. it_IT-paola-medium) or ElevenLabs voice_id
    "speaker": None,          # speaker id, only for multi-speaker voices
    "speed": 1.0,             # 1.0 = natural, 0.9 = slower, 1.1 = faster
    "sentence_pause": 0.35,   # seconds between sentences
    "paragraph_pause": 0.9,   # seconds between paragraphs
    "voices": {},             # extra voices: {"NAME": {"voice": "...", "speaker": null, "speed": 1.0}}
    "intro_music": None,      # path to an audio file (CC0 / own music)
    "outro_music": None,
    "intro_overlap": 1.5,     # seconds the voice starts before the intro music ends
    "bitrate": "96k",
    "base_url": "",           # public URL where the MP3s will be hosted (for feed.xml)
    "feed_url": "",           # public URL of feed.xml itself
    "link": "",               # podcast website (defaults to base_url)
    "description": "",        # show description (defaults to the book subtitle/title)
    "cover_url": "",          # 3000x3000 JPG/PNG, required by Spotify and Apple
    "owner_name": "",         # defaults to the book author
    "owner_email": "",        # required by Spotify and Apple to verify ownership
    "category": "Fiction",    # Apple Podcasts category
    "subcategory": None,      # e.g. "Science Fiction"
    "explicit": False,
    "type": "episodic",       # "serial" when episodes must be heard in order
}

SAMPLE_RATE = 22050
VOICES_JSON = "https://huggingface.co/rhasspy/piper-voices/resolve/main/voices.json?download=true"
ELEVENLABS_API = "https://api.elevenlabs.io/v1"
ELEVENLABS_MAX_CHARS = 1000


# ─── Config ───────────────────────────────────────────────────────────────────

def load_config(project_dir):
    config_path = Path(project_dir) / "book.config.json"
    if config_path.exists():
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    return {}

def podcast_settings(config):
    settings = dict(DEFAULT_PODCAST)
    settings.update(config.get("podcast") or {})
    lang = (config.get("language") or "en")[:2]
    if not settings["voice"] and settings["engine"] == "piper":
        settings["voice"] = DEFAULT_VOICES.get(lang, DEFAULT_VOICES["en"])
    return settings

def author_name(config):
    return (
        config.get("author_profile", {}).get("name") or
        config.get("author", {}).get("name") or
        "Author"
    )


# ─── Voices ───────────────────────────────────────────────────────────────────

def voices_dir(project_dir):
    d = Path(project_dir) / "podcast" / "voices"
    d.mkdir(parents=True, exist_ok=True)
    return d

def list_voices(lang):
    with urlopen(VOICES_JSON) as r:
        catalog = json.load(r)
    rows = []
    for key, v in sorted(catalog.items()):
        if not key.lower().startswith(lang.lower()):
            continue
        speakers = len(v.get("speaker_id_map") or {}) or 1
        rows.append(f"  {key:<36} quality={v.get('quality', '?'):<8} speakers={speakers}")
    print("\n".join(rows) if rows else f"No voices found for '{lang}'.")

def ensure_voice(project_dir, voice_id):
    d = voices_dir(project_dir)
    model = d / f"{voice_id}.onnx"
    if not model.exists() or not (d / f"{voice_id}.onnx.json").exists():
        print(f"Downloading voice {voice_id}...")
        subprocess.run(
            [sys.executable, "-m", "piper.download_voices", voice_id, "--download-dir", str(d)],
            check=True,
        )
    return model

_loaded = {}

def load_voice(project_dir, voice_id):
    if voice_id not in _loaded:
        from piper import PiperVoice
        _loaded[voice_id] = PiperVoice.load(str(ensure_voice(project_dir, voice_id)))
    return _loaded[voice_id]


# ─── Synthesis ────────────────────────────────────────────────────────────────

def elevenlabs_request(path, payload=None):
    # Without ELEVENLABS_API_KEY the request goes out keyless: in a Claude Code cloud
    # session a network secret for api.elevenlabs.io adds the xi-api-key header.
    headers = {"Content-Type": "application/json"}
    if os.environ.get("ELEVENLABS_API_KEY"):
        headers["xi-api-key"] = os.environ["ELEVENLABS_API_KEY"]
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(ELEVENLABS_API + path, data=data, headers=headers)
    for attempt in range(4):
        try:
            with urlopen(req) as r:
                return r.read()
        except HTTPError as e:
            if e.code < 500 and e.code != 429 or attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))

def list_elevenlabs_voices():
    voices = json.loads(elevenlabs_request("/voices"))["voices"]
    for v in sorted(voices, key=lambda v: v["name"]):
        labels = ", ".join(f"{k}={x}" for k, x in (v.get("labels") or {}).items())
        print(f"  {v['voice_id']}  {v['name']:<28} {labels}")

def synthesize_elevenlabs(project_dir, text, voice_cfg, previous_text=None, next_text=None):
    """One paragraph via the ElevenLabs API, cached by text + voice settings."""
    params = {k: voice_cfg.get(k) for k in ("voice", "model", "speed", "stability", "similarity_boost", "style")}
    key = hashlib.sha256(json.dumps([text, params], sort_keys=True).encode()).hexdigest()[:24]
    cache = Path(project_dir) / "podcast" / "cache" / "elevenlabs" / f"{key}.pcm"
    if not cache.exists():
        payload = {
            "text": text,
            "model_id": params["model"],
            "voice_settings": {
                "stability": params["stability"],
                "similarity_boost": params["similarity_boost"],
                "style": params["style"],
                "speed": min(max(float(params["speed"] or 1.0), 0.7), 1.2),
            },
        }
        if previous_text:
            payload["previous_text"] = previous_text
        if next_text:
            payload["next_text"] = next_text
        pcm = elevenlabs_request(f"/text-to-speech/{params['voice']}?output_format=pcm_{SAMPLE_RATE}", payload)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(pcm)
    return np.frombuffer(cache.read_bytes(), dtype=np.int16)

def synthesize(project_dir, text, voice_cfg):
    """Return mono int16 audio at SAMPLE_RATE for one sentence."""
    from piper import SynthesisConfig
    voice = load_voice(project_dir, voice_cfg["voice"])
    syn = SynthesisConfig(
        speaker_id=voice_cfg.get("speaker"),
        length_scale=1.0 / float(voice_cfg.get("speed") or 1.0),
    )
    chunks, rate = [], SAMPLE_RATE
    for chunk in voice.synthesize(text, syn_config=syn):
        rate = chunk.sample_rate
        chunks.append(np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16))
    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)
    return resample(audio, rate)

def resample(audio, rate):
    if rate == SAMPLE_RATE or audio.size == 0:
        return audio
    n = int(round(audio.size * SAMPLE_RATE / rate))
    x = np.linspace(0, audio.size - 1, n)
    return np.interp(x, np.arange(audio.size), audio).astype(np.int16)

def silence(seconds):
    return np.zeros(int(SAMPLE_RATE * max(seconds, 0)), dtype=np.int16)


# ─── Script parsing ───────────────────────────────────────────────────────────

def split_frontmatter(text):
    meta = {}
    m = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"\'')
        text = text[m.end():]
    return meta, text

def clean_inline(line):
    line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)   # links → text
    line = re.sub(r"[*_`]+", "", line)                        # emphasis
    line = re.sub(r"^\s*([-*+]|\d+\.)\s+", "", line)          # list markers
    line = re.sub(r"^\s*>\s?", "", line)                      # blockquote
    return line.strip()

def split_sentences(paragraph):
    parts = re.split(r"(?<=[.!?…»”])\s+", paragraph)
    return [p for p in (s.strip() for s in parts) if p]

def parse_script(text):
    """Yield events: ('say', voice_name, sentence) · ('pause', seconds) · ('para',)."""
    events, voice, buffer = [], None, []

    def flush():
        if buffer:
            for s in split_sentences(" ".join(buffer)):
                events.append(("say", voice, s))
            events.append(("para",))
            buffer.clear()

    for raw in text.splitlines():
        line = raw.strip()
        tag = re.fullmatch(r"\[(pause|voice|narrator|sfx)\s*([^\]]*)\]", line, flags=re.IGNORECASE)
        if tag:
            flush()
            kind, arg = tag.group(1).lower(), tag.group(2).strip()
            if kind == "sfx":
                parts = arg.split()
                if parts and parts[0].lower() == "morse":
                    words = [w for w in parts[1:] if w.lower() != "under"]
                    events.append(("morse", " ".join(words), "under" in [w.lower() for w in parts[1:]]))
                else:
                    events.append(("sfx", parts[0], len(parts) > 1 and parts[1].lower() == "under"))
            elif kind == "pause":
                events.append(("pause", float(arg.rstrip("s") or 1)))
            elif kind == "voice":
                voice = arg or None
            else:
                voice = None
        elif not line or line == "---":
            flush()
        elif line.startswith("#"):
            flush()
            buffer.append(line.lstrip("#").strip() + ".")
            flush()
        else:
            cleaned = clean_inline(line)
            if cleaned:
                buffer.append(cleaned)
    flush()
    return events


# ─── Rendering ────────────────────────────────────────────────────────────────

def voice_config(settings, name):
    base = {k: settings[k] for k in ("engine", "voice", "speaker", "speed", "model", "stability", "similarity_boost", "style")}
    if name is None:
        return base
    extra = settings["voices"].get(name)
    if extra is None:
        raise SystemExit(f"Voice '{name}' is used in a script but not defined in podcast.voices")
    if isinstance(extra, str):
        extra = {"voice": extra}
    return {**base, **extra}

def render_events(project_dir, events, settings):
    if settings["engine"] == "elevenlabs":
        return render_events_elevenlabs(project_dir, events, settings)
    pieces = []
    for ev in events:
        if ev[0] == "say":
            pieces.append(("audio", synthesize(project_dir, ev[2], voice_config(settings, ev[1]))))
            pieces.append(("audio", silence(settings["sentence_pause"])))
        elif ev[0] in ("sfx", "morse"):
            pieces.append(ev)
        elif ev[0] == "pause":
            pieces.append(("audio", silence(ev[1])))
        else:
            pieces.append(("audio", silence(settings["paragraph_pause"])))
    return apply_sfx(project_dir, pieces, settings)

def render_events_elevenlabs(project_dir, events, settings):
    """Whole paragraphs per request: better prosody than sentence by sentence."""
    # Long paragraphs are split at sentence boundaries: very long requests fail (502).
    blocks, current = [], None
    for ev in events:
        if ev[0] == "say":
            if current and current[0] == ev[1] and len(" ".join(current[1])) + len(ev[2]) < ELEVENLABS_MAX_CHARS:
                current[1].append(ev[2])
            else:
                if current and current[0] == ev[1]:
                    blocks.append(("join",))
                current = [ev[1], [ev[2]]]
                blocks.append(("say", current))
        else:
            current = None
            blocks.append(ev)
    texts = [" ".join(b[1][1]) for b in blocks if b[0] == "say"]
    pieces, i = [], 0
    for b in blocks:
        if b[0] == "say":
            prev = texts[i - 1] if i > 0 else None
            nxt = texts[i + 1] if i + 1 < len(texts) else None
            pieces.append(("audio", synthesize_elevenlabs(project_dir, texts[i], voice_config(settings, b[1][0]), prev, nxt)))
            i += 1
        elif b[0] in ("sfx", "morse"):
            pieces.append(b)
        elif b[0] == "pause":
            pieces.append(("audio", silence(b[1])))
        elif b[0] == "join":
            pieces.append(("audio", silence(settings["sentence_pause"])))
        else:
            pieces.append(("audio", silence(settings["paragraph_pause"])))
    return apply_sfx(project_dir, pieces, settings)

def write_wav(path, audio):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(audio.tobytes())

def audio_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())

def encode_mp3(project_dir, wav_path, mp3_path, settings, meta):
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg not found — install it (apt install ffmpeg / brew install ffmpeg)")
    music = {}
    for key in ("intro_music", "outro_music"):
        if settings.get(key):
            path = Path(project_dir) / settings[key]
            if not path.exists():
                raise SystemExit(f"{key} not found: {settings[key]}")
            music[key] = path

    inputs, filters, n = [], [], 0
    def add_input(path):
        nonlocal n
        inputs.extend(["-i", str(path)])
        filters.append(f"[{n}:a]aresample=44100,aformat=channel_layouts=mono[a{n}]")
        n += 1
        return f"[a{n - 1}]"

    voice = add_input(wav_path)
    if "intro_music" in music:
        intro = add_input(music["intro_music"])
        delay = max(audio_duration(music["intro_music"]) - float(settings["intro_overlap"]), 0)
        fade = float(settings["intro_overlap"]) + 0.5
        chain, label = filters[-1].rsplit("[", 1)
        filters[-1] = f"{chain},afade=t=out:st={max(delay - 0.5, 0):.2f}:d={fade:.2f}[{label}"
        filters.append(f"{voice}adelay={int(delay * 1000)}[vd]")
        filters.append(f"{intro}[vd]amix=inputs=2:duration=longest:normalize=0[iv]")
        voice = "[iv]"
    if "outro_music" in music:
        outro = add_input(music["outro_music"])
        filters.append(f"{voice}{outro}concat=n=2:v=0:a=1[out]")
    else:
        filters.append(f"{voice}anull[out]")

    tags = []
    for k, v in meta.items():
        if v:
            tags += ["-metadata", f"{k}={v}"]
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(filters),
         "-map", "[out]", "-codec:a", "libmp3lame", "-b:a", settings["bitrate"], *tags, str(mp3_path)],
        check=True,
    )

def episode_scripts(project_dir, names):
    scripts_dir = Path(project_dir) / "podcast" / "scripts"
    if names:
        return [Path(n) if Path(n).exists() else scripts_dir / n for n in names]
    return sorted(scripts_dir.glob("*.md"))

def build(project_dir, names):
    project_dir = Path(project_dir)
    config = load_config(project_dir)
    settings = podcast_settings(config)
    scripts = episode_scripts(project_dir, names)
    if not scripts:
        raise SystemExit("No scripts found in podcast/scripts/ — run /ghost-writer:podcast first")
    out_dir = project_dir / "podcast" / "episodes"
    out_dir.mkdir(parents=True, exist_ok=True)

    for script in scripts:
        meta, body = split_frontmatter(script.read_text(encoding="utf-8"))
        events = parse_script(body)
        audio = render_events(project_dir, events, settings)
        wav_path = out_dir / f"{script.stem}.wav"
        mp3_path = out_dir / f"{script.stem}.mp3"
        write_wav(wav_path, audio)
        encode_mp3(project_dir, wav_path, mp3_path, settings, {
            "title": meta.get("title", script.stem),
            "album": config.get("title", ""),
            "artist": author_name(config),
            "track": meta.get("episode", ""),
            "language": config.get("language", ""),
        })
        wav_path.unlink()
        if (project_dir / "docs").is_dir():   # GitHub Pages hosts the MP3s next to the feed
            (project_dir / "docs" / "episodes").mkdir(exist_ok=True)
            shutil.copy2(mp3_path, project_dir / "docs" / "episodes" / mp3_path.name)
        minutes = audio.size / SAMPLE_RATE / 60
        print(f"✅ {mp3_path}  ({minutes:.1f} min)")


# ─── Sample ───────────────────────────────────────────────────────────────────

def sample(project_dir, voice_ids, text=None):
    project_dir = Path(project_dir)
    config = load_config(project_dir)
    settings = podcast_settings(config)
    if not text:
        text = f"{config.get('title', 'Ghost Writer')}. {config.get('subtitle', '')}".strip()
    out_dir = project_dir / "podcast" / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    for voice_id in voice_ids:
        voice_id, _, speaker = voice_id.partition(":")
        cfg = {**settings, "voice": voice_id, "speaker": int(speaker) if speaker else None, "voices": {}}
        audio = render_events(project_dir, parse_script(text), cfg)
        name = voice_id + (f"-{speaker}" if speaker else "")
        wav_path = out_dir / f"{name}.wav"
        write_wav(wav_path, audio)
        encode_mp3(project_dir, wav_path, out_dir / f"{name}.mp3", {**cfg, "intro_music": None, "outro_music": None}, {})
        wav_path.unlink()
        print(f"🎧 {out_dir / (name + '.mp3')}")


# ─── Jingle ───────────────────────────────────────────────────────────────────
# Composed from scratch with numpy: no samples, no licenses, same seed = same jingle.

JINGLE_STYLES = {
    #             scale    chords (scale degrees)  bpm  drums
    "warm":       ("major", [0, 5, 3, 4],          88,  False),
    "upbeat":     ("major", [0, 4, 5, 3],          116, True),
    "mysterious": ("minor", [0, 5, 2, 6],          70,  False),
    "playful":    ("major", [0, 3, 4, 0],          128, True),
}
PRESET_STYLES = {
    "essay": "warm", "manual": "upbeat", "fiction": "mysterious",
    "biography": "warm", "fable": "playful", "childrens-book": "playful",
}
SCALES = {"major": [0, 2, 4, 5, 7, 9, 11], "minor": [0, 2, 3, 5, 7, 8, 10]}
JINGLE_RATE = 44100

def midi_hz(note):
    return 440.0 * 2 ** ((note - 69) / 12)

def envelope(n, attack, release):
    env = np.ones(n)
    a, r = min(int(attack * JINGLE_RATE), n), min(int(release * JINGLE_RATE), n)
    if a:
        env[:a] = np.linspace(0, 1, a)
    if r:
        env[-r:] *= np.linspace(1, 0, r)
    return env

def pad_tone(freq, n):
    t = np.arange(n) / JINGLE_RATE
    tone = sum(np.sin(2 * np.pi * freq * k * d * t) / k ** 1.5 for k in range(1, 6) for d in (0.997, 1.003))
    return tone * envelope(n, 0.25, 0.6)

def bell_tone(freq, n):
    t = np.arange(n) / JINGLE_RATE
    tone = np.sin(2 * np.pi * freq * t) + 0.35 * np.sin(2 * np.pi * freq * 2.76 * t) * np.exp(-t * 9)
    return tone * np.exp(-t * 3.5) * envelope(n, 0.004, 0.05)

def kick(n):
    t = np.arange(n) / JINGLE_RATE
    return np.sin(2 * np.pi * (45 + 90 * np.exp(-t * 30)) * t) * np.exp(-t * 12)

def hat(n, rng):
    t = np.arange(n) / JINGLE_RATE
    noise = rng.standard_normal(n)
    noise = np.diff(noise, prepend=0)   # crude high-pass
    return noise * np.exp(-t * 60) * 0.15

def reverb(x):
    out = x.copy()
    for delay, gain in ((0.031, 0.35), (0.047, 0.3), (0.071, 0.25), (0.113, 0.2), (0.167, 0.15)):
        d = int(delay * JINGLE_RATE)
        y = np.zeros_like(x)
        for k in range(1, 5):
            if d * k < x.size:
                y[d * k:] += x[:-d * k] * gain ** k
        out += y
    return out

def place(track, sound, start):
    s = int(start * JINGLE_RATE)
    end = min(s + sound.size, track.size)
    if s < end:
        track[s:end] += sound[:end - s]

def compose_jingle(style="warm", seconds=7.0, seed=0):
    scale_name, progression, bpm, drums = JINGLE_STYLES[style]
    rng = np.random.default_rng(seed)
    scale = SCALES[scale_name]
    root = 57 + int(rng.integers(0, 7))          # A3..D#4
    beat = 60.0 / bpm
    tail = 2.5
    chord_len = max((seconds - tail) / len(progression), beat * 2)
    total = int((chord_len * len(progression) + tail) * JINGLE_RATE)

    def degree_note(deg, octave=0):
        return root + scale[deg % 7] + 12 * (deg // 7 + octave)

    pad, bass, bells, perc = (np.zeros(total) for _ in range(4))
    contour = rng.permutation([0, 1, 2, 1, 2, 0, 2, 1])
    for i, deg in enumerate(progression):
        start = i * chord_len
        last = i == len(progression) - 1
        length = chord_len + (tail if last else 0.3)
        n = int(length * JINGLE_RATE)
        chord = [degree_note(deg), degree_note(deg + 2), degree_note(deg + 4)]
        for note in chord:
            place(pad, pad_tone(midi_hz(note), n), start)
        place(bass, np.sin(2 * np.pi * midi_hz(chord[0] - 12) * np.arange(n) / JINGLE_RATE) * envelope(n, 0.02, 0.4), start)
        steps = 1 if last else int(chord_len / (beat / 2))
        for s in range(steps):
            note = chord[contour[(i * 3 + s) % len(contour)]] + 12
            if last:
                note = degree_note(0, 2)
            place(bells, bell_tone(midi_hz(note), int(1.5 * JINGLE_RATE)), start + s * beat / 2)
        if drums and not last:
            for b in range(int(chord_len / beat)):
                place(perc, kick(int(0.4 * JINGLE_RATE)), start + b * beat)
                place(perc, hat(int(0.1 * JINGLE_RATE), rng), start + b * beat + beat / 2)

    mix = 0.18 * pad + 0.35 * bass + 0.30 * bells + 0.5 * perc
    mix = reverb(mix)
    mix *= envelope(total, 0.05, tail)
    mix = mix / (np.max(np.abs(mix)) or 1) * 0.7
    return (mix * 32767).astype(np.int16)

def whistle_tone(freq, n, glide_from=None, vibrato_depth=0.012, glide=0.09):
    """Whistle: sine with delayed vibrato and an optional slide into the note."""
    t = np.arange(n) / JINGLE_RATE
    f = np.full(n, freq)
    if glide_from:
        g = min(int(glide * JINGLE_RATE), n)
        f[:g] = np.linspace(glide_from, freq, g)
    vibrato = 1 + vibrato_depth * np.sin(2 * np.pi * 5.5 * t) * np.clip(t / 0.4, 0, 1)
    phase = 2 * np.pi * np.cumsum(f * vibrato) / JINGLE_RATE
    tone = np.sin(phase) + 0.08 * np.sin(2 * phase)
    return tone * envelope(n, 0.06, min(0.25, n / JINGLE_RATE / 2))

def square_bass(freq, n):
    """Eskibeat-style square sub with a short downward pitch drop."""
    t = np.arange(n) / JINGLE_RATE
    f = freq * (1 + 0.5 * np.exp(-t * 40))
    phase = 2 * np.pi * np.cumsum(f) / JINGLE_RATE
    square = np.sign(np.sin(phase)) * 0.45 + np.sin(phase) * 0.55
    return square * np.exp(-t * 4.5) * envelope(n, 0.003, 0.03)

def snare(n, rng):
    t = np.arange(n) / JINGLE_RATE
    body = np.sin(2 * np.pi * 185 * t) * np.exp(-t * 25)
    noise = np.diff(rng.standard_normal(n), prepend=0) * np.exp(-t * 18) * 0.35
    return body * 0.6 + noise

def echo(x, delay, feedback, repeats=5):
    out = x.copy()
    d = int(delay * JINGLE_RATE)
    for k in range(1, repeats + 1):
        if d * k < x.size:
            out[d * k:] += x[:-d * k] * feedback ** k
    return out

def load_sample(path):
    """Decode any audio file to mono float at JINGLE_RATE via ffmpeg."""
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-f", "s16le", "-ac", "1", "-ar", str(JINGLE_RATE), "-"],
        check=True, capture_output=True,
    ).stdout
    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float64)
    return audio / (np.max(np.abs(audio)) or 1)

def load_kit(kit_dir):
    """Real drum samples: kick.*, snare.*, hat.* in kit_dir. Missing ones fall back to synth."""
    kit = {}
    for name in ("kick", "snare", "hat"):
        found = sorted(Path(kit_dir).glob(f"{name}.*"))
        if found:
            kit[name] = load_sample(found[0])
    return kit

def compose_grime(seconds=7.0, seed=0, drum_mode="synth", kit_dir=None):
    """140 bpm grime beat under a sci-fi whistle lead (half-time snare, square bass, hat rolls).
    drum_mode: "synth", "kit" (samples from kit_dir) or "none"."""
    rng = np.random.default_rng(seed)
    kit = load_kit(kit_dir) if drum_mode == "kit" and kit_dir else {}
    if drum_mode == "kit" and not kit:
        raise SystemExit(f"No drum samples found in {kit_dir} — add kick.wav, snare.wav, hat.wav")

    def hit(name, seconds_long, gain=1.0):
        if drum_mode == "none":
            return np.zeros(1)
        if name in kit:
            return kit[name][:int(seconds_long * 2 * JINGLE_RATE)] * gain * (0.5 if name == "hat" else 1)
        n = int(seconds_long * JINGLE_RATE)
        return {"kick": lambda: kick(n), "snare": lambda: snare(n, rng), "hat": lambda: hat(n, rng)}[name]() * gain
    root = 40 + int(rng.integers(0, 4))           # E2..G2
    beat = 60.0 / 140
    bar = beat * 4
    s16 = beat / 4
    bars = max(3, int(round((seconds - 2) / bar)))
    tail = 2.2
    total = int((bars * bar + tail) * JINGLE_RATE)
    phrygian = [0, 1, 3, 5, 7, 8, 10]

    def note(deg, octave):
        return root + phrygian[deg % 7] + 12 * (deg // 7 + octave)

    lead, pad, bass, drums = (np.zeros(total) for _ in range(4))

    # Lead: two original motifs, (degree, length in 16ths); slides between notes
    motifs = [
        [(4, 4), (7, 10), (9, 2), (8, 4), (7, 8), (5, 4), (8, 8), (7, 8), (1, 12)],
        [(7, 6), (4, 2), (8, 8), (7, 4), (9, 4), (8, 12), (5, 4), (8, 4), (7, 16)],
    ]
    pos, prev = 0.0, None
    for deg, length in motifs[int(rng.integers(0, len(motifs)))]:
        if pos >= bars * bar:
            break
        freq = midi_hz(note(deg, 2))
        n = int(length * s16 * JINGLE_RATE)
        place(lead, whistle_tone(freq, n, prev), pos)
        pos, prev = pos + length * s16, freq
    lead = echo(lead, beat * 0.75, 0.38)

    # Pad: dark i - bII - i - bVII voicing, one chord per bar
    progression = [0, 1, 0, 6]
    for b in range(bars):
        deg = progression[b % 4]
        n = int((bar + (tail if b == bars - 1 else 0.1)) * JINGLE_RATE)
        for d in (deg, deg + 2, deg + 4):
            place(pad, pad_tone(midi_hz(note(d, 1)), n), b * bar)

    # Beat drops after the first bar
    bass_patterns = [[0, 3, 6, 10, 11], [0, 3, 7, 10, 14], [0, 2, 6, 8, 11, 14]]
    bass_pattern = bass_patterns[int(rng.integers(0, len(bass_patterns)))]
    for b in range(1, bars):
        start = b * bar
        deg = progression[b % 4]
        for step in bass_pattern:
            place(bass, square_bass(midi_hz(note(deg, 0)), int(s16 * 2.5 * JINGLE_RATE)), start + step * s16)
        for step in (0, 10):
            place(drums, hit("kick", 0.35), start + step * s16)
        place(drums, hit("snare", 0.3), start + 8 * s16)
        roll = b % 2 == 0 or b == bars - 1
        for step in range(0, 16, 2):
            if roll and step >= 12:
                for k in range(3):                 # triplet hat roll
                    place(drums, hit("hat", 0.06), start + (step + k * 2 / 3) * s16)
            else:
                place(drums, hit("hat", 0.08), start + step * s16)
    # Final hit on the downbeat after the last bar
    place(drums, hit("kick", 0.5), bars * bar)
    place(drums, hit("snare", 0.4, 0.7), bars * bar)
    place(bass, square_bass(midi_hz(note(0, 0)), int(1.2 * JINGLE_RATE)), bars * bar)

    mix = 0.30 * lead + 0.07 * reverb(pad) + 0.40 * bass + 0.55 * drums
    mix *= envelope(total, 0.02, tail * 0.8)
    mix = np.tanh(mix / (np.max(np.abs(mix)) or 1) * 1.6)   # light saturation
    mix = mix / (np.max(np.abs(mix)) or 1) * 0.75
    return (mix * 32767).astype(np.int16)

# ─── Grime loop (real recorded samples) ───────────────────────────────────────
# Everything except the whistle lead is a real recording from the Versilian
# Community Sample Library (VCSL, CC0 — https://github.com/sgossner/VCSL),
# downloaded on first use into podcast/music/kit/vcsl/. The loop is seamless:
# reverb and echo tails wrap around to the start, so it can play on repeat.

VCSL_BASE = "https://raw.githubusercontent.com/sgossner/VCSL/master/"
VCSL_KIT = {
    "kick":   "Membranophones/Struck Membranophones/Bass Drum 1/BDrumNew_hit_v7_rr1_Sum.wav",
    "snare":  "Membranophones/Struck Membranophones/Snare Drum, Modern 1/Snare2_HitSN_v7_rr1_Mid.wav",
    "clap":   "Idiophones/Struck Idiophones/Claps/Clap_rr2.wav",
    "hat":    "Idiophones/Struck Idiophones/Hi-Hat Cymbal/HiHat_HitC_v2_rr1_Mid.wav",
    "openhat": "Idiophones/Struck Idiophones/Hi-Hat Cymbal/HiHat_HitO_rr1_Mid.wav",
    "crash":  "Idiophones/Struck Idiophones/Suspended Cymbal 1/susCymb1_hit_f1.wav",
    "ratchet": "Idiophones/Struck Idiophones/Ratchet/Ratchet1_Crank_rr1_Mid.wav",
}
PIANO_NOTES = ["C", "D", "E", "F#", "G#", "A#"]   # Steinway B is sampled every whole tone
NOTE_PC = {"C": 0, "D": 2, "E": 4, "F#": 6, "G#": 8, "A#": 10}

_samples = {}

def vcsl_sample(project_dir, rel_path):
    from urllib.parse import quote
    if rel_path in _samples:
        return _samples[rel_path]
    local = Path(project_dir) / "podcast" / "music" / "kit" / "vcsl" / rel_path
    if not local.exists():
        local.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {rel_path.split('/')[-1]} (VCSL, CC0)...")
        with urlopen(VCSL_BASE + quote(rel_path)) as r:
            local.write_bytes(r.read())
    _samples[rel_path] = load_sample(local)
    return _samples[rel_path]

def pitch_shift(audio, semitones):
    if semitones == 0:
        return audio
    ratio = 2 ** (semitones / 12)
    x = np.arange(0, audio.size - 1, ratio)
    return np.interp(x, np.arange(audio.size), audio)

def piano(project_dir, midi, sustain=True, velocity=3):
    """Real Steinway note: nearest sampled note, shifted by at most one semitone."""
    best = min(((n, o) for n in PIANO_NOTES for o in range(0, 8)),
               key=lambda no: abs((no[1] + 1) * 12 + NOTE_PC[no[0]] - midi))
    sampled = (best[1] + 1) * 12 + NOTE_PC[best[0]]
    kind = "Sus" if sustain else "NoSus"
    path = (f"Chordophones/Zithers/Grand Piano, Steinway B/{kind}/"
            f"JHPiano_{kind}_Close_{best[0]}{best[1]}_vl{velocity}_rr1.wav")
    return pitch_shift(vcsl_sample(project_dir, path), midi - sampled)

def trim(audio, seconds, fade=0.04):
    n = min(int(seconds * JINGLE_RATE), audio.size)
    return audio[:n] * envelope(n, 0.0, fade)

def bitcrush(x, bits=8, hold=4):
    """Digital lo-fi: fewer amplitude steps and a sample-and-hold downsample."""
    peak = np.max(np.abs(x)) or 1
    levels = 2 ** (bits - 1)
    crushed = np.round(x / peak * levels) / levels * peak
    return np.repeat(crushed[::hold], hold)[:x.size]

def duck(x, key, depth=0.5, smooth=0.08):
    """Lower x while key (the whistle) is playing — keeps the lead on top."""
    k = int(smooth * JINGLE_RATE)
    env = np.convolve(np.abs(key), np.ones(k) / k, mode="same")
    env = env / (np.max(env) or 1)
    return x * (1 - depth * np.clip(env * 2, 0, 1))

def rms(x):
    return np.sqrt(np.mean(x ** 2)) or 1

def compose_grime_loop(project_dir, seed=0, bars=8, bpm=140, bed_level=1.0):
    """Seamless 140 bpm grime loop: the whistle lead on top of real drums, piano and FX."""
    rng = np.random.default_rng(seed)
    root = 40 + int(rng.integers(0, 4))           # same draws as compose_grime: same key and melody
    motif_index = int(rng.integers(0, 2))
    pattern_index = int(rng.integers(0, 3))
    beat = 60.0 / bpm
    bar = beat * 4
    s16 = beat / 4
    loop_len = int(bars * bar * JINGLE_RATE)
    total = loop_len + int(4 * JINGLE_RATE)       # room for tails, wrapped at the end
    dorian = [0, 2, 3, 5, 7, 9, 10]               # minor but not spooky: hip hop, not horror

    def note(deg, octave):
        return root + dorian[deg % 7] + 12 * (deg // 7 + octave)

    # User samples in podcast/music/kit/ (kick.*, snare.*, hat.*) override the VCSL ones
    user_kit = load_kit(Path(project_dir) / "podcast" / "music" / "kit")
    kit = {name: user_kit.get(name) if name in user_kit else vcsl_sample(project_dir, path)
           for name, path in VCSL_KIT.items()}
    kit["kick"] = trim(kit["kick"], 0.45, 0.15)
    kit["snare"] = trim(kit["snare"], 0.35, 0.12)
    kit["clap"] = trim(kit["clap"], 0.3, 0.1)
    kit["hat"] = trim(kit["hat"], 0.09, 0.04)
    kit["openhat"] = trim(kit["openhat"], 0.35, 0.15)
    kit["crash"] = trim(kit["crash"], 3.5, 1.5)
    kit["ratchet"] = trim(kit["ratchet"], 0.6, 0.1)

    lead, keys, bass, drums, fx = (np.zeros(total) for _ in range(5))

    # Whistle lead (unchanged from the grime jingle), repeated every 4 bars: the mantra
    motifs = [
        [(4, 4), (7, 10), (9, 2), (8, 4), (7, 8), (5, 4), (8, 8), (7, 8), (1, 12)],
        [(7, 6), (4, 2), (8, 8), (7, 4), (9, 4), (8, 12), (5, 4), (8, 4), (7, 16)],
    ]
    for phrase_start in range(0, bars, 4):
        pos, prev = phrase_start * bar, None
        for deg, length in motifs[motif_index]:
            if pos >= min(phrase_start + 4, bars) * bar:
                break
            freq = midi_hz(note(deg, 2))
            n = int(length * s16 * JINGLE_RATE)
            place(lead, whistle_tone(freq, n, prev, vibrato_depth=0.003, glide=0.035), pos)
            pos, prev = pos + length * s16, freq
    # Digital delay: the echoes are bit-crushed, the dry whistle stays clean
    lead = lead + bitcrush(echo(lead, beat * 0.75, 0.38) - lead, bits=8, hold=2) * 0.75

    progression = [0, 3, 0, 6]                    # i - IV - i - bVII
    bass_patterns = [[0, 3, 6, 10, 11], [0, 3, 7, 10, 14], [0, 2, 6, 8, 11, 14]]
    for b in range(bars):
        start = b * bar
        deg = progression[b % 4]
        # Piano: 7th chord on the one, below the whistle's register
        chord = [note(deg, 1), note(deg + 2, 1), note(deg + 4, 1), note(deg + 6, 1)]
        for midi in chord:
            place(keys, trim(piano(project_dir, midi, velocity=2), bar, 0.2), start)
        # Piano bass: low octaves on the grime pattern
        for step in bass_patterns[pattern_index]:
            low = trim(piano(project_dir, note(deg, 0) - 12, sustain=False, velocity=4), s16 * 2.5, 0.05)
            mid = trim(piano(project_dir, note(deg, 0), sustain=False, velocity=4), s16 * 2.5, 0.05)
            place(bass, low + 0.6 * mid[:low.size] if mid.size >= low.size else low, start + step * s16)
        # Drums
        kicks = [0, 10] + ([14] if b % 4 == 3 else [])
        for step in kicks:
            place(drums, kit["kick"], start + step * s16)
        place(drums, kit["snare"] + 0.7 * np.pad(kit["clap"], (0, max(0, kit["snare"].size - kit["clap"].size)))[:kit["snare"].size],
              start + 8 * s16)
        for step in range(0, 16, 2):
            if b % 2 == 1 and step >= 12:
                for k in range(3):
                    place(drums, kit["hat"] * 0.8, start + (step + k * 2 / 3) * s16)
            elif b % 2 == 0 and step == 14:
                place(drums, kit["openhat"] * 0.6, start + step * s16)
            else:
                place(drums, kit["hat"] * (1.0 if step % 4 == 2 else 0.7), start + step * s16)

    # FX: light crash on the one, ratchet on the last bar
    place(fx, kit["crash"] * 0.3, 0)
    place(fx, kit["ratchet"] * 0.5, (bars - 1) * bar + 12 * s16)

    # Mix by loudness: whistle on top, everything else ducks under it
    bed = (0.55 * duck(drums, lead, 0.35) / rms(drums) + 0.20 * duck(keys, lead, 0.6) / rms(keys) +
           0.50 * duck(bass, lead, 0.3) / rms(bass) + 0.10 * fx / rms(fx))
    mix = 1.0 * lead / rms(lead) + bed_level * bed   # bed_level 0.4 ≈ instruments in the background
    looped = mix[:loop_len].copy()
    tail = mix[loop_len:]
    looped[:tail.size] += tail[:loop_len]          # wrap tails: seamless on repeat
    looped = np.tanh(looped / (np.max(np.abs(looped)) or 1) * 1.2)
    looped = looped / (np.max(np.abs(looped)) or 1) * 0.85
    return (looped * 32767).astype(np.int16)


def jingle(project_dir, style=None, seconds=7.0, seed=None, drums="synth", bars=8, bpm=140, bed_level=1.0):
    project_dir = Path(project_dir)
    config = load_config(project_dir)
    style = style or PRESET_STYLES.get(config.get("preset", ""), "warm")
    extra = ("grime", "grime-loop")
    if style not in JINGLE_STYLES and style not in extra:
        raise SystemExit(f"Unknown style '{style}'. Available: {', '.join(list(JINGLE_STYLES) + list(extra))}")
    if seed is None:
        seed = sum(config.get("title", "").encode()) % 10000
    kit_dir = project_dir / "podcast" / "music" / "kit"
    if style == "grime-loop":
        audio = compose_grime_loop(project_dir, seed, bars, bpm, bed_level)
    elif style == "grime":
        audio = compose_grime(seconds, seed, drums, kit_dir)
    else:
        audio = compose_jingle(style, seconds, seed)
    out_dir = project_dir / "podcast" / "music"
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{drums}" if style == "grime" and drums != "synth" else ""
    if style == "grime-loop":
        suffix = (f"-{bpm}bpm" if bpm != 140 else "") + (f"-bed{bed_level:g}" if bed_level != 1.0 else "")
    out = out_dir / f"jingle-{style}-{seed}{suffix}.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(JINGLE_RATE)
        w.writeframes(audio.tobytes())
    print(f"🎵 {out}  ({audio.size / JINGLE_RATE:.1f} s, style={style}, seed={seed})")
    return out


# ─── RSS feed ─────────────────────────────────────────────────────────────────

def feed(project_dir):
    project_dir = Path(project_dir)
    config = load_config(project_dir)
    settings = podcast_settings(config)
    base = settings["base_url"].rstrip("/")
    if not base:
        print("⚠️  podcast.base_url is empty — enclosure URLs will be relative. Set it before publishing.")
    for key in ("feed_url", "cover_url", "owner_email"):
        if not settings.get(key):
            print(f"⚠️  podcast.{key} is empty — Spotify and Apple Podcasts require it.")
    episodes_dir = project_dir / "podcast" / "episodes"
    title = escape(config.get("title", "Podcast"))
    author = escape(settings.get("owner_name") or author_name(config))
    # podcast/episodes.json keeps size, duration and publication date of every published
    # episode, so the feed can be rebuilt later without the MP3s on disk and old dates never move.
    registry_path = project_dir / "podcast" / "episodes.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
    for script in episode_scripts(project_dir, []):
        mp3 = episodes_dir / f"{script.stem}.mp3"
        if mp3.exists():
            entry = registry.setdefault(script.stem, {})
            digest, size = hashlib.md5(mp3.read_bytes()).hexdigest()[:12], mp3.stat().st_size
            changed = entry["md5"] != digest if "md5" in entry else entry.get("length") not in (None, size)
            if changed:
                entry["rev"] = entry.get("rev", 0) + 1   # re-rendered audio: new URL, or Spotify keeps the old file
            entry.update(length=size, seconds=int(audio_duration(mp3)), md5=digest)
            if "pub" not in entry:
                last = max((e["pub"] for e in registry.values() if "pub" in e), default=0)
                entry["pub"] = int(max(datetime.now(timezone.utc).timestamp(), last + 3600))
    registry_path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    scripts = [s for s in episode_scripts(project_dir, []) if s.stem in registry]
    items = []
    for script in scripts:
        entry = registry[script.stem]
        mp3 = episodes_dir / f"{script.stem}.mp3"
        meta, _ = split_frontmatter(script.read_text(encoding="utf-8"))
        date = datetime.fromtimestamp(entry["pub"], tz=timezone.utc)
        url = f"{base}/{mp3.name}" if base else mp3.name
        if entry.get("rev"):
            url += f"?v={entry['rev']}"
        seconds = entry["seconds"]
        items.append(f"""    <item>
      <title>{escape(meta.get('title', script.stem))}</title>
      <itunes:title>{escape(meta.get('title', script.stem))}</itunes:title>
      <description>{escape(meta.get('description', ''))}</description>
      <enclosure url="{escape(url)}" length="{entry['length']}" type="audio/mpeg"/>
      <guid isPermaLink="false">{escape(script.stem)}</guid>
      <pubDate>{format_datetime(date)}</pubDate>
      <itunes:duration>{seconds // 60}:{seconds % 60:02d}</itunes:duration>
      <itunes:episode>{escape(meta.get('episode', ''))}</itunes:episode>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:explicit>{'true' if settings.get('explicit') else 'false'}</itunes:explicit>
    </item>""")
    description = escape(settings.get("description") or config.get("subtitle") or config.get("title", ""))
    category = escape(settings.get("category") or "Fiction")
    subcategory = settings.get("subcategory")
    category_xml = (f'<itunes:category text="{category}"><itunes:category text="{escape(subcategory)}"/></itunes:category>'
                    if subcategory else f'<itunes:category text="{category}"/>')
    feed_url = escape(settings.get("feed_url") or "")
    cover = escape(settings.get("cover_url") or "")
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{title}</title>
    <description>{description}</description>
    <language>{escape(config.get('language', 'en'))}</language>
    <link>{escape(settings.get('link') or base)}</link>
    <atom:link href="{feed_url}" rel="self" type="application/rss+xml"/>
    <itunes:author>{author}</itunes:author>
    <itunes:owner><itunes:name>{author}</itunes:name><itunes:email>{escape(settings.get('owner_email') or '')}</itunes:email></itunes:owner>
    <itunes:image href="{cover}"/>
    {category_xml}
    <itunes:explicit>{'true' if settings.get('explicit') else 'false'}</itunes:explicit>
    <itunes:type>{escape(settings.get('type') or 'episodic')}</itunes:type>
{chr(10).join(items)}
  </channel>
</rss>
"""
    out = project_dir / "podcast" / "feed.xml"
    out.write_text(xml, encoding="utf-8")
    if (project_dir / "docs").is_dir():   # GitHub Pages copy + listening page
        (project_dir / "docs" / "feed.xml").write_text(xml, encoding="utf-8")
        episodes_html = "".join(
            f'<li><h3>{escape(m.get("title", s.stem))}</h3><p>{escape(m.get("description", ""))}</p>'
            f'<audio controls preload="none" src="{escape(f"{base}/{s.stem}.mp3")}"></audio></li>'
            for s in scripts for m in [split_frontmatter(s.read_text(encoding="utf-8"))[0]])
        page = f"""<!doctype html>
<html lang="{escape(config.get('language', 'en'))}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Podcast</title>
<link rel="alternate" type="application/rss+xml" title="Feed RSS" href="feed.xml">
<style>body{{font-family:system-ui,sans-serif;max-width:720px;margin:2rem auto;padding:0 16px;background:#0e1116;color:#e6e6e6}}a{{color:#6ee7a0}}img{{width:100%;max-width:360px;border-radius:8px}}ul{{list-style:none;padding:0}}li{{margin:1.5rem 0}}audio{{width:100%}}h3{{margin:.2rem 0}}p{{color:#aab}}</style></head>
<body><img src="cover.jpg" alt="Copertina"><h1>{title}</h1><p>{description}</p>
<p>{author} · <a href="feed.xml">Feed RSS</a></p><ul>{episodes_html}</ul></body></html>
"""
        sito = project_dir / "build_sito.py"
        if sito.exists():   # pagina unica del sito (libro, personaggi, podcast, grafo)
            subprocess.run([sys.executable, str(sito)], check=True)
        else:
            (project_dir / "docs" / "index.html").write_text(page, encoding="utf-8")
    print(f"✅ {out} ({len(items)} episodes)")


# ─── Sound effects (ambient onomatopoeias) ───────────────────────────────────
# Script tag: [sfx NAME]        one-shot effect between sentences
#             [sfx NAME under]  bed mixed quietly under the next paragraph
# Files: podcast/sfx/NAME.wav if present, otherwise synthesized here (no downloads).
# Levels in book.config.json → podcast: sfx_level (one-shot, default 0.35),
# sfx_bed_level (bed, default 0.10), sfx_bed_seconds (default 6).

def _t(seconds):
    return np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE

def _env(n, attack=0.005, release=0.08):
    e = np.ones(n)
    a, r = int(SAMPLE_RATE * attack), int(SAMPLE_RATE * release)
    if a: e[:a] = np.linspace(0, 1, a)
    if r: e[-r:] = np.linspace(1, 0, r)
    return e

def _noise(seconds, seed=0):
    return np.random.default_rng(seed).standard_normal(int(SAMPLE_RATE * seconds))

def _lowpass(x, alpha):
    y = np.zeros_like(x); acc = 0.0
    for i, v in enumerate(x):
        acc += alpha * (v - acc); y[i] = acc
    return y

def _to_int16(x, level=1.0):
    x = x / (np.max(np.abs(x)) or 1) * level
    return (np.clip(x, -1, 1) * 32767).astype(np.int16)

def synth_sfx(name):
    if name == "terminale":                       # l'accordo di tre note del terminale
        t = _t(1.4); out = np.zeros_like(t)
        for i, f in enumerate((523.25, 659.25, 783.99)):
            start = int(SAMPLE_RATE * 0.12 * i); tt = t[: len(t) - start]
            tone = np.sin(2 * np.pi * f * tt) * np.exp(-tt * 2.2) * _env(len(tt), 0.004, 0.2)
            out[start:] += tone * (0.9 - 0.15 * i)
        return _to_int16(out, 0.8)
    if name == "nastro":                          # clic metallico, poi il nastro che gira
        click = _noise(0.012, 1) * _env(int(SAMPLE_RATE * 0.012), 0.0005, 0.008)
        t = _t(1.6); hum = (np.sin(2 * np.pi * 58 * t) + 0.4 * np.sin(2 * np.pi * 116 * t) + 0.15 * np.sin(2 * np.pi * 174 * t))
        ramp = np.minimum(1, t / 0.35) * _env(len(t), 0.01, 0.5)
        rumble = _lowpass(_noise(1.6, 2), 0.02) * 0.6
        belt = (hum * 0.5 + rumble) * ramp
        out = np.concatenate([click * 1.2, belt])
        return _to_int16(out, 0.7)
    if name in ("ewatch-mail", "ewatch-timer"):   # due impulsi corti / il ronzio lungo
        def buzz(sec):
            t = _t(sec); car = np.sign(np.sin(2 * np.pi * 185 * t)) * 0.6 + np.sin(2 * np.pi * 185 * t) * 0.4
            am = 0.5 + 0.5 * np.sin(2 * np.pi * 28 * t)
            return car * am * _env(len(t), 0.004, 0.03)
        if name == "ewatch-mail":
            out = np.concatenate([buzz(0.13), np.zeros(int(SAMPLE_RATE * 0.11)), buzz(0.13)])
        else:
            out = buzz(0.75)
        return _to_int16(_lowpass(out, 0.35), 0.55)
    if name == "neon":                            # ronzio del neon, da usare come bed
        t = _t(6.0); flick = 1 + 0.08 * _lowpass(_noise(6.0, 3), 0.002)
        hum = (np.sin(2 * np.pi * 100 * t) + 0.5 * np.sin(2 * np.pi * 200 * t) + 0.2 * np.sin(2 * np.pi * 300 * t)) * flick
        hiss = _lowpass(_noise(6.0, 4), 0.3) * 0.08
        return _to_int16((hum + hiss) * _env(len(t), 0.5, 1.0), 0.6)
    if name == "stampante":                       # la stampante del fondatore
        t = _t(2.8); motor = np.sin(2 * np.pi * 118 * t) * 0.35
        head = _noise(2.8, 5) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 7 * t))) * np.where((t > 0.4) & (t < 2.1), 1, 0)
        paper = _lowpass(_noise(2.8, 6), 0.08) * np.where(t > 2.1, np.exp(-(t - 2.1) * 4), 0) * 1.5
        return _to_int16((motor + _lowpass(head, 0.5) * 0.7 + paper) * _env(len(t), 0.05, 0.3), 0.6)
    if name == "carrello":                        # il carrello nel corridoio
        t = _t(3.5); roll = _lowpass(_noise(3.5, 7), 0.03) * (0.7 + 0.3 * np.sin(2 * np.pi * 1.7 * t))
        squeak = np.zeros_like(t)
        for k in range(5):
            s = int(SAMPLE_RATE * (0.4 + 0.7 * k)); n = int(SAMPLE_RATE * 0.09)
            if s + n < len(t):
                tt = _t(0.09); squeak[s:s + n] += np.sin(2 * np.pi * (1750 + 300 * np.sin(2 * np.pi * 6 * tt)) * tt) * _env(n, 0.01, 0.04) * 0.25
        return _to_int16((roll + squeak) * _env(len(t), 0.6, 1.0), 0.55)
    if name == "porta":                           # la doppia mandata
        def clack(seed):
            n = int(SAMPLE_RATE * 0.09); t = _t(0.09)
            return (_noise(0.09, seed) * 0.6 + np.sin(2 * np.pi * 290 * t) * 0.8) * np.exp(-t * 55) * _env(n, 0.001, 0.03)
        out = np.concatenate([clack(8), np.zeros(int(SAMPLE_RATE * 0.22)), clack(9)])
        return _to_int16(out, 0.75)
    if name == "vinile":                          # fruscio e crepitio del disco, bed
        t = _t(6.0); hiss = _lowpass(_noise(6.0, 10), 0.25) * 0.15
        pops = np.zeros_like(t); rng = np.random.default_rng(11)
        for s in rng.integers(0, len(t) - 200, 70):
            pops[s:s + 120] += rng.standard_normal(120) * np.exp(-np.arange(120) / 25) * rng.uniform(0.2, 1.0)
        return _to_int16((hiss + pops * 0.5) * _env(len(t), 0.3, 1.0), 0.5)
    if name == "telefono":                        # squillo a vuoto
        def ring():
            t = _t(1.0); return np.sin(2 * np.pi * 425 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 25 * t)) * _env(len(t), 0.01, 0.05)
        gap = np.zeros(int(SAMPLE_RATE * 1.2))
        return _to_int16(np.concatenate([ring(), gap, ring()]), 0.5)
    raise SystemExit(f"sfx sconosciuto: {name} (metti un file in podcast/sfx/{name}.wav o usa un nome della palette)")

# ─── Morse (l'eco nella testa di Tom) ────────────────────────────────────────
# [sfx morse IO SONO QUI]  → punti e linee autentici, timbro di vecchia radio a valvole.
# Solo nei capitoli dal POV di Tom: è lui che traduce la luce in suono (cap. 1).
MORSE = {"A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....", "I": "..",
         "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---", "P": ".--.", "Q": "--.-", "R": ".-.",
         "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-", "Y": "-.--", "Z": "--..",
         "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....", "6": "-....", "7": "--...", "8": "---..", "9": "----."}
MORSE_REV = {v: k for k, v in MORSE.items()}
MORSE_UNIT = 0.085          # secondi per punto (~14 wpm)
MORSE_FREQ = 640.0

def morse_decode(line):
    """'.. --- / ... --- -. ---' → 'IO SONO'"""
    words = []
    for w in re.split(r"\s*/\s*", line.strip().strip("*").strip()):
        letters = [MORSE_REV.get(sym, "?") for sym in w.split()]
        words.append("".join(letters))
    return " ".join(words)

def synth_morse(text):
    u = MORSE_UNIT; out = []
    def tone(units):
        n = int(SAMPLE_RATE * u * units); t = np.arange(n) / SAMPLE_RATE
        env = _env(n, 0.006, 0.012)
        return (np.sin(2 * np.pi * MORSE_FREQ * t) + 0.12 * np.sin(2 * np.pi * MORSE_FREQ * 2 * t)) * env
    def gap(units):
        return np.zeros(int(SAMPLE_RATE * u * units))
    norm = re.sub(r"[^A-Z0-9 ]", "", text.upper().replace("À", "A").replace("È", "E").replace("É", "E").replace("Ì", "I").replace("Ò", "O").replace("Ù", "U"))
    for wi, word in enumerate(norm.split()):
        if wi: out.append(gap(7))
        for li, ch in enumerate(word):
            if li: out.append(gap(3))
            for si, sym in enumerate(MORSE.get(ch, "")):
                if si: out.append(gap(1))
                out.append(tone(1 if sym == "." else 3))
    sig = np.concatenate(out) if out else np.zeros(1)
    hiss = _lowpass(_noise(len(sig) / SAMPLE_RATE + 0.01, 21), 0.2)[: len(sig)] * 0.05   # soffio di valvola
    return _to_int16(sig * 0.8 + hiss, 0.6)


SFX_PALETTE = ["terminale", "nastro", "ewatch-mail", "ewatch-timer", "neon", "stampante", "carrello", "porta", "vinile", "telefono"]
_sfx_cache = {}

def load_sfx(project_dir, name):
    if name in _sfx_cache:
        return _sfx_cache[name]
    custom = sorted((Path(project_dir) / "podcast" / "sfx").glob(f"{name}.*"))
    custom = [c for c in custom if c.suffix.lower() in (".wav", ".mp3", ".flac", ".ogg")]
    if custom:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(custom[0]), "-f", "s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"],
                             check=True, capture_output=True).stdout
        audio = np.frombuffer(raw, dtype=np.int16)
    else:
        audio = synth_sfx(name)
    _sfx_cache[name] = audio
    return audio

def mix_under(voice, bed, level, seconds):
    """Mix `bed` quietly under the first `seconds` of `voice`, fading out."""
    v = voice.astype(np.float64); n = min(len(v), len(bed), int(SAMPLE_RATE * seconds))
    if n <= 0:
        return voice
    fade = np.ones(n); r = int(SAMPLE_RATE * min(1.5, seconds / 3))
    fade[-r:] = np.linspace(1, 0, r)
    v[:n] += bed[:n].astype(np.float64) * level * fade
    return np.clip(v, -32768, 32767).astype(np.int16)

def apply_sfx(project_dir, pieces, settings):
    """pieces: list of ('audio', np.int16) | ('sfx', name, under). Returns one int16 array."""
    level = float(settings.get("sfx_level", 0.35)); bed_level = float(settings.get("sfx_bed_level", 0.10))
    bed_seconds = float(settings.get("sfx_bed_seconds", 6))
    out, pending_bed = [], None
    morse_level = float(settings.get("sfx_morse_level", 0.28))
    for pc in pieces:
        if pc[0] == "morse":
            audio = synth_morse(pc[1])
            if pc[2]:
                pending_bed = audio
            else:
                out.append((audio.astype(np.float64) * morse_level).astype(np.int16))
                out.append(silence(0.35))
            continue
        if pc[0] == "sfx":
            audio = load_sfx(project_dir, pc[1])
            if pc[2]:
                pending_bed = audio
            else:
                out.append((audio.astype(np.float64) * level).astype(np.int16))
                out.append(silence(0.25))
        else:
            a = pc[1]
            if pending_bed is not None and a.size > SAMPLE_RATE * 0.5:
                a = mix_under(a, pending_bed, bed_level, bed_seconds); pending_bed = None
            out.append(a)
    return np.concatenate(out) if out else silence(0)

def sfx(project_dir, names):
    """Render the palette (or the given names) to podcast/sfx/*.wav and a demo MP3."""
    project_dir = Path(project_dir); out_dir = project_dir / "podcast" / "sfx"; out_dir.mkdir(parents=True, exist_ok=True)
    names = names or SFX_PALETTE
    demo = []
    for n in names:
        audio = synth_sfx(n); write_wav(out_dir / f"{n}.wav", audio); demo += [audio, silence(0.8)]
        print(f"🔊 {n}: {audio.size / SAMPLE_RATE:.1f} s")
    wav = out_dir / "palette.wav"; write_wav(wav, np.concatenate(demo))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-b:a", "96k", str(out_dir / "palette.mp3")], check=True)
    wav.unlink(); print(f"✅ {out_dir / 'palette.mp3'}")


def cost(project_dir, names):
    """Characters that `build` would send to ElevenLabs per episode, net of the local cache."""
    project_dir = Path(project_dir); settings = podcast_settings(load_config(project_dir))
    cache_dir = project_dir / "podcast" / "cache" / "elevenlabs"
    total_new = total_all = 0
    for script in episode_scripts(project_dir, names):
        meta, body = split_frontmatter(script.read_text(encoding="utf-8"))
        events = parse_script(body)
        blocks, current = [], None
        for ev in events:                       # same grouping as render_events_elevenlabs
            if ev[0] == "say":
                if current and current[0] == ev[1] and len(" ".join(current[1])) + len(ev[2]) < ELEVENLABS_MAX_CHARS:
                    current[1].append(ev[2])
                else:
                    current = [ev[1], [ev[2]]]; blocks.append(current)
            else:
                current = None
        new = allc = 0
        for voice_name, sents in blocks:
            text = " ".join(sents); vc = voice_config(settings, voice_name)
            params = {k: vc.get(k) for k in ("voice", "model", "speed", "stability", "similarity_boost", "style")}
            key = hashlib.sha256(json.dumps([text, params], sort_keys=True).encode()).hexdigest()[:24]
            allc += len(text)
            if not (cache_dir / f"{key}.pcm").exists():
                new += len(text)
        total_new += new; total_all += allc
        print(f"{script.stem}: {new:>6} caratteri da sintetizzare su {allc:>6}  ({'tutto in cache' if new == 0 else f'{100 * new // max(allc, 1)}% nuovo'})")
    print(f"TOTALE: {total_new} caratteri da inviare a ElevenLabs (su {total_all})")


# ─── Scripts from chapters ────────────────────────────────────────────────────
# `scripts` rebuilds podcast/scripts/episode-NN.md from chapters/NN-*.md with the
# adaptation rules of this project (Morse, system boxes, numbers), keeping the
# per-episode fields written by the author in the script frontmatter
# (description, recap, teaser, status). `check` reports scripts out of sync.

_UNITS = ["zero", "uno", "due", "tre", "quattro", "cinque", "sei", "sette", "otto", "nove", "dieci",
          "undici", "dodici", "tredici", "quattordici", "quindici", "sedici", "diciassette", "diciotto", "diciannove"]
_TENS = {2: "venti", 3: "trenta", 4: "quaranta", 5: "cinquanta", 6: "sessanta", 7: "settanta", 8: "ottanta", 9: "novanta"}

def italian_number(n):
    if n < 20:
        return _UNITS[n]
    if n < 100:
        t, u = divmod(n, 10)
        w = _TENS[t]
        if u in (1, 8):
            w = w[:-1]
        if u == 3:
            return w + "tré"
        return w + (_UNITS[u] if u else "")
    if n < 1000:
        h, r = divmod(n, 100)
        w = "cento" if h == 1 else _UNITS[h] + "cento"
        if 80 <= r < 90:
            w = w[:-1]
        return w + (italian_number(r) if r else "")
    if n < 1000000:
        k, r = divmod(n, 1000)
        w = "mille" if k == 1 else italian_number(k) + "mila"
        return w + (italian_number(r) if r else "")
    return str(n)

# Morse lines that are read as sentences instead of word by word (author's choice).
MORSE_SPOKEN = {
    "STAI / ESAGERANDO / CON / LO / YOGA / IL / TUO / CUORE / NON / REGGE / PIU / FERMATI / O / RISCHI / LA / VITA":
        "Stai esagerando con lo yoga. Il tuo cuore non regge più. Fermati, o rischi la vita.",
}
# Morse quoted inside a sentence.
MORSE_INLINE = {
    "NO / SONO / QUI / CON / TE": '"no, sono qui con te"',
    "IO / SONO / QUI": '"io sono qui"',
}
_MORSE_FIX = {"SI": "Sì", "PIU": "Più"}

def morse_words(seq):
    return " ".join(_MORSE_FIX.get(w, w.capitalize()) + "." for w in seq.split(" / "))

_WEEKDAYS = {"lun": "lunedì", "mar": "martedì", "mer": "mercoledì", "gio": "giovedì",
             "ven": "venerdì", "sab": "sabato", "dom": "domenica"}

def spoken_time(text):
    # 23:34 → "ventitré e trentaquattro"; 08:00:01 → "otto, zero zero e un secondo"
    def t(m):
        h, mm, ss = int(m.group(1)), m.group(2), m.group(3)
        out = italian_number(h)
        mins = "zero zero" if mm == "00" else italian_number(int(mm))
        if ss is None:
            return out + (" in punto" if mm == "00" else " e " + mins)
        sec = "un secondo" if int(ss) == 1 else italian_number(int(ss)) + " secondi"
        return f"{out}, {mins} e {sec}"
    return re.sub(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b", t, text)

def spoken_numbers(text):
    text = spoken_time(text)
    text = re.sub(r"\b2x\b", "doppia", text)
    text = re.sub(r"(\d+)\s*%", lambda m: italian_number(int(m.group(1))) + " per cento", text)
    return re.sub(r"\b\d+\b", lambda m: italian_number(int(m.group(0))), text)

# System boxes read with a wording approved by the author (exact chapter line → spoken text).
BOX_SPOKEN = {
    "**TABELLA DI CONVERSIONE · uso personale**": "Tabella di conversione. Uso personale.",
    "**15 minuti · smutandata semplice**": "Quindici minuti: smutandata semplice.",
    "**30 minuti · doppia smutandata**": "Trenta minuti: doppia smutandata.",
    "**45 minuti · tripla smutandata**": "Quarantacinque minuti: tripla smutandata.",
    "**60 minuti · smutandata con testa nel cestino** *(tetto del supervisore)*":
        "Sessanta minuti: smutandata con testa nel cestino. Tetto del supervisore.",
    "**Interdizione + 30% per 3 mesi · testa nel water con le mutande in testa** *(solo ispettori)*":
        "Interdizione dal lavoro e trenta per cento dello stipendio per tre mesi: testa nel water con le mutande in testa. Solo ispettori.",
}

def spoken_box(line):
    s = line.strip().strip("*").strip()
    s = s.replace("[omesso in automatico]", "omesso in automatico").replace("[omesso]", "omesso")
    s = re.sub(r"\bRif\.", "Riferimento", s)
    s = re.sub(r"\bmod\.", "modello", s)
    s = re.sub(r"\bTV\b", "tivù", s)
    s = re.sub(r"\bTurno: B\b", "Turno: bi", s)
    s = re.sub(r"([\w.-]+)@([\w.-]+)\.(\w+)",
               lambda m: f"{m.group(1)} chiocciola {m.group(2).replace('.', ' punto ')} punto {m.group(3)}", s)
    s = s.replace("_", " ").replace(" · ", ". ")
    s = spoken_numbers(s)
    return s if s.endswith((".", "!", "?", "…")) else s + "."

def spoken_panel(line):
    s = re.sub(r"^\s*>\s?", "", line).replace("*", "").strip()
    s = re.sub(r"\b(lun|mar|mer|gio|ven|sab|dom)\b(?= \d)", lambda m: _WEEKDAYS[m.group(1)] + ",", s)
    s = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]\s*", "", s)
    if s.count(" · ") >= 3:                      # list of values: read as one sentence
        s = s.replace(" · ", ", ").replace(", …, ", "… ")
        s = re.sub(r", (0|zero)$", r". Zero", s)
    else:
        s = s.replace(" · ", ". ")
    s = spoken_numbers(s)
    return s if s.endswith((".", "!", "?")) else s + "."

# Parole che la voce accenta male: grafia del libro → grafia del copione (vedi podcast/plan.md, Pronunciation).
PRONUNCIATION = {"ribere": "ribére"}

def spoken_line(line):
    line = re.sub(r"`([^`]+)`", r"\1", line)
    def inline(m):
        seq = m.group(1)
        return MORSE_INLINE.get(seq, '"' + seq.replace(" / ", " ").lower() + '"')
    line = re.sub(r"\*?\b([A-ZÀ-Ù']{2,}(?: / [A-ZÀ-Ù']+)+)\b\.?\*?", inline, line)
    for word, said in PRONUNCIATION.items():
        line = re.sub(r"\b" + re.escape(word) + r"\b", said, line)
    return spoken_numbers(line)

# Onomatopee del libro (in corsivo nel testo) → effetto sonoro nel copione, letto E suonato.
# Override/estensione in book.config.json → podcast.sfx_map {"clac": "nastro", ...}.
SFX_MAP = {"dlin": "terminale", "clac": "nastro", "bzz bzz": "ewatch-mail", "bzzzz": "ewatch-timer",
           "frrr": "stampante", "driin": "telefono", "clac clac": "porta", "crr": "vinile under", "crr crr": "vinile",
           "cri-cri": "carrello", "zzz": "neon under"}

def adapt_chapter_body(body, sfx_map=None, morse_pov=False):
    sfx_map = {**SFX_MAP, **(sfx_map or {})}
    out = []
    last_morse = None
    for para in re.split(r"\n\s*\n", body.strip()):
        lines = [l for l in para.splitlines() if l.strip()]
        if not lines or lines[0].strip() == "---" or lines[0].startswith("#"):
            continue
        spoken = []
        for word in sorted(sfx_map, key=len, reverse=True):
            if re.search(r"\*" + re.escape(word) + r"[^\w*]*\*", para, flags=re.IGNORECASE):
                spoken.append(f"[sfx {sfx_map[word]}]")
                break
        for l in lines:
            s = l.strip()
            if re.fullmatch(r"\*?[.\-– /]+\*?", s):                       # dots and dashes
                if morse_pov:
                    text = morse_decode(s); last_morse = text
                    spoken.append(f"[sfx morse {text}]")
                else:
                    spoken.append("[pause 1.5]")
            elif re.fullmatch(r"\*?([A-ZÀ-Ù']+(?: / [A-ZÀ-Ù']+)*)\.?\*?", s):   # Morse words
                seq = re.fullmatch(r"\*?([A-ZÀ-Ù']+(?: / [A-ZÀ-Ù']+)*)\.?\*?", s).group(1)
                text = seq.replace(" / ", " ")
                if morse_pov and text != last_morse:
                    spoken.append(f"[sfx morse {text}" + (" under]" if len(text.split()) > 3 else "]"))
                last_morse = text
                spoken.append(MORSE_SPOKEN.get(seq) or morse_words(seq))
            elif s in BOX_SPOKEN:                                               # box with approved wording
                spoken.append(BOX_SPOKEN[s])
            elif re.fullmatch(r"\*\*.+\*\*", s):                                # system box
                spoken.append(spoken_box(s))
            elif s.startswith(">"):                                             # panel / blockquote
                spoken.append(spoken_panel(s))
            else:
                spoken.append(spoken_line(s))
        out.append("\n".join(spoken))
    return "\n\n".join(out)

def chapter_files(project_dir, names=None):
    chapters = sorted((Path(project_dir) / "chapters").glob("[0-9][0-9]-*.md"))
    if names:
        wanted = {re.sub(r"\D", "", Path(n).stem)[:2] for n in names}
        chapters = [c for c in chapters if c.stem[:2] in wanted]
    return chapters

def render_script(project_dir, chapter, existing_meta=None):
    config = load_config(project_dir)
    meta, text = split_frontmatter(chapter.read_text(encoding="utf-8"))
    body = text.split("\n## Demolition Log")[0]
    n = int(chapter.stem[:2])
    old = existing_meta or {}
    book = config.get("title", "").replace(": ", ". ").rstrip(".") + "."
    title = meta.get("title", chapter.stem[3:])
    fm = {
        "episode": str(n),
        "title": f"Capitolo {n} — {title}",
        "description": old.get("description", ""),
        "source": f"chapters/{chapter.name}",
        "status": old.get("status", "script"),
        "recap": old.get("recap", ""),
        "teaser": old.get("teaser", ""),
        "sfx_open": old.get("sfx_open", ""),
    }
    head = "---\n" + "\n".join(f'{k}: "{v}"' if k not in ("episode", "source") else f"{k}: {v}" for k, v in fm.items() if not (k == "sfx_open" and not v)) + "\n---\n"
    parts = [f"{book} Episodio {italian_number(n)}."]
    if fm["recap"]:
        parts.append(fm["recap"] if fm["recap"].startswith("Nell'episodio precedente") else "Nell'episodio precedente, " + fm["recap"])
    parts.append("[pause 1]")
    parts.append(f"# Capitolo {italian_number(n)}. {spoken_numbers(title)}")
    if fm["sfx_open"]:
        parts.append(f"[sfx {fm['sfx_open']} under]")
    pov = (meta.get("pov") or "").strip().lower()
    tom_pov = pov.startswith("tom") if pov else not re.search(r"\bEmma\b", body[:1500])   # fallback: Emma nelle prime righe → POV Emma
    parts.append(adapt_chapter_body(body, podcast_settings(config).get("sfx_map"), morse_pov=tom_pov))
    parts.append("[pause 1.5]")
    if fm["teaser"]:
        parts.append(fm["teaser"] if fm["teaser"].startswith("Nel prossimo episodio") else "Nel prossimo episodio, " + fm["teaser"])
    return head + "\n\n".join(parts) + "\n"

def scripts(project_dir, names):
    scripts_dir = Path(project_dir) / "podcast" / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    for chapter in chapter_files(project_dir, names):
        target = scripts_dir / f"episode-{chapter.stem[:2]}.md"
        old_meta = split_frontmatter(target.read_text(encoding="utf-8"))[0] if target.exists() else {}
        new = render_script(project_dir, chapter, old_meta)
        changed = (not target.exists()) or target.read_text(encoding="utf-8") != new
        target.write_text(new, encoding="utf-8")
        words = len(split_frontmatter(new)[1].split())
        print(f"{'✏️ ' if changed else '✅'} {target.name}  {words} parole  ({'rigenerato' if changed else 'già allineato'})")

def check(project_dir):
    scripts_dir = Path(project_dir) / "podcast" / "scripts"
    drift = 0
    for chapter in chapter_files(project_dir):
        target = scripts_dir / f"episode-{chapter.stem[:2]}.md"
        if not target.exists():
            print(f"❌ {target.name} manca (capitolo {chapter.name})"); drift += 1; continue
        old_meta, old_body = split_frontmatter(target.read_text(encoding="utf-8"))
        new_body = split_frontmatter(render_script(project_dir, chapter, old_meta))[1]
        if old_body != new_body:
            print(f"⚠️  {target.name} non allineato a {chapter.name}: rilancia `scripts`"); drift += 1
        else:
            print(f"✅ {target.name} allineato")
    sys.exit(1 if drift else 0)


if __name__ == "__main__":
    args = sys.argv[1:]
    cmd = args[0] if args else "build"
    rest = args[1:]
    if cmd == "voices" and podcast_settings(load_config("."))["engine"] == "elevenlabs":
        list_elevenlabs_voices()
    elif cmd == "voices":
        list_voices(rest[0] if rest else (load_config(".").get("language") or "en")[:2])
    elif cmd == "sample":
        text = None
        if "--text" in rest:
            i = rest.index("--text")
            text, rest = rest[i + 1], rest[:i] + rest[i + 2:]
        sample(".", rest or [podcast_settings(load_config("."))["voice"]], text)
    elif cmd == "scripts":
        scripts(".", rest)
    elif cmd == "sfx":
        sfx(".", rest)
    elif cmd == "cost":
        cost(".", rest)
    elif cmd == "check":
        check(".")
    elif cmd == "build":
        build(".", rest)
    elif cmd == "feed":
        feed(".")
    elif cmd == "jingle":
        opts = dict(zip(rest[::2], rest[1::2]))
        jingle(".", opts.get("--style"), float(opts.get("--seconds", 7)),
               int(opts["--seed"]) if "--seed" in opts else None, opts.get("--drums", "synth"),
               int(opts.get("--bars", 8)), int(opts.get("--bpm", 140)), float(opts.get("--bed", 1.0)))
    else:
        print(__doc__)
