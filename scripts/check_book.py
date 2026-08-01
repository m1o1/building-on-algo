#!/usr/bin/env python3
"""Manuscript drift-checker: verifies chapters/ against scripts/spine.py.

The checks enforce RULEBOOK PUB-6/PUB-13/PED-12 mechanically:

  errors (exit 1):
    E1  Example/Table/Figure caption numbered against the wrong chapter
    E2  reference to Example/Table/Figure N-M with no such caption in chapter N
    E3  reference to a chapter number outside the spine
    E4  Retrieval section quizzing a later chapter (PED-12)
    E5  stale pre-rewrite part titles or chapter-numbered code paths
    E6  figure reference with no file in figures/
    E7  Handoff table with no receiving "What You Need First" (PUB-13) [once wired]

  warnings (exit 0):
    W1  example caption numbering has gaps or is out of order
    W2  examples/ or projects/ path referenced in prose missing on disk
        (upgrade to error once Phase 5 re-extracts the examples tree)

Usage: python3 scripts/check_book.py [--strict-paths]
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spine  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CHAPTERS = ROOT / "chapters"

STALE_STRINGS = [
    # Old part titles (pre-rewrite) that must not survive in prose.
    "Value in Motion",
    "Randomness and Fair Draws",
    "Logic Signatures and Stateless Programs",
    "Cryptography and Zero-Knowledge Proofs",
    # Chapter-numbered code paths (killed by the stable-name scheme) — both
    # path form and dotted-import form.
    "examples/ch0",
    "examples/ch1",
    "examples/ch2",
    "examples.ch",
    "projects/chapter",
    "projects/zk-voting",
]

# Caption forms: bold example captions, pandoc table captions (`: Table N-M.`),
# and figure captions inside image alt text (`![Figure N-M. ...](...)`).
CAPTION_RE = re.compile(
    r"^\*\*(Example|Table|Figure) (\d+)-(\d+)\.\*\*"
    r"|^: (Table|Figure) (\d+)-(\d+)\."
    r"|!\[(Figure) (\d+)-(\d+)\.",
    re.MULTILINE,
)
REF_RE = re.compile(r"\b(Example|Table|Figure)s? (\d+)-(\d+)\b")
CHAPTER_REF_RE = re.compile(r"\bChapter (\d+)\b")
FIGFILE_RE = re.compile(r"\]\((figures/[^)#\s]+)\)")
PATH_RE = re.compile(r"\b((?:examples|projects)/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)")


def strip_code_blocks(text: str) -> str:
    """Remove fenced code blocks so prose checks don't fire on code."""
    out, in_code = [], False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        out.append(line if not in_code else "")
    return "\n".join(out)


def main() -> int:
    strict_paths = "--strict-paths" in sys.argv
    errors: list[str] = []
    warnings: list[str] = []

    texts: dict[str, str] = {}
    for f in sorted(CHAPTERS.glob("*.md")):
        texts[f.name] = f.read_text(encoding="utf-8")

    max_ch = max(c.number for c in spine.numbered())
    file_by_number = {c.number: c.filename for c in spine.numbered()}

    # Collect captions per chapter number
    captions: dict[tuple[str, int], set[int]] = defaultdict(set)
    for name, text in texts.items():
        for m in CAPTION_RE.finditer(text):
            kind, ch_s, item_s = [g for g in m.groups() if g is not None][:3]
            captions[(kind, int(ch_s))].add(int(item_s))

    # E1 + W1: captions belong to their own chapter, numbered densely
    for c in spine.numbered():
        text = texts.get(c.filename, "")
        own: dict[str, list[int]] = defaultdict(list)
        for cm in CAPTION_RE.finditer(text):
            kind, ch_s, item_s = [g for g in cm.groups() if g is not None][:3]
            n = int(ch_s)
            if n != c.number:
                errors.append(
                    f"E1 {c.filename}: caption '{kind} {n}-{item_s}' in chapter {c.number}"
                )
            else:
                own[kind].append(int(item_s))
        for kind, nums in own.items():
            expected = list(range(1, len(nums) + 1))
            if sorted(nums) != expected:
                warnings.append(
                    f"W1 {c.filename}: {kind} numbering {sorted(nums)} not dense 1..{len(nums)}"
                )
            if nums != sorted(nums):
                warnings.append(f"W1 {c.filename}: {kind} captions out of order: {nums}")

    # E2/E3: references resolve
    for name, text in texts.items():
        prose = strip_code_blocks(text)
        for kind, ch_s, item_s in REF_RE.findall(prose):
            n, m = int(ch_s), int(item_s)
            if n > max_ch:
                errors.append(f"E3 {name}: reference to {kind} {n}-{m} beyond spine")
                continue
            if m not in captions.get((kind, n), set()):
                errors.append(f"E2 {name}: {kind} {n}-{m} referenced but no such caption")
        for ch_s in CHAPTER_REF_RE.findall(prose):
            if not 1 <= int(ch_s) <= max_ch:
                errors.append(f"E3 {name}: reference to Chapter {ch_s} beyond spine")

    # E4: Retrieval reaches only backward
    for c in spine.numbered():
        text = texts.get(c.filename, "")
        m = re.search(r"^##+ .*Retrieval.*$", text, re.MULTILINE)
        if not m:
            continue
        after = text[m.end():]
        nxt = re.search(r"^##[^#]", after, re.MULTILINE)
        section = after[: nxt.start()] if nxt else after
        for line in section.split("\n"):
            if "(Preview" in line:
                continue  # labeled previews are IOUs, not retrieval (PED-12 exempt)
            for ch_s in CHAPTER_REF_RE.findall(line):
                if int(ch_s) >= c.number:
                    errors.append(
                        f"E4 {c.filename}: Retrieval references Chapter {ch_s} (chapter is {c.number})"
                    )

    # E5: stale strings
    for name, text in texts.items():
        for s in STALE_STRINGS:
            if s in text:
                count = text.count(s)
                errors.append(f"E5 {name}: stale string '{s}' x{count}")

    # E6: figures exist
    for name, text in texts.items():
        for fig in FIGFILE_RE.findall(text):
            if not (ROOT / fig).exists():
                errors.append(f"E6 {name}: missing figure file {fig}")

    # W2: code paths exist on disk. The reader's own scaffold from the setup
    # walkthrough (projects/my-first-contract) is created reader-side and is
    # deliberately not in the repo.
    READER_SIDE = ("projects/my-first-contract",)
    for name, text in texts.items():
        for p in set(PATH_RE.findall(text)):
            if p.startswith(READER_SIDE):
                continue
            candidate = ROOT / p
            if not candidate.exists():
                msg = f"W2 {name}: path '{p}' not on disk"
                (errors if strict_paths else warnings).append(msg)

    # E7: Handoff/receiving reciprocity — every concept chapter immediately
    # before a project must hand off, and the project must receive.
    chapters_in_order = spine.numbered()
    for i, c in enumerate(chapters_in_order[:-1]):
        nxt_ch = chapters_in_order[i + 1]
        if c.kind == "concept" and nxt_ch.kind == "project":
            if "Handoff" not in texts.get(c.filename, ""):
                errors.append(f"E7 {c.filename}: no Handoff table before project {nxt_ch.filename}")
            if "What You Need First" not in texts.get(nxt_ch.filename, ""):
                errors.append(f"E7 {nxt_ch.filename}: project lacks 'What You Need First' table")

    for w in warnings:
        print(f"  warn: {w}")
    for e in errors:
        print(f"ERROR: {e}")
    print(f"\n{len(errors)} errors, {len(warnings)} warnings across {len(texts)} files")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
