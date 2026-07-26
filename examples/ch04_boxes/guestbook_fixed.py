from algopy import (
    ARC4Contract, BoxMap, Global, GlobalState, Txn, UInt64, arc4, size_of,
)

BOX_FLAT = 2_500  # microAlgos per box, regardless of size
BOX_BYTE = 400  # microAlgos per byte of name plus contents


class Entry(arc4.Struct):
    who: arc4.Address
    signed_round: arc4.UInt64


class Guestbook(ARC4Contract):
    """A conference guestbook. One box per signature, priced before it is written."""

    def __init__(self) -> None:
        self.organizer = GlobalState(Global.creator_address)
        self.signed = GlobalState(UInt64(0))
        self.entry = BoxMap(UInt64, Entry, key_prefix=b"e")

    @arc4.abimethod
    def sign(self) -> UInt64:
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
        assert Txn.sender == self.organizer.value, "organizer only"
        assert index in self.entry, "no such entry"
        del self.entry[index]

    @arc4.abimethod(readonly=True)
    def entry_at(self, index: UInt64) -> Entry:
        return self.entry[index]

    @arc4.abimethod(readonly=True)
    def count(self) -> UInt64:
        return self.signed.value
