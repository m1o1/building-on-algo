from algopy import (ARC4Contract, Global, GlobalState, Txn, UInt64, arc4,
                    logged_assert)


class LoggedRegistry(ARC4Contract):
    """The same two checks, written to ARC-65.

    Each logs `ERR:<code>[:<message>]` and then fails, so the reason
    is in the bytecode and reaches a caller who has no app spec.
    """

    def __init__(self) -> None:
        self.entries = GlobalState(UInt64(0))

    @arc4.abimethod
    def record(self, count: UInt64) -> UInt64:
        logged_assert(Txn.sender == Global.creator_address, "ownerOnly")
        logged_assert(count > UInt64(0), "positiveCount", "count must be > 0")
        self.entries.value += count
        return self.entries.value
