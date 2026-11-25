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
        self.retry_rejected = False

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
            if img.get("use", "").startswith("shot:"):   # reuse another shot's picture
                src = self.base(img["use"].split(":", 1)[1])
                yield 2, sid, (lambda src=src, sid=sid: self._copy(src, self.base(sid)))
            elif img.get("use"):
                src = ref_path(img["use"])
                yield 0, sid, (lambda src=src, sid=sid: self._copy(src, self.base(sid)))
            else:
                refs = [self.base(r.split(":", 1)[1]) if r.startswith("shot:") else ref_path(r) for r in sh.get("refs", [])]
                stage = 1 if any(r.startswith("shot:") for r in sh.get("refs", [])) else 0
                prompt = f"{self.style}\n\n{sh['prompt'].strip()}"
                yield stage, sid, (lambda p=prompt, r=refs, sid=sid: self._gen(p, r, self.base(sid), "9:16", sid in redo))
            vars_ = dict(sh.get("variants", {}))
            for spk, p in (sh.get("talk") or {}).items():
                vars_[f"talk_{spk}"] = p
            faces = sh.get("faces") or {}
            for name, p in vars_.items():
                face = faces.get(name[5:]) if name.startswith("talk_") else (list(faces.values()) or [None])[0]
                yield 2, f"{sid}__{name}", (lambda p=p, sid=sid, name=name, face=face: self._variant(sid, name, p, sid in redo, face))
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

    def _variant(self, sid, name, prompt, force, face=None):
        base = self.base(sid)
        out = self.variant(sid, name)
        full = (f"{prompt} Keep the exact same composition, framing, background, lighting, colours and every other "
                f"character exactly as they are.")
        key = hashlib.sha1(base.read_bytes()).hexdigest()
        if self.retry_rejected and self.mask(sid, name).with_name(self.mask(sid, name).name.replace("_mask.png", "_rejected.txt")).exists():
            force = True
        st = self._gen(full, [base], out, "9:16", force, extra=key)
        for attempt in range(1, 3):
            if make_mask(base, out, self.mask(sid, name), "talk" if name.startswith("talk_") else "head", face):
                return st + ("" if attempt == 1 else f" (retry {attempt - 1})")
            st = self._gen(full, [base], out, "9:16", True, extra=key + str(attempt))
        ok = make_mask(base, out, self.mask(sid, name), "talk" if name.startswith("talk_") else "head", face)
        return st + (" ok after retries" if ok else " REJECTED (mouth stays still)")

    def _sprite(self, prompt, refs, sid, force):
        raw = self.out / "sprites" / f"{sid}_green.png"
        st = self._gen(prompt, refs, raw, "1:1", force)
        chroma_key(raw, self.sprite(sid))
        return st

    def run(self, redo=(), log=print):
        jobs = list(self.jobs(redo))
        for stage in (0, 1, 2):
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

def align(base: Path, var: Path) -> np.ndarray:
    """Line the variant up with the base picture (the model often shifts or rescales
    the whole image slightly). Returns the variant warped onto the base, as RGB."""
    import cv2
    a = np.asarray(Image.open(base).convert("RGB"))
    b = np.asarray(Image.open(var).convert("RGB").resize((a.shape[1], a.shape[0])))
    ga, gb = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY), cv2.cvtColor(b, cv2.COLOR_RGB2GRAY)
    orb = cv2.ORB_create(4000)
    ka, da = orb.detectAndCompute(ga, None)
    kb, db = orb.detectAndCompute(gb, None)
    if da is None or db is None:
        return b
    matches = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True).match(db, da)
    if len(matches) < 30:
        return b
    src = np.float32([kb[m.queryIdx].pt for m in matches])
    dst = np.float32([ka[m.trainIdx].pt for m in matches])
    M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=2.0)
    if M is None:
        return b
    return cv2.warpAffine(b, M, (a.shape[1], a.shape[0]), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def make_mask(base: Path, var: Path, out: Path, kind: str = "talk", face=None) -> bool:
    """Align the variant, then build a small soft mask over the one spot that
    changed (the mouth). Writes <variant>_aligned.png and the mask. Returns False
    (and writes no mask) if the variant changed more than that one spot."""
    a = np.asarray(Image.open(base).convert("RGB"), dtype=np.float32)
    b = align(base, var).astype(np.float32)
    h, w = a.shape[:2]
    d = np.abs(a - b).sum(axis=2)
    ds = np.asarray(Image.fromarray(d.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(5)), dtype=np.float32)
    if face is not None:  # only look for the change around this speaker's face
        fx, fy = int(face[0] * w), int(face[1] * h)
        lim = np.zeros_like(ds)
        lim[max(0, fy - int(h * 0.08)): fy + int(h * 0.08), max(0, fx - int(w * 0.13)): fx + int(w * 0.13)] = 1
        ds = ds * lim
    cy, cx = np.unravel_index(np.argmax(ds), ds.shape)
    # mouth-sized window around the strongest change (head-sized for eye/head variants)
    rx, ry = (int(w * 0.12), int(h * 0.07)) if kind == "talk" else (int(w * 0.16), int(h * 0.10))
    hot = ds > max(30.0, ds[cy, cx] * 0.25)
    win = np.zeros_like(hot)
    win[max(0, cy - ry): cy + ry, max(0, cx - rx): cx + rx] = True
    region = hot & win
    m = np.zeros((h, w), np.uint8)
    if region.any():
        ys, xs = np.nonzero(region)
        pad = int(w * 0.02)
        m[max(0, ys.min() - pad): ys.max() + pad, max(0, xs.min() - pad): xs.max() + pad] = 255
    # quality check: does the area just around the patch line up with the base?
    # (changes elsewhere don't matter, only the patch is pasted)
    inner = np.asarray(Image.fromarray(m).filter(ImageFilter.MaxFilter(9)))
    outer = np.asarray(Image.fromarray(m).filter(ImageFilter.MaxFilter(41)))
    ring = (outer > 0) & (inner == 0)
    seam = float(d[ring].mean()) if ring.any() else 999.0
    outside = seam / 765
    ok = bool(region.any()) and seam < 40.0
    aligned = out.with_name(out.name.replace("_mask.png", "_aligned.png"))
    rej = out.with_name(out.name.replace("_mask.png", "_rejected.txt"))
    if ok:
        Image.fromarray(b.astype(np.uint8)).save(aligned)
        Image.fromarray(m).filter(ImageFilter.GaussianBlur(int(w * 0.008) + 1)).save(out)
        rej.unlink(missing_ok=True)
    else:
        out.unlink(missing_ok=True)
        aligned.unlink(missing_ok=True)
        rej.write_text(f"seam mismatch {seam:.1f}\n")
    return ok


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
    ap.add_argument("--retry-rejected", action="store_true", help="have another go at mouth variants that failed the check")
    a = ap.parse_args(argv)
    ss = ShotSet(Path(a.episode))
    ss.retry_rejected = a.retry_rejected
    ss.run(set(a.redo))


if __name__ == "__main__":
    main()
