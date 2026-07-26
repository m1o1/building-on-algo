from algopy import ARC4Contract, Global, LocalState, Txn, UInt64, arc4, itxn


class DonatableVault(ARC4Contract):
    """Prices every share off the balance instead of off the books.

    A stranger's donation re-prices every position at once.
    """

    def __init__(self) -> None:
        self.shares = LocalState(UInt64)

    @arc4.abimethod
    def withdraw(self, share: UInt64) -> UInt64:
        assert share <= self.shares[Txn.sender], "more than you hold"
        app = Global.current_application_address
        payout = app.balance * share // UInt64(1_000_000)
        self.shares[Txn.sender] -= share
        itxn.Payment(receiver=Txn.sender, amount=payout, fee=UInt64(0)).submit()
        return payout
