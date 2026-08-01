from __future__ import annotations

import pytest

from scripts.localnet_helpers import get_localnet_algorand, normalize_localnet_time


@pytest.fixture
def algorand():
    try:
        client = get_localnet_algorand()
    except RuntimeError as exc:
        pytest.skip(str(exc))
    # Whatever ran before this test may have left the developer-mode clock
    # jumping by a year a block. Park it at one second a block so each test
    # starts from a known clock.
    normalize_localnet_time(client)
    return client
