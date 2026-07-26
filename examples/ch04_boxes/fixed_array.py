import typing

from algopy import ARC4Contract, Box, BoxMap, FixedArray, UInt64, arc4

Slots = FixedArray[UInt64, typing.Literal[4]]


class Bag(ARC4Contract):
    def __init__(self) -> None:
        self.bag = Box(Slots, key=b"b")
        self.seen = BoxMap(Slots, UInt64, key_prefix=b"s")

    @arc4.abimethod
    def fill(self) -> UInt64:
        slots = Slots.full(UInt64(0))
        slots[0] = UInt64(7)
        # no MBR pre-flight here; see guestbook_fixed.sign
        self.bag.value = slots.copy()  # a box value
        self.seen[slots] = UInt64(1)  # and a fixed-length box name
        return self.bag.value.freeze()[0]
