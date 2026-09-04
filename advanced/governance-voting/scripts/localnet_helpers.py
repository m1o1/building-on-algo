"""LocalNet plumbing shared by the runbook and the tests.

Everything specific to this project lives here: where the generated ZK
artifacts are, how the AlgoPlonk verifier LogicSig is loaded and addressed, how
the proof and public inputs are encoded for the anchor app's ABI method, and
how the eight-transaction proof group is assembled.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import os
from pathlib import Path
from types import ModuleType

from algosdk import encoding, transaction
from algosdk.atomic_transaction_composer import LogicSigTransactionSigner
from algosdk.v2client.models import SimulateTraceConfig

from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    CommonAppCallParams,
    PaymentParams,
    SigningAccount,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATED = PROJECT_ROOT / "zk" / "generated"
ARTIFACTS = PROJECT_ROOT / "smart_contracts" / "artifacts"

VERIFIER_TEAL = GENERATED / "VoteVerifier.teal"
PROOF_FILE = GENERATED / "vote.proof"
PUBLIC_INPUTS_FILE = GENERATED / "vote.public_inputs"

VOTING_CLIENT = ARTIFACTS / "governance_voting" / "governance_voting_client.py"
ANCHOR_CLIENT = ARTIFACTS / "verifier_anchor" / "verifier_anchor_client.py"
HELPER_CLIENT = ARTIFACTS / "commitment_helper" / "commitment_helper_client.py"

# Box minimum balance, from 2,500 + 400 * (name_len + data_len). The commitment
# box is paid for by its own voter through commit_vote; the other two are paid
# by the application account, which is why the deployer has to fund it.
COMMITMENT_BOX_MBR = 2_500 + 400 * (34 + 32)  # 28,900
PROOF_STATUS_BOX_MBR = 2_500 + 400 * (34 + 8)  # 19,300
TALLY_BOX_MBR = 2_500 + 400 * (10 + 8)  # 9,700

# The base minimum balance of any account, which the application account owes
# before it holds a single box.
ACCOUNT_BASE_MBR = 100_000


def app_funding_for(num_choices: int, voters: int) -> int:
    """What the application account needs before initialize() is called.

    Written as a sum rather than a round number so a reader can see which box
    each term pays for. A method that creates a box the app account cannot
    cover aborts partway through, and the failure names a minimum balance
    rather than the box.
    """
    return (
        ACCOUNT_BASE_MBR
        + num_choices * TALLY_BOX_MBR
        + voters * PROOF_STATUS_BOX_MBR
    )

# The proof group: verifier call, six padding transactions, governance call.
# PROOF_GROUP_SIZE in smart_contracts/governance_voting/contract.py.
PROOF_GROUP_SIZE = 8

# What each transaction in a group contributes to the pooled LogicSig budget,
# since AVM v10, whether or not it carries a LogicSig. Eight of these is the
# whole reason the group is eight long.
LOGIC_SIG_BUDGET_PER_TXN = 20_000


class MissingArtifact(RuntimeError):
    """A build output or ZK artifact the caller needs is not on disk."""


def get_localnet_algorand() -> AlgorandClient:
    algorand = AlgorandClient.default_localnet()
    try:
        algorand.client.algod.status()
    except Exception as exc:  # pragma: no cover - depends on local Docker/Podman.
        raise RuntimeError(
            "LocalNet is not reachable. Start it with `algokit localnet start`."
        ) from exc
    return algorand


def load_generated_client(path: Path, module_name: str) -> ModuleType:
    if not path.exists():
        raise MissingArtifact(
            f"Build artifact missing: {path}\n"
            "Run `algokit project run build` in this project first."
        )
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise MissingArtifact(f"Could not load generated client at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_voting_client() -> ModuleType:
    return load_generated_client(VOTING_CLIENT, "zk_voting_client")


def load_anchor_client() -> ModuleType:
    return load_generated_client(ANCHOR_CLIENT, "zk_anchor_client")


def load_helper_client() -> ModuleType:
    return load_generated_client(HELPER_CLIENT, "zk_helper_client")


def deploy_commitment_helper(algorand: AlgorandClient, admin: SigningAccount):
    """Deploy the MiMC helper and return a client for it."""
    module = load_helper_client()
    factory = module.CommitmentHelperFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    client, _ = factory.send.create.bare()
    return module, client


def commitment_for(helper_module, helper_client, choice: int, randomness: bytes) -> bytes:
    """Ask the chain for MiMC(choice, randomness).

    `commit` is a readonly method, so this simulates rather than submitting:
    no fee, no round, no state change. It returns the same 32 bytes
    `cmd/prove` prints, and the same 32 bytes `reveal_vote` will recompute.
    """
    result = helper_client.send.commit(
        helper_module.CommitArgs(choice=choice, randomness=randomness)
    )
    return bytes(result.abi_return)


# --------------------------------------------------------------------------
# Accounts and rounds
# --------------------------------------------------------------------------


def fund_account(
    algorand: AlgorandClient,
    dispenser: SigningAccount,
    account: SigningAccount,
    *,
    algos: int = 20,
) -> None:
    algorand.send.payment(
        PaymentParams(
            sender=dispenser.address,
            signer=dispenser.signer,
            receiver=account.address,
            amount=AlgoAmount.from_algo(algos),
        )
    )


def advance_rounds(
    algorand: AlgorandClient,
    sender: SigningAccount,
    count: int,
) -> int:
    """Force `count` rounds to be produced, and return the round reached.

    LocalNet produces blocks on demand, so a phase deadline expressed in rounds
    does not arrive on its own: something has to submit transactions. Each
    zero-amount self-payment carries a distinct note because a group of
    byte-identical transactions is rejected for duplicate transaction IDs.
    """
    for _ in range(count):
        algorand.send.payment(
            PaymentParams(
                sender=sender.address,
                signer=sender.signer,
                receiver=sender.address,
                amount=AlgoAmount.from_micro_algo(0),
                note=os.urandom(8),
            )
        )
    return current_round(algorand)


def current_round(algorand: AlgorandClient) -> int:
    return int(algorand.client.algod.status()["last-round"])


def advance_past(
    algorand: AlgorandClient,
    sender: SigningAccount,
    target: int,
    *,
    limit: int = 200,
) -> int:
    """Produce rounds until the chain is strictly past `target`.

    Counting rounds instead of reading them is the mistake this exists to
    avoid: on LocalNet every transaction produces a block, so the setup calls
    themselves move the chain, and a phase deadline computed from a round count
    fixed in advance is a deadline that arrives at a different time depending
    on how many transactions the script happened to send.
    """
    for _ in range(limit):
        if current_round(algorand) > target:
            return current_round(algorand)
        advance_rounds(algorand, sender, 1)
    raise RuntimeError(f"did not reach round {target + 1} within {limit} blocks")


# --------------------------------------------------------------------------
# Box references
# --------------------------------------------------------------------------


def commitment_box(address: str) -> bytes:
    return b"c_" + encoding.decode_address(address)


def proof_status_box(address: str) -> bytes:
    return b"p_" + encoding.decode_address(address)


def tally_box(choice: int) -> bytes:
    return b"t_" + choice.to_bytes(8, "big")


# --------------------------------------------------------------------------
# The ZK artifacts
# --------------------------------------------------------------------------


def read_artifact(path: Path) -> bytes:
    if not path.exists():
        raise MissingArtifact(
            f"Missing ZK artifact: {path}\n"
            "See the README: it is produced by `go run ./cmd/gen-verifier` and "
            "`go run ./cmd/prove` in zk/, and by "
            "`poetry run python -m scripts.build_verifier`."
        )
    return path.read_bytes()


def load_vote_manifest(prefix: str = "vote") -> dict:
    """Read what `go run ./cmd/prove` recorded about the proof it wrote."""
    path = GENERATED / f"{prefix}.json"
    if not path.exists():
        raise MissingArtifact(
            f"Missing {path}. Generate a proof with `go run ./cmd/prove` in zk/."
        )
    return json.loads(path.read_text())


def verifier_logicsig(algorand: AlgorandClient) -> transaction.LogicSigAccount:
    """Assemble the generated verifier TEAL and wrap it as a contract account.

    The returned account's address is the hash of the assembled program, so it
    is a commitment to the verifying key the program carries --- and therefore
    to the circuit. Regenerating the verifier from a different circuit produces
    a different address, which is what makes pinning that address in the
    governance app's global state meaningful.
    """
    teal = read_artifact(VERIFIER_TEAL).decode("utf-8")
    compiled = algorand.client.algod.compile(teal)
    return transaction.LogicSigAccount(base64.b64decode(compiled["result"]))


def chunk32(blob: bytes) -> list[bytes]:
    """Split a proof or public-input blob into the 32-byte words the ABI wants.

    Both arguments are declared `byte[32][]` on the anchor app, which is how
    they reach the LogicSig with a 2-byte element count in front --- the two
    bytes the generated verifier skips with `application_args(1)[2:]`.
    """
    if len(blob) % 32:
        raise ValueError(f"blob of {len(blob)} bytes is not a whole number of words")
    return [blob[i : i + 32] for i in range(0, len(blob), 32)]


# --------------------------------------------------------------------------
# The proof-submission group
# --------------------------------------------------------------------------


def build_proof_group(
    algorand: AlgorandClient,
    *,
    voting_client,
    anchor_client,
    lsig: transaction.LogicSigAccount,
    voter: SigningAccount,
    proof: bytes,
    public_inputs: bytes,
    method: str = "record_bound_proof",
    padding: int = PROOF_GROUP_SIZE - 2,
    extra_transactions: int = 0,
    record_for: SigningAccount | None = None,
    verifier_signer=None,
):
    """Assemble the group the chapter's diagram describes.

        [0]     LogicSig-signed call to the verifier anchor app
        [1..6]  padding, contributing 20,000 LogicSig budget units each
        [7]     the voter's call to GovernanceVoting.record_bound_proof

    The five optional arguments exist so the tests can build a group of the
    wrong shape --- too few or too many transactions, a proof recorded against
    somebody else's commitment, an anchor call that no LogicSig authorised ---
    and watch the binding checks reject it.
    """
    beneficiary = record_for or voter
    group = algorand.new_group()

    # [0] The verifier. Its sender is the LogicSig's contract account, so the
    #     program is what authorises this transaction, and the program is the
    #     PLONK verifier. It pays no fee; the voter's call covers the group.
    if verifier_signer is None:
        verifier_sender = lsig.address()
        signer = LogicSigTransactionSigner(lsig)
    else:
        verifier_sender = verifier_signer.address
        signer = verifier_signer.signer

    group.add_app_call_method_call(
        anchor_client.params.verify(
            args=(chunk32(proof), chunk32(public_inputs)),
            params=CommonAppCallParams(
                sender=verifier_sender,
                signer=signer,
                static_fee=AlgoAmount.from_micro_algo(0),
            ),
        )
    )

    # [1..6] Padding. Every transaction in the group adds 20,000 units to the
    #        LogicSig pool whether or not it carries a LogicSig, so the
    #        cheapest thing that buys budget is a zero-amount self-payment.
    for _ in range(padding):
        group.add_payment(
            PaymentParams(
                sender=voter.address,
                signer=voter.signer,
                receiver=voter.address,
                amount=AlgoAmount.from_micro_algo(0),
                static_fee=AlgoAmount.from_micro_algo(0),
                note=os.urandom(8),
            )
        )

    # [7] The state update, and the transaction that pays for everything.
    params = getattr(voting_client.params, method)(
        args=(beneficiary.address,),
        params=CommonAppCallParams(
            sender=voter.address,
            signer=voter.signer,
            static_fee=AlgoAmount.from_micro_algo(
                1_000 * (padding + 2 + extra_transactions)
            ),
            box_references=[
                commitment_box(beneficiary.address),
                proof_status_box(beneficiary.address),
            ],
        ),
    )
    group.add_app_call_method_call(params)

    for _ in range(extra_transactions):
        group.add_payment(
            PaymentParams(
                sender=voter.address,
                signer=voter.signer,
                receiver=voter.address,
                amount=AlgoAmount.from_micro_algo(0),
                static_fee=AlgoAmount.from_micro_algo(0),
                note=os.urandom(8),
            )
        )

    return group


def logic_sig_budget_consumed(group) -> int:
    """Ask a simulate what the verifier LogicSig cost to run.

    A confirmed transaction never reports this. `logic-sig-budget-consumed`
    exists only in a simulate response, and only per transaction, so the
    group's bill is the sum across its transactions --- which for this group is
    one number, because only one transaction carries a LogicSig.

    Execution tracing is turned off. It is on by default in algokit-utils and
    would return more than a megabyte of per-opcode stack changes for a
    verifier that runs 142,955 units of them.
    """
    response = group.simulate(
        exec_trace_config=SimulateTraceConfig(enable=False)
    ).simulate_response
    results = response["txn-groups"][0]["txn-results"]
    return sum(int(txn.get("logic-sig-budget-consumed", 0)) for txn in results)


def commit_vote_params(
    algorand: AlgorandClient,
    voting_client,
    voter: SigningAccount,
    commitment: bytes,
    *,
    mbr: int = COMMITMENT_BOX_MBR,
):
    """Build the (payment, app call) pair `commit_vote` expects."""
    payment = algorand.create_transaction.payment(
        PaymentParams(
            sender=voter.address,
            receiver=voting_client.app_address,
            amount=AlgoAmount.from_micro_algo(mbr),
        )
    )
    return payment, CommonAppCallParams(
        sender=voter.address,
        signer=voter.signer,
        static_fee=AlgoAmount.from_micro_algo(2_000),
        box_references=[commitment_box(voter.address)],
    )
