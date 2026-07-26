from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class Auction(ARC4Contract):
    def __init__(self) -> None:
        self.closes_at = GlobalState(UInt64(0))
        self.bids = GlobalState(UInt64(0))

    @arc4.abimethod
    def open_for(self, seconds: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.closes_at.value == UInt64(0), "already opened"
        assert seconds > UInt64(0), "empty window"
        self.closes_at.value = Global.latest_timestamp + seconds
        return self.closes_at.value

    @arc4.abimethod
    def bid(self) -> UInt64:
        assert self.closes_at.value != UInt64(0), "not open"
        # `<`, not `<=`: at exactly the deadline the auction is closed.
        assert Global.latest_timestamp < self.closes_at.value, "closed"
        self.bids.value += UInt64(1)
        return self.bids.value
