# book-example: mode=unit
from algopy import ARC4Contract, GlobalState, UInt64, arc4


class GlobalCounter(ARC4Contract):
    def __init__(self) -> None:
        self.count = GlobalState(UInt64(0))

    @arc4.abimethod
    def bump(self) -> UInt64:
        self.count.value += UInt64(1)
        return self.count.value
