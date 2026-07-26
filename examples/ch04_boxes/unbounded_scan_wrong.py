from algopy import ARC4Contract, BoxMap, UInt64, arc4


class Log(ARC4Contract):
    def __init__(self) -> None:
        self.entry = BoxMap(UInt64, arc4.Address, key_prefix=b"e")

    @arc4.abimethod(readonly=True)
    def all_entries(self, count: UInt64) -> arc4.DynamicArray[arc4.Address]:
        out = arc4.DynamicArray[arc4.Address]()
        index = UInt64(0)
        while index < count:
            out.append(self.entry[index])
            index += UInt64(1)
        return out
