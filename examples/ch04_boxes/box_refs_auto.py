"""Let algokit-utils work out which boxes an app call needs to reference."""

import sys

from algokit_utils import AlgorandClient, SendParams

from smart_contracts.artifacts.league.league_client import LeagueClient


def main(app_id: int) -> int:
    algorand = AlgorandClient.from_environment()
    who = algorand.account.from_environment("DEPLOYER")
    app = LeagueClient(algorand=algorand, app_id=app_id, default_sender=who.address)
    params = SendParams(populate_app_call_resources=True)
    return int(app.send.record(args=(10,), send_params=params).abi_return)


if __name__ == "__main__":
    main(int(sys.argv[1]))
