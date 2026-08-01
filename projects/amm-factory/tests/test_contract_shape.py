from __future__ import annotations

from pathlib import Path


FACTORY = Path("smart_contracts/amm_factory/contract.py")
POOL = Path("smart_contracts/factory_pool/contract.py")


def read_factory() -> str:
    return FACTORY.read_text(encoding="utf-8")


def read_pool() -> str:
    return POOL.read_text(encoding="utf-8")


def test_factory_creates_child_application_and_records_pair() -> None:
    source = read_factory()
    assert "compile_contract(FactoryPool)" in source
    assert "itxn.ApplicationCall(" in source
    assert "create_txn.created_app" in source
    assert "self.pools[key] = pool_app.id" in source
    assert "self.lp_tokens[key] = lp_token_id" in source


def test_factory_funds_child_before_bootstrap() -> None:
    source = read_factory()
    payment_index = source.index("itxn.Payment(")
    bootstrap_index = source.index('arc4.arc4_signature("bootstrap')
    assert payment_index < bootstrap_index
    assert "receiver=pool_app.address" in source
    assert "fee=UInt64(0)" in source


def test_verify_pool_uses_registry_creator_and_child_state() -> None:
    source = read_factory()
    assert "registered_pool != candidate_pool.id" in source
    assert "candidate_pool.creator != Global.current_application_address" in source
    assert 'Bytes(b"factory_app_id")' in source
    assert "pool_factory == Global.current_application_id.id" in source
    assert "pool_lp_token == self.lp_tokens.get" in source


def test_pool_requires_factory_bootstrap() -> None:
    source = read_pool()
    assert "Global.caller_application_id != UInt64(0)" in source
    assert "Global.caller_application_address == Global.creator_address" in source
    assert "Txn.sender == Global.creator_address" in source
    assert "self.factory_app_id.value = Global.caller_application_id" in source


def test_pool_keeps_chapter_five_amm_security_without_twap() -> None:
    source = read_pool()
    assert "op.mulw" in source
    assert "op.divmodw" in source
    assert "Invariant violated" in source
    assert "input_txn.sender == Txn.sender" in source
    assert "deposit_a.sender == Txn.sender" in source
    assert "lp_deposit.sender == Txn.sender" in source
    assert "cumulative_price" not in source
    assert "get_twap_price" not in source


def test_inner_transactions_pool_fees_to_outer_call() -> None:
    source = read_factory() + "\n" + read_pool()
    assert source.count("fee=UInt64(0)") >= 11
