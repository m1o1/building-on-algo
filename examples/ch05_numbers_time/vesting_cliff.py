from algopy import ARC4Contract, UInt64, arc4, op, subroutine


@subroutine
def vested_with_cliff(
    total: UInt64, start: UInt64, cliff: UInt64, end: UInt64, now: UInt64
) -> UInt64:
    # `<`, not `<=`: the grant unlocks AT the cliff round, not after it.
    if now < cliff:
        return UInt64(0)
    if now >= end:
        return total
    # The linear term measures from `start`, so arriving at the cliff
    # releases a lump sum -- the usual employee-equity meaning. Wide,
    # so a large grant cannot overflow the product.
    hi, lo = op.mulw(total, now - start)
    return op.divw(hi, lo, end - start)


class CliffVesting(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def vested_at(
        self,
        total: UInt64,
        start: UInt64,
        cliff: UInt64,
        end: UInt64,
        now: UInt64,
    ) -> UInt64:
        assert end > start, "schedule must have positive length"
        assert cliff >= start, "cliff before the schedule opens"
        assert cliff < end, "cliff at or after the schedule closes"
        return vested_with_cliff(total, start, cliff, end, now)
