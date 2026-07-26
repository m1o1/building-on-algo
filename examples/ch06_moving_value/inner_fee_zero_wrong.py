from algopy import ARC4Contract, Global, Txn, UInt64, arc4, itxn


class SelfFundedEcho(ARC4Contract):
    """Anyone may call this, and every call costs the app 1,000 microAlgo.

    The fee on an inner transaction is paid by the application account,
    never by the caller. A zero-Algo payment that charges itself a fee
    is a withdrawal with extra steps.
    """

    @arc4.abimethod
    def ping(self) -> None:
        itxn.Payment(
            receiver=Txn.sender,
            amount=UInt64(0),
            fee=Global.min_txn_fee,
        ).submit()
