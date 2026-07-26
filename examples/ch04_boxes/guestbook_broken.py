from algopy import (
    Account, ARC4Contract, Box, Bytes, Global, GlobalState, Txn, UInt64, arc4,
)

ENTRY = 40  # a 32-byte address followed by an 8-byte round number


class Guestbook(ARC4Contract):
    """A conference guestbook. The desk checks names off, not the chain."""

    def __init__(self) -> None:
        self.organizer = GlobalState(Global.creator_address)
        self.entries = Box(Bytes, key=b"entries")

    @arc4.abimethod
    def sign(self) -> UInt64:
        record = Txn.sender.bytes + arc4.UInt64(Global.round).bytes
        self.entries.value = self.entries.get(default=Bytes()) + record
        return self.entries.length // UInt64(ENTRY)

    @arc4.abimethod(readonly=True)
    def has_signed(self, who: Account) -> bool:
        blob = self.entries.value
        offset = UInt64(0)
        while offset < blob.length:
            if blob[offset : offset + UInt64(32)] == who.bytes:
                return True
            offset += UInt64(ENTRY)
        return False

    @arc4.abimethod(readonly=True)
    def all_entries(self) -> Bytes:
        return self.entries.value

    @arc4.abimethod
    def clear(self) -> None:
        assert Txn.sender == self.organizer.value, "organizer only"
        del self.entries.value
