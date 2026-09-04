from algopy import ARC4Contract, Bytes, UInt64, arc4, ensure_budget, op
from algopy.op import MiMCConfigurations


class CommitmentHelper(ARC4Contract):
    """Compute a vote commitment the way the AVM computes it.

    There is no standard Python library for MiMC under the BN254Mp110
    configuration, which leaves a reader without the Go toolchain unable to
    produce the one value `commit_vote` requires. The way out is to stop
    reimplementing the hash and ask the machine that defines it: this contract
    exists so a client can call `commit` and get back exactly the bytes
    `GovernanceVoting.reveal_vote` will recompute later.

    `commit` is `readonly`, so algokit-utils simulates it instead of submitting
    it --- no fee, no block, no state. Note what that does *not* mean: readonly
    is a promise to callers, not a rule the AVM enforces, and driving this
    method through the composer would submit it as a real transaction. It is
    safe to do so; it just costs a fee and a round for a value that did not
    need either.

    A voter who runs the Go prover does not need this contract at all:
    `cmd/prove` prints the same commitment, and computes it from the same
    gnark-crypto implementation the opcode is built on.
    """

    @arc4.abimethod(readonly=True)
    def commit(self, choice: UInt64, randomness: Bytes) -> Bytes:
        # Two 32-byte field elements at 550 units each, plus 10, is 1,110 ---
        # already past an application call's 700 before anything else runs.
        # Under the readonly simulate path the budget is raised for us; under a
        # real submission this is what pays for the hash.
        ensure_budget(UInt64(1200))

        assert randomness.length == UInt64(32), "Randomness must be 32 bytes"

        # The choice is padded to a full BN254 field element because that is
        # what gnark hashed inside the circuit. op.itob gives 8 bytes.
        choice_bytes = op.concat(op.bzero(24), op.itob(choice))
        return op.mimc(
            MiMCConfigurations.BN254Mp110,
            op.concat(choice_bytes, randomness),
        )
