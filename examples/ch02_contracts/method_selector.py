from algopy import ARC4Contract, Bytes, UInt64, arc4, gtxn


class Selectors(ARC4Contract):
    """A selector is four bytes of a hash of the method's written signature."""

    def __init__(self) -> None:
        self.count = UInt64(0)

    @arc4.abimethod
    def bump(self) -> UInt64:
        self.count += UInt64(1)
        return self.count

    @arc4.abimethod(readonly=True)
    def selector_of_bump(self) -> Bytes:
        # sha512_256("bump()uint64"), first four bytes, resolved at compile
        # time. The signature string is the name and the ABI types, nothing
        # else: rename the Python method and the selector is unchanged, but
        # change an argument type and every existing caller breaks.
        return arc4.arc4_signature("bump()uint64")

    @arc4.abimethod
    def only_beside_bump(self, other: gtxn.ApplicationCallTransaction) -> None:
        # Routing is a byte comparison against argument zero, which means you
        # can do the same comparison yourself when you need to.
        assert other.num_app_args > UInt64(0), "grouped call has no selector"
        assert other.app_args(0) == arc4.arc4_signature(
            "bump()uint64"
        ), "grouped call is not bump()"
