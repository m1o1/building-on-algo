import typing

from algopy import ARC4Contract, UInt64, arc4

Names: typing.TypeAlias = arc4.DynamicArray[arc4.String]


class Growable(ARC4Contract):
    """A dynamic array carries its own length, so it can be appended to."""

    @arc4.abimethod
    def make(self, first: arc4.String) -> Names:
        names = Names()
        names.append(first)
        names.append(arc4.String("anon"))
        return names

    @arc4.abimethod
    def count(self, names: Names) -> UInt64:
        return names.length
