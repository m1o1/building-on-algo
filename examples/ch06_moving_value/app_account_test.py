from algopy import UInt64
from algopy_testing import algopy_testing_context

from examples.ch06_moving_value.app_account import Treasury

BALANCE = 1_000_000
MIN_BALANCE = 100_000


def test_spendable_is_the_balance_above_the_minimum() -> None:
    with algopy_testing_context() as ctx:
        contract = Treasury()
        app = ctx.ledger.get_app(contract)
        ctx.ledger.update_account(
            app.address,
            balance=UInt64(BALANCE),
            min_balance=UInt64(MIN_BALANCE),
        )
        with ctx.txn.create_group([ctx.any.txn.application_call(app_id=app)]):
            # The account holds a million microAlgo and can send 900,000
            # of them. The last 100,000 are locked by the ledger, not by
            # any rule this contract wrote.
            assert contract.held() == BALANCE
            assert contract.spendable() == BALANCE - MIN_BALANCE
            assert contract.address().native == app.address
