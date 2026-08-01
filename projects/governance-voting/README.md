# Chapter 23: Private Governance Voting with Zero-Knowledge Proofs

This is the finished Chapter 23 project from *Building on Algorand*. It is a
four-phase governance vote in which ballots stay secret through the commit and
prove phases, and a PLONK proof over BN254 --- verified on chain by a LogicSig,
not by anyone's word --- attests that each secret ballot is a valid one.

Every ZK artifact this project needs is committed under `zk/generated/`, and
every one of them was produced by the command named beside it in the table
below. There are no placeholder keys here, and nothing in this directory stands
in for an artifact that was never generated. The only thing `zk/generated/`
does not carry is puyapy's `.puya.map` source map, which is build output like
any other and is gitignored.

## Prerequisites

- Python 3.12 or 3.13
- AlgoKit CLI 2.10 or later
- Poetry, installed by `algokit project bootstrap all` if it is not already
  present
- Docker or Podman for LocalNet
- **Go 1.25 or later, only if you want to change the circuit or prove a
  different ballot.** The committed artifacts let you run everything, including
  the trustless proof path, with no Go at all.

## Run It First!

```bash
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_governance_voting
algokit project run test
```

`scripts/run_governance_voting.py` runs one complete election with three voters:

- deploys the governance app, the verifier anchor app, and the MiMC helper
- binds the election to the verifier LogicSig's address and the anchor app ID
- takes three commitments, each paying its own `28,900` microAlgo box MBR
- advances rounds past the commit deadline and opens the prove phase
- **submits the eight-transaction proof group**, in which the AlgoPlonk
  LogicSig verifies a real PLONK proof and the governance app binds that
  proof's public inputs to the commitment already in box storage
- records the other two proofs through the chapter's admin-trusted hook
- reveals all three votes, each one re-derived from its MiMC preimage on chain
- reads the three tallies back

Watch for these checkpoints, which are the rows of the chapter's Table 23-1:

- `Verifier LogicSig address:` --- the hash of the verifier program, and
  therefore a commitment to the circuit. Change the circuit and this changes.
- `Verifier program bytes: 3464` --- the assembled verifier, the size the
  chapter reports.
- `App account funded with 187000 microAlgo of box MBR.` --- the exact bill,
  not a round number: `100,000` of account base, three tally boxes at `9,700`,
  and three proof-status boxes at `19,300`. Fund it short and `initialize`
  aborts partway through with a message about a minimum balance rather than
  about a box.
- `LogicSig budget consumed: 142,955 units of the 160,000 that 8 transactions
  pool.` --- read from a simulate of the real group, because a confirmed
  transaction does not report it. This is the number that decides the group
  size.
- `Proof group of 8 accepted:` --- the only line in the run that depends on
  elliptic-curve cryptography actually working.
- `Tally for choice 0/1/2: 1` --- one vote each, recovered from three
  commitments that revealed nothing until the reveal phase.

Without LocalNet you can still run the static path:

```bash
algokit project run build
algokit project run test-static
```

Those tests read the contract source and the compiled ARC-56 app specs, and
assert the security properties the chapter argues for and the exact ABI the
clients are written against. They need neither a chain nor Go.

## What is real, and what you must produce yourself

Everything below was generated on the toolchain named beside it and committed
as produced. Nothing is hand-written, edited or approximated.

| File | What it is | Produced by |
|---|---|---|
| `zk/generated/vote_circuit.ccs` | the compiled constraint system, 4,102 SCS constraints | `go run ./cmd/gen-verifier` |
| `zk/generated/vote_circuit.pk` | the PLONK proving key | same |
| `zk/generated/vote_circuit.vk` | the PLONK verifying key | same |
| `zk/generated/VoteVerifier.py` | the AlgoPlonk verifier, PuyaPy source, with the verifying key compiled in | same |
| `zk/generated/VoteVerifier.teal` | that verifier as TEAL, 3,464 bytes assembled | `python -m scripts.build_verifier` (puyapy 5.9.0) |
| `zk/generated/vote.proof` | one PLONK proof, 768 bytes | `go run ./cmd/prove` |
| `zk/generated/vote.public_inputs` | its two public inputs, 64 bytes | same |
| `zk/generated/vote.json` | the ballot behind that proof, so the client can drive it | same |

The verifier TEAL is the one row whose producing toolchain is not this
project's own. It was compiled by puyapy 5.9.0; the project pins 5.8.1, like
the other project directories in this book, and 5.8.1 assembles the same
AlgoPlonk source to 3,483 bytes instead of 3,464. Both verify the same proof.
`build_verifier` therefore leaves a committed `VoteVerifier.teal` alone unless
you pass `--force`, so the size and the LogicSig address stay put no matter
which puyapy a reader has installed.

**The proving and verifying keys come from a real ceremony.** `cmd/gen-verifier`
runs the setup against `setup.PerpetualPowersOfTauBN254`, which AlgoPlonk
embeds as `setup/PerpetualPowersOfTauBN254/{pk,vk}.bin` and derives from
`powersOfTau28_hez_final_18.ptau` --- the Perpetual Powers of Tau phase-1
transcript. AlgoPlonk ships `setup.TestOnlyBN254` too, which also compiles and
also proves, and whose toxic waste is generated locally on every run and is
therefore known to anyone who runs the same code. This project does not use it
anywhere, and neither should you.

**Nothing here is absent.** A reader with no Go toolchain can run every test in
this repository, including the trustless proof path, because the proof and the
verifier are committed. What Go buys you is the ability to prove a *different*
ballot, or to change the circuit.

### Regenerating the ZK artifacts

```bash
cd zk
go run ./cmd/gen-verifier                       # circuit, keys, verifier source
cd ..
poetry run python -m scripts.build_verifier     # verifier source -> TEAL
cd zk
go run ./cmd/prove -choice 1 -num-choices 3     # a proof for a fresh ballot
```

`gen-verifier` is deterministic: the SRS is fixed, the circuit is fixed, and
gnark's setup does not draw randomness, so on the pinned module versions it
writes byte-identical files. That was checked rather than assumed --- two
consecutive runs produce identical SHA-256 digests for all four outputs. It
takes about six seconds.

`prove` draws a random blinding factor unless you pass `-randomness`, so it
writes different bytes every time. Anything it prints, keep: the randomness is
half of the preimage the voter must present at reveal time, and losing it
forfeits the vote.

Changing the circuit changes the verifying key, which changes the verifier
program, which changes the LogicSig address --- so the artifacts move as a set.
Regenerate all of them, and re-run `set_verifier` on any live election.

## What this project measured

Four numbers the chapter states, checked on LocalNet against go-algorand
v4.7.4 rather than derived:

- **The verifier consumes 142,955 LogicSig budget units.** Read from
  `logic-sig-budget-consumed` in a simulate of the real group, which is what
  the workflow script prints; `scripts/localnet_helpers.py` has the one-call
  helper. The chapter says "about 143,000".
- **The circuit compiles to 4,102 SCS constraints.** Not the hundreds a reader
  would guess from three constraint declarations: `AssertIsLessOrEqual` against
  a variable bound decomposes a full 254-bit field element, and that dominates
  the count rather than the MiMC hash. Proof generation is still about 73
  milliseconds.
- **Eight transactions is the minimum, and it is exactly the minimum.** Seven
  pool 140,000 and fail with `dynamic cost budget exceeded, executing
  ec_pairing_check: local program cost was 105354`; eight pool 160,000 and
  succeed. The failure lands inside the pairing check, which is the single most
  expensive thing the program does.
- **The AVM's `mimc` opcode agrees with gnark exactly.** The same ballot hashed
  three ways --- by gnark's in-circuit gadget when the proof was made, by
  gnark-crypto in `cmd/prove`, and by `op.mimc(MiMCConfigurations.BN254Mp110,
  ...)` in `reveal_vote` --- produces one value. If any pair disagreed, a proof
  would verify against a commitment no reveal could ever open, and the system
  would look correct until the last phase.

## Where this project goes past the chapter, and why

The chapter prints the whole contract, both proof-recording methods included,
so nothing here is a version of the contract the chapter does not have. What
this directory adds around it is the machinery a printed page cannot carry.

| Here | In the chapter | Why |
|---|---|---|
| `tests/test_zk_voting.py` | Table 23-6 lists what each test proves, and prints one helper | twenty tests are twenty tests; the table is the map, not the territory |
| `tests/test_contract_shape.py` | named as the half of the suite that never touches a chain | source-level and ARC-56 properties, including the one that fails the build if a `rekey_to` assertion reappears in `record_bound_proof` |
| `smart_contracts/verifier_anchor` | named and explained, not printed | the LogicSig signs an application call, so an application has to be at the other end of it |
| `smart_contracts/commitment_helper` | described where MiMC is priced, not printed | without it a reader with no Go cannot compute a commitment, and so cannot commit |
| `scripts/localnet_helpers.py` | `build_proof_group` is named where the group is drawn | the eight-transaction builder, the box references, and the simulate that reads the LogicSig budget |
| `zk/cmd/gen-verifier`, `zk/cmd/prove` | the load-bearing lines of the first, and the flags of the second | the full programs, error handling included, that produced every committed artifact |

**Where the rekey check lives, and why not here.** `record_bound_proof` never
asserts `rekey_to` on the verifier's transaction or on the padding. That field
describes a rekey *this group would perform*, and the damage it is imagined to
prevent was done by one that already settled: a stateful contract asserting it
on somebody else's transaction restricts a wallet and protects nothing here.
The check belongs in the LogicSig, which is signing on that account's behalf,
and putting it there is the chapter's Exercise 5. What this contract does
instead is read the verifier account's current authorisation with
`acct_params_get AcctAuthAddr`, and `tests/test_contract_shape.py` fails the
build if a `rekey_to` assertion ever reappears in that method.

The rest of the padding is unchecked because pinning `Global.group_size` and
`Txn.group_index` already does the work: with the group fixed at eight and this
call fixed at index seven, no second governance call fits, and the other six
transactions are signed by their own senders and can do only what those senders
could do anyway.

## Reader Path

Read `smart_contracts/governance_voting/contract.py` first, in the order the
chapter builds it: `initialize`, `set_verifier`, `commit_vote`,
`advance_to_prove_phase`, `record_verified_proof`, `record_bound_proof`,
`reveal_vote`. Read `record_bound_proof` beside the chapter's binding checklist
and check them off against each other.

`scripts/run_governance_voting.py` is the executable transcript. `zk/circuit/`
is twenty-four lines of code and is the whole statement being proved;
everything else in `zk/` is machinery around it.

Save `tests/` for the testing section. `tests/test_zk_voting.py` is where the
binding is actually attacked: an anchor call no LogicSig signed, a ninth
transaction, a seventh missing, one voter's proof spent on another's
commitment, and a proof whose choice range does not match the election's.

## Useful Files

- `smart_contracts/governance_voting/contract.py` --- the voting state machine
  and both proof-recording methods.
- `smart_contracts/verifier_anchor/contract.py` --- the app the verifier
  LogicSig signs a call to, and a docstring explaining why it checks nothing.
- `smart_contracts/commitment_helper/contract.py` --- MiMC on demand, for
  clients with no Go.
- `scripts/run_governance_voting.py` --- the whole election, end to end.
- `scripts/localnet_helpers.py` --- artifact loading, box references, the
  eight-transaction group builder, and the simulate that reads the LogicSig
  budget.
- `scripts/build_verifier.py` --- compiles the generated verifier to TEAL, and
  leaves the committed one alone unless you pass `--force`.
- `zk/circuit/vote_circuit.go` --- the three constraints the proof satisfies.
- `zk/cmd/gen-verifier/` --- circuit compilation, PLONK setup, verifier
  generation.
- `zk/cmd/prove/` --- commitment computation and proof generation.
- `tests/test_contract_shape.py` --- source-level safety properties and the
  pinned ARC-56 ABI, no chain.
- `tests/test_zk_voting.py` --- the lifecycle and the binding, on LocalNet.
