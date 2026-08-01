# book-example: mode=compile
from algopy import (
    ARC4Contract, BoxMap, Global, GlobalState, Txn, UInt64, arc4,
    logged_assert, size_of,
)

BOX_FLAT = 2_500
BOX_BYTE = 400


class Entry(arc4.Struct):
    who: arc4.Address
    signed_round: arc4.UInt64


class PauseToggled(arc4.Struct):
    """The announcement. A silent switch is indistinguishable from an outage."""

    paused: arc4.Bool


class PausableGuestbook(ARC4Contract):
    """Chapter 5's guestbook wearing Example 10-8's switch, made audible.

    The flag and the guard are Chapter 10's pattern unchanged. What this
    chapter adds is the emit: the toggle announces itself, so a dashboard
    learns the switch moved without polling global state.
    """

    def __init__(self) -> None:
        self.organizer = GlobalState(Global.creator_address)
        self.signed = GlobalState(UInt64(0))
        self.paused = GlobalState(False)
        self.entry = BoxMap(UInt64, Entry, key_prefix=b"e")

    @arc4.abimethod
    def set_paused(self, paused: bool) -> None:
        assert Txn.sender == self.organizer.value, "organizer only"
        self.paused.value = paused
        arc4.emit(PauseToggled(arc4.Bool(paused)))

    @arc4.abimethod
    def sign(self) -> UInt64:
        # The guard, first, on the one method the public can change state
        # with. `logged_assert`, because "paused" is the rejection whose
        # reader is a wallet deciding what to tell its user.
        logged_assert(not self.paused.value, "paused", "signing is suspended")
        index = self.signed.value
        name_len = self.entry.key_prefix.length + UInt64(8)
        cost = UInt64(BOX_FLAT) + UInt64(BOX_BYTE) * (name_len + size_of(Entry))
        app = Global.current_application_address
        assert app.balance >= app.min_balance + cost, "app account underfunded"
        self.entry[index] = Entry(
            who=arc4.Address(Txn.sender), signed_round=arc4.UInt64(Global.round)
        )
        self.signed.value = index + UInt64(1)
        return index

    @arc4.abimethod
    def retire(self, index: UInt64) -> None:
        # Not guarded, deliberately. The pause stops the public; the tools an
        # organizer reaches for during an incident have to work during one.
        assert Txn.sender == self.organizer.value, "organizer only"
        assert index in self.entry, "no such entry"
        del self.entry[index]

    @arc4.abimethod(readonly=True)
    def count(self) -> UInt64:
        return self.signed.value
