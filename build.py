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
    brew install mdbook     # for mdbook target
    brew install pandoc     # for pdf target (also needs xelatex)
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

# ---------------------------------------------------------------------------
# Book structure metadata
# ---------------------------------------------------------------------------

# Part breaks: chapter filename → mdBook SUMMARY.md part header.
# Inserted before the named chapter in the table of contents.
PART_BREAKS: dict[str, str] = {
    "01-the-algorand-mental-model.md": "# Part I: Foundations",
    "05-a-constant-product-amm.md": "# Part II: Automated Market Making",
    "08-delegated-limit-order-book.md": "# Part III: Limit Order Book",
    "09-private-governance-voting.md": "# Part IV: Private Governance",
    "A1-cookbook.md": "# Appendices",
}

# Front-matter chapters appear as prefix entries (no bullet) in SUMMARY.md.
FRONT_MATTER = {"F1-legal-notice.md", "F2-preface.md"}

# Back-matter chapters appear as suffix entries (no bullet) after a separator.
BACK_MATTER = {"Z1-whats-next.md", "Z2-glossary.md", "Z3-bibliography.md"}


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
    r"""Adjust \_ escapes so math renders correctly in MathJax via pulldown-cmark.

    Inside \text{...}: strip the backslash (MathJax text mode treats _ as literal,
    and \_ would render with a visible backslash).
    Outside \text{...}: double the backslash so pulldown-cmark produces \_ in HTML,
    which MathJax interprets as a literal underscore in math mode.
    """
    # Step 1: Inside \text{...}, just remove \_ → _ (text mode _ is literal)
    content = re.sub(
        r"\\text\{[^}]*\}",
        lambda m: m.group(0).replace("\\_", "_"),
        content,
    )
    # Step 2: Remaining \_ (math mode) → \\_ so pulldown-cmark yields \_
    content = content.replace("\\_", "\\\\_")
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


def clean_for_mdbook(text: str) -> str:
    """Transform pandoc-flavored markdown for mdBook consumption.

    - Strips \\newpage and \\part{...} directives
    - Strips pandoc attributes from sub-headings
    - Converts --- to em-dash
    - Converts LaTeX math delimiters for MathJax
    - Drops content before the first # heading (part intros)
    - Strips {-} from the chapter heading
    """
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

    for path in chapter_files:
        text = path.read_text(encoding="utf-8")
        heading = extract_heading(text)
        if heading is None:
            continue

        title = clean_title(heading)
        cleaned = clean_for_mdbook(text)

        # Write cleaned chapter to mdbook/src/
        (SRC_DIR / path.name).write_text(cleaned, encoding="utf-8")

        # Part break before this chapter?
        if path.name in PART_BREAKS:
            summary_lines.append(f"\n{PART_BREAKS[path.name]}\n")

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
        print("\nmdbook not installed. Install with: brew install mdbook")
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

    output = ROOT / "Building-on-Algorand.pdf"
    cmd = [
        "pandoc",
        str(metadata),
        *[str(f) for f in chapter_files],
        "-o",
        str(output),
        "--pdf-engine=xelatex",
        "--syntax-highlighting=tango",
        "--top-level-division=chapter",
        "--toc",
        "--toc-depth=2",
        "-N",
    ]

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
