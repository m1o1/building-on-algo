from algopy import ARC4Contract, GlobalState, LocalState, Txn, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.member_count = GlobalState(UInt64(0))
        self.credits = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.credits[Txn.sender] = UInt64(0)
        self.member_count.value += UInt64(1)

    @arc4.abimethod(allow_actions=["CloseOut"])
    def leave(self) -> None:
        assert self.credits[Txn.sender] == 0, "claim your credits first"
        self.member_count.value -= UInt64(1)
