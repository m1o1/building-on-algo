# book-example: mode=script
"""Ask simulate for the fee a group must pay, then set it.

Do not hard-code a fee. Read minFee from suggested params and
group-usage from simulate. Heat: total = ceil(minFee * usage / 1e6).
"""

import sys
from pathlib import Path

from algokit_utils import (AlgoAmount, AlgorandClient, AppClient,
                           AppClientMethodCallParams, AppClientParams)

USAGE_SCALE = 1_000_000


def required_group_fee(min_fee: int, group_usage: int) -> int:
    """Convert simulate's group-usage into a pooled fee in microAlgo.

    group-usage is millionths of a min-fee, including every inner
    transaction. Round up once for the group, never per transaction.
    """
    return -(-min_fee * group_usage // USAGE_SCALE)


def main(app_id: int, spec_path: str) -> int:
    algorand = AlgorandClient.from_environment()
    beneficiary = algorand.account.from_environment("BENEFICIARY")
    client = AppClient(AppClientParams(
        app_spec=Path(spec_path).read_text(),
        algorand=algorand,
        app_id=app_id,
        default_sender=beneficiary.address,
    ))
    min_fee = algorand.client.algod.suggested_params().min_fee
    # Probe high enough that the group finishes. An underpaid
    # simulate stops early and underreports usage.
    probe = AlgoAmount.from_micro_algo(min_fee * 100)
    group = algorand.new_group().add_app_call_method_call(
        client.params.call(AppClientMethodCallParams(
            method="claim", args=[], static_fee=probe,
        ))
    )
    # Empty signers + allow-empty-signatures: algokit-utils already
    # enables this. The transactions still carry the signature *type*
    # that will be used once signed (Ed25519 here; a Falcon sender
    # needs a placeholder PQ envelope or usage is understated).
    result = group.simulate(allow_empty_signatures=True)
    usage = result.simulate_response["txn-groups"][0]["group-usage"]
    needed = required_group_fee(min_fee, usage)
    print(f"group-usage {usage}: pay {needed} microAlgo before signing")
    return needed


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
