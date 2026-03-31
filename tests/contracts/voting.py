"""Private governance voting contract - extracted from Chapter 8 of the book.
Tests the MiMC padding fix (choice must be padded to 32 bytes)."""

from algopy import (
    ARC4Contract, BoxMap, Bytes, Global, GlobalState,
    Txn, UInt64, arc4, gtxn, op,
)
from algopy.op import MiMCConfigurations

PHASE_COMMIT = 1
PHASE_PROVE = 2
PHASE_REVEAL = 3
PHASE_TALLY = 4


class PrivateVoting(ARC4Contract):
    def __init__(self) -> None:
        self.phase = GlobalState(UInt64(0))
        self.num_choices = GlobalState(UInt64(0))
        self.commit_end_round = GlobalState(UInt64(0))
        self.prove_end_round = GlobalState(UInt64(0))
        self.reveal_end_round = GlobalState(UInt64(0))
        self.verified_proofs = GlobalState(UInt64(0))
        self.commitments = BoxMap(arc4.Address, Bytes, key_prefix=b"c_")
        self.proof_status = BoxMap(arc4.Address, UInt64, key_prefix=b"p_")
        self.tallies = BoxMap(arc4.UInt64, UInt64, key_prefix=b"t_")

    @arc4.baremethod(create="require")
    def create(self) -> None:
        pass

    @arc4.abimethod
    def init_election(
        self,
        num_choices: UInt64,
        commit_end_round: UInt64,
        prove_end_round: UInt64,
        reveal_end_round: UInt64,
    ) -> None:
        assert Txn.sender == Global.creator_address
        self.phase.value = UInt64(PHASE_COMMIT)
        self.num_choices.value = num_choices
        self.commit_end_round.value = commit_end_round
        self.prove_end_round.value = prove_end_round
        self.reveal_end_round.value = reveal_end_round
        idx = UInt64(0)
        while idx < num_choices:
            self.tallies[arc4.UInt64(idx)] = UInt64(0)
            idx += UInt64(1)

    @arc4.abimethod
    def commit_vote(
        self,
        commitment: Bytes,
        mbr_payment: gtxn.PaymentTransaction,
    ) -> None:
        assert self.phase.value == UInt64(PHASE_COMMIT)
        sender = arc4.Address(Txn.sender)
        assert sender not in self.commitments
        self.commitments[sender] = commitment

    @arc4.abimethod
    def advance_to_prove_phase(self) -> None:
        assert Txn.sender == Global.creator_address
        assert self.phase.value == UInt64(PHASE_COMMIT)
        assert Global.round > self.commit_end_round.value
        self.phase.value = UInt64(PHASE_PROVE)

    @arc4.abimethod
    def record_verified_proof(self, voter: arc4.Address) -> None:
        assert self.phase.value == UInt64(PHASE_PROVE)
        assert Global.round <= self.prove_end_round.value
        assert voter in self.commitments
        assert voter not in self.proof_status
        assert Txn.sender == Global.creator_address, "Only admin"
        self.proof_status[voter] = UInt64(1)
        self.verified_proofs.value += UInt64(1)

    @arc4.abimethod
    def advance_to_reveal_phase(self) -> None:
        assert Txn.sender == Global.creator_address
        assert self.phase.value == UInt64(PHASE_PROVE)
        assert Global.round > self.prove_end_round.value
        self.phase.value = UInt64(PHASE_REVEAL)

    @arc4.abimethod
    def reveal_vote(self, choice: UInt64, randomness: Bytes) -> None:
        """Reveal a vote by providing the preimage of the commitment."""
        assert self.phase.value == UInt64(PHASE_REVEAL)

        sender = arc4.Address(Txn.sender)
        assert sender in self.commitments
        assert sender in self.proof_status
        assert self.proof_status[sender] == UInt64(1)

        # MiMC requires input to be a multiple of 32 bytes (one BN254 field
        # element per 32-byte chunk).  op.itob returns 8 bytes, so we pad
        # the choice to 32 bytes to match gnark's native field-element size.
        choice_bytes = op.concat(op.bzero(24), op.itob(choice))
        computed_hash = op.mimc(
            MiMCConfigurations.BN254Mp110,
            op.concat(choice_bytes, randomness),
        )
        stored_commitment = self.commitments[sender]
        assert computed_hash == stored_commitment

        choice_key = arc4.UInt64(choice)
        assert choice_key in self.tallies
        self.tallies[choice_key] += UInt64(1)

        self.proof_status[sender] = UInt64(2)  # Mark as revealed

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "Immutable"
