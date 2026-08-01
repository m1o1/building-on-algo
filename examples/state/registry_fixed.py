# book-example: mode=compile
from algopy import (
    Account, ARC4Contract, Global, GlobalMap, GlobalState, LocalState,
    StateTotals, Txn, UInt64, arc4,
)


class Profile(arc4.Struct):
    """One member's statistics, packed into a single local byte slot."""
    joined_round: arc4.UInt64
    awards: arc4.UInt64


class Registry(
    ARC4Contract,
    state_totals=StateTotals(global_uints=17, global_bytes=1, local_bytes=1),
):
    """A membership registry that hands out credits.

    The three corrections over the first draft: the two per-member numbers
    are packed into one struct in one local byte slot; the credit balance
    is a liability and lives in the contract's own global map, which a
    departing member cannot erase; and the count only counts joins, because
    a clear-state can never be observed.
    """

    def __init__(self) -> None:
        self.admin = GlobalState(Global.creator_address)
        self.ever_joined = GlobalState(UInt64(0))
        self.credits = GlobalMap(Account, UInt64, key_prefix="c")
        self.profile = LocalState(Profile)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.profile[Txn.sender] = Profile(
            joined_round=arc4.UInt64(Global.round),
            awards=arc4.UInt64(0),
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
        return self.profile[member].joined_round.as_uint64()

    @arc4.abimethod(readonly=True)
    def ever_joined_count(self) -> UInt64:
        return self.ever_joined.value

    @arc4.abimethod(allow_actions=["CloseOut"])
    def leave(self) -> None:
        owed = self.credits.get(Txn.sender, default=UInt64(0))
        assert owed == 0, "claim your credits before leaving"
