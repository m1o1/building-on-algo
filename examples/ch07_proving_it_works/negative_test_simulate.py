"""Prove a rejection happens, and read the reason off the exception."""

import sys
from pathlib import Path

from algokit_utils import (AlgorandClient, AppClient, AppClientMethodCallParams,
                           AppClientParams)
from algokit_utils.errors import LogicError


def main(app_id: int, spec_path: str) -> str:
    algorand = AlgorandClient.from_environment()
    client = AppClient(AppClientParams(
        app_spec=Path(spec_path).read_text(),
        algorand=algorand,
        app_id=app_id,
        default_sender=algorand.account.random().address,
    ))
    group = algorand.new_group().add_app_call_method_call(
        client.params.call(AppClientMethodCallParams(method="claim", args=[]))
    )
    try:
        # `skip_signatures` lets an unfunded stranger stand in for a real
        # attacker: the node evaluates without checking any signature.
        group.simulate(skip_signatures=True)
    except LogicError as rejected:
        # A failing simulate raises. `.message` wraps your string in the
        # contract, app id and txn id, so match it, do not compare it.
        assert "not the beneficiary" in rejected.message, rejected.message
        return f"rejected at pc={rejected.pc}: {rejected.message}"
    raise AssertionError("a stranger claimed and the contract allowed it")


if __name__ == "__main__":
    print(main(int(sys.argv[1]), sys.argv[2]))
