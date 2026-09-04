from algopy import (
    ARC4Contract,
    BoxMap,
    Bytes,
    Global,
    GlobalState,
    OnCompleteAction,
    OpUpFeeSource,
    Txn,
    UInt64,
    arc4,
    ensure_budget,
    gtxn,
    op,
    urange,
)
from algopy.op import MiMCConfigurations

PHASE_COMMIT = 1
PHASE_PROVE = 2
PHASE_REVEAL = 3
PHASE_TALLY = 4

# The proof-submission group: the verifier LogicSig's app call at index 0, six
# padding transactions that carry nothing but their 20,000 units of LogicSig
# budget each, and this contract's call last. Every transaction contributes to
# the pool whether or not it is LogicSig-signed, which is the only reason the
# padding exists.
PROOF_GROUP_SIZE = 8

# ARC-4 wire sizes for the two arguments the AlgoPlonk verifier reads. Both are
# `byte[32][]`, so both carry a 2-byte element count ahead of the payload.
PROOF_ARG_LEN = 2 + 24 * 32
PUBLIC_INPUTS_ARG_LEN = 2 + 2 * 32


class GovernanceVoting(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.num_choices = GlobalState(UInt64(0))
        self.commit_end_round = GlobalState(UInt64(0))
        self.prove_end_round = GlobalState(UInt64(0))
        self.phase = GlobalState(UInt64(0))
        self.total_votes = GlobalState(UInt64(0))
        self.verified_proofs = GlobalState(UInt64(0))

        # Set by set_verifier before the prove phase opens. Until they hold
        # real values, record_bound_proof refuses to run at all.
        self.verifier_address = GlobalState(Bytes())
        self.verifier_app = GlobalState(UInt64(0))

        self.commitments = BoxMap(arc4.Address, Bytes, key_prefix=b"c_")
        self.proof_status = BoxMap(arc4.Address, UInt64, key_prefix=b"p_")
        self.tallies = BoxMap(arc4.UInt64, UInt64, key_prefix=b"t_")

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        """Reject update and delete --- this contract is immutable."""
        assert False, "Contract is immutable"

    @arc4.abimethod
    def initialize(
        self,
        num_choices: UInt64,
        commit_duration: UInt64,
        prove_duration: UInt64,
    ) -> None:
        assert Txn.sender == Global.creator_address, "Only admin"
        assert self.phase.value == UInt64(0), "Already initialized"

        self.admin.value = Txn.sender.bytes
        self.num_choices.value = num_choices
        self.commit_end_round.value = Global.round + commit_duration
        self.prove_end_round.value = Global.round + commit_duration + prove_duration
        self.phase.value = UInt64(PHASE_COMMIT)

        assert num_choices > UInt64(0), "At least one choice"
        assert num_choices <= UInt64(16), "Max 16 choices"
        for i in urange(16):
            if i >= num_choices:
                break
            self.tallies[arc4.UInt64(i)] = UInt64(0)

    @arc4.abimethod
    def set_verifier(self, verifier: arc4.Address, verifier_app: UInt64) -> None:
        """Bind the election to one AlgoPlonk verifier LogicSig and anchor app.

        The LogicSig's address is the hash of its program, and the program has
        this circuit's verifying key compiled into it, so pinning the address
        pins the circuit. Changing the circuit changes the address, which is
        why this may only be set while the election is still taking
        commitments: after that, the statement being proved is frozen.
        """
        assert Txn.sender == Global.creator_address, "Only admin"
        assert self.phase.value == UInt64(PHASE_COMMIT), "Commit phase only"
        assert verifier_app > UInt64(0), "Verifier app required"

        self.verifier_address.value = verifier.bytes
        self.verifier_app.value = verifier_app

    @arc4.abimethod
    def commit_vote(
        self,
        commitment: Bytes,
        mbr_payment: gtxn.PaymentTransaction,
    ) -> None:
        """Submit a vote commitment. commitment = MiMC(choice, randomness)."""
        assert self.phase.value == UInt64(PHASE_COMMIT), "Not commit phase"
        assert Global.round <= self.commit_end_round.value, "Commit phase closed"
        assert commitment.length == UInt64(32), "Commitment must be 32 bytes"

        sender = arc4.Address(Txn.sender)
        assert sender not in self.commitments, "Already committed"

        # Exactly the box MBR, not at least it. This contract is immutable and
        # has no withdrawal path, so an overpayment is stranded forever.
        box_cost = UInt64(2500) + UInt64(400) * (UInt64(34) + UInt64(32))
        assert (
            mbr_payment.receiver == Global.current_application_address
        ), "Pay the application account"
        assert mbr_payment.amount == box_cost, "Pay the box MBR exactly"

        self.commitments[sender] = commitment
        self.total_votes.value += UInt64(1)

    @arc4.abimethod
    def advance_to_prove_phase(self) -> None:
        """Transition from commit to prove phase."""
        assert Txn.sender == Global.creator_address, "Only admin"
        assert self.phase.value == UInt64(PHASE_COMMIT), "Not commit phase"
        assert Global.round > self.commit_end_round.value, "Commit phase still open"
        self.phase.value = UInt64(PHASE_PROVE)

    @arc4.abimethod
    def record_verified_proof(self, voter: arc4.Address) -> None:
        """Teaching hook for recording an externally verified proof."""
        assert self.phase.value == UInt64(PHASE_PROVE), "Not prove phase"
        assert Global.round <= self.prove_end_round.value, "Prove phase closed"
        assert voter in self.commitments, "No commitment"
        assert voter not in self.proof_status, "Proof already recorded"

        # TEACHING VERSION: the admin's word and nothing else. This exists
        # so the state machine can be driven without assembling a proof
        # group; record_bound_proof below is what a deployment uses.
        assert Txn.sender == Global.creator_address, "Only admin"

        self.proof_status[voter] = UInt64(1)
        self.verified_proofs.value += UInt64(1)

    @arc4.abimethod
    def record_bound_proof(self, voter: arc4.Address) -> None:
        """Record a proof this group verified, trusting no one.

        This is the method record_verified_proof stands in for. It removes the
        admin from the trust boundary by refusing to write proof_status unless
        the AlgoPlonk verifier LogicSig ran, in this group, over public inputs
        that match this election's own state.

        Four of the checklist items are enforced elsewhere on purpose. The
        proof's *soundness* is the LogicSig's job --- if the proof is bad the
        LogicSig rejects and the whole group dies before this method commits
        anything. The verifier's own rekey_to and close_to fields are the
        LogicSig's job too: they describe transactions it is signing, and a
        stateful contract asserting them on someone else's transaction
        restricts a wallet without protecting anything here. What this method
        cannot delegate is the binding --- that the proof which verified is a
        proof about *this* voter's stored commitment --- and that is what the
        public-input comparison below does.
        """
        assert self.phase.value == UInt64(PHASE_PROVE), "Not prove phase"
        assert Global.round <= self.prove_end_round.value, "Prove phase closed"
        assert voter in self.commitments, "No commitment"
        assert voter not in self.proof_status, "Proof already recorded"

        assert self.verifier_app.value > UInt64(0), "Verifier not configured"

        # Exact group shape. Pinning our own index to the last slot is what
        # stops one verified proof from being spent twice: a second call to
        # this method anywhere in the group would read a group_index that is
        # not PROOF_GROUP_SIZE - 1 and fail here.
        assert Global.group_size == UInt64(PROOF_GROUP_SIZE), "Wrong group size"
        assert Txn.group_index == UInt64(PROOF_GROUP_SIZE - 1), "Wrong index"

        verifier_txn = gtxn.ApplicationCallTransaction(0)
        assert (
            verifier_txn.sender.bytes == self.verifier_address.value
        ), "Not verifier"
        assert verifier_txn.app_id.id == self.verifier_app.value, "Wrong anchor app"
        assert verifier_txn.on_completion == OnCompleteAction.NoOp, "Not a NoOp call"
        assert verifier_txn.num_app_args == UInt64(3), "Wrong arg count"

        # A LogicSig authorises transactions from the account whose address is
        # its program hash --- until that account is rekeyed, after which the
        # program never runs again and the sender check above proves nothing.
        # The transaction's own rekey_to field cannot detect that, because the
        # damage was done by a rekey that already settled. Read the account's
        # current authorisation instead.
        auth_addr, _exists = op.AcctParamsGet.acct_auth_addr(verifier_txn.sender)
        assert auth_addr == Global.zero_address, "Verifier is rekeyed"

        # The proof is application_args(1) and the public inputs are
        # application_args(2), both ARC-4 byte[32][]; argument 0 is the method
        # selector. Checking the lengths first means the slices below cannot
        # read past the end of a short argument.
        assert verifier_txn.app_args(1).length == UInt64(PROOF_ARG_LEN), "Proof size"
        public_inputs = verifier_txn.app_args(2)
        assert public_inputs.length == UInt64(PUBLIC_INPUTS_ARG_LEN), "Inputs size"
        assert public_inputs[0:2] == arc4.UInt16(2).bytes, "Inputs not 2 elements"

        # The binding itself. Public input 0 is the commitment the circuit
        # hashed to; it must be the commitment this contract already stores for
        # this voter. Public input 1 is the choice count the circuit range-
        # checked against; it must be this election's.
        assert public_inputs[2:34] == self.commitments[voter], "Commitment mismatch"
        expected_choices = op.concat(op.bzero(24), op.itob(self.num_choices.value))
        assert public_inputs[34:66] == expected_choices, "num_choices mismatch"

        self.proof_status[voter] = UInt64(1)
        self.verified_proofs.value += UInt64(1)

    @arc4.abimethod
    def advance_to_reveal_phase(self) -> None:
        assert Txn.sender == Global.creator_address, "Only admin"
        assert self.phase.value == UInt64(PHASE_PROVE), "Not prove phase"
        assert Global.round > self.prove_end_round.value, "Prove phase still open"
        self.phase.value = UInt64(PHASE_REVEAL)

    @arc4.abimethod
    def reveal_vote(self, choice: UInt64, randomness: Bytes) -> None:
        """Reveal a vote by providing the preimage of the commitment."""
        # The 64-byte MiMC hash alone costs 1,110 budget units --- more
        # than a single app call's 700. Raise the budget first.
        ensure_budget(UInt64(1200), OpUpFeeSource.GroupCredit)

        assert self.phase.value == UInt64(PHASE_REVEAL), "Not reveal phase"
        assert randomness.length == UInt64(32), "Randomness must be 32 bytes"

        sender = arc4.Address(Txn.sender)
        assert sender in self.commitments, "No commitment"
        assert sender in self.proof_status, "No recorded proof"
        assert self.proof_status[sender] == UInt64(1), "Vote already revealed"

        # MiMC requires input to be a multiple of 32 bytes (one BN254 field
        # element per 32-byte chunk).  op.itob returns 8 bytes, so we pad
        # the choice to 32 bytes to match gnark's native field-element size.
        choice_bytes = op.concat(op.bzero(24), op.itob(choice))
        computed_hash = op.mimc(
            MiMCConfigurations.BN254Mp110,
            op.concat(choice_bytes, randomness),
        )
        stored_commitment = self.commitments[sender]
        assert computed_hash == stored_commitment, "Wrong preimage for commitment"

        choice_key = arc4.UInt64(choice)
        assert choice_key in self.tallies, "No such choice"
        self.tallies[choice_key] += UInt64(1)

        self.proof_status[sender] = UInt64(2)  # Mark as revealed

    @arc4.abimethod(readonly=True)
    def get_tally(self, choice: UInt64) -> UInt64:
        return self.tallies[arc4.UInt64(choice)]
