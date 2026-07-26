from algopy import Account, ARC4Contract, BoxMap, Txn, UInt64, arc4


class League(ARC4Contract):
    def __init__(self) -> None:
        self.score = BoxMap(Account, UInt64)

    @arc4.abimethod
    def record(self, points: UInt64) -> UInt64:
        total = self.score.get(Txn.sender, default=UInt64(0)) + points
        self.score[Txn.sender] = total
        return total

    @arc4.abimethod(readonly=True)
    def score_of(self, who: Account) -> UInt64:
        return self.score.get(who, default=UInt64(0))
