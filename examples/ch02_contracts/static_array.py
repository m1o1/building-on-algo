import typing

from algopy import ARC4Contract, UInt64, arc4

Scores: typing.TypeAlias = arc4.StaticArray[arc4.UInt64, typing.Literal[3]]


class Fixed(ARC4Contract):
    """A fixed-length array has no length prefix, so its size is known."""

    @arc4.abimethod
    def make(self) -> Scores:
        return Scores(arc4.UInt64(10), arc4.UInt64(20), arc4.UInt64(30))

    @arc4.abimethod
    def total(self, s: Scores) -> UInt64:
        # Twenty-four bytes on the wire: three uint64s and nothing else.
        return s[0].as_uint64() + s[1].as_uint64() + s[2].as_uint64()
