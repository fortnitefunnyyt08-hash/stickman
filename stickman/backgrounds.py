"""Detailed, muted, slightly grim backgrounds. Drawn once per scene in world
coordinates, rasterised at 2x so camera push-ins stay sharp.

Each painter returns a dict of useful anchor points for the animation.
"""
from __future__ import annotations

import math
import random

import skia

from .draw import fill, hexc, mix, poly, stroke

INK = hexc("#151517")


def _rect(c, x, y, w, h, color, outline=None, ow=3, alpha=1.0):
    r = skia.Rect.MakeXYWH(x, y, w, h)
    c.drawRect(r, fill(color, alpha))
    if outline is not None:
        c.drawRect(r, stroke(outline, ow))


def _rrect(c, x, y, w, h, rad, color, outline=None, ow=3):
    r = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), rad, rad)
    c.drawRRect(r, fill(color))
    if outline is not None:
        c.drawRRect(r, stroke(outline, ow))


def _vgrad(c, x, y, w, h, top, bottom):
    p = skia.Paint(Shader=skia.GradientShader.MakeLinear([(x, y), (x, y + h)], [top, bottom]))
    c.drawRect(skia.Rect.MakeXYWH(x, y, w, h), p)


def _speckle(c, x, y, w, h, n, colors, rmin=1, rmax=3, seed=0, alpha=1.0):
    r = random.Random(seed)
    for _ in range(n):
        c.drawCircle(x + r.random() * w, y + r.random() * h, r.uniform(rmin, rmax), fill(r.choice(colors), alpha))


def _text(c, s, x, y, size, color, bold=True, center=False, font_path=None):
    tf = skia.Typeface.MakeFromFile(font_path or ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
                                                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
    f = skia.Font(tf, size)
    if center:
        x -= f.measureText(s) / 2
    c.drawString(s, x, y, f, fill(color))


def _sky(c, w, h, top="#7d858c", bottom="#a7adb0"):
    _vgrad(c, 0, 0, w, h, hexc(top), hexc(bottom))
    r = random.Random(3)
    for k in range(14):  # heavy low cloud
        cx, cy = r.uniform(-100, w + 100), r.uniform(0, h * 0.6)
        for j in range(5):
            c.drawOval(skia.Rect.MakeXYWH(cx + j * 70 - 140, cy + r.uniform(-25, 25), r.uniform(180, 320), r.uniform(70, 130)),
                       fill(hexc("#8a9196"), 0.35))


def _window(c, x, y, w, h, frame="#e9e7e1", glass="#4b5a66", inner=None):
    _rect(c, x - 10, y - 10, w + 20, h + 20, hexc(frame), INK, 4)
    _rect(c, x, y, w, h, hexc(glass))
    if inner:
        inner(c, x, y, w, h)
    c.drawLine(x + w / 2, y, x + w / 2, y + h, stroke(hexc(frame), 10))
    c.drawLine(x, y + h * 0.38, x + w, y + h * 0.38, stroke(hexc(frame), 10))
    _rect(c, x, y, w, h, hexc("#00000000"), INK, 3)
    _rect(c, x - 22, y + h + 8, w + 44, 16, hexc("#d8d5cc"), INK, 3)  # sill


def _wheelie_bin(c, x, y, color, s=1.0, overflowing=True, seed=0):
    w, h = 120 * s, 190 * s
    if overflowing:
        r = random.Random(seed)
        for k in range(4):
            bx = x + r.uniform(-10, w - 60)
            c.drawOval(skia.Rect.MakeXYWH(bx, y - 55 * s - r.uniform(0, 25), 80 * s, 70 * s), fill(hexc("#1e1f22")))
            c.drawOval(skia.Rect.MakeXYWH(bx, y - 55 * s - r.uniform(0, 25), 80 * s, 70 * s), stroke(INK, 3))
    c.drawPath(poly([(x, y), (x + w, y), (x + w * 0.93, y + h), (x + w * 0.07, y + h)]), fill(hexc(color)))
    c.drawPath(poly([(x, y), (x + w, y), (x + w * 0.93, y + h), (x + w * 0.07, y + h)]), stroke(INK, 4))
    lid = poly([(x - 8, y - 12), (x + w + 8, y - 12), (x + w + 8, y + 8), (x - 8, y + 8)])
    c.save()
    c.rotate(-14 if overflowing else 0, x + w, y)
    c.drawPath(lid, fill(mix(color, "#000000", 0.25)))
    c.drawPath(lid, stroke(INK, 4))
    c.restore()
    c.drawCircle(x + w * 0.15, y + h, 16 * s, fill(hexc("#222")))


def _puddles(c, x, y, w, n, seed=0, color="#7f8b94"):
    r = random.Random(seed)
    for _ in range(n):
        pw = r.uniform(80, 220)
        c.drawOval(skia.Rect.MakeXYWH(x + r.random() * (w - pw), y + r.uniform(-30, 30), pw, pw * 0.18), fill(hexc(color), 0.55))


def _terrace_row(c, x0, y_base, w, seed, height=330, colors=("#8f7b6e", "#7c6c62", "#93887c")):
    r = random.Random(seed)
    x = x0
    while x < x0 + w:
        hw = r.uniform(220, 280)
        col = hexc(r.choice(colors))
        _rect(c, x, y_base - height, hw, height, col, INK, 3)
        # brick lines
        for yy in range(int(y_base - height) + 18, int(y_base), 18):
            c.drawLine(x, yy, x + hw, yy, stroke(mix("#000000", "#555555", 0.5), 1, 0.15))
        # roof
        c.drawPath(poly([(x - 6, y_base - height), (x + hw + 6, y_base - height), (x + hw - 30, y_base - height - 70), (x + 30, y_base - height - 70)]),
                   fill(hexc("#4c4f55")))
        _rect(c, x + hw * 0.6, y_base - height - 110, 34, 50, hexc("#6d5a50"), INK, 2)  # chimney
        for wx in (0.15, 0.58):
            _rect(c, x + hw * wx, y_base - height + 50, hw * 0.27, 70, hexc("#55636d"), INK, 2)
            _rect(c, x + hw * wx, y_base - height + 170, hw * 0.27, 70, hexc("#55636d"), INK, 2)
        _rect(c, x + hw * 0.43, y_base - 110, 44, 110, hexc(r.choice(["#3d4f6b", "#6b2e2e", "#2f4d3a", "#e0ddd5"])), INK, 2)
        x += hw


# ── scenes ───────────────────────────────────────────────────

def estate(c, W=1080, H=1920):
    _sky(c, W, H)
    _terrace_row(c, -60, 900, W + 200, 11, 260, ("#7d7570", "#857a72"))
    _rect(c, 0, 900, W, 120, hexc("#6b706a"))  # far grass strip
    # the house: pebble-dash semi
    hx, hy, hw, hh = 150, 560, 780, 900
    c.drawPath(poly([(hx - 30, hy), (hx + hw + 30, hy), (hx + hw - 90, hy - 230), (hx + 90, hy - 230)]), fill(hexc("#53565c")))
    c.drawPath(poly([(hx - 30, hy), (hx + hw + 30, hy), (hx + hw - 90, hy - 230), (hx + 90, hy - 230)]), stroke(INK, 4))
    for k in range(9):  # roof tiles
        y = hy - 230 + k * 26
        c.drawLine(hx + 90 - k * 13, y, hx + hw - 90 + k * 13, y, stroke(hexc("#3e4146"), 2))
    _rect(c, hx + 520, hy - 330, 70, 120, hexc("#7a6658"), INK, 3)  # chimney
    _rect(c, hx, hy, hw, hh, hexc("#b9b3a4"), INK, 4)
    _speckle(c, hx, hy, hw, hh, 5500, [hexc("#a39d8e"), hexc("#cbc5b6"), hexc("#8f897b")], 1, 2.6, seed=4)
    # damp streaks
    for k, dx in enumerate((120, 430, 700)):
        c.drawRect(skia.Rect.MakeXYWH(hx + dx, hy + 5, 26, 260 + k * 60), fill(hexc("#6f6a5a"), 0.18))
    # gutter
    c.drawLine(hx - 30, hy + 4, hx + hw + 30, hy + 4, stroke(hexc("#2a2b2e"), 12))
    c.drawLine(hx + hw + 10, hy + 4, hx + hw + 10, hy + hh, stroke(hexc("#2a2b2e"), 9))

    def flag(c, x, y, w, h):
        _rect(c, x, y, w, h, hexc("#e9e7e2"))
        _rect(c, x + w * 0.42, y, w * 0.16, h, hexc("#b8242b"))
        _rect(c, x, y + h * 0.42, w, h * 0.16, hexc("#b8242b"))

    def sheet(c, x, y, w, h):
        _rect(c, x, y, w, h, hexc("#d9cfd8"))
        r = random.Random(9)
        for _ in range(26):
            px, py = x + r.random() * w, y + r.random() * h
            for a in range(5):
                c.drawCircle(px + math.cos(a * 1.26) * 8, py + math.sin(a * 1.26) * 8, 6, fill(hexc("#c38fa6"), 0.8))
        c.drawLine(x, y + 6, x + w, y + 6, stroke(hexc("#999"), 3))
        c.drawRect(skia.Rect.MakeXYWH(x + w * 0.55, y, w * 0.45, h), fill(hexc("#ffd98a"), 0.18))  # telly glow

    up_l = (hx + 90, hy + 110, 230, 230)
    up_r = (hx + 450, hy + 110, 230, 230)
    _window(c, *up_l, inner=flag)
    _window(c, *up_r, inner=sheet)
    _window(c, hx + 90, hy + 470, 260, 230)
    # front door
    _rect(c, hx + 520, hy + 470, 150, 430, hexc("#e4e2da"), INK, 4)
    _rect(c, hx + 545, hy + 500, 100, 120, hexc("#6f7f8a"), INK, 2)
    c.drawCircle(hx + 640, hy + 700, 7, fill(hexc("#c9a64a")))
    _rect(c, hx + 505, hy + 455, 180, 18, hexc("#d0ccc2"), INK, 3)
    # satellite dish hanging off
    c.save()
    c.rotate(38, hx + 700, hy + 70)
    c.drawOval(skia.Rect.MakeXYWH(hx + 640, hy + 20, 120, 120), fill(hexc("#cfd0cf")))
    c.drawOval(skia.Rect.MakeXYWH(hx + 640, hy + 20, 120, 120), stroke(INK, 4))
    c.drawLine(hx + 700, hy + 80, hx + 760, hy + 30, stroke(INK, 5))
    c.restore()
    c.drawLine(hx + 700, hy + 60, hx + 720, hy + 340, stroke(hexc("#222"), 3))  # dangling cable
    # front garden + fence
    gy = hy + hh
    _rect(c, 0, gy - 40, W, 300, hexc("#5f6a52"))
    _speckle(c, 0, gy - 40, W, 300, 900, [hexc("#4f5a44"), hexc("#6e7a5c")], 1, 3, seed=6)
    # soggy sofa
    sx, sy = 90, gy + 20
    _rrect(c, sx, sy, 330, 150, 20, hexc("#6d5f4a"), INK, 4)
    _rrect(c, sx - 20, sy - 70, 370, 100, 26, hexc("#7a6a52"), INK, 4)
    _rrect(c, sx - 30, sy - 20, 60, 150, 20, hexc("#7a6a52"), INK, 4)
    _rrect(c, sx + 300, sy - 20, 60, 150, 20, hexc("#7a6a52"), INK, 4)
    for k in range(5):
        c.drawOval(skia.Rect.MakeXYWH(sx + 30 + k * 60, sy + 20 + (k % 2) * 30, 50, 22), fill(hexc("#4a4033"), 0.6))
    # wheelie bins
    _wheelie_bin(c, 640, gy - 60, "#3c3f44", 1.0, seed=1)
    _wheelie_bin(c, 790, gy - 50, "#2f5b3a", 0.95, seed=2)
    _rect(c, 700, gy + 150, 140, 60, hexc("#1d1e21"))  # bin bag on the floor
    # low brick wall + pavement
    _rect(c, 0, gy + 230, W, 70, hexc("#7c5d4e"), INK, 4)
    for xx in range(0, W, 60):
        c.drawLine(xx, gy + 230, xx, gy + 300, stroke(hexc("#5d4438"), 2))
    _rect(c, 0, gy + 300, W, H - gy - 300, hexc("#7a7f84"))
    _puddles(c, 0, gy + 380, W, 6, seed=3)
    return {"push_target": (up_r[0] + up_r[2] / 2, up_r[1] + up_r[3] / 2)}


def bedroom(c, W=1080, H=1920):
    _rect(c, 0, 0, W, H, hexc("#b7ad94"))
    for x in range(0, W, 54):  # tired striped wallpaper
        _rect(c, x, 0, 22, 1250, hexc("#a99f86"))
    _rect(c, 0, 0, W, 120, hexc("#d8d2c4"))  # ceiling strip
    # damp patch spreading from the ceiling corner
    r = random.Random(2)
    for k in range(40):
        c.drawCircle(150 + r.gauss(0, 70), 120 + abs(r.gauss(0, 60)), r.uniform(20, 60), fill(hexc("#7d7a52"), 0.16))
    for k in range(12):
        c.drawCircle(150 + r.gauss(0, 50), 130 + abs(r.gauss(0, 40)), r.uniform(4, 12), fill(hexc("#3d4a2f"), 0.4))
    # window with rain (rain drawn live)
    win = (640, 300, 340, 420)
    _window(c, *win, glass="#53626d")
    # skirting + carpet
    _rect(c, 0, 1250, W, 30, hexc("#e6e1d6"), INK, 3)
    _rect(c, 0, 1280, W, H - 1280, hexc("#6e5b52"))
    _speckle(c, 0, 1280, W, H - 1280, 1800, [hexc("#5f4e46"), hexc("#7b675d")], 1, 3, seed=8)
    c.drawOval(skia.Rect.MakeXYWH(600, 1700, 260, 90), fill(hexc("#4f4038"), 0.5))  # stain
    # chest of drawers + telly
    _rect(c, 40, 980, 300, 270, hexc("#8b6a4c"), INK, 4)
    for k in range(3):
        _rect(c, 60, 1000 + k * 82, 260, 66, hexc("#9a7856"), INK, 3)
        c.drawCircle(190, 1033 + k * 82, 7, fill(INK))
    _rect(c, 70, 790, 240, 180, hexc("#1b1c1f"), INK, 4)
    _rect(c, 85, 805, 210, 150, hexc("#3a4a5c"))
    _rect(c, 160, 970, 80, 14, hexc("#1b1c1f"))
    # mattress on the floor
    _rrect(c, 90, 1330, 720, 120, 30, hexc("#d9d3c3"), INK, 4)
    for x in range(140, 800, 80):
        c.drawCircle(x, 1390, 5, fill(hexc("#b2aa98")))
    c.drawOval(skia.Rect.MakeXYWH(420, 1360, 140, 50), fill(hexc("#b89f62"), 0.35))
    # bedside crate with cans + ashtray
    _rect(c, 840, 1250, 170, 150, hexc("#2f5b8a"), INK, 4)
    for k in range(3):
        _rect(c, 855 + k * 52, 1270, 40, 110, hexc("#264a70"))
    for k, x in enumerate((850, 895, 960)):
        _rect(c, x, 1170 + (k == 1) * 20, 36, 80 - (k == 1) * 20, hexc(["#c8102e", "#d9d9d9", "#1f6f3f"][k]), INK, 3)
    c.drawOval(skia.Rect.MakeXYWH(930, 1225, 80, 28), fill(hexc("#9aa3a8")))
    c.drawOval(skia.Rect.MakeXYWH(930, 1225, 80, 28), stroke(INK, 3))
    for k in range(6):
        c.drawLine(945 + k * 9, 1232, 955 + k * 8, 1220 - (k % 3) * 4, stroke(hexc("#f0ede5"), 5))
    # crisp packet + can on floor
    _rect(c, 300, 1700, 46, 26, hexc("#b9c2c9"), INK, 2)
    return {"window": win, "tv": (85, 805, 210, 150), "floor": 1600, "mattress_top": 1340}


def living_room(c, W=1080, H=1920):
    _rect(c, 0, 0, W, H, hexc("#a4a58e"))
    r = random.Random(5)
    for y in range(80, 1300, 90):  # dated diamond wallpaper
        for x in range(-40, W + 40, 90):
            ox = 45 if (y // 90) % 2 else 0
            c.drawPath(poly([(x + ox, y - 18), (x + ox + 14, y), (x + ox, y + 18), (x + ox - 14, y)]), fill(hexc("#95967f")))
    _rect(c, 0, 0, W, 70, hexc("#d8d4c6"))
    # window w/ net curtain behind sofa
    win = (180, 380, 420, 380)

    def nets(c, x, y, w, h):
        _rect(c, x, y, w, h, hexc("#8b969c"))
        for k in range(0, int(w), 14):
            c.drawLine(x + k, y, x + k + 4, y + h, stroke(hexc("#eeeeea"), 3, 0.5))
    _window(c, *win, inner=nets)
    # radiator
    _rect(c, 680, 1080, 220, 140, hexc("#e4e2dc"), INK, 3)
    for k in range(9):
        c.drawLine(700 + k * 22, 1090, 700 + k * 22, 1210, stroke(hexc("#c5c3bc"), 5))
    # wonky picture frame
    c.save()
    c.rotate(-7, 790, 470)
    _rect(c, 700, 400, 180, 140, hexc("#8b6a4c"), INK, 4)
    _rect(c, 718, 418, 144, 104, hexc("#7f9aa8"))
    c.drawCircle(790, 480, 20, fill(hexc("#d9c9a3")))
    c.restore()
    # floor
    _rect(c, 0, 1300, W, 22, hexc("#e2ded2"), INK, 3)
    _rect(c, 0, 1322, W, H - 1322, hexc("#5a6a55"))
    _speckle(c, 0, 1322, W, H - 1322, 1500, [hexc("#4b5a47"), hexc("#677862")], 1, 3, seed=7)
    # sofa
    sx, sy = 40, 1010
    _rrect(c, sx, sy, 600, 210, 30, hexc("#6b4b45"), INK, 4)          # back
    _rrect(c, sx + 20, sy + 170, 560, 150, 24, hexc("#7b5751"), INK, 4)  # seat
    _rrect(c, sx - 20, sy + 120, 80, 210, 26, hexc("#6b4b45"), INK, 4)
    _rrect(c, sx + 560, sy + 120, 80, 210, 26, hexc("#6b4b45"), INK, 4)
    c.drawOval(skia.Rect.MakeXYWH(sx + 340, sy + 200, 100, 40), fill(hexc("#4b3330"), 0.6))  # burn mark
    # coffee table with cans, ashtray, remote
    _rect(c, 180, 1450, 380, 30, hexc("#8a6b4f"), INK, 4)
    _rect(c, 200, 1480, 20, 120, hexc("#8a6b4f"), INK, 3)
    _rect(c, 520, 1480, 20, 120, hexc("#8a6b4f"), INK, 3)
    for k, x in enumerate((210, 260, 470)):
        _rect(c, x, 1385, 36, 66, hexc(["#c8102e", "#e3b520", "#c8102e"][k]), INK, 3)
    c.drawOval(skia.Rect.MakeXYWH(330, 1425, 90, 30), fill(hexc("#9aa3a8")))
    c.drawOval(skia.Rect.MakeXYWH(330, 1425, 90, 30), stroke(INK, 3))
    # telly on a stand (screen drawn live)
    tv = (740, 830, 300, 210)
    _rect(c, 720, 1050, 340, 250, hexc("#3a3a3e"), INK, 4)
    _rect(c, tv[0] - 14, tv[1] - 14, tv[2] + 28, tv[3] + 28, hexc("#111214"), INK, 4)
    # crisp packets on floor
    for x, y, rot in ((120, 1650, 20), (620, 1760, -30), (880, 1580, 10)):
        c.save()
        c.rotate(rot, x, y)
        _rect(c, x, y, 60, 36, hexc(r.choice(["#c4252f", "#2c62b0", "#2e8b3e"])), INK, 2)
        c.restore()
    return {"tv": tv, "floor": 1700, "sofa_seat": (sx + 200, sy + 175)}


def street(c, W=3800, H=1920):
    _sky(c, W, H)
    _terrace_row(c, -40, 1300, W + 100, 21, 520)
    # front walls / hedges segments
    _rect(c, 0, 1300, W, 60, hexc("#6f6e66"))
    # hedge with a shopping trolley in it
    hx = 760
    r = random.Random(4)
    for k in range(70):
        c.drawCircle(hx + r.uniform(0, 420), 1250 + r.uniform(0, 100), r.uniform(25, 50), fill(hexc(r.choice(["#3e5a36", "#4b6b40", "#35502f"]))))
    tx, ty = hx + 140, 1160
    c.save()
    c.rotate(-18, tx, ty)
    for k in range(7):
        c.drawLine(tx + k * 30, ty, tx + k * 30 - 20, ty + 140, stroke(hexc("#b9bec2"), 4))
    for k in range(5):
        c.drawLine(tx - 3 * k, ty + k * 35, tx + 200 - 3 * k, ty + k * 35, stroke(hexc("#b9bec2"), 4))
    c.drawLine(tx + 200, ty, tx + 250, ty - 40, stroke(hexc("#c22"), 9))
    c.drawCircle(tx + 10, ty + 170, 14, stroke(hexc("#888"), 6))
    c.restore()
    # low wall the pasty lad sits on
    wx = 1650
    _rect(c, wx, 1220, 560, 140, hexc("#7d5e4f"), INK, 4)
    for yy in range(1220, 1360, 35):
        for xx in range(wx + ((yy // 35) % 2) * 35, wx + 560, 70):
            c.drawLine(xx, yy, xx, yy + 35, stroke(hexc("#5d4438"), 2))
        c.drawLine(wx, yy, wx + 560, yy, stroke(hexc("#5d4438"), 2))
    _rect(c, wx - 10, 1205, 580, 22, hexc("#9a9a93"), INK, 3)
    # lamp posts
    for lx in (300, 1450, 2600, 3500):
        _rect(c, lx, 700, 18, 660, hexc("#3b3e44"), INK, 2)
        c.drawPath(poly([(lx - 10, 700), (lx + 110, 690), (lx + 110, 712), (lx - 10, 722)]), fill(hexc("#3b3e44")))
        c.drawOval(skia.Rect.MakeXYWH(lx + 70, 708, 60, 22), fill(hexc("#f4e3a1"), 0.9))
    # bins + a mattress against a wall, for flavour
    _wheelie_bin(c, 2450, 1180, "#3c3f44", 0.9, seed=5)
    c.save()
    c.rotate(-8, 3000, 1100)
    _rrect(c, 2950, 1000, 120, 330, 20, hexc("#d9d3c3"), INK, 4)
    c.drawOval(skia.Rect.MakeXYWH(2975, 1150, 70, 60), fill(hexc("#b89f62"), 0.5))
    c.restore()
    # pavement + kerb + road
    _rect(c, 0, 1360, W, 280, hexc("#8c9095"))
    for x in range(0, W, 150):
        c.drawLine(x, 1360, x - 40, 1640, stroke(hexc("#7a7e83"), 3))
    c.drawLine(0, 1500, W, 1500, stroke(hexc("#7a7e83"), 3))
    _rect(c, 0, 1640, W, 26, hexc("#b8b8b2"), INK, 3)
    _rect(c, 0, 1666, W, H - 1666, hexc("#4c4f53"))
    for x in range(0, W, 260):
        _rect(c, x, 1820, 130, 14, hexc("#d9d6c6"), alpha=0.7)
    _puddles(c, 0, 1460, W, 18, seed=8)
    _puddles(c, 0, 1760, W, 12, seed=9, color="#5d6872")
    return {"ground": 1520, "trolley_x": hx + 200, "wall_x": wx + 280, "wall_top": 1210}


def offy(c, W=1080, H=1920):
    _rect(c, 0, 0, W, H, hexc("#c9c3ad"))
    _rect(c, 0, 0, W, 90, hexc("#e8e6df"))
    for x in range(60, W, 240):  # strip lights
        _rect(c, x, 96, 160, 18, hexc("#f7f6ef"), INK, 2)
    # door with bell (left)
    _rect(c, 20, 640, 230, 900, hexc("#4b5560"), INK, 5)
    _rect(c, 45, 670, 180, 520, hexc("#6f7e8a"), INK, 3)
    for k in range(3):  # stickers on the door
        _rect(c, 60 + k * 50, 1210 + k * 12, 44, 30, hexc(["#e23a3a", "#ffcc00", "#2c7be5"][k]), INK, 2)
    _text(c, "PUSH", 135, 760, 34, hexc("#e9e7e2"), center=True)
    _rect(c, 238, 610, 50, 12, hexc("#7a6a3a"))
    c.drawPath(poly([(262, 622), (240, 662), (284, 662)]), fill(hexc("#c9a64a")))
    c.drawPath(poly([(262, 622), (240, 662), (284, 662)]), stroke(INK, 3))
    # crisp shelves (middle-left)
    r = random.Random(12)
    sx = 300
    for k in range(4):
        y = 560 + k * 170
        _rect(c, sx, y + 130, 300, 16, hexc("#9aa0a6"), INK, 3)
        x = sx + 6
        while x < sx + 280:
            w = r.uniform(38, 52)
            col = hexc(r.choice(["#d6232e", "#2e5fb5", "#2c9a45", "#f2b711", "#7d3fa8", "#ef7b10"]))
            c.drawPath(poly([(x, y + 130), (x + w, y + 130), (x + w - 4, y + 40), (x + 4, y + 40)]), fill(col))
            c.drawPath(poly([(x, y + 130), (x + w, y + 130), (x + w - 4, y + 40), (x + 4, y + 40)]), stroke(INK, 2))
            c.drawCircle(x + w / 2, y + 85, 9, fill(hexc("#f5d27a")))
            x += w + 3
    # fag gantry behind the counter (right)
    gx, gy, gw, gh = 640, 420, 420, 560
    _rect(c, gx, gy, gw, gh, hexc("#2b2d31"), INK, 5)
    for row in range(8):
        for col in range(7):
            px, py = gx + 14 + col * 58, gy + 16 + row * 66
            _rect(c, px, py, 50, 56, hexc(r.choice(["#eae7df", "#e2dfd6", "#e8e4d8"])), INK, 2)
            _rect(c, px, py, 50, 16, hexc(r.choice(["#2a3f7a", "#b01e2e", "#1f6f3f", "#444", "#c9a64a"])))
            _rect(c, px + 4, py + 30, 42, 20, hexc("#1b1b1b"))
    _rect(c, gx - 10, gy - 70, gw + 20, 60, hexc("#c4252f"), INK, 4)
    _text(c, "TOBACCO", gx + gw / 2, gy - 25, 40, hexc("#ffffff"), center=True)
    # lottery sign + energy drink fridge glow at far right
    _rect(c, 640, 1010, 200, 110, hexc("#f2c500"), INK, 4)
    _text(c, "LOTTO", 740, 1080, 44, hexc("#2b2b2b"), center=True)
    # lino floor
    _rect(c, 0, 1540, W, H - 1540, hexc("#8b8a7f"))
    for y in range(1540, H, 70):
        for x in range(((y - 1540) // 70 % 2) * 70, W, 140):
            _rect(c, x, y, 70, 70, hexc("#9d9c90"))
    c.drawLine(0, 1540, W, 1540, stroke(INK, 4))
    return {"floor": 1640, "counter": (560, 1180, W - 560, 1640 - 1180), "door_x": 135}


def offy_counter(c, W=1080):
    """Foreground counter (drawn over Tariq, behind Kai)."""
    x, y, w, h = 560, 1180, W - 560, 460
    _rect(c, x, y + 26, w, h - 26, hexc("#7a6250"), INK, 5)
    for k in range(4):
        _rect(c, x + 30 + k * 125, y + 80, 100, 300, hexc("#866c58"), INK, 3)
    _rect(c, x - 20, y, w + 20, 30, hexc("#b9b4a8"), INK, 4)
    # scratch cards display on top
    _rect(c, x + 300, y - 120, 150, 120, hexc("#3a8dd6"), INK, 3)
    for k in range(4):
        _rect(c, x + 310 + k * 35, y - 105, 28, 90, hexc(["#ffcc00", "#e23a3a", "#2c9a45", "#ff7a00"][k]), INK, 2)
    # charity box + chewing gum
    _rect(c, x + 470, y - 60, 40, 60, hexc("#e3e1da"), INK, 2)


def shop_front(c, W=1080, H=1920):
    _sky(c, W, 700)
    # flats above the shop
    _rect(c, 0, 150, W, 650, hexc("#8a7466"), INK, 4)
    for yy in range(160, 800, 22):
        c.drawLine(0, yy, W, yy, stroke(hexc("#6f5d52"), 1.5, 0.5))
    for x in (80, 420, 760):
        _window(c, x, 280, 220, 260, glass="#56636c")
    # sign
    _rect(c, 0, 800, W, 170, hexc("#1e3f7a"), INK, 5)
    _text(c, "TARIQ'S", W / 2, 875, 76, hexc("#ffd83d"), center=True)
    _text(c, "FOOD & WINE  •  OFF LICENCE", W / 2, 940, 44, hexc("#ffffff"), center=True)
    # shop window full of posters + half-up shutter
    _rect(c, 0, 970, W, 520, hexc("#4c5660"), INK, 4)
    _rect(c, 0, 970, W, 160, hexc("#9aa0a4"))
    for yy in range(970, 1130, 16):
        c.drawLine(0, yy, W, yy, stroke(hexc("#7d8287"), 3))
    c.drawPath(poly([(30, 1000), (300, 1060), (90, 1110)], close=False), stroke(hexc("#1b1b1b"), 6))  # graffiti tag
    r = random.Random(3)
    for k, (txt, col) in enumerate((("CHEAP\nBOOZE", "#ffd83d"), ("PAYPOINT", "#2c7be5"), ("LOTTO", "#f2c500"),
                                    ("2 FOR\n£3", "#e23a3a"), ("ICE", "#9fd0ff"))):
        px = 30 + k * 210
        py = 1180 + (k % 2) * 60
        _rect(c, px, py, 180, 150, hexc(col), INK, 3)
        for j, line in enumerate(txt.split("\n")):
            _text(c, line, px + 90, py + 65 + j * 46, 38, hexc("#151517"), center=True)
    # door (Kai comes out of here)
    _rect(c, 400, 1130, 280, 360, hexc("#55606b"), INK, 5)
    _rect(c, 420, 1150, 240, 230, hexc("#7c8b96"), INK, 3)
    # pavement, kerb, road
    _rect(c, 0, 1490, W, 160, hexc("#8c9095"))
    _rect(c, 0, 1650, W, 24, hexc("#b8b8b2"), INK, 3)
    _rect(c, 0, 1674, W, H - 1674, hexc("#46494d"))
    for x in range(0, W, 260):
        _rect(c, x, 1810, 130, 14, hexc("#d9d6c6"), alpha=0.7)
    _puddles(c, 0, 1560, W, 5, seed=2)
    _puddles(c, 0, 1760, W, 6, seed=5, color="#5d6872")
    return {"ground": 1580, "door": (540, 1490), "road_y": 1830}


def end_card(c, W=1080, H=1920):
    _vgrad(c, 0, 0, W, H, hexc("#2b3036"), hexc("#14161a"))
    return {}


PAINTERS = {"estate": (estate, (1080, 1920)), "bedroom": (bedroom, (1080, 1920)),
            "living_room": (living_room, (1080, 1920)), "street": (street, (3800, 1920)),
            "offy": (offy, (1080, 1920)), "shop_front": (shop_front, (1080, 1920)),
            "end_card": (end_card, (1080, 1920))}


def render(name: str, scale: float = 2.0) -> tuple[skia.Image, dict, tuple[int, int]]:
    painter, (w, h) = PAINTERS[name]
    surf = skia.Surface(int(w * scale), int(h * scale))
    c = surf.getCanvas()
    c.scale(scale, scale)
    info = painter(c, w, h)
    return surf.makeImageSnapshot(), info, (w, h)
