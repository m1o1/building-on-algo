from algopy import ARC4Contract, BoxMap, Global, Txn, UInt64, arc4

SEASON_ROUNDS = 1_000_000


class Slot(arc4.Struct):
    owner: arc4.Address
    season: arc4.UInt64


class League(ARC4Contract):
    def __init__(self) -> None:
        self.score = BoxMap(Slot, UInt64, key_prefix=b"s")

    @arc4.abimethod
    def record(self, points: UInt64) -> UInt64:
        season = Global.round // UInt64(SEASON_ROUNDS)  # not a caller argument
        key = Slot(owner=arc4.Address(Txn.sender), season=arc4.UInt64(season))
        total = self.score.get(key, default=UInt64(0)) + points
        self.score[key] = total
        return total
