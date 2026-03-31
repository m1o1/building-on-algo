"""Unit tests for the token vesting contract (Chapter 2).
Tests the calculate_vested subroutine and claim flow."""

import pytest
from algopy_testing import algopy_testing_context
from algopy import UInt64, arc4, Bytes, Account, OnCompleteAction

from tests.contracts.vesting import (
    TokenVesting,
    VestingSchedule,
    calculate_vested,
)


class TestCalculateVested:
    """Tests for the vesting math subroutine."""

    def test_before_cliff_returns_zero(self):
        with algopy_testing_context():
            result = calculate_vested(
                total=UInt64(1_000_000),
                start=UInt64(100),
                cliff_end=UInt64(200),
                vesting_end=UInt64(1000),
                now=UInt64(150),
            )
            assert result == 0

    def test_at_cliff_boundary_returns_nonzero(self):
        with algopy_testing_context():
            result = calculate_vested(
                total=UInt64(1_000_000),
                start=UInt64(100),
                cliff_end=UInt64(200),
                vesting_end=UInt64(1000),
                now=UInt64(200),
            )
            # elapsed=100, duration=900, vested = 1_000_000 * 100 / 900 = 111_111
            assert result == 111_111

    def test_after_vesting_end_returns_total(self):
        with algopy_testing_context():
            result = calculate_vested(
                total=UInt64(1_000_000),
                start=UInt64(100),
                cliff_end=UInt64(200),
                vesting_end=UInt64(1000),
                now=UInt64(2000),
            )
            assert result == 1_000_000

    def test_exactly_at_vesting_end_returns_total(self):
        with algopy_testing_context():
            result = calculate_vested(
                total=UInt64(1_000_000),
                start=UInt64(100),
                cliff_end=UInt64(200),
                vesting_end=UInt64(1000),
                now=UInt64(1000),
            )
            assert result == 1_000_000

    def test_midway_linear_vesting(self):
        with algopy_testing_context():
            result = calculate_vested(
                total=UInt64(1_000_000),
                start=UInt64(0),
                cliff_end=UInt64(0),
                vesting_end=UInt64(1000),
                now=UInt64(500),
            )
            assert result == 500_000

    def test_large_amount_no_overflow(self):
        """Test with 100M tokens at 6 decimals = 10^14 base units.
        This is the overflow scenario described in Chapter 2."""
        with algopy_testing_context():
            total = UInt64(100_000_000_000_000)  # 10^14
            one_year = UInt64(31_536_000)
            result = calculate_vested(
                total=total,
                start=UInt64(0),
                cliff_end=UInt64(0),
                vesting_end=one_year,
                now=UInt64(15_768_000),  # halfway
            )
            assert result == 50_000_000_000_000

    def test_floor_division_favors_contract(self):
        """Verify that integer division rounds down (contract keeps dust)."""
        with algopy_testing_context():
            result = calculate_vested(
                total=UInt64(1_000_000),
                start=UInt64(0),
                cliff_end=UInt64(0),
                vesting_end=UInt64(3),
                now=UInt64(1),
            )
            # 1_000_000 / 3 = 333_333.33... -> floor to 333_333
            assert result == 333_333


class TestTokenVestingContract:
    """Tests for the TokenVesting contract."""

    def test_create_sets_admin(self):
        with algopy_testing_context() as ctx:
            contract = TokenVesting()
            with ctx.txn.create_group(
                active_txn_overrides={"on_completion": OnCompleteAction.NoOp}
            ):
                contract.create()
            assert contract.admin.value == ctx.default_sender.bytes

    def test_get_claimable_before_cliff_is_zero(self):
        with algopy_testing_context() as ctx:
            contract = TokenVesting()
            with ctx.txn.create_group(
                active_txn_overrides={"on_completion": OnCompleteAction.NoOp}
            ):
                contract.create()
            beneficiary = ctx.any.account()
            schedule = VestingSchedule(
                total_amount=arc4.UInt64(1_000_000),
                claimed_amount=arc4.UInt64(0),
                start_time=arc4.UInt64(100),
                cliff_end=arc4.UInt64(200),
                vesting_end=arc4.UInt64(1000),
                is_revoked=arc4.Bool(False),
            )
            contract.schedules[beneficiary] = schedule.copy()
            ctx.ledger.patch_global_fields(latest_timestamp=150)
            result = contract.get_claimable(beneficiary)
            assert result == 0

    def test_get_claimable_past_cliff(self):
        with algopy_testing_context() as ctx:
            contract = TokenVesting()
            with ctx.txn.create_group(
                active_txn_overrides={"on_completion": OnCompleteAction.NoOp}
            ):
                contract.create()
            beneficiary = ctx.any.account()
            schedule = VestingSchedule(
                total_amount=arc4.UInt64(1_000_000),
                claimed_amount=arc4.UInt64(0),
                start_time=arc4.UInt64(100),
                cliff_end=arc4.UInt64(200),
                vesting_end=arc4.UInt64(1000),
                is_revoked=arc4.Bool(False),
            )
            contract.schedules[beneficiary] = schedule.copy()
            ctx.ledger.patch_global_fields(latest_timestamp=550)
            result = contract.get_claimable(beneficiary)
            # elapsed=450, duration=900, vested = 1_000_000*450/900 = 500_000
            assert result == 500_000

    def test_get_claimable_after_partial_claim(self):
        with algopy_testing_context() as ctx:
            contract = TokenVesting()
            with ctx.txn.create_group(
                active_txn_overrides={"on_completion": OnCompleteAction.NoOp}
            ):
                contract.create()
            beneficiary = ctx.any.account()
            schedule = VestingSchedule(
                total_amount=arc4.UInt64(1_000_000),
                claimed_amount=arc4.UInt64(200_000),
                start_time=arc4.UInt64(100),
                cliff_end=arc4.UInt64(200),
                vesting_end=arc4.UInt64(1000),
                is_revoked=arc4.Bool(False),
            )
            contract.schedules[beneficiary] = schedule.copy()
            ctx.ledger.patch_global_fields(latest_timestamp=550)
            result = contract.get_claimable(beneficiary)
            # vested=500_000, claimed=200_000, claimable=300_000
            assert result == 300_000

    def test_immutability_rejects_update(self):
        with algopy_testing_context() as ctx:
            contract = TokenVesting()
            with ctx.txn.create_group(
                active_txn_overrides={"on_completion": OnCompleteAction.NoOp}
            ):
                contract.create()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": OnCompleteAction.UpdateApplication
                }
            ):
                with pytest.raises(AssertionError, match="Immutable"):
                    contract.reject_lifecycle()
