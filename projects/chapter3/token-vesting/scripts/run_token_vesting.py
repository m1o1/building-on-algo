from __future__ import annotations

from algokit_utils import (
    AlgoAmount,
    AssetTransferParams,
    CommonAppCallCreateParams,
    CommonAppCallParams,
    PaymentParams,
)
from algosdk.atomic_transaction_composer import TransactionWithSigner

from smart_contracts.artifacts.token_vesting.token_vesting_client import (
    CleanupScheduleArgs,
    CreateScheduleArgs,
    DepositTokensArgs,
    GetClaimableArgs,
    InitializeArgs,
    RevokeArgs,
    TokenVestingFactory,
)

from .localnet_helpers import (
    BOX_MBR,
    advance_time,
    create_vesting_token,
    fund_account,
    fund_app_account,
    get_localnet_algorand,
    opt_account_into_asset,
    schedule_box_key,
)


def main() -> None:
    algorand = get_localnet_algorand()

    admin = algorand.account.random()
    alice = algorand.account.random()
    bob = algorand.account.random()
    fund_account(algorand, admin)
    fund_account(algorand, alice)
    fund_account(algorand, bob)
    print(f"admin: {admin.address}")
    print(f"alice: {alice.address}")
    print(f"bob:   {bob.address}")

    asset_id = create_vesting_token(algorand, admin)
    print(f"created ASA: {asset_id}")

    factory = algorand.client.get_typed_app_factory(
        TokenVestingFactory,
        default_sender=admin.address,
        default_signer=algorand.account.get_signer(admin.address),
    )
    app_client, create_result = factory.send.create.bare(
        params=CommonAppCallCreateParams(static_fee=AlgoAmount.from_micro_algo(1_000))
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
    print("initialized app and opted it into the ASA")

    deposit_txn = algorand.create_transaction.asset_transfer(
        AssetTransferParams(
            sender=admin.address,
            receiver=app_address,
            asset_id=asset_id,
            amount=2_000_000,
        )
    )
    app_client.send.deposit_tokens(
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
    print("deposited 2,000,000 vesting tokens")

    opt_account_into_asset(algorand, alice, asset_id)
    alice_mbr_txn = algorand.create_transaction.payment(
        PaymentParams(
            sender=admin.address,
            receiver=app_address,
            amount=AlgoAmount.from_micro_algo(BOX_MBR),
        )
    )
    app_client.send.create_schedule(
        CreateScheduleArgs(
            beneficiary=alice.address,
            total_amount=1_000_000,
            cliff_duration=1,
            vesting_duration=5,
            mbr_payment=TransactionWithSigner(
                alice_mbr_txn,
                algorand.account.get_signer(admin.address),
            ),
        ),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(1_000),
            account_references=[alice.address],
            box_references=[schedule_box_key(alice.address)],
        ),
    )
    print("created Alice schedule")

    advance_time(algorand, 6)
    alice_claim = app_client.send.claim(
        params=CommonAppCallParams(
            sender=alice.address,
            signer=algorand.account.get_signer(alice.address),
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[asset_id],
            box_references=[schedule_box_key(alice.address)],
        )
    )
    print(f"Alice claimed: {alice_claim.abi_return}")
    app_client.send.cleanup_schedule(
        CleanupScheduleArgs(beneficiary=alice.address),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            box_references=[schedule_box_key(alice.address)],
        ),
    )
    print("cleaned up Alice schedule")

    opt_account_into_asset(algorand, bob, asset_id)
    bob_mbr_txn = algorand.create_transaction.payment(
        PaymentParams(
            sender=admin.address,
            receiver=app_address,
            amount=AlgoAmount.from_micro_algo(BOX_MBR),
        )
    )
    app_client.send.create_schedule(
        CreateScheduleArgs(
            beneficiary=bob.address,
            total_amount=500_000,
            cliff_duration=1,
            vesting_duration=20,
            mbr_payment=TransactionWithSigner(
                bob_mbr_txn,
                algorand.account.get_signer(admin.address),
            ),
        ),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(1_000),
            account_references=[bob.address],
            box_references=[schedule_box_key(bob.address)],
        ),
    )
    print("created Bob schedule")

    advance_time(algorand, 4)
    bob_claimable = app_client.send.get_claimable(
        GetClaimableArgs(beneficiary=bob.address),
        params=CommonAppCallParams(
            account_references=[bob.address],
            box_references=[schedule_box_key(bob.address)],
        ),
    )
    print(f"Bob claimable before revoke: {bob_claimable.abi_return}")
    revoked = app_client.send.revoke(
        RevokeArgs(beneficiary=bob.address),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[asset_id],
            account_references=[bob.address],
            box_references=[schedule_box_key(bob.address)],
        ),
    )
    print(f"Bob unvested tokens returned to admin: {revoked.abi_return}")
    if bob_claimable.abi_return:
        bob_claim = app_client.send.claim(
            params=CommonAppCallParams(
                sender=bob.address,
                signer=algorand.account.get_signer(bob.address),
                static_fee=AlgoAmount.from_micro_algo(2_000),
                asset_references=[asset_id],
                box_references=[schedule_box_key(bob.address)],
            )
        )
        print(f"Bob claimed vested amount after revoke: {bob_claim.abi_return}")
    app_client.send.cleanup_schedule(
        CleanupScheduleArgs(beneficiary=bob.address),
        params=CommonAppCallParams(
            static_fee=AlgoAmount.from_micro_algo(2_000),
            box_references=[schedule_box_key(bob.address)],
        ),
    )
    print("cleaned up Bob schedule")

    print("Chapter 3 workflow complete")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(exc)
        raise SystemExit(1) from exc
