"""Point at a network, and get an account that can pay for things."""

from algokit_utils import AlgoAmount, AlgorandClient


def main() -> str:
    algorand = AlgorandClient.from_environment()
    deployer = algorand.account.from_environment("DEPLOYER")
    algorand.account.ensure_funded_from_environment(
        account_to_fund=deployer.address,
        min_spending_balance=AlgoAmount.from_algo(10),
    )
    info = algorand.account.get_information(deployer.address)
    print(f"{deployer.address}\n  holds {info.amount}, {info.min_balance} locked")
    return deployer.address


if __name__ == "__main__":
    main()
