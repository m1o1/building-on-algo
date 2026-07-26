"""One return value, three call paths, three different shapes."""

import sys
from pathlib import Path

from algokit_utils import (AlgorandClient, AppClient, AppClientMethodCallParams,
                           AppClientParams)


def main(app_id: int, spec_path: str, method: str) -> None:
    algorand = AlgorandClient.from_environment()
    client = AppClient(AppClientParams(
        app_spec=Path(spec_path).read_text(),
        algorand=algorand,
        app_id=app_id,
        default_sender=algorand.account.from_environment("DEPLOYER").address,
    ))
    call = AppClientMethodCallParams(method=method, args=[])
    params = client.params.call(call)

    # `AppClient.send` decodes for you: this is already a Python value.
    print("send.call:", client.send.call(call).abi_return)

    # `algorand.send.*` hands back the ABIReturn wrapper, or None.
    wrapped = algorand.send.app_call_method_call(params).abi_return
    print("app_call_method_call:", None if wrapped is None else wrapped.value)

    # A simulate has no `abi_return` at all. Index `returns` from the end:
    # it holds one entry per ABI method call, not per transaction.
    simulated = algorand.new_group().add_app_call_method_call(params).simulate()
    print("simulate:", simulated.returns[-1].value)


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2], sys.argv[3])
