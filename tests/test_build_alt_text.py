"""Figure captions on their way to a page: Markdown out, LaTeX and HTML in.

One caption string in `figures/index.yaml` has to arrive intact in two
renderers that share none of the same escaping rules, and this file tests the
two functions that get it there -- `escape_alt_brackets`, for the PDF, and
`caption_to_html`, for the mdbook edition. They are tested together because
they are the same mistake made twice: in each case the caption is Markdown,
the destination is not, and the naive path typesets the markup instead of
applying it.

This file exists because of a defect that every gate passed. `build.py` turns
one `{{include-fig:slug}}` directive into a Markdown image paragraph, and it
escaped `[` and `]` across the whole caption -- which is right where pandoc is
still looking for link syntax, and wrong inside a backtick code span, where
inline code has already been parsed and a backslash is simply a backslash.
One committed revision -- `b93e5ba`, where `figures/index.yaml` first carried
a backticked caption and `build.py` still escaped the whole string -- built a
PDF whose Figure 1-5 caption read ``args\\[0\\]``, in monospace, backslashes on
the page. It took a rasterised read of the figure to see it: the structure
checks all pass, the build succeeds, and the PDF is well formed. The only
witness is the glyph.

The precision matters. Earlier drafts of this docstring said "the book
shipped", which is a claim about a released artifact and is not what happened:
the defect lived in the repository for exactly one commit and was caught by
this project's own review loop. Overstating a defect's reach is not a harmless
bit of emphasis -- it is the sort of detail a later reader checks, and finding
it wrong is a reason to distrust the rest of the note, which is the part that
is true.

`caption_to_html`'s three defects were found the same way and were not
reported by anyone: they were turned up while widening `FIGURE_IMG_RE`, in the
generated `mdbook/src/`, and every one of them had been on the HTML site for
as long as the site had figures. That is the same silence as the PDF defect
above, from the same cause -- pulldown-cmark passes a raw HTML block through
without looking inside it, so a caption full of backticks is well-formed
Markdown containing well-formed HTML containing printed backticks, and no
gate in this repository has an opinion about it.
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


def test_a_quote_in_the_caption_cannot_terminate_the_alt_attribute() -> None:
    # `four-clocks`'s caption, which is where this was found: the attribute
    # ended at the opening quote and the rest of the sentence was parsed as
    # further attributes.
    spoken, figcaption = build.caption_to_html('four values that look like "now"')
    assert '"' not in spoken
    assert spoken == "four values that look like &quot;now&quot;"
    assert figcaption == spoken


def test_a_code_span_becomes_code_in_the_caption() -> None:
    _, figcaption = build.caption_to_html("the `create=allow` route")
    assert figcaption == "the <code>create=allow</code> route"


def test_a_code_span_is_unmarked_in_the_spoken_alt() -> None:
    # Alt text is read aloud. Backticks are markup, not words, and a screen
    # reader that pronounces them is reading the wrong string.
    spoken, _ = build.caption_to_html("the `create=allow` route")
    assert spoken == "the create=allow route"
    assert "`" not in spoken and "<code>" not in spoken


def test_the_markdown_bracket_escape_is_undone() -> None:
    # `escape_alt_brackets` adds these for pandoc. HTML has no such escape, so
    # a backslash left in reaches the page as a backslash.
    spoken, figcaption = build.caption_to_html(r"the selector in `args[0]`, \[1\] of 4")
    assert spoken == "the selector in args[0], [1] of 4"
    assert figcaption == "the selector in <code>args[0]</code>, [1] of 4"


def test_a_tag_inside_a_code_span_is_escaped_as_content() -> None:
    # Ordering: escape first, mark up second. The other order emits a live
    # `<b>` inside the caption -- and `html.escape` afterwards would eat the
    # `<code>` tags this function just added.
    spoken, figcaption = build.caption_to_html("a `<b>` element & an ampersand")
    assert figcaption == "a <code>&lt;b&gt;</code> element &amp; an ampersand"
    assert spoken == "a &lt;b&gt; element &amp; an ampersand"


def test_the_pandoc_em_dash_spelling_is_converted() -> None:
    # ` --- ` is pandoc's, and pulldown-cmark leaves it as three hyphens.
    spoken, _ = build.caption_to_html("the fee --- and who pays it")
    assert spoken == "the fee — and who pays it"


def test_every_shipped_caption_produces_well_formed_html() -> None:
    """The corpus test, which is the one that would have caught all three.

    Each defect was a caption feature -- a quote, a backtick, a bracket
    escape -- that the unit cases above now cover one at a time. This asserts
    over what actually reaches the page: no raw quote can escape the `alt`
    attribute, no backtick survives into either output, and the only tags in
    the figcaption are the `<code>` pairs the function put there.
    """
    index = build.load_figure_index(ROOT / "figures" / "index.yaml")
    assert index, "figures/index.yaml did not load"
    # A corpus test proves nothing about a feature the corpus does not
    # contain, and two of the three defects were exactly that kind of
    # accident: one caption in twenty-one carries a quote, and if the day
    # comes when none does, this test goes on passing while covering less.
    # So assert the corpus still exercises what it is here to exercise.
    captions = [entry["caption"] for entry in index.values()]
    assert any('"' in c for c in captions), "no caption carries a quote any more"
    assert any("`" in c for c in captions), "no caption carries a code span any more"
    assert any("[" in c for c in captions), "no caption carries a bracket any more"
    for slug, entry in index.items():
        alt = build.escape_alt_brackets(build.figure_caption("Figure 0-0", entry["caption"]))
        spoken, figcaption = build.caption_to_html(alt)
        assert '"' not in spoken, f"{slug}: a raw quote would end the alt attribute"
        assert "`" not in spoken and "`" not in figcaption, (
            f"{slug}: a backtick survived into the rendered caption"
        )
        assert "\\[" not in figcaption and "\\]" not in figcaption, (
            f"{slug}: a Markdown bracket escape reached the HTML edition"
        )
        stripped = figcaption.replace("<code>", "").replace("</code>", "")
        assert "<" not in stripped and ">" not in stripped, (
            f"{slug}: figcaption carries a tag other than <code>: {figcaption!r}"
        )
        assert figcaption.count("<code>") == figcaption.count("</code>")
