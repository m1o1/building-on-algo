from __future__ import annotations

from algokit_utils import AlgoAmount, CommonAppCallParams, PaymentParams

from scripts.localnet_helpers import (
    MICRO_UNITS,
    STAKE_BOX_MBR,
    advance_localnet_time,
    asset_transfer_arg,
    create_test_asset,
    fund_account,
    get_localnet_algorand,
    load_amm_client,
    load_farm_client,
    opt_account_into_asset,
    payment_arg,
    reset_localnet_time,
    stake_box_reference,
    transfer_asset,
)


def main() -> int:
    try:
        algorand = get_localnet_algorand()
        amm_client = load_amm_client()
        farm_client = load_farm_client()
    except RuntimeError as exc:
        print(exc)
        return 1

    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    farmer = algorand.account.random()
    fund_account(algorand, dispenser, admin)
    fund_account(algorand, dispenser, farmer)

    try:
        reset_localnet_time(algorand, admin)

        token_a = create_test_asset(algorand, admin, name="Token A", unit="TKNA")
        token_b = create_test_asset(algorand, admin, name="Token B", unit="TKNB")
        reward_token = create_test_asset(
            algorand, admin, name="Reward Token", unit="RWD"
        )
        if token_a > token_b:
            token_a, token_b = token_b, token_a
        print(f"Token A: {token_a}")
        print(f"Token B: {token_b}")
        print(f"Reward token: {reward_token}")

        amm_factory = amm_client.ConstantProductPoolFactory(
            algorand,
            default_sender=admin.address,
            default_signer=admin.signer,
        )
        pool, pool_create = amm_factory.send.create.bare()
        print(f"AMM app ID: {pool.app_id}")
        print(f"AMM create tx: {pool_create.tx_id}")

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

        for asset_id in (token_a, token_b, lp_token, reward_token):
            opt_account_into_asset(algorand, farmer, asset_id)
        opt_account_into_asset(algorand, admin, lp_token)

        initial_lp = pool.send.add_initial_liquidity(
            amm_client.AddInitialLiquidityArgs(
                deposit_a=asset_transfer_arg(
                    algorand,
                    admin,
                    pool.app_address,
                    token_a,
                    10_000 * MICRO_UNITS,
                ),
                deposit_b=asset_transfer_arg(
                    algorand,
                    admin,
                    pool.app_address,
                    token_b,
                    10_000 * MICRO_UNITS,
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

        lp_to_stake = initial_lp // 4
        transfer_asset(algorand, admin, farmer, lp_token, lp_to_stake)
        print(f"LP transferred to farmer: {lp_to_stake}")

        farm_factory = farm_client.LpFarmFactory(
            algorand,
            default_sender=admin.address,
            default_signer=admin.signer,
        )
        farm, farm_create = farm_factory.send.create.bare()
        print(f"Farm app ID: {farm.app_id}")
        print(f"Farm create tx: {farm_create.tx_id}")

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
        print("Farm initialized and bound to the AMM LP token.")

        reward_deposit = 58_400
        reward_duration = 100
        farm.send.deposit_rewards(
            farm_client.DepositRewardsArgs(
                reward_txn=asset_transfer_arg(
                    algorand,
                    admin,
                    farm.app_address,
                    reward_token,
                    reward_deposit,
                ),
                duration_seconds=reward_duration,
            ),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                static_fee=AlgoAmount.from_micro_algo(1_000),
                asset_references=[reward_token],
            ),
        )
        print(
            "Rewards deposited: "
            f"{reward_deposit} base units over {reward_duration} seconds."
        )

        farm.send.stake(
            farm_client.StakeArgs(
                mbr_payment=payment_arg(
                    algorand, farmer, farm.app_address, STAKE_BOX_MBR
                ),
                lp_txn=asset_transfer_arg(
                    algorand, farmer, farm.app_address, lp_token, lp_to_stake
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
        print("Farmer staked LP for 30 days.")

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
        claimed = claim.abi_return
        assert claimed is not None
        print(f"Claimed rewards after 10 dev-mode seconds: {claimed}")

        farm.send.extend_lock(
            farm_client.ExtendLockArgs(new_lock_days=365),
            params=CommonAppCallParams(
                sender=farmer.address,
                signer=farmer.signer,
                static_fee=AlgoAmount.from_micro_algo(1_000),
                box_references=[stake_box_reference(farmer.address)],
            ),
        )
        print("Farmer extended the lock to 365 days.")

        advance_localnet_time(algorand, admin, offset_seconds=366 * 86400)
        farm.send.unstake(
            params=CommonAppCallParams(
                sender=farmer.address,
                signer=farmer.signer,
                static_fee=AlgoAmount.from_micro_algo(4_000),
                asset_references=[lp_token, reward_token],
                box_references=[stake_box_reference(farmer.address)],
            )
        )
        print("Farmer unstaked LP and received the box MBR refund.")
        print("Chapter 7 LP farming workflow complete.")
        return 0
    finally:
        reset_localnet_time(algorand, admin)


if __name__ == "__main__":
    raise SystemExit(main())
