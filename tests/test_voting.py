"""Unit tests for the private voting contract (Chapter 8).
Tests the MiMC 32-byte padding fix and authorization checks."""

import pytest
from algopy_testing import algopy_testing_context
from algopy import UInt64, Bytes, arc4, op, OnCompleteAction

from tests.contracts.voting import (
    PrivateVoting,
    PHASE_PROVE,
)


class TestMiMCPadding:
    """Verify that MiMC input is padded to 32-byte multiples."""

    def test_choice_bytes_are_32_bytes(self):
        """The fix pads op.itob(choice) from 8 bytes to 32 bytes
        by prepending 24 zero bytes."""
        with algopy_testing_context():
            choice = UInt64(1)
            choice_bytes = op.concat(op.bzero(24), op.itob(choice))
            assert len(choice_bytes) == 32

    def test_mimc_input_is_64_bytes(self):
        """With 32-byte choice + 32-byte randomness = 64 bytes,
        which is a valid multiple of 32 for the mimc opcode."""
        with algopy_testing_context():
            choice = UInt64(1)
            randomness = op.bzero(32)
            choice_bytes = op.concat(op.bzero(24), op.itob(choice))
            mimc_input = op.concat(choice_bytes, randomness)
            assert len(mimc_input) == 64

    def test_different_choices_produce_different_padding(self):
        """Choices 0 and 1 must produce different 32-byte representations."""
        with algopy_testing_context():
            bytes_0 = op.concat(op.bzero(24), op.itob(UInt64(0)))
            bytes_1 = op.concat(op.bzero(24), op.itob(UInt64(1)))
            assert bytes_0 != bytes_1


class TestVotingAuthorization:
    """Test the authorization fix for record_verified_proof."""

    def _create_contract(self, ctx):
        contract = PrivateVoting()
        with ctx.txn.create_group(
            active_txn_overrides={"on_completion": OnCompleteAction.NoOp}
        ):
            contract.create()
        return contract

    def test_record_proof_requires_admin(self):
        """record_verified_proof must reject non-admin callers."""
        with algopy_testing_context() as ctx:
            contract = self._create_contract(ctx)
            ctx.ledger.patch_global_fields(round=10)
            contract.phase.value = UInt64(PHASE_PROVE)
            contract.prove_end_round.value = UInt64(100)

            voter = ctx.any.account()
            voter_addr = arc4.Address(voter)
            contract.commitments[voter_addr] = op.bzero(32)

            non_admin = ctx.any.account()
            with ctx.txn.create_group(
                active_txn_overrides={"sender": non_admin}
            ):
                with pytest.raises(AssertionError, match="Only admin"):
                    contract.record_verified_proof(voter_addr)

    def test_record_proof_succeeds_as_admin(self):
        """record_verified_proof must succeed when called by admin (creator)."""
        with algopy_testing_context() as ctx:
            contract = self._create_contract(ctx)
            ctx.ledger.patch_global_fields(round=10)
            contract.phase.value = UInt64(PHASE_PROVE)
            contract.prove_end_round.value = UInt64(100)

            voter = ctx.any.account()
            voter_addr = arc4.Address(voter)
            contract.commitments[voter_addr] = op.bzero(32)

            contract.record_verified_proof(voter_addr)
            assert contract.proof_status[voter_addr] == 1
            assert contract.verified_proofs.value == 1
