from algopy import ARC4Contract, GlobalState, Txn, UInt64, arc4


class Drainable(ARC4Contract):
    def __init__(self) -> None:
        self.start = GlobalState(UInt64(0))

    @arc4.abimethod(readonly=True)
    def elapsed(self) -> UInt64:
        # WRONG. `Txn.last_valid` is chosen by the caller, who may set
        # it up to 1000 rounds ahead -- about 46 minutes of elapsed time
        # conjured on every call, free, and repeatable.
        return Txn.last_valid - self.start.value
