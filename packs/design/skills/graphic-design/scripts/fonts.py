#!/usr/bin/env python3
"""Download Google Fonts as local TTF files (Cyrillic included) plus a fonts.css.

  python3 fonts.py "Unbounded:700,900" "Inter:400,600" --out fonts

Writes fonts/<Family>-<weight>.ttf and fonts/fonts.css with @font-face rules
pointing at them. Local files make renders reproducible offline and are what
text2path.py needs to turn a logo's lettering into outlines.
"""
import argparse
import pathlib
import re
import sys
import urllib.parse
import urllib.request

# An old desktop user agent makes the CSS API answer with plain, unsubset TTF.
UA = "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/534.24 (KHTML, like Gecko)"


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("families", nargs="+", help='"Family Name:400,700" (weights optional, default 400)')
    ap.add_argument("--out", default="fonts")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    css_file = out / "fonts.css"
    # Keep rules from earlier runs so fonts can be added one family at a time.
    css_rules = {}
    if css_file.exists():
        for rule in css_file.read_text(encoding="utf-8").splitlines():
            m = re.search(r"src: url\('([^']+)'\)", rule)
            if m:
                css_rules[m.group(1)] = rule

    for spec in a.families:
        name, _, weights = spec.partition(":")
        weights = [w.strip() for w in (weights or "400").split(",") if w.strip()]
        query = urllib.parse.quote(name) + ":wght@" + ";".join(sorted(weights, key=int))
        try:
            css = get(f"https://fonts.googleapis.com/css2?family={query}&display=swap").decode()
        except Exception as e:  # unknown family or weight
            sys.exit(f"{name}: {e} (check the exact name and weights on fonts.google.com)")
        for block in re.findall(r"@font-face\s*{[^}]+}", css):
            weight = re.search(r"font-weight:\s*(\d+)", block).group(1)
            style = re.search(r"font-style:\s*(\w+)", block).group(1)
            url = re.search(r"url\((https://[^)]+)\)", block).group(1)
            fname = f"{name.replace(' ', '')}-{weight}{'' if style == 'normal' else style}.ttf"
            (out / fname).write_bytes(get(url))
            css_rules[fname] = (
                f"@font-face {{ font-family: '{name}'; font-weight: {weight}; font-style: {style}; "
                f"src: url('{fname}') format('truetype'); }}"
            )
            print(f"{out / fname}")

    css_file.write_text("\n".join(css_rules[k] for k in sorted(css_rules)) + "\n", encoding="utf-8")
    print(f"{css_file}  (подключай: <link rel=stylesheet href=\"{out.name}/fonts.css\">)")


if __name__ == "__main__":
    main()
