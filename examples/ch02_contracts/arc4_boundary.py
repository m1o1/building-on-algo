from algopy import ARC4Contract, UInt64, arc4


class Boundary(ARC4Contract):
    """`arc4.UInt64` is wire format. `UInt64` is a number. Convert at the edge."""

    @arc4.abimethod
    def add(self, a: arc4.UInt64, b: arc4.UInt64) -> arc4.UInt64:
        # Cross the boundary once on the way in...
        total: UInt64 = a.as_uint64() + b.as_uint64()
        # ...do the arithmetic in native types, and cross back once on the
        # way out. Nothing in between needs to know about ARC-4 at all.
        return arc4.UInt64(total)

    @arc4.abimethod
    def add_native(self, a: UInt64, b: UInt64) -> UInt64:
        # Or skip the boundary: PuyaPy encodes native `UInt64` as `uint64` in
        # the ABI too, so this method's argument and return types on the wire
        # are identical to `add`, with no conversions in the body. The ABI
        # name is part of the signature, so the selectors still differ:
        # fe6bdf69 for `add`, 5d767951 for this one.
        return a + b
