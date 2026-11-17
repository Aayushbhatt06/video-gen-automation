"""
Prop Extraction + 2D Bright Cartoon Prop Animation Library.

Pipeline:
  1. extract_props_for_beat(): scans each beat's English subtitle (+ story title) for
     keywords and maps them to cartoon prop drawers (truck, bank, money, brain, ...).
  2. plan_props(script): attaches a `props` list to every beat with layout slots,
     entrance delays and animation types, so props appear exactly when the story
     mentions them.
  3. draw_prop(): renders each prop as a flat, bright, thick-outlined 2D cartoon
     with pop / bounce / wiggle animation.
"""
import math
import re

from pipeline_fonts import get_font

OUTLINE = (28, 28, 40)
OW = 7  # outline width

# Bright cartoon palette
RED = (255, 72, 88)
ORANGE = (255, 150, 40)
YELLOW = (255, 214, 40)
GREEN = (60, 210, 110)
TEAL = (30, 200, 200)
BLUE = (50, 140, 255)
PURPLE = (160, 90, 255)
PINK = (255, 110, 190)
WHITE = (255, 255, 255)
BROWN = (170, 100, 50)
GREY = (190, 198, 210)
DARK = (55, 60, 75)
SKIN = (255, 210, 160)


# ---------------------------------------------------------------- helpers
def _r(cx, cy, w, h):
    return [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]


def _rr(d, cx, cy, w, h, fill, radius=18, width=OW):
    d.rounded_rectangle(_r(cx, cy, w, h), radius=int(radius), fill=fill, outline=OUTLINE, width=width)


def _el(d, cx, cy, w, h, fill, width=OW):
    d.ellipse(_r(cx, cy, w, h), fill=fill, outline=OUTLINE, width=width)


def _poly(d, pts, fill, width=OW):
    d.polygon(pts, fill=fill, outline=OUTLINE)
    d.line(pts + [pts[0]], fill=OUTLINE, width=width, joint="curve")


def _wheel(d, cx, cy, r):
    _el(d, cx, cy, r * 2, r * 2, DARK)
    _el(d, cx, cy, r * 0.9, r * 0.9, GREY, width=4)


# ---------------------------------------------------------------- prop drawers
# Each drawer: fn(d, cx, cy, s, t) where s = scale (1.0 ≈ 220 px box), t = seconds since entrance


def draw_truck(d, cx, cy, s, t):
    bob = math.sin(t * 14) * 3 * s
    _rr(d, cx - 40 * s, cy - 20 * s + bob, 200 * s, 120 * s, ORANGE, 14 * s)
    _rr(d, cx + 95 * s, cy - 5 * s + bob, 80 * s, 90 * s, BLUE, 14 * s)
    _rr(d, cx + 102 * s, cy - 22 * s + bob, 46 * s, 36 * s, (200, 240, 255), 8 * s, 4)
    for wx in (-100, 10, 100):
        _wheel(d, cx + wx * s, cy + 50 * s, 26 * s)


def draw_car(d, cx, cy, s, t):
    bob = math.sin(t * 16) * 3 * s
    _rr(d, cx, cy + 5 * s + bob, 230 * s, 70 * s, RED, 24 * s)
    _poly(d, [(cx - 60 * s, cy - 30 * s + bob), (cx + 50 * s, cy - 30 * s + bob),
              (cx + 80 * s, cy + bob), (cx - 90 * s, cy + bob)], (200, 240, 255))
    _wheel(d, cx - 70 * s, cy + 45 * s, 26 * s)
    _wheel(d, cx + 70 * s, cy + 45 * s, 26 * s)


def draw_bank(d, cx, cy, s, t):
    _poly(d, [(cx - 120 * s, cy - 50 * s), (cx, cy - 120 * s), (cx + 120 * s, cy - 50 * s)], YELLOW)
    _rr(d, cx, cy + 30 * s, 220 * s, 150 * s, WHITE, 6 * s)
    for px in (-75, -25, 25, 75):
        _rr(d, cx + px * s, cy + 30 * s, 22 * s, 130 * s, GREY, 4 * s, 4)
    d.text((cx, cy - 72 * s), "$", font=get_font(int(50 * s) + 8), fill=OUTLINE, anchor="mm")


def draw_money(d, cx, cy, s, t):
    for i in range(3):
        off = i * 16 * s
        sway = math.sin(t * 6 + i) * 6 * s
        _rr(d, cx - off + sway, cy - off, 200 * s, 100 * s, GREEN, 12 * s)
        _el(d, cx - off + sway, cy - off, 56 * s, 56 * s, (150, 240, 170), 4)


def draw_coin(d, cx, cy, s, t):
    squash = abs(math.cos(t * 5))
    w = max(20 * s, 170 * s * squash)
    _el(d, cx, cy, w, 170 * s, YELLOW)
    if squash > 0.35:
        _el(d, cx, cy, w * 0.7, 120 * s, ORANGE, 4)


def draw_phone(d, cx, cy, s, t):
    _rr(d, cx, cy, 120 * s, 220 * s, DARK, 24 * s)
    glow = (100 + int(80 * abs(math.sin(t * 4))), 200, 255)
    _rr(d, cx, cy - 5 * s, 96 * s, 170 * s, glow, 10 * s, 4)
    _el(d, cx, cy + 92 * s, 18 * s, 18 * s, GREY, 3)


def draw_laptop(d, cx, cy, s, t):
    _rr(d, cx, cy - 30 * s, 210 * s, 140 * s, DARK, 12 * s)
    _rr(d, cx, cy - 30 * s, 180 * s, 110 * s, (110, 210, 255), 6 * s, 4)
    _poly(d, [(cx - 130 * s, cy + 45 * s), (cx + 130 * s, cy + 45 * s),
              (cx + 110 * s, cy + 70 * s), (cx - 110 * s, cy + 70 * s)], GREY)


def draw_brain(d, cx, cy, s, t):
    pulse = 1 + 0.05 * math.sin(t * 8)
    for ox, oy in ((-45, -20), (40, -25), (-30, 30), (35, 28), (0, -50)):
        _el(d, cx + ox * s * pulse, cy + oy * s * pulse, 110 * s * pulse, 90 * s * pulse, PINK)
    d.line([(cx, cy - 80 * s), (cx, cy + 60 * s)], fill=OUTLINE, width=5)


def draw_heart(d, cx, cy, s, t):
    p = 1 + 0.12 * abs(math.sin(t * 6))
    _el(d, cx - 45 * s * p, cy - 30 * s * p, 110 * s * p, 110 * s * p, RED)
    _el(d, cx + 45 * s * p, cy - 30 * s * p, 110 * s * p, 110 * s * p, RED)
    _poly(d, [(cx - 98 * s * p, cy - 10 * s * p), (cx + 98 * s * p, cy - 10 * s * p), (cx, cy + 100 * s * p)], RED)


def draw_stomach(d, cx, cy, s, t):
    wob = math.sin(t * 5) * 8 * s
    _el(d, cx + wob, cy, 200 * s, 150 * s, PINK)
    _rr(d, cx - 70 * s, cy - 95 * s, 40 * s, 80 * s, PINK, 18 * s)
    for i in range(4):
        bx = cx - 40 * s + i * 28 * s
        by = cy + math.sin(t * 7 + i) * 18 * s
        _el(d, bx, by, 22 * s, 22 * s, (180, 255, 120), 3)


def draw_clock(d, cx, cy, s, t):
    _el(d, cx, cy, 200 * s, 200 * s, WHITE)
    _el(d, cx, cy, 170 * s, 170 * s, YELLOW, 4)
    a = t * 4
    d.line([(cx, cy), (cx + math.cos(a) * 65 * s, cy + math.sin(a) * 65 * s)], fill=OUTLINE, width=8)
    d.line([(cx, cy), (cx + math.cos(a / 12) * 42 * s, cy + math.sin(a / 12) * 42 * s)], fill=RED, width=10)


def draw_globe(d, cx, cy, s, t):
    _el(d, cx, cy, 210 * s, 210 * s, BLUE)
    shift = (t * 40 * s) % (120 * s)
    for ox, oy, w, h in ((-40, -30, 70, 50), (40, 20, 80, 60), (-10, 60, 50, 30)):
        x = cx + ox * s + shift - 60 * s
        if abs(x - cx) < 80 * s:
            _el(d, x, cy + oy * s, w * s, h * s, GREEN, 4)


def draw_rocket(d, cx, cy, s, t):
    up = -((t * 60) % 40) * s
    flame = 30 + 20 * abs(math.sin(t * 20))
    _poly(d, [(cx - 30 * s, cy + 70 * s + up), (cx, cy + (90 + flame) * s + up), (cx + 30 * s, cy + 70 * s + up)], ORANGE)
    _rr(d, cx, cy + up, 80 * s, 160 * s, WHITE, 36 * s)
    _poly(d, [(cx - 40 * s, cy - 50 * s + up), (cx, cy - 120 * s + up), (cx + 40 * s, cy - 50 * s + up)], RED)
    _el(d, cx, cy - 10 * s + up, 40 * s, 40 * s, (120, 220, 255), 4)


def draw_plane(d, cx, cy, s, t):
    dy = math.sin(t * 3) * 10 * s
    _rr(d, cx, cy + dy, 240 * s, 50 * s, WHITE, 25 * s)
    _poly(d, [(cx - 20 * s, cy + dy), (cx + 40 * s, cy + dy), (cx - 40 * s, cy + 90 * s + dy)], BLUE)
    _poly(d, [(cx - 100 * s, cy + dy), (cx - 80 * s, cy + dy), (cx - 120 * s, cy - 60 * s + dy)], RED)


def draw_house(d, cx, cy, s, t):
    _poly(d, [(cx - 120 * s, cy - 20 * s), (cx, cy - 120 * s), (cx + 120 * s, cy - 20 * s)], RED)
    _rr(d, cx, cy + 50 * s, 200 * s, 140 * s, YELLOW, 6 * s)
    _rr(d, cx - 45 * s, cy + 70 * s, 50 * s, 100 * s, BROWN, 6 * s, 4)
    _rr(d, cx + 50 * s, cy + 30 * s, 50 * s, 50 * s, (150, 220, 255), 6 * s, 4)


def draw_building(d, cx, cy, s, t):
    _rr(d, cx, cy, 150 * s, 240 * s, PURPLE, 8 * s)
    for row in range(5):
        for col in range(3):
            lit = (int(t * 3) + row + col) % 3 != 0
            _rr(d, cx + (col - 1) * 42 * s, cy - 90 * s + row * 42 * s, 28 * s, 26 * s,
                YELLOW if lit else (90, 70, 140), 4 * s, 3)


def draw_jail(d, cx, cy, s, t):
    _rr(d, cx, cy, 200 * s, 220 * s, GREY, 10 * s)
    for i in range(5):
        x = cx - 80 * s + i * 40 * s
        d.line([(x, cy - 105 * s), (x, cy + 105 * s)], fill=DARK, width=int(12 * s) + 2)


def draw_box(d, cx, cy, s, t):
    hop = -abs(math.sin(t * 6)) * 20 * s
    _rr(d, cx, cy + hop, 190 * s, 160 * s, (220, 160, 90), 8 * s)
    d.line([(cx, cy - 80 * s + hop), (cx, cy + 80 * s + hop)], fill=OUTLINE, width=6)
    _rr(d, cx, cy - 60 * s + hop, 190 * s, 24 * s, (240, 190, 120), 4 * s, 4)


def draw_food(d, cx, cy, s, t):
    _el(d, cx, cy - 45 * s, 200 * s, 90 * s, ORANGE)
    _rr(d, cx, cy, 210 * s, 26 * s, GREEN, 10 * s, 4)
    _rr(d, cx, cy + 25 * s, 200 * s, 34 * s, BROWN, 14 * s, 4)
    _rr(d, cx, cy + 60 * s, 200 * s, 40 * s, ORANGE, 18 * s)


def draw_water(d, cx, cy, s, t):
    for i in range(3):
        y = cy - 40 * s + i * 45 * s
        pts = [(cx - 120 * s + k * 10 * s, y + math.sin(t * 4 + k * 0.5 + i) * 14 * s) for k in range(25)]
        d.line(pts, fill=BLUE if i % 2 == 0 else TEAL, width=int(16 * s) + 4, joint="curve")


def draw_fire(d, cx, cy, s, t):
    f = 1 + 0.12 * math.sin(t * 18)
    _poly(d, [(cx - 80 * s, cy + 80 * s), (cx - 70 * s, cy - 20 * s), (cx - 20 * s, cy + 10 * s),
              (cx, cy - 120 * s * f), (cx + 30 * s, cy), (cx + 70 * s, cy - 40 * s), (cx + 80 * s, cy + 80 * s)], ORANGE)
    _poly(d, [(cx - 40 * s, cy + 80 * s), (cx - 20 * s, cy + 10 * s), (cx, cy - 50 * s * f),
              (cx + 20 * s, cy + 10 * s), (cx + 40 * s, cy + 80 * s)], YELLOW, 4)


def draw_lightning(d, cx, cy, s, t):
    flash = YELLOW if int(t * 10) % 2 == 0 else (255, 250, 160)
    _poly(d, [(cx + 20 * s, cy - 120 * s), (cx - 60 * s, cy + 10 * s), (cx - 5 * s, cy + 10 * s),
              (cx - 30 * s, cy + 120 * s), (cx + 60 * s, cy - 20 * s), (cx + 5 * s, cy - 20 * s)], flash)


def draw_chart(d, cx, cy, s, t):
    _rr(d, cx, cy, 230 * s, 200 * s, WHITE, 14 * s)
    grow = min(1.0, t * 1.5)
    for i, (hgt, col) in enumerate(((60, BLUE), (100, GREEN), (150, ORANGE))):
        h = hgt * s * grow
        x = cx - 60 * s + i * 60 * s
        _rr(d, x, cy + 80 * s - h / 2, 40 * s, max(6, h), col, 6 * s, 4)


def draw_book(d, cx, cy, s, t):
    _rr(d, cx - 55 * s, cy, 110 * s, 160 * s, BLUE, 8 * s)
    _rr(d, cx + 55 * s, cy, 110 * s, 160 * s, RED, 8 * s)
    for i in range(3):
        y = cy - 40 * s + i * 30 * s
        d.line([(cx - 90 * s, y), (cx - 20 * s, y)], fill=WHITE, width=5)
        d.line([(cx + 20 * s, y), (cx + 90 * s, y)], fill=WHITE, width=5)


def draw_crown(d, cx, cy, s, t):
    tilt = math.sin(t * 4) * 6 * s
    _poly(d, [(cx - 110 * s, cy + 50 * s), (cx - 110 * s, cy - 50 * s + tilt), (cx - 55 * s, cy),
              (cx, cy - 80 * s), (cx + 55 * s, cy), (cx + 110 * s, cy - 50 * s - tilt), (cx + 110 * s, cy + 50 * s)], YELLOW)
    for gx in (-55, 0, 55):
        _el(d, cx + gx * s, cy + 25 * s, 26 * s, 26 * s, RED, 4)


def draw_trophy(d, cx, cy, s, t):
    _el(d, cx, cy - 40 * s, 160 * s, 140 * s, YELLOW)
    _rr(d, cx, cy + 50 * s, 40 * s, 60 * s, YELLOW, 6 * s)
    _rr(d, cx, cy + 95 * s, 130 * s, 34 * s, BROWN, 8 * s)
    if int(t * 8) % 2:
        draw_star(d, cx + 95 * s, cy - 105 * s, 0.25 * s, t)


def draw_warning(d, cx, cy, s, t):
    p = 1 + 0.08 * abs(math.sin(t * 8))
    _poly(d, [(cx, cy - 110 * s * p), (cx + 120 * s * p, cy + 90 * s * p), (cx - 120 * s * p, cy + 90 * s * p)], YELLOW)
    _rr(d, cx, cy - 5 * s, 24 * s, 90 * s, OUTLINE, 10 * s, 1)
    _el(d, cx, cy + 60 * s, 26 * s, 26 * s, OUTLINE, 1)


def draw_question(d, cx, cy, s, t):
    wig = math.sin(t * 6) * 10 * s
    _el(d, cx + wig, cy, 200 * s, 200 * s, PURPLE)
    d.arc(_r(cx + wig, cy - 25 * s, 90 * s, 90 * s), 180, 60, fill=WHITE, width=int(20 * s) + 2)
    d.line([(cx + wig + 25 * s, cy + 10 * s), (cx + wig, cy + 35 * s)], fill=WHITE, width=int(20 * s) + 2)
    _el(d, cx + wig, cy + 70 * s, 26 * s, 26 * s, WHITE, 1)


def draw_exclaim(d, cx, cy, s, t):
    p = 1 + 0.1 * abs(math.sin(t * 9))
    _el(d, cx, cy, 200 * s * p, 200 * s * p, RED)
    _rr(d, cx, cy - 20 * s, 30 * s, 100 * s, WHITE, 12 * s, 1)
    _el(d, cx, cy + 60 * s, 32 * s, 32 * s, WHITE, 1)


def draw_flask(d, cx, cy, s, t):
    _poly(d, [(cx - 30 * s, cy - 100 * s), (cx + 30 * s, cy - 100 * s), (cx + 30 * s, cy - 30 * s),
              (cx + 100 * s, cy + 90 * s), (cx - 100 * s, cy + 90 * s), (cx - 30 * s, cy - 30 * s)], (220, 240, 255))
    _poly(d, [(cx - 70 * s, cy + 40 * s), (cx + 70 * s, cy + 40 * s), (cx + 100 * s, cy + 90 * s), (cx - 100 * s, cy + 90 * s)], GREEN, 4)
    for i in range(3):
        by = cy + 30 * s - ((t * 80 + i * 40) % 120) * s
        _el(d, cx - 20 * s + i * 20 * s, by, 18 * s, 18 * s, (180, 255, 180), 3)


def draw_tree(d, cx, cy, s, t):
    sway = math.sin(t * 3) * 8 * s
    _rr(d, cx, cy + 70 * s, 40 * s, 100 * s, BROWN, 8 * s)
    _el(d, cx + sway, cy - 30 * s, 200 * s, 170 * s, GREEN)


def draw_sun(d, cx, cy, s, t):
    for i in range(10):
        a = t * 1.5 + i * math.pi / 5
        d.line([(cx + math.cos(a) * 90 * s, cy + math.sin(a) * 90 * s),
                (cx + math.cos(a) * 130 * s, cy + math.sin(a) * 130 * s)], fill=ORANGE, width=int(14 * s) + 2)
    _el(d, cx, cy, 160 * s, 160 * s, YELLOW)


def draw_moon(d, cx, cy, s, t):
    _el(d, cx, cy, 190 * s, 190 * s, (255, 245, 180))
    _el(d, cx + 55 * s, cy - 30 * s, 150 * s, 150 * s, (40, 50, 110), 0)


def draw_star(d, cx, cy, s, t):
    rot = t * 2
    pts = []
    for i in range(10):
        r = (110 if i % 2 == 0 else 45) * s
        a = rot + i * math.pi / 5 - math.pi / 2
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    _poly(d, pts, YELLOW)


def draw_bomb(d, cx, cy, s, t):
    _el(d, cx, cy + 20 * s, 180 * s, 180 * s, DARK)
    _rr(d, cx + 50 * s, cy - 70 * s, 40 * s, 30 * s, GREY, 6 * s, 4)
    spark = 20 + 15 * abs(math.sin(t * 20))
    _el(d, cx + 85 * s, cy - 105 * s, spark * s, spark * s, ORANGE, 3)


def draw_map(d, cx, cy, s, t):
    _poly(d, [(cx - 120 * s, cy - 80 * s), (cx - 40 * s, cy - 100 * s), (cx + 40 * s, cy - 80 * s),
              (cx + 120 * s, cy - 100 * s), (cx + 120 * s, cy + 90 * s), (cx + 40 * s, cy + 110 * s),
              (cx - 40 * s, cy + 90 * s), (cx - 120 * s, cy + 110 * s)], (250, 230, 180))
    prog = min(1.0, t * 0.8)
    pts = [(cx - 90 * s + k * 18 * s, cy + 40 * s - math.sin(k * 0.6) * 50 * s) for k in range(int(11 * prog) + 1)]
    for i in range(0, len(pts) - 1, 2):
        d.line([pts[i], pts[i + 1]], fill=RED, width=7)
    _el(d, pts[-1][0], pts[-1][1], 28 * s, 28 * s, RED, 4)


def draw_key(d, cx, cy, s, t):
    rot = math.sin(t * 4) * 10 * s
    _el(d, cx - 60 * s, cy + rot, 100 * s, 100 * s, YELLOW)
    _el(d, cx - 60 * s, cy + rot, 40 * s, 40 * s, WHITE, 4)
    _rr(d, cx + 40 * s, cy + rot, 140 * s, 28 * s, YELLOW, 8 * s)
    _rr(d, cx + 90 * s, cy + 25 * s + rot, 18 * s, 34 * s, YELLOW, 4 * s, 4)


def draw_lock(d, cx, cy, s, t):
    d.arc(_r(cx, cy - 40 * s, 120 * s, 130 * s), 180, 360, fill=OUTLINE, width=int(24 * s) + 4)
    _rr(d, cx, cy + 30 * s, 170 * s, 130 * s, ORANGE, 16 * s)
    _el(d, cx, cy + 25 * s, 30 * s, 30 * s, OUTLINE, 1)


def draw_gift(d, cx, cy, s, t):
    hop = -abs(math.sin(t * 5)) * 14 * s
    _rr(d, cx, cy + 20 * s + hop, 180 * s, 140 * s, PINK, 10 * s)
    _rr(d, cx, cy - 55 * s + hop, 200 * s, 40 * s, RED, 8 * s)
    _rr(d, cx, cy + hop, 28 * s, 180 * s, YELLOW, 4 * s, 4)


def draw_camera(d, cx, cy, s, t):
    _rr(d, cx, cy, 220 * s, 150 * s, DARK, 20 * s)
    _el(d, cx, cy, 100 * s, 100 * s, GREY)
    _el(d, cx, cy, 55 * s, 55 * s, BLUE, 4)
    if int(t * 3) % 3 == 0:
        _el(d, cx + 80 * s, cy - 55 * s, 34 * s, 34 * s, WHITE, 3)


def draw_music(d, cx, cy, s, t):
    b = math.sin(t * 6) * 10 * s
    _el(d, cx - 50 * s, cy + 60 * s + b, 70 * s, 55 * s, PURPLE)
    _el(d, cx + 60 * s, cy + 40 * s - b, 70 * s, 55 * s, PURPLE)
    d.line([(cx - 18 * s, cy + 55 * s + b), (cx - 18 * s, cy - 80 * s)], fill=OUTLINE, width=10)
    d.line([(cx + 92 * s, cy + 35 * s - b), (cx + 92 * s, cy - 100 * s)], fill=OUTLINE, width=10)
    d.line([(cx - 18 * s, cy - 80 * s), (cx + 92 * s, cy - 100 * s)], fill=OUTLINE, width=18)


def draw_person(d, cx, cy, s, t):
    wave = math.sin(t * 8) * 30 * s
    _rr(d, cx, cy + 50 * s, 100 * s, 120 * s, TEAL, 30 * s)
    _el(d, cx, cy - 50 * s, 100 * s, 100 * s, SKIN)
    _el(d, cx - 18 * s, cy - 55 * s, 14 * s, 18 * s, OUTLINE, 1)
    _el(d, cx + 18 * s, cy - 55 * s, 14 * s, 18 * s, OUTLINE, 1)
    d.arc(_r(cx, cy - 35 * s, 40 * s, 24 * s), 0, 180, fill=OUTLINE, width=5)
    d.line([(cx + 50 * s, cy + 20 * s), (cx + 100 * s, cy - 30 * s + wave)], fill=SKIN, width=int(22 * s) + 2)


def draw_police(d, cx, cy, s, t):
    draw_person(d, cx, cy + 10 * s, s, t)
    _rr(d, cx, cy - 98 * s, 120 * s, 36 * s, BLUE, 10 * s)
    siren = RED if int(t * 6) % 2 else BLUE
    _el(d, cx, cy - 130 * s, 30 * s, 30 * s, siren, 3)


def draw_dna(d, cx, cy, s, t):
    for k in range(12):
        y = cy - 110 * s + k * 20 * s
        a = t * 3 + k * 0.6
        x1 = cx + math.sin(a) * 60 * s
        x2 = cx - math.sin(a) * 60 * s
        d.line([(x1, y), (x2, y)], fill=GREY, width=4)
        _el(d, x1, y, 22 * s, 22 * s, BLUE, 3)
        _el(d, x2, y, 22 * s, 22 * s, PINK, 3)


def draw_tooth(d, cx, cy, s, t):
    _poly(d, [(cx - 80 * s, cy - 80 * s), (cx + 80 * s, cy - 80 * s), (cx + 70 * s, cy + 20 * s),
              (cx + 45 * s, cy + 110 * s), (cx + 10 * s, cy + 30 * s), (cx - 10 * s, cy + 30 * s),
              (cx - 45 * s, cy + 110 * s), (cx - 70 * s, cy + 20 * s)], WHITE)


def draw_eye(d, cx, cy, s, t):
    _el(d, cx, cy, 230 * s, 140 * s, WHITE)
    look = math.sin(t * 2) * 30 * s
    _el(d, cx + look, cy, 90 * s, 90 * s, BLUE, 4)
    _el(d, cx + look, cy, 40 * s, 40 * s, OUTLINE, 1)


def draw_virus(d, cx, cy, s, t):
    rot = t * 1.5
    for i in range(8):
        a = rot + i * math.pi / 4
        ex, ey = cx + math.cos(a) * 100 * s, cy + math.sin(a) * 100 * s
        d.line([(cx, cy), (ex, ey)], fill=OUTLINE, width=8)
        _el(d, ex, ey, 30 * s, 30 * s, RED, 4)
    _el(d, cx, cy, 150 * s, 150 * s, GREEN)


def draw_card(d, cx, cy, s, t, label="FACT", color=None):
    """Generic fallback prop: bright sticker card with keyword text."""
    col = color or [YELLOW, PINK, TEAL, ORANGE, PURPLE][hash(label) % 5]
    wob = math.sin(t * 5) * 4 * s
    _rr(d, cx, cy + wob, 250 * s, 130 * s, col, 26 * s)
    d.text((cx, cy + wob), label[:12], font=get_font(int(46 * s) + 6), fill=OUTLINE, anchor="mm")


# keyword -> prop key
PROP_LIBRARY = {
    "truck": (draw_truck, ["truck", "trucks", "lorry", "trailer", "cargo", "freight"]),
    "car": (draw_car, ["car", "cars", "vehicle", "drive", "driver", "taxi", "road", "highway", "traffic"]),
    "bank": (draw_bank, ["bank", "banks", "banking", "loan", "finance", "economy", "market", "stock"]),
    "money": (draw_money, ["money", "cash", "dollar", "dollars", "$", "rupee", "rupees", "price", "paid", "pay", "rich", "billion", "million", "salary", "tax"]),
    "coin": (draw_coin, ["coin", "coins", "crypto", "bitcoin", "gold", "penny"]),
    "phone": (draw_phone, ["phone", "smartphone", "iphone", "mobile", "app", "android", "instagram", "youtube", "social"]),
    "laptop": (draw_laptop, ["laptop", "computer", "pc", "software", "internet", "online", "ai", "chatgpt", "code", "tech", "technology", "website", "google"]),
    "brain": (draw_brain, ["brain", "mind", "think", "memory", "smart", "iq", "neuron", "psychology"]),
    "heart": (draw_heart, ["heart", "love", "blood", "pulse", "health"]),
    "stomach": (draw_stomach, ["stomach", "gut", "digest", "acid", "swallow", "swallowed", "belly", "intestine"]),
    "clock": (draw_clock, ["clock", "time", "hour", "hours", "minute", "minutes", "seconds", "year", "years", "day", "days", "late"]),
    "globe": (draw_globe, ["world", "earth", "globe", "country", "countries", "global", "planet", "nation", "america", "india", "china", "usa", "uk", "europe"]),
    "rocket": (draw_rocket, ["rocket", "space", "nasa", "launch", "isro", "spacex", "satellite", "mars", "orbit"]),
    "plane": (draw_plane, ["plane", "airplane", "flight", "airport", "pilot", "fly", "flying", "aircraft", "jet"]),
    "house": (draw_house, ["house", "home", "rent", "room", "family", "village"]),
    "building": (draw_building, ["building", "city", "office", "company", "tower", "skyscraper", "corporate", "factory"]),
    "jail": (draw_jail, ["jail", "prison", "prisoner", "arrest", "arrested", "crime", "criminal", "escape", "court"]),
    "box": (draw_box, ["box", "package", "parcel", "delivery", "mail", "mailed", "courier", "amazon", "shipping"]),
    "food": (draw_food, ["food", "burger", "eat", "eating", "pizza", "meal", "restaurant", "snack", "cook"]),
    "water": (draw_water, ["water", "ocean", "sea", "wave", "waves", "river", "rain", "flood", "swim"]),
    "fire": (draw_fire, ["fire", "burn", "burning", "hot", "heat", "flame", "explode", "volcano"]),
    "lightning": (draw_lightning, ["electricity", "power", "energy", "electric", "battery", "lightning", "fast", "speed", "charge"]),
    "chart": (draw_chart, ["chart", "data", "percent", "%", "stats", "numbers", "growth", "record", "study", "survey", "increase", "measure", "measures", "length"]),
    "book": (draw_book, ["book", "law", "laws", "rule", "rules", "history", "school", "study", "exam", "government", "regulation"]),
    "crown": (draw_crown, ["king", "queen", "crown", "royal", "empire", "emperor", "ruler", "boss"]),
    "trophy": (draw_trophy, ["win", "won", "winner", "trophy", "champion", "award", "victory", "cricket", "match", "cup"]),
    "warning": (draw_warning, ["danger", "dangerous", "warning", "risk", "deadly", "toxic", "alert", "crash", "accident"]),
    "flask": (draw_flask, ["science", "scientist", "scientists", "lab", "experiment", "chemical", "research", "researchers"]),
    "tree": (draw_tree, ["tree", "trees", "forest", "plant", "nature", "jungle", "green"]),
    "sun": (draw_sun, ["sun", "summer", "solar", "sunlight", "daylight"]),
    "moon": (draw_moon, ["moon", "night", "dark", "sleep", "slept"]),
    "star": (draw_star, ["star", "stars", "famous", "celebrity", "viral", "trending", "bollywood", "movie", "film"]),
    "bomb": (draw_bomb, ["bomb", "explosion", "blast", "war", "attack", "army", "military", "soldier", "weapon"]),
    "map": (draw_map, ["map", "travel", "journey", "route", "voyage", "border", "trip", "miles", "kilometers"]),
    "key": (draw_key, ["key", "secret", "hidden", "unlock", "loophole", "trick", "hack"]),
    "lock": (draw_lock, ["lock", "locked", "security", "safe", "password", "privacy"]),
    "gift": (draw_gift, ["gift", "free", "bonus", "prize", "surprise", "festival", "diwali"]),
    "camera": (draw_camera, ["camera", "photo", "picture", "video", "selfie", "recorded"]),
    "music": (draw_music, ["music", "song", "songs", "sing", "singer", "concert", "dance"]),
    "police": (draw_police, ["police", "cop", "cops", "guard", "guards", "officer", "officials"]),
    "person": (draw_person, ["guy", "man", "woman", "people", "dude", "person", "kid", "children", "boy", "girl", "worker", "workers"]),
    "dna": (draw_dna, ["dna", "gene", "genes", "genetic", "cell", "cells", "body"]),
    "tooth": (draw_tooth, ["tooth", "teeth", "dentist", "chew", "chewing", "gum"]),
    "eye": (draw_eye, ["eye", "eyes", "see", "look", "watch", "vision", "noticed", "notice"]),
    "virus": (draw_virus, ["virus", "disease", "bacteria", "germ", "infection", "covid", "sick"]),
    "question": (draw_question, ["why", "how", "what", "mystery", "unknown", "nobody", "secretly"]),
    "exclaim": (draw_exclaim, ["wait", "shocking", "insane", "crazy", "wild", "omg", "unbelievable"]),
}

_KEYWORD_INDEX = {}
for _key, (_fn, _kws) in PROP_LIBRARY.items():
    for _kw in _kws:
        _KEYWORD_INDEX.setdefault(_kw, _key)

# Emotive/vague props should only be used when nothing concrete is found
_GENERIC_PROPS = {"question", "exclaim", "person", "eye", "clock"}

_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "have", "was", "were", "into", "over", "bro",
    "literally", "just", "about", "they", "their", "there", "then", "than", "what", "when", "your",
    "you", "here", "is", "are", "it", "its", "of", "to", "in", "on", "a", "an", "at", "be", "by", "or",
    "so", "but", "not", "no", "yes", "real", "really", "even", "every", "single", "part", "thing", "things",
    "going", "look", "first", "detail", "zoom", "inside", "breakdown", "where", "gets", "crazier", "because",
    "exact", "setup", "turning", "whole", "upside", "down", "which", "why", "everyone", "assumed", "random",
    "coincidence", "mistake", "joke", "trending", "right", "now", "backstory", "hell", "wait",
}

LAYOUT_SLOTS = {
    1: [(540, 700, 1.45)],
    2: [(320, 640, 1.05), (770, 800, 1.05)],
    3: [(290, 560, 0.85), (790, 600, 0.85), (560, 900, 0.95)],
}

ANIMS = ["pop", "drop", "slide_left", "slide_right", "spin_in"]


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-zA-Z$%]+", text.lower())]


def extract_props_for_beat(text: str, max_props: int = 3) -> list[dict]:
    found: list[str] = []
    labels: list[str] = []
    for tok in _tokens(text):
        key = _KEYWORD_INDEX.get(tok)
        if key and key not in found:
            found.append(key)
        elif not key and len(tok) >= 5 and tok not in _STOPWORDS and tok.upper() not in labels:
            labels.append(tok.upper())
    concrete = [k for k in found if k not in _GENERIC_PROPS]
    generic = [k for k in found if k in _GENERIC_PROPS]
    chosen = (concrete + generic)[:max_props]
    props = [{"kind": k, "label": k.upper()} for k in chosen]
    # Fill with keyword sticker cards so every beat shows something story-specific
    while len(props) < 2 and labels:
        props.append({"kind": "card", "label": labels.pop(0)})
    if not props:
        props.append({"kind": "exclaim", "label": "WOW"})
    return props[:max_props]


def plan_props(script: dict) -> dict:
    """Attach a `props` plan (kind, label, slot, delay, anim) to every beat in-place."""
    title_props = extract_props_for_beat(script.get("title", ""), 1)
    for i, beat in enumerate(script.get("beats", [])):
        props = extract_props_for_beat(beat.get("en_subtitle", ""))
        # Keep the main topic prop visible on the hook beat so the story frame is clear
        if i == 0 and title_props and title_props[0]["kind"] not in [p["kind"] for p in props]:
            props = (title_props + props)[:3]
        slots = LAYOUT_SLOTS[len(props)]
        for j, p in enumerate(props):
            x, y, sc = slots[j]
            p.update({"x": x, "y": y, "scale": sc, "delay": round(0.18 * j, 2), "anim": ANIMS[(i + j) % len(ANIMS)]})
        beat["props"] = props
        beat["prop"] = props[0]["label"]
    return script


def _ease_out_back(x: float) -> float:
    c1, c3 = 1.70158, 2.70158
    x = max(0.0, min(1.0, x))
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def draw_prop(d, prop: dict, local_t: float, beat_remaining: float, cam_zoom: float = 1.0) -> None:
    """Draw one planned prop with entrance + idle + exit animation."""
    t = local_t - prop.get("delay", 0.0)
    if t < 0:
        return
    enter = _ease_out_back(min(1.0, t / 0.35))
    exit_k = max(0.0, min(1.0, beat_remaining / 0.18))
    k = enter * exit_k
    if k <= 0.02:
        return

    x0, y0, base = prop["x"], prop["y"], prop["scale"]
    # Camera Ken Burns zoom around frame center
    x = 540 + (x0 - 540) * cam_zoom
    y = 760 + (y0 - 760) * cam_zoom
    anim = prop.get("anim", "pop")
    if anim == "drop":
        y -= (1 - enter) * 500
    elif anim == "slide_left":
        x -= (1 - enter) * 700
    elif anim == "slide_right":
        x += (1 - enter) * 700
    y += math.sin(t * 3 + x0) * 10  # idle float

    s = base * cam_zoom * (k if anim in ("pop", "spin_in") else exit_k)
    if s < 0.05:
        return

    kind = prop["kind"]
    if kind == "card" or kind not in PROP_LIBRARY:
        draw_card(d, x, y, s, t, prop.get("label", "FACT"))
    else:
        PROP_LIBRARY[kind][0](d, x, y, s, t)
