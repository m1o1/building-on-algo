from algopy import ARC4Contract, Asset, Global, GlobalState, Txn, UInt64, arc4


class SelfPair(ARC4Contract):
    """Accepts a pool of an asset against itself.

    Every later method reads `asset_a` and `asset_b` as two sides of a
    trade. When they are one asset, a deposit on one side is instantly
    withdrawable from the other, at whatever rate rounding allows.
    """

    def __init__(self) -> None:
        self.asset_a = GlobalState(UInt64(0))
        self.asset_b = GlobalState(UInt64(0))

    @arc4.abimethod
    def bootstrap(self, a: Asset, b: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        self.asset_a.value = a.id
        self.asset_b.value = b.id
