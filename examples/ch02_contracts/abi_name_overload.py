from algopy import ARC4Contract, arc4


class Adder(ARC4Contract):
    """Two Python methods, one ABI name, two selectors."""

    @arc4.abimethod(name="add")
    def add_one(self, a: arc4.UInt64) -> arc4.UInt64:
        # add(uint64)uint64 -> selector ff9a73d6
        return arc4.UInt64(a.as_uint64() + 1)

    @arc4.abimethod(name="add")
    def add_two(self, a: arc4.UInt64, b: arc4.UInt64) -> arc4.UInt64:
        # add(uint64,uint64)uint64 -> selector fe6bdf69
        return arc4.UInt64(a.as_uint64() + b.as_uint64())
