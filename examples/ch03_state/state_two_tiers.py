from algopy import (
    ARC4Contract,
    GlobalState,
    LocalState,
    StateTotals,
    Txn,
    UInt64,
    arc4,
)


class Registry(
    ARC4Contract,
    state_totals=StateTotals(global_uints=1, local_uints=1),
):
    def __init__(self) -> None:
        self.member_count = GlobalState(UInt64(0))
        self.credits = LocalState(UInt64)

    @arc4.abimethod(readonly=True)
    def my_credits(self) -> UInt64:
        return self.credits[Txn.sender]
