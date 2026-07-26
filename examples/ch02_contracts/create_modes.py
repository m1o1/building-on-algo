from algopy import ARC4Contract, Global, String, Txn, UInt64, arc4


class Modes(ARC4Contract):
    """`create` decides which application IDs a method will answer to."""

    def __init__(self) -> None:
        self.count = UInt64(0)
        self.label = String("visits")

    @arc4.abimethod(create="require")
    def create(self, label: arc4.String) -> None:
        # "require": the router asserts the application ID is zero, so this
        # method exists only for the transaction that brings the app into
        # being. It can never be called again.
        self.label = label.native

    @arc4.abimethod
    def bump(self) -> UInt64:
        # "disallow" is the default, and it is the one you want by default:
        # the router asserts the application ID is NOT zero.
        self.count += UInt64(1)
        return self.count

    @arc4.abimethod
    def reset(self) -> None:
        assert Txn.sender == Global.creator_address, "reset: creator only"
        self.count = UInt64(0)
