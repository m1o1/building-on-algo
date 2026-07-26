from algopy import ARC4Contract, UInt64, arc4, op, subroutine


@subroutine
def mul_div(a: UInt64, b: UInt64, d: UInt64) -> UInt64:
    """`(a * b) // d`, computed through the 128-bit intermediate.

    Aborts rather than truncating: `divw` refuses unless `d > hi`.
    """
    assert d != UInt64(0), "divide by zero"
    hi, lo = op.mulw(a, b)
    return op.divw(hi, lo, d)


class Rates(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def scale(self, amount: UInt64, num: UInt64, den: UInt64) -> UInt64:
        return mul_div(amount, num, den)

    @arc4.abimethod(readonly=True)
    def share_of(self, pot: UInt64, mine: UInt64, total: UInt64) -> UInt64:
        assert mine <= total, "share exceeds the whole"
        return mul_div(pot, mine, total)
