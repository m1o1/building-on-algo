from algopy import ARC4Contract, UInt64, arc4, subroutine

# There is no float on the AVM. A rate is an integer numerator over an
# agreed denominator; 10_000 basis points is one hundred percent.
BASIS_POINTS = 10_000


@subroutine
def fee_on(amount: UInt64, fee_bps: UInt64) -> UInt64:
    return (amount * fee_bps) // UInt64(BASIS_POINTS)


class Till(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def net_of_fee(self, amount: UInt64, fee_bps: UInt64) -> UInt64:
        assert fee_bps <= UInt64(BASIS_POINTS), "fee cannot exceed 100%"
        return amount - fee_on(amount, fee_bps)

    @arc4.abimethod(readonly=True)
    def fee_only(self, amount: UInt64, fee_bps: UInt64) -> UInt64:
        assert fee_bps <= UInt64(BASIS_POINTS), "fee cannot exceed 100%"
        return fee_on(amount, fee_bps)
