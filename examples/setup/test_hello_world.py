"""The template contract, held to its one promise."""

from algokit_utils import AlgorandClient

from smart_contracts.artifacts.hello_world.hello_world_client import (
    HelloWorldFactory,
)


def test_hello_greets_by_name() -> None:
    algorand = AlgorandClient.default_localnet()
    deployer = algorand.account.from_environment("DEPLOYER")
    factory = algorand.client.get_typed_app_factory(
        HelloWorldFactory, default_sender=deployer.address
    )
    client, _ = factory.deploy()

    result = client.send.hello(args=("Ada",))

    assert result.abi_return == "Hello, Ada"
