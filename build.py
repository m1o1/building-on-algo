#!/usr/bin/env python3
"""
Unified build script for Building on Algorand.

Usage:
    python build.py mdbook            # Build static HTML to mdbook/book/
    python build.py mdbook --serve    # Build and start local dev server
    python build.py mdbook --open     # Build and open in browser
    python build.py pdf               # Build PDF via pandoc + xelatex
    python build.py all               # Build both mdbook and PDF
    python build.py concat            # Reconstruct single Building-on-Algorand.md

Chapter sources live in chapters/. File prefixes control ordering:
    F*  = front matter     (Legal Notice, Preface)
    0*  = numbered chapters
    A*  = appendices       (Cookbook, Gotchas)
    Z*  = back matter      (What's Next, Glossary, Bibliography)

Prerequisites:
    mdbook CLI              # for mdbook target
    pandoc + xelatex        # for pdf target

Install mdbook from the official guide:
    https://rust-lang.github.io/mdBook/guide/installation.html
    cargo install mdbook
    # or download a precompiled binary for Windows/macOS/Linux
    # or, on macOS with Homebrew: brew install mdbook
"""

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CHAPTERS_DIR = ROOT / "chapters"
CHANGES_DIR = ROOT / "changes"
MDBOOK_DIR = ROOT / "mdbook"
SRC_DIR = MDBOOK_DIR / "src"
FIGURES_DIR = ROOT / "figures"

sys.path.insert(0, str(ROOT / "scripts"))
import spine  # noqa: E402

# ---------------------------------------------------------------------------
# Book structure metadata (derived from scripts/spine.py — the one spine table)
# ---------------------------------------------------------------------------

# Part breaks: chapter filename → mdBook SUMMARY.md part header.
# Inserted before the named chapter in the table of contents.
PART_BREAKS: dict[str, str] = {
    spine.first_of_part(p.number).filename: f"# Part {p.roman}: {p.title}"
    for p in spine.PARTS
}
PART_BREAKS[spine.APPENDICES[0]] = "# Appendices"

# Front-matter chapters appear as prefix entries (no bullet) in SUMMARY.md.
FRONT_MATTER = set(spine.FRONT_MATTER)

# Back-matter chapters appear as suffix entries (no bullet) after a separator.
BACK_MATTER = set(spine.BACK_MATTER)


# ---------------------------------------------------------------------------
# Chapter file discovery
# ---------------------------------------------------------------------------

def _chapter_sort_key(path: Path) -> tuple[int, str]:
    """Sort key that orders F* < 0* < A* < Z*."""
    c = path.name[0]
    order = {"F": 0, "A": 2, "Z": 3}.get(c, 1)
    return (order, path.name)


def get_chapter_files() -> list[Path]:
    """Return chapter .md files from chapters/ in book order."""
    return sorted(
        (p for p in CHAPTERS_DIR.glob("*.md")),
        key=_chapter_sort_key,
    )


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def clean_title(heading: str) -> str:
    """Extract display title from a heading line (strip # and {attrs})."""
    t = re.sub(r"^#+\s*", "", heading)
    t = re.sub(r"\s*\{[^}]*\}\s*$", "", t)
    return t.strip()


def extract_heading(text: str) -> str | None:
    """Find the first top-level # heading outside code blocks."""
    in_code = False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            in_code = not in_code
        if not in_code and re.match(r"^# ", line):
            return line
    return None


# ---------------------------------------------------------------------------
# Pandoc → mdBook transforms
# ---------------------------------------------------------------------------

def _is_math_content(content: str) -> bool:
    """Heuristic: does text between $...$ look like LaTeX math, not currency?"""
    s = content.strip()
    if not s:
        return False
    if "\\" in s:
        return True
    if "_" in s or "^" in s:
        return True
    if "{" in s or "}" in s:
        return True
    if len(s) == 1 and s.isalpha():
        return True
    if len(s) <= 30 and re.match(r"^[\w\s+\-*/=<>.,()]+$", s):
        if any(c in s for c in "+-*/=<>"):
            return True
    return False


def _protect_math_escapes(content: str) -> str:
    r"""Adjust underscores so math renders correctly in MathJax via pulldown-cmark.

    Inside \text{...}: strip the backslash from \_ (MathJax text mode treats _ as
    literal, and \_ would render with a visible backslash).
    Outside \text{...}: escape bare _ to \_ so pulldown-cmark does not interpret
    them as emphasis markers. MathJax treats \_ as a literal underscore in math
    mode, which is equivalent to _ for subscripts.
    """
    # Step 1: Inside \text{...}, just remove \_ → _ (text mode _ is literal)
    content = re.sub(
        r"\\text\{[^}]*\}",
        lambda m: m.group(0).replace("\\_", "_"),
        content,
    )
    # Step 2: Escape all remaining bare _ (subscripts) so pulldown-cmark
    # does not treat them as emphasis. Use a negative lookbehind to skip
    # already-escaped \_.
    content = re.sub(r"(?<!\\)_", r"\\_", content)
    return content


def _convert_math_delimiters(text: str) -> str:
    r"""Convert $...$ and $$...$$ to MathJax \\(...\\) and \\[...\\]."""
    lines = text.split("\n")
    out: list[str] = []
    in_code = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code

        if in_code:
            out.append(line)
            continue

        # Display math: $$...$$ on its own line
        dm = re.match(r"^(\s*)\$\$(.+)\$\$\s*$", line)
        if dm:
            indent, content = dm.group(1), dm.group(2)
            content = _protect_math_escapes(content)
            out.append(f"{indent}\\\\[{content}\\\\]")
            continue

        # Inline math: $...$ (not preceded by \ or $)
        def _replace_inline(m: re.Match) -> str:
            content = m.group(1)
            if _is_math_content(content):
                content = _protect_math_escapes(content)
                return f"\\\\({content}\\\\)"
            return m.group(0)

        line = re.sub(r"(?<![\$\\])\$([^$\n]+?)\$(?!\$)", _replace_inline, line)
        out.append(line)

    return "\n".join(out)


# Fenced-div callout classes used in chapter sources (pandoc syntax:
# `::: {.gotcha #id topic="..." title="..."}`). Rendered as styled HTML
# blocks for mdBook; the PDF pipeline maps them to LaTeX environments.
CALLOUT_LABELS = {
    "gotcha": "Gotcha",
    "note": "Note",
    "warning": "Warning",
    "tip": "Tip",
    "tryit": "Try it",
    "check": "Check yourself",
    "setup": "Setup",
    "spec": "The spec",
}


def _title_to_html(s: str) -> str:
    """Escape a div title attribute and render backtick spans as <code>."""
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s.replace(" --- ", " — ")


def _transform_divs_and_latex(text: str) -> str:
    """Strip raw ```{=latex} blocks and convert ::: fenced divs to HTML callouts."""
    lines = text.split("\n")
    out: list[str] = []
    in_code = False
    in_latex = False
    open_divs = 0

    for line in lines:
        stripped = line.strip()

        if in_latex:
            if stripped.startswith("```"):
                in_latex = False
            continue

        if stripped.startswith("```"):
            if not in_code and re.match(r"^`{3,}\s*\{=latex\}", stripped):
                in_latex = True
                continue
            in_code = not in_code
            out.append(line)
            continue

        if in_code:
            out.append(line)
            continue

        # Standalone inline raw-latex spans, e.g. `\chaptermark{...}`{=latex}
        if re.match(r"^`[^`]*`\{=latex\}\s*$", stripped):
            continue

        m = re.match(r"^:{3,}\s*\{\.([A-Za-z][\w-]*)([^}]*)\}\s*$", stripped)
        if m:
            cls, attrs = m.group(1), m.group(2)
            tm = re.search(r'title="([^"]*)"', attrs)
            label = CALLOUT_LABELS.get(cls, cls.capitalize())
            heading = f"{label} — {_title_to_html(tm.group(1))}" if tm else label
            if out and out[-1].strip():
                out.append("")
            out.append(f'<div class="callout callout-{cls}">')
            out.append(f'<p class="callout-title">{heading}</p>')
            out.append("")
            open_divs += 1
            continue

        if re.match(r"^:{3,}\s*$", stripped) and open_divs:
            open_divs -= 1
            if out and out[-1].strip():
                out.append("")
            out.append("</div>")
            continue

        # Pandoc table captions (`: Table N-M. ...`) read as definition lists
        # in mdBook and swallow the preceding paragraph. Emit a caption <p>.
        cm = re.match(r"^: (Table \d+-\d+\..*)$", stripped)
        if cm:
            if out and out[-1].strip():
                out.append("")
            out.append(f'<p class="table-caption">{_title_to_html(cm.group(1))}</p>')
            continue

        out.append(line)

    return "\n".join(out)


def clean_for_mdbook(text: str) -> str:
    """Transform pandoc-flavored markdown for mdBook consumption.

    - Strips raw ```{=latex} blocks; converts ::: fenced divs to HTML callouts
    - Strips \\newpage and \\part{...} directives
    - Strips pandoc attributes from sub-headings
    - Converts --- to em-dash
    - Converts LaTeX math delimiters for MathJax
    - Drops content before the first # heading (part intros)
    - Strips {-} from the chapter heading
    """
    text = _transform_divs_and_latex(text)
    lines = text.split("\n")
    out: list[str] = []
    in_code = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code = not in_code

        # Drop LaTeX directives
        if stripped == "\\newpage" or re.match(r"^\\part\{.*\}$", stripped):
            continue

        if not in_code:
            # Strip pandoc attributes from sub-headings: ## Title {#id} → ## Title
            line = re.sub(r"^(#{2,6}\s+.+?)\s*\{[^}]*\}\s*$", r"\1", line)
            # Pandoc em-dashes → unicode
            line = line.replace(" --- ", " — ")

        out.append(line)

    result = "\n".join(out)
    result = _convert_math_delimiters(result)

    # Strip everything before the first # heading (part intros, blank lines)
    heading_match = re.search(r"^# .+$", result, re.MULTILINE)
    if heading_match:
        result = result[heading_match.start() :]

    # Strip {-} / {attrs} from the chapter-level heading
    result = re.sub(r"^(# .+?)\s*\{[^}]*\}\s*$", r"\1", result, count=1, flags=re.MULTILINE)

    return result


# ---------------------------------------------------------------------------
# mdBook build
# ---------------------------------------------------------------------------

BOOK_TOML = """\
[book]
title = "Building on Algorand"
description = "Smart Contracts from First Principles to Production DeFi"
authors = ["Generated with Claude"]
language = "en"
src = "src"

[build]
build-dir = "book"

[output.html]
additional-css = ["theme/custom.css"]
default-theme = "light"
preferred-dark-theme = "navy"
mathjax-support = true
site-url = "/"
"""

CUSTOM_CSS = """\
/* --- Callout / admonition blockquotes --- */
blockquote {
    border-left: 4px solid #4a8fed;
    padding: 0.75em 1em;
    margin: 1.5em 0;
    background: rgba(74, 143, 237, 0.04);
    border-radius: 0 4px 4px 0;
}

/* --- Fenced-div callouts (gotcha, note, warning, ...) --- */
.callout {
    border-left: 4px solid #888;
    border-radius: 0 4px 4px 0;
    padding: 0.75em 1em;
    margin: 1.5em 0;
    background: rgba(128, 128, 128, 0.06);
}
.callout .callout-title {
    font-weight: 700;
    margin: 0 0 0.5em 0;
}
.callout p:last-child { margin-bottom: 0; }
.table-caption {
    font-size: 0.9em;
    font-style: italic;
    margin: 0.5em 0 1em 0;
    opacity: 0.85;
}
.callout-gotcha  { border-left-color: #d9534f; background: rgba(217, 83, 79, 0.06); }
.callout-warning { border-left-color: #f0ad4e; background: rgba(240, 173, 78, 0.07); }
.callout-note    { border-left-color: #4a8fed; background: rgba(74, 143, 237, 0.06); }
.callout-tip     { border-left-color: #5cb85c; background: rgba(92, 184, 92, 0.07); }
.callout-tryit   { border-left-color: #9b59b6; background: rgba(155, 89, 182, 0.06); }
.callout-check   { border-left-color: #16a085; background: rgba(22, 160, 133, 0.06); }
.callout-setup   { border-left-color: #7f8c8d; background: rgba(127, 140, 141, 0.07); }
.callout-spec    { border-left-color: #2c3e50; background: rgba(44, 62, 80, 0.07); }

/* --- Tables --- */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 1.5em 0;
    font-size: 0.95em;
}
table th {
    font-weight: 600;
    text-align: left;
}
table th, table td {
    padding: 0.5em 0.75em;
}

/* --- Code blocks --- */
pre {
    border-radius: 6px;
}

/* --- Slightly tighter line-height for long chapters --- */
.content main {
    line-height: 1.7;
}
"""


def _build_changelog() -> str | None:
    """Combine changes/*.md into a single changelog page."""
    if not CHANGES_DIR.is_dir():
        return None
    change_files = sorted(CHANGES_DIR.glob("*.md"), reverse=True)
    if not change_files:
        return None
    sections = [p.read_text(encoding="utf-8").strip() for p in change_files]
    sections = [s for s in sections if s]
    if not sections:
        return None
    header = "# Changelog\n\nA record of revisions, fixes, and improvements made to this book.\n"
    return header + "\n\n---\n\n".join(sections) + "\n"


def build_mdbook(*, serve: bool = False, open_browser: bool = False) -> None:
    """Build the mdBook HTML site from chapter sources."""
    chapter_files = get_chapter_files()
    if not chapter_files:
        print("Error: no chapter files found in chapters/", file=sys.stderr)
        sys.exit(1)

    # Prepare output directories
    if SRC_DIR.exists():
        shutil.rmtree(SRC_DIR)
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    theme_dir = MDBOOK_DIR / "theme"
    theme_dir.mkdir(parents=True, exist_ok=True)

    summary_lines = ["# Summary\n"]

    # Cover page
    cover_img = ROOT / "building-on-algo.jpg"
    if cover_img.exists():
        shutil.copy2(cover_img, SRC_DIR / cover_img.name)
        cover_md = (
            '<div style="text-align: center; padding: 2em 0;">\n'
            f'<img src="./{cover_img.name}" alt="Building on Algorand" '
            'style="max-width: 100%; max-height: 80vh;" />\n'
            "</div>\n"
        )
        (SRC_DIR / "cover.md").write_text(cover_md, encoding="utf-8")
        summary_lines.append("[Cover](./cover.md)")

    # Figures referenced by chapters as figures/<name>.svg
    if FIGURES_DIR.exists():
        shutil.copytree(FIGURES_DIR, SRC_DIR / "figures", dirs_exist_ok=True)

    for path in chapter_files:
        text = path.read_text(encoding="utf-8")
        heading = extract_heading(text)
        if heading is None:
            continue

        title = clean_title(heading)
        cleaned = clean_for_mdbook(text)

        # Write cleaned chapter to mdbook/src/
        (SRC_DIR / path.name).write_text(cleaned, encoding="utf-8")

        # Part break before this chapter? Emit the part header plus an intro
        # page carrying the part blurb (which the pre-heading strip removes
        # from the chapter page itself).
        if path.name in PART_BREAKS:
            summary_lines.append(f"\n{PART_BREAKS[path.name]}\n")
            bm = re.search(r"\\part\{[^}]*\}\s*\n\n(.+?)\n\n", text, re.DOTALL)
            if bm and not path.name.startswith("A"):
                part_title = PART_BREAKS[path.name].lstrip("# ").strip()
                page_name = f"part-intro-{path.name}"
                blurb = bm.group(1).strip()
                (SRC_DIR / page_name).write_text(
                    f"# {part_title}\n\n{blurb}\n", encoding="utf-8"
                )
                summary_lines.append(f"- [{part_title}](./{page_name})")

        # Separator before back matter
        if path.name == "Z1-whats-next.md":
            summary_lines.append("\n---\n")

        # Convert pandoc em-dashes for display
        display_title = title.replace(" --- ", " — ")

        # SUMMARY.md entry: front/back matter get no bullet, chapters get bullet
        if path.name in FRONT_MATTER or path.name in BACK_MATTER:
            summary_lines.append(f"[{display_title}](./{path.name})")
        else:
            summary_lines.append(f"- [{display_title}](./{path.name})")

    # Changelog from changes/ directory
    changelog = _build_changelog()
    if changelog:
        (SRC_DIR / "changelog.md").write_text(changelog, encoding="utf-8")
        summary_lines.append("[Changelog](./changelog.md)")

    summary_lines.append("")
    (SRC_DIR / "SUMMARY.md").write_text("\n".join(summary_lines), encoding="utf-8")
    (MDBOOK_DIR / "book.toml").write_text(BOOK_TOML, encoding="utf-8")
    (theme_dir / "custom.css").write_text(CUSTOM_CSS, encoding="utf-8")

    print(f"Prepared {len(chapter_files)} chapters in {SRC_DIR.relative_to(ROOT)}/")

    # Run mdbook
    if not shutil.which("mdbook"):
        print(
            """
mdBook (`mdbook`) not installed.

Install mdBook using one of the options in the official installation guide:
  https://rust-lang.github.io/mdBook/guide/installation.html

Common choices:
  - Download a precompiled mdbook binary for Windows, macOS, or Linux
  - Install Rust and run: cargo install mdbook
  - On macOS with Homebrew: brew install mdbook

After installing, make sure the mdbook executable is on your PATH.
""".strip()
        )
        sys.exit(1)

    if serve:
        cmd = ["mdbook", "serve", str(MDBOOK_DIR)]
        if open_browser:
            cmd.append("--open")
        print("Starting dev server (Ctrl+C to stop)...")
        subprocess.run(cmd)
    else:
        subprocess.run(["mdbook", "build", str(MDBOOK_DIR)], check=True)
        out = MDBOOK_DIR / "book"
        print(f"Built static site -> {out.relative_to(ROOT)}/")
        if open_browser:
            import webbrowser

            webbrowser.open(str(out / "index.html"))


# ---------------------------------------------------------------------------
# PDF build
# ---------------------------------------------------------------------------

FIGURE_PDF_FILTER = """\
-- Rewrite figures/<name>.svg image paths to the pre-converted PDFs.
function Image(img)
  local new = img.src:gsub("^figures/(.*)%.svg$", "build/figures-pdf/%1.pdf")
  img.src = new
  return img
end
"""

# Map fenced-div callouts to the BOAcallout tcolorbox environment defined in
# chapters/metadata.yaml. Labels must match CALLOUT_LABELS (HTML path).
CALLOUT_PDF_FILTER = """\
local labels = {
  gotcha = "Gotcha", note = "Note", warning = "Warning", tip = "Tip",
  tryit = "Try it", check = "Check yourself", setup = "Setup",
  spec = "The spec",
}

local function tex_escape(s)
  s = s:gsub("\\\\", "\\\\textbackslash{}")
  s = s:gsub("([%%{}$&#_])", "\\\\%1")
  s = s:gsub("%^", "\\\\^{}")
  s = s:gsub("~", "\\\\~{}")
  -- backtick spans become \\texttt
  s = s:gsub("`([^`]+)`", "\\\\texttt{%1}")
  return s
end

function Div(el)
  local label = labels[el.classes[1]]
  if not label then return nil end
  local title = el.attributes["title"]
  local head = label
  if title and title ~= "" then
    head = label .. " --- " .. title
  end
  local blocks = pandoc.List()
  blocks:insert(pandoc.RawBlock("latex",
    "\\\\begin{BOAcallout}{" .. tex_escape(head) .. "}"))
  blocks:extend(el.content)
  blocks:insert(pandoc.RawBlock("latex", "\\\\end{BOAcallout}"))
  return blocks
end
"""

# Inline code never hyphenates (mono fonts carry no hyphen points), so a long
# identifier would overflow the measure. This filter supplies break
# opportunities at the points where an identifier can legally split --
# after ., _, /, :, -, =, ",", and "(" -- as \allowbreak (no hyphen is ever
# inserted). Promised by the colophon (Z4). Short spans are left alone.
INLINE_CODE_PDF_FILTER = """\
local MIN_LEN = 15

function Code(el)
  local text = el.text
  local out = {}
  for i = 1, #text do
    local c = text:sub(i, i)
    local esc = c
    if c == "\\\\" then esc = "\\\\textbackslash{}"
    elseif c:match("[%%{}$&#_]") then esc = "\\\\" .. c
    elseif c == "^" then esc = "\\\\^{}"
    elseif c == "~" then esc = "\\\\~{}"
    end
    table.insert(out, esc)
    if #text >= MIN_LEN and i < #text and c:match("[%._/:%-=,(]") then
      table.insert(out, "\\\\allowbreak{}")
    end
  end
  return pandoc.RawInline("latex", "\\\\texttt{" .. table.concat(out) .. "}")
end
"""


def _convert_figures_for_pdf() -> Path | None:
    """Pre-convert figures/*.svg to PDF (xelatex cannot include SVG directly).

    Uses cairosvg (uv dependency group "pdf"). Returns the Lua filter path,
    or None if there are no figures.
    """
    if not FIGURES_DIR.exists():
        return None
    out_dir = ROOT / "build" / "figures-pdf"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        import cairosvg  # type: ignore[import-untyped]
    except ImportError:
        print(
            "Error: cairosvg not available. Run via: uv run --group pdf python3 build.py pdf",
            file=sys.stderr,
        )
        sys.exit(1)
    converted = 0
    for svg in sorted(FIGURES_DIR.glob("*.svg")):
        pdf = out_dir / (svg.stem + ".pdf")
        if pdf.exists() and pdf.stat().st_mtime >= svg.stat().st_mtime:
            continue
        cairosvg.svg2pdf(url=str(svg), write_to=str(pdf))
        converted += 1
    if converted:
        print(f"Converted {converted} figures to PDF")
    filter_path = ROOT / "build" / "figures-pdf-filter.lua"
    filter_path.write_text(FIGURE_PDF_FILTER, encoding="utf-8")
    return filter_path


def build_pdf() -> None:
    """Build PDF via pandoc + xelatex from chapter sources."""
    if not shutil.which("pandoc"):
        print("Error: pandoc not installed. Install with: brew install pandoc", file=sys.stderr)
        sys.exit(1)

    metadata = CHAPTERS_DIR / "metadata.yaml"
    if not metadata.exists():
        print(f"Error: {metadata} not found.", file=sys.stderr)
        sys.exit(1)

    chapter_files = get_chapter_files()
    if not chapter_files:
        print("Error: no chapter files found in chapters/", file=sys.stderr)
        sys.exit(1)

    lua_filter = _convert_figures_for_pdf()
    callout_filter = ROOT / "build" / "callouts-pdf-filter.lua"
    callout_filter.parent.mkdir(exist_ok=True)
    callout_filter.write_text(CALLOUT_PDF_FILTER, encoding="utf-8")
    inline_code_filter = ROOT / "build" / "inline-code-pdf-filter.lua"
    inline_code_filter.write_text(INLINE_CODE_PDF_FILTER, encoding="utf-8")

    output = ROOT / "Building-on-Algorand.pdf"
    cmd = [
        "pandoc",
        str(metadata),
        *[str(f) for f in chapter_files],
        "-o",
        str(output),
        "--pdf-engine=xelatex",
        "--highlight-style=tango",
        "--top-level-division=chapter",
        "--toc",
        "--toc-depth=2",
        "-N",
    ]
    cmd.insert(-8, f"--lua-filter={callout_filter}")
    cmd.insert(-8, f"--lua-filter={inline_code_filter}")
    if lua_filter is not None:
        cmd.insert(-8, f"--lua-filter={lua_filter}")

    print(f"Building PDF from {len(chapter_files)} chapters...")
    subprocess.run(cmd, check=True)
    print(f"Built -> {output.name}")


# ---------------------------------------------------------------------------
# Concat: reconstruct the monolithic markdown
# ---------------------------------------------------------------------------

def build_concat() -> None:
    """Reconstruct Building-on-Algorand.md from chapter sources."""
    metadata = CHAPTERS_DIR / "metadata.yaml"
    if not metadata.exists():
        print(f"Error: {metadata} not found.", file=sys.stderr)
        sys.exit(1)

    chapter_files = get_chapter_files()
    if not chapter_files:
        print("Error: no chapter files found in chapters/", file=sys.stderr)
        sys.exit(1)

    parts = [metadata.read_text(encoding="utf-8").rstrip()]
    for path in chapter_files:
        parts.append(path.read_text(encoding="utf-8").rstrip())

    output = ROOT / "Building-on-Algorand.md"
    output.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print(f"Concatenated {len(chapter_files)} chapters -> {output.name}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build Building on Algorand from chapter sources.",
    )
    sub = parser.add_subparsers(dest="command")

    mb = sub.add_parser("mdbook", help="Build mdbook HTML site")
    mb.add_argument("--serve", action="store_true", help="Start dev server with live reload")
    mb.add_argument("--open", action="store_true", help="Open in browser after build")

    sub.add_parser("pdf", help="Build PDF via pandoc + xelatex")
    sub.add_parser("all", help="Build both mdbook and PDF")
    sub.add_parser("concat", help="Reconstruct single Building-on-Algorand.md")

    args = parser.parse_args()

    if args.command == "mdbook":
        build_mdbook(serve=args.serve, open_browser=args.open)
    elif args.command == "pdf":
        build_pdf()
    elif args.command == "all":
        build_mdbook()
        build_pdf()
    elif args.command == "concat":
        build_concat()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
