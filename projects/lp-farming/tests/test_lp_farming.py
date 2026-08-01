from __future__ import annotations

import pytest
from algokit_utils import AlgoAmount, CommonAppCallParams, PaymentParams

from scripts.localnet_helpers import (
    MICRO_UNITS,
    STAKE_BOX_MBR,
    advance_localnet_time,
    asset_transfer_arg,
    create_test_asset,
    distinct_create_params,
    fund_account,
    load_amm_client,
    load_farm_client,
    opt_account_into_asset,
    payment_arg,
    stake_box_reference,
    transfer_asset,
)


pytestmark = pytest.mark.localnet


def generated_clients():
    try:
        return load_amm_client(), load_farm_client()
    except RuntimeError as exc:
        pytest.skip(str(exc))


def bootstrap_pool(algorand, amm_client, admin, *farmers):
    token_a = create_test_asset(algorand, admin, name="Token A", unit="TKNA")
    token_b = create_test_asset(algorand, admin, name="Token B", unit="TKNB")
    reward_token = create_test_asset(algorand, admin, name="Reward", unit="RWD")
    if token_a > token_b:
        token_a, token_b = token_b, token_a

    factory = amm_client.ConstantProductPoolFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    # A test that bootstraps two pools creates them from the same admin and
    # the same program, so each create needs its own note to stay a distinct
    # transaction.
    pool, _ = factory.send.create.bare(params=distinct_create_params())
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

    opt_account_into_asset(algorand, admin, lp_token)
    for farmer in farmers:
        for asset_id in (token_a, token_b, lp_token, reward_token):
            opt_account_into_asset(algorand, farmer, asset_id)

    initial_lp = pool.send.add_initial_liquidity(
        amm_client.AddInitialLiquidityArgs(
            deposit_a=asset_transfer_arg(
                algorand, admin, pool.app_address, token_a, 10_000 * MICRO_UNITS
            ),
            deposit_b=asset_transfer_arg(
                algorand, admin, pool.app_address, token_b, 10_000 * MICRO_UNITS
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
    return pool, token_a, token_b, lp_token, reward_token, initial_lp


def deploy_initialized_farm(
    algorand, farm_client, admin, pool, lp_token, reward_token
):
    factory = farm_client.LpFarmFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    farm, _ = factory.send.create.create()
    algorand.send.payment(
        PaymentParams(
            sender=admin.address,
            signer=admin.signer,
            receiver=farm.app_address,
            amount=AlgoAmount.from_micro_algo(1_000_000),
        )
    )
    farm.send.initialize(
        farm_client.InitializeArgs(
            lp_token=lp_token,
            reward_token=reward_token,
            amm_app=pool.app_id,
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(3_000),
            asset_references=[lp_token, reward_token],
            app_references=[pool.app_id],
        ),
    )
    return farm


def stake_lp(algorand, farm_client, farm, farmer, lp_token, amount):
    farm.send.stake(
        farm_client.StakeArgs(
            mbr_payment=payment_arg(
                algorand, farmer, farm.app_address, STAKE_BOX_MBR
            ),
            lp_txn=asset_transfer_arg(
                algorand, farmer, farm.app_address, lp_token, amount
            ),
            lock_days=30,
        ),
        params=CommonAppCallParams(
            sender=farmer.address,
            signer=farmer.signer,
            static_fee=AlgoAmount.from_micro_algo(1_000),
            asset_references=[lp_token],
            box_references=[stake_box_reference(farmer.address)],
        ),
    )


def test_lifecycle_stake_claim_extend_unstake(algorand) -> None:
    amm_client, farm_client = generated_clients()
    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    farmer = algorand.account.random()
    fund_account(algorand, dispenser, admin)
    fund_account(algorand, dispenser, farmer)

    pool, _, _, lp_token, reward_token, initial_lp = bootstrap_pool(
        algorand, amm_client, admin, farmer
    )
    farm = deploy_initialized_farm(
        algorand, farm_client, admin, pool, lp_token, reward_token
    )

    farm.send.deposit_rewards(
        farm_client.DepositRewardsArgs(
            reward_txn=asset_transfer_arg(
                algorand, admin, farm.app_address, reward_token, 58_400
            ),
            duration_seconds=100,
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(1_000),
            asset_references=[reward_token],
        ),
    )

    stake_amount = initial_lp // 5
    transfer_asset(algorand, admin, farmer, lp_token, stake_amount)
    stake_lp(algorand, farm_client, farm, farmer, lp_token, stake_amount)

    with pytest.raises(Exception, match="Lock not expired"):
        farm.send.unstake(
            params=CommonAppCallParams(
                sender=farmer.address,
                signer=farmer.signer,
                static_fee=AlgoAmount.from_micro_algo(4_000),
                asset_references=[lp_token, reward_token],
                box_references=[stake_box_reference(farmer.address)],
            )
        )

    advance_localnet_time(algorand, admin, offset_seconds=10)
    claim = farm.send.claim(
        params=CommonAppCallParams(
            sender=farmer.address,
            signer=farmer.signer,
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[reward_token],
            box_references=[stake_box_reference(farmer.address)],
        )
    )
    assert claim.abi_return is not None
    assert claim.abi_return > 0

    farm.send.extend_lock(
        farm_client.ExtendLockArgs(new_lock_days=365),
        params=CommonAppCallParams(
            sender=farmer.address,
            signer=farmer.signer,
            static_fee=AlgoAmount.from_micro_algo(1_000),
            box_references=[stake_box_reference(farmer.address)],
        ),
    )

    advance_localnet_time(algorand, admin, offset_seconds=366 * 86400)
    before_unstake = algorand.client.algod.account_info(farmer.address)
    before_algo = before_unstake["amount"]
    farm.send.unstake(
        params=CommonAppCallParams(
            sender=farmer.address,
            signer=farmer.signer,
            static_fee=AlgoAmount.from_micro_algo(4_000),
            asset_references=[lp_token, reward_token],
            box_references=[stake_box_reference(farmer.address)],
        )
    )
    after_unstake = algorand.client.algod.account_info(farmer.address)
    assert after_unstake["amount"] >= before_algo + STAKE_BOX_MBR - 4_000
    with pytest.raises(Exception):
        algorand.client.algod.application_box_by_name(
            farm.app_id,
            stake_box_reference(farmer.address),
        )


def test_accumulator_two_stakers_keeps_early_rewards(algorand) -> None:
    amm_client, farm_client = generated_clients()
    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    alice = algorand.account.random()
    bob = algorand.account.random()
    fund_account(algorand, dispenser, admin)
    fund_account(algorand, dispenser, alice)
    fund_account(algorand, dispenser, bob)

    pool, _, _, lp_token, reward_token, initial_lp = bootstrap_pool(
        algorand, amm_client, admin, alice, bob
    )
    farm = deploy_initialized_farm(
        algorand, farm_client, admin, pool, lp_token, reward_token
    )

    farm.send.deposit_rewards(
        farm_client.DepositRewardsArgs(
            reward_txn=asset_transfer_arg(
                algorand, admin, farm.app_address, reward_token, 58_400
            ),
            duration_seconds=100,
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(1_000),
            asset_references=[reward_token],
        ),
    )

    alice_stake = initial_lp // 10
    bob_stake = initial_lp // 5
    transfer_asset(algorand, admin, alice, lp_token, alice_stake)
    transfer_asset(algorand, admin, bob, lp_token, bob_stake)

    stake_lp(algorand, farm_client, farm, alice, lp_token, alice_stake)
    advance_localnet_time(algorand, admin, offset_seconds=30)
    stake_lp(algorand, farm_client, farm, bob, lp_token, bob_stake)
    advance_localnet_time(algorand, admin, offset_seconds=200)

    alice_claim = farm.send.claim(
        params=CommonAppCallParams(
            sender=alice.address,
            signer=alice.signer,
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[reward_token],
            box_references=[stake_box_reference(alice.address)],
        )
    ).abi_return
    bob_claim = farm.send.claim(
        params=CommonAppCallParams(
            sender=bob.address,
            signer=bob.signer,
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[reward_token],
            box_references=[stake_box_reference(bob.address)],
        )
    ).abi_return

    assert alice_claim is not None
    assert bob_claim is not None
    assert alice_claim > bob_claim
    assert alice_claim + bob_claim <= 58_400


def test_initialize_rejects_wrong_amm(algorand) -> None:
    amm_client, farm_client = generated_clients()
    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    farmer = algorand.account.random()
    fund_account(algorand, dispenser, admin)
    fund_account(algorand, dispenser, farmer)

    pool_a, _, _, lp_token_a, reward_token, _ = bootstrap_pool(
        algorand, amm_client, admin, farmer
    )
    pool_b, _, _, _, _, _ = bootstrap_pool(algorand, amm_client, admin, farmer)

    factory = farm_client.LpFarmFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    farm, _ = factory.send.create.create()
    algorand.send.payment(
        PaymentParams(
            sender=admin.address,
            signer=admin.signer,
            receiver=farm.app_address,
            amount=AlgoAmount.from_micro_algo(1_000_000),
        )
    )

    with pytest.raises(Exception, match="LP token mismatch"):
        farm.send.initialize(
            farm_client.InitializeArgs(
                lp_token=lp_token_a,
                reward_token=reward_token,
                amm_app=pool_b.app_id,
            ),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                static_fee=AlgoAmount.from_micro_algo(3_000),
                asset_references=[lp_token_a, reward_token],
                app_references=[pool_a.app_id, pool_b.app_id],
            ),
        )


def test_stake_rejects_underfunded_mbr(algorand) -> None:
    amm_client, farm_client = generated_clients()
    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    farmer = algorand.account.random()
    fund_account(algorand, dispenser, admin)
    fund_account(algorand, dispenser, farmer)

    pool, _, _, lp_token, reward_token, initial_lp = bootstrap_pool(
        algorand, amm_client, admin, farmer
    )
    farm = deploy_initialized_farm(
        algorand, farm_client, admin, pool, lp_token, reward_token
    )
    stake_amount = initial_lp // 5
    transfer_asset(algorand, admin, farmer, lp_token, stake_amount)

    with pytest.raises(Exception, match="Wrong MBR payment"):
        farm.send.stake(
            farm_client.StakeArgs(
                mbr_payment=payment_arg(algorand, farmer, farm.app_address, 1),
                lp_txn=asset_transfer_arg(
                    algorand, farmer, farm.app_address, lp_token, stake_amount
                ),
                lock_days=30,
            ),
            params=CommonAppCallParams(
                sender=farmer.address,
                signer=farmer.signer,
                static_fee=AlgoAmount.from_micro_algo(1_000),
                asset_references=[lp_token],
                box_references=[stake_box_reference(farmer.address)],
            ),
        )


def test_stake_rejects_mbr_overpayment(algorand) -> None:
    amm_client, farm_client = generated_clients()
    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    farmer = algorand.account.random()
    fund_account(algorand, dispenser, admin)
    fund_account(algorand, dispenser, farmer)

    pool, _, _, lp_token, reward_token, initial_lp = bootstrap_pool(
        algorand, amm_client, admin, farmer
    )
    farm = deploy_initialized_farm(
        algorand, farm_client, admin, pool, lp_token, reward_token
    )
    stake_amount = initial_lp // 5
    transfer_asset(algorand, admin, farmer, lp_token, stake_amount)

    with pytest.raises(Exception, match="Wrong MBR payment"):
        farm.send.stake(
            farm_client.StakeArgs(
                mbr_payment=payment_arg(
                    algorand,
                    farmer,
                    farm.app_address,
                    STAKE_BOX_MBR + 1,
                ),
                lp_txn=asset_transfer_arg(
                    algorand, farmer, farm.app_address, lp_token, stake_amount
                ),
                lock_days=30,
            ),
            params=CommonAppCallParams(
                sender=farmer.address,
                signer=farmer.signer,
                static_fee=AlgoAmount.from_micro_algo(1_000),
                asset_references=[lp_token],
                box_references=[stake_box_reference(farmer.address)],
            ),
        )
