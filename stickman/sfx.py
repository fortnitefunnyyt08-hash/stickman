"""Procedurally synthesised sound effects, ambience and music.

Everything here is generated from scratch with numpy, so there are no licensing
worries. To use a real recording instead, drop a WAV into assets/sfx/<name>.wav
and it will be used in place of the synthesised version.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import signal

from . import audio_io
from .config import ROOT

SR = audio_io.SR
OVERRIDES = ROOT / "assets" / "sfx"


def _rng(seed):
    return np.random.default_rng(seed)


def _t(d):
    return np.arange(int(d * SR)) / SR


def _bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def _lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype="low", fs=SR, output="sos"), x)


def _hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, btype="high", fs=SR, output="sos"), x)


def _norm(x, peak=0.9):
    m = np.abs(x).max()
    return x / m * peak if m > 0 else x


def _env(n, a=0.01, r=0.1):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def _formants(src, formants):
    out = np.zeros_like(src)
    for f, bw, g in formants:
        out += g * _bp(src, max(40, f - bw / 2), f + bw / 2)
    return out


def _glottal(f0, d, seed=0, jitter=0.01):
    """Buzz with a pitch contour f0(t) (array or float), like vocal cords."""
    t = _t(d)
    f = np.broadcast_to(np.asarray(f0, dtype=float), t.shape) * (1 + jitter * _lp(_rng(seed).standard_normal(len(t)), 8) * 30)
    ph = np.cumsum(f) / SR
    saw = 2 * (ph % 1) - 1
    return saw + 0.15 * _rng(seed + 1).standard_normal(len(t))


# ── one-shots ────────────────────────────────────────────────

def pop():
    t = _t(0.35)
    f = 900 * np.exp(-t * 18) + 140
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11)
    click = _hp(_rng(1).standard_normal(len(t)), 2000) * np.exp(-t * 200) * 0.6
    return _norm(x + click)


def slide():
    t = _t(1.0)
    n = _bp(_rng(2).standard_normal(len(t)), 300, 2500)
    return _norm(n * np.sin(np.pi * t / t[-1]) ** 1.5 * np.exp(-t * 1.5), 0.5)


def squeak(seed=0):
    r = _rng(100 + seed)
    t = _t(0.11)
    f0 = r.uniform(1500, 1900)
    f = f0 + 600 * t / t[-1] + 80 * np.sin(2 * np.pi * 38 * t)
    x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.3 * np.sin(4 * np.pi * np.cumsum(f) / SR)
    return _norm(x * np.sin(np.pi * t / t[-1]) ** 0.6, 0.55)


def door_ding():
    t = _t(1.6)
    x = sum(g * np.sin(2 * np.pi * f * t) * np.exp(-t * k) for f, g, k in
            [(1318, 1, 2.2), (1661, 0.6, 2.8), (2637, 0.3, 4), (3520, 0.15, 6), (1046, 0.4, 3)])
    x += 0.8 * sum(g * np.sin(2 * np.pi * f * (t - 0.18).clip(0)) * np.exp(-(t - 0.18).clip(0) * k) * (t > 0.18)
                   for f, g, k in [(1046, 1, 2.2), (1318, 0.5, 2.8), (2093, 0.3, 4)])
    return _norm(x, 0.6)


def _clink(seed, f=None, d=0.25):
    r = _rng(seed)
    t = _t(d)
    f = f or r.uniform(2800, 5200)
    x = sum(np.sin(2 * np.pi * f * m * t + r.uniform(0, 6)) * np.exp(-t * r.uniform(18, 40) * m) / m
            for m in (1, 1.47, 2.09, 2.76))
    return x


def _scatter(events, d):
    out = np.zeros(int(d * SR))
    for at, x, g in events:
        i = int(at * SR)
        n = min(len(x), len(out) - i)
        if n > 0:
            out[i:i + n] += g * x[:n]
    return out


def coins_jingle():
    r = _rng(5)
    ev = [(r.uniform(0, 0.45), _clink(50 + i), r.uniform(0.3, 1)) for i in range(14)]
    return _norm(_scatter(ev, 0.8), 0.45)


def coin_slam():
    r = _rng(7)
    thud = _lp(_rng(8).standard_normal(int(0.25 * SR)), 300) * np.exp(-_t(0.25) * 25)
    ev = [(0, _norm(thud) * 1.0, 1)]
    ev += [(r.uniform(0.0, 0.15), _clink(70 + i), r.uniform(0.4, 1)) for i in range(10)]
    ev += [(0.35 + i * r.uniform(0.07, 0.16), _clink(90 + i, d=0.12), 0.5 * 0.85 ** i) for i in range(14)]
    # one coin rolling away and spinning down
    t = _t(2.2)
    roll = _bp(_rng(9).standard_normal(len(t)), 2500, 6000) * (0.5 + 0.5 * np.sin(2 * np.pi * (14 - 5 * t) * t)) * np.exp(-t * 1.2) * 0.15
    ev += [(0.6, roll, 1)]
    return _norm(_scatter(ev, 3.0), 0.8)


def slide_pack():
    t = _t(0.5)
    return _norm(_bp(_rng(11).standard_normal(len(t)), 800, 4000) * np.sin(np.pi * t / t[-1]) ** 2, 0.3)


def lighter():
    flick = _hp(_rng(12).standard_normal(int(0.04 * SR)), 3000) * np.exp(-_t(0.04) * 90)
    t = _t(0.9)
    whoosh = _bp(_rng(13).standard_normal(len(t)), 200, 1200) * np.exp(-t * 3) * 0.25
    return _norm(_scatter([(0, flick, 1), (0.25, flick * 0.8, 1), (0.28, whoosh, 1)], 1.3), 0.5)


def crisp_rustle():
    r = _rng(14)
    out = np.zeros(int(0.9 * SR))
    for i in range(30):
        at = r.uniform(0, 0.75)
        n = int(r.uniform(0.005, 0.03) * SR)
        b = _hp(r.standard_normal(n), 2500) * np.hanning(n) * r.uniform(0.2, 1)
        j = int(at * SR)
        out[j:j + n] += b[: len(out) - j]
    return _norm(out, 0.4)


def sigh(seed=15, low=False):
    t = _t(1.3)
    n = _rng(seed).standard_normal(len(t))
    lo, hi = (350, 1800) if low else (600, 2800)
    x = _bp(n, lo, hi) * (np.sin(np.pi * np.clip(t / 1.2, 0, 1)) ** 1.2) * np.exp(-t * 0.8)
    return _norm(x, 0.35)


def sigh_tariq():
    return sigh(16, low=True)


def dog_bark():
    out = []
    for k, seed in enumerate((20, 21)):
        d = 0.22
        t = _t(d)
        f0 = 420 * (1 - 0.35 * t / d)
        x = _formants(_glottal(f0, d, seed, 0.03), [(700, 300, 1), (1300, 400, 0.6), (2600, 600, 0.3)])
        x *= np.exp(-t * 9) * np.clip(t * 200, 0, 1)
        out.append(x)
        out.append(np.zeros(int(0.12 * SR)))
    x = np.concatenate(out)
    x = _lp(x, 2500)  # distant
    return _norm(x, 0.5)


def _alarm(d, distant):
    t = _t(d)
    # classic two-tone whoop: alternating sweeps
    seg = (t * 2.2).astype(int) % 2
    f = np.where(seg == 0, 900 + 500 * ((t * 2.2) % 1), 1400 - 500 * ((t * 2.2) % 1))
    x = signal.square(2 * np.pi * np.cumsum(f) / SR) * 0.5
    x = _lp(x, 1800 if distant else 4000)
    return _norm(x * _env(len(t), 0.02, 0.3), 0.35 if distant else 0.6)


def car_alarm_far():
    return _alarm(2.2, True)


def car_alarm_near():
    return _alarm(1.9, False)


def pigeon():
    parts = []
    for f, d in ((420, 0.25), (520, 0.45), (400, 0.3)):
        t = _t(d)
        x = np.sin(2 * np.pi * (f + 40 * np.sin(np.pi * t / d)) * t) * np.sin(np.pi * t / d) ** 2
        x *= 1 + 0.4 * np.sin(2 * np.pi * 30 * t)
        parts += [x, np.zeros(int(0.05 * SR))]
    return _norm(np.concatenate(parts), 0.35)


def _groan(d, f_hi, f_lo, seed):
    t = _t(d)
    f0 = f_hi + (f_lo - f_hi) * (t / d) + 10 * np.sin(2 * np.pi * 5 * t)
    x = _formants(_glottal(f0, d, seed, 0.02), [(650, 200, 1), (1100, 250, 0.5), (2700, 400, 0.12)])
    return _norm(x * np.sin(np.pi * t / d) ** 0.8, 0.5)


def mam_groan():
    return _groan(1.1, 230, 180, 30)


def mam_groan_big():
    return _groan(1.5, 280, 210, 31)


def bikes_pass():
    """Three dirt bikes approach from the left, pass in slow-mo, fade right. Stereo."""
    d = 9.0
    t = _t(d)
    out = np.zeros((len(t), 2))
    for k, (delay, base, seed) in enumerate(((0.0, 95, 40), (0.45, 110, 41), (0.85, 85, 42))):
        tc = 3.9 + delay                         # closest approach
        x = (t - tc) / 1.6
        dist = np.sqrt(x ** 2 + 0.12)
        amp = 1 / dist ** 1.4
        amp *= np.clip(t / 0.5, 0, 1) * np.clip((d - t) / 1.5, 0, 1)
        doppler = 1 + 0.12 * (-np.tanh(x * 2))
        rev = 1 + 0.25 * np.sin(2 * np.pi * (0.7 + 0.2 * k) * t) ** 2 + 0.15 * _lp(_rng(seed).standard_normal(len(t)), 3) * 20
        f = base * doppler * rev
        ph = np.cumsum(f) / SR
        eng = sum(np.sin(2 * np.pi * h * ph) / h ** 0.9 for h in range(1, 14))
        eng += 0.4 * _bp(_rng(seed + 10).standard_normal(len(t)), 200, 3000)
        eng = np.tanh(eng * 1.5)
        eng = _lp(eng, 2500) * amp
        pan = np.clip(0.5 + 0.5 * np.tanh(x), 0, 1)
        out[:, 0] += eng * np.sqrt(1 - pan)
        out[:, 1] += eng * np.sqrt(pan)
    return out / np.abs(out).max() * 0.9


# ── ambience (generated to length) ───────────────────────────

def rain(d, seed=60):
    r = _rng(seed)
    n = len(_t(d))
    hiss = _bp(r.standard_normal(n), 800, 9000) * 0.25
    hiss *= 0.85 + 0.15 * _lp(r.standard_normal(n), 0.5) * 40
    drops = np.zeros(n)
    idx = r.integers(0, n - 400, int(d * 60))
    for i in idx:
        k = int(r.uniform(40, 200))
        drops[i:i + k] += r.uniform(-1, 1) * np.exp(-np.arange(k) / (k / 5))
    drops = _bp(drops, 1200, 7000) * 0.5
    low = _lp(r.standard_normal(n), 300) * 0.3
    return _norm(hiss + drops + low, 0.5)


def rain_inside(d):
    return _norm(_lp(rain(d, 61), 1500), 0.35)


def fridge_hum(d):
    t = _t(d)
    x = sum(g * np.sin(2 * np.pi * f * t) for f, g in ((50, 1), (100, 0.6), (150, 0.25), (300, 0.08)))
    x += 0.15 * _lp(_rng(62).standard_normal(len(t)), 600)
    return _norm(x, 0.2)


def _babble(d, seed, f_base, f_form, rate=4.5):
    r = _rng(seed)
    t = _t(d)
    syl = (_lp(r.standard_normal(len(t)), rate) * 25).clip(0, None)
    f0 = f_base * (1 + 0.25 * _lp(r.standard_normal(len(t)), 1.5) * 25)
    x = _formants(_glottal(f0, d, seed), [(f_form, 300, 1), (f_form * 2.1, 500, 0.5)])
    return x * syl


def telly_jeremy(d):
    """Muffled daytime-telly row: two arguing voices, crowd 'ooohs'."""
    r = _rng(70)
    a = _babble(d, 71, 140, 600, 5)
    b = _babble(d, 72, 230, 800, 6)
    t = _t(d)
    turn = (np.sin(2 * np.pi * 0.23 * t) > 0).astype(float)
    turn = _lp(turn, 3)
    x = a * turn + b * (1 - turn) * 0.9
    crowd = np.zeros(len(t))
    for at in np.arange(r.uniform(2, 5), d, r.uniform(6, 9)):
        n = int(1.5 * SR)
        i = int(at * SR)
        sw = np.sin(np.pi * np.arange(n) / n) ** 2
        seg = _bp(r.standard_normal(n), 300, 1400) * sw
        crowd[i:i + n] += seg[: len(crowd) - i]
    x = _lp(x + 0.6 * crowd, 1600)  # through a wall / tinny speaker
    return _norm(x, 0.4)


def telly_muffled(d):
    return _norm(_lp(telly_jeremy(d), 500), 0.3)


# ── music ────────────────────────────────────────────────────

def music(d, bpm=70, seed=80):
    """Plinky, slightly sad music-box loop (A minor). Ironically gentle."""
    beat = 60 / bpm
    t = _t(d)
    out = np.zeros(len(t))
    A4 = 440

    def note(semi, at, dur, g):
        f = A4 * 2 ** (semi / 12)
        n = int(dur * SR)
        tt = np.arange(n) / SR
        x = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt) * np.exp(-tt * 6)
             + 0.12 * np.sin(2 * np.pi * 3.01 * f * tt) * np.exp(-tt * 9))
        x *= np.exp(-tt * 2.2) * np.clip(tt * 300, 0, 1) * g
        i = int(at * SR)
        m = min(n, len(out) - i)
        if m > 0:
            out[i:i + m] += x[:m]

    # Am - F - C - E, arpeggiated, melody on top
    chords = [[0, 3, 7], [-4, 0, 3], [3, 7, 10], [-5, -1, 2]]
    melody = [12, 10, 7, 8, 7, 3, 5, 3, 2, 3, 7, 5, 4, 2, -1, 2]
    bar = 4 * beat
    k = 0
    at = 0.0
    while at < d:
        ch = chords[k % 4]
        for i in range(8):
            note(ch[i % 3] - 12 + (12 if i % 4 == 3 else 0), at + i * beat / 2, 2.0, 0.22)
        note(ch[0] - 24, at, bar * 1.1, 0.25)
        for j in range(4):
            note(melody[(k * 4 + j) % len(melody)], at + j * beat, 1.6, 0.35)
        at += bar
        k += 1
    pad = _lp(out, 3500)
    return _norm(pad * _env(len(out), 1.5, 3.0), 0.6)


# ── registry ─────────────────────────────────────────────────

ONE_SHOTS = {f.__name__: f for f in (pop, slide, door_ding, coins_jingle, coin_slam, slide_pack, lighter,
                                     crisp_rustle, sigh, sigh_tariq, dog_bark, car_alarm_far, car_alarm_near,
                                     pigeon, mam_groan, mam_groan_big, bikes_pass)}
AMBIENCE = {f.__name__: f for f in (rain, rain_inside, fridge_hum, telly_jeremy, telly_muffled)}
_cache: dict = {}


def _override(name):
    p = OVERRIDES / f"{name}.wav"
    if p.exists():
        return audio_io.read_wav(p)
    return None


def one_shot(name: str, variant: int = 0) -> np.ndarray:
    key = (name, variant)
    if key not in _cache:
        o = _override(name)
        if o is not None:
            _cache[key] = o
        elif name == "squeak":
            _cache[key] = squeak(variant)
        elif name in ONE_SHOTS:
            _cache[key] = ONE_SHOTS[name]()
        else:
            raise KeyError(f"unknown sfx '{name}'")
    return _cache[key]


def ambience(name: str, d: float) -> np.ndarray:
    o = _override(name)
    if o is not None:
        reps = int(np.ceil(d * SR / len(o)))
        return np.tile(o, reps)[: int(d * SR)]
    if name not in AMBIENCE:
        raise KeyError(f"unknown ambience '{name}'")
    return AMBIENCE[name](d)
