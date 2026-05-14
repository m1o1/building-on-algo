from __future__ import annotations

import pytest
from algokit_utils import AlgoAmount, CommonAppCallParams

from scripts.localnet_helpers import (
    MICRO_UNITS,
    asset_transfer_arg,
    create_test_asset,
    fund_account,
    opt_account_into_asset,
    payment_arg,
    quote_swap,
    transfer_asset,
)


pytestmark = pytest.mark.localnet


def deploy_bootstrapped_pool(algorand):
    from smart_contracts.artifacts.constant_product_pool import (
        constant_product_pool_client as amm_client,
    )

    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    trader = algorand.account.random()
    fund_account(algorand, dispenser, admin)
    fund_account(algorand, dispenser, trader)

    token_a = create_test_asset(algorand, admin, name="Token A", unit="TKNA")
    token_b = create_test_asset(algorand, admin, name="Token B", unit="TKNB")
    if token_a > token_b:
        token_a, token_b = token_b, token_a

    factory = amm_client.ConstantProductPoolFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    pool, _ = factory.send.create.bare()
    result = pool.send.bootstrap(
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
    lp_token = result.abi_return
    assert lp_token is not None
    for account in (admin, trader):
        for asset_id in (token_a, token_b, lp_token):
            opt_account_into_asset(algorand, account, asset_id)
    return pool, admin, trader, token_a, token_b, lp_token


def add_initial_liquidity(algorand, pool, admin, token_a, token_b, lp_token):
    from smart_contracts.artifacts.constant_product_pool import (
        constant_product_pool_client as amm_client,
    )

    amount_a = 10_000 * MICRO_UNITS
    amount_b = 10_000 * MICRO_UNITS
    result = pool.send.add_initial_liquidity(
        amm_client.AddInitialLiquidityArgs(
            deposit_a=asset_transfer_arg(
                algorand, admin, pool.app_address, token_a, amount_a
            ),
            deposit_b=asset_transfer_arg(
                algorand, admin, pool.app_address, token_b, amount_b
            ),
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[token_a, token_b, lp_token],
        ),
    )
    assert result.abi_return is not None
    return amount_a, amount_b, result.abi_return


def test_full_amm_workflow(algorand) -> None:
    from smart_contracts.artifacts.constant_product_pool import (
        constant_product_pool_client as amm_client,
    )

    pool, admin, trader, token_a, token_b, lp_token = deploy_bootstrapped_pool(
        algorand
    )
    reserve_a, reserve_b, _ = add_initial_liquidity(
        algorand, pool, admin, token_a, token_b, lp_token
    )

    transfer_asset(algorand, admin, trader, token_a, 1_000 * MICRO_UNITS)
    transfer_asset(algorand, admin, trader, token_b, 1_000 * MICRO_UNITS)
    swap_input = 100 * MICRO_UNITS
    expected_output = quote_swap(swap_input, reserve_a, reserve_b)
    swap = pool.send.swap(
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
    )
    assert swap.abi_return is not None
    assert swap.abi_return >= expected_output * 99 // 100

    add_more = pool.send.add_liquidity(
        amm_client.AddLiquidityArgs(
            deposit_a=asset_transfer_arg(
                algorand, trader, pool.app_address, token_a, 100 * MICRO_UNITS
            ),
            deposit_b=asset_transfer_arg(
                algorand, trader, pool.app_address, token_b, 100 * MICRO_UNITS
            ),
        ),
        params=CommonAppCallParams(
            sender=trader.address,
            signer=trader.signer,
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[token_a, token_b, lp_token],
        ),
    )
    minted_lp = add_more.abi_return
    assert minted_lp is not None
    assert minted_lp > 0

    remove = pool.send.remove_liquidity(
        amm_client.RemoveLiquidityArgs(
            lp_deposit=asset_transfer_arg(
                algorand, trader, pool.app_address, lp_token, minted_lp // 2
            ),
            min_a=1,
            min_b=1,
        ),
        params=CommonAppCallParams(
            sender=trader.address,
            signer=trader.signer,
            static_fee=AlgoAmount.from_micro_algo(3_000),
            asset_references=[token_a, token_b, lp_token],
        ),
    )
    assert remove.abi_return is not None
    assert remove.abi_return[0] > 0
    assert remove.abi_return[1] > 0


def test_swap_rejects_excessive_slippage(algorand) -> None:
    from smart_contracts.artifacts.constant_product_pool import (
        constant_product_pool_client as amm_client,
    )

    pool, admin, trader, token_a, token_b, lp_token = deploy_bootstrapped_pool(
        algorand
    )
    add_initial_liquidity(algorand, pool, admin, token_a, token_b, lp_token)
    transfer_asset(algorand, admin, trader, token_a, 1_000 * MICRO_UNITS)

    with pytest.raises(Exception, match="Slippage exceeded"):
        pool.send.swap(
            amm_client.SwapArgs(
                input_txn=asset_transfer_arg(
                    algorand, trader, pool.app_address, token_a, 100 * MICRO_UNITS
                ),
                min_output=10_000 * MICRO_UNITS,
            ),
            params=CommonAppCallParams(
                sender=trader.address,
                signer=trader.signer,
                static_fee=AlgoAmount.from_micro_algo(2_000),
                asset_references=[token_a, token_b],
            ),
        )


def test_swap_rejects_mismatched_sender(algorand) -> None:
    from smart_contracts.artifacts.constant_product_pool import (
        constant_product_pool_client as amm_client,
    )

    pool, admin, trader, token_a, token_b, lp_token = deploy_bootstrapped_pool(
        algorand
    )
    add_initial_liquidity(algorand, pool, admin, token_a, token_b, lp_token)
    transfer_asset(algorand, admin, trader, token_a, 1_000 * MICRO_UNITS)

    with pytest.raises(Exception, match="Input sender mismatch"):
        pool.send.swap(
            amm_client.SwapArgs(
                input_txn=asset_transfer_arg(
                    algorand, trader, pool.app_address, token_a, 100 * MICRO_UNITS
                ),
                min_output=1,
            ),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                static_fee=AlgoAmount.from_micro_algo(2_000),
                asset_references=[token_a, token_b],
            ),
        )


def test_swap_rejects_wrong_asset_and_wrong_receiver(algorand) -> None:
    from smart_contracts.artifacts.constant_product_pool import (
        constant_product_pool_client as amm_client,
    )

    pool, admin, trader, token_a, token_b, lp_token = deploy_bootstrapped_pool(
        algorand
    )
    _, _, minted_lp = add_initial_liquidity(
        algorand, pool, admin, token_a, token_b, lp_token
    )
    transfer_asset(algorand, admin, trader, lp_token, minted_lp // 10)

    with pytest.raises(Exception, match="Wrong input asset"):
        pool.send.swap(
            amm_client.SwapArgs(
                input_txn=asset_transfer_arg(
                    algorand, trader, pool.app_address, lp_token, minted_lp // 100
                ),
                min_output=1,
            ),
            params=CommonAppCallParams(
                sender=trader.address,
                signer=trader.signer,
                static_fee=AlgoAmount.from_micro_algo(2_000),
                asset_references=[token_a, token_b, lp_token],
            ),
        )

    transfer_asset(algorand, admin, trader, token_a, 1_000 * MICRO_UNITS)
    with pytest.raises(Exception):
        pool.send.swap(
            amm_client.SwapArgs(
                input_txn=asset_transfer_arg(
                    algorand, trader, trader.address, token_a, 100 * MICRO_UNITS
                ),
                min_output=1,
            ),
            params=CommonAppCallParams(
                sender=trader.address,
                signer=trader.signer,
                static_fee=AlgoAmount.from_micro_algo(2_000),
                asset_references=[token_a, token_b],
            ),
        )


def test_bootstrap_requires_asset_references_and_fee_pooling(algorand) -> None:
    from smart_contracts.artifacts.constant_product_pool import (
        constant_product_pool_client as amm_client,
    )

    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    fund_account(algorand, dispenser, admin)
    token_a = create_test_asset(algorand, admin, name="Token A", unit="TKNA")
    token_b = create_test_asset(algorand, admin, name="Token B", unit="TKNB")
    if token_a > token_b:
        token_a, token_b = token_b, token_a

    factory = amm_client.ConstantProductPoolFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    missing_refs_pool, _ = factory.send.create.bare()
    with pytest.raises(Exception):
        missing_refs_pool.send.bootstrap(
            amm_client.BootstrapArgs(
                seed_payment=payment_arg(
                    algorand, admin, missing_refs_pool.app_address, 500_000
                ),
                asset_a=token_a,
                asset_b=token_b,
            ),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                static_fee=AlgoAmount.from_micro_algo(4_000),
            ),
        )

    underfunded_pool, _ = factory.send.create.bare()
    with pytest.raises(Exception):
        underfunded_pool.send.bootstrap(
            amm_client.BootstrapArgs(
                seed_payment=payment_arg(
                    algorand, admin, underfunded_pool.app_address, 500_000
                ),
                asset_a=token_a,
                asset_b=token_b,
            ),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                static_fee=AlgoAmount.from_micro_algo(1_000),
                asset_references=[token_a, token_b],
            ),
        )
