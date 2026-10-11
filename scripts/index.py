#!/usr/bin/env python3
"""Build RAW/index.json: list of all Acts on the eISB (1922-present and pre-1922) and LRC Revised Acts.

Usage: python index.py [--refresh]
"""
import datetime as dt
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ISB, LRC, RAW, cached  # noqa: E402

ROW = re.compile(r'<a href="(en|ga)/act/(pub|prv|cam)/(\d+)/index\.html">(.*?)</a>', re.S)


def year_acts(year, refresh=False):
    path = f"years/{year}.html"
    if refresh and os.path.exists(os.path.join(RAW, path)):
        os.remove(os.path.join(RAW, path))
    data = cached(f"{ISB}/eli/{year}/act", path)
    if data is None:
        return []
    t = data.decode("utf-8", "replace")
    out, seen = [], set()
    for lang, kind, num, title in ROW.findall(t):
        key = (kind, int(num), lang)
        if key in seen:
            continue
        seen.add(key)
        title = html.unescape(re.sub(r"<[^>]+>", "", title)).strip()
        title = re.sub(r"\s+", " ", title)
        title = re.sub(r"^No\. \d+/\d+ [—-] ", "", title)
        out.append({"year": year, "kind": kind, "number": int(num), "lang": lang, "title": title})
    return out


def main():
    refresh = "--refresh" in sys.argv
    this_year = dt.date.today().year
    pre = cached(f"{ISB}/eli/pre-acts.html", "pre-acts.html").decode("utf-8", "replace")
    pre_years = sorted({int(y) for y in re.findall(r'<option value="(\d{4})"', pre)})
    acts = []
    for y in sorted(set(pre_years) | set(range(1922, this_year + 1))):
        got = year_acts(y, refresh=refresh or y >= this_year - 1)
        print(y, len(got), file=sys.stderr)
        acts.extend(got)
    # LRC revised acts (chronological list)
    p = os.path.join(RAW, "lrc-chron.html")
    if refresh and os.path.exists(p):
        os.remove(p)
    chron = cached(f"{LRC}/revacts/chron", "lrc-chron.html").decode("utf-8", "replace")
    revised = sorted({m for m in re.findall(r'href="/eli/(\d{4}/(?:act|bps|prv|si)/\d+)/front/revised/en/html"', chron)})
    with open(os.path.join(RAW, "index.json"), "w") as f:
        json.dump({"pre_years": pre_years, "acts": acts, "revised": revised}, f, indent=0)
    print(f"{len(acts)} acts, {len(revised)} revised", file=sys.stderr)


if __name__ == "__main__":
    main()
