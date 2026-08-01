"""The manuscript keeps its own promises: chapters/ vs scripts/spine.py.

Runs scripts/check_book.py's checks as a test. KNOWN_DEBT lists defects that
are already scheduled (BOOK-PLAN phase work); anything new fails immediately.
Prune entries as the phases land — an unused allowlist entry is itself flagged.
"""

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import check_book  # noqa: E402

# Defects the rewrite plan already owns. Format: exact error line from check_book.
# Empty since the Phase 3 integration agents landed; new entries need a phase owner.
KNOWN_DEBT: set[str] = set()


def test_generated_appendices_in_sync() -> None:
    """A3/A4 match what generate_appendices.py would write (PUB-7/PUB-14 [GEN])."""
    import generate_appendices as gen

    chapters = Path(__file__).resolve().parents[1] / "chapters"
    assert (chapters / "A3-gotchas.md").read_text(encoding="utf-8") == gen.generate_gotchas(), (
        "A3-gotchas.md drifted — edit the inline ::: {.gotcha} callouts and run "
        "python3 scripts/generate_appendices.py"
    )
    assert (chapters / "A4-example-finder.md").read_text(encoding="utf-8") == gen.generate_finder(), (
        "A4-example-finder.md drifted — edit the captions/finder comments and run "
        "python3 scripts/generate_appendices.py"
    )


def test_manuscript_integrity() -> None:
    buf = io.StringIO()
    with redirect_stdout(buf):
        check_book.main()
    lines = buf.getvalue().splitlines()
    errors = {line.removeprefix("ERROR: ") for line in lines if line.startswith("ERROR: ")}

    new_errors = errors - KNOWN_DEBT
    assert not new_errors, "new manuscript integrity errors:\n" + "\n".join(sorted(new_errors))

    stale_allowlist = KNOWN_DEBT - errors
    assert not stale_allowlist, (
        "fixed defects still allowlisted — prune KNOWN_DEBT:\n" + "\n".join(sorted(stale_allowlist))
    )
