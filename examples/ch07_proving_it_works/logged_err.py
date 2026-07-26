from algopy import ARC4Contract, UInt64, arc4, logged_err


class Tiers(ARC4Contract):
    """`logged_err` in a value-returning method needs somewhere to land.

    As the last statement it deadlocks: the stubs type it `-> None`,
    so mypy wants a return and PuyaPy calls that return unreachable.
    """

    @arc4.abimethod(readonly=True)
    def rate_for(self, tier: UInt64) -> UInt64:
        rate = UInt64(0)
        if tier == UInt64(1):
            rate = UInt64(100)
        elif tier == UInt64(2):
            rate = UInt64(250)
        else:
            logged_err("unknownTier", "no such tier")
        return rate
