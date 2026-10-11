"""HTML -> Markdown for the eISB pages that have no XML: pre-1922 Acts (print view) and the Constitution."""
import re

import lxml.html
from lxml import etree

from xmlmd import md_escape_start, norm_space

WRAP = {"i": ("*", "*"), "em": ("*", "*"), "b": ("**", "**"), "strong": ("**", "**"),
        "sup": ("<sup>", "</sup>"), "sub": ("<sub>", "</sub>"), "u": ("<u>", "</u>")}


def wrap(s, l, r):
    m = re.match(r"^(\s*)(.*?)(\s*)$", s, re.S)
    lead, core, trail = m.groups()
    if not core:
        return s
    return f"{lead}{l}{core}{r}{trail}"


def inline(el):
    out = [el.text or ""]
    for c in el:
        if isinstance(c.tag, str):
            t = c.tag.lower()
            if t in ("script", "style"):
                pass
            elif t == "br":
                out.append(" ")
            elif t in WRAP:
                out.append(wrap(inline(c), *WRAP[t]))
            elif t == "table":
                out.append(" " + table_html(c) + " ")
            else:
                out.append(inline(c))
        out.append(c.tail or "")
    return "".join(out)


def text(el):
    return norm_space(inline(el))


def table_html(tbl):
    rows = []
    for tr in tbl.iter("tr"):
        cells = []
        for td in tr:
            if not isinstance(td.tag, str) or td.tag not in ("td", "th"):
                continue
            attrs = ""
            for a in ("colspan", "rowspan"):
                v = td.get(a)
                if v and v != "1":
                    attrs += f' {a}="{v}"'
            ps = [text(p) for p in td.iter("p")] or [text(td)]
            content = "<br>".join(p for p in ps if p)
            content = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", content)
            content = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", content)
            cells.append(f"<td{attrs}>{content}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return "<table>" + "".join(rows) + "</table>"


def is_centered(p):
    return "text-align:center" in (p.get("style") or "").replace(" ", "")


# ---------------------------------------------------------------- pre-1922

def pre1922(raw):
    """Return (meta, markdown) for an eISB pre-1922 Act print page."""
    s = raw.decode("utf-8", "replace")
    i = s.find('<div class="act-content"')
    j = s.find("<!--End Content-->", i)
    if i < 0:
        return {}, ""
    frag = s[i:j if j > 0 else None]
    root = lxml.html.fromstring(frag)
    tbl = root.find(".//table")
    blocks = []
    meta = {}
    first_center = True
    rows = [tr for tr in tbl.iter("tr") if tr.getparent() is tbl or tr.getparent().getparent() is tbl] if tbl is not None else []
    for tr in rows:
        tds = [c for c in tr if isinstance(c.tag, str) and c.tag == "td"]
        if not tds:
            continue
        margin = None
        content = tds[-1]
        if len(tds) >= 3 and tds[1].find(".//a[@name]") is not None and any(
                (a.get("name") or "").startswith("sec") for a in tds[1].iter("a")):
            margin = text(tds[1])
        if margin is not None:
            num = ""
            for b in content.iter("b"):
                bt = re.sub(r"[.\s\u2014\u2013-]+$", "", norm_space(b.text_content()))
                if re.fullmatch(r"\d+[A-Z]{0,3}", bt):
                    num = bt
                    break
            label = f"{num}. {margin}" if num else margin
            label = label.replace("*", "").strip()
            if label:
                blocks.append("### " + label)
        for el in content:
            if not isinstance(el.tag, str):
                continue
            if el.tag == "p":
                t = text(el)
                if not t:
                    continue
                if is_centered(el):
                    if meta.get("heading") and t == meta["heading"]:
                        blocks = []  # title repeated after a table of contents: restart
                        continue
                    was_first, first_center = first_center, False
                    if was_first and not re.match(r"^CHAPTER\b", t) and (t.startswith("**") or not re.search(r"[a-z]", t.replace("*", ""))):
                        meta["heading"] = t
                        continue
                    if margin is None and not t.startswith("[") and len(t) < 160 and not re.match(r"^CHAPTER\b", t):
                        h = t.replace("*", "").strip()
                        if h:
                            blocks.append("## " + h)
                        continue
                blocks.append(md_escape_start(t))
            elif el.tag == "table":
                blocks.append(table_html(el))
            elif el.tag in ("div", "span", "blockquote", "ul", "ol"):
                t = text(el)
                if t:
                    blocks.append(md_escape_start(t))
    body = "\n\n".join(blocks)
    m = re.search(r"\[(\d{1,2})(?:st|nd|rd|th|d)?\.? ([A-Z][a-z]+),? (\d{4})\.?\]", body)
    if m:
        meta["date_text"] = m.group(0)
    return meta, body


# ---------------------------------------------------------------- constitution

ARTICLE = re.compile(r"^(ARTICLE|AIRTEAGAL)\s+(\d+[A-Z]?)\.?$")


def constitution(raw, lang):
    s = raw.decode("utf-8", "replace")
    s = re.sub(r"</\s*(?=<)", "", s)
    s = re.sub(r"</?h[1-6][^>]*>", "", s)
    start_pat = "Most Holy Trinity" if lang == "en" else "In Ainm na Tríonóide"
    art1 = s.find("<p>ARTICLE 1</p>" if lang == "en" else "<p>AIRTEAGAL 1</p>")
    i = s.rfind(start_pat, 0, art1)
    i = s.rfind("<p", 0, i)
    end_pat = 'name="index"' if lang == "en" else 'name="treoir"'
    j = s.find(end_pat, i)
    j = s.rfind("<", 0, j)
    frag = "<div>" + s[i:j] + "</div>"
    root = lxml.html.fromstring(frag)
    blocks = []
    for p in root.iter("p"):
        anc = p.getparent()
        # skip nested <p> (malformed HTML) whose parent is another p
        if anc is not None and anc.tag == "p":
            continue
        t = text(p)
        if not t:
            continue
        plain = t.replace("*", "").strip()
        m = ARTICLE.match(plain)
        if m:
            blocks.append(f"### {plain}")
            continue
        if is_centered(p) and "**" in t and plain.upper() == plain and len(plain) < 120:
            blocks.append("## " + plain)
            continue
        blocks.append(md_escape_start(t))
    return "\n\n".join(blocks)
