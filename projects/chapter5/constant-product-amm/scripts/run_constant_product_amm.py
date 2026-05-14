from __future__ import annotations

from algokit_utils import AlgoAmount, CommonAppCallParams

from scripts.localnet_helpers import (
    MICRO_UNITS,
    asset_transfer_arg,
    create_test_asset,
    fund_account,
    get_localnet_algorand,
    opt_account_into_asset,
    payment_arg,
    quote_swap,
    transfer_asset,
)


def main() -> int:
    try:
        algorand = get_localnet_algorand()
    except RuntimeError as exc:
        print(exc)
        return 1

    try:
        from smart_contracts.artifacts.constant_product_pool import (
            constant_product_pool_client as amm_client,
        )
    except ModuleNotFoundError:
        print("Build artifacts are missing. Run `algokit project run build` first.")
        return 1

    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    trader = algorand.account.random()
    second_lp = algorand.account.random()

    for account in (admin, trader, second_lp):
        fund_account(algorand, dispenser, account)

    token_a = create_test_asset(algorand, admin, name="Token A", unit="TKNA")
    token_b = create_test_asset(algorand, admin, name="Token B", unit="TKNB")
    if token_a > token_b:
        token_a, token_b = token_b, token_a
    print(f"Token A: {token_a}")
    print(f"Token B: {token_b}")

    factory = amm_client.ConstantProductPoolFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    pool, create_result = factory.send.create.bare()
    print(f"Pool app ID: {pool.app_id}")
    print(f"Pool address: {pool.app_address}")
    print(f"Create tx: {create_result.tx_id}")

    bootstrap = pool.send.bootstrap(
        amm_client.BootstrapArgs(
            seed_payment=payment_arg(algorand, admin, pool.app_address, 500_000),
            asset_a=token_a,
            asset_b=token_b,
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(4_000),
            asset_references=[token_a, token_b],
        ),
    )
    lp_token = bootstrap.abi_return
    assert lp_token is not None
    print(f"LP token: {lp_token}")

    for account in (admin, trader, second_lp):
        for asset_id in (token_a, token_b, lp_token):
            opt_account_into_asset(algorand, account, asset_id)

    initial_a = 10_000 * MICRO_UNITS
    initial_b = 10_000 * MICRO_UNITS
    initial_lp = pool.send.add_initial_liquidity(
        amm_client.AddInitialLiquidityArgs(
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
    transfer_asset(algorand, admin, second_lp, token_a, 2_000 * MICRO_UNITS)
    transfer_asset(algorand, admin, second_lp, token_b, 2_000 * MICRO_UNITS)

    swap_input = 100 * MICRO_UNITS
    expected_output = quote_swap(swap_input, initial_a, initial_b)
    swap_output = pool.send.swap(
        amm_client.SwapArgs(
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

    second_deposit_a = 1_000 * MICRO_UNITS
    second_deposit_b = 1_000 * MICRO_UNITS
    second_lp_minted = pool.send.add_liquidity(
        amm_client.AddLiquidityArgs(
            deposit_a=asset_transfer_arg(
                algorand, second_lp, pool.app_address, token_a, second_deposit_a
            ),
            deposit_b=asset_transfer_arg(
                algorand, second_lp, pool.app_address, token_b, second_deposit_b
            ),
        ),
        params=CommonAppCallParams(
            sender=second_lp.address,
            signer=second_lp.signer,
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[token_a, token_b, lp_token],
        ),
    ).abi_return
    assert second_lp_minted is not None
    print(f"Second LP minted: {second_lp_minted}")

    lp_to_remove = second_lp_minted // 2
    withdrawn = pool.send.remove_liquidity(
        amm_client.RemoveLiquidityArgs(
            lp_deposit=asset_transfer_arg(
                algorand, second_lp, pool.app_address, lp_token, lp_to_remove
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
    assert withdrawn is not None
    print(f"Removed LP: {lp_to_remove}")
    print(f"Withdrawn A: {withdrawn[0]}")
    print(f"Withdrawn B: {withdrawn[1]}")
    print("Chapter 5 AMM workflow complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
