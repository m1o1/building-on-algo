from algopy import ARC4Contract, Array, UInt64, arc4


class Bag(ARC4Contract):
    @arc4.abimethod
    def two_bags(self) -> UInt64:
        a = Array[UInt64]()
        a.append(UInt64(1))
        b = a.copy()  # without .copy() this line is a compile error
        b.append(UInt64(2))
        return a.length + b.length
