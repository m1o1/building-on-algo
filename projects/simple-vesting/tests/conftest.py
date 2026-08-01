from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    import algokit_utils


@pytest.fixture(scope="session")
def algorand() -> algokit_utils.AlgorandClient:
    # Imported lazily: scripts.localnet_helpers pulls in the generated
    # typed client, which only exists after `algokit project run build`,
    # and algokit_utils is only needed for LocalNet-backed tests.
    # The algopy_testing unit tests need neither the artifacts nor
    # LocalNet, so these imports must not run at collection time.
    import algokit_utils
    from scripts.localnet_helpers import require_localnet

    client = algokit_utils.AlgorandClient.default_localnet()
    try:
        require_localnet(client)
    except RuntimeError as exc:
        pytest.skip(str(exc))
    return client


@pytest.fixture(scope="session")
def admin(algorand: algokit_utils.AlgorandClient):
    return algorand.account.localnet_dispenser()
