from algopy import ARC4Contract, GlobalState, arc4


class Bid(arc4.Struct):
    amount: arc4.UInt64
    rounds: arc4.DynamicArray[arc4.UInt64]


class Auction(ARC4Contract):
    def __init__(self) -> None:
        self.best = GlobalState(arc4.UInt64(0))

    @arc4.abimethod(validate_encoding="unsafe_disabled")
    def submit(self, bid: Bid) -> None:
        bid.validate()
        assert bid.amount > self.best.value, "bid too low"
        self.best.value = bid.amount
