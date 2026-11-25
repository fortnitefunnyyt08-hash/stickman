"""Frame renderer: camera, backgrounds, per-scene animation, rain, grading,
captions and titles, piped straight into ffmpeg."""
from __future__ import annotations

import math
import random
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import skia

from . import backgrounds, draw
from .draw import clamp, ease, fill, hexc, stroke
from .timeline import Beat, Scene, Timeline


@dataclass
class Camera:
    cx: float = 540
    cy: float = 960
    zoom: float = 1.0
    rot: float = 0.0
    shake: float = 0.0


class Ctx:
    """Everything a scene's animation function gets each frame."""

    def __init__(self, canvas, scene: Scene, t: float, fps: int, info: dict, frame: int):
        self.c = canvas
        self.scene = scene
        self.t = t                    # seconds since scene start
        self.dur = scene.duration
        self.fps = fps
        self.info = info
        self.frame = frame
        self.cam = Camera()
        self.rain = 0.0               # 0..1 rain overlay intensity
        self.rain_speed = 1.0
        self.overlays = []            # callables drawn in screen space after grading

    def m(self, bid: str) -> Beat:
        return self.scene.mark(bid)

    def since(self, bid: str) -> float:
        return self.t - self.m(bid).start

    def prog(self, bid: str, dur: float | None = None, delay: float = 0.0) -> float:
        b = self.m(bid)
        d = dur if dur is not None else b.dur
        return clamp((self.t - b.start - delay) / max(1e-6, d))

    def within(self, bid: str) -> bool:
        b = self.m(bid)
        return b.start <= self.t < b.end

    def after(self, bid: str) -> bool:
        return self.t >= self.m(bid).start

    def talk(self, speaker: str) -> float:
        """Mouth-open amount 0..1 from whichever line `speaker` is saying now."""
        for b in self.scene.beats:
            if b.kind == "line" and b.speaker == speaker and b.start <= self.t < b.end:
                i = int((self.t - b.start) * self.fps)
                if b.env is not None and i < len(b.env):
                    return float(b.env[i]) ** 0.7
        return 0.0

    def speaking(self, speaker: str) -> bool:
        return any(b.kind == "line" and b.speaker == speaker and b.start <= self.t < b.end for b in self.scene.beats)


# ── screen-space effects ─────────────────────────────────────

class Rain:
    def __init__(self, W, H, n=260, seed=1):
        r = random.Random(seed)
        self.drops = [(r.uniform(-200, W + 200), r.uniform(0, H), r.uniform(0.6, 1.4), r.uniform(26, 60)) for _ in range(n)]
        self.W, self.H = W, H

    def draw(self, c, t, intensity, speed=1.0):
        if intensity <= 0:
            return
        p = stroke(hexc("#dfe6ec"), 2.2, 0.35 * intensity)
        for x, y, v, ln in self.drops:
            yy = (y + t * 1700 * v * speed) % (self.H + 100) - 50
            xx = x - (yy * 0.12)
            c.drawLine(xx, yy, xx - ln * 0.12, yy + ln, p)


def make_grain(W, H, n=6, seed=7):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        g = rng.integers(0, 255, (H // 2, W // 2), dtype=np.uint8)
        a = np.full_like(g, 255)
        rgba = np.dstack([g, g, g, a])
        out.append(skia.Image.fromarray(rgba, colorType=skia.kRGBA_8888_ColorType))
    return out


def vignette(c, W, H, amount):
    shader = skia.GradientShader.MakeRadial((W / 2, H / 2), H * 0.72, [skia.Color(0, 0, 0, 0), skia.Color(0, 0, 0, int(255 * amount))],
                                            [0.45, 1.0])
    c.drawRect(skia.Rect.MakeWH(W, H), skia.Paint(Shader=shader))


# ── captions + titles ────────────────────────────────────────

class Captions:
    def __init__(self, cfg: dict, W: int, H: int):
        cc = cfg["captions"]
        self.cfg = cc
        self.font = skia.Font(skia.Typeface.MakeFromFile(cc["font"]), cc["size"])
        self.W, self.H = W, H
        self.censor = [w.lower() for w in cc.get("censor", [])]

    def _fmt(self, w: str) -> str:
        if self.cfg.get("uppercase"):
            w = w.upper()
        for bad in self.censor:
            w = re.sub(bad, lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 2) + m.group(0)[-1], w, flags=re.I)
        return w

    def draw(self, c, beat: Beat, lt: float):
        words = beat.clip.words if beat.clip else []
        if not words:
            return
        cur = 0
        for i, (_, s, e) in enumerate(words):
            if lt >= s:
                cur = i
        n = self.cfg["max_words"]
        start = (cur // n) * n
        chunk = words[start:start + n]
        texts = [self._fmt(w) for w, _, _ in chunk]
        space = self.font.measureText(" ")
        widths = [self.font.measureText(tx) for tx in texts]
        # wrap if too wide
        total = sum(widths) + space * (len(texts) - 1)
        scale = min(1.0, (self.W - 120) / max(1, total))
        y = self.H * self.cfg["y"]
        x = self.W / 2 - total * scale / 2
        out = stroke(hexc(self.cfg["outline"]), self.cfg["outline_width"])
        for k, (tx, wdt) in enumerate(zip(texts, widths)):
            idx = start + k
            ws = chunk[k][1]
            pop = 1.0
            if idx == cur:
                pop = 1 + 0.18 * max(0, 1 - (lt - ws) / 0.12)
            active = idx == cur
            visible = lt >= ws - 0.02
            if not visible:
                x += (wdt + space) * scale
                continue
            c.save()
            cx = x + wdt * scale / 2
            c.translate(cx, y)
            c.scale(scale * pop, scale * pop)
            c.drawString(tx, -wdt / 2, 0, self.font, out)
            col = hexc(self.cfg["highlight"] if active else self.cfg["color"])
            c.drawString(tx, -wdt / 2, 0, self.font, fill(col))
            c.restore()
            x += (wdt + space) * scale


def draw_title(c, cfg, W, H, text, style, k_in, k_out, t):
    """style: stamp (top, typewriter) | card (full-screen black card) | endcard."""
    font = skia.Font(skia.Typeface.MakeFromFile(cfg["titles"]["font"]), cfg["titles"]["size"])
    if style == "card":
        a = min(k_in * 4, 1) * (1 - k_out)
        c.drawRect(skia.Rect.MakeWH(W, H), fill(hexc("#0d0e10"), a))
        w = font.measureText(text)
        c.drawString(text, W / 2 - w / 2, H * 0.47, font, fill(hexc("#f2f2ee"), a))
        return
    # stamp: typewriter in a box at the top-middle
    n = int(len(text) * clamp(k_in * 1.6))
    shown = text[:n]
    w = font.measureText(text)
    x, y = W / 2 - w / 2, H * 0.17
    a = 1 - k_out
    c.drawRect(skia.Rect.MakeXYWH(x - 30, y - 80, w + 60, 110), fill(hexc("#0d0e10"), 0.7 * a))
    c.drawString(shown, x, y, font, fill(hexc("#f2f2ee"), a))
    if n < len(text) and int(t * 4) % 2 == 0:
        c.drawRect(skia.Rect.MakeXYWH(x + font.measureText(shown) + 6, y - 50, 26, 56), fill(hexc("#f2f2ee"), a))


# ── main loop ────────────────────────────────────────────────

def render(cfg: dict, tl: Timeline, animations: dict, out: Path, audio: Path, preview: bool = False,
           only_scene: str | None = None, log=print) -> None:
    W, H, fps = cfg["video"]["width"], cfg["video"]["height"], cfg["video"]["fps"]
    st = cfg["style"]
    draw.set_style(st)
    scale_out = 0.5 if preview else 1.0
    OW, OH = int(W * scale_out), int(H * scale_out)
    scenes = [s for s in tl.scenes if not only_scene or s.id == only_scene]
    t_offset = scenes[0].start if only_scene else 0.0
    total = sum(s.duration for s in scenes)

    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{OW}x{OH}", "-r", str(fps),
           "-i", "-", "-ss", f"{t_offset:.3f}", "-t", f"{total:.3f}", "-i", str(audio),
           "-c:v", "libx264", "-preset", "veryfast" if preview else cfg["video"]["preset"],
           "-crf", str(cfg["video"]["crf"] + (4 if preview else 0)), "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(out)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    surf = skia.Surface(OW, OH)
    c = surf.getCanvas()
    rain = Rain(W, H)
    grain = make_grain(W, H)
    caps = Captions(cfg, W, H)
    tint = hexc(st["grade"]["tint"])
    bg_cache: dict = {}

    frame = 0
    try:
        for sc in scenes:
            if sc.background not in bg_cache:
                bg_cache.clear()
                bg_cache[sc.background] = backgrounds.render(sc.background, 1.0 if preview else 2.0)
            bg_img, info, (bw, bh) = bg_cache[sc.background]
            bscale = bw / bg_img.width()
            anim = animations.get(sc.id)
            nframes = int(round(sc.duration * fps))
            log(f"  rendering {sc.id:>10}: {nframes} frames")
            for f in range(nframes):
                t = f / fps
                c.save()
                c.scale(scale_out, scale_out)
                c.clear(skia.ColorBLACK)
                ctx = Ctx(c, sc, t, fps, info, frame)
                if anim and hasattr(anim, "camera"):
                    anim.camera(ctx)
                cam = ctx.cam
                fy = cfg["video"].get("frame_y", 0.56)
                cam.zoom = max(cam.zoom, 1.0)
                hw = W / 2 / cam.zoom
                cam.cx = min(max(cam.cx, hw), bw - hw)
                cam.cy = min(max(cam.cy, H * fy / cam.zoom), bh - H * (1 - fy) / cam.zoom)
                c.save()
                sx = (math.sin(frame * 1.7) + math.sin(frame * 0.83)) * cam.shake
                sy = (math.cos(frame * 1.3) + math.sin(frame * 0.57)) * cam.shake
                c.translate(W / 2 + sx, H * fy + sy)
                c.rotate(cam.rot)
                c.scale(cam.zoom, cam.zoom)
                c.translate(-cam.cx, -cam.cy)
                c.save()
                c.scale(bscale, bscale)
                c.drawImage(bg_img, 0, 0, skia.SamplingOptions(skia.FilterMode.kLinear))
                c.restore()
                if anim:
                    anim.draw(ctx)
                c.restore()
                # screen-space weather + grade
                rain.draw(c, sc.start + t, ctx.rain, ctx.rain_speed)
                c.drawRect(skia.Rect.MakeWH(W, H), fill(tint, st["grade"]["amount"]))
                g = grain[frame % len(grain)]
                gp = skia.Paint(BlendMode=skia.BlendMode.kOverlay)
                gp.setAlphaf(st["grain"])
                c.drawImageRect(g, skia.Rect.MakeWH(W, H), skia.SamplingOptions(), gp)
                vignette(c, W, H, st["vignette"])
                for ov in ctx.overlays:
                    ov(c)
                # titles
                for ti in sc.titles:
                    if ti["at"] <= t < ti["until"]:
                        k_in = (t - ti["at"]) / 1.0
                        k_out = clamp((t - (ti["until"] - 0.35)) / 0.35)
                        draw_title(c, cfg, W, H, ti["text"], ti.get("style", "stamp"), k_in, k_out, t)
                # captions
                for b in sc.beats:
                    if b.kind == "line" and b.start <= t < b.end + 0.15:
                        caps.draw(c, b, t - b.start)
                if anim and hasattr(anim, "screen"):
                    anim.screen(ctx)
                c.restore()
                arr = surf.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)
                proc.stdin.write(arr.tobytes())
                frame += 1
    finally:
        proc.stdin.close()
        rc = proc.wait()
    if rc != 0:
        raise RuntimeError("ffmpeg encode failed")
