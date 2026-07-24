# tests/test_simple_vesting_unit.py
import pytest
from algopy_testing import algopy_testing_context
from algopy import UInt64, OnCompleteAction

from tests.contracts.simple_vesting import (
    SimpleVesting,
)


class TestVestingMath:
    """Unit tests for the vesting calculation logic."""

    def test_before_cliff_returns_zero(self):
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            contract.total_amount.value = (
                UInt64(1_000_000)
            )
            contract.claimed_amount.value = UInt64(0)
            contract.start_time.value = UInt64(100)
            contract.cliff_end.value = UInt64(200)
            contract.vesting_end.value = UInt64(1000)

            ctx.ledger.patch_global_fields(
                latest_timestamp=150
            )
            result = contract.get_claimable()
            assert result == 0

    def test_midway_vesting(self):
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            contract.total_amount.value = (
                UInt64(1_000_000)
            )
            contract.claimed_amount.value = UInt64(0)
            contract.start_time.value = UInt64(0)
            contract.cliff_end.value = UInt64(0)
            contract.vesting_end.value = UInt64(1000)

            ctx.ledger.patch_global_fields(
                latest_timestamp=500
            )
            result = contract.get_claimable()
            # 1_000_000 * 500 / 1000 = 500_000
            assert result == 500_000

    def test_after_end_returns_total(self):
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            contract.total_amount.value = (
                UInt64(1_000_000)
            )
            contract.claimed_amount.value = UInt64(0)
            contract.start_time.value = UInt64(100)
            contract.cliff_end.value = UInt64(200)
            contract.vesting_end.value = UInt64(1000)

            ctx.ledger.patch_global_fields(
                latest_timestamp=2000
            )
            result = contract.get_claimable()
            assert result == 1_000_000

    def test_floor_division_rounds_down(self):
        """Integer division should favor the contract
        (beneficiary gets slightly less)."""
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            contract.total_amount.value = (
                UInt64(1_000_000)
            )
            contract.claimed_amount.value = UInt64(0)
            contract.start_time.value = UInt64(0)
            contract.cliff_end.value = UInt64(0)
            contract.vesting_end.value = UInt64(3)

            ctx.ledger.patch_global_fields(
                latest_timestamp=1
            )
            result = contract.get_claimable()
            # 1_000_000 / 3 = 333_333.33... -> 333_333
            assert result == 333_333

    def test_immutability_rejects_update(self):
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction
                        .UpdateApplication
                    )
                }
            ):
                with pytest.raises(
                    AssertionError,
                    match="immutable",
                ):
                    contract.reject_lifecycle()
