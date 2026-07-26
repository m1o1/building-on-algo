from algopy import ARC4Contract, Global, String, Txn, arc4


class Greeter(ARC4Contract):
    """Greet anyone who asks. Let the people who deployed it shut it down."""

    @arc4.abimethod
    def greet(self, name: String) -> String:
        assert name.bytes.length > 0
        return "Hello, " + name

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def shut_down(self) -> None:
        assert Txn.sender == Global.current_application_address, "admin only"
