from algopy import (ARC4Contract, Asset, Global, GlobalState, Txn, UInt64,
                    arc4, gtxn, itxn, subroutine)


class SimpleVesting(ARC4Contract):
    """Vests one ASA to one beneficiary, linearly, after a cliff.

    Deployed, funded, and demonstrably working: the admin initializes
    it against a deposit, time passes, the beneficiary claims, tokens
    arrive. Three things about it are wrong. None raise a compile
    error, and --- this is the part that matters --- none of them are
    caught by a test suite that looks thorough.
    """

    def __init__(self) -> None:
        self.admin = GlobalState(Global.creator_address)
        self.beneficiary = GlobalState(Global.zero_address)
        self.asset_id = GlobalState(UInt64(0))
        self.total = GlobalState(UInt64(0))
        self.claimed = GlobalState(UInt64(0))
        self.start = GlobalState(UInt64(0))
        self.cliff = GlobalState(UInt64(0))
        self.end = GlobalState(UInt64(0))

    @subroutine
    def vested(self, now: UInt64) -> UInt64:
        """How much has vested in total by `now`, claimed or not."""
        if now < self.cliff.value:
            return UInt64(0)
        if now >= self.end.value:
            return self.total.value
        elapsed = now - self.start.value
        duration = self.end.value - self.start.value
        return self.total.value * elapsed // duration

    @arc4.abimethod
    def opt_in_to_asset(self, asset: UInt64) -> None:
        """Call before initialize; needs 200,000 microAlgo of MBR in the app."""
        assert Txn.sender == self.admin.value, "admin only"
        itxn.AssetTransfer(
            xfer_asset=Asset(asset),
            asset_receiver=Global.current_application_address,
            asset_amount=0,
            fee=UInt64(0),
        ).submit()

    @arc4.abimethod
    def initialize(
        self,
        beneficiary: arc4.Address,
        cliff_duration: UInt64,
        vesting_duration: UInt64,
        deposit: gtxn.AssetTransferTransaction,
    ) -> None:
        """Fix the schedule around the deposit that funds it."""
        assert Txn.sender == self.admin.value, "admin only"
        assert self.total.value == UInt64(0), "already initialized"
        assert vesting_duration > cliff_duration, "vesting must exceed cliff"
        assert deposit.asset_receiver == Global.current_application_address, (
            "deposit must go to the contract"
        )
        assert deposit.asset_amount > UInt64(0), "deposit must be positive"

        now = Global.latest_timestamp
        self.beneficiary.value = beneficiary.native
        self.asset_id.value = deposit.xfer_asset.id
        self.total.value = deposit.asset_amount
        self.start.value = now
        self.cliff.value = now + cliff_duration
        self.end.value = now + vesting_duration

    @arc4.abimethod
    def claim(self) -> UInt64:
        """Send the beneficiary everything vested since the last claim."""
        assert Txn.sender == self.beneficiary.value
        claimable = self.vested(Global.latest_timestamp) - self.claimed.value
        if claimable == UInt64(0):
            return UInt64(0)
        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_id.value),
            asset_receiver=Txn.sender,
            asset_amount=claimable,
            fee=UInt64(0),
        ).submit()
        self.claimed.value += claimable
        return claimable

    @arc4.abimethod(readonly=True)
    def claimable(self) -> UInt64:
        return self.vested(Global.latest_timestamp) - self.claimed.value
