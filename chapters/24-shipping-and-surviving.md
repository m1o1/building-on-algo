\newpage

\part{Shipping}

One chapter, one subject: everything that only matters once strangers depend on your contract, and everything that cannot be added after you freeze it. Events, error codes, the pause switch, the lifecycle stance --- with the guestbook from Chapter 5 revisited as an operator's contract.

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# Shipping and Surviving

Every contract in this book so far has been finished when it worked. That is the point at which a reader stops and an operator starts, and the operator's questions are different ones: what happened, who can change this, and how does it end.

None of the three has anything to do with correctness. A contract can be correct and unobservable, correct and unfixable, correct and impossible to shut down.

::: {.spec title="Your commission: the guestbook an operator can run"}
Take Chapter 5's corrected guestbook and make it operable. It ships when:

1. Every signature announces itself --- a dashboard learns of it in the round it lands, without polling boxes.
2. Every refusal carries a code a client can act on without holding your source map.
3. The code can be fixed after deployment, and that power can be surrendered --- permanently, verifiably.
4. The organizer can suspend signing during an incident and lift the suspension after, without suspending their own tools.
5. When the conference ends, the organizer gets the account's minimum balance back --- boxes and base alike.
:::

## What an Operator Needs
The conference guestbook from Chapter 5 runs for three days and collects four hundred signatures. It works exactly as written, and the organizer needs three things from it that working does not supply.

On the second morning: how many people have signed? The number is on chain, and getting it means querying box by box, because the contract records signatures and announces nothing. A dashboard that wants to know the moment a signature lands has to keep asking. And when the app account ran low overnight and a signature bounced, the signer's wallet showed a program counter where the reason should have been.

On the third: a typo in a signer's display name needs correcting, and there is no path to change the contract.

On the fourth: the conference is over and the account's minimum balance stands at `100,000 + 400 × 22,100 = 8,940,000` microAlgos --- the base every account owes, plus four hundred boxes at the price Chapter 5 put on them --- against signatures nobody will ever read again. Getting it back means somebody calls `retire` four hundred times, and then a method that does not exist.

By the end of this chapter you will be able to:

- Write a log a client can read, and say what `algopy.log` does that `op.log` does not
- Tell an event, a bare log, and a return value apart in the same log array, and find an event again months later by its prefix alone
- Attach an error code to a failure, and say which client can still read it
- Say what approving `UpdateApplication` actually grants, and bound it
- Add a pause an operator can throw and lift, decide which methods it gates, and announce the throw
- Delete an application and recover what its account was holding
- Say what a box does to that, and why the order matters

## The Guestbook as It Stands
The corrected guestbook from Chapter 5, on disk at `examples/boxes/guestbook_fixed.py`, is where this chapter starts. It prices a box before writing it, refuses a signature the account cannot afford, and lets the organizer retire an entry. Every method does what its name says.

It also cannot be operated. Nothing it does reaches an indexer, nothing about it can be changed, and the account it funds cannot be emptied.

*Predict: the organizer wants all three of those fixed on the morning of day two, on the contract already on chain. Which of the three can be added without redeploying, and what decides that?*

## Saying What Happened
A contract's state is public, so anything it stores can be read. Reading is not the same as being told, and an indexer that has to poll every box to learn that one changed is doing the work a log exists to avoid.

You have emitted an event before: Chapter 8 put a `Claimed` announcement on the vesting contract's claim path, Chapter 19's lottery announced its winner, and Chapter 21's order book told its keepers about every order placed, filled and cancelled. What Chapter 8 deferred is everything an *operator* needs beyond emitting: the raw mechanism events are built on, the two other things that share the log, how a consumer tells the three apart, and how an event is found again months later by something that has never seen your source. Start below the event, at the raw mechanism.

**Example 24-1.** Logging bytes

<!-- finder: write bytes into a transaction's log -->

```python
from algopy import ARC4Contract, Bytes, UInt64, arc4, log


class Noisy(ARC4Contract):
    """`log` writes bytes to the transaction. Nothing reads them for you.

    It is a module-level function -- `algopy.log`, not `op.log` -- and it is
    variadic: it concatenates its arguments, converting `UInt64` to bytes and
    encoding a literal `str` as UTF-8.
    """

    @arc4.abimethod
    def note(self, amount: UInt64) -> None:
        # Three arguments, one log entry, no framing of any kind. A client
        # sees bytes and has to know what they mean.
        log(b"deposit:", amount, sep=b" ")
```

`op.log` does not exist. The name people reach for first is not the one that compiles.

What `log` does not do is say what the bytes mean. A client receives them and has to know already.

**Example 24-2.** An ARC-28 event

<!-- finder: emit an event a client can recognise -->

```python
from algopy import ARC4Contract, Txn, UInt64, arc4


class Signed(arc4.Struct):
    """An ARC-28 event is an ARC-4 struct, and its CLASS NAME is the event name.

    Clients match on `Signed(address,uint64)`, derived from the class name and
    the field types -- so renaming this class changes the selector and
    silently breaks every consumer watching for the old one.
    """

    who: arc4.Address
    index: arc4.UInt64


class Announcing(ARC4Contract):
    @arc4.abimethod
    def sign(self, index: UInt64) -> None:
        # The log gets a four-byte prefix, sha512_256 of the signature above,
        # then the ARC-4 encoding of the fields. That prefix is the only
        # thing distinguishing an event from a method's return value.
        arc4.emit(Signed(arc4.Address(Txn.sender), arc4.UInt64(index)))
```

The mechanism is Chapter 8's, unchanged --- class name and field types make the signature, `sha512_256` of it makes the prefix. What is new here is operational: renaming the class changes the selector, and nothing warns you. Every consumer watching for the old name goes quiet, which looks exactly like nothing happening.

**Example 24-3.** The same event, spelled out

<!-- finder: emit an event without importing its struct -->

```python
from algopy import ARC4Contract, Txn, UInt64, arc4


class AnnouncingUntyped(ARC4Contract):
    """The same event with the signature spelled out instead of imported.

    Measured on chain: this produces a byte-identical log to the struct form.
    Use it when the event is declared somewhere you cannot import from.

    The generated ARC-56 spec deduplicates events by shape, not by emit site,
    so any number of emits of one signature give one entry. Mixing this form
    with the struct form gives two, because this one carries no field names
    and puyapy synthesises `field1`/`field2` -- two spec entries describing
    one on-wire event.
    """

    @arc4.abimethod
    def sign(self, index: UInt64) -> None:
        arc4.emit("Signed(address,uint64)",
                  arc4.Address(Txn.sender), arc4.UInt64(index))
```

Measured on chain, the two forms produce byte-identical logs. Use the signature string where you cannot import the struct.

The generated ARC-56 spec deduplicates events by shape rather than by site, so four emits of one signature give one entry --- unless you mix the two forms, which gives two. The untyped form carries no field names, so PuyaPy synthesises `field1` and `field2`, and two entries then describe one on-wire event.

## Three Log Shapes, One Discriminator
A transaction's logs can hold three different things, and nothing in the log says which is which. A client has four bytes and a length to go on.

```console
>>> [(len(log), log[:4]) for log in confirmation['logs']]
(16, b'sign')
(44, b'\x91"\x88a')
(12, b'\x15\x1f|u')
>>> sha512_256(b'Signed(address,uint64)')[:4].hex()
'91228861'
>>> ARC4_RETURN_PREFIX.hex()
'151f7c75'
```

One `sign` call, three logs. The first is the raw `log`: sixteen bytes with no framing, whose leading `sign` is the beginning of the message rather than a selector --- which is the trap. The second is the event, prefixed with `sha512_256("Signed(address,uint64)")[:4]`. The third is the method's return value, which PuyaPy logs for you under the fixed prefix `151f7c75`.

Nothing distinguishes them but those four bytes and the length. A client that reads the first log as a selector gets `7369676e` and finds no event registered under it.

That is the whole basis on which an indexer separates an event from a return value, so an event's signature is an interface rather than a name.

## Saying Why It Failed
A user reports that your contract rejected their call, and the report contains one number: a program counter. Chapter 8 settled where the message went --- `assert x, "message"` puts it in a source map, and a client that kept the map can show it. This is about the client that did not.

That chapter also introduced `logged_assert` and its `ERR:code:message` lowering. Two things it did not cover decide whether a code survives to production.

*Predict: `logged_assert` writes `ERR:code:message` into the transaction's logs before failing --- and a rejected transaction never confirms. Say whether the code still reaches the client, and through what.*

**Example 24-4.** An error code that survives

<!-- finder: attach an error code a client can switch on -->

```python
from algopy import ARC4Contract, UInt64, arc4, logged_assert


class Diagnosable(ARC4Contract):
    """An assert message that reaches the client as a code it can switch on.

    A plain `assert x, "message"` puts the message in a source map the client
    needs to have kept. `logged_assert` logs `ERR:code:message` before
    failing, so the code arrives in the error string itself and survives a
    client that has no source map at all.
    """

    @arc4.abimethod
    def withdraw(self, amount: UInt64, balance: UInt64) -> UInt64:
        logged_assert(amount > UInt64(0), "amountZero", "nothing to withdraw")
        logged_assert(amount <= balance, "tooMuch", "balance will not cover it")
        return balance - amount
```

The code goes into the transaction's logs, where a client with no app spec reads it out of a `simulate`: `ERR:amountZero:nothing to withdraw`, measured. A rejected submission keeps no logs, so what this buys is legibility in simulate and in the bytecode --- not in a failed send.

::: {.gotcha #logged-assert-submit-vs-simulate topic="Compilation, tooling, and shipping" title="The error code reaches a failed send only on a node running the developer API"}
On LocalNet a rejected submission does carry the code, inside the `opcodes=` disassembly algod appends to the error. That tail comes from `EnableDeveloperAPI`, which AlgoKit's LocalNet sets true and which defaults to **false** everywhere else. Against a default node the same failure reads `logic eval error: err opcode executed. Details: app=<app-id>, pc=<n>`, with no code in it anywhere.

Test your error handling against `simulate`, which returns the logs, rather than against a LocalNet send that happens to be more generous than production.
:::

PuyaPy warns about four things here, none of which is an error --- the compiler emits the artifacts and exits zero, and it is this book's build that promotes a warning to a failure:

- The code must be camelCase.
- The code must be alphanumeric.
- The whole `ERR:code:message` string draws a warning past 64 bytes, because it lives in the bytecode.
- It draws a different warning at *exactly* 8 or 32 bytes --- the lengths of a uint64 and of a hash or address, so a log of exactly that size is ambiguous to anything parsing the transaction.

The last is the one that catches people, because it is a rule about a coincidence rather than about a mistake: `ERR:insufficient:balance too low` reads fine and is exactly 32 bytes, and adding one word fixes it. Keep both strings short, but not accidentally exact.

::: {.gotcha #arc56-has-no-errors-block topic="Compilation, tooling, and shipping" title="The ARC-56 spec carries no error-code mapping"}
`logged_assert`'s output is described as ARC-56 compatible, which is true of the *format* and not of a lookup table. PuyaPy 5.10.1 --- the version this book pins --- emits no `errors` key in the generated spec, so a client cannot resolve a code to a message by reading the app spec.

The code is recoverable because it is in the log and in the error string, not because anything published a dictionary. If your client wants human text for a code, it has to carry that mapping itself.
:::

## Changing It Later
A bug turns up in production, in a contract holding other people's money. Before you can ask what the fix is, you have to know whether the code can be changed at all --- and for most contracts the answer was decided on the day they were created, by somebody who was not thinking about this.

**Example 24-5.** Immutable, which is the default

<!-- finder: see what makes a contract impossible to change -->

```python
from algopy import ARC4Contract, UInt64, arc4


class Immutable(ARC4Contract):
    """The default, and the one worth choosing deliberately.

    No method approves `UpdateApplication` or `DeleteApplication`, so the
    compiled program refuses both -- there is no line here doing that, which
    is the point. A contract is immutable because of what it does not say.

    The AVM itself refuses nothing; it runs whatever program it is given.
    That distinction is why a non-ARC4 program returning 1 unconditionally is
    updatable by anyone. What rejects the update here is the generated router.
    """

    @arc4.abimethod(readonly=True)
    def answer(self) -> UInt64:
        return UInt64(42)
```

Immutability is the easiest property to have by accident and the hardest to notice you have lost. Nothing you can grep for grants it, and the day somebody adds a method approving `UpdateApplication` or `DeleteApplication`, nothing warns you that it is gone.

*Predict: the next listing grants the creator the power to fix bugs. Write down what the update method's body can check --- and what it cannot constrain about the program that replaces it.*

**Example 24-6.** An update path with a way to close it

<!-- finder: allow an upgrade without allowing it forever -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class Upgradeable(ARC4Contract):
    """An update path is a permission to replace the code entirely.

    Approving `UpdateApplication` does not let the creator patch a method. It
    lets them swap the whole program for a different one, keeping the
    application id, the state and the balance -- so every guarantee the
    current code makes is a guarantee only until the next update.
    """

    def __init__(self) -> None:
        self.frozen = GlobalState(UInt64(0))

    @arc4.abimethod(allow_actions=["UpdateApplication"])
    def update(self) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        # The escape hatch that makes the promise credible: once frozen, the
        # contract can never be replaced again, and the freeze is one-way.
        assert self.frozen.value == UInt64(0), "this contract is frozen"

    @arc4.abimethod
    def freeze(self) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        self.frozen.value = UInt64(1)
```

Approving `UpdateApplication` does not permit patching a method. It permits replacing the entire program, keeping the application id, the state and the balance --- so every guarantee the current code makes holds only until the next update, and a reader auditing the deployed bytecode is auditing a snapshot.

Half of the opening prediction settles here. None of the organizer's three fixes can land on the guestbook already on chain, because each one is a program change, and a program change needs an update method that shipped on day zero. The update path is the only one of the three that bootstraps itself: deployed early, it can carry in the other two, and nothing can carry it in.

That is why the freeze matters. `frozen` is one-way, and after it is set the contract can never be replaced again, which converts "trust the organizer" into "trust the organizer until this line runs".

::: {.gotcha #update-is-a-replacement-not-a-patch topic="Compilation, tooling, and shipping" title="An update replaces the whole program, not the method you meant to fix"}
`UpdateApplication` swaps the approval and clear programs entirely, keeping the application id, the global and local state, and the balance. There is no partial update and no diff.

Two consequences people meet late. Anyone auditing your deployed bytecode audited a snapshot, and an update invalidates it silently. And the new program inherits the old program's state without ever having declared it, so a schema the new code does not expect is still there and still counted against the creator's minimum balance --- unless that same update also supplies a larger global schema or extra pages, which consensus v42 now accepts. Local schema still cannot grow.
:::

A freeze is one of two switches, and shipping without the other is the more common mistake. The freeze removes a power permanently; a **pause** suspends a behaviour and can be lifted --- `frozen` minus the one-way constraint --- and it is what an operator reaches for when the fix is four hours away and the contract is losing money now. Deploying an update path without a pause means the only way to stop a live problem is to write, review and ship replacement code while it is happening.

The switch itself is nothing new: Example 10-8 gated a counter's mutations behind one admin flag. What an operator needs beyond the flag is the same thing this chapter has already given success and failure --- a way to be *told* --- plus a decision, method by method, about who the pause stops. On the guestbook, both fit on one screen.

**Example 24-7.** The guestbook, pausable

<!-- example: examples/shipping/guestbook_pausable.py mode=compile -->
<!-- finder: pause a live contract and announce the switch -->

```python
from algopy import (
    ARC4Contract, BoxMap, Global, GlobalState, Txn, UInt64, arc4,
    logged_assert, size_of,
)

BOX_FLAT = 2_500
BOX_BYTE = 400


class Entry(arc4.Struct):
    who: arc4.Address
    signed_round: arc4.UInt64


class PauseToggled(arc4.Struct):
    """The announcement. A silent switch is indistinguishable from an outage."""

    paused: arc4.Bool


class PausableGuestbook(ARC4Contract):
    """Chapter 5's guestbook wearing Example 10-8's switch, made audible.

    The flag and the guard are Chapter 10's pattern unchanged. What this
    chapter adds is the emit: the toggle announces itself, so a dashboard
    learns the switch moved without polling global state.
    """

    def __init__(self) -> None:
        self.organizer = GlobalState(Global.creator_address)
        self.signed = GlobalState(UInt64(0))
        self.paused = GlobalState(False)
        self.entry = BoxMap(UInt64, Entry, key_prefix=b"e")

    @arc4.abimethod
    def set_paused(self, paused: bool) -> None:
        assert Txn.sender == self.organizer.value, "organizer only"
        self.paused.value = paused
        arc4.emit(PauseToggled(arc4.Bool(paused)))

    @arc4.abimethod
    def sign(self) -> UInt64:
        # The guard, first, on the one method the public can change state
        # with. `logged_assert`, because "paused" is the rejection whose
        # reader is a wallet deciding what to tell its user.
        logged_assert(not self.paused.value, "paused", "signing is suspended")
        index = self.signed.value
        name_len = self.entry.key_prefix.length + UInt64(8)
        cost = UInt64(BOX_FLAT) + UInt64(BOX_BYTE) * (name_len + size_of(Entry))
        app = Global.current_application_address
        assert app.balance >= app.min_balance + cost, "app account underfunded"
        self.entry[index] = Entry(
            who=arc4.Address(Txn.sender), signed_round=arc4.UInt64(Global.round)
        )
        self.signed.value = index + UInt64(1)
        return index

    @arc4.abimethod
    def retire(self, index: UInt64) -> None:
        # Not guarded, deliberately. The pause stops the public; the tools an
        # organizer reaches for during an incident have to work during one.
        assert Txn.sender == self.organizer.value, "organizer only"
        assert index in self.entry, "no such entry"
        del self.entry[index]

    @arc4.abimethod(readonly=True)
    def count(self) -> UInt64:
        return self.signed.value
```

`set_paused` is Example 10-8's toggle plus one line, and the line is the point. A pause thrown silently is indistinguishable from an outage --- the dashboard shows signatures stopping and nothing else --- so the toggle announces itself the way a signature does, and whoever is on call reads `PauseToggled(bool)` in the round it happened instead of diffing global state against a memory of it.

The guard sits at the top of `sign`, spelled `logged_assert` rather than `assert` because "paused" is the rejection whose reader is most certain to be a wallet deciding what to tell a user. Where the guard does *not* go carries as much design as where it does:

- `count` stays readable: a pause gates writes, not reads, which is Chapter 10's rule.
- `retire` stays callable: it is the organizer's own tool, an incident is exactly when it is needed, and a pause that gates the operator's cleanup has locked the door with the keys inside.

Everything else is Chapter 5's guestbook unchanged, with `entry_at` elided for room --- it appears, unchanged, in `examples/shipping/guestbook_shippable.py` on disk.

Both switches are the operator's side of the story. A counterparty has the opposite problem: telling whether the code it audited is still the code that runs.

**Example 24-8.** Reading another application's version

<!-- finder: find out whether a contract has been replaced -->

```python
from algopy import ARC4Contract, Application, UInt64, arc4, op


class VersionAware(ARC4Contract):
    """Read how many times an application has been updated.

    `app_version` counts updates, so a non-zero value means the code running
    today is not the code that was deployed. A contract that trusts another
    can refuse to deal with one that has been replaced since it was audited.
    """

    @arc4.abimethod(readonly=True)
    def version_of(self, other: Application) -> UInt64:
        version, exists = op.AppParamsGet.app_version(other)
        assert exists, "no such application"
        return version
```

`app_version` counts updates, so a non-zero value means the code running now is not the code that was deployed. A contract that trusts another can refuse to deal with one that has been replaced since it was audited.

The freeze and `app_version` are the two halves of one question. The freeze is what an operator writes to promise the code will not change; `app_version` is what a counterparty reads to check that it has not. A promise nobody can verify is worth what it costs to make.

## Ending It
Deleting an application does not return what its account holds. The application is gone, the account survives with its balance and its holdings, and nothing can sign for it afterwards.

*Predict: the next listing sweeps the account and deletes the application in one call. Say which transaction field moves the minimum balance out --- and why `balance == 0` is the wrong test for a leftover asset.*

**Example 24-9.** Retirement with a sweep

<!-- finder: delete a contract and get its minimum balance back -->

```python
from algopy import (ARC4Contract, Asset, Global, Txn, UInt64, arc4,
                    itxn, logged_assert)


class Retirable(ARC4Contract):
    """Deleting an application does not return what its account holds.

    The application account survives the delete with its balance and its
    holdings, and nothing can sign for it afterwards -- so a sweep before the
    delete is not tidiness, it is the last moment the money is reachable.
    """

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def retire(self, token: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        app = Global.current_application_address
        # `is_opted_in`, not `balance == 0`, for two separate reasons. The
        # ledger's close rule counts HOLDINGS, not balances -- a zero-balance
        # opt-in still blocks the close -- and `Asset.balance` on an account
        # that never opted in is not a false, it is an abort, so the guard
        # would never run and the code would never be seen.
        logged_assert(not app.is_opted_in(token),
                      "sweepFirst",
                      "close the asset out before deleting")
        # Close the account itself, which returns the Algo balance including
        # the minimum balance this account was holding.
        itxn.Payment(
            receiver=Global.creator_address,
            close_remainder_to=Global.creator_address,
            fee=UInt64(0),
        ).submit()
```

The `close_remainder_to` on the inner payment is what returns the money, including the minimum balance the application account was holding --- the 100,000 microAlgo base along with everything its boxes pinned. Global schema is billed to the creator's account rather than this one, and deletion releases that separately. It has to happen in the same call that deletes the application, because after that call there is no code left to run.

::: {.gotcha #boxes-block-the-close topic="Compilation, tooling, and shipping" title="A box outlives its application, and its minimum balance with it"}
Deleting an application does not delete its boxes, and a box holds minimum balance against the application *account*, which survives. An account still holding boxes cannot be closed, so a contract that can be deleted while boxes remain has a path to stranding its own funds permanently.

Delete every box first, then close. A contract that permits deletion should check this rather than trusting whoever calls it to remember: Example 24-10's `close` refuses while any entry remains, which means it also has to keep a count of what remains.
:::

## The Guestbook an Operator Can Run
Three additions to Chapter 5's corrected guestbook, one per operator question. This is the commission's acceptance run: the event is item 1, `logged_assert` is item 2, `update` plus `freeze` is item 3, `close` is item 5 --- and item 4's pause is Example 24-7, folded in by Exercise 5. The full contract is on disk at `examples/shipping/guestbook_shippable.py` and compiles in CI.

**Example 24-10.** The guestbook, operable

<!-- finder: see a contract that can be observed, changed and shut down -->

```python
from algopy import (ARC4Contract, BoxMap, Global, GlobalState, Txn, UInt64,
                    arc4, itxn, log, logged_assert, size_of)

BOX_FLAT = 2_500
BOX_BYTE = 400


class Entry(arc4.Struct):
    who: arc4.Address
    signed_round: arc4.UInt64


class Signed(arc4.Struct):
    """The event. Its class name and field types are the ARC-28 signature."""

    who: arc4.Address
    index: arc4.UInt64


class Guestbook(ARC4Contract):
    """Chapter 5's guestbook, with the three things operating it needs."""

    def __init__(self) -> None:
        self.organizer = GlobalState(Global.creator_address)
        # Signatures ever taken. Never goes down, because it supplies the box
        # key and a retired index must never be handed out twice.
        self.signed = GlobalState(UInt64(0))
        # Boxes present right now. This is the one `close` asks about, and it
        # is a separate number for the reason Chapter 5 gives: the count a
        # signature's index is drawn from cannot also be the count of what is
        # left, or retiring an entry silently re-points the next signature at
        # a box that already exists.
        self.live = GlobalState(UInt64(0))
        self.frozen = GlobalState(UInt64(0))
        self.entry = BoxMap(UInt64, Entry, key_prefix=b"e")

    @arc4.abimethod
    def sign(self) -> UInt64:
        index = self.signed.value
        name_len = self.entry.key_prefix.length + UInt64(8)
        cost = UInt64(BOX_FLAT) + UInt64(BOX_BYTE) * (name_len + size_of(Entry))
        app = Global.current_application_address
        logged_assert(app.balance >= app.min_balance + cost,
                      "underfunded", "top up the app account")
        self.entry[index] = Entry(
            who=arc4.Address(Txn.sender), signed_round=arc4.UInt64(Global.round)
        )
        self.signed.value = index + UInt64(1)
        self.live.value += UInt64(1)
        # Two logs, deliberately different in kind. This one is raw bytes with
        # no framing at all; the emit below carries a four-byte selector; and
        # the compiler adds a third for the return value. One call, three
        # shapes, which is what a client has to tell apart.
        log(b"signed:", index, sep=b" ")
        arc4.emit(Signed(arc4.Address(Txn.sender), arc4.UInt64(index)))
        return index

    @arc4.abimethod(allow_actions=["UpdateApplication"])
    def update(self) -> None:
        assert Txn.sender == self.organizer.value, "organizer only"
        assert self.frozen.value == UInt64(0), "this guestbook is frozen"

    @arc4.abimethod
    def freeze(self) -> None:
        assert Txn.sender == self.organizer.value, "organizer only"
        self.frozen.value = UInt64(1)

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def close(self) -> None:
        assert Txn.sender == self.organizer.value, "organizer only"
        # Boxes outlive the application, and their minimum balance with them,
        # so the account cannot be closed until every one is gone.
        logged_assert(self.live.value == UInt64(0),
                      "entriesRemain", "delete every entry first")
        itxn.Payment(
            receiver=self.organizer.value,
            close_remainder_to=self.organizer.value,
            fee=UInt64(0),
        ).submit()

    @arc4.abimethod
    def retire(self, index: UInt64) -> None:
        assert Txn.sender == self.organizer.value, "organizer only"
        assert index in self.entry, "no such entry"
        del self.entry[index]
        self.live.value -= UInt64(1)

    @arc4.abimethod(readonly=True)
    def count(self) -> UInt64:
        return self.signed.value
```

**Addition one: say what happened.** `sign` emits `Signed(address,uint64)`. The organizer's dashboard now reads one log per signature instead of walking four hundred boxes, and it learns of a signature in the round it happened rather than the next time somebody polls.

**Addition two: leave a way to fix it.** `update` is organizer-only and refuses once `frozen` is set. The freeze is the half people leave out: an update path with no way to close it is a permanent power, and a conference guestbook should stop being upgradeable the day the conference ends. The one switch this listing leaves out is Example 24-7's pause; folding it in is Exercise 5.

**Addition three: make it possible to stop.** `close` deletes the application and closes the account to the organizer in the same call, and refuses while any entry remains. The four hundred boxes still have to go one at a time --- that is what a box costs --- but the money comes back.

The assertions also became `logged_assert`, so a client simulating a call it expects to fail can tell an underfunded account from an outstanding entry without holding a source map.

There is a fourth change the three additions do not account for. `close` needs to know how many boxes are left, and `signed` is not that number: Chapter 5 made it a high-water mark on purpose, so a signature's index would keep meaning something after a retirement. Decrementing it to answer `close` would have made `sign` hand out an index that already had a box under it, overwriting a live signature and leaving a contract that could never reach zero to be deleted at all. So `live` is a second counter, incremented by `sign` and decremented by `retire`, and `signed` keeps doing exactly what Chapter 5 said it did. One number cannot be both the next index and the remaining count.

The listing also drops `entry_at`, which is unchanged and left out for room.

The opening prediction's second half --- what decides it --- is now visible in full. Adding anything to a deployed contract means replacing its program, and replacing its program requires an update path that was deployed on day zero. A contract without one has made every one of these decisions permanently, on the day it was created, whether or not anybody was thinking about them. That is why the freeze rather than the update is the interesting half: the update is what you need, and the freeze is what makes needing it survivable.

## Retrieval
Answer these from memory before moving on. Three reach back into earlier chapters.

1. `log` and `arc4.emit` both write to the transaction's logs. What does a client see that tells them apart?
2. *(From Chapter 8)* What supplies an ARC-28 event's name --- and what, operationally, happens to consumers if you rename it after shipping?
3. Where does a `logged_assert` code end up, and what does a client have to do to read it?
4. A contract approves no update and no delete method. What can its creator change?
5. A contract carries both of this chapter's switches, and the freeze has been thrown. Can the operator still pause and unpause it, and what exactly can they no longer do?
6. What does deleting an application do to its account, and what does it do to its boxes?
7. *(From Chapter 11)* Who is billed for a box's minimum balance, and who is billed for global schema? Why does that decide the order of operations in `close`?
8. *(From Chapter 5)* How many boxes may a single transaction name, and who decides whether that number is eight or sixteen? What does that mean for a method that wants to delete boxes in bulk?
9. A freeze converts a promise into what, exactly? What can a counterparty read to check the promise held, without trusting the party who made it?

## Exercises
1. **(Trace)** An organizer deploys the guestbook, collects fifty signatures, then updates the contract to add a method. Walk through what changes and what does not: the application id, the boxes, the global state, the minimum balance, and any dashboard watching for `Signed(address,uint64)`. Then say which of those an auditor who read the original bytecode would need to re-check.

2. **(Parsons)** Four of these six lines are the body of a `close` method, scrambled. Two do not belong. Discard those two and say what each would cost you, then put the rest in a working order. Exactly one line's position is forced: name it, say what forces it, and say why the other three commute freely.

   ```text
   assert Txn.sender == self.organizer.value, "organizer only"
   logged_assert(self.live.value == UInt64(0), "entriesRemain")
   owner = self.organizer.value
   itxn.Payment(receiver=owner, close_remainder_to=owner, fee=UInt64(0)).submit()
   itxn.Payment(receiver=owner, close_remainder_to=owner, fee=UInt64(1000)).submit()
   del self.entry[UInt64(0)]
   ```

3. **(Debug)** A team emits `Deposited(address,uint64)` from a contract for six months. They then rename the event struct from `Deposited` to `Deposit` in a refactor that changes nothing else, and deploy it as an update. The contract works. Their analytics stop. Explain precisely what broke, why no error appeared anywhere, and what they should have done instead.

4. **(Compare)** Compare three lifecycle stances for a contract holding user funds: immutable from creation; updatable by an admin key forever; updatable until a one-way freeze. Compare on what a user must trust, what happens when a bug is found, what happens when the admin key is lost, and what an auditor can promise. Name a real situation that forces each.

5. **(Extend)** Fold Example 24-7's pause into Example 24-10's guestbook. Say which methods take the guard, which must not, and why --- Chapter 10's rule decides some of them, and `close` adds a case Chapter 10 never met. Then say what a thrown freeze does to the pause: can a frozen guestbook still be paused and unpaused, and what does your answer reveal about which method the freeze actually gates?

6. **(Extend)** The guestbook's `close` refuses while entries remain, which means an organizer with four hundred boxes must call `retire` four hundred times. Design a `sweep(first, count)` that deletes up to `count` boxes in one call. Write the signature, the guard and the loop bound; leave the body as comments. Then say what bounds `count`, what happens when it is set too high, and why the bound is not a number you can hard-code.

## Before You Continue
- [ ] I can emit an ARC-28 event and say what makes it distinguishable from a return value
- [ ] I can attach an error code, and say where a client with no source map reads it
- [ ] I can say what approving `UpdateApplication` grants, and bound it with a freeze
- [ ] I can add a pause, say which methods it must not gate, and say how the outside world learns it was thrown
- [ ] I can delete a contract, recover what its account held, and say why the boxes have to go first

## Mastery Checkpoint
That is the end of Part VII. The checklist above asks whether you followed the chapters. The Mastery Checkpoint printed on the next page asks something harder: whether you can build a thing this part did not show you. It is a small program with a stated acceptance test, and a fallback if you stall.
