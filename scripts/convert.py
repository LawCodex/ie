#!/usr/bin/env python3
"""Generate the Markdown corpus from the RAW cache (run index.py and fetch.py first).

Usage: python convert.py [--only constitution,acts,pre-1922]
Writes ROOT/constitution, ROOT/acts, ROOT/pre-1922 and RAW/manifest.json (used by readme.py).
"""
import argparse
import datetime as dt
import json
import os
import re
import shutil
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import htmlmd  # noqa: E402
import xmlmd  # noqa: E402
from common import ISB, LRC, RAW, ROOT  # noqa: E402

TODAY = dt.date.today().isoformat()
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                      "september", "october", "november", "december"], 1)}


def slugify(s, maxlen=80):
    s = s.replace("’", "").replace("'", "")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > maxlen:
        s = s[:maxlen].rsplit("-", 1)[0]
    return s or "act"


def title_slug(title, year):
    t = re.sub(r"[,\s]*\(?(?:No\.\s*\d+\)?\s*)?" + str(year) + r"\.?\s*$", "", title.strip())
    t = re.sub(r"[,.\s]+$", "", t)
    return slugify(t or title)


def clean_title(t):
    t = re.sub(r"\s+", " ", t).strip()
    return re.sub(r"\.$", "", t) if not t.endswith("etc.") else t


def iso_date(s):
    if not s:
        return None
    s = s.strip()
    if re.fullmatch(r"\d{8}", s):
        try:
            return dt.date(int(s[:4]), int(s[4:6]), int(s[6:])).isoformat()
        except ValueError:
            return None
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th|d)? ([A-Za-z]+),? (\d{4})", s)
    if m and m.group(2).lower() in MONTHS:
        try:
            return dt.date(int(m.group(3)), MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
        except ValueError:
            return None
    return None


def yq(v):
    if v is None:
        return None
    if isinstance(v, int):
        return str(v)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}|[a-z_]+", v):
        return v
    return json.dumps(v, ensure_ascii=False)


def write(path, fm, h1, body):
    lines = ["---"]
    for k, v in fm.items():
        if v is None or v == "":
            continue
        lines.append(f"{k}: {yq(v)}")
    lines.append("---")
    text = "\n".join(lines) + f"\n\n# {h1}\n\n" + body.strip() + "\n"
    text = re.sub(r"\n{3,}", "\n\n", text)
    full = os.path.join(ROOT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return len(text.encode())


def read(path):
    full = os.path.join(RAW, path)
    if not os.path.exists(full):
        return None
    with open(full, "rb") as f:
        return f.read()


# ---------------------------------------------------------------- constitution

def do_constitution(idx, manifest):
    for lang, title, fname in (("en", "Constitution of Ireland", "constitution-of-ireland.md"),
                               ("ga", "Bunreacht na hÉireann", "bunreacht-na-heireann.md")):
        raw = read(f"cons/{lang}.html")
        if raw is None:
            print("missing constitution", lang, file=sys.stderr)
            continue
        body = htmlmd.constitution(raw, lang)
        s = raw.decode("utf-8", "replace")
        dates = re.findall(r"text-align: right[^>]*>\s*(\d{1,2} [A-Za-z]+,? \d{4})\s*<", s)
        last = iso_date(dates[-1].replace(",", "")) if dates else None
        fm = {
            "title": title, "identifier": f"eli/cons/{lang}", "type": "constitution", "jurisdiction": "ie",
            "language": lang, "date": "1937-07-01", "last_amended": last, "status": "in_force",
            "version": "consolidated", "source": f"{ISB}/eli/cons/{lang}/html", "retrieved": TODAY,
        }
        write(f"constitution/{fname}", fm, title, body)
        manifest.append({"cat": "constitution", "lang": lang, "path": f"constitution/{fname}", "version": "consolidated"})


# ---------------------------------------------------------------- acts

def xml_act(a, raw, version, path, kind_type, source, identifier, extra=None):
    meta, body = xmlmd.convert(raw)
    title = clean_title(a["title"]) or clean_title(meta.get("title", ""))
    fm = {
        "title": title, "identifier": identifier, "type": kind_type, "jurisdiction": "ie",
        "language": a["lang"], "number": a["number"], "year": a["year"],
        "date": iso_date(meta.get("date")),
        "last_amended": iso_date((meta.get("updated_to") or "").replace(",", "")) if version == "revised" else None,
        "status": ("repealed" if meta.get("repealed") else "in_force") if version == "revised" else "unknown",
        "version": version,
    }
    if extra:
        fm.update(extra)
    fm["source"] = source
    fm["retrieved"] = TODAY
    size = write(path, fm, title, body)
    return size


def do_acts(idx, manifest, cats):
    revised = set(idx["revised"])
    for a in idx["acts"]:
        y, n, lang, kind = a["year"], a["number"], a["lang"], a["kind"]
        slug = title_slug(a["title"], y)
        if y < 1922:
            if "pre-1922" not in cats:
                continue
            do_pre1922(a, slug, revised, manifest)
            continue
        seg = {"pub": "act", "prv": "prv", "cam": "ca"}[kind]
        if kind == "cam":
            if "constitution" not in cats:
                continue
            path = f"constitution/amendments/{y}-ca-{n}-{'ga-' if lang == 'ga' else ''}{slug}.md"
            ktype, cat = "constitutional_amendment_act", "constitution-amendments"
        else:
            if "acts" not in cats:
                continue
            pre = "act" if kind == "pub" else "private-act"
            path = f"acts/{y}/{y}-{pre}-{n}-{'ga-' if lang == 'ga' else ''}{slug}.md"
            ktype = "act" if kind == "pub" else "private_act"
            cat = "acts" if kind == "pub" else "private-acts"
        enacted_url = f"{ISB}/eli/{y}/{seg}/{n}/enacted/{lang}/html"
        rkey = f"{y}/act/{n}"
        raw = None
        if kind == "pub" and lang == "en" and rkey in revised:
            raw = read(f"revised/{y}/act-{n}.xml")
            if raw is not None:
                size = xml_act(a, raw, "revised", path, ktype, f"{LRC}/eli/{y}/act/{n}/revised/en/html",
                               f"eli/{y}/act/{n}", {"revised_by": "Law Reform Commission", "as_enacted": enacted_url})
                manifest.append({"cat": cat, "lang": lang, "path": path, "version": "revised", "year": y, "size": size})
                continue
        raw = None if (seg == "ca" and lang == "ga") else read(f"enacted/{y}/{seg}-{n}-{lang}.xml")
        if raw is None and read(f"enacted/{y}/print-{seg}-{n}-{lang}.html") is not None:
            if y == 1922 and kind == "pub" and n > 5:
                # UK statute of 1922 listed on the 1922 page (e.g. Finance Act 1922, 12 & 13 Geo. 5 c. 17)
                if "pre-1922" in cats:
                    do_pre1922(a, slug, revised, manifest, f"enacted/{y}/print-{seg}-{n}-{lang}.html")
                continue
            do_html_act(a, path, ktype, cat, enacted_url, f"eli/{y}/{seg}/{n}",
                        read(f"enacted/{y}/print-{seg}-{n}-{lang}.html"), manifest)
            continue
        if raw is None:
            manifest.append({"cat": cat, "lang": lang, "path": None, "missing": enacted_url, "year": y})
            continue
        size = xml_act(a, raw, "as_enacted", path, ktype, enacted_url, f"eli/{y}/{seg}/{n}")
        manifest.append({"cat": cat, "lang": lang, "path": path, "version": "as_enacted", "year": y, "size": size})


def do_html_act(a, path, ktype, cat, url, ident, raw, manifest):
    meta, body = htmlmd.pre1922(raw)
    title = clean_title(a["title"])
    fm = {"title": title, "identifier": ident, "type": ktype, "jurisdiction": "ie", "language": a["lang"],
          "number": a["number"], "year": a["year"], "status": "unknown", "version": "as_enacted",
          "source": url, "retrieved": TODAY}
    size = write(path, fm, title, body)
    manifest.append({"cat": cat, "lang": a["lang"], "path": path, "version": "as_enacted", "year": a["year"], "size": size})


def do_pre1922(a, slug, revised, manifest, rawpath=None):
    y, n = a["year"], a["number"]
    path = f"pre-1922/{y}/{y}-ch-{n}-{slug}.md"
    enacted_url = f"{ISB}/eli/{y}/act/{n}/enacted/en/html"
    rkey = f"{y}/bps/{n}"
    if rkey in revised:
        raw = read(f"revised/{y}/bps-{n}.xml")
        if raw is not None:
            size = xml_act(a, raw, "revised", path, "act", f"{LRC}/eli/{y}/bps/{n}/revised/en/html",
                           f"eli/{y}/act/{n}", {"chapter": n, "revised_by": "Law Reform Commission", "as_enacted": enacted_url})
            manifest.append({"cat": "pre-1922", "lang": "en", "path": path, "version": "revised", "year": y, "size": size})
            return
    raw = read(rawpath or f"enacted/{y}/pre-{n}.html")
    if raw is None:
        manifest.append({"cat": "pre-1922", "lang": "en", "path": None, "missing": enacted_url, "year": y})
        return
    meta, body = htmlmd.pre1922(raw)
    title = clean_title(a["title"])
    date = None
    if meta.get("date_text"):
        date = iso_date(re.sub(r"[\[\].,]", "", meta["date_text"]).strip())
    fm = {"title": title, "identifier": f"eli/{y}/act/{n}", "type": "act", "jurisdiction": "ie", "language": "en",
          "number": n, "chapter": n, "year": y, "date": date, "status": "unknown", "version": "as_enacted",
          "source": enacted_url, "retrieved": TODAY}
    size = write(path, fm, title, body)
    manifest.append({"cat": "pre-1922", "lang": "en", "path": path, "version": "as_enacted", "year": y, "size": size})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="constitution,acts,pre-1922")
    args = ap.parse_args()
    cats = set(args.only.split(","))
    idx = json.load(open(os.path.join(RAW, "index.json")))
    for d in cats:
        p = os.path.join(ROOT, d)
        if os.path.isdir(p):
            shutil.rmtree(p)
    manifest = []
    if "constitution" in cats:
        do_constitution(idx, manifest)
    do_acts(idx, manifest, cats)
    mpath = os.path.join(RAW, "manifest.json")
    old = []
    if os.path.exists(mpath) and cats != {"constitution", "acts", "pre-1922"}:
        old = [m for m in json.load(open(mpath)) if not (m["cat"] in cats or
               (m["cat"].startswith("constitution") and "constitution" in cats) or
               (m["cat"] in ("acts", "private-acts") and "acts" in cats))]
    with open(mpath, "w") as f:
        json.dump(old + manifest, f, indent=0)
    if xmlmd.unknown_tags:
        print("unknown tags:", dict(xmlmd.unknown_tags), file=sys.stderr)
    print(f"{sum(1 for m in manifest if m.get('path'))} files written, "
          f"{sum(1 for m in manifest if not m.get('path'))} missing", file=sys.stderr)


if __name__ == "__main__":
    main()
