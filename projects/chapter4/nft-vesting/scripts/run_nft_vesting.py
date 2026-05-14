from __future__ import annotations

from algokit_utils import (
    AlgoAmount,
    AssetTransferParams,
    CommonAppCallCreateParams,
    CommonAppCallParams,
    PaymentParams,
)
from algosdk.atomic_transaction_composer import TransactionWithSigner

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

from .localnet_helpers import (
    SCHEDULE_MBR,
    advance_time,
    create_vesting_token,
    fund_account,
    fund_app_account,
    get_localnet_algorand,
    opt_account_into_asset,
    schedule_box_key,
    transfer_asset,
)


def create_schedule(
    algorand,
    app_client,
    app_address: str,
    admin,
    *,
    schedule_id: int,
    amount: int,
    cliff: int,
    duration: int,
) -> int:
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
            nft_url=b"ipfs://chapter4-local#arc3",
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


def main() -> None:
    algorand = get_localnet_algorand()

    admin = algorand.account.random()
    beneficiary = algorand.account.random()
    buyer = algorand.account.random()
    fund_account(algorand, admin)
    fund_account(algorand, beneficiary)
    fund_account(algorand, buyer)
    print(f"admin:      {admin.address}")
    print(f"beneficiary:{beneficiary.address}")
    print(f"buyer:      {buyer.address}")

    asset_id = create_vesting_token(algorand, admin)
    print(f"created vesting ASA: {asset_id}")

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
    app_id = create_result.app_id
    app_address = create_result.app_address
    print(f"deployed app: {app_id} ({app_address})")

    fund_app_account(algorand, admin, app_address)
    app_client.send.initialize(
        InitializeArgs(vesting_asset=asset_id),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[asset_id],
        ),
    )
    print("initialized app and opted it into the vesting ASA")

    deposit_txn = algorand.create_transaction.asset_transfer(
        AssetTransferParams(
            sender=admin.address,
            receiver=app_address,
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
    print(f"deposited {deposited.abi_return} vesting tokens")

    opt_account_into_asset(algorand, beneficiary, asset_id)
    schedule_id = 1
    nft_id = create_schedule(
        algorand,
        app_client,
        app_address,
        admin,
        schedule_id=schedule_id,
        amount=1_000_000,
        cliff=1,
        duration=20,
    )
    print(f"created transferable schedule NFT: {nft_id}")

    opt_account_into_asset(algorand, beneficiary, nft_id)
    app_client.send.deliver_nft(
        DeliverNftArgs(
            schedule_id=schedule_id,
            nft_asset=nft_id,
            beneficiary=beneficiary.address,
        ),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[nft_id],
            account_references=[beneficiary.address],
            box_references=[schedule_box_key(schedule_id)],
        ),
    )
    print("delivered NFT to beneficiary")

    advance_time(algorand, 4)
    beneficiary_claim = app_client.send.claim(
        ClaimArgs(schedule_id=schedule_id, nft_asset=nft_id),
        params=CommonAppCallParams(
            sender=beneficiary.address,
            signer=algorand.account.get_signer(beneficiary.address),
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[asset_id, nft_id],
            box_references=[schedule_box_key(schedule_id)],
        ),
    )
    print(f"beneficiary claimed: {beneficiary_claim.abi_return}")

    opt_account_into_asset(algorand, buyer, asset_id)
    opt_account_into_asset(algorand, buyer, nft_id)
    transfer_asset(algorand, beneficiary, buyer.address, nft_id, 1)
    print("transferred NFT to buyer")

    advance_time(algorand, 20)
    buyer_claim = app_client.send.claim(
        ClaimArgs(schedule_id=schedule_id, nft_asset=nft_id),
        params=CommonAppCallParams(
            sender=buyer.address,
            signer=algorand.account.get_signer(buyer.address),
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[asset_id, nft_id],
            box_references=[schedule_box_key(schedule_id)],
        ),
    )
    print(f"buyer claimed remaining tokens: {buyer_claim.abi_return}")

    app_client.send.cleanup_schedule(
        CleanupScheduleArgs(schedule_id=schedule_id),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            box_references=[schedule_box_key(schedule_id)],
        ),
    )
    print("cleaned up fully claimed schedule")

    revoke_schedule_id = 2
    revoke_nft_id = create_schedule(
        algorand,
        app_client,
        app_address,
        admin,
        schedule_id=revoke_schedule_id,
        amount=500_000,
        cliff=1,
        duration=20,
    )
    opt_account_into_asset(algorand, beneficiary, revoke_nft_id)
    app_client.send.deliver_nft(
        DeliverNftArgs(
            schedule_id=revoke_schedule_id,
            nft_asset=revoke_nft_id,
            beneficiary=beneficiary.address,
        ),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[revoke_nft_id],
            account_references=[beneficiary.address],
            box_references=[schedule_box_key(revoke_schedule_id)],
        ),
    )
    print(f"created revocation schedule NFT: {revoke_nft_id}")

    advance_time(algorand, 4)
    claimable = app_client.send.get_claimable(
        GetClaimableArgs(schedule_id=revoke_schedule_id),
        params=CommonAppCallParams(
            box_references=[schedule_box_key(revoke_schedule_id)]
        ),
    )
    revoked = app_client.send.revoke(
        RevokeArgs(
            schedule_id=revoke_schedule_id,
            nft_asset=revoke_nft_id,
            current_holder=beneficiary.address,
        ),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(5_000),
            asset_references=[asset_id, revoke_nft_id],
            account_references=[beneficiary.address],
            box_references=[schedule_box_key(revoke_schedule_id)],
        ),
    )
    print(f"beneficiary settled on revoke: {claimable.abi_return}")
    print(f"unvested tokens returned to admin: {revoked.abi_return}")

    app_client.send.cleanup_schedule(
        CleanupScheduleArgs(schedule_id=revoke_schedule_id),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            box_references=[schedule_box_key(revoke_schedule_id)],
        ),
    )
    print("cleaned up revoked schedule")

    print("Chapter 4 workflow complete")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(exc)
        raise SystemExit(1) from exc
