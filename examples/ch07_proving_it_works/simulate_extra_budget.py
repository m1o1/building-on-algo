"""Find out what a call really costs when 700 opcodes are not enough."""

import sys
from pathlib import Path

from algokit_utils import (AlgorandClient, AppClient, AppClientMethodCallParams,
                           AppClientParams)

PER_APP_CALL_BUDGET = 700


def main(app_id: int, spec_path: str) -> int:
    algorand = AlgorandClient.from_environment()
    client = AppClient(AppClientParams(
        app_spec=Path(spec_path).read_text(),
        algorand=algorand,
        app_id=app_id,
        default_sender=algorand.account.from_environment("DEPLOYER").address,
    ))
    group = algorand.new_group().add_app_call_method_call(
        client.params.call(AppClientMethodCallParams(method="sweep", args=[]))
    )
    # The extra budget exists only inside the simulation. It buys a
    # measurement, not a bigger program.
    result = group.simulate(extra_opcode_budget=20_000)

    consumed = result.simulate_response["txn-groups"][0]["app-budget-consumed"]
    needed = -(-consumed // PER_APP_CALL_BUDGET)
    print(f"sweep() burns {consumed} opcodes")
    print(f"pool {needed} app calls into the real group to afford it")
    return int(consumed)


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
