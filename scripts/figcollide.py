#!/usr/bin/env python3
"""Find glyphs that render on top of a rule.

The defect this catches is the one no numeric gate sees: a text label that
overhangs the box it sits in, or that is centred in a gap exactly as wide as
itself, so its outermost glyphs land on the strokes either side and read as
part of them.  `sha512_256` rendering as `$ha512_256` in abi-call-wire.svg is
the recorded instance; `Application account` overhanging its fixed-150px
mermaid actor box in contract-as-sender.mmd is the second.  Both were found
only by a human looking at the raster.

METHOD.  Render the figure twice at high resolution: once with every shape
element (rect, line, path, polygon, circle, ellipse) deleted, leaving text
alone, and once with every <text> deleted, leaving shapes alone.  Both
rasters share one coordinate space, so no transform arithmetic is needed --
which matters, because mermaid emits its geometry inside translated groups
and the rect coordinates in the file are not the coordinates on the page.
Any pixel inked in BOTH rasters is a glyph drawn over a stroke.

Reported in canvas px, with a cluster's bounding box, so the caller can find
it in the source.  A handful of pixels is a stroke grazing a descender and is
usually fine; tens of pixels in a cluster that spans a glyph's full height is
the defect.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

SHAPES = ("rect", "line", "path", "polygon", "circle", "ellipse")
RENDER_W = 2400
INK = 140          # 0-255; strokes and text are both darker than this
MIN_CLUSTER = 10   # canvas-px of overlap below which we do not report

# The threshold is in CANVAS px, so a cluster's raw raster-pixel count has to be
# divided by scale*scale -- an area ratio -- before it is compared.  The first
# version compared the raw count against MIN_CLUSTER * scale, mixing a length
# scaling into an area, which let a 7 canvas-px cluster through a threshold of
# 12.  That cluster is the Application lifeline crossing the self-message label
# in contract-as-sender: mermaid draws every self-message label across the
# lifeline it belongs to, so it is structural rather than a layout mistake, and
# the raster reads it cleanly (the rule is thin, grey, and lands mid-glyph
# rather than flush with a glyph edge, unlike `$ha512_256`).  10 keeps that
# quiet and still fires on the real defect: the pre-fix `Application account`
# overhang measures 12 canvas-px in its largest cluster.


def _strip(svg: str, tags) -> str:
    for tag in tags:
        svg = re.sub(rf"<{tag}\b[^>]*/>", "", svg)
        svg = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", svg, flags=re.S)
    return svg


def _raster(svg: str, tmp: Path, name: str) -> np.ndarray:
    src = tmp / f"{name}.svg"
    png = tmp / f"{name}.png"
    src.write_text(svg)
    subprocess.run(
        ["rsvg-convert", "-w", str(RENDER_W), "-b", "white", str(src), "-o", str(png)],
        check=True, capture_output=True,
    )
    return np.array(Image.open(png).convert("L")) < INK


def _canvas_width(svg: str) -> float:
    m = re.search(r'viewBox="[-\d.]+ [-\d.]+ ([\d.]+)', svg)
    if m:
        return float(m.group(1))
    return float(re.search(r'\bwidth="([\d.]+)', svg).group(1))


def _clusters(mask: np.ndarray, scale: float, gap: float = 6.0):
    """Bounding boxes of connected-ish regions, merged within `gap` canvas px."""
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return []
    order = np.argsort(xs)
    xs, ys = xs[order], ys[order]
    tol = gap * scale
    out, cur = [], [xs[0], xs[0], ys[0], ys[0], 1]
    for x, y in zip(xs[1:], ys[1:]):
        if x - cur[1] <= tol:
            cur[1] = max(cur[1], x)
            cur[2] = min(cur[2], y)
            cur[3] = max(cur[3], y)
            cur[4] += 1
        else:
            out.append(cur)
            cur = [x, x, y, y, 1]
    out.append(cur)
    return out


def check(path: Path) -> int:
    svg = path.read_text()
    width = _canvas_width(svg)
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        text_only = _strip(svg, SHAPES)
        shape_only = _strip(svg, ("text",))
        t = _raster(text_only, tmp, "t")
        s = _raster(shape_only, tmp, "s")
    if t.shape != s.shape:
        print(f"{path.name}: raster shape mismatch {t.shape} vs {s.shape}")
        return 1
    scale = t.shape[1] / width
    both = t & s
    hits = [c for c in _clusters(both, scale) if c[4] / (scale * scale) >= MIN_CLUSTER]
    if not hits:
        print(f"ok   {path.stem}")
        return 0
    total = int(both.sum() / (scale * scale))
    print(f"HIT  {path.stem}  {len(hits)} cluster(s), {total} canvas-px of overlap")
    for x0, x1, y0, y1, n in sorted(hits, key=lambda c: -c[4]):
        print(
            f"       x {x0/scale:7.1f}..{x1/scale:7.1f}  y {y0/scale:7.1f}..{y1/scale:7.1f}"
            f"  ({n/(scale*scale):5.0f} px)"
        )
    return 1


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        root = Path(__file__).resolve().parent.parent
        args = sorted(str(p) for p in (root / "figures" / "out").glob("*.svg"))
    bad = 0
    for a in args:
        bad += check(Path(a))
    print(f"\n{bad} of {len(args)} figures have text drawn over a rule")
    sys.exit(1 if bad else 0)
