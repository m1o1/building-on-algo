from algopy import ARC4Contract, GlobalState, StateTotals, UInt64, arc4


class Registry(
    ARC4Contract,
    state_totals=StateTotals(global_uints=8, global_bytes=2),
):
    def __init__(self) -> None:
        self.member_count = GlobalState(UInt64(0))

    @arc4.abimethod
    def bump(self) -> UInt64:
        self.member_count.value += UInt64(1)
        return self.member_count.value
