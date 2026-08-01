"""Source- and spec-level checks that run without a chain.

Most of the lottery's security is a refusal, and `test_lottery.py` proves
those by submitting the transaction and reading the error. A few properties
have no refusal to point at, because getting them wrong produces a contract
that works: an inner fee that is not zero drains the application account
slowly, a `draw` that took an argument would look exactly like this one, and
a `readonly` flag on a method that moves money would be honoured by every
client. Those get read out of the source and the compiled spec instead.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

LOTTERY = Path("smart_contracts/lottery/contract.py")
BEACON = Path("smart_contracts/beacon_stub/contract.py")
SPEC = Path("smart_contracts/artifacts/lottery/Lottery.arc56.json")


def read_lottery() -> str:
    return LOTTERY.read_text(encoding="utf-8")


def load_spec() -> dict:
    assert SPEC.exists(), "run `algokit project run build` first"
    return json.loads(SPEC.read_text(encoding="utf-8"))


def method_body(source: str, name: str) -> str:
    start = source.index(f"    def {name}(")
    rest = source[start + 1 :]
    end = rest.find("\n    @arc4.")
    return rest if end == -1 else rest[:end]


# ---------------------------- inner transactions ------------------------- #


def test_every_inner_payment_sets_a_zero_fee() -> None:
    source = read_lottery()
    payments = re.findall(r"itxn\.Payment\((.*?)\)\.submit\(\)", source, re.S)
    assert len(payments) == 3, f"expected three inner payments, saw {len(payments)}"
    for body in payments:
        assert "fee=UInt64(0)" in body, body


def test_the_inner_application_call_sets_a_zero_fee_too() -> None:
    """`arc4.abi_call` is the fourth inner transaction, and it is easy to miss.

    `fee` defaults to 0 on the ABI call path as it does on the `itxn`
    builders, so omitting it compiles to the same TEAL. Writing it is
    documentation; asserting it here is what stops somebody typing a number.
    """
    source = read_lottery()
    calls = re.findall(r"arc4\.abi_call\[[^\]]*\]\((.*?)\n        \)", source, re.S)
    assert len(calls) == 1, f"expected one inner app call, saw {len(calls)}"
    assert "fee=0" in calls[0], calls[0]


def test_payment_is_the_only_itxn_builder_used() -> None:
    """Four inner transactions: three payments and the beacon call."""
    source = read_lottery()
    assert source.count("itxn.") == 3
    assert source.count("arc4.abi_call") == 1
    assert "itxn.AssetTransfer" not in source
    assert "itxn.ApplicationCall" not in source


# ------------------------------ box lifecycle ---------------------------- #


def test_both_exit_paths_delete_the_entry_they_pay() -> None:
    """A payment with no delete beside it can be made a second time.

    Deleting the box is the whole double-claim guard: the next call fails on
    `key in self.entrants` because there is no key. The two lines have to be
    in the same method, unconditionally, on both exits.
    """
    source = read_lottery()
    assert source.count("del self.entrants[key]") == 2
    for name in ("sweep", "refund"):
        body = method_body(source, name)
        assert "del self.entrants[key]" in body, name
        assert "itxn.Payment(" in body, name
        assert 'assert key in self.entrants, "no such entry"' in body, name


# ------------------------------ authorization ---------------------------- #


def test_only_the_creator_can_initialise_or_commit() -> None:
    source = read_lottery()
    for name in ("initialize", "commit"):
        body = method_body(source, name)
        assert 'assert Txn.sender == Global.creator_address, "operator only"' in body


def test_the_lifecycle_is_closed() -> None:
    source = read_lottery()
    assert 'allow_actions=["UpdateApplication", "DeleteApplication"]' in source
    assert 'assert False, "the lottery is immutable"' in source


# ---------------------------- the compiled spec -------------------------- #


def test_draw_takes_no_arguments() -> None:
    """A caller chooses when to draw and nothing else."""
    spec = load_spec()
    draw = next(m for m in spec["methods"] if m["name"] == "draw")
    assert draw["args"] == [], draw["args"]


def test_the_global_schema_is_what_the_mbr_arithmetic_assumes() -> None:
    from scripts.localnet_helpers import (
        LOTTERY_GLOBAL_BYTES,
        LOTTERY_GLOBAL_UINTS,
    )

    schema = load_spec()["state"]["schema"]["global"]
    assert schema["ints"] == LOTTERY_GLOBAL_UINTS, schema
    assert schema["bytes"] == LOTTERY_GLOBAL_BYTES, schema


def test_no_method_is_marked_readonly() -> None:
    """Every method here writes state or sends money. None may be simulated."""
    for method in load_spec()["methods"]:
        assert not method.get("readonly"), method["name"]


def test_the_box_cost_matches_the_protocol_formula() -> None:
    from scripts.localnet_helpers import (
        ENTRY_BOX_COST,
        ENTRY_DATA_SIZE,
        ENTRY_KEY_SIZE,
    )

    assert ENTRY_KEY_SIZE == 10
    assert ENTRY_DATA_SIZE == 32
    assert ENTRY_BOX_COST == 2_500 + 400 * (ENTRY_KEY_SIZE + ENTRY_DATA_SIZE)
    assert ENTRY_BOX_COST == 19_300


# --------------------------------- the stub ------------------------------ #


def test_the_stub_implements_both_mandatory_arc21_methods() -> None:
    source = BEACON.read_text(encoding="utf-8")
    assert "def get(self, rnd: UInt64, user_data: Bytes) -> Bytes:" in source
    assert "def must_get(self, rnd: UInt64, user_data: Bytes) -> Bytes:" in source


def test_the_lottery_calls_get_rather_than_must_get() -> None:
    source = read_lottery()
    assert '"get(uint64,byte[])byte[]"' in source
    # The comment above the call names `must_get` to say why it is not used,
    # so look for the signature a call would carry rather than the word.
    assert '"must_get(uint64,byte[])byte[]"' not in source
