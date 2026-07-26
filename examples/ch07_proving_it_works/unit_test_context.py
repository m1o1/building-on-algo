from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class Deadline(ARC4Contract):
    """Behaviour that depends on the clock, tested without waiting.

    `algorand-python-testing` runs these methods as ordinary Python
    against an in-memory ledger you are allowed to write to, so "after
    the deadline" becomes an assignment instead of a sleep.
    """

    def __init__(self) -> None:
        self.owner = GlobalState(Global.creator_address)
        self.closes_at = GlobalState(UInt64(0))
        self.entries = GlobalState(UInt64(0))

    @arc4.abimethod
    def open_until(self, closes_at: UInt64) -> None:
        assert Txn.sender == self.owner.value, "owner only"
        assert self.closes_at.value == UInt64(0), "already open"
        assert closes_at > Global.latest_timestamp, "deadline already passed"
        self.closes_at.value = closes_at

    @arc4.abimethod
    def enter(self) -> UInt64:
        assert self.closes_at.value != UInt64(0), "not open"
        assert Global.latest_timestamp < self.closes_at.value, "closed"
        self.entries.value += UInt64(1)
        return self.entries.value
