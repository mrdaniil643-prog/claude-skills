"""Procedural ornaments for youth / music-scene design: cyber-sigilism, neo-tribal,
sparkles, barbed wire, chains, crosses, hearts, stars. SVG output, any colour.

  uv run --with shapely python ornaments.py sigil  --seed 4 --out sigil.svg     # thin spiky, symmetric
  uv run --with shapely python ornaments.py tribal --seed 2 --out tribal.svg    # heavy, flame-like curls
  uv run --with shapely python ornaments.py wings  --seed 9 --out wings.svg     # wide, horizontal spread
  uv run --with shapely python ornaments.py crown  --seed 5 --out crown.svg     # spikes rising from a base
  uv run --with shapely python ornaments.py sparkle|star|cross|heart --out x.svg
  uv run --with shapely python ornaments.py barbed|chain --length 6 --out wire.svg   # horizontal tiles
  uv run --with shapely python ornaments.py sheet --out sheet.svg               # 12 seeds of each, to pick from

--seed picks the variation (try many with `sheet`), --density 0.5–2 more or fewer
branches, --weight 0.5–2 line thickness, --fill colour. Output is outlines (one path),
so it works in logos, posters, letterforms replace:, and text3d.cjs --svg.
"""
import argparse
import math
import random
import sys

from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union


def catmull(pts, n=12):
    """Smooth curve through control points."""
    out = []
    p = [pts[0]] + pts + [pts[-1]]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2 +
                                    (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    out.append(pts[-1])
    return out


def taper(curve, w0, w1=0.0, power=1.0, lead=0.0):
    """Stroke a polyline whose width runs from w0 to w1, ending in a sharp tip.
    Built as a union of short round-capped segments, so tight bends of a thick
    stroke cannot fold over themselves and punch holes. lead > 0 also sharpens the
    start: width grows from 0 over that fraction of the length (tribal blades)."""
    n = len(curve)
    segs = []
    for i in range(n - 2):
        t = i / (n - 1)
        w = (w0 + (w1 - w0) * t ** power) / 2 * (min(1, t / lead) if lead else 1)
        if w > 0.05:
            segs.append(LineString([curve[i], curve[i + 1]]).buffer(w, quad_segs=4))
    # sharp tip: a triangle from the last width to the end point
    i = max(0, n - 3)
    (x0, y0), (x1, y1) = curve[i], curve[-1]
    tl = math.hypot(x1 - x0, y1 - y0) or 1
    nx, ny = -(y1 - y0) / tl, (x1 - x0) / tl
    wl = (w0 + (w1 - w0) * (i / (n - 1)) ** power) / 2
    segs.append(Polygon([(x0 + nx * wl, y0 + ny * wl), (x1, y1), (x0 - nx * wl, y0 - ny * wl)]).buffer(0))
    return unary_union(segs)


def branch(rnd, start, angle, length, w, depth, curl, spikes, out, lead=0.0):
    """One limb: a curving stroke that tapers to a point, sprouting thorns and sub-limbs."""
    pts, (x, y), a = [start], start, angle
    steps = 4
    for _ in range(steps):
        a += rnd.uniform(-curl, curl)
        x += math.cos(a) * length / steps; y += math.sin(a) * length / steps
        pts.append((x, y))
    curve = catmull(pts, 10)
    out.append(taper(curve, w, 0, 1.2, lead))
    if depth <= 0:
        return
    # thorns and sub-branches along the limb
    for _ in range(spikes):
        i = rnd.randint(len(curve) // 5, len(curve) - 4)
        px, py = curve[i]; qx, qy = curve[i + 1]
        base = math.atan2(qy - py, qx - px)
        side = rnd.choice((-1, 1))
        sub_a = base + side * rnd.uniform(0.35, 1.1)
        frac = 1 - i / len(curve)
        if rnd.random() < 0.55:
            branch(rnd, (px, py), sub_a, length * rnd.uniform(0.35, 0.6) * (0.6 + frac * 0.5), w * 0.6 * frac + w * 0.15, depth - 1, curl, max(1, spikes - 1), out)
        else:
            L = length * rnd.uniform(0.12, 0.25)
            tip = (px + math.cos(sub_a) * L, py + math.sin(sub_a) * L)
            out.append(taper([(px, py), ((px + tip[0]) / 2 + rnd.uniform(-2, 2), (py + tip[1]) / 2), tip], w * 0.7 * frac + w * 0.2, 0, 1))


def mirror(g):
    return unary_union([g, affinity.scale(g, -1, 1, origin=(0, 0))])


def sigil(rnd, a, kind):
    parts = []
    dens, wt = a.density, a.weight
    if kind == "sigil":
        # spine + limbs on one side, mirrored
        spine_len = rnd.uniform(260, 340)
        parts.append(taper(catmull([(0, -spine_len / 2), (rnd.uniform(-6, 6), 0), (0, spine_len / 2)], 12), 7 * wt, 0, 0.8))
        parts.append(taper(catmull([(0, -spine_len / 2), (rnd.uniform(-4, 4), -spine_len * 0.8)], 8), 6 * wt, 0, 1))
        for _ in range(int(rnd.randint(3, 5) * dens)):
            y = rnd.uniform(-spine_len * 0.45, spine_len * 0.45)
            ang = rnd.uniform(-1.1, 1.1) + (0 if rnd.random() < 0.7 else math.pi * 0.15)
            branch(rnd, (0, y), ang, rnd.uniform(90, 170), 6 * wt, 2, 0.5, 3, parts)
    elif kind == "tribal":
        for _ in range(int(rnd.randint(3, 4) * dens)):
            y = rnd.uniform(-90, 90)
            ang = rnd.uniform(-0.9, 0.9)
            branch(rnd, (rnd.uniform(-30, 10), y), ang, rnd.uniform(160, 240), 34 * wt, 1, 0.8, 2, parts, lead=0.35)
    elif kind == "wings":
        for _ in range(int(rnd.randint(5, 7) * dens)):
            y = rnd.uniform(-40, 40)
            ang = rnd.uniform(-0.55, 0.25)
            branch(rnd, (10, y), ang, rnd.uniform(160, 260), 9 * wt, 2, 0.35, 3, parts)
    elif kind == "crown":
        parts.append(taper(catmull([(0, 0), (90, rnd.uniform(-6, 6)), (180, 0)], 10), 9 * wt, 3 * wt, 1))
        for i in range(int(rnd.randint(3, 5) * dens)):
            x = 10 + i * rnd.uniform(28, 42)
            branch(rnd, (x, 0), math.pi / 2 + rnd.uniform(-0.35, 0.35), rnd.uniform(70, 150) * (1.2 if i == 0 else 1), 8 * wt, 1, 0.3, 2, parts)
    g = unary_union(parts)
    return mirror(g) if kind != "crown" else mirror(affinity.translate(g, 0, 0))


def simple(kind, a, rnd):
    w = a.weight
    if kind == "sparkle":
        pts = []
        for i in range(8):
            r = 100 if i % 2 == 0 else 14 * w
            th = math.pi / 2 + i * math.pi / 4
            pts.append((r * math.cos(th), r * math.sin(th)))
        # concave curves between the points
        curve = []
        for i in range(8):
            p, q = pts[i], pts[(i + 1) % 8]
            for k in range(8):
                t = k / 8
                curve.append((p[0] * (1 - t) ** 2 + 0 * 2 * t * (1 - t) + q[0] * t * t, p[1] * (1 - t) ** 2 + q[1] * t * t))
        return Polygon(curve).buffer(0)
    if kind == "star":
        return Polygon([((100 if i % 2 == 0 else 40) * math.cos(math.pi / 2 + i * math.pi / 5), (100 if i % 2 == 0 else 40) * math.sin(math.pi / 2 + i * math.pi / 5)) for i in range(10)])
    if kind == "cross":
        t = 16 * w
        g = unary_union([box(-t, -100, t, 100), box(-62, 30 - t, 62, 30 + t)])
        flare = [Polygon([(x - 2.2 * t, y), (x + 2.2 * t, y), (x, y + (6 if y > 0 else -6) * t / 2)]) for x, y in ((0, 100), (0, -100))]
        flare += [Polygon([(x, 30 - 2.2 * t), (x, 30 + 2.2 * t), (x + (1 if x > 0 else -1) * 3 * t, 30)]) for x in (62, -62)]
        return unary_union([g] + flare)
    if kind == "heart":
        pts = [(16 * math.sin(t) ** 3 * 6, (13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)) * 6) for t in (i / 120 * 2 * math.pi for i in range(120))]
        return Polygon(pts).buffer(0)
    if kind in ("barbed", "chain"):
        L = int(a.length)
        parts = []
        for i in range(L):
            x0 = i * 100
            if kind == "barbed":
                for ph in (0, math.pi):
                    pts = [(x0 + k * 5, 7 * math.sin(k / 20 * 2 * math.pi + ph)) for k in range(21)]
                    parts.append(LineString(pts).buffer(3.2 * w, cap_style="flat"))
                c = (x0 + 50, 0)
                for ang in (0.9, -0.9, 2.2, -2.2):
                    parts.append(taper([c, (c[0] + math.cos(ang) * 26, c[1] + math.sin(ang) * 26)], 5 * w, 0))
                parts.append(Point(c).buffer(8 * w))
            else:
                # alternate a face-on oval link with an edge-on link (a rounded bar)
                if i % 2 == 0:
                    ring = affinity.scale(Point(0, 0).buffer(1, quad_segs=24), 36, 21)
                    parts.append(affinity.translate(ring.difference(affinity.scale(Point(0, 0).buffer(1, quad_segs=24), 24, 9)), x0 + 50, 0))
                else:
                    parts.append(LineString([(x0 + 22, 0), (x0 + 78, 0)]).buffer(6.5 * w))
        return unary_union(parts)
    sys.exit(f"unknown ornament: {kind}")


def to_svg(g, fill, pad=12):
    g = g.buffer(0)
    polys = [g] if isinstance(g, Polygon) else list(getattr(g, "geoms", []))
    d = []
    for p in polys:
        if p.is_empty:
            continue
        d.append("M" + "L".join(f"{x:.1f} {-y:.1f}" for x, y in list(p.exterior.coords)[:-1]) + "Z")
        for r in p.interiors:
            d.append("M" + "L".join(f"{x:.1f} {-y:.1f}" for x, y in list(r.coords)[:-1]) + "Z")
    minx, miny, maxx, maxy = g.bounds
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{minx - pad:.1f} {-maxy - pad:.1f} {maxx - minx + 2 * pad:.1f} {maxy - miny + 2 * pad:.1f}">'
            f'<path fill="{fill}" fill-rule="evenodd" d="{"".join(d)}"/></svg>\n')


def make(kind, a, seed):
    rnd = random.Random(seed)
    if kind in ("sigil", "tribal", "wings", "crown"):
        return sigil(rnd, a, kind)
    return simple(kind, a, rnd)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("kind")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--density", type=float, default=1.0)
    ap.add_argument("--weight", type=float, default=1.0)
    ap.add_argument("--length", type=float, default=6)
    ap.add_argument("--fill", default="#111")
    ap.add_argument("--out", default="ornament.svg")
    a = ap.parse_args()
    if a.kind == "sheet":
        cells = []
        for row, kind in enumerate(("sigil", "tribal", "wings", "crown")):
            for col in range(6):
                g = make(kind, a, col + 1)
                b = g.bounds
                s = 160 / max(b[2] - b[0], b[3] - b[1])
                g = affinity.scale(g, s, s, origin=(0, 0))
                b = g.bounds
                cells.append(affinity.translate(g, col * 200 - (b[0] + b[2]) / 2, -row * 200 - (b[1] + b[3]) / 2))
        open(a.out, "w").write(to_svg(unary_union(cells), a.fill, 30))
        print(f"saved {a.out}: rows sigil, tribal, wings, crown; columns = --seed 1..6")
        return
    open(a.out, "w").write(to_svg(make(a.kind, a, a.seed), a.fill))
    print(f"saved {a.out}")


if __name__ == "__main__":
    main()
