from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.localnet_helpers import get_localnet_algorand


@pytest.fixture(scope="session")
def algorand():
    try:
        return get_localnet_algorand()
    except Exception as exc:
        message = str(exc)
        if (
            "LocalNet is not reachable" in message
            or "Failed to connect" in message
            or "Max retries exceeded" in message
        ):
            pytest.skip("LocalNet is not running")
        raise
