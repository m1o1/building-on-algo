<!-- GENERATED FILE. Do not edit.
     Every entry below is a ::: {.gotcha} callout somewhere in
     chapters/. Edit it there and run `python3 build.py gotchas`.
     scripts/validate.py check 14 fails if this file has drifted. -->

\newpage

# Gotchas by Topic

Every mistake the book stops to warn you about, in one place. Each entry appears in full where it can actually save you --- in the chapter, at the paragraph where you are about to make it --- and is repeated here because six months from now you will remember that the book warned you about something to do with box names and not which chapter it was in.

The pointer after each entry names the chapter it is drawn from; go there for the surrounding code.

## Global and local state

### A counter maintained on CloseOut is wrong the first time somebody clears state

Any global number that a close-out handler decrements --- member counts, active-stake totals, open-position tallies --- silently desynchronizes the first time an account uses ClearState instead of CloseOut, and there is no method you can add to repair it, because the contract was never told. If a number must be exact, derive it from something the contract controls, or rename it to something that only increases.

*From {{ch:state}}.*

### Reading a state key that was never written fails the transaction; it does not return zero

`self.fee.value` on a key that has never been written aborts the call, because PuyaPy compiles `.value` to a `*_get_ex` opcode plus an assertion that the key existed. Local state has a second, harsher absence: reading it for an account that never opted in, or that cleared, is a ledger error that no default argument can catch. Both bite hardest on `readonly` methods, where they turn into a denial-of-service surface --- a non-member calls `credits_of(themselves)` and your dashboard shows an error instead of a zero. Use `.get(default=...)` when a missing key should read as a value, `.maybe()` when absence is information, and an explicit `is_opted_in` check before touching another account's local state at all.

*From {{ch:state}}.*

### Binding an ARC-4 struct to a variable aliases the stored bytes

`entry = self.house.value` is a second name for the same encoded bytes, not a snapshot, and PuyaPy refuses to compile it rather than let you guess: *mutable reference to ARC-4-encoded value must be copied using .copy() when being assigned to another variable*. Add `.copy()` if you want a detached working copy; write through the attribute chain if you want to modify storage. Native `algopy.Struct` values do not have this restriction.

*From {{ch:state}}.*

### The state schema is fixed at creation and can never be widened

The number of global and local slots an application declares is written into the create transaction and is immutable for the life of the contract. There is no migration, no resize, no `UpdateApplication` escape hatch --- a contract that needs a sixty-fifth global key needs a new application and a state migration you write yourself. The MBR is charged for what you *declare*, not what you use, so a slot reserved against future need costs 28,500 or 50,000 microAlgos whether you ever write to it or not. That is the price of the option, and it is usually worth paying.

*From {{ch:token-vesting}}.*

### ClearState always succeeds, so local state cannot hold an obligation

Users can delete their local state at any time via ClearState, and the protocol guarantees this always succeeds. Never use local state as the sole record of financial obligations, debts, or token claims.

*From {{ch:token-vesting}}.*

## Box storage

### A BoxMap key prefix counts toward the box name length

The `name_len` in `2,500 + 400 * (name_len + data_size)` is the length of the *full* box name, prefix included. A `BoxMap` declared with `key_prefix=b"v_"` and keyed by a 32-byte address has a name length of 34, not 32 --- and if you leave `key_prefix` off, PuyaPy uses the attribute name, so `self.schedules` silently gives you a 9-byte prefix and a 41-byte name. A funding calculation that forgot the prefix underfunds every box, and the failure surfaces as a balance error inside `create_schedule` rather than as anything about box names. Declare the prefix explicitly so the arithmetic is visible in the source.

*From {{ch:token-vesting}}.*

### Every method that touches a box needs its own box reference

Every method that accesses box storage requires box references on the client side --- not just `create_schedule`. The `claim`, `revoke`, `cleanup_schedule`, `get_vesting_info`, and `get_claimable` methods all read or write the beneficiary's box and must include the same `box_references` declaration. Forgetting this on read-only methods like `get_vesting_info` is a common mistake --- the AVM enforces the I/O budget regardless of whether the access is a read or write.

*From {{ch:token-vesting}}.*

### Deleting an application does not delete its boxes, and the MBR is gone

Cleanup is not housekeeping, it is the only way to get the money back. If an application is deleted while it still owns boxes, those boxes remain in the ledger and the MBR they hold is locked permanently --- there is no application left to call `box_del`, and no protocol path that reclaims it. A contract that creates boxes therefore needs a delete path that is *reachable*: either it refuses `DeleteApplication` outright, as this one does, or it asserts that no boxes remain before allowing deletion. Shipping a deletable, box-owning contract with no such assertion is how funds become unrecoverable without anybody writing a bug.

*From {{ch:token-vesting}}.*

### A method that creates boxes fails unless the app account is funded first

**Fund the app account before calling `initialize`.** The `initialize` method creates tally boxes (one per choice). Each tally box costs `2,500 + 400 * (10 + 8) = 9,700 microAlgos` in MBR. For 3 choices, the app account needs at least `3 * 9,700 = 29,100 microAlgos` plus its base MBR of `100,000 microAlgos` before `initialize` is called. Send a payment to the app's address before the `initialize` call, or you will see a "balance below minimum" error.

*From {{ch:zk-voting}}.*

## Arithmetic and time

### Block timestamps come from a proposer's clock, not from a trusted clock

`Global.latest_timestamp` is whatever the block proposer's system clock said, bounded only by monotonicity and a ceiling of roughly 25 seconds ahead of the previous block. It is fine for a cliff measured in months and useless for anything measured in seconds. Any logic where a 25-second skew changes who wins --- an auction close, a rate lock, a first-come claim --- must key on round numbers or accept that the boundary is fuzzy. And never compare it against a client-supplied timestamp for equality; compare with `>=` and let the window be wide.

*From {{ch:token-vesting}}.*

### UInt64 overflow fails the transaction; it does not wrap

Read the swap formula again with an eye on the numerator: `delta_x * 997 * y`. With reserves in the billions of base units --- entirely ordinary for a six-decimal stablecoin --- that product passes $2^{64}$ long before anything looks large in human terms. The AVM does not wrap on overflow, it panics, so the failure mode is a swap that simply stops working once the pool gets deep enough, in production, having passed every test written against a small pool. Any multiplication whose operands are both user-scaled needs `op.mulw`, `op.divmodw`, or `BigUInt`. Test the arithmetic at the top of the range, not the middle.

*From {{ch:amm}}.*

### op.btoi fails on a BigUInt wider than eight bytes

The `op.btoi` call accepts a byte array of 0--8 bytes and interprets it as a big-endian unsigned integer. A `BigUInt` that exceeds $2^{64} - 1$ would produce more than 8 bytes, causing `btoi` to fail at runtime. The `assert twap < BigUInt(2**64)` guard ensures the TWAP result fits in 64-bit range before the conversion. With `TWAP_PRECISION = 10^9` and typical asset prices, this bound is safe for years of accumulation. If you use a higher precision scale factor or expect extreme price ratios, return a `BigUInt` instead of converting to `UInt64`.

*From {{ch:amm}}.*

## Inner transactions

### A non-zero inner transaction fee is paid out of the contract's own balance

A non-zero inner transaction fee is paid by the contract's own
Algo balance. Set `fee=UInt64(0)` explicitly and make the caller's outer
transaction cover the pooled fee.

*From {{ch:token-vesting}}.*

### Inner transactions have three separate ceilings, and one of them is depth

An application call may issue at most 16 inner transactions, a group may contain at most 256 across all of its calls, and the call chain may descend at most 8 applications deep --- the eighth contract cannot call another. A loop that emits one inner transfer per position works beautifully for twelve positions and fails at seventeen with an error naming none of this. Each inner application call also adds 700 units to the pooled opcode budget when it is submitted, which is a gift, not a cost. And no inner transactions may be issued from a ClearState program at all, so a clear-state path can never return anything to the user.

*From {{ch:yield-farming}}.*

## ASAs

### A contract-held clawback address is custody, and it is visible on-chain

Setting `clawback` to the contract address means the contract can take the NFT from anyone at any time. This is necessary for revocation, but it means the NFT is not fully "sovereign" --- holders should understand that the vesting contract retains authority over it. This is visible on-chain and should be communicated clearly in your application's UI.

*From {{ch:nfts}}.*

### An inner transfer to a holder who never opted in reverts the whole call

Known limitation: the settlement step sends vesting tokens to `current_holder`. If the NFT was transferred to someone who has not opted into the vesting token, the inner asset transfer will fail and the entire revocation transaction reverts. This means a holder who refuses to opt into the vesting token can effectively block revocation. In production, you would address this by checking the holder's opt-in status before attempting settlement: if they are not opted in, skip the vested token transfer and instead store the unclaimed amount for later retrieval via a separate `withdraw_settled` method. We omit this for clarity, but Exercise 7 asks you to design the solution. A related edge case: revoking while the contract itself still holds the NFT (before delivery) with `claimable > 0` would send the settlement from the contract to itself, stranding those tokens --- one more reason revocation should only happen after checking who the holder is, or before the cliff when nothing has vested.

*From {{ch:nfts}}.*

### The caller must opt into the LP token before the pool can send it

The caller must have already opted into the LP token before calling this method. If they have not, the inner `AssetTransfer` sending LP tokens will fail, and the entire atomic group rolls back --- the pool receives no tokens and no state changes. This is the "lazy opt-in" pattern: the contract does not check the opt-in explicitly; the protocol enforces it automatically. Client code must perform a zero-amount self-transfer of the LP token before calling `add_initial_liquidity`.

*From {{ch:amm}}.*

## Atomic groups

### A type-checked group argument says nothing about the rest of the group

`gtxn.PaymentTransaction` pins the type and the position of the transaction you named. It places no bound at all on what else rides in the group. An attacker is free to append transactions after yours --- a second app call to the same method, a close-out, a rekey of an account they control --- and each one is validated on its own terms. If your method's correctness depends on being the only call in the group, or on the group ending where you think it does, say so: `assert Global.group_size == UInt64(2)`. The assertion costs two opcodes and closes an entire class of restructuring attack.

*From {{ch:patterns}}.*

### Transactions in a group see each other's state changes as they execute

Atomicity is about the *commit*, not about isolation. The transactions in a group execute in order against a single shared, copy-on-write view of the ledger, so the second app call in a group reads the state the first one wrote --- the group's changes land in the ledger together only if every transaction succeeds. This is what makes fund-then-call work at all. It is also why "nobody can observe an intermediate state" is the wrong mental model: a contract you call in the same group absolutely can, and a design that assumes otherwise is assuming a guarantee the protocol never made.

*From {{ch:patterns}}.*

## Authorization

### The application address has no private key and can never be a sender

`Global.current_application_address` is the account derived from the application ID. It holds the contract's Algo and assets, it is the sender of every inner transaction the contract emits, and *no private key exists for it*. It can therefore never be `Txn.sender` on a top-level call, so a guard of the form `assert Txn.sender == Global.current_application_address` is not merely wrong but unsatisfiable --- and if it guards `DeleteApplication`, the application is undeletable forever. `Global.creator_address` is the account that created the application, is fixed at creation, and is a real signer. Use the creator for authorization, and the application address for balances and inner transactions.

*From {{ch:mental-model}}.*

### There is no private method: every abimethod is a public entry point

Nothing about `@arc4.abimethod` makes a method internal, and nothing about naming it `_helper` or omitting it from your client hides it. The router dispatches on a selector computed from the method signature, and anybody who can read your app spec --- or hash a signature they guessed --- can call it. A method is protected only by the assertions inside it. Before you ship, list every `abimethod` and name the check that stops the wrong caller; if a method has no such check, either it is genuinely public or you have a hole.

*From {{ch:mental-model}}.*

### Assert that the funding transaction's sender is the account being credited

The pattern below reads a payment from the group and credits `Txn.sender`. Those are two different accounts unless you say they are the same one. Left unasserted, anyone can build a group that pairs *somebody else's* pending payment with their own app call and take the position it paid for --- the payment is valid, the app call is valid, and the contract cheerfully credits the wrong party. Whenever a grouped transfer funds something that is booked to `Txn.sender`, assert `payment_txn.sender == Txn.sender`. If you genuinely want third-party sponsorship, model the beneficiary as an explicit method argument rather than leaving it implied.

*From {{ch:patterns}}.*

## Resource references, MBR, and budget

### An ABI return value is a log entry, and the log budget is smaller than the argument budget

The AVM has no return channel. `return` from an `abimethod` compiles to a `log` of the four-byte prefix `0x151f7c75` followed by the ARC-4 encoding of the value. An application call may log **1,024 bytes** in total across at most 32 `log` calls, while it may carry **2,048 bytes** of arguments --- so a method that echoes or expands its input can be made to fail by a caller who does nothing more unusual than sending a large argument. Bound anything variable-length that you return, and bound it well below the ceiling so the number means something to the caller.

*From {{ch:mental-model}}.*

### Opting a user in raises the user's minimum balance, not the application's

An application opt-in costs the *opting account* 100,000 microAlgos plus 28,500 per declared local uint and 50,000 per declared local byte slot. Declaring a generous local schema you never fill is therefore a tax you levy on every one of your users, forever, and the failure mode when they cannot pay it is a balance error that never mentions your application.

*From {{ch:state}}.*

### Opcode budget and fees pool over different transactions

Opcode budget and fees pool over different sets of transactions. Fees pool across the **whole group**: one transaction may overpay and cover a sibling of any type. Opcode budget pools only across the **application-call transactions** in the group --- adding a payment transaction to raise your compute ceiling does nothing at all. Two mechanisms, two scopes, and a group padded with the wrong transaction type fails with an opcode-budget error that looks like a fee problem.

*From {{ch:avm-limits}}.*

### An undeclared resource fails the program, it does not read as empty

An unavailable resource does not read as empty --- the program fails outright, with `unavailable Account` or `invalid Box reference`. This is why a method that works when called by the account that owns the box fails when called by anyone else: the sender is always implicitly available, and every *other* account has to be declared. algokit-utils 4.x populates most references automatically from the ABI method signature, which is a convenience and not a guarantee; anything the signature does not name, you declare yourself.

*From {{ch:avm-limits}}.*

## Cross-contract calls

### A contract's own global state is not evidence about its parent

Reading `factory_app_id` out of a pool and comparing it to the factory you trust proves only that the pool *claims* that parent. Global state is writable by its own application and by nothing else, which cuts both ways: nobody can forge the real factory's state, and anybody can forge a claim about it. Verification has to run in the direction where the trusted party is the writer --- ask the factory whether it created this pool, never ask the pool who created it. The same asymmetry governs every cross-contract trust decision in this book.

*From {{ch:amm-factory}}.*

### A cross-contract read spends one of the transaction's reference slots

The foreign apps array has a maximum of 8 entries per transaction (shared across the group since AVM v9). Each cross-contract read consumes one slot. If your transaction already references several apps, you may not have room for the AMM reference. Plan your foreign reference budget carefully when designing multi-contract interactions.

*From {{ch:yield-farming}}.*

## Pricing math

### Never price against spot: a single atomic group can move it

The preceding spot price example is shown for educational purposes. In production, always use the TWAP. External contracts can read the cumulative price accumulators from the pool's global state, store periodic snapshots, and compute the TWAP over their desired window.

*From {{ch:amm}}.*

### Updating the accumulator with zero stake divides by zero

The zero-balance guard is critical. If `total_staked` is zero, the update must be skipped entirely --- dividing by zero panics the AVM, and accumulating rewards when nobody is staked would create tokens from nowhere. Always check `total_staked > 0` before updating the accumulator.

*From {{ch:yield-farming}}.*

### Distribution must never exceed rate times elapsed time

The total rewards distributed must never exceed `reward_rate * elapsed_time`. Rounding in `op.divmodw` floors toward zero, ensuring the contract always retains dust. If you ever observe total distributions exceeding the reward pool, you have a bug. This is the single most important property to verify in your tests.

*From {{ch:yield-farming}}.*

### Enough stake floors the per-token increment to zero and rewards stall

`PRECISION = 10^9` also sets a *usability bound* on the other side. Each update computes $increment = \lfloor rate \times \Delta t \times 10^9 / \text{total\_effective} \rfloor$, so whenever `total_effective` exceeds $rate \times \Delta t \times 10^9$, the increment floors to zero --- yet `last_update_time` still advances, so that interval's rewards are permanently stranded. With very large stakes relative to the reward rate, most of a schedule's rewards can strand this way. Conservation still holds --- the contract never overpays, and unstreamed rewards simply stay in `rewards_remaining` --- but stakers receive less than the advertised rate. Production systems shrink the loss to negligible by using $10^{18}$-scale precision (with `BigUInt` arithmetic) or by carrying the division remainder forward between updates.

*From {{ch:yield-farming}}.*

## LogicSigs

### LogicSig arguments are public and are not covered by the signature

A delegated LogicSig's signature covers the *program*, not the arguments handed to it at submission time. `Arg[0]` is attacker-controlled input, visible on-chain, and changeable by anyone holding the signed program. Any value that must not be tampered with belongs in a `TemplateVar`, which is compiled into the bytes and therefore into the hash the signature is over. Putting a price, a recipient, or an amount in an argument and treating it as authorized is the single most direct way to lose the funds a delegated LogicSig protects.

*From {{ch:limit-order-book}}.*

### suggested_params() can hand you a last_valid past the LogicSig's expiry

**`last_valid` must respect EXPIRY_ROUND.** The LogicSig asserts `Txn.last_valid <= EXPIRY_ROUND`. If `suggested_params()` returns a `last_valid` round beyond the LogicSig's expiry, the fill transaction will be rejected by the LogicSig. Always set `sp.last = min(sp.last, expiry_round)` on the sell-side transaction before submitting.

*From {{ch:limit-order-book}}.*

### A delegated signature is valid forever unless the program says otherwise

There is no revoke. Once Alice signs a LogicSig, anyone who holds those bytes can submit them for as long as the program keeps approving, and deleting her wallet's copy changes nothing. Expiry is something you compile in --- a `Txn.last_valid <= EXPIRY_ROUND` assertion --- or something you build out of on-chain state the program is forced to consult, as `fill_order`'s status check does here. A delegation with neither is a permanent, transferable claim on the signer's account, and the only way to withdraw it is to rekey the account away.

*From {{ch:limit-order-book}}.*

### Missing close-to and rekey-to checks are the first thing an attacker tries

Every LogicSig that authorizes a payment must assert `Txn.close_remainder_to == Global.zero_address`; every one that authorizes an asset transfer must assert `Txn.asset_close_to == Global.zero_address`; and every one of them, whatever the type, must assert `Txn.rekey_to == Global.zero_address`. Miss the close check and a transaction that looks like a one-Algo transfer drains the account's entire balance to the attacker. Miss the rekey check and they take the account outright, permanently, signature and all. These three lines are not defence in depth; they are the load-bearing checks, and they are the most common finding in LogicSig audits by a wide margin. Note that they belong in LogicSigs specifically --- asserting them on incoming group transactions in a stateful contract restricts the user's wallet for no security benefit at all.

*From {{ch:limit-order-book}}.*

## Cryptography

### One mimc hash costs more than an application call's entire budget

**`reveal_vote` cannot fit in a single app call's opcode budget.** The `mimc` opcode costs 10 + 550 per 32-byte block, so hashing the 64-byte `choice || randomness` input costs 1,110 budget units --- well beyond the 700-unit budget of one application call. The `ensure_budget(UInt64(1200), OpUpFeeSource.GroupCredit)` call at the top of the method solves this on-chain: the contract issues no-op inner app calls that each add 700 units to the pooled budget, with their fees paid from the group's pooled fee credit (so the caller simply overpays the outer transaction fee). Without it, every reveal fails with a "dynamic cost budget exceeded" error. This is the same opcode budget management pattern as {{ch:patterns}}'s Pattern 9.

*From {{ch:zk-voting}}.*

## Testing and simulation

### simulate replaced dryrun; dryrun is gone from the node entirely

Older material, blog posts, and a good deal of surviving example code reach for the `dryrun` endpoint for exactly this job. It has been removed from go-algorand --- not deprecated, removed --- and any SDK call to it now fails against a current node. `simulate` is the replacement and it is strictly better: it runs the real program against real ledger state, honours the group, and can be asked for opcode-level traces. If you find yourself reading documentation that mentions `dryrun`, treat everything around it as dated by several protocol versions.

*From {{ch:testing}}.*

### time.sleep() does not advance LocalNet's block timestamp

On LocalNet, block timestamps only advance when new blocks are
produced, and blocks are produced on demand when transactions are submitted.
Calling `time.sleep(N)` alone does NOT advance the block timestamp. You must
also submit a transaction, even a zero-amount self-payment, to produce a block
with the updated timestamp. A typical `advance_time` helper sleeps for the
desired duration, then sends a dummy transaction to trigger a new block:

```python
import time
def advance_time(algorand, seconds):
"""Sleep, then send a dummy txn to produce a block with updated timestamp."""
time.sleep(seconds)
dispenser = algorand.account.localnet_dispenser()
algorand.send.payment(
algokit_utils.PaymentParams(
sender=dispenser.address,
receiver=dispenser.address,
amount=algokit_utils.AlgoAmount.from_micro_algo(0),
)
)
```

For testing, use short durations for cliff and vesting periods. For example,
set a cliff of 8 seconds and total vesting of 30 seconds instead of 90 days
and 365 days.

*From {{ch:token-vesting}}.*

### Identical app calls in quick succession collide as duplicate transaction IDs

Sending identical app calls in rapid succession on LocalNet can
produce identical transaction IDs, causing `"transaction already in ledger"`
errors. Add a unique `note` field to each transaction, such as
`note=os.urandom(8)` or `note=f"test-{i}".encode()`. In practice, add
`note=os.urandom(8)` to every `AppClientMethodCallParams` and
`PaymentParams`/`AssetTransferParams` in your test helpers; it costs nothing
and prevents intermittent test failures.

*From {{ch:token-vesting}}.*

## Compilation, tooling, and shipping

### An assert with no message produces a program counter and nothing else

Assertion messages do not exist on chain. The AVM aborts at a program counter; the compiler stores your message in the ARC-56 app spec under `sourceInfo.approval.sourceInfo[]`, keyed by that counter, and the client SDK maps the number back to the string. An `assert` written without a message contributes no entry at all, so there is nothing to map and your caller sees `assert failed pc=78`. This bites hardest on contracts other teams integrate against, because they may not have your source --- and it bites in production, where you are reading a failed transaction hours after the fact. Give every assertion a message, and ship the app spec alongside the contract.

*From {{ch:mental-model}}.*

### The minimum fee is a consensus parameter, not a constant

1,000 microAlgos is the minimum fee *today*. It is a consensus parameter, which means it can change at a protocol upgrade, and client code that multiplies a hard-coded 1,000 by a group size will underpay the whole group the moment it does. Read it from `suggested_params()` and scale that. Inside a contract you have no such option --- a fee cap like `assert Txn.fee <= UInt64(10_000)` has to use a constant --- but that is a safety bound rather than a computed fee, and choosing it generously costs nothing.

*From {{ch:patterns}}.*

### byte[] application arguments need their ARC-4 length prefix

**ARC-4 encoding for `byte[]` parameters.** The `place_order` method's `lsig_hash` parameter has type `Bytes`, which requires proper ARC-4 encoding when called via `app_args`. Do not pass raw 32-byte values directly in `app_args` --- use `AtomicTransactionComposer` or `algosdk.abi` for correct length-prefixed encoding. The typed client generated by `algokit generate client` handles this automatically.

*From {{ch:limit-order-book}}.*

### LocalNet reset invalidates every hard-coded app ID

`algokit localnet reset` wipes app IDs along with everything else. Any script that hard-codes an application ID --- including the `app_id=1001` shown later in this appendix --- stops working the moment you reset, and the error you get back is a confusing "application does not exist" rather than anything about the reset. Re-deploy after every reset, or read the ID from `deploy_result` instead of pasting it.

*From {{ch:setup}}.*

### `algokit compile py` is not `algokit project run build`

`algokit compile py` and `algokit project run build` are not interchangeable. `compile py` compiles a standalone file and drops its artifacts wherever you point it; `project run build` runs the whole pipeline defined in `.algokit.toml`, which also places artifacts in the location the template's scripts expect and generates the typed client. Use `compile py` and your deploy script will fail to find the app spec at the path every example in this book assumes.

*From {{ch:setup}}.*

### puyapy does not target the newest AVM version by default

`puyapy` does not default to the newest AVM version the network supports --- it defaults to a conservative one, currently 11. Code that uses a v12 feature compiles without complaint and then fails at assembly with an opcode error, or worse, silently takes a different code path. Pass `--target-avm-version` explicitly on every build; the projects in this book set it in `.algokit.toml` so the flag cannot be forgotten.

*From {{ch:avm-limits}}.*
