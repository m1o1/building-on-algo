from algopy import ARC4Contract, Global, String, Txn, UInt64, arc4

# The ABI return value is written to the transaction log, and an application
# call may log 1,024 bytes in total. A bound well under that is a bound the
# caller can understand.
MAX_NAME_BYTES = 64


class Greeter(ARC4Contract):
    """Greet anyone who asks. Let the account that created it shut it down."""

    @arc4.abimethod
    def greet(self, name: String) -> String:
        length = name.bytes.length
        assert length > UInt64(0), "greet: name must not be empty"
        assert length <= UInt64(MAX_NAME_BYTES), "greet: name is over 64 bytes"
        return "Hello, " + name

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def shut_down(self) -> None:
        assert Txn.sender == Global.creator_address, "shut_down: creator only"
