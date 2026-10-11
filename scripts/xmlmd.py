"""Convert eISB / LRC legislation XML (legislation.dtd, typesetting-oriented) to Markdown.

The same converter handles as-enacted XML (www.irishstatutebook.ie) and Revised Acts XML
(revisedacts.lawreform.ie). Revised Acts carry amendment markers as processing instructions
(<?change id=.. type=subs|addition|repeal mark=start|end?>) and annotation blocks
(<div class="annotations">); markers are rendered the way the LRC renders them, e.g. ``F1[...]``.
"""
import re
from collections import Counter

from lxml import etree

CHARS = {
    "emdash": "—", "endash": "–", "odq": "“", "cdq": "”", "osq": "‘", "csq": "’",
    "bull": "•", "nbsp": " ", "euro": "€", "pound": "£", "degree": "°",
    "ddagger": "‡", "dagger": "†", "afada": "á", "efada": "é", "ifada": "í",
    "ofada": "ó", "ufada": "ú", "Afada": "Á", "Efada": "É", "Ifada": "Í",
    "Ofada": "Ó", "Ufada": "Ú", "eolhyphen": "", "ill": "", "page": "", "graphic": "",
    "hr1": "", "hr": "", "br": " ", "sect-symbol": "§", "para": "¶", "times": "×",
    "mdash": "—", "ndash": "–", "copy": "©", "half": "½", "quarter": "¼",
}
INLINE_WRAP = {"i": ("*", "*"), "b": ("**", "**"), "u": ("<u>", "</u>"), "su": ("<sup>", "</sup>"),
               "sb": ("<sub>", "</sub>"), "sup": ("<sup>", "</sup>"), "sub": ("<sub>", "</sub>")}
TRANSPARENT = {"font", "span", "xref", "dfn", "smallcaps", "pc", "a", "q", "cite"}
STRUCT = {"sh2", "sh3", "preamble", "part", "chapter", "sect", "schedule", "l1", "l2", "l3", "l4", "division", "subpart", "group"}
SKIP_FRONT = {"acttoc", "actsreferredto", "coverpage", "actnumber", "metadata", "sectionreference"}

unknown_tags = Counter()


def lname(el):
    t = el.tag
    if not isinstance(t, str):
        return None
    return t.rsplit("}", 1)[-1]


def pi_attrs(pi):
    return dict(re.findall(r'(\w+)="([^"]*)"', pi.text or ""))


def norm_space(s):
    s = s.replace("­", "")
    s = re.sub(r"[ \t\r\n ]+", " ", s)
    return s.strip()


def md_escape_start(s):
    """Prevent paragraph text from being parsed as a list, heading, quote or rule."""
    if re.match(r"^(\d+)([.)])(\s|$)", s):
        s = re.sub(r"^(\d+)([.)])", r"\1\\\2", s, count=1)
    elif re.match(r"^([-+*](\s|$)|>|#|```|~~~)", s):
        s = "\\" + s
    return s


class Ctx:
    def __init__(self):
        self.change_no = {}   # change id -> F number
        self.notes = Counter()
        self.footnotes = []   # (label, text)
        self.fn_counter = 0

    def fnum(self, cid):
        if cid not in self.change_no:
            self.change_no[cid] = len(self.change_no) + 1
        return self.change_no[cid]


def change_marker(pi, ctx):
    a = pi_attrs(pi)
    if pi.target not in ("change", "prosp"):
        return ""
    cid = a.get("id")
    if not cid:
        return ""
    prefix = "F" if pi.target == "change" else "P"
    if a.get("type") == "repeal":
        if a.get("mark", "start") == "start" or "mark" not in a:
            return f"{prefix}{ctx.fnum(cid)}[...]"
        return ""
    if a.get("type") not in ("subs", "addition"):
        return ""
    if a.get("mark") == "start":
        return f"{prefix}{ctx.fnum(cid)}["
    if a.get("mark") == "end":
        return "]"
    return ""


def wrap(s, l, r):
    m = re.match(r"^(\s*)(.*?)(\s*)$", s, re.S)
    lead, core, trail = m.groups()
    if not core:
        return s
    return f"{lead}{l}{core}{r}{trail}"


def inline(el, ctx, skip_fn=False):
    """Render the content (children + text, not tail) of el as inline Markdown."""
    out = [el.text or ""]
    for ch in el:
        out.append(node_inline(ch, ctx))
        out.append(ch.tail or "")
    return "".join(out)


def node_inline(ch, ctx):
    if ch.tag is etree.PI:
        return change_marker(ch, ctx)
    if not isinstance(ch.tag, str):
        return ""
    n = lname(ch)
    if n in CHARS:
        return CHARS[n]
    if n == "unicode":
        c = ch.get("ch", "")
        try:
            v = chr(int(c, 16))
        except ValueError:
            return ""
        return "" if v == "­" else v
    if n in INLINE_WRAP:
        inner = inline(ch, ctx)
        if n in ("i", "b"):
            # avoid nesting the same marker
            if not inner.strip():
                return inner
            return wrap(inner, *INLINE_WRAP[n])
        return wrap(inner, *INLINE_WRAP[n])
    if n == "fn":
        ctx.fn_counter += 1
        label = ctx.fn_counter
        body = []
        for c in ch:
            if lname(c) == "marker":
                continue
            if lname(c) == "p":
                t = norm_space(inline(c, ctx))
                t = re.sub(r"^<sup>\s*\w+\s*</sup>\s*", "", t)
                body.append(t)
        ctx.footnotes.append((label, " ".join(b for b in body if b)))
        return f"[^{label}]"
    if n == "marker":
        return ""
    if n == "table":
        return " " + table_html(ch, ctx) + " "
    if n in ("div", "title", "number"):
        return " " + inline(ch, ctx) + " "
    if n in TRANSPARENT:
        return inline(ch, ctx)
    if n == "p":
        return " " + inline(ch, ctx) + " "
    unknown_tags[n] += 1
    return inline(ch, ctx)


def para_text(p, ctx):
    return norm_space(inline(p, ctx))


# ---------------------------------------------------------------- tables

def cell_blocks(td, ctx):
    parts = []
    for c in td:
        if c.tag is etree.PI:
            m = change_marker(c, ctx)
            if m:
                parts.append(m)
            continue
        n = lname(c)
        if n == "p" or n == "pc":
            parts.append(para_text(c, ctx))
        elif n == "table":
            parts.append(table_html(c, ctx))
        elif n is not None:
            parts.append(norm_space(inline(c, ctx)))
    txt = (td.text or "").strip()
    if txt:
        parts.insert(0, norm_space(txt))
    return [p for p in parts if p]


def rows_of(table):
    rows = []
    for el in table.iter():
        if lname(el) == "tr":
            rows.append([c for c in el if lname(c) in ("td", "th")])
    return rows


def table_html(table, ctx):
    rows = rows_of(table)
    out = ["<table>"]
    for r in rows:
        out.append("<tr>")
        for td in r:
            attrs = ""
            for a in ("colspan", "rowspan"):
                v = td.get(a)
                if v and v != "1":
                    attrs += f' {a}="{v}"'
            content = "<br>".join(md_inline_to_html(b) for b in cell_blocks(td, ctx))
            out.append(f"<td{attrs}>{content}</td>")
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


def md_inline_to_html(s):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # restore the few inline HTML tags we generate
    s = re.sub(r"&lt;(/?)(sup|sub|u|br)&gt;", r"<\1\2>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
    return s


def table_md(table, ctx):
    rows = rows_of(table)
    if not rows:
        return ""
    simple = True
    grid = []
    for r in rows:
        line = []
        for td in r:
            if (td.get("colspan") or "1") != "1" or (td.get("rowspan") or "1") != "1":
                simple = False
            bl = cell_blocks(td, ctx)
            if any(b.startswith("<table") for b in bl):
                simple = False
            line.append(" ".join(bl))
        grid.append(line)
    ncol = max(len(r) for r in grid)
    if not simple or ncol < 2 or any(len(r) != ncol for r in grid):
        return table_html(table, ctx)
    esc = [[c.replace("|", "\\|") for c in r] for r in grid]
    out = ["| " + " | ".join(esc[0]) + " |", "|" + "---|" * ncol]
    for r in esc[1:]:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


# ---------------------------------------------------------------- blocks

class Out:
    def __init__(self):
        self.blocks = []        # list of [kind, text]
        self.pending = ""       # block-level start markers waiting for the next block

    def add(self, kind, text):
        if not text and not self.pending:
            return
        if self.pending:
            if kind == "h":
                m = re.match(r"^(#+ )(.*)$", text)
                text = m.group(1) + self.pending + m.group(2)
            elif kind == "table":
                self.blocks.append(["p", self.pending.strip()])
            else:
                text = self.pending + text
            self.pending = ""
        self.blocks.append([kind, text])

    def close_marker(self, m):
        for b in reversed(self.blocks):
            if b[0] in ("p", "h"):
                b[1] = b[1] + m
                return
        self.pending += m

    def marker(self, m):
        if not m:
            return
        if m == "]":
            if self.pending:
                self.pending += m
            else:
                self.close_marker(m)
        elif m.endswith("[...]"):
            self.pending += m + " "
        else:
            self.pending += m


def title_text(el, ctx):
    """Join the paragraphs of a <title> element with an em dash."""
    parts = []
    if el is None:
        return ""
    if (el.text or "").strip():
        parts.append(norm_space(el.text))
    for c in el:
        if c.tag is etree.PI:
            m = change_marker(c, ctx)
            if m:
                parts.append(m)
            continue
        t = norm_space(inline(c, ctx)) if lname(c) in ("p", "pc") else norm_space(node_inline(c, ctx))
        if t:
            parts.append(t)
        if (c.tail or "").strip():
            parts.append(norm_space(c.tail))
    s = ""
    for p in parts:
        if not s:
            s = p
        elif s.endswith("[") or p == "]":
            s += p
        else:
            s += " — " + p
    return s.replace("*", "").strip()


def heading(level, text):
    level = max(2, min(level, 6))
    text = text.strip() or "\u2014"
    if level == 6 and False:
        return text
    return "#" * level + " " + text


def render_children(el, ctx, out, depth, in_annot=False):
    if (el.text or "").strip():
        out.add("p", md_escape_start(norm_space(el.text)))
    for c in el:
        render_node(c, ctx, out, depth, in_annot)
        if (c.tail or "").strip() and isinstance(c.tag, str):
            out.add("p", md_escape_start(norm_space(c.tail)))


def render_node(c, ctx, out, depth, in_annot=False):
    if c.tag is etree.PI:
        out.marker(change_marker(c, ctx))
        return
    n = lname(c)
    if n is None:
        return
    if n in ("p", "pc"):
        t = para_text(c, ctx)
        if t:
            out.add("p", md_escape_start(t))
        return
    if n == "table":
        out.add("table", table_md(c, ctx))
        return
    if n in ("title", "shtitle"):
        return  # handled by parent
    if n == "number":
        return
    if n == "div":
        cls = (c.get("class") or "").split()
        if "annotations" in cls:
            render_annotations(c, ctx, out)
            return
        render_children(c, ctx, out, depth, in_annot)
        return
    if n in STRUCT:
        render_struct(c, ctx, out, depth)
        return
    if n in ("sh", "narrative", "body", "backmatter", "frontmatter", "act", "commentaries", "group"):
        render_children(c, ctx, out, depth, in_annot)
        return
    if n == "commentary":
        typ = c.findtext("type") or "F"
        body = c.find("commentarycontent")
        txt = norm_space(inline(body, ctx)) if body is not None else ""
        out.add("p", f"> {typ}: {txt}")
        return
    if n in SKIP_FRONT:
        return
    if n in CHARS or n == "unicode":
        t = node_inline(c, ctx)
        if t.strip():
            out.add("p", t)
        return
    unknown_tags["block:" + n] += 1
    t = norm_space(inline(c, ctx))
    if t:
        out.add("p", md_escape_start(t))


def render_struct(el, ctx, out, depth):
    n = lname(el)
    t = el.find("title")
    if t is None:
        t = el.find("shtitle")
    ttl = title_text(t, ctx)
    level = 2 + depth
    if n == "sect":
        num = norm_space(el.findtext("number") or "").rstrip(".")
        label = f"{num}. {ttl}" if num and ttl else (num or ttl or "Section")
        out.add("h", heading(level, label))
    elif n in ("l1", "l2", "l3", "l4"):
        if ttl:
            out.add("p", "**" + ttl + "**" if "**" not in ttl else ttl)
        render_children(el, ctx, out, depth)
        return
    elif n in ("sh2", "sh3"):
        num = ""
        fp = el.find("p")
        if fp is not None and fp.find("b") is not None:
            num = norm_space("".join(fp.find("b").itertext())).rstrip(".")
        label = f"{num}. {ttl}" if num and ttl else (ttl or num or "Section")
        out.add("h", heading(level, label))
    else:
        if not ttl:
            ttl = {"schedule": "SCHEDULE", "part": "PART", "chapter": "CHAPTER"}.get(n, n.upper())
        out.add("h", heading(level, ttl))
    render_children(el, ctx, out, depth + 1)


ANNOT_LABEL = {"f-note": "F", "c-note": "C", "e-note": "E", "i-note": "I", "m-note": "M", "p-note": "P"}


def render_annotations(div, ctx, out):
    lines = []

    def walk(el, prefix_ref):
        for c in el:
            if c.tag is etree.PI or not isinstance(c.tag, str):
                continue
            n = lname(c)
            if n == "div":
                cls = (c.get("class") or "").split()
                label = None
                if cls and cls[0] in ANNOT_LABEL:
                    letter = ANNOT_LABEL[cls[0]]
                    ids = [x for x in cls[1:] if x.isdigit()]
                    if letter == "F" and ids:
                        label = ", ".join(f"F{ctx.fnum(i)}" for i in ids)
                    else:
                        ctx.notes[letter] += 1
                        label = f"{letter}{ctx.notes[letter]}"
                    first = [True]
                    walk_note(c, label, first)
                else:
                    walk(c, prefix_ref)
            elif n in ("p", "pc"):
                t = para_text(c, ctx)
                if t:
                    lines.append(t)
            elif n == "table":
                lines.append(table_html(c, ctx))

    def walk_note(el, label, first):
        for c in el:
            if not isinstance(c.tag, str):
                continue
            n = lname(c)
            if n in ("p", "pc"):
                t = para_text(c, ctx)
                if not t:
                    continue
                if first[0]:
                    t = f"{label}: {t}"
                    first[0] = False
                lines.append(t)
            elif n == "table":
                lines.append(table_html(c, ctx))
            elif n == "div":
                walk_note(c, label, first)

    walk(div, None)
    if lines:
        out.add("annot", "\n>\n".join("> " + (ln if ln.startswith("<table") else md_escape_start(ln)) for ln in lines))


def render_front(fm, ctx, out, title_upper):
    """Front matter: long title, enacting formula, Act-level annotations."""
    def walk(el):
        for c in el:
            if c.tag is etree.PI:
                out.marker(change_marker(c, ctx))
                continue
            n = lname(c)
            if n is None or n in SKIP_FRONT:
                continue
            if n in ("narrative", "acttitle"):
                continue  # cover page / LRC editorial boilerplate
            if n == "div" and "annotations" in (c.get("class") or ""):
                render_annotations(c, ctx, out)
                continue
            if n in ("p", "pc"):
                t = para_text(c, ctx)
                plain = re.sub(r"[*\s.,]", "", t).upper()
                if not t or plain == title_upper or re.match(r"^\*?(Number|Uimhir)\*?\s+\d+\s*(\*?(of|de)\*?\s+\d{4})?\.?$", t):
                    continue
                if plain in ("REVISED", "ACHTANNAATHBHREITHNITHE", "ARRANGEMENTOFSECTIONS", "CONTENTS", "ACHOIMRE", "CLÁR") or t.replace("*", "").startswith("Updated to"):
                    continue
                out.add("p", md_escape_start(t))
            elif n == "table":
                out.add("table", table_md(c, ctx))
            else:
                render_node(c, ctx, out, 0)
    walk(fm)


def parse(raw):
    parser = etree.XMLParser(resolve_entities=True, load_dtd=False, recover=True, huge_tree=True, no_network=True)
    return etree.fromstring(raw, parser)


def entity_values(raw):
    head = raw[:4000].decode("utf-8", "replace")
    return dict(re.findall(r'<!ENTITY\s+(\w+)\s+"([^"]*)"', head))


def convert(raw):
    """Return (meta, markdown_body) for an XML Act."""
    root = parse(raw)
    ctx = Ctx()
    meta = {}
    md = root.find("metadata")
    if md is not None:
        meta["title"] = norm_space(md.findtext("title") or "")
        meta["number"] = norm_space(md.findtext("number") or "")
        meta["year"] = norm_space(md.findtext("year") or "")
        meta["date"] = norm_space(md.findtext("dateofenactment") or "")
    ents = entity_values(raw)
    meta["updated_to"] = ents.get("updatedtodate")
    cp = root.find("frontmatter/coverpage")
    if cp is not None:
        cptext = norm_space(" ".join(cp.itertext()))
        if not meta["updated_to"]:
            m = re.search(r"Updated to (\d{1,2} [A-Z][a-z]+ \d{4})", cptext)
            if m:
                meta["updated_to"] = m.group(1)
        if re.search(r"\((Repealed|Spent|Revoked)\)", cptext[:400]):
            meta["repealed"] = True
    title_upper = re.sub(r"[*\s.,]", "", meta.get("title", "")).upper()
    # pre-number all F-notes in document order so markers in text get the LRC numbering
    for div in root.iter("div"):
        cls = (div.get("class") or "").split()
        if cls and cls[0] == "f-note":
            for i in cls[1:]:
                if i.isdigit():
                    ctx.fnum(i)
    ctx.change_no_initial = dict(ctx.change_no)
    out = Out()
    fm = root.find("frontmatter")
    if fm is not None:
        render_front(fm, ctx, out, title_upper)
    for part in ("body", "backmatter"):
        el = root.find(part)
        if el is not None:
            render_children(el, ctx, out, 0)
    # drop stray number/title/contents lines that precede the long title
    for i, (kind, txt) in enumerate(out.blocks):
        if kind == "h":
            break
        if kind == "p" and re.match(r"^\W*(AN ACT|ACHT)\b", txt.replace("*", ""), re.I):
            out.blocks[:i] = [b for b in out.blocks[:i] if b[0] == "annot"]
            break
    if out.pending.strip():
        out.add("p", out.pending.strip())
    text = "\n\n".join(b[1] for b in out.blocks if b[1])
    if ctx.footnotes:
        text += "\n\n" + "\n".join(f"[^{n}]: {t}" for n, t in ctx.footnotes)
    return meta, text
