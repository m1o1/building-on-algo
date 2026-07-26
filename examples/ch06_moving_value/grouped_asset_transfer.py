from algopy import (ARC4Contract, Asset, Global, GlobalState, LocalState, Txn,
                    UInt64, arc4, gtxn)


class TokenVault(ARC4Contract):
    """Accepts one specific ASA, and refuses every other one."""

    def __init__(self) -> None:
        self.token = GlobalState(UInt64(0))
        self.deposited = LocalState(UInt64)

    @arc4.abimethod
    def configure(self, token: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.token.value == UInt64(0), "already configured"
        self.token.value = token.id

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def deposit(self, transfer: gtxn.AssetTransferTransaction) -> UInt64:
        app = Global.current_application_address
        # Without the first assert, any worthless ASA buys a position.
        assert transfer.xfer_asset.id == self.token.value, "wrong asset"
        assert transfer.asset_receiver == app, "send it to this app"
        assert transfer.sender == Txn.sender, "fund your own balance"
        held = self.deposited.get(Txn.sender, UInt64(0))
        self.deposited[Txn.sender] = held + transfer.asset_amount
        return self.deposited[Txn.sender]
