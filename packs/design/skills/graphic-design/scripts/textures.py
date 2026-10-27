"""Material backgrounds for show posters: a frayed canvas patch, a notebook page,
crinkled liquid metal, and a red membrane network to lay over the metal.

  uv run --with pillow --with numpy python textures.py canvas --size 1080x1350 --out canvas.png
  uv run --with pillow --with numpy python textures.py notebook --size 1080x1080 --out page.png
  uv run --with pillow --with numpy python textures.py metal  --size 1080x1440 --out metal.png
  uv run --with shapely python textures.py cells --size 1080x1440 --seed 3 --out cells.svg

canvas   cream cotton canvas: weave, creases, stains, frayed edges with loose
         threads, black outside (or --bg none for transparency).
         --color "#e4ddcf" --fray 1.0 (fringe length) --threads 14 --wrinkle 1.0 --dirt 1.0
         --inset 0.035 (black margin, fraction of the short side)
notebook squared school-notebook sheet torn out of a spiral pad: 5 mm grid, red
         margin, ripped punch holes on the left, crumple folds, black outside.
         --rule grid|lines|blank --cell 34 (px at 1080) --margin right|left|none
         --crumple 1.0 --age 1.0 (yellowing) --inset 0.035
metal    crinkled foil / poured silver: blobs of liquid metal over fine creases,
         lit like chrome. --blobs 1.0 --crease 1.0 --tint 0.0–1 (green/amber
         reflections, as on a photographed sheet) --contrast 1.0
cells    red membrane: channels between mirrored oval cells, thick at the joints,
         tendrils running to the edges, plus thin outline rings. SVG, embossed
         by its own filter. --color "#e2546a" --cells 7 --tendrils 6 --rings 2
         --open 0.5 (how much of the frame the network covers)

Same --seed gives the same texture on every format of a series; change it per poster.
"""
import argparse
import math
import random
import sys


def args_size(s):
    w, h = s.lower().split("x")
    return int(w), int(h)


# ---------------------------------------------------------------- raster helpers
def _np():
    import numpy as np
    return np


def blur(x, sigma):
    """Gaussian blur through the FFT (wraps around: fine for textures)."""
    np = _np()
    if sigma <= 0:
        return x
    h, w = x.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    g = np.exp(-2 * (math.pi * sigma) ** 2 * (fx * fx + fy * fy))
    return np.fft.irfft2(np.fft.rfft2(x) * g, s=(h, w)).astype(np.float32)


def noise(rng, h, w, sigma):
    np = _np()
    n = blur(rng.normal(0, 1, (h, w)).astype(np.float32), sigma)
    return n / (n.std() + 1e-6)


def shade(height, light=(-0.5, -0.7, 0.6), k=1.0):
    np = _np()
    gy, gx = np.gradient(height)
    nx, ny, nz = -gx * k, -gy * k, np.ones_like(height)
    n = np.sqrt(nx * nx + ny * ny + 1)
    lx, ly, lz = light
    ln = math.sqrt(lx * lx + ly * ly + lz * lz)
    return (nx * lx + ny * ly + nz * lz) / (n * ln), (nx / n, ny / n, nz / n)


def hexrgb(h):
    np = _np()
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255


def save(arr, alpha, out):
    np = _np()
    from PIL import Image
    rgb = (np.clip(arr, 0, 1) * 255).astype(np.uint8)
    if alpha is None:
        Image.fromarray(rgb).save(out)
    else:
        a = (np.clip(alpha, 0, 1) * 255).astype(np.uint8)
        Image.fromarray(np.dstack([rgb, a])).save(out)


# ---------------------------------------------------------------- canvas
def cmd_canvas(a):
    np = _np()
    from PIL import Image, ImageDraw
    W, H = args_size(a.size)
    rng = np.random.default_rng(a.seed)
    k = min(W, H) / 1080
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

    # weave: warp and weft threads of uneven thickness and brightness
    pitch = 4.2 * k
    col = rng.normal(0, 1, int(W / pitch) + 2).astype(np.float32)
    row = rng.normal(0, 1, int(H / pitch) + 2).astype(np.float32)
    wx = xx + noise(rng, H, W, 10 * k) * 1.3 * k                      # threads are never ruler-straight
    wy = yy + noise(rng, H, W, 10 * k) * 1.3 * k
    ci, ri = np.clip((wx / pitch).astype(int), 0, len(col) - 1), np.clip((wy / pitch).astype(int), 0, len(row) - 1)
    warp = np.cos(math.pi * (wx / pitch)) ** 2
    weft = np.cos(math.pi * (wy / pitch)) ** 2
    over = ((ci + ri) % 2).astype(np.float32)                       # plain weave: who is on top
    weave = (warp * (0.6 + 0.4 * over) + weft * (0.6 + 0.4 * (1 - over))) * 0.5
    slub = 0.08 * (col[ci] + row[ri])                               # thicker/darker yarns
    weave = blur(weave, 0.5 * k) + slub * 0.6 + 0.12 * noise(rng, H, W, 0.8) + 0.1 * noise(rng, H, W, 3 * k)

    # wrinkles: big soft folds + cloth-like ridges (no paper-sharp lines)
    fold = noise(rng, H, W, 70 * k) * 7 + noise(rng, H, W, 22 * k) * 1.6
    for _ in range(int(4 * a.wrinkle)):
        x0, y0, ang = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0, math.pi)
        curve = noise(rng, H, W, 120 * k) * 25 * k
        d = (xx - x0) * math.sin(ang) - (yy - y0) * math.cos(ang) + curve
        along = (xx - x0) * math.cos(ang) + (yy - y0) * math.sin(ang)
        length = rng.uniform(0.15, 0.4) * max(W, H)
        fold += rng.uniform(2, 4) * np.exp(-(d / (14 * k)) ** 2) * np.exp(-(along / length) ** 2)
    light, _ = shade(fold * a.wrinkle, k=0.9)

    base = hexrgb(a.color)
    tone = 0.86 + 0.2 * weave + 0.6 * (light - light.mean())
    stain = noise(rng, H, W, 90 * k)
    dirt = np.clip(stain - 0.9, 0, None) * 0.07 * a.dirt + np.clip(noise(rng, H, W, 2 * k) - 2.8, 0, None) * 0.25 * a.dirt
    img = base[None, None, :] * tone[..., None] - dirt[..., None] * np.array([0.75, 0.82, 1.0], np.float32)

    # frayed outline: a ragged rectangle; fringe threads stick out of each side
    m = a.inset * min(W, H)
    def wob(n):  # slow drift + ragged yarn-scale bites
        slow = blur(rng.normal(0, 1, (1, n)).astype(np.float32), 40)[0]
        fast = blur(rng.normal(0, 1, (1, n)).astype(np.float32), 1.5)[0]
        return (slow / (slow.std() + 1e-6) * 5 + np.abs(fast / (fast.std() + 1e-6)) * 3) * k
    left, right = m + wob(H), W - m - wob(H)
    top, bottom = m + wob(W), H - m - wob(W)
    inside = (xx > left[yy.astype(int)]) & (xx < right[yy.astype(int)]) & (yy > top[xx.astype(int)]) & (yy < bottom[xx.astype(int)])
    alpha = inside.astype(np.float32)
    dist = np.minimum.reduce([xx - left[yy.astype(int)], right[yy.astype(int)] - xx, yy - top[xx.astype(int)], bottom[xx.astype(int)] - yy])
    worn = np.clip(1 - dist / (14 * k), 0, 1) * (0.5 + 0.5 * (noise(rng, H, W, 1.2 * k) > -0.3))
    img = img * (1 - worn[..., None] * 0.25) + base * 1.08 * worn[..., None] * 0.25

    # loose threads lying on the cloth and hanging off the edges
    over_img = Image.new("RGBA", (W * 2, H * 2), (0, 0, 0, 0))
    dr = ImageDraw.Draw(over_img)
    prng = random.Random(a.seed)
    # fringe: yarn ends crossing every edge, clustered, slightly curled, brighter than the cloth
    fr = 16 * k * a.fray
    edges = [("l", H), ("r", H), ("t", W), ("b", W)]
    for side, n in edges:
        t, cluster = 0.0, 1.0
        while t < n:
            t += pitch * prng.uniform(0.6, 1.6)
            if prng.random() < 0.08:
                cluster = prng.choice([0.3, 1, 1, 1.8, 2.6])
            if prng.random() < 0.2:
                continue
            ln = fr * cluster * prng.expovariate(1.0) + 3 * k
            ti = min(int(t), n - 1)
            e = {"l": left, "r": right, "t": top, "b": bottom}[side][ti]
            out_dir = {"l": (-1, 0), "r": (1, 0), "t": (0, -1), "b": (0, 1)}[side]
            x, y = (e, t) if side in "lr" else (t, e)
            x -= out_dir[0] * prng.uniform(2, 14) * k
            y -= out_dir[1] * prng.uniform(2, 14) * k
            ang = math.atan2(out_dir[1], out_dir[0]) + prng.gauss(0, 0.25)
            pts, steps = [], max(2, int(ln / (3 * k)))
            for _ in range(steps):
                pts.append((x * 2, y * 2))
                ang += prng.gauss(0, 0.12)
                x += math.cos(ang) * ln / steps
                y += math.sin(ang) * ln / steps
            c = int(225 + prng.uniform(-30, 25))
            dr.line(pts, fill=(c, c - 4, c - 14, int(prng.uniform(170, 255))), width=max(1, int(prng.uniform(1.5, 3.6) * k)))
    for i in range(a.threads):
        on_edge = i % 3 == 0
        if on_edge:
            side = prng.choice("lrtb")
            x = {"l": m, "r": W - m}.get(side, prng.uniform(m, W - m))
            y = {"t": m, "b": H - m}.get(side, prng.uniform(m, H - m))
        else:
            x, y = prng.uniform(m, W - m), prng.uniform(m, H - m)
        ang, pts = prng.uniform(0, 6.28), []
        for _ in range(prng.randint(30, 90)):
            pts.append((x * 2, y * 2))
            ang += prng.gauss(0, 0.35)
            x += math.cos(ang) * 6 * k
            y += math.sin(ang) * 6 * k
        width = max(2, int(3.2 * k * prng.uniform(0.7, 1.3)))
        dr.line([(px + 2, py + 3) for px, py in pts], fill=(40, 30, 20, 70), width=width + 1)   # shadow
        dr.line(pts, fill=(250, 246, 236, 235), width=width)
    ov = np.asarray(over_img.resize((W, H), Image.LANCZOS), np.float32) / 255
    oa = ov[..., 3:4]
    img = img * (1 - oa) + ov[..., :3] * oa
    alpha = np.maximum(alpha, oa[..., 0])

    if a.bg != "none":
        bg = hexrgb(a.bg)
        img = img * alpha[..., None] + bg * (1 - alpha[..., None])
        alpha = None
    save(img, alpha, a.out)
    print(f"saved {a.out} ({W}×{H}, canvas, seed {a.seed})")


# ---------------------------------------------------------------- notebook
def cmd_notebook(a):
    np = _np()
    W, H = args_size(a.size)
    rng = np.random.default_rng(a.seed)
    k = min(W, H) / 1080
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    m = a.inset * min(W, H)

    # crumple: soft bulges + a few sharp fold lines (paper keeps its creases)
    fold = noise(rng, H, W, 80 * k) * 5 + noise(rng, H, W, 25 * k) * 1.2 * a.crumple
    for _ in range(int(3 * a.crumple)):
        x0, y0, ang = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(0, math.pi)
        d = (xx - x0) * math.sin(ang) - (yy - y0) * math.cos(ang)
        fold += rng.uniform(1, 2.5) * np.abs(d) / (200 * k) * -1 + rng.uniform(0.6, 1.4) * np.exp(-(d / (2.5 * k)) ** 2)
    light, _ = shade(fold, k=0.9)
    paper = hexrgb(a.color)
    tone = 0.97 + 0.45 * (light - light.mean()) + 0.02 * noise(rng, H, W, 0.8) + 0.006 * noise(rng, H, W, 6 * k)
    img = paper[None, None, :] * tone[..., None]

    # ruling: thin printed lines, slightly uneven ink
    cell = a.cell * k
    ink = np.zeros((H, W), np.float32)
    off_x, off_y = rng.uniform(0, cell), rng.uniform(0, cell)
    def line(c, o):  # 1 on a printed line, fading over ~0.75 px
        return np.clip(1 - np.abs(((c - o + cell / 2) % cell) - cell / 2) / (0.75 * k), 0, 1)
    if a.rule == "grid":
        ink = np.maximum(line(xx, off_x), line(yy, off_y))
    elif a.rule == "lines":
        ink = line(yy, off_y)
    ink *= 0.85 + 0.15 * noise(rng, H, W, 20 * k)
    grid_col = np.array([0.42, 0.58, 0.74], np.float32)
    img = img * (1 - ink[..., None] * 0.6) + grid_col * ink[..., None] * 0.6 * tone[..., None]
    if a.margin != "none":
        mx = (W - m - 3.5 * cell) if a.margin == "right" else (m + 3.5 * cell + 26 * k)
        red = np.clip(1.4 - np.abs(xx - mx) / (1.2 * k), 0, 1)
        img = img * (1 - red[..., None] * 0.7) + np.array([0.86, 0.32, 0.38], np.float32) * red[..., None] * 0.7

    # yellowed, slightly dirty edges
    dist_edge = np.minimum.reduce([xx - m, yy - m, W - m - xx, H - m - yy])
    yel = np.clip(1 - dist_edge / (60 * k), 0, 1) ** 2 * 0.08 * a.age + np.clip(noise(rng, H, W, 120 * k) - 1, 0, None) * 0.04 * a.age
    img = img - yel[..., None] * np.array([0.0, 0.25, 0.9], np.float32)

    # outline: clean cut on three sides; the left edge is ripped off a spiral pad —
    # a ragged line with bites where the punch holes tore, and a few strip tabs left
    alpha = ((xx > m) & (xx < W - m) & (yy > m) & (yy < H - m)).astype(np.float32)
    rip = m + 24 * k + blur(rng.normal(0, 1, (H, 1)).astype(np.float32), 1.5)[:, 0] * 6 * k
    pitch = 30 * k
    row = ((yy - m) // pitch).astype(int)
    hy = ((yy - m) % pitch) - pitch / 2
    hole_x = m + 13 * k
    in_hole = (hy ** 2 + (xx - hole_x) ** 2) < (7 * k) ** 2
    tab_rows = rng.random(int(H / pitch) + 2) < 0.3
    keep_tab = tab_rows[row] & (xx > m + 3 * k) & ~in_hole
    bite = (hy ** 2 + (xx - rip[:, None] + 3 * k) ** 2) < (6 * k) ** 2
    cut = ((xx < rip[:, None]) & ~keep_tab) | (bite & ~tab_rows[row])
    alpha = np.where(cut, 0, alpha)
    torn = np.ones_like(xx, bool)
    # paper fibres on the ripped edge are lighter
    near = np.clip(1 - np.abs(xx - rip[:, None]) / (3 * k), 0, 1) * alpha * torn
    img = img * (1 - near[..., None] * 0.15) + near[..., None] * 0.15
    # cut edges cast a soft shadow on the black surface
    shadow = blur(alpha, 8 * k)
    bg = hexrgb(a.bg) if a.bg != "none" else np.zeros(3, np.float32)
    under = bg * (1 - 0.6 * shadow[..., None])
    out = img * alpha[..., None] + under * (1 - alpha[..., None])
    save(out, None if a.bg != "none" else alpha, a.out)
    print(f"saved {a.out} ({W}×{H}, notebook {a.rule}, seed {a.seed})")


# ---------------------------------------------------------------- metal
def cmd_metal(a):
    np = _np()
    W, H = args_size(a.size)
    rng = np.random.default_rng(a.seed)
    k = min(W, H) / 1080

    # poured blobs: smooth glossy plateaus with wrinkled, raised rims (liquid metal splashes)
    b = noise(rng, H, W, 42 * k) + 0.45 * noise(rng, H, W, 15 * k)
    plate = 1 / (1 + np.exp(-(b - 0.15) * 7))
    rim = np.exp(-((b - 0.15) * 3.5) ** 2)
    rough = 1 - np.abs(noise(rng, H, W, 4 * k))
    blobs = blur(plate, 2 * k) * 16 + rim * (2.5 + 2 * rough)
    # fine creases live in the valleys between blobs
    r1 = 1 - np.abs(noise(rng, H, W, 5 * k))
    r2 = 1 - np.abs(noise(rng, H, W, 13 * k))
    crease = ((r1 ** 3) * 1.4 + (r2 ** 2) * 2.0) * (1 - 0.8 * plate)
    height = blobs * a.blobs + crease * a.crease + noise(rng, H, W, 140 * k) * 14
    _, (nx, ny, nz) = shade(height, k=1.4 / k)
    # reflect the view vector (0,0,1) and look the direction up in a studio environment
    rx, ry, rz = 2 * nz * nx, 2 * nz * ny, 2 * nz * nz - 1
    sky = 0.5 + 0.5 * np.tanh((-ry - 0.05) * 6)                          # bright above, dark below
    band = np.exp(-((ry + 0.25) * 7) ** 2) * 0.55                        # dark horizon band
    soft = 0.65 + 0.35 * np.cos(rx * 4 + 1.2)                            # soft boxes left/right
    env = (0.12 + 0.95 * sky * soft - band + 0.25 * np.exp(-((rx - 0.5) * 5) ** 2)) * (0.75 + 0.25 * rz)
    yy = np.mgrid[0:H, 0:W][0].astype(np.float32)
    env = env * (1.08 - 0.25 * yy / H)                                   # sheet lit from above
    env = (env - env.mean()) * a.contrast + env.mean()
    env = np.clip(env, 0, None) ** 0.8 * 1.08
    img = np.repeat(env[..., None], 3, axis=2)
    if a.tint:
        t1, t2 = noise(rng, H, W, 140 * k), noise(rng, H, W, 140 * k)
        img += a.tint * 0.10 * np.stack([np.clip(t2, 0, None) * 0.8, np.clip(t1, 0, None) + np.clip(t2, 0, None) * 0.6,
                                         np.clip(t1, 0, None) * 0.3], -1) * (env[..., None] > 0.3)
    img = img * np.array([0.97, 0.99, 1.02], np.float32)                 # cool silver
    save(img, None, a.out)
    print(f"saved {a.out} ({W}×{H}, metal, seed {a.seed})")


# ---------------------------------------------------------------- cells
def cmd_cells(a):
    try:
        from shapely import affinity
        from shapely.geometry import LineString, Point, Polygon, box
        from shapely.ops import unary_union
    except ImportError:
        sys.exit("нужен shapely: uv run --with shapely python textures.py cells ...")
    W, H = args_size(a.size)
    rnd = random.Random(a.seed)
    k = min(W, H) / 1080
    cx = W / 2
    frame = box(0, 0, W, H)

    # oval cells on the left half, mirrored -> the symmetric "sigil" look
    cells, rings = [], []
    for _ in range(a.cells * 4):
        if len(cells) >= a.cells:
            break
        rx, ry = rnd.uniform(90, 220) * k, rnd.uniform(65, 150) * k
        x = rnd.uniform(-0.05 * W, cx - rx * 0.3)
        y = rnd.uniform(H * (0.5 - a.open * 0.6), H * (0.5 + a.open * 0.6))
        e = affinity.rotate(affinity.scale(Point(0, 0).buffer(1, 64), rx, ry), rnd.uniform(-35, 35))
        e = affinity.translate(e, x, y)
        if any(e.distance(c) < 8 * k for c in cells):
            continue
        cells.append(e)
    cells += [affinity.scale(c, -1, 1, origin=(cx, 0)) for c in cells]
    holes = unary_union(cells)

    # membrane: each cell grown by its own gap; merged, then rounded at the joints
    grown = unary_union([c.buffer(rnd.uniform(16, 60) * k) for c in cells])
    red = grown.difference(holes).buffer(10 * k).buffer(-10 * k)

    # tendrils: tapered curved horns from the membrane towards the edges
    targets = [(0, 0), (W, 0), (0, H), (W, H), (0, H * 0.5), (W, H * 0.5)]
    horns = []
    for i in range(a.tendrils):
        tx, ty = targets[i % len(targets)]
        tx, ty = tx + rnd.uniform(-0.1, 0.1) * W, ty + rnd.uniform(-0.1, 0.1) * H
        p = red.boundary.interpolate(red.boundary.project(Point(tx, ty)))
        n, pts = 24, []
        bend = rnd.uniform(-0.25, 0.25)
        for j in range(n + 1):
            t = j / n
            mx, my = p.x + (tx - p.x) * t, p.y + (ty - p.y) * t
            ox, oy = -(ty - p.y) * bend * math.sin(math.pi * t), (tx - p.x) * bend * math.sin(math.pi * t)
            pts.append((mx + ox, my + oy, (1 - t) ** 1.4 * rnd.uniform(16, 26) * k + 1))
        horns.append(unary_union([LineString([pts[j][:2], pts[j + 1][:2]]).buffer(pts[j][2]) for j in range(n)]))
    mirrored = [affinity.scale(h, -1, 1, origin=(cx, 0)) for h in horns]
    red = unary_union([red] + horns + mirrored).difference(holes).intersection(frame)

    for _ in range(a.rings):
        r = rnd.uniform(0.18, 0.32) * min(W, H)
        rings.append((rnd.uniform(0, W), rnd.uniform(0.3 * H, H), r))

    def path(g):
        polys = getattr(g, "geoms", [g])
        d = []
        for p in polys:
            if p.is_empty or not hasattr(p, "exterior"):
                continue
            for ring in [p.exterior, *p.interiors]:
                d.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in list(ring.coords)[:-1]) + "Z")
        return "".join(d)

    edge = max(1.5, 2.5 * k)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
<defs><filter id="emboss" x="-5%" y="-5%" width="110%" height="110%">
  <feGaussianBlur in="SourceAlpha" stdDeviation="{3 * k:.1f}" result="b"/>
  <feOffset in="b" dx="{2 * k:.1f}" dy="{3 * k:.1f}" result="o"/>
  <feComposite in="SourceAlpha" in2="o" operator="out" result="rim"/>
  <feFlood flood-color="#fff" flood-opacity=".45"/><feComposite in2="rim" operator="in" result="hi"/>
  <feComposite in="o" in2="SourceAlpha" operator="in" result="inner"/>
  <feFlood flood-color="#3a0008" flood-opacity=".55"/><feComposite in2="inner" operator="in" result="lo"/>
  <feMerge><feMergeNode in="SourceGraphic"/><feMergeNode in="lo"/><feMergeNode in="hi"/></feMerge>
</filter></defs>
<path d="{path(red)}" fill="{a.color}" fill-rule="evenodd" stroke="#5a0c16" stroke-opacity=".8" stroke-width="{edge:.1f}" filter="url(#emboss)"/>
{"".join(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.0f}" fill="none" stroke="#7a1020" stroke-opacity=".75" stroke-width="{edge:.1f}"/>' for x, y, r in rings)}
</svg>
'''
    open(a.out, "w", encoding="utf-8").write(svg)
    print(f"saved {a.out} ({W}×{H}, {len(cells)} cells, seed {a.seed}); put it over metal.png (show-chrome.html does the blending)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("canvas")
    p.add_argument("--color", default="#e4ddcf"); p.add_argument("--fray", type=float, default=1.0)
    p.add_argument("--threads", type=int, default=14); p.add_argument("--wrinkle", type=float, default=1.0)
    p.add_argument("--dirt", type=float, default=1.0); p.add_argument("--inset", type=float, default=0.035)
    p.add_argument("--bg", default="#050505")
    p.set_defaults(fn=cmd_canvas)
    p = sub.add_parser("notebook")
    p.add_argument("--color", default="#f4f2ec"); p.add_argument("--rule", default="grid", choices=["grid", "lines", "blank"])
    p.add_argument("--cell", type=float, default=34); p.add_argument("--margin", default="right", choices=["right", "left", "none"])
    p.add_argument("--crumple", type=float, default=1.0); p.add_argument("--age", type=float, default=1.0)
    p.add_argument("--inset", type=float, default=0.035); p.add_argument("--bg", default="#050505")
    p.set_defaults(fn=cmd_notebook)
    p = sub.add_parser("metal")
    p.add_argument("--blobs", type=float, default=1.0); p.add_argument("--crease", type=float, default=1.0)
    p.add_argument("--tint", type=float, default=0.0); p.add_argument("--contrast", type=float, default=1.0)
    p.set_defaults(fn=cmd_metal)
    p = sub.add_parser("cells")
    p.add_argument("--color", default="#e2546a"); p.add_argument("--cells", type=int, default=7)
    p.add_argument("--tendrils", type=int, default=6); p.add_argument("--rings", type=int, default=2)
    p.add_argument("--open", type=float, default=0.42)
    p.set_defaults(fn=cmd_cells)
    for p in sub.choices.values():
        p.add_argument("--size", default="1080x1350"); p.add_argument("--seed", type=int, default=1)
        p.add_argument("--out", required=True)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
