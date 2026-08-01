from __future__ import annotations

import pytest
from algokit_utils import AlgoAmount, CommonAppCallParams

from scripts.localnet_helpers import (
    MICRO_UNITS,
    asset_transfer_arg,
    create_test_asset,
    fund_account,
    opt_account_into_asset,
    pair_box_reference,
    payment_arg,
    quote_swap,
    transfer_asset,
)

pytestmark = pytest.mark.localnet

FACTORY_CREATE_SEED = 1_500_000


def deploy_factory_and_pool(algorand):
    from smart_contracts.artifacts.amm_factory import amm_factory_client
    from smart_contracts.artifacts.factory_pool import factory_pool_client

    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    trader = algorand.account.random()
    second_lp = algorand.account.random()
    fund_account(algorand, dispenser, admin)
    fund_account(algorand, dispenser, trader)
    fund_account(algorand, dispenser, second_lp)

    token_a = create_test_asset(algorand, admin, name="Factory A", unit="FCTA")
    token_b = create_test_asset(algorand, admin, name="Factory B", unit="FCTB")
    if token_a > token_b:
        token_a, token_b = token_b, token_a
    pair_boxes = [
        pair_box_reference(b"p_", token_a, token_b),
        pair_box_reference(b"l_", token_a, token_b),
    ]

    factory_factory = amm_factory_client.AmmFactoryFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    factory, _ = factory_factory.send.create.bare()
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
    pool = factory_pool_client.FactoryPoolClient(
        algorand=algorand,
        app_id=pool_id,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    return (
        amm_factory_client,
        factory_pool_client,
        factory,
        pool,
        admin,
        trader,
        second_lp,
        token_a,
        token_b,
        lp_token,
        pair_boxes,
    )


def test_factory_creates_and_verifies_registered_pool(algorand) -> None:
    (
        amm_factory_client,
        _pool_client,
        factory,
        pool,
        admin,
        _trader,
        _second_lp,
        token_a,
        token_b,
        lp_token,
        pair_boxes,
    ) = deploy_factory_and_pool(algorand)

    assert lp_token > 0
    assert (
        factory.send.get_pool(
            amm_factory_client.GetPoolArgs(asset_a=token_a, asset_b=token_b),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                box_references=[pair_boxes[0]],
            ),
        ).abi_return
        == pool.app_id
    )

    assert (
        factory.send.verify_pool(
            amm_factory_client.VerifyPoolArgs(
                candidate_pool=pool.app_id,
                asset_a=token_a,
                asset_b=token_b,
            ),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                app_references=[pool.app_id],
                asset_references=[token_a, token_b],
                box_references=pair_boxes,
            ),
        ).abi_return
        is True
    )


def test_pool_supports_liquidity_and_swaps(algorand) -> None:
    (
        _factory_client,
        pool_client,
        _factory,
        pool,
        admin,
        trader,
        second_lp,
        token_a,
        token_b,
        lp_token,
        _pair_boxes,
    ) = deploy_factory_and_pool(algorand)

    for account in (admin, trader, second_lp):
        for asset_id in (token_a, token_b, lp_token):
            opt_account_into_asset(algorand, account, asset_id)

    amount_a = 10_000 * MICRO_UNITS
    amount_b = 10_000 * MICRO_UNITS
    minted = pool.send.add_initial_liquidity(
        pool_client.AddInitialLiquidityArgs(
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
    ).abi_return
    assert minted is not None

    transfer_asset(algorand, admin, trader, token_a, 1_000 * MICRO_UNITS)
    swap_input = 100 * MICRO_UNITS
    expected_output = quote_swap(swap_input, amount_a, amount_b)
    swap = pool.send.swap(
        pool_client.SwapArgs(
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

    reserve_a_after_swap = amount_a + swap_input
    reserve_b_after_swap = amount_b - swap.abi_return
    later_a = 1_000 * MICRO_UNITS
    later_b = later_a * reserve_b_after_swap // reserve_a_after_swap
    transfer_asset(algorand, admin, second_lp, token_a, later_a)
    transfer_asset(algorand, admin, second_lp, token_b, later_b)

    later_lp = pool.send.add_liquidity(
        pool_client.AddLiquidityArgs(
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
    assert later_lp > 0

    burn_lp = later_lp // 2
    removed = pool.send.remove_liquidity(
        pool_client.RemoveLiquidityArgs(
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
    assert removed is not None
    removed_a, removed_b = removed
    assert removed_a > 0
    assert removed_b > 0


def test_duplicate_and_fake_pool_are_rejected(algorand) -> None:
    (
        amm_factory_client,
        pool_client,
        factory,
        pool,
        admin,
        _trader,
        _second_lp,
        token_a,
        token_b,
        _lp_token,
        pair_boxes,
    ) = deploy_factory_and_pool(algorand)

    with pytest.raises(Exception, match="Pool already exists"):
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

    fake_factory = pool_client.FactoryPoolFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    fake_pool, _ = fake_factory.send.create.bare()

    assert (
        factory.send.verify_pool(
            amm_factory_client.VerifyPoolArgs(
                candidate_pool=fake_pool.app_id,
                asset_a=token_a,
                asset_b=token_b,
            ),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                app_references=[fake_pool.app_id, pool.app_id],
                asset_references=[token_a, token_b],
                box_references=pair_boxes,
            ),
        ).abi_return
        is False
    )
