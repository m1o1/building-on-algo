from algopy import Account, ARC4Contract, BoxMap, UInt64, arc4, size_of


class Record(arc4.Struct):
    score: arc4.UInt64
    streak: arc4.UInt16


class League(ARC4Contract):
    def __init__(self) -> None:
        self.record = BoxMap(Account, Record, key_prefix=b"r")

    @arc4.abimethod(readonly=True)
    def cost_per_player(self) -> UInt64:
        name_len = self.record.key_prefix.length + UInt64(32)
        return UInt64(2_500) + UInt64(400) * (name_len + size_of(Record))
