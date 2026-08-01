# book-example: mode=compile
from algopy import ARC4Contract, ReferenceArray, UInt64, arc4


class Bag(ARC4Contract):
    @arc4.abimethod
    def one_bag(self) -> UInt64:
        a = ReferenceArray[UInt64]()
        a.append(UInt64(1))
        b = a  # both names see every update
        b.append(UInt64(2))
        return a.length
