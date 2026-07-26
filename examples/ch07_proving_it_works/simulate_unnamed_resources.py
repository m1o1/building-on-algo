"""Ask the node which resources a call touched, and watch it execute."""

import sys
from pathlib import Path

from algokit_utils import (AlgorandClient, AppClient, AppClientMethodCallParams,
                           AppClientParams)
from algosdk.v2client.models import SimulateTraceConfig


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
    result = group.simulate(
        allow_unnamed_resources=True,
        exec_trace_config=SimulateTraceConfig(enable=True, stack_change=True),
    )
    txn_group = result.simulate_response["txn-groups"][0]
    # Discovery, not permission: the real call must still declare these.
    print(f"touched: {txn_group.get('unnamed-resources-accessed', {})}")
    trace = txn_group["txn-results"][0]["exec-trace"]["approval-program-trace"]
    print(f"{len(trace)} opcodes, last at pc={trace[-1]['pc']}")
    return len(trace)


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
