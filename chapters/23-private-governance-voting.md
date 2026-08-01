\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Project}}
```
# Private Governance Voting with Zero-Knowledge Proofs

Your DAO needs to hold a vote, but the community demands ballot secrecy: no one should be able to see how anyone voted until results are final. On a public blockchain where all state is readable, this seems impossible. Zero-knowledge proofs make it possible.

This project builds the on-chain state machine for a privacy-preserving governance voting system, and the verifier group that proves each ballot is valid without revealing its choice during the voting period. It spends the primitives Chapter 22 priced --- the pairing check and the group budget that affords it, the MiMC hash, the commitment scheme --- and adds the advanced box storage patterns that track votes.

::: {.spec title="Your commission: a ballot that stays sealed until the count"}
Build the on-chain side of a private governance vote, in four phases. It ships when:

1. A voter can commit to a ballot during the commit phase without the chain learning the choice.
2. During the prove phase, every sealed ballot is shown valid --- one of the allowed choices --- by a proof that reveals nothing else.
3. The contract records a proof only on the evidence of the group that verified it, about the committing voter's own ballot.
4. The reveal phase opens the count: each reveal must match its commitment, and each voter tallies exactly once.
5. The privacy scope is stated honestly: disclosure is delayed until reveal, not permanent.
:::

## Run It First
The finished system for this chapter is in `projects/governance-voting/`, and it ships with a real proof rather than a placeholder --- AlgoPlonk embeds the Perpetual Powers of Tau BN254 ceremony key, so the setup is genuine and runs offline. The committed artifacts mean you can run the whole vote, including the proof, without a Go toolchain; Go is needed only to change the circuit or prove a different ballot. Before running it, predict how many transactions the verification group needs, and what the seven other transactions are doing while one of them verifies a proof.

```bash
cd projects/governance-voting
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_governance_voting
algokit project run test
```

Table 23-1 lists the output checkpoints to compare against the workflow output.

: Table 23-1. Output checkpoints for the private voting workflow

| Output checkpoint | What to watch for |
|-------------------|-------------------|
| Verifier LogicSig size | 3,464 assembled bytes of generated verifier |
| Commitment registered | The voter is eligible without the contract knowing how they will vote |
| Group size on the verifying call | Eight transactions, of which one carries the proof |
| LogicSig budget consumed | About 143,000 units against the 160,000 that eight transactions pool |
| Tally after three reveals | One vote per choice, with no link from any vote back to a voter |

Seven of those eight transactions do nothing. They are there because the opcode budget pools across the group at 20,000 units per transaction, and one pairing check does not fit in one transaction's share --- which Example 22-9 prices exactly.

The first row is a measurement of one build, not a property of the circuit. The committed `VoteVerifier.teal` was compiled by puyapy 5.9.0; the toolchain this book pins is 5.8.1, and it assembles the same AlgoPlonk source to 3,483 bytes. Both verify the same proof, and each produces a *different* program hash, which is the LogicSig's address. That is why the project commits the TEAL rather than rebuilding it: recompiling moves the verifier's address, and an election bound to the old one stops accepting proofs until its admin rebinds it.

## What You Need First

Chapter 22 ended with a Handoff table naming what this project would lean on; Table 23-2 is the other side of it. Every row is a primitive already priced --- this chapter is where each one is paid for rather than described. Use the table now, to see what the system is made of before any of it is in front of you, and later, when a line assumes something you would rather look up than reconstruct.

Answer the predict column before you follow the link.

: Table 23-2. What Chapter 22 built that this project spends

| Prerequisite | Where it lands here | Predict before you read it |
|--------------|---------------------|----------------------------|
| Example 22-9 | The generated verifier LogicSig and the eight-transaction group it travels in | The verifier measures about 143,000 units and one program has 20,000. Work out the smallest group that affords it, and say what the companion transactions carry. |
| Example 22-5 | Nowhere in the runnable contract: eligibility here is one commitment per address, and the register gate is left open --- Exercise 6 restores it | Membership can be proven without identity. Say what this chapter's commitment box key reveals about the voter anyway, and what that bounds the privacy to. |
| Example 18-2 | `commit_vote` and `reveal_vote`, the same commit-reveal cycle with a different hash | Say why no tally can start until commitments close, and what a voter who commits and never reveals forfeits. |
| Example 22-8 | The commitment inside the ZK circuit, and its recomputation in `reveal_vote` | MiMC costs 1,110 units for this chapter's 64-byte input against an application call's 700. Name the mechanism that covers the difference, and who funds it. |
| Example 22-7 | The scalar multiplications and pairing check inside the generated verifier | The verifier is a fixed routine generated from one circuit's verification key. Say what has to be regenerated when the circuit changes, and what that does to the verifier's address. |

## What Runs and What You Complete

Nothing in the transcript you just ran was mocked. A real PLONK proof, generated from a real circuit against a real ceremony key, was verified on chain by the generated LogicSig, and a smart contract compared that proof's public inputs against the commitment already sitting in its box storage before it would record anything. Table 23-3 splits the system by component, so that "you need Go for this part" lands on the one thing it is true of.

: Table 23-3. What runs from the repository, and what needs Go

| Component | What ran when you did | What changing it takes |
|-----------|-----------------------|------------------------|
| The vote circuit | Its compiled constraint system and keys are committed; the proof you submitted was generated from them | Go and gnark, then a rebind of every live election |
| The verifier LogicSig | Signed transaction 0 and verified the proof, spending about 143,000 pooled units | Regenerated with the circuit; its address is its program hash |
| The proof and public inputs | Committed, and submitted as arguments 1 and 2 of the anchor call | Go, to prove a different ballot |
| The voting contract | Deployed, took three commitments, bound one proof, tallied three reveals | puyapy --- it is the file you write in this chapter |
| The commitment helper | Simulated, to compute the two commitments the Go prover did not | puyapy |
| The Python client | Assembled the eight-transaction group and read the budget out of a simulate | algokit-utils |

The boundary between the two languages is a directory. Go, through gnark and AlgoPlonk, turns a circuit definition into four files under `zk/generated/`: a constraint system, a proving key, a verifying key, and a verifier program with that verifying key compiled into it. Python never sees the circuit. It reads those files, compiles the verifier to TEAL, and treats the result as an address it can put in a transaction group. That is why a reader with no Go toolchain is not locked out of anything except *changing the statement being proved*.

Two methods in the contract record a verified proof, and the chapter builds both. `record_verified_proof` trusts the admin to have checked the proof somewhere else; it is a seam, and it exists so the state machine can be exercised in one transaction instead of eight. `record_bound_proof` trusts no one: it refuses to write anything unless the verifier LogicSig ran in this group over public inputs that match this contract's own state. Run It First used the bound method for the first voter and the teaching hook for the other two, so the transcript you already have contains both trust boundaries side by side.

What is genuinely left for you is smaller than the list of methods suggests, and it is not the cryptography. The generated verifier proves things about a proof and guards nothing about its own account; the reveal phase never closes; a voter who commits and vanishes strands their box; and any address may commit, because the eligibility register Chapter 22 built is not wired in. The Production Hardening section at the end of the chapter collects those four with the exercises that close them.

You do not need elliptic curve arithmetic to follow any of this. AlgoPlonk generates the verifier; what you have to reason about is which statement it proves, what the group around it costs, and where the proof's public inputs get tied to on-chain state. If the math gets dense, treat the curve operations as priced black boxes --- Chapter 22 is where they were priced --- and keep your attention on the phases, the group, and the state.

## Project Setup

Scaffold a new project for this chapter. The template creates a `hello_world/` contract directory, which you rename:

```bash
algokit init -t python --name governance-voting
cd governance-voting/projects/governance-voting
algokit project bootstrap all
mv smart_contracts/hello_world smart_contracts/governance_voting
```

Your contract code goes in `smart_contracts/governance_voting/contract.py`. Delete the template-generated `deploy_config.py` in the renamed directory; it references the old `HelloWorld` contract.

## Why LogicSigs Are the ZK Engine

This project spends what Part V built and Chapter 22 priced. Chapter 20 taught the LogicSig itself; Chapter 21 put a fleet of them to work and wrote the eight-item security checklist a production verifier must still pass. Nothing about the primitive is new here. What is new is that the budget is the entire point.

The critical property is the [opcode budget](https://dev.algorand.co/concepts/smart-contracts/costs-constraints/) Example 20-11 demonstrated and Example 22-9 priced: since AVM v10, every transaction in a group contributes 20,000 opcodes to the LogicSig pool, regardless of whether it is signed by a LogicSig. In a group of 8 transactions, the pooled budget is 160,000 opcodes, and this chapter's verifier spends about 143,000 of them. A smart contract, at 700 opcodes per application call, would need over two hundred calls for the same verification.

The LogicSig and smart contract opcode pools are independent --- Example 20-11's other lesson --- so LogicSigs can carry the cryptographic heavy lifting (proof verification) while the full smart contract budget stays available for application logic (recording votes, managing phases, tallying results). That separation is the architectural foundation of the system. Table 23-4 is the two budget facts it rests on; Table B-4 in Appendix B sets the two execution modes side by side in full.

: Table 23-4. The two budget rows this chapter spends

| Property | Smart contract | LogicSig |
|----------|----------------|----------|
| Opcode budget per txn | 700 (pooled) | 20,000 (pooled separately) |
| Max pooled budget | ~190,400 (16 outer × 700 + up to 256 inner × 700) | 320,000 (16 × 20,000; all txns contribute, not just those with LogicSigs) |

Chapter 20 ended the budget discussion by saying that which wall a program meets first --- the pooled cost or the pooled size --- depends on its shape. This verifier answers that question. It assembles to 3,464 bytes against a per-program allowance of 1,000, and since AVM v11 that allowance pools too: `len(group) x 1,000` bytes, counted across every program and every argument in the group. Four transactions make the verifier *legal*; eight make it *affordable*. The budget sets the group length, the size limit never binds, and a group one transaction short fails inside `ec_pairing_check` rather than at the size check.

This project uses LogicSigs in **contract account mode**, Example 20-4's binding: the LogicSig program hash determines the account address. The verifier LogicSig does not need delegated authority; it needs enough pooled LogicSig opcode budget to run the elliptic curve operations. The generated verifier checks the proof and the lengths of its two arguments, and nothing else --- no fee bound, no rekey-to check, no group binding --- so as a program it fails Chapter 21's checklist on every line of it. That gap and its consequences are what the rest of this chapter is arranged around: the governance contract defends itself against a verifier account somebody else has taken over, and Exercise 5 closes the hole at its source.

## The Toolkit Chapter 22 Priced

Chapter 22 priced every primitive this project runs on: curve arithmetic in Example 22-7, the MiMC hash in Example 22-8, and the pairing check --- with the group budget that dominates this chapter --- in Example 22-9. Table B-2 in Appendix B is the whole price list on one page. None of it is retaught here. What remains are the two choices those prices force on a voting system: which curve, and which hash.

### BN254, Because Verification Is the Bill

The AVM supports two pairing-friendly curve families, both native since AVM v10. (See [Cryptographic Tools](https://dev.algorand.co/concepts/smart-contracts/cryptographic-tools/) for the full specifications.) **BN254** --- Ethereum's precompile curve, also called alt_bn128 --- has 64-byte G1 points and roughly 100-bit security after the 2016 Kim--Barbulescu exTNFS attack on pairing-friendly curves. **BLS12-381** --- Ethereum 2.0, Zcash Sapling --- has 96-byte G1 points and a full ~128-bit margin, at a higher price for every operation. The difference lands in the group size: a generated BN254 verifier needs about 8 minimum-fee transactions of pooled budget, a BLS12-381 verifier about 10, paid once per proof. This project verifies on BN254. Its proofs gate one ballot in one election, so verification cost wins over security margin; an application whose proofs must stay binding for decades would choose the other way.

### MiMC, Because the Circuit Is the Bill

Example 22-8 priced `mimc` at 10 units plus 550 per 32-byte block --- worse than `sha512_256` for anything on chain --- and showed why it is used anyway: proving a `sha256` preimage inside a circuit takes an enormous constraint system, and proving a MiMC one takes a small one. One caution travels with it: MiMC ([eprint.iacr.org/2016/492](https://eprint.iacr.org/2016/492) is its specification) has **known collisions** for inputs that are multiples of the elliptic curve modulus, so it is a circuit hash, never a general-purpose one.

MiMC is used in two places in the governance voting system. The ZK circuit proves that a private `choice` and `randomness` produce the public commitment, and the PLONK verifier checks that proof. Later, during reveal, the PuyaPy app recomputes the same MiMC commitment with `op.mimc()` and compares it with the stored commitment.

That leaves a gap on the client side, and it is a real one: the AVM has `op.mimc()`, gnark has a MiMC gadget, and Python has neither. A voter has to produce the commitment *before* they can commit, and no standard Python library computes MiMC under the BN254Mp110 configuration. Three ways out: run gnark-crypto's `mimc.NewMiMC()` from a Go harness, use AlgoPlonk's Go utilities, or stop reimplementing the hash and ask the machine that defines it. The project takes the third. `smart_contracts/commitment_helper/contract.py` is one `readonly` method that pads the choice, hashes 64 bytes with `op.mimc`, and returns the digest; algokit-utils answers a `readonly` call by simulating it, so the value costs no fee, no round and no state. The value it returns is the same value `cmd/prove` prints and the same value `reveal_vote` will recompute --- and a test in the project asserts exactly that, because if the three ever disagreed, a proof would verify against a commitment that no reveal could open.


## Zero-Knowledge Proofs, From Theory to Algorand

### What Zero-Knowledge Proofs Actually Prove

A zero-knowledge proof lets you convince someone that a statement is true without revealing why it's true. This is the one piece Chapter 22 did not teach: it priced the arithmetic a verifier is made of, and stopped short of what a proof system builds out of that arithmetic. A ZK proof system has three properties:

**Completeness:** If the statement is true and the prover is honest, the verifier will be convinced.

**Soundness:** If the statement is false, no cheating prover can convince the verifier (except with negligible probability).

**Zero-knowledge:** The verifier learns nothing beyond the truth of the statement. The proof itself reveals no information about the witness (the secret knowledge).

For our voting system, the statement is: "I cast a vote that is one of the valid choices (e.g., 0, 1, or 2) and my commitment hash is correctly computed." The witness (secret) is: which choice I actually made and the randomness I used in the commitment. The verifier learns: the vote is valid and the commitment is correct. The verifier does NOT learn: which choice was made.

### The ZK Proof Landscape Relevant to Algorand

**Groth16** ([eprint.iacr.org/2016/260](https://eprint.iacr.org/2016/260)): the most compact proof system (3 group elements; 128 bytes compressed, 256 bytes uncompressed, for BN254). Verification is one four-pair pairing check --- the product Example 22-9 priced. Requires a **trusted setup per circuit** (toxic waste that must be destroyed). Used by Zcash, Tornado Cash, and most deployed ZK applications. On Algorand, Groth16 verification costs substantially fewer opcodes than PLONK (roughly 30,000 to 50,000 against the 143,000 this chapter's PLONK verifier measures on BN254), but the per-circuit ceremony is the price.

**PLONK** ([eprint.iacr.org/2019/953](https://eprint.iacr.org/2019/953)): a universal SNARK (one trusted setup works for all circuits up to a size bound). Proofs are slightly larger than Groth16 but the universal setup is a major practical advantage. The **AlgoPlonk** library implements PLONK verification on Algorand using LogicSig verifiers.

**STARKs**: no trusted setup at all (transparent), post-quantum secure, but proofs are large (tens to hundreds of KB). Too large for efficient on-chain verification on Algorand given the 4KB AVM value limit and opcode budget constraints.

This project uses **PLONK over BN254** via AlgoPlonk, which gives the best balance of proof size, verification cost, and tooling maturity on Algorand. BN254 pairings, like all elliptic curve cryptography, do not survive a large quantum computer; What's Next maps Algorand's Falcon-based post-quantum architecture, what it already secures, and what it would mean for proofs like these.

### AlgoPlonk: The Bridge From gnark Circuits to Algorand Verification

[AlgoPlonk](https://github.com/giuliop/AlgoPlonk) is a Go library that takes a ZK circuit defined in [gnark](https://github.com/ConsenSys/gnark) (the leading Go ZK framework from ConsenSys), generates a proof off-chain, and produces either a LogicSig or smart contract verifier that validates the proof on-chain.

The workflow:

1. **Define the circuit** in Go using gnark's constraint system
2. **Generate proving and verification keys** via trusted setup
3. **Generate a proof** off-chain for a specific witness
4. **Generate an Algorand verifier** (LogicSig) from the verification key using AlgoPlonk
5. **Submit the proof on-chain** in an atomic group where the LogicSig verifier checks it

The bill for step 5 is the one the BN254 section already itemized: about 8 minimum-fee transactions of pooled budget per BN254 proof.


## Building the Voting System

*Before reading on, consider the design challenge: you need a contract where voters submit secret ballots, but the contract must still enforce that each vote is valid (one of the allowed choices) and that no one votes twice. How would you structure the phases of such a system? What data needs to go on-chain, and what must stay off-chain?*

### System Architecture

The voting system has four phases, using [box storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/) for commitments and [global state](https://dev.algorand.co/concepts/smart-contracts/storage/global/) for phase tracking:

**Phase 1, Setup:** The governance admin deploys the voting smart contract, defines the proposal (description, valid choices, voting period), and publishes the ZK circuit's verification key.

**Phase 2, Commitment:** Voters compute `commitment = MiMC(choice, randomness)` off-chain and submit the commitment on-chain. The commitment reveals nothing about the vote.

**Phase 3, Proof submission:** After the voting period closes, voters submit ZK proofs that their commitment corresponds to a valid choice without revealing which choice. This prevents last-minute vote changes (the commitment is already locked) while proving validity.

**Phase 4, Tallying:** Once all proofs are verified, voters reveal their votes with their randomness. The contract verifies each reveal matches its commitment and tallies the results. (Alternatively, with a more advanced circuit, the ZK proof itself can include a homomorphic tally contribution, eliminating the reveal phase entirely.)

### Privacy Scope: Delayed Disclosure, Not Permanent Secrecy

The design in this chapter gives *delayed disclosure*: votes are hidden during the commitment and proof phases, then revealed during tallying. After reveal, each voter's choice and randomness are public, and anyone can recompute the MiMC commitment.

Permanent ballot secrecy requires a different final phase. Common designs move tally contribution into the ZK circuit, use nullifiers to prevent double voting --- the has-this-claimant-already-claimed problem Chapter 22's Exercise 5 had you solve without a box per claimant --- and reveal only aggregate totals. That is a larger protocol than this chapter implements, so treat the commit-reveal design here as a bridge between ordinary transparent voting and fully private tallying.

### The ZK Circuit: Proving Vote Validity

The circuit proves: "I know a `choice` and `randomness` such that `MiMC(choice, randomness) = commitment` AND `choice ∈ {0, 1, 2}`."

The circuit is defined in Go because gnark (by ConsenSys) is the most mature ZK circuit framework available, and AlgoPlonk is written in Go. If you are unfamiliar with Go, the syntax is close enough to Python that you can follow the logic. The key lines are the `api.AssertIsEqual` constraint declarations; each one adds a rule the proof must satisfy.

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

Compiled to a Sparse Constraint System --- PLONK's form, rather than the R1CS Groth16 uses --- this circuit is **4,102 constraints**, measured. The count is dominated not by the MiMC hash but by `AssertIsLessOrEqual` against a variable bound, which decomposes a full 254-bit field element. Proof generation is still about 73 milliseconds on a modern CPU, so the circuit is small in the way that matters.

::: {.setup}
**Go project setup.** The Go code in this project is separate from the Python smart contract code. AlgoPlonk v0.1.10, the version tested for this chapter, uses Go 1.25 and gnark v0.14; newer releases (v0.3.x at review time) exist. Create a dedicated directory for the ZK components:

```bash
mkdir -p zk/{circuit,cmd/gen-verifier,cmd/prove}
cd zk
go mod init zk-voting
go get github.com/consensys/gnark@v0.14.0
go get github.com/consensys/gnark-crypto@v0.19.2
go get github.com/giuliop/algoplonk@v0.1.10
```

Save the preceding circuit code as `circuit/vote_circuit.go`. The verifier generator shown later in this chapter goes in `cmd/gen-verifier/main.go`, and the prover beside it in `cmd/prove/main.go`. The resulting `go.mod` will look approximately like this (exact versions may differ):

```text
module zk-voting

go 1.25

require (
github.com/consensys/gnark v0.14.0
github.com/consensys/gnark-crypto v0.19.2
github.com/giuliop/algoplonk v0.1.10
)
```

The `go get` commands populate the `require` block and download dependencies
automatically. You do not need to write `go.mod` by hand. Before publishing
production code, pin gnark and gnark-crypto to the versions used by
AlgoPlonk's own `go.mod`; the Go and gnark versions move together.
:::

### The Voting Smart Contract

The contract uses four phases tracked in global state, with three `BoxMap` instances for commitments, proof status, and tallies. Add the following to `smart_contracts/governance_voting/contract.py`:

```python
from algopy import (
    ARC4Contract, BoxMap, Bytes, Global, GlobalState, OnCompleteAction,
    OpUpFeeSource, Txn, UInt64, arc4, ensure_budget, op, gtxn, urange,
)
from algopy.op import MiMCConfigurations

PHASE_COMMIT = 1
PHASE_PROVE = 2
PHASE_REVEAL = 3
PHASE_TALLY = 4

# The proof-submission group: the verifier LogicSig's app call at index 0, six
# padding transactions that carry nothing but their 20,000 units of LogicSig
# budget each, and this contract's call last.
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
```

Nine global values, seven of them integers, and the schema is fixed at creation: an election that later wants a tenth needs a new application, not an upgrade. The `reject_lifecycle` bare method is what makes that stance explicit. Without it the default `ARC4Contract` routing would reject an update anyway, because no handler is registered for one --- but the rejection would be an anonymous `err`, and here it is a sentence an integrator can read.

The `initialize` method sets up the proposal parameters and creates tally boxes for each choice. The loop iterates up to a fixed maximum of 16 and breaks early. The cap is a design choice, not an AVM requirement (dynamic loop bounds are fine on the AVM): every tally box the method creates needs its own box reference and MBR funding from the caller, so a small fixed maximum keeps the box-reference count, the MBR bill, and the opcode budget of `initialize` predictable:

```python
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
```

`set_verifier` names the program that will be allowed to prove things to this election:

```python
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
```

The `commit_vote` method accepts a voter's 32-byte MiMC commitment hash during the commit phase. Each voter can commit only once, and pays for their own commitment box with a grouped payment:

```python
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
```

That `==` is the answer to the question Chapter 19's Exercise 2 asked. A `>=` on a payment that funds a box is safe only when the contract does something with the excess --- refunds it, credits it, lets somebody withdraw it. This contract is immutable, holds no withdrawal path and never will, so the excess would sit in the application account until the chain ends, above a minimum balance nobody can lower. Refusing it costs a voter one retry and costs the system nothing.

Closing the commit phase is one admin call, and the method after it records that a voter's ZK proof was validated. `record_verified_proof` is the seam in this contract: it takes the admin's word for that. Read it as something to be replaced rather than as a design:

```python
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
```

An admin who calls that method has proved nothing. They can mark any voter's proof verified without a proof existing, which is the whole point of the system given away in one line --- and the expense of the cryptography around it does not change that, because the cost of a check is not evidence that it constrains anything. The method earns its place for one reason: it is a single transaction, so the state machine can be exercised without assembling eight. Everything after this point in the chapter is about replacing it.

Table 23-5 is what the replacement has to check, in two groups: that the verifier ran, and that it ran over *this* voter's data.

: Table 23-5. Production proof-binding checks

| Category | Binding check | Why it is required |
|----------|---------------|--------------------|
| Verifier participation | Expected verifier address | Proves the group includes the specific LogicSig generated from this circuit's verification key |
| Verifier participation | Exact group shape | Prevents extra or reordered transactions from satisfying one component while changing another |
| Verifier participation | Verifier not already rekeyed | A LogicSig program stops running for an account the moment that account's authorized address changes |
| Public-input binding | Commitment public input | Ensures the proof verified the commitment already stored for this voter |
| Public-input binding | `num_choices` public input | Ensures the proof used this election's configured choice range |

The generated AlgoPlonk verifier proves a statement about the public inputs it is handed. Nothing in it knows what your application stores, so binding those public inputs to on-chain state is work the application has to do itself, by reading the verifier's transaction fields out of the group and comparing them against its own boxes. Example 23-1 does exactly that, and it is printed a few pages on, after the group it makes assertions about is in front of you.

Recording a proof also hides an operational cost, and both methods that do it hide the same one. Either one creates the proof status box (`p_` prefix + 32-byte address = 34-byte key, 8-byte UInt64 value), which costs `2,500 + 400 * (34 + 8) = 19,300 microAlgos` in MBR --- and unlike `commit_vote` neither takes an MBR payment, so the app account pays for each voter. Fund the app account for the expected electorate before the prove phase begins, or add an `mbr_payment` parameter as `commit_vote` has; Table 23-7 prices every box, and the Production Hardening section returns to this.

The `reveal_vote` method completes the commit-reveal cycle. The voter provides their original choice and 32-byte randomness, and the contract recomputes the MiMC hash to verify it matches the stored commitment. If valid, the tally is incremented:

```python
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

    @arc4.abimethod
    def advance_to_reveal_phase(self) -> None:
        assert Txn.sender == Global.creator_address, "Only admin"
        assert self.phase.value == UInt64(PHASE_PROVE), "Not prove phase"
        assert Global.round > self.prove_end_round.value, "Prove phase still open"
        self.phase.value = UInt64(PHASE_REVEAL)

    @arc4.abimethod(readonly=True)
    def get_tally(self, choice: UInt64) -> UInt64:
        return self.tallies[arc4.UInt64(choice)]
```

::: {.gotcha #mimc-exceeds-one-call-budget topic="Cryptography" title="One mimc hash costs more than an application call's entire budget"}
One `mimc` over 64 bytes costs 1,110 units --- 10 plus 550 per 32-byte block --- and an application call has 700. Any method hashing two field elements must raise its budget before the opcode: `ensure_budget(UInt64(1200), OpUpFeeSource.GroupCredit)` issues no-op inner app calls worth 700 units each, their fees drawn from the group's pooled fee credit, so the caller overpays the outer fee. Without it the call dies with `dynamic cost budget exceeded`. This chapter's instance is `reveal_vote`, whose recomputed `choice || randomness` commitment is exactly such a 64-byte hash.
:::

The state machine as written has no terminal phase.

::: {.tryit}
**Design gap.** The contract accumulates tallies during the reveal phase but has no `advance_to_tally_phase` method to formally close voting and finalize results. In the current design, the reveal phase remains open indefinitely. As an exercise, add a `PHASE_CLOSED` state (see Exercise 1 below) with an `advance_to_closed_phase` method that transitions from `PHASE_REVEAL` after a configurable duration, prevents further reveals, and emits the final tally via an ARC-28 event.
:::

The phase gating also decides what happens to a voter who drops out midway. A voter who commits but never proves cannot reveal --- `reveal_vote` requires `proof_status == 1` --- so their vote is forfeit, and the MBR in their commitment box (`c_` prefix) stays locked in the app account, because no cleanup method exists to delete orphaned commitments. A production system reclaims that MBR with an admin-callable cleanup method after the voting period ends; the Production Hardening section lists it.

MBR planning starts before the commit phase, at deployment.

::: {.gotcha #fund-app-before-box-creation topic="Box storage" title="A method that creates boxes fails unless the app account is funded first"}
An application account must already hold a box's minimum balance when the method that creates the box runs. Fund the account first, or the creating call fails with `account <address> balance <n> below min <m> (<k> assets)` --- a ledger refusal no assert inside the contract can catch or rename. Here that means paying the app before `initialize`: for a three-choice election, three tally boxes at `2,500 + 400 × (10 + 8) = 9,700` microAlgos each is 29,100, on top of the 100,000 base.
:::

Client-side code must declare which boxes each transaction will access, and this contract's methods touch different boxes.

**Box references are required for every method that touches boxes.** Callers must include box references in their transaction parameters:

- `initialize`: include box references for all tally boxes being created (e.g., `[(app_id, b"t_" + i.to_bytes(8, "big")) for i in range(num_choices)]`)
- `commit_vote`: include the commitment box reference (`(app_id, b"c_" + sender_address_bytes)`)
- `record_verified_proof` and `record_bound_proof`: include both the commitment box and the proof status box for the voter
- `reveal_vote`: include the commitment, proof status, and tally box references
- `get_tally`: include the tally box reference for the queried choice

A reference buys two things at once: the right to name a box, and 2,048 bytes of I/O allowance. The allowance counts every entry on the group, duplicates and empty ones included, so a call may carry references that name nothing and exist purely for budget --- which is what the padding in Chapter 5 is. When one goes missing, the message tells you which kind it was; Table 23-6 pairs them.

: Table 23-6. Which reference went missing, by the message it leaves

| Reference you dropped | Message you get |
|-----------------------|-----------------|
| The one that *named* a box | `invalid Box reference 0x...`, the box's name in hex: it is not in the call's available set at all |
| A padding reference, budget only | Every name still resolves, so the call gets further and dies on size: `box read budget (2048) exceeded` before the first opcode runs, or `write budget (2048) exceeded 2080` partway through |

Neither size message says much: the read form names the budget alone, the write form adds only the total you tried to dirty, and neither names a box --- so in a group that touches several, you narrow it by hand.

AlgoKit Utils populates app-call resources by default (`populate_app_call_resources` is `True` unless you turn it off), so the typed client generated by `algokit generate client` will usually assemble both the references and the padding for you. That default is a convenience, not a guarantee, and it is gone the moment the call is built by something else: another contract, a hand-rolled transaction, a different SDK. Write the references out explicitly when the group has to work without it.

Constructing box references in client code (example for `commit_vote`):
```python
from algosdk import encoding
voter_bytes = encoding.decode_address(voter.address)
boxes=[
(app_id, b"c_" + voter_bytes),  # commitment box
]
# For reveal_vote, include commitment, proof status, and tally boxes:
boxes=[
(app_id, b"c_" + voter_bytes),
(app_id, b"p_" + voter_bytes),
(app_id, b"t_" + choice.to_bytes(8, "big")),
]
```

::: {.setup}
**LocalNet round advancement.** On LocalNet with on-demand block production, rounds only advance when transactions are submitted. To test phase transitions (which depend on round numbers), you must send dummy transactions (e.g., zero-amount payments) to advance rounds past the commit or prove deadlines.
:::

### The LogicSig ZK Verifier

Generating the verifier is one Go program, and the project's `zk/cmd/gen-verifier` is all of it. It compiles the circuit, runs the PLONK setup against the ceremony key AlgoPlonk embeds, and writes four files into `zk/generated/`: the constraint system, the proving key, the verifying key, and the verifier as PuyaPy source with that verifying key compiled into it. Those four files are committed, which is why the workflow at the top of this chapter needed no Go at all. Here are the load-bearing lines, with the error handling that surrounds them in the project left out:

```go
// 1. Compile the circuit and run the PLONK setup.
var c circuit.VoteCircuit
compiled, _ := ap.Compile(&c, ecc.BN254, setup.PerpetualPowersOfTauBN254)

// 2. Write the compiled circuit and both keys, so `prove` does not
//    re-run the setup and a reader can inspect what was committed.
writeArtifact("generated/vote_circuit.ccs", compiled.Ccs)
writeArtifact("generated/vote_circuit.pk", compiled.Pk)
writeArtifact("generated/vote_circuit.vk", compiled.Vk)

// 3. Write the PuyaPy verifier for this verifying key. The key is baked
//    into the program, so the LogicSig's address commits to this circuit.
compiled.WritePuyaPyVerifier("generated/VoteVerifier.py", verifier.LogicSig)
```

`setup.PerpetualPowersOfTauBN254` is the choice that decides whether any of this means anything. It is a real ceremony transcript, embedded in the AlgoPlonk module and derived from `powersOfTau28_hez_final_18.ptau`. AlgoPlonk also ships `setup.TestOnlyBN254`, which compiles, proves and verifies exactly as happily --- and generates its toxic waste locally on every run, so anyone who runs the same code can forge proofs under it. A deployment records which ceremony its verifier came from, and this one is a real one.

A second command, `zk/cmd/prove`, produces one ballot's proof against those keys. It computes the MiMC commitment with gnark-crypto, proves the circuit for a private choice and blinding factor, verifies the proof off chain before anything reaches a network, and writes the proof, the public inputs, and a small JSON manifest the Python client reads. Regenerating the whole set is three commands:

```bash
cd zk
go run ./cmd/gen-verifier                    # circuit, keys, verifier source
cd ..
poetry run python -m scripts.build_verifier  # verifier source -> TEAL
cd zk
go run ./cmd/prove -choice 1 -num-choices 3  # a proof for a fresh ballot
```

The middle step is a Python one because the verifier AlgoPlonk writes is PuyaPy source, not TEAL. Note what `prove` prints and keep it: the blinding factor is half of the preimage the voter must present at reveal time, and losing it forfeits the vote as surely as never revealing.

What the generated verifier does is narrow and worth stating precisely. It signs an application call; it reads the proof from `Txn.application_args(1)` and the public inputs from `Txn.application_args(2)`, skipping the two-byte ARC-4 array length on each and leaving argument 0 to the method selector; it checks that those two arguments are 24 and 2 field elements long; it runs the PLONK verification with the AVM's `ec_*` opcodes; and it approves if and only if the proof verifies. Its address is the hash of that program. Everything else a LogicSig might check --- its fee, its rekey-to field, the shape of the group it is in, whether it has been used before --- it does not.

### The Atomic Group That Ties Everything Together

The full proof submission is a single atomic group; Figure 23-1 lays it out.

![Figure 23-1. The proof-submission group: the verifier's LogicSig-signed call at index 0, six companions carrying nothing but budget, and the governance call last.](figures/fig-23-1-proof-group.svg)

All eight transactions succeed or fail atomically. If the proof is invalid, the verifier LogicSig returns false, the entire group fails, and no state changes occur.

Transaction 0 needs somewhere to be sent. A LogicSig authorizes a transaction; it is not a callable program, so "the verifier runs" means "some transaction was authorized by it", and the transaction the generated verifier is written to authorize is an application call with three arguments. `smart_contracts/verifier_anchor/contract.py` is that application: one `verify(byte[32][],byte[32][])bool` method that returns `True` without checking anything, and a docstring explaining why checking anything there would be theatre. All the verification happened before the anchor's program was reached. What the anchor provides is a place for the proof and the public inputs to sit *as transaction fields*, where a second contract can read them.

The project builds the whole group in `scripts/localnet_helpers.py`, in `build_proof_group`: the LogicSig-signed anchor call at index 0 with the proof and public inputs ARC-4 encoded as `byte[32][]`, six zero-amount self-payments carrying nothing but their budget contribution, and the governance call last, paying the fees for all eight. Its optional arguments exist so the tests can build the group wrong on purpose.

### Binding the Proof to the State

A group that contains a verified proof and a state update is not yet a system. Nothing so far stops somebody from taking a proof that verified for one voter and recording it against another's commitment, or from calling the anchor app themselves with the same arguments and no LogicSig in sight. The governance contract has to read the group it is in and refuse anything that is not the group it expects:

- The governance app call is at the expected group index.
- `Global.group_size` equals the exact proof-submission group size.
- Transaction 0 is the verifier app call, signed by the expected LogicSig address.
- That verifier account's authorized address has not already been changed.
- The verifier app call targets the expected anchor app ID.
- The proof bytes are in `Txn.application_args(1)` of the verifier app call.
- The public-input bytes are in `Txn.application_args(2)` of the verifier app call.
- The public inputs decode to the stored commitment and `self.num_choices.value`.

Example 23-1 is that method. It belongs beside `record_verified_proof` in the file --- it is the same job with the admin removed --- and it is printed here because every assertion in it is about a group you had not seen until now.

**Example 23-1.** `record_bound_proof`: a proof recorded on the group's evidence

<!-- finder: make a contract believe a proof only because it watched it verify -->

```python
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
```

The method is the whole trustless path: `set_verifier` pins which program may prove things to this election, and `record_bound_proof` refuses to believe anything that program did not do here, in this group, about this voter. The workflow at the start of the chapter ran it for the first of its three voters, and `tests/test_zk_voting.py` attacks it five ways.

One checklist item from the earlier list is missing on purpose, and it is worth being explicit rather than quiet about it: the six padding transactions are not checked at all --- not their type, not their sender, not their fee. That is defensible here and would not be everywhere. Indices 1 through 6 are signed by whoever sent them and can do only what those senders could do without this group; an attacker who fills them with their own payments is spending their own money to buy a budget that verifies a proof they still cannot bind to anybody else's commitment. The two assertions that do the work are `Global.group_size` and `Txn.group_index`: with the group fixed at eight and this call fixed at index seven, no second governance call fits anywhere in it, which is what stops one verified proof from being recorded twice. Change either pin and the padding stops being harmless.

Do not pass independent "commitment" and "num choices" arguments to the governance call and trust them by themselves. The governance app must compare against the same public-input bytes consumed by the verifier LogicSig, which is why Example 23-1 slices `verifier_txn.app_args(2)` rather than reading anything from its own arguments. AlgoPlonk's generated LogicSig verifier reads proof and public inputs from the second and third application arguments because the first is reserved for the ARC-4 method selector, and the byte offsets in those slices --- 2, 34, 66 --- are the ARC-4 array length prefix followed by two 32-byte field elements.

The one check in Example 23-1 that is easy to read past is the `acct_auth_addr` one, and it is there because `verifier_txn.sender == verifier_address` does not mean what it appears to. If that account was rekeyed *earlier*, its LogicSig never runs again, and a transaction from that sender proves only that whoever now holds the authorization signed it.

That does **not** license the governance contract to assert `rekey_to` on the verifier's transaction. That field describes a rekey this group would perform, and the damage here was done by one that already settled, so the assertion looks like a defence while addressing a different event. The `rekey_to` check belongs in the LogicSig, which is signing on that account's behalf and for which it is mandatory --- Chapter 10 draws that line, and Exercise 5 is where the check gets written.

What a stateful contract *can* do about a rekey that already happened is read the account's authorization directly, with `acct_params_get AcctAuthAddr`, and refuse a verifier whose authorization has moved.


## Box Storage Patterns for Vote Tracking

### Box Storage Iteration: The On-Chain Enumeration Problem

Boxes are key-value stores with no built-in enumeration. You can read a box if you know its key, but you cannot iterate over all boxes. This is a fundamental constraint for tallying. (See [Algorand Python storage](https://algorandfoundation.github.io/puya/language-guide/storage/) for `Box`, `BoxMap`, and raw byte access patterns, and [Algorand Python data structures](https://algorandfoundation.github.io/puya/language-guide/data-structures/) for raw `Box` and `BoxMap` patterns.)

**Solution 1: Maintain an explicit index.** Store voter addresses in a separate "index" box as a concatenated byte array. Each address is 32 bytes. A 32KB box can hold 1,024 voter addresses, but touching the whole box requires 32KB of box I/O budget. A single app call provides only 8 references *in total* --- a combined ceiling shared by accounts, applications, assets and boxes, not a box-only allowance: `reveal_vote` already names three boxes, and `record_bound_proof` a box and an app --- so a max-size index needs extra references from other transactions in the group. How many is Chapter 5's reference-counting arithmetic, unchanged. For a single-call-friendly design, shard the index into smaller boxes (for example, 8KB shards holding 256 voters). This is an illustrative extension that could be added to the voting contract:

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
        assert voter_index.create(size=UInt64(INDEX_BOX_SIZE)), "no index box"

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

Each index slot stores one account's 32-byte public key, not the human-readable address string. The expression `index * 32` selects the start of that slot. Off-chain clients convert between display addresses and raw bytes at the boundary; on-chain code compares the result to another account value's `.bytes`. Older examples may spell these operations `BoxRef`; Chapter 5 retired that name, and `Box(Bytes, key=...)` is the same raw-byte surface.

**Solution 2: Off-chain indexing.** For most governance systems, the indexer reads all box storage off-chain and computes tallies client-side. This is the pragmatic approach when the number of voters exceeds what can be efficiently iterated on-chain within opcode budgets.

### Box Size Planning for the Voting Contract

Table 23-7 lists the four kinds of boxes the voting contract uses, each with the fixed key and data layout that fixes its MBR.

: Table 23-7. Box layout and minimum balance for the voting contract

| Box | Key format | Key size | Data | Data size | MBR per box |
|-----|-----------|----------|------|-----------|-------------|
| Commitment | `c_` + address | 34 bytes | MiMC hash | 32 bytes | 2,500 + 400 × 66 = 28,900 microAlgo |
| Proof status | `p_` + address | 34 bytes | uint64 | 8 bytes | 2,500 + 400 × 42 = 19,300 microAlgo |
| Tally | `t_` + uint64 | 10 bytes | uint64 | 8 bytes | 2,500 + 400 × 18 = 9,700 microAlgo |
| Voter index | `voter_index` | 11 bytes | addresses | 32,768 bytes | 2,500 + 400 × 32,779 = 13,114,100 microAlgo |

The voter-index box is a one-time MBR cost only if you add the explicit-index extension. The app account or admin must fund it before the first indexed commit.

Each voter costs 48,200 microAlgo in minimum balance, and the two halves are paid by different accounts. The voter pays the commitment box's 28,900 with the payment `commit_vote` requires, which is Example 11-4 --- charge the user for the box they create --- doing project work. The application account pays the proof status box's 19,300, because neither method that creates it takes a payment. So the deployment arithmetic for a three-choice election with three voters is `100,000 + 3 x 9,700 + 3 x 19,300 = 187,000` microAlgo into the app account before `initialize` runs --- the figure the workflow prints --- and the voters bring the rest as they arrive.


## What the Tests Prove

Forty tests ship with the project: twenty that deploy and play on LocalNet, and twenty that read the contract source and the compiled app specs without a chain at all. Eight of the twenty on-chain tests need the generated verifier and a real proof; if `zk/generated/` is empty they skip, naming the file they wanted, rather than failing.

Almost half of them are refusals, and a refusal is the easiest kind of test to get wrong. `pytest.raises(Exception)` around a chain call is close to worthless: a typo in a box reference, an unfunded sender and a misspelled method all raise, and every one of them reads as the contract doing its job. What makes a negative test about the check it claims to be about is matching the message:

```python
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
```

Every refusal test in the suite is one `with rejected_with("Already committed"):` block around the call that must not land, where `rejected_with` is the one-line factory for that context manager. A test that passes because the sender was unfunded now fails, and says what it wanted instead.

That is the reason every assertion in this contract carries a message. The messages are not decoration for the author, who has the source; they are the only thing an integrator or a test has to go on, and a bare `assert` leaves both with a program counter. Table 23-8 is the on-chain suite with the message each test is holding out for. Cover the third column and predict it from the second: the ones you cannot predict are the messages worth rewriting.

: Table 23-8. What each test in the suite proves

| Test | Scenario | The assertion that matters |
|------|----------|----------------------------|
| `python_state_machine_flow` | Three voters commit, are marked through the teaching hook, reveal | Each tally is exactly 1: three ballots in, three out, no link back to a voter |
| `initialize_needs_the_app_account_funded_for_its_boxes` | The app account holds its base minimum and one tally box | Fails with `below min` --- a balance error carrying a number, not a message about the box, and no assertion in the contract can catch it |
| `double_commit_rejected` | The same voter commits twice | `Already committed` |
| `commit_must_pay_the_box_MBR_exactly` | One microAlgo short, then one microAlgo over | `Pay the box MBR exactly`, both times |
| `reveal_must_match_commitment` | A voter reveals a choice they did not commit to, then the one they did | `Wrong preimage for commitment`, and the honest reveal still lands afterwards |
| `reveal_requires_a_recorded_proof` | A voter commits, never proves, and reveals | `No recorded proof`, and the tally stays at zero |
| `mimc_hashes_whole_field_elements` | 31 bytes of randomness offered to the helper and to `reveal_vote` | `Randomness must be 32 bytes` from both, and one randomness under two choices gives two different commitments |
| `a_vote_cannot_be_revealed_twice` | The same reveal sent again, carrying a note so it is a new transaction | `Vote already revealed` --- the status the first reveal wrote |
| `commitment_after_deadline_rejected` | A commit after `commit_end_round` has passed | `Commit phase closed` |
| `record_verified_proof_is_admin_only` | A voter calls the teaching hook for their own commitment | `Only admin` |
| `set_verifier_is_admin_only_and_commit_phase_only` | A stranger rebinds the verifier; then the admin does, after commitments closed | `Only admin`, then `Commit phase only` |
| `update_and_delete_are_rejected` | Delete through the typed client, update through a hand-built transaction | `Contract is immutable` for both |
| `avm_mimc_matches_the_go_prover` | The ballot behind the committed proof, hashed on chain | The digest equals the one `cmd/prove` recorded off chain |
| `bound_verifier_group_records_proof` | The real eight-transaction group, with the real proof | `verified_proofs` becomes 1, and the vote it unlocked reveals into its tally |
| `a_proof_cannot_be_recorded_twice` | The same group submitted a second time | `Proof already recorded` |
| `unsigned_anchor_call_rejected` | The same arguments, with the anchor called by an ordinary account | `Not verifier` |
| `extra_transaction_in_group_rejected` | A ninth transaction appended to the group | `Wrong group size` |
| `short_group_rejected` | Seven transactions, pooling 140,000 units | `dynamic cost budget exceeded`, inside `ec_pairing_check` rather than at any of the app's own guards |
| `mismatched_commitment_rejected` | One voter's proof recorded against another voter's commitment | `Commitment mismatch` |
| `mismatched_num_choices_rejected` | A four-choice election, and a proof made against three | `num_choices mismatch` |

The five tests from `unsigned_anchor_call_rejected` down are the binding under attack, and they are the ones worth reading in full in `tests/test_zk_voting.py`. Each takes the group that works and changes one thing about it.

The other twenty tests never touch a chain, because the properties they check cannot be seen from one. A contract whose asserts have no messages behaves identically to one whose asserts do; a `record_bound_proof` that asserted `rekey_to` on somebody else's transaction would pass every test above; `ensure_budget` called *after* `op.mimc` instead of before would fail only under a budget the test happened not to have; and a method wrongly marked `readonly` would be simulated by every client and never submitted, which looks like success. Those live in `tests/test_contract_shape.py`, asserted against the contract source and the compiled ARC-56 spec: every assert carries a message, the budget is raised before the hash, `get_tally` is the only readonly method, the box prefixes are the ones the scripts build by hand, and the generated verifier still reads its proof from application argument 1 and its public inputs from argument 2. That last one matters more than it looks: if AlgoPlonk ever moved those arguments, `record_bound_proof` would be slicing the wrong bytes and every test on the chain would still pass.

One test earns its place by being the reason the whole system holds together. The ballot behind the committed proof is hashed three times by three implementations --- by gnark's in-circuit MiMC gadget when the proof was generated, by gnark-crypto in `cmd/prove`, and by `op.mimc(MiMCConfigurations.BN254Mp110, ...)` inside `reveal_vote` --- and `avm_mimc_matches_the_go_prover` asserts that the third agrees with the first two. If any pair disagreed, a proof would verify against a commitment that no reveal could ever open, and the system would look correct until its last phase.


## Production Hardening

What runs is not the same as what ships. The contract has four seams left in it, and collecting them here makes hardening a list to work through rather than warnings to remember. For the vulnerability classes beyond this project, [secure-contracts.com/not-so-smart-contracts/algorand/](https://secure-contracts.com/not-so-smart-contracts/algorand/) is the audit-side catalogue.

What the system already enforces --- audit these first:

- Commitments are binding (MiMC collision resistance within the field)
- Commitments are hiding (randomness is cryptographically random, 256-bit)
- Double-voting is prevented (one commitment per address)
- Vote changes after commitment are prevented (phase transitions are irreversible)
- Phase transitions check round numbers correctly and are admin-only
- A recorded proof is a proof this group verified about this voter's commitment (Example 23-1), and a recorded proof cannot be recorded or revealed twice

What a deployment must still add, each with its one-line rule:

- **A hardened verifier wrapper.** The generated LogicSig verifies a proof and guards nothing about its own account: no fee bound, no rekey-to check, no group binding. Wrap it --- Chapter 21's checklist, applied to the verifier, and Exercise 5.
- **Retire the teaching hook.** `record_verified_proof` is still deployed beside `record_bound_proof`, and it still takes the admin's word. A production build deletes it, so that the bound method is the only way `proof_status` is ever written.
- **Setup you can cite.** PLONK soundness and the zero-knowledge property hold only if the universal trusted setup was honest. This verifier came from the Perpetual Powers of Tau BN254 ceremony that AlgoPlonk embeds; a deployment records which ceremony its own verifier came from, and never ships one built on `TestOnlyBN254`.
- **Proof-status MBR.** Recording a proof creates a 19,300-microAlgo box the app account pays for. Pre-fund the app for the expected electorate, or add an `mbr_payment` argument as `commit_vote` has.
- **Orphaned-commitment cleanup.** A voter who commits and never proves forfeits their vote and strands 28,900 microAlgos of box MBR. Add an admin-callable cleanup method that deletes unproven commitment boxes and reclaims the MBR after the vote closes.
- **A terminal phase.** As written, the reveal phase never closes. Add `PHASE_CLOSED` (Exercise 1) so results finalize, late reveals stop, and the final tally is emitted as an event.
- **A register gate.** Any address may commit once. Requiring proof of membership in a published register is Exercise 6.

Table 23-9 is the same boundary drawn component by component: what ships running, and what each seam takes to close.

: Table 23-9. Components built and concepts introduced

| Component | Status | Concepts Introduced |
|-----------|--------|---------------------|
| ZK circuit (gnark) | Compiled and committed; complete it in Go to change the statement | Groth16/PLONK proof systems, SCS, witness generation |
| MiMC commitments | Runs in the shipped workflow, on three implementations that agree | ZK-friendly hashing, commitment schemes |
| Voting smart contract | Runs in the shipped workflow | Multi-phase state machine, box-based vote tracking, tally accumulation |
| LogicSig ZK verifier | Runs in the shipped workflow; hardening its own account is Exercise 5 | BN254 curve operations, pairing checks, opcode budget pooling |
| Atomic verification group | Runs in the shipped workflow, and is attacked five ways in the suite | Coordinating LogicSig verification with smart contract state updates |

## Exercises

1. **(Apply)** The voting contract uses a 4-phase system (commit, prove, reveal, tally). Add a `PHASE_CLOSED` state that activates after the reveal phase ends, preventing any further action. What state transitions and checks need to change?

2. **(Analyze)** Why is MiMC used for commitments inside the ZK circuit instead of SHA-256? What are the security tradeoffs of using a less battle-tested hash function?

3. **(Evaluate)** Completeness, soundness, zero-knowledge: judge each against the reveal phase. Which of the three survives it intact, and where exactly is each of the others given up? Use the Privacy Scope section as the standard, and say what your verdict means for calling this design "private voting".

4. **(Create)** Design an extension where voters can delegate their vote to another address before the commitment phase. What changes to the commitment scheme, ZK circuit, and smart contract are needed? How do you prevent a delegate from learning what vote they are casting?

5. **(Create)** Harden the generated verifier. It approves any transaction that carries a proof which verifies, and a proof becomes public the moment it is submitted, so anyone can replay one --- in a transaction of their own choosing, with fields the program never looks at. Wrap or modify it so the LogicSig guards its own account.
   (a) Name the transaction an attacker builds from a replayed proof, and what it does to the verifier account.
   (b) Say what that costs an election already in flight, given Example 23-1's `acct_auth_addr` check and the fact that `set_verifier` only runs during the commit phase.
   (c) List which of Chapter 21's checklist items your wrapper adds.
   (d) Say what wrapping does to the verifier's address, and therefore to the deployment procedure.
   (e) Write the negative test that proves the wrapper refuses the transaction you named.

6. **(Create)** The register gate: Chapter 22's Handoff promised that Example 22-5 would prove a voter is on the register, and the runnable contract never does --- any address may commit once. Store a merkle root of eligible addresses at initialization and require an inclusion proof with each `commit_vote`. Say what the proof reveals about the voter, why that fits this design's delayed-disclosure scope anyway, and what a register proof that reveals nothing would require instead.

## Before You Continue

You should be able to check off all five of these:

- [ ] I can state what the vote circuit proves and what it keeps private, and say why the commitment is hashed with MiMC rather than SHA-256
- [ ] I can walk the four phases from commitment to tally, and explain why this design gives delayed disclosure rather than permanent ballot secrecy
- [ ] I can lay out the atomic group that verifies one proof --- the LogicSig-signed verifier call, the transactions that pool its opcode budget, and the state update --- and say why `verifier_txn.sender == verifier_address` alone does not prove the LogicSig ran
- [ ] I can explain why a contract cannot enumerate its own boxes, and price the commitment and proof-status boxes each voter adds
- [ ] I can name the checks that make a recorded proof evidence rather than an assertion, and say which one thing in this chapter a Go toolchain is actually required for

If any of these are unclear, revisit the relevant section before proceeding.

## Mastery Checkpoint
That is the end of Part VI. The checklist above asks whether you followed the chapters. The Mastery Checkpoint printed on the next page asks something harder: whether you can build a thing this part did not show you. It is a small program with a stated acceptance test, and a fallback if you stall.
