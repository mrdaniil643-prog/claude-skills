#!/usr/bin/env python3
"""Expressive type library: find, fetch, preview and extend display fonts by style.

  python3 typelib.py styles                              styles and how many fonts have Cyrillic
  python3 typelib.py list horror [--cyr] [--color]       fonts of a style (--cyr: full Cyrillic only)
  python3 typelib.py find "rubik"                        search by name
  python3 typelib.py get "Creepster" "Rubik Wet Paint" --out fonts
  python3 typelib.py specimen out.png --text "Кровавая луна" --style horror [--cyr]
  python3 typelib.py specimen out.png --text "DARK" --fonts "Pirata One,UnifrakturCook"
  python3 typelib.py check MyFont.otf "Текст заголовка"  which characters are missing
  python3 typelib.py add MyGothic.otf --style gothic [--name "My Gothic"]

The built-in catalog (references/fonts.json) holds ~230 Google Fonts (OFL/Apache,
free for commercial use) sorted into 15 styles, each checked glyph by glyph for
Cyrillic. `add` copies a font you own into ~/.graphic-design/fonts and records it
in ~/.graphic-design/fonts.json, so every later project can use it the same way.
Downloads go through the Google Fonts CSS API, falling back to the GitHub repo.
`specimen` and `check` need fontTools for local files (uv run --with fonttools).
"""
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
CATALOG = HERE.parent / "references" / "fonts.json"
USER_DIR = pathlib.Path.home() / ".graphic-design"
USER_CATALOG = USER_DIR / "fonts.json"
CACHE = pathlib.Path.home() / ".cache" / "graphic-design" / "fonts"
UA = "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/534.24 (KHTML, like Gecko)"
CYR_UP = "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
CYR = CYR_UP + CYR_UP.lower()


def load():
    cat = json.loads(CATALOG.read_text(encoding="utf-8"))
    if USER_CATALOG.exists():
        user = json.loads(USER_CATALOG.read_text(encoding="utf-8"))
        names = {f["name"] for f in user}
        cat["fonts"] = [f for f in cat["fonts"] if f["name"] not in names] + user
    return cat


def by_name(cat, name):
    for f in cat["fonts"]:
        if f["name"].lower() == name.lower():
            return f
    sys.exit(f"нет в каталоге: {name} (typelib.py find ...)")


def flag(f):
    cyr = {"full": "кир", "partial": "кир≈", "none": "лат"}[f["cyrillic"]]
    extra = []
    if f.get("color"):
        extra.append("цветной")
    if f.get("axes"):
        extra.append("вариативный " + ",".join(f"{a[0]} {a[1]:g}–{a[2]:g}" for a in f["axes"]))
    elif len(f.get("weights", [])) > 1:
        extra.append("начертания " + ",".join(map(str, f["weights"])))
    if f.get("user"):
        extra.append("свой")
    if f.get("note"):
        extra.append(f["note"])
    return f"{cyr:4} {f['name']:<28} {'; '.join(extra)}"


def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=40) as r:
        return r.read()


def ensure(f, out=None):
    """Return local font files for a catalog entry, downloading if needed."""
    if f.get("user"):
        return [pathlib.Path(f["file"])]
    dest = pathlib.Path(out) if out else CACHE
    dest.mkdir(parents=True, exist_ok=True)
    base = f["name"].replace(" ", "")
    have = sorted(dest.glob(f"{base}-*.ttf"))
    if have:
        return have
    files = []
    weights = f.get("weights") or [400]
    query = urllib.parse.quote(f["name"]) + ":wght@" + ";".join(map(str, weights))
    try:
        css = fetch(f"https://fonts.googleapis.com/css2?family={query}&display=swap").decode()
        for block in re.findall(r"@font-face\s*{[^}]+}", css):
            w = re.search(r"font-weight:\s*(\d+)", block).group(1)
            if re.search(r"font-style:\s*italic", block):
                continue
            p = dest / f"{base}-{w}.ttf"
            p.write_bytes(fetch(re.search(r"url\((https://[^)]+)\)", block).group(1)))
            files.append(p)
    except Exception:
        # Fallback: the original (possibly variable) file from github.com/google/fonts.
        p = dest / f"{base}-{'var' if f.get('axes') else weights[0]}.ttf"
        p.write_bytes(fetch(f"https://raw.githubusercontent.com/google/fonts/main/{urllib.parse.quote(f['path'])}"))
        files.append(p)
    return files


def face_css(f, files):
    rules = []
    for p in files:
        m = re.search(r"-(\d+)\.(ttf|otf)$", p.name)
        weight = m.group(1) if m else (f"{f['axes'][0][1]:g} {f['axes'][0][2]:g}" if f.get("axes") and f["axes"][0][0] == "wght" else "400")
        rules.append(f"@font-face{{font-family:'{f['name']}';src:url('{p.resolve().as_uri()}');font-weight:{weight}}}")
    return "\n".join(rules)


TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
                    ["a", "b", "v", "g", "d", "e", "yo", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t",
                     "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"]))


def translit(text):
    out = []
    for ch in text:
        t = TRANSLIT.get(ch.lower(), ch)
        out.append(t.upper() if ch.isupper() and len(t) == 1 else (t.capitalize() if ch.isupper() else t))
    return "".join(out)


def missing_chars(path, text):
    from fontTools.ttLib import TTFont
    cmap = TTFont(path, lazy=True).getBestCmap() or {}
    return sorted({ch for ch in text if not ch.isspace() and ord(ch) not in cmap})


# ---------- commands ----------
def cmd_styles(a):
    cat = load()
    for key, title in cat["styles"].items():
        fs = [f for f in cat["fonts"] if key in f["styles"]]
        cyr = sum(f["cyrillic"] == "full" for f in fs)
        print(f"{key:12} {len(fs):3} шрифтов, с кириллицей {cyr:2} — {title}")


def cmd_list(a):
    cat = load()
    if a.style not in cat["styles"]:
        sys.exit(f"нет стиля {a.style}; есть: {', '.join(cat['styles'])}")
    fs = [f for f in cat["fonts"] if a.style in f["styles"]]
    if a.cyr:
        fs = [f for f in fs if f["cyrillic"] == "full"]
    if a.color:
        fs = [f for f in fs if f.get("color")]
    print(f"{a.style}: {cat['styles'][a.style]} — {len(fs)}")
    for f in sorted(fs, key=lambda f: (f["cyrillic"] != "full", f["name"])):
        print("  " + flag(f))


def cmd_find(a):
    q = a.query.lower()
    for f in load()["fonts"]:
        if q in f["name"].lower():
            print(flag(f), " стили:", ", ".join(f["styles"]))


def cmd_get(a):
    cat = load()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    css_file = out / "fonts.css"
    rules = {}
    if css_file.exists():
        for line in css_file.read_text(encoding="utf-8").splitlines():
            m = re.search(r"src: url\('([^']+)'\)", line)
            if m:
                rules[m.group(1)] = line
    for name in a.names:
        f = by_name(cat, name)
        for p in ensure(f, out):
            if f.get("user"):
                shutil.copy(p, out / p.name)
                p = out / p.name
            m = re.search(r"-(\d+)\.(ttf|otf)$", p.name)
            weight = m.group(1) if m else ("100 900" if f.get("axes") else str((f.get("weights") or [400])[0]))
            rules[p.name] = (f"@font-face {{ font-family: '{f['name']}'; font-weight: {weight}; font-style: normal; "
                             f"src: url('{p.name}'); }}")
            print(p)
        if f.get("cyr_tracking"):
            print(f"  ! {f['name']}: {f['note']}")
        if f["cyrillic"] != "full":
            print(f"  ! {f['name']}: {'кириллица неполная' if f['cyrillic'] == 'partial' else 'нет кириллицы'} — для русского текста возьми замену: typelib.py list {f['styles'][0]} --cyr")
    css_file.write_text("\n".join(rules[k] for k in sorted(rules)) + "\n", encoding="utf-8")
    print(css_file)


def cmd_specimen(a):
    cat = load()
    if a.fonts:
        fs = [by_name(cat, n.strip()) for n in a.fonts.split(",")]
    elif a.style:
        fs = [f for f in cat["fonts"] if a.style in f["styles"]]
    else:
        sys.exit("укажи --style или --fonts")
    text = a.text or ("Тёмная ночь 1984" if a.cyr else "Тёмная ночь · Dark Night")
    needs_cyr = bool(set(text) & set(CYR))
    if a.cyr:
        fs = [f for f in fs if f["cyrillic"] == "full"]
    rows, css = [], []
    for f in fs:
        try:
            files = ensure(f)
        except Exception as e:
            print(f"skip {f['name']}: {e}", file=sys.stderr)
            continue
        css.append(face_css(f, files))
        miss = missing_chars(files[-1], text) if needs_cyr or f.get("user") else []
        # A Latin-only font still shows its character, on the transliterated text.
        shown = text if not miss else translit(text)
        warn = f"<i>нет кириллицы — показан транслит</i>" if miss and f["cyrillic"] == "none" else (f"<i>нет: {''.join(miss[:12])}</i>" if miss else "")
        weight = max(f.get("weights") or [400]) if a.heavy else (400 if 400 in (f.get("weights") or [400]) else (f.get("weights") or [400])[0])
        # Japanese fonts set Cyrillic on full-width cells; apply the catalog's tracking.
        track = (f"letter-spacing:{f['cyr_tracking']}em;word-spacing:{-f['cyr_tracking'] + 0.05:.2f}em;"
                 if f.get("cyr_tracking") and not miss and needs_cyr else "")
        rows.append(f"<div class=row><div class=lab>{f['name']}<br><span>{flag(f).split()[0]} · {', '.join(f['styles'])}</span>{warn}</div>"
                    f"<div class=s style=\"font-family:'{f['name']}';font-weight:{weight};{track}\">{shown}</div></div>")
    html = f"""<!doctype html><meta charset=utf-8><style>{''.join(css)}
      body{{margin:0;padding:24px;background:{a.bg};color:{a.fg};font:13px system-ui,sans-serif}}
      .row{{display:grid;grid-template-columns:230px 1fr;align-items:center;border-bottom:1px solid rgba(127,127,127,.25);padding:6px 0}}
      .lab{{font-weight:600}} .lab span{{font-weight:400;opacity:.6}} .lab i{{display:block;color:#e5484d;font-style:normal}}
      .s{{font-size:{a.size}px;line-height:1.15;white-space:nowrap;overflow:hidden}}</style>
      <h3 style="margin:0 0 10px">{a.style or 'Образцы'} — «{text}»</h3>{''.join(rows)}"""
    tmp = pathlib.Path(tempfile.mkdtemp()) / "specimen.html"
    tmp.write_text(html, encoding="utf-8")
    js = (f"const {{chromium}}=require('playwright');(async()=>{{const b=await chromium.launch();"
          f"const p=await b.newPage({{viewport:{{width:{a.width},height:400}}}});await p.goto({json.dumps(tmp.as_uri())});"
          f"await p.evaluate(()=>document.fonts.ready);await p.screenshot({{path:{json.dumps(str(pathlib.Path(a.out).resolve()))},fullPage:true,"
          f"type:{json.dumps('jpeg' if a.out.endswith(('.jpg', '.jpeg')) else 'png')}{',quality:82' if a.out.endswith(('.jpg', '.jpeg')) else ''}}});await b.close()}})()")
    r = subprocess.run(["node", "-e", js], shell=False)
    if r.returncode:
        sys.exit("рендер не удался: нужен Node.js с playwright")
    print(f"{a.out} ({len(rows)} шрифтов)")


def cmd_check(a):
    path = pathlib.Path(a.font)
    if not path.exists():
        f = by_name(load(), a.font)
        path = ensure(f)[-1]
    miss = missing_chars(path, a.text)
    print("все символы есть" if not miss else f"нет символов: {' '.join(miss)}")
    sys.exit(1 if miss else 0)


def cmd_add(a):
    from fontTools.ttLib import TTFont
    src = pathlib.Path(a.font)
    t = TTFont(src, lazy=True)
    cmap = t.getBestCmap() or {}
    up = sum(ord(c) in cmap for c in CYR_UP)
    lo = sum(ord(c) in cmap for c in CYR_UP.lower())
    name = a.name or t["name"].getBestFamilyName()
    cat = load()
    styles = a.style.split(",")
    for s in styles:
        if s not in cat["styles"]:
            sys.exit(f"нет стиля {s}; есть: {', '.join(cat['styles'])}")
    (USER_DIR / "fonts").mkdir(parents=True, exist_ok=True)
    dest = USER_DIR / "fonts" / src.name
    shutil.copy(src, dest)
    entry = {"name": name, "styles": styles, "cyrillic": "full" if up == lo == 33 else ("partial" if up else "none"),
             "latin": all(ord(c) in cmap for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"), "weights": [t["OS/2"].usWeightClass],
             "axes": [[x.axisTag, x.minValue, x.maxValue] for x in t["fvar"].axes] if "fvar" in t else [],
             "color": any(tag in t for tag in ("COLR", "SVG ", "CBDT", "sbix")), "user": True, "file": str(dest),
             "license": a.license or "проверь лицензию"}
    user = json.loads(USER_CATALOG.read_text(encoding="utf-8")) if USER_CATALOG.exists() else []
    user = [u for u in user if u["name"] != name] + [entry]
    USER_CATALOG.write_text(json.dumps(user, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"добавлен: {flag(entry)} → {dest}")
    if entry["cyrillic"] != "full":
        print(f"  кириллица: прописных {up}/33, строчных {lo}/33")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("styles").set_defaults(fn=cmd_styles)
    p = sub.add_parser("list"); p.add_argument("style"); p.add_argument("--cyr", action="store_true"); p.add_argument("--color", action="store_true"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("find"); p.add_argument("query"); p.set_defaults(fn=cmd_find)
    p = sub.add_parser("get"); p.add_argument("names", nargs="+"); p.add_argument("--out", default="fonts"); p.set_defaults(fn=cmd_get)
    p = sub.add_parser("specimen"); p.add_argument("out"); p.add_argument("--text"); p.add_argument("--style"); p.add_argument("--fonts")
    p.add_argument("--cyr", action="store_true"); p.add_argument("--heavy", action="store_true", help="самое жирное начертание")
    p.add_argument("--size", type=int, default=46); p.add_argument("--width", type=int, default=1400)
    p.add_argument("--bg", default="#f4f2ee"); p.add_argument("--fg", default="#111"); p.set_defaults(fn=cmd_specimen)
    p = sub.add_parser("check"); p.add_argument("font"); p.add_argument("text"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("add"); p.add_argument("font"); p.add_argument("--style", required=True, help="стиль или несколько через запятую")
    p.add_argument("--name"); p.add_argument("--license"); p.set_defaults(fn=cmd_add)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
