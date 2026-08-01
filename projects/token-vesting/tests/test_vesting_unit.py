"""The fast half of Chapter 9's suite.

Everything here runs against `algorand-python-testing`'s in-memory ledger:
no compilation, no LocalNet, no Docker, and a clock that moves four years in
one assignment. What that ledger cannot do is move a token, so the file stops
where the AVM starts --- the authorization and arithmetic that run before an
inner transaction, plus the inner transactions' own recorded fields.
"""

from __future__ import annotations

import pytest
from algopy import Account, OnCompleteAction, UInt64
from algopy_testing import AlgopyTestContext, algopy_testing_context

from smart_contracts.token_vesting.contract import TokenVesting

DAY = 86_400
CLIFF = 90 * DAY
DURATION = 360 * DAY
FOUR_YEARS = 4 * 365 * DAY
START = 1_700_000_000  # a fixed wall clock, so every schedule starts here
GRANT = 1_000_000_000  # 1,000 tokens at 6 decimals
POOL = 20_000_000_000  # what the admin deposited before any schedule exists
BOX_MBR = 2_500 + 400 * (34 + 41)


@pytest.fixture()
def ctx():  # type: ignore[no-untyped-def]
    with algopy_testing_context() as context:
        yield context


def _at(ctx: AlgopyTestContext, when: int) -> None:
    ctx.ledger.patch_global_fields(latest_timestamp=UInt64(when))


def _funded(ctx: AlgopyTestContext, pool: int = POOL) -> TokenVesting:
    """Create, initialize, and fill the pool. The admin is the default sender."""
    contract = TokenVesting()
    # algorand-python-testing 1.1.0 leaves a bare method's allow_actions as
    # strings, so the on-completion action has to be supplied as the enum here
    # or the routing check fails before the method body runs.
    with ctx.txn.create_group(
        active_txn_overrides={"on_completion": OnCompleteAction.NoOp}
    ):
        contract.create()
    asset = ctx.any.asset(total=2 * pool)
    contract.initialize(asset)
    deposit = ctx.any.txn.asset_transfer(
        sender=ctx.default_sender,
        asset_receiver=ctx.ledger.get_app(contract).address,
        xfer_asset=asset,
        asset_amount=UInt64(pool),
    )
    contract.deposit_tokens(deposit)
    return contract


def _mbr(ctx: AlgopyTestContext, contract: TokenVesting, sender: Account | None = None):  # type: ignore[no-untyped-def]
    return ctx.any.txn.payment(
        sender=sender or ctx.default_sender,
        receiver=ctx.ledger.get_app(contract).address,
        amount=UInt64(BOX_MBR),
    )


def _schedule(
    ctx: AlgopyTestContext,
    contract: TokenVesting,
    beneficiary: Account,
    total: int = GRANT,
    cliff: int = CLIFF,
    duration: int = DURATION,
) -> None:
    contract.create_schedule(
        beneficiary,
        UInt64(total),
        UInt64(cliff),
        UInt64(duration),
        _mbr(ctx, contract),
    )


# --- The curve, read through the queries a wallet polls ---------------------


def test_nothing_is_claimable_before_the_cliff(ctx: AlgopyTestContext) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    _at(ctx, START + CLIFF - 1)  # one second short of the threshold
    assert contract.get_claimable(beneficiary) == 0


def test_the_cliff_releases_everything_earned_since_the_start(
    ctx: AlgopyTestContext,
) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    _at(ctx, START + CLIFF)
    # The linear term measures from start, not from the cliff, so arriving at
    # the cliff releases a lump sum covering the whole three months.
    assert contract.get_claimable(beneficiary) == GRANT * CLIFF // DURATION


def test_the_ramp_floors_toward_the_contract(ctx: AlgopyTestContext) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    elapsed = CLIFF + 1  # deliberately not a divisor of the duration
    assert GRANT * elapsed % DURATION != 0, "pick an elapsed with a remainder"
    _at(ctx, START + elapsed)
    assert contract.get_claimable(beneficiary) == GRANT * elapsed // DURATION


def test_the_end_of_the_schedule_pays_the_exact_total(
    ctx: AlgopyTestContext,
) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    _at(ctx, START + DURATION)  # the dust the floors kept comes back here
    assert contract.get_claimable(beneficiary) == GRANT
    _at(ctx, START + DURATION + DAY)  # and never more than the total
    assert contract.get_claimable(beneficiary) == GRANT


def test_a_grant_that_would_overflow_a_narrow_multiply_still_pays(
    ctx: AlgopyTestContext,
) -> None:
    big = 10_000_000 * 10**6  # 10M tokens at 6 decimals
    _at(ctx, START)
    contract = _funded(ctx, pool=2 * big)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary, total=big, duration=FOUR_YEARS)

    elapsed = FOUR_YEARS - 1  # the last second before the schedule closes
    assert big * elapsed > 2**64, "this is the product that must not go narrow"
    _at(ctx, START + elapsed)
    assert contract.get_claimable(beneficiary) == big * elapsed // FOUR_YEARS


def test_a_stranger_has_no_schedule_to_read(ctx: AlgopyTestContext) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    stranger = ctx.any.account()

    with pytest.raises(AssertionError, match="No schedule"):
        contract.get_claimable(stranger)
    with pytest.raises(AssertionError, match="No schedule"):
        contract.get_vesting_info(stranger)


# --- create_schedule, up to the point where money would have to move --------


def test_only_the_admin_may_create_a_schedule(ctx: AlgopyTestContext) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    stranger = ctx.any.account()
    beneficiary = ctx.any.account()

    with ctx.txn.create_group(active_txn_overrides={"sender": stranger}):
        with pytest.raises(AssertionError, match="Only admin"):
            contract.create_schedule(
                beneficiary,
                UInt64(GRANT),
                UInt64(CLIFF),
                UInt64(DURATION),
                _mbr(ctx, contract, sender=stranger),
            )


def test_a_second_schedule_for_one_beneficiary_is_refused(
    ctx: AlgopyTestContext,
) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    with pytest.raises(AssertionError, match="Schedule already exists"):
        _schedule(ctx, contract, beneficiary)


def test_vesting_must_outlast_the_cliff(ctx: AlgopyTestContext) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()

    with pytest.raises(AssertionError, match="Vesting must exceed cliff"):
        _schedule(ctx, contract, beneficiary, cliff=DURATION, duration=DURATION)


def test_a_schedule_cannot_promise_more_than_the_pool_holds(
    ctx: AlgopyTestContext,
) -> None:
    _at(ctx, START)
    contract = _funded(ctx, pool=GRANT)
    beneficiary = ctx.any.account()

    with pytest.raises(AssertionError, match="Insufficient tokens"):
        _schedule(ctx, contract, beneficiary, total=GRANT + 1)


def test_creating_a_schedule_reserves_its_tokens_from_the_pool(
    ctx: AlgopyTestContext,
) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    assert contract.available_tokens.value == POOL - GRANT
    assert contract.beneficiary_count.value == 1
    info = contract.get_vesting_info(beneficiary)
    assert info.total_amount.as_uint64() == GRANT
    assert info.claimed_amount.as_uint64() == 0
    assert info.start_time.as_uint64() == START
    assert info.cliff_end.as_uint64() == START + CLIFF
    assert info.vesting_end.as_uint64() == START + DURATION
    assert not info.is_revoked.native


# --- revoke, including the transfer it emits --------------------------------


def test_revoke_returns_only_the_unvested_remainder(ctx: AlgopyTestContext) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    _at(ctx, START + DURATION // 2)
    vested = GRANT * (DURATION // 2) // DURATION
    assert contract.revoke(beneficiary) == GRANT - vested

    refund = ctx.txn.last_group.last_itxn.asset_transfer
    assert refund.asset_receiver == ctx.default_sender  # the admin funded it
    assert refund.asset_amount == GRANT - vested
    assert refund.fee == 0  # the caller's fee covers it, by pooling


def test_revoke_freezes_the_curve_at_the_revocation_timestamp(
    ctx: AlgopyTestContext,
) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    when = START + DURATION // 2
    _at(ctx, when)
    vested = GRANT * (DURATION // 2) // DURATION
    contract.revoke(beneficiary)

    info = contract.get_vesting_info(beneficiary)
    assert info.is_revoked.native
    assert info.total_amount.as_uint64() == vested
    assert info.cliff_end.as_uint64() == when
    assert info.vesting_end.as_uint64() == when

    # The capped total is fully vested from here on, not re-ramped.
    assert contract.get_claimable(beneficiary) == vested
    _at(ctx, START + DURATION)
    assert contract.get_claimable(beneficiary) == vested


def test_revoking_before_the_cliff_returns_the_whole_grant(
    ctx: AlgopyTestContext,
) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    _at(ctx, START + CLIFF - 1)
    assert contract.revoke(beneficiary) == GRANT
    assert ctx.txn.last_group.last_itxn.asset_transfer.asset_amount == GRANT
    assert contract.get_claimable(beneficiary) == 0


def test_revoking_a_fully_vested_schedule_moves_nothing(
    ctx: AlgopyTestContext,
) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    _at(ctx, START + DURATION)
    assert contract.revoke(beneficiary) == 0
    # Nothing was unvested, so the method sends no inner transaction at all.
    assert len(ctx.txn.last_group.itxn_groups) == 0
    assert contract.get_claimable(beneficiary) == GRANT


def test_only_the_admin_may_revoke(ctx: AlgopyTestContext) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    _at(ctx, START + DURATION // 2)
    with ctx.txn.create_group(active_txn_overrides={"sender": beneficiary}):
        with pytest.raises(AssertionError, match="Only admin"):
            contract.revoke(beneficiary)


def test_a_schedule_cannot_be_revoked_twice(ctx: AlgopyTestContext) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    _at(ctx, START + DURATION // 2)
    contract.revoke(beneficiary)
    with pytest.raises(AssertionError, match="Already revoked"):
        contract.revoke(beneficiary)


# --- cleanup_schedule, and the assertion with nothing to say ----------------


def test_cleanup_refunds_the_box_mbr_to_the_admin(ctx: AlgopyTestContext) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    _at(ctx, START + CLIFF - 1)
    contract.revoke(beneficiary)  # nothing vested, so nothing is owed

    stranger = ctx.any.account()  # cleanup is deliberately permissionless
    with ctx.txn.create_group(active_txn_overrides={"sender": stranger}):
        contract.cleanup_schedule(beneficiary)

    refund = ctx.txn.last_group.last_itxn.payment
    assert refund.receiver == ctx.default_sender  # the admin, not the caller
    assert refund.amount == BOX_MBR
    assert refund.fee == 0
    assert contract.beneficiary_count.value == 0
    with pytest.raises(AssertionError, match="No schedule"):
        contract.get_claimable(beneficiary)


def test_cleanup_refuses_a_schedule_that_is_still_owed_tokens(
    ctx: AlgopyTestContext,
) -> None:
    _at(ctx, START)
    contract = _funded(ctx)
    beneficiary = ctx.any.account()
    _schedule(ctx, contract, beneficiary)

    # This assertion carries no message, so the test can only say that
    # something was raised. Give it a sentence and this test can say which.
    with pytest.raises(AssertionError):
        contract.cleanup_schedule(beneficiary)
    assert contract.get_vesting_info(beneficiary).total_amount.as_uint64() == GRANT


# --- the lifecycle stance ---------------------------------------------------


@pytest.mark.parametrize(
    "action",
    [OnCompleteAction.UpdateApplication, OnCompleteAction.DeleteApplication],
)
def test_the_contract_refuses_to_be_updated_or_deleted(
    ctx: AlgopyTestContext, action: OnCompleteAction
) -> None:
    contract = _funded(ctx)
    with ctx.txn.create_group(active_txn_overrides={"on_completion": action}):
        with pytest.raises(AssertionError, match="Contract is immutable"):
            contract.reject_lifecycle()
