from algopy import (ARC4Contract, Global, GlobalState, Txn, UInt64, arc4, op,
                    subroutine)


@subroutine
def vested(total: UInt64, start: UInt64, end: UInt64, now: UInt64) -> UInt64:
    if now <= start:
        return UInt64(0)
    if now >= end:
        return total
    # Multiply first, through 128 bits; `divw` floors toward the pool.
    hi, lo = op.mulw(total, now - start)
    return op.divw(hi, lo, end - start)


class Vesting(ARC4Contract):
    def __init__(self) -> None:
        self.total = GlobalState(UInt64(0))
        self.start = GlobalState(UInt64(0))
        self.end = GlobalState(UInt64(0))

    @arc4.abimethod
    def configure(self, total: UInt64, start: UInt64, end: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.end.value == UInt64(0), "already configured"
        assert end > start, "schedule must have positive length"
        self.total.value = total
        self.start.value = start
        self.end.value = end

    @arc4.abimethod(readonly=True)
    def vested_now(self) -> UInt64:
        assert self.end.value != UInt64(0), "not configured"
        now = Global.round
        return vested(self.total.value, self.start.value, self.end.value, now)
