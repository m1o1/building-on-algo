import pytest
import algokit_utils

from scripts.localnet_helpers import (
    advance_time,
    create_test_asa,
    fund_account,
    require_localnet,
)


@pytest.fixture(scope="session")
def algorand() -> algokit_utils.AlgorandClient:
    client = algokit_utils.AlgorandClient.default_localnet()
    try:
        require_localnet(client)
    except RuntimeError as exc:
        pytest.skip(str(exc))
    return client


@pytest.fixture(scope="session")
def admin(algorand: algokit_utils.AlgorandClient):
    return algorand.account.localnet_dispenser()
