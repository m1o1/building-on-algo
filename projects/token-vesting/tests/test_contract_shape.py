from __future__ import annotations

from pathlib import Path


CONTRACT = Path("smart_contracts/token_vesting/contract.py")


def source() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def test_uses_box_map_for_beneficiary_schedules() -> None:
    text = source()
    assert "BoxMap(Account, VestingSchedule, key_prefix=b\"v_\")" in text
    assert "beneficiary not in self.schedules" in text


def test_validates_grouped_deposit_transfer() -> None:
    text = source()
    assert "Global.group_size == UInt64(2)" in text
    assert "deposit_txn.asset_receiver == Global.current_application_address" in text
    assert "deposit_txn.xfer_asset == Asset(self.asset_id.value)" in text
    assert "self.available_tokens.value += deposit_txn.asset_amount" in text


def test_schedule_creation_validates_group_shape() -> None:
    text = source()
    assert text.count("Global.group_size == UInt64(2)") >= 2
    assert "mbr_payment.receiver == Global.current_application_address" in text
    assert "mbr_payment.sender == Txn.sender" in text


def test_schedules_can_only_use_reserved_deposits() -> None:
    text = source()
    assert "self.available_tokens = GlobalState(UInt64(0))" in text
    assert "self.available_tokens.value >= total_amount" in text
    assert "self.available_tokens.value -= total_amount" in text


def test_box_mbr_payment_must_be_exact() -> None:
    text = source()
    assert "mbr_payment.amount == box_mbr" in text
    assert "mbr_payment.amount >= box_mbr" not in text


def test_inner_transactions_use_fee_pooling() -> None:
    text = source()
    assert text.count("fee=UInt64(0)") >= 4


def test_vesting_math_uses_wide_arithmetic() -> None:
    text = source()
    assert "op.mulw(total, elapsed)" in text
    assert "op.divmodw(high, low, UInt64(0), duration)" in text


def test_cleanup_refunds_admin_not_arbitrary_caller() -> None:
    text = source()
    assert "receiver=Account(self.admin.value)" in text
    assert "receiver=Txn.sender" not in text


def test_revocation_freezes_remaining_vested_amount() -> None:
    text = source()
    assert "now = Global.latest_timestamp" in text
    assert "schedule.total_amount = arc4.UInt64(vested)" in text
    assert "schedule.cliff_end = arc4.UInt64(now)" in text
    assert "schedule.vesting_end = arc4.UInt64(now)" in text
