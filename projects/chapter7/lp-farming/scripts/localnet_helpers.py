from __future__ import annotations

import importlib.util
import os
import time
import urllib.request
from pathlib import Path
from types import ModuleType

from algosdk.atomic_transaction_composer import TransactionWithSigner
from algosdk.encoding import decode_address

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
STAKE_BOX_MBR = 32_100
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[4]
CHAPTER5_PROJECT = REPO_ROOT / "projects" / "chapter5" / "constant-product-amm"
CHAPTER5_CLIENT = (
    CHAPTER5_PROJECT
    / "smart_contracts"
    / "artifacts"
    / "constant_product_pool"
    / "constant_product_pool_client.py"
)
CHAPTER7_CLIENT = (
    PROJECT_ROOT
    / "smart_contracts"
    / "artifacts"
    / "lp_farming"
    / "lp_farm_client.py"
)


def get_localnet_algorand() -> AlgorandClient:
    algorand = AlgorandClient.default_localnet()
    try:
        algorand.client.algod.status()
    except Exception as exc:  # pragma: no cover - depends on local Docker/Podman.
        raise RuntimeError(
            "LocalNet is not reachable. Start it with `algokit localnet start`."
        ) from exc
    return algorand


def load_generated_client(path: Path, module_name: str) -> ModuleType:
    if not path.exists():
        raise RuntimeError(
            f"Build artifact missing: {path}\n"
            "Run `algokit project run build` in the matching project first."
        )
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load generated client at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_amm_client() -> ModuleType:
    return load_generated_client(CHAPTER5_CLIENT, "chapter5_amm_client")


def load_farm_client() -> ModuleType:
    return load_generated_client(CHAPTER7_CLIENT, "chapter7_farm_client")


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


def stake_box_reference(address: str) -> bytes:
    return b"s_" + decode_address(address)


def set_timestamp_offset(algorand: AlgorandClient, offset_seconds: int) -> None:
    algod = algorand.client.algod
    if hasattr(algod, "set_timestamp_offset"):
        algod.set_timestamp_offset(offset_seconds)
        return

    address = getattr(algod, "algod_address", None)
    headers = dict(getattr(algod, "headers", {}) or {})
    token = getattr(algod, "algod_token", None)
    if token and "X-Algo-API-Token" not in headers:
        headers["X-Algo-API-Token"] = token
    if not address:
        raise RuntimeError("Could not find algod address for timestamp offset")

    url = f"{address}/v2/devmode/blocks/offset/{offset_seconds}"
    request = urllib.request.Request(url, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status >= 400:
            raise RuntimeError(f"Timestamp offset failed: HTTP {response.status}")


def advance_localnet_time(
    algorand: AlgorandClient,
    sender: SigningAccount,
    *,
    offset_seconds: int,
) -> None:
    set_timestamp_offset(algorand, offset_seconds)
    time.sleep(1)
    algorand.send.payment(
        PaymentParams(
            sender=sender.address,
            signer=sender.signer,
            receiver=sender.address,
            amount=AlgoAmount.from_micro_algo(0),
            note=os.urandom(8),
        )
    )


def reset_localnet_time(
    algorand: AlgorandClient,
    sender: SigningAccount,
) -> None:
    try:
        set_timestamp_offset(algorand, 0)
        algorand.send.payment(
            PaymentParams(
                sender=sender.address,
                signer=sender.signer,
                receiver=sender.address,
                amount=AlgoAmount.from_micro_algo(0),
                note=os.urandom(8),
            )
        )
    except Exception:
        pass
