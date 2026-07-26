from algopy import ARC4Contract, Bytes, UInt64, arc4, op


class RoundTrip(ARC4Contract):
    """Turn a number into a byte string and back without losing it."""

    @arc4.abimethod
    def encode(self, n: UInt64) -> Bytes:
        # `itob` always produces exactly eight bytes, big-endian, zero-padded.
        # The number 7 becomes 00 00 00 00 00 00 00 07, not the byte 07.
        return op.itob(n)

    @arc4.abimethod
    def decode(self, raw: Bytes) -> UInt64:
        # `btoi` reads at most eight bytes and rejects anything longer.
        assert raw.length <= UInt64(8), "decode: at most eight bytes"
        return op.btoi(raw)

    @arc4.abimethod
    def round_trips(self, n: UInt64) -> bool:
        # The round trip is exact for every value a uint64 can hold, which is
        # what makes itob a safe way to build a storage key out of a number.
        return op.btoi(op.itob(n)) == n

    @arc4.abimethod
    def keyed(self, prefix: Bytes, n: UInt64) -> Bytes:
        # Fixed width is the point: a prefix plus itob is a key you can always
        # take apart again, because the number is always the last eight bytes.
        return prefix + op.itob(n)
