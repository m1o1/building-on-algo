from algopy import (ARC4Contract, Account, Asset, Global, Txn, UInt64, arc4,
                    itxn)


class Distributor(ARC4Contract):
    """Sends units of an ASA out of the application account.

    Identical in shape to an inner payment, with three fields renamed.
    The receiver must already hold the asset or the transfer fails.
    """

    @arc4.abimethod
    def send(self, token: Asset, recipient: Account, amount: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        app = Global.current_application_address
        assert amount <= token.balance(app), "more than the app holds"
        itxn.AssetTransfer(
            xfer_asset=token,
            asset_receiver=recipient,
            asset_amount=amount,
            fee=UInt64(0),
        ).submit()
