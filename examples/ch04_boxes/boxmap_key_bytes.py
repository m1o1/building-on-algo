from algopy import Account, ARC4Contract, BoxMap, Bytes, UInt64, arc4


class League(ARC4Contract):
    def __init__(self) -> None:
        self.score = BoxMap(Account, UInt64)

    @arc4.abimethod(readonly=True)
    def prefix(self) -> Bytes:
        return self.score.key_prefix

    @arc4.abimethod(readonly=True)
    def box_name(self, who: Account) -> Bytes:
        return self.score.box(who).key
