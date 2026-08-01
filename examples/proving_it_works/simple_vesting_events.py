# book-example: mode=compile
from algopy import (ARC4Contract, Asset, Global, GlobalState, Txn, UInt64,
                    arc4, gtxn, itxn, op, subroutine)


class Claimed(arc4.Struct):
    """ARC-28 event: the class name and field types are its signature."""

    beneficiary: arc4.Address
    amount: arc4.UInt64


class SimpleVesting(ARC4Contract):
    """Vests one ASA to one beneficiary, linearly, after a cliff.

    The three corrections over the first draft: a claim that would move
    nothing is refused rather than reported as success; the vesting
    arithmetic multiplies through 128 bits so a production supply cannot
    overflow it; and every refusal carries a message a stranger can act on.
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
        # Multiply first, through 128 bits; `divw` floors toward the pool.
        hi, lo = op.mulw(self.total.value, elapsed)
        return op.divw(hi, lo, duration)

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
        assert Txn.sender == self.beneficiary.value, "not the beneficiary"
        claimable = self.vested(Global.latest_timestamp) - self.claimed.value
        assert claimable > UInt64(0), "nothing vested since the last claim"
        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_id.value),
            asset_receiver=Txn.sender,
            asset_amount=claimable,
            fee=UInt64(0),
        ).submit()
        self.claimed.value += claimable
        arc4.emit(Claimed(arc4.Address(Txn.sender), arc4.UInt64(claimable)))
        return claimable

    @arc4.abimethod(readonly=True)
    def claimable(self) -> UInt64:
        return self.vested(Global.latest_timestamp) - self.claimed.value
