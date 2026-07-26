\newpage

# Remembering Things: Global and Local State

A contract that cannot remember anything can still be useful --- it can check a signature, enforce a deadline, wave a transaction through. But it cannot run a membership, hold a balance, count anything, or know that you have already been paid. The moment a contract needs to remember, it needs *state*, and state on Algorand is not one thing. It is two things with different sizes, different owners, and --- this is the part that costs people money --- different lifetimes.

## The Problem
Here is a failure with a name: **the registry that owed 4,200 credits to nobody.**

A rewards program stores each member's credit balance in that member's *local state* --- the small slab of key/value pairs the protocol attaches to an account when it opts into an application. This is the obvious choice. Local state is per-account by construction, so each member's balance sits with the member, no lookup key required, no box to fund. The contract also keeps a global `member_count` that it increments on opt-in and decrements on close-out, so the dashboard can show how many people are in the program.

Then a member with 4,200 unclaimed credits sends a *ClearState* transaction. Not a close-out --- a clear-state. The protocol deletes their local slab and does not ask the contract's permission. The clear state program can return `False`; it changes nothing. The member's 4,200 credits stop existing. So does the evidence that they were ever owed.

Two things are now broken and only one of them is visible. The obvious break is the debt: the program's books no longer show a liability it still, in every non-technical sense, owes. The subtle break is the counter. `member_count` was decremented by `leave()`, and `leave()` never ran, so the count is now permanently one too high. Every future close-out makes it worse. There is no method you can add to fix this, because the contract was never told the member left.

Nothing in that story is a bug in anyone's code. Every line does exactly what it says. Something upstream of the code is wrong, and the rest of this chapter is about finding out what.

## What You'll Be Able to Do
By the end of this chapter you will be able to:

- Choose between global state, local state, and a keyed map for a given piece of data, and defend the choice by naming who can destroy it
- Declare a state schema that will still be correct after the features you have not written yet
- Read state that may never have been written, without failing the call
- Pack several fields into one state slot using an ARC-4 or a native struct, and explain when the compiler will make you write `.copy()`
- Handle every point at which an account enters and leaves your application: create, opt-in, close-out, and clear-state
- Predict which of your contract's numbers a departing member can falsify, and restructure so that they cannot

{{fig:state-scopes}} is the picture the rest of the chapter fills in. Read it before you read any code: two slabs, not one store, with an asymmetry on the right that is the whole reason this chapter exists.

{{include-fig:state-scopes}}

## The Mini-Build, Broken
Example: The registry, as first written {#ex:registry-broken}

<!-- finder: see a membership contract that keeps balances in local state -->

{{include-ex:registry-broken}}

{{ex:registry-broken}} is complete and deployable. It compiles, it runs on LocalNet, and it contains three decisions that are wrong. The story above has already shown you one of them; the other two are sitting in plain sight and are easier to find once you know they are there. Read it, deploy it, and then watch it break.

*Predict: three decisions in that contract are wrong. Write your three down now, in whatever words you have --- you are not expected to be right yet. Check them against the diff at the end of the chapter.*

Deploy it:

```console
$ algokit project deploy localnet
registry 1042 deployed
```

Then opt Alice and Bob in, award Alice 4,200 credits, and read the two view methods back. Every reading is correct:

```python
>>> registry.send.members().abi_return
2
>>> registry.send.credits_of(args=(alice,)).abi_return
4200
```

Now have Alice send an application call with `OnComplete=ClearState` instead of calling `leave()`, and read the same two methods again:

```python
>>> registry.send.members().abi_return
2
>>> registry.send.credits_of(args=(alice,)).abi_return
LogicError: cannot fetch key, ... has not opted in to app 1042
```

The count still says 2. Alice is gone.

{{fig:registry-break-trace}} is that sequence drawn out, one column per slab. Read it downward, then read the left-hand column on its own: nothing in it ever learns that the right-hand column stopped existing. That is not a gap in the contract's logic. There is no event to handle.

{{include-fig:registry-break-trace}}

Two failures, and they fail in different ways. `members()` returns a confident, wrong number. `credits_of(alice)` does not return a wrong number --- it *rejects the transaction*. Alice has no local slab any more, and reading the local state of an account that is not opted in is an error, not a zero. The reader who assumed missing-means-empty has now shipped a read-only method that a stranger can make fail.

There is a second, quieter version of the same trap that survives even when the account *is* opted in. `self.credits[member]` compiles down to `app_local_get_ex` followed by an assertion that the key existed. The raw opcode is happy to hand back a zero; PuyaPy is the one that insists the key was really there, on the reasonable theory that you would rather be told.

Two absences, then, and they do not share a fix. The missing *key* --- a slab that exists with nothing written at that name --- is repaired by reading with a default, which the next section shows. The missing *slab* --- Alice's case, the one you just watched fail --- is not repaired by any default argument, and stays open until {{ex:local-state-read}}. Keep the two apart in your head; conflating them is how the wrong fix gets shipped.

Three decisions caused all of this. The five sections that follow take the state model apart, and each one ends by naming what it repairs in the registry. By the end you will be able to state all three in a sentence each.

## The Global Slab
The global slab belongs to the application. It is created when the application is created, it is destroyed when the application is deleted, and no user can touch it. It holds up to **64 key/value pairs** in total, split at creation between `uint64` values and byte-string values.

Example: The two tiers side by side {#ex:state-two-tiers}

<!-- finder: declare both global and local state in one contract -->

{{include-ex:state-two-tiers}}

The load-bearing lines are the two declarations in `__init__`. `GlobalState(UInt64(0))` takes an *initial value* and so is written once at creation; `LocalState(UInt64)` takes a *type* and cannot have an initial value, because there is no account to write it for yet. That asymmetry is the API telling you something true: global state exists as soon as the application does, and local state does not exist until an account opts in.

`state_totals=StateTotals(...)` declares the schema explicitly. PuyaPy can usually infer it, and you should usually write it anyway --- see {{ex:state-schema-fixed}} for the reason.

Example: Reading and writing a global counter {#ex:global-counter}

<!-- finder: keep a counter in global state -->

{{include-ex:global-counter}}

The load-bearing line is `self.count.value += UInt64(1)`. `GlobalState` is a *cell*, not a value: `.value` is how you read through it and write through it. Forgetting `.value` is the most common typo in Algorand Python, and it produces a type error rather than silent nonsense, which is the good outcome.

Because this contract was declared with an initial value, `count` is written at creation and every later read is guaranteed to find it. That guarantee is exactly what the next two examples are about. Its unit test --- which lives at `examples/ch03_state/global_counter_test.py` and runs in CI --- constructs the contract inside an `algopy_testing_context()` and asserts `contract.bump() == 1` and then `== 2`, using the testing patterns from {{ch:testing}}.

Example: Reading state that may never have been written {#ex:global-get-default}

<!-- finder: read a global key that might not exist yet -->

{{include-ex:global-get-default}}

The load-bearing line is `.get(default=UInt64(1000))`. This declaration is `GlobalState(UInt64)` --- a type, no initial value --- so the key genuinely does not exist until somebody writes it. `self.joining_fee.value` on a fresh application would fail the transaction. `.get(default=...)` reads it as 1,000 instead.

This is half the fix for `credits_of` in the broken registry --- the half that covers a key nobody has written yet. It does nothing for Alice, whose slab no longer exists; a default argument is evaluated after the read succeeds, and her read never gets that far. {{ex:local-state-read}} closes that one. A read-only method that a stranger can make fail is a denial-of-service surface on your own dashboard, and it takes both fixes to close it.

Why you would want the failing version instead: sometimes "never written" is a real error and you want the call to stop. That is what {{ex:global-maybe}} is for.

Example: Distinguishing absent from zero {#ex:global-maybe}

<!-- finder: tell the difference between a state key set to zero and one never set -->

{{include-ex:global-maybe}}

The load-bearing line is `fee, exists = self.joining_fee.maybe()`. `.get(default=UInt64(0))` collapses "the fee is zero" and "no fee was ever set" into the same answer. `.maybe()` returns the value *and* a flag, so you can tell them apart. Reach for `.get()` when the default is genuinely correct and `.maybe()` when absence means something.

*Predict: a fee is set to `0` deliberately, to make joining free. What does `.maybe()` return, and what would `.get(default=UInt64(0))` have returned?*

Example: Deleting a global key {#ex:global-del}

<!-- finder: remove a key from global state entirely -->

{{include-ex:global-del}}

`del self.paused_at.value` removes the key, freeing the schema slot for reuse and making `bool(self.paused_at)` false again. Deleting a key does not shrink the declared schema --- the slot stays reserved and the MBR stays paid.

*What this section repairs in the registry:* `credits_of` has two absences, and this section fixes one. A key that was never written should be read with a default. An account with no slab at all is still unhandled, and stays that way for two more sections.

## Schema, Fixed at Creation
Example: Declaring a schema with room to grow {#ex:state-schema-fixed}

<!-- finder: reserve state schema slots for features I have not written yet -->

{{include-ex:state-schema-fixed}}

The load-bearing line is `state_totals=StateTotals(global_uints=8, global_bytes=2)` on a contract that currently uses exactly one uint and zero bytes. This is not sloppiness. It is the single most consequential line in the chapter.

**An application's state schema is fixed at creation and can never be widened.** Not by an update, not by a call, not by anything. The schema fields are read once, off the creation transaction, and are never read again.

What that failure looks like depends entirely on how you deploy, and the two paths could not be less alike.

A raw `ApplicationUpdate` transaction compares nothing. It pushes new bytecode to the existing application ID, the network accepts it, and the schema fields on that transaction are ignored, because schema is a creation-time property. Nothing anywhere reports an error. You find out in production, when the ninth uint the new code writes has nowhere to go.

AlgoKit's `deploy()` does compare, and it stops:

```console
$ algokit project deploy localnet
WARNING: Detected a breaking app schema change in app 1042:
ValueError: Schema break detected and on_schema_break=OnSchemaBreak.Fail,
stopping deployment. If you want to try deleting and recreating the app then
re-run with on_schema_break=OnSchemaBreak.ReplaceApp
```

That is the default, and it is the right one. {{tbl:deploy-decisions}} is the entire decision surface behind that message --- two settings, and nothing else to learn.

Table: What `deploy()` does with a changed contract {#tbl:deploy-decisions}

| What changed | What `deploy()` calls it | What you get to choose |
|--------------|--------------------------|------------------------|
| Nothing | a no-op | nothing; no transaction is sent |
| Only the bytecode | an *update* | `on_update`: `Fail` raises (default), `UpdateApp` keeps the app ID, `AppendApp` creates a second app, `ReplaceApp` creates and deletes |
| Any schema number went up, or extra pages did | a *schema break* | `on_schema_break`: `Fail` raises (default), `ReplaceApp` creates a new app and deletes the old one **in the same group**, `AppendApp` creates a new app and leaves the old one standing |

Look at the third row and notice what is missing from it: there is no option that widens the schema in place, because there is no such thing. Every option in that row produces a **new application ID**, and a new ID means every opted-in account, every stored balance, and every integration pointing at the old one is now pointing somewhere else.

So you reserve. Eight uints and two bytes cost 8 × 28,500 + 2 × 50,000 = 328,000 microAlgos of MBR, about a third of an Algo, one time --- and it is charged to the *creator's* account, not to the application account. Global schema MBR follows the creator; only box storage is funded from the application account itself. That distinction bites when a deployment script funds the app address and then cannot work out why the creator is short.

Why you would want this: every state field you add after launch is either free (because you reserved) or a migration (because you did not).

*Predict: you add a ninth global uint and run `algokit project deploy localnet` against the deployed application. What does `deploy()` print, and what would have happened instead if you had sent a bare `ApplicationUpdate` yourself?*

Example: Redeploying when the schema no longer fits {#ex:factory-deploy-idempotent}

<!-- finder: redeploy a contract whose state schema outgrew the deployed one -->

{{include-ex:factory-deploy-idempotent}}

This one does not run on the AVM --- it is a client-side deployment script, and it is here because it is the escape hatch for the mistake the previous example prevents. The load-bearing line is `on_schema_break=OnSchemaBreak.ReplaceApp`: row three of {{tbl:deploy-decisions}}, chosen deliberately instead of hit by accident.

`ReplaceApp` needs the old application to be deletable. If it is not, AlgoKit attempts the delete anyway and logs that it will most likely fail, which is a confusing way to discover that your migration cannot proceed. And because the delete rides in the same group as the create, `ReplaceApp` against a contract that is holding user funds destroys the contract holding them. It is a reasonable default on LocalNet and almost never one in production.

*What this section repairs in the registry:* the registry declares
`global_uints=1` and has no room to hold anything it takes back from local
state. The corrected contract reserves seventeen before it needs them.

## The Per-Account Slab
Local state is a separate slab per opted-in account: up to **16 key/value pairs**, created by an opt-in, deleted by a close-out or a clear-state. It is stored on the *account*, not on the application, and the MBR for it is paid by the *account*, not by you.

Example: Reading another account's local state {#ex:local-state-read}

<!-- finder: read a specific account's local state from a method -->

{{include-ex:local-state-read}}

The load-bearing line is `member.is_opted_in(Global.current_application_id)`, and it is load-bearing because of a distinction that costs people an afternoon. `LocalState` is indexed by account: `self.credits[Txn.sender]` for the caller, `self.credits[member]` for anyone else. `.get(account, default=...)` covers a key that was never *written* inside a slab that exists. It does **not** cover an account with no slab at all. Reading the local state of an account that has never opted in --- or that opted in and then cleared --- is a ledger error before any default can apply, and no default argument rescues it. Two absences, two different fixes: the opt-in check for the missing slab, the default for the missing key.

There is a second constraint hiding in that innocuous `member: Account` parameter: the AVM can only read the local state of accounts the transaction has explicitly made *available* to it, and that list is short and hard-capped. Reading `Txn.sender`'s slab always works; reading a list of members stops working the moment the list outgrows the cap. The exact numbers and the mechanics of declaring resources are a chapter of their own later in the book. The hint to take now is that local state is a poor fit for anything you need to iterate over.

Example: A keyed map in global state {#ex:global-map}

<!-- finder: store one value per account without requiring an opt-in -->

{{include-ex:global-map}}

`GlobalMap` gives you a keyed map inside the global slab: the `key_prefix` plus the encoded key form the actual state key. Nobody has to opt in, and nobody can walk away with the record.

Read that "inside the global slab" carefully, because it is the map's hard limit. Each entry is one global key/value pair, drawn from the same 64-pair budget the whole application shares. An entry is created by the *write*, not by the declaration: `self.credits[member] = UInt64(0)` spends one of those slots to record a zero that `.get(default=UInt64(0))` would have returned for nothing. Writing placeholder zeros into a `GlobalMap` buys you no correctness and costs you a creditor. `state_totals=StateTotals(global_uints=16)` means sixteen accounts, ever, and the ceiling is 64 minus whatever else the contract stores. A `GlobalMap` is the right shape for a bounded set --- a handful of admins, a fixed roster of pools, the registry in this chapter --- and the wrong shape the moment the number of keys is a function of how popular you get. For per-account data with no ceiling the answer is boxes, and the point here is that moving a record out of local state is not the same as making it unbounded. That is a picture this chapter cannot draw yet, because the third branch has not been introduced; {{ch:boxes}} opens with a decision tree covering all three storage classes.

Example: A keyed map in local state {#ex:local-map}

<!-- finder: store several named values per account in local state -->

{{include-ex:local-map}}

`LocalMap` is indexed by a *tuple* of account and key: `self.tally[Txn.sender, String("credits")]`. What it buys you is one declaration instead of one per field, so a set of named per-account values can be opened at runtime rather than fixed in `__init__`. What it does not buy you is slots: every distinct `(account, key)` pair is a separate local key and costs one of that account's sixteen, exactly as a separate `LocalState` would. The saving is in the source, not in the schema --- which is why the example declares `state_totals` itself instead of hoping the compiler guesses how many buckets you intend to open.

*Predict: this contract reserves four local uints. A user opts in, then calls `bump()` on five differently-named buckets. Which call fails, and does it fail at compile time or on chain?*

Both slabs cost minimum balance, and the two costs are charged to different people. {{tbl:state-mbr}} is the whole pricing model; it is worth memorizing, because it is short and because getting it wrong shows up as a funding bug in a deployment script rather than as a compiler error.

Table: What a declared state schema costs, and who pays it {#tbl:state-mbr}

| Scope | Base | Per `uint64` slot | Per byte slot | Charged to |
|-------|------|-------------------|---------------|------------|
| Global schema | 100,000 (app creation) | 28,500 | 50,000 | the **creator's** account, once |
| Local schema | 100,000 (each opt-in) | 28,500 | 50,000 | the **opting account**, every time |

All figures are microAlgos, and both are *locked*, not spent --- the balance stays in the account and stops being spendable. Global MBR follows the creator because the creator signed the creation transaction; only box storage is funded from the application account itself.

Run the corrected registry through it. Its schema is seventeen global uints, one global byte slot, and one local byte slot, so the creator locks 100,000 + 17 × 28,500 + 50,000 = **634,500** microAlgos once, and each member locks 100,000 + 50,000 = **150,000** microAlgos when they opt in. The broken version charged the creator only 178,500 --- and charged each member 157,000, because two local uints cost more than one packed byte slot. The correction moved cost off every member and onto the creator, one time. That is usually the trade you want, and it is a trade, not a saving.

*What this section repairs in the registry:* the registry keeps a per-member
liability --- `credits` --- in local state, where the member controls it. A
balance the contract owes belongs in storage the contract owns. Here that is a
`GlobalMap`, which is honest for a roster of this size and would have to become
boxes for a roster without a ceiling.

## Shaping What You Store
Global and local state are both flat maps from a key to a `uint64` or a byte string. That is the entire data model. The registry above spends two of its sixteen local slots on `joined_at` and `credits`, two numbers that would fit inside one. This cluster is about how to put structure into a flat store --- and about the one compiler error everybody hits on the way.

Example: A struct stored in a single state slot {#ex:struct-arc4}

<!-- finder: store several related fields in one state slot -->

{{include-ex:struct-arc4}}

`arc4.Struct` gives you a named record whose fields are packed into a single ARC-4 encoded byte string. The load-bearing line is `self.house = GlobalState(Profile(...))`: one `GlobalState`, one key, one slot of schema --- but two logical fields, and room for more without touching the schema. Because the value is a byte string, it costs a *bytes* slot rather than a *uint* slot, which matters when you count your schema in {{ex:state-schema-fixed}}.

Why you would want this: the schema you declare at creation is the schema you have forever ({{ex:state-schema-fixed}} shows why). Packing related fields into one struct buys you the ability to add a field later by widening the struct instead of widening the schema.

Example: Assigning an ARC-4 struct without copying it {#ex:struct-missing-copy}

<!-- finder: fix the "must be copied using .copy()" compiler error -->

{{include-ex:struct-missing-copy}}

This does not compile. The load-bearing line is `entry = self.house.value` --- and the error PuyaPy raises is worth reading in full, because it is the clearest error message in the toolchain:

```text
mutable reference to ARC-4-encoded value must be copied using .copy() when
being assigned to another variable
```

An ARC-4 struct in a variable is a *reference* into the encoded bytes, not a snapshot of them. `entry = self.house.value` does not give you a private copy to scribble on; it gives you a second name for the same bytes. PuyaPy refuses to let you write through that second name by accident, so it makes you say which one you meant: `entry = self.house.value.copy()` to work on a detached copy, or write through `self.house.value.credits` directly and never bind the struct to a name at all.

*Predict: if you write `entry = self.house.value.copy()` and then set `entry.credits`, what does `self.house.value.credits` read back as?*

Example: A native struct, mutated in place {#ex:struct-native}

<!-- finder: update one field of a stored record without re-encoding it -->

{{include-ex:struct-native}}

`algopy.Struct` --- note the capital `S`, and note that it is imported from `algopy` and not from `algopy.arc4` --- is the *native* struct. The load-bearing line is `self.house.value.credits += amount`: a field of a stored record updated in place, with no `.copy()` and no re-encoding ceremony.

The trade is exactly one thing. An ARC-4 struct can cross the ABI boundary --- it can be a method argument or a return value, because its encoding is the wire format. A native struct cannot; it is a storage layout, not a wire format. Use `arc4.Struct` when the record is part of your public interface, `Struct` when it is private to the contract.

Example: A frozen struct for terms that must not change {#ex:struct-frozen}

<!-- finder: make a stored record immutable after it is written -->

{{include-ex:struct-frozen}}

`frozen=True` makes the compiler reject any assignment to a field; `kw_only=True` makes every construction name its fields, so a two-`UInt64` record cannot be built with its arguments transposed. For terms that are set once at creation and read forever, both are free correctness.

*What this section repairs in the registry:* nothing yet, and that is worth saying out loud. This section buys the room the next three need. The registry spends two of its sixteen local slots on `joined_at` and `credits`, two numbers that belong in one record --- and a schema, once declared, is the schema you have forever. Packing them into a `Profile` is what makes the corrections that follow affordable.

## Getting In and Getting Out
Every account that interacts with your application does so through a small set of protocol-defined transitions. Four of them touch state: **create** (the application's global slab appears), **opt-in** (the account's local slab appears), **close-out** (the account leaves politely, running your code), and **clear-state** (the account leaves rudely, and your code cannot stop it). This cluster is those four, in order, and the last one is the one that lost the 4,200 credits.

Example: Initializing global state at creation {#ex:init-defaults}

<!-- finder: set global state values when the contract is created -->

{{include-ex:init-defaults}}

Everything in `__init__` runs exactly once, during the application-creation transaction. The load-bearing line is `self.admin = GlobalState(Global.creator_address)` --- the creator's address captured at birth, which is the cheapest authorization anchor there is.

`Global.creator_address` and `Txn.sender` are the same account here and only here. In every later call, `Txn.sender` is whoever is calling and `Global.creator_address` is still the creator, which is exactly why one of them is safe to compare an admin against and the other is not.

Example: A creation method that takes arguments {#ex:create-method}

<!-- finder: pass parameters to a contract at creation time -->

{{include-ex:create-method}}

`__init__` cannot take arguments --- it is not an ABI method and there is no way to pass it anything. When creation needs a parameter, you declare an ABI method with `create="require"`, which the compiler routes to run only on the creation transaction. The load-bearing line is `@arc4.abimethod(create="require")`: `"require"` means this method *only* runs at creation, as against the default `"disallow"` and the permissive `"allow"`.

Note that `__init__` still runs first, and still runs on the same transaction. `self.joining_fee` gets its zero from `__init__` and its real value from `create()`, in that order.

Example: Creating local state on opt-in {#ex:local-state-optin}

<!-- finder: initialize an account's local state when it opts in -->

{{include-ex:local-state-optin}}

`allow_actions=["OptIn"]` is the load-bearing line: it routes this method to run on an application call whose OnComplete is OptIn, which is the transaction that creates the caller's local slab. Writing local state for an account that has not opted in fails, so opt-in is the only place initial values can be set.

The cost lands on the caller. Opting into an application raises *the account's* minimum balance by 100,000 microAlgos plus the local schema --- 28,500 per uint, 50,000 per byte slot. A user with 0.1 Algo and no headroom cannot opt into your contract at all, and the error they see is a balance error that says nothing about your application.

Example: Handling a polite exit {#ex:close-out-handler}

<!-- finder: run code when an account closes out of my application -->

{{include-ex:close-out-handler}}

`allow_actions=["CloseOut"]` gives you a method that runs when an account leaves. This is real code with real power: the `assert` here refuses the close-out until the member's credits are zero, and the protocol honors the refusal. The account stays opted in.

Then read the next example and notice what that power is worth.

Example: The exit your contract cannot refuse {#ex:clear-state-drops-local}

<!-- finder: understand what happens to local state on a clear-state transaction -->

{{include-ex:clear-state-drops-local}}

This contract returns `False` from its clear state program. It refuses. **It does not matter.**

The load-bearing line is `def clear_state_program(self) -> bool: return False`, and the load-bearing fact is that the line has no effect on whether the account's local state is deleted. ClearState is a protocol-level guarantee that a user can always detach from an application: the local slab is deleted, the account's MBR is released, and the only thing your clear state program decides is whether it gets to run some logic on the way past. Return `True`, return `False`, run out of budget --- the slab goes.

So this contract's `member_count` is wrong the moment anybody clears state instead of closing out, and it is wrong forever, because `leave()` --- the only thing that decrements it --- never ran.

Here, at last, is the thing that was upstream of the broken registry's code. Every line in it does what it says; the mistake is a belief that "the contract's state" is one store that the contract controls. It is not. It is one slab the application owns outright and one slab per member that the *member* owns, and a member can burn their own slab down at any time for any reason, forever, and the application cannot refuse. Every one of the three wrong decisions follows from getting that one sentence wrong.

This is the point at which the chapter's one transferable rule can finally be stated, because you now have everything you need to apply it: **statistics may walk away; liabilities may not.** A number the contract merely *reports about* a user is safe in that user's slab; if the user destroys it, the contract has lost a reading it can recompute or live without. A number the contract *owes* a user is not safe there, because the user can destroy the evidence of a debt that survives the destruction. Hold that sentence against every field you put in local state for the rest of this book.

Here is the same mistake in its most expensive form, which is the one worth being able to recognize on sight:

{{include-ex:local-balance-wrong}}

`Payouts.owed` is a *liability*. The contract owes that number to that account. And it is stored in a slab that the account can delete unilaterally, without notice, without calling any of your methods. A user who clears state destroys the evidence of a debt. A user who clears state, re-opts in, and accrues again gets a fresh zero --- which is fine for them and might be catastrophic for an accounting system that assumed `owed` only ever went up.

*Predict: an attacker's account has `owed = 500`. They clear state and immediately opt in again. What does the contract now believe it owes them, and what did the protocol charge them for the round trip?*

*What this section repairs in the registry:* `member_count` is a number the contract cannot maintain, and `credits` is a liability stored somewhere the debtor can erase.

## The Mini-Build, Fixed
Three decisions, three corrections. The full corrected contract is on disk at `examples/ch03_state/registry_fixed.py` and compiles in CI; here is the diff that matters.

```diff
-    state_totals=StateTotals(global_uints=1, global_bytes=1, local_uints=2),
+    state_totals=StateTotals(global_uints=17, global_bytes=1, local_bytes=1),
-        self.member_count = GlobalState(UInt64(0))
-        self.joined_at = LocalState(UInt64)
-        self.credits = LocalState(UInt64)
+        self.ever_joined = GlobalState(UInt64(0))
+        self.credits = GlobalMap(Account, UInt64, key_prefix="c")
+        self.profile = LocalState(Profile)
-        return self.credits[member]
+        return self.credits.get(member, default=UInt64(0))
-        self.member_count.value -= UInt64(1)
+        owed = self.credits.get(Txn.sender, default=UInt64(0))
+        assert owed == 0, "claim your credits before leaving"
```

The diff omits one addition for space: a four-line `Profile` struct with `joined_round` and `awards` fields, both `arc4.UInt64`. The jump from `global_uints=1` to `17` is one uint for `ever_joined` and sixteen reserved for the `credits` map --- which is also this contract's membership ceiling, and the subject of the last correction below.

Deploy the fixed contract and run the exact sequence that broke the first one. Alice opts in, is awarded 4,200, and clears state:

```python
>>> registry.send.ever_joined_count().abi_return
2
>>> registry.send.credits_of(args=(alice,)).abi_return
4200
```

Alice's local slab is gone, her opt-in is gone, her minimum balance has been released --- and the contract still knows, to the credit, what it owes her. That is the whole chapter in four lines of output.

**Correction one: pack the two local numbers into one slot.** `joined_at` and `credits` became `profile`, a single `arc4.Struct` in a single byte slot. Local state went from two uints to one bytes slot, and there is now room to add a field without touching a schema that cannot be changed.

**Correction two: move the liability out of local state.** `credits` is now a `GlobalMap` keyed by account. The contract's own slab holds the debt, so a member who clears state loses their `profile` and their opt-in --- and keeps every credit they were owed. This is *statistics may walk away; liabilities may not*, applied: `joined_round` is a statistic and stays in the member's slab, `credits` is a liability and moves into the application's.

The move has a price, and the chapter would be lying to skip it. Sixteen reserved global uints means sixteen creditors, ever, because the global slab tops out at 64 pairs for the whole application. That ceiling is fine for a registry and unacceptable for anything that hopes to grow, and the general answer --- boxes, which are per-key, unbounded, and funded by whoever creates them --- is the subject of {{ch:boxes}}, next. What survives the move to boxes is the reasoning, not the container: the liability must sit in storage the debtor cannot delete.

**Correction three: stop claiming a number you cannot maintain.** `member_count` became `ever_joined`, which only ever increments, and `members()` became `ever_joined_count()`. This is not a cop-out. A contract genuinely cannot detect a clear-state, so a live membership count is not a thing an Algorand contract can compute from opt-ins and close-outs. The honest fix is to rename the number to something true --- the count of accounts that have ever joined --- and let an indexer answer the live-membership question by scanning for accounts with local state, which is a query, not a contract invariant.

`leave()` also changed shape. It no longer maintains a counter; it asserts that the departing member has nothing outstanding. And `credits_of` now reads with a default, so a stranger can no longer make a read-only method fail.

## What Bites People Here
Five, in the order you are likely to meet them: one about counters, one about reads, one about who pays, one about the compiler, and one about the exit a contract cannot refuse.

::: {.gotcha #clear-state-orphans-a-counter topic="Global and local state" title="A counter maintained on CloseOut is wrong the first time somebody clears state"}
Any global number that a close-out handler decrements --- member counts, active-stake totals, open-position tallies --- silently desynchronizes the first time an account uses ClearState instead of CloseOut, and there is no method you can add to repair it, because the contract was never told. If a number must be exact, derive it from something the contract controls, or rename it to something that only increases.
:::

::: {.gotcha #missing-key-fails-the-call topic="Global and local state" title="Reading a state key that was never written fails the transaction; it does not return zero"}
`self.fee.value` on a key that has never been written aborts the call, because PuyaPy compiles `.value` to a `*_get_ex` opcode plus an assertion that the key existed. Local state has a second, harsher absence: reading it for an account that never opted in, or that cleared, is a ledger error that no default argument can catch. Both bite hardest on `readonly` methods, where they turn into a denial-of-service surface --- a non-member calls `credits_of(themselves)` and your dashboard shows an error instead of a zero. Use `.get(default=...)` when a missing key should read as a value, `.maybe()` when absence is information, and an explicit `is_opted_in` check before touching another account's local state at all.
:::

::: {.gotcha #local-state-raises-the-users-mbr topic="Resource references, MBR, and budget" title="Opting a user in raises the user's minimum balance, not the application's"}
An application opt-in costs the *opting account* 100,000 microAlgos plus 28,500 per declared local uint and 50,000 per declared local byte slot. Declaring a generous local schema you never fill is therefore a tax you levy on every one of your users, forever, and the failure mode when they cannot pay it is a balance error that never mentions your application.
:::

::: {.gotcha #arc4-struct-assignment-aliases topic="Global and local state" title="Binding an ARC-4 struct to a variable aliases the stored bytes"}
`entry = self.house.value` is a second name for the same encoded bytes, not a snapshot, and PuyaPy refuses to compile it rather than let you guess: *mutable reference to ARC-4-encoded value must be copied using .copy() when being assigned to another variable*. Add `.copy()` if you want a detached working copy; write through the attribute chain if you want to modify storage. Native `algopy.Struct` values do not have this restriction.
:::

::: {.gotcha #clear-state-cannot-be-refused topic="Global and local state" title="Returning False from the clear state program does not keep the account attached"}
The clear state program's return value decides only whether its own logic is credited, not whether the account detaches. The local slab is deleted and the account's minimum balance released either way --- and the same is true if the program errors or runs out of budget, which is the whole point of the guarantee: a user must never be able to be held to an application by a contract that refuses to let go. Anything you were planning to enforce on the way out belongs in `CloseOut`, which a contract *can* reject, and anything a user could lose by skipping `CloseOut` must not have been stored in their slab in the first place.
:::

## Retrieval
Answer these from memory before moving on. Three of them reach back into earlier chapters on purpose.

1. Which slab is bigger, and by how much: the application's global slab or one account's local slab?
2. Name the one transition that deletes local state and that your contract cannot refuse.
3. What does `self.fee.value` do when `fee` has never been written?
4. Who pays the minimum-balance increase when an account opts into your application?
5. Why can `__init__` not take arguments, and what do you use instead?
6. *(From {{ch:mental-model}})* A contract is a transaction validator, not a process. What does that imply about when your state changes are actually committed?
7. *(From {{ch:mental-model}})* What is the base minimum balance of any Algorand account, in microAlgos?
8. *(From {{ch:testing}})* You want to prove that `leave()` rejects a member who still holds credits. Which tool shows you the rejection without submitting a transaction?

## Exercises
1. **(Trace)** Walk the broken registry through this exact sequence and write down the value of `member_count` and the result of `credits_of(alice)` after each step: Alice opts in; admin awards Alice 100; Bob opts in; Alice sends ClearState; Bob calls `leave()`; a fourth account calls `credits_of(alice)`. State which of the six results a user would call a bug and which the contract would call correct behavior.

2. **(Parsons)** Below are six statements. Four of them form the body of the fixed registry's `award` method; two do not belong in it at all. The decorator and signature are given, so syntax will not do your ordering for you.

   ```python
   @arc4.abimethod
   def award(self, member: Account, amount: UInt64) -> UInt64:
       ...
   ```

   The statements: (a) `assert Txn.sender == self.admin.value, "admin only"`; (b) `total = self.credits.get(member, default=UInt64(0)) + amount`; (c) `self.credits[member] = total`; (d) `return total`; (e) `assert member.is_opted_in(Global.current_application_id), "not a member"`; (f) `total = self.credits[member] + amount`.

   Do three things. Select the four that belong and order them. For each of the two you rejected, name the specific thing that goes wrong if you keep it --- one fails for a particular member on a particular call, and the other re-introduces a bug this chapter spent a whole section removing. Then: exactly one of the four you kept has no dataflow constraint forcing its position, so the AVM would accept it anywhere in the method. Name it, and say why putting it last is still wrong even though the chain cannot tell the difference.

3. **(Debug)** A contract declares `state_totals=StateTotals(global_uints=4)` and is deployed. Version two adds a fifth global uint. The developer skips `algokit project deploy` and signs a bare `ApplicationUpdate` against the existing application ID. The network accepts it; no error appears anywhere; in production, writes to the fifth field do not persist. Explain what the network accepted and why it did not object, say what `deploy()` would have done instead and which of its settings decides that, and describe what the developer must now do to keep the existing app ID --- or prove that they cannot.

4. **(Compare)** You need to store one `uint64` per user, and the user count is not known in advance. Compare three containers --- local state, a `GlobalMap`, and boxes (which you have not been taught yet, so reason from the one fact you have been given: a box is an independently created, independently funded key with no shared slab) --- on four axes: who pays the MBR, who can delete the data, whether the AVM can read an arbitrary user's value in a single call, and what ceiling the container imposes on the number of users. One of the three is disqualified outright by its ceiling before any of the other axes matter; name it, give the number, and say where that number comes from. Then state the one requirement that would force each of the remaining two.

5. **(Extend)** Extend the fixed registry with a `claim()` method that lets a member move their `credits` from the global map into an on-chain payment, and update `leave()` accordingly. You will hit a problem the chapter has not solved: `claim()` needs to send Algo, and sending Algo from a contract is a topic this chapter does not cover. Write the method with the transfer left as a comment, and write down precisely what you need to know to fill it in.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can name the one transition that deletes an account's local state without my contract's consent, and explain why returning `False` from the clear state program does not stop it.
- [ ] I can state the rule for which data belongs in local state and which does not, in the form "statistics may walk away; liabilities may not," and apply it to a field I am designing.
- [ ] I can predict whether a given read of state will return a value or fail the transaction, and choose between `.value`, `.get(default=...)`, and `.maybe()` accordingly.
- [ ] I can compute the MBR cost of a declared state schema, and say which account pays it for global state and which for local state.
- [ ] I can explain why `state_totals` should reserve slots I am not using yet, and describe what `deploy()` does when the schema no longer fits.

## Handoff: What the Vesting Project Needs
{{ch:token-vesting}} builds a real token vesting contract, and it makes storage decisions on the first page. {{tbl:state-handoff}} lists the examples from this chapter that it leans on, and what to predict before you read it.

Table: Examples from this chapter that the vesting project depends on {#tbl:state-handoff}

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| {{ex:state-schema-fixed}} | The schema declared on the vesting contract at creation | How many slots does a contract need to reserve when the number of beneficiaries is not known at creation? |
| {{ex:clear-state-drops-local}} | The decision to store vesting schedules in boxes rather than local state | A vesting schedule is an obligation the contract owes a beneficiary. Where can it not live? |
| {{ex:struct-arc4}} | The packed schedule record --- start, cliff, duration, total, claimed | Five numbers, one record. How many state slots should that cost? |
| {{ex:global-get-default}} | Reading a beneficiary's claimed-so-far amount | What should `claimed` read as for a beneficiary who has never claimed? |
| {{ex:init-defaults}} | Capturing the admin address at creation | Which of `Txn.sender` and `Global.creator_address` is safe to store as the admin, and why are they the same value exactly once? |
