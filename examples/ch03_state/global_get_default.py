from algopy import ARC4Contract, GlobalState, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.joining_fee = GlobalState(UInt64)

    @arc4.abimethod(readonly=True)
    def current_fee(self) -> UInt64:
        return self.joining_fee.get(default=UInt64(1000))
