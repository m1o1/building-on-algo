"""On-page glyph sizes and page footprints for every figure PDF.

Two measurements, because a figure can fail two ways and the second one was
invisible to this script for a whole round.

TYPE SIZE. On-page size = native size x scale. pdfplumber reports the native
size, so the scale has to be applied here. The *minimum* is what the floor is
about: a drawing whose modal type clears 8pt can still set its edge labels at
six.

DO NOT USE `char["size"]` -- IT IS NOT THE FONT SIZE FOR ROTATED TEXT. For an
upright glyph pdfplumber's `size` is the font matrix's vertical scale, which is
what we want; for a rotated one it is the glyph's *bounding-box height on the
page*, which after a 90-degree rotation is the glyph's WIDTH. A rotated lower-
case `o` therefore reports about 5.7 where the type is 9.375, a rotated space
reports 2.98, and the narrower the letter the smaller the lie. The first
version of this script did use it, and reported `constant-product-curve` at
2.40pt on the page with "native type down to 2.98pt" -- a figure whose smallest
real type is the 8.25pt tick labels. The tell was that no such size appears
anywhere in the source, and the shape of the error is worth remembering: the
bogus population was ALL non-upright and ALL from one rotated axis label, so it
looked like a real cluster of tiny type rather than like noise.

The font size is the magnitude of the text matrix's y-axis vector,
`sqrt(b^2 + d^2)` for `matrix = (a, b, c, d, e, f)`, which is rotation-
invariant and agrees with `size` exactly on upright text.

THE SCALE IS NOT `LINEWIDTH / width`, AND ASSUMING IT WAS COST A ROUND.
`graphicx` is configured with `width=\\maxwidth, height=\\maxheight,
keepaspectratio`, so the factor is `min(1, LINEWIDTH / W, TEXTHEIGHT / H)` and
a figure taller than `1.316 x W` is bound by its HEIGHT, not its width. For any
such figure the old formula reported type LARGER than the page actually sets
it, which is the one direction an instrument must never err in.

PAGE FOOTPRINT. Type size is not the only way a figure damages a page, and it
was not the way that got through. `mbr-rising-floor` was redrawn to clear the
type floor and did clear it -- at 604.8pt of on-page height, 97.7% of the
619pt text block, leaving nothing for the caption that has to sit beneath the
drawing. The caption's last line bottomed 15.6pt below every neighbouring
page's and cleared the folio by 3.4pt where the book's normal gap is about
19pt. Nothing in this script could see it, because this script only ever read
`page.width`. It reads both now and warns above `FOOTPRINT_WARN`.

`FOOTPRINT_WARN` is 570pt rather than 619pt precisely because 619 is the
number that misled the redraw: `\\textheight` is what the drawing may occupy
only if it has no caption, and every figure in this book has a two-to-three
sentence caption worth roughly 40-60pt. A figure between 570 and 619 does not
overflow on its own; it leaves too little for the caption, and the caption is
what falls off the bottom.

THE EVIDENCE FOR 570 IS THE TALLEST FIGURE THAT DEMONSTRABLY SETS CLEANLY,
AND IT HAS MOVED. This docstring cited three figures between 500 and 535pt
(`router-decision`, `group-commit`, `four-clocks`) as the whole of the
evidence, which left the band from 535 to 570 asserted rather than measured --
and then `mbr-rising-floor` grew to **547.01pt** and landed inside it, so the
threshold was carrying a figure it had never been shown to cover. It does
cover it, checked rather than assumed: Figure 4-2 sets on **printed folio 129,
which is pdf page index 130** -- in this book the folio is always the index
minus one, because the cover is index 1 and carries no folio, so a page
citation that does not say which of the two it is will send the next reader one
page off. The drawing's last line of in-figure text sits at `top` 615.5 /
`bottom` 623.9; the caption sets in two lines, `top` 643.8 (`bottom` 654.7) and
`top` 657.3 (`bottom` 668.3); and a further line of body prose follows at `top`
695.7 (`bottom` 706.6), above the folio at 729.2. Note that 668.3 and 706.6 are
`bottom` values -- this note quoted them as `top`s for a round, which understates
the caption's and the body line's reach by a full line height. Four figures
now exceed 500pt -- 547.01, 533.89 (`router-decision`), 521.93
(`group-commit`), 510.38 (`four-clocks`) -- and the tallest of them clears its
caption with a body line to spare. That is where the threshold comes from, and
570 keeps roughly 23pt of headroom above the tallest measured pass.

RE-CHECK THIS WHEN A FIGURE GROWS PAST 547pt, not when one trips the warning.
The warning fires at 570; the evidence stops at 547. A figure landing in
between is inside the gate and outside the demonstration, which is exactly the
state `mbr-rising-floor` was in for several rounds. Find the page the figure
lands on, confirm the caption is on it, and extend the note above. Find it by
the folio printed on the page -- the lone arabic word with `726 < top < 745` --
rather than by counting pages, and say in the note which of the two numbers you
are quoting. Do not look for the figure in `page.images`: these drawings are
form XObjects, so `page.images` is empty on exactly the pages that carry one.

A footprint warning does not fail the run; only the type floor does. The
threshold is a judgement about caption length rather than a hard geometric
limit, and a gate that fails on a judgement gets switched off.
"""
import glob
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import pdfplumber

# \linewidth and \textheight for this book, from chapters/metadata.yaml's
# geometry: letter paper, margin=1in, top=1.2in, bottom=1.2in.
LINEWIDTH = 470.4
TEXTHEIGHT = 619.0
FLOOR = 8.0          # the house minimum type size, in points ON THE PAGE
FOOTPRINT_WARN = 570.0   # on-page height above which the caption runs out of room
FIG_OUT = Path(__file__).resolve().parent.parent / "figures" / "out"


def font_size(char) -> float:
    matrix = char.get("matrix")
    if not matrix:
        return float(char["size"])
    _, b, _, d, _, _ = matrix
    return math.hypot(float(b), float(d))


def page_scale(width: float, height: float) -> float:
    """`keepaspectratio` against both \\maxwidth and \\maxheight."""
    return min(1.0, LINEWIDTH / width, TEXTHEIGHT / height)


rows = []
for path in sorted(glob.glob(str(FIG_OUT / "*.pdf"))):
    slug = os.path.basename(path)[:-4]
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        width = float(page.width)
        height = float(page.height)
        by_size = defaultdict(list)
        for char in page.chars:
            by_size[round(font_size(char), 2)].append(char["text"])
    if not by_size:
        continue
    scale = page_scale(width, height)
    smallest = min(by_size)
    sample = "".join(by_size[smallest])[:30].replace("\n", " ")
    rows.append((
        round(smallest * scale, 2), slug, width, height, scale,
        smallest, max(by_size), sample,
    ))

rows.sort()
for on_page, slug, width, height, scale, native_min, native_max, sample in rows:
    flag = "FAIL" if on_page < FLOOR else "ok  "
    need = FLOOR / scale
    on_h = height * scale
    # Which constraint actually binds, or `-` where neither does: a figure
    # smaller than the text block in both axes is set at 1:1 and is not
    # "width-bound" in any useful sense. Six of the twenty-one are in that
    # case, and labelling them by whichever ratio happened to be smaller read
    # as a claim about scaling that was not being applied.
    if scale == 1.0:
        bound = "-"
    else:
        bound = "H" if TEXTHEIGHT / height < LINEWIDTH / width else "W"
    tall = " TALL" if on_h > FOOTPRINT_WARN else ""
    print(
        f"{flag} {slug:24s} min {on_page:5.2f}pt  page {width * scale:6.2f}x"
        f"{on_h:6.2f}pt [{bound}]{tall:5s}  native {native_min:5.2f}-"
        f"{native_max:5.2f}  needs >= {need:5.2f}pt ({need / 0.75:5.2f}px)  "
        f"{sample!r}"
    )
bad = sum(1 for r in rows if r[0] < FLOOR)
tall = [r[1] for r in rows if r[3] * r[4] > FOOTPRINT_WARN]
print(f"\n{bad} of {len(rows)} below the {FLOOR}pt floor")
print(
    f"{len(tall)} of {len(rows)} above the {FOOTPRINT_WARN:.0f}pt footprint "
    f"warning{': ' + ', '.join(tall) if tall else ''}"
)
sys.exit(1 if bad else 0)
