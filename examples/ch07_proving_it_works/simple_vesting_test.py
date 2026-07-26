"""The Mini-Build's tests. All seven pass, and that is the point.

Four exercise the repaired contract. The three `test_the_broken_*`
cases pin the defects in place against the broken one: they pass
because they assert what that contract actually does, which is exactly
the shape a suite takes when it was written by reading the contract
instead of the requirement.
"""

import pytest
from algopy import Account, UInt64
from algopy_testing import AlgopyTestContext, algopy_testing_context

from examples.ch07_proving_it_works.simple_vesting_broken import (
    SimpleVesting as BrokenVesting,
)
from examples.ch07_proving_it_works.simple_vesting_fixed import SimpleVesting

START = 1_700_000_000
YEAR = 365 * 24 * 60 * 60
SMALL_TOTAL = 4_000_000
# Ten billion tokens at six decimals. Real supplies reach this; the
# narrow formula stops working an order of magnitude below it.
BIG_TOTAL = 10_000_000_000 * 10**6


def _configure(
    ctx: AlgopyTestContext,
    contract: SimpleVesting | BrokenVesting,
    beneficiary: Account,
    total: int,
) -> None:
    """Put the contract in the state `initialize` would have left it in."""
    contract.beneficiary.value = beneficiary
    contract.asset_id.value = UInt64(1001)
    contract.total.value = UInt64(total)
    contract.start.value = UInt64(START)
    contract.cliff.value = UInt64(START + YEAR)
    contract.end.value = UInt64(START + 4 * YEAR)
    ctx.ledger.patch_global_fields(latest_timestamp=UInt64(START))


def test_nothing_is_claimable_before_the_cliff() -> None:
    with algopy_testing_context() as ctx:
        contract = SimpleVesting()
        _configure(ctx, contract, ctx.default_sender, SMALL_TOTAL)
        ctx.ledger.patch_global_fields(
            latest_timestamp=UInt64(START + YEAR - 1)
        )
        assert contract.claimable() == 0


def test_a_claim_after_the_cliff_pays_the_elapsed_share() -> None:
    with algopy_testing_context() as ctx:
        contract = SimpleVesting()
        _configure(ctx, contract, ctx.default_sender, SMALL_TOTAL)
        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(START + YEAR))
        assert contract.claim() == SMALL_TOTAL // 4
        assert contract.claimed.value == SMALL_TOTAL // 4


def test_a_claim_that_would_move_nothing_is_rejected() -> None:
    """The repaired contract refuses rather than reporting a zero payout."""
    with algopy_testing_context() as ctx:
        contract = SimpleVesting()
        _configure(ctx, contract, ctx.default_sender, SMALL_TOTAL)
        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(START + YEAR))
        contract.claim()
        with pytest.raises(AssertionError, match="nothing vested"):
            contract.claim()


def test_the_repaired_schedule_survives_a_production_supply() -> None:
    with algopy_testing_context() as ctx:
        contract = SimpleVesting()
        _configure(ctx, contract, ctx.default_sender, BIG_TOTAL)
        at_two_years = UInt64(START + 2 * YEAR)
        assert contract.vested(at_two_years) == BIG_TOTAL // 2


def test_the_broken_version_reports_success_for_a_claim_that_moved_nothing(
) -> None:
    """Defect 1, pinned: a second claim in the same second returns 0 and
    commits. Every assertion a caller could make about it holds."""
    with algopy_testing_context() as ctx:
        contract = BrokenVesting()
        _configure(ctx, contract, ctx.default_sender, SMALL_TOTAL)
        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(START + YEAR))
        contract.claim()
        assert contract.claim() == 0


def test_the_broken_version_rejects_a_stranger_without_saying_why() -> None:
    """Defect 3, pinned: the assertion has no message, so `AssertionError`
    arrives with an empty string where the reason should be."""
    with algopy_testing_context() as ctx:
        contract = BrokenVesting()
        _configure(ctx, contract, ctx.any.account(), SMALL_TOTAL)
        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(START + YEAR))
        with pytest.raises(AssertionError) as caught:
            contract.claim()
        assert str(caught.value) == ""


def test_the_broken_schedule_overflows_at_a_production_supply() -> None:
    """Defect 2, pinned. `algorand-python-testing` raises for exactly the
    operations that would abort on the AVM, so this is one line."""
    with algopy_testing_context() as ctx:
        contract = BrokenVesting()
        _configure(ctx, contract, ctx.default_sender, BIG_TOTAL)
        at_two_years = UInt64(START + 2 * YEAR)
        with pytest.raises(ArithmeticError):
            contract.vested(at_two_years)
