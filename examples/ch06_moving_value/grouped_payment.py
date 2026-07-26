from algopy import (ARC4Contract, Global, GlobalState, LocalState, Txn, UInt64,
                    arc4, gtxn)

MIN_DEPOSIT = 100_000


class Deposits(ARC4Contract):
    """Credits a caller for Algo they sent in the same group."""

    def __init__(self) -> None:
        self.total = GlobalState(UInt64(0))
        self.credited = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def deposit(self, payment: gtxn.PaymentTransaction) -> UInt64:
        app = Global.current_application_address
        # The parameter type pins the transaction's type and position.
        # It says nothing about where the money went, or whose it was.
        assert payment.receiver == app, "pay this application"
        assert payment.sender == Txn.sender, "fund your own balance"
        assert payment.amount >= UInt64(MIN_DEPOSIT), "below the minimum"
        held = self.credited.get(Txn.sender, UInt64(0))
        self.credited[Txn.sender] = held + payment.amount
        self.total.value += payment.amount
        return self.credited[Txn.sender]
