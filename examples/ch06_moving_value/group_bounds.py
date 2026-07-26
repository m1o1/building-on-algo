from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4, gtxn

GROUP_SIZE = 2


class Escrow(ARC4Contract):
    """Reads the payment directly before it, and no other group shape."""

    def __init__(self) -> None:
        self.received = GlobalState(UInt64(0))

    @arc4.abimethod
    def claim(self) -> UInt64:
        # Two assertions doing two different jobs: the first says how
        # long the group is, the second says where in it this call sits.
        assert Global.group_size == UInt64(GROUP_SIZE), "expected two"
        assert Txn.group_index == UInt64(1), "the call goes second"
        # Position-relative, so the pair still works if it is ever
        # nested inside a larger group with the size check relaxed.
        payment = gtxn.PaymentTransaction(Txn.group_index - 1)
        app = Global.current_application_address
        assert payment.receiver == app, "pay this application"
        assert payment.sender == Txn.sender, "fund your own claim"
        self.received.value += payment.amount
        return self.received.value
