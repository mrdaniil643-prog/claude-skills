#!/usr/bin/env python3
"""Build and check colour palettes in OKLCH.

  python3 palette.py from-hex "#D9541E" [--scheme complement|analogous|triad|split|mono] [--dark]
  uv run --with pillow python palette.py from-image reference.jpg [--n 6]
  python3 palette.py contrast "#F3ECE0" "#13213C"

from-hex   : brand colour -> background, ink, 9-step tint scale, accent; CSS
             variables and a contrast matrix, every pair WCAG-rated.
from-image : dominant colours of a reference (share %, OKLCH) and suggested
             roles: background, text, accent.
contrast   : WCAG ratio of two colours.
"""
import argparse
import math
import sys


# ---------- colour maths: sRGB <-> OKLab/OKLCH ----------
def hex_to_rgb(h):
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{round(min(1, max(0, c)) * 255):02X}" for c in rgb)


def lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def delin(c):
    return 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def rgb_to_oklch(rgb):
    r, g, b = (lin(c) for c in rgb)
    l = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    L = 0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s
    A = 1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s
    B = 0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s
    return L, math.hypot(A, B), math.degrees(math.atan2(B, A)) % 360


def oklch_to_rgb_raw(L, C, H):
    a, b = C * math.cos(math.radians(H)), C * math.sin(math.radians(H))
    l = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3
    r = 4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return tuple(delin(c) if c >= 0 else -delin(-c) for c in (r, g, bb))


def oklch_to_rgb(L, C, H):
    """Reduce chroma until the colour fits sRGB (keeps hue and lightness)."""
    lo, hi = 0.0, C
    rgb = oklch_to_rgb_raw(L, C, H)
    if all(-1e-4 <= c <= 1 + 1e-4 for c in rgb):
        return rgb
    for _ in range(24):
        mid = (lo + hi) / 2
        if all(-1e-4 <= c <= 1 + 1e-4 for c in oklch_to_rgb_raw(L, mid, H)):
            lo = mid
        else:
            hi = mid
    return oklch_to_rgb_raw(L, lo, H)


def contrast(a, b):
    def y(rgb):
        r, g, bb = (lin(c) for c in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * bb
    hi, lo = sorted((y(a), y(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def grade(r):
    return "AAA" if r >= 7 else "AA" if r >= 4.5 else "AA крупный" if r >= 3 else "нельзя для текста"


def fmt(h):
    L, C, H = rgb_to_oklch(hex_to_rgb(h))
    return f"{h}  oklch({L * 100:.0f}% {C:.3f} {H:.0f})"


# ---------- commands ----------
def cmd_contrast(a):
    r = contrast(hex_to_rgb(a.a), hex_to_rgb(a.b))
    print(f"{a.a} / {a.b}: {r:.2f}:1 — {grade(r)}")


def cmd_from_hex(a):
    L, C, H = rgb_to_oklch(hex_to_rgb(a.hex))
    offsets = {"complement": [180], "analogous": [-30, 30], "triad": [120, 240], "split": [150, 210], "mono": []}[a.scheme]
    mk = lambda l, c, h: rgb_to_hex(oklch_to_rgb(l, c, h % 360))
    # Tint scale: equal lightness steps, chroma eased toward the ends so the
    # lightest and darkest steps stay clean instead of muddy or neon.
    scale = {}
    for step, l in zip((50, 100, 200, 300, 400, 500, 600, 700, 800, 900), (0.97, 0.93, 0.86, 0.78, 0.69, 0.60, 0.51, 0.42, 0.33, 0.24)):
        scale[step] = mk(l, C * (1 - abs(l - 0.6) * 0.9), H)
    accent_h = H + (offsets[0] if offsets else 0)
    accent = mk(max(0.55, min(0.8, L)), max(C, 0.12) if offsets else C, accent_h)
    extra = [mk(0.65, max(C * 0.8, 0.08), H + o) for o in offsets[1:]]
    if a.dark:
        bg, surface, ink, muted = mk(0.17, min(C, 0.03), H), mk(0.23, min(C, 0.035), H), mk(0.96, 0.01, H), mk(0.75, 0.02, H)
    else:
        bg, surface, ink, muted = mk(0.975, min(C, 0.012), H), mk(0.94, min(C, 0.02), H), mk(0.2, min(C, 0.04), H), mk(0.45, min(C, 0.03), H)
    roles = {"bg": bg, "surface": surface, "ink": ink, "muted": muted, "brand": a.hex.upper(), "accent": accent}
    for i, e in enumerate(extra, 2):
        roles[f"accent-{i}"] = e

    print("Роли:")
    for k, v in roles.items():
        print(f"  --{k:<9} {fmt(v)}")
    print("Шкала бренда:")
    for k, v in scale.items():
        print(f"  --brand-{k:<4} {fmt(v)}")
    print("\nКонтраст (текст / фон):")
    for fg in ("ink", "muted", "brand", "accent"):
        for bgk in ("bg", "surface", "brand"):
            if fg == bgk:
                continue
            r = contrast(hex_to_rgb(roles[fg]), hex_to_rgb(roles[bgk]))
            print(f"  {fg:>6} на {bgk:<7} {r:5.2f}:1  {grade(r)}")
    on_brand = max(("#FFFFFF", roles["ink"]), key=lambda c: contrast(hex_to_rgb(c), hex_to_rgb(roles["brand"])))
    print(f"  текст на brand: {on_brand} ({contrast(hex_to_rgb(on_brand), hex_to_rgb(roles['brand'])):.2f}:1)")
    print("\n:root {")
    for k, v in roles.items():
        print(f"  --{k}: {v};")
    for k, v in scale.items():
        print(f"  --brand-{k}: {v};")
    print("}")


def cmd_from_image(a):
    try:
        from PIL import Image
    except ImportError:
        sys.exit("нужен Pillow: uv run --with pillow python palette.py from-image ...")
    im = Image.open(a.image).convert("RGB")
    im.thumbnail((300, 300))
    q = im.quantize(colors=max(a.n * 3, 12), method=Image.Quantize.MEDIANCUT, kmeans=4)
    pal = q.getpalette()
    counts = sorted(q.getcolors(), reverse=True)
    total = sum(c for c, _ in counts)
    picked = []
    for c, idx in counts:
        rgb = tuple(v / 255 for v in pal[idx * 3: idx * 3 + 3])
        lab = rgb_to_oklch(rgb)
        # Skip near-duplicates so the list shows distinct colours, not shades.
        if any(abs(lab[0] - p[1][0]) < 0.06 and _hue_close(lab, p[1]) for p in picked):
            continue
        picked.append((rgb, lab, c / total))
        if len(picked) == a.n:
            break
    print("Доминирующие цвета:")
    for rgb, (L, C, H), share in picked:
        print(f"  {rgb_to_hex(rgb)}  {share * 100:4.1f} %  oklch({L * 100:.0f}% {C:.3f} {H:.0f})")
    bg = picked[0][0]
    text = max(picked, key=lambda p: contrast(p[0], bg))[0]
    accent = max(picked[1:] or picked, key=lambda p: p[1][1])[0]
    print(f"\nРоли: фон {rgb_to_hex(bg)}, текст {rgb_to_hex(text)} ({contrast(text, bg):.1f}:1), акцент {rgb_to_hex(accent)}")
    if contrast(text, bg) < 4.5:
        print("  В референсе нет пары для мелкого текста ≥ 4.5:1: добавь тёмный/светлый нейтральный.")


def _hue_close(a, b):
    if a[1] < 0.03 and b[1] < 0.03:
        return True
    d = abs(a[2] - b[2]) % 360
    return min(d, 360 - d) < 18 and abs(a[1] - b[1]) < 0.05


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("from-hex"); p.add_argument("hex")
    p.add_argument("--scheme", default="complement", choices=["complement", "analogous", "triad", "split", "mono"])
    p.add_argument("--dark", action="store_true", help="тёмная тема: тёмный фон, светлый текст")
    p.set_defaults(fn=cmd_from_hex)
    p = sub.add_parser("from-image"); p.add_argument("image"); p.add_argument("--n", type=int, default=6)
    p.set_defaults(fn=cmd_from_image)
    p = sub.add_parser("contrast"); p.add_argument("a"); p.add_argument("b")
    p.set_defaults(fn=cmd_contrast)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
