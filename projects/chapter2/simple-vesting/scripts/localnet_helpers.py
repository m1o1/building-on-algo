import os
import time
from collections.abc import Callable

import algokit_utils
from algosdk.atomic_transaction_composer import TransactionWithSigner

from smart_contracts.artifacts.simple_vesting.simple_vesting_client import (
    InitializeArgs,
    OptInToAssetArgs,
    SimpleVestingClient,
    SimpleVestingFactory,
)


def random_note() -> bytes:
    return os.urandom(8)


def require_localnet(algorand: algokit_utils.AlgorandClient) -> None:
    try:
        algorand.client.algod.status()
    except Exception as exc:  # pragma: no cover - depends on local Docker
        raise RuntimeError(
            "LocalNet is not reachable. Start it with `algokit localnet start` "
            "before running this workflow."
        ) from exc


def deploy(algorand: algokit_utils.AlgorandClient, admin) -> SimpleVestingClient:
    factory = algorand.client.get_typed_app_factory(
        SimpleVestingFactory,
        default_sender=admin.address,
    )
    app_client, _ = factory.send.create.bare(
        params=algokit_utils.CommonAppCallCreateParams(note=random_note())
    )
    return app_client


def create_test_asa(
    algorand: algokit_utils.AlgorandClient,
    creator,
    total: int = 10_000_000_000,
    decimals: int = 6,
) -> int:
    result = algorand.send.asset_create(
        algokit_utils.AssetCreateParams(
            sender=creator.address,
            total=total,
            decimals=decimals,
            default_frozen=False,
            asset_name="Chapter2 Test Token",
            unit_name="C2T",
            note=random_note(),
        )
    )
    return result.asset_id


def fund_account(
    algorand: algokit_utils.AlgorandClient,
    sender,
    receiver_address: str,
    amount: int = 500_000,
) -> None:
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=sender.address,
            receiver=receiver_address,
            amount=algokit_utils.AlgoAmount.from_micro_algo(amount),
            note=random_note(),
        )
    )


def advance_time(algorand: algokit_utils.AlgorandClient, seconds: int) -> None:
    time.sleep(seconds)
    dispenser = algorand.account.localnet_dispenser()
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=dispenser.address,
            receiver=dispenser.address,
            amount=algokit_utils.AlgoAmount.from_micro_algo(0),
            note=random_note(),
        )
    )


def opt_account_into_asset(
    algorand: algokit_utils.AlgorandClient,
    account,
    asset_id: int,
) -> None:
    algorand.send.asset_opt_in(
        algokit_utils.AssetOptInParams(
            sender=account.address,
            asset_id=asset_id,
            note=random_note(),
        )
    )


def initialize_contract(
    algorand: algokit_utils.AlgorandClient,
    app_client: SimpleVestingClient,
    admin,
    beneficiary,
    token_id: int,
    total: int,
    cliff: int,
    vesting: int,
) -> None:
    fund_account(algorand, admin, app_client.app_address, amount=300_000)
    app_client.send.opt_in_to_asset(
        OptInToAssetArgs(asset=token_id),
        params=algokit_utils.CommonAppCallParams(
            static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000),
            note=random_note(),
        ),
    )

    deposit_txn = algorand.create_transaction.asset_transfer(
        algokit_utils.AssetTransferParams(
            sender=admin.address,
            receiver=app_client.app_address,
            asset_id=token_id,
            amount=total,
            note=random_note(),
        )
    )
    deposit_arg = TransactionWithSigner(
        deposit_txn,
        algorand.account.get_signer(admin.address),
    )

    app_client.send.initialize(
        InitializeArgs(
            asset=token_id,
            beneficiary=beneficiary.address,
            total_amount=total,
            cliff_duration=cliff,
            vesting_duration=vesting,
            deposit_txn=deposit_arg,
        ),
        params=algokit_utils.CommonAppCallParams(note=random_note()),
    )


def setup_initialized_contract(
    algorand: algokit_utils.AlgorandClient,
    admin,
    cliff: int,
    vesting: int,
    total: int,
) -> tuple[SimpleVestingClient, int, object]:
    app_client = deploy(algorand, admin)
    token_id = create_test_asa(algorand, admin, total=max(total, 10_000_000_000))
    beneficiary = algorand.account.random()
    fund_account(algorand, admin, beneficiary.address)
    opt_account_into_asset(algorand, beneficiary, token_id)
    initialize_contract(
        algorand,
        app_client,
        admin,
        beneficiary,
        token_id,
        total,
        cliff,
        vesting,
    )
    return app_client, token_id, beneficiary


def failure_message(
    result: algokit_utils.SendAtomicTransactionComposerResults,
) -> str:
    txn_group = result.simulate_response["txn-groups"][0]  # type: ignore[index]
    return str(txn_group["failure-message"])


def localnet_client() -> tuple[algokit_utils.AlgorandClient, object]:
    algorand = algokit_utils.AlgorandClient.default_localnet()
    require_localnet(algorand)
    return algorand, algorand.account.localnet_dispenser()


def print_step(label: str, action: Callable[[], object]) -> object:
    print(label)
    result = action()
    if result is not None:
        print(f"  {result}")
    return result
