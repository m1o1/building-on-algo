from algopy import ARC4Contract, Box, Bytes, UInt64, arc4

SLOT = 8


class Slots(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"slots")

    @arc4.abimethod(readonly=True)
    def read(self, index: UInt64) -> arc4.UInt64:
        raw = self.data.extract(index * UInt64(SLOT), UInt64(SLOT))
        return arc4.UInt64.from_bytes(raw)
