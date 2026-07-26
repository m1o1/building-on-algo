from algopy import ARC4Contract, Box, Global, Txn, arc4, size_of, zero_bytes


class Record(arc4.Struct):
    score: arc4.UInt64
    streak: arc4.UInt16


class League(ARC4Contract):
    def __init__(self) -> None:
        self.record = Box(Record, key=b"r")

    @arc4.abimethod
    def reset(self) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.record.create(size=size_of(Record)), "already allocated"
        self.record.value = zero_bytes(Record)
