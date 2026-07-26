from algopy import ARC4Contract, arc4, op


class Gate(ARC4Contract):
    """Two spellings of the same opcode, with different diagnostics.

    Both methods compile to a bare `err`. Only the second produces an
    ARC-56 `sourceInfo` entry, which is the only thing that lets a
    client say anything more useful than the program counter.
    `op.err()` is `assert False` with the diagnostics deleted.
    """

    @arc4.abimethod
    def closed_for_now(self) -> None:
        op.err()

    @arc4.abimethod
    def also_closed(self) -> None:
        assert False, "closed for now"  # noqa: B011
