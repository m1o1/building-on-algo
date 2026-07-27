"""Image alt text: brackets escaped outside code spans, left alone inside.

This file exists because of a defect that every gate passed. `build.py` turns
one `{{include-fig:slug}}` directive into a Markdown image paragraph, and it
escaped `[` and `]` across the whole caption -- which is right where pandoc is
still looking for link syntax, and wrong inside a backtick code span, where
inline code has already been parsed and a backslash is simply a backslash.
The book shipped a caption reading ``args\\[0\\]``, in monospace, backslashes
on the page, and it took a rasterised read of the figure to see it: the
structure checks all pass, the build succeeds, and the PDF is well formed. The
only witness is the glyph.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import build  # noqa: E402


def test_brackets_outside_code_spans_are_escaped() -> None:
    assert build.escape_alt_brackets("see [1] and [2]") == r"see \[1\] and \[2\]"


def test_brackets_inside_a_code_span_are_left_alone() -> None:
    # The exact shape that shipped wrong: an identifier subscript in the
    # abi-call-wire caption.
    caption = "the selector that occupies `args[0]`; each argument follows"
    assert build.escape_alt_brackets(caption) == caption


def test_a_caption_mixing_both_escapes_only_the_prose_half() -> None:
    got = build.escape_alt_brackets("`args[0]` holds it [see the figure]")
    assert got == r"`args[0]` holds it \[see the figure\]"


def test_a_multi_backtick_span_is_one_span() -> None:
    # ``a ` b [x]`` is a single code span whose body contains a lone backtick.
    # A closing run must match the opening run's length, or the span ends in
    # the middle of the code and the tail gets escaped as prose.
    caption = "``a ` b [x]`` and [y]"
    assert build.escape_alt_brackets(caption) == r"``a ` b [x]`` and \[y\]"


def test_an_unclosed_backtick_is_prose() -> None:
    # No closing run means no code span, so pandoc will read the brackets as
    # link syntax and they still need escaping.
    assert build.escape_alt_brackets("stray ` tick [z]") == r"stray ` tick \[z\]"


def test_every_shipped_caption_survives_a_round_trip() -> None:
    """No caption in the index gains a backslash inside a code span.

    The unit cases above test the function; this one tests the corpus, which
    is what actually goes to the page. It is cheap and it is the check that
    would have caught the original defect on the day it was introduced.
    """
    index = build.load_figure_index(ROOT / "figures" / "index.yaml")
    assert index, "figures/index.yaml did not load"
    for slug, entry in index.items():
        alt = build.escape_alt_brackets(build.figure_caption("Figure 0-0", entry["caption"]))
        for span in build.CODE_SPAN_RE.finditer(alt):
            assert "\\" not in span.group("body"), (
                f"{slug}: alt text carries a backslash inside the code span "
                f"{span.group(0)!r}, which pandoc typesets literally"
            )
