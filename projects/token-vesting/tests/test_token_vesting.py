from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path

import pytest
from algokit_utils import (
    AlgoAmount,
    AppClientMethodCallParams,
    AppFactoryCreateParams,
    AssetCreateParams,
    AssetTransferParams,
    CommonAppCallCreateParams,
    CommonAppCallParams,
    PaymentParams,
)
from algosdk.atomic_transaction_composer import TransactionWithSigner
from algosdk.encoding import decode_address, encode_address

from scripts.localnet_helpers import (
    BOX_MBR,
    advance_time,
    create_vesting_token,
    fund_account,
    fund_app_account,
    opt_account_into_asset,
    schedule_box_key,
)
from smart_contracts.artifacts.token_vesting.token_vesting_client import (
    CleanupScheduleArgs,
    CreateScheduleArgs,
    DepositTokensArgs,
    GetClaimableArgs,
    InitializeArgs,
    RevokeArgs,
    TokenVestingFactory,
)


pytestmark = pytest.mark.localnet

# ARC-28: an event is identified by the first four bytes of the sha512_256
# hash of its signature, exactly like an ARC-4 method selector.
CLAIMED_SIGNATURE = "Claimed(address,uint64)"
CLAIMED_PREFIX = hashlib.new("sha512_256", CLAIMED_SIGNATURE.encode()).digest()[:4]


def deploy_initialized_app(algorand):
    admin = algorand.account.random()
    fund_account(algorand, admin)
    asset_id = create_vesting_token(algorand, admin)

    factory = algorand.client.get_typed_app_factory(
        TokenVestingFactory,
        default_sender=admin.address,
        default_signer=algorand.account.get_signer(admin.address),
    )
    app_client, create_result = factory.send.create.bare(
        params=CommonAppCallCreateParams(static_fee=AlgoAmount.from_micro_algo(1_000))
    )
    fund_app_account(algorand, admin, create_result.app_address)
    app_client.send.initialize(
        InitializeArgs(vesting_asset=asset_id),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[asset_id],
        ),
    )

    deposit_txn = algorand.create_transaction.asset_transfer(
        AssetTransferParams(
            sender=admin.address,
            receiver=create_result.app_address,
            asset_id=asset_id,
            amount=2_000_000,
        )
    )
    deposited = app_client.send.deposit_tokens(
        DepositTokensArgs(
            deposit_txn=TransactionWithSigner(
                deposit_txn,
                algorand.account.get_signer(admin.address),
            )
        ),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(1_000),
            asset_references=[asset_id],
        ),
    )
    assert deposited.abi_return == 2_000_000
    return admin, asset_id, app_client, create_result


def create_typed_schedule(
    algorand,
    app_client,
    app_address,
    admin,
    beneficiary,
    amount,
    cliff,
    duration,
):
    mbr_txn = algorand.create_transaction.payment(
        PaymentParams(
            sender=admin.address,
            receiver=app_address,
            amount=AlgoAmount.from_micro_algo(BOX_MBR),
        )
    )
    app_client.send.create_schedule(
        CreateScheduleArgs(
            beneficiary=beneficiary.address,
            total_amount=amount,
            cliff_duration=cliff,
            vesting_duration=duration,
            mbr_payment=TransactionWithSigner(
                mbr_txn,
                algorand.account.get_signer(admin.address),
            ),
        ),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(1_000),
            account_references=[beneficiary.address],
            box_references=[schedule_box_key(beneficiary.address)],
        ),
    )


def test_full_claim_and_cleanup_flow(algorand) -> None:
    admin, asset_id, app_client, create_result = deploy_initialized_app(algorand)
    beneficiary = algorand.account.random()
    fund_account(algorand, beneficiary)
    opt_account_into_asset(algorand, beneficiary, asset_id)

    create_typed_schedule(
        algorand,
        app_client,
        create_result.app_address,
        admin,
        beneficiary,
        amount=1_000_000,
        cliff=1,
        duration=5,
    )
    advance_time(algorand, 6)

    claim = app_client.send.claim(
        params=CommonAppCallParams(
            sender=beneficiary.address,
            signer=algorand.account.get_signer(beneficiary.address),
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[asset_id],
            box_references=[schedule_box_key(beneficiary.address)],
        )
    )
    assert claim.abi_return == 1_000_000

    app_client.send.cleanup_schedule(
        CleanupScheduleArgs(beneficiary=beneficiary.address),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            box_references=[schedule_box_key(beneficiary.address)],
        ),
    )
    with pytest.raises(Exception, match="No schedule"):
        app_client.send.get_claimable(
            GetClaimableArgs(beneficiary=beneficiary.address),
            params=CommonAppCallParams(
                account_references=[beneficiary.address],
                box_references=[schedule_box_key(beneficiary.address)],
            ),
        )


def test_claim_emits_arc28_claimed_event(algorand) -> None:
    admin, asset_id, app_client, create_result = deploy_initialized_app(algorand)
    beneficiary = algorand.account.random()
    fund_account(algorand, beneficiary)
    opt_account_into_asset(algorand, beneficiary, asset_id)

    create_typed_schedule(
        algorand,
        app_client,
        create_result.app_address,
        admin,
        beneficiary,
        amount=750_000,
        cliff=1,
        duration=5,
    )
    advance_time(algorand, 6)

    claim = app_client.send.claim(
        params=CommonAppCallParams(
            sender=beneficiary.address,
            signer=algorand.account.get_signer(beneficiary.address),
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[asset_id],
            box_references=[schedule_box_key(beneficiary.address)],
        )
    )
    assert claim.abi_return == 750_000

    logs = [base64.b64decode(entry) for entry in claim.confirmation["logs"]]
    events = [entry for entry in logs if entry[:4] == CLAIMED_PREFIX]
    assert len(events) == 1, "claim should emit exactly one Claimed event"

    # Both fields are fixed-size ARC-4 types, so the payload is a plain
    # concatenation: 32 bytes of address followed by 8 bytes of amount.
    payload = events[0][4:]
    assert len(payload) == 40
    assert encode_address(payload[:32]) == beneficiary.address
    assert int.from_bytes(payload[32:], "big") == 750_000


def test_revoke_returns_only_unvested_tokens(algorand) -> None:
    admin, asset_id, app_client, create_result = deploy_initialized_app(algorand)
    beneficiary = algorand.account.random()
    fund_account(algorand, beneficiary)
    opt_account_into_asset(algorand, beneficiary, asset_id)

    create_typed_schedule(
        algorand,
        app_client,
        create_result.app_address,
        admin,
        beneficiary,
        amount=500_000,
        cliff=1,
        # Long enough that blocks produced by anything else sharing this
        # LocalNet cannot finish the schedule before the revocation.
        duration=300,
    )
    advance_time(algorand, 4)

    claimable = app_client.send.get_claimable(
        GetClaimableArgs(beneficiary=beneficiary.address),
        params=CommonAppCallParams(
            account_references=[beneficiary.address],
            box_references=[schedule_box_key(beneficiary.address)],
        ),
    )
    assert 0 < claimable.abi_return < 500_000

    revoked = app_client.send.revoke(
        RevokeArgs(beneficiary=beneficiary.address),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[asset_id],
            account_references=[beneficiary.address],
            box_references=[schedule_box_key(beneficiary.address)],
        ),
    )

    claim = app_client.send.claim(
        params=CommonAppCallParams(
            sender=beneficiary.address,
            signer=algorand.account.get_signer(beneficiary.address),
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[asset_id],
            box_references=[schedule_box_key(beneficiary.address)],
        )
    )
    assert claim.abi_return >= claimable.abi_return
    assert claim.abi_return + revoked.abi_return == 500_000

    app_client.send.cleanup_schedule(
        CleanupScheduleArgs(beneficiary=beneficiary.address),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            box_references=[schedule_box_key(beneficiary.address)],
        ),
    )
    with pytest.raises(Exception, match="No schedule"):
        app_client.send.get_claimable(
            GetClaimableArgs(beneficiary=beneficiary.address),
            params=CommonAppCallParams(
                account_references=[beneficiary.address],
                box_references=[schedule_box_key(beneficiary.address)],
            ),
        )


# --- The chapter's helpers, in the generic-client register ------------------
# Everything above drives the contract through the generated typed client,
# which is what a production integration should do. The helpers below are the
# ones Chapter 9 prints: string method names, hand-built groups, and box and
# asset references named by hand. They live here so the page can print code
# that has run.

APP_SPEC = Path(
    "smart_contracts/artifacts/token_vesting/"
    "TokenVesting.arc56.json"
).read_text()


def deploy_vesting(algorand, admin):
    """Deploy a fresh TokenVesting contract and
    fund it with enough Algo for MBR."""
    factory = algorand.client.get_app_factory(
        app_spec=APP_SPEC,
        default_sender=admin.address,
    )
    # A bare create, because this contract's create method is a bare method.
    # factory.deploy() would hand back the app this admin deployed last time,
    # which is what a deployment script wants and not what a test wants. The
    # note is what keeps two tests from building the same create twice.
    app_client, _ = factory.send.bare.create(
        params=AppFactoryCreateParams(note=os.urandom(8))
    )
    # Fund the contract: 300,000 covers base MBR +
    # ASA opt-in + inner txn fee headroom
    algorand.send.payment(
        PaymentParams(
            sender=admin.address,
            receiver=app_client.app_address,
            amount=AlgoAmount.from_micro_algo(300_000),
        )
    )
    return app_client


def create_test_asa(algorand, admin, total):
    """Create the ASA this contract will vest. The admin holds all of it."""
    result = algorand.send.asset_create(
        AssetCreateParams(
            sender=admin.address,
            total=total,
            decimals=6,
            asset_name="TestVestingToken",
            unit_name="TVT",
            # Two tests creating the same ASA from the same admin would
            # otherwise build the same transaction twice, and the second is
            # rejected as already in the ledger.
            note=os.urandom(8),
        )
    )
    return result.asset_id


def deposit_tokens(algorand, admin, vesting, token_id, amount):
    """Group the transfer with the call, which is what the method asserts."""
    transfer = algorand.create_transaction.asset_transfer(
        AssetTransferParams(
            sender=admin.address,
            receiver=vesting.app_address,
            asset_id=token_id,
            amount=amount,
        )
    )
    return vesting.send.call(
        AppClientMethodCallParams(
            method="deposit_tokens",
            args=[transfer],
            asset_references=[token_id],
        )
    ).abi_return


def create_schedule(
    algorand, admin, vesting, beneficiary,
    total, cliff_duration, vesting_duration,
):
    """Pay the box MBR and create the schedule, in one group of two."""
    mbr_txn = algorand.create_transaction.payment(
        PaymentParams(
            sender=admin.address,
            receiver=vesting.app_address,
            amount=AlgoAmount.from_micro_algo(BOX_MBR),
        )
    )
    vesting.send.call(
        AppClientMethodCallParams(
            method="create_schedule",
            args=[
                beneficiary, total, cliff_duration, vesting_duration, mbr_txn,
            ],
            account_references=[beneficiary],
            # decode_address is from algosdk.encoding
            box_references=[b"v_" + decode_address(beneficiary)],
        )
    )


def get_claimable(vesting, beneficiary):
    """What a wallet polls. Readonly, and it still has to name the box."""
    return vesting.send.call(
        AppClientMethodCallParams(
            method="get_claimable",
            args=[beneficiary],
            account_references=[beneficiary],
            box_references=[b"v_" + decode_address(beneficiary)],
        )
    ).abi_return


def onboard_beneficiary(algorand, admin, beneficiary, token_id):
    """Fund a beneficiary and opt them into the grant asset.
    Nothing can be paid to an account that has not opted in."""
    algorand.send.payment(PaymentParams(
        sender=admin.address, receiver=beneficiary.address,
        amount=AlgoAmount.from_micro_algo(500_000),
        note=os.urandom(8),
    ))
    algorand.send.asset_transfer(AssetTransferParams(
        sender=beneficiary.address, receiver=beneficiary.address,
        asset_id=token_id, amount=0,
    ))


# Wraps the v4 send.call pattern for concise test code. Methods that emit
# inner transactions (claim, revoke, cleanup_schedule) need a static_fee of
# 2,000 so the outer transaction's fee covers the inner one by pooling; the
# note is what tells two otherwise identical calls apart.
FEE_FOR_ONE_INNER = AlgoAmount.from_micro_algo(2_000)


def call_method(app_client, method, args, sender=None, static_fee=None):
    return app_client.send.call(
        AppClientMethodCallParams(
            method=method, args=args, sender=sender, static_fee=static_fee,
            note=os.urandom(8),
        )
    )


class TestTokenVesting:
    def test_full_lifecycle(self, algorand):
        admin = algorand.account.localnet_dispenser()
        beneficiary = algorand.account.random()
        token_id = create_test_asa(algorand, admin, total=10_000_000_000)
        onboard_beneficiary(algorand, admin, beneficiary, token_id)

        vesting = deploy_vesting(algorand, admin)
        call_method(vesting, "initialize", [token_id],
                    static_fee=FEE_FOR_ONE_INNER)
        deposit_tokens(algorand, admin, vesting, token_id, 1_000_000_000)

        # Use short durations for LocalNet testing (seconds, not months).
        # Production contracts would use cliff_duration=90*86400,
        # vesting_duration=365*86400.
        create_schedule(algorand, admin, vesting, beneficiary.address,
            total=1_000_000_000,
            cliff_duration=8,
            vesting_duration=30)

        assert get_claimable(vesting, beneficiary.address) == 0
        advance_time(algorand, 10)  # Past cliff
        claimable = get_claimable(vesting, beneficiary.address)
        assert 0 < claimable < 1_000_000_000

        call_method(vesting, "claim", [], sender=beneficiary.address,
                    static_fee=FEE_FOR_ONE_INNER)
        advance_time(algorand, 30)  # Past full vesting
        call_method(vesting, "claim", [], sender=beneficiary.address,
                    static_fee=FEE_FOR_ONE_INNER)
        call_method(vesting, "cleanup_schedule", [beneficiary.address],
                    static_fee=FEE_FOR_ONE_INNER)

    def test_revocation_returns_unvested(self, algorand):
        admin = algorand.account.localnet_dispenser()
        beneficiary = algorand.account.random()
        token_id = create_test_asa(algorand, admin, total=10_000_000_000)
        onboard_beneficiary(algorand, admin, beneficiary, token_id)
        vesting = deploy_vesting(algorand, admin)
        call_method(vesting, "initialize", [token_id],
                    static_fee=FEE_FOR_ONE_INNER)
        deposit_tokens(algorand, admin, vesting, token_id, 1_000_000_000)
        # A long vesting window, so that blocks produced by anything else
        # sharing this LocalNet cannot finish the schedule mid-test.
        create_schedule(algorand, admin, vesting, beneficiary.address,
            total=1_000_000_000,
            cliff_duration=8,
            vesting_duration=300)

        advance_time(algorand, 15)  # Past cliff, mid-vesting
        unvested = call_method(vesting, "revoke", [beneficiary.address],
                               static_fee=FEE_FOR_ONE_INNER)
        assert unvested.abi_return > 0
        claimed = call_method(vesting, "claim", [], sender=beneficiary.address,
                              static_fee=FEE_FOR_ONE_INNER)
        assert claimed.abi_return > 0
        assert claimed.abi_return + unvested.abi_return == 1_000_000_000

    def test_double_claim_fails(self, algorand):
        admin = algorand.account.localnet_dispenser()
        beneficiary = algorand.account.random()
        token_id = create_test_asa(algorand, admin, total=10_000_000_000)
        onboard_beneficiary(algorand, admin, beneficiary, token_id)
        vesting = deploy_vesting(algorand, admin)
        call_method(vesting, "initialize", [token_id],
                    static_fee=FEE_FOR_ONE_INNER)
        deposit_tokens(algorand, admin, vesting, token_id, 1_000_000_000)
        create_schedule(algorand, admin, vesting, beneficiary.address,
            total=1_000_000_000,
            cliff_duration=8,
            vesting_duration=30)

        # Past full vesting, deliberately: mid-schedule, a second claim
        # succeeds, because submitting the first one produced a block and a
        # second of vesting with it. Only an exhausted schedule refuses.
        advance_time(algorand, 35)
        call_method(vesting, "claim", [], sender=beneficiary.address,
                    static_fee=FEE_FOR_ONE_INNER)
        with pytest.raises(Exception, match="Nothing to claim"):
            call_method(vesting, "claim", [], sender=beneficiary.address,
                        static_fee=FEE_FOR_ONE_INNER)
