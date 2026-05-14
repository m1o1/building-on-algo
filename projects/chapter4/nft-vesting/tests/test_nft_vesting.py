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
    SCHEDULE_MBR,
    advance_time,
    create_vesting_token,
    fund_account,
    fund_app_account,
    opt_account_into_asset,
    schedule_box_key,
    transfer_asset,
)
from smart_contracts.artifacts.nft_vesting.nft_vesting_client import (
    ClaimArgs,
    CleanupScheduleArgs,
    CreateScheduleArgs,
    DeliverNftArgs,
    DepositTokensArgs,
    GetClaimableArgs,
    InitializeArgs,
    NftVestingFactory,
    RevokeArgs,
)


pytestmark = pytest.mark.localnet


def deploy_initialized_app(algorand):
    admin = algorand.account.random()
    fund_account(algorand, admin)
    asset_id = create_vesting_token(algorand, admin)

    factory = algorand.client.get_typed_app_factory(
        NftVestingFactory,
        default_sender=admin.address,
        default_signer=algorand.account.get_signer(admin.address),
    )
    app_client, create_result = factory.send.create.bare(
        params=CommonAppCallCreateParams(
            static_fee=AlgoAmount.from_micro_algo(1_000)
        )
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
    *,
    schedule_id,
    amount,
    cliff,
    duration,
):
    mbr_txn = algorand.create_transaction.payment(
        PaymentParams(
            sender=admin.address,
            receiver=app_address,
            amount=AlgoAmount.from_micro_algo(SCHEDULE_MBR),
        )
    )
    result = app_client.send.create_schedule(
        CreateScheduleArgs(
            schedule_id=schedule_id,
            total_amount=amount,
            cliff_duration=cliff,
            vesting_duration=duration,
            nft_url=b"ipfs://chapter4-test#arc3",
            metadata_hash=b"\0" * 32,
            mbr_payment=TransactionWithSigner(
                mbr_txn,
                algorand.account.get_signer(admin.address),
            ),
        ),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            box_references=[schedule_box_key(schedule_id)],
        ),
    )
    return result.abi_return


def deliver_nft(
    algorand,
    app_client,
    admin,
    holder,
    *,
    schedule_id,
    nft_id,
):
    opt_account_into_asset(algorand, holder, nft_id)
    app_client.send.deliver_nft(
        DeliverNftArgs(
            schedule_id=schedule_id,
            nft_asset=nft_id,
            beneficiary=holder.address,
        ),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[nft_id],
            account_references=[holder.address],
            box_references=[schedule_box_key(schedule_id)],
        ),
    )


def claim(algorand, app_client, holder, *, schedule_id, nft_id, asset_id):
    return app_client.send.claim(
        ClaimArgs(schedule_id=schedule_id, nft_asset=nft_id),
        params=CommonAppCallParams(
            sender=holder.address,
            signer=algorand.account.get_signer(holder.address),
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[asset_id, nft_id],
            box_references=[schedule_box_key(schedule_id)],
        ),
    )


def test_transfer_transfers_claim_rights(algorand) -> None:
    admin, asset_id, app_client, create_result = deploy_initialized_app(algorand)
    beneficiary = algorand.account.random()
    buyer = algorand.account.random()
    fund_account(algorand, beneficiary)
    fund_account(algorand, buyer)
    opt_account_into_asset(algorand, beneficiary, asset_id)
    opt_account_into_asset(algorand, buyer, asset_id)

    schedule_id = 1
    nft_id = create_schedule(
        algorand,
        app_client,
        create_result.app_address,
        admin,
        schedule_id=schedule_id,
        amount=1_000_000,
        cliff=1,
        duration=20,
    )
    deliver_nft(
        algorand,
        app_client,
        admin,
        beneficiary,
        schedule_id=schedule_id,
        nft_id=nft_id,
    )

    advance_time(algorand, 4)
    first_claim = claim(
        algorand,
        app_client,
        beneficiary,
        schedule_id=schedule_id,
        nft_id=nft_id,
        asset_id=asset_id,
    )
    assert 0 < first_claim.abi_return < 1_000_000

    opt_account_into_asset(algorand, buyer, nft_id)
    transfer_asset(algorand, beneficiary, buyer.address, nft_id, 1)

    with pytest.raises(Exception, match="Caller does not hold this NFT"):
        claim(
            algorand,
            app_client,
            beneficiary,
            schedule_id=schedule_id,
            nft_id=nft_id,
            asset_id=asset_id,
        )

    advance_time(algorand, 20)
    second_claim = claim(
        algorand,
        app_client,
        buyer,
        schedule_id=schedule_id,
        nft_id=nft_id,
        asset_id=asset_id,
    )
    assert first_claim.abi_return + second_claim.abi_return == 1_000_000

    app_client.send.cleanup_schedule(
        CleanupScheduleArgs(schedule_id=schedule_id),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            box_references=[schedule_box_key(schedule_id)],
        ),
    )
    with pytest.raises(Exception, match="No schedule"):
        app_client.send.get_claimable(
            GetClaimableArgs(schedule_id=schedule_id),
            params=CommonAppCallParams(
                box_references=[schedule_box_key(schedule_id)]
            ),
        )


def test_wrong_nft_for_schedule_fails(algorand) -> None:
    admin, asset_id, app_client, create_result = deploy_initialized_app(algorand)
    beneficiary = algorand.account.random()
    fund_account(algorand, beneficiary)
    opt_account_into_asset(algorand, beneficiary, asset_id)

    first_nft = create_schedule(
        algorand,
        app_client,
        create_result.app_address,
        admin,
        schedule_id=1,
        amount=500_000,
        cliff=1,
        duration=20,
    )
    second_nft = create_schedule(
        algorand,
        app_client,
        create_result.app_address,
        admin,
        schedule_id=2,
        amount=500_000,
        cliff=1,
        duration=20,
    )
    deliver_nft(
        algorand,
        app_client,
        admin,
        beneficiary,
        schedule_id=1,
        nft_id=first_nft,
    )
    deliver_nft(
        algorand,
        app_client,
        admin,
        beneficiary,
        schedule_id=2,
        nft_id=second_nft,
    )
    advance_time(algorand, 4)

    with pytest.raises(Exception, match="Wrong NFT"):
        claim(
            algorand,
            app_client,
            beneficiary,
            schedule_id=1,
            nft_id=second_nft,
            asset_id=asset_id,
        )


def test_revoke_settles_holder_and_allows_cleanup(algorand) -> None:
    admin, asset_id, app_client, create_result = deploy_initialized_app(algorand)
    beneficiary = algorand.account.random()
    fund_account(algorand, beneficiary)
    opt_account_into_asset(algorand, beneficiary, asset_id)

    schedule_id = 3
    nft_id = create_schedule(
        algorand,
        app_client,
        create_result.app_address,
        admin,
        schedule_id=schedule_id,
        amount=500_000,
        cliff=1,
        duration=20,
    )
    deliver_nft(
        algorand,
        app_client,
        admin,
        beneficiary,
        schedule_id=schedule_id,
        nft_id=nft_id,
    )
    advance_time(algorand, 4)

    claimable = app_client.send.get_claimable(
        GetClaimableArgs(schedule_id=schedule_id),
        params=CommonAppCallParams(
            box_references=[schedule_box_key(schedule_id)]
        ),
    )
    assert 0 < claimable.abi_return < 500_000

    revoked = app_client.send.revoke(
        RevokeArgs(
            schedule_id=schedule_id,
            nft_asset=nft_id,
            current_holder=beneficiary.address,
        ),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(5_000),
            asset_references=[asset_id, nft_id],
            account_references=[beneficiary.address],
            box_references=[schedule_box_key(schedule_id)],
        ),
    )
    assert 0 < revoked.abi_return < 500_000

    claimable_after = app_client.send.get_claimable(
        GetClaimableArgs(schedule_id=schedule_id),
        params=CommonAppCallParams(
            box_references=[schedule_box_key(schedule_id)]
        ),
    )
    assert claimable_after.abi_return == 0

    app_client.send.cleanup_schedule(
        CleanupScheduleArgs(schedule_id=schedule_id),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            box_references=[schedule_box_key(schedule_id)],
        ),
    )
