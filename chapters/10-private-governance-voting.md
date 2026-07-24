\newpage

\part{Cryptography and Zero-Knowledge Proofs}

Part IV pushes the AVM to its limits with advanced cryptography. You will build a privacy-preserving governance voting system using zero-knowledge proofs, explore Algorand's native elliptic curve opcodes and the MiMC hash, and learn about the Falcon-based post-quantum security roadmap.

# Private Governance Voting with Zero-Knowledge Proofs

Your DAO needs to hold a vote, but the community demands ballot secrecy --- no one should be able to see how anyone voted until results are final. On a public blockchain where all state is readable, this seems impossible. Zero-knowledge proofs make it possible.

In this project we build the on-chain state machine for a privacy-preserving governance voting system and map the verifier architecture needed to prove that each ballot is valid without revealing its choice during the voting period. Along the way, we explore the AVM's native elliptic curve opcodes, zero-knowledge proof construction and on-chain verification, advanced box storage patterns, and Algorand's Falcon-based post-quantum security architecture.

> **Note: Implementation Scope.** The PuyaPy voting contract in this chapter is the runnable core: deployment, proposal setup, commitment storage, phase transitions, reveal, and tallying. The Go/gnark/AlgoPlonk sections are an advanced integration path with placeholders you must complete in a real Go module. Until you add the production verifier-group binding described in the following sections, `record_verified_proof` is an admin-trusted teaching hook, not a trustless proof-verification method.

## Project Setup

Scaffold a new project for this chapter. The template creates a `hello_world/` contract directory which we rename:

```bash
algokit init -t python --name governance-voting
cd governance-voting
algokit project bootstrap all
mv smart_contracts/hello_world smart_contracts/governance_voting
```

Your contract code goes in `smart_contracts/governance_voting/contract.py`. Delete the template-generated `deploy_config.py` in the renamed directory --- it references the old `HelloWorld` contract.

> **Note: Technology stack for this chapter.** This project spans two languages and three components:
>
> 1. **Algorand Python** (PuyaPy) --- the voting smart contract (`contract.py`), compiled with `algokit project run build`
> 2. **Go** (gnark + AlgoPlonk) --- the ZK circuit definition and verifier LogicSig generator, compiled with `go build`. This chapter pins the current AlgoPlonk-compatible Go and gnark versions in the setup section below.
> 3. **Python client code** --- deployment scripts and test harnesses using AlgoKit Utils
>
> The data flow is: the Go program generates a TEAL verifier LogicSig from the circuit definition. The Python client compiles this TEAL via algod, then uses it in atomic groups alongside the voting contract. You can build and test the voting contract (component 1) independently; the Go components (component 2) are needed only for end-to-end ZK proof verification.

Table 10-1 summarizes the two implementation tracks in this chapter.

Table 10-1. Chapter implementation tracks

| Track | What works | What it proves |
|-------|------------|----------------|
| Python-only state machine | Compile/deploy the PuyaPy contract, commit, use the admin hook as a test seam, reveal, tally | Phase logic, box storage, MBR, and commit-reveal correctness |
| Full ZK integration | Complete the Go circuit/verifier, submit the verifier group, bind public inputs in the app | Trustless proof verification plus the state-machine checks |

> **Note:** This chapter covers advanced cryptography. You do not need to understand elliptic curve math to build the voting system --- AlgoPlonk handles the heavy lifting. We explain the concepts so you can reason about what the system *proves* and where its security guarantees come from. If the math feels dense, focus on the architecture (phases, atomic groups, state management) and treat the curve operations as black boxes.

## Part 1: LogicSig Recap --- Why They Are the ZK Engine

This project builds on the LogicSig foundation from Chapter 9. If you skipped that chapter, read at least Part 1 (Logic Signatures) before continuing. Here we recap only the aspects relevant to ZK verification.

The critical property for this chapter is the [opcode budget](https://dev.algorand.co/concepts/smart-contracts/costs-constraints/). Since AVM v10, every transaction in a group contributes 20,000 opcodes to the LogicSig pool, regardless of whether it is signed by a LogicSig. In a group of 8 transactions where one or more carry a LogicSig, the pooled budget is 160,000 opcodes --- enough to verify a BN254 PLONK proof that costs approximately 145,000 opcodes. Smart contracts, at 700 opcodes per app call, would need over 200 calls for the same verification, making them prohibitively expensive.

The LogicSig and smart contract opcode pools are independent. This means we can use LogicSigs for the cryptographic heavy lifting (proof verification) while preserving the full smart contract budget for application logic (recording votes, managing phases, tallying results). This separation is the architectural foundation of the system we are about to build.

For this project, we use LogicSigs in **contract account mode** --- the LogicSig program hash determines the account address. The verifier LogicSig does not need delegated authority; it needs enough pooled LogicSig opcode budget to run the elliptic curve operations. The generated verifier checks the proof and public inputs, but it is still a LogicSig program and must be treated with the Chapter 9 safety checklist. In production, wrap or modify the generated verifier so it also rejects close-to, rekey-to, excessive fees, and unexpected group structure. The wrapper group must also bind the proof inputs to the governance state update. App-side checks help the governance app reject bad groups, but they do not protect the LogicSig account from standalone misuse if it is ever funded.

> **Note: Python-Only Track.** Without the Go toolchain, you can still test the contract state machine by using the admin-trusted proof hook as a test seam. That path does not test trustless ZK verification.

## Part 2: The AVM's Cryptographic Toolkit

### Native Elliptic Curve Opcodes (AVM v10+)

The AVM provides native support for two pairing-friendly elliptic curve families. (See [Cryptographic Tools](https://dev.algorand.co/concepts/smart-contracts/cryptographic-tools/) and the [opcodes reference](https://dev.algorand.co/reference/algorand-teal/opcodes/) for complete specifications.)

**BN254** (also called alt_bn128 or bn256): The curve used by Ethereum's precompiles, Zcash's original ceremony, and most existing Groth16 deployments. Points in G1 are 64 bytes, G2 are 128 bytes. Verification is cheaper on BN254 than BLS12-381.

**BLS12-381**: The curve used by Ethereum 2.0, Zcash Sapling, and most modern ZK systems. Provides higher security margins than BN254 (~128-bit, versus BN254's roughly 100 bits after the 2016 Kim--Barbulescu exTNFS attack on pairing-friendly curves). Points in G1 are 96 bytes, G2 are 192 bytes.

The available opcodes:

| Opcode | Cost (BN254 G1) | Description |
|--------|-----------------|-------------|
| `ec_add` | 125 | Point addition: P + Q |
| `ec_scalar_mul` | 1,810 | Scalar multiplication: sP |
| `ec_multi_scalar_mul` | 3,600 + 90 per 32B of scalar | Multi-scalar: s₁P₁ + s₂P₂ + ... |
| `ec_pairing_check` | 8,000 + 7,400 per 64B of B | Pairing verification: e(A,B) = 1? |
| `ec_subgroup_check` | 20 | Verify point is in prime-order subgroup |
| `ec_map_to` | 630 | Hash-to-curve mapping |
| `mimc` | 10 + 550 per 32B of input | MiMC hash (AVM v11+; ZK-friendly, known collisions outside ZK) |

The `ec_*` opcodes shipped in AVM v10; `mimc` arrived a version later, in AVM v11 (go-algorand 4.0, January 2025).

The `ec_pairing_check` opcode is the workhorse for SNARK verification. A Groth16 verification requires checking:

```
e(A, B) · e(-vk_α, vk_β) · e(-∑(pub_i · vk_i), vk_γ) · e(-C, vk_δ) = 1
```

This is a single pairing check with 4 pairs, which `ec_pairing_check` handles natively.

### MiMC: the ZK-Friendly Hash

The AVM includes a native `mimc` opcode --- a hash function designed specifically for efficient evaluation inside ZK circuits. MiMC has **known collisions** for inputs that are multiples of the elliptic curve modulus, so it is NOT a general-purpose hash function. It exists solely for ZK applications where the hash must be efficiently provable in a SNARK/PLONK circuit.

For our governance voting system, MiMC is used in two places. The ZK circuit proves that a private `choice` and `randomness` produce the public commitment, and the PLONK verifier checks that proof. Later, during reveal, the PuyaPy app recomputes the same MiMC commitment with `op.mimc()` and compares it with the stored commitment.

> **Client-side MiMC computation.** The AVM provides a native `op.mimc()` opcode, but there is no standard Python library for computing MiMC hashes with the BN254Mp110 configuration. To test the commit-reveal flow, you need a client-side MiMC implementation that matches the AVM's output. Options: (1) use the Go gnark-crypto library's `mimc.NewMiMC()` from a Go test harness, (2) use AlgoPlonk's Go utilities which include compatible MiMC, or (3) compute the commitment on-chain via a `simulate` call and capture the result. Option 3 is the simplest approach: build a helper contract with a single method that takes `choice` and `randomness`, computes `op.mimc(MiMCConfigurations.BN254Mp110, ...)`, and returns the hash. Call it via `simulate` (no fees, no state changes) to get the commitment value for your tests.


## Part 3: Zero-Knowledge Proofs --- From Theory to Algorand

### What Zero-Knowledge Proofs Actually Prove

A zero-knowledge proof lets you convince someone that a statement is true without revealing why it's true. On Algorand, ZK proofs are verified using the AVM's native [cryptographic tools](https://dev.algorand.co/concepts/smart-contracts/cryptographic-tools/) --- elliptic curve opcodes on BN254 and BLS12-381. More precisely, a ZK proof system has three properties:

**Completeness:** If the statement is true and the prover is honest, the verifier will be convinced.

**Soundness:** If the statement is false, no cheating prover can convince the verifier (except with negligible probability).

**Zero-knowledge:** The verifier learns nothing beyond the truth of the statement. The proof itself reveals no information about the witness (the secret knowledge).

For our voting system, the statement is: "I cast a vote that is one of the valid choices (e.g., 0, 1, or 2) and my commitment hash is correctly computed." The witness (secret) is: which choice I actually made and the randomness I used in the commitment. The verifier learns: the vote is valid and the commitment is correct. The verifier does NOT learn: which choice was made.

### The ZK Proof Landscape Relevant to Algorand

**Groth16** --- The most compact proof system (3 group elements; 128 bytes compressed, 256 bytes uncompressed, for BN254). Verification is fast: one pairing check. Requires a **trusted setup per circuit** (toxic waste that must be destroyed). Used by Zcash, Tornado Cash, and most deployed ZK applications. On Algorand, Groth16 verification via pairing checks costs substantially fewer opcodes than PLONK (~30,000-50,000), but requires the per-circuit trusted setup ceremony. PLONK verification costs ~145,000 opcodes on the AVM with BN254 but avoids per-circuit trusted setup.

**PLONK** --- A universal SNARK (one trusted setup works for all circuits up to a size bound). Proofs are slightly larger than Groth16 but the universal setup is a major practical advantage. The **AlgoPlonk** library implements PLONK verification on Algorand using LogicSig verifiers.

**STARKs** --- No trusted setup at all (transparent), post-quantum secure, but proofs are large (tens to hundreds of KB). Too large for efficient on-chain verification on Algorand given the 4KB AVM value limit and opcode budget constraints.

For this project, we'll use **PLONK over BN254** via AlgoPlonk, which provides the best balance of proof size, verification cost, and tooling maturity on Algorand.

### AlgoPlonk: the Bridge From gnark Circuits to Algorand Verification

AlgoPlonk is a Go library that takes a ZK circuit defined in **gnark** (the leading Go ZK framework from ConsenSys), generates a proof off-chain, and produces either a LogicSig or smart contract verifier that validates the proof on-chain.

The workflow:
1. **Define the circuit** in Go using gnark's constraint system
2. **Generate proving and verification keys** via trusted setup
3. **Generate a proof** off-chain for a specific witness
4. **Generate an Algorand verifier** (LogicSig) from the verification key using AlgoPlonk
5. **Submit the proof on-chain** in an atomic group where the LogicSig verifier checks it

A BN254 LogicSig verifier costs **~8 minimum transaction fees** (8 × 20,000 = 160,000 opcodes budget). A BLS12-381 verifier costs ~10 fees. These are paid once per proof verification.


## Part 4: Building the Private Governance Voting System

*Before reading on, consider the design challenge: you need a contract where voters submit secret ballots, but the contract must still enforce that each vote is valid (one of the allowed choices) and that no one votes twice. How would you structure the phases of such a system? What data needs to go on-chain, and what must stay off-chain?*

### System Architecture

The voting system has four phases, using [box storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/) for commitments and [global state](https://dev.algorand.co/concepts/smart-contracts/storage/global/) for phase tracking:

**Phase 1 --- Setup:** The governance admin deploys the voting smart contract, defines the proposal (description, valid choices, voting period), and publishes the ZK circuit's verification key.

**Phase 2 --- Commitment:** Voters compute `commitment = MiMC(choice, randomness)` off-chain and submit the commitment on-chain. The commitment reveals nothing about the vote.

**Phase 3 --- Proof submission:** After the voting period closes, voters submit ZK proofs that their commitment corresponds to a valid choice without revealing which choice. This prevents last-minute vote changes (the commitment is already locked) while proving validity.

**Phase 4 --- Tallying:** Once all proofs are verified, voters reveal their votes with their randomness. The contract verifies each reveal matches its commitment and tallies the results. (Alternatively, with a more advanced circuit, the ZK proof itself can include a homomorphic tally contribution, eliminating the reveal phase entirely.)

### Privacy Scope: Delayed Disclosure, Not Permanent Secrecy

The design in this chapter gives *delayed disclosure*: votes are hidden during the commitment and proof phases, then revealed during tallying. After reveal, each voter's choice and randomness are public, and anyone can recompute the MiMC commitment.

Permanent ballot secrecy requires a different final phase. Common designs move tally contribution into the ZK circuit, use nullifiers to prevent double voting, and reveal only aggregate totals. That is a larger protocol than this chapter implements, so treat the commit-reveal design here as a bridge between ordinary transparent voting and fully private tallying.

### The ZK Circuit: Proving Vote Validity

The circuit proves: "I know a `choice` and `randomness` such that `MiMC(choice, randomness) = commitment` AND `choice ∈ {0, 1, 2}`."

The circuit is defined in Go because gnark (by ConsenSys) is the most mature ZK circuit framework available, and AlgoPlonk is written in Go. If you are unfamiliar with Go, the syntax is close enough to Python that you can follow the logic. The key lines are the `api.AssertIsEqual` constraint declarations --- each one adds a rule that the proof must satisfy. Here is the circuit in gnark:

The following Go code defines the ZK circuit. Save it as `circuit/vote_circuit.go` in a separate Go module (not part of the Python project):

```go
package voting

import (
    "github.com/consensys/gnark/frontend"
    "github.com/consensys/gnark/std/hash/mimc"
)

// VoteCircuit defines the ZK circuit for valid vote proof
type VoteCircuit struct {
    // Public inputs (visible to verifier)
    Commitment frontend.Variable `gnark:",public"`
    NumChoices frontend.Variable `gnark:",public"` // e.g., 3

    // Private inputs (the witness --- known only to prover)
    Choice     frontend.Variable // The actual vote (0, 1, or 2)
    Randomness frontend.Variable // Random blinding factor
}

func (c *VoteCircuit) Define(api frontend.API) error {
    // Constraint 1: commitment = MiMC(choice, randomness)
    // MiMC is natively supported in gnark
    mimc, err := mimc.NewMiMC(api)
    if err != nil {
        return err
    }
    mimc.Write(c.Choice)
    mimc.Write(c.Randomness)
    computed := mimc.Sum()
    api.AssertIsEqual(computed, c.Commitment)

    // Constraint 2: choice is in valid range [0, NumChoices)
    // We prove choice < NumChoices using bit decomposition
    api.AssertIsLessOrEqual(c.Choice, api.Sub(c.NumChoices, 1))

    // Constraint 3: choice >= 0 (implicit in field arithmetic,
    // but we add a range check for safety)
    bits := api.ToBinary(c.Choice, 8) // 8 bits supports up to 255 choices
    recomposed := api.FromBinary(bits...)
    api.AssertIsEqual(recomposed, c.Choice)

    return nil
}
```

This circuit has ~100-200 constraints (PLONK uses a Sparse Constraint System, or SCS, rather than R1CS) --- very small. The MiMC hash dominates the constraint count. Proof generation is near-instant on any modern CPU.

> **Go project setup.** The Go code in this project is separate from the Python smart contract code. AlgoPlonk v0.1.10 --- the version tested for this chapter; newer releases (v0.3.x at review time) exist --- uses Go 1.25 and gnark v0.14. Create a dedicated directory for the ZK components:
>
> ```bash
> mkdir -p zk-voting/{circuit,cmd}
> cd zk-voting
> go mod init zk-voting
> go get github.com/consensys/gnark@v0.14.0
> go get github.com/consensys/gnark-crypto@v0.19.2
> go get github.com/giuliop/algoplonk@v0.1.10
> ```
>
> Save the preceding circuit code as `circuit/vote_circuit.go`. The verifier generator code (shown later in this chapter) goes in `cmd/main.go`. The resulting `go.mod` will look approximately like this (exact versions may differ):
>
> ```
> module zk-voting
>
> go 1.25
>
> require (
>     github.com/consensys/gnark v0.14.0
>     github.com/consensys/gnark-crypto v0.19.2
>     github.com/giuliop/algoplonk v0.1.10
> )
> ```
>
> The `go get` commands populate the `require` block and download dependencies
> automatically. You do not need to write `go.mod` by hand. Before publishing
> production code, pin gnark and gnark-crypto to the versions used by
> AlgoPlonk's own `go.mod`; the Go and gnark versions move together.

### The Voting Smart Contract

The contract uses four phases tracked in global state, with three `BoxMap` instances for commitments, proof status, and tallies. Add the following to `smart_contracts/governance_voting/contract.py`:

```python
from algopy import (
    ARC4Contract, BoxMap, Bytes, Global, GlobalState, OpUpFeeSource,
    Txn, UInt64, arc4, ensure_budget, op, gtxn, urange,
)
from algopy.op import MiMCConfigurations

PHASE_COMMIT = 1
PHASE_PROVE = 2
PHASE_REVEAL = 3
PHASE_TALLY = 4

class GovernanceVoting(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.num_choices = GlobalState(UInt64(0))
        self.commit_end_round = GlobalState(UInt64(0))
        self.prove_end_round = GlobalState(UInt64(0))
        self.phase = GlobalState(UInt64(0))
        self.total_votes = GlobalState(UInt64(0))
        self.verified_proofs = GlobalState(UInt64(0))

        self.commitments = BoxMap(arc4.Address, Bytes, key_prefix=b"c_")
        self.proof_status = BoxMap(arc4.Address, UInt64, key_prefix=b"p_")
        self.tallies = BoxMap(arc4.UInt64, UInt64, key_prefix=b"t_")

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        """Reject update and delete --- this contract is immutable."""
        assert False, "Contract is immutable"
```

The `reject_lifecycle` bare method explicitly rejects `UpdateApplication` and `DeleteApplication` on-completion actions. Without this, the default ARC4Contract routing would reject them anyway (no handler registered), but an explicit rejection with a clear error message is a security best practice --- it makes the contract's immutability self-documenting and auditable.

The `initialize` method sets up the proposal parameters and creates tally boxes for each choice. The loop iterates up to a fixed maximum of 16 and breaks early. The cap is a design choice, not an AVM requirement (dynamic loop bounds are fine on the AVM): every tally box the method creates needs its own box reference and MBR funding from the caller, so a small fixed maximum keeps the box-reference count, the MBR bill, and the opcode budget of `initialize` predictable:

```python
    @arc4.abimethod
    def initialize(
        self,
        num_choices: UInt64,
        commit_duration: UInt64,
        prove_duration: UInt64,
    ) -> None:
        assert Txn.sender == Global.creator_address
        assert self.phase.value == UInt64(0)

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
```

The `commit_vote` method accepts a voter's 32-byte MiMC commitment hash during the commit phase. Each voter can commit only once, and must provide an MBR payment to cover the box storage cost:

```python
    @arc4.abimethod
    def commit_vote(
        self,
        commitment: Bytes,
        mbr_payment: gtxn.PaymentTransaction,
    ) -> None:
        """Submit a vote commitment. commitment = MiMC(choice, randomness)."""
        assert self.phase.value == UInt64(PHASE_COMMIT)
        assert Global.round <= self.commit_end_round.value
        assert commitment.length == UInt64(32), "Commitment must be 32 bytes"

        sender = arc4.Address(Txn.sender)
        assert sender not in self.commitments

        box_cost = UInt64(2500) + UInt64(400) * (UInt64(34) + UInt64(32))
        assert mbr_payment.receiver == Global.current_application_address
        assert mbr_payment.amount >= box_cost

        self.commitments[sender] = commitment
        self.total_votes.value += UInt64(1)
```

The `record_verified_proof` method records that a voter's ZK proof was validated. In the following runnable teaching contract, this is deliberately admin-trusted so you can compile and test the Python state machine without completing the Go verifier integration. The production binding requirements immediately after the snippet describe what must replace this trust boundary before deployment:

```python
    @arc4.abimethod
    def advance_to_prove_phase(self) -> None:
        """Transition from commit to prove phase."""
        assert Txn.sender == Global.creator_address
        assert self.phase.value == UInt64(PHASE_COMMIT)
        assert Global.round > self.commit_end_round.value
        self.phase.value = UInt64(PHASE_PROVE)

    @arc4.abimethod
    def record_verified_proof(self, voter: arc4.Address) -> None:
        """Teaching hook for recording an externally verified proof."""
        assert self.phase.value == UInt64(PHASE_PROVE)
        assert Global.round <= self.prove_end_round.value
        assert voter in self.commitments
        assert voter not in self.proof_status

        # TEACHING VERSION: Restrict to admin while the verifier integration
        # remains illustrative. Do not deploy this trust boundary as-is.
        assert Txn.sender == Global.creator_address, "Only admin"

        self.proof_status[voter] = UInt64(1)
        self.verified_proofs.value += UInt64(1)
```

> **Warning: Trust assumption.** In this simplified version, `record_verified_proof` trusts the admin to only call it after verifying the ZK proof off-chain. The admin could mark any voter's proof as verified without actual verification, defeating the purpose of ZK proofs. A production implementation must verify that the expected LogicSig verifier participates in the current atomic group and that the proof's public inputs match the stored commitment and election configuration. See the production binding checklist later in this part before treating this as a trustless voting system.

Table 10-2 groups the production proof-binding checks into two categories.

Table 10-2. Production proof-binding checks

| Category | Binding check | Why it is required |
|----------|---------------|--------------------|
| Verifier participation | Expected verifier address | Proves the group includes the specific LogicSig generated from this circuit's verification key |
| Verifier participation | Hardened verifier wrapper | Ensures the verifier LogicSig itself rejects rekeying and unsafe transaction fields |
| Verifier participation | Exact group shape | Prevents extra or reordered transactions from satisfying one component while changing another |
| Public-input binding | Commitment public input | Ensures the proof verified the commitment already stored for this voter |
| Public-input binding | `num_choices` public input | Ensures the proof used this election's configured choice range |

The generated AlgoPlonk verifier proves a statement about the public inputs it receives. Your application still has to bind those public inputs to on-chain state. One common pattern is to expose the public inputs in transaction fields the app can inspect (for example, app-call arguments or verifier anchor transaction notes), and use a verifier wrapper that also checks those same fields. The smart contract then checks the mirrored values against `self.commitments[voter]` and `self.num_choices.value` before writing `proof_status`.

> **Warning:** The `record_verified_proof` method creates a proof status box (`p_` prefix + 32-byte address = 34-byte key, 8-byte UInt64 value). This costs `2,500 + 400 * (34 + 8) = 19,300 microAlgos` in MBR. The app account must have sufficient Algo to cover this MBR for each voter. Unlike `commit_vote`, which requires a caller-provided MBR payment, the preceding code does not --- either fund the app account with enough Algo before the prove phase begins, or add an `mbr_payment` parameter to `record_verified_proof` as we did for `commit_vote`.

The `reveal_vote` method completes the commit-reveal cycle. The voter provides their original choice and 32-byte randomness, and the contract recomputes the MiMC hash to verify it matches the stored commitment. If valid, the tally is incremented:

```python
    @arc4.abimethod
    def reveal_vote(self, choice: UInt64, randomness: Bytes) -> None:
        """Reveal a vote by providing the preimage of the commitment."""
        # The 64-byte MiMC hash alone costs 1,110 budget units --- more
        # than a single app call's 700. Raise the budget first.
        ensure_budget(UInt64(1200), OpUpFeeSource.GroupCredit)

        assert self.phase.value == UInt64(PHASE_REVEAL)
        assert randomness.length == UInt64(32), "Randomness must be 32 bytes"

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

    @arc4.abimethod
    def advance_to_reveal_phase(self) -> None:
        assert Txn.sender == Global.creator_address
        assert self.phase.value == UInt64(PHASE_PROVE)
        assert Global.round > self.prove_end_round.value
        self.phase.value = UInt64(PHASE_REVEAL)

    @arc4.abimethod(readonly=True)
    def get_tally(self, choice: UInt64) -> UInt64:
        return self.tallies[arc4.UInt64(choice)]
```

> **Warning: `reveal_vote` cannot fit in a single app call's opcode budget.** The `mimc` opcode costs 10 + 550 per 32-byte block, so hashing the 64-byte `choice || randomness` input costs 1,110 budget units --- well beyond the 700-unit budget of one application call. The `ensure_budget(UInt64(1200), OpUpFeeSource.GroupCredit)` call at the top of the method solves this on-chain: the contract issues no-op inner app calls that each add 700 units to the pooled budget, with their fees paid from the group's pooled fee credit (so the caller simply overpays the outer transaction fee). Without it, every reveal fails with a "dynamic cost budget exceeded" error. This is the same opcode budget management pattern as Chapter 8's Pattern 9.

Even with the budget handled, the state machine as written leaves one lifecycle question open.

> **Design gap --- exercise opportunity.** The contract accumulates tallies during the reveal phase but has no `advance_to_tally_phase` method to formally close voting and finalize results. In the current design, the reveal phase remains open indefinitely. As an exercise, add a `PHASE_CLOSED` state (see Exercise 2 below) with an `advance_to_closed_phase` method that transitions from `PHASE_REVEAL` after a configurable duration, prevents further reveals, and emits the final tally via an ARC-28 event.

A related consequence of the phase design concerns voters who drop out midway.

> **Note: Voters who do not prove forfeit their vote.** A voter who submits a commitment during the commit phase but fails to provide a ZK proof during the prove phase cannot reveal their vote --- the `reveal_vote` method requires `proof_status == 1`. Their vote is effectively lost. Additionally, the box storage MBR for their commitment box (`c_` prefix) remains locked in the app account, since no cleanup method exists to delete orphaned commitment boxes. A production system should include an admin-callable cleanup method that can reclaim MBR from unproven commitments after the voting period ends.

MBR planning starts even earlier than the commit phase --- at deployment.

> **Warning: Fund the app account before calling `initialize`.** The `initialize` method creates tally boxes (one per choice). Each tally box costs `2,500 + 400 * (10 + 8) = 9,700 microAlgos` in MBR. For 3 choices, the app account needs at least `3 * 9,700 = 29,100 microAlgos` plus its base MBR of `100,000 microAlgos` before `initialize` is called. Send a payment to the app's address before the `initialize` call, or you will see a "balance below minimum" error.

As with every contract that uses box storage, client-side code must declare which boxes each transaction will access. The voting contract has several methods that touch different boxes, so it is worth listing them all.

> **Warning: Box references are required for every method that touches boxes.** Callers must include box references in their transaction parameters:
>
> - `initialize`: include box references for all tally boxes being created (e.g., `[(app_id, b"t_" + i.to_bytes(8, "big")) for i in range(num_choices)]`)
> - `commit_vote`: include the commitment box reference (`(app_id, b"c_" + sender_address_bytes)`)
> - `record_verified_proof`: include both the commitment box and the proof status box for the voter
> - `reveal_vote`: include the commitment, proof status, and tally box references
> - `get_tally`: include the tally box reference for the queried choice
>
> Forgetting box references produces "box read/write budget exceeded." The typed client generated by `algokit generate client` does NOT automatically add these --- you must specify them manually.
>
> Constructing box references in client code (example for `commit_vote`):
> ```python
> from algosdk import encoding
> voter_bytes = encoding.decode_address(voter.address)
> boxes=[
>     (app_id, b"c_" + voter_bytes),  # commitment box
> ]
> # For reveal_vote, include commitment, proof status, and tally boxes:
> boxes=[
>     (app_id, b"c_" + voter_bytes),
>     (app_id, b"p_" + voter_bytes),
>     (app_id, b"t_" + choice.to_bytes(8, "big")),
> ]
> ```

Finally, a testing note specific to the phase-based design of this contract.

> **LocalNet round advancement:** On LocalNet with on-demand block production, rounds only advance when transactions are submitted. To test phase transitions (which depend on round numbers), you must send dummy transactions (e.g., zero-amount payments) to advance rounds past the commit or prove deadlines.

### The LogicSig ZK Verifier

This is where AlgoPlonk generates the verifier. The following Go code is an
illustrative example of the workflow, not a complete listing. It uses
placeholder variables (`computedCommitment`, `myRandomness`)
that you must replace with concrete values before saving it as `cmd/main.go` in
a Go module separate from the Python project:

```go
package main

import (
    "github.com/consensys/gnark-crypto/ecc"
    ap "github.com/giuliop/algoplonk"
    "github.com/giuliop/algoplonk/setup"
    "github.com/giuliop/algoplonk/testutils"
    "github.com/giuliop/algoplonk/verifier"
)

func main() {
    // 1. Compile the circuit and generate proving/verification keys.
    var circuit VoteCircuit
    compiledCircuit, _ := ap.Compile(
        &circuit,
        ecc.BN254,
        setup.PerpetualPowersOfTauBN254,
    )

    // 2. Generate PuyaPy for a LogicSig verifier, then compile it to TEAL.
    puyaVerifier := "generated/VoteVerifier.py"
    compiledCircuit.WritePuyaPyVerifier(puyaVerifier, verifier.LogicSig)
    testutils.CompileWithPuyaPy(puyaVerifier, "")

    // 3. Create and export a proof for a specific vote.
    assignment := VoteCircuit{
        Commitment: computedCommitment,  // Public
        NumChoices: 3,                    // Public
        Choice:     1,                    // Private --- the actual vote
        Randomness: myRandomness,         // Private --- blinding factor
    }
    verifiedProof, _ := compiledCircuit.Verify(&assignment)
    verifiedProof.ExportProofAndPublicInputs(
        "generated/VoteVerifier.proof",
        "generated/VoteVerifier.public_inputs",
    )

    // 4. Client code submits one app call signed by the verifier LogicSig.
    // The proof and public inputs are app-call arguments 1 and 2.
    // Add the governance proof-recording call in the same atomic group.
}
```

> **Building and running the Go code.** The preceding `cmd/main.go` code is illustrative --- it shows the AlgoPlonk workflow but uses placeholder variables (`computedCommitment`, `myRandomness`, `publicWitness`). To compile and run a working version, you would fill in concrete values and import the circuit package. From the `zk-voting` directory:
>
> ```bash
> # Verify everything compiles (after filling in placeholder values)
> go build ./...
>
> # Run the verifier generator
> go run ./cmd/main.go
> ```
>
> The `go build ./...` command compiles all packages in the module. If you see import errors, run `go mod tidy` to resolve dependency versions. `WritePuyaPyVerifier(..., verifier.LogicSig)` writes the PuyaPy verifier, and `testutils.CompileWithPuyaPy` compiles it to TEAL for use from your Python client.

The generated LogicSig verifier:
- Has a deterministic address (the hash of the verification program)
- Signs an application call transaction
- Reads proof bytes from `Txn.application_args(1)`
- Reads public-input bytes from `Txn.application_args(2)`
- Executes the PLONK verification algorithm using the AVM's `ec_*` opcodes
- Returns true if and only if the proof is valid for the given public inputs
- Needs pooled LogicSig opcode budget, roughly eight transactions for BN254

### The Atomic Group That Ties Everything Together

The full proof submission is a single atomic group:

```text
Transaction Group:
[0] LogicSig-signed call to verifier anchor app       <- ZK verification
[1..6] Companion transactions for LogicSig budget     <- +20,000 each
[7] Voter -> GovernanceVoting.record_verified_proof   <- State update
```

All eight transactions succeed or fail atomically. If the proof is invalid, the verifier LogicSig returns false, the entire group fails, and no state changes occur. If the proof is valid, the governance app call records the verification in the contract's box storage.

The security binding is the part the runnable teaching contract intentionally isolates. The production proof-recording method must verify that the expected LogicSig verifier is present in the group, that the group has the exact expected shape, and that the proof's public inputs match on-chain state. The [LogicSig security guidelines](https://dev.algorand.co/concepts/smart-contracts/logic-sigs/) are directly relevant here: a LogicSig that verifies a cryptographic proof but does not validate how it is grouped with the state update is only half of the system.

Here `make_verify_transactions` is a project helper, not an AlgoPlonk API. It
builds a LogicSig-signed app call to a small verifier anchor app/method, usually
named `verify(proof, public_inputs)`, with ARC-4 encoded proof and public-input
arguments. Then it adds the companion transactions needed for pooled LogicSig
opcode budget.
### Production Verifier Binding Checklist

For a production implementation, store the verifier LogicSig address and verifier target app ID in global state during initialization. Then replace the admin-trusted hook with a method that verifies the exact group layout.

The production method should check:

- The governance app call is at the expected group index.
- `Global.group_size` equals the exact proof-submission group size.
- Transaction 0 is the verifier app call, signed by the expected LogicSig address.
- The verifier LogicSig itself rejects rekeying and other unsafe fields.
- The verifier app call also has `rekey_to == Global.zero_address`.
- The verifier app call targets the expected verifier/dummy app ID.
- The proof bytes are in `Txn.application_args(1)` of the verifier app call.
- The public-input bytes are in `Txn.application_args(2)` of the verifier app call.
- The public inputs decode to the stored commitment and `self.num_choices.value`.
- The padding transactions have the expected type, app ID, fee, and no rekey.

Do not pass independent "commitment" and "num choices" arguments to the governance call and trust them by themselves. The governance app must compare against the same public-input bytes consumed by the verifier LogicSig. AlgoPlonk's generated LogicSig verifier reads proof and public inputs from the second and third application arguments because the first application argument is reserved for the ARC-4 method selector. Decode the public-input bytes according to the encoding emitted by AlgoPlonk, including any ARC-4 array length prefixes.

Do not rely on `verifier_txn.sender == verifier_address` alone. If the verifier contract account was rekeyed earlier, a later transaction from that sender would no longer prove that the verifier LogicSig executed. Wrap or modify the generated verifier so the LogicSig itself rejects `Txn.rekey_to != Global.zero_address`, and avoid accepting verifier accounts whose current authorization state has already been changed.


## Part 5: Advanced Box Storage Patterns for Vote Tracking

### Box Storage Iteration: the On-Chain Enumeration Problem

Boxes are key-value stores with no built-in enumeration. You can read a box if you know its key, but you cannot iterate over all boxes. This is a fundamental constraint for tallying. (See [Algorand Python storage](https://algorandfoundation.github.io/puya/lg-storage.html) for `Box`, `BoxMap`, and raw byte access patterns, and [Algorand Python data structures](https://algorandfoundation.github.io/puya/lg-data-structures.html) for raw `Box` and `BoxMap` patterns.)

**Solution 1: Maintain an explicit index.** Store voter addresses in a separate "index" box as a concatenated byte array. Each address is 32 bytes. A 32KB box can hold 1,024 voter addresses, but touching the whole box requires 32KB of box I/O budget. A single app call provides only 8 box references, so a max-size index needs extra references from other transactions in the group. For a single-call-friendly design, shard the index into smaller boxes (for example, 8KB shards holding 256 voters). This is an illustrative extension that could be added to the voting contract:

```python
# Index box: concatenated 32-byte addresses
from algopy import Box, Bytes

INDEX_BOX_KEY = b"voter_index"
INDEX_BOX_SIZE = 32_768
INDEX_CAPACITY = 1_024
self.voter_count = GlobalState(UInt64(0))

@arc4.abimethod
def commit_vote(self, commitment: Bytes, ...) -> None:
    # ... existing logic ...

    # Append voter address to index
    voter_index = Box(Bytes, key=INDEX_BOX_KEY)
    if not voter_index:
        assert voter_index.create(size=UInt64(INDEX_BOX_SIZE))

    count = self.voter_count.value
    assert count < UInt64(INDEX_CAPACITY), "Index full"
    # Write sender address at offset count * 32
    voter_index.replace(count * UInt64(32), Txn.sender.bytes)
    self.voter_count.value = count + UInt64(1)
```

To read from that packed index, use raw byte access with `Box(Bytes, key=...)`:

```python
from algopy import Box, Bytes

@arc4.abimethod
def read_voter_at_index(self, index: UInt64) -> Bytes:
    voter_index = Box(Bytes, key=b"voter_index")
    # Read 32 bytes at the correct offset
    return voter_index.extract(index * UInt64(32), UInt64(32))
```

Each index slot stores one account's 32-byte public key, not the human-readable address string. The expression `index * 32` selects the start of that slot. Off-chain clients convert between display addresses and raw bytes at the boundary; on-chain code compares the result to another account value's `.bytes`.

Older examples may use `BoxRef`; this book uses `Box(Bytes, key=...)` for the same raw byte operations.

**Solution 2: Off-chain indexing.** For most governance systems, the indexer reads all box storage off-chain and computes tallies client-side. This is the pragmatic approach when the number of voters exceeds what can be efficiently iterated on-chain within opcode budgets.

### Box Size Planning for the Voting Contract

The voting contract uses four kinds of boxes, each with a fixed key and data layout that determines its MBR:

| Box | Key format | Key size | Data | Data size | MBR per box |
|-----|-----------|----------|------|-----------|-------------|
| Commitment | `c_` + address | 34 bytes | MiMC hash | 32 bytes | 2,500 + 400 × 66 = 28,900 μAlgo |
| Proof status | `p_` + address | 34 bytes | uint64 | 8 bytes | 2,500 + 400 × 42 = 19,300 μAlgo |
| Tally | `t_` + uint64 | 10 bytes | uint64 | 8 bytes | 2,500 + 400 × 18 = 9,700 μAlgo |
| Voter index | `voter_index` | 11 bytes | addresses | 32,768 bytes | 2,500 + 400 × 32,779 = 13,114,100 μAlgo |

The voter-index box is a one-time MBR cost only if you add the explicit-index extension. The app account or admin must fund it before the first indexed commit.

Each voter costs ~48,200 μAlgo in MBR (commitment box: 28,900 + proof status box: 19,300), paid by the voter via the MBR payment pattern from the AMM chapter. The `commit_vote` method requires MBR for the commitment box (28,900 μAlgo), and `record_verified_proof` creates the proof status box requiring an additional 19,300 μAlgo. In test code, ensure the app account is funded for both boxes before calling these methods.


## Part 6: Algorand's Post-Quantum Security --- Falcon and State Proofs

*Before reading on, consider: the ZK proofs in this chapter use BN254, an elliptic curve scheme. What happens to these proofs --- and to Algorand's Ed25519 transaction signatures --- when large-scale quantum computers arrive? Does your voting system need to be redesigned, or is there a way to layer post-quantum security on top?*

### Why Post-Quantum Matters for Blockchain

Every Algorand transaction today is signed with Ed25519, an elliptic curve scheme. Shor's algorithm, running on a sufficiently powerful quantum computer, can solve the discrete logarithm problem that Ed25519's security depends on. This means a quantum adversary could forge signatures, steal funds, and rewrite transaction histories.

The timeline is uncertain --- estimates range from 10 to 30+ years for a cryptographically relevant quantum computer --- but blockchains are designed to operate for decades. The "harvest now, decrypt later" threat is already real: an adversary can record today's signed transactions and break them later when quantum computers exist. For a system that needs to be trustworthy for the lifetime of the data it secures, post-quantum preparation is engineering prudence, not speculation.

### What Is Falcon?

Falcon (Fast Fourier Lattice-based Compact Signatures over NTRU) is one of the post-quantum digital signature algorithms NIST selected for standardization in 2022; its formal standard (FN-DSA, FIPS 206) was still forthcoming as of this writing. It was developed by Pierre-Alain Fouque, Jeffrey Hoffstein, Paul Kirchner, Vadim Lyubashevsky, Thomas Pornin, Thomas Prest, Thomas Ricosset, Gregor Seiler, William Whyte, and Zhenfei Zhang.

Falcon's security is based on the hardness of the **Short Integer Solution (SIS)** problem over NTRU lattices. Unlike the discrete logarithm and factoring problems that Shor's algorithm breaks, lattice problems have no known efficient quantum algorithms. The best known quantum attacks against lattices provide only modest speedups over classical attacks --- nothing like the exponential speedup Shor gives for ECC.

Key properties that make Falcon suitable for Algorand:

**Compact signatures:** Falcon-512 produces ~666-byte signatures (NIST Level 1, ~128-bit security). Falcon-1024 produces ~1,280-byte signatures (NIST Level 5, ~256-bit security). These are small for post-quantum schemes --- Dilithium signatures are ~2.4–4.6KB by comparison.

**Fast verification:** Verification requires only a few FFT (Fast Fourier Transform) operations over small polynomials, making it fast even on constrained hardware. This aligns with Algorand's need to verify thousands of signatures per second during consensus.

**Deterministic signing mode:** Algorand's implementation uses a deterministic signing mode (developed by David Lazar and Chris Peikert), meaning signing the same message with the same key always produces the same signature. This eliminates a class of side-channel attacks related to randomness quality.

The Algorand connection runs deep: Chris Peikert (CSO, Algorand Foundation; formerly Head of Cryptography, Algorand Technologies) and Craig Gentry (former Algorand Foundation research fellow) co-authored the foundational GPV framework (Gentry-Peikert-Vaikuntanathan, 2008) that Falcon is built on.

### How Algorand Uses Falcon Today: State Proofs

State Proofs are Algorand's mechanism for trustless cross-chain communication. (See [State Proofs](https://dev.algorand.co/concepts/protocol/state-proofs/).) Every 256 rounds (~12 minutes), the network produces a **State Proof**: a compact cryptographic certificate attesting to all transactions that occurred during that interval. State Proofs are signed by participation nodes holding a supermajority of online stake.

The key innovation: State Proof signatures use **Falcon-1024**, not Ed25519. This means the chain of State Proofs --- the authenticated history of every transaction on Algorand --- is quantum-secure today, even though regular transaction signatures still use Ed25519.

The architecture:

1. **Participation key generation:** When a node registers for consensus, it generates both Ed25519 participation keys (for voting) and Falcon-1024 keys (for State Proofs). The Falcon key's Merkle root (the `sprfkey` field) is registered on-chain.

2. **Signature collection:** After each 256-round interval, participating nodes sign the interval's transaction commitment using their Falcon keys.

3. **Proof aggregation:** The individual Falcon signatures are aggregated into a compact certificate using a Merkle tree committed with **SumHash512** --- a subset-sum based hash function chosen for its ZK-SNARK friendliness (it's more efficient to prove in a circuit than SHA-256).

4. **On-chain attestation:** The State Proof transaction (containing the proof and the message it attests to) goes through regular consensus and is written to the chain.

5. **External verification:** A light client on another chain (Ethereum, for example) can verify the State Proof using only the Falcon verification algorithm and the Merkle root --- no trust in intermediaries required.

This is why Algorand claims its **history is already quantum-secure**: even if someone breaks Ed25519 in the future, the chain of State Proofs (signed with quantum-resistant Falcon) still authenticates every past transaction. The attacker could potentially forge new Ed25519 transactions, but they cannot rewrite the State Proof-attested history.

### The Path to Fully Quantum-Secure Transactions

Algorand has demonstrated Falcon-signed transactions on MainNet using LogicSigs as the authorization mechanism. The approach:

1. Generate a Falcon-1024 keypair off-chain
2. Create a LogicSig program that verifies a Falcon signature against the user's Falcon public key
3. The LogicSig's contract account address becomes the user's "quantum-safe" address
4. Transactions from this address are authorized by the LogicSig, which verifies the Falcon signature passed as an argument

The AVM opcode `falcon_verify` (shipped in AVM v12, September 2025) makes Falcon verification native at a cost of 1,700 opcodes. The first Falcon-signed transaction on Algorand MainNet was executed on November 3, 2025, using a LogicSig-based Falcon account.

The full post-quantum transition roadmap involves:

1. **History protection (done):** State Proofs with Falcon-1024
2. **Transaction protection (done):** Falcon-based LogicSig accounts using the native `falcon_verify` opcode (AVM v12). First MainNet transaction: November 3, 2025.
3. **Consensus protection (research):** Replace the Ed25519-based VRF with a post-quantum VRF. Active research includes ZKBoo/ZKB++ based constructions and lattice-based VRF proposals.

### Implications for Our Voting System

Our governance voting system uses BN254 elliptic curves for ZK proofs. BN254 is NOT post-quantum secure --- a quantum computer running Shor's algorithm could break it. This means:

- **The vote commitments (MiMC hashes) are quantum-safe** --- hash functions are resistant to quantum attacks (Grover's algorithm provides only a quadratic speedup, manageable with larger hash sizes).
- **The ZK proofs themselves are NOT quantum-safe** --- the elliptic curve pairing used for PLONK/Groth16 verification is vulnerable to Shor's algorithm.
- **The vote reveals are quantum-safe** --- they're just preimage demonstrations against the MiMC hash.

For a production system that needs to be quantum-resistant end-to-end, you would need to replace the pairing-based ZK proofs with **ZK-STARKs** (which use hash functions instead of elliptic curves and are quantum-resistant). STARKs produce larger proofs, making on-chain verification more expensive, but they eliminate the quantum vulnerability entirely. This is an active area of research for all blockchain ZK systems.


## Part 7: Testing the Complete System

### Testing Without the Go Toolchain

If you cannot install the Go toolchain (gnark, AlgoPlonk), you can still test the voting contract's core flow: deploy, initialize, commit votes, advance phases, and reveal votes. The commit-reveal cycle verifies commitments against MiMC hashes without needing ZK proofs.

Use the admin-trusted hook as a test-only seam before reveal. This exercises the state machine; trustless verification starts with the verifier-group integration test.

### Test Scenario: Python-Only State Machine

This scenario exercises the full commit-prove-reveal-tally lifecycle without touching the Go toolchain.

> **Note:** The following tests are structural outlines showing *what* to test and *how* to assert. The helper functions (`deploy_voting_contract`, `generate_random_scalar`, `mimc_hash`, `fund_mbr`, `advance_rounds`, etc.) are project-specific wrappers around the [AlgoKit Utils](https://dev.algorand.co/algokit/utils/python/testing/) calls shown earlier in this chapter --- implement them using the deployment and interaction patterns demonstrated in the preceding sections. The patterns here --- lifecycle tests, failure-path tests, invariant tests --- are the ones you should implement for any production contract.

The following outline belongs in `tests/test_governance_voting.py` after you
implement the preceding helper functions (not part of the contract code).

The Python-only state-machine test covers commit, admin proof marking, reveal, and tally reads with three voters. It verifies commitments, proof-status gating, reveals, and tallies, but it does not verify ZK proofs:

```python
# test_governance_voting.py
import pytest
import algokit_utils

class TestGovernanceVoting:
    def test_python_state_machine_flow(self):
        """Python-only: commit -> admin proof mark -> reveal -> tally."""
        algorand = algokit_utils.AlgorandClient.default_localnet()
        admin = algorand.account.localnet_dispenser()
        voting_client = deploy_voting_contract(algorand, admin)
        voting_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="initialize", args=[3, 100, 100],
            )
        )

        voters = [algorand.account.random() for _ in range(3)]
        choices = [0, 1, 2]
        randomness = [generate_random_scalar() for _ in range(3)]
        commitments = [
            mimc_hash(choice, rand) for choice, rand in zip(choices, randomness)
        ]

        # Phase 1: Submit commitments
        for voter, commitment in zip(voters, commitments):
            voting_client.send.call(
                algokit_utils.AppClientMethodCallParams(
                    method="commit_vote",
                    args=[commitment, fund_mbr(voter, voting_client)],
                    sender=voter.address,
                )
            )

        # Phase 2: Mark proofs through the admin-trusted teaching hook.
        # This is not the trustless ZK verifier path.
        advance_rounds(algorand, 101)
        voting_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="advance_to_prove_phase",
            )
        )
        for voter in voters:
            voting_client.send.call(
                algokit_utils.AppClientMethodCallParams(
                    method="record_verified_proof",
                    args=[voter.address],
                )
            )

        # Phase 3: Reveal votes and check tallies
        advance_rounds(algorand, 101)
        voting_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="advance_to_reveal_phase",
            )
        )
        for voter, choice, rand in zip(voters, choices, randomness):
            voting_client.send.call(
                algokit_utils.AppClientMethodCallParams(
                    method="reveal_vote",
                    args=[choice, rand],
                    sender=voter.address,
                )
            )

        tally_0 = voting_client.send.call(
            algokit_utils.AppClientMethodCallParams(method="get_tally", args=[0])
        )
        tally_1 = voting_client.send.call(
            algokit_utils.AppClientMethodCallParams(method="get_tally", args=[1])
        )
        tally_2 = voting_client.send.call(
            algokit_utils.AppClientMethodCallParams(method="get_tally", args=[2])
        )
        assert tally_0.abi_return == 1
        assert tally_1.abi_return == 1
        assert tally_2.abi_return == 1
```

### Full ZK Integration Test Outline

After you complete the Go verifier and production binding method, add a separate integration test for the trustless proof path:

```python
def test_bound_verifier_group_records_proof(self):
    """Full integration: verifier group + bound app proof record."""
    # Setup mirrors the Python-only test through the commit phase.
    proof = generate_vote_proof(choice, randomness, commitment, num_choices=3)
    public_inputs = encode_public_inputs(commitment, num_choices=3)
    verify_group = build_algoplonk_verifier_group(
        verifier_lsig,
        verifier_app_id,
        proof,
        public_inputs,
    )
    record_params = voting_client.params.call(
        algokit_utils.AppClientMethodCallParams(
            method="record_bound_proof",
            args=[voter.address],
        )
    )
    submit_atomic_group(verify_group + [record_params])
```

That integration test should also include failure cases: wrong verifier address, extra transaction in the group, mismatched commitment public input, and mismatched `num_choices` public input.

The full ZK integration suite should also keep the circuit-level invalid proof test. It confirms that the ZK circuit rejects out-of-range choices before a verifier group is submitted:

```python
    def test_invalid_proof_rejected(self):
        """A proof for a choice outside valid range must fail."""
        admin = algorand.account.localnet_dispenser()
        voting_client = deploy_voting_contract(algorand, admin)
        call_method(voting_client, "initialize", [3, 100, 100])
        voter = algorand.account.random()
        bad_choice = 5
        rand = generate_random_scalar()
        commitment = mimc_hash(bad_choice, rand)
        # Commit succeeds (commitment is just a hash --- validity is proven later)
        call_method(voting_client, "commit_vote",
                    [commitment, fund_mbr(voter, voting_client)])
        advance_rounds(algorand, 101)
        call_method(voting_client, "advance_to_prove_phase", [])
        # Proof generation should fail: circuit rejects choice >= num_choices
        with pytest.raises(Exception):
            generate_vote_proof(bad_choice, rand, commitment, num_choices=3)
```

The remaining failure-path tests verify that invalid state-machine operations are correctly rejected. The double commit test ensures one-vote-per-voter:

```python
    def test_double_commit_rejected(self):
        """Same voter cannot commit twice."""
        admin = algorand.account.localnet_dispenser()
        voting_client = deploy_voting_contract(algorand, admin)
        call_method(voting_client, "initialize", [3, 100, 100])
        voter = algorand.account.random()
        rand = generate_random_scalar()
        commitment = mimc_hash(1, rand)
        call_method(voting_client, "commit_vote",
                    [commitment, fund_mbr(voter, voting_client)])
        rand2 = generate_random_scalar()
        commitment2 = mimc_hash(2, rand2)
        with pytest.raises(Exception):
            call_method(voting_client, "commit_vote",
                        [commitment2, fund_mbr(voter, voting_client)])
```

The reveal and timing tests verify the commit-reveal binding (revealing a different choice than committed must fail) and the phase deadline enforcement (commits after the deadline are rejected):

```python
    def test_reveal_must_match_commitment(self):
        """Revealing a different choice than committed fails."""
        admin = algorand.account.localnet_dispenser()
        voting_client = deploy_voting_contract(algorand, admin)
        call_method(voting_client, "initialize", [3, 100, 100])
        voter = algorand.account.random()
        rand = generate_random_scalar()
        commitment = mimc_hash(1, rand)
        call_method(voting_client, "commit_vote",
                    [commitment, fund_mbr(voter, voting_client)])
        advance_rounds(algorand, 201)
        call_method(voting_client, "advance_to_reveal_phase", [])
        with pytest.raises(Exception):
            call_method(voting_client, "reveal_vote", [2, rand],
                        sender=voter.address)

    def test_commitment_after_deadline_rejected(self):
        """Commits after the commit period are rejected."""
        admin = algorand.account.localnet_dispenser()
        voting_client = deploy_voting_contract(algorand, admin)
        call_method(voting_client, "initialize", [3, 50, 100])
        advance_rounds(algorand, 51)
        voter = algorand.account.random()
        rand = generate_random_scalar()
        commitment = mimc_hash(0, rand)
        with pytest.raises(Exception):
            call_method(voting_client, "commit_vote",
                        [commitment, fund_mbr(voter, voting_client)])
```

### Security Audit Checklist for the Voting System

The runnable PuyaPy contract covers the state-machine checks. The ZK verifier checks are production requirements for replacing the admin-trusted teaching hook:

- Commitments are binding (MiMC collision resistance within the field)
- Commitments are hiding (randomness is cryptographically random, 256-bit)
- Double-voting is prevented (one commitment per address)
- Vote changes after commitment are prevented (phase transitions are irreversible)
- Box storage MBR funding requirements are identified; cleanup/refund paths are production hardening
- Phase transitions check round numbers correctly and are admin-only

Production verifier hardening before deployment:

- ZK proofs cannot be forged (PLONK soundness)
- ZK proofs reveal nothing about the vote during the prove phase (zero-knowledge property)
- LogicSig verifier address is hardcoded/verified in the smart contract
- Public inputs to the ZK proof are bound to on-chain state (commitment, num_choices)
- Group size is validated in the proof-submission atomic group
- Admin cannot mark proofs verified without the verifier group
- The trusted setup ceremony is properly conducted (for PLONK, a universal setup from a ceremony)

## Summary

In this chapter you learned to:

- Explain the three properties of zero-knowledge proofs (completeness, soundness, zero-knowledge) and why each matters for private voting
- Describe the commit-reveal pattern and how it provides delayed vote disclosure on a public blockchain
- Use the AVM's native elliptic curve opcodes (BN254) for on-chain cryptographic verification
- Explain why MiMC is used inside ZK circuits instead of SHA-256, and the security tradeoffs involved
- Design a ZK circuit using gnark/AlgoPlonk that proves a vote is valid without revealing which choice was selected during the prove phase
- Build a multi-phase voting smart contract with registration, commitment, reveal, and tallying phases
- Use LogicSig opcode pooling (20,000 opcodes per group transaction, since AVM v10) to verify ZK proofs on-chain
- Describe Algorand's Falcon-based post-quantum security roadmap and its implications for long-term cryptographic design

| Component | Status | Concepts Introduced |
|-----------|--------|---------------------|
| ZK circuit (gnark) | Illustrative until completed in Go | Groth16/PLONK proof systems, SCS, witness generation |
| MiMC commitments | Runnable in the PuyaPy contract | ZK-friendly hashing, commitment schemes |
| Voting smart contract | Runnable PuyaPy state machine | Multi-phase state machine, box-based vote tracking, tally accumulation |
| LogicSig ZK verifier | Illustrative AlgoPlonk integration | BN254 curve operations, pairing checks, opcode budget pooling |
| Atomic verification group | Production sketch | Coordinating LogicSig verification with smart contract state updates |
| Post-quantum discussion | Conceptual | Falcon signatures, state proofs, hash-based commitments |

## Exercises

1. **(Recall)** What are the three properties of a zero-knowledge proof? Which one ensures the verifier learns nothing about which choice the voter selected?

2. **(Apply)** The voting contract uses a 4-phase system (commit, prove, reveal, tally). Add a `PHASE_CLOSED` state that activates after the reveal phase ends, preventing any further action. What state transitions and checks need to change?

3. **(Analyze)** Why is MiMC used for commitments inside the ZK circuit instead of SHA-256? What are the security tradeoffs of using a less battle-tested hash function?

4. **(Create)** Design an extension where voters can delegate their vote to another address before the commitment phase. What changes to the commitment scheme, ZK circuit, and smart contract are needed? How do you prevent a delegate from learning what vote they are casting?

5. **(Create)** Replace the admin-trusted `record_verified_proof` hook with a bound verifier-group design. Identify the trusted parties you are removing, the exact group shape, where public inputs are exposed, what the app checks, what the verifier checks, and which negative tests prove the binding fails safely.

## Appendix A: Opcode Costs for Cryptographic Operations

Costs from the [AVM opcodes reference](https://dev.algorand.co/reference/algorand-teal/opcodes/).

| Operation | Curve | Cost (opcodes) |
|-----------|-------|----------------|
| ec_add | BN254 G1 | 125 |
| ec_add | BLS12-381 G1 | 205 |
| ec_scalar_mul | BN254 G1 | 1,810 |
| ec_scalar_mul | BLS12-381 G1 | 2,950 |
| ec_multi_scalar_mul | BN254 G1 | 3,600 + 90 per 32B of B |
| ec_multi_scalar_mul | BLS12-381 G1 | 6,500 + 95 per 32B of B |
| ec_pairing_check | BN254 | 8,000 + 7,400 per 64B of B |
| ec_pairing_check | BLS12-381 | 13,000 + 10,000 per 96B of B |
| ec_subgroup_check | BN254 G1 | 20 |
| ec_subgroup_check | BLS12-381 G2 | 2,340 |
| mimc | BN254 | 10 + 550 per 32B of input |
| ed25519verify | --- | 1,900 |
| falcon_verify | --- | 1,700 |

## Appendix B: Key Differences Between Smart Contracts and LogicSigs

See [AVM](https://dev.algorand.co/concepts/smart-contracts/avm/) for the full specification of both execution modes.

| Property | Smart Contract | LogicSig |
|----------|---------------|----------|
| Opcode budget per txn | 700 (pooled) | 20,000 (pooled separately) |
| Max pooled budget | ~190,400 (16 outer × 700 + up to 256 inner × 700) | 320,000 (16 × 20,000; all txns contribute, not just those with LogicSigs) |
| Has state | Yes (global, local, boxes) | No |
| Can issue inner transactions | Yes | No |
| Persistent address | App ID → deterministic address | Program hash → deterministic address |
| Can be updated | If authorized | No (immutable by nature) |
| Modes | Application calls | Contract account OR delegated signature |
| Can read boxes | Yes | No |
| Can access other apps' state | Yes (with references) | No |
| Primary use case | Stateful dApps | ZK verification, delegation, specialized escrow |

## Appendix C: Resources

| Resource | URL |
|----------|-----|
| AlgoPlonk (ZK on Algorand) | [github.com/giuliop/AlgoPlonk](https://github.com/giuliop/AlgoPlonk) |
| gnark (ZK circuit framework) | [github.com/ConsenSys/gnark](https://github.com/ConsenSys/gnark) |
| Cryptographic Tools | [dev.algorand.co/concepts/smart-contracts/cryptographic-tools/](https://dev.algorand.co/concepts/smart-contracts/cryptographic-tools/) |
| AVM Opcodes Reference | [dev.algorand.co/reference/algorand-teal/opcodes/](https://dev.algorand.co/reference/algorand-teal/opcodes/) |
| State Proofs | [dev.algorand.co/concepts/protocol/state-proofs/](https://dev.algorand.co/concepts/protocol/state-proofs/) |
| Falcon CLI tool | [github.com/algorandfoundation/falcon-signatures](https://github.com/algorandfoundation/falcon-signatures) |
| Algorand Post-Quantum | [algorand.co/technology/post-quantum](https://algorand.co/technology/post-quantum) |
| Falcon Technical Brief | algorand.co/blog/technical-brief-quantum-resistant-transactions |
| LogicSig Concepts and Security Considerations | [dev.algorand.co/concepts/smart-contracts/logic-sigs/](https://dev.algorand.co/concepts/smart-contracts/logic-sigs/) |
| Building Secure Contracts (Algorand) | secure-contracts.com/not-so-smart-contracts/algorand/ |
| MiMC Hash Specification | eprint.iacr.org/2016/492 |
| PLONK Paper | eprint.iacr.org/2019/953 |
| Groth16 Paper | eprint.iacr.org/2016/260 |
