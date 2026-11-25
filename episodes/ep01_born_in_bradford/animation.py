"""Episode 1 choreography: "Born in Bradford".

Each scene is a class with:
  camera(ctx)  set ctx.cam / ctx.rain for this frame
  draw(ctx)    draw characters + foreground in world coordinates
  screen(ctx)  (optional) draw in screen space on top of everything
All timing is keyed to beat ids from script.yaml, so when the real voices make
lines longer or shorter, the animation follows automatically.
"""
from __future__ import annotations

import math
import random

import skia

from stickman.draw import (ADULT, BABY, Face, Look, Pose, back_out, blink_at, clamp, coin, coins, draw_stickman, ease,
                           ease_in, ease_out, fag, fag_pack, fill, hexc, keyframes, lerp, mix, pasty, phone, poly,
                           stroke, waddle, walk)

INK = hexc("#151517")
KAI_NAPPY = Look(nappy=True, tuft=True)
KAI_VEST = Look(nappy=True, vest=True, tuft=True)
MAM = Look(gown="#e7a1b6", hair="bun", hair_color="#5a4632")
MIDWIFE = Look(scrubs="#5f8fb8", hair="short", hair_color="#2d2320")
TARIQ = Look(readers_on_head=True, hair="short", hair_color="#1d1d1d")
PASTY_LAD = Look(tracksuit="#4a4d55", socks_over=True, hair="short", hair_color="#3a2a1f")
LADS = [Look(tracksuit="#2c2d33", socks_over=True, bucket_hat="#3b3d44"),
        Look(tracksuit="#8b8e95", socks_over=True, bucket_hat="#2a2b30"),
        Look(tracksuit="#3f4148", socks_over=True, bucket_hat="#9a9da3")]

STEP_SQUEAK_GAIN = 0.55


def kai(c, hip, s, pose=Pose(), face=Face(), look=KAI_NAPPY, facing=1, rot=0.0):
    if rot:
        c.save()
        c.rotate(rot, *hip)
    j = draw_stickman(c, hip, BABY, pose, face, look, facing, s)
    if rot:
        c.restore()
    return j


def kai_hip_y(ground, s, bob=0.0):
    return ground - BABY.leg * s * 0.97 - bob * 6 * s


def seat_pose(**kw):
    p = dict(lean=-4, arm_b=(20, 30), arm_f=(30, 40), leg_b=(88, -6), leg_f=(84, 4))
    p.update(kw)
    return Pose(**p)


def tv_screen(c, rect, t):
    x, y, w, h = rect
    flick = 0.85 + 0.15 * math.sin(t * 23) * math.sin(t * 7.3)
    c.drawRect(skia.Rect.MakeXYWH(x, y, w, h), fill(mix("#2d4a6a", "#7fa3c4", flick * 0.6)))
    c.drawRect(skia.Rect.MakeXYWH(x, y + h * 0.72, w, h * 0.16), fill(hexc("#e8c547")))
    # two tiny guests having a row
    for k, px in enumerate((0.3, 0.68)):
        jump = abs(math.sin(t * (5 + k * 2))) * 6 if int(t * 1.3) % 2 == k else 0
        hx, hy = x + w * px, y + h * 0.55 - jump
        c.drawLine(hx, hy, hx, hy - h * 0.22, stroke(hexc("#f5f5f0"), 4))
        c.drawCircle(hx, hy - h * 0.3, h * 0.08, fill(hexc("#f5f5f0")))
        c.drawLine(hx, hy - h * 0.16, hx + (12 if k == 0 else -12), hy - h * 0.25 - jump, stroke(hexc("#f5f5f0"), 4))


def window_rain(c, rect, t):
    x, y, w, h = rect
    c.save()
    c.clipRect(skia.Rect.MakeXYWH(x, y, w, h))
    r = random.Random(4)
    for k in range(26):
        px = x + r.random() * w
        spd = r.uniform(40, 140)
        py = y + ((r.random() * h + t * spd) % (h + 60)) - 30
        c.drawLine(px, py, px + 2, py + r.uniform(14, 40), stroke(hexc("#c9d3da"), 3, 0.55))
        c.drawCircle(px + 1, py + 40, 3, fill(hexc("#c9d3da"), 0.6))
    c.restore()


# ─────────────────────────────────────────────────────────────
class ColdOpen:
    def camera(self, x):
        tx, ty = x.info["push_target"]
        k = ease(clamp((x.t - 0.6) / (x.dur - 0.6)))
        x.cam.cx = lerp(540, tx, k)
        x.cam.cy = lerp(1000, ty + 60, k)
        x.cam.zoom = lerp(1.0, 2.6, k ** 1.4)
        x.rain = 1.0

    def draw(self, x):
        tx, ty = x.info["push_target"]
        # telly glow flicker behind the bedsheet
        a = 0.12 + 0.1 * (0.5 + 0.5 * math.sin(x.t * 17) * math.sin(x.t * 5))
        x.c.drawRect(skia.Rect.MakeXYWH(tx - 115, ty - 115, 230, 230), fill(hexc("#9fc4ff"), a))


# ─────────────────────────────────────────────────────────────
class Birth:
    MAM_HIP = (275, 1392)
    MW_HIP = (660, 1425)
    SHEET_OUT = (470, 1430)
    SIT = (560, 1735)
    UNDER = (455, 1470)

    def mid(self, x):
        return x.m("pop").start

    def kai_state(self, x):
        """-> (hip, rot, pose, face, facing, behind_sheet, visible)"""
        t = x.t
        s_pop, s_sit, s_look = x.m("pop").start, x.m("sit").start, x.m("look").start
        if t < s_pop:
            return None
        bl = blink_at(t, 0.4)
        if t < s_sit:  # shoot out + slide across the carpet
            k = ease_out((t - s_pop) / (s_sit - s_pop))
            hx = lerp(self.SHEET_OUT[0], self.SIT[0], k)
            hy = lerp(self.SHEET_OUT[1], self.SIT[1], k) - math.sin(k * math.pi) * 120
            rot = lerp(-420, -80, k)
            return (hx, hy), rot, seat_pose(arm_b=(150, 10), arm_f=(160, 10)), Face(eyes="wide", mouth="o"), 1, False
        if t < s_look:  # sits up, blinks
            k = back_out((t - s_sit) / 0.5)
            blink = 1.0 if 0.35 < t - s_sit < 0.5 or 0.62 < t - s_sit < 0.74 else 0.0
            return self.SIT, lerp(-80, 0, k), seat_pose(), Face(eyes="open", blink=blink), 1, False
        turn = x.m("turn")
        if t < turn.start:
            # look around: damp patch, ashtray, rainy window, then dead stare
            lk = x.m("look")
            looks = [(lk.start, (0, 0)), (lk.start + 0.4, (-1, -1)), (lk.start + 1.2, (-1, -1)), (lk.start + 1.5, (1, 0.2)),
                     (lk.start + 2.2, (1, 0.2)), (lk.start + 2.5, (0.8, -1)), (lk.end - 0.2, (0.8, -1)), (lk.end + 0.2, (0, 0))]
            look = keyframes(t, looks)
            eyes = "open" if t < x.m("hold").start else "tired"
            brows = 0.0 if t < x.m("hold").start else -0.4
            mouth = "flat" if t < x.m("hold").start else "frown"
            return self.SIT, 0, seat_pose(), Face(eyes=eyes, look=look, blink=bl, brows=brows, mouth=mouth, talk=x.talk("kai")), 1, False
        sb = x.m("sendback")
        lift = x.m("lift")
        if t < lift.start:
            # gets up and scrabbles back under the sheet
            k = ease((t - turn.start) / max(0.1, (sb.start + sb.dur * 0.45) - turn.start))
            hx = lerp(self.SIT[0], self.UNDER[0], k)
            hy = lerp(self.SIT[1], self.UNDER[1], k)
            if k < 0.15:
                pose = seat_pose()
            else:
                pose, sway, bob = waddle(t * 3.2, 1.3)
                hy -= bob * 8
            under = k > 0.97
            if under:
                pose, _, _ = waddle(t * 6, 1.4)  # little legs scrabbling
                pose.lean = 70
            return (hx, hy), 0, pose, Face(eyes="glare", brows=0.6, mouth="grimace", talk=x.talk("kai")), -1, under
        return None  # handled by the midwife lift

    def camera(self, x):
        t = x.t
        wide = (420, 1400, 1.55)
        keys = [(0, wide), (self.mid(x) + 0.2, wide), (x.m("sit").start + 0.3, (540, 1560, 1.6)),
                (x.m("look").start + 0.2, (540, 1250, 1.05)), (x.m("look").end - 0.2, (540, 1250, 1.05)),
                (x.m("hold").start + 0.3, (560, 1655, 2.6)), (x.m("turn").start, (560, 1655, 2.6)),
                (x.m("turn").start + 0.6, (500, 1500, 1.7)), (x.m("lift").start, (500, 1500, 1.7)),
                (x.m("lift").start + 0.8, (640, 1290, 2.0)), (x.dur, (640, 1280, 2.15))]
        cx, cy, z = keyframes(t, keys)
        x.cam.cx, x.cam.cy, x.cam.zoom = cx, cy, z
        x.cam.shake = 6 * max(0, 1 - abs(t - self.mid(x)) / 0.25)

    def mam(self, x):
        t = x.t
        nr = x.m("norefunds")
        lit = t >= nr.start + 0.35
        lighting = nr.start - 0.2 <= t < nr.start + 0.9
        arm_f = (150, 70) if lighting else (100, 60) if lit else (60, 40)
        face = Face(eyes="tired", look=(-1, -0.3), blink=blink_at(t, 1.1), mouth="flat", talk=x.talk("mam"))
        if t < self.mid(x) + 0.1:  # pushing
            strain = 0.5 + 0.5 * math.sin(t * 3)
            face = Face(eyes="squint", brows=1.0, mouth="grimace", talk=0.4 * strain if t < x.m("push_line").start else 0)
            arm_f = (40, 20)
        pose = Pose(lean=-48, arm_b=(-40, 10), arm_f=arm_f, leg_b=(140, -110), leg_f=(150, -118))
        j = draw_stickman(x.c, self.MAM_HIP, ADULT, pose, face, MAM, 1, 1.15)
        if lighting and t >= nr.start:
            fl = 0.7 + 0.3 * math.sin(t * 40)
            hx, hy = j["hand_f"]
            x.c.drawOval(skia.Rect.MakeXYWH(hx + 6, hy - 30 * fl, 12, 26 * fl), fill(hexc("#ffb23e")))
        if lit or lighting:
            fag(x.c, j["hand_f"], t, 1.1, angle=-30, lit=lit)
        return j

    def sheet(self, x):
        p = skia.Path()
        p.moveTo(200, 1400)
        p.cubicTo(250, 1300, 320, 1270, 380, 1300)
        p.cubicTo(450, 1330, 520, 1380, 560, 1450)
        p.lineTo(200, 1455)
        p.close()
        x.c.drawPath(p, fill(hexc("#cfdbe3")))
        x.c.drawPath(p, stroke(INK, 5))
        for k in range(3):
            x.c.drawLine(300 + k * 60, 1320 + k * 15, 330 + k * 70, 1440, stroke(hexc("#a9bac6"), 3))

    def midwife(self, x):
        t = x.t
        lift = x.m("lift")
        if t < lift.start:
            reach = 0.5 + 0.5 * math.sin(t * 2) if t < self.mid(x) else 0.3
            arm_f = (75 + 10 * reach, 20)
            arm_b = (60, 30)
            face = Face(eyes="open", mouth="smile", blink=blink_at(t, 2.2), talk=x.talk("midwife"))
        else:
            k1 = ease((t - lift.start) / 0.35)
            k2 = ease((t - lift.start - 0.35) / 0.65)
            arm_f = (lerp(75, 40, k1) + lerp(0, 105, k2), lerp(20, 0, k2))
            arm_b = (lerp(60, 120, k2), lerp(30, 20, k2))
            face = Face(eyes="open", mouth="flat", look=(-0.6, -0.8), blink=blink_at(t, 2.2))
        pose = Pose(lean=14, arm_b=arm_b, arm_f=arm_f, leg_b=(-5, -88), leg_f=(5, -95))
        return draw_stickman(x.c, self.MW_HIP, ADULT, pose, face, MIDWIFE, -1, 1.15)

    def draw(self, x):
        c, t = x.c, x.t
        tv_screen(c, x.info["tv"], t)
        window_rain(c, x.info["window"], t)
        self.mam(x)
        st = self.kai_state(x)
        if st and st[5]:  # under the sheet: draw Kai first
            hip, rot, pose, face, facing, _ = st
            kai(c, hip, 1.3, pose, face, KAI_NAPPY, facing, rot)
        self.sheet(x)
        if st and not st[5]:
            hip, rot, pose, face, facing, _ = st
            kai(c, hip, 1.3, pose, face, KAI_NAPPY, facing, rot)
        j = self.midwife(x)
        lift = x.m("lift")
        if t >= lift.start:
            hand = j["hand_f"]
            k = ease((t - lift.start) / 0.35)
            hip = (lerp(self.UNDER[0], hand[0], k), lerp(self.UNDER[1], hand[1] + 26, k))
            sw = math.sin((t - lift.start) * 2.4) * 6 * clamp(t - lift.start - 0.9)
            face = Face(eyes="glare", brows=0.9, mouth="frown", look=(0.3, 0), blink=blink_at(t, 0.3),
                        talk=x.talk("kai"))
            pose = Pose(arms_folded=True, leg_b=(8, 4), leg_f=(-6, 6))
            kai(c, hip, 1.3, pose, face, KAI_NAPPY, 1, sw)
            # midwife's fingers pinching the nappy
            c.drawCircle(hand[0], hand[1] + 4, 10, fill(hexc("#fbfbf8")))
            c.drawCircle(hand[0], hand[1] + 4, 10, stroke(INK, 4))


# ─────────────────────────────────────────────────────────────
class Errand:
    MAM_HIP = (330, 1205)
    SEAT = (700, 1600)

    def camera(self, x):
        t = x.t
        wide = (520, 1390, 1.5)
        st = x.m("stare")
        cl = x.m("climb")
        keys = [(0, wide), (st.start, wide), (st.start + 0.12, (690, 1395, 2.7)), (st.end, (690, 1395, 2.8)),
                (cl.start + 0.25, wide), (x.dur, (540, 1420, 1.6))]
        cx, cy, z = keyframes(t, keys) if t >= st.start else wide
        x.cam.cx, x.cam.cy, x.cam.zoom = cx, cy, z

    def kai_pos(self, x):
        cl = x.m("climb")
        k = clamp((x.t - cl.start) / cl.dur)
        if k <= 0:
            return self.SEAT, "seat"
        if k < 0.35:
            return (self.SEAT[0], lerp(self.SEAT[1], 1640, ease(k / 0.35)) - math.sin(k / 0.35 * math.pi) * 40), "hop"
        kk = ease((k - 0.35) / 0.65)
        return (lerp(self.SEAT[0] - 20, 560, kk), 1640), "walk"

    def draw(self, x):
        c, t = x.c, x.t
        tv_screen(c, x.info["tv"], t)
        # Mam on the sofa
        gs = x.m("goshop")
        holding = gs.start <= t < x.m("climb").start + x.m("climb").dur * 0.8
        kick = x.m("card").start + 1.7
        kk = clamp(1 - abs(t - kick) / 0.25)
        arm_f = (lerp(30, 80, ease((t - gs.start) / 0.4)), lerp(40, 0, ease((t - gs.start) / 0.4))) if holding else (30, 50)
        pose = Pose(lean=-10, arm_b=(-20, 40), arm_f=arm_f, leg_b=(92, -84), leg_f=(84 + 20 * kk, -84 + 70 * kk))
        face = Face(eyes="tired", look=(1, -0.3), blink=blink_at(t, 0.7), talk=x.talk("mam"),
                    mouth="flat")
        j = draw_stickman(c, self.MAM_HIP, ADULT, pose, face, MAM, 1, 1.1)
        fag(c, j["hand_b"], t, 1.0, angle=-60)
        if holding:
            coins(c, (j["hand_f"][0] + 8, j["hand_f"][1]), 5, 1.2, seed=3)
        # crisp packet she kicks across the floor
        pk = clamp((t - kick) / 0.9)
        px, py = lerp(470, 1050, ease_out(pk)), 1650 - math.sin(pk * math.pi) * 160
        c.save()
        c.rotate(pk * 540, px, py)
        c.drawRect(skia.Rect.MakeXYWH(px - 30, py - 18, 60, 36), fill(hexc("#2c62b0")))
        c.drawRect(skia.Rect.MakeXYWH(px - 30, py - 18, 60, 36), stroke(INK, 3))
        c.restore()
        # car seat + Kai
        self.car_seat_back(c)
        pos, mode = self.kai_pos(x)
        talk = x.talk("kai")
        bl = blink_at(t, 0.2)
        st = x.m("stare")
        if st.start <= t < st.end:
            face = Face(eyes="tired", look=(0, 0), brows=-0.2, mouth="flat", blink=0)
        else:
            face = Face(eyes="tired", look=(-1, -0.4), brows=0.4, mouth="frown", blink=bl, talk=talk)
        has_coins = t >= x.m("climb").start + x.m("climb").dur * 0.8
        if mode == "seat":
            kai(c, (pos[0], pos[1] - 40), 1.35, seat_pose(arm_f=(40, 40)), face, KAI_VEST, -1)
        else:
            if mode == "walk" and t < x.m("climb").end:
                pose, sway, bob = waddle(t * 2.8)
            else:
                pose, sway, bob = Pose(), 0, 0
            if has_coins:
                pose.arm_f = (130, 70)
            kai(c, (pos[0], kai_hip_y(pos[1], 1.35, bob)), 1.35, pose, face, KAI_VEST, -1, sway)
            if has_coins:
                coins(c, (pos[0] - 14, pos[1] - 135), 5, 1.1, seed=3)
        self.car_seat_front(c, mode)

    def car_seat_back(self, c):
        x, y = self.SEAT
        p = skia.Path()
        p.moveTo(x - 110, y + 40)
        p.cubicTo(x - 120, y - 120, x + 60, y - 220, x + 120, y - 160)
        p.lineTo(x + 120, y + 40)
        p.close()
        c.drawPath(p, fill(hexc("#55595f")))
        c.drawPath(p, stroke(INK, 5))

    def car_seat_front(self, c, mode):
        x, y = self.SEAT
        c.drawPath(poly([(x - 130, y), (x + 130, y), (x + 110, y + 60), (x - 110, y + 60)]), fill(hexc("#3e4247")))
        c.drawPath(poly([(x - 130, y), (x + 130, y), (x + 110, y + 60), (x - 110, y + 60)]), stroke(INK, 5))
        h = skia.Path()
        h.addArc(skia.Rect.MakeXYWH(x - 140, y - 170, 280, 260), 180, 180)
        c.drawPath(h, stroke(hexc("#2b2e33"), 14))
        if mode == "seat":
            c.drawLine(x - 40, y - 90, x - 10, y - 20, stroke(hexc("#2b2e33"), 7))


# ─────────────────────────────────────────────────────────────
class Waddle:
    X0 = 700
    V = 520.0
    STRIDE = 150.0   # px per waddle cycle (2 squeaks)
    S = 1.65

    def x_at(self, scene, t):
        a = scene.mark("alright_kai").start
        b = scene.mark("alright_lad").end
        slow = max(0.0, min(t, b) - a)
        return self.X0 + self.V * t - self.V * 0.6 * slow

    def phase(self, scene, t):
        return (self.x_at(scene, t) - self.X0) / self.STRIDE

    def camera(self, x):
        kx = self.x_at(x.scene, x.t)
        x.cam.cx = kx + 90
        x.cam.cy = 1390
        x.cam.zoom = 1.9
        x.rain = 0.9

    def draw(self, x):
        c, t = x.c, x.t
        info = x.info
        g = info["ground"]
        # pasty lad on the wall
        lx = self.lad_x(x.scene)
        nod = clamp(1 - abs(t - x.m("alright_lad").start - 0.15) / 0.3)
        chew = 0.25 * abs(math.sin(t * 5)) if not x.speaking("pasty_lad") else 0
        face = Face(eyes="tired", look=(-0.6, 0.2), mouth="flat", talk=max(chew, x.talk("pasty_lad")), blink=blink_at(t, 1.7))
        pose = Pose(lean=-4, head_tilt=-14 * nod, arm_b=(20, 40), arm_f=(40, 110), leg_b=(88, -80), leg_f=(80, -70))
        j = draw_stickman(c, (lx, info["wall_top"] - 6), ADULT, pose, face, PASTY_LAD, -1, 1.05)
        pasty(c, (j["hand_f"][0] - 6, j["hand_f"][1] - 6), 1.0)
        # pigeon bigger than Kai
        px = self.pigeon_x(x.scene)
        self.pigeon(c, px, g + 20, t, self.x_at(x.scene, t))
        # Kai
        kx = self.x_at(x.scene, t)
        pose, sway, bob = waddle(self.phase(x.scene, t), 1.0)
        pose.arm_b = (30, 90)
        pose.arm_f = (40, 100)    # clutching coins to his chest
        dist_lad = kx - lx
        look = (-1 if dist_lad > 40 else 1, 0) if abs(dist_lad) < 380 else (1, 0.1)
        if abs(kx - px) < 330:
            look = (1 if kx < px else -1, -0.8)
        knod = clamp(1 - abs(t - x.m("alright_kai").start - 0.1) / 0.3)
        face = Face(eyes="tired", look=look, mouth="flat", talk=x.talk("kai"), blink=blink_at(t))
        pose.head_tilt = -12 * knod
        j = kai(c, (kx, kai_hip_y(g, self.S, bob)), self.S, pose, face, KAI_VEST, 1, sway)
        coins(c, (j["neck"][0] + 16, j["neck"][1] + 26), 4, 1.0, seed=5)

    def lad_x(self, scene):
        return self.x_at(scene, scene.mark("alright_kai").start) + 150

    def pigeon_x(self, scene):
        return self.x_at(scene, scene.mark("walk2").start + 1.1) + 60

    def pigeon(self, c, x, ground, t, kai_x):
        s = 1.9
        turn = -1 if kai_x < x else 1
        near = abs(kai_x - x) < 300
        peck = 0.0 if near else max(0.0, math.sin(t * 3)) ** 8
        leg = stroke(hexc("#c46a7a"), 5 * s)
        for dx in (-12, 12):
            c.drawLine(x + dx * s, ground - 40 * s, x + dx * s, ground, leg)
            c.drawLine(x + dx * s, ground, x + (dx + 14 * turn) * s, ground, leg)
        c.save()
        c.rotate(-25 * turn + peck * 30 * turn, x, ground - 80 * s)
        tail = poly([(x - 50 * s * turn, ground - 70 * s), (x - 120 * s * turn, ground - 40 * s), (x - 110 * s * turn, ground - 10 * s)])
        c.drawPath(tail, fill(hexc("#4f565f")))
        c.drawPath(tail, stroke(INK, 4))
        body = skia.Rect.MakeXYWH(x - 70 * s, ground - 150 * s, 140 * s, 115 * s)
        c.drawOval(body, fill(hexc("#7d8590")))
        c.drawOval(body, stroke(INK, 5))
        wing = skia.Rect.MakeXYWH(x - 55 * s * (1 if turn > 0 else 0.3), ground - 125 * s, 80 * s, 60 * s)
        c.drawOval(wing, fill(hexc("#69717b")))
        c.drawOval(wing, stroke(INK, 3))
        c.drawLine(x - 20 * s, ground - 108 * s, x + 30 * s, ground - 108 * s, stroke(INK, 3))
        nx, ny = x + 40 * s * turn, ground - 150 * s
        c.drawOval(skia.Rect.MakeXYWH(nx - 34 * s, ny - 30 * s, 68 * s, 70 * s), fill(hexc("#4f7a6a")))   # shiny neck
        c.drawOval(skia.Rect.MakeXYWH(nx - 26 * s, ny - 10 * s, 50 * s, 40 * s), fill(hexc("#7a5a86"), 0.6))
        hx, hy = nx + 14 * s * turn, ny - 55 * s
        c.drawCircle(hx, hy, 30 * s, fill(hexc("#737b86")))
        c.drawCircle(hx, hy, 30 * s, stroke(INK, 5))
        ex = hx + 12 * s * turn
        c.drawCircle(ex, hy - 6 * s, 8 * s, fill(hexc("#e8892c")))
        c.drawCircle(ex + (2 if near else 0) * s * turn, hy - 6 * s, 4 * s, fill(INK))
        c.drawPath(poly([(hx + 26 * s * turn, hy - 2 * s), (hx + 50 * s * turn, hy + 6 * s), (hx + 26 * s * turn, hy + 10 * s)]), fill(hexc("#3b3b3b")))
        c.drawCircle(hx + 26 * s * turn, hy - 2 * s, 5 * s, fill(hexc("#efefef")))
        c.restore()


# ─────────────────────────────────────────────────────────────
class Offy:
    S = 1.6
    TARIQ_HIP = (850, 1235)
    CRATES = (395, 1660)   # x-left, floor
    CRATE_H = 84
    TOP_X = 470

    def stack_top(self):
        return self.CRATES[1] - 3 * self.CRATE_H

    def kai_state(self, scene, t):
        """-> (x, ground_y, walking_phase or None, facing)"""
        floor = 1665
        tw, cl, ex = scene.mark("twenty"), scene.mark("climb"), scene.mark("exit")
        enter_end = tw.end
        if t < enter_end:
            k = clamp(t / enter_end)
            xk = lerp(150, 360, k)
            return xk, floor, (xk - 150) / 120, 1
        if t < cl.end:
            k = clamp((t - cl.start) / cl.dur)
            if t < cl.start:
                return 360, floor, None, 1
            # three hops up the crates
            hop = min(2, int(k * 3))
            kk = (k * 3) - hop
            y0 = floor - hop * self.CRATE_H
            y1 = floor - (hop + 1) * self.CRATE_H
            xk = lerp(360, self.TOP_X, clamp(k * 1.5))
            return xk, lerp(y0, y1, ease(kk)) - math.sin(kk * math.pi) * 40, None, 1
        if t < ex.start:
            return self.TOP_X, self.stack_top(), None, 1
        k = clamp((t - ex.start) / ex.dur)
        if k < 0.2:
            kk = k / 0.2
            return lerp(self.TOP_X, 330, kk), lerp(self.stack_top(), floor, ease_in(kk)), None, -1
        xk = lerp(330, 60, (k - 0.2) / 0.8)
        return xk, floor, (330 - xk) / 120, -1

    def camera(self, x):
        t = x.t
        two = (650, 1260, 1.6)
        sl = x.m("slam")
        st = x.m("stare")
        keys = [(0, (420, 1300, 1.3)), (x.m("twenty").end, (480, 1300, 1.3)), (x.m("climb").end, two),
                (sl.start + 0.2, two), (sl.start + 0.6, (430, 1420, 1.4)), (sl.end - 0.3, (300, 1520, 1.4)),
                (sl.end + 0.2, two), (st.start, two), (st.start + 1.0, (830, 990, 2.4)), (st.end + 0.2, (830, 990, 2.4)),
                (x.m("goon").end, two), (x.m("exit").start + 0.3, (420, 1330, 1.3)), (x.dur, (300, 1330, 1.3))]
        cx, cy, z = keyframes(t, keys)
        x.cam.cx, x.cam.cy, x.cam.zoom = cx, cy, z
        x.cam.shake = 8 * max(0, 1 - abs(t - sl.start) / 0.15)

    def tariq(self, x):
        t = x.t
        st, sl, sh = x.m("stare"), x.m("slam"), x.m("short")
        counting = sh.start <= t < sh.end
        staring = st.start <= t < st.start + 1.5
        sliding = st.start + 1.5 <= t < st.end + 0.3
        follow = sl.start + 0.5 <= t < sl.end
        look = (0, 1)
        if counting:
            look = (-0.6, 1)
        if follow:
            look = (-1, 0.6)
        if staring:
            look = (-1, -0.1)
        face = Face(eyes="tired", look=look, blink=blink_at(t, 0.9), mouth="flat", talk=x.talk("tariq"),
                    brows=-0.3 if staring else 0)
        if counting:
            arm_f = (100 + 12 * math.sin(t * 9), -10)
        elif sliding:
            arm_f = (lerp(70, 95, ease((t - st.start - 1.5) / 0.5)), 0)
        else:
            arm_f = (150, -125)
        pose = Pose(lean=4 if counting else 0, arm_b=(160, -140), arm_f=arm_f, head_tilt=8 if (counting or not staring and not follow) else 0)
        j = draw_stickman(x.c, self.TARIQ_HIP, ADULT, pose, face, TARIQ, -1, 2.0)
        if not (counting or sliding):
            phone(x.c, (lerp(j["hand_f"][0], j["hand_b"][0], 0.5), j["hand_f"][1] - 10), 2.0)
        return j

    def draw(self, x):
        c, t = x.c, x.t
        from stickman.backgrounds import offy_counter
        j = self.tariq(x)
        offy_counter(c)
        top = 1180
        sl = x.m("slam")
        st = x.m("stare")
        # coins on the counter after the slam
        if t >= sl.start:
            r = random.Random(11)
            for k in range(8):
                ang = r.uniform(-0.4, 0.4)
                dist = r.uniform(30, 180)
                kk = ease_out(clamp((t - sl.start) / 0.5))
                cx = 610 + dist * kk * math.cos(ang)
                cy = top - 6 - 40 * math.sin(kk * math.pi) * r.random()
                if x.after("short") and k < 5:
                    cx = lerp(cx, 720, ease((t - x.m("short").start) / 0.8))
                coin(c, (cx, cy), 1.4, silver=k % 3 != 0, edge=0.75)
            # the one that rolls all the way to the door
            rk = clamp((t - sl.start - 0.2) / (sl.dur - 0.2))
            if rk < 0.15:
                k2 = rk / 0.15
                rx, ry = lerp(600, 545, k2), lerp(top - 8, 1650, ease_in(k2))
            else:
                k2 = ease_out((rk - 0.15) / 0.85)
                rx, ry = lerp(545, 165, k2), 1650 - abs(math.sin(k2 * 12)) * 10 * (1 - k2)
            wob = math.sin(t * 30) * (1 - rk)
            coin(c, (rx, ry), 1.4, silver=True, edge=0.85 - 0.1 * wob if rk < 0.98 else 0.2)
        # fags sliding across
        if t >= st.start + 1.5:
            pk = ease((t - st.start - 1.5) / 0.5)
            if t < x.m("cheers").start:
                fag_pack(c, (lerp(760, 640, pk), top - 22), 1.4)
        # crates
        cx0, floor = self.CRATES
        for k in range(3):
            y = floor - (k + 1) * self.CRATE_H
            col = ["#2f6fa8", "#d23a2f", "#e1b12c"][k]
            c.drawRect(skia.Rect.MakeXYWH(cx0 + (k % 2) * 6, y, 150, self.CRATE_H), fill(hexc(col)))
            c.drawRect(skia.Rect.MakeXYWH(cx0 + (k % 2) * 6, y, 150, self.CRATE_H), stroke(INK, 4))
            for h in range(4):
                c.drawRect(skia.Rect.MakeXYWH(cx0 + 14 + h * 34 + (k % 2) * 6, y + 14, 22, self.CRATE_H - 28), fill(mix(col, "#000000", 0.3)))
        # Kai
        kx, gy, ph, facing = self.kai_state(x.scene, t)
        slam_k = clamp(1 - abs(t - sl.start - 0.05) / 0.25)
        if ph is not None:
            pose, sway, bob = waddle(ph, 1.0)
        else:
            pose, sway, bob = Pose(), 0, 0
        has_fags = t >= x.m("cheers").start - 0.2
        has_coins = t < sl.start
        if has_coins:
            pose.arm_f = (120, 80)
            pose.arm_b = (110, 90)
        if sl.start - 0.35 <= t < sl.start + 0.4:
            pose.arm_f = (lerp(175, 80, slam_k), 0)
        if has_fags:
            pose.arm_b = (20, 120)
        look = (1, -0.7) if t < x.m("climb").start else (1, 0)
        if sl.start + 0.5 <= t < sl.end:
            look = (-1, 1)
        if st.start <= t < st.start + 1.5:
            look = (1, 0)
        face = Face(eyes="tired", look=look, brows=0.3, mouth="flat", talk=x.talk("kai"), blink=blink_at(t, 0.5))
        if facing < 0:
            face.look = (1, 0)
        jk = kai(c, (kx, kai_hip_y(gy, self.S, bob)), self.S, pose, face, KAI_VEST, facing, sway)
        if has_coins:
            coins(c, (jk["neck"][0] + 20 * facing, jk["neck"][1] + 20), 5, 1.2, seed=4)
        if has_fags:
            fag_pack(c, (jk["elbow_b"][0], jk["elbow_b"][1] + 10), 1.2, angle=10)


# ─────────────────────────────────────────────────────────────
class Lads:
    S = 1.7

    def kai_x(self, scene, t):
        lv = scene.mark("leave")
        if t < lv.start:
            return 600
        return 600 + (t - lv.start) * 230

    def phase(self, scene, t):
        return (self.kai_x(scene, t) - 600) / 130

    def camera(self, x):
        t = x.t
        tn, js = x.m("turn"), x.m("jobcentre")
        wide = (580, 1560, 1.35)
        keys = [(0, (600, 1450, 1.9)), (x.m("build").start, (600, 1450, 1.9)), (x.m("pass").start, wide),
                (tn.start, wide), (tn.end, (600, 1400, 2.6)), (js.end, (600, 1400, 2.6)),
                (x.m("leave").start + 0.8, (760, 1450, 1.6)), (x.dur, (900, 1450, 1.6))]
        cx, cy, z = keyframes(t, keys)
        x.cam.cx, x.cam.cy, x.cam.zoom = cx, cy, z
        b, p = x.m("build"), x.m("pass")
        x.cam.shake = 5 * clamp((t - b.start) / b.dur) * (1 if t < p.end else 0)
        x.rain = 0.9
        x.rain_speed = 0.25 if p.start <= t < p.end else 1.0

    def draw(self, x):
        c, t = x.c, x.t
        g = x.info["ground"]
        st, b, p, f, tn, lv = (x.m(k) for k in ("step", "build", "pass", "fade", "turn", "leave"))
        # Kai
        kx = self.kai_x(x.scene, t)
        walking = t >= lv.start
        pose, sway, bob = waddle(self.phase(x.scene, t)) if walking else (Pose(), 0, 0)
        pose.arm_b = (20, 120)
        step_k = ease(t / st.dur)
        y = kai_hip_y(g, self.S, bob) - (1 - step_k) * 10
        wind = p.start <= t < p.end
        if t < b.start:
            face = Face(eyes="tired", look=(1, 0), blink=blink_at(t))
        elif t < tn.start:
            face = Face(eyes="wide", look=(-1 + 2 * self.bike_look(x), 0), mouth="o" if wind else "flat")
        elif t < tn.end:
            k = ease((t - tn.start) / tn.dur)
            face = Face(eyes="wide" if k < 0.6 else "tired", look=(lerp(1, 0, k), 0))
        else:
            face = Face(eyes="tired", look=(0, 0) if not walking else (1, 0), mouth="flat", brows=-0.3,
                        talk=x.talk("kai"), blink=blink_at(t))
        if wind:
            pose.lean = -8 + 3 * math.sin(t * 13)
            pose.head_tilt = -6 + 4 * math.sin(t * 17)
        j = kai(c, (kx, y), self.S, pose, face, KAI_VEST, 1, sway)
        fag_pack(c, (j["elbow_b"][0], j["elbow_b"][1] + 10), 1.1, angle=10)
        # crisp packet blowing past his face
        if wind:
            k = clamp((t - p.start - 1.6) / 1.2)
            if 0 < k < 1:
                px, py = lerp(-80, 1200, k), j["head"][1] + math.sin(k * 9) * 30
                c.save()
                c.rotate(k * 900, px, py)
                c.drawRect(skia.Rect.MakeXYWH(px - 26, py - 16, 52, 32), fill(hexc("#d6232e")))
                c.drawRect(skia.Rect.MakeXYWH(px - 26, py - 16, 52, 32), stroke(INK, 3))
                c.restore()
        # the lads
        for k in range(3):
            bx = self.bike_x(x, k)
            if -500 < bx < 1600:
                self.bike(c, bx, 1855 - k * 8, t, k)

    def bike_look(self, x):
        b, p = x.m("build"), x.m("pass")
        return clamp((x.t - p.start - 0.6) / (p.dur - 0.8))

    def bike_x(self, x, k):
        b, p = x.m("build"), x.m("pass")
        t = x.t
        delay = k * 0.85
        if t < p.start + delay - 0.4:
            return -600
        u = (t - p.start - delay + 0.4) / (p.dur + 0.2)
        return lerp(-450, 1550, u)

    def bike(self, c, x, ground, t, k):
        wheelie = 26 + 6 * math.sin(t * 1.5 + k)
        c.save()
        rear = (x, ground - 70)
        c.rotate(-wheelie, rear[0], ground)
        front = (x + 300, ground - 70)
        for wx, wy in (rear, front):
            c.drawCircle(wx, wy, 70, stroke(hexc("#1c1c1f"), 22))
            c.drawCircle(wx, wy, 70, stroke(INK, 3))
            for a in range(6):
                ang = a * math.pi / 3 + t * 6
                c.drawLine(wx, wy, wx + math.cos(ang) * 58, wy + math.sin(ang) * 58, stroke(hexc("#aaaaaa"), 2))
            c.drawCircle(wx, wy, 10, fill(hexc("#888")))
        col = ["#e8612c", "#2f7fd8", "#e2c227"][k]
        frame = poly([(rear[0], rear[1]), (x + 110, ground - 150), (x + 230, ground - 160), (front[0] - 20, front[1] - 40), (x + 150, ground - 80)])
        c.drawPath(frame, fill(hexc("#2a2a2e")))
        c.drawPath(frame, stroke(INK, 4))
        c.drawPath(poly([(x + 80, ground - 175), (x + 250, ground - 185), (x + 260, ground - 160), (x + 70, ground - 150)]), fill(hexc(col)))
        c.drawPath(poly([(x + 80, ground - 175), (x + 250, ground - 185), (x + 260, ground - 160), (x + 70, ground - 150)]), stroke(INK, 4))
        c.drawLine(front[0], front[1], x + 250, ground - 220, stroke(hexc("#c0c0c0"), 10))
        c.drawLine(x + 235, ground - 235, x + 275, ground - 215, stroke(INK, 9))
        c.drawPath(poly([(front[0] - 60, front[1] - 90), (front[0] + 30, front[1] - 95), (front[0] - 20, front[1] - 70)]), fill(hexc(col)))
        c.drawRect(skia.Rect.MakeXYWH(x - 40, ground - 160, 50, 34), fill(hexc("#f2d11b")))
        c.drawRect(skia.Rect.MakeXYWH(x - 40, ground - 160, 50, 34), stroke(INK, 3))
        # exhaust smoke puffs
        for p in range(4):
            ph = (t * 1.5 + p / 4) % 1
            c.drawCircle(x - 60 - ph * 160, ground - 120 - ph * 40, 14 + ph * 34, fill(hexc("#b5b7ba"), 0.4 * (1 - ph)))
        # rider
        standing = k == 0
        waving = k == 1
        hip = (x + 150, ground - (250 if standing else 205))
        arm_b = (150, -30)
        arm_f = (175, -10 + 30 * math.sin(t * 9)) if waving else (110, -30)
        legs = ((40, -40), (25, -30)) if standing else ((80, -100), (70, -90))
        pose = Pose(lean=20, arm_b=arm_b, arm_f=arm_f, leg_b=legs[0], leg_f=legs[1])
        draw_stickman(c, hip, ADULT, pose, Face(eyes="glare", mouth="smirk" if k != 2 else "o"), LADS[k], 1, 1.1)
        c.restore()


# ─────────────────────────────────────────────────────────────
class EndCard:
    def camera(self, x):
        x.rain = 0.5

    def draw(self, x):
        t = x.t
        pose, sway, bob = Pose(arm_f=(150 + 15 * math.sin(t * 6), 20)), 0, 0
        face = Face(eyes="tired", look=(0, 0), mouth="flat", blink=blink_at(t, 0.3))
        kai(x.c, (540, 1430), 2.4, pose, face, Look(tracksuit="#8b8e95", tuft=True, socks_over=True), 1)

    def screen(self, x):
        c, t = x.c, x.t
        big = skia.Font(skia.Typeface.MakeFromFile("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), 120)
        mid = skia.Font(skia.Typeface.MakeFromFile("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"), 64)
        k = back_out(clamp(t / 0.6))
        for txt, f, y, col in (("EPISODE 2 →", big, 520, "#ffd83d"), ("THE JOB CENTRE", mid, 640, "#f2f2ee")):
            w = f.measureText(txt)
            c.save()
            c.translate(540, y)
            c.scale(k, k)
            c.drawString(txt, -w / 2, 0, f, stroke(INK, 16))
            c.drawString(txt, -w / 2, 0, f, fill(hexc(col)))
            c.restore()
        a = clamp((t - 1.0) / 0.5)
        pulse = 1 + 0.05 * math.sin(t * 6)
        txt = "Follow for part 2"
        w = mid.measureText(txt)
        c.save()
        c.translate(540, 1720)
        c.scale(pulse, pulse)
        r = skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(-w / 2 - 40, -80, w + 80, 120), 60, 60)
        c.drawRRect(r, fill(hexc("#e8314a"), a))
        c.drawString(txt, -w / 2, 0, mid, fill(hexc("#ffffff"), a))
        c.restore()


SCENES = {"cold_open": ColdOpen(), "birth": Birth(), "errand": Errand(), "waddle": Waddle(), "offy": Offy(),
          "lads": Lads(), "end_card": EndCard()}


# ── footstep squeaks, synced to the waddle cycles above ──────

def _steps(scene, t0, t1, phase_fn, pan=0.5, gain=STEP_SQUEAK_GAIN):
    ev, last, t, n = [], None, t0, 0
    while t < t1:
        ph = phase_fn(t)
        k = math.floor(ph * 2)
        if last is not None and k != last:
            ev.append({"name": "squeak", "t": scene.start + t, "variant": n % 6, "gain": gain, "pan": pan})
            n += 1
        last = k
        t += 1 / 120
    return ev


def audio_events(tl) -> list:
    ev = []
    for sc in tl.scenes:
        if sc.id == "waddle":
            w = SCENES["waddle"]
            ev += _steps(sc, 0, sc.duration, lambda t: w.phase(sc, t))
        elif sc.id == "offy":
            o = SCENES["offy"]

            def ph(t, o=o, sc=sc):
                r = o.kai_state(sc, t)[2]
                return r if r is not None else 0.0
            ev += _steps(sc, 0, sc.mark("twenty").end, ph)
            ev += _steps(sc, sc.mark("exit").start + 0.4, sc.duration, ph)
        elif sc.id == "lads":
            l = SCENES["lads"]
            ev += _steps(sc, sc.mark("leave").start, sc.duration, lambda t: l.phase(sc, t), pan=0.7)
        elif sc.id == "errand":
            cl = sc.mark("climb")
            ev += _steps(sc, cl.start + cl.dur * 0.35, cl.end, lambda t: t * 2.8)
    return ev
