from algopy import ARC4Contract, Box, Bytes, Global, GlobalState, Txn, UInt64, arc4

ENTRY = 32
MAX_ENTRIES = 64


class Log(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"log")
        self.count = GlobalState(UInt64(0))

    @arc4.abimethod
    def start(self) -> bool:
        assert Txn.sender == Global.creator_address, "creator only"
        return self.data.create(size=UInt64(0))

    @arc4.abimethod
    def append(self, entry: arc4.Address) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        index = self.count.value
        assert index < UInt64(MAX_ENTRIES), "log is full"
        self.data.resize((index + UInt64(1)) * UInt64(ENTRY))
        self.data.replace(index * UInt64(ENTRY), entry.bytes)
        self.count.value = index + UInt64(1)
        return index
