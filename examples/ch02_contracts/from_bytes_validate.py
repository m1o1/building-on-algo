from algopy import ARC4Contract, Bytes, UInt64, arc4


class Decoding(ARC4Contract):
    """`from_bytes` reinterprets. It does not check. `validate` checks."""

    @arc4.abimethod
    def size(self, raw: Bytes) -> UInt64:
        # `from_bytes` is free: it relabels the bytes as an ARC-4 value and
        # performs no checking whatsoever. If `raw` is b"\x00\x05" with no
        # payload behind it, this call still succeeds...
        text = arc4.String.from_bytes(raw)
        # ...and the failure surfaces here, or later, or not at all.
        return text.bytes.length

    @arc4.abimethod
    def checked_size(self, raw: Bytes) -> UInt64:
        text = arc4.String.from_bytes(raw)
        # `validate` is the check `from_bytes` skipped: it rejects a length
        # prefix that disagrees with the bytes that follow it.
        text.validate()
        return text.native.bytes.length

    @arc4.abimethod
    def encode(self, n: arc4.UInt64) -> Bytes:
        # The other direction is always safe, because the value was already
        # a well-formed ARC-4 encoding.
        return n.bytes
