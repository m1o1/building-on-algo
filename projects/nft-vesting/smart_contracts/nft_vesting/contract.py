from algopy import (
    ARC4Contract,
    Account,
    Asset,
    BoxMap,
    Bytes,
    Global,
    GlobalState,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
    op,
    subroutine,
)


class VestingSchedule(arc4.Struct):
    nft_asset_id: arc4.UInt64
    total_amount: arc4.UInt64
    claimed_amount: arc4.UInt64
    start_time: arc4.UInt64
    cliff_end: arc4.UInt64
    vesting_end: arc4.UInt64
    is_revoked: arc4.Bool


class Claimed(arc4.Struct):
    """ARC-28 event: who was paid, and how much (Example 8-16's device)."""

    beneficiary: arc4.Address
    amount: arc4.UInt64


@subroutine
def calculate_vested(
    total: UInt64,
    start: UInt64,
    cliff_end: UInt64,
    vesting_end: UInt64,
    now: UInt64,
) -> UInt64:
    if now < cliff_end:
        return UInt64(0)
    if now >= vesting_end:
        return total
    elapsed = now - start
    duration = vesting_end - start
    high, low = op.mulw(total, elapsed)
    q_hi, vested, r_hi, r_lo = op.divmodw(high, low, UInt64(0), duration)
    assert q_hi == 0, "Overflow in vesting calculation"
    return vested


class NftVesting(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.asset_id = GlobalState(UInt64(0))
        self.is_initialized = GlobalState(UInt64(0))
        self.schedule_count = GlobalState(UInt64(0))
        self.available_tokens = GlobalState(UInt64(0))
        self.schedules = BoxMap(arc4.UInt64, VestingSchedule, key_prefix=b"v_")

    @arc4.baremethod(create="require")
    def create(self) -> None:
        self.admin.value = Txn.sender.bytes

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "This contract is immutable"

    @arc4.abimethod
    def initialize(self, vesting_asset: Asset) -> None:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert self.is_initialized.value == UInt64(0), "Already initialized"
        assert vesting_asset.clawback == Global.zero_address, "Unsafe clawback"
        assert vesting_asset.freeze == Global.zero_address, "Unsafe freeze"
        assert not vesting_asset.default_frozen, "Unsafe default frozen"
        self.asset_id.value = vesting_asset.id
        self.is_initialized.value = UInt64(1)

        itxn.AssetTransfer(
            xfer_asset=vesting_asset,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()

    @arc4.abimethod
    def deposit_tokens(
        self,
        deposit_txn: gtxn.AssetTransferTransaction,
    ) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert Global.group_size == UInt64(2), "Expected 2 transactions"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert (
            deposit_txn.asset_receiver == Global.current_application_address
        ), "Deposit must go to the contract"
        assert (
            deposit_txn.xfer_asset == Asset(self.asset_id.value)
        ), "Wrong deposit asset"
        assert deposit_txn.asset_amount > UInt64(0), "Zero deposit"

        self.available_tokens.value += deposit_txn.asset_amount
        return deposit_txn.asset_amount

    @arc4.abimethod
    def create_schedule(
        self,
        schedule_id: UInt64,
        total_amount: UInt64,
        cliff_duration: UInt64,
        vesting_duration: UInt64,
        nft_url: Bytes,
        metadata_hash: Bytes,
        mbr_payment: gtxn.PaymentTransaction,
    ) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert Global.group_size == UInt64(2), "Expected 2 transactions"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert total_amount > UInt64(0), "Amount must be positive"
        assert vesting_duration > cliff_duration, "Vesting must exceed cliff"
        assert self.available_tokens.value >= total_amount, "Insufficient tokens"

        schedule_key = arc4.UInt64(schedule_id)
        assert schedule_key not in self.schedules, "Schedule ID already exists"

        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(49))
        nft_mbr = UInt64(100_000)
        schedule_mbr = box_mbr + nft_mbr
        assert (
            mbr_payment.receiver == Global.current_application_address
        ), "MBR must go to the contract"
        assert mbr_payment.sender == Txn.sender, "MBR sender mismatch"
        assert mbr_payment.amount == schedule_mbr, "Wrong MBR payment"

        now = Global.latest_timestamp
        nft_txn = itxn.AssetConfig(
            total=UInt64(1),
            decimals=UInt64(0),
            asset_name=b"Vesting NFT",
            unit_name=b"VEST",
            url=nft_url,
            metadata_hash=metadata_hash,
            default_frozen=False,
            manager=Global.current_application_address,
            clawback=Global.current_application_address,
            reserve=Global.zero_address,
            freeze=Global.zero_address,
            fee=UInt64(0),
        ).submit()
        nft_id = nft_txn.created_asset.id

        self.schedules[schedule_key] = VestingSchedule(
            nft_asset_id=arc4.UInt64(nft_id),
            total_amount=arc4.UInt64(total_amount),
            claimed_amount=arc4.UInt64(0),
            start_time=arc4.UInt64(now),
            cliff_end=arc4.UInt64(now + cliff_duration),
            vesting_end=arc4.UInt64(now + vesting_duration),
            is_revoked=arc4.Bool(False),
        )
        self.available_tokens.value -= total_amount
        self.schedule_count.value += UInt64(1)

        return nft_id

    @arc4.abimethod
    def deliver_nft(
        self,
        schedule_id: UInt64,
        nft_asset: Asset,
        beneficiary: Account,
    ) -> None:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        schedule_key = arc4.UInt64(schedule_id)
        assert schedule_key in self.schedules, "No schedule for this NFT"
        schedule = self.schedules[schedule_key].copy()
        assert schedule.nft_asset_id.as_uint64() == nft_asset.id, "Wrong NFT"
        assert nft_asset.balance(
            Global.current_application_address
        ) == UInt64(1), "Contract does not hold this NFT"

        itxn.AssetTransfer(
            xfer_asset=nft_asset,
            asset_receiver=beneficiary,
            asset_amount=UInt64(1),
            fee=UInt64(0),
        ).submit()

    @arc4.abimethod
    def claim(self, schedule_id: UInt64, nft_asset: Asset) -> UInt64:
        assert nft_asset.balance(Txn.sender) == UInt64(1), (
            "Caller does not hold this NFT"
        )

        schedule_key = arc4.UInt64(schedule_id)
        assert schedule_key in self.schedules, "No schedule for this NFT"
        schedule = self.schedules[schedule_key].copy()
        assert schedule.nft_asset_id.as_uint64() == nft_asset.id, "Wrong NFT"
        assert not schedule.is_revoked.native, "Schedule revoked"

        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            Global.latest_timestamp,
        )
        already_claimed = schedule.claimed_amount.as_uint64()
        claimable = vested - already_claimed
        assert claimable > UInt64(0), "Nothing to claim"

        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_id.value),
            asset_receiver=Txn.sender,
            asset_amount=claimable,
            fee=UInt64(0),
        ).submit()

        schedule.claimed_amount = arc4.UInt64(already_claimed + claimable)
        self.schedules[schedule_key] = schedule.copy()

        arc4.emit(Claimed(arc4.Address(Txn.sender), arc4.UInt64(claimable)))
        return claimable

    @arc4.abimethod
    def revoke(
        self,
        schedule_id: UInt64,
        nft_asset: Asset,
        current_holder: Account,
    ) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"

        schedule_key = arc4.UInt64(schedule_id)
        assert schedule_key in self.schedules, "No schedule for this NFT"
        schedule = self.schedules[schedule_key].copy()
        assert schedule.nft_asset_id.as_uint64() == nft_asset.id, "Wrong NFT"
        assert not schedule.is_revoked.native, "Already revoked"
        assert nft_asset.balance(current_holder) == UInt64(1), (
            "Holder does not have NFT"
        )

        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            Global.latest_timestamp,
        )
        already_claimed = schedule.claimed_amount.as_uint64()
        claimable = vested - already_claimed
        unvested = schedule.total_amount.as_uint64() - vested

        if claimable > UInt64(0):
            itxn.AssetTransfer(
                xfer_asset=Asset(self.asset_id.value),
                asset_receiver=current_holder,
                asset_amount=claimable,
                fee=UInt64(0),
            ).submit()

        itxn.AssetTransfer(
            xfer_asset=nft_asset,
            asset_sender=current_holder,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(1),
            fee=UInt64(0),
        ).submit()

        itxn.AssetConfig(
            config_asset=nft_asset,
            fee=UInt64(0),
        ).submit()

        if unvested > UInt64(0):
            itxn.AssetTransfer(
                xfer_asset=Asset(self.asset_id.value),
                asset_receiver=Account(self.admin.value),
                asset_amount=unvested,
                fee=UInt64(0),
            ).submit()

        schedule.total_amount = arc4.UInt64(vested)
        schedule.claimed_amount = arc4.UInt64(vested)
        schedule.is_revoked = arc4.Bool(True)
        self.schedules[schedule_key] = schedule.copy()

        return unvested

    @arc4.abimethod
    def cleanup_schedule(self, schedule_id: UInt64) -> None:
        schedule_key = arc4.UInt64(schedule_id)
        assert schedule_key in self.schedules, "No schedule"
        schedule = self.schedules[schedule_key].copy()
        assert (
            schedule.claimed_amount.as_uint64()
            >= schedule.total_amount.as_uint64()
        ), "Not fully claimed"

        del self.schedules[schedule_key]
        self.schedule_count.value -= UInt64(1)

        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(49))
        itxn.Payment(
            receiver=Account(self.admin.value),
            amount=box_mbr,
            fee=UInt64(0),
        ).submit()

    @arc4.abimethod(readonly=True)
    def get_vesting_info(self, schedule_id: UInt64) -> VestingSchedule:
        schedule_key = arc4.UInt64(schedule_id)
        assert schedule_key in self.schedules, "No schedule"
        return self.schedules[schedule_key].copy()

    @arc4.abimethod(readonly=True)
    def get_claimable(self, schedule_id: UInt64) -> UInt64:
        schedule_key = arc4.UInt64(schedule_id)
        assert schedule_key in self.schedules, "No schedule"
        schedule = self.schedules[schedule_key].copy()
        if schedule.is_revoked.native:
            return UInt64(0)
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            Global.latest_timestamp,
        )
        return vested - schedule.claimed_amount.as_uint64()
