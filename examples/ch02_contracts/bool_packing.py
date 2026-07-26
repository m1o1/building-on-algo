import typing

from algopy import ARC4Contract, arc4

Flags: typing.TypeAlias = arc4.StaticArray[arc4.Bool, typing.Literal[8]]


class Packed(ARC4Contract):
    """Adjacent ARC-4 bools share a byte. Bools with a gap between them cannot."""

    @arc4.abimethod
    def flags(self) -> Flags:
        # Eight bools in one byte: on, off, on, off... encodes as 0xaa.
        on, off = arc4.Bool(True), arc4.Bool(False)
        return Flags(on, off, on, off, on, off, on, off)

    @arc4.abimethod
    def paired(self) -> arc4.Tuple[arc4.Bool, arc4.Bool, arc4.UInt64]:
        # Nine bytes: the two bools pack into one, then the uint64 follows.
        return arc4.Tuple((arc4.Bool(True), arc4.Bool(True), arc4.UInt64(7)))
