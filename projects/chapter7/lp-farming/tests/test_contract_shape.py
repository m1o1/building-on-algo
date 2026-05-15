from pathlib import Path


CONTRACT = (
    Path(__file__).resolve().parents[1]
    / "smart_contracts"
    / "lp_farming"
    / "contract.py"
)


def test_farm_verifies_amm_lp_token() -> None:
    source = CONTRACT.read_text(encoding="utf-8")

    assert "op.AppGlobal.get_ex_uint64" in source
    assert 'Bytes(b"lp_token_id")' in source
    assert 'assert lp_id == lp_token.id, "LP token mismatch"' in source


def test_stake_requires_mbr_payment_and_sender_binding() -> None:
    source = CONTRACT.read_text(encoding="utf-8")

    assert "mbr_payment: gtxn.PaymentTransaction" in source
    assert "mbr_payment.sender == Txn.sender" in source
    assert "mbr_payment.receiver == Global.current_application_address" in source
    assert "mbr_payment.amount == UInt64(STAKE_BOX_MBR)" in source
    assert "lp_txn.sender == Txn.sender" in source
    assert "lp_txn.asset_receiver == Global.current_application_address" in source


def test_inner_transactions_use_fee_pooling() -> None:
    source = CONTRACT.read_text(encoding="utf-8")

    inner_transaction_count = source.count("itxn.AssetTransfer(")
    inner_transaction_count += source.count("itxn.Payment(")
    assert inner_transaction_count >= 5
    assert source.count("fee=UInt64(0)") >= inner_transaction_count


def test_reward_math_uses_wide_arithmetic_and_bounds() -> None:
    source = CONTRACT.read_text(encoding="utf-8")

    assert "op.mulw" in source
    assert "op.divmodw" in source
    assert "MAX_REWARD_RATE" in source
    assert "MAX_REWARD_DURATION" in source
    assert "Accumulator overflow" in source
    assert "Reward overflow" in source
    assert "self._update_reward()" in source


def test_group_shapes_are_explicit() -> None:
    source = CONTRACT.read_text(encoding="utf-8")

    assert "Global.group_size == UInt64(1)" in source
    assert "Global.group_size == UInt64(2)" in source
    assert "Global.group_size == UInt64(3)" in source
