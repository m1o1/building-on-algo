from algopy import ARC4Contract, Bytes, UInt64, arc4, op


class Slices(ARC4Contract):
    """Raw bytes slice the way Python slices, and index to a one-byte Bytes."""

    @arc4.abimethod
    def head(self, b: Bytes) -> Bytes:
        return b[:4]

    @arc4.abimethod
    def tail(self, b: Bytes) -> Bytes:
        return b[-4:]

    @arc4.abimethod
    def byte_at(self, b: Bytes, i: UInt64) -> UInt64:
        # `b[i]` is a Bytes of length one, not a number. `btoi` reads it as one.
        return op.btoi(b[i])
