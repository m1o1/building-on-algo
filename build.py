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
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).parent
CHAPTERS_DIR = ROOT / "chapters"
CHANGES_DIR = ROOT / "changes"
MDBOOK_DIR = ROOT / "mdbook"
SRC_DIR = MDBOOK_DIR / "src"
BUILD_DIR = ROOT / "build"
MANIFEST = CHAPTERS_DIR / "book.yaml"


# ---------------------------------------------------------------------------
# Book structure metadata — read from chapters/book.yaml
# ---------------------------------------------------------------------------
#
# Ordering used to be lexical (a filename-prefix sort of F* < 0* < A* < Z*)
# with part breaks and front/back matter hard-coded in three module-level
# constants. That made chapter position a property of the filename, so
# reordering a chapter meant renaming a file and every reference to it.
#
# Ordering is now declared in chapters/book.yaml. Nothing in this module
# infers structure from a filename any more.


@dataclass
class Entry:
    """One file in the book, in reading order."""

    path: Path
    slug: str
    role: str  # front | chapter | appendix | back
    kind: str = ""  # concept | project | capstone (chapters only)
    code: str = ""  # project directory, if any
    part_id: str = ""
    part_title: str = ""
    # SUMMARY.md part header to emit before this entry, or "" for none.
    mdbook_part_header: str = ""
    # Display number, assigned by number_entries(). 0 = unnumbered.
    number: int = 0


@dataclass
class Book:
    entries: list[Entry] = field(default_factory=list)
    examples_root: Path | None = None
    examples_manifest: Path | None = None

    @property
    def files(self) -> list[Path]:
        return [e.path for e in self.entries]

    def by_slug(self, slug: str) -> Entry | None:
        for e in self.entries:
            if e.slug == slug:
                return e
        return None


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ImportError:  # pragma: no cover - environment problem, not logic
        print(
            "Error: PyYAML is required to read chapters/book.yaml.\n"
            "Install it with:  pip install pyyaml",
            file=sys.stderr,
        )
        sys.exit(1)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _entry_from(raw: dict, role: str, **extra) -> Entry:
    name = raw["file"]
    path = CHAPTERS_DIR / name
    if not path.exists():
        raise SystemExit(f"book.yaml references a missing file: chapters/{name}")
    if "slug" not in raw:
        raise SystemExit(f"book.yaml entry for {name} has no slug")
    return Entry(
        path=path,
        slug=raw["slug"],
        role=role,
        kind=raw.get("kind", ""),
        code=raw.get("code", ""),
        **extra,
    )


def load_book(manifest: Path = MANIFEST) -> Book:
    """Parse chapters/book.yaml into an ordered list of entries."""
    if not manifest.exists():
        raise SystemExit(f"Error: {manifest} not found.")
    doc = _load_yaml(manifest)
    book = Book()

    for raw in doc.get("front", []):
        book.entries.append(_entry_from(raw, "front"))

    for part in doc.get("parts", []):
        part_id = part.get("id", "")
        title = part.get("title", "")
        # A part header is emitted before the part's FIRST chapter only.
        header = ""
        if part.get("mdbook_break", True):
            header = "# " + (part.get("mdbook_title") or title)
        for i, raw in enumerate(part.get("chapters", [])):
            book.entries.append(
                _entry_from(
                    raw,
                    "chapter",
                    part_id=part_id,
                    part_title=title,
                    mdbook_part_header=header if i == 0 else "",
                )
            )

    app = doc.get("appendices") or {}
    app_header = "# " + (app.get("mdbook_title") or app.get("part_title", "Appendices"))
    for i, raw in enumerate(app.get("files", [])):
        book.entries.append(
            _entry_from(
                raw,
                "appendix",
                part_title=app.get("part_title", "Appendices"),
                mdbook_part_header=app_header if i == 0 else "",
            )
        )

    for raw in doc.get("back", []):
        book.entries.append(_entry_from(raw, "back"))

    ex = doc.get("examples") or {}
    if ex.get("root"):
        book.examples_root = ROOT / ex["root"]
    if ex.get("manifest"):
        book.examples_manifest = ROOT / ex["manifest"]

    number_entries(book)
    _check_orphans(book)
    return book


def number_entries(book: Book) -> None:
    """Assign display numbers: chapters 1..N, appendices A..Z."""
    n = 0
    a = 0
    for e in book.entries:
        if e.role == "chapter":
            n += 1
            e.number = n
        elif e.role == "appendix":
            a += 1
            e.number = a


def _check_orphans(book: Book) -> None:
    """Every .md in chapters/ must be claimed by the manifest."""
    declared = {e.path.name for e in book.entries}
    on_disk = {p.name for p in CHAPTERS_DIR.glob("*.md")}
    orphans = sorted(on_disk - declared)
    if orphans:
        raise SystemExit(
            "Files in chapters/ that book.yaml does not list "
            "(add them or delete them): " + ", ".join(orphans)
        )


# ---------------------------------------------------------------------------
# Resolution pass: chapters/ → build/resolved/
# ---------------------------------------------------------------------------
#
# Neither renderer reads chapters/ directly. Both read build/resolved/, which
# is chapters/ after every mechanical substitution has been applied. Today that
# means example transclusion; Phase 1 adds cross-reference number resolution to
# the same pass. Keeping one resolution stage means the PDF and the HTML can
# never disagree about what the source says.
#
# Transclusion directive, on a line by itself:
#
#     {{include-ex:global-counter}}
#
# expands to a tagged ```python fence holding the current contents of the file
# examples/index.yaml maps that slug to. This is what makes the Completeness
# Contract mechanical rather than aspirational: the book cannot print code that
# differs from the code CI compiles, because the book does not store code.
#
# Note the deliberate distinction from the inline reference form {{ex:slug}},
# which Phase 1 resolves to a display number like "Example 3-4". `ex:` cites an
# example; `include-ex:` prints one.

RESOLVED_DIR = BUILD_DIR / "resolved"
INCLUDE_EX_RE = re.compile(r"^[ \t]*\{\{include-ex:([a-z0-9][a-z0-9-]*)\}\}[ \t]*$", re.MULTILINE)
EXAMPLE_LANG = {".py": "python", ".teal": "teal", ".ts": "typescript", ".json": "json"}


def load_example_index(manifest: Path | None) -> dict[str, dict]:
    """Map example slug → entry from examples/index.yaml."""
    if manifest is None or not manifest.exists():
        return {}
    doc = _load_yaml(manifest) or {}
    return {e["slug"]: e for e in doc.get("examples", []) if e.get("slug")}


def transclude_examples(text: str, index: dict[str, dict], examples_root: Path, where: str) -> str:
    """Replace {{include-ex:slug}} directives with the example's source."""

    def _expand(match: re.Match) -> str:
        slug = match.group(1)
        entry = index.get(slug)
        if entry is None:
            raise SystemExit(
                f"{where}: {{{{include-ex:{slug}}}}} names an example that is not "
                f"in examples/index.yaml"
            )
        source = examples_root / entry["path"]
        if not source.exists():
            raise SystemExit(
                f"{where}: example {slug!r} points at a missing file: "
                f"examples/{entry['path']}"
            )
        lang = EXAMPLE_LANG.get(source.suffix, "text")
        body = source.read_text(encoding="utf-8").strip("\n")
        return f"```{lang}\n{body}\n```"

    return INCLUDE_EX_RE.sub(_expand, text)


def resolve_book(book: Book) -> Book:
    """Write build/resolved/ and return a Book whose entries point at it."""
    if RESOLVED_DIR.exists():
        shutil.rmtree(RESOLVED_DIR)
    RESOLVED_DIR.mkdir(parents=True, exist_ok=True)

    index = load_example_index(book.examples_manifest)
    examples_root = book.examples_root or (ROOT / "examples")

    resolved = Book(
        examples_root=book.examples_root,
        examples_manifest=book.examples_manifest,
    )
    for entry in book.entries:
        text = entry.path.read_text(encoding="utf-8")
        text = transclude_examples(text, index, examples_root, f"chapters/{entry.path.name}")
        out = RESOLVED_DIR / entry.path.name
        out.write_text(text, encoding="utf-8")
        resolved.entries.append(replace(entry, path=out))
    return resolved


# ---------------------------------------------------------------------------
# Chapter file discovery
# ---------------------------------------------------------------------------

def get_chapter_files() -> list[Path]:
    """Return chapter .md files from chapters/ in book order."""
    return load_book().files


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
    book = resolve_book(load_book())
    chapter_files = book.files
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

    seen_back = False
    for entry in book.entries:
        path = entry.path
        text = path.read_text(encoding="utf-8")
        heading = extract_heading(text)
        if heading is None:
            continue

        title = clean_title(heading)
        cleaned = clean_for_mdbook(text)

        # Write cleaned chapter to mdbook/src/
        (SRC_DIR / path.name).write_text(cleaned, encoding="utf-8")

        # Part break before this chapter?
        if entry.mdbook_part_header:
            summary_lines.append(f"\n{entry.mdbook_part_header}\n")

        # Separator before back matter
        if entry.role == "back" and not seen_back:
            summary_lines.append("\n---\n")
            seen_back = True

        # Convert pandoc em-dashes for display
        display_title = title.replace(" --- ", " — ")

        # SUMMARY.md entry: front/back matter get no bullet, chapters get bullet
        if entry.role in ("front", "back"):
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

APPENDIX_MARKER = "```{=latex}\n\\appendix\n```\n"


def _pdf_source_list(book: Book) -> list[Path]:
    """Book files with a raw-LaTeX \\appendix marker before the first appendix."""
    sources: list[Path] = []
    emitted = False
    for entry in book.entries:
        if entry.role == "appendix" and not emitted:
            BUILD_DIR.mkdir(parents=True, exist_ok=True)
            marker = BUILD_DIR / "_appendix.md"
            marker.write_text(APPENDIX_MARKER, encoding="utf-8")
            sources.append(marker)
            emitted = True
        sources.append(entry.path)
    return sources


def build_pdf() -> None:
    """Build PDF via pandoc + xelatex from chapter sources."""
    if not shutil.which("pandoc"):
        print("Error: pandoc not installed. Install with: brew install pandoc", file=sys.stderr)
        sys.exit(1)

    metadata = CHAPTERS_DIR / "metadata.yaml"
    if not metadata.exists():
        print(f"Error: {metadata} not found.", file=sys.stderr)
        sys.exit(1)

    book = resolve_book(load_book())
    chapter_files = book.files
    if not chapter_files:
        print("Error: no chapter files found in chapters/", file=sys.stderr)
        sys.exit(1)

    # Without \appendix, pandoc's -N numbers the first appendix as though it
    # were the next chapter of the book — the Cookbook has been presented to
    # readers as "Chapter 11". Emitting the directive ahead of the first
    # appendix restarts the counter at A.
    sources = _pdf_source_list(book)

    output = ROOT / "Building-on-Algorand.pdf"
    cmd = [
        "pandoc",
        str(metadata),
        *[str(f) for f in sources],
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

    chapter_files = resolve_book(load_book()).files
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
