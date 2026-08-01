"""Find the deployed HelloWorld (deploying if needed) and call it."""

from algokit_utils import AlgorandClient

from smart_contracts.artifacts.hello_world.hello_world_client import (
    HelloWorldFactory,
)


def main() -> None:
    algorand = AlgorandClient.default_localnet()
    deployer = algorand.account.from_environment("DEPLOYER")
    factory = algorand.client.get_typed_app_factory(
        HelloWorldFactory, default_sender=deployer.address
    )
    client, _ = factory.deploy()
    print(f"hello_world {client.app_id} lives at {client.app_address}")

    result = client.send.hello(args=("Ada",))
    print(f"returned {result.abi_return!r}")


if __name__ == "__main__":
    main()
