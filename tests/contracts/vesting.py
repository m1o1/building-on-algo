"""Token vesting contract - extracted from Chapter 2 of the book."""

from algopy import (
    ARC4Contract, Account, Asset, BoxMap, Bytes, Global, GlobalState,
    Txn, UInt64, arc4, itxn, op, subroutine,
)


class VestingSchedule(arc4.Struct):
    total_amount: arc4.UInt64
    claimed_amount: arc4.UInt64
    start_time: arc4.UInt64
    cliff_end: arc4.UInt64
    vesting_end: arc4.UInt64
    is_revoked: arc4.Bool


@subroutine
def calculate_vested(
    total: UInt64, start: UInt64, cliff_end: UInt64,
    vesting_end: UInt64, now: UInt64,
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
        self.admin = GlobalState(Bytes())          # Admin address (set during creation)
        self.asset_id = GlobalState(UInt64(0))
        self.is_initialized = GlobalState(UInt64(0))
        self.beneficiary_count = GlobalState(UInt64(0))
        self.schedules = BoxMap(Account, VestingSchedule, key_prefix=b"v_")

    @arc4.baremethod(create="require")
    def create(self) -> None:
        self.admin.value = Txn.sender.bytes

    @arc4.abimethod
    def initialize(self, asset_id: UInt64) -> None:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert self.is_initialized.value == UInt64(0), "Already initialized"
        self.asset_id.value = asset_id
        self.is_initialized.value = UInt64(1)
        itxn.AssetTransfer(
            xfer_asset=Asset(asset_id),
            asset_receiver=Global.current_application_address,
            asset_amount=0,
            fee=UInt64(0),
        ).submit()

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
        claimed = schedule.claimed_amount.as_uint64()
        claimable = vested - claimed
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
        return claimable

    @arc4.abimethod(readonly=True)
    def get_claimable(self, beneficiary: Account) -> UInt64:
        assert beneficiary in self.schedules, "No vesting schedule"
        schedule = self.schedules[beneficiary].copy()
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            Global.latest_timestamp,
        )
        return vested - schedule.claimed_amount.as_uint64()

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "Immutable"
