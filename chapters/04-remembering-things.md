\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# Remembering Things: Global and Local State

Chapter 3's counter remembered exactly one number, and the memory came for free: `self.count` persisted between calls, and where that number lived, what it cost, and who could take it away never came up. Those questions come due the moment a contract runs a membership, holds a balance per member, or has to know that you have already been paid --- because state on Algorand is not one thing. It is two things with different sizes, different owners, and different lifetimes. The lifetimes are what cost people money.

## A Balance Per Member, and Who Owns It
A rewards program needs to remember one number per member: the credits that member has earned. The number has to survive between calls, it has to be attributable to an account, and the contract has to be able to read one member's number without reading everybody's.

Algorand's answer is *local state*, the small slab of key/value pairs the protocol attaches to an account when it opts into an application. It is per-account by construction, so each member's balance sits with the member, no lookup key required, no box to fund. The same program keeps a global `member_count` that it increments on opt-in and decrements on close-out, so the dashboard can show how many people are enrolled.

Figure 4-1 shows two slabs rather than one store, and the asymmetry between them: the account controls its own slab and can destroy it without the application's consent.

![Figure 4-1. Two slabs, not one store. The application owns one global slab; every account that opts in owns its own local slab — and can destroy it without the application's consent.](figures/state-scopes.svg)

::: {.spec title="Your commission: a membership registry that keeps honest books"}
The contract you build this chapter runs the rewards program end to end: members enroll themselves, an admin hands out credits, a dashboard reads the numbers back. It must:

1. Enroll any account that asks, and remember the round it joined
2. Let the admin --- and only the admin --- award credits to a member
3. Answer, for any account, how many credits it holds --- zero is an answer, an error is not
4. Report how many accounts have joined
5. Never lose track of a credit it has awarded --- however a member leaves, the books must still show what that member is owed

Five requirements, six methods. At the end of the chapter you will re-run the finished registry against this list.
:::

By the end of this chapter you will be able to:

- Choose between global state, local state, and a keyed map for a given piece of data, and defend the choice by naming who can destroy it
- Declare a state schema that will still be correct after the features you have not written yet
- Read state that may never have been written, without failing the call
- Pack several fields into one state slot using an ARC-4 or a native struct, and explain when the compiler will make you write `.copy()`
- Handle every point at which an account enters and leaves your application: create, opt-in, close-out, and clear-state
- Predict which of your contract's numbers a departing member can falsify, and restructure so that they cannot

## Building the Registry in Local State
Here is that commission, as anyone fresh from Chapter 3 would first write it --- complete, and in full: each member's balance in the member's own slab, the count in the application's.

**Example 4-1.** The registry, as first written

<!-- finder: see a membership contract that keeps balances in local state -->

```python
from algopy import (
    Account, ARC4Contract, Global, GlobalState, LocalState, StateTotals,
    Txn, UInt64, arc4,
)


class Registry(
    ARC4Contract,
    state_totals=StateTotals(global_uints=1, global_bytes=1, local_uints=2),
):
    """A membership registry that hands out credits."""

    def __init__(self) -> None:
        self.admin = GlobalState(Global.creator_address)
        self.member_count = GlobalState(UInt64(0))
        self.joined_at = LocalState(UInt64)
        self.credits = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.joined_at[Txn.sender] = Global.round
        self.credits[Txn.sender] = UInt64(0)
        self.member_count.value += UInt64(1)

    @arc4.abimethod
    def award(self, member: Account, amount: UInt64) -> UInt64:
        assert Txn.sender == self.admin.value, "admin only"
        self.credits[member] += amount
        return self.credits[member]

    @arc4.abimethod(readonly=True)
    def credits_of(self, member: Account) -> UInt64:
        return self.credits[member]

    @arc4.abimethod(readonly=True)
    def member_since(self, member: Account) -> UInt64:
        return self.joined_at[member]

    @arc4.abimethod(readonly=True)
    def members(self) -> UInt64:
        return self.member_count.value

    @arc4.abimethod(allow_actions=["CloseOut"])
    def leave(self) -> None:
        self.member_count.value -= UInt64(1)
```

Example 4-1 is complete and deployable. It compiles, it runs on LocalNet, and it contains three decisions that are wrong. Two of them will fail with a transcript in a moment; the third fails nothing, costs money, and stays invisible until the first feature you try to add.

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

Now have Alice leave the other way: not by calling `leave()`, but with an application call carrying `OnComplete=ClearState` --- one of Chapter 2's six on-completion actions, and one `Registry` has no method for. Read the same two methods again:

```python
>>> registry.send.members().abi_return
2
>>> registry.send.credits_of(args=(alice,)).abi_return
LogicError: Txn 4QXT...7MRB had error
'cannot fetch key, V3ZK...6PDA has not opted in to app 1042'
at PC 240 and Source Line 173:
    ... 10 lines of TEAL trace ...
```

The count still says 2. Alice is gone.

Figure 4-2 draws that sequence out, one column per slab. Nothing in the left-hand column ever learns that the right-hand column stopped existing. That is not a gap in the contract's logic; there is no event to handle.

![Figure 4-2. The registry losing 4,200 credits, in three moments. The right-hand column is deleted by a transaction the left-hand column never observes, which is why the count on the left is wrong from that instant and cannot be repaired.](figures/registry-break-trace.svg)

Two failures, and they fail differently. `members()` returns a confident, wrong number. `credits_of(alice)` does not return a wrong number at all; it *rejects the transaction*. Alice has no local slab any more, and reading the local state of an account that is not opted in is an error, not a zero. The reader who assumed missing-means-empty has now shipped a read-only method that a stranger can make fail.

A second, quieter version of the same trap survives even when the account *is* opted in. `self.credits[member]` compiles down to `app_local_get_ex` followed by an assertion that the key existed. The raw opcode is happy to hand back a zero; PuyaPy is the one that insists the key was really there, on the reasonable theory that you would rather be told.

Two absences, and they do not share a fix. The missing *key* (a slab that exists with nothing written at that name) is repaired by reading with a default. The missing *slab* (Alice's case) is not repaired by any default argument, and stays open until Example 4-9. Conflating the two is how the wrong fix gets shipped.

Ship Example 4-1 anyway, and the transcript above is the bill. Alice did not attack anyone: clearing state is an ordinary piece of account hygiene --- it detaches her from an application she is done with and hands back the 157,000 microAlgos of minimum balance her opt-in had locked. Why the protocol guarantees her that exit, and why your contract gets no vote in it, is the business of "Getting In and Getting Out," later in this chapter. What the exit cost the registry is both books at once. The 4,200 credits stopped existing, and so did the evidence that they were ever owed; the contract's records no longer show a liability it still, in every non-technical sense, owes. And the count never heals: `member_count` is decremented by `leave()`, `leave()` never ran, so the number is permanently one too high, every member who clears instead of closing out widens the gap, and no method you add later can repair it, because the contract was never told that anyone left.

Every line in that program does exactly what it says. What ran out is the storage class. **Local state belongs to the account, not to the application, and an account may hand its slab back at any time, for any reason.** Which of your numbers can survive that is what decides where each one goes.

Three decisions caused all of this. The rest of the chapter takes the state model apart and builds the registry again on the far side of it.

## The Global Slab
The global slab belongs to the application. It is created when the application is created, it is destroyed when the application is deleted, and no user can touch it. It holds up to **64 key/value pairs** in total, split at creation between `uint64` values and byte-string values.

**Example 4-2.** The two tiers side by side

<!-- finder: declare both global and local state in one contract -->

```python
from algopy import (
    ARC4Contract,
    GlobalState,
    LocalState,
    StateTotals,
    Txn,
    UInt64,
    arc4,
)


class Registry(
    ARC4Contract,
    state_totals=StateTotals(global_uints=1, local_uints=1),
):
    def __init__(self) -> None:
        self.member_count = GlobalState(UInt64(0))
        self.credits = LocalState(UInt64)

    @arc4.abimethod(readonly=True)
    def my_credits(self) -> UInt64:
        return self.credits[Txn.sender]
```

The two declarations in `__init__` are not symmetrical. `GlobalState(UInt64(0))` takes an *initial value* and so is written once at creation; `LocalState(UInt64)` takes a *type* and cannot have an initial value, because there is no account to write it for yet. Global state exists as soon as the application does; local state does not exist until an account opts in.

`state_totals=StateTotals(...)` declares the schema explicitly. PuyaPy can usually infer it. Write it anyway (Example 4-7 shows why).

**Example 4-3.** Reading and writing a global counter

<!-- finder: keep a counter in global state -->

```python
from algopy import ARC4Contract, GlobalState, UInt64, arc4


class GlobalCounter(ARC4Contract):
    def __init__(self) -> None:
        self.count = GlobalState(UInt64(0))

    @arc4.abimethod
    def bump(self) -> UInt64:
        self.count.value += UInt64(1)
        return self.count.value
```

`self.count.value += UInt64(1)` does the work. `GlobalState` is a *cell*, not a value: `.value` is how you read through it and write through it. Forgetting `.value` is the most common typo in Algorand Python, and it produces a type error rather than silent nonsense.

Because this contract was declared with an initial value, `count` is written at creation and every later read is guaranteed to find it. Its unit test, at `examples/state/global_counter_test.py`, runs in CI: it constructs the contract inside an `algopy_testing_context()` and asserts `contract.bump() == 1` and then `== 2`, using the testing patterns from Chapter 8.

**Example 4-4.** Reading state that may never have been written

<!-- finder: read a global key that might not exist yet -->

```python
from algopy import ARC4Contract, GlobalState, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.joining_fee = GlobalState(UInt64)

    @arc4.abimethod(readonly=True)
    def current_fee(self) -> UInt64:
        return self.joining_fee.get(default=UInt64(1000))
```

`.get(default=UInt64(1000))` is the new part. The declaration is `GlobalState(UInt64)`, a type with no initial value, so the key genuinely does not exist until somebody writes it. `self.joining_fee.value` on a fresh application would fail the transaction; `.get(default=...)` reads it as 1,000 instead.

This is half the fix for `credits_of` in the broken registry: the half that covers a key nobody has written yet. It does nothing for Alice, whose slab no longer exists; a default argument is evaluated after the read succeeds, and her read never gets that far. Example 4-9 closes that one. A read-only method that a stranger can make fail is a denial-of-service surface on your own dashboard, and it takes both fixes to close it.

::: {.gotcha #missing-key-fails-the-call topic="Global and local state" title="Reading a state key that was never written fails the transaction; it does not return zero"}
`self.fee.value` on a key that has never been written aborts the call, because PuyaPy compiles `.value` to a `*_get_ex` opcode plus an assertion that the key existed. Local state has a second, harsher absence: reading it for an account that never opted in, or that cleared, is a ledger error that no default argument can catch. Both bite hardest on `readonly` methods, where they turn into a denial-of-service surface: a non-member calls `credits_of(themselves)` and your dashboard shows an error instead of a zero. Use `.get(default=...)` when a missing key should read as a value, `.maybe()` when absence is information, and an explicit `is_opted_in` check before touching another account's local state at all.
:::

Sometimes "never written" is a real error and the call should stop. That is what Example 4-5 is for.

**Example 4-5.** Distinguishing absent from zero

<!-- finder: tell the difference between a state key set to zero and one never set -->

```python
from algopy import ARC4Contract, GlobalState, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.joining_fee = GlobalState(UInt64)

    @arc4.abimethod
    def raise_fee(self, delta: UInt64) -> UInt64:
        fee, exists = self.joining_fee.maybe()
        assert exists, "no fee has ever been set"
        self.joining_fee.value = fee + delta
        return self.joining_fee.value
```

`fee, exists = self.joining_fee.maybe()` is the difference. `.get(default=UInt64(0))` collapses "the fee is zero" and "no fee was ever set" into the same answer. `.maybe()` returns the value *and* a flag, so you can tell them apart. Use `.get()` when the default is genuinely correct and `.maybe()` when absence means something.

*Predict: a fee is set to `0` deliberately, to make joining free. What does `.maybe()` return, and what would `.get(default=UInt64(0))` have returned?*

**Example 4-6.** Deleting a global key

<!-- finder: remove a key from global state entirely -->

```python
from algopy import ARC4Contract, GlobalState, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.paused_at = GlobalState(UInt64)

    @arc4.abimethod
    def resume(self) -> bool:
        was_paused = bool(self.paused_at)
        del self.paused_at.value
        return was_paused
```

`del self.paused_at.value` removes the key, freeing the schema slot for reuse and making `bool(self.paused_at)` false again. Deleting a key does not shrink the declared schema: the slot stays reserved and the MBR stays paid.

In the registry, `credits_of` has two absences, and this fixes one. A key that was never written should be read with a default. An account with no slab at all is still unhandled.

## Schema, Fixed at Creation
**Example 4-7.** Declaring a schema with room to grow

<!-- finder: reserve state schema slots for features I have not written yet -->

```python
from algopy import ARC4Contract, GlobalState, StateTotals, UInt64, arc4


class Registry(
    ARC4Contract,
    state_totals=StateTotals(global_uints=8, global_bytes=2),
):
    def __init__(self) -> None:
        self.member_count = GlobalState(UInt64(0))

    @arc4.abimethod
    def bump(self) -> UInt64:
        self.member_count.value += UInt64(1)
        return self.member_count.value
```

`state_totals=StateTotals(global_uints=8, global_bytes=2)` sits on a contract that currently uses exactly one uint and zero bytes. That is deliberate, not sloppy.

**For a contract that refuses updates --- every contract in this book before Chapter 24 --- the state schema declared at creation is the schema it keeps.** Local schema can never be widened by anything. Consensus v42 lets an approved `UpdateApplication` rewrite *global* schema and extra pages, moving the extra MBR onto the updater --- but a refused update never gets that far.

What that failure looks like depends on how you deploy, and the two paths are nothing alike.

A raw `ApplicationUpdate` transaction compares nothing. It pushes new bytecode to the existing application ID and the network accepts it. Consensus v42 lets that same transaction rewrite extra pages and the *global* schema (the local schema is still ignored). An update that supplies either field installs both, replacing the previous values: growing global schema while leaving extra pages at zero also zeroes the pages, and shrinking global schema below current usage fails. If the update supplies neither field, the old sizes stand and the ninth uint the new code writes has nowhere to go --- nothing reports an error until a call tries to write it. If the contract refuses the update, the new code never deploys at all.

AlgoKit's `deploy()` does compare, and it stops:

```console
$ algokit project deploy localnet
WARNING: Detected a breaking app schema change in app 1042:
ValueError: Schema break detected and on_schema_break=OnSchemaBreak.Fail,
stopping deployment. If you want to try deleting and recreating the app then
re-run with on_schema_break=OnSchemaBreak.ReplaceApp
```

That is the default, and it is the right one. Table 4-1 is the whole decision surface behind that message: two settings, and nothing else to learn.

: Table 4-1. What `deploy()` does with a changed contract

| What changed | What `deploy()` calls it | What you get to choose |
|--------------|--------------------------|------------------------|
| Nothing | a no-op | nothing; no transaction is sent |
| Only the bytecode | an *update* | `on_update`: `Fail` raises (default), `UpdateApp` keeps the app ID, `AppendApp` creates a second app, `ReplaceApp` creates and deletes |
| Any schema number went up, or extra pages did | a *schema break* | `on_schema_break`: `Fail` raises (default), `ReplaceApp` creates a new app and deletes the old one **in the same group**, `AppendApp` creates a new app and leaves the old one standing |

The third row still has no in-place widen: as of algokit-utils 4.x, `deploy()` treats a schema increase as a break, even though consensus v42 would accept an `UpdateApplication` that grows global schema or extra pages (local schema still cannot grow). Every option in that row produces a **new application ID**, and a new ID means every opted-in account, every stored balance, and every integration pointing at the old one is now pointing somewhere else.

So you reserve. Eight uints and two bytes cost 8 × 28,500 + 2 × 50,000 = 328,000 microAlgos of MBR, about a third of an Algo, one time, and it is charged to the *creator's* account, not to the application account. Global schema MBR follows the creator; only box storage is funded from the application account itself. That distinction bites when a deployment script funds the app address and then cannot work out why the creator is short.

Every state field you add after launch is either free (because you reserved) or a migration (because you did not).

*Predict: you add a ninth global uint and run `algokit project deploy localnet` against the deployed application. What does `deploy()` print, and what would have happened instead if you had sent a bare `ApplicationUpdate` that did not declare the new schema?*

**Example 4-8.** Redeploying when the schema no longer fits

<!-- finder: redeploy a contract whose state schema outgrew the deployed one -->

```python
"""Redeploy a registry whose declared state schema no longer matches the code."""

from algokit_utils import AlgorandClient, OnSchemaBreak, OnUpdate

from smart_contracts.artifacts.registry.registry_client import RegistryFactory


def main() -> int:
    algorand = AlgorandClient.from_environment()
    deployer = algorand.account.from_environment("DEPLOYER")
    factory = algorand.client.get_typed_app_factory(
        RegistryFactory, default_sender=deployer.address
    )
    client, result = factory.deploy(
        on_schema_break=OnSchemaBreak.ReplaceApp,
        on_update=OnUpdate.UpdateApp,
    )
    print(f"registry {client.app_id}: {result.operation_performed}")
    return client.app_id


if __name__ == "__main__":
    main()
```

This one does not run on the AVM. It is a client-side deployment script, the escape hatch for the mistake the previous example prevents. `on_schema_break=OnSchemaBreak.ReplaceApp` is row three of Table 4-1, chosen deliberately instead of hit by accident.

`ReplaceApp` needs the old application to be deletable. If it is not, AlgoKit attempts the delete anyway and logs that it will most likely fail, which is a confusing way to discover that your migration cannot proceed. And because the delete rides in the same group as the create, `ReplaceApp` against a contract that is holding user funds destroys the contract holding them. It is a reasonable default on LocalNet and almost never one in production.

The registry, as first written, declares `global_uints=1` and has no room to hold anything it takes back from local state. The corrected contract reserves seventeen before it needs them.

## The Per-Account Slab
Local state is a separate slab per opted-in account: up to **16 key/value pairs**, created by an opt-in, deleted by a close-out or a clear-state. It is stored on the *account*, not on the application, and the MBR for it is paid by the *account*, not by you.

**Example 4-9.** Reading another account's local state

<!-- finder: read a specific account's local state from a method -->

```python
from algopy import Account, ARC4Contract, Global, LocalState, Txn, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.credits = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.credits[Txn.sender] = UInt64(0)

    @arc4.abimethod(readonly=True)
    def credits_of(self, member: Account) -> UInt64:
        if not member.is_opted_in(Global.current_application_id):
            return UInt64(0)
        return self.credits.get(member, default=UInt64(0))
```

`member.is_opted_in(Global.current_application_id)` guards a distinction that costs people an afternoon. `LocalState` is indexed by account: `self.credits[Txn.sender]` for the caller, `self.credits[member]` for anyone else. `.get(account, default=...)` covers a key that was never *written* inside a slab that exists. It does **not** cover an account with no slab at all. Reading the local state of an account that has never opted in, or that opted in and then cleared, is a ledger error before any default can apply. Two absences, two different fixes: the opt-in check for the missing slab, the default for the missing key.

A second constraint hides in that innocuous `member: Account` parameter: the AVM can only read the local state of accounts the transaction has explicitly made *available* to it, and that list is short and hard-capped. Reading `Txn.sender`'s slab always works; reading a list of members stops working the moment the list outgrows the cap. The exact numbers and the mechanics of declaring resources get a chapter of their own later in the book. Local state is a poor fit for anything you need to iterate over.

**Example 4-10.** A keyed map in global state

<!-- finder: store one value per account without requiring an opt-in -->

```python
from algopy import Account, ARC4Contract, GlobalMap, StateTotals, UInt64, arc4


class Registry(ARC4Contract, state_totals=StateTotals(global_uints=16)):
    def __init__(self) -> None:
        self.credits = GlobalMap(Account, UInt64, key_prefix="c")

    @arc4.abimethod
    def award(self, member: Account, amount: UInt64) -> UInt64:
        total = self.credits.get(member, default=UInt64(0)) + amount
        self.credits[member] = total
        return total
```

`GlobalMap` gives you a keyed map inside the global slab: the `key_prefix` plus the encoded key form the actual state key. Nobody has to opt in, and nobody can walk away with the record.

"Inside the global slab" is the map's hard limit. Each entry is one global key/value pair, drawn from the same 64-pair budget the whole application shares. An entry is created by the *write*, not by the declaration: `self.credits[member] = UInt64(0)` spends one of those slots to record a zero that `.get(default=UInt64(0))` would have returned for nothing. Writing placeholder zeros into a `GlobalMap` buys you no correctness and costs you a creditor. `state_totals=StateTotals(global_uints=16)` means sixteen accounts, ever, and the ceiling is 64 minus whatever else the contract stores. A `GlobalMap` is the right shape for a bounded set --- a handful of admins, a fixed roster of pools, the registry in this chapter --- and the wrong shape the moment the number of keys is a function of how popular you get. For per-account data with no ceiling the answer is boxes; moving a record out of local state is not the same as making it unbounded. Chapter 5 opens with a decision tree covering all three storage classes.

**Example 4-11.** A keyed map in local state

<!-- finder: store several named values per account in local state -->

```python
from algopy import ARC4Contract, LocalMap, StateTotals, String, Txn, UInt64, arc4


class Registry(ARC4Contract, state_totals=StateTotals(local_uints=4)):
    def __init__(self) -> None:
        self.tally = LocalMap(String, UInt64, key_prefix="t")

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.tally[Txn.sender, String("credits")] = UInt64(0)

    @arc4.abimethod
    def bump(self, bucket: String) -> UInt64:
        current = self.tally.get(Txn.sender, bucket, default=UInt64(0))
        self.tally[Txn.sender, bucket] = current + UInt64(1)
        return current + UInt64(1)
```

`LocalMap` is indexed by a *tuple* of account and key: `self.tally[Txn.sender, String("credits")]`. It buys one declaration instead of one per field, so a set of named per-account values can be opened at runtime rather than fixed in `__init__`. It does not buy slots: every distinct `(account, key)` pair is a separate local key and costs one of that account's sixteen, exactly as a separate `LocalState` would. The saving is in the source, not in the schema, which is why the example declares `state_totals` itself instead of hoping the compiler guesses how many buckets you intend to open.

*Predict: this contract reserves four local uints. A user opts in, then calls `bump()` on five differently-named buckets. Which call fails, and does it fail at compile time or on chain?*

Both slabs cost minimum balance, and the two costs are charged to different people. Table 4-2 is the whole pricing model. Getting it wrong shows up as a funding bug in a deployment script rather than as a compiler error.

: Table 4-2. What a declared state schema costs, and who pays it

| Scope | Base | Per `uint64` slot | Per byte slot | Charged to |
|-------|------|-------------------|---------------|------------|
| Global schema | 100,000 (app creation) | 28,500 | 50,000 | the **creator's** account, once |
| Local schema | 100,000 (each opt-in) | 28,500 | 50,000 | the **opting account**, every time |

All figures are microAlgos, and both are *locked*, not spent: the balance stays in the account and stops being spendable. Global MBR follows the creator because the creator signed the creation transaction; only box storage is funded from the application account itself.

Run the corrected registry through it. Its schema is seventeen global uints, one global byte slot, and one local byte slot, so the creator locks 100,000 + 17 × 28,500 + 50,000 = **634,500** microAlgos once, and each member locks 100,000 + 50,000 = **150,000** microAlgos when they opt in. The broken version charged the creator only 178,500 and charged each member 157,000, because two local uints cost more than one packed byte slot. The correction moved cost off every member and onto the creator, one time. That is usually the trade you want, and it is a trade, not a saving.

The registry keeps a per-member liability, `credits`, in local state, where the member controls it. A balance the contract owes belongs in storage the contract owns. Here that is a `GlobalMap`, which is honest for a roster of this size and would have to become boxes for a roster without a ceiling.

## Shaping What You Store
Global and local state are both flat maps from a key to a `uint64` or a byte string. That is the entire data model. The registry above spends two of its sixteen local slots on `joined_at` and `credits`, two numbers that would fit inside one. Structs are how you put structure into a flat store, and there is one compiler error everybody hits on the way.

**Example 4-12.** A struct stored in a single state slot

<!-- finder: store several related fields in one state slot -->

```python
from algopy import ARC4Contract, GlobalState, arc4


class Profile(arc4.Struct):
    joined_round: arc4.UInt64
    credits: arc4.UInt64


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.house = GlobalState(Profile(arc4.UInt64(0), arc4.UInt64(0)))

    @arc4.abimethod(readonly=True)
    def house_credits(self) -> arc4.UInt64:
        return self.house.value.credits
```

`arc4.Struct` gives you a named record whose fields are packed into a single ARC-4 encoded byte string. `self.house = GlobalState(Profile(...))` is the whole declaration: one `GlobalState`, one key, one slot of schema --- but two logical fields, and room for more without touching the schema. Because the value is a byte string, it costs a *bytes* slot rather than a *uint* slot, which matters when you count your schema in Example 4-7.

For every contract that refuses updates --- every one in this book before Chapter 24 --- the schema you declare at creation is the schema you have forever (Example 4-7 shows why), so packing related fields into one struct buys you the ability to add a field later by widening the struct instead of widening the schema.

**Example 4-13.** Assigning an ARC-4 struct without copying it

<!-- finder: fix the "must be copied using .copy()" compiler error -->

```python
from algopy import ARC4Contract, GlobalState, arc4


class Profile(arc4.Struct):
    joined_round: arc4.UInt64
    credits: arc4.UInt64


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.house = GlobalState(Profile(arc4.UInt64(0), arc4.UInt64(0)))

    @arc4.abimethod
    def award(self) -> None:
        entry = self.house.value
        entry.credits = arc4.UInt64(1)
```

This does not compile. `entry = self.house.value` is the offending line, and PuyaPy's error says why:

```text
mutable reference to ARC-4-encoded value must be copied using .copy() when
being assigned to another variable
```

An ARC-4 struct in a variable is a *reference* into the encoded bytes, not a snapshot of them. `entry = self.house.value` does not give you a private copy to scribble on; it gives you a second name for the same bytes. PuyaPy refuses to let you write through that second name by accident, so it makes you say which one you meant: `entry = self.house.value.copy()` to work on a detached copy, or write through `self.house.value.credits` directly and never bind the struct to a name at all.

*Predict: if you write `entry = self.house.value.copy()` and then set `entry.credits`, what does `self.house.value.credits` read back as?*

**Example 4-14.** A native struct, mutated in place

<!-- finder: update one field of a stored record without re-encoding it -->

```python
from algopy import ARC4Contract, GlobalState, Struct, UInt64, arc4


class Profile(Struct):
    joined_round: UInt64
    credits: UInt64


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.house = GlobalState(Profile(joined_round=UInt64(0), credits=UInt64(0)))

    @arc4.abimethod
    def award(self, amount: UInt64) -> UInt64:
        self.house.value.credits += amount
        return self.house.value.credits
```

`algopy.Struct` is the *native* struct: capital `S`, imported from `algopy` and not from `algopy.arc4`. `self.house.value.credits += amount` updates a field of a stored record in place, with no `.copy()` and no re-encoding ceremony.

The trade is exactly one thing. An ARC-4 struct can cross the ABI boundary: it can be a method argument or a return value, because its encoding is the wire format. A native struct cannot; it is a storage layout, not a wire format. Use `arc4.Struct` when the record is part of your public interface, `Struct` when it is private to the contract.

::: {.gotcha #arc4-struct-assignment-aliases topic="Global and local state" title="Binding an ARC-4 struct to a variable aliases the stored bytes"}
`entry = self.house.value` is a second name for the same encoded bytes, not a snapshot, and PuyaPy refuses to compile it rather than let you guess: *mutable reference to ARC-4-encoded value must be copied using .copy() when being assigned to another variable*. Add `.copy()` if you want a detached working copy; write through the attribute chain if you want to modify storage. Native `algopy.Struct` values do not have this restriction.
:::

**Example 4-15.** A frozen struct for terms that must not change

<!-- finder: make a stored record immutable after it is written -->

```python
from algopy import ARC4Contract, GlobalState, Struct, UInt64, arc4


class Terms(Struct, frozen=True, kw_only=True):
    cliff: UInt64
    duration: UInt64


class Vault(ARC4Contract):
    def __init__(self) -> None:
        self.terms = GlobalState(Terms(cliff=UInt64(100), duration=UInt64(1000)))

    @arc4.abimethod(readonly=True)
    def cliff_round(self) -> UInt64:
        return self.terms.value.cliff
```

`frozen=True` makes the compiler reject any assignment to a field; `kw_only=True` makes every construction name its fields, so a two-`UInt64` record cannot be built with its arguments transposed. For terms that are set once at creation and read forever, both are free correctness.

Nothing in the registry changes yet. Packing `joined_at` and `credits` into a `Profile` is what makes the corrections that follow affordable, because a refused-update contract's schema, once declared, is the schema it keeps.

## Getting In and Getting Out
Every account that interacts with your application does so through a small set of protocol-defined transitions. Four of them touch state: **create** (the application's global slab appears), **opt-in** (the account's local slab appears), **close-out** (the account leaves politely, running your code), and **clear-state** (the account leaves rudely, and your code cannot stop it). The last of the four is what lost the 4,200 credits.

**Example 4-16.** Initializing global state at creation

<!-- finder: set global state values when the contract is created -->

```python
from algopy import ARC4Contract, Global, GlobalState, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Global.creator_address)
        self.member_count = GlobalState(UInt64(0))

    @arc4.abimethod(readonly=True)
    def admin_address(self) -> arc4.Address:
        return arc4.Address(self.admin.value)
```

Everything in `__init__` runs exactly once, during the application-creation transaction. `self.admin = GlobalState(Global.creator_address)` captures the creator's address at birth, the cheapest authorization anchor there is.

`Global.creator_address` and `Txn.sender` are the same account here and only here. In every later call, `Txn.sender` is whoever is calling and `Global.creator_address` is still the creator, which is why one of them is safe to compare an admin against and the other is not.

**Example 4-17.** A creation method that takes arguments

<!-- finder: pass parameters to a contract at creation time -->

```python
from algopy import ARC4Contract, GlobalState, Txn, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Txn.sender)
        self.joining_fee = GlobalState(UInt64(0))

    @arc4.abimethod(create="require")
    def create(self, joining_fee: UInt64) -> None:
        self.joining_fee.value = joining_fee

    @arc4.abimethod(readonly=True)
    def fee(self) -> UInt64:
        return self.joining_fee.value
```

`__init__` cannot take arguments: it is not an ABI method and there is no way to pass it anything. When creation needs a parameter, declare an ABI method with `create="require"`, which the compiler routes to run only on the creation transaction. In `@arc4.abimethod(create="require")`, `"require"` means the method *only* runs at creation, as against the default `"disallow"` and the permissive `"allow"`.

`__init__` still runs first, and still runs on the same transaction. `self.joining_fee` gets its zero from `__init__` and its real value from `create()`, in that order.

**Example 4-18.** Creating local state on opt-in

<!-- finder: initialize an account's local state when it opts in -->

```python
from algopy import ARC4Contract, Global, LocalState, Txn, UInt64, arc4


class Membership(ARC4Contract):
    def __init__(self) -> None:
        self.joined_at = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.joined_at[Txn.sender] = Global.round
```

`allow_actions=["OptIn"]` routes this method to run on an application call whose OnComplete is OptIn, the transaction that creates the caller's local slab. Writing local state for an account that has not opted in fails, so opt-in is the only place initial values can be set.

The cost lands on the caller. Opting into an application raises *the account's* minimum balance by 100,000 microAlgos plus the local schema: 28,500 per uint, 50,000 per byte slot. A user with 0.1 Algo and no headroom cannot opt into your contract at all, and the error they see is a balance error that says nothing about your application.

::: {.gotcha #local-state-raises-the-users-mbr topic="Resource references, MBR, and budget" title="Opting a user in raises the user's minimum balance, not the application's"}
An application opt-in costs the *opting account* 100,000 microAlgos plus 28,500 per declared local uint and 50,000 per declared local byte slot. Declaring a generous local schema you never fill is therefore a tax you levy on every one of your users, forever, and the failure mode when they cannot pay it is a balance error that never mentions your application.
:::

**Example 4-19.** Handling a polite exit

<!-- finder: run code when an account closes out of my application -->

```python
from algopy import ARC4Contract, GlobalState, LocalState, Txn, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.member_count = GlobalState(UInt64(0))
        self.credits = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.credits[Txn.sender] = UInt64(0)
        self.member_count.value += UInt64(1)

    @arc4.abimethod(allow_actions=["CloseOut"])
    def leave(self) -> None:
        assert self.credits[Txn.sender] == 0, "claim your credits first"
        self.member_count.value -= UInt64(1)
```

`allow_actions=["CloseOut"]` gives you a method that runs when an account leaves, and it has real power: the `assert` here refuses the close-out until the member's credits are zero, and the protocol honors the refusal. The account stays opted in.

**Example 4-20.** The exit your contract cannot refuse

<!-- finder: understand what happens to local state on a clear-state transaction -->

```python
from algopy import ARC4Contract, GlobalState, LocalState, Txn, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.member_count = GlobalState(UInt64(0))
        self.credits = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.credits[Txn.sender] = UInt64(0)
        self.member_count.value += UInt64(1)

    @arc4.abimethod(allow_actions=["CloseOut"])
    def leave(self) -> None:
        self.member_count.value -= UInt64(1)

    def clear_state_program(self) -> bool:
        return False
```

This contract returns `False` from its clear state program. It refuses. **It does not matter.**

`def clear_state_program(self) -> bool: return False` has no effect on whether the account's local state is deleted. ClearState is a protocol-level guarantee that a user can always detach from an application: the local slab is deleted, the account's MBR is released, and the only thing your clear state program decides is whether it gets to run some logic on the way past. Return `True`, return `False`, run out of budget: the slab goes.

::: {.gotcha #clear-state-cannot-be-refused topic="Global and local state" title="Returning False from the clear state program does not keep the account attached"}
The clear state program's return value decides only whether its own logic is credited, not whether the account detaches. The local slab is deleted and the account's minimum balance released either way, and the same is true if the program errors or runs out of budget, which is the whole point of the guarantee: a user must never be able to be held to an application by a contract that refuses to let go. Anything you were planning to enforce on the way out belongs in `CloseOut`, which a contract *can* reject, and anything a user could lose by skipping `CloseOut` must not have been stored in their slab in the first place.
:::

So this contract's `member_count` is wrong the moment anybody clears state instead of closing out, and it is wrong forever, because `leave()`, the only thing that decrements it, never ran.

::: {.gotcha #clear-state-orphans-a-counter topic="Global and local state" title="A counter maintained on CloseOut is wrong the first time somebody clears state"}
Any global number that a close-out handler decrements (member counts, active-stake totals, open-position tallies) silently desynchronizes the first time an account uses ClearState instead of CloseOut, and there is no method you can add to repair it, because the contract was never told. If a number must be exact, derive it from something the contract controls, or rename it to something that only increases.
:::

Upstream of the broken registry's code is one wrong belief: that "the contract's state" is a single store the contract controls. It is not. It is one slab the application owns outright and one slab per member that the *member* owns, and a member can burn their own slab down at any time for any reason, forever, and the application cannot refuse. All three wrong decisions follow from that.

One rule falls out of that, and it transfers to every contract you write: **statistics may walk away; liabilities may not.** A number the contract merely *reports about* a user is safe in that user's slab; if the user destroys it, the contract has lost a reading it can recompute or live without. A number the contract *owes* a user is not safe there, because the user can destroy the evidence of a debt that survives the destruction. Hold that against every field you put in local state for the rest of this book.

The same mistake, in its most expensive form --- a variation of Example 4-1 that stores nothing but the liability:

```python
from algopy import ARC4Contract, LocalState, Txn, UInt64, arc4


class Payouts(ARC4Contract):
    def __init__(self) -> None:
        self.owed = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.owed[Txn.sender] = UInt64(0)

    @arc4.abimethod
    def accrue(self, amount: UInt64) -> UInt64:
        self.owed[Txn.sender] += amount
        return self.owed[Txn.sender]
```

`Payouts.owed` is a *liability*. The contract owes that number to that account. And it is stored in a slab that the account can delete unilaterally, without notice, without calling any of your methods. A user who clears state destroys the evidence of a debt. A user who clears state, re-opts in, and accrues again gets a fresh zero, which is fine for them and might be catastrophic for an accounting system that assumed `owed` only ever went up.

*Predict: an attacker's account has `owed = 500`. They clear state and immediately opt in again. What does the contract now believe it owes them, and what did the protocol charge them for the round trip?*

In the registry: `member_count` is a number the contract cannot maintain, and `credits` is a liability stored somewhere the debtor can erase.

## Building It Again in the Contract's Own Slab
Three decisions, three corrections. Here is the diff that matters; the whole corrected contract follows as Example 4-21.

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

The diff omits a four-line `Profile` struct with `joined_round` and `awards` fields, both `arc4.UInt64`; the listing settles it. The jump from `global_uints=1` to `17` is one uint for `ever_joined` and sixteen reserved for the `credits` map, which is also this contract's membership ceiling.

**Example 4-21.** The registry, corrected

<!-- example: examples/state/registry_fixed.py mode=compile -->
<!-- finder: see the registry with all three defects fixed -->

```python
from algopy import (
    Account, ARC4Contract, Global, GlobalMap, GlobalState, LocalState,
    StateTotals, Txn, UInt64, arc4,
)


class Profile(arc4.Struct):
    """One member's statistics, packed into a single local byte slot."""
    joined_round: arc4.UInt64
    awards: arc4.UInt64


class Registry(
    ARC4Contract,
    state_totals=StateTotals(global_uints=17, global_bytes=1, local_bytes=1),
):
    """A membership registry that hands out credits.

    The three corrections over the first draft: the two per-member numbers
    are packed into one struct in one local byte slot; the credit balance
    is a liability and lives in the contract's own global map, which a
    departing member cannot erase; and the count only counts joins, because
    a clear-state can never be observed.
    """

    def __init__(self) -> None:
        self.admin = GlobalState(Global.creator_address)
        self.ever_joined = GlobalState(UInt64(0))
        self.credits = GlobalMap(Account, UInt64, key_prefix="c")
        self.profile = LocalState(Profile)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.profile[Txn.sender] = Profile(
            joined_round=arc4.UInt64(Global.round),
            awards=arc4.UInt64(0),
        )
        self.ever_joined.value += UInt64(1)

    @arc4.abimethod
    def award(self, member: Account, amount: UInt64) -> UInt64:
        assert Txn.sender == self.admin.value, "admin only"
        total = self.credits.get(member, default=UInt64(0)) + amount
        self.credits[member] = total
        return total

    @arc4.abimethod(readonly=True)
    def credits_of(self, member: Account) -> UInt64:
        return self.credits.get(member, default=UInt64(0))

    @arc4.abimethod(readonly=True)
    def member_since(self, member: Account) -> UInt64:
        return self.profile[member].joined_round.as_uint64()

    @arc4.abimethod(readonly=True)
    def ever_joined_count(self) -> UInt64:
        return self.ever_joined.value

    @arc4.abimethod(allow_actions=["CloseOut"])
    def leave(self) -> None:
        owed = self.credits.get(Txn.sender, default=UInt64(0))
        assert owed == 0, "claim your credits before leaving"
```

Deploy the fixed contract and run the exact sequence that broke the first one. Alice opts in, is awarded 4,200, and clears state:

```python
>>> registry.send.ever_joined_count().abi_return
2
>>> registry.send.credits_of(args=(alice,)).abi_return
4200
```

Alice's local slab is gone, her opt-in is gone, her minimum balance has been released --- and the contract still knows, to the credit, what it owes her.

**Correction one: pack the two local numbers into one slot.** `joined_at` and `credits` became `profile`, a single `arc4.Struct` in a single byte slot. Local state went from two uints to one bytes slot, and there is now room to add a field without touching a schema that cannot be changed.

**Correction two: move the liability out of local state.** `credits` is now a `GlobalMap` keyed by account. The contract's own slab holds the debt, so a member who clears state loses their `profile` and their opt-in --- and keeps every credit they were owed. This is *statistics may walk away; liabilities may not*, applied: `joined_round` is a statistic and stays in the member's slab, `credits` is a liability and moves into the application's.

The move has a price, and it is itemized. The creator's minimum balance rises from 178,500 to 634,500 microAlgos at creation --- sixteen reserved uint slots at 28,500 each, paid whether or not a creditor ever occupies them --- while each member's opt-in MBR *falls* from 157,000 to 150,000, because packing two locals into one bytes slot is cheaper than two uint slots. And sixteen creditors is what this contract *reserved*, not what the protocol allows: the global slab tops out at 64 pairs, so with one uint spent on `ever_joined` and one bytes on the admin, the ceiling is sixty-two. Either number is fine for a registry and unacceptable for anything that hopes to grow. The general answer is boxes --- per-key, unbounded, and funded by whoever creates them --- and it is the subject of Chapter 5, next. What survives the move to boxes is the reasoning, not the container: the liability must sit in storage the debtor cannot delete.

**Correction three: stop claiming a number you cannot maintain.** `member_count` became `ever_joined`, which only ever increments, and `members()` became `ever_joined_count()`. This is not a cop-out: a contract genuinely cannot detect a clear-state, so a live membership count is not something an Algorand contract can compute from opt-ins and close-outs. The honest fix is to rename the number to something true --- the count of accounts that have ever joined --- and let an indexer answer the live-membership question by scanning for accounts with local state, which is a query, not a contract invariant.

`leave()` also changed shape. It no longer maintains a counter; it asserts that the departing member has nothing outstanding. And `credits_of` now reads with a default, so a stranger can no longer make a read-only method fail. What the registry still cannot do is take a seventeenth creditor.

That settles the commission from the top of the chapter, item by item:

1. Enroll any account that asks and remember the round it joined --- yes, in one packed slot instead of two; a joining round is a statistic, so it is allowed to walk away with her.
2. Let the admin, and only the admin, award credits --- yes, unchanged from the first version.
3. Answer for any account's credits without failing --- yes: a stranger who was never a member reads a zero now, not a `LogicError`.
4. Report how many accounts have joined --- yes, and the first version failed it by promising a different number, a live membership count that no contract on this chain can maintain.
5. Never lose track of a credit it has awarded --- yes: the 4,200 in the transcript above survived the destruction of the slab it was first kept in.

Five for five, on the second try.

## Retrieval
Answer these from memory before moving on. Two of them reach back into earlier chapters, and the last one reaches forward on purpose.

1. Which slab is bigger, and by how much: the application's global slab or one account's local slab?
2. Name the one transition that deletes local state and that your contract cannot refuse.
3. What does `self.fee.value` do when `fee` has never been written?
4. Who pays the minimum-balance increase when an account opts into your application?
5. Why can `__init__` not take arguments, and what do you use instead?
6. *(From Chapter 2)* A contract is a transaction validator, not a process. What does that imply about when your state changes are actually committed?
7. *(From Chapter 2)* What is the base minimum balance of any Algorand account, in microAlgos?
8. *(Preview --- Chapter 8 answers this)* You want to prove that `leave()` rejects a member who still holds credits. What would show you the rejection without submitting a transaction? You have not been given the tool yet; write down what it would have to do.

## Exercises
1. Walk the broken registry through this exact sequence: Alice opts in; admin awards Alice 100; Bob opts in; Alice sends ClearState; Bob calls `leave()`; a fourth account calls `credits_of(alice)`.

   a. **(Trace)** Write down the value of `member_count` and the result of `credits_of(alice)` after each step.

   b. **(Trace)** State which of the six results a user would call a bug and which the contract would call correct behavior.

2. Below are six statements. Four of them form the body of the fixed registry's `award` method; two do not belong in it at all. The decorator and signature are given, so syntax will not do your ordering for you.

   ```python
   @arc4.abimethod
   def award(self, member: Account, amount: UInt64) -> UInt64:
       ...
   ```

   The statements: (a) `assert Txn.sender == self.admin.value, "admin only"`; (b) `total = self.credits.get(member, default=UInt64(0)) + amount`; (c) `self.credits[member] = total`; (d) `return total`; (e) `assert member.is_opted_in(Global.current_application_id), "not a member"`; (f) `total = self.credits[member] + amount`.

   a. **(Parsons)** Select the four that belong and order them.

   b. **(Debug)** For each of the two you rejected, name the specific thing that goes wrong if you keep it: one fails for a particular member on a particular call, and the other re-introduces a bug this chapter removed.

   c. **(Parsons)** Exactly one of the four you kept has no dataflow constraint forcing its position, so the AVM would accept it anywhere in the method. Name it.

   d. **(Compare)** Say why putting that statement last is still wrong even though the chain cannot tell the difference.

3. A contract declares `state_totals=StateTotals(global_uints=4)` and is deployed. Version two adds a fifth global uint. The developer skips `algokit project deploy` and signs a bare `ApplicationUpdate` against the existing application ID. The network accepts it; no error appears anywhere; in production, writes to the fifth field do not persist.

   a. **(Debug)** Explain what the network accepted and why it did not object.

   b. **(Trace)** Say what `deploy()` would have done instead, and which of its settings decides that.

   c. **(Debug)** Describe what the developer must now do to keep the existing app ID, or prove that they cannot.

4. You need to store one `uint64` per user, and the user count is not known in advance. The three containers are local state, a `GlobalMap`, and boxes; you have not been taught boxes yet, so reason from the one fact you have been given: a box is an independently created, independently funded key with no shared slab.

   a. **(Compare)** Compare the three on four axes: who pays the MBR, who can delete the data, whether the AVM can read an arbitrary user's value in a single call, and what ceiling the container imposes on the number of users.

   b. **(Compare)** One of the three is disqualified outright by its ceiling before any of the other axes matter; name it, give the number, and say where that number comes from.

   c. **(Compare)** State the one requirement that would force each of the remaining two.

5. Extend the fixed registry with a `claim()` method that lets a member move their `credits` from the global map into an on-chain payment. You will hit a problem the chapter has not solved: `claim()` needs to send Algo, and sending Algo from a contract is a topic this chapter does not cover.

   a. **(Extend)** Write the method with the transfer left as a comment.

   b. **(Extend)** Update `leave()` accordingly.

   c. **(Extend)** Write down precisely what you need to know to fill the comment in.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can name the one transition that deletes an account's local state without my contract's consent, and explain why returning `False` from the clear state program does not stop it.
- [ ] I can state the rule for which data belongs in local state and which does not, in the form "statistics may walk away; liabilities may not," and apply it to a field I am designing.
- [ ] I can predict whether a given read of state will return a value or fail the transaction, and choose between `.value`, `.get(default=...)`, and `.maybe()` accordingly.
- [ ] I can compute the MBR cost of a declared state schema, and say which account pays it for global state and which for local state.
- [ ] I can explain why `state_totals` should reserve slots I am not using yet, and describe what `deploy()` does when the schema no longer fits.

## Handoff: Where the Vesting Project Keeps a Schedule
Chapter 9 builds a real token vesting contract, and it makes storage decisions on the first page. Table 4-3 lists the examples from this chapter that it leans on, and what to predict before you read it.

: Table 4-3. Examples from this chapter that the vesting project depends on

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| Example 4-7 | The schema declared on the vesting contract at creation | How many slots does a contract need to reserve when the number of beneficiaries is not known at creation? |
| Example 4-20 | The decision to store vesting schedules in boxes rather than local state | A vesting schedule is an obligation the contract owes a beneficiary. Where can it not live? |
| Example 4-12 | The packed schedule record: start, cliff, duration, total, claimed | Five numbers, one record. How many state slots should that cost? |
| Example 4-4 | Reading a beneficiary's claimed-so-far amount | What should `claimed` read as for a beneficiary who has never claimed? |
| Example 4-16 | Capturing the admin address at creation | Which of `Txn.sender` and `Global.creator_address` is safe to store as the admin, and why are they the same value exactly once? |
