"""Repository validation harness.

The harness keeps generated compiler output out of the source tree by writing
PuyaPy artifacts to a temporary directory.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "validation" / "manifest.json"
EXAMPLES_ROOT = ROOT / "examples"
EXAMPLES_INDEX = EXAMPLES_ROOT / "index.yaml"
FIGURES_ROOT = ROOT / "figures"
FIGURES_INDEX = FIGURES_ROOT / "index.yaml"
FIGURES_OUT = FIGURES_ROOT / "out"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


ACTIVE = {"active"}
PENDING = {"pending", "pending-pr", "pending-extraction"}
KNOWN_STATUSES = ACTIVE | PENDING
TARGET_AVM_VERSION = "12"


def test() -> None:
    run([sys.executable, "-m", "pytest", "tests", "-q"])


def active_items(manifest: dict, key: str) -> list[dict]:
    return [
        item
        for item in manifest.get(key, [])
        if status_of(item) in ACTIVE
    ]


def status_of(item: dict) -> str:
    status = item.get("status", "active")
    if status not in KNOWN_STATUSES:
        name = item.get("name") or item.get("path") or item
        raise AssertionError(f"Unknown manifest status {status!r} for {name}")
    return status


def compile_contracts() -> None:
    manifest = load_manifest()
    contracts = [
        ROOT / item["path"]
        for item in active_items(manifest, "compiled_contracts")
    ]
    if not contracts:
        print("No active compile targets in validation manifest")
        return
    with tempfile.TemporaryDirectory(prefix="building-on-algo-puya-") as tmp:
        out_dir = Path(tmp) / "artifacts"
        out_dir.mkdir()
        run(
            [
                sys.executable,
                "-m",
                "puyapy",
                "--target-avm-version",
                TARGET_AVM_VERSION,
                "--out-dir",
                str(out_dir),
                *[str(path) for path in contracts],
            ]
        )
        outputs = sorted(path.name for path in out_dir.iterdir())
        if not outputs:
            raise AssertionError("PuyaPy produced no artifacts")
        print("Compiled artifacts:")
        for name in outputs:
            print(f"  {name}")


def check_manifest(strict: bool = False) -> None:
    manifest = load_manifest()
    missing = []
    pending = []
    for item in manifest.get("compiled_contracts", []):
        status = status_of(item)
        if status in PENDING:
            pending.append(f"compile: {item['name']}")
            continue
        if not (ROOT / item["path"]).exists():
            missing.append(item["path"])
    for item in manifest.get("high_risk_flows", []):
        status = status_of(item)
        if status in PENDING:
            pending.append(f"flow: {item['name']}")
            continue
        test_path = item["test"].split("::", 1)[0]
        if not (ROOT / test_path).exists():
            missing.append(item["test"])
        if "::" in item["test"]:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "--collect-only",
                    "-q",
                    item["test"],
                ],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if result.returncode != 0:
                missing.append(item["test"])
    for item in manifest.get("localnet_smoke", []):
        status = status_of(item)
        if status in PENDING:
            pending.append(f"localnet: {item['name']}")
            continue
        script_path = item.get("script")
        if script_path and not (ROOT / script_path).exists():
            missing.append(script_path)
    for item in manifest.get("coverage_summary", []):
        status_of(item)
    if missing:
        raise AssertionError(f"Missing validation targets: {missing}")
    if strict and pending:
        raise AssertionError(f"Pending validation targets: {pending}")
    print("Validation manifest targets exist")
    if pending:
        print("Pending validation targets:")
        for item in pending:
            print(f"  {item}")


def localnet_smoke() -> None:
    if shutil.which("algokit") is None:
        print("Skipping LocalNet smoke: algokit is not installed")
        return
    print("+ algokit localnet status", flush=True)
    status = subprocess.run(
        ["algokit", "localnet", "status"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    status_output = f"{status.stdout}\n{status.stderr}"
    if status.returncode != 0:
        # Any failed status check means LocalNet is unavailable (no container
        # engine, engine not running, or LocalNet not started) -- skip, don't crash.
        print("Skipping LocalNet smoke: LocalNet is not available")
        print(status_output.strip())
        return
    if status.stdout:
        print(status.stdout, end="")
    if status.stderr:
        print(status.stderr, end="", file=sys.stderr)
    status.check_returncode()
    manifest = load_manifest()
    active_scripts = [
        item
        for item in manifest.get("localnet_smoke", [])
        if status_of(item) in ACTIVE
    ]
    pending = [
        item["name"]
        for item in manifest.get("localnet_smoke", [])
        if status_of(item) in PENDING
    ]
    for item in active_scripts:
        script = item.get("script")
        if script:
            run([sys.executable, script])
    if pending:
        print("Pending project LocalNet smoke scripts:")
        for name in pending:
            print(f"  {name}")


# ---------------------------------------------------------------------------
# examples/ -- the Completeness Contract harness
#
# Every numbered example in the book is a complete, buildable program living on
# disk under examples/. This target walks examples/index.yaml and dispatches by
# execution mode. It is the slowest target in the suite by a wide margin (one
# puyapy invocation per example), so CI runs it on the full-build job rather
# than on every commit; --changed-only exists for the local edit loop.
# ---------------------------------------------------------------------------

EXAMPLE_MODES = {"compile", "compile-fail", "unit", "localnet"}
EXAMPLE_TIERS = {"core", "extended"}


def _load_yaml(path: Path) -> dict:
    try:
        import yaml
    except ModuleNotFoundError:  # pragma: no cover - environment guard
        raise SystemExit(
            "PyYAML is required to read the example index.\n"
            "  uv sync --group build   (or: pip install pyyaml)"
        ) from None
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_examples() -> list[dict]:
    """Parse and schema-check examples/index.yaml."""
    if not EXAMPLES_INDEX.exists():
        raise SystemExit(f"Missing example index: {EXAMPLES_INDEX}")
    data = _load_yaml(EXAMPLES_INDEX)
    entries = data.get("examples") or []
    problems: list[str] = []
    seen: set[str] = set()
    for position, entry in enumerate(entries, start=1):
        slug = entry.get("slug")
        where = slug or f"entry #{position}"
        if not slug:
            problems.append(f"{where}: missing slug")
        elif slug in seen:
            problems.append(f"{where}: duplicate slug")
        else:
            seen.add(slug)
        rel = entry.get("path")
        if not rel:
            problems.append(f"{where}: missing path")
        elif not (EXAMPLES_ROOT / rel).exists():
            problems.append(f"{where}: path does not exist: examples/{rel}")
        mode = entry.get("mode")
        if mode not in EXAMPLE_MODES:
            problems.append(f"{where}: mode must be one of {sorted(EXAMPLE_MODES)}, got {mode!r}")
        tier = entry.get("tier")
        if tier not in EXAMPLE_TIERS:
            problems.append(f"{where}: tier must be one of {sorted(EXAMPLE_TIERS)}, got {tier!r}")
        if mode == "compile-fail" and not entry.get("expect"):
            # Without this, a compile-fail example passes when it fails for a
            # typo instead of for the reason the book claims.
            problems.append(f"{where}: compile-fail requires an `expect` substring")
        if mode == "unit":
            unit_test = entry.get("test")
            if not unit_test:
                problems.append(f"{where}: unit mode requires a `test` file")
            elif not (EXAMPLES_ROOT / unit_test).exists():
                problems.append(f"{where}: test does not exist: examples/{unit_test}")
    if problems:
        raise AssertionError(
            "examples/index.yaml is invalid:\n  " + "\n  ".join(problems)
        )
    return entries


def load_figures() -> list[dict]:
    """Parse and schema-check figures/index.yaml.

    A figure entry is small on purpose: the slug the book refers to it by, the
    caption that follows it on the page, and the source file it was drawn from.
    Everything else — its number, which chapter it lands in, which file each
    renderer consumes — is derived, which is why none of it is written here.
    """
    if not FIGURES_INDEX.exists():
        return []
    data = _load_yaml(FIGURES_INDEX)
    entries = data.get("figures") or []
    problems: list[str] = []
    seen: set[str] = set()
    for position, entry in enumerate(entries, start=1):
        slug = entry.get("slug")
        where = slug or f"entry #{position}"
        if not slug:
            problems.append(f"{where}: missing slug")
        elif slug in seen:
            problems.append(f"{where}: duplicate slug")
        else:
            seen.add(slug)
        if not entry.get("caption"):
            problems.append(f"{where}: missing caption")
        rel = entry.get("source")
        if not rel:
            problems.append(f"{where}: missing source")
        elif not (FIGURES_ROOT / rel).exists():
            problems.append(f"{where}: source does not exist: figures/{rel}")
    if problems:
        raise AssertionError("figures/index.yaml is invalid:\n  " + "\n  ".join(problems))
    return entries


def _puyapy(source: Path, out_dir: Path) -> subprocess.CompletedProcess:
    """Compile one example.

    --target-avm-version is always passed explicitly: puyapy defaults to AVM
    v11, so omitting it silently verifies one AVM version below the book's.
    """
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "puyapy",
            "--target-avm-version",
            TARGET_AVM_VERSION,
            "--out-dir",
            str(out_dir),
            str(source),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _changed_example_paths() -> set[str] | None:
    """Paths under examples/ touched relative to origin/HEAD, or None if unknown."""
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD", "--", "examples"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "examples"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    names = result.stdout.split() + (
        untracked.stdout.split() if untracked.returncode == 0 else []
    )
    return {name[len("examples/"):] for name in names if name.startswith("examples/")}


def check_examples(changed_only: bool = False) -> None:
    entries = load_examples()
    if changed_only:
        changed = _changed_example_paths()
        if changed is None:
            print("--changed-only: git unavailable, running every example")
        else:
            before = len(entries)
            entries = [
                entry
                for entry in entries
                if entry["path"] in changed or entry.get("test") in changed
            ]
            print(f"--changed-only: {len(entries)} of {before} examples touched")
    if not entries:
        print("No examples to check")
        return

    localnet_available = shutil.which("algokit") is not None
    failures: list[str] = []
    skipped: list[str] = []
    passed = 0

    with tempfile.TemporaryDirectory(prefix="building-on-algo-examples-") as tmp:
        out_root = Path(tmp)
        for entry in entries:
            slug = entry["slug"]
            mode = entry["mode"]
            source = EXAMPLES_ROOT / entry["path"]
            out_dir = out_root / slug
            out_dir.mkdir(parents=True, exist_ok=True)

            if mode == "localnet" and not localnet_available:
                skipped.append(f"{slug} (localnet: algokit not installed)")
                continue

            # Every mode except compile-fail must compile: the Completeness
            # Contract says the artifact on the page builds.
            result = _puyapy(source, out_dir)
            output = f"{result.stdout}\n{result.stderr}"

            if mode == "compile-fail":
                expect = entry["expect"]
                if result.returncode == 0:
                    failures.append(f"{slug}: expected a compile failure, got exit 0")
                elif expect not in output:
                    failures.append(
                        f"{slug}: compile failed, but not for the declared reason.\n"
                        f"      expected substring: {expect!r}\n"
                        f"      actual output: {output.strip()[:400]}"
                    )
                else:
                    passed += 1
                continue

            if result.returncode != 0:
                failures.append(f"{slug}: compile failed\n      {output.strip()[:400]}")
                continue
            if "error:" in output:
                failures.append(f"{slug}: compiler reported an error\n      {output.strip()[:400]}")
                continue

            if mode == "unit":
                unit = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "pytest",
                        str(EXAMPLES_ROOT / entry["test"]),
                        "-q",
                        "-o",
                        "python_files=*_test.py",
                        "-o",
                        "testpaths=",
                    ],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if unit.returncode != 0:
                    failures.append(
                        f"{slug}: unit test failed\n      "
                        f"{(unit.stdout + unit.stderr).strip()[-600:]}"
                    )
                    continue

            if mode == "localnet":
                script = entry.get("script")
                if not script:
                    skipped.append(f"{slug} (localnet: no driver script yet)")
                    continue
                driver = subprocess.run(
                    [sys.executable, str(EXAMPLES_ROOT / script)],
                    cwd=ROOT,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                if driver.returncode != 0:
                    failures.append(
                        f"{slug}: LocalNet driver failed\n      "
                        f"{(driver.stdout + driver.stderr).strip()[-600:]}"
                    )
                    continue

            passed += 1

    print(f"Examples: {passed} passed, {len(failures)} failed, {len(skipped)} skipped")
    for note in skipped:
        print(f"  skip: {note}")
    if failures:
        raise AssertionError(
            "Example harness failures:\n  " + "\n  ".join(failures)
        )


# ---------------------------------------------------------------------------
# --structure: the eleven checks
#
# These enforce the invariants that make the book's apparatus mechanical rather
# than a thing somebody remembers to do. Each check is numbered to match §11.3
# of RESTRUCTURING-PLAN.md; the numbering is stable so a CI failure can be
# looked up. Severity is per-check and deliberate: an error is a claim the book
# makes to the reader that has become false, a warning is a smell.
# ---------------------------------------------------------------------------

CHAPTERS_DIR = ROOT / "chapters"
BOOK_MANIFEST = CHAPTERS_DIR / "book.yaml"

XREF_RE = re.compile(r"\{\{([a-z][a-z-]*):([^}]*)\}\}")
XREF_NAMESPACES = {"ex", "tbl", "fig", "ch", "chn", "part", "include-ex", "include-fig"}
# {{figure:...}} is the single most likely typo for {{fig:...}} and would
# otherwise sail through as an unknown namespace. Name it explicitly.
BANNED_NAMESPACES = {"figure", "table", "example", "chapter", "sec", "section"}

MAX_CODE_LINE = 85
# Wrapping is a property of the content, not the author's patience: prose-ish
# fences (ASCII diagrams, JSON payloads, TEAL listings, terminal transcripts)
# are exempt wholesale because breaking their lines would corrupt them.
NOWRAP_LANGS = {"text", "json", "teal", "console", "output", ""}
TIER_LINE_BUDGET = {"core": 35, "extended": 20}

# Check 4 stays registered but disabled until Phase 5 folds A1-cookbook.md into
# the need-shaped chapters. Flipping this to True is the last act of Phase 5.
# The callout vocabulary, kept in step with build.py's CALLOUT_LABEL and the
# tcolorbox environments in chapters/metadata.yaml. Eight kinds of aside plus
# .gotcha, which Phase 3 populates and harvests into an appendix.
CALLOUT_CLASSES = {
    "note", "tip", "warning", "gotcha", "setup",
    "spec", "version", "check", "tryit",
}
CALLOUT_OPEN_RE = re.compile(r"^::: \{\.([a-z]+)\}$")
CALLOUT_ANY_OPEN_RE = re.compile(r"^:::\s*\S")

COOKBOOK_RETIRED = False
COOKBOOK_FILE = "A1-cookbook.md"


@dataclass
class Problem:
    check: int
    severity: str  # "error" | "warning"
    where: str
    message: str

    def __str__(self) -> str:
        return f"[check {self.check:>2}] {self.severity:<7} {self.where}: {self.message}"


def _fences(text: str):
    """Yield (open_line_no, info_string, body_lines) for each fenced block."""
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("```"):
            info = stripped[3:].strip()
            start = i + 1
            body: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            yield start, info, body
        i += 1


def _outside_fences(text: str):
    """Yield (line_no, line) for lines that are not inside a code fence."""
    in_fence = False
    for n, line in enumerate(text.split("\n"), start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield n, line


def _load_book_manifest() -> dict:
    if not BOOK_MANIFEST.exists():
        raise SystemExit(f"Missing book manifest: {BOOK_MANIFEST}")
    return _load_yaml(BOOK_MANIFEST) or {}


def _manifest_entries(doc: dict) -> list[dict]:
    """Every file entry in book.yaml, tagged with its role and kind."""
    out: list[dict] = []
    for raw in doc.get("front", []):
        out.append({**raw, "role": "front"})
    for part in doc.get("parts", []):
        for raw in part.get("chapters", []):
            out.append({**raw, "role": "chapter", "part_id": part.get("id", "")})
    for raw in (doc.get("appendices") or {}).get("files", []):
        out.append({**raw, "role": "appendix"})
    for raw in doc.get("back", []):
        out.append({**raw, "role": "back"})
    return out


def check_structure(strict: bool = False) -> None:
    doc = _load_book_manifest()
    entries = _manifest_entries(doc)
    examples = load_examples()
    figures = load_figures()
    figure_slugs = {f["slug"] for f in figures}
    placements: dict[str, list[str]] = {}  # figure slug -> [where, ...]
    example_slugs = {e["slug"] for e in examples}
    chapter_slugs = {e["slug"] for e in entries}
    problems: list[Problem] = []

    # -- check 2: duplicate slug ------------------------------------------
    # Slugs are the book's permanent identifiers. A duplicate silently makes
    # one of two references point at the wrong thing, forever.
    for label, slugs in (("book.yaml", [e["slug"] for e in entries]),
                         ("examples/index.yaml", [e["slug"] for e in examples])):
        seen: set[str] = set()
        for slug in slugs:
            if slug in seen:
                problems.append(Problem(2, "error", label, f"duplicate slug {slug!r}"))
            seen.add(slug)
    for slug in chapter_slugs & example_slugs:
        problems.append(
            Problem(2, "error", "book.yaml/index.yaml",
                    f"slug {slug!r} names both a chapter and an example")
        )

    # Anchors declared in prose, collected before check 1 resolves references.
    # A table or figure declares itself with an attribute on its caption line:
    #     : Fee pooling rules {#tbl:fee-pooling}
    anchor_re = re.compile(r"\{#(tbl|fig|ex):([a-z0-9][a-z0-9-]*)\}")
    # A figure has no caption line in the chapter to hang {#fig:slug} on — its
    # caption lives in figures/index.yaml — so the placement directive is what
    # mints the anchor. Both syntaxes feed the same `anchors` map, which is what
    # lets {{fig:slug}} resolve and check 3 notice an unreferenced figure.
    placement_re = re.compile(r"\{\{include-fig:([a-z0-9][a-z0-9-]*)\}\}")
    anchors: dict[str, str] = {}   # slug -> "chapters/file.md:line"
    references: dict[str, list[str]] = {}  # slug -> [where, ...]

    for entry in entries:
        path = CHAPTERS_DIR / entry["file"]
        if not path.exists():
            problems.append(Problem(2, "error", "book.yaml", f"missing file: {entry['file']}"))
            continue
        text = path.read_text(encoding="utf-8")
        rel = f"chapters/{entry['file']}"
        is_chapter = entry["role"] == "chapter"
        kind = entry.get("kind", "")

        for line_no, line in _outside_fences(text):
            for ns, slug in anchor_re.findall(line):
                key = f"{ns}:{slug}"
                if key in anchors:
                    problems.append(
                        Problem(2, "error", f"{rel}:{line_no}",
                                f"duplicate anchor {{#{key}}}, first seen at {anchors[key]}")
                    )
                anchors[key] = f"{rel}:{line_no}"

            for slug in placement_re.findall(line):
                key = f"fig:{slug}"
                where = f"{rel}:{line_no}"
                placements.setdefault(slug, []).append(where)
                if key in anchors:
                    problems.append(
                        Problem(2, "error", where,
                                f"duplicate anchor {{#{key}}}, first seen at {anchors[key]}")
                    )
                anchors[key] = where

            # -- check 5: appendix-in-chapter ------------------------------
            # An appendix inside a chapter is a section the author could not
            # place. It also collides with the real appendices in the ToC.
            if is_chapter and re.match(r"^#{2,6}\s+Appendix\b", line.strip()):
                problems.append(
                    Problem(5, "error", f"{rel}:{line_no}",
                            f"chapter contains an appendix section: {line.strip()!r}")
                )

        # -- check 1: unknown slug ----------------------------------------
        for line_no, line in _outside_fences(text):
            for ns, slug in XREF_RE.findall(line):
                where = f"{rel}:{line_no}"
                if ns in BANNED_NAMESPACES:
                    correct = {"figure": "fig", "table": "tbl", "example": "ex",
                               "chapter": "ch"}.get(ns, "ch")
                    problems.append(
                        Problem(1, "error", where,
                                f"{{{{{ns}:}}}} is not a namespace — did you mean "
                                f"{{{{{correct}:}}}}?")
                    )
                    continue
                if ns not in XREF_NAMESPACES:
                    problems.append(
                        Problem(1, "error", where, f"unknown xref namespace {{{{{ns}:}}}}")
                    )
                    continue
                references.setdefault(f"{ns}:{slug}", []).append(where)

        # -- check 6 and 7: fences ----------------------------------------
        for open_line, info, body in _fences(text):
            lang = info.split()[0] if info else ""
            if not lang:
                problems.append(
                    Problem(6, "error", f"{rel}:{open_line - 1}",
                            "code fence has no language tag")
                )
            if lang in NOWRAP_LANGS or "{.nowrap}" in info:
                continue
            for offset, code_line in enumerate(body):
                if len(code_line) > MAX_CODE_LINE:
                    problems.append(
                        Problem(7, "error", f"{rel}:{open_line + offset}",
                                f"code line is {len(code_line)} chars "
                                f"(limit {MAX_CODE_LINE}); wrap it, or tag the "
                                f"fence ```{lang} {{.nowrap}}")
                    )

        # -- check 8: project re-teaching ---------------------------------
        # A project chapter that re-explains a concept is spending the reader's
        # attention on something they already paid for. Warning, not error:
        # a deliberate one-line reminder is legitimate.
        if kind == "project":
            for line_no, line in _outside_fences(text):
                if re.match(r"^#{2,3}\s+(What Is|Understanding|A Primer|Introduction to)\b",
                            line.strip()):
                    problems.append(
                        Problem(8, "warning", f"{rel}:{line_no}",
                                f"project chapter re-teaches a concept: {line.strip()!r}")
                    )

        # -- check 12: callout vocabulary ---------------------------------
        # New in Phase 1, beyond the eleven of §11.3, because the callout
        # system it guards is also new. An unrecognised class is worse than a
        # missing one: the HTML renderer boxes anything with a class attribute,
        # while pandoc's LaTeX writer silently drops a Div it has no
        # environment for. A typo would therefore render as a callout in the
        # HTML and as bare prose in the PDF, and nothing would report it.
        depth = 0
        for line_no, line in _outside_fences(text):
            stripped = line.strip()
            if stripped == ":::":
                depth -= 1
                if depth < 0:
                    problems.append(
                        Problem(12, "error", f"{rel}:{line_no}",
                                "callout closed but never opened")
                    )
                    depth = 0
                continue
            opening = CALLOUT_OPEN_RE.match(stripped)
            if CALLOUT_ANY_OPEN_RE.match(stripped) and not opening:
                problems.append(
                    Problem(12, "error", f"{rel}:{line_no}",
                            f"malformed callout {stripped!r}; expected ::: {{.class}}")
                )
                depth += 1
                continue
            if opening:
                depth += 1
                if opening.group(1) not in CALLOUT_CLASSES:
                    problems.append(
                        Problem(12, "error", f"{rel}:{line_no}",
                                f"unknown callout class {opening.group(1)!r}; "
                                f"one of {', '.join(sorted(CALLOUT_CLASSES))}")
                    )
        if depth:
            problems.append(
                Problem(12, "error", rel, f"{depth} callout(s) left unclosed")
            )

        # -- check 11: capstone leak --------------------------------------
        # The capstone must be assemblable from what precedes it. A chapter
        # that names capstone-only material has leaked the ending.
        if is_chapter and kind != "capstone":
            for line_no, line in _outside_fences(text):
                if re.search(r"\bcapstone\b", line, re.IGNORECASE):
                    problems.append(
                        Problem(11, "error", f"{rel}:{line_no}",
                                "non-capstone chapter refers to the capstone")
                    )

    # -- check 1 (continued): every reference resolves ---------------------
    for key, wheres in references.items():
        ns, _, slug = key.partition(":")
        if ns in ("ch", "chn"):
            known = slug in chapter_slugs
        elif ns in ("ex", "include-ex"):
            known = slug in example_slugs
        elif ns == "include-fig":
            known = slug in figure_slugs
        elif ns == "part":
            known = slug in {p.get("id") for p in doc.get("parts", [])}
        else:
            known = key in anchors
        if not known:
            for where in wheres:
                problems.append(Problem(1, "error", where, f"unresolved reference {{{{{key}}}}}"))

    # -- check 3: orphan number (tables and figures only) ------------------
    # Scoped deliberately. An unreferenced example is fine — examples are read
    # in place. An unreferenced *numbered* table or figure means the reader was
    # given a number they are never told to use.
    for key, where in anchors.items():
        if key.startswith(("tbl:", "fig:")) and key not in references:
            problems.append(
                Problem(3, "warning", where, f"{key} is numbered but never referenced")
            )

    # -- check 4: cookbook residue ----------------------------------------
    if COOKBOOK_RETIRED and (CHAPTERS_DIR / COOKBOOK_FILE).exists():
        problems.append(
            Problem(4, "error", f"chapters/{COOKBOOK_FILE}",
                    "cookbook is retired but the file is still in the book")
        )

    # -- check 9: print/disk drift ----------------------------------------
    # The book must not contain a hand-pasted copy of a file that lives in
    # examples/. Transclusion exists precisely so the printed artifact and the
    # compiled artifact cannot diverge; a literal paste re-opens that gap.
    def _normalize(code: str) -> str:
        return "\n".join(line.rstrip() for line in code.strip().split("\n") if line.strip())

    on_disk = {
        _normalize((EXAMPLES_ROOT / e["path"]).read_text(encoding="utf-8")): e["slug"]
        for e in examples
    }
    for entry in entries:
        path = CHAPTERS_DIR / entry["file"]
        if not path.exists():
            continue
        for open_line, info, body in _fences(path.read_text(encoding="utf-8")):
            slug = on_disk.get(_normalize("\n".join(body)))
            if slug:
                problems.append(
                    Problem(9, "error", f"chapters/{entry['file']}:{open_line}",
                            f"example {slug!r} is pasted literally; "
                            f"use {{{{include-ex:{slug}}}}} instead")
                )

    # -- check 10: tier overrun -------------------------------------------
    for e in examples:
        budget = TIER_LINE_BUDGET[e["tier"]]
        source = EXAMPLES_ROOT / e["path"]
        printed = len(source.read_text(encoding="utf-8").strip("\n").split("\n"))
        if printed > budget:
            problems.append(
                Problem(10, "error", f"examples/{e['path']}",
                        f"{printed} printed lines exceeds the {e['tier']} budget of {budget}")
            )

    # -- check 13: figures are drawn, rendered, and placed ------------------
    # The rendered SVG and PDF are committed, so a contributor without
    # mermaid-cli can still build the book — which also means a stale or
    # missing render is invisible until someone opens the PDF and finds a
    # missing-image box. This is the check that makes it visible instead.
    for figure in figures:
        slug = figure["slug"]
        for suffix in (".svg", ".pdf"):
            artifact = FIGURES_OUT / f"{slug}{suffix}"
            if not artifact.exists():
                problems.append(
                    Problem(13, "error", f"figures/index.yaml",
                            f"{slug}: figures/out/{slug}{suffix} has not been rendered; "
                            f"run `python3 build.py figures`")
                )
        where = placements.get(slug, [])
        if not where:
            problems.append(
                Problem(13, "warning", "figures/index.yaml",
                        f"{slug} is drawn and indexed but no chapter places it")
            )
        elif len(where) > 1:
            problems.append(
                Problem(13, "error", where[1],
                        f"{slug} is placed {len(where)} times; a figure is numbered "
                        f"where it appears, so it can appear only once")
            )
    for slug, wheres in placements.items():
        if slug not in figure_slugs:
            problems.append(
                Problem(13, "error", wheres[0],
                        f"{{{{include-fig:{slug}}}}} names a figure that is not in "
                        f"figures/index.yaml")
            )

    errors = [p for p in problems if p.severity == "error"]
    warnings = [p for p in problems if p.severity == "warning"]
    for problem in sorted(problems, key=lambda p: (p.check, p.where)):
        print(f"  {problem}")
    print(
        f"Structure: {len(entries)} files, {len(examples)} examples, "
        f"{len(anchors)} anchors, {len(references)} references — "
        f"{len(errors)} errors, {len(warnings)} warnings"
    )
    if errors:
        raise AssertionError(f"{len(errors)} structural errors")
    if strict and warnings:
        raise AssertionError(f"{len(warnings)} structural warnings (--strict)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--manifest", action="store_true")
    parser.add_argument("--localnet-smoke", action="store_true")
    parser.add_argument("--examples", action="store_true")
    parser.add_argument("--structure", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="--examples only: restrict to examples touched in the working tree",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="fail if manifest entries are still marked pending",
    )
    args = parser.parse_args()

    if args.all or args.manifest:
        check_manifest(strict=args.strict)
    if args.all or args.test:
        test()
    if args.all or args.compile:
        compile_contracts()
    if args.all or args.structure:
        check_structure(strict=args.strict)
    if args.examples:
        check_examples(changed_only=args.changed_only)
    if args.all or args.localnet_smoke:
        localnet_smoke()
    if not any(vars(args).values()):
        parser.print_help()


if __name__ == "__main__":
    main()
