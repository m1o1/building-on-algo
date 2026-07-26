from algopy import (
    Account, ARC4Contract, Global, GlobalState, LocalState, StateTotals,
    Txn, UInt64, arc4,
)


class Registry(
    ARC4Contract,
    state_totals=StateTotals(global_uints=1, global_bytes=1, local_uints=2),
):
    """A membership registry that hands out credits."""

    def __init__(self) -> None:
        self.admin = GlobalState(Global.creator_address)
        self.member_count = GlobalState(UInt64(0))
        self.joined_at = LocalState(UInt64)
        self.credits = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.joined_at[Txn.sender] = Global.round
        self.credits[Txn.sender] = UInt64(0)
        self.member_count.value += UInt64(1)

    @arc4.abimethod
    def award(self, member: Account, amount: UInt64) -> UInt64:
        assert Txn.sender == self.admin.value, "admin only"
        self.credits[member] += amount
        return self.credits[member]

    @arc4.abimethod(readonly=True)
    def credits_of(self, member: Account) -> UInt64:
        return self.credits[member]

    @arc4.abimethod(readonly=True)
    def member_since(self, member: Account) -> UInt64:
        return self.joined_at[member]

    @arc4.abimethod(readonly=True)
    def members(self) -> UInt64:
        return self.member_count.value

    @arc4.abimethod(allow_actions=["CloseOut"])
    def leave(self) -> None:
        self.member_count.value -= UInt64(1)
