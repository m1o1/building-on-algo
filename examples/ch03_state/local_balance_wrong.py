from algopy import ARC4Contract, LocalState, Txn, UInt64, arc4


class Payouts(ARC4Contract):
    def __init__(self) -> None:
        self.owed = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.owed[Txn.sender] = UInt64(0)

    @arc4.abimethod
    def accrue(self, amount: UInt64) -> UInt64:
        self.owed[Txn.sender] += amount
        return self.owed[Txn.sender]
