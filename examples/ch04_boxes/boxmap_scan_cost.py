from algopy import ARC4Contract, BoxMap, UInt64, arc4, urange

PAGE = 8  # one box reference per entry, and a group carries a fixed few


class Log(ARC4Contract):
    def __init__(self) -> None:
        self.entry = BoxMap(UInt64, arc4.Address, key_prefix=b"e")

    @arc4.abimethod(readonly=True)
    def page(self, start: UInt64) -> arc4.DynamicArray[arc4.Address]:
        out = arc4.DynamicArray[arc4.Address]()
        for index in urange(start, start + UInt64(PAGE)):
            found, exists = self.entry.maybe(index)
            if exists:
                out.append(found)
        return out
