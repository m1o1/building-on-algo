from __future__ import annotations

import time

from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    AssetCreateParams,
    AssetOptInParams,
    AssetTransferParams,
    PaymentParams,
)
from algokit_utils.models.account import SigningAccount
from algosdk.encoding import decode_address


BOX_MBR = 32_500


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
            asset_name="Chapter 3 Vesting Token",
            unit_name="C3VEST",
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


def advance_time(algorand: AlgorandClient, seconds: int) -> None:
    time.sleep(seconds)
    dispenser = algorand.account.localnet_dispenser()
    algorand.send.payment(
        PaymentParams(
            sender=dispenser.address,
            receiver=dispenser.address,
            amount=AlgoAmount.from_micro_algo(0),
        )
    )


def schedule_box_key(address: str) -> bytes:
    return b"v_" + decode_address(address)
