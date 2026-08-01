from __future__ import annotations

from pathlib import Path


CONTRACT = Path("smart_contracts/nft_vesting/contract.py")


def source() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def test_uses_schedule_id_box_map_for_transferable_schedules() -> None:
    text = source()
    assert "BoxMap(arc4.UInt64, VestingSchedule, key_prefix=b\"v_\")" in text
    assert "schedule_key = arc4.UInt64(schedule_id)" in text


def test_validates_grouped_deposit_transfer_and_reserves_tokens() -> None:
    text = source()
    assert "Global.group_size == UInt64(2)" in text
    assert "deposit_txn.asset_receiver == Global.current_application_address" in text
    assert "deposit_txn.xfer_asset == Asset(self.asset_id.value)" in text
    assert "self.available_tokens.value += deposit_txn.asset_amount" in text


def test_initialization_rejects_externally_controllable_vesting_assets() -> None:
    text = source()
    assert "vesting_asset.clawback == Global.zero_address" in text
    assert "vesting_asset.freeze == Global.zero_address" in text
    assert "not vesting_asset.default_frozen" in text


def test_schedule_creation_uses_exact_mbr_payment() -> None:
    text = source()
    assert "mbr_payment.receiver == Global.current_application_address" in text
    assert "mbr_payment.sender == Txn.sender" in text
    assert "mbr_payment.amount == schedule_mbr" in text
    assert "mbr_payment.amount >= box_mbr + nft_mbr" not in text


def test_schedules_can_only_use_reserved_deposits() -> None:
    text = source()
    assert "self.available_tokens = GlobalState(UInt64(0))" in text
    assert "self.available_tokens.value >= total_amount" in text
    assert "self.available_tokens.value -= total_amount" in text


def test_minted_nft_has_contract_manager_and_clawback() -> None:
    text = source()
    assert "total=UInt64(1)" in text
    assert "decimals=UInt64(0)" in text
    assert "manager=Global.current_application_address" in text
    assert "clawback=Global.current_application_address" in text
    assert "freeze=Global.zero_address" in text


def test_claim_validates_current_nft_holder_and_matching_asset() -> None:
    text = source()
    assert "nft_asset.balance(Txn.sender) == UInt64(1)" in text
    assert "schedule.nft_asset_id.as_uint64() == nft_asset.id" in text
    assert "vesting_asset.balance(Global.current_application_address)" not in text


def test_revocation_claws_back_and_destroys_nft() -> None:
    text = source()
    assert "nft_asset.balance(current_holder) == UInt64(1)" in text
    assert "asset_sender=current_holder" in text
    assert "config_asset=nft_asset" in text
    assert "schedule.is_revoked = arc4.Bool(True)" in text


def test_inner_transactions_use_fee_pooling() -> None:
    text = source()
    assert text.count("fee=UInt64(0)") >= 7


def test_vesting_math_uses_wide_arithmetic() -> None:
    text = source()
    assert "op.mulw(total, elapsed)" in text
    assert "op.divmodw(high, low, UInt64(0), duration)" in text


def test_cleanup_refunds_box_mbr_to_admin() -> None:
    text = source()
    cleanup = text.split("def cleanup_schedule", maxsplit=1)[1]
    cleanup = cleanup.split("@arc4.abimethod(readonly=True)", maxsplit=1)[0]
    assert "receiver=Account(self.admin.value)" in cleanup
    assert "receiver=Txn.sender" not in cleanup
