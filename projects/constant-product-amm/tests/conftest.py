from __future__ import annotations

import pytest

from scripts.localnet_helpers import get_localnet_algorand


@pytest.fixture
def algorand():
    try:
        return get_localnet_algorand()
    except RuntimeError as exc:
        pytest.skip(str(exc))
