"""Redesign letters and bend whole words: outline operations, glyph swaps, envelope warps.

  uv run --with shapely --with fonttools --with uharfbuzz --with svgelements python letterforms.py \\
      --font fonts/Unbounded-900.ttf --text "НОЧЬ" --out word.svg \\
      --op round=0.03 --char "О=replace:icons/eye.svg" --warp arc=40

Units are em (1 em = font size). Glyph operations (--op, in order; --char "Б=op:args"
for one character only; several ops per char with ";"):
  weight=d          bolder (+) / thinner (-) by d em          weight=0.03
  round=r           round every corner with radius r          round=0.04
  outline=w         hollow letter, wall thickness w           outline=0.025
  inline=w[,gap]    engraved line inside the letter           inline=0.012,0.03
  stencil=w[,n,a]   n cuts of width w at angle a°             stencil=0.03,1,0
  slice=n,shift     cut in n bands, shift alternate bands     slice=5,0.03
  rough=amp[,freq]  torn, irregular edge                      rough=0.012,40
  spikes=len[,ang]  thorns on sharp corners (angle < ang°)    spikes=0.12,110
  thorns=len,step   thorns along the outer edge every step    thorns=0.06,0.18
  drip=len,n        melting drips from the bottom edges       drip=0.4,3
  scale=sx[,sy]     resize this glyph about its baseline      scale=1.3
  shift=dx,dy       move it                                   shift=0,0.1
  rotate=deg        rotate it about its centre                rotate=-12
  replace:file.svg  swap the glyph for your own drawing (fills; stroked icons are thickened)

Whole-text warps (--warp, in order):
  arc=deg  rainbow bend (negative = smile)      circle=deg  text around a circle (360 = full ring)
  arch=a   top edge arches up                   bulge=a     swell in the middle (negative = squeeze)
  wave=amp,periods                              flag=amp,periods   wave growing to the right
  perspective=k  top narrower (negative: bottom) rise=k     letters grow left→right
  skew=deg  slant (italic)                       fisheye=a  lens bulge from the centre
  jitter=deg,shift[,seed]  hand-made wobble per letter   bounce=shift  alternate up/down

Output: SVG in outlines (one path, even-odd fill). Feed it to text3d.cjs --svg for 3D.
"""
import argparse
import math
import random
import re
import sys

import shapely
import uharfbuzz as hb
from fontTools.misc.bezierTools import splitCubicAtT, splitQuadraticAtT
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont
from shapely import affinity
from shapely.geometry import LineString, MultiPolygon, Point, Polygon, box
from shapely.ops import unary_union

S = 1000.0  # SVG units per em


# ---------- glyph outlines -> shapely ----------
class PolyPen(BasePen):
    """Flattens glyph contours to point rings (curves sampled finely)."""

    def __init__(self, glyphset, steps=16):
        super().__init__(glyphset)
        self.rings, self.cur, self.steps = [], [], steps

    def _moveTo(self, p):
        self.cur = [p]

    def _lineTo(self, p):
        self.cur.append(p)

    def _curveToOne(self, p1, p2, p3):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps
            mt = 1 - t
            self.cur.append((mt**3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t**3 * p3[0],
                             mt**3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t**3 * p3[1]))

    def _qCurveToOne(self, p1, p2):
        p0 = self.cur[-1]
        for i in range(1, self.steps + 1):
            t = i / self.steps
            mt = 1 - t
            self.cur.append((mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0], mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1]))

    def _closePath(self):
        if len(self.cur) > 2:
            self.rings.append(self.cur)
        self.cur = []

    _endPath = _closePath


def signed_area(r):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(r, r[1:] + r[:1])) / 2


def rings_to_geom(rings):
    """Non-zero fill like a font renderer: contours running the same way as the
    largest one are solids (their overlaps merge), opposite ones are counters.
    Even-odd would punch holes where a font's contours overlap."""
    rings = [r for r in rings if len(r) > 2 and abs(signed_area(r)) > 1e-6]
    if not rings:
        return Polygon()
    outer = 1 if signed_area(max(rings, key=lambda r: abs(signed_area(r)))) > 0 else -1
    solid = unary_union([Polygon(r).buffer(0) for r in rings if signed_area(r) * outer > 0])
    holes = unary_union([Polygon(r).buffer(0) for r in rings if signed_area(r) * outer < 0])
    return solid.difference(holes) if not holes.is_empty else solid


def evenodd_geom(rings):
    """Even-odd combination, for SVG drawings (replace:)."""
    g = Polygon()
    for r in rings:
        p = Polygon(r).buffer(0)
        if not p.is_empty:
            g = g.symmetric_difference(p)
    return g


def clean(g):
    g = shapely.make_valid(g).buffer(0)
    if isinstance(g, Polygon):
        return MultiPolygon([g]) if not g.is_empty else MultiPolygon()
    if isinstance(g, MultiPolygon):
        return g
    return MultiPolygon([p for p in getattr(g, "geoms", []) if isinstance(p, Polygon) and not p.is_empty])


# ---------- SVG import for replace: ----------
def svg_geom(path):
    from svgelements import SVG, Path, Shape
    svg = SVG.parse(path)
    parts = []
    for el in svg.elements():
        if not isinstance(el, Shape):
            continue
        p = Path(el)
        if len(p) == 0:
            continue
        rings = []
        for sub in p.as_subpaths():
            sub = Path(sub)
            n = max(8, int(sub.length(error=1e-2) / 0.5) if sub.length(error=1e-2) else 8)
            pts = [(pt.x, -pt.y) for pt in (sub.point(i / n) for i in range(n + 1))]
            rings.append(pts)
        fill = el.fill is not None and el.fill.value is not None and str(el.fill) != "none"
        stroke = el.stroke is not None and el.stroke.value is not None and str(el.stroke) != "none"
        sw = float(el.stroke_width or 1)
        if fill:
            parts.append(evenodd_geom([r for r in rings if len(r) > 2]))
        if stroke or not fill:
            for r in rings:
                if len(r) > 1:
                    parts.append(LineString(r).buffer(sw / 2, join_style="round", cap_style="round"))
    g = unary_union(parts)
    if g.is_empty:
        sys.exit(f"{path}: nothing drawable found")
    return g


# ---------- glyph operations ----------
def op_apply(g, name, args, ctx, rnd):
    a = [float(x) for x in args.split(",")] if args and name != "replace" else []
    minx, miny, maxx, maxy = g.bounds if not g.is_empty else (0, 0, 0, 0)
    if name == "weight":
        return g.buffer(a[0] * S, join_style="mitre", mitre_limit=3)
    if name == "round":
        r = a[0] * S
        return g.buffer(r, join_style="round").buffer(-2 * r, join_style="round").buffer(r, join_style="round")
    if name == "outline":
        return g.difference(g.buffer(-a[0] * S, join_style="mitre"))
    if name == "inline":
        w, gap = a[0] * S, (a[1] if len(a) > 1 else 0.03) * S
        inner = g.buffer(-gap, join_style="mitre")
        return g.difference(inner.difference(inner.buffer(-w, join_style="mitre")))
    if name == "stencil":
        w, n, ang = a[0] * S, int(a[1]) if len(a) > 1 else 1, a[2] if len(a) > 2 else 0
        cuts = []
        for i in range(n):
            y = ctx["base"] + ctx["cap"] * (i + 1) / (n + 1)
            band = box(minx - S, y - w / 2, maxx + S, y + w / 2)
            cuts.append(affinity.rotate(band, ang, origin=((minx + maxx) / 2, y)))
        return g.difference(unary_union(cuts))
    if name == "slice":
        n, sh = int(a[0]), a[1] * S
        out, h = [], (maxy - miny) / n
        for i in range(n):
            band = g.intersection(box(minx - S, miny + i * h, maxx + S, miny + (i + 1) * h))
            out.append(affinity.translate(band, sh if i % 2 else -sh, 0))
        return unary_union(out)
    if name == "rough":
        amp, freq = a[0] * S, (a[1] if len(a) > 1 else 40)
        dense = shapely.segmentize(g, S / freq / 2)
        ph = [rnd.random() * 6.28 for _ in range(4)]
        def jit(x, y):
            n = (math.sin(x * freq / S * 6.1 + ph[0]) + math.sin(y * freq / S * 5.3 + ph[1]) +
                 math.sin((x + y) * freq / S * 9.7 + ph[2]) * 0.6 +
                 # hash noise from the coordinate itself, so a ring's first and last point stay equal
                 ((math.sin(x * 12.9898 + y * 78.233 + ph[3]) * 43758.5453) % 1 - 0.5) * 1.2)
            return amp * n / 3
        return shapely.transform(dense, lambda c: [[x + jit(x, y), y + jit(y, x)] for x, y in c])
    if name in ("spikes", "thorns"):
        add = []
        for poly in getattr(g, "geoms", [g]):
            ring = list(poly.exterior.coords)[:-1]
            n = len(ring)
            if name == "spikes":
                L, lim = a[0] * S, (a[1] if len(a) > 1 else 110)
                simp = Polygon(ring).simplify(S * 0.004)
                ring = list(simp.exterior.coords)[:-1]
                n = len(ring)
                orient = 1 if Polygon(ring).exterior.is_ccw else -1
                for i in range(n):
                    p0, p1, p2 = ring[i - 1], ring[i], ring[(i + 1) % n]
                    v1 = (p0[0] - p1[0], p0[1] - p1[1]); v2 = (p2[0] - p1[0], p2[1] - p1[1])
                    l1, l2 = math.hypot(*v1), math.hypot(*v2)
                    if l1 < 1 or l2 < 1:
                        continue
                    cosang = (v1[0] * v2[0] + v1[1] * v2[1]) / (l1 * l2)
                    ang = math.degrees(math.acos(max(-1, min(1, cosang))))
                    cross = v1[0] * v2[1] - v1[1] * v2[0]
                    if ang < lim and cross * orient < 0:  # convex corner
                        bis = (-(v1[0] / l1 + v2[0] / l2), -(v1[1] / l1 + v2[1] / l2))
                        bl = math.hypot(*bis) or 1
                        tip = (p1[0] + bis[0] / bl * L, p1[1] + bis[1] / bl * L)
                        w = min(l1, l2, L) * 0.45
                        add.append(Polygon([(p1[0] + v1[0] / l1 * w, p1[1] + v1[1] / l1 * w), tip, (p1[0] + v2[0] / l2 * w, p1[1] + v2[1] / l2 * w), p1]))
            else:
                L, step = a[0] * S, a[1] * S
                ext = poly.exterior
                sign = 1 if ext.is_ccw else -1   # outward normal of a CCW ring is (ty, -tx)
                d, total = step / 2, ext.length
                while d < total:
                    p = ext.interpolate(d); q = ext.interpolate(min(total, d + 2))
                    tx, ty = q.x - p.x, q.y - p.y; tl = math.hypot(tx, ty) or 1
                    nx, ny = sign * ty / tl, -sign * tx / tl
                    b = L * 0.35
                    add.append(Polygon([(p.x - tx / tl * b, p.y - ty / tl * b), (p.x + nx * L, p.y + ny * L), (p.x + tx / tl * b, p.y + ty / tl * b)]))
                    d += step
        return unary_union([g] + add)
    if name == "drip":
        L, n = a[0] * S, int(a[1]) if len(a) > 1 else 3
        # Bottom points of the outline (works after rough edges too).
        lows = [(x, y) for poly in getattr(g, "geoms", [g])
                for x, y in shapely.segmentize(poly.exterior, S * 0.01).coords if y < miny + S * 0.035]
        add = []
        for _ in range(n if lows else 0):
            x, y = rnd.choice(lows)
            ln, r = L * (0.3 + rnd.random() * 0.7), S * (0.025 + rnd.random() * 0.025)
            stem = LineString([(x, y + r), (x, y - ln)]).buffer(r * 0.8)
            add += [stem, Point(x, y - ln - r * 0.4).buffer(r * 1.5),
                    Polygon([(x - r * 2.6, y + 1), (x + r * 2.6, y + 1), (x, y - r * 2.5)]).buffer(r * 0.4)]
        return unary_union([g] + add)
    if name == "scale":
        sx = a[0]; sy = a[1] if len(a) > 1 else sx
        return affinity.scale(g, sx, sy, origin=((minx + maxx) / 2, ctx["base"]))
    if name == "shift":
        return affinity.translate(g, a[0] * S, a[1] * S if len(a) > 1 else 0)
    if name == "rotate":
        return affinity.rotate(g, a[0], origin="centroid")
    sys.exit(f"unknown op: {name}")


def parse_ops(spec):
    ops = []
    for part in filter(None, (s.strip() for s in spec.split(";"))):
        if part.startswith("replace:"):
            ops.append(("replace", part[8:]))
        else:
            name, _, args = part.partition("=")
            ops.append((name.strip(), args.strip()))
    return ops


# ---------- whole-text warps ----------
def warp(g, name, args, bounds, rnd, glyphs):
    a = [float(x) for x in args.split(",")] if args else []
    minx, miny, maxx, maxy = bounds
    W, Hh = maxx - minx, maxy - miny
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2

    def tf(fn):
        return shapely.transform(shapely.segmentize(g, S * 0.01), lambda c: [fn(x, y) for x, y in c])

    if name in ("arc", "circle"):
        deg = a[0]
        if abs(deg) < 1e-3:
            return g
        theta_total = math.radians(abs(deg))
        R = W / theta_total
        up = 1 if deg > 0 else -1
        def f(x, y):
            th = (x - cx) / R
            rr = R + (y - miny) * up
            return [cx + rr * math.sin(th), miny + up * (rr * math.cos(th) - R)]
        return tf(f)
    if name == "arch":
        return tf(lambda x, y: [x, miny + (y - miny) * (1 + a[0] * math.sin(math.pi * (x - minx) / W))])
    if name == "bulge":
        return tf(lambda x, y: [x, cy + (y - cy) * (1 + a[0] * math.sin(math.pi * (x - minx) / W))])
    if name in ("wave", "flag"):
        amp, per = a[0] * S, (a[1] if len(a) > 1 else 1)
        return tf(lambda x, y: [x, y + amp * (((x - minx) / W) if name == "flag" else 1) * math.sin(2 * math.pi * per * (x - minx) / W)])
    if name == "perspective":
        k = a[0]
        return tf(lambda x, y: [cx + (x - cx) * (1 - k * ((y - miny) / Hh if k > 0 else (maxy - y) / Hh) * (1 if k > 0 else -1)), y])
    if name == "rise":
        return tf(lambda x, y: [x, miny + (y - miny) * (1 + a[0] * (x - minx) / W)])
    if name == "skew":
        t = math.tan(math.radians(a[0]))
        return tf(lambda x, y: [x + (y - miny) * t, y])
    if name == "fisheye":
        k, rmax = a[0], math.hypot(W, Hh) / 2
        def f(x, y):
            dx, dy = x - cx, y - cy
            r = math.hypot(dx, dy) / rmax
            m = 1 + k * (1 - r * r)
            return [cx + dx * m, cy + dy * m]
        return tf(f)
    if name in ("jitter", "bounce"):
        out = []
        for i, gl in enumerate(glyphs):
            if name == "jitter":
                r = random.Random(int(a[2]) if len(a) > 2 else 7 + i)
                gl = affinity.rotate(gl, (r.random() - 0.5) * 2 * a[0], origin="centroid")
                gl = affinity.translate(gl, 0, (r.random() - 0.5) * 2 * (a[1] if len(a) > 1 else 0) * S)
            else:
                gl = affinity.translate(gl, 0, a[0] * S * (1 if i % 2 else -1))
            out.append(gl)
        return unary_union(out)
    sys.exit(f"unknown warp: {name}")


def to_path(g):
    def ring(c):
        pts = list(c)[:-1]
        return "M" + "L".join(f"{x:.1f} {-y:.1f}" for x, y in pts) + "Z"
    d = []
    for p in clean(g).geoms:
        d.append(ring(p.exterior.coords))
        d += [ring(i.coords) for i in p.interiors]
    return "".join(d)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--font", required=True)
    ap.add_argument("--text"); ap.add_argument("--lines", help='"СТРОКА 1|СТРОКА 2"')
    ap.add_argument("--out", default="letters.svg")
    ap.add_argument("--tracking", type=float, default=0.0, help="extra spacing, em")
    ap.add_argument("--leading", type=float, default=1.05, help="line height, em")
    ap.add_argument("--align", default="center", choices=["left", "center", "right"])
    ap.add_argument("--features", default=""); ap.add_argument("--var", default="")
    ap.add_argument("--op", action="append", default=[], help="glyph operation for every letter")
    ap.add_argument("--char", action="append", default=[], help='"Б=op:args;op2:args" or "О=replace:file.svg"')
    ap.add_argument("--warp", action="append", default=[], help="whole-text warp")
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--fill", default="#111"); ap.add_argument("--pad", type=float, default=0.06)
    a = ap.parse_args()
    if not (a.text or a.lines):
        sys.exit("--text or --lines required")
    rnd = random.Random(a.seed)

    tt = TTFont(a.font)
    upem = tt["head"].unitsPerEm
    loc = {k: float(v) for k, v in (p.split("=") for p in a.var.split(","))} if a.var else None
    gs = tt.getGlyphSet(location=loc)
    order = tt.getGlyphOrder()
    k = S / upem
    os2 = tt["OS/2"]
    cap = (getattr(os2, "sCapHeight", 0) or upem * 0.7) * k
    face = hb.Face(hb.Blob.from_file_path(a.font)); font = hb.Font(face)
    if loc:
        font.set_variations(loc)
    feats = {f.lstrip("-+"): not f.startswith("-") for f in filter(None, (x.strip() for x in a.features.split(",")))}

    per_char = {}
    for spec in a.char:
        ch, _, ops = spec.partition("=")
        per_char.setdefault(ch, []).extend(parse_ops(ops))
    global_ops = [o for spec in a.op for o in parse_ops(spec)]

    glyphs, line_geoms = [], []
    lines = (a.lines or a.text).split("|")
    for li, line in enumerate(lines):
        buf = hb.Buffer(); buf.add_str(line); buf.guess_segment_properties(); hb.shape(font, buf, feats)
        x, base = 0.0, -li * a.leading * S
        row = []
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            ch = line[info.cluster]
            adv = pos.x_advance * k
            if info.codepoint == 0 and ch.strip():
                sys.exit(f"в шрифте нет символа: {ch}")
            pen = PolyPen(gs)
            gs[order[info.codepoint]].draw(pen)
            g = rings_to_geom([[((px + pos.x_offset) * k + x, py * k + base + pos.y_offset * k) for px, py in r] for r in pen.rings])
            ctx = {"base": base, "cap": cap}
            # This character's own ops first (a replace, then its styling), then the global ones.
            for name, args in per_char.get(ch, []) + global_ops:
                if name == "replace":
                    rg = svg_geom(args)
                    b = rg.bounds
                    sc = cap / (b[3] - b[1])
                    rg = affinity.scale(rg, sc, sc, origin=(b[0], b[1]))
                    b = rg.bounds
                    rg = affinity.translate(rg, x - b[0] + S * 0.02, base - b[1])
                    adv = (b[2] - b[0]) + S * 0.04
                    g = rg
                else:
                    # Repair after every op: rough edges and spikes can self-intersect.
                    g = clean(shapely.make_valid(op_apply(g, name, args, ctx, rnd))) if not g.is_empty else g
            row.append(g)
            x += adv + a.tracking * S
        lw = x - a.tracking * S
        shift = {"left": 0, "center": -lw / 2, "right": -lw}[a.align]
        row = [affinity.translate(g, shift, 0) for g in row]
        glyphs += [g for g in row if not g.is_empty]
    whole = unary_union(glyphs)
    for spec in a.warp:
        name, _, args = spec.partition("=")
        whole = warp(whole, name.strip(), args.strip(), whole.bounds, rnd, glyphs)
        glyphs = [whole] if name.strip() not in ("jitter", "bounce") else glyphs
    whole = clean(whole).simplify(S * 0.0015)
    minx, miny, maxx, maxy = whole.bounds
    pad = a.pad * S
    vb = f"{minx - pad:.1f} {-maxy - pad:.1f} {maxx - minx + 2 * pad:.1f} {maxy - miny + 2 * pad:.1f}"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="{(maxx - minx + 2 * pad) / 2:.0f}" height="{(maxy - miny + 2 * pad) / 2:.0f}">\n'
           f'  <path fill="{a.fill}" fill-rule="evenodd" d="{to_path(whole)}"/>\n</svg>\n')
    open(a.out, "w", encoding="utf-8").write(svg)
    print(f"saved {a.out} ({len(svg) // 1024} KB)")


if __name__ == "__main__":
    main()
