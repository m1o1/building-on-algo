from algopy import Account, ARC4Contract, BoxMap, UInt64, arc4


class League(ARC4Contract):
    def __init__(self) -> None:
        self.score = BoxMap(Account, UInt64)

    @arc4.abimethod(readonly=True)
    def score_size(self, who: Account) -> UInt64:
        return self.score.box(who).length
