from algopy import ARC4Contract, Global, LocalState, Txn, UInt64, arc4


class Membership(ARC4Contract):
    def __init__(self) -> None:
        self.joined_at = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.joined_at[Txn.sender] = Global.round
