from algopy import (
    ARC4Contract,
    Asset,
    Bytes,
    Global,
    GlobalState,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
)


class SimpleVesting(ARC4Contract):
    """A simplified vesting contract for one beneficiary.
    Tokens vest linearly from start to vesting_end,
    with nothing claimable before cliff_end."""

    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.asset_id = GlobalState(UInt64(0))
        self.beneficiary = GlobalState(Bytes())
        self.total_amount = GlobalState(UInt64(0))
        self.claimed_amount = GlobalState(UInt64(0))
        self.start_time = GlobalState(UInt64(0))
        self.cliff_end = GlobalState(UInt64(0))
        self.vesting_end = GlobalState(UInt64(0))

    @arc4.baremethod(create="require")
    def create(self) -> None:
        """Record who deployed this contract."""
        self.admin.value = Txn.sender.bytes

    @arc4.baremethod(
        allow_actions=[
            "UpdateApplication",
            "DeleteApplication",
        ]
    )
    def reject_lifecycle(self) -> None:
        """Make the contract immutable."""
        assert False, "Contract is immutable"

    @arc4.abimethod
    def opt_in_to_asset(self, asset: UInt64) -> None:
        """Opt the contract into an ASA.
        Must be called before the deposit group."""
        assert Txn.sender.bytes == self.admin.value, \
            "Only admin"
        itxn.AssetTransfer(
            xfer_asset=Asset(asset),
            asset_receiver=(
                Global.current_application_address
            ),
            asset_amount=0,
            fee=UInt64(0),
        ).submit()

    @arc4.abimethod
    def initialize(
        self,
        asset: UInt64,
        beneficiary: arc4.Address,
        total_amount: UInt64,
        cliff_duration: UInt64,
        vesting_duration: UInt64,
        deposit_txn: gtxn.AssetTransferTransaction,
    ) -> None:
        """Set up the vesting schedule and accept the
        token deposit in one atomic group."""
        assert Txn.sender.bytes == self.admin.value, \
            "Only admin"
        assert self.asset_id.value == UInt64(0), \
            "Already initialized"
        assert vesting_duration > cliff_duration, \
            "Vesting must exceed cliff"
        assert total_amount > UInt64(0), \
            "Amount must be positive"

        # Verify the grouped deposit
        assert deposit_txn.xfer_asset == Asset(asset)
        assert deposit_txn.asset_receiver \
            == Global.current_application_address
        assert deposit_txn.asset_amount == total_amount

        self.asset_id.value = asset
        self.beneficiary.value = beneficiary.bytes
        self.total_amount.value = total_amount
        now = Global.latest_timestamp
        self.start_time.value = now
        self.cliff_end.value = now + cliff_duration
        self.vesting_end.value = now + vesting_duration

    @arc4.abimethod
    def claim(self) -> UInt64:
        """Beneficiary claims vested tokens."""
        assert Txn.sender.bytes \
            == self.beneficiary.value, "Only beneficiary"

        now = Global.latest_timestamp
        if now < self.cliff_end.value:
            return UInt64(0)

        if now >= self.vesting_end.value:
            vested = self.total_amount.value
        else:
            elapsed = now - self.start_time.value
            duration = (
                self.vesting_end.value
                - self.start_time.value
            )
            vested = (
                self.total_amount.value
                * elapsed
                // duration
            )

        claimable = vested - self.claimed_amount.value
        if claimable == UInt64(0):
            return UInt64(0)

        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_id.value),
            asset_receiver=Txn.sender,
            asset_amount=claimable,
            fee=UInt64(0),
        ).submit()

        self.claimed_amount.value = (
            self.claimed_amount.value + claimable
        )
        return claimable

    @arc4.abimethod(readonly=True)
    def get_claimable(self) -> UInt64:
        """How many tokens can the beneficiary
        claim right now?"""
        now = Global.latest_timestamp
        if now < self.cliff_end.value:
            return UInt64(0)

        if now >= self.vesting_end.value:
            vested = self.total_amount.value
        else:
            elapsed = now - self.start_time.value
            duration = (
                self.vesting_end.value
                - self.start_time.value
            )
            vested = (
                self.total_amount.value
                * elapsed
                // duration
            )

        return vested - self.claimed_amount.value

    @arc4.abimethod(readonly=True)
    def get_admin(self) -> arc4.Address:
        """Return the admin address."""
        return arc4.Address.from_bytes(
            self.admin.value
        )
