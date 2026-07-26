from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class Splitter(ARC4Contract):
    """Divides a pot between shareholders.

    The divisor is checked once, where it is established -- not at every
    site that divides by it.
    """

    def __init__(self) -> None:
        self.shares = GlobalState(UInt64(0))

    @arc4.abimethod
    def set_shares(self, shares: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.shares.value == UInt64(0), "shares already set"
        assert shares > UInt64(0), "need at least one share"
        self.shares.value = shares

    @arc4.abimethod(readonly=True)
    def per_share(self, pot: UInt64) -> UInt64:
        assert self.shares.value > UInt64(0), "not initialised"
        return pot // self.shares.value

    @arc4.abimethod(readonly=True)
    def remainder(self, pot: UInt64) -> UInt64:
        assert self.shares.value > UInt64(0), "not initialised"
        return pot % self.shares.value
