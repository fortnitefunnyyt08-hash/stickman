"""Generate an episode's AI pictures from shots.yaml (cached; only new or changed
shots cost money).

    python -m stickman.shots episodes/ep01_born_in_bradford            # generate missing
    python -m stickman.shots episodes/ep01_born_in_bradford --redo b_sit   # redo one shot
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageFilter

from .config import BUILD
from .fal import generate, spent

AI = BUILD / "ai"
CHAR_SHEETS = {"kai": "kai_mid", "kai_vest": "kai_vest"}       # which sheet a character name points to


def ref_path(ref: str) -> Path:
    kind, name = ref.split(":", 1)
    if kind == "bg":
        return AI / "backgrounds" / f"{name}.png"
    if kind == "char":
        return AI / "characters" / f"{CHAR_SHEETS.get(name, name)}_sheet.png"
    raise ValueError(ref)


def _h(*parts) -> str:
    return hashlib.sha1(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:10]


class ShotSet:
    def __init__(self, ep_dir: Path):
        self.ep_dir = Path(ep_dir)
        self.spec = yaml.safe_load((self.ep_dir / "shots.yaml").read_text())
        self.out = AI / self.ep_dir.name
        self.style = self.spec.get("style", "").strip()

    # file locations
    def base(self, sid):
        return self.out / "shots" / f"{sid}.png"

    def variant(self, sid, name):
        return self.out / "shots" / f"{sid}__{name}.png"

    def mask(self, sid, name):
        return self.out / "shots" / f"{sid}__{name}_mask.png"

    def sprite(self, sid):
        return self.out / "sprites" / f"{sid}.png"

    def jobs(self, redo=()):
        """Yield (stage, key, fn) jobs. Stage 0 = base pictures, 1 = variants (need base)."""
        for sh in self.spec["shots"]:
            sid = sh["id"]
            img = sh.get("image", {})
            if img.get("use"):
                src = ref_path(img["use"])
                yield 0, sid, (lambda src=src, sid=sid: self._copy(src, self.base(sid)))
            else:
                refs = [ref_path(r) for r in sh.get("refs", [])]
                prompt = f"{self.style}\n\n{sh['prompt'].strip()}"
                yield 0, sid, (lambda p=prompt, r=refs, sid=sid: self._gen(p, r, self.base(sid), "9:16", sid in redo))
            vars_ = dict(sh.get("variants", {}))
            for spk, p in (sh.get("talk") or {}).items():
                vars_[f"talk_{spk}"] = p
            for name, p in vars_.items():
                yield 1, f"{sid}__{name}", (lambda p=p, sid=sid, name=name: self._variant(sid, name, p, sid in redo))
        for sp in self.spec.get("sprites", []):
            refs = [ref_path(r) for r in sp.get("refs", [])]
            prompt = (f"{self.style}\n\nA single cut-out character/prop for animation on a perfectly flat, solid pure green "
                      f"(#00FF00) chroma-key background, no shadow on the ground, no other objects, whole subject visible "
                      f"with space around it: {sp['prompt'].strip()}")
            yield 0, sp["id"], (lambda p=prompt, r=refs, sid=sp["id"]: self._sprite(p, r, sid, sid in redo))

    def _copy(self, src, dst):
        dst.parent.mkdir(parents=True, exist_ok=True)
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            shutil.copy(src, dst)
        return "copied"

    def _gen(self, prompt, refs, out, aspect, force, extra=""):
        tag = out.with_suffix(".key")
        key = _h(prompt, [str(r) for r in refs], aspect, extra)
        if out.exists() and not force and tag.exists() and tag.read_text() == key:
            return "cached"
        generate(prompt, out, refs=refs or None, aspect=aspect)
        tag.write_text(key)
        return "generated"

    def _variant(self, sid, name, prompt, force):
        base = self.base(sid)
        out = self.variant(sid, name)
        full = (f"{prompt} Keep the exact same composition, framing, background, lighting, colours and every other "
                f"character exactly as they are.")
        st = self._gen(full, [base], out, "9:16", force, extra=hashlib.sha1(base.read_bytes()).hexdigest())
        make_mask(base, out, self.mask(sid, name))
        return st

    def _sprite(self, prompt, refs, sid, force):
        raw = self.out / "sprites" / f"{sid}_green.png"
        st = self._gen(prompt, refs, raw, "1:1", force)
        chroma_key(raw, self.sprite(sid))
        return st

    def run(self, redo=(), log=print):
        jobs = list(self.jobs(redo))
        for stage in (0, 1):
            todo = [(k, f) for s, k, f in jobs if s == stage]
            with ThreadPoolExecutor(6) as ex:
                for k, res in zip([k for k, _ in todo], ex.map(lambda kf: _safe(kf[1]), todo)):
                    log(f"  {k:<28} {res}")
        log(f"  AI spend so far: ${spent():.2f}")


def _safe(fn):
    try:
        return fn()
    except Exception as e:  # keep going; report at the end
        return f"FAILED: {str(e)[:200]}"


# ── image helpers ────────────────────────────────────────────

def make_mask(base: Path, var: Path, out: Path) -> None:
    """Soft mask covering only the area that changed (e.g. a mouth), so a variant
    can be blended over the base without any other drift showing."""
    a = np.asarray(Image.open(base).convert("RGB").resize((384, 672)), dtype=np.float32)
    b = np.asarray(Image.open(var).convert("RGB").resize((384, 672)), dtype=np.float32)
    d = np.abs(a - b).sum(axis=2)
    d = np.asarray(Image.fromarray(d.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), dtype=np.float32)
    thr = max(25.0, np.percentile(d, 99.0) * 0.5)
    hot = d > thr
    if hot.sum() == 0:
        m = np.zeros_like(d)
    else:
        # keep the densest blob: the window around the strongest change
        ys, xs = np.nonzero(hot)
        cy, cx = np.unravel_index(np.argmax(d), d.shape)
        near = (np.abs(ys - cy) < 90) & (np.abs(xs - cx) < 90)
        ys, xs = ys[near], xs[near]
        m = np.zeros_like(d)
        y0, y1 = max(0, ys.min() - 14), min(d.shape[0], ys.max() + 14)
        x0, x1 = max(0, xs.min() - 14), min(d.shape[1], xs.max() + 14)
        m[y0:y1, x0:x1] = 255
    img = Image.fromarray(m.astype(np.uint8)).filter(ImageFilter.GaussianBlur(8))
    w, h = Image.open(base).size
    img.resize((w, h)).save(out)


def chroma_key(src: Path, dst: Path) -> None:
    """Remove the flat backdrop. The model rarely gives pure #00FF00, so the key
    colour is sampled from the picture's border and removed by colour distance."""
    im = np.asarray(Image.open(src).convert("RGB"), dtype=np.float32) / 255
    border = np.concatenate([im[:8].reshape(-1, 3), im[-8:].reshape(-1, 3), im[:, :8].reshape(-1, 3), im[:, -8:].reshape(-1, 3)])
    key = np.median(border, axis=0)
    dist = np.sqrt(((im - key) ** 2).sum(axis=2))
    alpha = np.clip((dist - 0.10) / 0.12, 0, 1)
    # keep only the region connected to the subject: fill holes from the inside
    a8 = Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.MedianFilter(5))
    alpha = np.asarray(a8, dtype=np.float32) / 255
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    # despill edges toward neutral
    edge = (alpha > 0) & (alpha < 1)
    g = np.where(edge, np.minimum(g, (r + b) / 2 + 0.05), g)
    out = np.dstack([r, g, b, alpha])
    ys, xs = np.nonzero(alpha > 0.05)
    if len(ys):
        out = out[max(0, ys.min() - 4): ys.max() + 4, max(0, xs.min() - 4): xs.max() + 4]
    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((out * 255).astype(np.uint8), "RGBA").save(dst)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--redo", nargs="*", default=[])
    a = ap.parse_args(argv)
    ShotSet(Path(a.episode)).run(set(a.redo))


if __name__ == "__main__":
    main()
