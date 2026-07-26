from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class SplitterWrong(ARC4Contract):
    def __init__(self) -> None:
        self.shares = GlobalState(UInt64(0))

    @arc4.abimethod
    def set_shares(self, shares: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        self.shares.value = shares  # zero is accepted here...

    @arc4.abimethod(readonly=True)
    def per_share(self, pot: UInt64) -> UInt64:
        return pot // self.shares.value  # ...and detonates here, as `/ 0`
