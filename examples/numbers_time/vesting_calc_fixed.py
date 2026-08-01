# book-example: mode=compile
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4, op


class VestingCalculator(ARC4Contract):
    """Reports how much of a grant has vested so far.

    It only reports. Actually paying the beneficiary needs an inner
    transaction, which is the next chapter.
    """

    def __init__(self) -> None:
        self.total = GlobalState(UInt64(0))
        self.start = GlobalState(UInt64(0))
        self.end = GlobalState(UInt64(0))
        self.configured = GlobalState(False)

    @arc4.abimethod
    def configure(self, total: UInt64, start: UInt64, end: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert not self.configured.value, "already configured"
        assert end > start, "schedule must have positive length"
        self.total.value = total
        self.start.value = start
        self.end.value = end
        self.configured.value = True

    @arc4.abimethod(readonly=True)
    def vested_now(self) -> UInt64:
        assert self.configured.value, "not configured"
        now = Global.round
        if now <= self.start.value:
            return UInt64(0)
        if now >= self.end.value:
            return self.total.value
        hi, lo = op.mulw(self.total.value, now - self.start.value)
        return op.divw(hi, lo, self.end.value - self.start.value)

    @arc4.abimethod(readonly=True)
    def schedule(self) -> tuple[UInt64, UInt64, UInt64]:
        assert self.configured.value, "not configured"
        return self.total.value, self.start.value, self.end.value
