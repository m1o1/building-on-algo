from algopy import ARC4Contract, Global, GlobalState, UInt64, arc4, gtxn


class ReplayableEscrow(ARC4Contract):
    """Reads transaction zero, and never asks how long the group is.

    One payment at index 0, followed by fifteen copies of this call,
    credits the same money sixteen times. The payment is real; the
    accounting is not.
    """

    def __init__(self) -> None:
        self.received = GlobalState(UInt64(0))

    @arc4.abimethod
    def claim(self) -> UInt64:
        payment = gtxn.PaymentTransaction(0)
        assert payment.receiver == Global.current_application_address
        self.received.value += payment.amount
        return self.received.value
