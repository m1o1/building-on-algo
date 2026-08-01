#!/usr/bin/env python3
"""Per-example CI harness: every annotated example compiles (PUB-1).

Sources of truth:
  - chapters/*.md carry `<!-- example: examples/<topic>/<file>.py mode=M -->`
    annotations beside example captions;
  - each file under examples/ may also carry a `# book-example: mode=M` header
    (used when a file exists ahead of its chapter annotation).

Modes:
  compile       puyapy must compile the file
  compile-fail  puyapy must FAIL to compile the file
  script        client-side code: byte-compiled only (py_compile)
  unit          compile + run the sibling *_test.py under pytest
  localnet      end-to-end driver; only run with --localnet

Checks:
  - every chapter-annotated path exists on disk (else listed as MISSING)
  - every file on disk under examples/ is annotated somewhere (else ORPHAN)
  - each file passes its mode

Results are cached by content hash in build/example-cache.json.

Usage:
  uv run --group compile python scripts/compile_examples.py [--only PREFIX]
      [--localnet] [--no-cache]
"""

from __future__ import annotations

import hashlib
import json
import py_compile
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
CHAPTERS = ROOT / "chapters"
CACHE_FILE = ROOT / "build" / "example-cache.json"

ANNOT_RE = re.compile(r"<!--\s*example:\s*(examples/[\w/.-]+\.py)\s+mode=([\w-]+)\s*-->")
HEADER_RE = re.compile(r"^#\s*book-example:\s*mode=([\w-]+)", re.MULTILINE)
VALID_MODES = {"compile", "compile-fail", "script", "unit", "localnet"}


def chapter_annotations() -> dict[str, str]:
    modes: dict[str, str] = {}
    for f in sorted(CHAPTERS.glob("*.md")):
        for path, mode in ANNOT_RE.findall(f.read_text(encoding="utf-8")):
            if mode not in VALID_MODES:
                print(f"ERROR: {f.name}: invalid mode {mode!r} for {path}")
                sys.exit(2)
            prev = modes.get(path)
            if prev and prev != mode:
                print(f"ERROR: conflicting modes for {path}: {prev} vs {mode}")
                sys.exit(2)
            modes[path] = mode
    return modes


def file_mode(p: Path) -> str | None:
    m = HEADER_RE.search(p.read_text(encoding="utf-8")[:400])
    return m.group(1) if m else None


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def compile_one(p: Path) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as out:
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "puyapy",
                str(p),
                "--out-dir",
                out,
                "--target-avm-version",
                "12",
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
    return r.returncode == 0, (r.stderr or r.stdout).strip()[-2000:]


def run_mode(p: Path, mode: str, localnet: bool) -> tuple[str, str]:
    """Return (status, detail); status in ok|fail|skip."""
    if mode == "script":
        try:
            py_compile.compile(str(p), doraise=True)
            return "ok", ""
        except py_compile.PyCompileError as e:
            return "fail", str(e)[:500]
    if mode == "compile":
        ok, out = compile_one(p)
        return ("ok", "") if ok else ("fail", out)
    if mode == "compile-fail":
        ok, out = compile_one(p)
        return ("ok", "") if not ok else ("fail", "compiled but was expected to fail")
    if mode == "unit":
        ok, out = compile_one(p)
        if not ok:
            return "fail", out
        test = p.with_name(p.stem + "_test.py")
        if not test.exists():
            return "fail", f"unit mode but no {test.name}"
        r = subprocess.run(
            [sys.executable, "-m", "pytest", str(test), "-q"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        return ("ok", "") if r.returncode == 0 else ("fail", r.stdout[-1500:])
    if mode == "localnet":
        if not localnet:
            return "skip", "needs --localnet"
        r = subprocess.run(
            [sys.executable, str(p)], capture_output=True, text=True, cwd=ROOT
        )
        return ("ok", "") if r.returncode == 0 else ("fail", (r.stderr or r.stdout)[-1500:])
    return "fail", f"unknown mode {mode}"


def main() -> int:
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1]
    localnet = "--localnet" in sys.argv
    use_cache = "--no-cache" not in sys.argv

    cache: dict[str, str] = {}
    if use_cache and CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text())

    annots = chapter_annotations()
    disk = {
        str(p.relative_to(ROOT))
        for p in EXAMPLES.rglob("*.py")
        if "__pycache__" not in p.parts
        and not p.stem.endswith("_test")
        and p.name != "__init__.py"
    }

    missing = sorted(set(annots) - disk)
    orphans = sorted(p for p in disk if p not in annots and not file_mode(ROOT / p))

    failures: list[str] = []
    ran = skipped = cached = 0
    for rel in sorted(disk):
        if only and not rel.startswith(only) and only not in rel:
            continue
        p = ROOT / rel
        mode = annots.get(rel) or file_mode(p)
        if not mode:
            continue
        key = f"{rel}:{mode}:{sha(p)}"
        if use_cache and cache.get(key) == "ok":
            cached += 1
            continue
        status, detail = run_mode(p, mode, localnet)
        if status == "ok":
            cache[key] = "ok"
            ran += 1
            print(f"  ok [{mode}] {rel}")
        elif status == "skip":
            skipped += 1
        else:
            failures.append(f"{rel} [{mode}]: {detail}")
            print(f"FAIL [{mode}] {rel}\n     {detail.splitlines()[-1] if detail else ''}")

    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=0))

    for m in missing:
        print(f"MISSING (annotated, not on disk): {m}")
    for o in orphans:
        print(f"ORPHAN (on disk, no annotation/header): {o}")

    print(
        f"\n{ran} ran, {cached} cached, {skipped} skipped, {len(failures)} failed, "
        f"{len(missing)} missing, {len(orphans)} orphans"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
