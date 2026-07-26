from algopy import ARC4Contract, Asset, Global, GlobalState, Txn, UInt64, arc4


class Pair(ARC4Contract):
    """Registers a two-asset pool, and insists the two are different."""

    def __init__(self) -> None:
        self.asset_a = GlobalState(UInt64(0))
        self.asset_b = GlobalState(UInt64(0))

    @arc4.abimethod
    def bootstrap(self, a: Asset, b: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.asset_a.value == UInt64(0), "already bootstrapped"
        # The whole example. Two arguments of the same type are two
        # names, not two things; nothing stops them naming one asset.
        assert a.id != b.id, "a pair needs two different assets"
        self.asset_a.value = a.id
        self.asset_b.value = b.id
