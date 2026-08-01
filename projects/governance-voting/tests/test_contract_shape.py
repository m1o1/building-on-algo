"""Source-level and app-spec checks that need neither LocalNet nor Go.

Two kinds of check live here. The source-level ones assert the security
properties the chapter argues for, at the one place nothing else looks: the
contract text. A property that holds only because the current test happens to
exercise it is a property one refactor away from gone.

The app-spec ones assert the compiled ARC-56 shape --- every method signature,
the global schema, and the box-map prefixes. That is the surface everything
off-chain is written against: the typed clients, the box references the scripts
build by hand, and the argument layout the proof group depends on. A renamed
method or a reordered argument is a breaking change that no source-shape test
notices, because the source still says what it always said.
"""

import ast
import json
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VOTING = PROJECT_ROOT / "smart_contracts" / "governance_voting" / "contract.py"
ANCHOR = PROJECT_ROOT / "smart_contracts" / "verifier_anchor" / "contract.py"
HELPER = PROJECT_ROOT / "smart_contracts" / "commitment_helper" / "contract.py"
VERIFIER_SOURCE = PROJECT_ROOT / "zk" / "generated" / "VoteVerifier.py"
ARTIFACTS = PROJECT_ROOT / "smart_contracts" / "artifacts"


@pytest.mark.parametrize("path", [VOTING, ANCHOR, HELPER], ids=lambda p: p.parent.name)
def test_every_assert_carries_a_message(path: Path) -> None:
    """A bare assert hands an integrator a program counter and nothing else.

    The reader of a refusal is rarely the author of the contract: it is whoever
    wired a client to it at two in the morning. This is the one property that
    cannot be tested from outside --- a bare assert fails exactly like a
    messaged one --- so it is asserted against the source.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    bare = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Assert) and node.msg is None
    ]

    assert bare == [], f"{path.name} has asserts with no message at lines {bare}"


def test_lifecycle_is_immutable() -> None:
    source = VOTING.read_text(encoding="utf-8")

    assert 'allow_actions=["UpdateApplication", "DeleteApplication"]' in source
    assert 'assert False, "Contract is immutable"' in source


def test_phase_transitions_are_admin_only_and_check_rounds() -> None:
    source = VOTING.read_text(encoding="utf-8")

    for method in ("advance_to_prove_phase", "advance_to_reveal_phase", "set_verifier"):
        body = _method_body(source, method)
        assert "Global.creator_address" in body, f"{method} has no admin check"

    assert (
        "assert Global.round > self.commit_end_round.value"
        in _method_body(source, "advance_to_prove_phase")
    )
    assert (
        "assert Global.round > self.prove_end_round.value"
        in _method_body(source, "advance_to_reveal_phase")
    )


def test_initialize_runs_once() -> None:
    body = _method_body(VOTING.read_text(encoding="utf-8"), "initialize")

    assert "assert self.phase.value == UInt64(0)" in body
    assert "assert Txn.sender == Global.creator_address" in body


def test_commit_vote_is_paid_for_and_single_use() -> None:
    body = _method_body(VOTING.read_text(encoding="utf-8"), "commit_vote")

    assert "assert sender not in self.commitments" in body
    assert "mbr_payment.receiver == Global.current_application_address" in body
    # `==`, not `>=`: the contract is immutable and has no withdrawal path, so
    # an accepted overpayment is money nobody can ever move again.
    assert "mbr_payment.amount == box_cost" in body
    assert "commitment.length == UInt64(32)" in body


def test_bound_proof_pins_the_group_shape() -> None:
    body = _method_body(VOTING.read_text(encoding="utf-8"), "record_bound_proof")

    assert "Global.group_size == UInt64(PROOF_GROUP_SIZE)" in body
    assert "Txn.group_index == UInt64(PROOF_GROUP_SIZE - 1)" in body


def test_bound_proof_binds_public_inputs_to_state() -> None:
    body = _method_body(VOTING.read_text(encoding="utf-8"), "record_bound_proof")

    # The verifier is identified, not assumed.
    assert "verifier_txn.sender.bytes == self.verifier_address.value" in body
    assert "verifier_txn.app_id.id == self.verifier_app.value" in body

    # A rekeyed verifier account no longer runs the program, and the
    # transaction's own rekey_to field cannot say so.
    assert "op.AcctParamsGet.acct_auth_addr" in body
    assert "auth_addr == Global.zero_address" in body

    # Both public inputs are compared against this contract's own state.
    assert "public_inputs[2:34] == self.commitments[voter]" in body
    assert "public_inputs[34:66] == expected_choices" in body


def test_bound_proof_does_not_assert_rekey_on_other_transactions() -> None:
    """The app must not police fields that belong to the LogicSig.

    Asserting `rekey_to` on somebody else's transaction restricts a wallet
    without protecting this contract, and it reads as a defence against the
    already-rekeyed case that it does not defend against. The chapter's own
    argument puts that check in the verifier LogicSig instead.
    """
    body = _method_body(VOTING.read_text(encoding="utf-8"), "record_bound_proof")

    offenders = [
        line.strip()
        for line in body.splitlines()
        if line.strip().startswith("assert") and "rekey_to" in line
    ]
    assert offenders == [], f"rekey_to asserted on a foreign transaction: {offenders}"


def test_reveal_raises_budget_before_hashing() -> None:
    body = _method_body(VOTING.read_text(encoding="utf-8"), "reveal_vote")

    ensure = body.index("ensure_budget(")
    hashing = body.index("op.mimc(")
    assert ensure < hashing, "the budget must be raised before mimc runs"
    assert "OpUpFeeSource.GroupCredit" in body
    assert "self.proof_status[sender] == UInt64(1)" in body


def test_reveal_marks_the_vote_spent() -> None:
    body = _method_body(VOTING.read_text(encoding="utf-8"), "reveal_vote")

    # proof_status moves 1 -> 2, and the guard above only admits 1, so a second
    # reveal by the same voter cannot pass.
    assert "self.proof_status[sender] = UInt64(2)" in body


def test_anchor_app_claims_no_authority() -> None:
    source = ANCHOR.read_text(encoding="utf-8")

    assert "return arc4.Bool(True)" in source
    assert "record_bound_proof" in source, "the anchor should name its real reader"


def test_generated_verifier_reads_the_documented_arguments() -> None:
    if not VERIFIER_SOURCE.exists():
        pytest.skip(f"{VERIFIER_SOURCE.name} not generated; see the README")

    source = VERIFIER_SOURCE.read_text(encoding="utf-8")

    # The chapter states which application arguments carry what. If AlgoPlonk
    # ever moves them, record_bound_proof's slices are reading the wrong bytes
    # and every other test in this suite would still pass.
    assert "proof = py.Txn.application_args(1)[2:]" in source
    assert "public_inputs = py.Txn.application_args(2)[2:]" in source
    assert "ec.pairing_check(EC.BN254g1" in source


# ---------------------------------------------------------------------------
# The compiled ARC-56 shape.
# ---------------------------------------------------------------------------


def app_spec(folder: str, name: str) -> dict:
    path = ARTIFACTS / folder / f"{name}.arc56.json"
    if not path.exists():
        pytest.skip(f"{path.name} not built; run `algokit project run build`")
    return json.loads(path.read_text(encoding="utf-8"))


def signatures(spec: dict) -> set[str]:
    """The ARC-4 signature of every method, exactly as a caller must send it."""
    return {
        f"{m['name']}({','.join(a['type'] for a in m['args'])}){m['returns']['type']}"
        for m in spec["methods"]
    }


def test_governance_abi_is_the_documented_one() -> None:
    assert signatures(app_spec("governance_voting", "GovernanceVoting")) == {
        "initialize(uint64,uint64,uint64)void",
        "set_verifier(address,uint64)void",
        "commit_vote(byte[],pay)void",
        "advance_to_prove_phase()void",
        "record_verified_proof(address)void",
        "record_bound_proof(address)void",
        "advance_to_reveal_phase()void",
        "reveal_vote(uint64,byte[])void",
        "get_tally(uint64)uint64",
    }


def test_governance_state_schema_is_the_documented_one() -> None:
    spec = app_spec("governance_voting", "GovernanceVoting")

    # Seven uint64s and two byte slices. The schema is fixed at creation, so
    # this is also the check that says a new global would need a new app.
    assert spec["state"]["schema"]["global"] == {"ints": 7, "bytes": 2}
    assert spec["state"]["schema"]["local"] == {"ints": 0, "bytes": 0}
    assert set(spec["state"]["keys"]["global"]) == {
        "admin",
        "num_choices",
        "commit_end_round",
        "prove_end_round",
        "phase",
        "total_votes",
        "verified_proofs",
        "verifier_address",
        "verifier_app",
    }


def test_box_prefixes_match_the_ones_clients_build_by_hand() -> None:
    """`c_`, `p_` and `t_`, base64-encoded in the app spec.

    Every box reference in scripts/localnet_helpers.py is assembled from these
    two-byte prefixes. Change a prefix in the contract and the references stop
    naming anything, which the AVM reports as `invalid Box reference` rather
    than as a mismatch.
    """
    boxes = app_spec("governance_voting", "GovernanceVoting")["state"]["maps"]["box"]

    assert boxes["commitments"]["prefix"] == "Y18="  # b"c_"
    assert boxes["commitments"]["keyType"] == "address"
    assert boxes["proof_status"]["prefix"] == "cF8="  # b"p_"
    assert boxes["proof_status"]["valueType"] == "uint64"
    assert boxes["tallies"]["prefix"] == "dF8="  # b"t_"
    assert boxes["tallies"]["keyType"] == "uint64"


def test_update_and_delete_route_to_the_rejecting_bare_method() -> None:
    bare = app_spec("governance_voting", "GovernanceVoting")["bareActions"]

    assert bare["create"] == ["NoOp"]
    assert sorted(bare["call"]) == ["DeleteApplication", "UpdateApplication"]


def test_get_tally_is_readonly() -> None:
    methods = app_spec("governance_voting", "GovernanceVoting")["methods"]
    by_name = {m["name"]: m for m in methods}

    assert by_name["get_tally"]["readonly"] is True
    # Nothing that writes state may claim to be readonly: a client would
    # simulate it and never send it.
    assert [m["name"] for m in methods if m.get("readonly")] == ["get_tally"]


def test_anchor_and_helper_abi_are_the_documented_ones() -> None:
    # The anchor's two arguments are what the verifier LogicSig reads out of
    # application_args 1 and 2, and what record_bound_proof slices.
    assert signatures(app_spec("verifier_anchor", "VerifierAnchor")) == {
        "verify(byte[32][],byte[32][])bool"
    }
    assert signatures(app_spec("commitment_helper", "CommitmentHelper")) == {
        "commit(uint64,byte[])byte[]"
    }

    helper = app_spec("commitment_helper", "CommitmentHelper")["methods"][0]
    assert helper["readonly"] is True, "the helper is simulated, never submitted"


def _method_body(source: str, name: str) -> str:
    """Return one method's text, from its `def` to the next one."""
    start = source.index(f"    def {name}(")
    rest = source[start + 1 :]
    end = rest.find("\n    @arc4.")
    return rest if end == -1 else rest[:end]
