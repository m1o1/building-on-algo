from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class Registry(ARC4Contract):
    """Two rejections, one of which can explain itself.

    Both compile to the same `assert`. The string in the first never
    reaches the chain: PuyaPy turns it into a TEAL comment and an
    ARC-56 `sourceInfo` entry keyed by program counter, and the
    compiled bytes do not contain it. The second has no message at
    all, so there is no `sourceInfo` entry to look up --- the node
    reports a program counter and that is the whole story.
    """

    def __init__(self) -> None:
        self.owner = GlobalState(Global.creator_address)
        self.entries = GlobalState(UInt64(0))

    @arc4.abimethod
    def record(self, count: UInt64) -> UInt64:
        assert Txn.sender == self.owner.value, "owner only"
        assert count > UInt64(0)
        self.entries.value += count
        return self.entries.value
