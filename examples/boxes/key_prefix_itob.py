# book-example: mode=compile
from algopy import ARC4Contract, Bytes, UInt64, arc4, op


class Keys(ARC4Contract):
    @arc4.abimethod
    def keyed(self, prefix: Bytes, n: UInt64) -> Bytes:
        # Fixed width is the point: a prefix plus itob is a key you can always
        # take apart again, because the number is always the last eight bytes.
        return prefix + op.itob(n)
