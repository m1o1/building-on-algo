from algopy import ARC4Contract, Bytes, Global, String, Txn, UInt64, arc4, op

# A label longer than this makes `describe` awkward to read and costs the
# creator global-state bytes for nothing.
MAX_LABEL_BYTES = 32


class Counter(ARC4Contract):
    """A public counter with a label the creator chooses at creation."""

    def __init__(self) -> None:
        self.count = UInt64(0)
        self.label = String("visits")

    @arc4.abimethod(create="require")
    def create(self, label: arc4.String) -> None:
        text = label.native
        assert text.bytes.length > UInt64(0), "create: label must not be empty"
        assert text.bytes.length <= UInt64(MAX_LABEL_BYTES), "create: label too long"
        self.label = text

    @arc4.abimethod(readonly=True)
    def bump(self) -> arc4.UInt64:
        self.count += UInt64(1)
        return arc4.UInt64(self.count)

    @arc4.abimethod(readonly=True)
    def current(self) -> arc4.UInt64:
        return arc4.UInt64(self.count)

    @arc4.abimethod(readonly=True)
    def describe(self) -> Bytes:
        return self.label.bytes + op.itob(self.count)

    @arc4.abimethod(create="allow")
    def reset(self) -> None:
        assert Txn.sender == Global.creator_address, "reset: creator only"
        self.count = UInt64(0)
