from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4, itxn


class AllOrNothing(ARC4Contract):
    """Books the withdrawal first, then makes it. Both, or neither."""

    def __init__(self) -> None:
        self.paid_out = GlobalState(UInt64(0))

    @arc4.abimethod
    def withdraw(self, amount: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        # The counter moves before the money does. If the payment below
        # fails --- or if any later transaction in the group fails ---
        # this assignment is discarded along with it.
        self.paid_out.value += amount
        itxn.Payment(
            receiver=Txn.sender,
            amount=amount,
            fee=UInt64(0),
        ).submit()
        return self.paid_out.value
