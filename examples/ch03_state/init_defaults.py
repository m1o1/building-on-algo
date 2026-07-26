from algopy import ARC4Contract, Global, GlobalState, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Global.creator_address)
        self.member_count = GlobalState(UInt64(0))

    @arc4.abimethod(readonly=True)
    def admin_address(self) -> arc4.Address:
        return arc4.Address(self.admin.value)
