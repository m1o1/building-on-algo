from algopy import ARC4Contract, UInt64, arc4


class Meter(ARC4Contract):
    """`readonly=True` is a promise to the caller, not a rule for you."""

    def __init__(self) -> None:
        self.count = UInt64(0)

    @arc4.abimethod
    def bump(self) -> UInt64:
        self.count += UInt64(1)
        return self.count

    @arc4.abimethod(readonly=True)
    def current(self) -> UInt64:
        # Marked readonly, so clients answer this by simulating rather than
        # submitting: no fee, no round to wait for, no ledger change.
        return self.count
