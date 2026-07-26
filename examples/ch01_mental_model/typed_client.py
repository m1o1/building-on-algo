"""Create the greeter through the client `algokit generate client` wrote."""

from algokit_utils import AlgorandClient

from smart_contracts.artifacts.greeter.greeter_client import GreeterFactory


def main() -> int:
    algorand = AlgorandClient.from_environment()
    deployer = algorand.account.from_environment("DEPLOYER")
    factory = algorand.client.get_typed_app_factory(
        GreeterFactory, default_sender=deployer.address
    )
    client, _result = factory.send.create.bare()
    print(f"greeter {client.app_id} lives at {client.app_address}")
    return client.app_id


if __name__ == "__main__":
    main()
