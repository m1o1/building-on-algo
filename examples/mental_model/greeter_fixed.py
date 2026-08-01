# book-example: mode=compile
"""The greeter with its three corrections applied (Chapter 2).

Corrections against the first pass: every assertion carries a message, the
returned greeting is bounded below the log budget, and the shutdown guard
names an account that exists and can sign.
"""

from algopy import ARC4Contract, Global, String, Txn, UInt64, arc4

MAX_NAME_BYTES = 64


class Greeter(ARC4Contract):
    """Greet anyone who asks. Let the people who deployed it shut it down."""

    @arc4.abimethod
    def greet(self, name: String) -> String:
        length = name.bytes.length
        assert length > UInt64(0), "greet: name must not be empty"
        assert length <= UInt64(MAX_NAME_BYTES), "greet: name is over 64 bytes"
        return "Hello, " + name

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def shut_down(self) -> None:
        assert Txn.sender == Global.creator_address, "shut_down: creator only"
