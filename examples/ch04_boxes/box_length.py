from algopy import ARC4Contract, Box, Bytes, UInt64, arc4


class Blob(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"data")

    @arc4.abimethod(readonly=True)
    def size(self) -> UInt64:
        assert self.data, "box does not exist"
        return self.data.length
