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
    CommonAppCallCreateParams,
    PaymentParams,
    SigningAccount,
)


MICRO_UNITS = 1_000_000
STAKE_BOX_MBR = 32_100
PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
AMM_PROJECT = REPO_ROOT / "projects" / "constant-product-amm"
AMM_CLIENT = (
    AMM_PROJECT
    / "smart_contracts"
    / "artifacts"
    / "constant_product_pool"
    / "constant_product_pool_client.py"
)
FARM_CLIENT = (
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
    return load_generated_client(AMM_CLIENT, "amm_client")


def load_farm_client() -> ModuleType:
    return load_generated_client(FARM_CLIENT, "farm_client")


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
            # algokit-utils caches suggested params, so two asset creations
            # with the same fields inside the cache window would build the
            # same transaction ID and the second would be rejected as a
            # duplicate. The random note keeps every creation distinct.
            note=os.urandom(8),
        )
    )
    return result.asset_id


def distinct_create_params() -> CommonAppCallCreateParams:
    """App-create params carrying a random note.

    Two creations from the same sender and the same program build
    byte-identical transactions inside AlgoKit Utils' suggested-params cache
    window, and the ledger rejects the second as a duplicate. The note keeps
    each creation distinct.
    """
    return CommonAppCallCreateParams(note=os.urandom(8))


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


# The offset the clock rests at between jumps. It cannot be zero: a zero
# offset makes every new block reuse the previous block's timestamp, which
# freezes the ledger clock for good --- no REST call and no container
# restart takes it back, and `algokit localnet reset` is the only way home.
# One second per block is the smallest honest forward tick.
RESTING_OFFSET_SECONDS = 1


def normalize_localnet_time(algorand: AlgorandClient) -> None:
    """Park the developer-mode clock at one second per block.

    The offset is a standing per-block increment, so a test that jumps a
    year forward leaves every later block a year apart until something
    replaces the value. Calling this at the start of a test makes the clock
    a known quantity no matter what ran before it. It never sets zero,
    which would freeze the clock permanently.

    A node without the developer-mode endpoint keeps wall-clock time, which
    is already a sane starting state, so the failure is not fatal here.
    """
    try:
        set_timestamp_offset(algorand, RESTING_OFFSET_SECONDS)
    except Exception:  # pragma: no cover - node without the devmode endpoint.
        pass


def advance_localnet_time(
    algorand: AlgorandClient,
    sender: SigningAccount,
    *,
    offset_seconds: int,
) -> None:
    """Move the developer-mode ledger clock forward, and only forward.

    The offset endpoint sets a standing per-block increment, not a one-shot
    jump: every later block advances by it too, until a different value
    replaces it. So this seals one block at the requested jump and then
    parks the offset back at one second per block. Without that, a test
    that crossed 366 days would leave every later block --- in this suite
    and in any other project sharing the LocalNet --- 366 days apart.
    """
    if offset_seconds <= 0:
        raise ValueError(
            "advance_localnet_time only moves forward; "
            "an offset of zero freezes the LocalNet clock."
        )
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
    set_timestamp_offset(algorand, RESTING_OFFSET_SECONDS)
