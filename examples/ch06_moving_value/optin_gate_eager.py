from algopy import (ARC4Contract, Account, Asset, Global, GlobalState, Txn,
                    UInt64, arc4, itxn)

REWARD_UNITS = 1_000


class Rewards(ARC4Contract):
    """Refuses to pay a recipient who cannot receive the asset.

    Without the check the transfer still fails and the group still
    rolls back --- but the caller reads a ledger error, not a sentence.
    """

    def __init__(self) -> None:
        self.token = GlobalState(UInt64(0))

    @arc4.abimethod
    def configure(self, token: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.token.value == UInt64(0), "already configured"
        self.token.value = token.id

    @arc4.abimethod
    def reward(self, recipient: Account) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        token = Asset(self.token.value)
        # A boolean for any account; token.balance would fail instead.
        assert recipient.is_opted_in(token), "recipient must opt in first"
        itxn.AssetTransfer(
            xfer_asset=token,
            asset_receiver=recipient,
            asset_amount=UInt64(REWARD_UNITS),
            fee=UInt64(0),
        ).submit()
        return UInt64(REWARD_UNITS)
