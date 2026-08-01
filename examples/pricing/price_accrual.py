# book-example: mode=unit
from algopy import (ARC4Contract, BigUInt, Global, GlobalState, UInt64, arc4,
                    op)

MAX_UINT64 = 18_446_744_073_709_551_615


class Accrual(ARC4Contract):
    """A price multiplied by the time it held, added up."""
    def __init__(self) -> None:
        self.cumulative = GlobalState(BigUInt(0))
        self.last_update = GlobalState(UInt64(0))
        self.price = GlobalState(UInt64(0))

    @arc4.abimethod
    def touch(self, new_price: UInt64) -> None:
        """Take a scaled price; credit the interval to the one it replaces."""
        now = Global.latest_timestamp
        last = self.last_update.value
        if last > UInt64(0) and now > last:
            # The price that HELD over the interval, credited before it is
            # replaced. The new one did not exist for any of that time.
            self.cumulative.value += (BigUInt(self.price.value)
                                      * BigUInt(now - last))
        self.last_update.value = now
        self.price.value = new_price

    @arc4.abimethod(readonly=True)
    def average_since(self, past: arc4.UInt512, past_time: UInt64) -> UInt64:
        """Two snapshots differenced over their gap."""
        assert self.last_update.value > past_time, "no interval"
        gap = BigUInt(self.last_update.value - past_time)
        mean = (self.cumulative.value - past.as_biguint()) // gap
        # Not provable: the caller picks the snapshot, so nothing bounds this.
        assert mean <= BigUInt(MAX_UINT64), "average does not fit a UInt64"
        return op.btoi(mean.bytes)
