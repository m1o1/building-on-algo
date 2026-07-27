"""The fast half of the suite: schedule arithmetic, no LocalNet.

This applies the `unit_test_context` pattern from the testing chapter.
`algorand-python-testing` runs the contract as ordinary Python against an
in-memory ledger, so a four-year vesting schedule is a series of
assignments to `latest_timestamp` rather than four years of waiting.

What this file can cover: everything downstream of `calculate_vested`,
and the authorization checks on methods whose bodies do not need an AVM
(`create_schedule`, `revoke`, `cleanup_schedule`, `reject_lifecycle`).
What it cannot cover: box MBR, grouped payments, inner transactions, and
the asset opt-in. Those need a real AVM and live in
`test_token_vesting.py`, which is why `claim` is absent here -- its
authorization check is reachable, but nothing past it is.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from algopy import Account, OnCompleteAction, UInt64, arc4
from algopy_testing import algopy_testing_context

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smart_contracts.token_vesting.contract import (  # noqa: E402
    TokenVesting,
    VestingSchedule,
    calculate_vested,
)

NOW = 1_700_000_000
DAY = 24 * 60 * 60
YEAR = 365 * DAY
CLIFF = 90 * DAY
DURATION = 4 * YEAR
GRANT = 1_000_000_000_000  # 1,000,000 tokens at six decimals


# --- calculate_vested, the curve on its own ---------------------------------


def test_nothing_vests_before_the_cliff() -> None:
    with algopy_testing_context():
        vested = calculate_vested(
            UInt64(GRANT),
            UInt64(NOW),
            UInt64(NOW + CLIFF),
            UInt64(NOW + DURATION),
            UInt64(NOW + CLIFF - 1),
        )
        assert vested == 0


def test_the_cliff_releases_a_lump_sum_measured_from_start() -> None:
    """The linear term measures from `start`, not from `cliff_end`.

    So arriving at the cliff pays out the whole first ninety days at
    once rather than starting a ramp from zero.
    """
    with algopy_testing_context():
        vested = calculate_vested(
            UInt64(GRANT),
            UInt64(NOW),
            UInt64(NOW + CLIFF),
            UInt64(NOW + DURATION),
            UInt64(NOW + CLIFF),
        )
        assert vested == GRANT * CLIFF // DURATION
        assert vested > 0


def test_the_full_grant_vests_at_the_end_and_stays_there() -> None:
    with algopy_testing_context():
        for offset in (0, DAY, 100 * YEAR):
            vested = calculate_vested(
                UInt64(GRANT),
                UInt64(NOW),
                UInt64(NOW + CLIFF),
                UInt64(NOW + DURATION),
                UInt64(NOW + DURATION + offset),
            )
            assert vested == GRANT


def test_the_curve_floors_so_dust_stays_in_the_contract() -> None:
    """Never more than the exact fraction, and at most one unit less."""
    with algopy_testing_context():
        for elapsed in (CLIFF, YEAR, YEAR + 1, 3 * YEAR, DURATION - 1):
            vested = calculate_vested(
                UInt64(GRANT),
                UInt64(NOW),
                UInt64(NOW + CLIFF),
                UInt64(NOW + DURATION),
                UInt64(NOW + elapsed),
            )
            assert int(vested) == GRANT * elapsed // DURATION
            assert int(vested) * DURATION <= GRANT * elapsed


def test_a_grant_that_would_overflow_a_narrow_multiply_still_works() -> None:
    """`total * elapsed` overflows here; `mulw` into `divmodw` does not.

    MAX_UINT64 // (DURATION - 1) is 146,235,605,498, so any grant above
    that aborts a narrow multiply somewhere in the back half of the
    schedule. This one is four orders of magnitude past it.
    """
    huge = 1_000_000_000_000_000  # 1e15 base units
    assert huge * (DURATION - 1) > 2**64 - 1
    with algopy_testing_context():
        vested = calculate_vested(
            UInt64(huge),
            UInt64(NOW),
            UInt64(NOW + CLIFF),
            UInt64(NOW + DURATION),
            UInt64(NOW + DURATION // 2),
        )
        assert vested == huge * (DURATION // 2) // DURATION


# --- the contract, with the ledger's clock under test control ---------------


def _initialized(ctx, asset_id: int = 1001) -> TokenVesting:
    """A contract past `create`, with `initialize`'s state written by hand.

    `create` runs for real, because the whole point of `create="require"`
    is that it runs exactly once and that is worth exercising. `initialize`
    does not, because its job is an inner opt-in transaction against a real
    asset -- exactly the half of the contract a unit test cannot reach.
    The LocalNet suite covers that; this file starts from the state it
    would have left.
    """
    ctx.ledger.patch_global_fields(latest_timestamp=UInt64(NOW))
    contract = TokenVesting()
    app = ctx.ledger.get_app(contract)
    with ctx.txn.create_group([ctx.any.txn.application_call(app_id=app)]):
        contract.create()
    contract.asset_id.value = UInt64(asset_id)
    contract.is_initialized.value = UInt64(1)
    contract.available_tokens.value = UInt64(10 * GRANT)
    return contract


def _schedule(contract: TokenVesting, who: Account) -> None:
    """Write a schedule directly, bypassing the grouped MBR payment.

    The MBR payment is exactly the part a unit test cannot exercise, so
    this helper writes what `create_schedule` would have written and
    leaves the group-shape assertions to the LocalNet suite.
    """
    contract.schedules[who] = VestingSchedule(
        total_amount=arc4.UInt64(GRANT),
        claimed_amount=arc4.UInt64(0),
        start_time=arc4.UInt64(NOW),
        cliff_end=arc4.UInt64(NOW + CLIFF),
        vesting_end=arc4.UInt64(NOW + DURATION),
        is_revoked=arc4.Bool(False),
    )
    contract.available_tokens.value -= UInt64(GRANT)
    contract.beneficiary_count.value += UInt64(1)


def test_get_claimable_tracks_the_clock() -> None:
    with algopy_testing_context() as ctx:
        contract = _initialized(ctx)
        bob = ctx.any.account()
        _schedule(contract, bob)

        assert contract.get_claimable(bob) == 0

        ctx.ledger.patch_global_fields(
            latest_timestamp=UInt64(NOW + DURATION // 2)
        )
        half = contract.get_claimable(bob)
        assert half == GRANT * (DURATION // 2) // DURATION

        ctx.ledger.patch_global_fields(
            latest_timestamp=UInt64(NOW + DURATION)
        )
        assert contract.get_claimable(bob) == GRANT


def test_a_beneficiary_with_no_schedule_is_refused() -> None:
    with algopy_testing_context() as ctx:
        contract = _initialized(ctx)
        stranger = ctx.any.account()
        with pytest.raises(AssertionError, match="No schedule"):
            contract.get_claimable(stranger)


def test_a_stranger_cannot_create_a_schedule() -> None:
    """`Txn.sender` is the admin only because `create` ran as the creator."""
    with algopy_testing_context() as ctx:
        contract = _initialized(ctx)
        stranger = ctx.any.account()
        beneficiary = ctx.any.account()
        payment = ctx.any.txn.payment(
            sender=stranger,
            receiver=ctx.ledger.get_app(contract).address,
            amount=UInt64(32_500),
        )
        with ctx.txn.create_group(
            [
                payment,
                ctx.any.txn.application_call(
                    app_id=ctx.ledger.get_app(contract), sender=stranger
                ),
            ]
        ):
            with pytest.raises(AssertionError, match="Only admin"):
                contract.create_schedule(
                    beneficiary,
                    UInt64(GRANT),
                    UInt64(CLIFF),
                    UInt64(DURATION),
                    payment,
                )


def test_a_stranger_cannot_revoke() -> None:
    with algopy_testing_context() as ctx:
        contract = _initialized(ctx)
        bob = ctx.any.account()
        _schedule(contract, bob)
        stranger = ctx.any.account()
        with ctx.txn.create_group(
            [
                ctx.any.txn.application_call(
                    app_id=ctx.ledger.get_app(contract), sender=stranger
                )
            ]
        ):
            with pytest.raises(AssertionError, match="Only admin"):
                contract.revoke(bob)


def test_cleanup_refuses_a_schedule_that_is_not_fully_claimed() -> None:
    """Permissionless is not the same as unguarded.

    The `raises` here is deliberately unpinned: the fully-claimed guard in
    `cleanup_schedule` carries no assert message, so there is no string to
    match on. That is a gap in the contract rather than in the test --
    see the chapter's discussion of messageless asserts.
    """
    with algopy_testing_context() as ctx:
        contract = _initialized(ctx)
        bob = ctx.any.account()
        _schedule(contract, bob)
        with pytest.raises(AssertionError):
            contract.cleanup_schedule(bob)


@pytest.mark.parametrize(
    "action",
    [OnCompleteAction.UpdateApplication, OnCompleteAction.DeleteApplication],
)
def test_the_contract_refuses_updates_and_deletes(action) -> None:
    """`reject_lifecycle` claims both actions in order to refuse them.

    A method that did not claim them would be refused by the router with
    no message at all; this one is reached and then fails on purpose.

    Note what this does and does not prove. Calling the method directly
    bypasses the router, so the parametrized on-completion value only
    satisfies the emulator's routing precondition -- it does not exercise
    dispatch. That the router refuses *unclaimed* actions is a LocalNet
    assertion, and lives in `test_token_vesting.py`.
    """
    with algopy_testing_context() as ctx:
        contract = _initialized(ctx)
        app = ctx.ledger.get_app(contract)
        with ctx.txn.create_group(
            [ctx.any.txn.application_call(app_id=app, on_completion=action)]
        ):
            with pytest.raises(AssertionError, match="Contract is immutable"):
                contract.reject_lifecycle()


def test_revoke_caps_the_total_and_freezes_the_curve() -> None:
    """After revocation the beneficiary keeps what had vested, exactly."""
    with algopy_testing_context() as ctx:
        contract = _initialized(ctx)
        bob = ctx.any.account()
        _schedule(contract, bob)

        halfway = NOW + DURATION // 2
        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(halfway))
        vested_at_revocation = int(contract.get_claimable(bob))

        unvested = contract.revoke(bob)
        assert int(unvested) == GRANT - vested_at_revocation

        # A year later the beneficiary is owed the same amount and no more:
        # `revoke` set cliff_end and vesting_end to the revocation time, so
        # the curve is frozen rather than re-applied to the capped total.
        ctx.ledger.patch_global_fields(latest_timestamp=UInt64(halfway + YEAR))
        assert int(contract.get_claimable(bob)) == vested_at_revocation


def test_a_schedule_cannot_be_revoked_twice() -> None:
    with algopy_testing_context() as ctx:
        contract = _initialized(ctx)
        bob = ctx.any.account()
        _schedule(contract, bob)
        ctx.ledger.patch_global_fields(
            latest_timestamp=UInt64(NOW + DURATION // 2)
        )
        contract.revoke(bob)
        with pytest.raises(AssertionError, match="Already revoked"):
            contract.revoke(bob)
