"""Seven tests: four hold the repaired contract to its requirements, and
three document what the broken draft does --- the shape of a suite written
from the code, kept here as the chapter's exhibit."""

import pytest
from algopy import UInt64, arc4
from algopy_testing import AlgopyTestContext, algopy_testing_context

from examples.proving_it_works.simple_vesting_broken import (
    SimpleVesting as BrokenVesting,
)
from examples.proving_it_works.simple_vesting_fixed import (
    SimpleVesting as FixedVesting,
)

DAY = 86_400
CLIFF = 90 * DAY
DURATION = 360 * DAY
SUPPLY = 10_000_000 * 10**6  # a production supply: 10M tokens at 6 decimals


@pytest.fixture()
def ctx():  # type: ignore[no-untyped-def]
    with algopy_testing_context() as context:
        yield context


def _initialized(ctx: AlgopyTestContext, contract_cls, total: int):
    """Deploy-and-initialize against a deposit; returns (contract, beneficiary)."""
    contract = contract_cls()
    beneficiary = ctx.any.account()
    asset = ctx.any.asset(total=2 * total)
    deposit = ctx.any.txn.asset_transfer(
        asset_receiver=ctx.ledger.get_app(contract).address,
        xfer_asset=asset,
        asset_amount=UInt64(total),
    )
    contract.initialize(
        arc4.Address(beneficiary),
        UInt64(CLIFF),
        UInt64(DURATION),
        deposit,
    )
    return contract, beneficiary


def _at(ctx: AlgopyTestContext, when: int) -> None:
    ctx.ledger.patch_global_fields(latest_timestamp=UInt64(when))


# --- The repaired contract, held to the requirements -----------------------


def test_nothing_vests_before_the_cliff(ctx: AlgopyTestContext) -> None:
    _at(ctx, 1_000_000)
    contract, beneficiary = _initialized(ctx, FixedVesting, 1_000_000)
    _at(ctx, 1_000_000 + CLIFF - DAY)
    with ctx.txn.create_group(active_txn_overrides={"sender": beneficiary}):
        with pytest.raises(AssertionError, match="nothing vested"):
            contract.claim()


def test_the_linear_ramp_pays_the_elapsed_share(ctx: AlgopyTestContext) -> None:
    _at(ctx, 1_000_000)
    contract, beneficiary = _initialized(ctx, FixedVesting, 1_000_000)
    _at(ctx, 1_000_000 + DURATION // 2)
    with ctx.txn.create_group(active_txn_overrides={"sender": beneficiary}):
        paid = contract.claim()
    # The requirement: total * elapsed / duration, floored toward the pool.
    assert paid == 1_000_000 * (DURATION // 2) // DURATION


def test_a_claim_that_would_move_nothing_is_refused(ctx: AlgopyTestContext) -> None:
    _at(ctx, 1_000_000)
    contract, beneficiary = _initialized(ctx, FixedVesting, 1_000_000)
    _at(ctx, 1_000_000 + DURATION)
    with ctx.txn.create_group(active_txn_overrides={"sender": beneficiary}):
        assert contract.claim() == 1_000_000  # everything, exactly once
        with pytest.raises(AssertionError, match="nothing vested"):
            contract.claim()  # and never a silent zero after it


def test_a_stranger_is_rejected_by_name(ctx: AlgopyTestContext) -> None:
    _at(ctx, 1_000_000)
    contract, _ = _initialized(ctx, FixedVesting, 1_000_000)
    stranger = ctx.any.account()
    _at(ctx, 1_000_000 + DURATION)
    with ctx.txn.create_group(active_txn_overrides={"sender": stranger}):
        with pytest.raises(AssertionError, match="not the beneficiary"):
            contract.claim()


# --- The broken draft, documented (tests written from the code) ------------


def test_the_broken_version_reports_success_for_a_claim_that_moved_nothing(
    ctx: AlgopyTestContext,
) -> None:
    _at(ctx, 1_000_000)
    contract, beneficiary = _initialized(ctx, BrokenVesting, 1_000_000)
    _at(ctx, 1_000_000 + DAY)  # before the cliff: nothing is due
    with ctx.txn.create_group(active_txn_overrides={"sender": beneficiary}):
        assert contract.claim() == 0  # a "success" that should be a refusal


def test_the_broken_version_rejects_a_stranger_without_saying_why(
    ctx: AlgopyTestContext,
) -> None:
    _at(ctx, 1_000_000)
    contract, _ = _initialized(ctx, BrokenVesting, 1_000_000)
    stranger = ctx.any.account()
    with ctx.txn.create_group(active_txn_overrides={"sender": stranger}):
        with pytest.raises(AssertionError) as rejected:
            contract.claim()
    assert "beneficiary" not in str(rejected.value)  # bare assert: no message


def test_the_broken_schedule_overflows_at_a_production_supply(
    ctx: AlgopyTestContext,
) -> None:
    _at(ctx, 1_000_000)
    contract, beneficiary = _initialized(ctx, BrokenVesting, SUPPLY)
    _at(ctx, 1_000_000 + DURATION // 2)  # mid-ramp: total * elapsed > 2**64
    with ctx.txn.create_group(active_txn_overrides={"sender": beneficiary}):
        with pytest.raises(ArithmeticError):
            contract.claim()
