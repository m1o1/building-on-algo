from algopy import ARC4Contract, Global, LocalState, Txn, UInt64, arc4, gtxn


class AnyTokenVault(ARC4Contract):
    """Checks that an asset arrived, never which asset it was.

    An attacker mints their own ASA for free, sends a billion units of
    it, and is credited exactly as if they had sent the real one.
    """

    def __init__(self) -> None:
        self.deposited = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def deposit(self, transfer: gtxn.AssetTransferTransaction) -> UInt64:
        app = Global.current_application_address
        assert transfer.asset_receiver == app, "send it to this app"
        held = self.deposited.get(Txn.sender, UInt64(0))
        self.deposited[Txn.sender] = held + transfer.asset_amount
        return self.deposited[Txn.sender]
