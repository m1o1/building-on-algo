from algopy import ARC4Contract, UInt64, arc4, op


class Join(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def divide_wide(self, hi: UInt64, lo: UInt64, d: UInt64) -> UInt64:
        # Not "divw 0": that string is the AVM's, and a contract that
        # borrows it makes its own guard indistinguishable from the
        # opcode failing underneath it.
        assert d != UInt64(0), "divisor must be non-zero"
        # `divw` aborts unless the quotient fits in 64 bits, and the
        # test it applies is exactly `d > hi`.
        assert d > hi, "quotient would not fit in 64 bits"
        return op.divw(hi, lo, d)
