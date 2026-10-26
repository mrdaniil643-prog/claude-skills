#!/usr/bin/env python3
"""Search the Opus video prompt library (references/videos.json).

  find_prompts.py                         stats: categories and tech tags
  find_prompts.py coffee recipe           entries matching all words
  find_prompts.py -c 3d -t threejs        filter by category / tech tag
  find_prompts.py --full                  only entries with a complete prompt
  find_prompts.py --show ror-fly-880547   print one prompt in full
"""
import argparse
import collections
import json
import pathlib
import sys

DATA = pathlib.Path(__file__).resolve().parent.parent / "references" / "videos.json"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("words", nargs="*", help="words that must all appear in title or prompt")
    ap.add_argument("-c", "--category", help="motion | explainer | 3d | interactive")
    ap.add_argument("-t", "--tag", action="append", default=[], help="tech tag, repeatable (canvas, svg, threejs, gsap...)")
    ap.add_argument("--full", action="store_true", help="skip entries whose prompt is partial")
    ap.add_argument("-n", "--limit", type=int, default=15)
    ap.add_argument("--show", metavar="SLUG", help="print the full prompt of one entry")
    a = ap.parse_args()

    items = json.loads(DATA.read_text(encoding="utf-8"))
    for x in items:
        # About half the entries carry no title upstream; use the prompt opening.
        x["title"] = x["title"] or " ".join(x["prompt"].split())[:80]

    if a.show:
        for x in items:
            if x["slug"] == a.show:
                print(f"# {x['title']}\n")
                print(f"author: @{x['author']}  post: {x['post_url']}")
                print(f"category: {x['category']}  tech: {', '.join(x['tech_tags'])}")
                if x["prompt_partial"]:
                    print("NOTE: the creator shared only part of the prompt or just described the result")
                print("\n" + x["prompt"])
                return
        sys.exit(f"no entry with slug {a.show}")

    if not (a.words or a.category or a.tag or a.full):
        print(f"{len(items)} entries")
        print("categories:", dict(collections.Counter(x["category"] for x in items)))
        print("tech tags:", dict(collections.Counter(t for x in items for t in x["tech_tags"]).most_common()))
        return

    words = [w.lower() for w in a.words]
    hits = []
    for x in items:
        if a.category and x["category"] != a.category:
            continue
        if any(t not in x["tech_tags"] for t in a.tag):
            continue
        if a.full and x["prompt_partial"]:
            continue
        text = (x["title"] + " " + x["prompt"]).lower()
        if all(w in text for w in words):
            hits.append(x)

    print(f"{len(hits)} match(es)")
    for x in hits[: a.limit]:
        flag = " [partial]" if x["prompt_partial"] else ""
        snippet = " ".join(x["prompt"].split())[:140]
        print(f"\n{x['slug']}  ({x['category']}; {', '.join(x['tech_tags'])}){flag}\n  {x['title']}\n  {snippet}...")


if __name__ == "__main__":
    main()
