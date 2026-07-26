from algopy import ARC4Contract, Bytes, String, UInt64, arc4


class Text(ARC4Contract):
    """Three ways to hold text, and the one difference that separates them."""

    @arc4.abimethod
    def length(self, s: String) -> UInt64:
        # `String` supports neither `len()` nor indexing: the AVM has no UTF-8
        # support, so the only honest answer is a count of bytes.
        return s.bytes.length

    @arc4.abimethod
    def join(self, a: String, b: String) -> String:
        # Concatenation is cheap precisely because a `String` carries no
        # length prefix that would have to be rewritten.
        return a + " " + b

    @arc4.abimethod
    def to_arc4(self, s: String) -> arc4.String:
        # `arc4.String` is the same UTF-8 text with a two-byte big-endian
        # length prefix in front of it. That prefix is the whole difference.
        return arc4.String(s)

    @arc4.abimethod
    def raw(self, s: String) -> Bytes:
        # `Bytes` is the untyped form underneath both: no prefix, no promise
        # that the contents are text at all.
        return s.bytes
