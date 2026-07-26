from algopy import ARC4Contract, LocalMap, StateTotals, String, Txn, UInt64, arc4


class Registry(ARC4Contract, state_totals=StateTotals(local_uints=4)):
    def __init__(self) -> None:
        self.tally = LocalMap(String, UInt64, key_prefix="t")

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.tally[Txn.sender, String("credits")] = UInt64(0)

    @arc4.abimethod
    def bump(self, bucket: String) -> UInt64:
        current = self.tally.get(Txn.sender, bucket, default=UInt64(0))
        self.tally[Txn.sender, bucket] = current + UInt64(1)
        return current + UInt64(1)
