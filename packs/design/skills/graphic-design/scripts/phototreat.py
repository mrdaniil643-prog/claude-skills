"""Photo treatments for music-scene posters and covers, chained in one call.

  uv run --with pillow --with numpy python phototreat.py in.jpg out.png --fx "flash,crush,grain=0.18"
  ... --fx "xerox=0.5,grain=0.25"                  photocopy / DIY zine
  ... --fx "duotone=#0b0b0b,#ff2a2a,halftone=10"   two-colour print with a dot screen
  ... --fx "dream,chroma=4,grain=0.1"              soundcloud haze
  ... --fx "vhs"                                   tape: chroma bleed, scanlines, noise
  ... --fx "paint=8,paper"                         painted / gouache
  uv run --with pillow --with numpy python phototreat.py --list

Effects (in the order written; numbers optional):
  flash[=k]          direct on-camera flash: blown centre, hard falloff, cool cast
  crush[=k]          crushed blacks, lifted contrast, muted colour (dark rap)
  grain[=amt]        film / sensor grain                       0.05–0.3
  duotone=dark,light map luminance to two colours
  tint=#hex[,k]      colour wash (multiply-ish)
  halftone[=cell]    dot screen, size in px                    6–16
  xerox[=thr]        harsh photocopy: threshold, toner noise   0.35–0.6
  bitmap             1-bit dither (Floyd–Steinberg)
  chroma[=px]        RGB split / chromatic aberration          2–12
  motion[=px,deg]    motion blur                               20,0
  dream[=k]          glow + soft focus + lifted blacks
  pixel[=size]       pixelate (low-res internet)               6–20
  scanlines[=gap]    CRT lines
  vhs                chroma bleed + scanlines + noise + soft
  vignette[=k]       darken edges
  sharpen[=k]        crisp edges after effects
  paint[=r]          painted: Kuwahara brush patches           4–12
  sketch[=k]         pencil drawing of the photo (grey)
  ink[=thr]          brush-pen line art with solid blacks     0.4–0.6
  paper[=k]          paper tooth and fibres, slightly warm — put last

Hand-made looks (keep one tool for the whole system, see references/handmade.md):
  ... --fx "paint=8,paper"                         oil/gouache poster
  ... --fx "sketch,paper=1.2"                      pencil sketch
  ... --fx "ink=0.5,paper"                         ink drawing over the photo
"""
import argparse
import sys

import numpy as np
from PIL import Image, ImageFilter, ImageOps

FX_HELP = __doc__


def hexrgb(h):
    h = h.strip().lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255


def lum(a):
    return a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722


def fx_flash(a, k=1.0):
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot((xx - w * 0.5) / w, (yy - h * 0.42) / h)
    light = np.clip(1.0 - r * 1.6, 0, 1) ** 1.5 * 0.65 * k
    out = a * (1 + light[..., None] * 1.1) + light[..., None] * 0.05
    out = (out - 0.5) * (1 + 0.35 * k) + 0.5
    out = out * np.array([0.96, 0.99, 1.06])               # cool cast
    out *= np.clip(1.15 - r * 0.9 * k, 0.25, 1)[..., None]  # hard falloff
    return out


def fx_crush(a, k=1.0):
    l = lum(a)[..., None]
    out = l + (a - l) * (1 - 0.45 * k)                     # mute colour
    out = np.clip((out - 0.12 * k) / (1 - 0.12 * k), 0, 1)  # crush blacks
    return out ** (1 + 0.25 * k)


def fx_grain(a, amt=0.15, rng=None):
    n = rng.normal(0, amt, a.shape[:2])[..., None]
    return a + n * (0.6 + 0.4 * (1 - lum(a)[..., None]))


def fx_duotone(a, dark, light):
    l = lum(np.clip(a, 0, 1))[..., None]
    return hexrgb(dark) * (1 - l) + hexrgb(light) * l


def fx_tint(a, col, k=0.5):
    return a * (1 - k) + a * hexrgb(col) * k * 1.4


def fx_halftone(a, cell=10):
    cell = int(cell)
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    h, w = a.shape[:2]
    out = np.ones((h, w, 3), np.float32)
    small = np.asarray(img.resize((max(1, w // cell), max(1, h // cell)), Image.BILINEAR), np.float32) / 255
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = np.clip(yy // cell, 0, small.shape[0] - 1), np.clip(xx // cell, 0, small.shape[1] - 1)
    col = small[cy, cx]
    d = np.hypot(xx % cell - cell / 2, yy % cell - cell / 2) / (cell / 2)
    radius = np.sqrt(1 - lum(col)) * 1.15
    ink = (d < radius)[..., None]
    paper = np.array([0.97, 0.96, 0.93])
    return np.where(ink, col * 0.85, paper)


def fx_xerox(a, thr=0.5, rng=None):
    l = lum(np.clip(a, 0, 1))
    blur = np.asarray(Image.fromarray((l * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)), np.float32) / 255
    noise = rng.normal(0, 0.06, l.shape)
    ink = (blur + noise) < thr
    speck = rng.random(l.shape) < 0.004
    out = np.where(ink ^ speck, 0.06, 0.95)
    return np.repeat(out[..., None], 3, axis=2)


def fx_bitmap(a):
    img = Image.fromarray((np.clip(lum(a), 0, 1) * 255).astype(np.uint8)).convert("1")
    return np.repeat(np.asarray(img.convert("L"), np.float32)[..., None] / 255, 3, axis=2)


def fx_chroma(a, px=4):
    px = int(px)
    out = a.copy()
    out[..., 0] = np.roll(a[..., 0], px, axis=1)
    out[..., 2] = np.roll(a[..., 2], -px, axis=1)
    return out


def fx_motion(a, px=24, deg=0):
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).rotate(deg, resample=Image.BICUBIC, expand=True)
    arr = np.asarray(img, np.float32) / 255
    k = int(px)
    acc = np.zeros_like(arr)
    for i in range(-k // 2, k // 2 + 1):
        acc += np.roll(arr, i, axis=1)
    acc /= (k + 1)
    out = Image.fromarray((acc * 255).astype(np.uint8)).rotate(-deg, resample=Image.BICUBIC, expand=True)
    h, w = a.shape[:2]
    ow, oh = out.size
    out = out.crop(((ow - w) // 2, (oh - h) // 2, (ow - w) // 2 + w, (oh - h) // 2 + h))
    return np.asarray(out, np.float32) / 255


def fx_dream(a, k=1.0):
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    glow = np.asarray(img.filter(ImageFilter.GaussianBlur(max(a.shape[:2]) * 0.012)), np.float32) / 255
    out = 1 - (1 - a) * (1 - glow * 0.55 * k)            # screen blend
    return out * (1 - 0.1 * k) + 0.08 * k                  # lift blacks


def fx_pixel(a, size=10):
    h, w = a.shape[:2]
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    img = img.resize((max(1, w // int(size)), max(1, h // int(size))), Image.BILINEAR).resize((w, h), Image.NEAREST)
    return np.asarray(img, np.float32) / 255


def fx_scanlines(a, gap=3):
    gap = int(gap)
    m = np.ones(a.shape[0], np.float32)
    m[::gap] = 0.72
    return a * m[:, None, None]


def fx_vhs(a, rng=None):
    a = fx_chroma(a, max(2, a.shape[1] // 300))
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    a = np.asarray(img, np.float32) / 255
    a = fx_scanlines(a, 3)
    a = a + rng.normal(0, 0.05, a.shape[:2])[..., None]
    return (a - 0.5) * 0.92 + 0.5 + np.array([0.02, 0, 0.03])


def fx_vignette(a, k=1.0):
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / np.sqrt(2)
    return a * (1 - k * 0.75 * r ** 2.2)[..., None]


def fx_sharpen(a, k=1.0):
    img = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.UnsharpMask(2, int(120 * k), 2))
    return np.asarray(img, np.float32) / 255


def _box(x, r):
    """Mean over a (2r+1)² window, edge-padded, via an integral image."""
    p = np.pad(x, ((r + 1, r), (r + 1, r)) + ((0, 0),) * (x.ndim - 2), mode="edge")
    c = p.cumsum(0).cumsum(1)
    n = 2 * r + 1
    return (c[n:, n:] - c[:-n, n:] - c[n:, :-n] + c[:-n, :-n]) / (n * n)


def fx_paint(a, r=6):
    """Kuwahara: each pixel takes the mean of its calmest quadrant -> flat brush patches, sharp edges."""
    r = max(2, int(r))
    h, w = a.shape[:2]
    l = lum(a)
    m, m2, ml = _box(a, r // 2), _box(l * l, r // 2), _box(l, r // 2)
    var = m2 - ml * ml
    s = r // 2 + 1
    vp = np.pad(var, s, mode="edge")
    mp = np.pad(m, ((s, s), (s, s), (0, 0)), mode="edge")
    best, out = np.full((h, w), np.inf, np.float32), np.zeros_like(a)
    for dy in (0, 2 * s):
        for dx in (0, 2 * s):
            v = vp[dy:dy + h, dx:dx + w]
            pick = v < best
            best = np.where(pick, v, best)
            out = np.where(pick[..., None], mp[dy:dy + h, dx:dx + w], out)
    return out


def fx_sketch(a, k=1.0):
    """Pencil drawing: colour-dodge of the inverted blur, slightly darkened lines."""
    l = lum(np.clip(a, 0, 1))
    blur = np.asarray(Image.fromarray(((1 - l) * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(max(a.shape[:2]) * 0.006 * k)), np.float32) / 255
    out = np.clip(l / np.maximum(1 - blur, 1e-3), 0, 1) ** 1.6
    return np.repeat(out[..., None], 3, axis=2)


def fx_ink(a, thr=0.5):
    """Line art from edges (difference of Gaussians), like a brush-pen trace of the photo."""
    l = (np.clip(lum(a), 0, 1) * 255).astype(np.uint8)
    s = max(a.shape[:2]) / 1000
    g1 = np.asarray(Image.fromarray(l).filter(ImageFilter.GaussianBlur(1.0 * s)), np.float32)
    g2 = np.asarray(Image.fromarray(l).filter(ImageFilter.GaussianBlur(2.2 * s)), np.float32)
    dog = g1 - g2
    line = 0.5 + 0.5 * np.tanh((dog + 4 * (1 - thr)) * 0.8)   # dark side of an edge -> 0
    shade = (g1 / 255) < thr * 0.35                       # solid blacks in the darkest areas
    out = np.where(shade, 0.05, 0.05 + 0.9 * line)
    return np.repeat(out[..., None], 3, axis=2).astype(np.float32)


def fx_paper(a, k=1.0, rng=None):
    """Cold-press paper: fibres and tooth multiplied in, ink sits in the valleys."""
    h, w = a.shape[:2]
    n = rng.normal(0, 1, (h, w)).astype(np.float32)
    tooth = _box(n, 1) * 0.6 + _box(n, 4) * 1.4
    fib = np.asarray(Image.fromarray(((n * 0.5 + 0.5).clip(0, 1) * 255).astype(np.uint8)).filter(
        ImageFilter.BoxBlur(3)).resize((w // 6 + 1, h)).resize((w, h)), np.float32) / 255 - 0.5
    tex = 1 + (tooth * 0.06 + fib * 0.08) * k
    warm = np.array([1.0, 0.985, 0.95], np.float32)
    return (a * tex[..., None]) * (1 - 0.15 * k * (1 - warm))


FX = {"flash": fx_flash, "crush": fx_crush, "grain": fx_grain, "duotone": fx_duotone, "tint": fx_tint, "halftone": fx_halftone,
      "xerox": fx_xerox, "bitmap": fx_bitmap, "chroma": fx_chroma, "motion": fx_motion, "dream": fx_dream, "pixel": fx_pixel,
      "scanlines": fx_scanlines, "vhs": fx_vhs, "vignette": fx_vignette, "sharpen": fx_sharpen,
      "paint": fx_paint, "sketch": fx_sketch, "ink": fx_ink, "paper": fx_paper}
NEEDS_RNG = {"grain", "xerox", "vhs", "paper"}


def parse_chain(spec):
    """'flash,duotone=#000,#f00,grain=0.2' -> [(flash,[]),(duotone,[#000,#f00]),(grain,[0.2])]"""
    items, cur = [], None
    for tok in spec.split(","):
        tok = tok.strip()
        name, eq, val = tok.partition("=")
        if name in FX:
            cur = (name, [val] if eq else [])
            items.append(cur)
        elif cur is not None:
            cur[1].append(tok)
        else:
            sys.exit(f"unknown effect: {tok} (see --list)")
    return items


def main():
    ap = argparse.ArgumentParser(description=FX_HELP, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", nargs="?"); ap.add_argument("output", nargs="?")
    ap.add_argument("--fx", default="flash,grain=0.12")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()
    if a.list or not (a.input and a.output):
        print(FX_HELP); return
    src = Image.open(a.input)
    alpha = src.getchannel("A") if src.mode in ("RGBA", "LA") else None
    arr = np.asarray(ImageOps.exif_transpose(src).convert("RGB"), np.float32) / 255
    rng = np.random.default_rng(a.seed)
    for name, args in parse_chain(a.fx):
        vals = [v if v.startswith("#") else float(v) for v in args]
        fn = FX[name]
        arr = fn(arr, *vals, rng=rng) if name in NEEDS_RNG else fn(arr, *vals)
        arr = np.clip(arr, 0, 1).astype(np.float32)
    out = Image.fromarray((arr * 255).astype(np.uint8))
    if alpha is not None and alpha.size == out.size:
        out.putalpha(alpha)
    out.save(a.output, quality=92)
    print(f"saved {a.output} ({out.size[0]}×{out.size[1]})")


if __name__ == "__main__":
    main()
