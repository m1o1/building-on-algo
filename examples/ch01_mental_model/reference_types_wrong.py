from algopy import ARC4Contract, Global, Txn, arc4


class GatedWrong(ARC4Contract):
    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def shut_down(self) -> None:
        # Compiles. Deploys. Can never pass: nobody holds the key to an
        # application's own account, and the AVM refuses to let an
        # application call itself.
        assert Txn.sender == Global.current_application_address, "admin only"
