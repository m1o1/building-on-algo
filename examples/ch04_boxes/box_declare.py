from algopy import ARC4Contract, Box, UInt64, arc4


class Tally(ARC4Contract):
    def __init__(self) -> None:
        self.total = Box(UInt64, key=b"total")

    @arc4.abimethod
    def bump(self, by: UInt64) -> UInt64:
        self.total.value = self.total.get(default=UInt64(0)) + by
        return self.total.value
