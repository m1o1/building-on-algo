# book-example: mode=compile
from algopy import ARC4Contract, Array, UInt64, arc4


class Bag(ARC4Contract):
    @arc4.abimethod
    def frozen(self) -> UInt64:
        working = Array[UInt64]()
        working.append(UInt64(1))
        snapshot = working.freeze()
        grown = snapshot.append(UInt64(2))  # returns a copy
        return snapshot.length + grown.length
