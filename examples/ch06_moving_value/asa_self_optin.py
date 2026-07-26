from algopy import (ARC4Contract, Asset, Global, GlobalState, Txn, UInt64,
                    arc4, itxn)

OPT_IN_MBR = 100_000


class Holder(ARC4Contract):
    """Opts the application account into an ASA it did not create.

    An account holds an asset only after a zero-amount transfer to
    itself. A contract does that for itself with an inner transaction;
    it is the one opt-in on Algorand that needs nobody's signature.
    """

    def __init__(self) -> None:
        self.token = GlobalState(UInt64(0))

    @arc4.abimethod
    def opt_in_to(self, token: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.token.value == UInt64(0), "already holding one"
        app = Global.current_application_address
        # The 100,000 microAlgo of new minimum balance has to already
        # be in the account, or the transfer below fails.
        assert app.balance >= app.min_balance + UInt64(OPT_IN_MBR), "fund me"
        itxn.AssetTransfer(
            xfer_asset=token,
            asset_receiver=app,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()
        self.token.value = token.id
