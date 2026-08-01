"""Chapter 13's donation attack, run against both pools.

The unlocked pool is drained end to end. The locked pool still floors to
zero once the donation is large enough -- which is the point: the lock
raises the attacker's price, and only the `minted > 0` guard closes the door.
"""

import pytest
from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.pricing.first_depositor import MINIMUM_LIQUIDITY, Mint
from examples.pricing.first_depositor_unlocked import Mint as UnlockedMint

VICTIM_DEPOSIT = 10_000_000


def test_unlocked_pool_swallows_the_second_deposit() -> None:
    with algopy_testing_context():
        pool = UnlockedMint()
        pool.open(UInt64(1))
        pool.donate(UInt64(VICTIM_DEPOSIT))

        assert pool.join(UInt64(VICTIM_DEPOSIT)) == 0
        assert pool.supply.value == 1
        assert pool.reserve.value == 1 + 2 * VICTIM_DEPOSIT
        # The attacker holds the only share and redeems both deposits.
        assert pool.redeem(UInt64(1)) == 1 + 2 * VICTIM_DEPOSIT


def test_locked_pool_still_floors_but_refuses() -> None:
    with algopy_testing_context():
        pool = Mint()
        pool.open(UInt64(MINIMUM_LIQUIDITY + 1))
        # The lock multiplies the donation the attack needs by the locked
        # minimum: about 1,001 x the victim's deposit, not 1 x it.
        pool.donate(UInt64(VICTIM_DEPOSIT * (MINIMUM_LIQUIDITY + 1)))

        with pytest.raises(AssertionError, match="deposit too small for this pool"):
            pool.join(UInt64(VICTIM_DEPOSIT))
        assert pool.supply.value == MINIMUM_LIQUIDITY + 1


def test_locked_pool_credits_an_ordinary_deposit() -> None:
    with algopy_testing_context():
        pool = Mint()
        pool.open(UInt64(MINIMUM_LIQUIDITY + 1))
        assert pool.join(UInt64(VICTIM_DEPOSIT)) == VICTIM_DEPOSIT
