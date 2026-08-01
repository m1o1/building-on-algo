"""A LocalNet stand-in for the deployed ARC-21 randomness beacon.

ARC-21 is Final and has exactly two mandatory methods, `get` and `must_get`.
This contract implements both over global state, which is how the deployed
beacon stores its values too -- a box-backed beacon would make every consumer
declare a box reference it does not own.

`publish` is not part of ARC-21. It stands in for whatever the real beacon's
off-chain daemon does, and it is the reason this stub exists: on TestNet you
cannot ask a beacon to go silent, and a lottery whose beacon goes silent is
the branch the refund path is for.
"""

from algopy import (
    ARC4Contract,
    Bytes,
    Global,
    GlobalState,
    Txn,
    UInt64,
    arc4,
    op,
)

BEACON_VALUE_SIZE = 32


class BeaconStub(ARC4Contract):
    def __init__(self) -> None:
        self.value = GlobalState(Bytes(b""), key=b"v")
        self.published_for = GlobalState(UInt64(0), key=b"r")

    @arc4.abimethod
    def publish(self, rnd: UInt64, value: Bytes) -> None:
        """Not ARC-21. The knob a test needs and production does not have."""
        assert Txn.sender == Global.creator_address, "publisher only"
        assert value.length == UInt64(BEACON_VALUE_SIZE), "value is 32 bytes"
        self.value.value = value
        self.published_for.value = rnd

    @arc4.abimethod(readonly=True)
    def get(self, rnd: UInt64, user_data: Bytes) -> Bytes:
        """ARC-21. Absence is an empty slice, not an error."""
        if self.published_for.value != rnd:
            return Bytes(b"")
        if user_data.length == UInt64(0):
            return self.value.value
        return op.sha3_256(self.value.value + user_data)

    @arc4.abimethod(readonly=True)
    def must_get(self, rnd: UInt64, user_data: Bytes) -> Bytes:
        """ARC-21. Absence is an assert, which is why the lottery uses `get`."""
        assert self.published_for.value == rnd, "no value for that round"
        return self.get(rnd, user_data)
