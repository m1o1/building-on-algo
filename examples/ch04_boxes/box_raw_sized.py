from algopy import ARC4Contract, Box, Bytes, Global, Txn, UInt64, arc4

MAX_BOX = 32_768


class Blob(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"data")

    @arc4.abimethod
    def allocate(self, size: UInt64) -> bool:
        assert Txn.sender == Global.creator_address, "creator only"
        assert size <= UInt64(MAX_BOX), "max box size is 32,768 bytes"
        return self.data.create(size=size)

    @arc4.abimethod(readonly=True)
    def head(self, length: UInt64) -> Bytes:
        return self.data.extract(UInt64(0), length)
