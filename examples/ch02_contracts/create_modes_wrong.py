from algopy import ARC4Contract, Global, Txn, UInt64, arc4


class Modes(ARC4Contract):
    def __init__(self) -> None:
        self.count = UInt64(0)

    @arc4.abimethod(create="allow")
    def reset(self) -> None:
        # "allow" removes the application-ID check entirely. A caller who
        # sends this against application ID 0 creates a brand new app, runs
        # __init__, resets that one, and is told it worked.
        assert Txn.sender == Global.creator_address, "reset: creator only"
        self.count = UInt64(0)
