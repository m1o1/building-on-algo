from algopy import (ARC4Contract, Global, GlobalState, LocalState, Txn, UInt64,
                    arc4, gtxn, itxn)


class TipJar(ARC4Contract):
    """Collects tips for one creator and pays them out on request.

    Deployed, funded, and demonstrably working: a tip arrives, the
    counter moves, the creator withdraws. Four things about how value
    moves through it are wrong, and none of them raise a compile
    error. Three are on this book's danger list.
    """

    def __init__(self) -> None:
        self.owner = GlobalState(Global.creator_address)
        self.tips_received = GlobalState(UInt64(0))
        self.tipped = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def tip(self, payment: gtxn.PaymentTransaction) -> UInt64:
        """Credit the caller for a tip they sent in this group."""
        assert payment.amount >= UInt64(1_000), "tips start at 0.001 Algo"
        given = self.tipped.get(Txn.sender, UInt64(0))
        self.tipped[Txn.sender] = given + payment.amount
        self.tips_received.value += payment.amount
        return self.tips_received.value

    @arc4.abimethod
    def withdraw(self) -> UInt64:
        """Send the jar's contents to the owner."""
        assert Txn.sender == self.owner.value, "owner only"
        app = Global.current_application_address
        amount = app.balance
        itxn.Payment(
            receiver=self.owner.value,
            amount=amount,
            fee=Global.min_txn_fee,
        ).submit()
        return amount

    @arc4.abimethod(readonly=True)
    def total(self) -> UInt64:
        return self.tips_received.value
