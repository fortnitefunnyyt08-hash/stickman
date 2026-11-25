"""Text-to-speech: ElevenLabs (cloned voices) with an espeak-ng placeholder.

Every generated line is cached under build/cache/tts, so re-running a build
only regenerates lines whose text, voice or settings changed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import audio_io
from .config import BUILD, pitch_for, voice_for

CACHE = BUILD / "cache" / "tts"
WORD_RE = re.compile(r"\S+")


@dataclass
class Clip:
    path: Path                       # final mono 44.1k wav (pitch-shifted, trimmed)
    duration: float
    words: list[tuple[str, float, float]] = field(default_factory=list)  # caption words
    backend: str = "placeholder"


def api_key() -> str:
    # In the Claude cloud environment the network proxy injects the real key
    # for api.elevenlabs.io, so a dummy value is fine there. Locally, set
    # ELEVENLABS_API_KEY in your shell or a .env file.
    return os.environ.get("ELEVENLABS_API_KEY") or _dotenv().get("ELEVENLABS_API_KEY") or "proxy-injected"


def _dotenv() -> dict:
    p = Path(__file__).resolve().parent.parent / ".env"
    out = {}
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _hash(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]


def synthesize(cfg: dict, episode: int, speaker: str, text: str, say: str | None, mode: str = "auto") -> Clip:
    """mode: auto (ElevenLabs when a voice ID exists), elevenlabs, placeholder."""
    say = say or text
    voice_id, ch = voice_for(cfg, speaker)
    use_eleven = mode == "elevenlabs" or (mode == "auto" and voice_id)
    if mode == "elevenlabs" and not voice_id:
        raise RuntimeError(f"No ElevenLabs voice for '{speaker}'. Run: python -m stickman.clone")
    pitch = pitch_for(ch, episode)
    formant = ch.get("formant", "shifted")
    CACHE.mkdir(parents=True, exist_ok=True)

    if use_eleven:
        model = ch.get("model_id") or cfg["tts"]["model_id"]
        text_in = f"{ch['direction']} {say}" if ch.get("direction") else say
        raw_key = _hash(["el", voice_id, text_in, model, ch.get("settings")])
        raw_audio, alignment = _eleven_raw(cfg, voice_id, text_in, model, ch.get("settings") or {}, raw_key)
        backend = "elevenlabs"
    else:
        ph = ch.get("placeholder", {})
        raw_key = _hash(["es", ph, say])
        raw_audio, alignment = _espeak_raw(say, ph, raw_key), None
        backend = "placeholder"

    final = CACHE / f"{raw_key}_p{pitch:+.2f}_{formant}.wav"
    meta = final.with_suffix(".json")
    if not (final.exists() and meta.exists()):
        filt = None
        if abs(pitch) > 1e-3:
            ratio = 2 ** (pitch / 12)
            filt = f"rubberband=pitch={ratio:.5f}:formant={formant}:transients=smooth"
        tmp = final.with_suffix(".tmp.wav")
        audio_io.to_wav(raw_audio, tmp, extra_filters=filt)
        data = audio_io.read_wav(tmp)
        tmp.unlink()
        lead, tail = audio_io.trim_silence_bounds(data)
        lead = max(0.0, lead - 0.03)
        spoken = _text_start(alignment)
        if spoken is not None:  # cut anything said before the real words (e.g. a spoken [tag])
            lead = max(lead, spoken - 0.06)
        tail = min(len(data) / audio_io.SR, tail + 0.12)
        data = data[int(lead * audio_io.SR): int(tail * audio_io.SR)]
        peak = np.abs(data).max() or 1
        data = data / peak * 0.89
        audio_io.write_wav(final, data)
        meta.write_text(json.dumps({"lead": lead, "duration": len(data) / audio_io.SR,
                                    "alignment": alignment}))
    m = json.loads(meta.read_text())
    words = _caption_words(text, say, m["alignment"], m["lead"], m["duration"], final)
    return Clip(final, m["duration"], words, backend)


# ── ElevenLabs ───────────────────────────────────────────────

def _eleven_raw(cfg, voice_id, say, model, settings, key) -> tuple[Path, dict | None]:
    mp3 = CACHE / f"{key}.mp3"
    js = CACHE / f"{key}.align.json"
    if mp3.exists() and js.exists():
        return mp3, json.loads(js.read_text())
    import requests

    tts = cfg["tts"]
    url = f"{tts['api_base']}/v1/text-to-speech/{voice_id}/with-timestamps"
    body = {"text": say, "model_id": model, "voice_settings": settings}
    r = requests.post(url, params={"output_format": tts["output_format"]},
                      headers={"xi-api-key": api_key(), "Content-Type": "application/json"},
                      json=body, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"ElevenLabs TTS failed ({r.status_code}): {r.text[:500]}")
    data = r.json()
    mp3.write_bytes(base64.b64decode(data["audio_base64"]))
    align = data.get("alignment")
    js.write_text(json.dumps(align))
    return mp3, align


# ── espeak placeholder ───────────────────────────────────────

def _espeak_raw(say: str, ph: dict, key: str) -> Path:
    out = CACHE / f"{key}.espeak.wav"
    if out.exists():
        return out
    if not shutil.which("espeak-ng"):
        raise RuntimeError("espeak-ng not installed (apt-get install espeak-ng) and no ElevenLabs voice set")
    text = say.replace("t' ", "t ").replace("'", "")
    subprocess.run(["espeak-ng", "-v", ph.get("voice", "en-gb"), "-p", str(ph.get("pitch", 40)),
                    "-s", str(ph.get("speed", 150)), "-w", str(out), text], check=True,
                   capture_output=True)
    return out


def _text_start(alignment) -> float | None:
    """Start time of the first spoken character after any leading [audio tag]."""
    if not alignment or not alignment.get("characters"):
        return None
    chars = alignment["characters"]
    if not chars or chars[0] != "[":
        return None
    depth = 0
    for c, s in zip(chars, alignment["character_start_times_seconds"]):
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
        elif depth == 0 and not c.isspace() and c not in ".":
            return s
    return None


# ── caption word timings ─────────────────────────────────────

def _caption_words(text, say, alignment, lead, duration, wav) -> list[tuple[str, float, float]]:
    cap_words = WORD_RE.findall(text)
    timed = []
    if alignment and alignment.get("characters"):
        chars = alignment["characters"]
        st = alignment["character_start_times_seconds"]
        en = alignment["character_end_times_seconds"]
        cur, cs, ce = "", None, None
        depth = 0
        for c, s, e in zip(chars, st, en):
            if c == "[":
                depth += 1
                continue
            if c == "]":
                depth = max(0, depth - 1)
                continue
            if depth:
                continue
            if c.isspace():
                if cur:
                    timed.append((cur, cs, ce))
                cur, cs = "", None
            else:
                if cs is None:
                    cs = s
                cur += c
                ce = e
        if cur:
            timed.append((cur, cs, ce))
        timed = [(w, max(0.0, s - lead), max(0.0, e - lead)) for w, s, e in timed]
    if timed and len(timed) == len(cap_words):
        return [(cw, s, e) for cw, (_, s, e) in zip(cap_words, timed)]
    # Estimate: spread words over the clip weighted by length.
    weights = np.array([len(w.strip(".,!?'")) + 2 for w in cap_words], dtype=float)
    span = max(0.2, duration - 0.12)
    edges = np.concatenate([[0], np.cumsum(weights) / weights.sum() * span])
    return [(w, float(edges[i]), float(edges[i + 1])) for i, w in enumerate(cap_words)]
