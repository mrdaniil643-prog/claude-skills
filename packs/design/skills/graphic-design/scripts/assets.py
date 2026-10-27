#!/usr/bin/env python3
"""Get design material: icons (SVG), licensed photos, background cut-outs.

  python3 assets.py icon-search coffee                  find icons across sets
  python3 assets.py icon lucide:coffee ph:star-fill --color "#13213C" --out icons
  python3 assets.py photo "coffee beans macro" --n 6 --out photos
  python3 assets.py cutout portrait.jpg portrait-cut.png [--person]
  uv run --with segno python assets.py qr "https://tickets.example/tour" qr.svg [--dark "#000"] [--light none]
  uv run --with opencv-python-headless python assets.py qrcheck poster.png   decode the QR in a finished render

Icons come from Iconify (200+ open sets: lucide, tabler, ph, solar, mdi,
material-symbols, simple-icons for brand logos...). When the API is unreachable
the set is fetched once as the npm package @iconify-json/<set> and cached in
~/.cache/graphic-design/icons. Check each set's licence before commercial use
(lucide ISC, tabler MIT, ph MIT, solar CC BY 4.0, mdi Apache 2.0).

Photos come from Openverse (CC-licensed, commercial use + modification only);
credits.txt records author, licence and source for each file. Cut-outs run
rembg locally through uvx (the model, ~170 MB, downloads on first use).
"""
import argparse
import io
import json
import pathlib
import re
import subprocess
import sys
import tarfile
import urllib.parse
import urllib.request

CACHE = pathlib.Path.home() / ".cache" / "graphic-design" / "icons"
FALLBACK_SETS = ["lucide", "tabler", "ph", "solar"]
UA = {"User-Agent": "graphic-design-skill/1.0"}


def fetch(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return r.read()


def icon_set(prefix):
    """Whole Iconify set as JSON, from cache or the npm package."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{prefix}.json"
    if not path.exists():
        tgz = subprocess.run(
            ["npm", "pack", "-s", f"@iconify-json/{prefix}", "--pack-destination", str(CACHE)],
            capture_output=True, text=True, shell=sys.platform == "win32",
        )
        if tgz.returncode:
            sys.exit(f"no icon set '{prefix}': {tgz.stderr.strip()[:200]}")
        archive = CACHE / tgz.stdout.strip().splitlines()[-1]
        with tarfile.open(archive) as t:
            path.write_bytes(t.extractfile("package/icons.json").read())
        archive.unlink()
    return json.loads(path.read_text(encoding="utf-8"))


def svg_from_set(data, name):
    icons, aliases = data.get("icons", {}), data.get("aliases", {})
    seen = 0
    while name not in icons and name in aliases and seen < 5:
        name, seen = aliases[name]["parent"], seen + 1
    if name not in icons:
        return None
    ic = icons[name]
    w, h = ic.get("width", data.get("width", 16)), ic.get("height", data.get("height", 16))
    left, top = ic.get("left", 0), ic.get("top", 0)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{left} {top} {w} {h}" '
            f'width="{w}" height="{h}">{ic["body"]}</svg>')


def cmd_icon(a):
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for ref in a.names:
        prefix, _, name = ref.partition(":")
        try:
            svg = fetch(f"https://api.iconify.design/{prefix}/{name}.svg").decode()
        except Exception:
            svg = svg_from_set(icon_set(prefix), name)
        if not svg or "<svg" not in svg:
            sys.exit(f"{ref}: no such icon (try icon-search)")
        if a.color:
            svg = svg.replace("currentColor", a.color)
        dest = out / f"{prefix}-{name}.svg"
        dest.write_text(svg, encoding="utf-8")
        print(dest)


def cmd_icon_search(a):
    try:
        res = json.loads(fetch(f"https://api.iconify.design/search?query={urllib.parse.quote(a.query)}&limit={a.n}"))
        hits = res.get("icons", [])
        source = "api.iconify.design"
    except Exception:
        hits, source = [], f"npm-наборы {', '.join(FALLBACK_SETS)}"
        words = a.query.lower().split()
        for prefix in FALLBACK_SETS:
            data = icon_set(prefix)
            names = list(data.get("icons", {})) + list(data.get("aliases", {}))
            hits += [f"{prefix}:{n}" for n in names if all(w in n for w in words)]
        hits = hits[: a.n]
    print(f"{len(hits)} найдено ({source})")
    for h in hits:
        print(h)


def cmd_photo(a):
    q = urllib.parse.urlencode({"q": a.query, "license_type": "commercial,modification", "page_size": a.n})
    try:
        res = json.loads(fetch(f"https://api.openverse.org/v1/images/?{q}"))
    except Exception as e:
        sys.exit(f"Openverse недоступен ({e}). Попроси фото у пользователя или используй генератор изображений.")
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    credits = []
    for i, r in enumerate(res.get("results", []), 1):
        ext = (re.search(r"\.(jpe?g|png|webp)(\?|$)", r["url"], re.I) or [None, "jpg"])[1].lower()
        dest = out / f"{i:02d}-{re.sub(r'[^a-z0-9]+', '-', (r.get('title') or 'photo').lower())[:40].strip('-')}.{ext}"
        try:
            dest.write_bytes(fetch(r["url"], timeout=40))
        except Exception as e:
            print(f"skip {r['url']}: {e}", file=sys.stderr)
            continue
        lic = f"CC {r['license'].upper()} {r.get('license_version') or ''}".strip()
        credits.append(f"{dest.name}: «{r.get('title')}» — {r.get('creator') or 'автор не указан'}, {lic}, {r.get('foreign_landing_url')}")
        print(f"{dest}  {r.get('width')}×{r.get('height')}  {lic}")
    (out / "credits.txt").write_text("\n".join(credits) + "\n", encoding="utf-8")
    print(f"{out / 'credits.txt'} — указывай авторство, если лицензия BY")


def cmd_cutout(a):
    model = "u2net_human_seg" if a.person else a.model
    cmd = ["uvx", "-q", "--from", "rembg[cpu,cli]", "rembg", "i", "-m", model]
    if a.alpha_matting:
        cmd += ["-a"]
    r = subprocess.run(cmd + [a.input, a.output], shell=sys.platform == "win32")
    if r.returncode:
        sys.exit("rembg не отработал: нужен uv (https://docs.astral.sh/uv/) и доступ к PyPI/GitHub")
    print(a.output)


def cmd_qr(a):
    try:
        import segno
    except ImportError:
        sys.exit("нужен segno: uv run --with segno python assets.py qr ...")
    q = segno.make(a.data, error="m")
    q.save(a.out, scale=10, border=4, dark=a.dark, light=None if a.light == "none" else a.light)
    print(f"{a.out}  ({q.version}-{q.error}; печатай ≥ 20 мм, проверь камерой телефона)")


def cmd_qrcheck(a):
    try:
        import cv2
    except ImportError:
        sys.exit("нужен OpenCV: uv run --with opencv-python-headless python assets.py qrcheck ...")
    img = cv2.imread(a.image)
    if img is None:
        sys.exit(f"не открыть {a.image}")
    det, h, w = cv2.QRCodeDetector(), img.shape[0], img.shape[1]
    # A phone is pointed at the code; emulate that with zooms and crops of the frame.
    tries = [img, cv2.resize(img, None, fx=2, fy=2)]
    for fy in (0, 0.25, 0.5):
        for fx in (0, 0.25, 0.5):
            tries.append(img[int(h * fy):int(h * (fy + 0.5)), int(w * fx):int(w * (fx + 0.5))])
    for im in tries:
        val = det.detectAndDecode(im)[0]
        if val:
            print(f"QR читается: {val}")
            return
    sys.exit("QR не найден или не читается: увеличь, добавь светлую рамку (тихую зону), убери текстуру поверх")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("icon"); p.add_argument("names", nargs="+", help="set:name"); p.add_argument("--color"); p.add_argument("--out", default="icons")
    p.set_defaults(fn=cmd_icon)
    p = sub.add_parser("icon-search"); p.add_argument("query"); p.add_argument("--n", type=int, default=30)
    p.set_defaults(fn=cmd_icon_search)
    p = sub.add_parser("photo"); p.add_argument("query"); p.add_argument("--n", type=int, default=6); p.add_argument("--out", default="photos")
    p.set_defaults(fn=cmd_photo)
    p = sub.add_parser("cutout"); p.add_argument("input"); p.add_argument("output")
    p.add_argument("--person", action="store_true", help="модель для людей (u2net_human_seg)")
    p.add_argument("--model", default="isnet-general-use", help="u2net, isnet-general-use, birefnet-general, birefnet-portrait")
    p.add_argument("--alpha-matting", action="store_true", help="мягче край волос/меха, медленнее")
    p.set_defaults(fn=cmd_cutout)
    p = sub.add_parser("qr"); p.add_argument("data"); p.add_argument("out"); p.add_argument("--dark", default="#000000"); p.add_argument("--light", default="#ffffff")
    p.set_defaults(fn=cmd_qr)
    p = sub.add_parser("qrcheck"); p.add_argument("image"); p.set_defaults(fn=cmd_qrcheck)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
