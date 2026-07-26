"""Run `claim` against real ledger state without committing it."""

import sys
from pathlib import Path

from algokit_utils import (AlgorandClient, AppClient, AppClientMethodCallParams,
                           AppClientParams)


def main(app_id: int, spec_path: str) -> int:
    algorand = AlgorandClient.from_environment()
    beneficiary = algorand.account.from_environment("BENEFICIARY")
    client = AppClient(AppClientParams(
        app_spec=Path(spec_path).read_text(),
        algorand=algorand,
        app_id=app_id,
        default_sender=beneficiary.address,
    ))
    group = algorand.new_group().add_app_call_method_call(
        client.params.call(AppClientMethodCallParams(method="claim", args=[]))
    )
    result = group.simulate()

    # `returns` holds one entry per ABI method call, not per transaction.
    would_return = result.returns[-1].value
    consumed = result.simulate_response["txn-groups"][0]["app-budget-consumed"]
    print(f"claim() would return {would_return}, using {consumed} opcodes")
    print(f"group {result.group_id} was evaluated and thrown away")
    return int(would_return)


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
