from algopy import (ARC4Contract, Global, GlobalState, LocalState, Txn, UInt64,
                    arc4, gtxn, itxn)

TIP_GROUP_SIZE = 2


class TipJar(ARC4Contract):
    """Collects tips for one creator and pays them out on request.

    The same contract, with the four defects repaired: the payment is
    checked for destination and sender, the group is bounded, the
    inner transaction stops charging the jar for its own fees, and the
    withdrawal leaves the minimum balance where it belongs.
    """

    def __init__(self) -> None:
        self.owner = GlobalState(Global.creator_address)
        self.tips_received = GlobalState(UInt64(0))
        self.tipped = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def tip(self, payment: gtxn.PaymentTransaction) -> UInt64:
        """Credit the caller for a tip they sent in this group."""
        assert Global.group_size == UInt64(TIP_GROUP_SIZE), "pay, then call"
        app = Global.current_application_address
        assert payment.receiver == app, "tip this jar, not an account"
        assert payment.sender == Txn.sender, "credit goes to the payer"
        assert payment.amount >= UInt64(1_000), "tips start at 0.001 Algo"
        given = self.tipped.get(Txn.sender, UInt64(0))
        self.tipped[Txn.sender] = given + payment.amount
        self.tips_received.value += payment.amount
        return self.tips_received.value

    @arc4.abimethod
    def withdraw(self) -> UInt64:
        """Send the jar's spendable contents to the owner."""
        assert Txn.sender == self.owner.value, "owner only"
        app = Global.current_application_address
        amount = app.balance - app.min_balance
        itxn.Payment(
            receiver=self.owner.value,
            amount=amount,
            fee=UInt64(0),
        ).submit()
        return amount

    @arc4.abimethod(readonly=True)
    def total(self) -> UInt64:
        return self.tips_received.value
