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
    python build.py figures           # Re-render figures/src/ (outputs are committed)

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
import hashlib
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).parent
CHAPTERS_DIR = ROOT / "chapters"
SCRIPTS_DIR = ROOT / "scripts"
FIGURES_DIR = ROOT / "figures"
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
    figures_manifest: Path | None = None

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
        # A part header is emitted before the part's FIRST chapter only, and
        # it uses the same `title` the PDF's \part{} directive typesets. Phase 0
        # honoured mdbook_title/mdbook_break overrides here so the migration
        # could be proven byte-for-byte; Phase 1 retired them.
        header = "# " + title
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
    app_header = "# " + app.get("part_title", "Appendices")
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

    figs = doc.get("figures") or {}
    if figs.get("manifest"):
        book.figures_manifest = ROOT / figs["manifest"]

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

# Figures work the same way, and for the same reason: a chapter names a figure
# and never a file path or an image tag, so one directive serves two renderers
# that need different files (SVG for the HTML, PDF for LaTeX) at different
# paths. The placement directive is deliberately distinct from the citation
# {{fig:slug}} exactly as include-ex: is from ex:.
INCLUDE_FIG_RE = re.compile(
    r"^[ \t]*\{\{include-fig:([a-z0-9][a-z0-9-]*)\}\}[ \t]*$", re.MULTILINE
)


def figure_caption(display: str, title: str) -> str:
    """Compose a figure's on-page caption: the number, then the caption text.

    Module-level and separate from its one caller so that `scripts/validate.py`
    check 21 can test the real composition rather than a copy of it. A copy is
    what let the original defect stand: the caption text was being altered on
    the way to the page and every check was looking at whether the figure
    existed instead.

    Not `.rstrip(". ")`. That takes a SET of characters, so it deleted the
    caption's own terminal period from all 21 entries in figures/index.yaml,
    every one of which is written as a sentence. The empty title it was
    reaching for is handled as the special case it actually is.
    """
    title = str(title).strip()
    return f"{display}. {title}" if title else str(display)


def load_figure_index(manifest: Path | None) -> dict[str, dict]:
    """Map figure slug → entry from figures/index.yaml."""
    if manifest is None or not manifest.exists():
        return {}
    doc = _load_yaml(manifest) or {}
    return {e["slug"]: e for e in doc.get("figures", []) if e.get("slug")}


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


# ---------------------------------------------------------------------------
# Cross-references: dual-identity numbering
# ---------------------------------------------------------------------------
#
# Every numbered element in the book carries two identities. The slug is
# permanent, written by the author, and never renumbered. The display number is
# computed at build time and never written down anywhere in the source.
#
# An author declares a caption:
#
#     Table: Storage options compared {#tbl:storage-options}
#
# and cites it from anywhere in the book:
#
#     ... as {{tbl:storage-options}} shows ...
#
# Pass 1 walks chapters/ in book order and assigns display numbers. Pass 2
# substitutes. Inserting a table in chapter 4 renumbers everything after it in
# chapter 4, and every reference across the whole book follows, because no
# reference ever contained a number to begin with.
#
# The full map is written to build/xref.json — not because the build needs it,
# but because "which chapter is Figure 9-3 in?" should be answerable without
# grepping.

CAPTION_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<kind>Table|Figure|Example):[ \t]+"
    r"(?P<title>.*?)[ \t]*\{#(?P<ns>tbl|fig|ex):(?P<slug>[a-z0-9][a-z0-9-]*)\}[ \t]*$",
    re.MULTILINE,
)
REF_RE = re.compile(r"\{\{(?P<ns>tbl|fig|ex|ch|chn|part):(?P<slug>[a-z0-9][a-z0-9-]*)\}\}")
# {{figure:...}} is the likeliest typo for {{fig:...}} and silently survives a
# naive resolver as ordinary prose. Name it, and fail on it.
BANNED_REF_RE = re.compile(r"\{\{(figure|table|example|chapter|sec|section):[^}]*\}\}")

NS_LABEL = {"tbl": "Table", "fig": "Figure", "ex": "Example"}


# Front matter has no chapter number to hang a caption on, but the Preface does
# carry a figure — the book's dependency graph — and O'Reilly's own convention
# for that case is a P prefix: Figure P-1. Only the Preface gets one. A figure
# anywhere else in front or back matter is an error, because two files sharing
# the P sequence would silently mint two Figure P-1s.
FRONT_MATTER_LABEL = {"preface": "P"}


def _chapter_label(entry: Entry) -> str:
    """The number a table or figure in this file is prefixed with: 4, A, or P."""
    if entry.role == "appendix":
        return chr(ord("A") + entry.number - 1)
    if entry.role == "chapter":
        return str(entry.number)
    return FRONT_MATTER_LABEL.get(entry.slug, "")


def _anchors_in(text: str, figures: dict[str, dict], where: str) -> list[tuple]:
    """Every numbered anchor in one file, in the order a reader meets it.

    Two syntaxes mint an anchor. `Table: … {#tbl:slug}` is a caption the author
    writes above the thing being captioned. `{{include-fig:slug}}` is a
    placement directive whose caption lives in figures/index.yaml, because a
    figure's caption belongs with the figure, not with whichever chapter
    happens to place it.
    """
    found = []
    for match in CAPTION_RE.finditer(text):
        found.append(
            (match.start(), match.group("ns"), match.group("slug"), match.group("title").strip())
        )
    for match in INCLUDE_FIG_RE.finditer(text):
        slug = match.group(1)
        entry = figures.get(slug)
        if entry is None:
            raise SystemExit(
                f"{where}: {{{{include-fig:{slug}}}}} names a figure that is not "
                f"in figures/index.yaml"
            )
        found.append((match.start(), "fig", slug, str(entry.get("caption", "")).strip()))
    found.sort(key=lambda item: item[0])
    return found


def collect_xrefs(book: Book, figures: dict[str, dict] | None = None) -> dict:
    """Pass 1: assign a display number to every anchor in the book."""
    figures = figures or {}
    xrefs: dict[str, dict] = {}
    parts: dict[str, str] = {}
    roman = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]

    part_order: list[str] = []
    for entry in book.entries:
        if entry.role == "chapter" and entry.part_id and entry.part_id not in part_order:
            part_order.append(entry.part_id)
    for i, part_id in enumerate(part_order):
        parts[part_id] = roman[i] if i < len(roman) else str(i + 1)

    for entry in book.entries:
        if entry.role == "chapter":
            display = f"Chapter {entry.number}"
        elif entry.role == "appendix":
            display = f"Appendix {_chapter_label(entry)}"
        else:
            display = ""
        xrefs[f"ch:{entry.slug}"] = {
            "kind": "chapter",
            "display": display,
            "file": entry.path.name,
            "title": "",
        }
        # The bare-number form. Prose that pluralises -- "Chapters 5 and 6",
        # "Chapters 2 through 7" -- has already written the noun, so {{ch:}}
        # would render "Chapters Chapter 5 and Chapter 6". {{chn:}} supplies
        # the number alone so those constructions stay idiomatic without any
        # chapter number being written into the source.
        xrefs[f"chn:{entry.slug}"] = {
            "kind": "chapter-number",
            "display": _chapter_label(entry) if entry.role in {"chapter", "appendix"} else "",
            "file": entry.path.name,
            "title": "",
        }

        ordinals = {"tbl": 0, "fig": 0, "ex": 0}
        prefix = _chapter_label(entry)
        text = entry.path.read_text(encoding="utf-8")
        where = f"chapters/{entry.path.name}"
        for _pos, ns, slug, title in _anchors_in(text, figures, where):
            key = f"{ns}:{slug}"
            if key in xrefs:
                raise SystemExit(
                    f"{where}: duplicate anchor {{#{key}}}, "
                    f"already declared in {xrefs[key]['file']}"
                )
            ordinals[ns] += 1
            if not prefix:
                raise SystemExit(
                    f"{where}: {{#{key}}} is in front or back "
                    f"matter, which has no chapter number to hang a caption on"
                )
            xrefs[key] = {
                "kind": NS_LABEL[ns],
                "display": f"{NS_LABEL[ns]} {prefix}-{ordinals[ns]}",
                "number": f"{prefix}-{ordinals[ns]}",
                "file": entry.path.name,
                "chapter": entry.number,
                "title": title,
            }

    for part_id, numeral in parts.items():
        xrefs[f"part:{part_id}"] = {
            "kind": "part",
            "display": f"Part {numeral}",
            "file": "",
            "title": "",
        }
    return xrefs


def _resolve_text(text: str, xrefs: dict, where: str, figures: dict[str, dict] | None = None) -> str:
    """Pass 2: rewrite captions to their display form and substitute references."""
    figures = figures or {}
    banned = BANNED_REF_RE.search(text)
    if banned:
        raise SystemExit(
            f"{where}: {banned.group(0)} is not a cross-reference namespace. "
            f"Use {{{{fig:}}}}, {{{{tbl:}}}}, {{{{ex:}}}}, {{{{ch:}}}}, {{{{chn:}}}} or {{{{part:}}}}."
        )

    def _place_figure(match: re.Match) -> str:
        # One directive becomes one Markdown image paragraph, which is the only
        # form both renderers already understand: pandoc promotes an image alone
        # in a paragraph to a figure and typesets the alt text as the caption,
        # and mdbook passes it through to <img>. The path written here is the
        # SVG at a book-root-relative location; scripts/figures.lua swaps the
        # extension for the LaTeX pass, which needs the PDF instead.
        slug = match.group(1)
        info = xrefs[f"fig:{slug}"]
        caption = figure_caption(info["display"], info["title"])
        alt = caption.replace("[", r"\[").replace("]", r"\]")
        return f"![{alt}](figures/{slug}.svg)"

    text = INCLUDE_FIG_RE.sub(_place_figure, text)

    def _caption(match: re.Match) -> str:
        key = f"{match.group('ns')}:{match.group('slug')}"
        info = xrefs[key]
        indent = match.group("indent")
        if match.group("ns") == "ex":
            # NOT pandoc's ": caption" syntax. That syntax is only a caption
            # when it sits against a table; against a code block, pandoc reads
            # the paragraph ABOVE it as a definition-list term and swallows the
            # caption into the definition. An example caption is therefore a
            # bold lead-in paragraph, which both renderers typeset identically
            # and neither reinterprets. (Phase 4 found this the hard way.)
            return f"{indent}**{info['display']}.** {info['title']}"
        # Pandoc's table-caption syntax. clean_for_mdbook() rewrites it for the
        # HTML renderer, which has no caption concept of its own.
        return f"{indent}: {info['display']}. {info['title']}"

    text = CAPTION_RE.sub(_caption, text)

    def _ref(match: re.Match) -> str:
        key = f"{match.group('ns')}:{match.group('slug')}"
        info = xrefs.get(key)
        if info is None:
            raise SystemExit(f"{where}: unresolved cross-reference {{{{{key}}}}}")
        return info["display"]

    return REF_RE.sub(_ref, text)


def resolve_book(book: Book) -> Book:
    """Write build/resolved/ and return a Book whose entries point at it."""
    if RESOLVED_DIR.exists():
        shutil.rmtree(RESOLVED_DIR)
    RESOLVED_DIR.mkdir(parents=True, exist_ok=True)

    index = load_example_index(book.examples_manifest)
    examples_root = book.examples_root or (ROOT / "examples")
    figures = load_figure_index(book.figures_manifest)
    xrefs = collect_xrefs(book, figures)
    (BUILD_DIR / "xref.json").write_text(
        json.dumps(xrefs, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    resolved = Book(
        examples_root=book.examples_root,
        examples_manifest=book.examples_manifest,
        figures_manifest=book.figures_manifest,
    )
    for entry in book.entries:
        where = f"chapters/{entry.path.name}"
        text = entry.path.read_text(encoding="utf-8")
        text = transclude_examples(text, index, examples_root, where)
        text = _resolve_text(text, xrefs, where, figures)
        out = RESOLVED_DIR / entry.path.name
        out.write_text(text, encoding="utf-8")
        resolved.entries.append(replace(entry, path=out))
    return resolved


# ---------------------------------------------------------------------------
# Gotchas: marked once where they bite, harvested into one appendix
# ---------------------------------------------------------------------------
#
# A gotcha belongs twice in a book and can only be written once. It belongs in
# the chapter, at the exact paragraph where a reader is about to make the
# mistake, because that is where the warning has any chance of landing. And it
# belongs in a single list, because six months later the reader remembers that
# the book warned them about *something* to do with box names and has no idea
# which chapter it was in.
#
# Writing it twice is how the two copies drift. So it is written once, in the
# chapter, as a callout carrying two extra attributes:
#
#     ::: {.gotcha #box-prefix-mbr topic="Box storage" title="A BoxMap key prefix counts toward the box name length"}
#     ...
#     :::
#
# The opening line is one line however long it gets; both renderers and the
# harvester read it line-wise.
#
# and `python3 build.py gotchas` collects every one of them into
# chapters/A3-gotchas.md, grouped by topic, each entry pointing back at the
# chapter it came from. The generated file is committed for the same reason
# figures/out/ is: someone who only wants to build the book should not have to
# run a generation step first. validate.py check 14 fails if it has drifted.
#
# The id is not rendered anywhere. It exists so that a gotcha keeps a stable
# identity when it moves between chapters, and so that check 14 can name the
# duplicate when two of them collide.

# The topic vocabulary is closed, and deliberately short. An open vocabulary
# produces "Boxes", "Box storage" and "Box Storage" as three separate headings
# in the appendix within a month.
GOTCHA_TOPICS = [
    "Global and local state",
    "Box storage",
    "Arithmetic and time",
    "Inner transactions",
    "ASAs",
    "Atomic groups",
    "Authorization",
    "Resource references, MBR, and budget",
    "Cross-contract calls",
    "Pricing math",
    "LogicSigs",
    "Cryptography",
    "Testing and simulation",
    "Compilation, tooling, and shipping",
]

GOTCHA_APPENDIX_FILE = "A3-gotchas.md"
GOTCHA_OPEN_RE = re.compile(r"^::: \{\.gotcha\b(?P<attrs>[^}]*)\}[ \t]*$")
GOTCHA_ATTR_RE = re.compile(
    r'#(?P<id>[a-z0-9][a-z0-9-]*)|(?P<key>[a-z]+)="(?P<val>[^"]*)"'
)


@dataclass
class Gotcha:
    ident: str
    topic: str
    title: str
    body: str
    source_slug: str   # the chapter or appendix it was marked in
    where: str         # "chapters/04-p-nfts.md:212", for error messages


def _manifest_raw(manifest: Path = MANIFEST) -> dict:
    """book.yaml as a plain dict, without the existence checks load_book does.

    The harvester runs *before* load_book can, because load_book insists every
    file it names exists and the file this produces may not yet.
    """
    return _load_yaml(manifest)


def _source_files(doc: dict) -> list[tuple[str, str]]:
    """(filename, slug) for every non-generated entry, in reading order."""
    out: list[tuple[str, str]] = []
    for raw in doc.get("front", []) or []:
        out.append((raw["file"], raw["slug"]))
    for part in doc.get("parts", []) or []:
        for raw in part.get("chapters", []) or []:
            out.append((raw["file"], raw["slug"]))
    for raw in (doc.get("appendices") or {}).get("files", []) or []:
        if not raw.get("generated"):
            out.append((raw["file"], raw["slug"]))
    for raw in doc.get("back", []) or []:
        out.append((raw["file"], raw["slug"]))
    return out


def harvest_gotchas(manifest: Path = MANIFEST) -> list[Gotcha]:
    """Every {.gotcha} callout in the book, in reading order."""
    doc = _manifest_raw(manifest)
    found: list[Gotcha] = []
    seen: dict[str, str] = {}

    for name, slug in _source_files(doc):
        path = CHAPTERS_DIR / name
        if not path.exists():
            raise SystemExit(f"book.yaml references a missing file: chapters/{name}")
        lines = path.read_text(encoding="utf-8").split("\n")
        i = 0
        while i < len(lines):
            match = GOTCHA_OPEN_RE.match(lines[i])
            if not match:
                i += 1
                continue
            where = f"chapters/{name}:{i + 1}"
            attrs: dict[str, str] = {}
            ident = ""
            for attr in GOTCHA_ATTR_RE.finditer(match.group("attrs")):
                if attr.group("id"):
                    ident = attr.group("id")
                else:
                    attrs[attr.group("key")] = attr.group("val")
            # Collect the body up to the closing marker, respecting fences so a
            # ::: inside a code sample cannot end the callout early.
            body: list[str] = []
            i += 1
            in_fence = False
            while i < len(lines):
                line = lines[i]
                if line.strip().startswith("```"):
                    in_fence = not in_fence
                elif not in_fence and line.strip() == ":::":
                    break
                body.append(line)
                i += 1
            else:
                raise SystemExit(f"{where}: gotcha callout is never closed")
            i += 1

            missing = [k for k in ("topic", "title") if not attrs.get(k)]
            if not ident:
                raise SystemExit(f"{where}: gotcha has no #id")
            if missing:
                raise SystemExit(
                    f"{where}: gotcha #{ident} is missing "
                    + " and ".join(f'{k}="…"' for k in missing)
                )
            if attrs["topic"] not in GOTCHA_TOPICS:
                raise SystemExit(
                    f'{where}: gotcha #{ident} has topic "{attrs["topic"]}", which is '
                    f"not one of: {', '.join(GOTCHA_TOPICS)}"
                )
            if ident in seen:
                raise SystemExit(
                    f"{where}: duplicate gotcha id #{ident}, first seen at {seen[ident]}"
                )
            seen[ident] = where
            found.append(
                Gotcha(
                    ident=ident,
                    topic=attrs["topic"],
                    title=attrs["title"],
                    body="\n".join(body).strip("\n"),
                    source_slug=slug,
                    where=where,
                )
            )
    return found


def render_gotchas_appendix(gotchas: list[Gotcha]) -> str:
    """The Markdown source of Appendix C, ready to be written to chapters/."""
    by_topic: dict[str, list[Gotcha]] = {}
    for g in gotchas:
        by_topic.setdefault(g.topic, []).append(g)

    out: list[str] = [
        "<!-- GENERATED FILE. Do not edit.",
        "     Every entry below is a ::: {.gotcha} callout somewhere in",
        "     chapters/. Edit it there and run `python3 build.py gotchas`.",
        "     scripts/validate.py check 14 fails if this file has drifted. -->",
        "",
        "\\newpage",
        "",
        "# Gotchas by Topic",
        "",
        "Every mistake the book stops to warn you about, in one place. Each entry "
        "appears in full where it can actually save you --- in the chapter, at the "
        "paragraph where you are about to make it --- and is repeated here because "
        "six months from now you will remember that the book warned you about "
        "something to do with box names and not which chapter it was in.",
        "",
        "The pointer after each entry names the chapter it is drawn from; go there "
        "for the surrounding code.",
        "",
    ]
    for topic in GOTCHA_TOPICS:
        entries = by_topic.get(topic)
        if not entries:
            continue
        out.append(f"## {topic}")
        out.append("")
        for g in entries:
            out.append(f"### {g.title}")
            out.append("")
            out.append(g.body)
            out.append("")
            out.append(f"*From {{{{ch:{g.source_slug}}}}}.*")
            out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def write_gotchas_appendix(manifest: Path = MANIFEST) -> Path:
    """Regenerate chapters/A3-gotchas.md. Idempotent; safe to call every build."""
    target = CHAPTERS_DIR / GOTCHA_APPENDIX_FILE
    text = render_gotchas_appendix(harvest_gotchas(manifest))
    if not target.exists() or target.read_text(encoding="utf-8") != text:
        target.write_text(text, encoding="utf-8")
    return target


# ---------------------------------------------------------------------------
# Figures: render once, commit the output
# ---------------------------------------------------------------------------
#
# Neither renderer can draw a diagram at build time. Pandoc and xelatex have no
# idea what Mermaid is, and mdbook-mermaid draws in the browser, which produces
# nothing a print edition can use. So the drawing happens here, ahead of time,
# and the results are committed: a contributor with neither mermaid-cli nor
# rsvg-convert installed can still build the whole book.
#
# Both kinds of source take the same road to PDF. A .mmd goes through mermaid-cli
# to SVG; a hand-drawn .svg is copied as-is; and then ONE uniform rsvg-convert
# pass turns every SVG into the PDF that \includegraphics wants. Letting
# mermaid-cli write the PDF directly would be shorter and wrong: that path is a
# Puppeteer page print, so the file arrives page-sized with margins baked in, and
# \includegraphics scales the margins along with the drawing.
#
# PDF rather than PNG because graphicx cannot read SVG at all, and a PNG that
# looks fine on screen goes soft under an 8pt caption on paper.

FIG_SRC_DIR = FIGURES_DIR / "src"
FIG_OUT_DIR = FIGURES_DIR / "out"
FIG_HASHES = FIG_OUT_DIR / ".hashes.json"
FIG_THEME = FIGURES_DIR / "theme.json"
FIG_PUPPETEER = FIGURES_DIR / "puppeteer.json"


def _digest(*paths: Path) -> str:
    """A stable fingerprint of the inputs that determine one figure's output."""
    h = hashlib.sha256()
    for path in paths:
        h.update(path.read_bytes() if path.exists() else b"")
        h.update(b"\0")
    return h.hexdigest()


def _preserve_label_spaces(svg: Path) -> None:
    """Stop librsvg eating the spaces between words in a Mermaid label.

    With htmlLabels off, Mermaid splits a label one word per <tspan> and carries
    the separator as a *leading* space on each: `<tspan>What</tspan><tspan> the
    </tspan>`. XML's default whitespace handling strips leading whitespace, so
    librsvg renders "Whatthe" -- and since browsers apply the same rule to the
    same file, this is not something the mdbook edition would have caught
    either. Declaring xml:space="preserve" on the <text> element keeps them.

    Safe because mermaid-cli emits the SVG minified: the only whitespace inside
    a <text> element is the separators we want back.
    """
    text = svg.read_text(encoding="utf-8")
    patched = re.sub(r"<text(?![\w-])(?![^>]*xml:space)", '<text xml:space="preserve"', text)
    if patched != text:
        svg.write_text(patched, encoding="utf-8")


def render_figures(*, force: bool = False) -> None:
    """Render figures/src/ into the committed SVG and PDF pair in figures/out/."""
    if not FIG_SRC_DIR.is_dir():
        print("No figures/src/ directory; nothing to render.")
        return
    FIG_OUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        hashes = json.loads(FIG_HASHES.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        hashes = {}

    mmdc = shutil.which("mmdc")
    rsvg = shutil.which("rsvg-convert")
    sources = sorted([*FIG_SRC_DIR.glob("*.mmd"), *FIG_SRC_DIR.glob("*.svg")])
    rendered = skipped = 0

    for source in sources:
        slug = source.stem
        svg_out = FIG_OUT_DIR / f"{slug}.svg"
        pdf_out = FIG_OUT_DIR / f"{slug}.pdf"
        stamp = _digest(source, FIG_THEME) if source.suffix == ".mmd" else _digest(source)
        fresh = (
            not force
            and hashes.get(source.name) == stamp
            and svg_out.exists()
            and pdf_out.exists()
        )
        if fresh:
            skipped += 1
            continue

        if source.suffix == ".mmd":
            if not mmdc:
                # Not an error. The outputs are committed precisely so that a
                # missing drawing toolchain cannot stop anyone building the book.
                print(f"  warning: mermaid-cli (mmdc) not found; keeping committed {slug}.svg")
                continue
            cmd = ["mmdc", "-i", str(source), "-o", str(svg_out), "-c", str(FIG_THEME)]
            if FIG_PUPPETEER.exists():
                cmd += ["-p", str(FIG_PUPPETEER)]
            done = subprocess.run(cmd, capture_output=True, text=True)
            if done.returncode != 0:
                # mermaid reports a syntax error on stdout and a stack trace on
                # stderr; a bare CalledProcessError would show neither, and the
                # line number is the whole diagnosis.
                raise SystemExit(
                    f"figures/src/{source.name}: mermaid-cli failed\n"
                    + (done.stdout or "").strip()
                    + "\n"
                    + (done.stderr or "").strip().split("\n")[0]
                )
            _preserve_label_spaces(svg_out)
        else:
            shutil.copy2(source, svg_out)

        if not rsvg:
            print(f"  warning: rsvg-convert not found; keeping committed {slug}.pdf")
            continue
        subprocess.run(
            ["rsvg-convert", "-f", "pdf", "-o", str(pdf_out), str(svg_out)],
            check=True,
            capture_output=True,
        )
        hashes[source.name] = stamp
        rendered += 1
        print(f"  {slug}: svg + pdf")

    FIG_HASHES.write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Figures: {rendered} rendered, {skipped} unchanged, {len(sources)} total")


def copy_figures_for_mdbook() -> int:
    """Place the SVGs inside the mdbook src root.

    build_mdbook() empties mdbook/src/ and writes only chapters into it, so a
    path pointing at ../figures/ would escape the book root and be dropped
    without a word. The images have to live under src/ to survive.
    """
    svgs = sorted(FIG_OUT_DIR.glob("*.svg")) if FIG_OUT_DIR.is_dir() else []
    if not svgs:
        return 0
    dest = SRC_DIR / "figures"
    dest.mkdir(parents=True, exist_ok=True)
    for svg in svgs:
        shutil.copy2(svg, dest / svg.name)
    return len(svgs)


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


# The book's callout vocabulary. Nine classes, fixed: eight kinds of aside plus
# .gotcha, which Phase 3 harvests into an appendix. A reader learns what each
# box means once. Anything outside this set is a typo, and scripts/validate.py
# check 12 says so rather than letting it render as ordinary prose.
CALLOUT_LABEL = {
    "note": "Note",
    "tip": "Tip",
    "warning": "Warning",
    "gotcha": "Gotcha",
    "setup": "Setup",
    "spec": "How it works",
    "version": "Version",
    "check": "Check your understanding",
    "tryit": "Try it yourself",
}
# A callout may carry pandoc attributes after its class -- .gotcha always does,
# because the gotcha appendix is generated from them. Everything after the class
# is metadata for the harvester and is not rendered by either renderer.
CALLOUT_OPEN_RE = re.compile(r"^::: \{\.([a-z]+)(?:\s[^}]*)?\}\s*$")


FIGURE_IMG_RE = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<src>figures/[a-z0-9-]+\.svg)\)$")


def clean_for_mdbook(text: str) -> str:
    """Transform pandoc-flavored markdown for mdBook consumption.

    - Strips \\newpage and \\part{...} directives
    - Strips pandoc attributes from sub-headings
    - Converts callout fenced divs to HTML (pulldown-cmark has no fenced divs)
    - Converts --- to em-dash
    - Converts LaTeX math delimiters for MathJax
    - Drops content before the first # heading (part intros)
    - Strips {-} from the chapter heading
    """
    lines = text.split("\n")
    out: list[str] = []
    in_code = False
    callout_depth = 0

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
            # Resolved captions: pandoc writes ": Table 4-1. Title", which
            # pulldown-cmark has no notion of. Render it as a bold lead-in.
            line = re.sub(
                r"^(\s*): (Table|Figure|Example) ([\w-]+)\. (.*)$",
                r"\1**\2 \3.** \4",
                line,
            )
            # A figure placement, which the resolver has already turned into an
            # image paragraph. Pandoc promotes that to a captioned figure by
            # itself; pulldown-cmark has no such notion and would emit a bare
            # <img> with the caption hidden in the alt text, where a sighted
            # reader never sees it and the numbering the prose refers to
            # vanishes. So write the <figure> element out longhand.
            figure = FIGURE_IMG_RE.match(line)
            if figure:
                alt, src = figure.group(1), figure.group(2)
                caption = alt.replace(" --- ", " — ")
                out.append("<figure class=\"book-figure\">")
                out.append(f'<img src="{src}" alt="{alt}" />')
                out.append(f"<figcaption>{caption}</figcaption>")
                out.append("</figure>")
                continue

            # Pandoc em-dashes → unicode
            line = line.replace(" --- ", " — ")

            # Callouts. pulldown-cmark has no fenced-div syntax, so the class
            # becomes an HTML wrapper the theme stylesheet can reach. The blank
            # line after the opening tag matters: without it pulldown-cmark
            # treats everything up to the closing tag as a raw HTML block and
            # stops rendering the markdown inside.
            opening = CALLOUT_OPEN_RE.match(line)
            if opening:
                cls = opening.group(1)
                out.append(f'<div class="callout callout-{cls}">')
                out.append(f'<p class="callout-label">{CALLOUT_LABEL[cls]}</p>')
                out.append("")
                callout_depth += 1
                continue
            if line.strip() == ":::" and callout_depth:
                out.append("")
                out.append("</div>")
                callout_depth -= 1
                continue

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

/* --- Callouts -------------------------------------------------------------
   Nine classes, and the same nine colours the PDF uses (chapters/metadata.yaml
   defines them as \\definecolor entries for tcolorbox). Keeping the two lists
   in step is what makes a reader who has met one Warning in the HTML edition
   recognise the next one in print. This lives in build.py rather than in
   mdbook/theme/custom.css because mdbook/ is generated and gitignored: every
   build rewrites that file from this string, so this string is the source. */
.callout {
    --callout-color: #6b7280;
    border-left: 4px solid var(--callout-color);
    background: color-mix(in srgb, var(--callout-color) 5%, transparent);
    padding: 0.85em 1.1em 0.1em;
    margin: 1.5em 0;
    border-radius: 0 4px 4px 0;
}
.callout > .callout-label {
    color: var(--callout-color);
    font-weight: 700;
    font-size: 0.82em;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    margin: 0 0 0.5em;
}
.callout > p:last-child { margin-bottom: 0.85em; }
.callout-note    { --callout-color: #2563eb; }
.callout-tip     { --callout-color: #059669; }
.callout-warning { --callout-color: #dc2626; }
.callout-gotcha  { --callout-color: #b45309; }
.callout-setup   { --callout-color: #6b7280; }
.callout-spec    { --callout-color: #7c3aed; }
.callout-version { --callout-color: #0891b2; }
.callout-check   { --callout-color: #be185d; }
.callout-tryit   { --callout-color: #15803d; }

/* --- Figures --- */
.book-figure {
    margin: 1.8em 0;
    text-align: center;
}
.book-figure img {
    max-width: 100%;
    height: auto;
    /* The diagrams are drawn in greys on white for the print edition. On a dark
       theme that reads as a bright hole in the page, so give them a plate. */
    background: #ffffff;
    border-radius: 4px;
    padding: 0.5em;
}
.book-figure figcaption {
    margin-top: 0.6em;
    font-size: 0.9em;
    font-style: italic;
    opacity: 0.85;
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
    write_gotchas_appendix()
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
    n_figs = copy_figures_for_mdbook()

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

    print(
        f"Prepared {len(chapter_files)} chapters and {n_figs} figures "
        f"in {SRC_DIR.relative_to(ROOT)}/"
    )

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

    write_gotchas_appendix()
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
        # Div classes are invisible to pandoc's LaTeX writer without this.
        f"--lua-filter={SCRIPTS_DIR / 'callouts.lua'}",
        # The resolved source names the SVG the HTML edition serves; graphicx
        # cannot read SVG, so this swaps in the PDF rendered beside it.
        f"--lua-filter={SCRIPTS_DIR / 'figures.lua'}",
        # An example caption is a bold paragraph above its listing, so nothing
        # holds the two together across a page break; this does. It runs BEFORE
        # codebreak.lua, which wraps some paragraphs in raw-LaTeX blocks and
        # would hide the caption-then-listing adjacency this one tests for.
        f"--lua-filter={SCRIPTS_DIR / 'keeptogether.lua'}",
        # The monospace font has HyphenChar=None, so a long identifier has no
        # break opportunity of its own; this puts one after each `.`, `_` and
        # `/` it already contains, printing no character to do it.
        f"--lua-filter={SCRIPTS_DIR / 'codebreak.lua'}",
        # ...and this is what lets the swapped-in bare filename resolve.
        f"--resource-path=.:{(FIGURES_DIR / 'out').relative_to(ROOT)}",
        # Pandoc has never had a --syntax-highlighting flag; the option is
        # --highlight-style. The typo sat here unnoticed because pandoc exits
        # 6 before doing any work, so the PDF target failed on every run.
        "--highlight-style=tango",
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

    write_gotchas_appendix()
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

    fg = sub.add_parser("figures", help="Render figures/src/ to committed SVG + PDF")
    fg.add_argument("--force", action="store_true", help="Re-render even if unchanged")

    sub.add_parser("gotchas", help="Regenerate the gotcha appendix from {.gotcha} callouts")

    args = parser.parse_args()

    if args.command == "mdbook":
        build_mdbook(serve=args.serve, open_browser=args.open)
    elif args.command == "pdf":
        build_pdf()
    elif args.command == "figures":
        render_figures(force=args.force)
    elif args.command == "gotchas":
        target = write_gotchas_appendix()
        count = len(harvest_gotchas())
        print(f"Gotchas: {count} harvested -> {target.relative_to(ROOT)}")
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
