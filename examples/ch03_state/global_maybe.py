from algopy import ARC4Contract, GlobalState, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.joining_fee = GlobalState(UInt64)

    @arc4.abimethod
    def raise_fee(self, delta: UInt64) -> UInt64:
        fee, exists = self.joining_fee.maybe()
        assert exists, "no fee has ever been set"
        self.joining_fee.value = fee + delta
        return self.joining_fee.value
