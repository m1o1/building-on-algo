from algopy import (ARC4Contract, Account, Asset, Global, Txn, UInt64, arc4,
                    itxn)


class Recall(ARC4Contract):
    """Moves an asset out of an account that signed nothing.

    `asset_sender` is the field that makes this a clawback, and it
    works only while the app is the asset's clawback address.
    """

    @arc4.abimethod
    def recall(self, token: Asset, victim: Account, amount: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        app = Global.current_application_address
        assert token.clawback == app, "not the clawback address"
        itxn.AssetTransfer(
            xfer_asset=token, asset_sender=victim, asset_receiver=app,
            asset_amount=amount, fee=UInt64(0),
        ).submit()
