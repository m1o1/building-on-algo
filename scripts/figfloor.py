"""On-page glyph sizes for every figure PDF, against the 8pt house floor.

On-page size = native size x min(1, LINEWIDTH / natural width). pdfplumber
reports the native size, so the scale has to be applied here. The *minimum*
is what the floor is about: a drawing whose modal type clears 8pt can still
set its edge labels at six.

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
"""
import glob
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

import pdfplumber

LINEWIDTH = 470.4   # \linewidth in this book, from chapters/metadata.yaml geometry
FLOOR = 8.0        # the house minimum, in points ON THE PAGE
FIG_OUT = Path(__file__).resolve().parent.parent / "figures" / "out"


def font_size(char) -> float:
    matrix = char.get("matrix")
    if not matrix:
        return float(char["size"])
    _, b, _, d, _, _ = matrix
    return math.hypot(float(b), float(d))


rows = []
for path in sorted(glob.glob(str(FIG_OUT / "*.pdf"))):
    slug = os.path.basename(path)[:-4]
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[0]
        width = float(page.width)
        by_size = defaultdict(list)
        for char in page.chars:
            by_size[round(font_size(char), 2)].append(char["text"])
    if not by_size:
        continue
    scale = min(1.0, LINEWIDTH / width)
    smallest = min(by_size)
    sample = "".join(by_size[smallest])[:34].replace("\n", " ")
    rows.append((round(smallest * scale, 2), slug, width, smallest, max(by_size), sample))

rows.sort()
for on_page, slug, width, native_min, native_max, sample in rows:
    flag = "FAIL" if on_page < FLOOR else "ok  "
    need = FLOOR * width / LINEWIDTH if width > LINEWIDTH else FLOOR
    print(
        f"{flag} {slug:24s} min {on_page:5.2f}pt  canvas {width:7.2f}pt  "
        f"native {native_min:5.2f}-{native_max:5.2f}  "
        f"needs >= {need:5.2f}pt ({need / 0.75:5.2f}px)  {sample!r}"
    )
bad = sum(1 for r in rows if r[0] < FLOOR)
print(f"\n{bad} of {len(rows)} below the {FLOOR}pt floor")
sys.exit(1 if bad else 0)
