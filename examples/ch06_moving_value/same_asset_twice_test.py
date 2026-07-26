import pytest
from algopy_testing import algopy_testing_context

from examples.ch06_moving_value.same_asset_twice import Pair


def test_two_different_assets_bootstrap_the_pair() -> None:
    with algopy_testing_context() as ctx:
        contract = Pair()
        app = ctx.ledger.get_app(contract)
        a = ctx.any.asset()
        b = ctx.any.asset()
        call = ctx.any.txn.application_call(app_id=app, sender=ctx.default_sender)
        with ctx.txn.create_group([call]):
            contract.bootstrap(a, b)
            assert contract.asset_a.value == a.id
            assert contract.asset_b.value == b.id


def test_one_asset_named_twice_is_refused() -> None:
    """Tinyman V1's $3M bug, in one line of test."""
    with algopy_testing_context() as ctx:
        contract = Pair()
        app = ctx.ledger.get_app(contract)
        a = ctx.any.asset()
        call = ctx.any.txn.application_call(app_id=app, sender=ctx.default_sender)
        with ctx.txn.create_group([call]):  # noqa: SIM117
            with pytest.raises(AssertionError):
                contract.bootstrap(a, a)
