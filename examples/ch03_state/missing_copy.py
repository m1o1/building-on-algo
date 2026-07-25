from algopy import ARC4Contract, GlobalState, arc4


class Point(arc4.Struct):
    x: arc4.UInt64
    y: arc4.UInt64


class MissingCopy(ARC4Contract):
    def __init__(self) -> None:
        self.origin = GlobalState(Point(arc4.UInt64(0), arc4.UInt64(0)))

    @arc4.abimethod
    def shift(self) -> None:
        moved = self.origin.value
        moved.x = arc4.UInt64(1)
