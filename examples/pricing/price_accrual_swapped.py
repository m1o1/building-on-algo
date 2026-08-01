# book-example: mode=compile
from algopy import ARC4Contract, BigUInt, Global, GlobalState, UInt64, arc4


class Accrual(ARC4Contract):
    """The same accrual, crediting the interval to the wrong price."""
    def __init__(self) -> None:
        self.cumulative = GlobalState(BigUInt(0))
        self.last_update = GlobalState(UInt64(0))
        self.price = GlobalState(UInt64(0))

    @arc4.abimethod
    def touch(self, new_price: UInt64) -> None:
        now = Global.latest_timestamp
        last = self.last_update.value
        self.price.value = new_price            # replaced first, and that is
        if last > UInt64(0) and now > last:     # the whole of the defect
            self.cumulative.value += (BigUInt(self.price.value)
                                      * BigUInt(now - last))
        self.last_update.value = now
