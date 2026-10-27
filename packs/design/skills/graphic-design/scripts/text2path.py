"""Turn lettering into SVG outlines with real shaping (kerning, ligatures, Cyrillic).

  uv run --with uharfbuzz --with fonttools python text2path.py Font.ttf "ТЕКСТ" > word.svg
      [--size 200] [--tracking 0.04] [--features "ss01,-liga"] [--var "wght=800"]
      [--fill "#111"] [--id wordmark]

Prints a standalone SVG whose viewBox hugs the ink. Logos must ship as outlines
so they look the same everywhere without the font installed; paste the <path>
into the logo file and position it with a transform.
"""
import argparse
import re
import sys

import uharfbuzz as hb
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("font")
    ap.add_argument("text")
    ap.add_argument("--size", type=float, default=200, help="font size in SVG units")
    ap.add_argument("--tracking", type=float, default=0, help="extra letter spacing in em (0.04 = +4%%)")
    ap.add_argument("--features", default="", help='OpenType features, e.g. "ss01,-liga,tnum"')
    ap.add_argument("--var", default="", help='variable axes, e.g. "wght=800,wdth=90"')
    ap.add_argument("--fill", default="#111")
    ap.add_argument("--id", default="text")
    a = ap.parse_args()

    blob = hb.Blob.from_file_path(a.font)
    face = hb.Face(blob)
    font = hb.Font(face)
    location = {}
    if a.var:
        location = {k: float(v) for k, v in (p.split("=") for p in a.var.split(","))}
        font.set_variations(location)

    buf = hb.Buffer()
    buf.add_str(a.text)
    buf.guess_segment_properties()
    features = {}
    for f in filter(None, (x.strip() for x in a.features.split(","))):
        features[f.lstrip("-+")] = not f.startswith("-")
    hb.shape(font, buf, features)

    tt = TTFont(a.font)
    upem = tt["head"].unitsPerEm
    glyphs = tt.getGlyphSet(location=location or None)
    order = tt.getGlyphOrder()
    k = a.size / upem
    track = a.tracking * upem

    pen = SVGPathPen(glyphs)
    bounds = BoundsPen(glyphs)
    x = 0
    missing = sorted({a.text[info.cluster] for info in buf.glyph_infos if info.codepoint == 0})
    if missing:
        sys.exit(f"the font has no glyphs for: {' '.join(missing)}")
    for i, (info, pos) in enumerate(zip(buf.glyph_infos, buf.glyph_positions)):
        name = order[info.codepoint]
        # Flip Y (font units go up, SVG goes down) and scale to --size.
        m = (k, 0, 0, -k, (x + pos.x_offset) * k, -pos.y_offset * k)
        glyphs[name].draw(TransformPen(pen, m))
        glyphs[name].draw(TransformPen(bounds, m))
        x += pos.x_advance + (track if i < len(buf.glyph_infos) - 1 else 0)

    if not bounds.bounds:
        sys.exit("nothing drawn: does the font cover these characters?")
    x0, y0, x1, y1 = bounds.bounds
    w, h = x1 - x0, y1 - y0
    # Hundredths of a unit are invisible at any size and keep the file small.
    d = re.sub(r"-?\d+\.\d+", lambda m: f"{float(m.group()):.2f}".rstrip("0").rstrip("."), pen.getCommands())
    print(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0:.2f} {y0:.2f} {w:.2f} {h:.2f}" '
        f'width="{w:.0f}" height="{h:.0f}">\n'
        f'  <path id="{a.id}" fill="{a.fill}" d="{d}"/>\n</svg>'
    )


if __name__ == "__main__":
    main()
