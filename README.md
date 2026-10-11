# LawCodex — Ireland (`ie`)

The primary legislation of Ireland — **Bunreacht na hÉireann** (the Constitution, in English and Irish)
and the **Acts of the Oireachtas** from 1922 to 2026, plus the **pre-1922 statutes** still published
on the Irish Statute Book — as plain Markdown, one file per text.

Part of [LawCodex](https://github.com/LawCodex) — the laws of every country as Markdown in git.

Retrieved: 2026-10-11. **5,450 files.**

## Contents

| Category | Directory | Files |
|---|---|---:|
| Constitution — English text (*Constitution of Ireland*) | `constitution/` | 1 |
| Constitution — Irish text (*Bunreacht na hÉireann*, the authoritative text) | `constitution/` | 1 |
| Acts amending the Constitution — English | `constitution/amendments/` | 32 |
| Acts amending the Constitution — Irish | `constitution/amendments/` (`*-ga-*`) | 32 |
| Public Acts 1922–2026 — **revised** (consolidated by the Law Reform Commission) | `acts/<year>/` | 577 |
| Public Acts 1922–2026 — **as enacted** (no Revised Act available) | `acts/<year>/` | 3,431 |
| Public Acts enacted in Irish — Irish-language text (English text also present) | `acts/<year>/` (`*-ga-*`) | 24 |
| Private Acts 1922–2026 (as enacted) | `acts/<year>/` (`*-private-act-*`) | 73 |
| Pre-1922 statutes (as enacted text on the eISB; a few revised by the LRC) | `pre-1922/<year>/` | 1,279 (revised: 8) |
| **Total** | | **5,450** |

Public Acts in English: 4,008 files, of which 577 are Revised Acts and 3,431 are as-enacted texts.

### Revised vs. as-enacted

Every file says which text it contains in its front matter (`version:`):

- `revised` — a **Revised Act** of the [Law Reform Commission](https://revisedacts.lawreform.ie/revacts/intro):
  an administrative consolidation incorporating all textual amendments up to the date given in
  `last_amended` ("Updated to ..."). The LRC revises all Acts since 2004 that have been textually amended
  (except Finance Acts) and about 170 frequently-used earlier Acts. Amendments are marked as on the LRC site:
  `F1[`amended text`]`, `F2[...]` for repealed text, `P1[...]` for prospective (not yet commenced)
  amendments; each section is followed by its annotations in a block quote (`F` = textual amendments,
  `C` = modifications not altering text, `E` = editorial notes). Revised Acts may themselves be repealed
  (`status: repealed`). `as_enacted` gives the eISB URL of the original text.
- `as_enacted` — the text **as originally enacted**, from the electronic Irish Statute Book (eISB).
  Later amendments and repeals are **not** applied: check the eISB *Legislation Directory* for the
  current status. Such files have `status: unknown`.
- `consolidated` — the Constitution, as published on the eISB with all amendments in force.

## Structure

```
constitution/
  constitution-of-ireland.md          English text
  bunreacht-na-heireann.md            Irish text
  amendments/<year>-ca-<n>[-ga]-<slug>.md   Acts amending the Constitution (English / Irish)
acts/<year>/
  <year>-act-<n>-<slug>.md            Public Act No. <n> of <year>
  <year>-act-<n>-ga-<slug>.md         Irish-language text of an Act enacted in Irish
  <year>-private-act-<n>-<slug>.md    Private Act No. <n> of <year>
pre-1922/<year>/
  <year>-ch-<n>-<slug>.md             statute of <year>, chapter <n> (eISB numbering)
```

Each file starts with YAML front matter (`title`, `identifier` = ELI path, `type`, `language`, `number`,
`year`, `date` of enactment, `last_amended`, `status`, `version`, `source`, `retrieved`), then the title as
`#`, the long title and enacting formula, then the text. Parts, chapters and schedules are headings, nested
by depth; sections are headings of the form `N. Marginal note`. Footnotes become Markdown footnotes; tables
become Markdown tables when simple, otherwise HTML. Articles of the Constitution are `###` headings.

## Not covered

- **Statutory Instruments** (~40,000+ S.I.s since 1922) — skipped as mass-volume secondary legislation.
  They are available on the eISB (`/eli/<year>/si/<n>/made/en/html`). The 18 S.I.s revised by the LRC are
  also skipped.
- Consolidated versions of Acts that have **no LRC Revised Act** — no official consolidation exists; those
  Acts are given as enacted.
- Official **translations** (Irish versions of English-language Acts on achtanna.ie / oireachtas.ie) — only
  the text(s) as enacted are included. Constitutional amendment Acts and the Acts enacted in Irish are
  included in both languages as published on the eISB.
- **Pre-1922 statutes not published in electronic form** on the eISB (the eISB notes that a small number of
  statutes kept in force by the Statute Law Revision Act 2007 have no electronic text), UK *local and personal*
  Acts 1801–1922, and pre-1922 statutes repealed by the Statute Law Revision Acts.
- Bills, Oireachtas debates, EU law.
- Texts listed on the eISB but not retrievable at generation time:
  - https://www.irishstatutebook.ie/eli/1833/act/49/enacted/en/html (listed on the year page, but the page returns 404)

## Sources

- **Electronic Irish Statute Book (eISB)**, Office of the Attorney General — <https://www.irishstatutebook.ie>
  - Acts 1922–present: XML source, `https://www.irishstatutebook.ie/eli/<year>/act/<n>/enacted/en/xml`
    (private Acts: `/eli/<year>/prv/<n>/...`, constitutional amendments: `/eli/<year>/ca/<n>/...`);
    year lists from `/eli/<year>/act`.
  - Pre-1922 Acts: print HTML view `https://www.irishstatutebook.ie/eli/<year>/act/<n>/enacted/en/print`
    (no XML is published for them).
  - Constitution: `https://www.irishstatutebook.ie/eli/cons/en/html` and `/eli/cons/ga/html`.
- **Law Reform Commission — Revised Acts** — <https://revisedacts.lawreform.ie>; list from
  `/revacts/chron`, XML from `/eli/<year>/act/<n>/revised/en/xml`.

## Licence

Text from the eISB is re-used under the **Oireachtas (Open Data) PSI Licence**, which incorporates the
Creative Commons Attribution 4.0 International licence (see
<https://www.irishstatutebook.ie/eli/open-data.html> and
<https://www.oireachtas.ie/parliament/about/copyrightandre-use/>): © Government of Ireland; Oireachtas copyright material
reproduced with the permission of the Houses of the Oireachtas. Revised Acts are administrative
consolidations prepared by the Law Reform Commission (a public body) and re-used as public sector
information; they carry the LRC's disclaimer that they are not an official statement of the law.
Only the texts as enacted (and the Constitution as published by the Oireachtas) are authoritative.

This repository is an unofficial conversion. Where a conversion error is suspected, refer to the `source` URL.

## Regenerating

```sh
pip install -r scripts/requirements.txt
python scripts/index.py      # year lists + LRC list -> ../_raw/ie/index.json
python scripts/fetch.py      # download XML/HTML into ../_raw/ie (cached; ≤4 parallel requests, throttled)
python scripts/convert.py    # write constitution/, acts/, pre-1922/
python scripts/readme.py     # regenerate this README
```

The raw cache location can be changed with `LAWCODEX_RAW`. Neither site's robots.txt sets restrictions or a
Crawl-delay; requests are throttled to ≥0.25 s apart per host with the User-Agent
`LawCodex/1.0 (+https://github.com/LawCodex)`.
