import pytest
from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.ch06_moving_value.grouped_payment import Deposits
from examples.ch06_moving_value.grouped_payment_wrong import LooseDeposits

DEPOSIT = 200_000


def test_a_payment_to_the_application_is_credited() -> None:
    with algopy_testing_context() as ctx:
        contract = Deposits()
        app = ctx.ledger.get_app(contract)
        sender = ctx.default_sender
        payment = ctx.any.txn.payment(
            sender=sender, receiver=app.address, amount=UInt64(DEPOSIT)
        )
        call = ctx.any.txn.application_call(app_id=app, sender=sender)
        with ctx.txn.create_group([payment, call], active_txn_index=1):
            assert contract.deposit(payment) == DEPOSIT
            assert contract.total.value == DEPOSIT


def test_a_payment_to_somewhere_else_is_refused() -> None:
    """The attack the receiver check exists to stop."""
    with algopy_testing_context() as ctx:
        contract = Deposits()
        app = ctx.ledger.get_app(contract)
        attacker = ctx.default_sender
        # Real money, really moved --- into the attacker's own account.
        elsewhere = ctx.any.txn.payment(
            sender=attacker, receiver=attacker, amount=UInt64(DEPOSIT)
        )
        call = ctx.any.txn.application_call(app_id=app, sender=attacker)
        with ctx.txn.create_group([elsewhere, call], active_txn_index=1):  # noqa: SIM117
            with pytest.raises(AssertionError):
                contract.deposit(elsewhere)


def test_the_wrong_variant_credits_that_same_payment() -> None:
    """Same group, same self-payment, and a free balance."""
    with algopy_testing_context() as ctx:
        contract = LooseDeposits()
        app = ctx.ledger.get_app(contract)
        attacker = ctx.default_sender
        elsewhere = ctx.any.txn.payment(
            sender=attacker, receiver=attacker, amount=UInt64(DEPOSIT)
        )
        call = ctx.any.txn.application_call(app_id=app, sender=attacker)
        with ctx.txn.create_group([elsewhere, call], active_txn_index=1):
            assert contract.deposit(elsewhere) == DEPOSIT
