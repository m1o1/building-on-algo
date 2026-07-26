from algopy import ARC4Contract, GlobalState, arc4


class Profile(arc4.Struct):
    joined_round: arc4.UInt64
    credits: arc4.UInt64


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.house = GlobalState(Profile(arc4.UInt64(0), arc4.UInt64(0)))

    @arc4.abimethod(readonly=True)
    def house_credits(self) -> arc4.UInt64:
        return self.house.value.credits
