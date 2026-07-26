from algopy import ARC4Contract, String, arc4


class Smallest(ARC4Contract):
    """One method, one answer, no memory. This is a whole application."""

    @arc4.abimethod
    def ping(self) -> String:
        return String("pong")
