from algopy import (ARC4Contract, Asset, Global, GlobalState, Txn, UInt64,
                    arc4, gtxn)

MAX_FEE_BPS = 500


class Staking(ARC4Contract):
    """Every assertion checks meaning. The router already checked shape.

    It proved this is a NoOp on a live app, `fee_bps` is eight bytes,
    and `deposit` is an axfer directly before this call in the group.
    """

    def __init__(self) -> None:
        self.admin = GlobalState(Global.creator_address)
        self.stake_asset = GlobalState(UInt64(0))
        self.fee_bps = GlobalState(UInt64(0))

    @arc4.abimethod
    def configure(self, stake_asset: Asset, fee_bps: UInt64) -> None:
        assert Txn.sender == self.admin.value, "admin only"
        assert self.stake_asset.value == UInt64(0), "already initialized"
        assert stake_asset.id != UInt64(0), "asset required"
        assert fee_bps <= UInt64(MAX_FEE_BPS), "fee too high"
        self.stake_asset.value = stake_asset.id
        self.fee_bps.value = fee_bps

    @arc4.abimethod
    def stake(self, deposit: gtxn.AssetTransferTransaction) -> UInt64:
        assert self.stake_asset.value != UInt64(0), "not initialized"
        assert deposit.xfer_asset.id == self.stake_asset.value, "wrong asset"
        app = Global.current_application_address
        assert deposit.asset_receiver == app, "wrong receiver"
        assert deposit.sender == Txn.sender, "deposit must be from the caller"
        return deposit.asset_amount
