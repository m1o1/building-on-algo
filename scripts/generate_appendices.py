#!/usr/bin/env python3
"""Regenerate the generated appendices from inline sources (PUB-7, PUB-14).

  A3-gotchas.md        <- every ::: {.gotcha} callout in numbered chapters
                          and in the hand-written appendices (A1, A2)
  A4-example-finder.md <- every example caption's <!-- finder: ... --> line

tests/test_book_integrity.py::test_generated_appendices_in_sync fails when
either file drifts from what this script would write. Edit callouts/captions
in the chapters, then run:  python3 scripts/generate_appendices.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import spine  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CHAPTERS = ROOT / "chapters"

GOTCHA_OPEN = re.compile(r'^:{3,}\s*\{\.gotcha\s+#([\w-]+)\s+topic="([^"]+)"\s+title="([^"]+)"\}\s*$')
DIV_CLOSE = re.compile(r"^:{3,}\s*$")
CAPTION = re.compile(r"^\*\*Example (\d+)-(\d+)\.\*\*")
FINDER = re.compile(r"<!--\s*finder:\s*(.+?)\s*-->")

PREAMBLE = """\\newpage

```{{=latex}}
\\renewcommand{{\\BOAchapterkind}}{{}}
```

# {title}
"""


def numbered_chapter_files() -> list[tuple[int, Path]]:
    return [(c.number, CHAPTERS / c.filename) for c in spine.numbered()]


def handwritten_appendix_files() -> list[tuple[str, Path]]:
    """(letter, path) for the hand-written appendices; A3/A4 are generated."""
    generated = {"A3-gotchas.md", "A4-example-finder.md"}
    return [
        (letter, CHAPTERS / fname)
        for letter, fname in spine.APPENDIX_LETTERS.items()
        if fname not in generated
    ]


def harvest_gotchas() -> list[dict]:
    entries = []
    sources: list[tuple[object, Path]] = list(numbered_chapter_files())
    sources += handwritten_appendix_files()
    for origin, path in sources:
        lines = path.read_text(encoding="utf-8").split("\n")
        i, in_code = 0, False
        while i < len(lines):
            line = lines[i]
            if line.strip().startswith("```"):
                in_code = not in_code
            m = None if in_code else GOTCHA_OPEN.match(line.strip())
            if m:
                body: list[str] = []
                depth, j, inner_code = 1, i + 1, False
                while j < len(lines):
                    s = lines[j].strip()
                    if s.startswith("```"):
                        inner_code = not inner_code
                    if not inner_code and re.match(r"^:{3,}\s*\{", s):
                        depth += 1
                    elif not inner_code and DIV_CLOSE.match(s):
                        depth -= 1
                        if depth == 0:
                            break
                    body.append(lines[j])
                    j += 1
                entries.append({
                    "id": m.group(1),
                    "topic": m.group(2),
                    "title": m.group(3),
                    "body": "\n".join(body).strip(),
                    "origin": origin,
                })
                i = j
            i += 1
    return entries


def generate_gotchas() -> str:
    entries = harvest_gotchas()
    topics: list[str] = []
    for e in entries:
        if e["topic"] not in topics:
            topics.append(e["topic"])

    out = [
        "<!-- GENERATED FILE. Do not edit.",
        "     Every entry below is a ::: {.gotcha} callout in a numbered chapter",
        "     or a hand-written appendix.",
        "     Edit it there and run `python3 scripts/generate_appendices.py`.",
        "     tests/test_book_integrity.py fails if this file has drifted. -->",
        "",
        PREAMBLE.format(title="Appendix C: Gotchas by Topic {-}"),
        "Every mistake the book stops to warn you about, in one place. Each entry appears in full where it can actually save you --- in the chapter, at the paragraph where you are about to make it --- and is repeated here because six months from now you will remember that the book warned you about something to do with box names and not which chapter it was in.",
        "",
        "The pointer after each entry names the chapter or appendix it is drawn from; go there for the surrounding code.",
    ]
    for topic in topics:
        out += ["", f"## {topic} {{-}}"]
        for e in entries:
            if e["topic"] != topic:
                continue
            src = e["origin"]
            where = f"Appendix {src}" if isinstance(src, str) else f"Chapter {src}"
            out += ["", f"### {e['title']} {{-}}", "", e["body"], "", f"*From {where}.*"]
    return "\n".join(out).rstrip() + "\n"


def harvest_finders() -> list[dict]:
    rows = []
    for num, path in numbered_chapter_files():
        lines = path.read_text(encoding="utf-8").split("\n")
        for i, line in enumerate(lines):
            cm = CAPTION.match(line)
            if not cm:
                continue
            for j in range(i + 1, min(i + 5, len(lines))):
                fm = FINDER.search(lines[j])
                if fm:
                    rows.append({
                        "task": fm.group(1),
                        "example": f"Example {cm.group(1)}-{cm.group(2)}",
                        "chapter": num,
                    })
                    break
    return rows


def generate_finder() -> str:
    rows = harvest_finders()
    out = [
        "<!-- GENERATED FILE. Do not edit.",
        "     Every row below is an example caption in a numbered chapter paired",
        "     with the `<!-- finder: ... -->` line beneath it. Edit those and run",
        "     `python3 scripts/generate_appendices.py`.",
        "     tests/test_book_integrity.py fails if this file has drifted. -->",
        "",
        PREAMBLE.format(title="Appendix D: The Example Finder {-}"),
        "Every numbered example in the book, listed by what it is *for* rather than by what it is called. The left column is the task you arrived with; the right is where the example that does it lives.",
        "",
        "A caption names an example from the author's side. This appendix names it from yours, which is why the wording here will not match the wording on the page. The tables are deliberately uncaptioned: they are lookup surfaces, not numbered exhibits, and nothing in the book cites them.",
        "",
        "## By Part {-}",
    ]
    for part in spine.PARTS:
        chapter_nums = [c.number for c in spine.numbered() if c.part == part.number]
        part_rows = [r for r in rows if r["chapter"] in chapter_nums]
        if not part_rows:
            continue
        out += ["", f"### Part {part.roman}: {part.title} {{-}}", "", "| To do this | Go to |", "|------------|-------|"]
        for r in part_rows:
            out.append(f"| {r['task'][:1].upper()}{r['task'][1:]} | {r['example']} |")
    out += [
        "",
        "## Alphabetical {-}",
        "",
        "| To do this | Go to |",
        "|------------|-------|",
    ]
    for r in sorted(rows, key=lambda r: r["task"].lower()):
        out.append(f"| {r['task'][:1].upper()}{r['task'][1:]} | {r['example']} |")
    return "\n".join(out).rstrip() + "\n"


def main() -> None:
    (CHAPTERS / "A3-gotchas.md").write_text(generate_gotchas(), encoding="utf-8")
    (CHAPTERS / "A4-example-finder.md").write_text(generate_finder(), encoding="utf-8")
    g = len(harvest_gotchas())
    f = len(harvest_finders())
    print(f"A3: {g} gotchas; A4: {f} finder rows")


if __name__ == "__main__":
    main()
