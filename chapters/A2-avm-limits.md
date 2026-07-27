\newpage

# AVM Limits and Protocol Parameters

Every constraint in this appendix is a consensus parameter, which means two things. It is the same on LocalNet, TestNet, and MainNet, so a contract that fits on your laptop fits in production. And it changes only when the protocol upgrades, which is why each table below names the AVM version a value belongs to rather than presenting it as timeless.

The figures here were checked against **consensus version v41 / AVM v12** (go-algorand 4.7.4). (See [Costs and Constraints](https://dev.algorand.co/concepts/smart-contracts/costs-constraints/) and [Protocol Parameters](https://dev.algorand.co/concepts/protocol/protocol-parameters/) for the authoritative specification.)

## Quick Reference: AVM Limits

{{tbl:avm-limits}} collects the limits worth committing to memory. The rest of this appendix explains the ones that are easy to get wrong.

Table: AVM limits quick reference {#tbl:avm-limits}

| Limit | Value |
|-------|-------|
| Max group size | 16 transactions |
| Opcode budget per app call | 700 (pooled) |
| Opcode budget per LogicSig txn | 20,000 (pooled, separate pool) |
| Max inner transactions per app call | 16 |
| Max inner transactions per group | 256 |
| Inner call depth | 8 |
| Program size (approval + clear combined) | 2,048 bytes (base); up to 8,192 bytes with 3 extra pages (each adds 2,048) |
| Global state pairs | 64 max |
| Local state pairs per user | 16 max |
| Key + value size (global or local) | 128 bytes max |
| Box size | 0–32,768 bytes |
| Box name | 1–64 bytes |
| Box MBR | 2,500 + 400 × (name_len + data_size) microAlgo |
| Box reference read budget | 2,048 bytes per reference (v41; was 1,024) |
| Access-list entries per app call | 16 (v41 unified `Access` list) |
| Legacy foreign-account references | 8 per app call (v41; was 4) |
| ASA opt-in MBR | 100,000 microAlgo |
| Min account balance | 100,000 microAlgo |
| Min transaction fee | 1,000 microAlgo |

## Minimum Balance Requirements

The MBR is not a fee. It is a floor: the balance an account must keep above zero to stay valid. It is refunded when the resource that caused it is released --- close out of an ASA, delete a box, and the balance is yours again. {{tbl:mbr-costs}} gives every increment.

Table: Minimum balance increments by resource {#tbl:mbr-costs}

| Resource | MBR increment (microAlgo) |
|----------|----------------------|
| Base account | 100,000 |
| Each ASA opted into or created | 100,000 |
| Each application opted into | 100,000 |
| Each application created | 100,000 × (1 + extra program pages) |
| Each global state uint slot (creator) | 28,500 |
| Each global state bytes slot (creator) | 50,000 |
| Each local state uint slot (opted-in account) | 28,500 |
| Each local state bytes slot (opted-in account) | 50,000 |
| Each box (paid by the app account) | 2,500 + 400 × (name_len + data_size) |

Two of these are the reliable source of `account <address> balance <n> below min <m> (<k> assets)` failures in a contract that looked fine in testing.

The **schema MBR is charged to the creator at creation time**, for the schema declared, not for the slots actually used. Declaring `global_num_bytes=16` and using two of them costs the same as using sixteen.

The **box name in the box MBR formula includes the `BoxMap` key prefix.** A `BoxMap` declared with `key_prefix=b"pos_"` and keyed by a 32-byte address has a name length of 36, not 32 --- so its MBR is 2,500 + 400 × (36 + data_size), and a funding calculation that forgot the prefix underfunds every box by 1,600 microAlgo.

## Opcode Budget

Two separate pools, which are constantly confused for each other.

**Application calls** get 700 units each, and since AVM v5 (`EnableAppCostPooling`) that budget is **pooled across the application-call transactions in a group** --- four app calls in one group share 2,800 units, and one of them may spend 2,000 of it. Padding a group with no-op app calls purely to raise the shared ceiling is a standard technique.

**LogicSig programs** get 20,000 units each, from a completely separate pool. Since AVM v10 that pool is also shared, across `len(group) × 20,000`.

Most opcodes cost 1 unit. The expensive ones are cryptographic: `ed25519verify` costs 1,900, `ecdsa_verify` 1,700, `sha256` 35, `keccak256` 130, `sha512_256` 45. One `ed25519verify` therefore consumes more than twice a single app call's entire budget --- which is why signature verification in a stateful contract needs either pooling or a LogicSig.

::: {.gotcha #budget-is-not-fees topic="Resource references, MBR, and budget" title="Opcode budget and fees pool over different transactions"}
Opcode budget and fees pool over different sets of transactions. Fees pool across the **whole group**: one transaction may overpay and cover a sibling of any type. Opcode budget pools only across the **application-call transactions** in the group --- adding a payment transaction to raise your compute ceiling does nothing at all. Two mechanisms, two scopes, and a group padded with the wrong transaction type fails with an opcode-budget error that looks like a fee problem.
:::

## Resource Availability

A contract may only touch accounts, assets, applications, and boxes that the transaction *declared* in advance. This is what makes parallel execution possible, and it is the constraint that most often turns a correct contract into a failing one.

Through AVM v11 the declaration was spread across four separate arrays --- `accounts`, `foreign_assets`, `foreign_apps`, `boxes` --- with their own limits and a combined ceiling of 8 entries per application call. **AVM v12 (consensus v41) replaces them with a single unified `Access` list of up to 16 entries**, which holds any mix of resource types. The legacy arrays still work; the foreign-account limit within them rose from 4 to 8.

Also new in v41: a box reference now grants 2,048 bytes of read budget rather than 1,024, so a 4 KB box needs two references instead of four.

::: {.gotcha #unavailable-resource topic="Resource references, MBR, and budget" title="An undeclared resource fails the program, it does not read as empty"}
An unavailable resource does not read as empty --- the program fails outright, with `unavailable Account` or `invalid Box reference`. This is why a method that works when called by the account that owns the box fails when called by anyone else: the sender is always implicitly available, and every *other* account has to be declared. algokit-utils 4.x populates most references automatically from the ABI method signature, which is a convenience and not a guarantee; anything the signature does not name, you declare yourself.
:::

## Consensus-Layer Surface This Book Does Not Build On

Three parts of the protocol are real, current, and deliberately not given a chapter, because no project in this book uses them and inventing one would teach less than the survey below.

**Participation and heartbeats.** Accounts that participate in consensus register participation keys through a key-registration transaction and, since consensus v40, emit periodic `heartbeat` transactions to prove liveness; an account that goes silent is suspended from proposing until it re-registers. This affects node operators and staking services. It does not affect contract logic: a smart contract cannot register keys, and `Global` exposes no consensus-participation fields.

**State proofs.** Every 256 rounds the network produces a state proof --- a compact, post-quantum-secure cryptographic attestation that a light client can verify without downloading the chain. The AVM does not verify state proofs; verification is a client-side operation, and the on-chain surface is limited to the state-proof transaction type itself. Relevant if you are building a bridge or a light client, not if you are building an application.

**Application versioning.** Consensus v41 added a `RejectVersion` field to application-call transactions, letting a caller declare the maximum application version it is willing to interact with, so a client cannot be silently switched onto an updated contract mid-flight. This matters for callers of mutable contracts; every contract in this book rejects `UpdateApplication`, which makes the field moot for them.

## AVM Version History

{{tbl:avm-versions}} lists the versions this book's material depends on. A contract compiled for a lower version runs unchanged on a higher one; the reverse is not true, which is why `--target-avm-version` is worth setting explicitly rather than inheriting.

Table: AVM versions and the capabilities they introduced {#tbl:avm-versions}

| AVM version | Consensus | Introduced |
|-------------|-----------|-----------|
| v5 | v30 | Inner transactions; app-call opcode budget pooling |
| v6 | v31 | Inner transaction types beyond payment/asset transfer |
| v7 | v32 | `base64_decode`, `json_ref`, `block` |
| v8 | v33 | Box storage |
| v9 | v34 | `ec_add` and friends (BN254 pairing) |
| v10 | v35 | LogicSig budget pooling across the group; `falcon_verify` groundwork |
| v11 | v39 | `mimc`; incentive-related fields |
| v12 | v41 | Unified `Access` list (16 entries); 8 foreign accounts; 2,048-byte box references; `RejectVersion` |

::: {.gotcha #avm-target-version-default topic="Compilation, tooling, and shipping" title="puyapy does not target the newest AVM version by default"}
`puyapy` does not default to the newest AVM version the network supports --- it defaults to a conservative one, currently 11. Code that uses a v12 feature compiles without complaint and then fails at assembly with an opcode error, or worse, silently takes a different code path. Pass `--target-avm-version` explicitly on every build; the projects in this book set it in `.algokit.toml` so the flag cannot be forgotten.
:::
