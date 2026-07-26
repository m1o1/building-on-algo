from algopy import ARC4Contract, UInt64, arc4, op


class Wide(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def product_words(self, a: UInt64, b: UInt64) -> tuple[UInt64, UInt64]:
        # The full 128-bit product, as a high word and a low word.
        # `mulw` never aborts: every uint64 pair has a 128-bit product.
        hi, lo = op.mulw(a, b)
        return hi, lo

    @arc4.abimethod(readonly=True)
    def fits_in_64(self, a: UInt64, b: UInt64) -> bool:
        # A non-destructive overflow test. `a * b` would have aborted.
        hi, _lo = op.mulw(a, b)
        return hi == UInt64(0)
