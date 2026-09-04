"""Compile the generated AlgoPlonk verifier LogicSig to TEAL.

`zk/cmd/gen-verifier` writes `zk/generated/VoteVerifier.py`, which is PuyaPy
source with the circuit's verifying key compiled into it. This turns it into
the TEAL the client signs with.

It is a separate step from `python -m smart_contracts build` for two reasons.
The verifier is a `@logicsig`, not an `ARC4Contract`, so it has no app spec and
no typed client, and the template build script only walks
`smart_contracts/*/contract.py`. And the output needs renaming: AlgoPlonk names
the logicsig `Verifier` inside the file, so puyapy writes `Verifier.teal` no
matter what the source file is called.

The committed `VoteVerifier.teal` is left alone unless you ask for it back.
It is a generated ZK artifact like `vote.proof` and `vote_circuit.vk`: produced
once, by a named command, and committed so a reader with no Go toolchain can
still run the trustless path. It also assembles to the exact 3,447 bytes the
chapter's Run It First table reports, and puyapy's output moves between
releases, so regenerating it on every build would make a measured number
depend on which puyapy the reader happened to install.

Run it from the project root:

    poetry run python -m scripts.build_verifier            # keep what is there
    poetry run python -m scripts.build_verifier --force    # recompile it
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED = PROJECT_ROOT / "zk" / "generated"
SOURCE = GENERATED / "VoteVerifier.py"
TARGET = GENERATED / "VoteVerifier.teal"

# The name AlgoPlonk gives the logicsig, and therefore the name puyapy gives
# its output. verifier.DefaultFileName in the Go module.
PUYAPY_OUTPUT_STEM = "Verifier"


def main(argv: list[str] | None = None) -> int:
    force = "--force" in (argv if argv is not None else sys.argv[1:])

    if TARGET.exists() and not force:
        print(
            f"{TARGET.name} is already present ({TARGET.stat().st_size} bytes of "
            "TEAL, 3,447 assembled); pass --force to recompile it from "
            f"{SOURCE.name}."
        )
        return 0

    if not SOURCE.exists():
        print(
            f"Missing {SOURCE}.\n"
            "Generate it first with `go run ./cmd/gen-verifier` from zk/, or "
            "check out the committed copy.",
            file=sys.stderr,
        )
        return 1

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "puyapy",
            "--out-dir",
            str(GENERATED),
            "--target-avm-version",
            "13",
            str(SOURCE),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    print(result.stdout, end="")
    if result.returncode:
        print(result.stderr, file=sys.stderr, end="")
        return result.returncode

    produced = GENERATED / f"{PUYAPY_OUTPUT_STEM}.teal"
    if not produced.exists():
        print(f"puyapy did not write {produced}", file=sys.stderr)
        return 1

    produced.replace(TARGET)
    for suffix in (".puya.map",):
        stale = GENERATED / f"{PUYAPY_OUTPUT_STEM}{suffix}"
        if stale.exists():
            stale.replace(GENERATED / f"VoteVerifier{suffix}")

    print(f"wrote {TARGET} ({TARGET.stat().st_size} bytes of TEAL)")
    print(
        "The verifier's address is the hash of this program, so re-run "
        "set_verifier on any live election."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
