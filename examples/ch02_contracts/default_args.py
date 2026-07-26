from algopy import ARC4Contract, Txn, UInt64, arc4


class Defaults(ARC4Contract):
    """Tell the client where to find an argument the caller did not supply."""

    def __init__(self) -> None:
        self.count = UInt64(0)
        self.owner = Txn.sender

    @arc4.abimethod(readonly=True)
    def get_owner(self) -> arc4.Address:
        return arc4.Address(self.owner)

    @arc4.abimethod(default_args={"who": "get_owner", "since": "count"})
    def snapshot(self, who: arc4.Address, since: arc4.UInt64) -> UInt64:
        # The client fills these in. The contract still has to check them.
        assert who.native == self.owner, "snapshot: not the owner"
        assert since.as_uint64() <= self.count, "snapshot: since is ahead"
        return self.count - since.as_uint64()
