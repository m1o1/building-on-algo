from algopy import ARC4Contract, LocalState, Txn, UInt64, arc4, gtxn


class LooseDeposits(ARC4Contract):
    """Credits the caller for a payment that may have gone anywhere.

    A payment to the attacker's own account satisfies this method just
    as well as a payment to the application, so the balance is free.
    """

    def __init__(self) -> None:
        self.credited = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def deposit(self, payment: gtxn.PaymentTransaction) -> UInt64:
        held = self.credited.get(Txn.sender, UInt64(0))
        self.credited[Txn.sender] = held + payment.amount
        return self.credited[Txn.sender]
