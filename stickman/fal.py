"""fal.ai image generation (pictures only, no video). The key is injected by the
network proxy in the cloud environment, or read from FAL_KEY locally."""
from __future__ import annotations

import base64
import json
import mimetypes
import os
from pathlib import Path

import requests

from .config import BUILD

LEDGER = BUILD / "ai" / "spend.jsonl"
PRICES = {"fal-ai/nano-banana": 0.039, "fal-ai/nano-banana/edit": 0.039}   # USD per image, approx


def _key() -> str:
    return os.environ.get("FAL_KEY") or "proxy-injected"


def data_uri(path: Path) -> str:
    mt = mimetypes.guess_type(str(path))[0] or "image/png"
    return f"data:{mt};base64," + base64.b64encode(Path(path).read_bytes()).decode()


def generate(prompt: str, out: Path, refs: list[Path] | None = None, aspect: str = "9:16",
             model: str | None = None) -> Path:
    """Text-to-image, or image editing/consistency from reference pictures when refs are given."""
    model = model or ("fal-ai/nano-banana/edit" if refs else "fal-ai/nano-banana")
    body = {"prompt": prompt, "num_images": 1, "output_format": "png", "sync_mode": True, "aspect_ratio": aspect}
    if refs:
        body["image_urls"] = [data_uri(p) for p in refs]
    r = requests.post(f"https://fal.run/{model}", headers={"Authorization": f"Key {_key()}"}, json=body, timeout=600)
    if r.status_code != 200:
        raise RuntimeError(f"fal {model} failed ({r.status_code}): {r.text[:500]}")
    url = r.json()["images"][0]["url"]
    data = base64.b64decode(url.split(",", 1)[1]) if url.startswith("data:") else requests.get(url, timeout=120).content
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as f:
        f.write(json.dumps({"model": model, "out": str(out), "usd": PRICES.get(model, 0)}) + "\n")
    return out


def spent() -> float:
    if not LEDGER.exists():
        return 0.0
    return sum(json.loads(line)["usd"] for line in LEDGER.read_text().splitlines() if line.strip())
