from algopy import ARC4Contract, Global, Txn, UInt64, arc4


class Bare(ARC4Contract):
    """A bare method answers a call that carries no arguments at all."""

    def __init__(self) -> None:
        self.opted_in = UInt64(0)

    @arc4.baremethod(create="require")
    def create(self) -> None:
        # No selector, no arguments. This is what `send.bare.create()` calls,
        # and it is why the cheapest possible deploy is a bare create.
        pass

    @arc4.baremethod(allow_actions=["OptIn"])
    def opt_in(self) -> None:
        self.opted_in += UInt64(1)

    @arc4.baremethod(allow_actions=["DeleteApplication"])
    def delete(self) -> None:
        assert Txn.sender == Global.creator_address, "delete: creator only"

    @arc4.abimethod(readonly=True)
    def members(self) -> UInt64:
        return self.opted_in
