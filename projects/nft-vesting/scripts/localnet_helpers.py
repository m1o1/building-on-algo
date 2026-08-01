from __future__ import annotations

import struct
import time
import os

from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    AssetCreateParams,
    AssetOptInParams,
    AssetTransferParams,
    PaymentParams,
)
from algokit_utils.models.account import SigningAccount


BOX_MBR = 26_100
NFT_MBR = 100_000
SCHEDULE_MBR = BOX_MBR + NFT_MBR


def get_localnet_algorand() -> AlgorandClient:
    algorand = AlgorandClient.default_localnet()
    try:
        algorand.client.algod.status()
    except Exception as exc:
        raise RuntimeError(
            "LocalNet is not reachable. Start it with `algokit localnet start`."
        ) from exc
    return algorand


def fund_account(
    algorand: AlgorandClient,
    account: SigningAccount,
    micro_algo: int = 10_000_000,
) -> None:
    dispenser = algorand.account.localnet_dispenser()
    algorand.send.payment(
        PaymentParams(
            sender=dispenser.address,
            receiver=account.address,
            amount=AlgoAmount.from_micro_algo(micro_algo),
        )
    )


def create_vesting_token(
    algorand: AlgorandClient,
    creator: SigningAccount,
    total: int = 10_000_000,
) -> int:
    result = algorand.send.asset_create(
        AssetCreateParams(
            sender=creator.address,
            total=total,
            asset_name="Chapter 12 Vesting Token",
            unit_name="C12VEST",
            decimals=0,
        )
    )
    return result.asset_id


def opt_account_into_asset(
    algorand: AlgorandClient,
    account: SigningAccount,
    asset_id: int,
) -> None:
    algorand.send.asset_opt_in(
        AssetOptInParams(sender=account.address, asset_id=asset_id)
    )


def transfer_asset(
    algorand: AlgorandClient,
    sender: SigningAccount,
    receiver: str,
    asset_id: int,
    amount: int,
) -> None:
    algorand.send.asset_transfer(
        AssetTransferParams(
            sender=sender.address,
            receiver=receiver,
            asset_id=asset_id,
            amount=amount,
        )
    )


def fund_app_account(
    algorand: AlgorandClient,
    sender: SigningAccount,
    app_address: str,
    micro_algo: int = 300_000,
) -> None:
    algorand.send.payment(
        PaymentParams(
            sender=sender.address,
            receiver=app_address,
            amount=AlgoAmount.from_micro_algo(micro_algo),
        )
    )


def latest_timestamp(algorand: AlgorandClient) -> int:
    """The timestamp every contract in the next block will read as `now`."""
    last_round = algorand.client.algod.status()["last-round"]
    return algorand.client.algod.block_info(last_round)["block"]["ts"]


def produce_block(algorand: AlgorandClient) -> None:
    dispenser = algorand.account.localnet_dispenser()
    algorand.send.payment(
        PaymentParams(
            sender=dispenser.address,
            receiver=dispenser.address,
            amount=AlgoAmount.from_micro_algo(0),
            # A random note keeps repeat calls from colliding as duplicate
            # transaction IDs; see the gotcha in Chapter 9.
            note=os.urandom(8),
        )
    )


def timestamp_offset(algorand: AlgorandClient) -> int:
    """Dev-mode adds this many seconds to each block. Zero means wall clock."""
    try:
        return int(algorand.client.algod.get_timestamp_offset()["offset"])
    except Exception:
        return 0


def advance_time(algorand: AlgorandClient, seconds: int) -> None:
    """Move the ledger clock forward by at least `seconds`.

    Block timestamps move only when blocks are produced, and how far each
    block moves depends on dev mode's timestamp offset: with no offset a
    block carries wall-clock time, so sleeping is what advances it; with an
    offset of N each block carries the previous timestamp plus N, so only
    blocks advance it. Checking the clock afterwards covers both, and keeps
    the suite honest when a LocalNet shared with other work has an offset set.
    """
    target = latest_timestamp(algorand) + seconds
    if timestamp_offset(algorand) == 0:
        time.sleep(seconds)
    for _ in range(seconds + 8):  # bounded, so a frozen clock fails instead
        if latest_timestamp(algorand) >= target:
            return
        produce_block(algorand)
    raise RuntimeError(
        "LocalNet's clock did not advance. A dev-mode timestamp offset of 0 "
        "freezes it, and only `algokit localnet reset` clears that."
    )


def schedule_box_key(schedule_id: int) -> bytes:
    return b"v_" + struct.pack(">Q", schedule_id)
