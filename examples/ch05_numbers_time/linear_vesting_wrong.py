from algopy import ARC4Contract, UInt64, arc4, subroutine


@subroutine
def vested_wrong(
    total: UInt64, start: UInt64, end: UInt64, now: UInt64
) -> UInt64:
    # WRONG. The division runs first, so the ratio is 0 for the whole
    # schedule and 1 only at the very end: this pays nothing at all
    # until the last round, then everything at once. The guards are gone
    # too, so `now < start` underflows and `end == start` divides by zero.
    return ((now - start) // (end - start)) * total


class VestingWrong(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def vested_at(
        self, total: UInt64, start: UInt64, end: UInt64, now: UInt64
    ) -> UInt64:
        return vested_wrong(total, start, end, now)
