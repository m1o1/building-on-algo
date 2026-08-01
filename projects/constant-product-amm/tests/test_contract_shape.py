from __future__ import annotations

from pathlib import Path


CONTRACT = Path("smart_contracts/constant_product_pool/contract.py")


def read_contract() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def test_bootstrap_hardens_assets_and_binds_seed_payment() -> None:
    source = read_contract()
    assert "asset_a.id < asset_b.id" in source
    assert "asset_a.clawback == Global.zero_address" in source
    assert "asset_a.freeze == Global.zero_address" in source
    assert "not asset_a.default_frozen" in source
    assert "asset_b.clawback == Global.zero_address" in source
    assert "asset_b.freeze == Global.zero_address" in source
    assert "not asset_b.default_frozen" in source
    assert "seed_payment.sender == Txn.sender" in source
    assert "seed_payment.receiver == Global.current_application_address" in source


def test_every_grouped_user_transfer_is_bound_to_app_call_sender() -> None:
    source = read_contract()
    assert "deposit_a.sender == Txn.sender" in source
    assert "deposit_b.sender == Txn.sender" in source
    assert "input_txn.sender == Txn.sender" in source
    assert "lp_deposit.sender == Txn.sender" in source


def test_asset_ids_and_receivers_are_checked() -> None:
    source = read_contract()
    assert "deposit_a.xfer_asset == Asset(self.asset_a.value)" in source
    assert "deposit_b.xfer_asset == Asset(self.asset_b.value)" in source
    assert "input_asset == asset_a" in source
    assert "input_asset == asset_b" in source
    assert "lp_deposit.xfer_asset == Asset(self.lp_token_id.value)" in source
    assert source.count("Global.current_application_address") >= 8


def test_inner_transactions_pool_fees_to_the_outer_group() -> None:
    source = read_contract()
    assert source.count("fee=UInt64(0)") >= 8


def test_amm_math_uses_wide_arithmetic_and_invariant_check() -> None:
    source = read_contract()
    assert "op.mulw" in source
    assert "op.divmodw" in source
    assert "op.addw" in source
    assert "Swap input too large" in source
    assert "op.bsqrt" in source
    assert "BigUInt(amount_a) * BigUInt(amount_b)" in source
    assert "Invariant violated" in source
    assert "new_high > old_high" in source


def test_twap_updates_before_reserve_mutations() -> None:
    source = read_contract()
    for method_name in ("swap", "add_liquidity", "remove_liquidity"):
        marker = f"def {method_name}"
        method_start = source.index(marker)
        twap_index = source.index("self._update_twap()", method_start)
        reserve_write = source.index("self.reserve_a.value", twap_index)
        assert twap_index < reserve_write


def test_lifecycle_is_immutable_after_create() -> None:
    source = read_contract()
    assert '@arc4.baremethod(create="require")' in source
    assert 'allow_actions=["UpdateApplication", "DeleteApplication"]' in source
    assert "Contract is immutable" in source
