from algopy import ARC4Contract, Global, UInt64, arc4


class Status(ARC4Contract):
    """One call, several values, each one still typed on the far side."""

    def __init__(self) -> None:
        self.count = UInt64(0)

    @arc4.abimethod(readonly=True)
    def snapshot(self) -> arc4.Tuple[arc4.String, arc4.UInt64, arc4.Bool]:
        return arc4.Tuple(
            (
                arc4.String("visits"),
                arc4.UInt64(self.count),
                arc4.Bool(self.count > UInt64(0)),
            )
        )
