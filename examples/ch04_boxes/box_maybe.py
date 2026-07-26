from algopy import ARC4Contract, Box, UInt64, arc4


class Tally(ARC4Contract):
    def __init__(self) -> None:
        self.total = Box(UInt64, key=b"total")

    @arc4.abimethod(readonly=True)
    def total_if_any(self) -> tuple[UInt64, bool]:
        value, exists = self.total.maybe()
        return value, exists
