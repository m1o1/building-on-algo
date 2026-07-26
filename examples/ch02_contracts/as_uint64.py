from algopy import Account, ARC4Contract, BigUInt, String, UInt64, arc4


class Unwrap(ARC4Contract):
    """Every ARC-4 type unwraps. The method you call depends on the type."""

    @arc4.abimethod
    def small(self, n: arc4.UInt64) -> UInt64:
        # Integers up to 64 bits: `as_uint64()`. The `.native` property still
        # exists and still works, but it is deprecated in favour of this.
        return n.as_uint64()

    @arc4.abimethod
    def large(self, n: arc4.UInt512) -> BigUInt:
        # Wider integers do not fit in a uint64, so they unwrap to
        # `BigUInt`, which is carried as a byte string.
        return n.as_biguint()

    @arc4.abimethod
    def text(self, s: arc4.String) -> String:
        # Everything that is not an integer keeps `.native`, undeprecated.
        return s.native

    @arc4.abimethod
    def who(self, a: arc4.Address) -> Account:
        return a.native

    @arc4.abimethod
    def flag(self, b: arc4.Bool) -> bool:
        return b.native
