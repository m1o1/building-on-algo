from __future__ import annotations

import pytest
from algokit_utils import (
    AlgoAmount,
    AssetTransferParams,
    CommonAppCallCreateParams,
    CommonAppCallParams,
    PaymentParams,
)
from algosdk.atomic_transaction_composer import TransactionWithSigner

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


def create_schedule(
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

    create_schedule(
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


def test_revoke_returns_only_unvested_tokens(algorand) -> None:
    admin, asset_id, app_client, create_result = deploy_initialized_app(algorand)
    beneficiary = algorand.account.random()
    fund_account(algorand, beneficiary)
    opt_account_into_asset(algorand, beneficiary, asset_id)

    create_schedule(
        algorand,
        app_client,
        create_result.app_address,
        admin,
        beneficiary,
        amount=500_000,
        cliff=1,
        duration=20,
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
