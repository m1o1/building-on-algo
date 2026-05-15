from __future__ import annotations

import base64
from dataclasses import dataclass

from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    AssetCreateParams,
    AssetOptInParams,
    AssetTransferParams,
    PaymentParams,
    SendParams,
)
from algosdk import encoding
from algosdk.atomic_transaction_composer import TransactionWithSigner

MICRO_UNITS = 10**6


@dataclass
class LocalnetAccount:
    address: str
    signer: object


def get_localnet_algorand() -> AlgorandClient:
    algorand = AlgorandClient.default_localnet()
    try:
        algorand.client.algod.status()
    except Exception as exc:  # pragma: no cover - depends on local environment
        raise RuntimeError(
            "LocalNet is not running. Start it with `algokit localnet start`."
        ) from exc
    algorand.set_suggested_params_timeout(0)
    return algorand


def fund_account(
    algorand: AlgorandClient,
    dispenser: LocalnetAccount,
    account: LocalnetAccount,
    *,
    amount: int = 10_000_000,
) -> None:
    algorand.send.payment(
        PaymentParams(
            sender=dispenser.address,
            signer=dispenser.signer,
            receiver=account.address,
            amount=AlgoAmount.from_micro_algo(amount),
        )
    )


def payment_arg(
    algorand: AlgorandClient,
    sender: LocalnetAccount,
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


def create_test_asset(
    algorand: AlgorandClient,
    creator: LocalnetAccount,
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
    account: LocalnetAccount,
    asset_id: int,
) -> None:
    algorand.send.asset_opt_in(
        AssetOptInParams(
            sender=account.address,
            signer=account.signer,
            asset_id=asset_id,
        ),
        send_params=SendParams(suppress_log=True),
    )


def transfer_asset(
    algorand: AlgorandClient,
    sender: LocalnetAccount,
    receiver: LocalnetAccount,
    asset_id: int,
    amount: int,
) -> None:
    algorand.send.asset_transfer(
        AssetTransferParams(
            sender=sender.address,
            signer=sender.signer,
            receiver=receiver.address,
            asset_id=asset_id,
            amount=amount,
        )
    )


def asset_transfer_arg(
    algorand: AlgorandClient,
    sender: LocalnetAccount,
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


def pair_box_reference(prefix: bytes, asset_a: int, asset_b: int) -> bytes:
    return prefix + asset_a.to_bytes(8, "big") + asset_b.to_bytes(8, "big")


def decode_box_uint64(value: str) -> int:
    raw = base64.b64decode(value)
    return int.from_bytes(raw, "big")


def address_bytes(address: str) -> bytes:
    return encoding.decode_address(address)
