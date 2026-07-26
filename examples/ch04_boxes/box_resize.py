from algopy import ARC4Contract, Box, Bytes, Global, Txn, UInt64, arc4


class Blob(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"data")

    @arc4.abimethod
    def start(self) -> bool:
        assert Txn.sender == Global.creator_address, "creator only"
        return self.data.create(size=UInt64(0))

    @arc4.abimethod
    def grow(self, extra: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        new_size = self.data.length + extra
        assert new_size <= UInt64(32_768), "max box size is 32,768 bytes"
        self.data.resize(new_size)
        return new_size
