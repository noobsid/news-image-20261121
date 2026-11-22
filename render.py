#!/usr/bin/env python3
"""Saturday 21 November 2026 - the world's news on one broadsheet page.

Version two of the artwork: every panel is now a small painted scene
instead of a flat glyph. Each scene is rendered on its own supersampled
stage (three times print size, then shrunk with a Lanczos filter), with
gradient skies, shaded buildings, smoke and glow laid in on a separate
translucent sheet, and seeded random detail so the picture is identical
on every run. The words on the page - masthead, figures, headlines,
briefs, date check - are unchanged from the first edition. Build-time
only: the submitted program (main.py) copies the finished entry.png
unchanged.
"""
import math
import os
import random

from PIL import Image, ImageDraw, ImageFont

PAGE = 1024
EDGE = 36                       # outer margin
SPAN = PAGE - 2 * EDGE          # usable width
SS = 3                          # scene supersampling factor
SEED = 20261121

CREAM = (248, 243, 226)
CREAM_DK = (239, 231, 205)
BLACK = (22, 20, 17)
GREY = (96, 90, 76)
CRIMSON = (172, 30, 44)
NAVY = (30, 76, 138)
PINE = (13, 112, 108)
OCHRE = (172, 118, 20)
MOSS = (48, 108, 56)
PLUM = (98, 64, 138)
WHITE = (255, 255, 255)

REGION_INK = {
    "EUROPE": CRIMSON, "ASIA": OCHRE, "AMERICAS": NAVY,
    "MIDDLE EAST": PINE, "AFRICA": MOSS, "OCEANIA": PLUM,
}

FONT_DIR = "/usr/share/fonts/truetype/liberation/"
SERIF = FONT_DIR + "LiberationSerif-Bold.ttf"
SERIF_IT = FONT_DIR + "LiberationSerif-BoldItalic.ttf"
SANS = FONT_DIR + "LiberationSans-Regular.ttf"
SANS_B = FONT_DIR + "LiberationSans-Bold.ttf"
MONO_IT = FONT_DIR + "LiberationMono-BoldItalic.ttf"


def F(path, size):
    return ImageFont.truetype(path, size)


def wrap_copy(d, text, fnt, width):
    """Word-wrap to a pixel width, newspaper style."""
    out, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if d.textlength(trial, font=fnt) <= width:
            line = trial
        else:
            if line:
                out.append(line)
            line = word
    if line:
        out.append(line)
    return out


def clip_line(d, text, fnt, width):
    """Force a single line, cutting with an ellipsis when needed."""
    if d.textlength(text, font=fnt) <= width:
        return text
    while text and d.textlength(text + "…", font=fnt) > width:
        text = text.rsplit(" ", 1)[0] if " " in text else text[:-1]
    return text + "…"


def set_block(d, text, x, y, width, fnt, fill, step, limit):
    """Set a wrapped block of text; return the y just past its last line."""
    for line in wrap_copy(d, text, fnt, width)[:limit]:
        d.text((x, y), line, font=fnt, fill=fill)
        y += step
    return y


# ------------------------------------------------------------ colour maths
def mix(a, b, t):
    """Blend two RGB colours; t=0 gives a, t=1 gives b."""
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def tone(col, f):
    """Scale a colour's brightness by f (f<1 darkens, f>1 lightens)."""
    return tuple(max(0, min(255, int(round(c * f)))) for c in col)


# ------------------------------------------------------------- scene stage
class Stage:
    """One panel's painting, drawn at SS times its printed size.

    Solid work goes on `self.d`; smoke, glow and other translucent work
    goes on `self.od`, a separate sheet composited over the top when the
    scene is finished and shrunk to print size.
    """

    def __init__(self, w, h, rng):
        self.w, self.h = w, h
        self.rng = rng
        self.img = Image.new("RGB", (w * SS, h * SS), WHITE)
        self.d = ImageDraw.Draw(self.img)
        self.sheet = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        self.od = ImageDraw.Draw(self.sheet)

    # -- scaled primitive wrappers (coordinates in printed pixels) --
    def _box(self, box):
        return [v * SS for v in box]

    def _pts(self, pts):
        return [(x * SS, y * SS) for x, y in pts]

    def rect(self, box, fill=None, outline=None, width=1):
        self.d.rectangle(self._box(box), fill=fill, outline=outline,
                         width=max(1, int(width * SS)))

    def line(self, pts, fill, width=1):
        self.d.line(self._pts(pts), fill=fill, width=max(1, int(width * SS)),
                    joint="curve")

    def poly(self, pts, fill, outline=None):
        self.d.polygon(self._pts(pts), fill=fill, outline=outline)

    def disc(self, cx, cy, r, fill, outline=None):
        self.d.ellipse(self._box([cx - r, cy - r, cx + r, cy + r]),
                       fill=fill, outline=outline)

    def oval(self, box, fill=None, outline=None, width=1):
        self.d.ellipse(self._box(box), fill=fill, outline=outline,
                       width=max(1, int(width * SS)))

    def arc(self, box, a0, a1, fill, width=1):
        self.d.arc(self._box(box), a0, a1, fill=fill,
                   width=max(1, int(width * SS)))

    def text(self, xy, s, fnt, fill, anchor=None):
        self.d.text((xy[0] * SS, xy[1] * SS), s, font=fnt, fill=fill,
                    anchor=anchor)

    # -- translucent-sheet primitives --
    def o_disc(self, cx, cy, r, rgba):
        self.od.ellipse(self._box([cx - r, cy - r, cx + r, cy + r]),
                        fill=rgba)

    def o_oval(self, box, rgba):
        self.od.ellipse(self._box(box), fill=rgba)

    def o_poly(self, pts, rgba):
        self.od.polygon(self._pts(pts), fill=rgba)

    def o_line(self, pts, rgba, width=1):
        self.od.line(self._pts(pts), fill=rgba,
                     width=max(1, int(width * SS)), joint="curve")

    # -- shared painting effects --
    def sky(self, top, horizon, split=1.0):
        """Vertical gradient over the top `split` fraction of the scene."""
        rows = int(self.h * SS * split)
        for i in range(rows):
            t = i / max(1, rows - 1)
            self.d.line([0, i, self.w * SS, i], fill=mix(top, horizon, t))

    def fill_below(self, y, top, bottom):
        """Vertical gradient from y to the bottom of the scene."""
        rows = self.h * SS - int(y * SS)
        for i in range(rows):
            t = i / max(1, rows - 1)
            yy = int(y * SS) + i
            self.d.line([0, yy, self.w * SS, yy], fill=mix(top, bottom, t))

    def glow(self, cx, cy, r, col, alpha):
        """Soft radial glow: shrinking translucent discs."""
        steps = 7
        for i in range(steps, 0, -1):
            rr = r * i / steps
            a = int(alpha * (1 - i / (steps + 1)) ** 1.5) + 4
            self.o_disc(cx, cy, rr, col + (a,))

    def smoke(self, cx, cy, n, spread, rise, col, alpha, r0=3.0):
        """A rising plume of overlapping soft puffs."""
        x, y, r = cx, cy, r0
        for i in range(n):
            self.o_disc(x, y, r, col + (alpha,))
            x += self.rng.uniform(-spread, spread) + spread * 0.55
            y -= rise
            r += r0 * 0.45

    def cloud(self, cx, cy, w, col, alpha):
        """A flat-bottomed cloud from overlapping discs."""
        for dx, rr in ((-0.30, 0.30), (-0.10, 0.42), (0.14, 0.38),
                       (0.32, 0.26)):
            self.o_disc(cx + dx * w, cy, rr * w * 0.36, col + (alpha,))
        self.o_oval([cx - 0.42 * w, cy - 4, cx + 0.44 * w, cy + 5],
                    col + (alpha,))

    def windows(self, x, y, w, h, cols, rows, lit, dark, lit_ratio):
        """A grid of windows on a building face; some lit, some dark."""
        cw, ch = w / cols, h / rows
        for i in range(cols):
            for j in range(rows):
                wx = x + i * cw + cw * 0.24
                wy = y + j * ch + ch * 0.26
                col = lit if self.rng.random() < lit_ratio else dark
                self.rect([wx, wy, wx + cw * 0.5, wy + ch * 0.48], fill=col)

    def block(self, x, y, w, h, body, lit_ratio=0.4, cols=None, rows=None):
        """A city building: shaded faces, a parapet, a grid of windows."""
        self.rect([x, y, x + w, y + h], fill=body)
        self.rect([x + w * 0.72, y, x + w, y + h], fill=tone(body, 0.78))
        self.rect([x, y, x + w, y + 2.2], fill=tone(body, 1.18))
        cols = cols or max(2, int(w / 9))
        rows = rows or max(2, int(h / 10))
        self.windows(x + 2, y + 4, w - 4, h - 6, cols, rows,
                     (255, 208, 122), tone(body, 0.55), lit_ratio)

    def sparkle(self, y0, y1, n, col, alpha):
        """Short bright strokes scattered on water."""
        for _ in range(n):
            x = self.rng.uniform(2, self.w - 8)
            y = self.rng.uniform(y0, y1)
            ln = self.rng.uniform(2.5, 6.5)
            self.o_line([(x, y), (x + ln, y)], col + (alpha,), width=0.8)

    def finish(self):
        base = self.img.convert("RGBA")
        base.alpha_composite(self.sheet)
        return base.convert("RGB").resize((self.w, self.h), Image.LANCZOS)


def bezier(p0, p1, p2, n=26):
    """Sample a quadratic Bezier curve into a point list."""
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    return pts


# ------------------------------------------------------------ hero scenes
def sc_bahrain(w, h, ink, rng):
    """Dusk over a coastal air base: hangars, radar, runway, sea in front,
    missile trails arcing in and one strike blooming smoke."""
    s = Stage(w, h, rng)
    s.sky((56, 42, 86), (204, 102, 62), split=0.60)
    s.glow(w * 0.70, h * 0.56, 26, (255, 176, 96), 120)
    s.disc(w * 0.70, h * 0.56, 8.5, (255, 196, 116))
    for gx in (0.12, 0.34, 0.88):                       # far shore hills
        s.poly([(w * gx - 26, h * 0.60), (w * gx, h * 0.47),
                (w * gx + 30, h * 0.60)], fill=(74, 54, 78))
    # base ground and runway
    s.rect([0, h * 0.60, w, h * 0.80], fill=(58, 52, 58))
    for i in range(40):                                 # apron texture
        x, y = rng.uniform(0, w), rng.uniform(h * 0.61, h * 0.79)
        s.line([(x, y), (x + rng.uniform(2, 6), y)], fill=(70, 64, 70),
               width=0.7)
    s.poly([(6, h * 0.79), (w * 0.52, h * 0.63), (w * 0.66, h * 0.63),
            (w * 0.30, h * 0.79)], fill=(38, 36, 42))
    for t in (0.18, 0.42, 0.66, 0.88):                  # runway dashes
        x = 6 + (w * 0.52 - 6) * t + 8
        y = h * 0.79 + (h * 0.63 - h * 0.79) * t
        s.line([(x, y), (x + 7, y - 1.6)], fill=(226, 220, 190), width=1.1)
    # hangars with arched roofs
    for hx, hw in ((14, 52), (76, 44)):
        hy = h * 0.60
        s.rect([hx, hy - 15, hx + hw, hy + 1], fill=(104, 102, 110))
        s.arc([hx, hy - 24, hx + hw, hy - 4], 180, 360, fill=(132, 130, 138),
              width=3.2)
        s.rect([hx, hy - 15, hx + hw, hy - 13.4], fill=(140, 138, 146))
        s.rect([hx + hw * 0.36, hy - 11, hx + hw * 0.64, hy + 1],
               fill=(52, 50, 56))
        s.rect([hx + 5, hy - 9, hx + 10, hy - 4.6], fill=(255, 208, 122))
    # radar tower with dome and sweep bar
    rx = w * 0.60
    s.rect([rx - 3, h * 0.36, rx + 3, h * 0.60], fill=(88, 86, 94))
    s.oval([rx - 10, h * 0.20, rx + 10, h * 0.38], fill=(196, 194, 200))
    s.oval([rx - 10, h * 0.20, rx + 2, h * 0.38], fill=(216, 214, 220))
    s.line([(rx - 12, h * 0.235), (rx + 12, h * 0.215)], fill=(70, 68, 76),
           width=1.8)
    # control tower, lit cab
    tx = w * 0.80
    s.rect([tx - 4.5, h * 0.34, tx + 4.5, h * 0.60], fill=(96, 94, 102))
    s.rect([tx - 8, h * 0.26, tx + 8, h * 0.36], fill=(60, 62, 70))
    s.rect([tx - 6.6, h * 0.28, tx + 6.6, h * 0.335], fill=(255, 214, 130))
    s.line([(tx, h * 0.26), (tx, h * 0.17)], fill=(40, 40, 46), width=1.2)
    s.disc(tx, h * 0.16, 1.4, CRIMSON)
    # parked jets on the apron
    for jx, jy, sc in ((w * 0.36, h * 0.70, 1.0), (w * 0.47, h * 0.745, 0.8)):
        s.poly([(jx - 11 * sc, jy), (jx + 2 * sc, jy - 3.4 * sc),
                (jx + 12 * sc, jy), (jx + 2 * sc, jy + 1.6 * sc)],
               fill=(30, 30, 38))
        s.disc(jx + 3.4 * sc, jy - 1.8 * sc, 1.5 * sc, (150, 190, 220))
    # missile trails arcing in, one impact blooming
    for (x0, bend, x1) in ((w * 0.16, w * 0.34, w * 0.60),
                           (w * 0.30, w * 0.52, w * 0.78),
                           (w * 0.06, w * 0.22, w * 0.40)):
        pts = bezier((x0, -4), (bend, h * 0.16), (x1, h * 0.585))
        for i in range(len(pts) - 1):
            a = int(150 * (i / len(pts)) ** 1.5) + 26
            s.o_line([pts[i], pts[i + 1]], (232, 226, 218, a), width=2.6)
        hx_, hy_ = pts[-1]
        s.glow(hx_, hy_, 7, (255, 150, 70), 170)
        s.disc(hx_, hy_, 2.2, (255, 214, 130))
    s.glow(w * 0.60, h * 0.585, 10, (255, 120, 60), 150)
    s.smoke(w * 0.60, h * 0.56, 6, 2.6, 4.6, (40, 36, 40), 120, r0=3.4)
    # sea in front, with dusk sparkle
    s.fill_below(h * 0.80, (26, 70, 88), (10, 34, 52))
    s.sparkle(h * 0.83, h * 0.97, 30, (255, 190, 120), 120)
    s.sparkle(h * 0.83, h * 0.97, 18, (170, 210, 225), 90)
    for fx in range(4, int(w), 11):                     # perimeter fence
        s.line([(fx, h * 0.795), (fx, h * 0.755)], fill=(24, 24, 30),
               width=0.9)
    return s.finish()


def sc_kryvyi(w, h, ink, rng):
    """A Ukrainian city block under a missile: lit apartment windows, a
    church dome, smoke rising off the struck building."""
    s = Stage(w, h, rng)
    s.sky((66, 80, 102), (172, 176, 182), split=0.78)
    s.cloud(w * 0.22, h * 0.16, 54, (226, 228, 230), 90)
    s.cloud(w * 0.78, h * 0.11, 66, (208, 212, 218), 80)
    for i, (bx, bw, bh) in enumerate(((6, 30, 26), (44, 24, 20),
                                     (238, 26, 22), (268, 22, 28))):
        s.block(bx, h * 0.72 - bh, bw, bh, (128, 138, 152), lit_ratio=0.3)
    # church with an onion dome, left
    cx0 = w * 0.155
    s.rect([cx0 - 11, h * 0.44, cx0 + 11, h * 0.72], fill=(88, 96, 112))
    s.rect([cx0 - 13, h * 0.415, cx0 + 13, h * 0.45], fill=(70, 78, 94))
    s.oval([cx0 - 7.5, h * 0.235, cx0 + 7.5, h * 0.43], fill=(46, 84, 96))
    s.oval([cx0 - 7.5, h * 0.235, cx0, h * 0.43], fill=(58, 102, 114))
    s.line([(cx0, h * 0.235), (cx0, h * 0.175)], fill=(30, 34, 42), width=1.2)
    s.line([(cx0 - 2.6, h * 0.20), (cx0 + 2.6, h * 0.20)], fill=(30, 34, 42),
           width=1.2)
    s.windows(cx0 - 8, h * 0.50, 16, 16, 2, 2, (255, 208, 122),
              (52, 60, 74), 0.5)
    # foreground apartment blocks
    s.block(w * 0.315, h * 0.30, 56, h * 0.44, (104, 112, 128), lit_ratio=0.5)
    s.block(w * 0.545, h * 0.235, 62, h * 0.505, (94, 102, 120), lit_ratio=0.45)
    s.block(w * 0.795, h * 0.345, 52, h * 0.395, (110, 116, 130),
            lit_ratio=0.4)
    # the struck block: blackened corner, fire glow, smoke plume
    sx = w * 0.795
    s.poly([(sx + 34, h * 0.345), (sx + 52, h * 0.345), (sx + 52, h * 0.52),
            (sx + 40, h * 0.47), (sx + 36, h * 0.42)], fill=(34, 32, 34))
    s.glow(sx + 43, h * 0.44, 9, (255, 130, 54), 170)
    s.disc(sx + 43, h * 0.44, 2.4, (255, 196, 110))
    s.smoke(sx + 40, h * 0.33, 8, 3.4, 4.4, (52, 50, 54), 105, r0=4.2)
    # missile streaking down toward it, with a segmented smoke trail
    pts = bezier((w * 0.30, -4), (w * 0.55, h * 0.10), (sx + 40, h * 0.415))
    for i in range(0, len(pts) - 1, 2):
        a = 60 + int(110 * i / len(pts))
        s.o_line([pts[i], pts[i + 1]], (238, 236, 232, a), width=2.2)
    hx_, hy_ = pts[-1]
    s.line([pts[-3], (hx_ + 5, hy_ + 3.4)], fill=(30, 30, 36), width=2.6)
    s.glow(hx_, hy_, 6, (255, 170, 84), 180)
    # street: cars, lamps, bare trees
    s.rect([0, h * 0.74, w, h], fill=(52, 54, 62))
    s.line([(0, h * 0.875), (w, h * 0.875)], fill=(120, 118, 104), width=1)
    for carx, col in ((w * 0.40, (38, 44, 56)), (w * 0.665, (64, 52, 48))):
        s.rect([carx, h * 0.815, carx + 17, h * 0.865], fill=col)
        s.rect([carx + 3.4, h * 0.79, carx + 12.6, h * 0.82],
               fill=tone(col, 1.25))
        s.disc(carx + 4, h * 0.872, 2.1, (16, 16, 20))
        s.disc(carx + 13, h * 0.872, 2.1, (16, 16, 20))
    for tx in (w * 0.06, w * 0.285, w * 0.955):         # bare winter trees
        s.line([(tx, h * 0.99), (tx, h * 0.80)], fill=(28, 28, 34), width=1.6)
        for ang, ln in ((-0.7, 9), (-0.3, 11), (0.25, 10), (0.65, 8)):
            s.line([(tx, h * 0.83), (tx + ln * math.sin(ang),
                    h * 0.83 - ln * math.cos(ang) * 0.62)],
                   fill=(28, 28, 34), width=0.9)
    for lx in (w * 0.21, w * 0.50, w * 0.76):           # street lamps
        s.glow(lx, h * 0.775, 4.6, (255, 205, 120), 130)
    return s.finish()


def sc_wallstreet(w, h, ink, rng):
    """A trading floor at the moment of the rout: skyline behind, a big
    candlestick chart plunging across the board, heads below."""
    s = Stage(w, h, rng)
    s.sky((14, 20, 38), (34, 44, 70), split=1.0)
    for bx, bw, bh, tonef in ((2, 26, 62, 1.0), (30, 20, 46, 0.9),
                              (w - 52, 22, 52, 0.95), (w - 28, 25, 68, 1.0),
                              (w - 76, 18, 38, 0.85)):
        body = tone((26, 34, 54), tonef)
        s.rect([bx, h - bh - 12, bx + bw, h - 12], fill=body)
        s.windows(bx + 2, h - bh - 9, bw - 4, bh - 4, max(2, bw // 8), 5,
                  (255, 214, 140), (16, 22, 36), 0.42)
    # the big board
    bx0, by0, bw_, bh_ = w * 0.185, h * 0.075, w * 0.63, h * 0.72
    s.rect([bx0 - 2, by0 - 2, bx0 + bw_ + 2, by0 + bh_ + 2],
           fill=(96, 118, 152))
    s.rect([bx0, by0, bx0 + bw_, by0 + bh_], fill=(24, 30, 48))
    for i in range(1, 5):                               # gridlines
        gy = by0 + bh_ * i / 5
        s.line([(bx0 + 3, gy), (bx0 + bw_ - 3, gy)], fill=(52, 64, 92),
               width=0.7)
    for i in range(1, 6):
        gx = bx0 + bw_ * i / 6
        s.line([(gx, by0 + 3), (gx, by0 + bh_ - 3)], fill=(44, 56, 82),
               width=0.6)
    # candlesticks on a falling path, then volume bars
    n = 11
    closes = []
    price = 0.16
    for i in range(n):
        cxp = bx0 + 8 + i * (bw_ - 16) / (n - 1)
        drop = 0.045 + 0.028 * (i / n) ** 1.6
        opn, cls = price, price + drop
        col = (64, 204, 128) if i < 3 else (236, 66, 78)
        y_op = by0 + bh_ * 0.66 * opn + 3
        y_cl = by0 + bh_ * 0.66 * cls + 3
        s.line([(cxp, y_op - 3.4), (cxp, y_cl + 3.4)], fill=col, width=1.1)
        s.rect([cxp - 3.1, min(y_op, y_cl), cxp + 3.1, max(y_op, y_cl) + 1.4],
               fill=col)
        closes.append((cxp, y_cl))
        vh = rng.uniform(3, 8) + i * 0.85               # volume swells
        s.rect([cxp - 3.1, by0 + bh_ - vh, cxp + 3.1, by0 + bh_ - 1],
               fill=tone(col, 0.62))
        price = cls
    s.line(closes, fill=(255, 92, 96), width=1.5)
    ax, ay = bx0 + bw_ - 14, by0 + bh_ * 0.60            # the plunge arrow
    s.line([(bx0 + bw_ * 0.52, by0 + 8), (ax, ay)], fill=(255, 70, 80),
           width=2.6)
    s.poly([(ax + 5, ay + 5.4), (ax - 4.4, ay + 2.2), (ax + 1.8, ay - 4.6)],
           fill=(255, 70, 80))
    # trading floor: silhouetted heads and glowing monitors
    s.rect([0, h * 0.845, w, h], fill=(8, 10, 17))
    for i, fx in enumerate((0.07, 0.20, 0.335, 0.63, 0.755, 0.885)):
        fxw = w * fx
        s.disc(fxw, h * 0.905, 4.6, (5, 6, 10))
        s.oval([fxw - 7.4, h * 0.945, fxw + 7.4, h * 1.02], fill=(5, 6, 10))
        mcol = (110, 190, 255) if i % 2 == 0 else (255, 128, 128)
        s.rect([fxw + 6.4, h * 0.885, fxw + 15.4, h * 0.945], fill=(16, 20, 30),
               outline=(70, 84, 110), width=0.7)
        s.rect([fxw + 7.4, h * 0.893, fxw + 14.4, h * 0.928], fill=mcol)
    return s.finish()


# ------------------------------------------------------------- mid scenes
def sc_convoy(w, h, ink, rng):
    """Sinaloa desert: a federal convoy on a mountain road, dust up."""
    s = Stage(w, h, rng)
    s.sky((238, 198, 142), (250, 232, 192), split=0.66)
    s.glow(w * 0.16, h * 0.20, 15, (255, 226, 160), 130)
    s.disc(w * 0.16, h * 0.20, 5.6, (255, 232, 170))
    s.poly([(0, h * 0.52), (w * 0.30, h * 0.30), (w * 0.55, h * 0.52)],
           fill=(178, 140, 110))                        # far ridge
    s.poly([(w * 0.48, h * 0.54), (w * 0.76, h * 0.335), (w, h * 0.54)],
           fill=(150, 108, 80))                         # near ridge
    for rx, ry in ((w * 0.30, h * 0.335), (w * 0.755, h * 0.37)):
        s.line([(rx - 5, ry + 3), (rx, ry - 2), (rx + 5, ry + 3)],
               fill=(236, 214, 180), width=1.1)
    s.fill_below(h * 0.54, (226, 188, 130), (206, 164, 104))
    for _ in range(46):                                 # grit and scrub
        x, y = rng.uniform(0, w), rng.uniform(h * 0.56, h * 0.97)
        s.line([(x, y), (x + rng.uniform(1, 3), y)], fill=(188, 148, 96),
               width=0.7)
    s.poly([(0, h * 0.97), (0, h * 0.74), (w, h * 0.665), (w, h * 0.97)],
           fill=(74, 66, 60))                           # the road
    for t in (0.14, 0.36, 0.58, 0.80):                  # centre dashes
        x = w * t
        y = h * 0.74 + (h * 0.665 - h * 0.74) * t + 6
        s.line([(x, y), (x + 6.5, y - 0.8)], fill=(238, 228, 190), width=1.1)
    def truck(cx, cy, sc, col):
        s.o_oval([cx - 15 * sc, cy - 3 * sc, cx + 2 * sc, cy + 3.4 * sc],
                 (216, 182, 132, 105))                  # dust behind
        s.o_oval([cx - 11 * sc, cy - 5 * sc, cx - 1 * sc, cy + 2 * sc],
                 (222, 190, 140, 80))
        s.rect([cx - 13 * sc, cy - 6.4 * sc, cx + 9 * sc, cy + 1.4 * sc],
               fill=col)
        s.rect([cx - 3 * sc, cy - 10.4 * sc, cx + 6.4 * sc, cy - 6.2 * sc],
               fill=tone(col, 1.12))
        s.rect([cx - 1.6 * sc, cy - 9.8 * sc, cx + 2 * sc, cy - 6.8 * sc],
               fill=(168, 205, 220))
        s.rect([cx + 3.4 * sc, cy - 9.8 * sc, cx + 5.8 * sc, cy - 6.8 * sc],
               fill=(168, 205, 220))
        for wx in (cx - 8.4 * sc, cx + 5.4 * sc):
            s.disc(wx, cy + 1.8 * sc, 2.5 * sc, (22, 22, 24))
            s.disc(wx, cy + 1.8 * sc, 1.1 * sc, (120, 120, 124))
        s.disc(cx + 9.6 * sc, cy - 2.4 * sc, 0.9 * sc, (255, 226, 150))
    truck(w * 0.30, h * 0.755, 1.02, (44, 52, 44))
    truck(w * 0.565, h * 0.715, 0.9, (58, 62, 58))
    truck(w * 0.79, h * 0.685, 0.78, (40, 46, 52))
    gx = w * 0.945                                        # a saguaro
    s.line([(gx, h * 0.97), (gx, h * 0.60)], fill=(52, 106, 62), width=3)
    s.line([(gx, h * 0.74), (gx - 5, h * 0.74), (gx - 5, h * 0.64)],
           fill=(52, 106, 62), width=2.2)
    s.line([(gx, h * 0.79), (gx + 5, h * 0.79), (gx + 5, h * 0.68)],
           fill=(52, 106, 62), width=2.2)
    hx, hy = w * 0.86, h * 0.15                           # helicopter
    s.oval([hx - 6, hy - 2.4, hx + 6, hy + 2.4], fill=(40, 42, 48))
    s.line([(hx - 15, hy - 4.4), (hx + 15, hy - 4.4)], fill=(40, 42, 48),
           width=1.3)
    s.line([(hx + 5, hy), (hx + 12, hy - 2.6)], fill=(40, 42, 48), width=1.4)
    return s.finish()


def sc_signing(w, h, ink, rng):
    """Brussels: two flags, a long table, and the trade chart rising on
    the screen behind the signatories."""
    s = Stage(w, h, rng)
    s.sky((238, 230, 208), (216, 202, 170), split=0.80)
    s.fill_below(h * 0.80, (150, 122, 88), (128, 102, 70))
    sx0, sy0, sw_, sh_ = w * 0.335, h * 0.10, w * 0.33, h * 0.46
    s.rect([sx0, sy0, sx0 + sw_, sy0 + sh_], fill=(26, 40, 66),
           outline=(120, 110, 88), width=1.2)
    pts = [(sx0 + 5, sy0 + sh_ - 6), (sx0 + sw_ * 0.38, sy0 + sh_ * 0.58),
           (sx0 + sw_ * 0.62, sy0 + sh_ * 0.62), (sx0 + sw_ - 6, sy0 + 6)]
    s.line(pts, fill=(84, 220, 140), width=1.7)
    s.poly([(sx0 + sw_ - 6, sy0 + 6), (sx0 + sw_ - 12.5, sy0 + 7.6),
            (sx0 + sw_ - 7.2, sy0 + 12.5)], fill=(84, 220, 140))
    for gx in (0.25, 0.5, 0.75):
        s.line([(sx0 + sw_ * gx, sy0 + 3), (sx0 + sw_ * gx, sy0 + sh_ - 3)],
               fill=(52, 68, 98), width=0.6)
    # flags: the EU circle of stars, Indonesia's red over white
    for fx, kind in ((w * 0.115, "eu"), (w * 0.845, "id")):
        s.line([(fx, h * 0.08), (fx, h * 0.66)], fill=(70, 62, 50), width=1.6)
        s.disc(fx, h * 0.065, 1.5, (196, 160, 84))
        fw, fh = w * 0.155, h * 0.30
        if kind == "eu":
            s.poly([(fx, h * 0.09), (fx + fw, h * 0.13), (fx + fw, h * 0.09 + fh),
                    (fx, h * 0.09 + fh)], fill=(32, 62, 148))
            for i in range(8):
                a = 2 * math.pi * i / 8
                s.disc(fx + fw * 0.5 + fw * 0.27 * math.cos(a),
                       h * 0.09 + fh * 0.5 + fh * 0.27 * math.sin(a), 1.05,
                       (250, 205, 60))
        else:
            s.poly([(fx, h * 0.09), (fx + fw, h * 0.13), (fx + fw,
                    h * 0.09 + fh * 0.5), (fx, h * 0.09 + fh * 0.5)],
                   fill=(206, 40, 48))
            s.poly([(fx, h * 0.09 + fh * 0.5), (fx + fw, h * 0.09 + fh * 0.5),
                    (fx + fw, h * 0.09 + fh), (fx, h * 0.09 + fh)],
                   fill=(246, 246, 244))
    # the long table and three signatories
    ty = h * 0.665
    s.poly([(w * 0.13, ty), (w * 0.87, ty), (w * 0.815, h * 0.94),
            (w * 0.185, h * 0.94)], fill=(104, 74, 48))
    s.poly([(w * 0.13, ty), (w * 0.87, ty), (w * 0.845, ty + 4.6),
            (w * 0.155, ty + 4.6)], fill=(140, 104, 66))
    for fx in (0.315, 0.50, 0.685):
        cxp = w * fx
        s.disc(cxp, ty - 8.6, 4.3, (40, 36, 34))
        s.oval([cxp - 7.6, ty - 5.4, cxp + 7.6, ty + 1.6], fill=(40, 36, 34))
        s.rect([cxp - 6.6, ty + 2.2, cxp + 6.6, ty + 7.6], fill=(248, 246, 240))
        s.disc(cxp + 3.6, ty + 4.8, 0.85, CRIMSON)
    for px in (w * 0.075, w * 0.905):                     # plant pots
        s.poly([(px - 4.6, h * 0.90), (px + 4.6, h * 0.90), (px + 3.2, h),
                (px - 3.2, h)], fill=(150, 84, 52))
        for ang in (-0.6, -0.2, 0.25, 0.6):
            s.line([(px, h * 0.90), (px + 6 * math.sin(ang),
                    h * 0.90 - 6.6 * math.cos(ang))], fill=(52, 116, 62),
                   width=1.2)
    return s.finish()


def sc_cop(w, h, ink, rng):
    """Antalya: a conference hall built around a great globe, delegates
    in arcs beneath it, deadlock in the air."""
    s = Stage(w, h, rng)
    s.sky((240, 233, 210), (208, 198, 170), split=1.0)
    s.glow(w / 2, h * 0.30, 40, (255, 244, 200), 60)
    gx, gy, gr = w / 2, h * 0.335, h * 0.265
    s.disc(gx, gy, gr, (172, 205, 226))
    s.oval([gx - gr * 0.42, gy - gr, gx + gr * 0.42, gy + gr],
           outline=(70, 110, 150), width=1.1)
    s.oval([gx - gr, gy - gr * 0.42, gx + gr, gy + gr * 0.42],
           outline=(70, 110, 150), width=1.1)
    s.line([(gx - gr, gy), (gx + gr, gy)], fill=(70, 110, 150), width=1)
    for bx, by, br, col in ((-0.52, -0.34, 0.30, (96, 152, 96)),
                            (0.30, -0.10, 0.34, (104, 158, 92)),
                            (-0.18, 0.38, 0.26, (196, 172, 110)),
                            (0.52, 0.42, 0.20, (96, 152, 96))):
        s.disc(gx + bx * gr, gy + by * gr, br * gr, col)
    s.oval([gx - gr, gy - gr, gx + gr, gy + gr], outline=(52, 88, 128),
           width=1.7)
    s.arc([gx - gr * 1.5, gy + gr * 0.52, gx + gr * 1.5, gy + gr * 1.9],
          200, 340, fill=(120, 100, 70), width=2.2)
    for sx_ in (w * 0.085, w * 0.845):                    # side screens
        s.rect([sx_, h * 0.16, sx_ + w * 0.115, h * 0.42], fill=(30, 44, 60))
        s.disc(sx_ + w * 0.057, h * 0.29, 5.2, (84, 190, 110))
        s.line([(sx_ + w * 0.057, h * 0.29), (sx_ + w * 0.057, h * 0.225)],
               fill=(84, 190, 110), width=1.2)
    for row, (ry, cnt, sc) in enumerate(((0.60, 9, 0.8), (0.735, 11, 0.95),
                                         (0.885, 13, 1.1))):
        for i in range(cnt):
            cxp = w * (0.5 + (i - (cnt - 1) / 2) * 0.062 * sc)
            s.rect([cxp - 5.6 * sc, h * ry, cxp + 5.6 * sc, h * ry + 5 * sc],
                   fill=(128, 100, 68) if row < 2 else (110, 84, 56))
            s.disc(cxp, h * ry - 2.2 * sc, 2.1 * sc, (52, 46, 42))
            s.rect([cxp - 2.4 * sc, h * ry + 1.2 * sc, cxp + 2.4 * sc,
                    h * ry + 2.8 * sc], fill=(238, 234, 220))
    return s.finish()


def sc_hormuz(w, h, ink, rng):
    """The strait at first light: headlands either side, two tankers in
    the channel, a flare of trouble off the second one's bow."""
    s = Stage(w, h, rng)
    s.sky((206, 224, 234), (242, 238, 218), split=0.52)
    s.glow(w * 0.80, h * 0.20, 16, (255, 230, 170), 120)
    s.disc(w * 0.80, h * 0.20, 5, (255, 236, 180))
    s.poly([(0, h * 0.52), (0, h * 0.30), (w * 0.13, h * 0.20),
            (w * 0.235, h * 0.52)], fill=(104, 96, 88))
    s.poly([(w, h * 0.52), (w, h * 0.26), (w * 0.90, h * 0.17),
            (w * 0.815, h * 0.52)], fill=(96, 88, 82))
    for hx in (w * 0.05, w * 0.10, w * 0.93):
        s.line([(hx, h * 0.36), (hx + 7, h * 0.315)], fill=(140, 130, 118),
               width=1)
    s.fill_below(h * 0.52, (44, 104, 136), (20, 56, 88))
    for _ in range(30):
        x, y = rng.uniform(2, w - 8), rng.uniform(h * 0.56, h * 0.95)
        s.o_line([(x, y), (x + rng.uniform(3, 7), y)], (150, 198, 220, 110),
                 width=0.8)
    def tanker(cx, cy, sc, flip):
        hull = (58, 40, 40)
        s.poly([(cx - 26 * sc, cy - 3 * sc), (cx + 22 * sc, cy - 3 * sc),
                (cx + 26 * sc, cy + 1 * sc), (cx + 20 * sc, cy + 5.4 * sc),
                (cx - 22 * sc, cy + 5.4 * sc), (cx - 26 * sc, cy + 1 * sc)],
               fill=hull)
        s.rect([cx - 26 * sc, cy + 1.4 * sc, cx + 22.5 * sc, cy + 3 * sc],
               fill=(128, 48, 42))
        s.line([(cx - 25 * sc, cy - 3 * sc), (cx + 23 * sc, cy - 3 * sc)],
               fill=(30, 26, 26), width=1.1 * sc)
        cols = [(186, 84, 52), (52, 96, 160), (70, 140, 96), (186, 140, 52)]
        for i in range(4):                              # container stacks
            for j in range(2):
                s.rect([cx + (-19 + i * 8.6) * sc, cy - (6.6 + j * 3.2) * sc,
                        cx + (-11 + i * 8.6) * sc, cy - (3.6 + j * 3.2) * sc],
                       fill=cols[(i + j) % 4])
        sx_ = cx + (19 if flip else -19) * sc           # superstructure
        s.rect([sx_ - 4.6 * sc, cy - 12.6 * sc, sx_ + 4.6 * sc, cy - 3 * sc],
               fill=(232, 230, 224))
        s.windows(sx_ - 3.6 * sc, cy - 11.8 * sc, 7.2 * sc, 5.4 * sc, 3, 2,
                  (255, 208, 122), (70, 80, 92), 0.6)
        s.rect([sx_ - 1.5 * sc, cy - 15.6 * sc, sx_ + 1.5 * sc,
                cy - 12.6 * sc], fill=(40, 40, 44))
        s.smoke(sx_, cy - 16.6 * sc, 4, 1.6, 2.6, (210, 210, 212), 110,
                r0=1.7 * sc)
        for t in (0.3, 0.6, 0.9):                       # bow wake
            wx = cx - (27 + 7 * t) * sc * (1 if flip else -1)
            s.o_line([(wx, cy + 4.6 * sc), (wx + 5 * sc * (1 if flip else -1),
                       cy + 4.6 * sc)], (220, 238, 244, 130), width=0.9)
    tanker(w * 0.335, h * 0.60, 1.0, False)
    tanker(w * 0.755, h * 0.565, 0.72, True)
    s.glow(w * 0.755 - 21, h * 0.575, 6.5, (255, 140, 60), 170)   # the flare
    s.disc(w * 0.755 - 21, h * 0.575, 1.7, (255, 200, 120))
    s.smoke(w * 0.755 - 21, h * 0.55, 4, 1.8, 3.0, (60, 56, 56), 110, r0=2.0)
    for gx, gy in ((w * 0.42, h * 0.14), (w * 0.52, h * 0.10)):
        s.arc([gx - 3.4, gy - 2, gx, gy + 2], 200, 330, fill=(70, 80, 88),
              width=1)
        s.arc([gx, gy - 2, gx + 3.4, gy + 2], 210, 340, fill=(70, 80, 88),
              width=1)
    return s.finish()


def sc_shenzhen(w, h, ink, rng):
    """Dusk skyline behind a summit table: three flags, three chairs,
    and the fallout still to come."""
    s = Stage(w, h, rng)
    s.sky((62, 68, 118), (216, 138, 94), split=0.74)
    towers = ((4, 30, 34), (30, 18, 24), (52, 24, 42), (80, 16, 28),
              (100, 26, 36), (130, 18, 26), (148, 15, 32))
    for bx, bw, bh in towers:
        body = (36, 40, 60)
        s.rect([bx, h * 0.74 - bh, bx + bw, h * 0.74], fill=body)
        s.windows(bx + 1.6, h * 0.74 - bh + 2.4, bw - 3.2, bh - 4, 3, 4,
                  (255, 206, 128), (22, 26, 40), 0.5)
        s.disc(bx + bw / 2, h * 0.74 - bh - 1.6, 1.05, (255, 84, 84))
    s.poly([(w * 0.435, h * 0.74), (w * 0.475, h * 0.16), (w * 0.50, h * 0.16),
            (w * 0.525, h * 0.74)], fill=(30, 34, 52))  # the tapered tower
    s.windows(w * 0.462, h * 0.30, w * 0.045, h * 0.40, 1, 6,
              (255, 206, 128), (20, 24, 38), 0.55)
    s.disc(w * 0.487, h * 0.135, 1.2, (255, 84, 84))
    s.fill_below(h * 0.74, (52, 46, 58), (38, 34, 46))
    ty = h * 0.815
    s.poly([(w * 0.10, ty), (w * 0.90, ty), (w * 0.85, h * 0.985),
            (w * 0.15, h * 0.985)], fill=(26, 24, 34))
    s.poly([(w * 0.10, ty), (w * 0.90, ty), (w * 0.875, ty + 3.6),
            (w * 0.125, ty + 3.6)], fill=(52, 48, 62))
    for fx, col in ((0.315, CRIMSON), (0.50, OCHRE), (0.685, NAVY)):
        cxp = w * fx
        s.disc(cxp, ty - 7.8, 4.0, (16, 15, 22))
        s.oval([cxp - 7.0, ty - 4.8, cxp + 7.0, ty + 1.8], fill=(16, 15, 22))
        s.line([(cxp + 8.6, ty + 1), (cxp + 8.6, ty - 8.6)],
               fill=(150, 148, 140), width=0.9)
        s.poly([(cxp + 8.6, ty - 8.6), (cxp + 15.6, ty - 6.6),
                (cxp + 8.6, ty - 4.6)], fill=col)
        s.rect([cxp - 3.2, ty + 2.4, cxp + 3.2, ty + 5.0],
               fill=(236, 232, 218))
    return s.finish()


# ----------------------------------------------------------- small scenes
def sc_embassy(w, h, ink, rng):
    """Copenhagen: an embassy facade, its flag coming down the pole, a
    placard at the gate with one word on it."""
    s = Stage(w, h, rng)
    s.sky((164, 170, 178), (208, 209, 208), split=0.86)
    bx0, bw_ = w * 0.16, w * 0.56
    s.rect([bx0, h * 0.26, bx0 + bw_, h * 0.88], fill=(198, 190, 172))
    s.rect([bx0, h * 0.26, bx0 + bw_, h * 0.315], fill=(172, 162, 144))
    s.poly([(bx0 - 4, h * 0.26), (bx0 + bw_ / 2, h * 0.075),
            (bx0 + bw_ + 4, h * 0.26)], fill=(120, 112, 98))
    for i in range(5):                                  # pilasters
        px = bx0 + 5 + i * (bw_ - 8) / 4
        s.rect([px - 1.3, h * 0.33, px + 1.3, h * 0.88], fill=(178, 168, 148))
    s.windows(bx0 + 6, h * 0.38, bw_ - 12, h * 0.30, 4, 1, (96, 104, 116),
              (70, 76, 88), 0.0)
    s.rect([bx0 + bw_ / 2 - 4.4, h * 0.60, bx0 + bw_ / 2 + 4.4, h * 0.88],
           fill=(58, 54, 50))
    s.oval([bx0 + bw_ / 2 - 5.6, h * 0.545, bx0 + bw_ / 2 + 5.6, h * 0.65],
           outline=(150, 140, 122), width=1.1)
    fx = w * 0.845                                        # the flag, lowered
    s.line([(fx, h * 0.06), (fx, h * 0.88)], fill=(52, 50, 48), width=1.5)
    s.disc(fx, h * 0.045, 1.5, (170, 148, 92))
    fy = h * 0.44
    s.poly([(fx, fy), (fx + 17, fy + 2.2), (fx + 17, fy + 5.6),
            (fx, fy + 4.2)], fill=(238, 238, 236))
    s.poly([(fx, fy + 4.2), (fx + 17, fy + 5.6), (fx + 17, fy + 8.8),
            (fx, fy + 7.4)], fill=(44, 74, 140))
    s.poly([(fx, fy + 7.4), (fx + 17, fy + 8.8), (fx + 17, fy + 12.2),
            (fx, fy + 10.6)], fill=(198, 44, 52))
    s.line([(fx, fy + 12.6), (fx - 3.4, h * 0.90)], fill=(90, 86, 80),
           width=0.8)                                   # the lowering rope
    s.rect([0, h * 0.88, w, h], fill=(96, 94, 90))      # gate rail
    for gx in range(3, int(w), 10):
        s.line([(gx, h * 0.88), (gx, h * 0.97)], fill=(52, 50, 48), width=1)
    s.rect([w * 0.035, h * 0.60, w * 0.035 + 47, h * 0.60 + 13.5],
           fill=CREAM, outline=ink, width=1.1)          # the placard
    s.text((w * 0.035 + 23.5, h * 0.60 + 6.75), "EXPELLED",
           F(SERIF, int(8.6 * SS)), ink, anchor="mm")
    return s.finish()


def sc_chalkboard(w, h, ink, rng):
    """A chalkboard after a breakthrough: zeta functions, a claimed
    proof, and the countdown chalked large - six weeks."""
    s = Stage(w, h, rng)
    s.sky((38, 72, 58), (28, 54, 44), split=1.0)
    s.rect([0, 0, w, h], outline=(118, 84, 54), width=2.6)   # wooden frame
    s.rect([2.6, 2.6, w - 2.6, h - 2.6], outline=(86, 60, 38), width=0.8)
    for _ in range(7):                                  # chalk dust smudges
        sx_ = rng.uniform(0, w - 46)
        sy_ = rng.uniform(0, h - 15)
        s.o_oval([sx_, sy_, sx_ + rng.uniform(24, 44),
                  sy_ + rng.uniform(8, 14)], (240, 240, 235, 26))
    chalk = (238, 240, 234)
    s.text((8, 5.5), "6 WEEKS", F(SERIF, int(14.5 * SS)), chalk)
    s.line([(8, 15.2), (58, 14.8)], fill=chalk, width=1.2)
    s.line([(57, 7), (60, 10.5), (65, 3.4)], fill=chalk, width=1.2)  # a tick
    eqs = ["ζ(s) = Σ n^-s", "π(x) ~ x/ln x", "Re(s) = 1/2",
           "L(χ, s) ≠ 0", "ζ(1/2+it) = 0 ?"]
    for i, eq in enumerate(eqs):
        s.text((72, 3.8 + i * 6.1), eq, F(MONO_IT, int(7.4 * SS)),
               (214, 220, 212))
    for i in range(8):                                  # scribbled working
        x = 126 + rng.uniform(0, 12)
        y = 6 + i * 3.9 + rng.uniform(0, 1.4)
        s.o_line([(x, y), (x + rng.uniform(9, 21), y + rng.uniform(-1, 1))],
                 (220, 226, 218, 130), width=0.7)
    s.rect([w - 34, h - 6.4, w - 15, h - 3.2], fill=(52, 46, 42))  # eraser
    s.rect([w - 34, h - 6.4, w - 15, h - 5.2], fill=(150, 140, 128))
    s.rect([10, h - 5.2, 24, h - 3.6], fill=(240, 240, 236))       # chalk
    s.rect([27, h - 5.0, 36, h - 3.8], fill=(240, 240, 236))
    return s.finish()


def sc_council(w, h, ink, rng):
    """The Security Council horseshoe: arcs of desks and delegates
    under the emblem, a nameplate out front."""
    s = Stage(w, h, rng)
    s.sky((28, 50, 94), (46, 76, 130), split=1.0)
    gx, gy = w / 2, h * 0.30
    s.oval([gx - 7, gy - 7, gx + 7, gy + 7], outline=(206, 220, 240),
           width=1.1)
    s.disc(gx, gy, 2.2, (206, 220, 240))
    for a in (-0.9, -0.45, 0, 0.45, 0.9):
        s.line([(gx, gy - 6.4), (gx + 6.4 * math.sin(a), gy - 6.4 *
                math.cos(a) + 1.6)], fill=(206, 220, 240), width=0.7)
    for r, col, wd in ((15.5, (150, 112, 72), 4.6), (21.5, (128, 94, 58), 5.2)):
        s.arc([w / 2 - r * 1.9, h * 0.86 - r, w / 2 + r * 1.9, h * 0.86 + r],
              180, 360, fill=col, width=wd)
    for i in range(13):                                 # delegates on the arc
        a = math.pi + (i / 12) * math.pi
        for r in (15.5, 21.5):
            cxp = w / 2 + r * 1.9 * math.cos(a)
            cyp = h * 0.86 + r * math.sin(a)
            s.disc(cxp, cyp - 2.6, 1.65, (238, 226, 205))
            s.rect([cxp - 1.9, cyp - 0.6, cxp + 1.9, cyp + 0.9],
                   fill=(240, 238, 230))
    s.oval([w / 2 - 12, h * 0.56, w / 2 + 12, h * 0.82], fill=(58, 88, 140))
    s.rect([w / 2 - 13.5, h - 9.8, w / 2 + 13.5, h - 0.6],
           fill=(16, 30, 58), outline=(150, 170, 200), width=0.9)
    s.text((w / 2, h - 5.2), "UNSC", F(SERIF, int(8.6 * SS)),
           (232, 238, 246), anchor="mm")
    return s.finish()


def sc_port(w, h, ink, rng):
    """Hodeidah: gantry cranes over a container ship, and the port's
    name painted large on a foreground box."""
    s = Stage(w, h, rng)
    s.sky((196, 220, 228), (238, 234, 208), split=0.58)
    s.fill_below(h * 0.58, (40, 110, 122), (24, 72, 88))
    for _ in range(14):
        x, y = rng.uniform(2, w - 8), rng.uniform(h * 0.62, h * 0.96)
        s.o_line([(x, y), (x + rng.uniform(3, 6), y)], (170, 216, 220, 110),
                 width=0.8)
    s.rect([0, h * 0.545, w * 0.62, h * 0.60], fill=(110, 100, 88))  # quay
    hx0 = w * 0.03                                        # the ship
    s.poly([(hx0, h * 0.475), (hx0 + w * 0.46, h * 0.475),
            (hx0 + w * 0.415, h * 0.565), (hx0 + w * 0.045, h * 0.565)],
           fill=(44, 46, 52))
    s.rect([hx0, h * 0.515, hx0 + w * 0.44, h * 0.54], fill=(140, 52, 46))
    cols = [(198, 84, 52), (52, 100, 168), (72, 148, 100), (206, 148, 54),
            (120, 84, 160)]
    for i in range(5):
        for j in range(2):
            s.rect([hx0 + 5 + i * 13.4, h * 0.475 - 6.4 - j * 6.2,
                    hx0 + 16.6 + i * 13.4, h * 0.475 - 0.6 - j * 6.2],
                   fill=cols[(i + j * 2) % 5])
    s.rect([hx0 + w * 0.40, h * 0.475 - 12.6, hx0 + w * 0.455, h * 0.475],
           fill=(228, 226, 220))
    for cxx in (w * 0.155, w * 0.375):                     # gantry cranes
        s.line([(cxx - 9, h * 0.545), (cxx - 9, h * 0.10)], fill=(70, 76, 84),
               width=1.7)
        s.line([(cxx + 9, h * 0.545), (cxx + 9, h * 0.10)], fill=(70, 76, 84),
               width=1.7)
        s.line([(cxx - 13, h * 0.10), (cxx + 15, h * 0.10)], fill=(70, 76, 84),
               width=1.9)
        s.line([(cxx - 9, h * 0.30), (cxx + 9, h * 0.10)], fill=(70, 76, 84),
               width=0.8)
        s.line([(cxx + 9, h * 0.30), (cxx - 9, h * 0.10)], fill=(70, 76, 84),
               width=0.8)
    s.line([(w * 0.155 + 4, h * 0.10), (w * 0.155 + 4, h * 0.245)],
           fill=(52, 56, 62), width=0.9)                  # a box mid-lift
    s.rect([w * 0.155 - 1.5, h * 0.245, w * 0.155 + 9.5, h * 0.245 + 6.2],
           fill=(206, 148, 54))
    bx0, by0 = w * 0.665, h * 0.475                        # foreground stack
    s.rect([bx0, by0, bx0 + 52, by0 + 9.2], fill=(172, 34, 46))
    s.rect([bx0, by0 + 10.2, bx0 + 52, by0 + 19.4], fill=(52, 100, 168))
    s.rect([bx0 + 3, by0 + 1.8, bx0 + 49, by0 + 7.4], outline=(240, 220, 220),
           width=0.8)
    s.text((bx0 + 26, by0 + 4.6), "HODEIDAH", F(SERIF, int(8.8 * SS)),
           (248, 244, 238), anchor="mm")
    return s.finish()


def sc_mosquito(w, h, ink, rng):
    """Brazil after dark: a giant bacteria-laden mosquito over the
    rooftops, microbes drifting, a specimen tag tied to one wing."""
    s = Stage(w, h, rng)
    s.sky((22, 32, 44), (54, 68, 60), split=0.80)
    for _ in range(16):                                   # stars
        s.disc(rng.uniform(2, w - 2), rng.uniform(1, h * 0.4),
               rng.uniform(0.4, 0.8), (220, 228, 220))
    s.glow(w * 0.86, h * 0.20, 9, (240, 240, 210), 90)
    s.disc(w * 0.86, h * 0.20, 3.6, (240, 240, 214))
    s.disc(w * 0.845, h * 0.185, 3.3, (22, 32, 44))
    blocks = ((0, 14, 15), (16, 10, 11), (28, 16, 18), (46, 11, 12),
              (118, 13, 14), (133, 17, 17), (152, 12, 12))
    for bx, bw, bh in blocks:                             # the rooftops
        s.rect([bx, h - bh, bx + bw, h], fill=(14, 18, 24))
        s.windows(bx + 1.4, h - bh + 2, bw - 2.8, bh - 3, 2, 2,
                  (255, 206, 120), (10, 13, 18), 0.4)
    cx, cy = w * 0.40, h * 0.46                             # the mosquito
    s.o_poly([(cx - 4, cy - 6), (cx + 26, cy - 17), (cx + 30, cy - 8),
              (cx + 2, cy - 1)], (235, 240, 238, 120))    # far wing
    s.oval([cx - 24, cy - 4.4, cx + 2, cy + 4.4], fill=(30, 34, 30))
    for i in range(4):                                    # abdomen banding
        s.arc([cx - 24 + i * 6.2, cy - 4.4, cx - 17 + i * 6.2, cy + 4.4],
              90, 270, fill=(120, 128, 110), width=1)
    s.disc(cx + 4.5, cy - 0.6, 5.4, (38, 42, 38))         # thorax
    s.disc(cx + 11.6, cy - 2.2, 3.6, (26, 29, 26))        # head
    s.disc(cx + 12.8, cy - 3.4, 1.6, (214, 52, 52))       # the red eye
    s.line([(cx + 14.6, cy - 1.2), (cx + 30, cy + 5.2)], fill=(20, 22, 20),
           width=1.15)                                    # proboscis
    s.line([(cx + 13.4, cy - 5.2), (cx + 20, cy - 11.4)], fill=(20, 22, 20),
           width=0.8)                                     # antenna
    s.o_poly([(cx - 2, cy - 5), (cx - 22, cy - 19), (cx - 14, cy - 21),
              (cx + 4, cy - 7)], (240, 244, 240, 150))    # near wing
    for lx, bend in ((cx - 8, 1), (cx + 1, -1), (cx + 8, 1)):   # legs
        s.line([(lx, cy + 3.4), (lx + 4.4 * bend, cy + 9.6),
                (lx + 2.2 * bend, cy + 15.6)], fill=(22, 24, 22), width=1)
    for bx, by, br in ((w * 0.63, h * 0.30, 3.4), (w * 0.71, h * 0.55, 2.6),
                       (w * 0.575, h * 0.62, 2.2)):       # bacteria motifs
        s.disc(bx, by, br, (96, 178, 104))
        for i in range(6):
            a = 2 * math.pi * i / 6 + bx
            s.line([(bx + br * math.cos(a), by + br * math.sin(a)),
                    (bx + (br + 2.2) * math.cos(a),
                     by + (br + 2.2) * math.sin(a))], fill=(96, 178, 104),
                   width=0.9)
            s.disc(bx + (br + 2.6) * math.cos(a), by + (br + 2.6) *
                   math.sin(a), 0.8, (96, 178, 104))
    s.line([(cx - 15, cy - 19.6), (w * 0.755, h * 0.13)], fill=(200, 196, 180),
           width=0.7)                                     # the tag's string
    s.rect([w * 0.755, h * 0.115, w * 0.755 + 40, h * 0.115 + 11.6],
           fill=CREAM, outline=ink, width=1.0)
    s.text((w * 0.755 + 20, h * 0.115 + 5.8), "BACTERIA",
           F(SERIF, int(7.8 * SS)), ink, anchor="mm")
    return s.finish()


SCENES = {
    "bases": sc_bahrain, "missile": sc_kryvyi, "chart-down": sc_wallstreet,
    "cuffs": sc_convoy, "handshake": sc_signing, "globe": sc_cop,
    "tanker": sc_hormuz, "summit": sc_shenzhen, "embassy": sc_embassy,
    "chalk": sc_chalkboard, "council": sc_council, "port": sc_port,
    "mosquito": sc_mosquito,
}


# ------------------------------------------------------------------ ledger
FIGURES = [  # (figure, caption) - Saturday in six numbers
    ("2", "US bases in Bahrain Iran says its Guards struck"),
    ("2", "killed as a missile hits Kryvyi Rih, Zelensky's home town"),
    ("11", "dead in Sinaloa violence after the cartel arrest"),
    ("98.5%", "of EU tariffs the Indonesia trade deal removes"),
    ("$1tn", "the Gulf states' estimated losses from the Iran war"),
    ("-10%", "Wall Street's slide into correction in the AI sell-off"),
]
REGION_TALLY = [("EUROPE", 10), ("AMERICAS", 11), ("MIDDLE EAST", 6),
                ("ASIA", 5), ("AFRICA", 3), ("OCEANIA", 1)]
LEADS = [
    {"region": "MIDDLE EAST", "art": "bases", "src": "Al Jazeera",
     "headline": "Iran strikes US bases in Bahrain",
     "body": "The Revolutionary Guards say they hit al-Riffa and Awali; "
             "Manama reports a fire at a civilian industrial plant."},
    {"region": "EUROPE", "art": "missile", "src": "OneTurn",
     "headline": "Missile hits Zelensky's home town",
     "body": "A Russian ballistic missile struck central Kryvyi Rih, "
             "killing two people and wounding dozens on Saturday."},
    {"region": "AMERICAS", "art": "chart-down", "src": "UPI",
     "headline": "AI sell-off tips Wall Street into correction",
     "body": "The S&P 500 and Dow enter correction and the Nasdaq wipes "
             "out its 2026 gains as Anthropic's IPO stumbles."},
]
MIDS = [
    {"region": "AMERICAS", "art": "cuffs", "src": "BBC",
     "headline": "Mexico seizes FBI most-wanted cartel boss",
     "body": "Seized in Guasave; the violence that followed kills 11."},
    {"region": "ASIA", "art": "handshake", "src": "France 24",
     "headline": "EU and Indonesia sign their trade deal",
     "body": "Brussels signing ends ten years of talks; 98.5% of tariffs go."},
    {"region": "EUROPE", "art": "globe", "src": "OneTurn",
     "headline": "COP31 deadlocked over fossil fuels",
     "body": "Phase-out fight leaves Antalya talks stuck on the final text."},
    {"region": "MIDDLE EAST", "art": "tanker", "src": "UKMTO",
     "headline": "Two tankers hit near the Hormuz strait",
     "body": "Two tanker incidents logged near Oman; Tehran blames a mine."},
    {"region": "ASIA", "art": "summit", "src": "BBC",
     "headline": "Shenzhen fallout: Trump defends Putin",
     "body": "Trump backs Putin ties; Zelensky calls him 'a killer'."},
]
SMALLS = [
    {"region": "EUROPE", "art": "embassy", "stat": "EXPELLED",
     "headline": "Denmark expels Russian envoy over rapper plot"},
    {"region": "AMERICAS", "art": "chalk", "stat": "6 WEEKS",
     "headline": "AI-aided Riemann proof claimed at Anthropic"},
    {"region": "ASIA", "art": "council", "stat": "UNSC",
     "headline": "France seeks UN action on Myanmar ruling"},
    {"region": "MIDDLE EAST", "art": "port", "stat": "HODEIDAH",
     "headline": "Houthis hit Saudi Arabia after Hodeidah strike"},
    {"region": "AMERICAS", "art": "mosquito", "stat": "BACTERIA",
     "headline": "Bacteria mosquitoes cut child dengue in Brazil"},
]
BRIEFS = [
    (14, "EUROPE", "CERN reports first evidence of an ultra-rare particle decay"),
    (15, "EUROPE", "French officers sentenced over the Zecler beating in Paris"),
    (16, "AMERICAS", "Man convicted of starting the 2025 Palisades fire in LA"),
    (17, "AMERICAS", "FBI probes apparent hack of its criminal-justice database"),
    (18, "AMERICAS", "Rackspace breach exposes customers' Kubernetes secrets"),
    (19, "EUROPE", "Finland probes suspected Russian helicopter airspace breach"),
    (20, "MIDDLE EAST", "Fire at Basra power station kills four, injures 35"),
    (21, "MIDDLE EAST", "Lebanon's president demands Israel quit the south"),
    (22, "AFRICA", "Nigeria recovers 24 bodies after a boat capsize"),
    (23, "AFRICA", "ANC fights to hold on to South Africa's big cities"),
    (24, "AFRICA", "Chad closes its border with Sudan"),
    (25, "ASIA", "Nepal's PM Shah makes his first visit to India"),
    (26, "ASIA", "Manila hosts Quad, ASEAN-India and East Asia summits"),
    (27, "EUROPE", "EU floats a €1.78tn budget with a Big Tech tax"),
    (28, "EUROPE", "Sweden and France hold first joint nuclear drill"),
    (29, "EUROPE", "Geneva talks keep work on 'killer robot' rules alive"),
    (30, "AMERICAS", "Bolsonaro in intensive care with bowel obstruction"),
    (31, "AMERICAS", "Trump opens the Pacific seabed to deep-sea mining"),
    (32, "AMERICAS", "New York's Mamdani vows to close Rikers by 2032"),
    (33, "AMERICAS", "US declassifies more UFO footage from the Middle East"),
    (34, "MIDDLE EAST", "New fossil carnivore unearthed in the Emirates"),
    (35, "EUROPE", "Norway fells Trafalgar Square's Christmas tree"),
    (36, "OCEANIA", "Australia: former MP Fred Nile dies at 92"),
]
DATE_CHECK = ("Checked before printing: the missiles that fell in Poland "
              "and Cyclone Akvan's landfall belong to Friday 20 November, "
              "so Poland appears here only as Saturday's NATO fallout; "
              "the Peru quake reached Sunday's wires and is left out. "
              "Every story on this page is dated Saturday 21 November 2026.")
DECK = ("Iran hits Bahrain, a missile in Zelensky's home town, Wall "
        "Street's AI rout: one Saturday.")


# -------------------------------------------------------------------- page
def number_disc(d, x, y, n):
    d.ellipse([x, y, x + 25, y + 25], fill=CRIMSON)
    d.text((x + 12.5, y + 12.5), str(n), font=F(SANS_B, 14), fill=WHITE,
           anchor="mm")


def paint_panel(page, st, x, y, w, h, seed):
    """Paint one story's scene and paste it into the page."""
    painter = SCENES[st["art"]]
    scene = painter(int(round(w)), int(round(h)), REGION_INK[st["region"]],
                    random.Random(seed))
    page.paste(scene, (int(round(x)), int(round(y))))


def story_card(page, d, st, x, y, w, h, tier, n):
    d.rectangle([x, y, x + w, y + h], fill=WHITE, outline=BLACK, width=2)
    ink = REGION_INK[st["region"]]
    d.rectangle([x, y, x + w, y + 5], fill=ink)
    if tier == "lead":
        paint_panel(page, st, x + 8, y + 12, w - 16, 94, SEED + n)
        ty = y + 112
    elif tier == "mid":
        paint_panel(page, st, x + 8, y + 10, w - 16, 60, SEED + n)
        ty = y + 76
    else:                                      # small card: a mini scene
        paint_panel(page, st, x + 8, y + 9, w - 16, 38, SEED + n)
        ty = y + 52
    number_disc(d, x + 8, ty, n)
    kx = x + 40
    d.text((kx, ty + 3), st["region"], font=F(SANS_B, 11), fill=ink)
    if tier == "small":
        set_block(d, st["headline"], x + 9, ty + 22, w - 18,
                  F(SERIF, 14), BLACK, 15, limit=2)
        return
    d.text((kx, ty + 16), st.get("src", ""), font=F(SANS, 9), fill=GREY)
    hsize, hstep = (19, 21) if tier == "lead" else (15, 17)
    hy = set_block(d, st["headline"], x + 9, ty + 30, w - 18,
                   F(SERIF, hsize), BLACK, hstep, limit=3)
    bsize = 11.5 if tier == "lead" else 10.5
    set_block(d, st["body"], x + 9, hy + 2, w - 18, F(SANS, bsize),
              GREY, 14, limit=3 if tier == "lead" else 2)


def masthead(d):
    """Kicker row, the big serif date, and the deck line under it."""
    d.text((EDGE, 22), "THE DAILY WORLD · THE WORLD IN ONE DAY",
           font=F(SANS_B, 13), fill=CRIMSON)
    right = "36 STORIES · 6 REGIONS · EVERY ONE DATED SATURDAY 21 NOVEMBER 2026"
    d.text((PAGE - EDGE, 22), right, font=F(SANS_B, 13), fill=BLACK,
           anchor="ra")
    d.line([EDGE, 42, PAGE - EDGE, 42], fill=BLACK, width=3)
    d.text((PAGE / 2, 50), "Saturday 21 November 2026", font=F(SERIF, 57),
           fill=BLACK, anchor="ma")
    d.line([EDGE, 116, PAGE - EDGE, 116], fill=BLACK, width=1)
    d.text((PAGE / 2, 122), DECK, font=F(SERIF_IT, 19), fill=GREY, anchor="ma")


def figures_strip(d, top):
    """Six numbered facts in a ruled, shaded band."""
    cell = SPAN / 6
    d.rectangle([EDGE, top, PAGE - EDGE, top + 58], fill=CREAM_DK,
                outline=BLACK, width=2)
    for i, (val, cap) in enumerate(FIGURES):
        cx = EDGE + i * cell
        if i:
            d.line([cx, top, cx, top + 58], fill=BLACK, width=1)
        d.text((cx + cell / 2, top + 6), val, font=F(SERIF, 25),
               fill=CRIMSON, anchor="ma")
        lines = wrap_copy(d, cap, F(SANS, 9.5), cell - 12)[:2]
        for j, line in enumerate(lines):
            d.text((cx + cell / 2, top + 36 + j * 11), line,
                   font=F(SANS, 9.5), fill=GREY, anchor="ma")


def tally_bar(d, top):
    """Black band naming each region and how many stories it holds."""
    d.rectangle([EDGE, top, PAGE - EDGE, top + 28], fill=BLACK)
    label = "   ·   ".join(f"{name} {n}" for name, n in REGION_TALLY)
    d.text((PAGE / 2, top + 6), label, font=F(SANS_B, 13.5), fill=WHITE,
           anchor="ma")


def briefs_block(d, top, gap):
    """The rest of the day: numbered one-liners in three columns."""
    d.text((EDGE, top), "ALSO ON SATURDAY 21 NOVEMBER — THE REST OF THE DAY",
           font=F(SANS_B, 13), fill=BLACK)
    d.line([EDGE, top + 20, PAGE - EDGE, top + 20], fill=BLACK, width=1)
    col_w = (SPAN - 2 * gap) / 3
    bf = F(SANS, 10.5)
    per_col = (len(BRIEFS) + 2) // 3
    for i, (n, region, text) in enumerate(BRIEFS):
        col, row = divmod(i, per_col)
        bx = EDGE + col * (col_w + gap)
        by = top + 26 + row * 14.8
        d.text((bx, by), f"{n}.", font=F(SANS_B, 10.5), fill=CRIMSON)
        d.text((bx + 22, by), clip_line(d, text, bf, col_w - 24), font=bf,
               fill=BLACK)


def date_check_box(d):
    """Red-ruled strip recording what was deliberately left out, and why."""
    d.rectangle([EDGE, 954, PAGE - EDGE, 998], outline=CRIMSON, width=2)
    d.text((EDGE + 10, 960), "DATE CHECK", font=F(SANS_B, 12), fill=CRIMSON)
    lines = wrap_copy(d, DATE_CHECK, F(SANS, 10.5), SPAN - 130)[:2]
    for j, line in enumerate(lines):
        d.text((EDGE + 108, 961 + j * 14), line, font=F(SANS, 10.5),
               fill=BLACK)
    d.text((PAGE - EDGE, 1004), "Sources credited per panel · Original artwork",
           font=F(SANS, 9.5), fill=GREY, anchor="ra")


def save_page(img, path):
    """Save the page; if the painted detail overflows the byte budget,
    fall back to an adaptive 256-colour palette with no dithering."""
    img.save(path, optimize=True)
    if os.path.getsize(path) > 1_000_000:
        pal = img.quantize(colors=256, method=Image.MEDIANCUT,
                           dither=Image.NONE)
        pal.save(path, optimize=True)
    return os.path.getsize(path)


def render_page():
    img = Image.new("RGB", (PAGE, PAGE), CREAM)
    d = ImageDraw.Draw(img)
    masthead(d)
    figures_strip(d, 148)
    tally_bar(d, 214)
    gap = 10
    lead_w = (SPAN - 2 * gap) / 3
    for i, st in enumerate(LEADS):
        story_card(img, d, st, EDGE + i * (lead_w + gap), 252, lead_w, 234,
                   "lead", i + 1)
    mid_w = (SPAN - 4 * gap) / 5
    for i, st in enumerate(MIDS):
        story_card(img, d, st, EDGE + i * (mid_w + gap), 496, mid_w, 178,
                   "mid", i + 4)
    for i, st in enumerate(SMALLS):
        story_card(img, d, st, EDGE + i * (mid_w + gap), 684, mid_w, 114,
                   "small", i + 9)
    briefs_block(d, 810, gap)
    date_check_box(d)
    size = save_page(img, "entry.png")
    print(f"wrote entry.png ({size} bytes)")


if __name__ == "__main__":
    render_page()
