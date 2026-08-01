"""Run one private governance election end to end on LocalNet.

Three voters commit, one of them proves through the real AlgoPlonk verifier
LogicSig and the other two through the chapter's admin-trusted teaching hook,
and all three reveal. The interesting transaction is the eight-transaction
proof group: everything before it is a state machine, and everything after it
is arithmetic.

    poetry run python -m scripts.run_governance_voting
"""

from __future__ import annotations

from algokit_utils import AlgoAmount, CommonAppCallParams, PaymentParams

from scripts.localnet_helpers import (
    COMMITMENT_BOX_MBR,
    LOGIC_SIG_BUDGET_PER_TXN,
    MissingArtifact,
    app_funding_for,
    PROOF_FILE,
    PROOF_GROUP_SIZE,
    PUBLIC_INPUTS_FILE,
    advance_past,
    build_proof_group,
    commit_vote_params,
    commitment_box,
    commitment_for,
    deploy_commitment_helper,
    fund_account,
    get_localnet_algorand,
    load_anchor_client,
    load_vote_manifest,
    load_voting_client,
    logic_sig_budget_consumed,
    proof_status_box,
    read_artifact,
    tally_box,
    verifier_logicsig,
)

# Round budgets for the two timed phases. They are generous because every
# transaction produces a block on LocalNet, so the setup calls themselves eat
# into the window; the script waits on the deadline it reads back from global
# state rather than on a count it decided in advance.
COMMIT_DURATION = 20
PROVE_DURATION = 20
NUM_CHOICES = 3


def main() -> int:
    try:
        algorand = get_localnet_algorand()
        voting_module = load_voting_client()
        anchor_module = load_anchor_client()
    except (RuntimeError, MissingArtifact) as exc:
        print(exc)
        return 1

    try:
        manifest = load_vote_manifest()
        proof = read_artifact(PROOF_FILE)
        public_inputs = read_artifact(PUBLIC_INPUTS_FILE)
        lsig = verifier_logicsig(algorand)
    except MissingArtifact as exc:
        print(exc)
        return 1

    if manifest["num_choices"] != NUM_CHOICES:
        print(
            f"The committed proof is for {manifest['num_choices']} choices and "
            f"this script runs a {NUM_CHOICES}-choice election. Regenerate with "
            f"`go run ./cmd/prove -num-choices {NUM_CHOICES}`."
        )
        return 1

    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    voters = [algorand.account.random() for _ in range(3)]
    fund_account(algorand, dispenser, admin, algos=50)
    for voter in voters:
        fund_account(algorand, dispenser, voter, algos=20)

    print(f"Verifier LogicSig address: {lsig.address()}")
    print(f"Verifier program bytes:    {len(lsig.lsig.logic)}")

    # ---------------------------------------------------------------- setup
    anchor_factory = anchor_module.VerifierAnchorFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    anchor, _ = anchor_factory.send.create.bare()
    print(f"Verifier anchor app ID:    {anchor.app_id}")

    voting_factory = voting_module.GovernanceVotingFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    voting, _ = voting_factory.send.create.bare()
    print(f"Governance app ID:         {voting.app_id}")

    helper_module, helper = deploy_commitment_helper(algorand, admin)
    print(f"Commitment helper app ID:  {helper.app_id}")

    # The app account pays for every box it creates: one tally box per choice
    # and one proof-status box per voter. The commitment boxes are the voters'
    # own bill, settled by the payment commit_vote requires.
    funding = app_funding_for(NUM_CHOICES, len(voters))
    algorand.send.payment(
        PaymentParams(
            sender=admin.address,
            signer=admin.signer,
            receiver=voting.app_address,
            amount=AlgoAmount.from_micro_algo(funding),
        )
    )
    print(f"App account funded with {funding} microAlgo of box MBR.")

    voting.send.initialize(
        voting_module.InitializeArgs(
            num_choices=NUM_CHOICES,
            commit_duration=COMMIT_DURATION,
            prove_duration=PROVE_DURATION,
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(1_000),
            box_references=[tally_box(i) for i in range(NUM_CHOICES)],
        ),
    )
    print(f"Initialized: {NUM_CHOICES} choices, phase COMMIT.")

    voting.send.set_verifier(
        voting_module.SetVerifierArgs(
            verifier=lsig.address(),
            verifier_app=anchor.app_id,
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(1_000),
        ),
    )
    print("Bound to the verifier LogicSig address and anchor app.")

    # --------------------------------------------------------------- commit
    # Voter 0 casts the ballot the committed proof was generated for; that is
    # the one whose proof the LogicSig will verify. The other two go through
    # the teaching hook, which is what a reader without the Go toolchain gets.
    prover_choice = int(manifest["choice"])
    prover_randomness = bytes.fromhex(manifest["randomness"])
    prover_commitment = bytes.fromhex(manifest["commitment"])

    ballots = [
        (voters[0], prover_choice, prover_randomness, prover_commitment),
    ]
    for index, voter in enumerate(voters[1:], start=1):
        choice = (prover_choice + index) % NUM_CHOICES
        randomness = bytes([index]) * 32
        commitment = commitment_for(helper_module, helper, choice, randomness)
        ballots.append((voter, choice, randomness, commitment))

    # The helper and the Go prover agree, which is the whole reason the
    # Python-only track is usable: whichever produced a commitment, the same
    # reveal_vote arithmetic reproduces it.
    assert (
        commitment_for(helper_module, helper, prover_choice, prover_randomness)
        == prover_commitment
    ), "The chain and cmd/prove disagree about MiMC"

    for voter, _choice, _randomness, commitment in ballots:
        payment, params = commit_vote_params(algorand, voting, voter, commitment)
        voting.send.commit_vote(
            voting_module.CommitVoteArgs(
                commitment=commitment,
                mbr_payment=payment,
            ),
            params=params,
        )
    print(f"Three commitments stored, {COMMITMENT_BOX_MBR} microAlgo of MBR each.")

    # ---------------------------------------------------------------- prove
    state = voting.state.global_state.get_all()
    advance_past(algorand, admin, state["commit_end_round"])
    voting.send.advance_to_prove_phase(
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(1_000),
        )
    )
    print("Phase PROVE.")

    def proof_group():
        return build_proof_group(
            algorand,
            voting_client=voting,
            anchor_client=anchor,
            lsig=lsig,
            voter=voters[0],
            proof=proof,
            public_inputs=public_inputs,
        )

    # Simulate before submitting, because the cost of the verification is the
    # reason the group is eight transactions long and a confirmed transaction
    # never reports it. The group built here is thrown away: a simulate lands
    # nothing, so the one below is a fresh group with fresh padding notes.
    consumed = logic_sig_budget_consumed(proof_group())
    pooled = PROOF_GROUP_SIZE * LOGIC_SIG_BUDGET_PER_TXN
    print(
        f"LogicSig budget consumed: {consumed:,} units of the {pooled:,} that "
        f"{PROOF_GROUP_SIZE} transactions pool."
    )

    result = proof_group().send()
    print(
        f"Proof group of {PROOF_GROUP_SIZE} accepted: the LogicSig verified a "
        "PLONK proof and the app bound it to the stored commitment."
    )
    print(f"Confirmed in round {result.confirmations[0]['confirmed-round']}.")

    for voter, _choice, _randomness, _commitment in ballots[1:]:
        voting.send.record_verified_proof(
            voting_module.RecordVerifiedProofArgs(voter=voter.address),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                static_fee=AlgoAmount.from_micro_algo(1_000),
                box_references=[
                    commitment_box(voter.address),
                    proof_status_box(voter.address),
                ],
            ),
        )
    print("Two further proofs recorded through the admin-trusted teaching hook.")

    # --------------------------------------------------------------- reveal
    advance_past(algorand, admin, state["prove_end_round"])
    voting.send.advance_to_reveal_phase(
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(1_000),
        )
    )
    print("Phase REVEAL.")

    for voter, choice, randomness, _commitment in ballots:
        voting.send.reveal_vote(
            voting_module.RevealVoteArgs(choice=choice, randomness=randomness),
            params=CommonAppCallParams(
                sender=voter.address,
                signer=voter.signer,
                # ensure_budget(1200) issues one op-up inner call, which needs
                # its own minimum fee out of the group's pooled credit.
                static_fee=AlgoAmount.from_micro_algo(2_000),
                box_references=[
                    commitment_box(voter.address),
                    proof_status_box(voter.address),
                    tally_box(choice),
                ],
            ),
        )
    print("All three votes revealed; the app recomputed each MiMC commitment.")

    # ---------------------------------------------------------------- tally
    for choice in range(NUM_CHOICES):
        tally = voting.send.get_tally(
            voting_module.GetTallyArgs(choice=choice),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                box_references=[tally_box(choice)],
            ),
        ).abi_return
        print(f"Tally for choice {choice}: {tally}")

    print("Chapter 23 private voting workflow complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
