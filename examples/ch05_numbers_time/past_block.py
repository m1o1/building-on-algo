from algopy import ARC4Contract, Txn, UInt64, arc4, op


class Lookback(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def previous_timestamp(self) -> UInt64:
        # The window is anchored to the TRANSACTION's fields, not to the
        # current round: it runs to `Txn.first_valid - 1` and no further.
        # `- 1` cannot underflow in practice: algod never builds a
        # transaction with `first_valid == 0`. A hand-rolled one would.
        return op.Block.blk_timestamp(Txn.first_valid - UInt64(1))

    @arc4.abimethod(readonly=True)
    def same_thing_without_the_lookup(self) -> UInt64:
        # Identical value, and it can never fall outside the window.
        return Txn.first_valid_time
