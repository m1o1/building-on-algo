from algopy import ARC4Contract, UInt64, arc4, op


class Contrast(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def quotient_low_only(self, a: UInt64, b: UInt64, d: UInt64) -> UInt64:
        # Wrong whenever the quotient needs more than 64 bits: the high
        # word is dropped and nothing complains.
        hi, lo = op.mulw(a, b)
        _qh, ql, _rh, _rl = op.divmodw(hi, lo, UInt64(0), d)
        return ql

    @arc4.abimethod(readonly=True)
    def remainder(self, a: UInt64, b: UInt64, d: UInt64) -> UInt64:
        # The remainder is the one thing `divw` cannot give you.
        hi, lo = op.mulw(a, b)
        _qh, _ql, _rh, rl = op.divmodw(hi, lo, UInt64(0), d)
        return rl
