"""Repository validation harness.

The harness keeps generated compiler output out of the source tree by writing
PuyaPy artifacts to a temporary directory.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "validation" / "manifest.json"


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--compile", action="store_true")
    parser.add_argument("--manifest", action="store_true")
    parser.add_argument("--localnet-smoke", action="store_true")
    parser.add_argument("--all", action="store_true")
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
    if args.all or args.localnet_smoke:
        localnet_smoke()
    if not any(vars(args).values()):
        parser.print_help()


if __name__ == "__main__":
    main()
