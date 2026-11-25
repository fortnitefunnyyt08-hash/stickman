"""Episode 1 with AI-illustrated shots (shots.yaml), animated in code:
Ken Burns camera moves, lip flaps from mouth-open variants, cut-out sprites for
action (Kai's pop out and waddle, the dirt bikes, a rolling coin), rain and shake.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import skia
import yaml
from PIL import Image

from stickman.draw import back_out, clamp, ease, ease_in, ease_out, fill, hexc, lerp, stroke
from stickman.shots import ShotSet

W, H = 1080, 1920
SAMPLING = skia.SamplingOptions(skia.CubicResampler.Mitchell())
INK = hexc("#151517")

_shots: ShotSet | None = None
_img: dict = {}
_scene_shots: dict = {}


def _load_rgb(path: Path) -> skia.Image:
    a = np.asarray(Image.open(path).convert("RGBA"))
    return skia.Image.fromarray(np.ascontiguousarray(a), colorType=skia.kRGBA_8888_ColorType)


def _load_layer(img: Path, mask: Path) -> skia.Image:
    rgb = np.asarray(Image.open(img).convert("RGB"))
    m = np.asarray(Image.open(mask).convert("L").resize((rgb.shape[1], rgb.shape[0])))
    a = m.astype(np.float32) / 255
    rgba = np.dstack([(rgb * a[..., None]).astype(np.uint8), m])  # premultiplied
    return skia.Image.fromarray(np.ascontiguousarray(rgba), colorType=skia.kRGBA_8888_ColorType,
                                alphaType=skia.kPremul_AlphaType)


def setup(ep_dir, tl, preview=False):
    global _shots
    _shots = ShotSet(Path(ep_dir))
    spec = _shots.spec
    for sh in spec["shots"]:
        sid = sh["id"]
        _img[sid] = _load_rgb(_shots.base(sid))
        names = list((sh.get("variants") or {}).keys()) + [f"talk_{k}" for k in (sh.get("talk") or {})]
        for n in names:
            m = _shots.mask(sid, n)
            v = m.with_name(m.name.replace("_mask.png", "_aligned.png"))
            if v.exists() and m.exists():
                _img[f"{sid}__{n}"] = _load_layer(v, m)
    for sp in spec.get("sprites", []):
        p = _shots.sprite(sp["id"])
        if p.exists():
            _img[sp["id"]] = _load_rgb(p)
    for sc in tl.scenes:
        lst = [s for s in spec["shots"] if s["scene"] == sc.id]
        _scene_shots[sc.id] = sorted(lst, key=lambda s: sc.mark(s["from"]).start)


# ── generic shot player ──────────────────────────────────────

def current_shot(x):
    lst = _scene_shots.get(x.scene.id, [])
    cur, start, end = None, 0.0, x.dur
    for i, s in enumerate(lst):
        st = x.m(s["from"]).start if i else 0.0
        if x.t >= st:
            cur, start = s, st
            end = x.m(lst[i + 1]["from"]).start if i + 1 < len(lst) else x.dur
    return cur, start, end


def shot_matrix(sh, k, img: skia.Image, t, shake=0.0):
    (cx0, cy0, z0), (cx1, cy1, z1) = sh.get("move", [[0.5, 0.5, 1.0], [0.5, 0.5, 1.0]])
    e = ease(k)
    cx, cy, z = lerp(cx0, cx1, e), lerp(cy0, cy1, e), lerp(z0, z1, e)
    # gentle handheld drift so nothing is ever perfectly still
    cx += 0.002 * math.sin(t * 0.9)
    cy += 0.002 * math.sin(t * 0.7 + 1)
    iw, ih = img.width(), img.height()
    s = max(W / iw, H / ih) * z
    hw, hh = W / 2 / s, H / 2 / s
    px = min(max(cx * iw, hw), iw - hw)
    py = min(max(cy * ih, hh), ih - hh)
    m = skia.Matrix()
    m.setTranslate(-px, -py)
    m.postScale(s, s)
    m.postTranslate(W / 2 + shake * math.sin(t * 70), H / 2 + shake * math.cos(t * 53))
    return m


def draw_image(c, img, m, alpha=1.0):
    c.save()
    c.concat(m)
    p = skia.Paint()
    if alpha < 1:
        p.setAlphaf(alpha)
    c.drawImage(img, 0, 0, SAMPLING, p)
    c.restore()


def sprite(c, name, x, y, height, rot=0.0, flip=False, alpha=1.0):
    """Draw a cut-out with its bottom-centre at (x, y) in screen pixels."""
    img = _img.get(name)
    if img is None:
        return
    s = height / img.height()
    c.save()
    c.translate(x, y)
    c.rotate(rot)
    c.scale(-s if flip else s, s)
    p = skia.Paint()
    if alpha < 1:
        p.setAlphaf(alpha)
    c.drawImage(img, -img.width() / 2, -img.height(), SAMPLING, p)
    c.restore()


def flap(x, speaker):
    """Mouth open/closed from the voice loudness, with a little hysteresis feel."""
    v = x.talk(speaker)
    return v > 0.28


class Player:
    full_frame = True
    rain = False

    def shake(self, x):
        return 0.0

    def camera(self, x):
        sh, _, _ = current_shot(x)
        x.rain = 1.0 if (sh and sh.get("rain")) else 0.0

    def variant(self, x, sh, st, en):
        """Name of a non-talk variant to show (override per scene)."""
        return None

    def draw(self, x):
        c = x.c
        sh, st, en = current_shot(x)
        if not sh:
            return
        sid = sh["id"]
        img = _img[sid]
        k = (x.t - st) / max(0.01, en - st)
        m = shot_matrix(sh, k, img, x.scene.start + x.t, self.shake(x))
        draw_image(c, img, m)
        v = self.variant(x, sh, st, en)
        if v and f"{sid}__{v}" in _img:
            draw_image(c, _img[f"{sid}__{v}"], m)
        for spk in (sh.get("talk") or {}):
            key = f"{sid}__talk_{spk}"
            if key in _img and flap(x, spk):
                draw_image(c, _img[key], m)
        self.extra(x, sh, st, en, m)

    def extra(self, x, sh, st, en, m):
        pass


def waddle_pose(phase):
    a = math.sin(phase * 2 * math.pi)
    return 6 * a, abs(math.sin(phase * 2 * math.pi))


# ── scenes ───────────────────────────────────────────────────

class ColdOpen(Player):
    def draw(self, x):
        super().draw(x)
        a = 1 - clamp(x.t / 0.8)  # fade in from black
        if a > 0:
            x.c.drawRect(skia.Rect.MakeWH(W, H), fill(hexc("#000000"), a))


class Birth(Player):
    def shake(self, x):
        return 14 * max(0.0, 1 - abs(x.t - x.m("pop").start) / 0.3)

    def variant(self, x, sh, st, en):
        if sh["id"] != "b_sit":
            return None
        lk = x.m("look")
        if lk.start + 0.3 <= x.t < lk.start + lk.dur * 0.5:
            return "up"
        if lk.start + lk.dur * 0.5 <= x.t < lk.end - 0.2:
            return "window"
        return None

    def extra(self, x, sh, st, en, m):
        if sh["id"] != "b_wide":
            return
        pop = x.m("pop")
        k = (x.t - pop.start) / pop.dur
        if 0 <= k <= 1:
            # Kai shoots out from under the sheet and tumbles off towards the camera
            kk = ease_out(k)
            sx = lerp(W * 0.42, W * 0.9, kk)
            sy = lerp(H * 0.66, H * 1.25, ease_in(k)) - math.sin(k * math.pi) * H * 0.18
            sprite(x.c, "kai_slide", sx, sy, lerp(H * 0.18, H * 0.42, kk), rot=lerp(-40, 320, kk))


class Errand(Player):
    pass


class Waddle(Player):
    """Kai waddles across each street shot; the pasty lad and the pigeon are in the pictures."""

    def kai_x(self, x, sh, st, en):
        k = (x.t - st) / max(0.01, en - st)
        if sh["id"] == "w_lad":
            return lerp(-0.05, 0.42, ease_out(k)) * W   # slows to nod at the lad
        return lerp(-0.12, 1.12, k) * W

    def extra(self, x, sh, st, en, m):
        kx = self.kai_x(x, sh, st, en)
        phase = (x.t - st) * 2.6
        sway, bob = waddle_pose(phase)
        sprite(x.c, "kai_walk", kx, H * 0.9 - bob * 14, H * 0.3, rot=sway)


class Offy(Player):
    def shake(self, x):
        return 12 * max(0.0, 1 - abs(x.t - x.m("slam").start) / 0.2)

    def extra(self, x, sh, st, en, m):
        if sh["id"] != "o_coins":
            return
        # one coin rolls all the way to the door
        k = clamp((x.t - st - 0.3) / 2.0)
        if 0 < k < 1:
            cx = lerp(W * 0.55, W * 0.08, ease_out(k))
            cy = H * 0.86 + abs(math.sin(k * 14)) * 10 * (1 - k)
            wob = 0.25 + 0.15 * math.sin(x.t * 30) * (1 - k)
            rect = skia.Rect.MakeXYWH(cx - 16, cy - 16 * (1 - wob * 2.5), 32, 32 * (1 - wob * 2.5) * 2)
            x.c.drawOval(rect, fill(hexc("#d6a742")))
            x.c.drawOval(rect, stroke(INK, 3))


class Lads(Player):
    def camera(self, x):
        super().camera(x)
        p = x.m("pass")
        x.rain_speed = 0.25 if p.start <= x.t < p.end else 1.0

    def shake(self, x):
        b, p = x.m("build"), x.m("pass")
        if b.start <= x.t < p.end:
            return 3 + 5 * clamp((x.t - b.start) / (b.dur + 1))
        return 0.0

    def extra(self, x, sh, st, en, m):
        if sh["id"] != "l_kai":
            return
        p = x.m("pass")
        k = (x.t - p.start + 0.2) / (p.dur + 0.4)
        if 0 <= k <= 1:
            bx = lerp(-W * 0.9, W * 1.9, k)            # slow-mo wheelies across the road
            bob = math.sin(x.t * 9) * 6
            sprite(x.c, "lads_bikes", bx, H * 0.97 + bob, H * 0.36, rot=-3 + math.sin(x.t * 2) * 2)
            ck = clamp((x.t - p.start - 1.2) / 1.4)
            if 0 < ck < 1:
                sprite(x.c, "crisp_packet", lerp(-80, W + 80, ck), H * 0.55 + math.sin(ck * 9) * 40, 110, rot=ck * 720)


class EndCard(Player):
    def screen(self, x):
        c, t = x.c, x.t
        from stickman.config import ROOT
        tf = skia.Typeface.MakeFromFile(str(ROOT / "assets/fonts/Bangers-Regular.ttf"))
        big, mid = skia.Font(tf, 150), skia.Font(tf, 96)
        k = back_out(clamp(t / 0.6))
        for txt, f, y, col in (("EPISODE 2 >>", big, 330, "#ffd83d"), ("THE JOB CENTRE", mid, 450, "#f2f2ee")):
            w = f.measureText(txt)
            c.save()
            c.translate(W / 2, y)
            c.scale(k, k)
            c.drawString(txt, -w / 2, 0, f, stroke(INK, 18))
            c.drawString(txt, -w / 2, 0, f, fill(hexc(col)))
            c.restore()
        a = clamp((t - 0.9) / 0.5)
        pulse = 1 + 0.05 * math.sin(t * 6)
        txt = "FOLLOW FOR PART 2"
        w = mid.measureText(txt)
        c.save()
        c.translate(W / 2, 1780)
        c.scale(pulse, pulse)
        r = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-w / 2 - 44, -92, w + 88, 124), 62, 62)
        c.drawRRect(r, fill(hexc("#e8314a"), a))
        c.drawString(txt, -w / 2, 0, mid, fill(hexc("#ffffff"), a))
        c.restore()


SCENES = {"cold_open": ColdOpen(), "birth": Birth(), "errand": Errand(), "waddle": Waddle(), "offy": Offy(),
          "lads": Lads(), "end_card": EndCard()}


def audio_events(tl) -> list:
    """Squeaky footsteps while Kai waddles across the street shots."""
    ev = []
    for sc in tl.scenes:
        if sc.id != "waddle":
            continue
        n = 0
        t = 0.0
        while t < sc.duration:
            ev.append({"name": "squeak", "t": sc.start + t, "variant": n % 6, "gain": 0.5, "pan": 0.5})
            n += 1
            t += 1 / (2.6 * 2)
    for sc in tl.scenes:
        if sc.id == "lads":
            ev.append({"name": "door_ding", "t": sc.start + 0.05, "gain": 0.6})
    return ev
