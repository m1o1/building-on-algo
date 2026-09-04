"""LocalNet tests for the private governance voting system.

Two suites in one file, split by what they need. The state-machine tests need
only LocalNet and are the chapter's Python-only track. The tests marked `zk`
additionally need the generated verifier and a proof, and they are the ones
that exercise the trustless path: a real PLONK proof, verified by the real
AlgoPlonk LogicSig, bound to real box state --- and then four ways of getting
that binding wrong.
"""

from __future__ import annotations

import re

import pytest
from algosdk.transaction import OnComplete

from algokit_utils import (
    AlgoAmount,
    AppUpdateParams,
    CommonAppCallParams,
    PaymentParams,
)

from scripts.localnet_helpers import (
    ACCOUNT_BASE_MBR,
    COMMITMENT_BOX_MBR,
    TALLY_BOX_MBR,
    advance_past,
    app_funding_for,
    build_proof_group,
    commit_vote_params,
    commitment_box,
    commitment_for,
    deploy_commitment_helper,
    fund_account,
    load_anchor_client,
    load_voting_client,
    proof_status_box,
    tally_box,
    verifier_logicsig,
)

pytestmark = pytest.mark.localnet


def rejected_with(fragment: str):
    """Assert that the block fails, and that it fails for the stated reason.

    `pytest.raises(Exception)` on a chain call is close to worthless: a typo in
    a box reference, an unfunded sender or a misspelled method all raise, and
    all of them read as the contract doing its job. Matching the assert message
    is what makes the test about the check it claims to be about.
    """
    return _RejectedWith(fragment)


class _RejectedWith:
    def __init__(self, fragment: str):
        self.fragment = fragment

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, _tb):
        assert exc is not None, f"expected a failure mentioning {self.fragment!r}"
        text = str(exc).replace("\n", " ")
        assert self.fragment in text, (
            f"failed for the wrong reason: wanted {self.fragment!r}, got "
            f"{re.sub(r'\s+', ' ', text)[:300]!r}"
        )
        return True


COMMIT_DURATION = 20
PROVE_DURATION = 20
NUM_CHOICES = 3


class Election:
    """One deployed election, plus the accounts and clients that drive it."""

    def __init__(
        self,
        algorand,
        *,
        num_choices: int = NUM_CHOICES,
        voters: int = 1,
        funding: int | None = None,
    ):
        self.algorand = algorand
        self.num_choices = num_choices
        self.voting_module = load_voting_client()
        self.anchor_module = load_anchor_client()

        dispenser = algorand.account.localnet_dispenser()
        self.admin = algorand.account.random()
        self.voters = [algorand.account.random() for _ in range(voters)]
        fund_account(algorand, dispenser, self.admin, algos=50)
        for voter in self.voters:
            fund_account(algorand, dispenser, voter, algos=20)

        self.anchor, _ = self.anchor_module.VerifierAnchorFactory(
            algorand,
            default_sender=self.admin.address,
            default_signer=self.admin.signer,
        ).send.create.bare()

        self.voting, _ = self.voting_module.GovernanceVotingFactory(
            algorand,
            default_sender=self.admin.address,
            default_signer=self.admin.signer,
        ).send.create.bare()

        self.helper_module, self.helper = deploy_commitment_helper(algorand, self.admin)

        # Exactly the box MBR this election will owe, so a test that creates
        # one box too many fails on the box rather than on slack funding.
        algorand.send.payment(
            PaymentParams(
                sender=self.admin.address,
                signer=self.admin.signer,
                receiver=self.voting.app_address,
                amount=AlgoAmount.from_micro_algo(
                    app_funding_for(num_choices, voters)
                    if funding is None
                    else funding
                ),
            )
        )

    # -- setup ------------------------------------------------------------

    def initialize(self, *, commit_duration=COMMIT_DURATION, prove_duration=PROVE_DURATION):
        self.voting.send.initialize(
            self.voting_module.InitializeArgs(
                num_choices=self.num_choices,
                commit_duration=commit_duration,
                prove_duration=prove_duration,
            ),
            params=self._admin_params(
                box_references=[tally_box(i) for i in range(self.num_choices)]
            ),
        )
        return self

    def set_verifier(self, address: str, app_id: int):
        self.voting.send.set_verifier(
            self.voting_module.SetVerifierArgs(verifier=address, verifier_app=app_id),
            params=self._admin_params(),
        )
        return self

    # -- voting -----------------------------------------------------------

    def commitment(self, choice: int, randomness: bytes) -> bytes:
        return commitment_for(self.helper_module, self.helper, choice, randomness)

    def commit(self, voter, commitment: bytes, *, mbr: int = COMMITMENT_BOX_MBR):
        payment, params = commit_vote_params(
            self.algorand, self.voting, voter, commitment, mbr=mbr
        )
        return self.voting.send.commit_vote(
            self.voting_module.CommitVoteArgs(
                commitment=commitment, mbr_payment=payment
            ),
            params=params,
        )

    def to_prove_phase(self):
        state = self.voting.state.global_state.get_all()
        advance_past(self.algorand, self.admin, state["commit_end_round"])
        self.voting.send.advance_to_prove_phase(params=self._admin_params())
        return self

    def to_reveal_phase(self):
        state = self.voting.state.global_state.get_all()
        advance_past(self.algorand, self.admin, state["prove_end_round"])
        self.voting.send.advance_to_reveal_phase(params=self._admin_params())
        return self

    def record_via_admin(self, voter):
        return self.voting.send.record_verified_proof(
            self.voting_module.RecordVerifiedProofArgs(voter=voter.address),
            params=self._admin_params(
                box_references=[
                    commitment_box(voter.address),
                    proof_status_box(voter.address),
                ]
            ),
        )

    def reveal(self, voter, choice: int, randomness: bytes, *, note: bytes | None = None):
        """Send one reveal.

        `note` is for the test that reveals twice. Repeating a reveal verbatim
        produces a byte-identical transaction, and the ledger rejects a
        duplicate transaction ID before the program runs --- which would look
        like the contract refusing, and is not.
        """
        return self.voting.send.reveal_vote(
            self.voting_module.RevealVoteArgs(choice=choice, randomness=randomness),
            params=CommonAppCallParams(
                sender=voter.address,
                signer=voter.signer,
                # ensure_budget(1200) issues one op-up inner call, and that
                # call needs a minimum fee out of the group's pooled credit.
                static_fee=AlgoAmount.from_micro_algo(2_000),
                note=note,
                box_references=[
                    commitment_box(voter.address),
                    proof_status_box(voter.address),
                    tally_box(choice),
                ],
            ),
        )

    def tally(self, choice: int) -> int:
        return self.voting.send.get_tally(
            self.voting_module.GetTallyArgs(choice=choice),
            params=self._admin_params(box_references=[tally_box(choice)]),
        ).abi_return

    def _admin_params(self, **kwargs) -> CommonAppCallParams:
        return CommonAppCallParams(
            sender=self.admin.address,
            signer=self.admin.signer,
            static_fee=AlgoAmount.from_micro_algo(1_000),
            **kwargs,
        )


# ---------------------------------------------------------------------------
# The Python-only track: no Go toolchain, no proofs.
# ---------------------------------------------------------------------------


def test_python_state_machine_flow(algorand) -> None:
    """commit -> admin proof mark -> reveal -> tally, with three voters."""
    election = Election(algorand, voters=3).initialize()

    choices = [0, 1, 2]
    randomness = [bytes([i + 1]) * 32 for i in range(3)]
    commitments = [
        election.commitment(choice, rand)
        for choice, rand in zip(choices, randomness, strict=True)
    ]

    for voter, commitment in zip(election.voters, commitments, strict=True):
        election.commit(voter, commitment)

    election.to_prove_phase()
    for voter in election.voters:
        election.record_via_admin(voter)

    election.to_reveal_phase()
    for voter, choice, rand in zip(
        election.voters, choices, randomness, strict=True
    ):
        election.reveal(voter, choice, rand)

    assert election.tally(0) == 1
    assert election.tally(1) == 1
    assert election.tally(2) == 1


def test_initialize_needs_the_app_account_funded_for_its_boxes(algorand) -> None:
    """A method that creates boxes the app cannot pay for aborts on the floor.

    The failure is worth seeing once, because it names the wrong thing: it is
    a minimum-balance error carrying a number, not a message about the box that
    could not be written, and no assertion in the contract can catch it. The
    minimum-balance check runs after the program has already returned success.
    """
    election = Election(algorand, funding=ACCOUNT_BASE_MBR + TALLY_BOX_MBR)

    with rejected_with("below min"):
        election.initialize()


def test_double_commit_rejected(algorand) -> None:
    election = Election(algorand).initialize()
    voter = election.voters[0]

    election.commit(voter, election.commitment(1, b"\x01" * 32))

    with rejected_with("Already committed"):
        election.commit(voter, election.commitment(2, b"\x02" * 32))


def test_commit_must_pay_the_box_MBR_exactly(algorand) -> None:
    """Underpaying is refused, and so is overpaying.

    The contract is immutable and has no withdrawal path, so an overpayment
    would sit in the application account until the chain ends. `==` refuses it
    at the door rather than accepting money nobody can ever move.
    """
    election = Election(algorand, voters=2).initialize()
    short, generous = election.voters

    with rejected_with("Pay the box MBR exactly"):
        election.commit(
            short, election.commitment(0, b"\x0a" * 32), mbr=COMMITMENT_BOX_MBR - 1
        )

    with rejected_with("Pay the box MBR exactly"):
        election.commit(
            generous, election.commitment(1, b"\x0b" * 32), mbr=COMMITMENT_BOX_MBR + 1
        )

    election.commit(generous, election.commitment(1, b"\x0b" * 32))
    assert election.voting.state.global_state.get_all()["total_votes"] == 1


def test_reveal_must_match_commitment(algorand) -> None:
    """Revealing a different choice than the one committed fails."""
    election = Election(algorand).initialize()
    voter = election.voters[0]
    randomness = b"\x03" * 32

    election.commit(voter, election.commitment(1, randomness))
    election.to_prove_phase()
    election.record_via_admin(voter)
    election.to_reveal_phase()

    with rejected_with("Wrong preimage for commitment"):
        election.reveal(voter, 2, randomness)

    # The honest reveal still works afterwards: the failed attempt committed
    # nothing, because a failing transaction changes no state.
    election.reveal(voter, 1, randomness)
    assert election.tally(1) == 1


def test_reveal_requires_a_recorded_proof(algorand) -> None:
    """A voter who commits but never proves cannot reveal, and forfeits."""
    election = Election(algorand).initialize()
    voter = election.voters[0]
    randomness = b"\x04" * 32

    election.commit(voter, election.commitment(0, randomness))
    election.to_prove_phase()
    election.to_reveal_phase()

    with rejected_with("No recorded proof"):
        election.reveal(voter, 0, randomness)

    assert election.tally(0) == 0


def test_mimc_hashes_whole_field_elements(algorand) -> None:
    """The choice is padded to 32 bytes before it is hashed.

    `op.itob` yields 8 bytes and `mimc` consumes whole 32-byte BN254 field
    elements, so both sides pad the choice to 32 and hash 64 bytes in total.
    Two consequences are visible from outside the contract: a commitment is one
    field element wide, and a randomness that is not exactly 32 bytes is
    refused rather than quietly padded --- which is what stops two different
    ballots from sharing one commitment.
    """
    election = Election(algorand).initialize()
    voter = election.voters[0]
    randomness = b"\x08" * 32

    commitment = election.commitment(1, randomness)
    assert len(commitment) == 32

    # Same randomness, different ballot. Only the padded choice differs, and
    # the hash has to carry that difference.
    assert election.commitment(2, randomness) != commitment

    with rejected_with("Randomness must be 32 bytes"):
        election.commitment(1, b"\x08" * 31)

    # The contract enforces the same rule where it matters: a short preimage
    # cannot be stretched into a match for a stored commitment.
    election.commit(voter, commitment)
    election.to_prove_phase()
    election.record_via_admin(voter)
    election.to_reveal_phase()

    with rejected_with("Randomness must be 32 bytes"):
        election.reveal(voter, 1, b"\x08" * 31)

    election.reveal(voter, 1, randomness)
    assert election.tally(1) == 1


def test_a_vote_cannot_be_revealed_twice(algorand) -> None:
    """Revealing spends the proof: proof_status moves 1 -> 2, and only 1 opens.

    Nothing else stops a voter from sending the same reveal again --- the
    preimage still matches the commitment, and the box is still theirs. What
    refuses the second one is the status the first reveal wrote.

    The second attempt carries a note so that it is a different transaction
    from the first. Without it the ledger rejects a duplicate transaction ID
    and the program never runs, which passes this test for the wrong reason.
    """
    election = Election(algorand).initialize()
    voter = election.voters[0]
    randomness = b"\x09" * 32

    election.commit(voter, election.commitment(2, randomness))
    election.to_prove_phase()
    election.record_via_admin(voter)
    election.to_reveal_phase()

    election.reveal(voter, 2, randomness)

    with rejected_with("Vote already revealed"):
        election.reveal(voter, 2, randomness, note=b"second attempt")

    assert election.tally(2) == 1


def test_commitment_after_deadline_rejected(algorand) -> None:
    election = Election(algorand).initialize(commit_duration=1, prove_duration=20)
    voter = election.voters[0]

    state = election.voting.state.global_state.get_all()
    advance_past(algorand, election.admin, state["commit_end_round"])

    with rejected_with("Commit phase closed"):
        election.commit(voter, election.commitment(0, b"\x05" * 32))


def test_record_verified_proof_is_admin_only(algorand) -> None:
    """The teaching hook's trust boundary is exactly one account wide."""
    election = Election(algorand, voters=2).initialize()
    voter, attacker = election.voters

    election.commit(voter, election.commitment(1, b"\x06" * 32))
    election.to_prove_phase()

    with rejected_with("Only admin"):
        election.voting.send.record_verified_proof(
            election.voting_module.RecordVerifiedProofArgs(voter=voter.address),
            params=CommonAppCallParams(
                sender=attacker.address,
                signer=attacker.signer,
                static_fee=AlgoAmount.from_micro_algo(1_000),
                box_references=[
                    commitment_box(voter.address),
                    proof_status_box(voter.address),
                ],
            ),
        )


def test_set_verifier_is_admin_only_and_commit_phase_only(algorand) -> None:
    election = Election(algorand, voters=2).initialize()
    _voter, attacker = election.voters

    with rejected_with("Only admin"):
        election.voting.send.set_verifier(
            election.voting_module.SetVerifierArgs(
                verifier=attacker.address, verifier_app=election.anchor.app_id
            ),
            params=CommonAppCallParams(
                sender=attacker.address,
                signer=attacker.signer,
                static_fee=AlgoAmount.from_micro_algo(1_000),
            ),
        )

    # And the circuit is frozen once commitments close: a verifier swapped in
    # during the prove phase would be a different statement about the same
    # commitments.
    election.to_prove_phase()
    with rejected_with("Commit phase only"):
        election.set_verifier(attacker.address, election.anchor.app_id)


def test_update_and_delete_are_rejected(algorand) -> None:
    election = Election(algorand).initialize()
    spec = election.voting.app_spec

    with rejected_with("Contract is immutable"):
        election.voting.send.delete.bare()

    # The update is built without the typed client, and still reports the
    # ARC-56 message rather than the AVM's `err opcode executed`. Constructing
    # any AppClient registers an error transformer on the shared
    # AlgorandClient (app_client.py:1315), so every call through that client
    # gets the substitution --- not only calls made through the typed client.
    with rejected_with("Contract is immutable"):
        algorand.send.app_update(
            AppUpdateParams(
                sender=election.admin.address,
                signer=election.admin.signer,
                app_id=election.voting.app_id,
                approval_program=spec.source.get_decoded_approval(),
                clear_state_program=spec.source.get_decoded_clear(),
                on_complete=OnComplete.UpdateApplicationOC,
            )
        )


# ---------------------------------------------------------------------------
# The trustless track: a real proof through the real verifier.
# ---------------------------------------------------------------------------


@pytest.mark.zk
class TestBoundVerifier:
    @staticmethod
    def _election(algorand, zk_artifacts, *, voters=1, num_choices=NUM_CHOICES):
        manifest = zk_artifacts["manifest"]
        lsig = verifier_logicsig(algorand)
        election = Election(algorand, voters=voters, num_choices=num_choices)
        election.initialize().set_verifier(lsig.address(), election.anchor.app_id)
        election.lsig = lsig
        election.commit(
            election.voters[0], bytes.fromhex(manifest["commitment"])
        )
        return election

    @staticmethod
    def _group(election, zk_artifacts, **kwargs):
        return build_proof_group(
            election.algorand,
            voting_client=election.voting,
            anchor_client=election.anchor,
            lsig=election.lsig,
            voter=election.voters[0],
            proof=zk_artifacts["proof"],
            public_inputs=zk_artifacts["public_inputs"],
            **kwargs,
        )

    def test_avm_mimc_matches_the_go_prover(self, algorand, zk_artifacts) -> None:
        """The whole system rests on this one equality.

        The circuit hashed the ballot with gnark's in-circuit MiMC gadget,
        `cmd/prove` recomputed it with gnark-crypto, and `reveal_vote` will
        recompute it a third time with the AVM's mimc opcode. If any pair of
        those disagreed, a proof would verify against a commitment no reveal
        could ever open.
        """
        manifest = zk_artifacts["manifest"]
        election = Election(algorand)

        on_chain = election.commitment(
            int(manifest["choice"]), bytes.fromhex(manifest["randomness"])
        )
        assert on_chain.hex() == manifest["commitment"]

    def test_bound_verifier_group_records_proof(self, algorand, zk_artifacts) -> None:
        election = self._election(algorand, zk_artifacts)
        election.to_prove_phase()

        self._group(election, zk_artifacts).send()

        state = election.voting.state.global_state.get_all()
        assert state["verified_proofs"] == 1

        # And the vote it unlocked opens correctly.
        manifest = zk_artifacts["manifest"]
        election.to_reveal_phase()
        election.reveal(
            election.voters[0],
            int(manifest["choice"]),
            bytes.fromhex(manifest["randomness"]),
        )
        assert election.tally(int(manifest["choice"])) == 1

    def test_a_proof_cannot_be_recorded_twice(self, algorand, zk_artifacts) -> None:
        election = self._election(algorand, zk_artifacts)
        election.to_prove_phase()

        self._group(election, zk_artifacts).send()
        with rejected_with("Proof already recorded"):
            self._group(election, zk_artifacts).send()

    def test_unsigned_anchor_call_rejected(self, algorand, zk_artifacts) -> None:
        """The anchor app approves anyone; the governance app does not.

        This is the attack the anchor's docstring warns about: call
        `verify` from an ordinary account with the same arguments, so the
        group *looks* like a verification and no LogicSig ever ran.
        """
        election = self._election(algorand, zk_artifacts, voters=2)
        election.to_prove_phase()

        group = self._group(
            election, zk_artifacts, verifier_signer=election.voters[1]
        )
        with rejected_with("Not verifier"):
            group.send()

    def test_extra_transaction_in_group_rejected(self, algorand, zk_artifacts) -> None:
        election = self._election(algorand, zk_artifacts)
        election.to_prove_phase()

        with rejected_with("Wrong group size"):
            self._group(election, zk_artifacts, extra_transactions=1).send()

    def test_short_group_rejected(self, algorand, zk_artifacts) -> None:
        election = self._election(algorand, zk_artifacts)
        election.to_prove_phase()

        # Seven transactions pool 140,000 LogicSig units against the
        # 142,955 this verifier consumes, so it dies inside the pairing check
        # rather than at any of the app's own guards.
        with rejected_with("dynamic cost budget exceeded"):
            self._group(election, zk_artifacts, padding=5).send()

    def test_mismatched_commitment_rejected(self, algorand, zk_artifacts) -> None:
        """One voter's proof cannot be spent on another voter's commitment."""
        election = self._election(algorand, zk_artifacts, voters=2)
        other = election.voters[1]
        election.commit(other, election.commitment(0, b"\x07" * 32))
        election.to_prove_phase()

        with rejected_with("Commitment mismatch"):
            self._group(election, zk_artifacts, record_for=other).send()

    def test_mismatched_num_choices_rejected(self, algorand, zk_artifacts) -> None:
        """A proof carries the choice range it was checked against.

        The election below has four choices; the committed proof was generated
        against three. The commitment public input still matches --- it is the
        same ballot --- so only the second public input catches this.
        """
        election = self._election(algorand, zk_artifacts, num_choices=4)
        election.to_prove_phase()

        with rejected_with("num_choices mismatch"):
            self._group(election, zk_artifacts).send()
