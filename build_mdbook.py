#!/usr/bin/env python3
"""
Generate an mdBook from Building-on-Algorand.md for static web hosting.

Usage:
    python build_mdbook.py            # Build static HTML to mdbook/book/
    python build_mdbook.py --serve    # Build and start local dev server with live reload
    python build_mdbook.py --open     # Build and open in browser

Output:
    mdbook/book/    Static HTML site, ready to deploy to any static hosting.

Prerequisites:
    brew install mdbook     # macOS
    cargo install mdbook    # via Rust toolchain
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SOURCE = ROOT / "Building-on-Algorand.md"
CHANGES_DIR = ROOT / "changes"
MDBOOK_DIR = ROOT / "mdbook"
SRC_DIR = MDBOOK_DIR / "src"

# ---------------------------------------------------------------------------
# Part structure — optional part dividers inserted before certain chapters
# in the mdBook SUMMARY.md table of contents.
# ---------------------------------------------------------------------------
PART_BREAKS = {
    "algorand-smart-contract-cookbook": "# Appendices",
}

# Chapters that appear as suffix entries (no bullet) in SUMMARY.md.
SUFFIX_CHAPTERS = {"whats-next", "glossary", "bibliography", "changelog"}


# ---------------------------------------------------------------------------
# Markdown parsing
# ---------------------------------------------------------------------------

def strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter delimited by --- at the start of the file."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip("\n")


def split_chapters(text: str) -> list[tuple[str, str]]:
    """
    Split markdown at top-level # headings, respecting fenced code blocks.
    Returns [(heading_line, body_text), ...].
    Content before the first heading is discarded (frontmatter/preamble).
    """
    lines = text.split("\n")
    chapters: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_body: list[str] = []
    in_code = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code

        if not in_code and re.match(r"^# ", line):
            if current_heading is not None:
                chapters.append((current_heading, "\n".join(current_body)))
            current_heading = line
            current_body = []
        elif current_heading is not None:
            current_body.append(line)

    if current_heading is not None:
        chapters.append((current_heading, "\n".join(current_body)))

    return chapters


# ---------------------------------------------------------------------------
# Pandoc → mdBook cleanup
# ---------------------------------------------------------------------------

def clean_title(heading: str) -> str:
    """Extract clean title text from a heading line (strip # and {attrs})."""
    t = re.sub(r"^#+\s*", "", heading)
    t = re.sub(r"\s*\{[^}]*\}\s*$", "", t)
    return t.strip()


def slugify(title: str) -> str:
    s = title.lower()
    s = s.replace("'", "")  # don't → dont, what's → whats
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def _is_math_content(content: str) -> bool:
    """Heuristic: does text between $...$ look like LaTeX math, not currency?"""
    s = content.strip()
    if not s:
        return False
    # LaTeX commands like \frac, \times, \Delta
    if "\\" in s:
        return True
    # Subscripts / superscripts
    if "_" in s or "^" in s:
        return True
    # LaTeX grouping braces
    if "{" in s or "}" in s:
        return True
    # Single letter variable ($x$, $k$, $r$)
    if len(s) == 1 and s.isalpha():
        return True
    # Short expression with math operators (e.g. 997/1000)
    if len(s) <= 30 and re.match(r"^[\w\s+\-*/=<>.,()]+$", s):
        if any(c in s for c in "+-*/=<>"):
            return True
    return False


def _protect_math_escapes(content: str) -> str:
    r"""Double backslashes before _ in math content so they survive markdown.

    Pandoc uses \_ for a literal underscore.  pulldown-cmark (mdBook's markdown
    parser) treats \_ as an escape and swallows the backslash, leaving bare _
    which MathJax then interprets as a subscript operator.

    Writing \\_ in the markdown file makes pulldown-cmark produce \_ in HTML,
    which MathJax correctly renders as a literal underscore.
    """
    return content.replace("\\_", "\\\\_")


def _convert_math_delimiters(text: str) -> str:
    r"""Convert LaTeX math delimiters for MathJax in mdBook.

    $$...$$ → \\[...\\]   (display math)
    $...$   → \\(...\\)   (inline math, only when content looks like LaTeX)

    Currency $signs (like $100) are left unchanged.
    Code blocks are not touched.
    """
    lines = text.split("\n")
    out: list[str] = []
    in_code = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
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
            return m.group(0)  # leave unchanged (currency, etc.)

        line = re.sub(r"(?<![\$\\])\$([^$\n]+?)\$(?!\$)", _replace_inline, line)
        out.append(line)

    return "\n".join(out)


def clean_body(text: str) -> str:
    """Strip pandoc-specific constructs from chapter body text."""
    lines = text.split("\n")
    out: list[str] = []
    in_code = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            in_code = not in_code

        # Drop LaTeX commands: \newpage, \part{...}
        if stripped == "\\newpage" or re.match(r"^\\part\{.*\}$", stripped):
            continue

        if not in_code:
            # Strip pandoc attributes from sub-headings: ## Title {#id} → ## Title
            line = re.sub(r"^(#{2,6}\s+.+?)\s*\{[^}]*\}\s*$", r"\1", line)
            # Pandoc em-dashes → unicode
            line = line.replace(" --- ", " — ")

        out.append(line)

    result = "\n".join(out)
    # Convert LaTeX math delimiters for MathJax
    result = _convert_math_delimiters(result)
    return result


# ---------------------------------------------------------------------------
# Filename assignment
# ---------------------------------------------------------------------------

def make_filename(slug: str, is_unnumbered: bool, chapter_counter: list[int]) -> str:
    """Assign a filename. Numbered chapters get chNN- prefix."""
    if slug == "preface" or slug in SUFFIX_CHAPTERS or is_unnumbered:
        return f"{slug}.md"

    if slug == "algorand-smart-contract-cookbook":
        return "cookbook.md"
    if slug == "consolidated-gotchas-cheat-sheet":
        return "gotchas.md"

    chapter_counter[0] += 1
    n = chapter_counter[0]
    return f"ch{n:02d}-{slug}.md"


# ---------------------------------------------------------------------------
# SUMMARY.md generation
# ---------------------------------------------------------------------------

def build_summary(
    chapters: list[tuple[str, str, str, bool]],
) -> str:
    """
    Build SUMMARY.md content.
    chapters: [(display_title, filename, slug, is_unnumbered), ...]
    """
    lines = ["# Summary\n"]

    for title, filename, slug, _unnum in chapters:
        # Insert part break if this chapter starts a new part
        if slug in PART_BREAKS:
            lines.append(f"\n{PART_BREAKS[slug]}\n")

        # Separator before suffix chapters
        if slug == "whats-next":
            lines.append("\n---\n")

        # Prefix entries (preface) and suffix entries have no bullet
        if slug == "preface" or slug in SUFFIX_CHAPTERS:
            lines.append(f"[{title}](./{filename})")
        else:
            lines.append(f"- [{title}](./{filename})")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# book.toml
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


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Changelog from changes/ directory
# ---------------------------------------------------------------------------

def build_changelog() -> str | None:
    """Read all markdown files from changes/ and combine into a single changelog page.

    Files are sorted in reverse natural order (newest revision first).
    Each file's content is included as-is, separated by a horizontal rule.
    Returns None if the changes/ directory doesn't exist or is empty.
    """
    if not CHANGES_DIR.is_dir():
        return None

    change_files = sorted(CHANGES_DIR.glob("*.md"), reverse=True)
    if not change_files:
        return None

    sections: list[str] = []
    for path in change_files:
        content = path.read_text(encoding="utf-8").strip()
        if content:
            sections.append(content)

    if not sections:
        return None

    header = "# Changelog\n\nA record of revisions, fixes, and improvements made to this book.\n"
    return header + "\n\n---\n\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Main build logic
# ---------------------------------------------------------------------------

def generate(source: Path) -> Path:
    """Read source markdown, produce mdBook directory structure. Returns MDBOOK_DIR."""
    text = source.read_text(encoding="utf-8")
    text = strip_frontmatter(text)

    raw_chapters = split_chapters(text)
    if not raw_chapters:
        print(f"Error: no chapters found in {source}", file=sys.stderr)
        sys.exit(1)

    # Prepare output dirs
    if SRC_DIR.exists():
        shutil.rmtree(SRC_DIR)
    SRC_DIR.mkdir(parents=True, exist_ok=True)

    theme_dir = MDBOOK_DIR / "theme"
    theme_dir.mkdir(parents=True, exist_ok=True)

    chapter_counter = [0]  # mutable counter shared across calls
    chapter_info: list[tuple[str, str, str, bool]] = []

    for heading, body in raw_chapters:
        title = clean_title(heading)
        slug = slugify(title)
        is_unnumbered = "{-}" in heading

        filename = make_filename(slug, is_unnumbered, chapter_counter)
        chapter_content = f"# {title}\n{clean_body(body)}"

        (SRC_DIR / filename).write_text(chapter_content, encoding="utf-8")
        chapter_info.append((title, filename, slug, is_unnumbered))

    # Changelog from changes/ directory
    changelog_content = build_changelog()
    if changelog_content:
        changelog_file = "changelog.md"
        (SRC_DIR / changelog_file).write_text(changelog_content, encoding="utf-8")
        chapter_info.append(("Changelog", changelog_file, "changelog", True))

    # SUMMARY.md
    summary = build_summary(chapter_info)
    (SRC_DIR / "SUMMARY.md").write_text(summary, encoding="utf-8")

    # book.toml
    (MDBOOK_DIR / "book.toml").write_text(BOOK_TOML, encoding="utf-8")

    # Custom CSS
    (theme_dir / "custom.css").write_text(CUSTOM_CSS, encoding="utf-8")

    n = len(chapter_info)
    print(f"Split {source.name} into {n} chapters in {SRC_DIR.relative_to(ROOT)}/")
    return MDBOOK_DIR


def run_mdbook(book_dir: Path, serve: bool = False, open_browser: bool = False) -> None:
    """Run mdbook build (or serve)."""
    if not shutil.which("mdbook"):
        print()
        print("mdbook is not installed. Install with:")
        print("  brew install mdbook            # macOS (Homebrew)")
        print("  cargo install mdbook           # Rust toolchain")
        print("  # Or download from https://github.com/rust-lang/mdBook/releases")
        print()
        print(f"Chapter files are ready in {SRC_DIR.relative_to(ROOT)}/.")
        print("Run 'mdbook build mdbook/' after installing.")
        sys.exit(1)

    if serve:
        cmd = ["mdbook", "serve", str(book_dir)]
        if open_browser:
            cmd.append("--open")
        print(f"Starting dev server (Ctrl+C to stop)...")
        subprocess.run(cmd)
    else:
        subprocess.run(["mdbook", "build", str(book_dir)], check=True)
        out = book_dir / "book"
        print(f"Built static site → {out.relative_to(ROOT)}/")
        print(f"Open {out / 'index.html'} in a browser, or deploy the folder.")
        if open_browser:
            import webbrowser
            webbrowser.open(str(out / "index.html"))


def main() -> None:
    args = set(sys.argv[1:])

    if {"-h", "--help"} & args:
        print(__doc__.strip())
        sys.exit(0)

    if not SOURCE.exists():
        print(f"Error: {SOURCE} not found.", file=sys.stderr)
        sys.exit(1)

    book_dir = generate(SOURCE)

    serve = "--serve" in args
    open_browser = "--open" in args
    run_mdbook(book_dir, serve=serve, open_browser=open_browser)


if __name__ == "__main__":
    main()
