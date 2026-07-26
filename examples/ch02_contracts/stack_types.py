from algopy import ARC4Contract, Bytes, UInt64, arc4, op


class StackTypes(ARC4Contract):
    """Every value the AVM holds is a uint64 or a byte string. That is all."""

    @arc4.abimethod
    def numeric(self, a: UInt64, b: UInt64) -> UInt64:
        # Both operands are uint64 values. A product that does not fit in
        # 64 bits is a runtime failure, not a wraparound.
        return a * b

    @arc4.abimethod
    def bytewise(self, a: Bytes, b: Bytes) -> UInt64:
        # Byte strings concatenate and report a length. They do not add.
        return (a + b).length

    @arc4.abimethod
    def wide(self, a: UInt64, b: UInt64) -> Bytes:
        # When a product will not fit in a uint64 it has to become bytes.
        # `mulw` returns the high and low 64-bit words.
        high, low = op.mulw(a, b)
        return op.itob(high) + op.itob(low)
