from __future__ import annotations

from algokit_utils import AlgoAmount, CommonAppCallParams

from scripts.localnet_helpers import (
    MICRO_UNITS,
    asset_transfer_arg,
    create_test_asset,
    fund_account,
    get_localnet_algorand,
    opt_account_into_asset,
    pair_box_reference,
    payment_arg,
    quote_swap,
    transfer_asset,
)

FACTORY_CREATE_SEED = 1_500_000


def main() -> int:
    try:
        algorand = get_localnet_algorand()
    except RuntimeError as exc:
        print(exc)
        return 1

    try:
        from smart_contracts.artifacts.amm_factory import amm_factory_client
        from smart_contracts.artifacts.factory_pool import factory_pool_client
    except ModuleNotFoundError:
        print("Build artifacts are missing. Run `algokit project run build` first.")
        return 1

    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    trader = algorand.account.random()
    second_lp = algorand.account.random()

    for account in (admin, trader, second_lp):
        fund_account(algorand, dispenser, account)

    token_a = create_test_asset(algorand, admin, name="Factory A", unit="FCTA")
    token_b = create_test_asset(algorand, admin, name="Factory B", unit="FCTB")
    if token_a > token_b:
        token_a, token_b = token_b, token_a
    pair_boxes = [
        pair_box_reference(b"p_", token_a, token_b),
        pair_box_reference(b"l_", token_a, token_b),
    ]
    print(f"Token A: {token_a}")
    print(f"Token B: {token_b}")

    factory_factory = amm_factory_client.AmmFactoryFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    factory, create_result = factory_factory.send.create.bare()
    print(f"Factory app ID: {factory.app_id}")
    print(f"Factory address: {factory.app_address}")
    print(f"Create tx: {create_result.tx_id}")

    created = factory.send.create_pool(
        amm_factory_client.CreatePoolArgs(
            seed_payment=payment_arg(
                algorand, admin, factory.app_address, FACTORY_CREATE_SEED
            ),
            asset_a=token_a,
            asset_b=token_b,
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(7_000),
            asset_references=[token_a, token_b],
            box_references=pair_boxes,
        ),
    )
    pool_id, lp_token = created.abi_return
    print(f"Factory-created pool: {pool_id}")
    print(f"LP token: {lp_token}")

    pool = factory_pool_client.FactoryPoolClient(
        algorand=algorand,
        app_id=pool_id,
        default_sender=admin.address,
        default_signer=admin.signer,
    )

    canonical = factory.send.verify_pool(
        amm_factory_client.VerifyPoolArgs(
            candidate_pool=pool_id,
            asset_a=token_a,
            asset_b=token_b,
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            app_references=[pool_id],
            asset_references=[token_a, token_b],
            box_references=[pair_boxes[0], pair_boxes[1]],
        ),
    ).abi_return
    assert canonical is True
    print("Factory verification accepted the registered pool.")

    for account in (admin, trader, second_lp):
        for asset_id in (token_a, token_b, lp_token):
            opt_account_into_asset(algorand, account, asset_id)

    initial_a = 10_000 * MICRO_UNITS
    initial_b = 10_000 * MICRO_UNITS
    initial_lp = pool.send.add_initial_liquidity(
        factory_pool_client.AddInitialLiquidityArgs(
            deposit_a=asset_transfer_arg(
                algorand, admin, pool.app_address, token_a, initial_a
            ),
            deposit_b=asset_transfer_arg(
                algorand, admin, pool.app_address, token_b, initial_b
            ),
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[token_a, token_b, lp_token],
        ),
    ).abi_return
    assert initial_lp is not None
    print(f"Initial LP minted: {initial_lp}")

    transfer_asset(algorand, admin, trader, token_a, 1_000 * MICRO_UNITS)
    transfer_asset(algorand, admin, trader, token_b, 1_000 * MICRO_UNITS)

    swap_input = 100 * MICRO_UNITS
    expected_output = quote_swap(swap_input, initial_a, initial_b)
    swap_output = pool.send.swap(
        factory_pool_client.SwapArgs(
            input_txn=asset_transfer_arg(
                algorand, trader, pool.app_address, token_a, swap_input
            ),
            min_output=expected_output * 99 // 100,
        ),
        params=CommonAppCallParams(
            sender=trader.address,
            signer=trader.signer,
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[token_a, token_b],
        ),
    ).abi_return
    assert swap_output is not None
    print(f"Swap output: {swap_output}")

    reserve_a_after_swap = initial_a + swap_input
    reserve_b_after_swap = initial_b - swap_output
    later_a = 1_000 * MICRO_UNITS
    later_b = later_a * reserve_b_after_swap // reserve_a_after_swap
    transfer_asset(algorand, admin, second_lp, token_a, later_a)
    transfer_asset(algorand, admin, second_lp, token_b, later_b)

    later_lp = pool.send.add_liquidity(
        factory_pool_client.AddLiquidityArgs(
            deposit_a=asset_transfer_arg(
                algorand, second_lp, pool.app_address, token_a, later_a
            ),
            deposit_b=asset_transfer_arg(
                algorand, second_lp, pool.app_address, token_b, later_b
            ),
        ),
        params=CommonAppCallParams(
            sender=second_lp.address,
            signer=second_lp.signer,
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[token_a, token_b, lp_token],
        ),
    ).abi_return
    assert later_lp is not None
    print(f"Later LP minted: {later_lp}")

    burn_lp = later_lp // 2
    removed_a, removed_b = pool.send.remove_liquidity(
        factory_pool_client.RemoveLiquidityArgs(
            lp_deposit=asset_transfer_arg(
                algorand, second_lp, pool.app_address, lp_token, burn_lp
            ),
            min_a=1,
            min_b=1,
        ),
        params=CommonAppCallParams(
            sender=second_lp.address,
            signer=second_lp.signer,
            static_fee=AlgoAmount.from_micro_algo(3_000),
            asset_references=[token_a, token_b, lp_token],
        ),
    ).abi_return
    assert removed_a > 0
    assert removed_b > 0
    print(f"Removed liquidity: {removed_a} asset A, {removed_b} asset B")

    duplicate_rejected = False
    try:
        factory.send.create_pool(
            amm_factory_client.CreatePoolArgs(
                seed_payment=payment_arg(
                    algorand, admin, factory.app_address, FACTORY_CREATE_SEED
                ),
                asset_a=token_a,
                asset_b=token_b,
            ),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                static_fee=AlgoAmount.from_micro_algo(7_000),
                asset_references=[token_a, token_b],
                box_references=pair_boxes,
            ),
        )
    except Exception:
        duplicate_rejected = True
    assert duplicate_rejected
    print("Duplicate pool creation was rejected.")

    fake_factory = factory_pool_client.FactoryPoolFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    fake_pool, _ = fake_factory.send.create.bare()
    fake_canonical = factory.send.verify_pool(
        amm_factory_client.VerifyPoolArgs(
            candidate_pool=fake_pool.app_id,
            asset_a=token_a,
            asset_b=token_b,
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            app_references=[fake_pool.app_id],
            asset_references=[token_a, token_b],
            box_references=[pair_boxes[0], pair_boxes[1]],
        ),
    ).abi_return
    assert fake_canonical is False
    print("A directly deployed fake pool was rejected.")
    print("Chapter 6 AMM factory workflow complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
