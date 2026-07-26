from algopy import (
    Account, ARC4Contract, Global, GlobalMap, GlobalState, LocalState,
    StateTotals, Txn, UInt64, arc4,
)


class Profile(arc4.Struct):
    joined_round: arc4.UInt64
    awards: arc4.UInt64


class Registry(
    ARC4Contract,
    state_totals=StateTotals(global_uints=17, global_bytes=1, local_bytes=1),
):
    """The same registry, with the three decisions corrected."""

    def __init__(self) -> None:
        self.admin = GlobalState(Global.creator_address)
        self.ever_joined = GlobalState(UInt64(0))
        self.credits = GlobalMap(Account, UInt64, key_prefix="c")
        self.profile = LocalState(Profile)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.profile[Txn.sender] = Profile(
            joined_round=arc4.UInt64(Global.round), awards=arc4.UInt64(0)
        )
        self.ever_joined.value += UInt64(1)

    @arc4.abimethod
    def award(self, member: Account, amount: UInt64) -> UInt64:
        assert Txn.sender == self.admin.value, "admin only"
        total = self.credits.get(member, default=UInt64(0)) + amount
        self.credits[member] = total
        return total

    @arc4.abimethod(readonly=True)
    def credits_of(self, member: Account) -> UInt64:
        return self.credits.get(member, default=UInt64(0))

    @arc4.abimethod(readonly=True)
    def member_since(self, member: Account) -> UInt64:
        if not member.is_opted_in(Global.current_application_id):
            return UInt64(0)
        blank = Profile(arc4.UInt64(0), arc4.UInt64(0))
        return self.profile.get(member, default=blank).joined_round.native

    @arc4.abimethod(readonly=True)
    def ever_joined_count(self) -> UInt64:
        return self.ever_joined.value

    @arc4.abimethod(allow_actions=["CloseOut"])
    def leave(self) -> None:
        owed = self.credits.get(Txn.sender, default=UInt64(0))
        assert owed == 0, "claim your credits before leaving"
