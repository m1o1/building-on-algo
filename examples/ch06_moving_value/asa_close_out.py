from algopy import ARC4Contract, Asset, Global, Txn, UInt64, arc4, itxn


class Retiring(ARC4Contract):
    """Gives up a holding and recovers the 100,000 microAlgo.

    `asset_close_to` sends the entire remaining balance whatever
    `asset_amount` says. The creator is always opted in.
    """

    @arc4.abimethod
    def stop_holding(self, token: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        itxn.AssetTransfer(
            xfer_asset=token,
            asset_receiver=token.creator,
            asset_amount=UInt64(0),
            asset_close_to=token.creator,
            fee=UInt64(0),
        ).submit()
