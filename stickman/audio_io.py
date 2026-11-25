"""Small audio helpers: read/write WAV via ffmpeg, envelopes."""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np

SR = 44100


def run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{r.stderr[-2000:]}")


def to_wav(src: Path, dst: Path, sr: int = SR, extra_filters: str | None = None) -> None:
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ac", "1", "-ar", str(sr)]
    if extra_filters:
        cmd += ["-af", extra_filters]
    run(cmd + [str(dst)])


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        assert w.getsampwidth() == 2, "expected 16-bit wav"
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            data = data.reshape(-1, 2).mean(axis=1)
    return data


def write_wav(path: Path, data: np.ndarray, sr: int = SR) -> None:
    data = np.clip(data, -1, 1)
    ch = 1 if data.ndim == 1 else data.shape[1]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((data * 32767).astype(np.int16).tobytes())


def envelope(data: np.ndarray, fps: int, sr: int = SR) -> np.ndarray:
    """Per-video-frame loudness 0..1, used for mouth flaps."""
    hop = sr // fps
    n = int(np.ceil(len(data) / hop))
    pad = np.pad(data, (0, n * hop - len(data)))
    rms = np.sqrt((pad.reshape(n, hop) ** 2).mean(axis=1))
    if rms.max() > 0:
        rms = rms / np.percentile(rms, 95).clip(1e-4)
    return np.clip(rms, 0, 1)


def trim_silence_bounds(data: np.ndarray, sr: int = SR, thresh: float = 0.02) -> tuple[float, float]:
    idx = np.where(np.abs(data) > thresh)[0]
    if len(idx) == 0:
        return 0.0, len(data) / sr
    return idx[0] / sr, idx[-1] / sr
