import pytest
from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.ch06_moving_value.inner_payment import Faucet

BALANCE = 1_000_000
MIN_BALANCE = 100_000
SEND = 50_000


def _funded(ctx, contract):  # type: ignore[no-untyped-def]
    app = ctx.ledger.get_app(contract)
    ctx.ledger.update_account(
        app.address, balance=UInt64(BALANCE), min_balance=UInt64(MIN_BALANCE)
    )
    return app


def test_the_inner_payment_carries_the_recipient_amount_and_a_zero_fee() -> None:
    with algopy_testing_context() as ctx:
        contract = Faucet()
        app = _funded(ctx, contract)
        recipient = ctx.any.account()
        call = ctx.any.txn.application_call(app_id=app, sender=ctx.default_sender)
        with ctx.txn.create_group([call]):
            left = contract.pay(recipient, UInt64(SEND))
        assert left == BALANCE - MIN_BALANCE - SEND
        payment = ctx.txn.last_group.last_itxn.payment
        assert payment.receiver == recipient
        assert payment.amount == SEND
        # Zero, so the fee comes out of the caller's pooled fee rather
        # than out of the application's own balance.
        assert payment.fee == 0


def test_a_payment_that_would_breach_the_minimum_balance_is_refused() -> None:
    with algopy_testing_context() as ctx:
        contract = Faucet()
        app = _funded(ctx, contract)
        recipient = ctx.any.account()
        call = ctx.any.txn.application_call(app_id=app, sender=ctx.default_sender)
        with ctx.txn.create_group([call]):  # noqa: SIM117
            with pytest.raises(AssertionError):
                contract.pay(recipient, UInt64(BALANCE - MIN_BALANCE + 1))


def test_only_the_creator_may_spend() -> None:
    with algopy_testing_context() as ctx:
        contract = Faucet()
        app = _funded(ctx, contract)
        stranger = ctx.any.account()
        call = ctx.any.txn.application_call(app_id=app, sender=stranger)
        with ctx.txn.create_group([call]):  # noqa: SIM117
            with pytest.raises(AssertionError):
                contract.pay(stranger, UInt64(SEND))
