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
FIGURES_SRC = FIGURES_ROOT / "src"

# Check 21 tests the builder's own caption composition rather than a copy of
# it, so it needs the real function. Imported lazily inside a try so that this
# script still runs its other twenty checks if `build.py` is unimportable --
# a broken builder should produce one clear failure here, not twenty spurious
# ones everywhere else.
sys.path.insert(0, str(ROOT))
try:
    from build import figure_caption as _figure_caption
except Exception:  # pragma: no cover - reported by check 21 itself
    _figure_caption = None

# The one spelling of the elided-TEAL marker. Every LogicError transcript in
# the book cuts its trace under this exact line; check 19 enforces it.
TRACE_MARKER = "    ... 10 lines of TEAL trace ..."


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

# `script` is the client-side mode: a deployment or driver program that runs on
# the developer's machine, not on the AVM. Feeding one to puyapy is a category
# error, so it is byte-compiled instead. The Completeness Contract still holds
# --- the file on disk is a whole program, not a fragment.
EXAMPLE_MODES = {"compile", "compile-fail", "unit", "localnet", "script"}
# `minibuild` is the per-chapter Mini-Build: §2.4 sets it at 30-90 lines, which
# is deliberately larger than any micro-example. It is a tier so that check 10
# still bounds it instead of exempting it.
EXAMPLE_TIERS = {"core", "extended", "minibuild"}


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

            if mode == "script":
                # Client-side program: byte-compile it. This catches syntax
                # errors and nothing else, which is honest -- executing it
                # would need a funded LocalNet and a generated typed client
                # that only exists inside a project directory.
                byte = subprocess.run(
                    [sys.executable, "-m", "py_compile", str(source)],
                    cwd=ROOT, text=True, capture_output=True, check=False,
                )
                if byte.returncode != 0:
                    failures.append(
                        f"{slug}: script does not byte-compile\n      "
                        f"{(byte.stdout + byte.stderr).strip()[-400:]}"
                    )
                else:
                    passed += 1
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
# §2.6, the two house rules that were honoured by hand through Phase 4 and are
# machine-checked from Phase 5a on.
#
# MAX_FENCE_LINES caps the *fence*, never the artifact. A 90-line Mini-Build is
# legal; presenting it as one unbroken 90-line block is not, because that block
# is precisely the thing a reader skips. Split it and put prose between the
# halves — which is what §2.4 asks for anyway. The escape hatch is an explicit
# `{.long}` on the fence's info string, for the rare listing that genuinely
# cannot be cut (a full ARC-56 JSON, a disassembly).
MAX_FENCE_LINES = 50
# MAX_UNPROMPTED_LINES is the density floor: a reader should never travel this
# far without something that asks them to do rather than read. The plan says
# "~120", and the tilde is load-bearing — this is reported as a warning, since
# a hard error on an approximate rule teaches authors to pad rather than to
# engage. PROMPT_LINE_RE is what counts as engagement: a section break, a
# callout, a table, a numbered caption, a placed figure, an exercise, a predict
# prompt, or a block quote.
MAX_UNPROMPTED_LINES = 120
PROMPT_LINE_RE = re.compile(
    r"^(?:#{2,6}\s"
    r"|:::"
    r"|\|"
    r"|(?:Table|Figure|Example):\s"
    r"|\{\{include-fig:"
    r"|\d+\.\s+\*\*\("
    r"|\*Predict"
    r"|>\s"
    r")"
)
# Wrapping is a property of the content, not the author's patience: prose-ish
# fences (ASCII diagrams, JSON payloads, TEAL listings, terminal transcripts)
# are exempt wholesale because breaking their lines would corrupt them.
NOWRAP_LANGS = {"text", "json", "teal", "console", "output", ""}
TIER_LINE_BUDGET = {"core": 35, "extended": 20, "minibuild": 90}

# Check 4 stays registered but disabled until Phase 5 folds A1-cookbook.md into
# the need-shaped chapters. Flipping this to True is the last act of Phase 5.
# The callout vocabulary, kept in step with build.py's CALLOUT_LABEL and the
# tcolorbox environments in chapters/metadata.yaml. Eight kinds of aside plus
# .gotcha, which Phase 3 populates and harvests into an appendix.
CALLOUT_CLASSES = {
    "note", "tip", "warning", "gotcha", "setup",
    "spec", "version", "check", "tryit",
}
# A callout may carry pandoc attributes after its class. .gotcha always does --
# an id, a topic, and a title -- because the gotcha appendix is generated from
# them (build.py harvest_gotchas). Everything after the class is metadata for
# the harvester; neither renderer prints it.
CALLOUT_OPEN_RE = re.compile(r"^::: \{\.([a-z]+)(?:\s[^}]*)?\}$")
CALLOUT_ANY_OPEN_RE = re.compile(r"^:::\s*\S")

# The two below are build.py's harvester regexes, copied deliberately rather
# than imported: this check exists to catch input the harvester mis-parses, and
# a checker that shares the parser cannot see the mis-parse. The value pattern
# is [^"]* — it has no notion of an escaped inner quote, so
#     title="the \"free\" read"
# matches as far as `the \`, and everything after it becomes residue the
# harvester silently drops. The appendix then ships a title cut off mid-phrase,
# and check 14 stays green, because both sides of that comparison are generated
# from the same truncation. Nothing else in the toolchain would ever say so.
GOTCHA_OPEN_ATTRS_RE = re.compile(r"^::: \{\.gotcha\b(?P<attrs>[^}]*)\}$")
GOTCHA_ATTR_RE = re.compile(
    r'#(?P<id>[a-z0-9][a-z0-9-]*)|(?P<key>[a-z]+)="(?P<val>[^"]*)"'
)

COOKBOOK_RETIRED = False
COOKBOOK_FILE = "A4-cookbook.md"


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


def _fence_blocks(text: str):
    """Yield one [(line_no, line), ...] list per code fence.

    Check 19 needs the whole fence at once, not a line and its successor: a
    missing marker is a property of the transcript's *extent*, and the line
    where it should have been says nothing on its own.
    """
    block = None
    for i, line in enumerate(text.split("\n"), start=1):
        if line.strip().startswith("```"):
            if block is None:
                block = []
            else:
                yield block
                block = None
            continue
        if block is not None:
            block.append((i, line))
    if block:
        yield block


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
                # A .gotcha's attributes are not decoration -- they are the
                # only input to the generated appendix. Anything the harvester
                # cannot parse is discarded without a word, so parse it here
                # the same way and insist that nothing is left over.
                gotcha = GOTCHA_OPEN_ATTRS_RE.match(stripped)
                if gotcha:
                    attrs = gotcha.group("attrs")
                    residue = GOTCHA_ATTR_RE.sub("", attrs).strip()
                    if residue:
                        detail = (
                            'an attribute value cannot contain an escaped quote'
                            if '\\"' in attrs else
                            "unparsable attribute text"
                        )
                        problems.append(
                            Problem(12, "error", f"{rel}:{line_no}",
                                    f"gotcha attributes do not parse: {detail}; "
                                    f"the harvester would silently drop {residue!r}")
                        )
        if depth:
            problems.append(
                Problem(12, "error", rel, f"{depth} callout(s) left unclosed")
            )

        # -- check 15: single-fence length (§2.6) --------------------------
        # An error in chapters written under this rule, a warning in the ones
        # that predate it and are contracted by the remaining sub-phases. The
        # test for "written under this rule" is the chapter's own content, not
        # a flag someone has to remember to set: a restructured chapter shows
        # its artifact broken before it fixes it (§2.4), so a `## The
        # Mini-Build` heading is the marker, and it cannot go stale. Warning
        # rather than exempting keeps the outstanding work visible in every
        # run instead of only in the plan.
        restructured = re.search(r"^## The Mini-Build", text, re.MULTILINE) is not None
        if is_chapter:
            for open_line, info, body in _fences(text):
                if "{.long}" in info:
                    continue
                if len(body) > MAX_FENCE_LINES:
                    problems.append(
                        Problem(15, "error" if restructured else "warning",
                                f"{rel}:{open_line}",
                                f"fenced block is {len(body)} lines, over the "
                                f"{MAX_FENCE_LINES}-line cap; split it with prose "
                                f"between the halves, or mark the fence {{.long}}")
                    )

        # -- check 16: prompt density (§2.6) ------------------------------
        if is_chapter:
            run_start = 1
            run = 0
            for line_no, line in enumerate(text.split("\n"), 1):
                if PROMPT_LINE_RE.match(line.strip()):
                    run = 0
                    run_start = line_no + 1
                    continue
                run += 1
                if run > MAX_UNPROMPTED_LINES:
                    problems.append(
                        Problem(16, "warning", f"{rel}:{run_start}",
                                f"{run} lines with no prompt, table, figure, callout "
                                f"or exercise (soft limit {MAX_UNPROMPTED_LINES})")
                    )
                    run = 0
                    run_start = line_no + 1

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
        elif ns == "ex":
            # {{ex:slug}} prints a NUMBER ("Example 3-7"), and a number only
            # exists where a caption anchor mints one. build.py's _ref() dies
            # with SystemExit on an ex: reference that has no anchor, so
            # resolving this against examples/index.yaml alone would let a
            # green validator hand a broken book to the renderer. The stricter
            # rule wins; index membership is checked separately below so the
            # two failure modes report differently.
            known = key in anchors
            if not known and slug in example_slugs:
                for where in wheres:
                    problems.append(
                        Problem(1, "error", where,
                                f"{{{{ex:{slug}}}}} is registered in examples/index.yaml "
                                f"but no chapter mints {{#ex:{slug}}} — an example is "
                                f"numbered by its caption line, so this reference has no "
                                f"number to print. Add the caption where the example is "
                                f"placed, or cite the file by path instead.")
                    )
                continue
        elif ns == "include-ex":
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

    # -- check 1 (continued): every ex: anchor names a registered example ---
    # The reverse of the rule above. A caption that mints {#ex:slug} for a slug
    # examples/index.yaml has never heard of numbers something CI does not
    # compile, which is exactly the drift the Completeness Contract exists to
    # prevent — the number looks authoritative and nothing is checking it.
    for key, where in anchors.items():
        ns, _, slug = key.partition(":")
        if ns == "ex" and slug not in example_slugs:
            problems.append(
                Problem(1, "error", where,
                        f"caption mints {{#ex:{slug}}} but no such slug is registered "
                        f"in examples/index.yaml — the example would be numbered "
                        f"without ever being compiled")
            )

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

    # -- check 10: tier overrun, and check 7 on example sources ------------
    # Check 7 above scans code *fences* in chapters, which means it never sees
    # examples/**, even though every one of those files is transcluded into the
    # book verbatim and is printed under the same measure. Reuse the read.
    for e in examples:
        budget = TIER_LINE_BUDGET[e["tier"]]
        source = EXAMPLES_ROOT / e["path"]
        text = source.read_text(encoding="utf-8")
        lines = text.strip("\n").split("\n")
        if len(lines) > budget:
            problems.append(
                Problem(10, "error", f"examples/{e['path']}",
                        f"{len(lines)} printed lines exceeds the {e['tier']} "
                        f"budget of {budget}")
            )
        for offset, code_line in enumerate(lines, start=1):
            if len(code_line) > MAX_CODE_LINE:
                problems.append(
                    Problem(7, "error", f"examples/{e['path']}:{offset}",
                            f"code line is {len(code_line)} chars "
                            f"(limit {MAX_CODE_LINE}); wrap it")
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

    # -- check 21: a figure caption reaches the page as it was written --------
    # Checks 13 and 3 cover a figure's existence and its number; nothing
    # covered its *text*, and that gap shipped. `build.py`'s `_place_figure`
    # composed the caption as
    #
    #     f"{info['display']}. {info['title']}".rstrip(". ")
    #
    # and `str.rstrip` takes a set of characters rather than a suffix, so it
    # deleted the caption's own terminal period from all 21 entries -- every
    # figure in the book, in every build, for as long as the line existed. No
    # check saw it because every check was asking whether the figure was there,
    # not what it said. So this one compares the composed caption against
    # `figures/index.yaml` character for character and reports any difference.
    #
    # IT CALLS `build.figure_caption`, IT DOES NOT REIMPLEMENT IT. That
    # function was lifted to module level in `build.py` for this check, and the
    # reason is that a check which recomposes the caption itself is testing its
    # own copy: the copy would be written correctly, would pass forever, and
    # would say nothing about what the builder does. The first draft of this
    # check did exactly that -- `composed = f"Figure X-Y. {caption}"` followed
    # by `composed.endswith(caption)`, an assertion that is true by
    # construction and can never fire. Calling the real function is what makes
    # the check able to fail.
    #
    # Not written against `Building-on-Algorand.md` either. The concatenated
    # manuscript is build output; it may be absent and it may be stale, and a
    # check that quietly passes when its input is missing is worse than no
    # check. Calling the composition directly means this runs on a bare clone.
    #
    # The period rule is a house-style rule (`publishing-pro.md`: a caption is
    # a sentence and ends like one) and is enforced on the source entry rather
    # than on the composition, so the message points at the line an author
    # would edit.
    if _figure_caption is None:
        problems.append(
            Problem(21, "error", "build.py",
                    "build.figure_caption could not be imported, so caption "
                    "fidelity is unchecked; fix the import before trusting a "
                    "clean run")
        )
    for figure in figures if _figure_caption is not None else []:
        slug = figure["slug"]
        source_caption = str(figure.get("caption", ""))
        if not source_caption.strip():
            problems.append(
                Problem(21, "error", "figures/index.yaml",
                        f"{slug}: caption is empty; every figure carries one, and it "
                        f"lives here rather than in the chapter that places it")
            )
            continue
        if not source_caption.rstrip().endswith("."):
            problems.append(
                Problem(21, "error", "figures/index.yaml",
                        f"{slug}: caption does not end in a period -- a caption is a "
                        f"sentence and is punctuated as one "
                        f"(...{source_caption.rstrip()[-40:]!r})")
            )
        # `display` is computed at build time from where the placement sits, so
        # a representative one stands in here; the invariant under test is not
        # about the number but about whether the caption text survives having a
        # number put in front of it, which is exactly what `rstrip` broke.
        written = source_caption.strip()
        composed = _figure_caption("Figure 4-2", written)
        if not composed.endswith(written):
            problems.append(
                Problem(21, "error", "figures/index.yaml",
                        f"{slug}: build.py composes this caption as {composed[-48:]!r}, "
                        f"which does not end with the caption as written "
                        f"({written[-48:]!r}) -- the builder is altering caption text "
                        f"rather than only prefixing the figure number")
            )
        if source_caption.strip().lower().startswith("figure"):
            problems.append(
                Problem(21, "error", "figures/index.yaml",
                        f"{slug}: caption opens with {source_caption.strip()[:16]!r}; "
                        f"the number and the word `Figure` are prefixed at build time "
                        f"from where the figure is placed, so writing them here "
                        f"doubles them on the page")
            )

    # -- check 14: the generated gotcha appendix has not drifted -------------
    # chapters/A3-gotchas.md is derived from every ::: {.gotcha} callout in the
    # book, and it is committed rather than built on demand, for the same
    # reason figures/out/ is: someone who only wants to render the book should
    # not have to run a generation step first. Committed derived output goes
    # stale unless something notices, so this is the something. It also
    # surfaces every hard failure the harvester raises -- unknown topic,
    # missing title, duplicate id -- as one error rather than a traceback.
    try:
        sys.path.insert(0, str(ROOT))
        import build as _build  # noqa: PLC0415

        expected = _build.render_gotchas_appendix(_build.harvest_gotchas())
    except SystemExit as exc:
        problems.append(Problem(14, "error", "chapters/", str(exc)))
    else:
        target = CHAPTERS_DIR / _build.GOTCHA_APPENDIX_FILE
        actual = target.read_text(encoding="utf-8") if target.exists() else None
        if actual != expected:
            problems.append(
                Problem(14, "error", f"chapters/{_build.GOTCHA_APPENDIX_FILE}",
                        "generated gotcha appendix has drifted from its sources; "
                        "run `python3 build.py gotchas`")
            )

    # -- check 17: one transaction ID, one failure ---------------------------
    # Transaction IDs are globally unique, so the same elided ID appearing
    # twice in the book is the same transaction twice, and it cannot have
    # failed in two different applications or with two different messages.
    # Nothing else notices: the two sites are usually chapters apart, and one
    # of them is often a figure, which no other check reads at all. The
    # recorded instance is `J4KD...81XR`, used for an `assert failed` in
    # figures/src/simulate-trace.svg and for an unrelated failure in
    # chapters/05-c-numbers-and-time.md, introduced by a fix to the figure.
    #
    # Scope, stated rather than assumed: this harvests `chapters/` and
    # `figures/src/` only. `projects/`, `examples/` and `tests/` are code, not
    # transcripts, and are deliberately not read -- a contradiction there would
    # be a test failure, not a rendering defect.
    txid_re = re.compile(
        r"\b(?:[Tt]ransaction|Txn)\s+([A-Z0-9]{4}(?:\.\.\.)?[A-Z0-9]{3,})[:'\s]"
    )
    app_res = (re.compile(r"\bapp=(\d+)"), re.compile(r"\bappId:\s*(\d+)"))
    # Three discriminators, because the book has two transcript shapes and the
    # first version of this check only understood one of them. The algod form
    # spells out `logic eval error: MSG. Details: app=N, pc=N`; the dominant
    # form in the manuscript is what algokit-utils prints, `Txn ID had error
    # 'MSG' at PC N and Source Line M:`, which carries neither `logic eval
    # error:` nor `app=`. A check that harvests only the first is inert against
    # the corpus it was written for, which is what happened here.
    msg_res = (
        re.compile(r"logic eval error:\s*(.+?)\s*(?:\.\s*Details:|$)"),
        re.compile(r"rejected by logic err=\s*(.+?)\s*(?:\.\s*Details:|$)"),
        re.compile(r"had error\s*'(.+?)'\s*(?:at PC|$)"),
    )
    pc_re = re.compile(r"(?:\bpc=|\bat PC\s+)(\d+)")
    # id -> {"app": {value: where}, "msg": {value: where}, "pc": {value: where}}
    txids: dict[str, dict[str, dict[str, str]]] = {}

    def _harvest_txids(raw: str, rel: str) -> None:
        # Collapse the source to one line per ID so a transcript wrapped across
        # three lines -- or across three <text> elements in an SVG -- still
        # associates its ID with the app= and message that belong to it.
        flat = re.sub(r"<[^>]+>", " ", raw) if rel.endswith((".svg", ".mmd")) else raw
        for match in txid_re.finditer(flat):
            txid = match.group(1)
            line_no = flat.count("\n", 0, match.start()) + 1
            where = f"{rel}:{line_no}"
            window = re.sub(r"\s+", " ", flat[match.end():match.end() + 240])
            # Stop at the next *different* transaction ID so two adjacent
            # transcripts do not bleed into each other. It must be a different
            # one: the `Runtime error when executing X (appId: N) in
            # transaction ID: MSG` form names its own ID a second time inside
            # its own message, and truncating there cut every such transcript
            # off before its message closed.
            for nxt in txid_re.finditer(window):
                if nxt.group(1) != txid:
                    window = window[: nxt.start()]
                    break
            seen = txids.setdefault(txid, {"app": {}, "msg": {}, "pc": {}})
            for field, patterns in (("app", app_res), ("msg", msg_res)):
                for pattern in patterns:
                    hit = pattern.search(window)
                    if hit:
                        seen[field].setdefault(hit.group(1), where)
                        break
            pc = pc_re.search(window)
            if pc:
                seen["pc"].setdefault(pc.group(1), where)

    for entry in entries:
        path = CHAPTERS_DIR / entry["file"]
        if path.exists():
            _harvest_txids(path.read_text(encoding="utf-8"), f"chapters/{entry['file']}")
    if FIGURES_SRC.is_dir():
        for path in sorted(FIGURES_SRC.rglob("*")):
            if path.is_file():
                rel = path.relative_to(FIGURES_SRC).as_posix()
                _harvest_txids(path.read_text(encoding="utf-8", errors="replace"),
                               f"figures/src/{rel}")

    for txid, seen in sorted(txids.items()):
        for field, label in (("app", "app id"), ("msg", "failure message"),
                             ("pc", "program counter")):
            values = seen[field]
            if len(values) > 1:
                sites = "; ".join(f"{v!r} at {w}" for v, w in sorted(values.items()))
                problems.append(
                    Problem(17, "error", sorted(values.values())[0],
                            f"transaction {txid} is shown with {len(values)} different "
                            f"{label}s -- a transaction ID is globally unique, so these "
                            f"cannot both be it: {sites}")
                )

    # -- check 18: no format strings or agent placeholders in the prose -------
    # A Go format string is what the *source* says; the reader never sees a
    # `%d`. Quoting one inside a backtick span presents an unrenderable
    # literal as an error message, and it is invisible to every other check
    # because it is legal markdown. The recorded instance is
    # `write budget exceeded (%d > %d) while %s box %#x` in the zk-voting
    # chapter. `{TXID}` is the placeholder spelling used in .claude/agents/;
    # the manuscript's is `{id}`, and mixing them defeats the grep that audits
    # prefix coverage.
    # `%w` is in the verb class because the recorded go-algorand wrapper is
    # `transaction %v: %w`; an earlier version of this check omitted it and
    # would have passed that string. Three shapes are deliberately excluded,
    # none of which is a Go format string: a shell parameter expansion
    # (`${FILE%.svg}`), a percent-encoded run (`a%2F%3Ab.svg`) and a strftime
    # pattern (`%Y-%m-%d`). None appears in the corpus today -- the exclusions
    # are here so that adding one later does not produce a spurious error
    # someone then "fixes" by weakening the check.
    #
    # The strftime exclusion cannot be written as "a run of strftime letters
    # containing no Go verb", because `%d` is both: that formulation left
    # `%Y-%m-%d` firing. It is written instead as a property of the run's verb
    # set -- *every* verb is a strftime letter and *at least one* is exclusive
    # to strftime. `%Y-%m-%d` is excluded because `%Y` and `%m` are strftime
    # and nothing else, which is what licenses reading the `%d` beside them as
    # a day rather than an integer. `%G %s` is not excluded: `%s` is not a
    # strftime letter at all, so the run fails the *every* half. `%e %d` is
    # not excluded either, and that is the deliberately conservative case --
    # `e`, `b`, `p`, `U` and `G` are strftime letters that read too easily as
    # something else, so they are held out of the exclusive set and cannot on
    # their own license the exclusion. The three exclusions are stripped *per
    # run*, not per line. An earlier version
    # skipped the whole line on any strftime hit, so one `%Y-%m-%d` in a caption
    # silenced both this check and the `{TXID}` check for everything else on
    # that line; an exclusion that widens to the line is a hole, and
    # `(%d > %d)` next to a date went straight through it.
    #
    # A strftime run is two or more `%X` pairs joined by at most two characters
    # of punctuation. It is stripped only when *every* verb in it is a letter
    # strftime uses and *at least one* is a letter Go's fmt does not use. Both
    # halves are load-bearing, and the reason is the overlap: `d`, `b`, `e`,
    # `p`, `U`, `G`, `s`, `w`, `x`, `X` are claimed by both notations. Requiring
    # every verb to be a strftime letter is what stops `transaction %p: %w`
    # from being eaten (`w` is not one); requiring one strftime-only letter is
    # what stops `%e %d` from being eaten (neither is exclusive). Without both,
    # a real format string disappears from the corpus and the check goes quiet
    # about it -- which is the same shape as the line-level exclusion this
    # replaced, only narrower.
    span_re = re.compile(r"`[^`\n]+`")
    fmt_re = re.compile(r"%[-+#]?[0-9.]*[dsvxXqtwf]")
    shell_re = re.compile(r"\$\{[^}]*\}")
    strftime_run_re = re.compile(r"(?:%[a-zA-Z][^%a-zA-Z0-9]{0,2}){2,}")
    pct_encoded_run_re = re.compile(r"(?:%[0-9A-Fa-f]{2}){2,}")
    verb_re = re.compile(r"%([a-zA-Z])")
    STRFTIME_LETTERS = set("YmdHMSjaAbBpZeIkyCGuUVWnrTFD")
    STRFTIME_ONLY = STRFTIME_LETTERS - set("dsvxXqtwf") - set("bepUG")

    def _is_strftime_run(run: str) -> bool:
        verbs = verb_re.findall(run)
        return (bool(verbs)
                and all(v in STRFTIME_LETTERS for v in verbs)
                and any(v in STRFTIME_ONLY for v in verbs))

    def _strip_exclusions(text: str) -> str:
        text = shell_re.sub("", text)
        text = pct_encoded_run_re.sub("", text)
        return strftime_run_re.sub(
            lambda m: "" if _is_strftime_run(m.group(0)) else m.group(0), text)

    def _format_string_hits(line: str):
        for span in span_re.findall(line):
            probe = _strip_exclusions(span)
            if fmt_re.search(probe):
                yield span

    for entry in entries:
        path = CHAPTERS_DIR / entry["file"]
        if not path.exists():
            continue
        rel = f"chapters/{entry['file']}"
        for line_no, line in _outside_fences(path.read_text(encoding="utf-8")):
            for hit in _format_string_hits(line):
                problems.append(
                    Problem(18, "error", f"{rel}:{line_no}",
                            f"format string in a backtick span: {hit} -- quote what the "
                            f"tool prints, not the format string that produces it")
                )
            if "{TXID}" in line:
                problems.append(
                    Problem(18, "error", f"{rel}:{line_no}",
                            "{TXID} is the .claude/agents/ placeholder spelling; "
                            "the manuscript's is {id}")
                )
    # Figures are the recorded source of this defect family and have no fences,
    # so every line is scanned. A raw `%d` outside a backtick span counts here:
    # an SVG has no inline-code markup, so the backtick heuristic that keeps
    # chapter prose honest would let a figure through untouched.
    if FIGURES_SRC.is_dir():
        for path in sorted(FIGURES_SRC.rglob("*")):
            if not path.is_file():
                continue
            rel = f"figures/src/{path.relative_to(FIGURES_SRC).as_posix()}"
            text = path.read_text(encoding="utf-8", errors="replace")
            for line_no, line in enumerate(text.split("\n"), start=1):
                probe = _strip_exclusions(line)
                hit = fmt_re.search(probe)
                if hit:
                    problems.append(
                        Problem(18, "error", f"{rel}:{line_no}",
                                f"format string in a figure: {hit.group(0)} -- a figure's "
                                f"quoted strings are held to the manuscript's standard; "
                                f"render the literal, not the verb that produces it")
                    )
                if "{TXID}" in line:
                    problems.append(
                        Problem(18, "error", f"{rel}:{line_no}",
                                "{TXID} is the .claude/agents/ placeholder spelling; "
                                "the manuscript's is {id}")
                    )

    # -- check 19: an elided TEAL trace is marked where it was cut ------------
    # The book's convention is that a `LogicError` transcript shows the
    # message's first line and then the ten lines of generated TEAL the real
    # exception prints, cut under a visible marker. Eleven transcripts shipped
    # at d845ff3 without a correct marker, failing in two ways: four carried a
    # marker of the wrong spelling (`12 lines`, `9 lines`, `11 lines`,
    # `9 lines`), two ended on the trailing colon of `... at PC N:` with no
    # marker at all -- leaving the fence ending mid-sentence on the
    # exception's own promise of the trace -- and the remaining five simply
    # had nothing where the marker belonged. (The four misspelled ones are the
    # transcripts that end on `and Source Line N:`; do not swap those two
    # shapes, as an earlier revision of this comment did.)
    #
    # The check therefore has to see four things, and the first version saw
    # only the third of them. (1) PRESENCE: every transcript inside a fence
    # gets exactly one marker, measured over the transcript's whole extent,
    # because a marker that is simply absent leaves no line to inspect.
    # (2) FINALITY: that marker is the transcript's last non-blank line -- a
    # marker sitting above the message says the wrong block was cut.
    # (3) POSITION: a line ending on the `and Source Line {n}:` colon is
    # followed immediately by the marker. A bare `at PC {n}:` colon is
    # reported too, but it is the no-source-map spelling: `logic_error.py`
    # `:83-84` emits it on exactly the `line_no is None` branch whose
    # `trace()` returns the "Could not determine TEAL source line" advisory
    # (`:89-95`) instead of TEAL, so nothing was elided there and the fix is
    # to restore the missing `and Source Line {n}:` clause, not to add the
    # marker. See `.claude/agents/algorand-verified-facts.md`'s entry
    # requiring every transcript in this book to carry the clause and a real
    # ten-line trace.
    # (4) SPELLING: any line that reads like the marker is byte-identical
    # to it.
    #
    # Presence is the part that matters. The first version tested (3) alone,
    # passed six deliberate injections, and still reported only six of the
    # eleven shipped defects, because none of the other five ended on a colon.
    # An injection that only ever perturbs a line the check already looks at
    # cannot show that the check looks in enough places. The test that settles
    # it is running the finished check against `git archive HEAD chapters`.
    #
    # Two boundaries are load-bearing and were both established by running the
    # widened check over the corpus rather than by reasoning about it. A
    # transcript is opened only by `LogicError:` as the line's first non-space
    # text, or by a pytest report's `E   LogicError:`; a *raw algod* string
    # quoted without the Python exception around it opens nothing, because the
    # ten TEAL lines are a client-side artifact that algokit-utils appends from
    # a source map it kept -- the node prints none of them, so
    # `chapters/07-c-proving-it-works.md:522` is right to carry no marker
    # and demanding one there is a false positive. And the extent ends at the
    # next opener, the next *prompt* line, or the end of the fence: three
    # transcripts, in two REPL fences, continue with a further command after
    # the marker, so without the prompt boundary rule (2) would fire on all
    # three.
    #
    # Note that only (1) and (2) are scoped to a recognised transcript. (3) and
    # (4) are a sibling loop over every line of every fence, transcript or not,
    # and that is deliberate: a misspelled marker or a fence ending on either
    # of those colons is a defect wherever it appears, and neither needs an
    # opener to be judged. Descriptions of this check in `CLAUDE.md` and
    # `.claude/agents/publishing-pro.md` say the same; if you change the
    # scoping, change all three.
    logicerr_open_re = re.compile(r"^(?:E\s+)?LogicError:")
    prompt_re = re.compile(r"^(?:>>>|\$|In \[\d+\]:)")
    srcline_re = re.compile(r"(?:Source Line \d+|at PC \d+):\s*$")
    marker_like_re = re.compile(r"\.\.\..*TEAL trace")
    for entry in entries:
        path = CHAPTERS_DIR / entry["file"]
        if not path.exists():
            continue
        rel = f"chapters/{entry['file']}"
        for block in _fence_blocks(path.read_text(encoding="utf-8")):
            # Split the fence into transcripts. `except LogicError as err:` and
            # `from ... import LogicError` are Python source, not output, and
            # start no transcript, which is why the opener must lead the line.
            starts = [i for i, (_, line) in enumerate(block)
                      if logicerr_open_re.match(line.lstrip())]
            for n, start in enumerate(starts):
                end = starts[n + 1] if n + 1 < len(starts) else len(block)
                for j in range(start + 1, end):
                    if prompt_re.match(block[j][1].lstrip()):
                        end = j
                        break
                extent = block[start:end]
                markers = [k for k, (_, line) in enumerate(extent)
                           if line == TRACE_MARKER]
                where = f"{rel}:{block[start][0]}"
                if len(markers) != 1:
                    problems.append(
                        Problem(19, "error", where,
                                f"a LogicError transcript carries {len(markers)} "
                                f"copies of the elided-trace marker, not 1 -- every "
                                f"transcript cuts its trace under exactly one "
                                f"{TRACE_MARKER.strip()!r}")
                    )
                    continue
                last = max(k for k, (_, line) in enumerate(extent) if line.strip())
                if markers[0] != last:
                    problems.append(
                        Problem(19, "error", where,
                                f"the elided-trace marker is at {rel}:"
                                f"{extent[markers[0]][0]} but the transcript runs to "
                                f"{rel}:{extent[last][0]} -- the marker stands where "
                                f"the trace was cut, which is below the message, not "
                                f"above it")
                    )
            for i, (line_no, line) in enumerate(block):
                nxt = block[i + 1][1] if i + 1 < len(block) else None
                m_src = srcline_re.search(line)
                if m_src:
                    # The bare `at PC N:` shape is reported whatever follows
                    # it. Guarding it on `nxt != TRACE_MARKER` would let the
                    # one fix this branch exists to forbid -- appending the
                    # marker -- silence the error instead of persisting it.
                    if (m_src.group(0).startswith("at PC")
                            or nxt is None or nxt != TRACE_MARKER):
                        shown = "the end of the fence" if nxt is None \
                            else repr(nxt.strip()[:48])
                        if m_src.group(0).startswith("at PC"):
                            # The no-source-map spelling. Nothing was elided
                            # here, so appending the marker would fabricate a
                            # trace algokit-utils never printed.
                            problems.append(
                                Problem(19, "error", f"{rel}:{line_no}",
                                        f"a fenced line ends on a bare 'at PC N:' "
                                        f"colon -- that is the spelling used when "
                                        f"the client had no source map, and what "
                                        f"follows it upstream is the 'Could not "
                                        f"determine TEAL source line' advisory, not "
                                        f"TEAL; restore the ' and Source Line N:' "
                                        f"clause rather than adding "
                                        f"{TRACE_MARKER.strip()!r}")
                            )
                        else:
                            problems.append(
                                Problem(19, "error", f"{rel}:{line_no}",
                                        f"a fenced line ends on its Source Line "
                                        f"colon but the next line is {shown} -- the "
                                        f"elided TEAL trace must be marked with "
                                        f"{TRACE_MARKER.strip()!r}")
                            )
                if marker_like_re.search(line) and line != TRACE_MARKER:
                    problems.append(
                        Problem(19, "error", f"{rel}:{line_no}",
                                f"elided-trace marker is spelled {line.strip()!r} -- "
                                f"the one spelling is {TRACE_MARKER.strip()!r}, and the "
                                f"count in it is the trace length the exception prints, "
                                f"not a number chosen per transcript")
                    )

    # --- Check 20: a block element needs a blank line above it ------------
    #
    # Pandoc's markdown, unlike CommonMark, does not let a heading or a list
    # interrupt a paragraph. With no blank line above it, a `### Heading` is
    # simply the paragraph's last line and a `- item` is simply more of its
    # last sentence. Both then render as body prose. A swallowed heading
    # appears in no table of contents, sets no running head and carries no
    # anchor for a cross-reference to land on; a swallowed list arrives as a
    # single run-on paragraph with stray hyphens or digits where the bullets
    # were -- `The generated LogicSig verifier: - Has a deterministic address
    # ... - Signs an application call transaction - Reads proof bytes from`.
    #
    # Nothing else in this file notices, because every other structural check
    # reads the block list pandoc already parsed, and that is precisely the
    # list this defect removes the element from. The check has to read the
    # raw line.
    #
    # EVERY CARVE-OUT AND EVERY EXTENSION BELOW WAS SETTLED BY RUNNING THE
    # SHAPE THROUGH PANDOC. An earlier version of this comment justified two
    # of them from memory and got both backwards, which is why each one now
    # carries the command that decided it.
    #
    # Carved out, because pandoc parses them correctly:
    #
    #     printf '## Exercises\n1. **(Trace)** first\n' | pandoc -t html
    #         -> <h2 ...>Exercises</h2><ol><li>...
    #   A heading is its own block and closes itself, so a list directly
    #   beneath one still parses. The book has fifteen `## Exercises`
    #   sections; eight open with a blank line and seven -- the seven concept
    #   chapters, `01-c` through `07-c` -- put the numbered list directly
    #   under the heading. All seven are correct.
    #
    #   Without this carve-out the check fires on all seven. On the corpus as
    #   it stood when the check was written it reported thirteen in total,
    #   seven of them these false ones and six of them real, so 54% noise --
    #   and a check that is more than half noise gets switched off within a
    #   round. Reproduce either number by replacing `heading_re.match(
    #   prev_line)` in `closes_own_block()` with `False`: against today's
    #   tree, whose six real ones are fixed, the count is 7 and the noise is
    #   all of it.
    #
    #     printf 'Intro.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n- item\n'
    #         | pandoc -t html   -> <table>...</table><ul><li>item</li></ul>
    #     printf '::: {.note}\n- item\n:::\n'
    #         | pandoc -t html   -> <div class="note"><ul><li>item</li></ul>
    #   A table row and a callout fence do end their own block.
    #
    #     printf 'Para.\n\n```python\nx=1\n```\n- a\n' | pandoc -t html
    #         -> ...<pre>...</pre><ul><li>a</li></ul>
    #   So does a closing code fence -- and the fence delimiter is a non-blank
    #   previous line, so without this carve-out both branches fire on it.
    #
    #   ALL FOUR APPLY TO BOTH BRANCHES, which is why they live in
    #   `closes_own_block()` below rather than beside the list test. The first
    #   version of this check put three of the four inside the list branch and
    #   left the heading branch with only the closing fence, so
    #   `printf '## Parent\n### Child\n' | pandoc -t html` -- which sets
    #   `<h2>` then `<h3>`, both real -- was reported as a swallowed heading.
    #   A carve-out is a property of the PREVIOUS line, so it cannot belong to
    #   one branch.
    #
    # NOT carved out, because pandoc does NOT parse them correctly:
    #
    #     printf 'Intro.\n\n> quoted\n- item one\n- item two\n' | pandoc -t html
    #         -> <blockquote><p>quoted - item one - item two</p></blockquote>
    #   A blockquote does not close itself; the list is lazily continued into
    #   it and the bullets set as literal hyphens. `>` used to be carved out
    #   here alongside `|` and `:::`, on the stated grounds that all three
    #   "end their own block". Two of them do.
    #
    #     printf 'Intro para.\nHeading text\n============\n' | pandoc -t html
    #         -> <p>Intro para. Heading text ============</p>
    #   Setext obeys the SAME blank-line rule as ATX, not the opposite one,
    #   and is swallowed identically -- so the underline prints literally. The
    #   `-` form is worse: it sets as an em dash inside the paragraph, which
    #   is invisible even to a reader who knows to look. Flagged on the
    #   underline line, and only when the text above the underline is itself
    #   a paragraph continuation; a blank line two rows up, or a block that
    #   closed itself there, makes it a real heading.
    #
    #     printf 'Intro para.\nHeading text\n-\n' | pandoc -t html
    #         -> <p>Intro para. Heading text -</p>
    #   A SINGLE hyphen is a Setext underline (`printf 'Heading text\n-\n'`
    #   alone sets an `<h2>`), so it is swallowed like any other. The pattern
    #   asked for `-{2,}` and missed it, and no other pattern here covers a
    #   bare `-` either.
    #
    #     printf 'Intro para.\n    - item one\n' | pandoc -t html
    #         -> <p>Intro para. - item one</p>
    #   Four spaces of indent does not make it a nested list when there is no
    #   parent item; it is still swallowed. The bullet pattern therefore
    #   allows any indent, and it is the PREVIOUS line -- unindented ordinary
    #   paragraph text -- that decides, since a list under an indented line
    #   really is a nesting or a lazy continuation.
    #
    # Both branches run outside code fences only, since a leading `#` or `-`
    # in a shell or YAML fence is a comment or an item and there are hundreds
    # of each, and never at line 1.
    #
    # This is a formatting gate, so it is described in `CLAUDE.md` and in
    # `.claude/agents/publishing-pro.md` as well as here, exactly as check 19
    # is; if you change the carve-outs or the shapes covered, change all three.
    #
    # All four shapes in the "NOT carved out" list occur zero times in the
    # corpus today, so widening to them moved no count. They are latent
    # traps, and the reason to close them now is that the same root cause --
    # a block element that needs a blank line above it and did not get one --
    # has already produced two different surfaces in this book, and the check
    # written for the surface that was seen did not find the other.
    #
    # Run over all 24 chapters it found six real instances, every one of them
    # present at `d845ff3`: the heading at `10-p-zk-voting.md:597` and five
    # lists (`07-p-yield-farming.md`, `08-c-patterns.md`,
    # `09-p-limit-order-book.md`, and two in `10-p-zk-voting.md`). Six hits
    # is the argument for the check rather than against it -- the rendered
    # page looks like prose that was always prose, which is how these got
    # past five review rounds and a rasterize-and-read pass.
    heading_re = re.compile(r"^#{1,6} \S")
    bullet_re = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])\s+\S")
    fence_re = re.compile(r"^\s*(```|~~~)")
    # `-` needs no repetition: `printf 'Heading text\n-\n' | pandoc -t html`
    # sets an `<h2>`, so a single hyphen is a Setext underline and is
    # swallowed by a paragraph above it exactly as `---` is. `-{2,}` missed it
    # and a bare `-` matches `bullet_re` no better, since a list marker needs
    # whitespace and content after it -- so nothing saw the shape at all. The
    # widening cannot add a false positive for the same reason.
    setext_re = re.compile(r"^(=+|-+)\s*$")

    def closes_own_block(prev_line: str) -> bool:
        """True where pandoc ends the previous block, so what follows parses.

        All four shapes were run through pandoc; the commands are in the
        comment above. This is shared by both branches deliberately: an
        earlier version tested the heading, table-row and callout carve-outs
        inside the list branch only, so `### Child` directly under `## Parent`
        -- which pandoc sets as a real `<h3>` -- was reported as swallowed.
        Zero occurrences today, but the docs described the carve-outs as
        applying to the check rather than to one of its two branches.
        """
        return bool(
            heading_re.match(prev_line)
            or fence_re.match(prev_line)
            or prev_line.lstrip().startswith(("|", ":::"))
        )

    for entry in entries:
        path = CHAPTERS_DIR / entry["file"]
        if not path.exists():
            continue
        rel = f"chapters/{entry['file']}"
        lines = path.read_text(encoding="utf-8").split("\n")
        in_fence = False
        for i, line in enumerate(lines):
            if fence_re.match(line):
                in_fence = not in_fence
                continue
            if in_fence or i == 0:
                continue
            prev = lines[i - 1]
            if not prev.strip():
                continue
            # Every carve-out is checked before either branch, because all
            # four are properties of the previous line rather than of the
            # element being judged.
            if closes_own_block(prev):
                continue
            # A Setext underline under text that is itself a paragraph
            # continuation: the heading was swallowed and the underline
            # prints as literal `=` signs or as an em dash. The line that
            # decides is two above, not one: `prev` is the heading's own text,
            # so it is `lines[i - 2]` that has to be paragraph text rather
            # than a block that closed itself.
            if (setext_re.match(line) and i >= 2 and lines[i - 2].strip()
                    and not closes_own_block(lines[i - 2])):
                problems.append(
                    Problem(20, "error", f"{rel}:{i + 1}",
                            f"Setext underline {line.strip()[:20]!r} under "
                            f"{prev.strip()[:40]!r}, which is itself a "
                            f"continuation of the paragraph above it -- pandoc "
                            f"reads all three as one paragraph and prints the "
                            f"underline as body text; a blank line above "
                            f"{prev.strip()[:24]!r} makes it the heading it "
                            f"was meant to be")
                )
                continue
            if heading_re.match(line):
                problems.append(
                    Problem(20, "error", f"{rel}:{i + 1}",
                            f"heading {line.strip()[:52]!r} has no blank line above "
                            f"it, so it is parsed as the last line of the preceding "
                            f"paragraph -- it will not appear in the table of "
                            f"contents, will set no running head, and will carry no "
                            f"anchor")
                )
                continue
            if not bullet_re.match(line):
                continue
            # A list continuing, or a line indented enough that this item is a
            # nesting or a lazy continuation of it. This one stays in the list
            # branch: an indented previous line does not rescue a heading.
            if bullet_re.match(prev) or prev.startswith((" ", "\t")):
                continue
            problems.append(
                Problem(20, "error", f"{rel}:{i + 1}",
                        f"list item {line.strip()[:46]!r} has no blank line above "
                        f"it, so pandoc folds the whole list into the preceding "
                        f"paragraph and the bullets render as literal hyphens or "
                        f"digits in running prose")
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
