#!/usr/bin/env python3
"""Download sources listed in RAW/index.json into the RAW cache (re-runs skip cached files).

- 1922+ Acts: eISB as-enacted XML  /eli/<y>/act|prv/<n>/enacted/<lang>/xml
- pre-1922 Acts: eISB print HTML   /eli/<y>/act/<n>/enacted/en/print  (no XML is published)
- LRC Revised Acts: revised XML    /eli/<y>/act|bps/<n>/revised/en/xml
- Constitution: eISB HTML          /eli/cons/<lang>/html
"""
import concurrent.futures as cf
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ISB, LRC, RAW, cached  # noqa: E402


def jobs():
    idx = json.load(open(os.path.join(RAW, "index.json")))
    for lang in ("en", "ga"):
        yield f"{ISB}/eli/cons/{lang}/html", f"cons/{lang}.html"
    for r in idx["revised"]:
        y, kind, n = r.split("/")
        if kind in ("act", "bps"):
            yield f"{LRC}/eli/{y}/{kind}/{n}/revised/en/xml", f"revised/{y}/{kind}-{n}.xml"
    for a in idx["acts"]:
        y, n, lang = a["year"], a["number"], a["lang"]
        seg = {"pub": "act", "prv": "prv", "cam": "ca"}[a["kind"]]
        if y < 1922:
            yield f"{ISB}/eli/{y}/act/{n}/enacted/en/print", f"enacted/{y}/pre-{n}.html"
        elif seg == "ca" and lang == "ga":
            # the XML endpoint returns the English text for /ga/xml of constitutional amendment Acts
            yield f"{ISB}/eli/{y}/{seg}/{n}/enacted/ga/print", f"enacted/{y}/print-{seg}-{n}-ga.html"
        else:
            yield f"{ISB}/eli/{y}/{seg}/{n}/enacted/{lang}/xml", f"enacted/{y}/{seg}-{n}-{lang}.xml"


def fallback_jobs():
    """Acts listed on 1922+ year pages without XML (e.g. the UK Finance Act 1922): use the print HTML."""
    idx = json.load(open(os.path.join(RAW, "index.json")))
    for a in idx["acts"]:
        y, n, lang = a["year"], a["number"], a["lang"]
        seg = {"pub": "act", "prv": "prv", "cam": "ca"}[a["kind"]]
        if y >= 1922 and os.path.exists(os.path.join(RAW, f"enacted/{y}/{seg}-{n}-{lang}.xml.404")):
            yield f"{ISB}/eli/{y}/{seg}/{n}/enacted/{lang}/print", f"enacted/{y}/print-{seg}-{n}-{lang}.html"


def main():
    todo = list(jobs())
    todo += [j for j in fallback_jobs() if j not in todo]
    missing = []
    done = 0
    with cf.ThreadPoolExecutor(4) as ex:
        futs = {ex.submit(cached, url, path): (url, path) for url, path in todo}
        for f in cf.as_completed(futs):
            url, path = futs[f]
            try:
                if f.result() is None:
                    missing.append(url)
            except Exception as e:  # noqa: BLE001
                missing.append(f"{url} ERROR {e}")
            done += 1
            if done % 200 == 0:
                print(f"{done}/{len(todo)}", file=sys.stderr, flush=True)
    with open(os.path.join(RAW, "missing.txt"), "w") as f:
        f.write("\n".join(sorted(missing)) + "\n")
    print(f"{len(todo)} jobs, {len(missing)} missing", file=sys.stderr)


if __name__ == "__main__":
    main()
