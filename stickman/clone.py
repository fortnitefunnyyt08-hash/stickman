"""Clone character voices on ElevenLabs from the cleaned samples.

    python -m stickman.clone            # clone every character with a voice_sample
    python -m stickman.clone kai mam    # just these
    python -m stickman.clone --force    # re-clone even if a voice ID exists

Voice IDs are saved to config/voices.local.yaml (git-ignored).
Only clone voices of people who have agreed to it.
"""
from __future__ import annotations

import argparse
import sys

import requests

from .config import ROOT, load_local_voices, load_series, save_local_voice
from .tts import api_key


def clone(cfg: dict, key: str, ch: dict) -> str:
    sample = ROOT / ch["voice_sample"]
    if not sample.exists():
        raise SystemExit(f"[{key}] sample not found: {sample}")
    url = f"{cfg['tts']['api_base']}/v1/voices/add"
    with open(sample, "rb") as f:
        r = requests.post(
            url,
            headers={"xi-api-key": api_key()},
            data={"name": f"Stickman - {ch['name']}",
                  "description": f"Stickman series character voice: {ch['name']} (used with consent)",
                  "remove_background_noise": "true"},
            files=[("files", (sample.name, f, "audio/wav"))],
            timeout=300,
        )
    if r.status_code != 200:
        raise SystemExit(f"[{key}] clone failed ({r.status_code}): {r.text[:500]}")
    return r.json()["voice_id"]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("characters", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_series()
    local = load_local_voices()
    targets = a.characters or [k for k, c in cfg["characters"].items() if c.get("voice_sample")]
    for key in targets:
        ch = cfg["characters"][key]
        if not ch.get("voice_sample"):
            print(f"[{key}] no voice_sample, skipping")
            continue
        if local.get(key) and not a.force:
            print(f"[{key}] already cloned: {local[key]} (use --force to redo)")
            continue
        vid = clone(cfg, key, ch)
        save_local_voice(key, vid)
        print(f"[{key}] cloned -> {vid}")


if __name__ == "__main__":
    sys.exit(main())
