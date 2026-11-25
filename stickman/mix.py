"""Audio mix: dialogue + one-shot SFX + scene ambience + music, with ducking."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import signal

from . import audio_io, sfx
from .timeline import Timeline

SR = audio_io.SR


def _add(buf, x, at, gain=1.0, pan=None):
    i = int(round(at * SR))
    if i >= len(buf) or i + len(x) <= 0:
        return
    if i < 0:
        x, i = x[-i:], 0
    n = min(len(x), len(buf) - i)
    if x.ndim == 1:
        if pan is None:
            buf[i:i + n] += gain * x[:n, None] * 0.7071
        else:
            buf[i:i + n, 0] += gain * x[:n] * np.sqrt(1 - pan)
            buf[i:i + n, 1] += gain * x[:n] * np.sqrt(pan)
    else:
        buf[i:i + n] += gain * x[:n]


def mix(cfg: dict, tl: Timeline, out: Path, extra_events: list | None = None, log=print) -> None:
    a = cfg["audio"]
    total = tl.duration + 0.5
    n = int(total * SR)
    voice = np.zeros((n, 2))
    fx = np.zeros((n, 2))
    amb = np.zeros((n, 2))

    for sc in tl.scenes:
        for b in sc.beats:
            t0 = sc.start + b.start
            if b.kind == "line":
                _add(voice, audio_io.read_wav(b.clip.path), t0, a["voice_gain"])
            for s in b.sfx:
                _add(fx, sfx.one_shot(s["name"]), t0 + float(s.get("at", 0)), a["sfx_gain"] * float(s.get("gain", 1)))
        for am in sc.ambience:
            x = sfx.ambience(am["name"], sc.duration + 0.6)
            fade = np.ones(len(x))
            k = int(0.3 * SR)
            fade[:k] = np.linspace(0, 1, k)
            fade[-k:] = np.linspace(1, 0, k)
            _add(amb, x * fade, sc.start - 0.3 if sc.start > 0 else 0, a["ambience_gain"] * float(am.get("gain", 1)))

    for ev in extra_events or []:
        _add(fx, sfx.one_shot(ev["name"], ev.get("variant", 0)), ev["t"], a["sfx_gain"] * ev.get("gain", 1.0), ev.get("pan"))

    music = sfx.music(total)
    mus = np.stack([music, np.roll(music, int(0.012 * SR))], axis=1)

    # duck music + ambience under dialogue
    env = np.abs(voice).max(axis=1)
    hop = 512
    m = len(env) // hop
    talk = (env[: m * hop].reshape(m, hop).max(axis=1) > 0.02).astype(float)
    talk = np.repeat(talk, hop)
    talk = np.pad(talk, (0, n - len(talk)))
    sos = signal.butter(1, 3, fs=SR, output="sos")
    talk = np.clip(signal.sosfilt(sos, talk) * 1.6, 0, 1)
    duck = 1 - (1 - a["duck"]) * talk

    out_buf = voice + fx + (amb + mus * a["music_gain"]) * duck[:, None]
    peak = np.abs(out_buf).max()
    if peak > 0.98:
        out_buf = np.tanh(out_buf / peak * 1.2) / np.tanh(1.2) * 0.95
    audio_io.write_wav(out, out_buf.astype(np.float32))
    log(f"  mixed {total:.1f}s of audio -> {out}")
