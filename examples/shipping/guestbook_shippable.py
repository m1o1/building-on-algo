# book-example: mode=compile
from algopy import (ARC4Contract, BoxMap, Global, GlobalState, Txn, UInt64,
                    arc4, itxn, log, logged_assert, size_of)

BOX_FLAT = 2_500
BOX_BYTE = 400


class Entry(arc4.Struct):
    who: arc4.Address
    signed_round: arc4.UInt64


class Signed(arc4.Struct):
    """The event. Its class name and field types are the ARC-28 signature."""

    who: arc4.Address
    index: arc4.UInt64


class Guestbook(ARC4Contract):
    """Chapter 5's guestbook, with the three things operating it needs."""

    def __init__(self) -> None:
        self.organizer = GlobalState(Global.creator_address)
        # Signatures ever taken. Never goes down, because it supplies the box
        # key and a retired index must never be handed out twice.
        self.signed = GlobalState(UInt64(0))
        # Boxes present right now. This is the one `close` asks about, and it
        # is a separate number for the reason Chapter 5 gives: the count a
        # signature's index is drawn from cannot also be the count of what is
        # left, or retiring an entry silently re-points the next signature at
        # a box that already exists.
        self.live = GlobalState(UInt64(0))
        self.frozen = GlobalState(UInt64(0))
        self.entry = BoxMap(UInt64, Entry, key_prefix=b"e")

    @arc4.abimethod
    def sign(self) -> UInt64:
        index = self.signed.value
        name_len = self.entry.key_prefix.length + UInt64(8)
        cost = UInt64(BOX_FLAT) + UInt64(BOX_BYTE) * (name_len + size_of(Entry))
        app = Global.current_application_address
        logged_assert(app.balance >= app.min_balance + cost,
                      "underfunded", "top up the app account")
        self.entry[index] = Entry(
            who=arc4.Address(Txn.sender), signed_round=arc4.UInt64(Global.round)
        )
        self.signed.value = index + UInt64(1)
        self.live.value += UInt64(1)
        # Two logs, deliberately different in kind. This one is raw bytes with
        # no framing at all; the emit below carries a four-byte selector; and
        # the compiler adds a third for the return value. One call, three
        # shapes, which is what a client has to tell apart.
        log(b"signed:", index, sep=b" ")
        arc4.emit(Signed(arc4.Address(Txn.sender), arc4.UInt64(index)))
        return index

    @arc4.abimethod(allow_actions=["UpdateApplication"])
    def update(self) -> None:
        assert Txn.sender == self.organizer.value, "organizer only"
        assert self.frozen.value == UInt64(0), "this guestbook is frozen"

    @arc4.abimethod
    def freeze(self) -> None:
        assert Txn.sender == self.organizer.value, "organizer only"
        self.frozen.value = UInt64(1)

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def close(self) -> None:
        assert Txn.sender == self.organizer.value, "organizer only"
        # Boxes outlive the application, and their minimum balance with them,
        # so the account cannot be closed until every one is gone.
        logged_assert(self.live.value == UInt64(0),
                      "entriesRemain", "delete every entry first")
        itxn.Payment(
            receiver=self.organizer.value,
            close_remainder_to=self.organizer.value,
            fee=UInt64(0),
        ).submit()

    @arc4.abimethod
    def retire(self, index: UInt64) -> None:
        assert Txn.sender == self.organizer.value, "organizer only"
        assert index in self.entry, "no such entry"
        del self.entry[index]
        self.live.value -= UInt64(1)

    @arc4.abimethod(readonly=True)
    def entry_at(self, index: UInt64) -> Entry:
        return self.entry[index]

    @arc4.abimethod(readonly=True)
    def count(self) -> UInt64:
        return self.signed.value
