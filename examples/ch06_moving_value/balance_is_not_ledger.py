from algopy import (ARC4Contract, Global, GlobalState, LocalState, Txn, UInt64,
                    arc4, gtxn, itxn)


class Vault(ARC4Contract):
    """Tracks what it was given, not what it happens to hold.

    `self.reserve` is the ledger. The account's balance also counts
    the minimum balance, the funding that got the app running, and
    anything a stranger has sent it. None of that is anyone's money.
    """

    def __init__(self) -> None:
        self.reserve = GlobalState(UInt64(0))
        self.credited = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def deposit(self, payment: gtxn.PaymentTransaction) -> UInt64:
        app = Global.current_application_address
        assert payment.receiver == app, "pay this application"
        assert payment.sender == Txn.sender, "fund your own balance"
        self.reserve.value += payment.amount
        held = self.credited.get(Txn.sender, UInt64(0))
        self.credited[Txn.sender] = held + payment.amount
        return self.reserve.value

    @arc4.abimethod
    def withdraw(self, amount: UInt64) -> UInt64:
        # Checked against the books, never against `app.balance`.
        assert amount <= self.credited[Txn.sender], "more than you put in"
        self.credited[Txn.sender] -= amount
        self.reserve.value -= amount
        itxn.Payment(receiver=Txn.sender, amount=amount, fee=UInt64(0)).submit()
        return self.reserve.value
