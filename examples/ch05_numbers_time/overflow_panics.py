from algopy import ARC4Contract, UInt64, arc4

MAX_UINT64 = 18_446_744_073_709_551_615


class Ledger(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def add(self, a: UInt64, b: UInt64) -> UInt64:
        # Aborts on overflow. It does not wrap, and there is no result
        # to inspect afterwards -- the whole transaction is discarded.
        return a + b

    @arc4.abimethod(readonly=True)
    def add_checked(self, a: UInt64, b: UInt64) -> UInt64:
        # Ask the question as a comparison. `MAX_UINT64 - a` cannot
        # itself underflow, because `a` is a UInt64.
        assert b <= UInt64(MAX_UINT64) - a, "sum would overflow"
        return a + b
