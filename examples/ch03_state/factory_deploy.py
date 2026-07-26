"""Redeploy a registry whose declared state schema no longer matches the code."""

from algokit_utils import AlgorandClient, OnSchemaBreak, OnUpdate

from smart_contracts.artifacts.registry.registry_client import RegistryFactory


def main() -> int:
    algorand = AlgorandClient.from_environment()
    deployer = algorand.account.from_environment("DEPLOYER")
    factory = algorand.client.get_typed_app_factory(
        RegistryFactory, default_sender=deployer.address
    )
    client, result = factory.deploy(
        on_schema_break=OnSchemaBreak.ReplaceApp,
        on_update=OnUpdate.UpdateApp,
    )
    print(f"registry {client.app_id}: {result.operation_performed}")
    return client.app_id


if __name__ == "__main__":
    main()
