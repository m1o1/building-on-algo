from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.ch06_moving_value.balance_is_not_ledger import Vault

DEPOSIT = 200_000
DONATION = 5_000_000
MIN_BALANCE = 100_000


def test_a_donation_moves_the_balance_and_not_the_books() -> None:
    with algopy_testing_context() as ctx:
        contract = Vault()
        app = ctx.ledger.get_app(contract)
        sender = ctx.default_sender
        payment = ctx.any.txn.payment(
            sender=sender, receiver=app.address, amount=UInt64(DEPOSIT)
        )
        call = ctx.any.txn.application_call(app_id=app, sender=sender)
        with ctx.txn.create_group([payment, call], active_txn_index=1):
            assert contract.deposit(payment) == DEPOSIT

        # A stranger sends the application account five Algo. Nothing
        # about it is a deposit, and nothing about it is anyone's claim.
        ctx.ledger.update_account(
            app.address,
            balance=UInt64(MIN_BALANCE + DEPOSIT + DONATION),
            min_balance=UInt64(MIN_BALANCE),
        )
        assert contract.reserve.value == DEPOSIT
        assert contract.credited[sender] == DEPOSIT


def test_withdrawal_is_bounded_by_the_books_not_by_the_balance() -> None:
    with algopy_testing_context() as ctx:
        contract = Vault()
        app = ctx.ledger.get_app(contract)
        sender = ctx.default_sender
        ctx.ledger.update_account(
            app.address,
            balance=UInt64(MIN_BALANCE + DEPOSIT + DONATION),
            min_balance=UInt64(MIN_BALANCE),
        )
        payment = ctx.any.txn.payment(
            sender=sender, receiver=app.address, amount=UInt64(DEPOSIT)
        )
        call = ctx.any.txn.application_call(app_id=app, sender=sender)
        with ctx.txn.create_group([payment, call], active_txn_index=1):
            contract.deposit(payment)
            # The account can afford far more than this. The books say
            # this is all the caller is owed, so this is all they get.
            assert contract.withdraw(UInt64(DEPOSIT)) == 0
        assert ctx.txn.last_group.last_itxn.payment.amount == DEPOSIT
