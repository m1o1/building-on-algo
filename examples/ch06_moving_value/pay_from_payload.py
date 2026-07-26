from algopy import (ARC4Contract, Account, Global, Txn, UInt64, arc4, gtxn,
                    itxn)

FEE_BASIS_POINTS = 50


class Forwarder(ARC4Contract):
    """Takes a cut, forwards the rest, and holds no float.

    The Algo leaving in the inner payment arrived in the same group,
    moments earlier. The application account is a conduit here, not a
    treasury: nothing accumulates in it between calls.
    """

    @arc4.abimethod
    def forward(
        self, payment: gtxn.PaymentTransaction, recipient: Account
    ) -> UInt64:
        app = Global.current_application_address
        assert Global.group_size == UInt64(2), "payment, then call"
        assert payment.receiver == app, "pay this application"
        assert payment.sender == Txn.sender, "forward your own money"
        cut = payment.amount * UInt64(FEE_BASIS_POINTS) // UInt64(10_000)
        itxn.Payment(
            receiver=recipient,
            amount=payment.amount - cut,
            fee=UInt64(0),
        ).submit()
        return cut
