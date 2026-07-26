from algopy import ARC4Contract, arc4


class Boundary(ARC4Contract):
    @arc4.abimethod
    def add(self, a: arc4.UInt64, b: arc4.UInt64) -> arc4.UInt64:
        # An ARC-4 value is an encoding, not a number. It has no `+`.
        return a + b
