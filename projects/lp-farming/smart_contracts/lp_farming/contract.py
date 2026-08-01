from algopy import (
    ARC4Contract,
    Account,
    Application,
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

PRECISION = 10**9
SCALE = 1000
SECONDS_PER_DAY = 86400
MIN_LOCK_DAYS = 30
MAX_LOCK_DAYS = 365
MIN_LOCK = MIN_LOCK_DAYS * SECONDS_PER_DAY
MAX_LOCK = MAX_LOCK_DAYS * SECONDS_PER_DAY
MAX_REWARD_DURATION = 365 * SECONDS_PER_DAY
MAX_REWARD_RATE = 584
MAX_UINT64 = 2**64 - 1
STAKE_BOX_MBR = 32_100


class StakePosition(arc4.Struct):
    effective_balance: arc4.UInt64
    lp_amount: arc4.UInt64
    reward_per_token_paid: arc4.UInt64
    accrued_rewards: arc4.UInt64
    unlock_time: arc4.UInt64


class LPFarm(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.lp_token_id = GlobalState(UInt64(0))
        self.reward_token_id = GlobalState(UInt64(0))
        self.amm_app_id = GlobalState(UInt64(0))
        self.total_effective = GlobalState(UInt64(0))
        self.reward_rate = GlobalState(UInt64(0))
        self.reward_end_time = GlobalState(UInt64(0))
        self.last_update_time = GlobalState(UInt64(0))
        self.reward_per_token_stored = GlobalState(UInt64(0))
        self.rewards_remaining = GlobalState(UInt64(0))
        self.is_initialized = GlobalState(UInt64(0))
        self.stakes = BoxMap(arc4.Address, StakePosition, key_prefix=b"s_")

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.admin.value = Txn.sender.bytes

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "Contract is immutable"

    @arc4.abimethod
    def initialize(
        self,
        lp_token: Asset,
        reward_token: Asset,
        amm_app: Application,
    ) -> None:
        assert Global.group_size == UInt64(1), "Unexpected group size"
        assert Txn.sender == Account(self.admin.value), "Admin only"
        assert self.is_initialized.value == UInt64(0), "Already initialized"

        lp_id, exists = op.AppGlobal.get_ex_uint64(amm_app, Bytes(b"lp_token_id"))
        assert exists, "AMM has no lp_token_id"
        assert lp_id == lp_token.id, "LP token mismatch"

        self.lp_token_id.value = lp_token.id
        self.reward_token_id.value = reward_token.id
        self.amm_app_id.value = amm_app.id
        self.last_update_time.value = Global.latest_timestamp

        itxn.AssetTransfer(
            xfer_asset=lp_token,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()
        itxn.AssetTransfer(
            xfer_asset=reward_token,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()

        self.is_initialized.value = UInt64(1)

    @arc4.abimethod
    def deposit_rewards(
        self,
        reward_txn: gtxn.AssetTransferTransaction,
        duration_seconds: UInt64,
    ) -> None:
        assert Global.group_size == UInt64(2), "Unexpected group size"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert Txn.sender == Account(self.admin.value), "Admin only"
        assert reward_txn.sender == Txn.sender, "Reward sender mismatch"
        assert reward_txn.xfer_asset == Asset(self.reward_token_id.value)
        assert reward_txn.asset_receiver == Global.current_application_address
        assert duration_seconds > UInt64(0), "Zero duration"
        assert duration_seconds <= UInt64(MAX_REWARD_DURATION)
        assert Global.latest_timestamp >= self.reward_end_time.value, (
            "Reward period active"
        )

        self._update_reward()

        amount = reward_txn.asset_amount
        assert amount > UInt64(0), "Zero reward deposit"

        new_rate = amount // duration_seconds
        assert new_rate > UInt64(0), "Reward rate rounds to zero"
        assert new_rate <= UInt64(MAX_REWARD_RATE), "Reward rate too high"

        distributable = new_rate * duration_seconds
        pool_capacity = UInt64(MAX_UINT64) - self.rewards_remaining.value
        assert distributable <= pool_capacity, "Reward pool overflow"

        h, worst_increment = op.mulw(distributable, UInt64(PRECISION))
        assert h == UInt64(0), "Accumulator capacity overflow"
        acc_capacity = UInt64(MAX_UINT64) - self.reward_per_token_stored.value
        assert worst_increment <= acc_capacity, "Accumulator capacity overflow"

        self.rewards_remaining.value += distributable
        self.reward_rate.value = new_rate
        self.last_update_time.value = Global.latest_timestamp
        self.reward_end_time.value = Global.latest_timestamp + duration_seconds

    @arc4.abimethod
    def stake(
        self,
        mbr_payment: gtxn.PaymentTransaction,
        lp_txn: gtxn.AssetTransferTransaction,
        lock_days: UInt64,
    ) -> None:
        assert Global.group_size == UInt64(3), "Unexpected group size"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert mbr_payment.sender == Txn.sender, "MBR sender mismatch"
        assert mbr_payment.receiver == Global.current_application_address
        assert mbr_payment.amount == UInt64(STAKE_BOX_MBR), "Wrong MBR payment"
        assert lp_txn.xfer_asset == Asset(self.lp_token_id.value)
        assert lp_txn.asset_receiver == Global.current_application_address
        assert lp_txn.sender == Txn.sender, "LP sender mismatch"
        assert lp_txn.asset_amount > UInt64(0), "Zero stake"
        assert lock_days >= UInt64(MIN_LOCK_DAYS), "Below minimum lock"
        assert lock_days <= UInt64(MAX_LOCK_DAYS), "Above maximum lock"

        self._update_reward()

        duration = lock_days * UInt64(SECONDS_PER_DAY)
        multiplier = _calculate_multiplier(duration)
        lp_amount = lp_txn.asset_amount
        high, low = op.mulw(lp_amount, multiplier)
        q_hi, effective, rem_hi, rem_lo = op.divmodw(
            high, low, UInt64(0), UInt64(SCALE)
        )
        assert q_hi == UInt64(0), "Effective balance overflow"
        assert effective > UInt64(0), "Zero effective stake"
        capacity = UInt64(MAX_UINT64) - self.total_effective.value
        assert effective <= capacity, "Total effective overflow"

        key = arc4.Address(Txn.sender)
        assert key not in self.stakes, "Already staked"
        self.stakes[key] = StakePosition(
            effective_balance=arc4.UInt64(effective),
            lp_amount=arc4.UInt64(lp_amount),
            reward_per_token_paid=arc4.UInt64(
                self.reward_per_token_stored.value
            ),
            accrued_rewards=arc4.UInt64(0),
            unlock_time=arc4.UInt64(Global.latest_timestamp + duration),
        )
        self.total_effective.value += effective

    @arc4.abimethod
    def claim(self) -> UInt64:
        assert Global.group_size == UInt64(1), "Unexpected group size"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        self._update_reward()

        key = arc4.Address(Txn.sender)
        pos = self.stakes[key].copy()
        current_rpt = self.reward_per_token_stored.value
        total_pending = self._pending_for(pos, current_rpt)

        assert total_pending > UInt64(0), "Nothing to claim"
        assert total_pending <= self.rewards_remaining.value

        pos.reward_per_token_paid = arc4.UInt64(current_rpt)
        pos.accrued_rewards = arc4.UInt64(0)
        self.stakes[key] = pos.copy()
        self.rewards_remaining.value -= total_pending

        itxn.AssetTransfer(
            xfer_asset=Asset(self.reward_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=total_pending,
            fee=UInt64(0),
        ).submit()

        return total_pending

    @arc4.abimethod
    def extend_lock(self, new_lock_days: UInt64) -> None:
        assert Global.group_size == UInt64(1), "Unexpected group size"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert new_lock_days >= UInt64(MIN_LOCK_DAYS), "Below minimum lock"
        assert new_lock_days <= UInt64(MAX_LOCK_DAYS), "Above maximum lock"
        self._update_reward()

        key = arc4.Address(Txn.sender)
        pos = self.stakes[key].copy()
        old_effective = pos.effective_balance.as_uint64()
        lp_amount = pos.lp_amount.as_uint64()
        assert old_effective > UInt64(0), "No stake"

        current_rpt = self.reward_per_token_stored.value
        accrued = self._pending_for(pos, current_rpt)

        new_duration = new_lock_days * UInt64(SECONDS_PER_DAY)
        new_unlock = Global.latest_timestamp + new_duration
        assert new_unlock > pos.unlock_time.as_uint64(), (
            "New lock must extend beyond current"
        )
        new_multiplier = _calculate_multiplier(new_duration)
        h, l = op.mulw(lp_amount, new_multiplier)
        q_hi, new_effective, rem_hi, rem_lo = op.divmodw(
            h, l, UInt64(0), UInt64(SCALE)
        )
        assert q_hi == UInt64(0), "Effective balance overflow"

        reduced_total = self.total_effective.value - old_effective
        capacity = UInt64(MAX_UINT64) - reduced_total
        assert new_effective <= capacity, "Total effective overflow"
        self.total_effective.value = reduced_total + new_effective

        pos.reward_per_token_paid = arc4.UInt64(current_rpt)
        pos.accrued_rewards = arc4.UInt64(accrued)
        pos.effective_balance = arc4.UInt64(new_effective)
        pos.unlock_time = arc4.UInt64(new_unlock)
        self.stakes[key] = pos.copy()

    @arc4.abimethod
    def unstake(self) -> None:
        assert Global.group_size == UInt64(1), "Unexpected group size"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        self._update_reward()

        key = arc4.Address(Txn.sender)
        pos = self.stakes[key].copy()
        effective = pos.effective_balance.as_uint64()
        lp_amount = pos.lp_amount.as_uint64()
        assert effective > UInt64(0), "No stake"
        assert Global.latest_timestamp >= pos.unlock_time.as_uint64(), (
            "Lock not expired"
        )

        current_rpt = self.reward_per_token_stored.value
        total_pending = self._pending_for(pos, current_rpt)

        self.total_effective.value -= effective

        itxn.AssetTransfer(
            xfer_asset=Asset(self.lp_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=lp_amount,
            fee=UInt64(0),
        ).submit()

        if total_pending > UInt64(0):
            assert total_pending <= self.rewards_remaining.value
            self.rewards_remaining.value -= total_pending
            itxn.AssetTransfer(
                xfer_asset=Asset(self.reward_token_id.value),
                asset_receiver=Txn.sender,
                asset_amount=total_pending,
                fee=UInt64(0),
            ).submit()

        del self.stakes[key]

        itxn.Payment(
            receiver=Txn.sender,
            amount=UInt64(STAKE_BOX_MBR),
            fee=UInt64(0),
        ).submit()

    @subroutine
    def _pending_for(
        self, pos: StakePosition, current_rpt: UInt64
    ) -> UInt64:
        effective = pos.effective_balance.as_uint64()
        assert effective > UInt64(0), "No stake"
        paid_rpt = pos.reward_per_token_paid.as_uint64()
        diff = current_rpt - paid_rpt
        high, low = op.mulw(effective, diff)
        q_hi, new_rewards, rem_hi, rem_lo = op.divmodw(
            high, low, UInt64(0), UInt64(PRECISION)
        )
        assert q_hi == UInt64(0), "Reward overflow"
        accrued = pos.accrued_rewards.as_uint64()
        capacity = UInt64(MAX_UINT64) - accrued
        assert new_rewards <= capacity, "Reward overflow"
        return accrued + new_rewards

    @subroutine
    def _update_reward(self) -> None:
        if self.total_effective.value == UInt64(0):
            self.last_update_time.value = Global.latest_timestamp
            return

        now = Global.latest_timestamp
        end = self.reward_end_time.value
        effective_now = now if now < end else end
        last = self.last_update_time.value
        if effective_now <= last:
            return

        delta_t = effective_now - last
        rate = self.reward_rate.value
        total = self.total_effective.value

        assert delta_t <= UInt64(MAX_REWARD_DURATION)
        assert rate <= UInt64(MAX_REWARD_RATE)

        rate_time = rate * delta_t
        high, low = op.mulw(rate_time, UInt64(PRECISION))
        q_hi, increment, rem_hi, rem_lo = op.divmodw(
            high, low, UInt64(0), total
        )
        assert q_hi == UInt64(0), "Accumulator overflow"

        capacity = UInt64(MAX_UINT64) - self.reward_per_token_stored.value
        assert increment <= capacity, "Accumulator overflow"
        self.reward_per_token_stored.value += increment
        self.last_update_time.value = effective_now


@subroutine
def _calculate_multiplier(duration: UInt64) -> UInt64:
    assert duration >= UInt64(MIN_LOCK), "Below minimum lock"
    assert duration <= UInt64(MAX_LOCK), "Above maximum lock"
    lock_range = UInt64(MAX_LOCK - MIN_LOCK)
    excess = duration - UInt64(MIN_LOCK)
    high, low = op.mulw(excess, UInt64(3 * SCALE))
    q_hi, bonus, rem_hi, rem_lo = op.divmodw(
        high, low, UInt64(0), lock_range
    )
    assert q_hi == UInt64(0), "Multiplier overflow"
    return UInt64(SCALE) + bonus
