import pytest
from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.ch06_moving_value.group_bounds import Escrow
from examples.ch06_moving_value.group_bounds_wrong import ReplayableEscrow

PAID = 300_000


def test_a_payment_followed_by_the_call_is_accepted() -> None:
    with algopy_testing_context() as ctx:
        contract = Escrow()
        app = ctx.ledger.get_app(contract)
        sender = ctx.default_sender
        payment = ctx.any.txn.payment(
            sender=sender, receiver=app.address, amount=UInt64(PAID)
        )
        call = ctx.any.txn.application_call(app_id=app, sender=sender)
        with ctx.txn.create_group([payment, call], active_txn_index=1):
            assert contract.claim() == PAID


def test_appending_a_second_call_to_the_group_is_refused() -> None:
    """One payment, two calls: the group-size check is what stops it."""
    with algopy_testing_context() as ctx:
        contract = Escrow()
        app = ctx.ledger.get_app(contract)
        sender = ctx.default_sender
        payment = ctx.any.txn.payment(
            sender=sender, receiver=app.address, amount=UInt64(PAID)
        )
        first = ctx.any.txn.application_call(app_id=app, sender=sender)
        second = ctx.any.txn.application_call(app_id=app, sender=sender)
        group = [payment, first, second]
        with ctx.txn.create_group(group, active_txn_index=1):  # noqa: SIM117
            with pytest.raises(AssertionError):
                contract.claim()


def test_the_wrong_variant_credits_one_payment_twice() -> None:
    with algopy_testing_context() as ctx:
        contract = ReplayableEscrow()
        app = ctx.ledger.get_app(contract)
        sender = ctx.default_sender
        payment = ctx.any.txn.payment(
            sender=sender, receiver=app.address, amount=UInt64(PAID)
        )
        first = ctx.any.txn.application_call(app_id=app, sender=sender)
        second = ctx.any.txn.application_call(app_id=app, sender=sender)
        group = [payment, first, second]
        with ctx.txn.create_group(group, active_txn_index=1):
            assert contract.claim() == PAID
        with ctx.txn.create_group(group, active_txn_index=2):
            # The same 300,000 microAlgo, counted a second time.
            assert contract.claim() == PAID * 2
