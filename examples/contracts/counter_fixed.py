# book-example: mode=compile
from algopy import ARC4Contract, Global, String, Txn, UInt64, arc4

# A label longer than this makes `describe` awkward to read and costs the
# creator global-state bytes for nothing.
MAX_LABEL_BYTES = 32


class Counter(ARC4Contract):
    """A public counter with a label the creator chooses at creation.

    The three corrections over the first draft: `bump` writes state, so it
    no longer claims `readonly` and the client submits a real transaction;
    `describe` returns a typed tuple a generated client can decode instead
    of raw bytes; and `reset` accepts the default `create="disallow"`, so
    it can only be aimed at a counter that already exists.
    """

    def __init__(self) -> None:
        self.count = UInt64(0)
        self.label = String("visits")

    @arc4.abimethod(create="require")
    def create(self, label: arc4.String) -> None:
        text = label.native
        assert text.bytes.length > UInt64(0), "create: label must not be empty"
        assert text.bytes.length <= UInt64(MAX_LABEL_BYTES), "create: label too long"
        self.label = text

    @arc4.abimethod
    def bump(self) -> arc4.UInt64:
        self.count += UInt64(1)
        return arc4.UInt64(self.count)

    @arc4.abimethod(readonly=True)
    def current(self) -> arc4.UInt64:
        return arc4.UInt64(self.count)

    @arc4.abimethod(readonly=True)
    def describe(self) -> arc4.Tuple[arc4.String, arc4.UInt64]:
        return arc4.Tuple((arc4.String(self.label), arc4.UInt64(self.count)))

    @arc4.abimethod
    def reset(self) -> None:
        assert Txn.sender == Global.creator_address, "reset: creator only"
        self.count = UInt64(0)
