from algopy import ARC4Contract, GlobalState, Txn, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Txn.sender)
        self.joining_fee = GlobalState(UInt64(0))

    @arc4.abimethod(create="require")
    def create(self, joining_fee: UInt64) -> None:
        self.joining_fee.value = joining_fee

    @arc4.abimethod(readonly=True)
    def fee(self) -> UInt64:
        return self.joining_fee.value
