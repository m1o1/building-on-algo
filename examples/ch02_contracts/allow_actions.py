from algopy import ARC4Contract, Global, Txn, UInt64, arc4

# ClearState is the sixth on-completion action and it is deliberately absent
# below: it runs the clear-state program, not this one, so no decorator here
# can route it, refuse it, or even see it.


class Lifecycle(ARC4Contract):
    """The five on-completion actions a method can be routed to."""

    def __init__(self) -> None:
        self.members = UInt64(0)

    @arc4.abimethod
    def touch(self) -> UInt64:
        return self.members  # NoOp: the default, and every ordinary call

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.members += UInt64(1)

    @arc4.abimethod(allow_actions=["CloseOut"])
    def leave(self) -> None:
        assert self.members > UInt64(0), "leave: nobody is opted in"
        self.members -= UInt64(1)

    @arc4.abimethod(allow_actions=["UpdateApplication"])
    def upgrade(self) -> None:
        assert Txn.sender == Global.creator_address, "upgrade: creator only"

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def shut_down(self) -> None:
        assert Txn.sender == Global.creator_address, "shut_down: creator only"
