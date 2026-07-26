from algopy import ARC4Contract, Global, UInt64, arc4


class Clocks(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def now_round(self) -> UInt64:
        # The round currently being formed. Ledger-supplied, and the
        # only thing in this file that means "now".
        return Global.round

    @arc4.abimethod(readonly=True)
    def now_timestamp(self) -> UInt64:
        # The PREVIOUS block's timestamp -- one block behind the round
        # above, roughly 2.75 seconds in the past, always.
        return Global.latest_timestamp

    @arc4.abimethod(readonly=True)
    def rounds_since(self, past: UInt64) -> UInt64:
        assert past <= Global.round, "that round has not happened yet"
        return Global.round - past
