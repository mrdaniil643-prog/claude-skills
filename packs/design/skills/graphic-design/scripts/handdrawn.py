"""Hand-drawn graphics: sketchy elements and whole sketch backgrounds, one hand, one tool.

  uv run --with shapely python handdrawn.py sheet --tool ink --out sheet.svg          every element
  uv run --with shapely python handdrawn.py cross --variant orthodox --tool charcoal --out cross.svg
  uv run --with shapely python handdrawn.py bg --size 1080x1350 --tool pencil --ink "#e9e4da" \\
      --items "cross:8,star:8,sparkle:10,scribble:3,hatch:4,splatter:5,heart:4,barbed:2" \\
      --clear 0.38 --seed 4 --out bg.svg

Elements: cross (variants latin, orthodox, gothic, x), dagger, star, sparkle, heart,
circle, spiral, arrow, lightning, flame, moon, eye, crown, barbed, vine, hatch,
scribble, splatter, drip, xmark, underline.

Tools (keep ONE per design so everything matches):
  pencil   thin, grainy, double-pass lines           — sketchbook, soft
  ink      clean pen line with slight wobble         — tattoo flash, zine
  marker   thick, flat, slightly translucent          — street, DIY
  charcoal wide, dusty, smudged edges                 — dark, painterly
  brush    pressure-heavy dry-brush strokes           — expressive, gestural

Output: SVG with the tool's texture as an SVG filter (renders in browsers and
render.cjs). --ink sets the colour; --bg fills a background (default transparent).
--clear 0.0–0.6 keeps an empty ellipse in the middle for the main subject.
"""
import argparse
import math
import random
import sys

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

TOOLS = {
    #          width  passes  jitter  pressure  opacity
    "pencil":   (1.3,   2,     0.9,    0.35,     0.9),
    "ink":      (2.4,   1,     0.5,    0.45,     1.0),
    "marker":   (5.5,   1,     0.6,    0.1,      0.88),
    "charcoal": (5.0,   2,     1.2,    0.5,      0.92),
    "brush":    (7.5,   1,     0.8,    0.85,     1.0),
}

FILTERS = {
    "pencil": """<filter id="tool" x="-5%" y="-5%" width="110%" height="110%">
      <feTurbulence type="fractalNoise" baseFrequency="1.6" numOctaves="2" seed="3" result="n"/>
      <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.2 1.7" result="grain"/>
      <feComposite in="SourceGraphic" in2="grain" operator="in" result="g"/>
      <feTurbulence type="fractalNoise" baseFrequency=".06" numOctaves="2" seed="5" result="w"/>
      <feDisplacementMap in="g" in2="w" scale="1.6" xChannelSelector="R" yChannelSelector="G"/></filter>""",
    "ink": """<filter id="tool" x="-5%" y="-5%" width="110%" height="110%">
      <feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="2" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="1.3" xChannelSelector="R" yChannelSelector="G"/></filter>""",
    "marker": """<filter id="tool" x="-5%" y="-5%" width="110%" height="110%">
      <feTurbulence type="fractalNoise" baseFrequency=".5" numOctaves="2" seed="7" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="2.2" xChannelSelector="R" yChannelSelector="G" result="d"/>
      <feTurbulence type="fractalNoise" baseFrequency=".02 .9" numOctaves="1" seed="4" result="s"/>
      <feColorMatrix in="s" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -1.2 1.5" result="streak"/>
      <feComposite in="d" in2="streak" operator="in"/></filter>""",
    "charcoal": """<filter id="tool" x="-8%" y="-8%" width="116%" height="116%">
      <feTurbulence type="fractalNoise" baseFrequency=".7" numOctaves="3" seed="9" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="4" xChannelSelector="R" yChannelSelector="G" result="d"/>
      <feGaussianBlur in="d" stdDeviation=".7" result="b"/>
      <feTurbulence type="fractalNoise" baseFrequency="1.2" numOctaves="2" seed="1" result="g"/>
      <feColorMatrix in="g" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.6 1.9" result="grain"/>
      <feComposite in="b" in2="grain" operator="in"/></filter>""",
    "brush": """<filter id="tool" x="-6%" y="-6%" width="112%" height="112%">
      <feTurbulence type="fractalNoise" baseFrequency=".8" numOctaves="2" seed="6" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="2.5" xChannelSelector="R" yChannelSelector="G" result="d"/>
      <feTurbulence type="fractalNoise" baseFrequency=".9 .04" numOctaves="2" seed="8" result="s"/>
      <feColorMatrix in="s" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2 1.6" result="dry"/>
      <feComposite in="d" in2="dry" operator="in"/></filter>""",
}


class Hand:
    """Turns ideal centerlines into hand-made strokes for one tool."""

    def __init__(self, tool, rnd, scale=1.0):
        self.w, self.passes, self.jit, self.press, self.op = TOOLS[tool]
        self.rnd, self.k = rnd, scale

    def wobble(self, pts, amount):
        """Low-frequency drift + tiny tremor, applied along the stroke."""
        r = self.rnd
        dense = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 3))
            dense += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n)]
        dense.append(pts[-1])
        ph = [r.uniform(0, 6.3) for _ in range(4)]
        L = len(dense)
        out = []
        for i, (x, y) in enumerate(dense):
            t = i / max(1, L - 1)
            dx = (math.sin(t * 3.1 + ph[0]) * 1.4 + math.sin(t * 11 + ph[1]) * 0.35) * amount
            dy = (math.sin(t * 2.7 + ph[2]) * 1.4 + math.sin(t * 13 + ph[3]) * 0.35) * amount
            out.append((x + dx + r.uniform(-.15, .15) * amount, y + dy + r.uniform(-.15, .15) * amount))
        return out

    def stroke(self, pts, weight=1.0, closed=False):
        """One gesture: overshoot, wobble, pressure-shaped width, repeated passes."""
        if closed:
            pts = pts + [pts[0], pts[1] if len(pts) > 1 else pts[0]]
        geoms = []
        for p in range(self.passes):
            q = list(pts)
            # overshoot / undershoot at both ends, like a quick hand
            if len(q) >= 2:
                for end in (0, -1):
                    a, b = (q[0], q[1]) if end == 0 else (q[-1], q[-2])
                    d = math.hypot(a[0] - b[0], a[1] - b[1]) or 1
                    ext = self.rnd.uniform(-0.02, 0.12) * d
                    na = (a[0] + (a[0] - b[0]) / d * ext, a[1] + (a[1] - b[1]) / d * ext)
                    q[0 if end == 0 else -1] = na
            off = (self.rnd.uniform(-1, 1) * p * 1.2, self.rnd.uniform(-1, 1) * p * 1.2)
            q = [(x + off[0], y + off[1]) for x, y in q]
            line = self.wobble(q, self.jit * self.k)
            n = len(line)
            segs = []
            base = self.w * weight * self.k * (0.75 if p else 1)
            for i in range(n - 1):
                t = i / max(1, n - 1)
                prs = (1 - self.press) + self.press * math.sin(math.pi * min(1, max(0, t))) ** 0.6
                w = base * prs * (0.85 + 0.3 * self.rnd.random() if self.press > 0.6 else 1)
                if w > 0.05:
                    segs.append(LineString([line[i], line[i + 1]]).buffer(w / 2, quad_segs=3))
            if segs:
                geoms.append(unary_union(segs))
        return unary_union(geoms)

    def blob(self, cx, cy, r):
        pts = []
        n = 14
        for i in range(n):
            a = i / n * 2 * math.pi
            rr = r * (0.75 + 0.5 * self.rnd.random())
            pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
        return Polygon(pts).buffer(r * 0.25).buffer(-r * 0.1)


# ---------- elements: centerlines in a ~100-unit box centred on (0,0), y down ----------
def ellipse(rx, ry, a0=0, turns=1.0, n=48):
    return [(rx * math.cos(a0 + t / n * 2 * math.pi * turns), ry * math.sin(a0 + t / n * 2 * math.pi * turns)) for t in range(n + 1)]


def element(name, h, rnd, variant=None):
    S = []
    if name == "cross":
        v = variant or rnd.choice(["latin", "orthodox", "gothic", "latin"])
        if v == "x":
            S += [h.stroke([(-35, -35), (35, 35)], 1.3), h.stroke([(35, -35), (-35, 35)], 1.3)]
        else:
            S += [h.stroke([(0, -52), (0, 52)], 1.2), h.stroke([(-30, -20), (30, -20)], 1.2)]
            if v == "orthodox":
                S += [h.stroke([(-14, -38), (14, -38)], 1.0), h.stroke([(-18, 30), (18, 18)], 1.0)]
            if v == "gothic":
                for x, y, dx, dy in ((0, -52, 1, 0), (0, 52, 1, 0), (-30, -20, 0, 1), (30, -20, 0, 1)):
                    S.append(h.stroke([(x - dx * 9, y - dy * 9), (x + dx * 9, y + dy * 9)], 0.9))
                S.append(h.stroke(ellipse(9, 9, rnd.uniform(0, 6)), 0.6, True) if False else h.stroke([(0, -29), (9, -20), (0, -11), (-9, -20), (0, -29)], 0.7))
    elif name == "dagger":
        S += [h.stroke([(-6, -18), (0, 55), (6, -18)], 1.0), h.stroke([(0, -14), (0, 40)], 0.5),
              h.stroke([(-24, -20), (24, -20)], 1.3), h.stroke([(0, -22), (0, -48)], 1.6), h.stroke(ellipse(6, 6), 0.8, True)]
        S[-1] = h.stroke([(x, y - 54) for x, y in ellipse(6, 6)], 0.8)
    elif name == "star":
        pts = [(48 * math.cos(-math.pi / 2 + i * 4 * math.pi / 5), 48 * math.sin(-math.pi / 2 + i * 4 * math.pi / 5)) for i in range(6)]
        S.append(h.stroke(pts, 1.0))
    elif name == "sparkle":
        S += [h.stroke([(0, -50), (0, 50)], 1.0), h.stroke([(-34, 0), (34, 0)], 1.0),
              h.stroke([(-12, -12), (12, 12)], 0.6), h.stroke([(12, -12), (-12, 12)], 0.6)]
    elif name == "heart":
        pts = [(16 * math.sin(t) ** 3 * 2.9, -(13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) * 2.9)
               for t in (i / 40 * 2 * math.pi for i in range(41))]
        S.append(h.stroke(pts, 1.0))
    elif name == "circle":
        S.append(h.stroke(ellipse(48, 34, rnd.uniform(0, 6), 1.15), 0.9))
    elif name == "spiral":
        S.append(h.stroke([(r * math.cos(a), r * math.sin(a)) for a, r in ((t / 60 * 6 * math.pi, 3 + t / 60 * 45) for t in range(61))], 0.8))
    elif name == "arrow":
        line = [(-48, 20), (-10, -10), (30, -18), (46, -30)]
        S += [h.stroke(line, 1.0), h.stroke([(26, -40), (46, -30), (34, -10)], 1.0)]
    elif name == "lightning":
        S.append(h.stroke([(10, -55), (-14, 0), (10, -4), (-10, 55)], 1.2))
    elif name == "flame":
        for dx, s in ((0, 1), (-16, 0.7), (16, 0.75)):
            S.append(h.stroke([(dx - 10 * s, 40), (dx - 18 * s, 0), (dx, -50 * s), (dx + 18 * s, 0), (dx + 10 * s, 40)], 0.8))
    elif name == "moon":
        S.append(h.stroke([(18 * math.cos(a) * 2.6 - 8, 18 * math.sin(a) * 2.6) for a in (math.pi * (0.35 + 1.3 * i / 30) for i in range(31))], 1.0))
        S.append(h.stroke([(14 * math.cos(a) * 2.6 + 6, 14 * math.sin(a) * 2.6) for a in (math.pi * (0.45 + 1.1 * i / 30) for i in range(31))], 0.8))
    elif name == "eye":
        S += [h.stroke([(-50, 0), (0, -26), (50, 0)], 0.9), h.stroke([(-50, 0), (0, 26), (50, 0)], 0.9),
              h.stroke(ellipse(13, 13, 0, 1.1), 0.9)]
    elif name == "crown":
        S += [h.stroke([(-45, 25), (-45, -20), (-22, 5), (0, -35), (22, 5), (45, -20), (45, 25), (-45, 25)], 1.0)]
    elif name == "barbed":
        pts = [(x, 4 * math.sin(x / 9)) for x in range(-60, 61, 6)]
        S.append(h.stroke(pts, 0.8))
        S.append(h.stroke([(x, -4 * math.sin(x / 9)) for x in range(-60, 61, 6)], 0.7))
        for x in range(-45, 50, 30):
            S += [h.stroke([(x - 7, -8), (x + 7, 8)], 0.7), h.stroke([(x + 7, -8), (x - 7, 8)], 0.7)]
    elif name == "vine":
        pts = [(x, 10 * math.sin(x / 14)) for x in range(-60, 61, 5)]
        S.append(h.stroke(pts, 0.9))
        for x in range(-50, 55, 16):
            y = 10 * math.sin(x / 14)
            d = 1 if (x // 16) % 2 else -1
            S.append(h.stroke([(x - 4, y), (x + 3, y + d * 14)], 0.7))
    elif name == "hatch":
        # parallel diagonal strokes kept inside a loose 90×80 patch
        tilt = rnd.uniform(0.5, 0.9)
        for i in range(-7, 8):
            c = i * 7
            y0, y1 = c - 40 * tilt, c + 40 * tilt
            S.append(h.stroke([(-40 + rnd.uniform(-4, 4), y1), (40 + rnd.uniform(-4, 4), y0)], 0.45))
        box = Polygon([(-46, -42), (46, -42), (46, 42), (-46, 42)])
        S = [s.intersection(box) for s in S]
    elif name == "scribble":
        pts, x, y = [], -45, -30
        for i in range(18):
            pts.append((x + rnd.uniform(-6, 6), y + rnd.uniform(-4, 4)))
            x = -45 if x > 0 else 45
            y += 3.5
        S.append(h.stroke(pts, 0.55))
    elif name == "splatter":
        S.append(h.blob(0, 0, rnd.uniform(9, 15)))
        for _ in range(rnd.randint(8, 16)):
            a, d = rnd.uniform(0, 6.3), rnd.uniform(14, 50)
            S.append(Point(math.cos(a) * d, math.sin(a) * d).buffer(rnd.uniform(1, 4.5)))
    elif name == "drip":
        S.append(h.stroke([(0, -50), (0, 35)], 1.6))
        S.append(Point(0, 40).buffer(7 * h.k))
    elif name == "xmark":
        S += [h.stroke([(-14, -14), (14, 14)], 1.2), h.stroke([(14, -14), (-14, 14)], 1.2)]
    elif name == "underline":
        S.append(h.stroke([(-55, 0), (-10, 4), (40, -2), (58, 6)], 1.1))
    else:
        sys.exit(f"unknown element: {name}")
    return unary_union([g for g in S if g is not None and not g.is_empty])


def place(g, x, y, s, rot):
    from shapely import affinity
    g = affinity.rotate(g, rot, origin=(0, 0))
    g = affinity.scale(g, s, s, origin=(0, 0))
    return affinity.translate(g, x, y)


def to_path(g):
    polys = [g] if isinstance(g, Polygon) else [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon)]
    d = []
    for p in polys:
        if p.is_empty:
            continue
        d.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in list(p.exterior.coords)[:-1]) + "Z")
        for r in p.interiors:
            d.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in list(r.coords)[:-1]) + "Z")
    return "".join(d)


def svg(g, a, w=None, h=None, pad=16):
    minx, miny, maxx, maxy = g.bounds if w is None else (0, 0, w, h)
    if w is None:
        minx, miny, maxx, maxy = minx - pad, miny - pad, maxx + pad, maxy + pad
    op = TOOLS[a.tool][4]
    bg = f'<rect x="{minx}" y="{miny}" width="{maxx - minx}" height="{maxy - miny}" fill="{a.bg}"/>' if a.bg != "none" else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{minx:.1f} {miny:.1f} {maxx - minx:.1f} {maxy - miny:.1f}"'
            f' width="{maxx - minx:.0f}" height="{maxy - miny:.0f}"><defs>{FILTERS[a.tool]}</defs>{bg}'
            f'<path fill="{a.ink}" fill-opacity="{op}" fill-rule="nonzero" filter="url(#tool)" d="{to_path(g)}"/></svg>\n')


ALL = ["cross", "dagger", "star", "sparkle", "heart", "circle", "spiral", "arrow", "lightning", "flame", "moon",
       "eye", "crown", "barbed", "vine", "hatch", "scribble", "splatter", "drip", "xmark", "underline"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", help="element name, 'bg' or 'sheet'")
    ap.add_argument("--variant"); ap.add_argument("--tool", default="ink", choices=list(TOOLS))
    ap.add_argument("--ink", default="#111"); ap.add_argument("--bg", default="none")
    ap.add_argument("--seed", type=int, default=1); ap.add_argument("--out", default="hand.svg")
    ap.add_argument("--size", default="1080x1350"); ap.add_argument("--items", default="cross:6,star:6,sparkle:8,heart:3,scribble:3,hatch:3,splatter:4,barbed:2,xmark:6")
    ap.add_argument("--clear", type=float, default=0.0, help="empty centre ellipse, fraction of the frame")
    ap.add_argument("--scale", type=float, default=1.0, help="element size multiplier for bg")
    a = ap.parse_args()
    rnd = random.Random(a.seed)

    if a.what == "sheet":
        h = Hand(a.tool, rnd)
        cells = []
        names = ALL + ["cross"] * 3
        variants = [None] * len(ALL) + ["orthodox", "gothic", "x"]
        variants[0] = "latin"
        for i, (n, v) in enumerate(zip(names, variants)):
            cells.append(place(element(n, h, rnd, v), (i % 6) * 140 + 70, (i // 6) * 140 + 70, 1, 0))
        rows = (len(names) + 5) // 6
        open(a.out, "w").write(svg(unary_union(cells), a, 6 * 140, rows * 140))
        print(f"saved {a.out}: {', '.join(ALL)}, cross orthodox/gothic/x ({a.tool})")
        return
    if a.what == "bg":
        W, H = map(int, a.size.split("x"))
        items = []
        for spec in a.items.split(","):
            n, _, c = spec.partition(":")
            items += [n.strip()] * int(c or 1)
        rnd.shuffle(items)
        k = min(W, H) / 1080
        h = Hand(a.tool, rnd, scale=1.0)
        placed, shapes = [], []
        cx, cy, rx, ry = W / 2, H * 0.45, W * a.clear, H * a.clear * 0.9
        for name in items:
            s = rnd.uniform(0.9, 1.9) * k * a.scale * (0.6 if name in ("xmark", "sparkle", "splatter") else 1)
            r = 55 * s
            for _ in range(60):
                x, y = rnd.uniform(r * 0.4, W - r * 0.4), rnd.uniform(r * 0.4, H - r * 0.4)
                if a.clear and ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 < 1:
                    continue
                if all(math.hypot(x - px, y - py) > (r + pr) * 0.8 for px, py, pr in placed):
                    break
            else:
                continue
            placed.append((x, y, r))
            h.k = 1 / s  # keep stroke weight constant across sizes: one pen for the whole sheet
            g = element(name, h, rnd)
            shapes.append(place(g, x, y, s, rnd.uniform(-25, 25)))
        open(a.out, "w").write(svg(unary_union(shapes), a, W, H))
        print(f"saved {a.out}: {len(shapes)} elements, {a.tool}")
        return
    h = Hand(a.tool, rnd)
    open(a.out, "w").write(svg(element(a.what, h, rnd, a.variant), a))
    print(f"saved {a.out}")


if __name__ == "__main__":
    main()
