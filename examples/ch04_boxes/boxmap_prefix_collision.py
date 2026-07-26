from algopy import ARC4Contract, BoxMap, Bytes, UInt64, arc4


class Ledger(ARC4Contract):
    def __init__(self) -> None:
        self.short = BoxMap(Bytes, UInt64, key_prefix=b"a")
        self.long = BoxMap(Bytes, UInt64, key_prefix=b"ab")

    @arc4.abimethod
    def collide(self) -> bool:
        self.short[Bytes(b"bc")] = UInt64(1)
        self.long[Bytes(b"c")] = UInt64(2)
        # Both wrote the box named b"abc". The second write won.
        return self.short[Bytes(b"bc")] == UInt64(2)
