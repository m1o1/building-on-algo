"""Checks for the repository validation manifest."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "validation" / "manifest.json"
KNOWN_STATUSES = {"active", "pending", "pending-pr", "pending-extraction"}
PENDING = {"pending", "pending-pr", "pending-extraction"}


def load_manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_manifest_active_targets_exist() -> None:
    manifest = load_manifest()
    for item in manifest["compiled_contracts"]:
        if item.get("status", "active") in PENDING:
            continue
        assert (ROOT / item["path"]).exists(), item["path"]
    for item in manifest["high_risk_flows"]:
        if item.get("status", "active") in PENDING:
            continue
        test_file = item["test"].split("::", 1)[0]
        assert (ROOT / test_file).exists(), item["test"]


def test_manifest_status_values_are_known() -> None:
    manifest = load_manifest()
    for section in (
        "compiled_contracts",
        "high_risk_flows",
        "localnet_smoke",
        "coverage_summary",
    ):
        for item in manifest.get(section, []):
            assert item.get("status", "active") in KNOWN_STATUSES


def test_pending_entries_have_tracking_notes() -> None:
    manifest = load_manifest()
    pending_items = []
    for section in (
        "compiled_contracts",
        "high_risk_flows",
        "localnet_smoke",
        "coverage_summary",
    ):
        pending_items.extend(
            item for item in manifest.get(section, [])
            if item.get("status", "active") in PENDING
        )
    assert pending_items, "manifest should expose remaining validation gaps"
    for item in pending_items:
        assert (
            item.get("notes")
            or item.get("issue")
            or item.get("pr")
            or item.get("pending_gaps")
        )


def test_validation_commands_are_declared() -> None:
    commands = load_manifest()["commands"]
    for name in ("unit", "manifest", "compile", "all", "strict"):
        assert name in commands
        assert commands[name].startswith("uv run")
