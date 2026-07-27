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

### Returning False from the clear state program does not keep the account attached

The clear state program's return value decides only whether its own logic is credited, not whether the account detaches. The local slab is deleted and the account's minimum balance released either way --- and the same is true if the program errors or runs out of budget, which is the whole point of the guarantee: a user must never be able to be held to an application by a contract that refuses to let go. Anything you were planning to enforce on the way out belongs in `CloseOut`, which a contract *can* reject, and anything a user could lose by skipping `CloseOut` must not have been stored in their slab in the first place.

*From {{ch:state}}.*

### An account balance is not an accounting record

`Global.current_application_address.balance` tells you what the account holds. It does not tell you what anyone is owed, because it also counts the minimum balance, the funding that got the contract running, fee refunds, and anything a stranger chose to send. A contract that prices positions off its balance can have every position re-valued by an outsider making a payment, which in an empty pool means the first depositor sets the price to whatever they like --- the first-depositor donation attack, met again in the AMM. Keep the ledger in state you write, check withdrawals against the ledger, and treat the balance as a liveness signal at most. When the two disagree, the difference is information: it is fees you paid, donations you received, or a bug, and all three are worth knowing about.

*From {{ch:moving-value}}.*

### The state schema is fixed at creation and can never be widened

The number of global and local slots an application declares is written into the create transaction and is immutable for the life of the contract. There is no migration, no resize, no `UpdateApplication` escape hatch --- a contract that needs a sixty-fifth global key needs a new application and a state migration you write yourself. The MBR is charged for what you *declare*, not what you use, so a slot reserved against future need costs 28,500 or 50,000 microAlgos whether you ever write to it or not. That is the price of the option, and it is usually worth paying.

*From {{ch:token-vesting}}.*

### ClearState always succeeds, so local state cannot hold an obligation

Users can delete their local state at any time via ClearState, and the protocol guarantees this always succeeds. Never use local state as the sole record of financial obligations, debts, or token claims.

*From {{ch:token-vesting}}.*

## Box storage

### Two BoxMaps with variable-length keys can name the same box

A `BoxMap` box name is nothing but `key_prefix + encode(key)`, so a map with prefix `b"a"` and key `b"bc"` names the same box as a map with prefix `b"ab"` and key `b"c"`. The second write silently overwrites the first and no tool warns you, because concatenation cannot tell where you meant the seam to be. Fixed-width keys --- `Account`, `UInt64`, a fixed-size struct, a `FixedArray` --- are immune, since every name in the family is the same length. With `Bytes`, `String`, or dynamic array keys, give every map a prefix of the same length or include a separator that cannot occur in a key.

*From {{ch:boxes}}.*

### Box.splice never changes a box's size

`splice(start, length, value)` looks like a list insertion and is not one: after removing and inserting, it forces the result back to the box's original size. Inserting eight bytes pushes eight bytes off the end; removing eight appends eight zero bytes. `resize` is the only operation that changes a box's size, and it is also the only one that changes the minimum balance --- so if you want an insertion that grows the box, `resize` first and `splice` second.

*From {{ch:boxes}}.*

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

### Dividing before multiplying silently returns zero

`(a // b) * c` is integer division first, so it returns zero for every input where `a < b` --- which for a proportion means every input except the last one. It is the transcription every spreadsheet formula invites and it produces a contract that pays nothing at all until the moment it pays everything. Write `(a * c) // b` instead. Doing so moves the risk from rounding to overflow, which is a trade you want, because overflow aborts loudly and rounding-to-zero does not: route the product through `op.mulw` and `op.divw` and both problems are gone at once. No test that checks only the endpoints of a schedule will catch this, because the endpoints are the two points the wrong form gets right.

*From {{ch:numbers-and-time}}.*

### Overflow and underflow end the transaction, they do not wrap

On the AVM, `a + b` past 2^64-1 reports `+ overflowed`, `a - b` with `b > a` reports `- would result negative`, and `a // 0` reports `/ 0` (while `a % 0` reports `% 0`). None of them wrap, none of them return a sentinel, and none of them are catchable --- the transaction is discarded, so there is no state left to inspect and no assertion of yours to fire. The consequence is denial of service, not theft: a contract holding funds can become permanently uncallable on an input path nobody tested, especially if the offending value was set by an init-once method. Test the boundaries, not the middle. And note that the wording differs between the chain and `algopy_testing`, which reports `OverflowError: + overflows` and `ArithmeticError: - underflows` --- never quote one as the other in a runbook.

*From {{ch:numbers-and-time}}.*

### Guard a divisor where it is set, not where it is used

A division-by-zero guard placed at the division site has to be repeated at every division site, and the day somebody adds a third one it will not be. Put it in the method that establishes the value --- `assert shares > UInt64(0)` in the setter, `assert end > start` in `configure` --- and it holds for every use forever, including uses that do not exist yet. This matters more than it sounds because in practice the divisor is usually a *difference* (`end - start`, `total - claimed`), so one assertion about the ordering of two parameters retires both the `/ 0` and the `- would result negative` in a single line. PuyaPy warns about a literal `// UInt64(0)` and says nothing at all about a zero that arrives in a variable, which is every zero that has ever caused an incident.

*From {{ch:numbers-and-time}}.*

### Txn.last_valid is a number the caller chose

Reading `Txn.last_valid` as "now" hands the caller control of your clock: they may set it up to a thousand rounds beyond the current round, for free, on every call, and nothing about such a transaction looks unusual. Against a time-based release schedule that is roughly forty-six minutes of unearned progress per transaction, repeatable as fast as fees can be paid. It survives testing for the opposite of the obvious reason: AlgoKit Utils widens the validity window to the protocol maximum of a thousand rounds on LocalNet, so your tests already run the attack at full strength and pass anyway, because they assert that a call returned rather than that it returned the right number. The safe use of the field is the opposite direction: `assert Txn.last_valid <= EXPIRY` bounds a number the caller chose, which is fine, because a caller who chooses badly only hurts themselves. Use `Global.round` for "now", always --- and remember that `Global.latest_timestamp` is the *previous* block's timestamp, so the two are never describing the same block.

*From {{ch:numbers-and-time}}.*

### Block seeds are already public when the caller builds the transaction

`op.Block` can only read rounds at or before `Txn.first_valid - 1`, and that round is committed and public before the transaction exists --- so a caller can compute your contract's "random" answer off-chain, check whether they win, and submit only when they do, for free, as many times as they like. The common objection to `blk_seed` --- that a proposer might choose a favourable seed --- is actually false, since the seed is a VRF output the proposer can compute but not select. The real problem is worse and needs no proposer at all, and no arrangement of the code fixes it. Use a commit-reveal shape against the ARC-21 randomness beacon: commit publicly to a future round, close entries, then read that round's value once it exists. Note also that the readable window is `1001 - (last_valid - first_valid)` rounds wide, so a transaction with a full validity window can read exactly one block --- and that `blk_timestamp(Global.round - 1)` never works at all. The readable window ends at `first_valid - 1`, and `first_valid` is the last round already committed when the transaction was built, so `Global.round - 1` is always at least one round too new. Reach for `Txn.first_valid - 1` instead.

*From {{ch:numbers-and-time}}.*

### UInt64 overflow fails the transaction; it does not wrap

Read the swap formula again with an eye on the numerator: `delta_x * 997 * y`. With reserves in the billions of base units --- entirely ordinary for a six-decimal stablecoin --- that product passes $2^{64}$ long before anything looks large in human terms. The AVM does not wrap on overflow, it panics, so the failure mode is a swap that simply stops working once the pool gets deep enough, in production, having passed every test written against a small pool. Any multiplication whose operands are both user-scaled needs `op.mulw`, `op.divmodw`, or `BigUInt`. Test the arithmetic at the top of the range, not the middle.

*From {{ch:amm}}.*

### op.btoi fails on a BigUInt wider than eight bytes

The `op.btoi` call accepts a byte array of 0--8 bytes and interprets it as a big-endian unsigned integer. A `BigUInt` that exceeds $2^{64} - 1$ would produce more than 8 bytes, causing `btoi` to fail at runtime. The `assert twap < BigUInt(2**64)` guard ensures the TWAP result fits in 64-bit range before the conversion. With `TWAP_PRECISION = 10^9` and typical asset prices, this bound is safe for years of accumulation. If you use a higher precision scale factor or expect extreme price ratios, return a `BigUInt` instead of converting to `UInt64`.

*From {{ch:amm}}.*

## Inner transactions

### A non-zero inner transaction fee is paid out of the contract's own balance

The fee on an inner transaction comes from the application account, never from the caller. `fee: UInt64 | int = 0` is already the default on every `itxn` builder in algorand-python, so the danger is not an omitted fee --- it is a fee somebody wrote a non-zero value into, most often `Global.min_txn_fee` in the belief that a transaction must carry one. On a method anybody may call, that is an unbounded drain at 1,000 microAlgo per call, and it does not stop being a problem when the balance is large: draining the account toward its minimum makes every other inner transaction the contract wants to send start failing. Write `fee=UInt64(0)` explicitly so the omission reads as a decision, and make the caller cover the group with `assert Txn.fee >= UInt64(TOTAL)`, counting one minimum fee per transaction including the inner ones. Fees pool across an atomic group; that is what makes a zero-fee inner transaction valid in the first place.

*From {{ch:moving-value}}.*

### An application account's balance is not what it can spend

Every Algorand account that still exists when a transaction settles must hold at least its minimum balance, and an application's account is no exception: 100,000 microAlgo to exist, plus 100,000 per asset it holds, plus its box charges. Its declared schema is not in that sum --- schema minimum balance is billed to the creator and to the accounts that opt in, never to the application account. An inner payment of `app.balance` therefore fails for every account that will still exist afterwards --- not for large amounts, for every amount --- and it fails twice over. The fee is the first reason: an inner transaction's fee is taken from the application account *before* the payment is applied, so an instruction to send the whole balance is short by exactly one fee before it is ever attempted, and the message says `overspend` rather than anything about a minimum balance, which sends people looking in the wrong place. The second reason survives `fee=UInt64(0)` entirely: an account holding one asset owes 200,000, and a payment leaving it at zero is refused when the group settles --- this time with a message that does name the minimum, and from the ledger rather than from your program. The only account that slips past both is one holding nothing else at all, which is emptied and deleted rather than checked, and that is a closure, not a withdrawal. Spend `app.balance - app.min_balance`, set `fee=UInt64(0)` so nothing is taken first, and remember that this figure moves: opting into one more asset raises the floor by 100,000 microAlgo and silently reduces what a previously-working withdrawal may send. The failure mode is worse than a rejected transaction, because a contract whose only withdrawal path is unconditionally broken and whose account has no private key is holding money nobody can ever reach.

*From {{ch:moving-value}}.*

### Inner transactions have three separate ceilings, and one of them is depth

An application call may issue at most 16 inner transactions, a group may contain at most 256 across all of its calls, and the call chain may descend at most 8 applications deep --- the eighth contract cannot call another. A loop that emits one inner transfer per position works beautifully for twelve positions and fails at seventeen with an error naming none of this. Each inner application call also adds 700 units to the pooled opcode budget when it is submitted, which is a gift, not a cost. And no inner transactions may be issued from a ClearState program at all, so a clear-state path can never return anything to the user.

*From {{ch:yield-farming}}.*

## ASAs

### Two asset arguments may name the same asset

Two parameters of type `Asset` are two names, not two things, and neither the ABI nor the AVM will stop a caller passing one asset for both. In a pool contract, every later method reads the two as opposing sides of a trade and each of those methods is individually correct; with one asset on both sides, a deposit becomes instantly withdrawable from the other side at whatever the pricing arithmetic produces. This is the core of the Tinyman V1 exploit of January 2022, worth roughly three million dollars, and the fix is `assert a.id != b.id` in the method that stores them. The same reasoning applies to any pair of same-typed arguments that the contract will later treat as distinct --- two accounts, two boxes, two application ids.

*From {{ch:moving-value}}.*

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

### A typed group argument checks the type, never the contents

`payment: gtxn.PaymentTransaction` guarantees that the named slot holds a payment. It guarantees nothing about the receiver, the amount, the sender, or --- for an asset transfer --- which asset. A payment the caller sent to their own account satisfies the type perfectly, costs one fee, and leaves their balance where it started, so an unchecked deposit method hands out positions for free. Ask all four questions on every incoming transfer: `xfer_asset` against a stored id, `amount` against a floor, `receiver` against `Global.current_application_address`, and `sender` against `Txn.sender`. The asset id in particular must come from state your contract wrote, never from a method argument --- an id the caller supplies is a formality the caller performs on themselves.

*From {{ch:moving-value}}.*

### A group index check without a group size check bounds nothing

Checking `Txn.group_index` says where your call sits; it says nothing about how many other transactions ride alongside it, and a group may hold sixteen. A method that reads a payment at a fixed index and never asserts `Global.group_size` can be called once per remaining slot against the same payment, crediting the same money up to sixteen times in one atomic group --- every transaction in which is valid, correctly signed, and honest about what it is. This is what makes the receiver and asset checks worth having: an attacker who cannot forge a transfer can still restructure the group around one. A typed group parameter already reads position-relatively --- PuyaPy lowers it that way --- but that is the compiler's choice, not your assertion, and it bounds one slot and nothing else. Assert the size and the index together, and read neighbours position-relative (`Txn.group_index - 1`) rather than absolutely, so the pattern survives being nested later.

*From {{ch:moving-value}}.*

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

### create=allow removes the application-ID check, and at ID zero every caller is the creator

The three values of `create` are not three flavours of the same check. `"require"` asserts the application ID is zero and `"disallow"` asserts it is non-zero; `"allow"` deletes the assertion, and the generated router matches such a method *above* the `txn ApplicationID` branch entirely. A caller can therefore send it against application ID zero, which creates a fresh application from your program, runs `__init__`, and executes the method against empty state. Any guard of the form `Txn.sender == Global.creator_address` passes there, because the sender is the one doing the creating. Use `"allow"` only for a method genuinely designed to run in both worlds, and if you cannot say in one sentence what it should do at ID zero, you want `"disallow"`.

*From {{ch:contracts}}.*

### Assert that the funding transaction's sender is the account being credited

The pattern below reads a payment from the group and credits `Txn.sender`. Those are two different accounts unless you say they are the same one. Left unasserted, anyone can build a group that pairs *somebody else's* pending payment with their own app call and take the position it paid for --- the payment is valid, the app call is valid, and the contract cheerfully credits the wrong party. Whenever a grouped transfer funds something that is booked to `Txn.sender`, assert `payment_txn.sender == Txn.sender`. If you genuinely want third-party sponsorship, model the beneficiary as an explicit method argument rather than leaving it implied.

*From {{ch:patterns}}.*

## Resource references, MBR, and budget

### An ABI return value is a log entry, and the log budget is smaller than the argument budget

The AVM has no return channel. `return` from an `abimethod` compiles to a `log` of the four-byte prefix `0x151f7c75` followed by the ARC-4 encoding of the value. An application call may log **1,024 bytes** in total across at most 32 `log` calls, while it may carry **2,048 bytes** of arguments --- so a method that echoes or expands its input can be made to fail by a caller who does nothing more unusual than sending a large argument. Bound anything variable-length that you return, and bound it well below the ceiling so the number means something to the caller.

*From {{ch:mental-model}}.*

### ARC-4 bools share a byte only while they are adjacent, so field order changes the size

Eight `arc4.Bool` values in a row occupy one byte. Put any non-bool field between two of them and each is rounded up to a byte of its own: `(bool,bool,uint64)` encodes in nine bytes and `(bool,uint64,bool)` in ten, for the same three values. In a tuple that is one byte. In a struct with sixteen flags interleaved with other fields it is fourteen wasted bytes on every read and every write, and in box storage those bytes are priced at 400 microAlgos each, forever. Group your bools.

*From {{ch:contracts}}.*

### Opting a user in raises the user's minimum balance, not the application's

An application opt-in costs the *opting account* 100,000 microAlgos plus 28,500 per declared local uint and 50,000 per declared local byte slot. Declaring a generous local schema you never fill is therefore a tax you levy on every one of your users, forever, and the failure mode when they cannot pay it is a balance error that never mentions your application.

*From {{ch:state}}.*

### Writing a box can make a contract that worked yesterday stop working today

Creating or growing a box raises the *application account's* minimum balance by 400 microAlgos per byte, plus 2,500 for each new box --- and nothing about that shows up in the source, in a compiler warning, or in a test. The contract keeps working until the account's balance meets a floor that has been rising underneath it, and then every call that writes a box fails at once, with an error about an account rather than about a box: `account <address> balance <n> below min <m> (<k> assets)`. That is not a `LogicError` and it will not be caught by anything asserting on your messages, because the check happens after your program has already run and returned success --- there is no assertion of yours left to fire. A contract whose storage grows with usage needs either a funding plan that grows with it or a pre-flight check like {{ex:app-mbr-floor}} that refuses in a sentence a caller can act on. Deleting or shrinking a box gives the whole charge back, which is the only thing in this chapter that makes the floor go down.

*From {{ch:boxes}}.*

### A box is charged at its full size, however few bytes you touch

Each box reference grants 2,048 bytes of I/O budget, and that allowance is checked as **two separate budgets that are never added together**. The *read* budget is charged before your program runs, as the sum of the full current sizes of every referenced box that exists --- even one you never intended to read. The *write* budget is charged as the full size of each box written, once per box, with `box_resize` charging the full **new** size. Neither charges the bytes you touched: `extract`, `replace`, and `.length` all cost the same as `.value`, because the charge happened before and around them. Both budgets pool across the whole transaction group, and references need not be distinct --- duplicate and empty references each grant another 2,048 bytes, which is the fix. algokit-utils pads up to eight references for you by default, so a budget failure that padding can cover will not appear until the call is assembled by something that does not pad: another contract, a hand-built transaction, a different SDK.

*From {{ch:boxes}}.*

### A loop bounded by a runtime value has a ceiling you did not choose

`while index < count` over box entries compiles cleanly, because `count` is a runtime value and the compiler has no opinion about it. What stops it is the box-reference cap or the 700-unit opcode budget, and in practice the reference cap arrives first, because the cap --- eight on the legacy foreign arrays, sixteen on the v41 `Access` list --- is a much lower ceiling than 700 units of arithmetic. Both arrive as a failed transaction in production rather than as an error at build time. Marking the method `readonly=True` buys you a delay and not a reprieve: the tooling simulates it with a 320,000-unit opcode budget, so the loop that dies on chain at entry 30 may run to entry 8,000 in your tests and then die anyway. Bound the loop by a constant the contract chose and let the caller page.

*From {{ch:boxes}}.*

### Unnamed resources are a discovery tool, not a permission

Setting `allow_unnamed_resources=True` on a simulate lets the program reach accounts, assets, applications and boxes that the transaction never declared, and reports every one of them back under `unnamed-resources-accessed`. It is tempting to read a passing simulate as evidence the call works. It is not: the submitted transaction is still subject to the ordinary resource rules and will fail on the first undeclared reference. The flag exists so that tooling can *find out* what to declare --- algokit-utils uses exactly this response to populate the reference arrays for you --- and the correct use is to run the simulate, read the resources back, and put them in the real call. A related trap sits next to it: the resource arrays have a per-transaction cap, and a method that touches more than fits cannot be fixed by declaring harder. It has to be split across a group, which is a design change and better discovered here than in production.

*From {{ch:testing}}.*

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

### A method marked readonly is answered by simulation, so anything it writes is silently discarded

`readonly=True` is a permission granted to callers, not a restriction imposed on you: the compiler does not stop a readonly method from writing state, and if you submit one as a real transaction its writes commit normally. What happens instead is that every conforming client reads the flag out of the app spec and answers the call with `simulate` --- no fee, no round, no ledger change --- and reports the returned value as though it had happened. A readonly method that mutates therefore produces correct-looking answers forever while changing nothing, and the discrepancy only appears when somebody reads the chain directly. The rule is mechanical: if the method body can reach an assignment to state or an inner transaction, it is not readonly. The simulation is a client-side courtesy and a caller can decline it --- `counter.new_group().bump().send()` builds a real group and submits it --- but reaching for that to make a readonly method write is a sign the flag is on the wrong method.

*From {{ch:contracts}}.*

### A failed transaction returns no logs; a failed simulation does

It is natural to assume that if a contract logs its reason before failing, the reason comes back with the rejection. It does not, on a submitted transaction: the node's response to a failed `POST /v2/transactions` is a message and nothing else, with no logs array, no matter what the program logged before it aborted. Logs from a failing group survive in exactly one place --- the simulate response, at `txn-groups[g].txn-results[i].txn-result.logs`, which the simulator saves specifically because a debugging tool needs them. They are not on the execution trace either; a trace unit carries a program counter, stack and scratch changes, and spawned inner transactions, and has no log field. So ARC-65's promise that the failure reason is recoverable from the API response is true of simulate and false of a real submission. Plan your error reporting accordingly: for a client that can afford to re-run a failure through simulate, logs are recoverable; for one reacting to a rejection in the wild, the program counter is all there is.

*From {{ch:testing}}.*

### A failing simulate raises rather than returning a failure

`composer.simulate()` and the group-level `.simulate()` in algokit-utils inspect the response before handing it back, and if the group failed they raise `LogicError` instead of returning. This catches out almost everyone writing a negative test for the first time, because the natural shape --- call simulate, then read `failure-message` off the result --- has no result to read. Everything you wanted is on the exception: `.message`, `.pc`, `.transaction_id`, and `.traces`, which carries the execution trace if you enabled it. Wrap the call in `try`/`except LogicError` and assert against `.message` specifically rather than merely that something was raised --- and assert with `in`, because `.message` wraps your string in the contract name, application ID and transaction ID. Two related facts are worth carrying. algokit-utils turns on `allow_more_logs`, `allow_unnamed_resources`, `allow_empty_signatures` and a full trace config on every simulate it makes, and always substitutes an empty signer, so a simulate that succeeds is not evidence that the same group would have been accepted with real signatures and declared resources. And `simulate` is the only endpoint for this job now: `dryrun` has been removed from go-algorand outright, not deprecated, so any older material or example code that reaches for it is dated by several protocol versions.

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
    """Sleep, then send a dummy txn to produce a block."""
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

### from_bytes relabels bytes as an ARC-4 value and verifies nothing; validate is the check it skipped

`arc4.String.from_bytes(raw)` emits no opcodes and performs no validation --- the stub documentation says so --- so a length prefix that disagrees with the payload behind it sails through and fails somewhere else, later, in code that had nothing to do with the decision. PuyaPy does insert argument validation on ABI methods by default, which is why this mostly bites on values you assembled yourself from boxes, logs, or arguments to a method carrying `validate_encoding="unsafe_disabled"`. Where you have disabled it for opcode budget, `.validate()` is not optional; it is the same check, moved to a line you chose.

*From {{ch:contracts}}.*

### A byte[] return arrives at the client as a list of integers, and no decoder will guess otherwise

Returning `Bytes` from an ABI method gives the method a `byte[]` return type, and a conforming client decodes `byte[]` into a list of integers --- because that is what the type means. Text that you concatenated by hand comes back as `[118, 105, 115, ...]`, and the caller has no way to know it was ever meant to be read. This never raises: it is a wrong answer that succeeds. If the value has structure, say so in the return type --- `arc4.String`, a tuple, a struct --- and let the encoding carry the meaning instead of a comment in your codebase.

*From {{ch:contracts}}.*

### The string in an assert message is not in your program

`assert cond, "message"` puts the string in two places and neither is the chain: a TEAL comment, which is discarded at assembly, and an ARC-56 `sourceInfo` entry keyed by the program counter of the `assert` opcode. The compiled bytes do not contain it --- `b"owner only" in bytecode` is `False` --- and the AVM reports only `assert failed pc=85`. Everything legible after that is a client-side lookup against the app spec, which means a caller integrating from a different toolchain, a different language, or a block explorer gets a number and has to come and ask you what it means. Worse, a *bare* `assert` with no message produces no `sourceInfo` entry at all, so it is invisible to every tool that reads the spec, and it will sit in the bytecode immediately beside the existence assertions PuyaPy inserts on state reads, which do have messages. If the reason must survive without the app spec, `logged_assert()` writes it into the program as an ARC-65 log. Expect the approval program to grow by roughly forty per cent or more for a couple of checks, and be clear that you are buying legibility for callers who lack your artifacts, not for anything on-chain.

*From {{ch:testing}}.*

### A readonly call is simulated with skipped signatures and a huge budget

{{ch:contracts}} established that `readonly=True` is a promise to callers rather than anything the compiler or the AVM enforces, and that a readonly method which writes state has its writes silently discarded. The half that bites later is *how* the client keeps the promise. algokit-utils answers a readonly call with a simulate, and that simulate runs with signatures skipped and the maximum extra opcode budget granted --- which is why a readonly call is free and instant, and also why it is a much more permissive environment than a real submission. A readonly method that consumes 2,000 opcodes answers correctly in your client every time and fails the first time anybody submits it, as does one that needed a signature the simulation waived. The rule is to submit every readonly method at least once, on LocalNet, before you trust the numbers it gives you.

*From {{ch:testing}}.*

### An unconditional failure in a value-returning method deadlocks the type checker

`logged_err()` and `logged_assert()` are typed `-> None` in the algopy stubs, because from Python's point of view they are ordinary calls. PuyaPy knows better and treats them as terminal. The two views collide in a method that returns a value: put `logged_err(...)` as the last statement and mypy reports `Missing return statement`, add a `return` after it to satisfy mypy and PuyaPy reports unreachable code. Neither tool is wrong and there is no flag that resolves it. The shape that compiles is to make the failure a branch rather than a terminator --- bind a local, use `if`/`elif`/`else` with the failure in the `else`, and return the local once at the end. Void methods have no such problem. While you are writing them, expect PuyaPy to warn if your error code is not alphanumeric or not camelCase, to warn once the whole `ERR:code:message` string passes 64 bytes, and avoid the `AER` prefix, which is reserved for specific ARC errors.

*From {{ch:testing}}.*

### The minimum fee is a consensus parameter, not a constant

1,000 microAlgos is the minimum fee *today*. It is a consensus parameter, which means it can change at a protocol upgrade, and client code that multiplies a hard-coded 1,000 by a group size will underpay the whole group the moment it does. Read it from `suggested_params()` and scale that. Inside a contract you have no such option --- a fee cap like `assert Txn.fee <= UInt64(10_000)` has to use a constant --- but that is a safety bound rather than a computed fee, and choosing it generously costs nothing.

*From {{ch:patterns}}.*

### byte[] application arguments need their ARC-4 length prefix

**ARC-4 encoding for `byte[]` parameters.** The `place_order` method's `lsig_hash` parameter has type `Bytes`, which requires proper ARC-4 encoding when called via `app_args`. Do not pass raw 32-byte values directly in `app_args` --- use `AtomicTransactionComposer` or `algosdk.abi` for correct length-prefixed encoding. The typed client generated by `algokit generate client` handles this automatically.

*From {{ch:limit-order-book}}.*

### LocalNet reset invalidates every hard-coded app ID

`algokit localnet reset` wipes app IDs along with everything else. Any script that hard-codes an application ID --- including the `app_id=1001` shown later in this appendix --- stops working the moment you reset, and the error you get back is a confusing "application does not exist" rather than anything about the reset. Re-deploy after every reset, or read the ID from `deploy_result` instead of pasting it.

*From {{ch:setup}}.*

### Compiling a contract is not the same command as building a project

`algokit compile py` and `algokit project run build` are not interchangeable. `compile py` compiles a standalone file and drops its artifacts wherever you point it; `project run build` runs the whole pipeline defined in `.algokit.toml`, which also places artifacts in the location the template's scripts expect and generates the typed client. Use `compile py` and your deploy script will fail to find the app spec at the path every example in this book assumes.

*From {{ch:setup}}.*

### puyapy does not target the newest AVM version by default

`puyapy` does not default to the newest AVM version the network supports --- it defaults to a conservative one, currently 11. Code that uses a v12 feature compiles without complaint and then fails at assembly with an opcode error, or worse, silently takes a different code path. Pass `--target-avm-version` explicitly on every build; the projects in this book set it in `.algokit.toml` so the flag cannot be forgotten.

*From {{ch:avm-limits}}.*
