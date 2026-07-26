from algopy import ARC4Contract, Box, Bytes, Global, Txn, UInt64, arc4

SLOT = 8
MAX_SLOTS = 64


class Slots(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"slots")

    @arc4.abimethod
    def allocate(self, count: UInt64) -> bool:
        assert Txn.sender == Global.creator_address, "creator only"
        assert count <= UInt64(MAX_SLOTS), "too many slots"
        return self.data.create(size=count * UInt64(SLOT))

    @arc4.abimethod
    def write(self, index: UInt64, value: arc4.UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        self.data.replace(index * UInt64(SLOT), value.bytes)
