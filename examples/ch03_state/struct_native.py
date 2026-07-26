from algopy import ARC4Contract, GlobalState, Struct, UInt64, arc4


class Profile(Struct):
    joined_round: UInt64
    credits: UInt64


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.house = GlobalState(Profile(joined_round=UInt64(0), credits=UInt64(0)))

    @arc4.abimethod
    def award(self, amount: UInt64) -> UInt64:
        self.house.value.credits += amount
        return self.house.value.credits
