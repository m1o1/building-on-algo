import algokit_utils

from scripts.localnet_helpers import (
    advance_time,
    create_test_asa,
    deploy,
    fund_account,
    initialize_contract,
    localnet_client,
    opt_account_into_asset,
    print_step,
    random_note,
)


def main() -> None:
    algorand, admin = localnet_client()

    total = 1_000_000
    cliff = 3
    vesting = 8

    app_client = print_step(
        "1. Deploy SimpleVesting",
        lambda: deploy(algorand, admin),
    )
    print(f"   app id: {app_client.app_id}")
    print(f"   app address: {app_client.app_address}")

    token_id = print_step(
        "2. Create a test ASA",
        lambda: create_test_asa(algorand, admin, total=10_000_000_000),
    )
    print(f"   asset id: {token_id}")

    beneficiary = algorand.account.random()
    fund_account(algorand, admin, beneficiary.address)
    opt_account_into_asset(algorand, beneficiary, token_id)
    print(f"3. Funded beneficiary: {beneficiary.address}")

    print_step(
        "4. Fund, opt in, deposit, and initialize the vesting schedule",
        lambda: initialize_contract(
            algorand,
            app_client,
            admin,
            beneficiary,
            token_id,
            total,
            cliff,
            vesting,
        ),
    )

    before_cliff = app_client.send.claim(
        params=algokit_utils.CommonAppCallParams(
            sender=beneficiary.address,
            static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000),
            note=random_note(),
        )
    )
    print(f"5. Claim before cliff returned: {before_cliff.abi_return}")

    print("6. Advance past full vesting")
    advance_time(algorand, vesting + 1)

    final_claim = app_client.send.claim(
        params=algokit_utils.CommonAppCallParams(
            sender=beneficiary.address,
            static_fee=algokit_utils.AlgoAmount.from_micro_algo(2_000),
            note=random_note(),
        )
    )
    print(f"7. Final claim returned: {final_claim.abi_return}")

    holding = algorand.client.algod.account_asset_info(beneficiary.address, token_id)
    print(f"8. Beneficiary ASA balance: {holding['asset-holding']['amount']}")


if __name__ == "__main__":
    main()
