#!/usr/bin/env python3
"""Page-makeup defects in a built PDF, found by scanning page boundaries.

WHY THIS EXISTS. A change that decides where a *line* ends is measured by the
per-paragraph `Overfull \\hbox` diff against a control build. A change that
decides where a *page* ends -- `\\brokenpenalty`, `\\Needspace`, `\\nopagebreak`,
`widowpenalty`, float placement -- moves no line ending at all, so that diff is
empty for it by construction, and reading the emptiness as "no effect" is how a
typography variant that stranded two callouts at a page foot got shipped for a
round. `Underfull \\vbox` is not the instrument either: it is a search tool for
finding pages worth rasterising, and two variants can sit half a percent apart
on it while differing by everything on the page. This script is the instrument.
It reads the artifact the reader holds and reports the four defects that page
makeup actually produces.

THE FOUR STATISTICS, defined here because a table of them elsewhere is not
self-describing and every previous attempt to re-derive these numbers from a
prose description of them failed:

  broken page-ends     the last body line of a page ends in a hyphen or a
                       slash directly after an alphanumeric or a `)`. Most are
                       correct typography -- English hyphenates across pages --
                       so this is a population to look at, not a defect count.

  ident-splits         the last body line ends in `.`, `_` or `/` after an
                       alphanumeric AND the next page's first body line starts
                       lowercase or with `_`. This is the *candidate* set for a
                       page turn landing inside an identifier. The bulk of it is
                       sentence-final periods before a code fence, which are
                       benign; the genuine ones have to be read off the listing
                       below the count. Do not quote the raw number as a defect
                       count -- name the sites.

  stranded captions    a page's last body line is the start of an
                       `Example|Figure|Table N-M.` caption, so the label sits at
                       the foot of a page naming something on the next one. The
                       front matter's list of tables and list of figures match
                       this shape too; they are filtered by their dot leaders
                       (see `_is_contents_entry`) because otherwise they read as
                       a permanent floor of one or two and get re-litigated
                       every round as a "known false positive".

  empty callout bars   a page's last body line is exactly a callout label, so
                       the reader turns the page on a coloured header bar with
                       no body under it.

USAGE

    python3 scripts/pagescan.py Building-on-Algorand.pdf
    python3 scripts/pagescan.py ctl=/tmp/meas/r18ctl/book.pdf shipped=book.pdf

Every PDF given is reported with the same code, which is the point: these
numbers are only ever meaningful as a comparison between a control build and a
variant built from the same source. A single column of them describes a book,
not a mechanism.

TWO TRAPS, both met in practice and both expensive.

First, THE CONTROL HAS TO BE BUILT AT THE CURRENT SOURCE. An old build
directory silently answers a question about an older manuscript. One unrelated
caption edit moved a control's `Underfull \\vbox` from 179 to 182 and its
broken page-ends from 21 to 20 in an afternoon.

Second, `--lua-filter=path` is ONE argv token in this build. Removing a filter
by deleting the token and its neighbour eats the *preceding* filter -- doing
that dropped `figures.lua`, cost 18 pages and all 21 figures, and would have
been invisible in the statistic under test. It was the page count that caught
it, which is the argument for printing every number the harness has and not
only the one being asked about. Prefer
`cmd = [c for c in cmd if 'name.lua' not in c]` and assert on the surviving
filter count.

An earlier version of this script hardcoded three PDF paths and ignored argv
entirely, so passing a path on the command line reported a stale build's
numbers under the new build's name. That is why this one takes its inputs as
arguments and prints the path it read next to every tag.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# A running head, a folio, or a part title -- furniture rather than body text.
FURNITURE_RE = re.compile(r"^(CHAPTER \d+\.|APPENDIX [A-Z]\.|PART )")
FOLIO_RE = re.compile(r"\d+")

BROKEN_END_RE = re.compile(r"[A-Za-z0-9)][_/‐‑-]$")
IDENT_END_RE = re.compile(r"[A-Za-z0-9)][._/]$")
IDENT_START_RE = re.compile(r"^[a-z_]")
CAPTION_RE = re.compile(r"^(Example|Figure|Table) \d+-\d+\.")
CALLOUT_RE = re.compile(r"(GOTCHA|SETUP|NOTE|WARNING|TIP|PITFALL)$")
# Three or more dot-leader groups: a contents entry, never a caption in situ.
CONTENTS_RE = re.compile(r"(\.\s+){3,}")


def page_texts(pdf: str) -> list[str]:
    result = subprocess.run(
        ["pdftotext", "-layout", pdf, "-"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.split("\f")


def body_lines(page: str, from_top: bool) -> list[str]:
    """Non-blank lines of a page with the furniture stripped off one end.

    `from_top` strips the running head and folio that lead a page; otherwise
    the ones that trail it. Only the end being inspected is cleaned, because
    stripping both would need the caller to say which end it meant anyway.
    """
    lines = [line.rstrip() for line in page.split("\n") if line.strip()]
    while lines:
        candidate = (lines[0] if from_top else lines[-1]).strip()
        is_furniture = (
            FOLIO_RE.fullmatch(candidate)
            or FURNITURE_RE.match(candidate)
            or (candidate.isupper() and len(candidate) > 12)
        )
        if not is_furniture:
            break
        lines.pop(0) if from_top else lines.pop()
    return lines


def _is_contents_entry(line: str) -> bool:
    """A list-of-tables or list-of-figures row rather than a caption in place.

    Both render as `Table 9-5. Chapter build sequence . . . . . 213`, which
    matches the caption shape exactly. The dot leaders are what separate them
    and they are not otherwise produced by this book's prose.
    """
    return CONTENTS_RE.search(line) is not None


def scan(pdf: str) -> dict[str, list[tuple]]:
    pages = page_texts(pdf)
    found: dict[str, list[tuple]] = {
        "broken": [], "ident": [], "caption": [], "callout": [],
    }
    for index in range(len(pages) - 1):
        above = body_lines(pages[index], from_top=False)
        below = body_lines(pages[index + 1], from_top=True)
        if not above or not below:
            continue
        # The PDF page number, not the printed folio: `book.log`'s `[N]`
        # markers are folios and the physical page is `N + 1`, so a scan that
        # reports one and a log that reports the other disagree by one on
        # every site and the disagreement looks like a measurement error.
        page_number = index + 1
        last, first = above[-1].strip(), below[0].strip()
        if BROKEN_END_RE.search(last):
            found["broken"].append((page_number, last[-40:]))
        if IDENT_END_RE.search(last) and IDENT_START_RE.match(first):
            found["ident"].append((page_number, last[-40:], first[:30]))
        if CAPTION_RE.match(last) and not _is_contents_entry(last):
            found["caption"].append((page_number, last[:55]))
        if CALLOUT_RE.fullmatch(last):
            found["callout"].append((page_number, last))
    return found


def report(tag: str, pdf: str) -> dict[str, list[tuple]]:
    found = scan(pdf)
    print(
        f"=== {tag}: broken page-ends {len(found['broken'])} "
        f"| ident-split candidates {len(found['ident'])} "
        f"| stranded captions {len(found['caption'])} "
        f"| empty callout bars {len(found['callout'])}   [{pdf}]"
    )
    for site in found["ident"]:
        print("   IDENT  ", site)
    for site in found["caption"]:
        print("   CAPTION", site)
    for site in found["callout"]:
        print("   CALLOUT", site)
    return found


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip().split("\n\n")[0])
        print("\nusage: pagescan.py [tag=]file.pdf [[tag=]file.pdf ...]")
        return 2
    for argument in argv:
        tag, _, path = argument.rpartition("=")
        if not path:
            tag, path = "", argument
        if not tag:
            tag = Path(path).stem
        if not Path(path).exists():
            print(f"=== {tag}: MISSING [{path}]")
            continue
        report(tag, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
