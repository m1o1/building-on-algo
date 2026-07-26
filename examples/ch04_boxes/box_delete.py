from algopy import ARC4Contract, Box, Global, Txn, UInt64, arc4


class Tally(ARC4Contract):
    def __init__(self) -> None:
        self.total = Box(UInt64, key=b"total")

    @arc4.abimethod
    def start(self) -> None:
        assert self.total.create(), "already started"

    @arc4.abimethod
    def stop(self) -> bool:
        assert Txn.sender == Global.creator_address, "creator only"
        existed = bool(self.total)
        del self.total.value
        return existed
