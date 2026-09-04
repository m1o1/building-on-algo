\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Appendix B: AVM Limits and Protocol Parameters {-}

Every constraint in this appendix is a consensus parameter, which means two things. It is the same on LocalNet, TestNet, and MainNet running the same consensus version, so a contract that fits on your laptop fits in production. And it changes only when the protocol upgrades, which is why each table below names the AVM version a value belongs to rather than presenting it as timeless.

The figures here were checked against **consensus version v42 / AVM v13** (go-algorand 5.0.1), the MainNet protocol as of September 2026. Values that first appeared in v41 / AVM v12 are labeled as such; they remain in force. Fee numerics --- `MinTxnFee`, Falcon's two-min-fee contribution, the per-byte size surcharge --- are snapshots of that consensus version, not eternal constants; a client that needs the current fee reads `minFee` from `/v2/transactions/params` and `group-usage` from `simulate` (Example 8-11). (See [Costs and Constraints](https://dev.algorand.co/concepts/smart-contracts/costs-constraints/) and [Protocol Parameters](https://dev.algorand.co/concepts/protocol/protocol-parameters/) for the authoritative specification.)

## Quick Reference: AVM Limits {-}

Table B-1 collects the limits worth committing to memory. The rest of this appendix explains the ones that are easy to get wrong.

: Table B-1. AVM limits quick reference

| Limit | Value |
|-------|-------|
| Max group size | 16 transactions |
| Opcode budget per app call | 700 (pooled) |
| Opcode budget per LogicSig txn | 20,000 (pooled across the group: `len(group) × 20,000`) |
| Max inner transactions per `itxn_submit` | 16 |
| Max inner transactions per group | 256 |
| Inner call depth | 8 |
| Program size (approval + clear combined) | 2,048 bytes base; 8,192 with 3 extra pages (v42: 16,384 with 7 pages + surcharge) |
| LogicSig program size | 1,000 bytes/txn pooled (v40: 16,000 in a full group; v42: one txn can buy 16,000) |
| LogicSig arguments | 1,000 bytes per txn pooled, independent of program bytes (not purchasable) |
| Global state pairs | 64 max |
| Local state pairs per user | 16 max |
| Key + value size (global or local) | 128 bytes max |
| Application arguments, all of them together | 2,048 bytes (v42: up to 16,384 with surcharge) |
| Box size | 0–32,768 bytes |
| Box name | 1–64 bytes |
| Box MBR | 2,500 + 400 × (name_len + data_size) microAlgo |
| Box MBR at the size ceiling | **13,135,300 microAlgo**, about 13.14 Algo: 2,500 + 400 × (64 + 32,768), a maximum-size box under a maximum-length name |
| Box reference read budget | 2,048 bytes per reference (v41; was 1,024) |
| Access-list entries per app call | 16 (v41 unified `Access` list) |
| Legacy foreign-account references | 8 per app call (v41; was 4) |
| ASA opt-in MBR | 100,000 microAlgo |
| Min account balance | 100,000 microAlgo |
| Min transaction fee (`MinTxnFee`) | 1,000 microAlgo (v42 base; not the whole fee) |

A transaction that stays inside those free allowances still pays exactly one minimum fee. Consensus v42 prices bytes *beyond* them at 0.1 microAlgo per byte (one ten-thousandth of a min-fee). Native Falcon-1024 authorization is the exception that costs more even at the old sizes --- three min-fees rather than one; see the survey below. Ordinary grouped inner-transaction fee pooling as taught in Chapter 11 is unchanged for the contracts in this book. Price anything that goes past those allowances with `simulate`'s group-usage rather than by counting transactions.

Block headers also carry a `CongestionTax`. Nothing in the current fee calculation reads it --- it is informational --- and it may later raise fees above the minimum under congestion, which is another reason not to hard-code a fee. [Heat](https://algorand.co/blog/enhancing-on-chain-flavor-in-algorand-5.0-part-4-heat) is the protocol note; this book does not guess an activation date.

Most of the cryptographic opcode costs exceed an application call's 700-unit budget, so they need `ensure_budget` or a group with room in it. Table B-2 lists them, verified against go-algorand 5.0.1 (`data/transactions/logic/opcodes.go`) and [AVM opcode specs](https://specs.algorand.co/avm/avm-appendix-a).

: Table B-2. Cryptographic opcode costs

| Opcode | Cost |
|---|---|
| `sha256` | 35 |
| `sha512_256` | 45 |
| `sha512` | 15 + 2 per 32 bytes of input (v13; max 271 at 4,096 bytes, so it fits in one app call) |
| `keccak256` | 130 |
| `sha3_256` | 130 |
| `ed25519verify`, `ed25519verify_bare` | 1,900 |
| `ecdsa_verify` | 1,700 (Secp256k1), 2,500 (Secp256r1) |
| `ecdsa_pk_decompress` | 650 (Secp256k1), 2,400 (Secp256r1) |
| `ecdsa_pk_recover` | 2,000 (flat) |
| `falcon_verify` | 1,700 (signature is variable-length, max 1,423 bytes) |
| `vrf_verify` | 5,700 (output is 64 bytes) |
| `ec_add` | 125 (BN254g1), 170 (BN254g2) |
| `ec_scalar_mul` | 1,810 (BN254g1), 3,430 (BN254g2) |
| `ec_multi_scalar_mul` | 3,600 + 90 per 32 bytes of scalars (BN254g1); 7,200 + 270 (BN254g2) |
| `ec_pairing_check` | 8,000 + 7,400 per chunk of the **second** operand; a chunk is 64 bytes under `BN254g1` and 128 bytes under `BN254g2` |
| `ec_subgroup_check` | 20 (BN254g1), 3,100 (BN254g2) |
| `ec_map_to` | 630 (BN254g1), 3,300 (BN254g2) |
| `mimc` | 10 + 550 per 32 bytes |
| `poseidon2` | 7 + 350 per 32 bytes (`BN254t2` and `BLS12_381t2`; v13) |

Two of those rows are worth a second look. `ec_subgroup_check` costs 20 units on `BN254g1` and 3,100 on `BN254g2`, which is the whole story of that curve: BN254's G1 has cofactor 1, so every point on the curve is already in the subgroup and the check reduces to an on-curve test; G2 does not, and pays for a scalar multiplication to prove membership.

`ec_pairing_check`'s unit is the one to read carefully, and it has two moving parts rather than one. The chunk *count* is measured over the second operand; the chunk *size* is the point size of the group you named. Name `BN254g1` and you have named the 64-byte group while the second operand holds 128-byte G2 points --- two chunks per pair. Name `BN254g2` and one 128-byte chunk covers two 64-byte G1 points, so one chunk covers two pairings. Four pairs are 67,200 one way round and 22,800 the other. Chapter 22 works the arithmetic.

## Minimum Balance Requirements {-}

The MBR is not a fee. It is a floor: the balance an account must keep above zero to stay valid. It is refunded when the resource that caused it is released --- close out of an ASA, delete a box, and the balance is yours again. Table B-3 gives every increment.

: Table B-3. Minimum balance increments by resource

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

## Opcode Budget {-}

Two separate pools, which are constantly confused for each other. Table B-4 sets the two execution modes side by side --- the first two rows are the pools; the rest is everything else that differs.

: Table B-4. Smart contracts and LogicSigs compared

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

**Application calls** get 700 units each, and since AVM v5 (`EnableAppCostPooling`) that budget is **pooled across the application-call transactions in a group** --- four app calls in one group share 2,800 units, and one of them may spend 2,000 of it. Padding a group with no-op app calls purely to raise the shared ceiling is a standard technique.

**LogicSig programs** get 20,000 units each, from a completely separate pool. Since AVM v10 that pool is also shared, across `len(group) × 20,000`.

Most opcodes cost 1 unit. The expensive ones are cryptographic: `ed25519verify` costs 1,900, `ecdsa_verify` 1,700, `sha256` 35, `keccak256` 130, `sha512_256` 45. One `ed25519verify` therefore consumes more than twice a single app call's entire budget --- which is why signature verification in a stateful contract needs either pooling or a LogicSig.

::: {.gotcha #budget-is-not-fees topic="Resource references, MBR, and budget" title="Opcode budget and fees pool over different transactions"}
Opcode budget and fees pool over different sets of transactions. Fees pool across the **whole group**: one transaction may overpay and cover a sibling of any type. Opcode budget pools only across the **application-call transactions** in the group --- adding a payment transaction to raise your compute ceiling does nothing at all. Two mechanisms, two scopes, and a group padded with the wrong transaction type fails with an opcode-budget error that looks like a fee problem.
:::

## Resource Availability {-}

A contract may only touch accounts, assets, applications, and boxes that the transaction *declared* in advance. This is what makes parallel execution possible, and it is the constraint that most often turns a correct contract into a failing one.

Through AVM v11 the declaration was spread across four separate arrays --- `accounts`, `foreign_assets`, `foreign_apps`, `boxes` --- with their own limits and a combined ceiling of 8 entries per application call. **AVM v12 (consensus v41) replaces them with a single unified `Access` list of up to 16 entries**, which holds any mix of resource types. The legacy arrays still work; the foreign-account limit within them rose from 4 to 8.

Also new in v41: a box reference now grants 2,048 bytes of read budget rather than 1,024, so a 4 KB box needs two references instead of four.

Consensus v42 / AVM v13 adds opt-in cross-application box access --- nine `app_box_*` opcodes that take an application ID --- gated by two flags the *owning* application's code must set through `app_params_set`: `AppForeignBoxReads` (any application may read) and `AppFamilyBoxAccess` (applications with the same creator may read and write). Both default off. This book does not spend those opcodes; they are listed here so a v13 feature is not mistaken for a v12 default.

::: {.gotcha #unavailable-resource topic="Resource references, MBR, and budget" title="An undeclared resource fails the program, it does not read as empty"}
An unavailable resource does not read as empty --- the program fails outright, with `unavailable Account` or `invalid Box reference`. This is why a method that works when called by the account that owns the box fails when called by anyone else: the sender is always implicitly available, and every *other* account has to be declared. algokit-utils 4.x populates most references automatically from the ABI method signature, which is a convenience and not a guarantee; anything the signature does not name, you declare yourself.
:::

## Consensus-Layer Surface This Book Does Not Build On {-}

Four parts of the protocol are real, current, and deliberately not given a chapter, because no project in this book uses them and inventing one would teach less than the survey below.

**Participation and heartbeats.** Accounts that participate in consensus register participation keys through a key-registration transaction and, since consensus v40, emit periodic `heartbeat` transactions to prove liveness; an account that goes silent is suspended from proposing until it re-registers. This affects node operators and staking services. It does not affect contract logic: a smart contract cannot register keys, and `Global` exposes no consensus-participation fields.

**State proofs.** Every 256 rounds the network produces a state proof --- a compact, post-quantum-secure cryptographic attestation that a light client can verify without downloading the chain. The AVM does not verify state proofs; verification is a client-side operation, and the on-chain surface is limited to the state-proof transaction type itself. Relevant if you are building a bridge or a light client, not if you are building an application.

**Application versioning.** Consensus v41 added a `RejectVersion` field to application-call transactions, and it is a floor rather than a ceiling: go-algorand defines it as *the lowest application version for which this transaction should immediately fail*, so a caller willing to talk to versions 1 through 4 sets `RejectVersion = 5`, and 0 means no check at all. Set it and a client cannot be silently switched onto an updated contract mid-flight. This matters for callers of mutable contracts. Every contract in this book before Chapter 24 rejects `UpdateApplication`, which makes the field moot for them; the two in that chapter that approve it are exactly the case `RejectVersion` exists for, and it is the caller-side counterpart to the `app_version` read taught there.

**Native Falcon accounts, SizeSponsor, and extra program pages (v42).** Consensus v42 made Falcon-1024 a first-class way to authorize an account (scheme, salt, 1,793-byte public key, signature up to 1,423 bytes; three min-fees rather than one). It also raised the extra-page ceiling from 3 to 7 (16,384 bytes combined, with a per-byte surcharge above 8,192), made extra pages and global schema mutable on update, and recorded a `SizeSponsor` for who pays the resulting MBR. Callers of a larger program must declare extra resource references to cover the extra I/O --- `simulate` reports how many; this book does not spend that surface. None of the projects here create Falcon-authorized accounts or grow a live application's pages. The LogicSig-based Falcon pattern Chapter 22 priced still works.

## AVM Version History {-}

Table B-5 lists the versions this book's material depends on. A contract compiled for a lower version runs unchanged on a higher one; the reverse is not true, which is why `--target-avm-version` is worth setting explicitly rather than inheriting.

: Table B-5. AVM versions and the capabilities they introduced

| AVM version | Consensus | Introduced |
|-------------|-----------|---------------------------------------------------------------|
| v5 | v30 | Inner transactions; app-call opcode budget pooling (`EnableAppCostPooling`) |
| v6 | v31 | Inner transaction types beyond payment and asset transfer |
| v7 | v34 | `vrf_verify`, `ed25519verify_bare`, `sha3_256`, `base64_decode`, `json_ref`, `block` |
| v8 | v36 | Box storage; `switch`/`match`; the subroutine frame opcodes |
| v9 | v38 | No new opcodes at all |
| v10 | v39 | The whole `ec_*` family, BN254 and BLS12-381 alike; `box_resize`, `box_splice`; LogicSig *cost* pooling across the group (`EnableLogicSigCostPooling`) |
| v11 | v40 | `mimc`; `online_stake`; block-incentive fields; LogicSig *size* pooling |
| v12 | v41 | `falcon_verify`; unified `Access` list (16 entries); 8 foreign accounts; 2,048-byte box references; `RejectVersion` |
| v13 | v42 | `sha512`; `poseidon2`; `app_box_*`; `app_params_set`; varint-encoded branch offsets |

The two columns do not move in lockstep, which is the reason to read this table rather than assume it. Consensus versions 32, 33, 35 and 37 shipped with no AVM change at all --- the AVM version simply carried forward --- and consensus v38 raised the AVM to 9 while adding no opcodes. The mapping above is the `LogicSigVersion` field of each consensus version in `config/consensus.go`, which is where the AVM version a network will accept is actually decided.

::: {.gotcha #avm-target-version-default topic="Compilation, tooling, and shipping" title="puyapy does not target the newest AVM version by default"}
`puyapy` does not default to the newest AVM version the network supports --- it defaults to a conservative one, currently 11. Code that uses a v13 opcode fails the compile with a hard error naming both versions (`Opcode 'sha512' requires a min AVM version of 13 but the target AVM version is 11`). The quieter hazard is shipping a program whose assembly differs from the one you measured, because a lower target silently omits v12/v13 codegen. Pass `--target-avm-version` explicitly on every build, and pin it in the project's own build step --- `smart_contracts/__main__.py` in an AlgoKit project --- so that no one has to remember the flag. This book's projects pin `--target-avm-version=13`.
:::

## Legacy Resource Addressing {-}

Two wire-format facts about resource references live here because you will meet them in other people's transactions and tooling, not in lines this book has you write.

**The foreign-array index form.** Before typed resource arguments, an `Account`, `Asset`, or `Application` parameter was an *index into the transaction's foreign arrays*, and contracts read the arrays by hand. The form still works and still appears in deployed contracts:

<!-- example: examples/costs/legacy_foreign_array.py mode=compile -->

```python
from algopy import Account, ARC4Contract, Txn, UInt64, arc4


class Legacy(ARC4Contract):
    """The pre-ARC-4 way: an index into a foreign array."""

    @arc4.abimethod(readonly=True)
    def by_index(self, which: UInt64) -> Account:
        # `Txn.accounts(0)` is always the sender, so caller-supplied indexes
        # are one-based in practice. This is what an `Account` argument
        # compiles down to, and reading it by hand is how it was done
        # before the type existed.
        # `<=`, not `<`: index 0 is the sender and `num_accounts`
        # counts only the DECLARED accounts, so `<` makes the last
        # one unreachable.
        assert which <= Txn.num_accounts, "not declared"
        return Txn.accounts(which)
```

`Txn.accounts(0)` is always the sender, which is why hand-written indexes are effectively one-based, and why off-by-one bugs in this area point at the *wrong account* rather than at none.

**The unified access list (consensus v41).** Consensus v41 added a single unified access list alongside the separate accounts, assets, and applications arrays (see Table B-5). A transaction uses one form or the other, never both, which is why a modern contract can reference more resources in one transaction than the old per-array caps allowed. It is a wire-format change rather than a source-level one: a fact about what your transactions may carry rather than a line the contracts in this book write.

## Further Reading {-}

The Algorand 5.0 "flavor" series is the upgrade narrative behind the v42 rows in this appendix:

- [Part 1: Salt](https://algorand.co/blog/enhancing-on-chain-flavor-in-algorand-5.0-part-1-salt) --- native Falcon accounts and address salt
- [Part 2: Fatter apps and transactions](https://algorand.co/blog/enhancing-on-chain-flavor-in-algorand-5.0-part-2-fatter-apps-and-transactions) --- extra pages, SizeSponsor, larger notes, arguments, and LogicSigs
- [Part 3: Acid](https://algorand.co/blog/enhancing-on-chain-flavor-in-algorand-5.0-part-3-acid) --- foreign-box access and family shared state
- [Part 4: Heat](https://algorand.co/blog/enhancing-on-chain-flavor-in-algorand-5.0-part-4-heat) --- usage-based fees, `simulate`, `CongestionTax`
- [Algorand v5.0.0 is here](https://algorand.co/blog/algorand-v5.0.0-is-here.-heres-what-it-means-for-you) --- the upgrade announcement
- [go-algorand 5.0.0](https://github.com/algorand/go-algorand/releases/tag/v5.0.0-stable) --- the consensus-upgrade release (dryrun and tealdbg removed; use `simulate`)
