\newpage


# Consolidated Gotchas Cheat Sheet {-}

Every gotcha from every chapter in one scannable list.

## Box Storage

(See [Box Storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/).)

- MBR formula includes name length: `2,500 + 400 × (name_len + data_size)` microAlgos
- Each box reference provides only 1KB of I/O budget --- a 4KB box needs 4 references
- Boxes cannot be accessed in the ClearStateProgram --- all box opcodes fail immediately
- Box size was immutable prior to AVM v10; since AVM v10, `box_resize` and `box_splice` allow in-place resizing without deleting and recreating
- If an app is deleted, its boxes are NOT deleted and the MBR is locked forever
- `box_get` fails if the box exceeds 4KB; use `box_extract` for larger boxes
- Box data is unstructured bytes --- you manage serialization yourself
- Box names with non-ASCII bytes produce confusing error messages

## Inner Transactions

(See [Inner Transactions](https://dev.algorand.co/concepts/smart-contracts/inner-txn/).)

- **Always** set `fee=UInt64(0)` on inner transactions; otherwise the contract's Algo balance pays
- Budget adds +700 opcodes per inner app call when submitted
- Maximum 16 inner transactions per application call (pooled to 256 across the group)
- Maximum call depth of 8 --- the 8th contract cannot make further app calls
- ClearState programs cannot issue inner transactions
- State changes from earlier transactions in a group ARE visible to later transactions in the same group (they share a single copy-on-write state object). The group's aggregate changes commit to the ledger only after every transaction succeeds.

## Local State

(See [Local Storage](https://dev.algorand.co/concepts/smart-contracts/storage/local/).)

- Users can clear local state at any time via ClearState; this **always** succeeds
- Maximum 16 key-value pairs per user per application
- Schema (number of uint/byte slots) is immutable after app creation --- plan ahead
- Never use local state as the sole store for financial obligations (debts, locked tokens)

## Global State

(See [Global Storage](https://dev.algorand.co/concepts/smart-contracts/storage/global/).)

- Maximum 64 key-value pairs per application
- Key + value combined maximum 128 bytes per pair
- Schema is immutable after creation --- allocate extra slots for future needs

## Assets (ASAs)

(See [Assets Overview](https://dev.algorand.co/concepts/assets/overview/).)

- Contracts (and users) must opt into each ASA before receiving it; costs 0.1 Algo MBR
- `asset_sender` is only for clawback, not for sending --- use `Txn.sender` for regular transfers
- `Txn.receiver` is for Payment transactions; `Txn.asset_receiver` is for AssetTransfer
- Similarly: `Txn.amount` vs `Txn.asset_amount`, `Txn.close_remainder_to` vs `Txn.asset_close_to`
- Setting freeze/clawback address to the zero address makes it permanently immutable

## Arithmetic

(See [AVM](https://dev.algorand.co/concepts/smart-contracts/avm/).)

- `UInt64` overflow panics (fails the transaction) --- it does not wrap around
- Use `mulw`/`divmodw` or `BigUInt` for intermediate calculations that may overflow
- Floor division is the default and rounds in favor of the pool (correct for DeFi)
- For ceiling division: `ceil(a/b) = (a + b - 1) / b`
- `BigUInt` supports up to 512-bit values via byte-array arithmetic

## Resource References

(See [Resource Usage](https://dev.algorand.co/concepts/smart-contracts/resource-usage/).)

- 8 foreign references (accounts + assets + apps + boxes) per transaction
- References are shared across the group since AVM v9 --- spread across multiple txns if needed
- For compound references (asset holdings), both account and asset must appear in the same top-level transaction's arrays
- The transaction sender and current application are implicitly available

## Logic Signatures

(See [Logic Signatures](https://dev.algorand.co/concepts/smart-contracts/logic-sigs/).)

- In LogicSig programs, always check the close field and `rekey_to` equal zero address (`close_remainder_to` for payments, `asset_close_to` for asset transfers, `rekey_to` for both) --- missing any one is directly exploitable
- Always cap the fee to prevent fee-drain attacks
- Include an expiration mechanism (check `Txn.last_valid` or `Txn.first_valid`)
- Check `Global.genesis_hash` to restrict to a specific network (MainNet/TestNet)
- Arguments (`Arg[0]`, etc.) are visible on-chain and are NOT signed --- anyone can change them
- LogicSig signed delegations are valid forever unless you build in expiration
- LogicSig opcode budget is 20,000 per transaction (separate pool from smart contracts). Since AVM v10, LogicSig budgets pool across the group --- e.g., 8 LogicSig transactions contribute 160,000 opcodes to a shared LogicSig pool
- Template variables are baked into the program at compile time and ARE covered by the signature

## Compilation and Tooling

(See [AlgoKit CLI overview](https://dev.algorand.co/algokit/cli/overview/).)

- PuyaPy versions below 5.3.2 had a missing-assert bug --- always use v5.7.1+
- Global and local state schemas are immutable after app creation
- `algokit localnet reset` between test suites for clean state
- Block timestamps come from the proposer's clock, accurate only within ~25 seconds
- The minimum fee (1,000 microAlgos) is a consensus parameter that can change --- never hardcode it in client code (use `suggested_params()` instead). In contracts, fee cap checks like `Txn.fee <= UInt64(10_000)` necessarily use constants; this is an accepted tradeoff since the cap is a safety bound, not an exact fee

## Security

(See [Rekeying](https://dev.algorand.co/concepts/accounts/rekeying/) for the rekey attack vector.)

- For Logic Signatures, missing close-to / rekey checks are the #1 audit finding: assert `close_remainder_to` (payments), `asset_close_to` (asset transfers), and `rekey_to` (all types). These checks are not needed in stateful contracts --- the fields affect the sender's account, not the contract's
- Always verify group size matches expectations
- Always verify asset IDs in every transfer (don't assume)
- Always verify the receiver of incoming transfers is the contract address
- ClearState always succeeds --- design for users being able to exit at any time
- Rejected UpdateApplication and DeleteApplication makes a contract immutable (recommended for DeFi)
- Run Tealer static analysis: `tealer approval.teal --detect all`
