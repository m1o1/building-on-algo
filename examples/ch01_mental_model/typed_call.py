"""Call a method through the typed client and read back what it returned."""

import sys

from algokit_utils import AlgorandClient

from smart_contracts.artifacts.greeter.greeter_client import GreeterClient


def main(app_id: int) -> str:
    algorand = AlgorandClient.from_environment()
    caller = algorand.account.from_environment("DEPLOYER")
    greeter = algorand.client.get_typed_app_client_by_id(
        GreeterClient, app_id=app_id, default_sender=caller.address
    )
    result = greeter.send.greet(args=("Ada",))
    print(f"{result.tx_ids[0][:8]} returned {result.abi_return!r}")
    return str(result.abi_return)


if __name__ == "__main__":
    main(int(sys.argv[1]))
