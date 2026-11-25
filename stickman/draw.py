"""Stickman drawing kit (skia). Characters, faces, outfits, props, motion helpers.

Angles are in degrees: 0 = pointing straight down, positive = toward the way the
character faces. `facing` is +1 (right) or -1 (left).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, replace

import skia

# ── colour + paint helpers ───────────────────────────────────

def hexc(s: str, a: int = 255) -> int:
    s = s.lstrip("#")
    return skia.Color(int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


def mix(c1: str, c2: str, k: float) -> int:
    a = [int(c1.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return skia.Color(*[int(x + (y - x) * k) for x, y in zip(a, b)])


INK = hexc("#151517")
WHITE = hexc("#ffffff")
FIGURE = hexc("#fbfbf8")      # stickman body colour (white figures)
HEAD = FIGURE


def set_style(style: dict) -> None:
    """Apply series-wide figure colours from config/series.yaml -> style."""
    global INK, FIGURE, HEAD
    INK = hexc(style.get("ink", "#151517"))
    FIGURE = hexc(style.get("figure", "#fbfbf8"))
    HEAD = FIGURE


def fill(color, alpha: float = 1.0) -> skia.Paint:
    p = skia.Paint(AntiAlias=True, Color=color)
    if alpha < 1:
        p.setAlphaf(alpha)
    return p


def stroke(color, w: float, alpha: float = 1.0, cap=skia.Paint.kRound_Cap) -> skia.Paint:
    p = skia.Paint(AntiAlias=True, Color=color, Style=skia.Paint.kStroke_Style, StrokeWidth=w)
    p.setStrokeCap(cap)
    p.setStrokeJoin(skia.Paint.kRound_Join)
    if alpha < 1:
        p.setAlphaf(alpha)
    return p


def poly(points, close=True) -> skia.Path:
    p = skia.Path()
    p.moveTo(*points[0])
    for q in points[1:]:
        p.lineTo(*q)
    if close:
        p.close()
    return p


def smooth_path(points, close=False) -> skia.Path:
    """Catmull-Rom-ish smooth path through points."""
    p = skia.Path()
    p.moveTo(*points[0])
    pts = points + ([points[0], points[1]] if close else [points[-1]])
    for i in range(1, len(pts) - 1):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        p.quadTo(x1, y1, (x1 + x2) / 2, (y1 + y2) / 2) if i < len(pts) - 2 else p.lineTo(x1, y1)
    if close:
        p.close()
    return p


# ── easing / motion ──────────────────────────────────────────

def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_in(x):
    x = clamp(x)
    return x ** 3


def lerp(a, b, k):
    return a + (b - a) * k


def back_out(x, s=1.7):
    x = clamp(x) - 1
    return x * x * ((s + 1) * x + s) + 1


def keyframes(t, keys):
    """keys: [(time, value_or_tuple), ...] eased between."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            k = ease((t - t0) / max(1e-6, t1 - t0))
            if isinstance(v0, tuple):
                return tuple(lerp(a, b, k) for a, b in zip(v0, v1))
            return lerp(v0, v1, k)
    return keys[-1][1]


# ── body + pose ──────────────────────────────────────────────

@dataclass
class Body:
    head_r: float = 34
    neck: float = 8
    torso: float = 100
    upper_arm: float = 50
    lower_arm: float = 46
    thigh: float = 56
    shin: float = 54
    line: float = 9

    @property
    def leg(self):
        return self.thigh + self.shin


ADULT = Body()
BABY = Body(head_r=44, neck=2, torso=40, upper_arm=24, lower_arm=20, thigh=20, shin=19, line=8)


@dataclass
class Pose:
    lean: float = 0                  # torso: + forward, - back
    arm_b: tuple = (8, 10)           # (shoulder, elbow-bend) back arm
    arm_f: tuple = (-8, 10)          # front arm
    leg_b: tuple = (9, -3)           # (hip, knee-bend) back leg
    leg_f: tuple = (-9, 3)
    head_tilt: float = 0
    arms_folded: bool = False


STAND = Pose()


@dataclass
class Face:
    eyes: str = "open"               # open | tired | wide | closed | glare | squint
    look: tuple = (0.0, 0.0)         # pupil offset -1..1
    blink: float = 0.0               # 0..1
    brows: float = 0.0               # + angry/frown, - worried/raised
    mouth: str = "flat"              # flat | frown | smile | o | grimace | smirk
    talk: float = 0.0                # 0..1 mouth open from speech
    cheeks: bool = False


@dataclass
class Look:
    """Outfit + accessories."""
    nappy: bool = False
    vest: bool = False
    tuft: bool = False
    gown: str | None = None          # dressing gown colour
    scrubs: str | None = None
    tracksuit: str | None = None
    socks_over: bool = False
    hair: str | None = None          # bun | short | cap
    bucket_hat: str | None = None
    readers_on_head: bool = False
    hair_color: str = "#3b2f2a"


def _pt(o, ang, length, facing):
    a = math.radians(ang)
    return (o[0] + math.sin(a) * length * facing, o[1] + math.cos(a) * length)


def joints(hip, body: Body, pose: Pose, facing: int = 1, s: float = 1.0) -> dict:
    j = {"hip": hip}
    lean = math.radians(pose.lean)
    j["neck"] = (hip[0] + math.sin(lean) * body.torso * s * facing, hip[1] - math.cos(lean) * body.torso * s)
    j["shoulder"] = _pt(j["neck"], 180 + pose.lean, -body.torso * 0.08 * s, facing)  # slightly below neck
    j["head"] = (j["neck"][0] + math.sin(lean) * (body.neck + body.head_r) * s * facing,
                 j["neck"][1] - math.cos(lean) * (body.neck + body.head_r) * s)
    for side in ("b", "f"):
        sh, el = getattr(pose, f"arm_{side}")
        j[f"elbow_{side}"] = _pt(j["shoulder"], sh, body.upper_arm * s, facing)
        j[f"hand_{side}"] = _pt(j[f"elbow_{side}"], sh + el, body.lower_arm * s, facing)
        hp, kn = getattr(pose, f"leg_{side}")
        j[f"knee_{side}"] = _pt(hip, hp, body.thigh * s, facing)
        j[f"foot_{side}"] = _pt(j[f"knee_{side}"], hp + kn, body.shin * s, facing)
    return j


def _limb(c, pts, w, color=None):
    c.drawPath(poly(pts, close=False), stroke(INK if color is None else color, w))


def _body_line(c, pts, w):
    """A white limb with a dark outline."""
    _limb(c, pts, w + max(3.0, w * 0.6), INK)
    _limb(c, pts, w, FIGURE)


def draw_stickman(c: skia.Canvas, hip, body: Body = ADULT, pose: Pose = STAND, face: Face = Face(),
                  look: Look = Look(), facing: int = 1, s: float = 1.0, head_fill=None, ink=None) -> dict:
    """Draws one character with its hip at `hip`. Returns joint positions for props."""
    head_fill = FIGURE if head_fill is None else head_fill
    ink = INK if ink is None else ink
    j = joints(hip, body, pose, facing, s)
    lw = body.line * s
    # back limbs first
    if not pose.arms_folded:
        _arm(c, j, "b", lw, look, s, body)
    _leg(c, j, "b", lw, look, s)
    if look.nappy:
        _leg(c, j, "f", lw, look, s)

    # clothing on torso
    if look.gown:
        _gown(c, j, look.gown, lw, s, facing, body)
    if look.scrubs:
        _tunic(c, j, look.scrubs, lw, s, facing, body)
    if look.tracksuit:
        _limb(c, [j["hip"], j["neck"]], lw * 3.6 + 4 * s, ink)
        _limb(c, [j["hip"], j["neck"]], lw * 3.6, hexc(look.tracksuit))
        _limb(c, [j["hip"], j["neck"]], lw * 0.4, mix(look.tracksuit, "#ffffff", 0.35))
    else:
        _body_line(c, [j["hip"], j["neck"]], lw)
    if look.vest:
        _vest(c, j, lw, s, body)
    if look.nappy:
        _nappy(c, j, lw, s, body)
    else:
        _leg(c, j, "f", lw, look, s)
    if pose.arms_folded:
        _folded_arms(c, j, lw, s, body, facing, look)
    else:
        _arm(c, j, "f", lw, look, s, body)

    _head(c, j["head"], body.head_r * s, lw, face, look, facing, pose.head_tilt, head_fill, ink)
    return j


def _arm(c, j, side, lw, look, s, body):
    pts = [j["shoulder"], j[f"elbow_{side}"], j[f"hand_{side}"]]
    if look.gown:
        _limb(c, pts[:2] + [_lerp_pt(pts[1], pts[2], 0.75)], lw * 3.0, hexc(look.gown))
    if look.tracksuit:
        _limb(c, pts, lw * 2.6 + 4 * s, INK)
        _limb(c, pts, lw * 2.6, hexc(look.tracksuit))
        c.drawCircle(*pts[2], lw * 0.9, fill(FIGURE))
        c.drawCircle(*pts[2], lw * 0.9, stroke(INK, 2.5 * s))
        return
    if look.scrubs:
        _limb(c, [pts[0], _lerp_pt(pts[0], pts[1], 0.6)], lw * 2.8, hexc(look.scrubs))
    _body_line(c, pts, lw)


def _folded_arms(c, j, lw, s, body, facing, look):
    sh, hp = j["shoulder"], j["hip"]
    y = lerp(sh[1], hp[1], 0.35)
    w = body.upper_arm * s * 0.9
    a = (sh[0] - w * 0.9, y)
    b = (sh[0] + w * 0.9, y + 2 * s)
    if look.tracksuit:
        _limb(c, [a, b], lw * 2.6, hexc(look.tracksuit))
    _body_line(c, [(sh[0] - w * 0.6, sh[1] + 4 * s), a, b], lw)
    _body_line(c, [(sh[0] + w * 0.6, sh[1] + 4 * s), b, (a[0] + w * 0.3, y - 3 * s)], lw)


def _lerp_pt(a, b, k):
    return (lerp(a[0], b[0], k), lerp(a[1], b[1], k))


def _leg(c, j, side, lw, look, s):
    pts = [j["hip"], j[f"knee_{side}"], j[f"foot_{side}"]]
    if look.tracksuit:
        _limb(c, pts, lw * 2.8 + 4 * s, INK)
        _limb(c, pts, lw * 2.8, hexc(look.tracksuit))
        if look.socks_over:
            _limb(c, [_lerp_pt(pts[1], pts[2], 0.72), pts[2]], lw * 3.0, hexc("#f4f4f4"))
        # trainers
        f = pts[2]
        c.drawOval(skia.Rect.MakeXYWH(f[0] - 13 * s, f[1] - 5 * s, 28 * s, 13 * s), fill(hexc("#e9e9ea")))
        c.drawOval(skia.Rect.MakeXYWH(f[0] - 13 * s, f[1] - 5 * s, 28 * s, 13 * s), stroke(INK, 2.5 * s))
        return
    _body_line(c, pts, lw)


def _gown(c, j, color, lw, s, facing, body):
    n, h = j["neck"], j["hip"]
    w = body.torso * s
    top_l, top_r = (n[0] - w * 0.22, n[1] + 4 * s), (n[0] + w * 0.22, n[1] + 4 * s)
    dx = h[0] - n[0]
    bot_l, bot_r = (h[0] - w * 0.36 + dx * 0.2, h[1] + w * 0.55), (h[0] + w * 0.36 + dx * 0.2, h[1] + w * 0.55)
    path = poly([top_l, top_r, bot_r, bot_l])
    c.drawPath(path, fill(hexc(color)))
    c.drawPath(path, stroke(INK, lw * 0.45))
    # lapels + belt
    c.drawPath(poly([n, _lerp_pt(n, h, 0.55), (h[0] + w * 0.1 * facing, h[1] + w * 0.5)], close=False),
               stroke(mix(color, "#000000", 0.25), lw * 0.4))
    by = lerp(n[1], h[1], 0.75)
    c.drawLine(lerp(top_l[0], bot_l[0], 0.6), by, lerp(top_r[0], bot_r[0], 0.6), by, stroke(mix(color, "#000000", 0.2), lw * 0.7))
    # fluffy texture dots
    for k in range(9):
        px = lerp(top_l[0], bot_r[0], (k * 0.37) % 1)
        py = lerp(n[1] + 10 * s, h[1] + w * 0.4, (k * 0.61) % 1)
        c.drawCircle(px, py, 2.2 * s, fill(mix(color, "#ffffff", 0.35)))


def _tunic(c, j, color, lw, s, facing, body):
    n, h = j["neck"], j["hip"]
    w = body.torso * s
    path = poly([(n[0] - w * 0.2, n[1] + 3 * s), (n[0] + w * 0.2, n[1] + 3 * s),
                 (h[0] + w * 0.25, h[1] + w * 0.12), (h[0] - w * 0.25, h[1] + w * 0.12)])
    c.drawPath(path, fill(hexc(color)))
    c.drawPath(path, stroke(INK, lw * 0.45))
    c.drawPath(poly([(n[0] - w * 0.08, n[1] + 3 * s), (n[0], n[1] + w * 0.14), (n[0] + w * 0.08, n[1] + 3 * s)], close=False),
               stroke(INK, lw * 0.35))


def _vest(c, j, lw, s, body):
    n, h = j["neck"], j["hip"]
    w = body.torso * s
    path = poly([(n[0] - w * 0.32, n[1] + 2 * s), (n[0] - w * 0.12, n[1] + 2 * s), (n[0], n[1] + w * 0.15),
                 (n[0] + w * 0.12, n[1] + 2 * s), (n[0] + w * 0.32, n[1] + 2 * s),
                 (h[0] + w * 0.42, h[1] - w * 0.05), (h[0] - w * 0.42, h[1] - w * 0.05)])
    c.drawPath(path, fill(hexc("#f5f3ee")))
    c.drawPath(path, stroke(INK, lw * 0.5))
    # a little stain, naturally
    c.drawOval(skia.Rect.MakeXYWH(n[0] + w * 0.02, lerp(n[1], h[1], 0.55), w * 0.16, w * 0.11), fill(hexc("#c9b48a"), 0.7))


def _nappy(c, j, lw, s, body):
    h = j["hip"]
    w = body.thigh * s * 0.95
    r = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(h[0] - w, h[1] - w * 0.6, 2 * w, w * 1.2), w * 0.5, w * 0.5)
    c.drawRRect(r, fill(hexc("#fbfbf8")))
    c.drawRRect(r, stroke(INK, lw * 0.6))
    c.drawRect(skia.Rect.MakeXYWH(h[0] - w * 0.95, h[1] - w * 0.45, w * 0.35, w * 0.25), fill(hexc("#9ec9e8")))
    c.drawRect(skia.Rect.MakeXYWH(h[0] + w * 0.6, h[1] - w * 0.45, w * 0.35, w * 0.25), fill(hexc("#9ec9e8")))


def _head(c, ctr, r, lw, f: Face, look: Look, facing, tilt, head_fill, ink):
    x, y = ctr
    c.save()
    c.rotate(tilt * facing, x, y)
    if look.hair == "bun":
        c.drawCircle(x - r * 0.75 * facing, y - r * 0.55, r * 0.42, fill(hexc(look.hair_color)))
        c.drawCircle(x - r * 0.75 * facing, y - r * 0.55, r * 0.42, stroke(ink, lw * 0.5))
    c.drawCircle(x, y, r, fill(head_fill))
    if look.hair in ("bun", "short", "scraped"):
        p = skia.Path()
        p.addArc(skia.Rect.MakeXYWH(x - r, y - r, 2 * r, 2 * r), 200, 140)
        p.close()
        c.drawPath(p, fill(hexc(look.hair_color)))
        for k in (-0.3, 0.0, 0.3):  # scraped-back comb lines
            c.drawLine(x + r * k, y - r * 0.62, x + r * (k - 0.25 * facing), y - r * 0.92, stroke(mix(look.hair_color, "#000000", 0.35), lw * 0.25))
    c.drawCircle(x, y, r, stroke(ink, lw))
    if look.tuft:
        p = skia.Path()
        p.moveTo(x - r * 0.05, y - r * 0.98)
        p.cubicTo(x - r * 0.1, y - r * 1.5, x + r * 0.45, y - r * 1.55, x + r * 0.3 * facing, y - r * 1.2)
        c.drawPath(p, stroke(ink, lw * 0.7))
    if look.readers_on_head:
        gy = y - r * 0.82
        for dx in (-0.32, 0.32):
            c.drawOval(skia.Rect.MakeXYWH(x + r * dx - r * 0.22, gy - r * 0.13, r * 0.44, r * 0.28), stroke(ink, lw * 0.35))
        c.drawLine(x - r * 0.1, gy, x + r * 0.1, gy, stroke(ink, lw * 0.3))
    if look.bucket_hat:
        hc = hexc(look.bucket_hat)
        brim = skia.Path()
        brim.moveTo(x - r * 1.3, y - r * 0.35)
        brim.quadTo(x, y - r * 0.6, x + r * 1.3, y - r * 0.35)
        brim.lineTo(x + r * 0.85, y - r * 0.6)
        brim.quadTo(x + r * 0.9, y - r * 1.35, x, y - r * 1.35)
        brim.quadTo(x - r * 0.9, y - r * 1.35, x - r * 0.85, y - r * 0.6)
        brim.close()
        c.drawPath(brim, fill(hc))
        c.drawPath(brim, stroke(ink, lw * 0.5))
    _face(c, x + r * 0.18 * facing, y + r * 0.05, r, lw, f, facing, ink)
    c.restore()


def _face(c, x, y, r, lw, f: Face, facing, ink):
    ex = r * 0.36
    ey = y - r * 0.12
    er = r * 0.2
    lx, ly = f.look
    for i, sx in enumerate((-1, 1)):
        cx = x + sx * ex
        open_amt = {"open": 1, "tired": 0.5, "wide": 1.25, "closed": 0, "glare": 0.38, "squint": 0.2}[f.eyes]
        open_amt *= 1 - clamp(f.blink)
        h = er * 2 * open_amt
        if open_amt > 0.05:
            rect = skia.Rect.MakeXYWH(cx - er, ey - er * (1.25 if f.eyes == "wide" else 1), er * 2,
                                      er * (2.5 if f.eyes == "wide" else 2))
            c.save()
            # eyelid clip: keep the lower part of the eye
            c.clipRect(skia.Rect.MakeLTRB(cx - er * 1.5, ey + er - h, cx + er * 1.5, ey + er * 1.6))
            c.drawOval(rect, fill(WHITE))
            pr = er * (0.42 if f.eyes == "wide" else 0.55)
            c.drawCircle(cx + lx * er * 0.45 + facing * er * 0.1, ey + ly * er * 0.45 + er * 0.1, pr, fill(ink))
            c.drawOval(rect, stroke(ink, lw * 0.28))
            c.restore()
            if open_amt < 0.95:  # lid line
                c.drawLine(cx - er * 1.05, ey + er - h, cx + er * 1.05, ey + er - h, stroke(ink, lw * 0.45))
        else:
            c.drawLine(cx - er, ey + er * 0.3, cx + er, ey + er * 0.3, stroke(ink, lw * 0.45))
        # brows
        by = ey - er * (1.5 if f.eyes == "wide" else 1.25)
        tilt = f.brows * er * 0.5 * sx
        c.drawLine(cx - er, by - tilt, cx + er, by + tilt, stroke(ink, lw * 0.45))
    # mouth
    my = y + r * 0.45
    mw = r * 0.32
    if f.talk > 0.08:
        h = r * 0.08 + r * 0.32 * clamp(f.talk)
        c.drawOval(skia.Rect.MakeXYWH(x - mw * 0.6, my - h / 2, mw * 1.2, h), fill(hexc("#3a1a1c")))
        c.drawOval(skia.Rect.MakeXYWH(x - mw * 0.6, my - h / 2, mw * 1.2, h), stroke(ink, lw * 0.35))
        return
    p = skia.Path()
    if f.mouth == "flat":
        p.moveTo(x - mw * 0.7, my)
        p.lineTo(x + mw * 0.7, my)
    elif f.mouth == "frown":
        p.moveTo(x - mw * 0.8, my + r * 0.07)
        p.quadTo(x, my - r * 0.1, x + mw * 0.8, my + r * 0.07)
    elif f.mouth == "smile":
        p.moveTo(x - mw * 0.8, my - r * 0.05)
        p.quadTo(x, my + r * 0.14, x + mw * 0.8, my - r * 0.05)
    elif f.mouth == "smirk":
        p.moveTo(x - mw * 0.6, my + r * 0.02)
        p.quadTo(x + mw * 0.2, my + r * 0.03, x + mw * 0.8 * facing, my - r * 0.06)
    elif f.mouth == "grimace":
        p.moveTo(x - mw * 0.8, my)
        for k in range(1, 7):
            p.lineTo(x - mw * 0.8 + k * mw * 1.6 / 6, my + (r * 0.04 if k % 2 else -r * 0.04))
    elif f.mouth == "o":
        c.drawCircle(x, my, r * 0.09, fill(hexc("#3a1a1c")))
        c.drawCircle(x, my, r * 0.09, stroke(ink, lw * 0.35))
        return
    c.drawPath(p, stroke(ink, lw * 0.5))


# ── props ────────────────────────────────────────────────────

def fag(c, hand, t, s=1.0, angle=-20, smoke=True, lit=True):
    c.save()
    c.translate(*hand)
    c.rotate(angle)
    c.drawRect(skia.Rect.MakeXYWH(0, -3 * s, 26 * s, 6 * s), fill(hexc("#f2f0ea")))
    c.drawRect(skia.Rect.MakeXYWH(0, -3 * s, 8 * s, 6 * s), fill(hexc("#d49a52")))
    if lit:
        glow = 0.7 + 0.3 * math.sin(t * 7)
        c.drawRect(skia.Rect.MakeXYWH(25 * s, -3 * s, 4 * s, 6 * s), fill(mix("#7a2a10", "#ff6a1a", glow)))
    c.restore()
    if smoke and lit:
        ang = math.radians(angle)
        tip = (hand[0] + math.cos(ang) * 29 * s, hand[1] + math.sin(ang) * 29 * s)
        for k in range(5):
            ph = (t * 0.6 + k / 5) % 1
            sx = tip[0] + math.sin(ph * 9 + k) * 10 * s * ph
            sy = tip[1] - ph * 110 * s
            c.drawCircle(sx, sy, (4 + ph * 16) * s, fill(hexc("#c9c9cc"), 0.35 * (1 - ph)))


def phone(c, hand, s=1.0, angle=0, glow=True):
    c.save()
    c.translate(*hand)
    c.rotate(angle)
    r = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-10 * s, -30 * s, 20 * s, 36 * s), 4 * s, 4 * s)
    c.drawRRect(r, fill(hexc("#1d1d22")))
    if glow:
        c.drawRect(skia.Rect.MakeXYWH(-8 * s, -27 * s, 16 * s, 29 * s), fill(hexc("#9fd0ff")))
    c.restore()


def coins(c, pos, n=5, s=1.0, seed=0):
    import random
    r = random.Random(seed)
    for k in range(n):
        dx, dy = r.uniform(-12, 12) * s, r.uniform(-6, 6) * s
        coin(c, (pos[0] + dx, pos[1] + dy), s * r.uniform(0.8, 1.1), silver=r.random() < 0.6)


def coin(c, pos, s=1.0, silver=True, edge=0.0):
    w = 9 * s
    h = 9 * s * (1 - 0.8 * abs(edge))
    col = hexc("#c9c9cf") if silver else hexc("#c2914a")
    c.drawOval(skia.Rect.MakeXYWH(pos[0] - w, pos[1] - h, 2 * w, 2 * h), fill(col))
    c.drawOval(skia.Rect.MakeXYWH(pos[0] - w, pos[1] - h, 2 * w, 2 * h), stroke(INK, 2 * s))


def fag_pack(c, pos, s=1.0, angle=0):
    c.save()
    c.translate(*pos)
    c.rotate(angle)
    rect = skia.Rect.MakeXYWH(-16 * s, -22 * s, 32 * s, 44 * s)
    c.drawRect(rect, fill(hexc("#f1efe9")))
    c.drawRect(skia.Rect.MakeXYWH(-16 * s, -22 * s, 32 * s, 14 * s), fill(hexc("#2a3f7a")))
    c.drawRect(skia.Rect.MakeXYWH(-13 * s, 4 * s, 26 * s, 12 * s), fill(hexc("#1b1b1b")))
    c.drawRect(rect, stroke(INK, 2.5 * s))
    c.restore()


def pasty(c, pos, s=1.0, bite=True):
    p = skia.Path()
    p.moveTo(pos[0] - 26 * s, pos[1] + 6 * s)
    p.quadTo(pos[0], pos[1] - 26 * s, pos[0] + 26 * s, pos[1] + 6 * s)
    p.close()
    c.drawPath(p, fill(hexc("#d9a15a")))
    c.drawPath(p, stroke(INK, 3 * s))
    for k in range(5):
        x = pos[0] - 16 * s + k * 8 * s
        c.drawLine(x, pos[1] - 6 * s - (8 - abs(k - 2) * 3) * s, x + 4 * s, pos[1] - 10 * s - (8 - abs(k - 2) * 3) * s, stroke(hexc("#a56d2c"), 3 * s))
    if bite:
        c.drawCircle(pos[0] + 24 * s, pos[1] - 2 * s, 8 * s, fill(hexc("#00000000")))


# ── walk cycles ──────────────────────────────────────────────

def waddle(phase: float, amount: float = 1.0) -> tuple[Pose, float, float]:
    """Baby waddle: returns (pose, sway_deg, bob_px_per_unit)."""
    a = math.sin(phase * 2 * math.pi)
    b = abs(math.sin(phase * 2 * math.pi))
    pose = Pose(lean=2, arm_b=(25 * a * amount - 30, 20), arm_f=(-25 * a * amount - 30, 20),
                leg_b=(22 * a * amount, -8 * (1 - b)), leg_f=(-22 * a * amount, -8 * b))
    return pose, 7 * a * amount, b


def walk(phase: float, amount: float = 1.0) -> tuple[Pose, float]:
    a = math.sin(phase * 2 * math.pi)
    b = abs(math.cos(phase * 2 * math.pi))
    pose = Pose(lean=4, arm_b=(28 * a * amount, 15), arm_f=(-28 * a * amount, 15),
                leg_b=(26 * a * amount, -18 * max(0, -a)), leg_f=(-26 * a * amount, -18 * max(0, a)))
    return pose, b


def with_pose(p: Pose, **kw) -> Pose:
    return replace(p, **kw)


def blink_at(t: float, seed: float = 0.0) -> float:
    """Natural-ish blinking: returns 0..1 eyelid closure."""
    period = 3.1 + (seed % 1.3)
    ph = (t + seed) % period
    return clamp(1 - abs(ph - 0.08) / 0.08) if ph < 0.16 else 0.0
