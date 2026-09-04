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
    total_amount: arc4.UInt64
    claimed_amount: arc4.UInt64
    start_time: arc4.UInt64
    cliff_end: arc4.UInt64
    vesting_end: arc4.UInt64
    is_revoked: arc4.Bool


class Claimed(arc4.Struct):
    """ARC-28 event: who was paid, and how much (Example 8-17's device)."""

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


class TokenVesting(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.asset_id = GlobalState(UInt64(0))
        self.is_initialized = GlobalState(UInt64(0))
        self.beneficiary_count = GlobalState(UInt64(0))
        self.available_tokens = GlobalState(UInt64(0))
        self.schedules = BoxMap(Account, VestingSchedule, key_prefix=b"v_")

    @arc4.baremethod(create="require")
    def create(self) -> None:
        self.admin.value = Txn.sender.bytes

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "Contract is immutable"

    @arc4.abimethod(readonly=True)
    def get_admin(self) -> arc4.Address:
        return arc4.Address.from_bytes(self.admin.value)

    @arc4.abimethod
    def initialize(self, vesting_asset: Asset) -> None:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert self.is_initialized.value == UInt64(0), "Already initialized"

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

        assert deposit_txn.asset_receiver == Global.current_application_address
        assert deposit_txn.xfer_asset == Asset(self.asset_id.value)
        assert deposit_txn.asset_amount > UInt64(0)

        self.available_tokens.value += deposit_txn.asset_amount
        return deposit_txn.asset_amount

    @arc4.abimethod
    def create_schedule(
        self,
        beneficiary: Account,
        total_amount: UInt64,
        cliff_duration: UInt64,
        vesting_duration: UInt64,
        mbr_payment: gtxn.PaymentTransaction,
    ) -> None:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert Global.group_size == UInt64(2), "Expected 2 transactions"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert beneficiary not in self.schedules, "Schedule already exists"
        assert total_amount > UInt64(0), "Amount must be positive"
        assert vesting_duration > cliff_duration, "Vesting must exceed cliff"
        assert self.available_tokens.value >= total_amount, "Insufficient tokens"

        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(34) + UInt64(41))
        assert mbr_payment.receiver == Global.current_application_address
        assert mbr_payment.sender == Txn.sender
        assert mbr_payment.amount == box_mbr

        now = Global.latest_timestamp
        self.schedules[beneficiary] = VestingSchedule(
            total_amount=arc4.UInt64(total_amount),
            claimed_amount=arc4.UInt64(0),
            start_time=arc4.UInt64(now),
            cliff_end=arc4.UInt64(now + cliff_duration),
            vesting_end=arc4.UInt64(now + vesting_duration),
            is_revoked=arc4.Bool(False),
        )
        self.available_tokens.value -= total_amount
        self.beneficiary_count.value += UInt64(1)

    @arc4.abimethod
    def claim(self) -> UInt64:
        beneficiary = Txn.sender
        assert beneficiary in self.schedules, "No vesting schedule"

        schedule = self.schedules[beneficiary].copy()
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            Global.latest_timestamp,
        )

        claimable = vested - schedule.claimed_amount.as_uint64()
        assert claimable > UInt64(0), "Nothing to claim"

        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_id.value),
            asset_receiver=beneficiary,
            asset_amount=claimable,
            fee=UInt64(0),
        ).submit()

        schedule.claimed_amount = arc4.UInt64(
            schedule.claimed_amount.as_uint64() + claimable
        )
        self.schedules[beneficiary] = schedule.copy()

        arc4.emit(Claimed(arc4.Address(beneficiary), arc4.UInt64(claimable)))
        return claimable

    @arc4.abimethod
    def revoke(self, beneficiary: Account) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert beneficiary in self.schedules, "No schedule"

        schedule = self.schedules[beneficiary].copy()
        assert not schedule.is_revoked.native, "Already revoked"

        now = Global.latest_timestamp
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            now,
        )
        unvested = schedule.total_amount.as_uint64() - vested

        schedule.is_revoked = arc4.Bool(True)
        schedule.total_amount = arc4.UInt64(vested)
        schedule.cliff_end = arc4.UInt64(now)
        schedule.vesting_end = arc4.UInt64(now)
        self.schedules[beneficiary] = schedule.copy()

        if unvested > UInt64(0):
            itxn.AssetTransfer(
                xfer_asset=Asset(self.asset_id.value),
                asset_receiver=Account(self.admin.value),
                asset_amount=unvested,
                fee=UInt64(0),
            ).submit()

        return unvested

    @arc4.abimethod
    def cleanup_schedule(self, beneficiary: Account) -> None:
        assert beneficiary in self.schedules, "No schedule"

        schedule = self.schedules[beneficiary].copy()
        assert (
            schedule.claimed_amount.as_uint64()
            >= schedule.total_amount.as_uint64()
        )

        del self.schedules[beneficiary]
        self.beneficiary_count.value -= UInt64(1)

        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(34) + UInt64(41))
        itxn.Payment(
            receiver=Account(self.admin.value),
            amount=box_mbr,
            fee=UInt64(0),
        ).submit()

    @arc4.abimethod(readonly=True)
    def get_vesting_info(self, beneficiary: Account) -> VestingSchedule:
        assert beneficiary in self.schedules, "No schedule"
        return self.schedules[beneficiary].copy()

    @arc4.abimethod(readonly=True)
    def get_claimable(self, beneficiary: Account) -> UInt64:
        assert beneficiary in self.schedules, "No schedule"
        schedule = self.schedules[beneficiary].copy()
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            Global.latest_timestamp,
        )
        return vested - schedule.claimed_amount.as_uint64()
