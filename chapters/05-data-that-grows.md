\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# Data That Grows: Box Storage

The last chapter ended on a ceiling. A registry that moved its liabilities into the global slab became correct and, in the same stroke, became a contract with room for sixteen creditors. That is fine for a roster you control and useless for anything that hopes to get popular. Boxes are the tier that removes the ceiling: a box is an independently created, independently funded key that belongs to the application and to nobody else, and a contract can have as many of them as it can pay for.

The price is that you now pay per byte, in three currencies: minimum balance, I/O budget, and opcode budget. None of the three is checked by the compiler. This chapter is about seeing those three numbers before the chain shows them to you.

## A Record Per Attendee
A conference wants an on-chain guestbook. Attendees sign it once; the contract records who signed and in which round; anybody can ask whether a given account has signed. It is about as simple as a stateful contract gets, and it needs forty bytes per attendee: a 32-byte address followed by an 8-byte round number. Neither slab in Chapter 4 will hold that. The application's 64 global pairs and each account's 16 local ones are hard ceilings, and the number of people who will walk through the door is not a number you can declare in advance.

So the guestbook goes in a box.

Figure 5-1 is the picture Chapter 4 could not draw, because its third branch did not exist. Its first question is the one you can least afford to answer wrong.

![Figure 5-1. Where does this data go? Three questions, asked in the order that costs least to answer wrong.](figures/storage-decision-tree.svg)

The tree's first two branches are Chapter 4's material, and you can answer them already. Its third is this chapter: what a box costs to hold, and what it costs to reach.

::: {.spec title="Your commission: a guestbook that cannot fill up"}
The contract you build this chapter is the conference guestbook. It must:

1. Record a signature from any attendee --- who signed, and in which round --- and hand back a number that keeps naming that signature
2. Answer the check-in desk's question --- has this account signed? --- at a per-call cost that does not grow with the crowd
3. Take as many signatures as the conference can draw: no ceiling written into the design
4. Refuse a signature the application account cannot afford, in a sentence the organizer at the desk can act on
5. Let the organizer --- and only the organizer --- remove an entry, and reclaim what it cost to keep

Five requirements, four methods. At the end of the chapter you will re-run the finished contract against this list.
:::

By the end of this chapter you will be able to:

- Choose between global state, local state, and box storage for a given piece of data, and defend the choice by naming what it costs and who pays
- Compute a box's minimum balance requirement before you write the box, and say which account is charged
- Predict whether a given app call has enough box I/O budget to do what it is about to do, and say what to change when it does not
- Read and write a box as raw bytes at a known offset, name the two things that buys which a typed read cannot, and grow a box safely, including the one operation that looks like it grows a box and does not
- Recognize an unbounded loop over box data on sight, and replace it with something that has a ceiling you chose
- Name the three places a limit in this chapter is quietly paid for by tooling rather than by your contract, and say what happens the first time something else assembles the call

## Building the Guestbook in One Box
Here is that commission, as anyone fresh from Chapter 4 would first write it --- complete, and in full: one box, every signature appended to it, one record after another.

**Example 5-1.** The guestbook, as first written

<!-- finder: see a contract that appends records into a single box -->

```python
from algopy import (
    Account, ARC4Contract, Box, Bytes, Global, GlobalState, Txn, UInt64, arc4,
)

ENTRY = 40  # a 32-byte address followed by an 8-byte round number


class Guestbook(ARC4Contract):
    """A conference guestbook. The desk checks names off, not the chain."""

    def __init__(self) -> None:
        self.organizer = GlobalState(Global.creator_address)
        self.entries = Box(Bytes, key=b"entries")

    @arc4.abimethod
    def sign(self) -> UInt64:
        record = Txn.sender.bytes + arc4.UInt64(Global.round).bytes
        self.entries.value = self.entries.get(default=Bytes()) + record
        return self.entries.length // UInt64(ENTRY)

    @arc4.abimethod(readonly=True)
    def has_signed(self, who: Account) -> bool:
        blob = self.entries.value
        offset = UInt64(0)
        while offset < blob.length:
            if blob[offset : offset + UInt64(32)] == who.bytes:
                return True
            offset += UInt64(ENTRY)
        return False

    @arc4.abimethod(readonly=True)
    def all_entries(self) -> Bytes:
        return self.entries.value

    @arc4.abimethod
    def clear(self) -> None:
        assert Txn.sender == self.organizer.value, "organizer only"
        del self.entries.value
```

Example 5-1 is complete and deployable. It compiles, it runs on LocalNet, and it contains three decisions that are wrong. Two of them are lines you can point at. The third is a line that is not there, which is the harder kind to find and the more common kind to ship.

*Predict: three decisions in that contract are wrong. Write your three down now, in whatever words you have. You are not expected to be right yet. Check them against the diff at the end of the chapter.*

Deploy it and fund the application account with one Algo, which is the number a deployment script reaches for when nobody has done the arithmetic:

```console
$ algokit project deploy localnet
guestbook 1088 deployed
$ algokit task transfer --receiver <app address> --amount 1
```

Then sign it, over and over. For fifty-five signatures every reading is correct:

```python
>>> guestbook.send.sign().abi_return
55
>>> guestbook.send.sign().abi_return
ValueError: Error resolving execution info via simulate in transaction 0:
transaction FQ7X...4KJA: account 4WEK...5ZDQ balance 1000000 below min
1001300 (0 assets)
```

That error is not a `LogicError`. No assertion failed, and no line of the program rejected anything. The program ran to completion and *then* the node refused to keep the transaction, because applying its effects would have left an account invalid. The message is arithmetic about an account rather than a sentence about your contract.

`Error resolving execution info via simulate` means it never reached the chain. The client simulates every group holding an application call before submitting, to work out which boxes and accounts to declare, and the refusal came back from that dry run. This whole class of failure arrives as a plain `ValueError` from your client library rather than as anything Algorand-shaped.

`4WEK...5ZDQ` is the application's own address, not the signer's. And the word *box* appears nowhere in the message, even though a box is the only reason the number moved. The transaction that failed did not create a box. It appended forty bytes to a box that has existed since the first signature.

**Growing a box raises the application account's minimum balance, and it raises it at the moment of the write.**

The number is exactly derivable. The box is named `b"entries"`, seven bytes, and holds forty bytes per signature, so at *n* signatures it costs

$$2{,}500 + 400 \times (7 + 40n)$$

microAlgos of minimum balance, on top of the application account's own 100,000-microAlgo base. At *n* = 55 that totals 985,300 and the account has 1,000,000. At *n* = 56 it totals 1,001,300, and the account is 1,300 microAlgos short. Every signature costs 16,000 microAlgos (400 per byte, forty bytes), and the deployment script funded for none of them.

Figure 5-2 is that arithmetic as a picture. The balance is a flat line, because nobody sent the contract any more money. The floor is a staircase, because every signature raises it by the same 16,000, and the contract kept working right up until the two lines crossed between the fifty-fifth step and the fifty-sixth.

![Figure 5-2. A contract that works today and fails tomorrow with no change to its code. The contract stops working on the record where the two lines cross.](figures/mbr-rising-floor.svg)

Top the account up and the guestbook works again for another forty-odd signatures. Then it stops a second time, on a different error entirely:

```python
>>> guestbook.send.sign().abi_return
102
>>> guestbook.send.sign().abi_return
LogicError: Txn RQ2M...H7VA had error 'concat produced a too big (4120) byte-array'
at PC 111 and Source Line 55:
    ... 10 lines of TEAL trace ...
```

The transaction ID, the program counter and the source line are
real, and they are noise for everything this chapter is about. The `Source Line` is
there only because this client compiled the contract itself and kept the map
algod returned; a caller handed nothing but the app spec gets the program
counter and no line at all.

That one has nothing to do with money, and topping up will not touch it. `sign` reads the whole blob into a value, concatenates forty bytes onto it, and writes the value back. A value on the AVM stack cannot exceed 4,096 bytes, and 4,120 is what 103 forty-byte records come to. The box itself is allowed to reach 32,768 bytes; the program is not allowed to *hold* more than 4,096 of them at once. The one-box design hit a limit on the value, not on the storage. (The broken `sign` returns the count *after* writing, so the call that answered `102` was the hundred and second signature and the failing one is the hundred and third. The corrected version returns the index it just wrote instead, which is why its transcript later in the chapter counts from zero.)

*Predict: you have now seen two walls, at the fifty-sixth signature and the hundred and third. One of them can be pushed further out by sending the contract more money. The other cannot be pushed out by anything you put in the transaction. And there is a third wall you have not seen, pushed out for you by something nobody wrote down. Which is which, and why?*

The third defect has not failed yet, which is what makes it the dangerous one. `has_signed`, the read-only method the check-in desk calls before letting somebody sign twice, scans the whole blob in a `while` loop with no ceiling in it. Call it from a client and it keeps working: algokit-utils runs `readonly` methods through simulation, and asks simulation for **320,000 opcode units** rather than the 700 an application call gets on chain (Chapter 2 priced that 700). The method that looks free is carried by a budget more than four hundred times larger than the real one.

The bill arrives the first time anything submits that method for real, or the first time another contract calls it. `readonly` is a delay, not a reprieve. And because the loop's cost per entry moves whenever you edit the loop body, the number of signatures it survives is not a fact about the contract you can look up; it is a measurement that goes stale.

Now ship Example 5-1 anyway, and those transcripts happen to real people, in worse light. It works on LocalNet, it works on TestNet with the eleven people who tried it, and it works on the day of the conference for fifty-five attendees. The fifty-sixth is refused at the desk by an error that never says the word *box*, and nobody on site connects the two, because nobody created a box that day: the box was created weeks ago and has been getting more expensive ever since. Somebody tops the account up and the line moves again, which feels like a fix and is a countdown --- the `concat` wall is forty-seven signatures further on, and the desk's `has_signed` is one integration away from running on the real budget. Every line in that contract does exactly what it says. What ran out is a belief carried over from every other language: that appending to a list costs about the same each time. On the AVM it does not.

Three decisions caused all of this. The rest of the chapter takes box storage apart, returning to the guestbook as each piece of the design it needs comes into reach.

## One Box, and What It Costs
A box is a named byte string owned by the application. It is created by the contract, it is deleted by the contract, and no user can touch it, which is exactly the property Chapter 4 was reaching for when it moved the registry's liabilities out of local state. A box holds **0 to 32,768 bytes**, its name is **1 to 64 bytes**, and there is no limit on how many an application may have except what it can pay for.

**Example 5-2.** Declaring and reading a box

<!-- finder: store a single value in a box -->

```python
from algopy import ARC4Contract, Box, UInt64, arc4


class Tally(ARC4Contract):
    def __init__(self) -> None:
        self.total = Box(UInt64, key=b"total")

    @arc4.abimethod
    def bump(self, by: UInt64) -> UInt64:
        self.total.value = self.total.get(default=UInt64(0)) + by
        return self.total.value
```

The key line is `self.total = Box(UInt64, key=b"total")`. A `Box` is a *handle*, not a value: declaring one in `__init__` creates nothing and costs nothing. The box comes into existence on the first write, and that is the transaction that raises the minimum balance.

`.value`, `.get(default=...)`, and `.maybe()` behave exactly as they do on `GlobalState`, and for the same reason: reading a box that does not exist fails the call rather than returning zero. Everything Chapter 4 taught you about the difference between absent and zero applies here unchanged.

**Example 5-3.** Telling an absent box from an empty one

<!-- finder: check whether a box exists without failing the call -->

```python
from algopy import ARC4Contract, Box, UInt64, arc4


class Tally(ARC4Contract):
    def __init__(self) -> None:
        self.total = Box(UInt64, key=b"total")

    @arc4.abimethod(readonly=True)
    def total_if_any(self) -> tuple[UInt64, bool]:
        value, exists = self.total.maybe()
        return value, exists
```

The line that matters is `value, exists = self.total.maybe()`. On a box the distinction is sharper than it is in global state, because a box can genuinely exist while holding zero bytes: `create(size=UInt64(0))` is legal and produces a box whose `.length` is `0` and whose `bool()` is `True`. Absent, empty, and zero are three different states here, not two.

**Example 5-4.** Creating and deleting a box explicitly

<!-- finder: create a box up front and delete it to reclaim the MBR -->

```python
from algopy import ARC4Contract, Box, Global, Txn, UInt64, arc4


class Tally(ARC4Contract):
    def __init__(self) -> None:
        self.total = Box(UInt64, key=b"total")

    @arc4.abimethod
    def start(self) -> None:
        assert self.total.create(), "already started"

    @arc4.abimethod
    def stop(self) -> bool:
        assert Txn.sender == Global.creator_address, "creator only"
        existed = bool(self.total)
        del self.total.value
        return existed
```

Two lines do the work. `self.total.create()` allocates the box without writing a value and returns `False` if it already existed, so `assert self.total.create()` is how you say "this must be the first time." And `del self.total.value` deletes the box outright, which **refunds the entire minimum balance it was holding**. MBR is locked, not spent; delete the resource and the Algo becomes spendable again.

That refund is the reason `stop()` has a `Txn.sender` check on it. A method that deletes a box moves real money, even though no payment appears anywhere in it.

::: {.gotcha #box-mbr-refunded-on-delete topic="Resource references, MBR, and budget" title="Deleting or shrinking a box refunds its minimum balance"}
Box minimum balance is locked, not spent. Deleting a box refunds the entire charge --- the 2,500-microAlgo base and 400 per byte of name and contents --- to the application account, and shrinking one refunds the 400 per byte removed. It is the only mechanism in the box model that makes the account's floor go *down*, which is why a method that deletes a box moves real money even though no payment appears anywhere in it: an unguarded `clear` or `retire` is a withdrawal lever. Put a sender check on anything that deletes or shrinks a box, and treat the refund as part of the contract's economics rather than a rounding detail.
:::

**Example 5-5.** What the application account can actually spend

<!-- finder: check the app account has enough balance before creating a box -->

```python
from algopy import ARC4Contract, Box, Global, UInt64, arc4


class Vault(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(UInt64, key=b"d")

    @arc4.abimethod(readonly=True)
    def spendable(self) -> UInt64:
        app = Global.current_application_address
        if app.balance <= app.min_balance:
            return UInt64(0)
        return app.balance - app.min_balance

    @arc4.abimethod
    def open_vault(self) -> None:
        app = Global.current_application_address
        cost = UInt64(2_500) + UInt64(400) * (UInt64(1) + UInt64(8))
        assert app.balance >= app.min_balance + cost, "app account underfunded"
        assert self.data.create(), "already open"
```

`assert app.balance >= app.min_balance + cost` is the guard. Both fields are readable from inside the contract, on any account the transaction has made available, and `Global.current_application_address` is always available to the application itself. The difference between them is what the account can part with without becoming invalid.

Which makes it tempting to write the check the way you would say it out loud, as `assert app.balance - app.min_balance >= cost`. Do not. UInt64 subtraction on the AVM does not go negative; it fails the transaction. A contract that has been deployed but never funded has `balance = 0` against a `min_balance` of 100,000, so that subtraction is exactly the case that underflows, and the reader gets `- would result negative` instead of your message. **Write the guard as an addition on the right-hand side, and the underflow cannot happen.** `spendable()` in the same example makes the same move with an explicit zero case.

`open_vault` computes what its box will cost before creating it, and refuses with a message that names the problem. The chain's version of "you are underfunded" is arithmetic about an account; yours can be a sentence.

The single-concept examples that follow (the ones demonstrating `create`, `resize`, `replace`, `extract`, and the `BoxMap` machinery) do not carry this guard. Each is stripped to the one operation it teaches, and a four-line pre-flight in front of a three-line method would bury the line you are meant to be reading. That is a presentation choice, not a pattern: every one of them creates or grows a box, so every one of them needs the guard before it goes anywhere near a network you care about. This example is the form to copy, and the corrected guestbook at the end of the chapter shows it in situ. Where an example has some *other* reason to omit something, it says so in a comment on the line.

*Predict: `open_vault`'s box is named `b"d"` and holds a single eight-byte number, nine bytes of data in all. Guess what it costs to keep, in microAlgos, before you read the next line.*

The `cost` that guard compares against comes from one formula. For a single box it is short enough to keep in your head:

$$2{,}500 + 400 \times (\text{name bytes} + \text{value bytes})$$

`open_vault`'s box is named `b"d"` and holds an eight-byte number, so it costs 2,500 + 400 × 9 = 6,100 microAlgos, which is the number the contract computes inline. Both terms are *bytes*, and the name is one of them: a fact that costs nothing here, where the name is a byte long and written in the source, and costs real money in the next section, where the names are generated.

Table 5-1 is the whole pricing model. Memorizing it repays the same effort Table 4-2 in Chapter 4 did: getting it wrong produces a funding bug in a script rather than an error in a compiler.

: Table 5-1. What box storage costs, and who pays it

| Cost | Amount | Charged to | Refunded when |
|------|--------|------------|---------------|
| Box exists at all | 2,500 microAlgos | the **application account** | the box is deleted |
| Each byte of name | 400 microAlgos | the **application account** | the box is deleted |
| Each byte of contents | 400 microAlgos | the **application account** | the box is deleted or shrunk |

Every row says *application account*, and that is the asymmetry to hold against Chapter 4. Global and local schema MBR follows a **user**: the creator for global, the opting-in account for local. Box MBR follows the **contract**. A deployment script that funds the creator generously and the application address not at all will deploy a contract that cannot store anything, and the error will be about a balance.

::: {.gotcha #box-growth-raises-app-mbr topic="Resource references, MBR, and budget" title="Writing a box can make a contract that worked yesterday stop working today"}
Creating or growing a box raises the *application account's* minimum balance by 400 microAlgos per byte, plus 2,500 per new box, and none of it shows in the source, a compiler warning, or a test. The contract keeps working until the balance meets a floor that has been rising underneath it; then every call that writes a box fails, with an error about an account rather than a box: `account <address> balance <n> below min <m> (<k> assets)`. It is not a `LogicError`: the check runs after your program has already returned success. Storage that grows with usage needs a funding plan that grows with it, or a pre-flight check like Example 5-5 that refuses in a sentence a caller can act on.
:::

For the guestbook, this explains the fifty-sixth signature. The contract never asked what the write would cost, so the chain answered with an account error instead. A pre-flight check turns an unexplained balance failure into a named one.

## Many Boxes, and What They're Named
One box per contract is rarely what you want. `BoxMap` gives you a keyed family of boxes: one box per key, each independently created, each independently priced. It is a naming scheme rather than a data structure, and every bug in it is a naming bug.

**Example 5-6.** A box per account

<!-- finder: store one value per account in boxes -->

```python
from algopy import Account, ARC4Contract, BoxMap, Txn, UInt64, arc4


class League(ARC4Contract):
    def __init__(self) -> None:
        self.score = BoxMap(Account, UInt64)

    @arc4.abimethod
    def record(self, points: UInt64) -> UInt64:
        total = self.score.get(Txn.sender, default=UInt64(0)) + points
        self.score[Txn.sender] = total
        return total

    @arc4.abimethod(readonly=True)
    def score_of(self, who: Account) -> UInt64:
        return self.score.get(who, default=UInt64(0))
```

The line to watch is `self.score = BoxMap(Account, UInt64)`. Compare it to Chapter 4's `GlobalMap`, which has the same shape and a completely different bill: a `GlobalMap` entry consumes one of the application's 64 shared global slots, so the map has a hard ceiling and the creator pays. A `BoxMap` entry is its own box, so there is no ceiling and the application account pays. That is the whole trade, and it is the answer to the registry's sixteen-creditor problem.

**Example 5-7.** What a BoxMap actually names

<!-- finder: find out the real box name behind a BoxMap key -->

```python
from algopy import Account, ARC4Contract, BoxMap, Bytes, UInt64, arc4


class League(ARC4Contract):
    def __init__(self) -> None:
        self.score = BoxMap(Account, UInt64)

    @arc4.abimethod(readonly=True)
    def prefix(self) -> Bytes:
        return self.score.key_prefix

    @arc4.abimethod(readonly=True)
    def box_name(self, who: Account) -> Bytes:
        return self.score.box(who).key
```

The key line is `self.score.box(who).key`. `BoxMap` is a naming convention, not a new storage primitive: `self.score[who]` reads the box named `key_prefix + encode(who)`, and nothing about it is special to the AVM. When `key_prefix` is not given it defaults to the member variable's own name. Here that is `b"score"`, five bytes of name on every single box, charged 400 microAlgos each. Naming the map `self.s` would save 1,600 microAlgos per box and leave you an unreadable contract; `key_prefix=b"s"` takes the saving without the cost.

That saving is the single-box formula from the last section, applied to a name nobody wrote down. Make the contract do that arithmetic rather than a deployment script.

**Example 5-8.** Pricing a box before you write it

<!-- finder: compute the MBR cost of a box in the contract itself -->

```python
from algopy import Account, ARC4Contract, BoxMap, UInt64, arc4, size_of


class Record(arc4.Struct):
    score: arc4.UInt64
    streak: arc4.UInt16


class League(ARC4Contract):
    def __init__(self) -> None:
        self.record = BoxMap(Account, Record, key_prefix=b"r")

    @arc4.abimethod(readonly=True)
    def cost_per_player(self) -> UInt64:
        name_len = self.record.key_prefix.length + UInt64(32)
        return UInt64(2_500) + UInt64(400) * (name_len + size_of(Record))
```

The line that matters is `name_len = self.record.key_prefix.length + UInt64(32)`. **The box name is not the key you passed.** For a `BoxMap` it is the prefix followed by the encoded key, so a map with a one-byte prefix keyed by a 32-byte address has 33-byte names, and a funding calculation that counted 32 underfunds every box by 400 microAlgos. `size_of(Record)` supplies the other term at compile time for any fixed-size type, so the whole cost can be computed by the contract rather than transcribed into a deployment script and then quietly diverged from.

**Example 5-9.** Two maps that write the same box

<!-- finder: understand why two BoxMaps can overwrite each other -->

```python
from algopy import ARC4Contract, BoxMap, Bytes, UInt64, arc4


class Ledger(ARC4Contract):
    def __init__(self) -> None:
        self.short = BoxMap(Bytes, UInt64, key_prefix=b"a")
        self.long = BoxMap(Bytes, UInt64, key_prefix=b"ab")

    @arc4.abimethod
    def collide(self) -> bool:
        self.short[Bytes(b"bc")] = UInt64(1)
        self.long[Bytes(b"c")] = UInt64(2)
        # Both wrote the box named b"abc". The second write won.
        return self.short[Bytes(b"bc")] == UInt64(2)
```

*Predict before you read on: one map has `key_prefix=b"a"` and is handed the key `b"bc"`. The other has `key_prefix=b"ab"` and is handed the key `b"c"`. Write down the box name each one ends up reading.*

`key_prefix=b"a"` with the key `b"bc"` names the box `b"abc"`. `key_prefix=b"ab"` with the key `b"c"` also names the box `b"abc"`. They are the same box. The second write overwrites the first, `collide()` returns `True`, and no part of the toolchain warned anybody, because concatenation is all that happened, and concatenation does not know where you meant the seam to be.

The example is contrived and the shape is not: any two `BoxMap`s over a variable-length key type --- `Bytes`, `String`, a dynamic array --- can be made to collide by choosing prefixes that overlap where the keys differ.

::: {.gotcha #box-prefix-collision topic="Box storage" title="Two BoxMaps with variable-length keys can name the same box"}
A `BoxMap` box name is nothing but `key_prefix + encode(key)`, so a map with prefix `b"a"` and key `b"bc"` names the same box as a map with prefix `b"ab"` and key `b"c"`. The second write silently overwrites the first and no tool warns you, because concatenation cannot tell where you meant the seam to be. Fixed-width keys (`Account`, `UInt64`, a fixed-size struct, a `FixedArray`) are immune, since every name in the family is the same length. With `Bytes`, `String`, or dynamic array keys, give every map a prefix of the same length or include a separator that cannot occur in a key.
:::

**Example 5-10.** A composite key

<!-- finder: key a BoxMap by more than one value -->

```python
from algopy import ARC4Contract, BoxMap, Global, Txn, UInt64, arc4

SEASON_ROUNDS = 1_000_000


class Slot(arc4.Struct):
    owner: arc4.Address
    season: arc4.UInt64


class League(ARC4Contract):
    def __init__(self) -> None:
        self.score = BoxMap(Slot, UInt64, key_prefix=b"s")

    @arc4.abimethod
    def record(self, points: UInt64) -> UInt64:
        season = Global.round // UInt64(SEASON_ROUNDS)  # not a caller argument
        key = Slot(owner=arc4.Address(Txn.sender), season=arc4.UInt64(season))
        total = self.score.get(key, default=UInt64(0)) + points
        self.score[key] = total
        return total
```

`self.score = BoxMap(Slot, UInt64, key_prefix=b"s")` declares it, where `Slot` is an `arc4.Struct` of an address and a season. The season comes from `Global.round // SEASON_ROUNDS`, computed by the contract, not taken as an argument. A caller who can choose a key field can choose an unbounded number of them, and every distinct key is a new box at the application's expense; the composite key is the shape that makes that mistake cheap to write and expensive to hold. Any fixed-size ARC-4 type can be a key, and the encoding is what gets concatenated, so a two-field key costs its two fields' worth of name: here 1 + 32 + 8 = 41 bytes of name for 8 bytes of value, which is what makes wide keys expensive. It is also why a composite key is safe from the collision in the preceding section: every key in the family encodes to exactly 40 bytes.

For the guestbook, this is the shape of the fix. One box that every signature reads and rewrites is a cost that grows with the number of people who came before you. One box per signature, keyed by an index, is a cost that does not.

## What a Transaction Must Declare
Naming is settled. Reaching is a separate problem, and the one that fails in production, because it is the only rule in this chapter enforced by the transaction rather than by the program.

*A contract may only touch boxes the transaction declared in advance.* Every box a call will read or write has to be listed on the transaction before the program starts running. Nothing in the method signature does this for you: `score_of(who: Account)` names an account, and the account reference it implies is not the box reference the body needs. A box the transaction did not declare does not read as empty; it fails the call with `invalid Box reference`.

The rule is new. Chapter 4's global and local state needed no declarations at all, because the schema was fixed at creation and the AVM already knew where to look. Nor is it the resource rule you met in Example 2-4, where passing an `Account` or an `Asset` as an argument made it available as a side effect of the signature. Boxes have no such side effect, because a box name is bytes the program computes, and the transaction is assembled before the program runs. Appendix B tabulates the caps and the exact accounting in full.

**Example 5-11.** Letting the client work out the references

<!-- finder: avoid declaring box references by hand on every call -->

```python
"""Let algokit-utils work out which boxes an app call needs to reference."""

import sys

from algokit_utils import AlgorandClient, SendParams

from smart_contracts.artifacts.league.league_client import LeagueClient


def main(app_id: int) -> int:
    algorand = AlgorandClient.from_environment()
    who = algorand.account.from_environment("DEPLOYER")
    app = LeagueClient(algorand=algorand, app_id=app_id, default_sender=who.address)
    params = SendParams(populate_app_call_resources=True)
    return int(app.send.record(args=(10,), send_params=params).abi_return)


if __name__ == "__main__":
    main(int(sys.argv[1]))
```

The line to watch is `SendParams(populate_app_call_resources=True)`. algokit-utils simulates the call first, reads back the resources the simulation says it wanted, and puts them on the real transaction. This is on by default in algokit-utils 4.x, and it removes most of the tedium.

It is a convenience and not a guarantee: the simulation only discovers the boxes that *the path it took* touched. A method that reads a different box depending on an argument will populate correctly for the argument you simulated and incorrectly for the one you did not.

A box reference does two things. It makes the box *available*, and it grants **2,048 bytes of I/O budget** (consensus v41 raised this from 1,024). The second half is where the mistakes live. They come from assuming the budget works like a bandwidth meter counting bytes as they move. It does not.

**The allowance is checked twice, as two separate budgets that are never added together, and each one charges a box's *whole size* rather than the bytes you touched.**

The *read* budget is charged **before the program runs at all**. The node adds up the full current size of every box the transaction referenced *that exists*, and if that total is over the allowance the call is dead before its first opcode, whether or not the program was ever going to read a single one of those boxes. Reference a 3,000-byte box you had no intention of reading, on one reference, and the call fails with `box read budget (2048) exceeded`. That message names the budget and stops. It does not say how many bytes you asked for, so the arithmetic that got you here is yours to redo.

The *write* budget is charged as the program runs, once per box written, again at the box's full size, and for `resize`, at its full *new* size. Overwriting one byte of a 3,000-byte box costs 3,000 against the write budget, not one. Deleting a box refunds only what the same group has already spent writing that box; deleting a box nobody in the group has written refunds nothing, because nothing was charged.

Two consequences follow. A read-modify-write does *not* cost double: reading a 1,500-byte box and writing it back charges 1,500 against the read budget and 1,500 against the write budget, and since the two are never summed, that call fits on a single 2,048-byte reference. And the two levers a call has are which boxes it references and how many references it carries; the bytes it touches are not one of them.

Table 5-2 works four calls through both budgets. Rows two through four are the ones that catch people.

: Table 5-2. Four calls, and the references each one needs

| What the call does | Read budget | Write budget | References |
|----------------------------------|----------|----------|--------|
| Reads and rewrites one 1,500-byte box | 1,500 | 1,500 | 1 |
| References one 3,000-byte box and never reads it | 3,000 | 0 | 2 |
| References two 1,200-byte boxes, writes one | 2,400 | 1,200 | 2 |
| Creates a box that does not exist yet, 40 bytes | 0 | 40 | 1 |

Row two is the read budget charging for a box the program ignores. Row three is both budgets summing across the boxes they cover (the read side over every referenced box that exists, the write side over every box actually written), so the *larger* of the two is what has to fit, and here that is the read side, inflated by a box the program only ever writes to. Row four is the mirror image: a box that does not exist yet is charged nothing on read, because there is nothing there to charge for.

Before references multiply, run the two budgets once by hand, on numbers you already have. The broken guestbook's box holds forty bytes per signature. Take the call that records the thirtieth signature: twenty-nine records exist, so the box holds 29 × 40 = 1,160 bytes.

- **Read budget:** the box exists and the transaction references it, so the charge is its full current size --- 1,160 --- before the first opcode, whether or not `sign` was going to read it. (It was: it reads the blob to append to it.)
- **Write budget:** `sign` writes the grown blob back, and the charge is the box's whole new size, 30 × 40 = 1,200. Not the forty bytes that changed.
- The two are never added. Each sits under 2,048, so one reference carries the call.

Now find the first signature one reference cannot carry. The write charge runs forty bytes ahead of the read charge, so it hits the wall first, at the smallest *n* with 40*n* > 2,048: *n* = 52, charging 2,080. Hold on to that number; the script in Example 5-12 is about to confirm it.

The escape hatch: *references do not have to name distinct boxes.* Declaring the same box twice grants it 4,096 bytes, three times 6,144, and so on. Both budgets pool across the entire transaction group, not just one call. A single transaction uses either the legacy foreign arrays or the v41 `Access` list, never both, and Table 5-3 is the whole difference between the two paths.

: Table 5-3. The two reference paths, and the ceiling each one buys

| | Legacy foreign arrays | v41 `Access` list |
|---|---|---|
| References per transaction | 8, combined across all resource types | 16, of any resource type |
| I/O budget if all are box or empty references | 16,384 bytes | 32,768 bytes --- exactly a box's maximum size |

Which path a call takes is decided by whatever assembles the transaction, not by anything in your contract, so unless you own every client that will ever call you, design against eight and treat sixteen as a ceiling rather than a floor. A box large enough to need more than eight references is a box only a caller you control can reach at all.

**Example 5-12.** Working out how many references a call needs

<!-- finder: work out how many box references an app call needs -->

```python
"""Work out how many box references a call needs for the boxes it touches."""

import sys

BYTES_PER_REF = 2048  # I/O budget per box reference, consensus v41+


def refs_needed(existing_sizes: list[int], written_sizes: list[int]) -> int:
    """Read and write are separate budgets, each charging a box's FULL size."""
    read = sum(existing_sizes)
    write = sum(written_sizes)
    by_budget = -(-max(read, write) // BYTES_PER_REF)  # never summed
    return max(len(existing_sizes), by_budget)


if __name__ == "__main__":
    sizes = [int(a) for a in sys.argv[1:]]
    print(f"{sum(sizes)}B in {len(sizes)} boxes: {refs_needed(sizes, sizes)} refs")
```

That script takes the two budgets separately and returns the larger requirement. It also floors the answer at the number of boxes touched, because budget is not the only thing a reference buys: every box must be *named* by some reference whether or not the budget needed it, so a call touching five tiny boxes needs five references even though their combined size fits in one. Run the broken guestbook through it, and it hands back the number you worked by hand: the **fifty-second** signature is the first that one reference cannot carry: `write budget (2048) exceeded 2080`. The two numbers come in that order: the budget first, then the total you tried to dirty. The message names no box and no operation, so in a group that writes several boxes it tells you *that* the budget went and not *which* write took it. That one you narrow by hand.

*Predict: that wall lands at the fifty-second signature and the minimum-balance wall lands at the fifty-sixth. The conference story has the organizer meeting the balance error first. What could make the earlier wall arrive later than the later one?*

The answer is the tooling. `populate_app_call_resources` does not just find the boxes a call needs; it also reads back how much extra I/O budget the simulation wanted and pads the transaction with that many *empty* box references, up to the eight-reference cap. Empty and duplicate references both count toward the allowance, so a default client call quietly buys as much budget as the simulation says it needs, up to 16,384 bytes rather than 2,048. That moves the write-budget wall from the fifty-second signature out to the four hundred and tenth, which is why the conference organizer met the minimum-balance error at the fifty-sixth and never saw a budget error at all.

*The budget failure was not absent from the broken contract; it was paid for by a client-side convenience, and it comes back the moment the call is assembled by something that does not pad*: another contract, a hand-built transaction, a different SDK. Two of the three walls in this chapter are like this. The one that cannot be papered over is the 4,096-byte limit on a value, because that limit is about what the program may hold in a register, and no number of references changes it.

::: {.gotcha #resource-padding-hides-budget-walls topic="Resource references, MBR, and budget" title="algokit-utils pads box references, so budget failures wait for a different caller"}
`populate_app_call_resources` does more than discover which boxes a call needs: it reads back how much extra I/O budget the simulation wanted and pads the transaction with empty box references, up to the eight-reference cap --- 16,384 bytes where the naive arithmetic says 2,048. A budget failure that padding can cover therefore never appears under the default client. It comes back, unchanged, the first time the same call is assembled by something that does not pad: another contract, a hand-built transaction, a different SDK. When a box-heavy method works in your scripts, rerun the arithmetic on one unpadded reference before concluding that it works.
:::

Three conveniences hide limits in this chapter, and a contract that passes every check you know how to run can be sitting on all three at once. `populate_app_call_resources` pads the I/O budget. `readonly=True` buys a method 320,000 opcode units under simulation instead of the 700 it gets on chain, which you already met carrying the broken guestbook's `has_signed`. And `algopy_testing`, the framework Chapter 8 builds on, emulates box *contents* faithfully and does not enforce the I/O budget or the 4,096-byte stack limit at all, so a green unit test is silent about both. None of the three is a defect. What they have in common is that they are all on the *caller's* side of the boundary, and the caller is the one thing your contract does not get to choose.

::: {.gotcha #box-charged-at-full-size topic="Resource references, MBR, and budget" title="A box is charged at its full size, however few bytes you touch"}
Each box reference grants 2,048 bytes of I/O budget, and that allowance is checked as **two separate budgets that are never added together**. The *read* budget is charged before your program runs, as the sum of the full current sizes of every referenced box that exists, even one you never intended to read. The *write* budget is charged as the full size of each box written, once per box, with `box_resize` charging the full **new** size. Neither charges the bytes you touched: `extract`, `replace`, and `.length` all cost the same as `.value`. Both budgets pool across the whole transaction group, and references need not be distinct: duplicate and empty references each grant another 2,048 bytes, which is the fix.
:::

Table 5-4 is the full ladder for the one-box guestbook, on a single reference.

: Table 5-4. The four walls of the one-box guestbook, on a single reference

| Signature | Wall | The arithmetic |
|---|---|---|
| 52nd | write budget | 40 × 52 = 2,080 bytes, over one reference's 2,048 |
| 56th | minimum balance | the floor crosses the account's 1,000,000-microAlgo funding |
| 103rd | value size | the blob passes 4,096 bytes in `concat` |
| 820th | box size | 819 entries fit in 32,760 bytes; the 820th does not --- never reached |

Every one of those walls is invisible in the source, and the order they arrive in depends on how the transaction was assembled.

For the guestbook, the invisible walls are now countable. The fifty-second and hundred and third signatures stop being surprises and become arithmetic you can do before deploying.

## Bytes, Not Values
Everything so far has treated a box as a typed value. Underneath it is a byte string, and the AVM has opcodes that read and write *ranges* of it without ever materializing the rest. Since a box is charged at its full size no matter how few bytes you touch, it is fair to ask what those opcodes are for, if not for saving budget.

They are for reach. A typed read has to put the whole box on the stack, and **a value on the AVM stack cannot exceed 4,096 bytes**. Above that size, `.value` does not become expensive; it becomes impossible, and the range operations are the only way to get at the box at all. That is the wall the broken guestbook hit at its hundred and third signature.

**Example 5-13.** A box sized up front

<!-- finder: allocate a box of a fixed size and read part of it -->

```python
from algopy import ARC4Contract, Box, Bytes, Global, Txn, UInt64, arc4

MAX_BOX = 32_768


class Blob(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"data")

    @arc4.abimethod
    def allocate(self, size: UInt64) -> bool:
        assert Txn.sender == Global.creator_address, "creator only"
        assert size <= UInt64(MAX_BOX), "max box size is 32,768 bytes"
        return self.data.create(size=size)

    @arc4.abimethod(readonly=True)
    def head(self, length: UInt64) -> Bytes:
        return self.data.extract(UInt64(0), length)
```

The key line is `self.data.create(size=size)`. For a `Box[Bytes]` (a box with no fixed-size type behind it), `create` **requires** a size, because there is nothing to infer one from. Neither assertion above it is decoration. The size check is there because 32,768 is a hard AVM limit, and a `create` past it fails with an error about the box rather than about your argument. The sender check is there because `size` is a caller's argument and the minimum balance it locks is the *application's* money: an unguarded `allocate` lets any stranger convert 13.1 Algo of the contract's balance into an unusable box for the price of one transaction fee, and, since `create` on an existing box of a different size fails outright, keep it that way forever. Any method whose argument sets a box's size belongs behind a caller check.

`create` is stricter than it looks. Called on a box that already exists **at the same size**, it does nothing and returns `False`. Called on a box that exists at a *different* size, it fails the call. It is not a resize.

**Example 5-14.** The Box behind a BoxMap entry

<!-- finder: use raw box operations on one entry of a BoxMap -->

```python
from algopy import Account, ARC4Contract, BoxMap, UInt64, arc4


class League(ARC4Contract):
    def __init__(self) -> None:
        self.score = BoxMap(Account, UInt64)

    @arc4.abimethod(readonly=True)
    def score_size(self, who: Account) -> UInt64:
        return self.score.box(who).length
```

The line that matters is `self.score.box(who)`, which hands you an ordinary `Box` for one entry. Everything in this section applies to `BoxMap` entries through that handle: there is no second API to learn, because there was never a second primitive.

::: {.gotcha #boxref-is-deprecated topic="Compilation, tooling, and shipping" title="BoxRef is deprecated and its methods are on Box"}
Older code and older tutorials reach for `BoxRef` for the byte-level box operations (`create`, `resize`, `splice`, `extract`, `replace`) and for `.ref` to get at them from a typed `Box`. As of `algorand-python` 3.5.0 both are deprecated: the stub carries `@deprecated("Methods in BoxRef are now directly available on Box")`, and `.ref` carries one of its own. The methods live on `Box` now.

The deprecation is silent at compile time, so the old form keeps working and keeps being copied.
:::

**Example 5-15.** Asking a box how big it is

<!-- finder: get a box's size without reading its contents -->

```python
from algopy import ARC4Contract, Box, Bytes, UInt64, arc4


class Blob(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"data")

    @arc4.abimethod(readonly=True)
    def size(self) -> UInt64:
        assert self.data, "box does not exist"
        return self.data.length
```

`.length` adds nothing to the *write* budget, because it writes nothing, and it works at any size because the number it returns never puts the box on the stack. What it does not do is dodge the read budget: that was charged before the program started, at the box's full size, purely because the transaction referenced it. A method whose only box operation is `.length` on a 30,000-byte box still needs fifteen references to run. The `assert self.data` above it does one thing the compiler's own check does not. PuyaPy already emits an existence check behind `.length`, so the call fails either way; the explicit assertion gives the failure a sentence instead of a bare `assert failed` at whatever line the compiler chose.

**Example 5-16.** Writing one slot of a packed box

<!-- finder: update part of a box without rewriting the whole thing -->

```python
from algopy import ARC4Contract, Box, Bytes, Global, Txn, UInt64, arc4

SLOT = 8
MAX_SLOTS = 64


class Slots(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"slots")

    @arc4.abimethod
    def allocate(self, count: UInt64) -> bool:
        assert Txn.sender == Global.creator_address, "creator only"
        assert count <= UInt64(MAX_SLOTS), "too many slots"
        return self.data.create(size=count * UInt64(SLOT))

    @arc4.abimethod
    def write(self, index: UInt64, value: arc4.UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        self.data.replace(index * UInt64(SLOT), value.bytes)
```

`self.data.replace(index * UInt64(SLOT), value.bytes)` is the write. `replace` puts bytes at an offset and leaves the box's size alone; if the write would run past the end, the call fails.

The folklore about what it buys is wrong. It does **not** reduce the write budget: the box is charged its full size the moment the program writes to it, by `replace` exactly as by `.value`. What it buys is two things the budget has nothing to do with. It works on boxes above 4,096 bytes, where the read-modify-write through `.value` cannot run at all. And its opcode cost is constant in the box's size rather than proportional to it, which keeps a method's 700 units from being consumed by copying bytes it did not care about.

**Example 5-17.** Reading one slot of a packed box

<!-- finder: read part of a box without reading the whole thing -->

```python
from algopy import ARC4Contract, Box, Bytes, UInt64, arc4

SLOT = 8


class Slots(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"slots")

    @arc4.abimethod(readonly=True)
    def read(self, index: UInt64) -> arc4.UInt64:
        raw = self.data.extract(index * UInt64(SLOT), UInt64(SLOT))
        return arc4.UInt64.from_bytes(raw)
```

`extract(start, length)` is `replace`'s twin and buys exactly the same two things for the same reason: it reaches into a box of any size, and its cost in opcodes does not grow with the box. The read budget was already charged in full before the program started, so `extract` is not saving it anything either.

`arc4.UInt64.from_bytes(raw)` then reinterprets the eight bytes as a number. It checks nothing. Extract from the wrong offset and you get a perfectly valid number that means nothing.

*Predict: a box holds 20,000 bytes and a method reads eight of them with `extract`, changes nothing, and returns. How many box references does that call need? The answer is not one.*

Ten. The read budget was charged at the box's full 20,000 bytes before the program ran a single opcode, purely because the transaction named the box, and 20,000 over 2,048 rounds up to ten. The eight bytes you actually wanted had no say in it, which is why the next figure prices packing against splitting.

MBR is the half of the trade that *packing* really does change, and Figure 5-3 prices it.

![Figure 5-3. The same twenty-four bytes stored two ways, priced both times. Splitting a struct across three boxes pays for the account address three times over.](figures/packed-box-layout.svg)

The figure compares one struct in one box against the same struct split across three, and the split loses badly: the 2,500-microAlgo constant and the key bytes are charged once *per box*, so a 32-byte address in the name gets paid for three times. Splitting also costs references: three boxes need at least three, where one box needs one. Here packing wins on both counts, and offset access is what makes a packed box workable to read and write once it is large.

The ten references you just counted for a 20,000-byte box are the argument *for* splitting: a call that needed only one piece could reference only that piece and pay for only that piece. Both readings are right, and they answer different questions. Splitting buys I/O budget when a call genuinely needs one piece and not the others; it costs minimum balance always, on every piece, for as long as the pieces exist. So the seam goes where the access pattern already puts it: pack what is read together, split what is read apart. The figure's struct loses by splitting because all three of its pieces are always read at once.

**Example 5-18.** Sizing a box from its type

<!-- finder: create a box exactly the size of the struct it will hold -->

```python
from algopy import ARC4Contract, Box, Global, Txn, arc4, size_of, zero_bytes


class Record(arc4.Struct):
    score: arc4.UInt64
    streak: arc4.UInt16


class League(ARC4Contract):
    def __init__(self) -> None:
        self.record = Box(Record, key=b"r")

    @arc4.abimethod
    def reset(self) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.record.create(size=size_of(Record)), "already allocated"
        self.record.value = zero_bytes(Record)
```

Two calls, and together they are the canonical way to allocate a fixed-size record. `size_of(Record)` is the encoded size of any fixed-size type, computed at compile time (10 bytes here, for an 8-byte and a 2-byte field), so the size never has to be written down twice and cannot drift when you add a field. `zero_bytes(Record)` produces a correctly-sized zero value of that type, which is how you initialize a record without constructing one field by field.

The two assertions wrapped around them are not part of the pattern, but they are part of shipping it. `create` returns `False` when the box already exists at that size, and letting that `False` fall on the floor is a compiler warning (`expression result is ignored`) and a silent overwrite of live data; asserting it turns `reset` into a method that can only run once. The sender check is there because the line below destroys a record, and a method that destroys data is as privileged as one that spends money.

For the guestbook, this reaches the hundred and third signature and only that one. Rewriting `sign` to `resize` and `replace` instead of reading `.value` and concatenating would move the 4,096-byte wall out of the way entirely, because no version of the box would ever reach the stack. That design is Example 5-21 in the next section, a real alternative to the correction this chapter makes.

## Changing a Box's Size
A box's size is fixed until something changes it, and exactly one operation changes it.

**Example 5-19.** Growing a box

<!-- finder: make an existing box bigger -->

```python
from algopy import ARC4Contract, Box, Bytes, Global, Txn, UInt64, arc4


class Blob(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"data")

    @arc4.abimethod
    def start(self) -> bool:
        assert Txn.sender == Global.creator_address, "creator only"
        return self.data.create(size=UInt64(0))

    @arc4.abimethod
    def grow(self, extra: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        new_size = self.data.length + extra
        assert new_size <= UInt64(32_768), "max box size is 32,768 bytes"
        self.data.resize(new_size)
        return new_size
```

`start` is here because `grow` cannot bootstrap itself: `.length` on a box that does not exist fails, so a `Blob` with only a `grow` method has no reachable first call. The line to watch is `self.data.resize(new_size)`. Growing zero-pads on the right; shrinking truncates on the right and **refunds the minimum balance for the bytes removed**. It is the only operation that changes a box's size, and every byte of the new size is charged at 400 microAlgos to the application account at the moment the call runs.

It is also charged against the write budget at its whole new size, easy to forget here because `resize` looks like it only touches the difference. Growing a box from 2,000 bytes to 2,100 charges 2,100 against the write budget, not 100.

**Example 5-20.** The operation that looks like it grows a box

<!-- finder: insert bytes into the middle of a box -->

```python
from algopy import ARC4Contract, Box, Bytes, UInt64, arc4


class Blob(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"data")

    @arc4.abimethod
    def insert(self, at: UInt64, value: Bytes) -> UInt64:
        # splice does not resize: the tail is truncated to hold the size.
        self.data.splice(at, UInt64(0), value)
        return self.data.length
```

*Predict: a box holds the eight bytes `AABBCCDD` (four two-byte records). The contract calls `splice(2, 0, b"XX")` --- inserting two bytes at offset 2 and removing none. Write down the box's contents and its length afterwards.*

`splice(start, length, value)` removes `length` bytes at `start` and inserts `value` there, then forces the result back to the box's original size. Insert eight bytes without removing any, and eight bytes fall off the end. Remove eight without inserting, and eight zero bytes appear at the end. The name says list operation; the behavior is fixed-width. If you want the box to get bigger, `resize` it first and `splice` second.

::: {.gotcha #splice-does-not-resize topic="Box storage" title="Box.splice never changes a box's size"}
`splice(start, length, value)` looks like a list insertion and is not one: after removing and inserting, it forces the result back to the box's original size. Inserting eight bytes pushes eight bytes off the end; removing eight appends eight zero bytes. `resize` is the only operation that changes a box's size, and it is also the only one that changes the minimum balance, so if you want an insertion that grows the box, `resize` first and `splice` second.
:::

**Example 5-21.** Appending to a list in one box

<!-- finder: append a fixed-size record to a growing box -->

```python
from algopy import ARC4Contract, Box, Bytes, Global, GlobalState, Txn, UInt64, arc4

ENTRY = 32
MAX_ENTRIES = 64


class Log(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"log")
        self.count = GlobalState(UInt64(0))

    @arc4.abimethod
    def start(self) -> bool:
        assert Txn.sender == Global.creator_address, "creator only"
        return self.data.create(size=UInt64(0))

    @arc4.abimethod
    def append(self, entry: arc4.Address) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        index = self.count.value
        assert index < UInt64(MAX_ENTRIES), "log is full"
        self.data.resize((index + UInt64(1)) * UInt64(ENTRY))
        self.data.replace(index * UInt64(ENTRY), entry.bytes)
        self.count.value = index + UInt64(1)
        return index
```

This is the broken guestbook's design, done correctly. The pair that does it is `resize` followed by `replace`: grow the box by exactly one entry, then write the new entry at its offset. The count lives in global state rather than being derived from `.length`, which costs nothing and reads better.

What that buys is smaller than it looks. The box never reaches the stack, so the 4,096-byte wall is gone and the design keeps working up to the box's real 32,768-byte ceiling. The opcode cost per append is constant instead of growing with the data. Both are real wins over the broken version.

What it does **not** buy is I/O. `resize` charges the box's whole new size against the write budget, so appending to a 4,000-byte box costs 4,000, exactly what writing `.value` would have cost. Entries are 32 bytes, so on a single reference the sixty-fifth append is the one that fails: 32 × 65 is 2,080, and 2,080 > 2,048. That is where `MAX_ENTRIES = 64` in the example comes from: the write budget divided by the entry size, written down as an assertion so the log fills up with a sentence instead of a budget error. A design with a ceiling should say what its ceiling is; this one can, because the ceiling is arithmetic. Sixty-four entries, from a design whose selling point was that it never re-reads what it already stored. The MBR also still grows by 400 microAlgos per byte on every append.

So `resize` plus `replace` is the right way to maintain a list in one box, and it does not make a list in one box a good idea for unbounded data. This design tops out at 1,024 entries even with every reference you can buy, and much sooner than that with the references you will actually send. Whether that is enough depends on whether your data has a natural ceiling. A day's audit log does. An attendee list does not, which is why the guestbook's correction is one box per signature rather than this.

**Example 5-22.** Reading a page of a BoxMap

<!-- finder: iterate over box entries without running out of budget -->

```python
from algopy import ARC4Contract, BoxMap, UInt64, arc4, urange

PAGE = 8  # one box reference per entry, and a group carries a fixed few


class Log(ARC4Contract):
    def __init__(self) -> None:
        self.entry = BoxMap(UInt64, arc4.Address, key_prefix=b"e")

    @arc4.abimethod(readonly=True)
    def page(self, start: UInt64) -> arc4.DynamicArray[arc4.Address]:
        out = arc4.DynamicArray[arc4.Address]()
        for index in urange(start, start + UInt64(PAGE)):
            found, exists = self.entry.maybe(index)
            if exists:
                out.append(found)
        return out
```

The key line is `for index in urange(start, start + UInt64(PAGE))`. The loop's length is a constant the contract chose, not a function of how much data exists, so the call's cost is knowable before it is sent. `PAGE` is eight because eight is what the legacy foreign arrays hold, and a method that reads more boxes than the transaction can declare fails regardless of how much budget it has. On the v41 `Access` path a page of sixteen is available; eight is the number that works on both, which is why the example uses it. `.maybe()` rather than `[]` lets the page run past the end of the data without failing.

Now the version that does not do that, which compiles perfectly:

**Example 5-23.** A scan with no ceiling

<!-- finder: recognize an unbounded loop over box data -->

```python
from algopy import ARC4Contract, BoxMap, UInt64, arc4


class Log(ARC4Contract):
    def __init__(self) -> None:
        self.entry = BoxMap(UInt64, arc4.Address, key_prefix=b"e")

    @arc4.abimethod(readonly=True)
    def all_entries(self, count: UInt64) -> arc4.DynamicArray[arc4.Address]:
        out = arc4.DynamicArray[arc4.Address]()
        index = UInt64(0)
        while index < count:
            out.append(self.entry[index])
            index += UInt64(1)
        return out
```

Nothing here is a type error. The compiler has no opinion about `count`, because `count` is a runtime value; it will happily emit a loop that runs four billion times. What stops it is the reference cap: a `BoxMap` scan needs a reference per box, so the ninth entry has nowhere to be declared. The opcode budget would stop it soon after. Neither is a compiler message; both are a failed transaction.

It generalises beyond boxes, because the shape is the same every time: **a loop bounded by a runtime value has a ceiling you did not choose and cannot see.** The fix is never "make the loop faster." It is to bound the loop by a constant and let the caller ask again, which moves the iteration off-chain, where it is free, and leaves the contract with a cost it can prove.

::: {.gotcha #unbounded-box-scan topic="Resource references, MBR, and budget" title="A loop bounded by a runtime value has a ceiling you did not choose"}
`while index < count` over box entries compiles cleanly, because `count` is a runtime value and the compiler has no opinion about it. What stops it is the box-reference cap or the 700-unit opcode budget --- in practice the cap first, since eight legacy references (sixteen on the v41 `Access` list) is a far lower ceiling --- and either arrives as a failed transaction in production, not a build-time error. Marking the method `readonly=True` buys a delay and not a reprieve: the tooling simulates it with a 320,000-unit opcode budget, so the loop that dies on chain at entry 30 may run to entry 8,000 in your tests and then die anyway. Bound the loop by a constant the contract chose and let the caller page.
:::

In the guestbook, the unbounded scan is `has_signed`. There is no budget you can buy that makes it safe, so the corrected contract does not scan at all. It exposes an indexed read and a count, and lets the client do the walking.

The array types a box value can be --- and the `.copy()` rule that comes with them --- are an IOU this chapter leaves unpaid on purpose; Chapter 9 redeems it beside the vesting contract's claim method, where the compiler first makes the choice load-bearing.

## Building It Again, One Box Per Signature
Three decisions, three corrections. The full corrected contract compiles in CI as `examples/boxes/guestbook_fixed.py`; here is the spine of the diff, with bodies and decorators elided, and then the whole contract.

```diff
-        self.entries = Box(Bytes, key=b"entries")
+        self.signed = GlobalState(UInt64(0))
+        self.entry = BoxMap(UInt64, Entry, key_prefix=b"e")
     def sign(self) -> UInt64:
-        self.entries.value = self.entries.get(default=Bytes()) + record
-        return self.entries.length // UInt64(ENTRY)
+        cost = UInt64(BOX_FLAT) + UInt64(BOX_BYTE) * (name_len + size_of(Entry))
+        assert app.balance >= app.min_balance + cost, "app account underfunded"
+        self.entry[index] = Entry(who=..., signed_round=...)
+        return index
-    def has_signed(self, who: Account) -> bool:
-        while offset < blob.length:  # no ceiling in it
-        return False
+    def entry_at(self, index: UInt64) -> Entry:
+    def count(self) -> UInt64:
```

The diff is the shape of the fix. Example 5-24 is the contract itself, and the parts the diff elides are load-bearing: the import line changes in both directions, `ENTRY = 40` gives way to the two halves of the pricing formula, and the forty bytes become a struct.

**Example 5-24.** The guestbook, corrected

<!-- example: examples/boxes/guestbook_fixed.py mode=compile -->
<!-- finder: see the guestbook with all three defects fixed -->

```python
from algopy import (
    ARC4Contract, BoxMap, Global, GlobalState, Txn, UInt64, arc4, size_of,
)

BOX_FLAT = 2_500
BOX_BYTE = 400


class Entry(arc4.Struct):
    who: arc4.Address
    signed_round: arc4.UInt64


class Guestbook(ARC4Contract):
    """A conference guestbook. The desk checks names off, not the chain.

    The three corrections over the first draft: one box per signature
    instead of one growing blob; the write is priced from the declarations
    and refused in a sentence when the account cannot cover it; and nothing
    iterates on chain --- the client walks `count()` and `entry_at()`.
    """

    def __init__(self) -> None:
        self.organizer = GlobalState(Global.creator_address)
        self.signed = GlobalState(UInt64(0))
        self.entry = BoxMap(UInt64, Entry, key_prefix=b"e")

    @arc4.abimethod
    def sign(self) -> UInt64:
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

    @arc4.abimethod(readonly=True)
    def entry_at(self, index: UInt64) -> Entry:
        return self.entry[index]

    @arc4.abimethod(readonly=True)
    def count(self) -> UInt64:
        return self.signed.value

    @arc4.abimethod
    def retire(self, index: UInt64) -> None:
        assert Txn.sender == self.organizer.value, "organizer only"
        assert index in self.entry, "no such entry"
        del self.entry[index]
```

Two of the broken version's methods appear nowhere in it. `all_entries`, which returned the whole blob, is gone along with `has_signed`; the organizer's `clear`, which deleted the single box, has no counterpart, because there is no longer one box to clear. In their places: `entry_at`, `count`, and a new `retire`, each taken up below.

Deploy the fixed contract, fund it with the same one Algo, and sign it forty-one times:

```python
>>> guestbook.send.sign().abi_return
39
>>> guestbook.send.sign().abi_return
LogicError: Txn 5KDA...92QP had error 'Runtime error when executing Guestbook
(appId: 1103) in transaction 0: app account underfunded'
at PC 120 and Source Line 70:
    ... 10 lines of TEAL trace ...
```

The AVM did not write any of that sentence. It emits `assert failed pc=120` and nothing more; the rest is the client reassembling the message from the app spec it already holds, by the mechanism Chapter 2 laid out, which is why a caller without your app spec gets `assert failed pc=120` and no explanation. It is also why the two halves of that line disagree about which transaction they mean: the header's `Txn 5KDA...92QP` is the real one, while the reassembled sentence says `in transaction 0`, naming the *group index* instead. The client fills that slot by searching the message for the first `transaction ` it can find, and by the time it looks, the group has already been through a simulate whose own wrapper begins `in transaction 0:`. Two layers wrote to one sentence and neither knew about the other. Write assert messages for the operator holding the client, not for the chain.

The fixed guestbook stops *sooner*, at the forty-first signature rather than the fifty-sixth, and that is the correction working, not failing. The broken contract got further on the same Algo because a shared blob is cheaper per entry, and it got there by accumulating three walls it could not see. One Algo genuinely does not pay for more than forty boxes, and no code can conjure a minimum balance. What changed is that the contract now says so, in a sentence an organizer at a check-in desk can act on, and says it before writing anything rather than after.

**Correction one: one box per signature.** `self.entries` became `self.entry`, a `BoxMap[UInt64, Entry]` keyed by an index the contract maintains in global state. Signing creates a box instead of rewriting one, and that changes both currencies at once.

Table 5-5 prices the next signature both ways, in both currencies, with *n* signatures already stored. Everything the correction did is in its four rows.

: Table 5-5. One shared box against one box per signature, with *n* signatures already stored

| What is charged | Broken: one shared box | Fixed: one box per signature |
|----------------|------------------------------|------------------------------|
| **Read budget** | 40*n* (the whole blob) | 0 (the box does not exist yet) |
| **Write budget** | 40(*n*+1) (the whole new blob) | 40 (the one box written) |
| **Minimum balance** | 400 × 40 = **16,000** per signature | 2,500 + 400 × (9 + 40) = **22,100** |
| **First budget wall** | 52nd signature, on one reference | none; the MBR guard binds first, at the 41st |

The top two rows are one fact: the broken version's cost per signature was the *whole history*, charged twice over, and the fixed version's is one record. That is why the fifty-second-signature wall is gone, along with the four hundred and tenth it became once algokit's padding was spending eight references at a time, the 103rd-signature `concat` limit, and the 820th-signature ceiling the box's own maximum size imposed.

The third row is the bill for it: every signature is 6,100 microAlgos dearer, about 38% more, because the 2,500-microAlgo per-box constant and the nine bytes of name are now paid once per entry instead of once for all of them.

Those two currencies are the whole trade, and the shapes matter more than the numbers. The MBR went up by a *constant*; the I/O budget went from a *curve* to a constant. A constant you can pay by funding the account once. A curve you cannot pay at all: it eventually exceeds any allowance, and the only question is which signature discovers that. Trading a higher constant for a flat curve is the trade you almost always want.

Example 5-21 is the design that keeps one growing box on purpose, and it is the cheaper one up to sixty-four entries (flat MBR per entry, no 2,500 to spare), but it cannot escape the middle row of that table. `resize` charges the box's whole new size, so at 32 bytes an entry the sixty-fifth append dies on a single reference. `BoxMap` is the one with no such number in it.

That is the choice Figure 5-1 was drawing all along. The guestbook's data is per-signature, unbounded, and owned by the contract, and following those three answers down the tree lands on boxes every time.

**Correction two: price the write before making it.** This is the defect that was a line that was not there: nothing in the broken `sign` to point at, because the missing thing was the guard. `sign` computes the box's minimum-balance cost from the map's own prefix and the record's own size, and asserts the application account can cover it. Nothing in that assertion is a magic number transcribed from a wiki: `self.entry.key_prefix.length` and `size_of(Entry)` both read from declarations at the top of the listing, so adding a field to `Entry` updates the check automatically.

Two things it still does not do.

The first is that it does not make the *signer* pay. The organizer funds the application account, and every attendee spends the organizer's Algo. Having the caller cover the box they create requires a payment transaction grouped with the app call, so that the contract can inspect the payment and refuse to write the box unless the exact MBR arrived with it. Chapter 9 does precisely that on its first contract method, and Chapter 23 generalizes it. For now the check is honest about a cost it cannot shift.

The second is that it does not enforce one signature per attendee, and neither did the broken version: `has_signed` was a question the contract answered for other people, never one `sign` asked itself. Nothing stops one address from calling `sign` a thousand times, and with the organizer paying 22,100 microAlgos a call, that is a way to spend somebody else's Algo at the cost of a fee. The guard makes it fail politely rather than corrupt anything, which is the difference between a bad afternoon and a lost guestbook, but it does not stop it happening. The fix is a one-line change of shape: key the map by `Txn.sender` instead of a counter, and the ledger enforces the rule by construction, because an account cannot have two boxes with the same name. That costs the indexed reads `entry_at` gives you, which is why this version does not do it; but if you are building the real thing and the rule is "once per attendee," let the key say so.

**Correction three: stop iterating on chain.** `has_signed` and `all_entries` are gone, replaced by `entry_at(index)` and `count()`. That is not a reduction in capability. The check-in desk still gets its answer, by calling `count()` once and `entry_at` as many times as it needs, from a client with no opcode budget and no reference cap. What moved is not the work but where the work happens, and a contract that exposes an indexed read has a knowable cost per call, which is the only kind of cost you can build a conference on.

There is also a `retire(index)` the broken version had no way to offer, because you cannot delete the middle of a blob. Deleting a box refunds its 22,100 microAlgos to the application account, the only mechanism in this chapter that makes the minimum balance go *down*. It is organizer-only, and the `assert Txn.sender == self.organizer.value` on its first line is not decoration: a `retire` anyone could call would let a stranger erase a signature and pocket nothing. That is the worst kind of bug, damage with no motive to explain it away. The line under it, `assert index in self.entry`, is quieter and no less deliberate. `del` on a `BoxMap` entry that does not exist is not an error, because the underlying `box_del` reports a `False` that PuyaPy discards, so without that check, retiring an index that was never signed would succeed silently, and an organizer would have no way to tell "removed" from "was never there."

`retire` changes what `count()` means. `self.signed` counts signatures ever taken, not boxes currently present, so once anything is retired `count()` is a high-water mark and `entry_at` on a retired index fails rather than returning an empty entry. That is deliberate: reusing indices would make a signature's index meaningless, and an index that means something is worth more than a count that is exact. The client walks `0..count()` and tolerates gaps.

That settles the commission from the top of the chapter, item by item:

1. Record any attendee's signature and hand back a number that keeps naming it --- yes: `sign` returns the index it wrote, and the high-water-mark decision above is that number staying meaningful after retirements.
2. Answer the desk's question at a per-call cost that does not grow with the crowd --- yes, by refusing to answer it on chain: `count` and `entry_at` each cost the same at four hundred signatures as at four, and the walk moved to the client, where there is no budget to exhaust.
3. Take as many signatures as the conference can draw --- yes: one box per signature has no curve in it, and the only ceiling left is funding, which is the organizer's dial rather than the design's.
4. Refuse a write the account cannot afford, in a sentence --- yes: `app account underfunded`, at the forty-first signature on one Algo, before anything was half-written.
5. Let the organizer, and only the organizer, remove an entry and reclaim its cost --- yes: `retire` sits behind a sender check precisely because deleting a box moves 22,100 microAlgos of real money.

Five for five, and every number in the list was arithmetic before it was a transcript.

The chapter's one transferable rule: **a box is charged at its whole size, in both currencies, no matter how few of its bytes you touch.** Against the **I/O budget** it is charged twice, and the two charges are never added: once at its current size the moment the transaction references it, before your first opcode runs, and again at its new size when the program writes to it. Against **minimum balance** it is charged for the size it currently is, for as long as it exists, which is why that charge moves only when the size does. The rule says nothing about the third currency this chapter opened with, the opcode budget, because that is the one place where touching fewer bytes genuinely is cheaper: reading a box through `.value` costs opcodes in proportion to its size, while `extract` and `replace` cost the same however large the box is. That exception, and the 4,096-byte stack limit, are the whole reason those two operations exist; neither of them makes either of the other two charges smaller.

## Retrieval
Answer these from memory before moving on. Three reach back into earlier chapters.

1. What does a box cost in minimum balance, and which account is charged?
2. How many bytes of I/O budget does one box reference grant, and what are the *two* separate budgets that allowance is checked against? Which one is charged before your program runs?
3. State the chapter's transferable rule in one sentence.
4. What must a transaction declare before a contract may touch a box, and what happens if it does not?
5. Name the only operation that changes a box's size, and the one that looks like it does and does not.
6. The broken guestbook's write-budget wall is at the fifty-second signature, but the conference organizer never saw a budget error. What was paying for it, and name two ways of assembling the same call that stop paying.
7. *(From Chapter 4)* Which storage tier can a user delete without your contract's consent, and what does that imply about where a liability may live?
8. *(From Chapter 2)* Minimum balance is locked rather than spent. What happens to the locked Algo when a box is deleted?
9. *(From Chapter 3)* A method marked `readonly=True` is simulated rather than submitted. Does that exempt it from the opcode budget on chain?

## Exercises
1. The broken guestbook is deployed and its application account is funded with exactly 1.5 Algo. Every call is sent with exactly one box reference, with no padding. The single box is named `b"entries"` and each signature appends 40 bytes. The first wall is the **write budget, at the 52nd signature**: `box_put` charges the box's whole new size, and 40 × 52 = 2,080, which is over the 2,048 one reference grants. That one is worked for you; find the other three, in the order they would arrive if each previous one were somehow removed.

   a. **(Trace)** Work out the minimum-balance wall, remembering that the figure needs the application account's own 100,000 base and the box's 7-byte name, not just 400 a byte.

   b. **(Trace)** Work out the wall at the 4,096-byte limit on a value the AVM will put on the stack.

   c. **(Trace)** Work out the wall at the box's own maximum size.

   d. **(Compare)** Two of the four walls move if the *caller* assembles the transaction differently, and two do not. Say which are which, and what that tells you about where a wall really lives.

2. Below are six statements. Four of them form the body of a `withdraw` method that decrements a balance stored in a `BoxMap[Account, UInt64]` named `self.balance`; two do not belong in it at all. The decorator and signature are given.

   ```python
   @arc4.abimethod
   def withdraw(self, amount: UInt64) -> UInt64:
       ...
   ```

   The statements: (a) `current = self.balance.get(Txn.sender, default=UInt64(0))`; (b) `assert current >= amount, "insufficient balance"`; (c) `self.balance[Txn.sender] = current - amount`; (d) `return current - amount`; (e) `current = self.balance[Txn.sender]`; (f) `assert self.balance.box(Txn.sender).length == 8, "no balance box"`.

   Both rejects fail on the same call --- a first-time caller who has never deposited --- and they fail *differently*, which is why only one of them would survive a code review.

   a. **(Parsons)** Select the four that belong and order them.

   b. **(Debug)** For each reject, say exactly what that first-time caller sees.

   c. **(Debug)** Say which of the two a reviewer would wave through, and why: one of them wears the costume of a safety check, and it costs nothing in I/O budget to wear it, because the box's full size was charged the moment the transaction referenced it and `.length` adds nothing on top.

   d. **(Debug)** Say what that check silently converts a well-defined behaviour into, and why "it's just a safety check" is the wrong defence for a line that changes what the method means.

   e. **(Compare)** Say what the method should do when `current - amount` is zero, and what that decision costs.

3. A contract stores a 5,000-byte configuration blob in a single box and exposes `update_field(index, value)`, which reads `self.config.value`, splices eight bytes in at `index * 8`, and writes the whole thing back. Unit tests pass, and the premise matters: `algopy_testing` emulates box *contents* faithfully and does not enforce the AVM's I/O budgets or its stack limits at all, so a passing unit test says nothing about either. Called on LocalNet through a default algokit-utils client, it fails.

   a. **(Trace)** Before working through anything else, write down which of the two limits you expect to fail and what its message will be arithmetic *about*: a box, or a value.

   b. **(Debug)** Say which of the two limits it hits, and which it does *not* hit even though the naive arithmetic says it should.

   c. **(Debug)** Say why not: what did the client do on your behalf, and what is the number that ran out anyway?

   d. **(Debug)** Give the fix, and say honestly which of the two limits it removes and which one it does not, because it is only one of them.

4. You need to store one 64-byte record per user, the user count is unbounded, and the records are read one at a time by the user they belong to. The record is a **liability**: it is the contract's own accounting of what it owes that user, and if it disappears the contract's books are wrong in the user's favour. Keep that in view, because it decides one of the three designs on its own. The three: (i) a `BoxMap[Account, Record]`; (ii) one large box holding records at computed offsets, accessed with `extract` and `replace`; (iii) local state, packed into a single byte slot.

   a. **(Compare)** Compare all three on four axes: MBR cost per user, who pays it, I/O budget per read, and what happens when a user stops using the contract.

   b. **(Compare)** One of the three is disqualified by a hard ceiling; name it, give the number, and say where the number comes from.

   c. **(Compare)** A second is disqualified by the liability requirement, for a reason that has nothing to do with any ceiling; name it and say what the reason is.

   d. **(Compare)** For the design left standing, say what it costs per user and who pays that cost.

   e. **(Compare)** Say what single change to the requirements would make one of the two disqualified designs the right answer after all.

5. Extend the fixed guestbook so that the *signer* pays for their own box rather than the organizer. You will hit a problem the chapter has not solved: making the signer pay requires a payment transaction grouped with the application call, and reading a grouped transaction from inside a contract is not covered here.

   a. **(Extend)** Write the method with the payment check left as a comment.

   b. **(Extend)** Write down precisely what you need to know to fill it in, including what the contract must verify about that payment.

   c. **(Debug)** Say what goes wrong if the contract verifies only the amount.

## Before You Continue
You should be able to check off all five of these:

- [ ] Given a piece of data, I can walk the decision tree to global state, local state, or a box, and defend the answer.
- [ ] I can compute a box's minimum balance from its name and its contents, including the `BoxMap` prefix, and say which account is charged and when it is refunded.
- [ ] I can count the box references an app call needs by working out its read budget and its write budget separately, and say what to do when one reference is not enough.
- [ ] I can name the three places in this chapter where a limit is quietly paid for by tooling rather than by my contract, and say what happens the first time something else assembles the call.
- [ ] I can say why `extract` and `replace` exist (to reach into a box the AVM cannot put on the stack), name the only operation that changes a box's size and what `splice` does instead, and restructure a loop bounded by a runtime value into one with a ceiling I chose.

## Handoff: The Boxes the Vesting Project Writes
Chapter 9 builds a real token vesting contract, and it stores every beneficiary's schedule in a box on the first page. Table 5-6 lists the examples from this chapter that it leans on, and what to predict before you read it.

: Table 5-6. Examples from this chapter that the vesting project depends on

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| Example 5-6 | One schedule box per beneficiary, keyed by address | Why can a vesting schedule not live in the beneficiary's local state? |
| Example 5-8 | Funding the application account before the first schedule is created | A 32-byte address key, a 2-byte prefix, and a 41-byte record. What does one schedule cost? |
| Example 5-5 | The guard that refuses to create a schedule the contract cannot afford | What does the signer see if the guard is missing? |
| Example 5-11 | Every client call that touches a schedule box | The method takes the beneficiary as an argument. Does that alone make the box available? |
| Example 5-22 | Why the project has no "list all schedules" method | How many schedules could such a method return before it failed, and would that number be stable? |
| Exercise 5 | The grouped payment that makes the beneficiary fund their own schedule box | You wrote down what the contract must verify about that payment. Which of your checks does the project actually make? |
