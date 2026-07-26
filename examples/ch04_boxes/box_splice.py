from algopy import ARC4Contract, Box, Bytes, UInt64, arc4


class Blob(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"data")

    @arc4.abimethod
    def insert(self, at: UInt64, value: Bytes) -> UInt64:
        # splice does not resize: the tail is truncated to hold the size.
        self.data.splice(at, UInt64(0), value)
        return self.data.length
