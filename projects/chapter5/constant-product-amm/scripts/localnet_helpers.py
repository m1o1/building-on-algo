from __future__ import annotations

from algosdk.atomic_transaction_composer import TransactionWithSigner

from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    AssetCreateParams,
    AssetOptInParams,
    AssetTransferParams,
    PaymentParams,
    SigningAccount,
)


MICRO_UNITS = 1_000_000


def get_localnet_algorand() -> AlgorandClient:
    algorand = AlgorandClient.default_localnet()
    try:
        algorand.client.algod.status()
    except Exception as exc:  # pragma: no cover - depends on local Docker/Podman.
        raise RuntimeError(
            "LocalNet is not reachable. Start it with `algokit localnet start`."
        ) from exc
    return algorand


def fund_account(
    algorand: AlgorandClient,
    dispenser: SigningAccount,
    account: SigningAccount,
    *,
    algos: int = 20,
) -> None:
    algorand.send.payment(
        PaymentParams(
            sender=dispenser.address,
            signer=dispenser.signer,
            receiver=account.address,
            amount=AlgoAmount.from_algo(algos),
        )
    )


def create_test_asset(
    algorand: AlgorandClient,
    creator: SigningAccount,
    *,
    name: str,
    unit: str,
    total: int = 1_000_000_000_000,
) -> int:
    result = algorand.send.asset_create(
        AssetCreateParams(
            sender=creator.address,
            signer=creator.signer,
            total=total,
            decimals=6,
            asset_name=name,
            unit_name=unit,
            default_frozen=False,
        )
    )
    return result.asset_id


def opt_account_into_asset(
    algorand: AlgorandClient,
    account: SigningAccount,
    asset_id: int,
) -> None:
    algorand.send.asset_opt_in(
        AssetOptInParams(
            sender=account.address,
            signer=account.signer,
            asset_id=asset_id,
        )
    )


def transfer_asset(
    algorand: AlgorandClient,
    sender: SigningAccount,
    receiver: SigningAccount | str,
    asset_id: int,
    amount: int,
) -> None:
    receiver_address = receiver if isinstance(receiver, str) else receiver.address
    algorand.send.asset_transfer(
        AssetTransferParams(
            sender=sender.address,
            signer=sender.signer,
            receiver=receiver_address,
            asset_id=asset_id,
            amount=amount,
        )
    )


def payment_arg(
    algorand: AlgorandClient,
    sender: SigningAccount,
    receiver: str,
    amount: int,
) -> TransactionWithSigner:
    txn = algorand.create_transaction.payment(
        PaymentParams(
            sender=sender.address,
            receiver=receiver,
            amount=AlgoAmount.from_micro_algo(amount),
        )
    )
    return TransactionWithSigner(txn, sender.signer)


def asset_transfer_arg(
    algorand: AlgorandClient,
    sender: SigningAccount,
    receiver: str,
    asset_id: int,
    amount: int,
) -> TransactionWithSigner:
    txn = algorand.create_transaction.asset_transfer(
        AssetTransferParams(
            sender=sender.address,
            receiver=receiver,
            asset_id=asset_id,
            amount=amount,
        )
    )
    return TransactionWithSigner(txn, sender.signer)


def quote_swap(input_amount: int, reserve_in: int, reserve_out: int) -> int:
    input_with_fee = input_amount * 997
    return (input_with_fee * reserve_out) // (reserve_in * 1000 + input_with_fee)
