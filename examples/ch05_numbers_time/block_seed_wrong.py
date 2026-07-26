from algopy import ARC4Contract, Txn, UInt64, arc4, op


class LotteryWrong(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def draw(self, slots: UInt64) -> UInt64:
        assert slots > UInt64(0), "no slots to draw from"
        # WRONG, and not fixable by choosing a different round. Every
        # round a contract CAN read is already public when the caller
        # builds the transaction, so the caller computes the outcome
        # off-chain and submits only when it suits them.
        seed = op.Block.blk_seed(Txn.first_valid - UInt64(1))
        # `% slots` is also biased toward low values, which would matter
        # if the seed were secret. It is not, so it is the lesser flaw.
        return op.btoi(op.extract(seed, 24, 8)) % slots
