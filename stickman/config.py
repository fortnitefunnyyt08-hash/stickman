"""Loading the series config, local voice IDs and episode scripts."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "series.yaml"
VOICES_LOCAL = ROOT / "config" / "voices.local.yaml"
BUILD = ROOT / "build"


def load_series() -> dict:
    cfg = yaml.safe_load(CONFIG.read_text())
    local = load_local_voices()
    for key, ch in cfg["characters"].items():
        if not ch.get("voice_id") and local.get(key):
            ch["voice_id"] = local[key]
    return cfg


def load_local_voices() -> dict:
    if VOICES_LOCAL.exists():
        return yaml.safe_load(VOICES_LOCAL.read_text()) or {}
    return {}


def save_local_voice(character: str, voice_id: str) -> None:
    data = load_local_voices()
    data[character] = voice_id
    VOICES_LOCAL.write_text(
        "# Cloned ElevenLabs voice IDs (written by `python -m stickman.clone`). Git-ignored.\n"
        + yaml.safe_dump(data, sort_keys=True)
    )


def load_episode(path: str | os.PathLike) -> tuple[Path, dict]:
    p = Path(path)
    if p.is_dir():
        p = p / "script.yaml"
    return p.parent, yaml.safe_load(p.read_text())


def voice_for(cfg: dict, speaker: str) -> tuple[str | None, dict]:
    """Return (voice_id, character_cfg) following `voice_from` links."""
    ch = cfg["characters"][speaker]
    src = ch
    seen = set()
    while not src.get("voice_id") and src.get("voice_from") and src["voice_from"] not in seen:
        seen.add(src["voice_from"])
        src = cfg["characters"][src["voice_from"]]
    return src.get("voice_id"), ch


def pitch_for(ch: dict, episode: int) -> float:
    if "pitch_start" in ch:
        return float(ch["pitch_start"]) + float(ch.get("pitch_step", 0)) * (episode - 1)
    return float(ch.get("pitch", 0))
