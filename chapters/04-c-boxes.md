\newpage

# Data That Grows: Box Storage

The last chapter ended on a ceiling. A registry that moved its liabilities into the global slab became correct and, in the same stroke, became a contract with room for sixteen creditors. That is fine for a roster you control and useless for anything that hopes to get popular. Boxes are the tier that removes the ceiling: a box is an independently created, independently funded key that belongs to the application and to nobody else, and a contract can have as many of them as it can pay for.

The price of removing that ceiling is that you now pay per byte, on a schedule, in three different currencies --- minimum balance, I/O budget, and opcode budget --- and none of the three is checked by the compiler. This chapter is mostly about learning to see those three numbers before the chain shows them to you.

## The Problem
Here is a failure with a name: **the guestbook that stopped taking signatures at fifty-six.**

A conference wants an on-chain guestbook. Attendees sign it once; the contract records who signed and in which round; anybody can ask whether a given account has signed. It is about as simple as a stateful contract gets, and the obvious implementation writes every signature into one box, one after another, forty bytes each --- a 32-byte address followed by an 8-byte round number.

It works. It works on LocalNet, it works on TestNet with the eleven people who tried it, and it works on the day of the conference for fifty-five attendees. The fifty-sixth signature fails, and the error says the application account's balance would fall below its minimum. It does not mention boxes. Nobody on site connects the two, because nobody created a box --- the box was created weeks ago and has been quietly getting more expensive ever since.

Somebody tops the account up. Now the signatures go through again, for a while, and then a different failure starts: `has_signed` --- the read-only method the check-in desk calls before letting somebody sign twice --- begins rejecting. Not returning `False`. Rejecting, with an opcode-budget error, on a method that touches no funds and changes nothing.

Nothing in that story is a bug in anyone's code. Every line does exactly what it says. What is wrong is a belief carried over from every other language the author has written: that appending to a list costs about the same each time. On the AVM it does not, and the rest of this chapter is about what it costs instead.

## What You'll Be Able to Do
By the end of this chapter you will be able to:

- Choose between global state, local state, and box storage for a given piece of data, and defend the choice by naming what it costs and who pays
- Compute a box's minimum balance requirement before you write the box, and say which account is charged
- Predict whether a given app call has enough box I/O budget to do what it is about to do, and say what to change when it does not
- Read and write a box as raw bytes at a known offset, name the two things that buys which a typed read cannot, and grow a box safely --- including the one operation that looks like it grows a box and does not
- Choose an array type for a value you are about to store, and say whether assigning it copies or aliases
- Recognize an unbounded loop over box data on sight, and replace it with something that has a ceiling you chose
- Name the three places a limit in this chapter is quietly paid for by tooling rather than by your contract, and say what happens the first time something else assembles the call

{{fig:storage-decision-tree}} is the picture the rest of the chapter fills in --- and the picture {{ch:state}} could not draw yet, because its third branch did not exist. Read it before you read any code, in the order the branches are asked: the first question is the one you can least afford to answer wrong.

{{include-fig:storage-decision-tree}}

The tree's first two branches are {{ch:state}}'s material, and you can answer them already. Its third is this chapter: everything below follows from what a box costs to hold and what it costs to reach.

## The Mini-Build, Broken
Example: The guestbook, as first written {#ex:guestbook-broken}

<!-- finder: see a contract that appends records into a single box -->

{{include-ex:guestbook-broken}}

{{ex:guestbook-broken}} is complete and deployable. It compiles, it runs on LocalNet, and it contains three decisions that are wrong. Two of them are lines you can point at. The third is a line that is not there, which is the harder kind to find and the more common kind to ship.

*Predict: three decisions in that contract are wrong. Write your three down now, in whatever words you have --- you are not expected to be right yet. Check them against the diff at the end of the chapter.*

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
AlgodHTTPError: TransactionPool.Remember: transaction FQ7X...4KJA:
account 4WEK...5ZDQ balance 1000000 below min 1001300 (0 assets)
```

Read that error twice before reading on. Notice first what it is not: it is not a `LogicError`. No assertion failed, and no line of the program rejected anything. The program ran to completion and *then* the node refused to keep the transaction, because applying its effects would have left an account invalid. That is why the message is arithmetic about an account rather than a sentence about your contract.

Notice second whose account it is. `4WEK...5ZDQ` is the application's own address, not the signer's. And notice third that the word *box* does not appear anywhere in it, even though a box is the only reason the number moved. The transaction that failed did not create a box --- it appended forty bytes to a box that has existed since the first signature.

So: **growing a box raises the application account's minimum balance, and it raises it at the moment of the write.**

The number is exactly derivable, which is the point. The box is named `b"entries"`, seven bytes, and holds forty bytes per signature, so at *n* signatures it costs

$$2{,}500 + 400 \times (7 + 40n)$$

microAlgos of minimum balance, on top of the application account's own 100,000-microAlgo base. At *n* = 55 that totals 985,300 and the account has 1,000,000. At *n* = 56 it totals 1,001,300, and the account is 1,300 microAlgos short. Every signature costs 16,000 microAlgos --- 400 per byte, forty bytes --- and the deployment script funded for none of them.

{{fig:mbr-rising-floor}} is that arithmetic as a picture. The balance is a flat line, because nobody sent the contract any more money. The floor is a staircase, because every signature raises it by the same 16,000, and the contract kept working right up until the two lines crossed between the fifty-fifth step and the fifty-sixth.

{{include-fig:mbr-rising-floor}}

Top the account up and the guestbook works again --- for another forty-odd signatures, and then it stops a second time, on a different error entirely:

```python
>>> guestbook.send.sign().abi_return
102
>>> guestbook.send.sign().abi_return
LogicError: Txn RQ2M...H7VA had error 'concat produced a too big
(4120) byte-array' at PC 214 and Source Line 19:
    ... 12 lines of TEAL trace ...
```

Every `LogicError` in this book is printed that way and then trimmed to its
`.message` in the prose --- the transaction ID, the program counter, and the
trace are real, and they are noise for everything this chapter is about.

That one has nothing to do with money, and topping up will not touch it. `sign` reads the whole blob into a value, concatenates forty bytes onto it, and writes the value back. A value on the AVM stack cannot exceed 4,096 bytes, and 4,120 is what 103 forty-byte records come to. The box itself is allowed to reach 32,768 bytes; the program is not allowed to *hold* more than 4,096 of them at once. The one-box design hit a limit on the value, not on the storage. (The broken `sign` returns the count *after* writing, so the call that answered `102` was the hundred and second signature and the failing one is the hundred and third. The corrected version returns the index it just wrote instead, which is why its transcript later in the chapter counts from zero.)

*Predict: you have now seen two walls, at the fifty-sixth signature and the hundred and third. One of them can be pushed further out by sending the contract more money. The other cannot be pushed out by anything you put in the transaction --- and there is a third wall you have not seen, which was pushed out for you by something nobody wrote down. Which is which, and why?*

There is a third defect, and it has not failed yet, which is what makes it the dangerous one. `has_signed` --- the read-only method the check-in desk calls before letting somebody sign twice --- scans the whole blob in a `while` loop with no ceiling in it. Call it from a client and it keeps working: algokit-utils runs `readonly` methods through simulation, and it asks simulation for **320,000 opcode units** rather than the 700 an application call gets on chain ({{ch:mental-model}} priced that 700). So the method a reader would swear is free is being carried by a budget more than four hundred times larger than the real one.

The bill arrives the first time anything submits that method for real, or the first time another contract calls it. `readonly` is a delay, not a reprieve. And because the loop's cost per entry moves whenever you edit the loop body, the number of signatures it survives is not a fact about the contract you can look up --- it is a measurement that goes stale.

Three decisions caused all of this. The six sections that follow take box storage apart, and each one ends by naming what it repairs in the guestbook --- or, once, by admitting it repairs nothing. By the end you will be able to state all three in a sentence each.

## One Box, and What It Costs
A box is a named byte string owned by the application. It is created by the contract, it is deleted by the contract, and no user can touch it --- which is exactly the property {{ch:state}} was reaching for when it moved the registry's liabilities out of local state. A box holds **0 to 32,768 bytes**, its name is **1 to 64 bytes**, and there is no limit on how many an application may have except what it can pay for.

Example: Declaring and reading a box {#ex:box-declare}

<!-- finder: store a single value in a box -->

{{include-ex:box-declare}}

The load-bearing line is `self.total = Box(UInt64, key=b"total")`. A `Box` is a *handle*, not a value: declaring one in `__init__` creates nothing and costs nothing. The box comes into existence on the first write, and that is the transaction that raises the minimum balance.

`.value`, `.get(default=...)`, and `.maybe()` behave exactly as they do on `GlobalState`, and for the same reason --- reading a box that does not exist fails the call rather than returning zero. Everything {{ch:state}} taught you about the difference between absent and zero applies here unchanged.

Example: Telling an absent box from an empty one {#ex:box-maybe}

<!-- finder: check whether a box exists without failing the call -->

{{include-ex:box-maybe}}

The load-bearing line is `value, exists = self.total.maybe()`. On a box the distinction is sharper than it is in global state, because a box can genuinely exist while holding zero bytes: `create(size=UInt64(0))` is legal and produces a box whose `.length` is `0` and whose `bool()` is `True`. Absent, empty, and zero are three different states here, not two.

Example: Creating and deleting a box explicitly {#ex:box-delete}

<!-- finder: create a box up front and delete it to reclaim the MBR -->

{{include-ex:box-delete}}

Two load-bearing lines. `self.total.create()` allocates the box without writing a value and returns `False` if it already existed --- so `assert self.total.create()` is how you say "this must be the first time." And `del self.total.value` deletes the box outright, which **refunds the entire minimum balance it was holding**. MBR is locked, not spent; delete the resource and the Algo becomes spendable again.

That refund is the reason `stop()` has a `Txn.sender` check on it. A method that deletes a box moves real money, even though no payment appears anywhere in it.

Example: What the application account can actually spend {#ex:app-mbr-floor}

<!-- finder: check the app account has enough balance before creating a box -->

{{include-ex:app-mbr-floor}}

The load-bearing line is `assert app.balance >= app.min_balance + cost`. Both fields are readable from inside the contract, on any account the transaction has made available --- and `Global.current_application_address` is always available to the application itself. The difference between them is the only balance that means anything: it is what the account can part with without becoming invalid.

Which makes it tempting to write the check the way you would say it out loud, as `assert app.balance - app.min_balance >= cost`. Do not. UInt64 subtraction on the AVM does not go negative; it fails the transaction. A contract that has been deployed but never funded has `balance = 0` against a `min_balance` of 100,000, so that subtraction is exactly the case that underflows, and the reader gets `- would result negative` instead of your message. **Write the guard as an addition on the right-hand side, and the underflow cannot happen.** `spendable()` in the same example makes the same move with an explicit zero case, for the same reason.

With that, `open_vault` computes what its box will cost before creating it, and refuses with a message that names the problem. Compare that to the error the broken guestbook produced. The chain's version of "you are underfunded" is arithmetic about an account; yours can be a sentence.

One piece of housekeeping about the rest of this chapter, said once here so it does not have to be said twenty times. The single-concept examples that follow --- the ones demonstrating `create`, `resize`, `replace`, `extract`, and the `BoxMap` machinery --- do not carry this guard. Each is stripped to the one operation it is teaching, and a four-line pre-flight in front of a three-line method would bury the line you are meant to be reading. That is a presentation choice, not a pattern: every one of them creates or grows a box, so every one of them needs the guard before it goes anywhere near a network you care about. This example is the form to copy, and the corrected guestbook at the end of the chapter is it in situ. Where an example has some *other* reason to omit something, it says so in a comment on the line.

*Predict: `open_vault`'s box is named `b"d"` and holds a single eight-byte number --- nine bytes of data in all. Guess what it costs to keep, in microAlgos, before you read the next line.*

The `cost` that guard is comparing against comes from one formula, and for a single box it is short enough to keep in your head:

$$2{,}500 + 400 \times (\text{name bytes} + \text{value bytes})$$

`open_vault`'s box is named `b"d"` and holds an eight-byte number, so it costs 2,500 + 400 × 9 = 6,100 microAlgos, which is the number the contract computes inline. Note that both terms are *bytes*, and that the name is one of them --- a fact that costs nothing here, where the name is a byte long and written in the source, and costs real money in the next section, where the names are generated.

{{tbl:box-costs}} is the whole pricing model. It is short, and it is worth memorizing for the same reason {{tbl:state-mbr}} in {{ch:state}} was: getting it wrong produces a funding bug in a script rather than an error in a compiler.

Table: What box storage costs, and who pays it {#tbl:box-costs}

| Cost | Amount | Charged to | Refunded when |
|------|--------|------------|---------------|
| Box exists at all | 2,500 microAlgos | the **application account** | the box is deleted |
| Each byte of name | 400 microAlgos | the **application account** | the box is deleted |
| Each byte of contents | 400 microAlgos | the **application account** | the box is deleted or shrunk |

Every row says *application account*, and that is the asymmetry worth holding against {{ch:state}}. Global and local schema MBR follows a **user** --- the creator for global, the opting-in account for local. Box MBR follows the **contract**. A deployment script that funds the creator generously and the application address not at all will deploy a contract that cannot store anything, and the error will be about a balance.

*What this section repairs in the guestbook:* the fifty-sixth signature. The contract never asked what the write would cost, so the chain answered with an account error instead. A pre-flight check turns an unexplained balance failure into a named one.

## Many Boxes, and What They're Named
One box per contract is rarely what you want. `BoxMap` gives you a keyed family of boxes --- one box per key, each independently created, each independently priced. It is also, as this section is mostly about, a naming scheme rather than a data structure, and every bug in it is a naming bug.

Example: A box per account {#ex:boxmap-declare}

<!-- finder: store one value per account in boxes -->

{{include-ex:boxmap-declare}}

The load-bearing line is `self.score = BoxMap(Account, UInt64)`. Compare it to {{ch:state}}'s `GlobalMap`, which has the same shape and a completely different bill: a `GlobalMap` entry consumes one of the application's 64 shared global slots, so the map has a hard ceiling and the creator pays. A `BoxMap` entry is its own box, so there is no ceiling and the application account pays. That is the whole trade, and it is the answer to the registry's sixteen-creditor problem.

Example: What a BoxMap actually names {#ex:boxmap-key-bytes}

<!-- finder: find out the real box name behind a BoxMap key -->

{{include-ex:boxmap-key-bytes}}

The load-bearing line is `self.score.box(who).key`. `BoxMap` is a naming convention, not a new storage primitive: `self.score[who]` reads the box named `key_prefix + encode(who)`, and nothing about it is special to the AVM. When `key_prefix` is not given it defaults to the member variable's own name --- here `b"score"`, five bytes of name on every single box, charged 400 microAlgos each. Naming the map `self.s` would be a 1,600-microAlgo saving per box and an unreadable contract; naming it explicitly with `key_prefix=b"s"` is both.

That saving is the single-box formula from the last section, applied to a name nobody wrote down. It is worth making the contract do that arithmetic rather than a deployment script.

Example: Pricing a box before you write it {#ex:box-mbr-math}

<!-- finder: compute the MBR cost of a box in the contract itself -->

{{include-ex:box-mbr-math}}

The load-bearing line is `name_len = self.record.key_prefix.length + UInt64(32)`, and the trap it defuses is in the first term inside the parentheses. **The box name is not the key you passed.** For a `BoxMap` it is the prefix followed by the encoded key, so a map with a one-byte prefix keyed by a 32-byte address has 33-byte names, and a funding calculation that counted 32 underfunds every box by 400 microAlgos. `size_of(Record)` supplies the other term at compile time for any fixed-size type, so the whole cost can be computed by the contract rather than transcribed into a deployment script and then quietly diverged from.

Example: Two maps that write the same box {#ex:boxmap-prefix-collision}

<!-- finder: understand why two BoxMaps can overwrite each other -->

{{include-ex:boxmap-prefix-collision}}

*Predict before you read on: one map has `key_prefix=b"a"` and is handed the key `b"bc"`. The other has `key_prefix=b"ab"` and is handed the key `b"c"`. Write down the box name each one ends up reading.*

Read that one slowly. `key_prefix=b"a"` with the key `b"bc"` names the box `b"abc"`. `key_prefix=b"ab"` with the key `b"c"` also names the box `b"abc"`. They are the same box. The second write overwrites the first, `collide()` returns `True`, and no part of the toolchain warned anybody --- because concatenation is all that happened, and concatenation does not know where you meant the seam to be.

This only bites when keys are variable-length, which in practice means `Bytes`, `String`, and dynamic array keys. Fixed-width keys --- `Account`, `UInt64`, a fixed-size struct --- cannot collide this way, because every name in the family is the same length. When your keys are variable-length, either give every map a prefix of the same length or include a separator that cannot appear in a key.

Example: A composite key {#ex:boxmap-composite-key}

<!-- finder: key a BoxMap by more than one value -->

{{include-ex:boxmap-composite-key}}

The load-bearing line is `self.score = BoxMap(Slot, UInt64, key_prefix=b"s")`, where `Slot` is an `arc4.Struct` of an address and a season. Notice where the season comes from: `Global.round // SEASON_ROUNDS`, computed by the contract, not taken as an argument. A caller who can choose a key field can choose an unbounded number of them, and every distinct key is a new box at the application's expense --- the composite key is exactly the shape that makes that mistake cheap to write and expensive to hold. Any fixed-size ARC-4 type can be a key, and the encoding is what gets concatenated, so a two-field key costs its two fields' worth of name --- here 1 + 32 + 8 = 41 bytes of name for 8 bytes of value, which is the arithmetic that makes wide keys expensive. It is also the reason a composite key is safe from the collision in the preceding section: every key in the family encodes to exactly 40 bytes.

*What this section repairs in the guestbook:* the shape of the storage. One box that every signature reads and rewrites is a cost that grows with the number of people who came before you. One box per signature, keyed by an index, is a cost that does not.

## What a Transaction Must Declare
Naming is settled. Reaching is a separate problem, and it is the one that fails in production, because it is the only rule in this chapter that is enforced by the transaction rather than by the program.

*A contract may only touch boxes the transaction declared in advance.* Every box a call will read or write has to be listed on the transaction before the program starts running. Nothing in the method signature does this for you: `score_of(who: Account)` names an account, and the account reference it implies is not the box reference the body needs. A box the transaction did not declare does not read as empty --- it fails the call with `invalid Box reference`.

This is a genuinely new rule, and it is worth being clear about how new. {{ch:state}}'s global and local state needed no declarations at all, because the schema was fixed at creation and the AVM already knew where to look. And it is not the resource rule you met in {{ex:reference-types}}, where passing an `Account` or an `Asset` as an argument made it available as a side effect of the signature. Boxes have no such side effect, because a box name is bytes the program computes, and the transaction is assembled before the program runs. The caps and the exact accounting are tabulated in full in {{ch:avm-limits}}; what matters here is what the declaration buys.

Example: Letting the client work out the references {#ex:box-refs-auto}

<!-- finder: avoid declaring box references by hand on every call -->

{{include-ex:box-refs-auto}}

The load-bearing line is `SendParams(populate_app_call_resources=True)`. algokit-utils simulates the call first, reads back the resources the simulation says it wanted, and puts them on the real transaction. This is on by default in algokit-utils 4.x, and it removes most of the tedium.

It is a convenience and not a guarantee, and the failure mode is worth knowing before you meet it: the simulation only discovers the boxes that *the path it took* touched. A method that reads a different box depending on an argument will populate correctly for the argument you simulated and incorrectly for the one you did not.

A box reference does two things. It makes the box *available*, and it grants **2,048 bytes of I/O budget** (consensus v41 raised this from 1,024). The second half is where the mistakes live, and they come from assuming the budget works like a bandwidth meter counting bytes as they move. It does not.

**The allowance is checked twice, as two separate budgets that are never added together, and each one charges a box's *whole size* rather than the bytes you touched.**

The *read* budget is charged **before the program runs at all**. The node adds up the full current size of every box the transaction referenced *that exists*, and if that total is over the allowance the call is dead before its first opcode --- whether or not the program was ever going to read a single one of those boxes. Reference a 3,000-byte box you had no intention of reading, on one reference, and the call fails with `read budget exceeded (3000 > 2048)`.

The *write* budget is charged as the program runs, once per box written, again at the box's full size --- and for `resize`, at its full *new* size. Overwriting one byte of a 3,000-byte box costs 3,000 against the write budget, not one. Deleting a box refunds only what the same group has already spent writing that box; deleting a box nobody in the group has written refunds nothing, because nothing was charged.

Two consequences follow, and both are counterintuitive enough to be worth stating flatly. The first is that a read-modify-write does *not* cost double: reading a 1,500-byte box and writing it back charges 1,500 against the read budget and 1,500 against the write budget, and since the two are never summed, that call fits comfortably on a single 2,048-byte reference. The second is that there is no such thing as touching a box cheaply. There is only referencing fewer boxes, or referencing the same ones more times.

{{tbl:box-ref-count}} works four calls through both budgets. Cover the last three columns and do them yourself before reading it; rows two through four are the ones that catch people.

Table: Four calls, and the references each one needs {#tbl:box-ref-count}

| What the call does | Read budget | Write budget | References |
|----------------------------------|----------|----------|--------|
| Reads and rewrites one 1,500-byte box | 1,500 | 1,500 | 1 |
| References one 3,000-byte box and never reads it | 3,000 | 0 | 2 |
| References two 1,200-byte boxes, writes one | 2,400 | 1,200 | 2 |
| Creates a box that does not exist yet, 40 bytes | 0 | 40 | 1 |

Row two is the read budget charging for a box the program ignores. Row three is both budgets summing across the boxes they cover --- the read side over every referenced box that exists, the write side over every box actually written --- so the *larger* of the two is what has to fit, and here that is the read side, inflated by a box the program only ever writes to. Row four is the mirror image: a box that does not exist yet is charged nothing on read, because there is nothing there to charge for.

Because there is no way to touch a box cheaply, the escape hatch is worth knowing precisely: *references do not have to name distinct boxes.* Declaring the same box twice grants it 4,096 bytes, three times 6,144, and so on. Both budgets pool across the entire transaction group, not just one call. And a single transaction uses either the legacy foreign arrays or the v41 `Access` list --- never both --- so the cap on references is **eight** combined foreign references on the legacy path, or **sixteen** of any resource type on the `Access` path. Sixteen of those entries spent on *box* references --- or on empty ones --- is 32,768 bytes, which is exactly a box's maximum size. That is not a coincidence; it is the ceiling being made reachable on purpose.

Which path a call takes is decided by whatever assembles the transaction, not by anything in your contract --- so unless you own every client that will ever call you, design against eight and treat sixteen as a ceiling rather than a floor. That is a real design constraint and not a footnote: a box large enough to need more than eight references is a box that only a caller you control can reach at all. Keep it in mind for the rest of this chapter, where several reference counts run well past eight.

Example: Working out how many references a call needs {#ex:box-io-budget}

<!-- finder: work out how many box references an app call needs -->

{{include-ex:box-io-budget}}

That script takes the two budgets separately and returns the larger requirement, which is the arithmetic the model actually demands. It also floors the answer at the number of boxes touched, because budget is not the only thing a reference buys: every box must be *named* by some reference whether or not the budget needed it, so a call touching five tiny boxes needs five references even though their combined size fits in one. Run the broken guestbook through it. Signing when *n* entries exist reads a box of 40*n* bytes and writes one of 40(*n*+1) --- so the write budget always binds first, and it binds at 40(*n*+1) > 2,048, which is the **fifty-second** signature on a single reference: `write budget exceeded (2080 > 2048) while writing box 0x...` --- the real message names the box in hex, which is worth knowing, because it is how you tell which box in a group blew the budget.

*Predict: that wall lands at the fifty-second signature and the minimum-balance wall lands at the fifty-sixth. The story at the start of this chapter says the organizer saw the balance error first. What could make the earlier wall arrive later than the later one?*

The answer is the tooling, and it is the most useful thing in this section. `populate_app_call_resources` does not just find the boxes a call needs --- it also reads back how much extra I/O budget the simulation wanted and pads the transaction with that many *empty* box references, up to the eight-reference cap. Empty and duplicate references both count toward the allowance, so a default client call is quietly buying as much budget as the simulation says it needs, up to 16,384 bytes rather than 2,048. That moves the write-budget wall from the fifty-second signature out to the four hundred and tenth, which is why the conference organizer met the minimum-balance error at the fifty-sixth and never saw a budget error at all.

Notice what that means for testing. *The budget failure was not absent from the broken contract; it was paid for by a client-side convenience, and it comes back the moment the call is assembled by something that does not pad* --- another contract, a hand-built transaction, a different SDK. Two of the three walls in this chapter are like this. The one that cannot be papered over by anything is the 4,096-byte limit on a value, because that limit is about what the program may hold in a register, and no number of references changes it.

Three conveniences hide limits in this chapter, and it is worth naming all three together, because a contract that passes every check you know how to run can still be sitting on all three at once. `populate_app_call_resources` pads the I/O budget, which is this section. `readonly=True` buys a method 320,000 opcode units under simulation instead of the 700 it gets on chain, which you already met carrying the broken guestbook's `has_signed`. And `algopy_testing` --- the framework {{ch:testing}} builds on --- emulates box *contents* faithfully and does not enforce the I/O budget or the 4,096-byte stack limit at all, so a green unit test is silent about both. None of the three is a defect; each is doing exactly what it was built to do. What they have in common is that they are all on the *caller's* side of the boundary, and the caller is the one thing your contract does not get to choose.

So the full ladder for the one-box guestbook, on a single reference, is: the **fifty-second** signature exceeds the write budget; the **fifty-sixth** exceeds the minimum balance; the **hundred and third** exceeds 4,096 bytes in `concat`; and the box's own 32,768-byte ceiling would arrive at the **eight hundred and twentieth** --- 819 entries fit in 32,760 bytes, and the 820th is the one that does not --- which the contract can never reach. Every one of those walls is invisible in the source, and the order they arrive in depends on how the transaction was assembled.

*What this section repairs in the guestbook:* the invisible walls. Once you can count references and sizes, the fifty-second and hundred and third signatures stop being surprises and become arithmetic you can do before deploying.

## Bytes, Not Values
Everything so far has treated a box as a typed value. Underneath it is a byte string, and the AVM has opcodes that read and write *ranges* of it without ever materializing the rest. Given what the last section established --- that a box is charged at its full size no matter how few bytes you touch --- it is fair to ask what those opcodes are for, if not for saving budget.

They are for reach. A typed read has to put the whole box on the stack, and **a value on the AVM stack cannot exceed 4,096 bytes**. Above that size, `.value` does not become expensive; it becomes impossible, and the range operations are the only way to get at the box at all. That is the wall the broken guestbook hit at its hundred and third signature, and this section is the equipment for living above it.

Example: A box sized up front {#ex:box-raw-sized}

<!-- finder: allocate a box of a fixed size and read part of it -->

{{include-ex:box-raw-sized}}

The load-bearing line is `self.data.create(size=size)`. For a `Box[Bytes]` --- a box with no fixed-size type behind it --- `create` **requires** a size, because there is nothing to infer one from. Neither assertion above it is decoration. The size check is there because 32,768 is a hard AVM limit, and a `create` past it fails with an error about the box rather than about your argument. The sender check is there because `size` is a caller's argument and the minimum balance it locks is the *application's* money: an unguarded `allocate` lets any stranger convert 13.1 Algo of the contract's balance into an unusable box for the price of one transaction fee, and, since `create` on an existing box of a different size fails outright, keep it that way forever. Any method whose argument sets a box's size belongs behind a caller check.

`create` is also stricter than it looks in one specific way. Called on a box that already exists **at the same size**, it does nothing and returns `False`. Called on a box that exists at a *different* size, it fails the call. It is not a resize.

Example: The Box behind a BoxMap entry {#ex:boxmap-box-handle}

<!-- finder: use raw box operations on one entry of a BoxMap -->

{{include-ex:boxmap-box-handle}}

The load-bearing line is `self.score.box(who)`, which hands you an ordinary `Box` for one entry. Everything in this section applies to `BoxMap` entries through that handle --- there is no second API to learn, because there was never a second primitive.

Example: Asking a box how big it is {#ex:box-length}

<!-- finder: get a box's size without reading its contents -->

{{include-ex:box-length}}

`.length` adds nothing to the *write* budget, because it writes nothing, and it works at any size because the number it returns never puts the box on the stack. What it does not do is dodge the read budget: that was charged before the program started, at the box's full size, purely because the transaction referenced it. A method whose only box operation is `.length` on a 30,000-byte box still needs fifteen references to run. The `assert self.data` above it is doing one thing the compiler's own check does not. PuyaPy already emits an existence check behind `.length`, so the call fails either way; the explicit assertion is what gives the failure a sentence instead of a bare `assert failed` at whatever line the compiler chose.

Example: Writing one slot of a packed box {#ex:box-replace}

<!-- finder: update part of a box without rewriting the whole thing -->

{{include-ex:box-replace}}

The load-bearing line is `self.data.replace(index * UInt64(SLOT), value.bytes)`. `replace` writes bytes at an offset and leaves the box's size alone; if the write would run past the end, the call fails.

Be precise about what it buys, because this is where the folklore is wrong. It does **not** reduce the write budget: the box is charged its full size the moment the program writes to it, by `replace` exactly as by `.value`. What it buys is two things the budget has nothing to do with. It works on boxes above 4,096 bytes, where the read-modify-write through `.value` cannot run at all. And its opcode cost is constant in the box's size rather than proportional to it, which is what keeps a method's 700 units from being consumed by copying bytes it did not care about.

Example: Reading one slot of a packed box {#ex:box-extract}

<!-- finder: read part of a box without reading the whole thing -->

{{include-ex:box-extract}}

`extract(start, length)` is `replace`'s twin and buys exactly the same two things for the same reason: it reaches into a box of any size, and its cost in opcodes does not grow with the box. The read budget was already charged in full before the program started, so `extract` is not saving it anything either.

`arc4.UInt64.from_bytes(raw)` then reinterprets the eight bytes as a number --- and *reinterprets* is the exact word. It checks nothing. Extract from the wrong offset and you get a perfectly valid number that means nothing.

*Predict: a box holds 20,000 bytes and a method reads eight of them with `extract`, changes nothing, and returns. How many box references does that call need? The answer is not one.*

Ten. The read budget was charged at the box's full 20,000 bytes before the program ran a single opcode, purely because the transaction named the box, and 20,000 over 2,048 rounds up to ten. The eight bytes you actually wanted had no say in it. If that feels like a lot to pay for eight bytes, it is --- and it is the reason the next figure prices packing against splitting.

MBR is the half of the trade that *packing* really does change, and {{fig:packed-box-layout}} prices it.

{{include-fig:packed-box-layout}}

The figure compares one struct in one box against the same struct split across three, and the split loses badly --- because the 2,500-microAlgo constant and the key bytes are charged once *per box*, so a 32-byte address in the name gets paid for three times. Splitting also costs references: three boxes need at least three, where one box needs one. Here packing wins on both, and offset access is what makes a packed box workable to read and write once it is large. You want both.

That may read as a reversal, because the ten references you just counted for a 20,000-byte box are exactly the argument *for* splitting: a call that needed only one piece could reference only that piece and pay for only that piece. Both readings are right, and they answer different questions. Splitting buys I/O budget when a call genuinely needs one piece and not the others; it costs minimum balance always, on every piece, for as long as the pieces exist. So the seam goes where the access pattern already puts it --- pack what is read together, split what is read apart --- and the figure's struct loses by splitting because all three of its pieces are always read at once.

Example: Sizing a box from its type {#ex:sized-types}

<!-- finder: create a box exactly the size of the struct it will hold -->

{{include-ex:sized-types}}

Two load-bearing calls, and together they are the canonical way to allocate a fixed-size record. `size_of(Record)` is the encoded size of any fixed-size type, computed at compile time --- 10 bytes here, for an 8-byte and a 2-byte field --- so the size never has to be written down twice and cannot drift when you add a field. `zero_bytes(Record)` produces a correctly-sized zero value of that type, which is how you initialize a record without constructing one field by field.

The two assertions wrapped around them are not part of the pattern but are part of shipping it. `create` returns `False` when the box already exists at that size, and letting that `False` fall on the floor is a compiler warning (`expression result is ignored`) and a silent overwrite of live data; asserting it turns `reset` into a method that can only run once. The sender check is there because the line below destroys a record, and a method that destroys data is as privileged as one that spends money.

*What this section repairs in the guestbook:* the hundred and third signature, and only that one. Rewriting `sign` to `resize` and `replace` instead of reading `.value` and concatenating would move the 4,096-byte wall out of the way entirely, because no version of the box would ever reach the stack. That design is {{ex:box-list-append}} in the next section, it is a real alternative to the correction this chapter actually makes, and the next section is where you find out which of the other walls it leaves standing.

## Changing a Box's Size
A box's size is fixed until something changes it, and exactly one operation changes it.

Example: Growing a box {#ex:box-resize}

<!-- finder: make an existing box bigger -->

{{include-ex:box-resize}}

`start` is here because `grow` cannot bootstrap itself: `.length` on a box that does not exist fails, so a `Blob` with only a `grow` method has no reachable first call. The load-bearing line is `self.data.resize(new_size)`. Growing zero-pads on the right; shrinking truncates on the right and **refunds the minimum balance for the bytes removed**. It is the only operation that changes a box's size, and every byte of the new size is charged at 400 microAlgos to the application account at the moment the call runs.

It is also charged against the write budget at its whole new size, which is the same rule as everything else in this chapter and easy to forget here because `resize` looks like it only touches the difference. Growing a box from 2,000 bytes to 2,100 charges 2,100 against the write budget, not 100.

Example: The operation that looks like it grows a box {#ex:box-splice}

<!-- finder: insert bytes into the middle of a box -->

{{include-ex:box-splice}}

*Predict: a box holds the eight bytes `AABBCCDD` (four two-byte records). The contract calls `splice(2, 0, b"XX")` --- inserting two bytes at offset 2 and removing none. Write down the box's contents and its length afterwards.*

`splice(start, length, value)` removes `length` bytes at `start` and inserts `value` there --- and then forces the result back to the box's original size. Insert eight bytes without removing any, and eight bytes fall off the end. Remove eight without inserting, and eight zero bytes appear at the end. The name says list operation; the behavior is fixed-width. If you want the box to get bigger, `resize` it first and `splice` second.

Example: Appending to a list in one box {#ex:box-list-append}

<!-- finder: append a fixed-size record to a growing box -->

{{include-ex:box-list-append}}

This is the broken guestbook's design, done correctly. The load-bearing pair is `resize` followed by `replace`: grow the box by exactly one entry, then write the new entry at its offset. The count lives in global state rather than being derived from `.length`, which costs nothing and reads better.

What that buys is precise, and it is smaller than it looks. The box never reaches the stack, so the 4,096-byte wall is gone and the design keeps working up to the box's real 32,768-byte ceiling. The opcode cost per append is constant instead of growing with the data. Both are real wins over the broken version.

What it does **not** buy is I/O. `resize` charges the box's whole new size against the write budget --- the same rule as everything else here --- so appending to a 4,000-byte box costs 4,000, exactly what writing `.value` would have cost. Entries are 32 bytes, so on a single reference the sixty-fifth append is the one that fails: 32 × 65 is 2,080, and 2,080 > 2,048. That is where `MAX_ENTRIES = 64` in the example comes from --- it is not a round number somebody liked, it is the write budget divided by the entry size, written down as an assertion so the log fills up with a sentence instead of a budget error. A design with a ceiling should say what its ceiling is; this one can, because the ceiling is arithmetic. Sixty-four entries, from a design whose whole selling point was that it never re-reads what it already stored. The MBR also still grows by 400 microAlgos per byte on every append.

So `resize` plus `replace` is the right way to maintain a list in one box, and it does not make a list in one box a good idea for unbounded data. This design tops out at 1,024 entries even with every reference you can buy, and much sooner than that with the references you will actually send. Whether that is enough depends on whether your data has a natural ceiling. A day's audit log does. An attendee list does not, which is why the guestbook's correction is one box per signature rather than this.

Example: Reading a page of a BoxMap {#ex:boxmap-scan-cost}

<!-- finder: iterate over box entries without running out of budget -->

{{include-ex:boxmap-scan-cost}}

The load-bearing line is `for index in urange(start, start + UInt64(PAGE))`. The loop's length is a constant the contract chose, not a function of how much data exists, so the call's cost is knowable before it is sent. `PAGE` is eight because eight is what the legacy foreign arrays hold, and a method that reads more boxes than the transaction can declare fails regardless of how much budget it has. On the v41 `Access` path a page of sixteen is available; eight is the number that works on both, which is why the example uses it. `.maybe()` rather than `[]` lets the page run past the end of the data without failing.

Now the version that does not do that, which compiles perfectly:

Example: A scan with no ceiling {#ex:unbounded-scan-wrong}

<!-- finder: recognize an unbounded loop over box data -->

{{include-ex:unbounded-scan-wrong}}

Nothing here is a type error. The compiler has no opinion about `count`, because `count` is a runtime value; it will happily emit a loop that runs four billion times. What stops it is the reference cap, which arrives first and arrives brutally: a `BoxMap` scan needs a reference per box, so the ninth entry has nowhere to be declared. The opcode budget would stop it soon after. Neither is a compiler message; both are a failed transaction.

This is worth generalizing beyond boxes, because it is the same shape every time: **a loop bounded by a runtime value has a ceiling you did not choose and cannot see.** The fix is never "make the loop faster." It is to bound the loop by a constant and let the caller ask again --- which moves the iteration off-chain, where it is free, and leaves the contract with a cost it can prove.

*What this section repairs in the guestbook:* `has_signed`. There is no budget you can buy that makes an unbounded scan safe, so the corrected contract does not scan at all. It exposes an indexed read and a count, and lets the client do the walking.

## Values You Can Put in a Box
Everything so far has been about bytes in the ledger. This section is about the thing you hand a box, because it turns out not every value can be one. One of the four array types you will actually choose between cannot go in a box at all, and of the three that can, not all of them make a key whose price you can work out in advance. Choosing between them is one question asked twice --- *does assignment copy, and can the value change after it is built?* --- and the answers determine both what compiles and what is storable.

Example: A value-semantics array {#ex:array-value-semantics}

<!-- finder: understand why an array assignment needs .copy() -->

{{include-ex:array-value-semantics}}

The load-bearing line is `b = a.copy()`, and the comment on it is the point: without `.copy()`, that line does not compile. `Array` has **value semantics** --- two names must mean two arrays --- and rather than silently copying for you or silently aliasing, PuyaPy makes you say which you meant. This is the same rule, and the same error message, that {{ch:state}} met on `arc4.Struct`. It is worth recognizing as one rule and not two.

Example: A reference-semantics array {#ex:reference-array}

<!-- finder: share one array between two names -->

{{include-ex:reference-array}}

`ReferenceArray` is the opposite choice: `b = a` is legal and gives you a second name for the same array, exactly as a Python list would. It buys you the ability to pass a large working array to a subroutine without copying it.

It costs you three things, and the third is the one that matters in this chapter. It costs scratch slots, a finite per-transaction resource --- the compiler spends them for you, and you never ask for them. (What `scratch_slots=` on the contract does is the reverse: it marks slots **off limits** to Puya, which is what you need when your own code wants a slot for something else, such as reading another transaction's scratch space with `op.gload_uint64`.) It costs the guarantee that a value you handed to a subroutine came back unchanged. And it cannot be stored: a `ReferenceArray` in a box fails to compile with `type is not suitable for storage`, because it lives in scratch space rather than in an encoded value. It also cannot hold dynamic elements, for the same reason --- `reference arrays can't have dynamic elements`. It is a working type, not a stored one.

Example: Freezing a working array {#ex:immutable-array-freeze}

<!-- finder: make an array immutable once it is built -->

{{include-ex:immutable-array-freeze}}

The load-bearing line is `grown = snapshot.append(UInt64(2))`. On an `ImmutableArray`, `.append()` does not mutate --- it returns a new array and leaves the original alone, so the return value is the whole point.

*Predict: what does the compiler do if you write `snapshot.append(UInt64(2))` on its own line and ignore what comes back?*

It warns: `expression result is ignored`. That is worth noticing, because it is unusually kind. The compiler cannot know you meant to mutate, but it can see you computed something and threw it away, and it says so. Do not rely on that everywhere --- it is a warning about an ignored result, not a check that you used the right array type.

`ImmutableArray` also has **no `.copy()` method at all**, and does not need one. Plain assignment is legal and safe, because there is no mutation for two names to disagree about. That is the single cleanest reason to reach for it: the `.copy()` discipline the next four chapters will make you practise simply does not apply. `.freeze()` converts a mutable `Array` into one, which is the usual way to get one: build it mutably, freeze it when it is done.

Example: An array with its length in its type {#ex:fixed-array}

<!-- finder: declare an array whose length is known at compile time -->

{{include-ex:fixed-array}}

`FixedArray[UInt64, typing.Literal[4]]` puts the length in the type, which makes the whole thing a fixed-size type --- so `size_of` works on it and `zero_bytes` works on it, and, decisively for this chapter, it makes a **`BoxMap` key of a fixed name length**. Every box in the map is named by the same number of bytes, so every box in the map costs the same, and you can price the map before you build it. The two commented lines are that claim being cashed: the same array goes into a `Box` as a value on one line and names a `BoxMap` entry on the next. `.full(...)` builds one with every slot set, and `.copy()` is required going into the box for the reason the first example in this section established. `ImmutableFixedArray` is the frozen counterpart --- the fifth array type, and the one you will reach for least --- and `FixedArray.freeze()` is how you get one. The return line uses it in passing: `self.bag.value.freeze()[0]` reads the array back out of the box and freezes it, which is the form you can index, hand to a subroutine, or return without any `.copy()` ceremony at all.

One thing that example deliberately does not have is a minimum-balance pre-flight, and it says so in a comment. It creates two boxes --- one named `b"b"` in a single byte and holding the array's 32, one named by the 32-byte array itself and holding 8 --- and pays 15,700 plus 18,900, or 34,600 microAlgos of new MBR, for the privilege, which is exactly the cost the last section insisted on checking first. Four lines about array types are not the place to relitigate that, but a contract is: the guard belongs in front of those two writes, in the form the corrected guestbook uses.

A dynamic `Array` can be a box *value* --- boxes are perfectly happy with length-prefixed data, and a box you `resize` is the natural home for one. It can also be a `BoxMap` key: `BoxMap(Array[UInt64], UInt64, key_prefix=b"b")` compiles without a word of complaint. That is worth knowing precisely because it is a trap the compiler will not spring for you. A dynamic key encodes to a different number of bytes for every entry, so every box in the map has a different name length, so `2,500 + 400 × (name + data)` is a different number for every box --- you can no longer price the map, only price one entry of it. It also puts the map back in the variable-length-key family the collision section warned about. So the connection back to the rest of the chapter is not "fixed is better" as a matter of taste: a fixed-size array is the one you can *name a box with* and still know what the map costs, and a dynamic one is the one you should only *fill a box with*.

{{tbl:array-types}} settles the choice. Read down the *Assignment* column first --- that is the one that decides whether your code compiles --- then the *Can it be stored* column, which decides whether the value can leave the transaction at all.

Table: The four array types you choose between, and how to tell them apart {#tbl:array-types}

| Type | Assignment | Mutable | Can it be stored | Reach for it when |
|------|------------|---------|------------------|-------------------|
| `Array` | `.copy()` required | yes | value; key priced per entry | building a variable-length value locally |
| `FixedArray` | `.copy()` required | yes | value **or** fixed-price key | the length is known and the value must be sizeable |
| `ImmutableArray` | aliases safely (no `.copy()`) | no | value; key priced per entry | a built value that must not change afterwards |
| `ReferenceArray` | aliases | yes | **no** | passing a large working array to subroutines |

Two rows are the only singletons in the table, and they are the two worth memorizing: `FixedArray` is the one that makes a `BoxMap` key costing the same for every entry, because its length is in its type, and `ReferenceArray` is the one that cannot be stored at all. The remaining two differ from each other only in whether the value can change after it is built --- which is the assignment column saying the same thing a second way, since a value that cannot change is a value that is safe to alias. So: fixed-price key, take `FixedArray`; subroutine scratch that never lands in the ledger, take `ReferenceArray`; must not change once built, take `ImmutableArray`; otherwise `Array`.

*What this section repairs in the guestbook:* nothing, and it is the only section that repairs nothing. It is here because the next four chapters build values before they store them, because `.copy()` is the compiler error you are most likely to hit while doing it, and because `type is not suitable for storage` is the second.

## The Mini-Build, Fixed
Three decisions, three corrections. The full corrected contract is on disk at `examples/ch04_boxes/guestbook_fixed.py` and compiles in CI; here is the spine of the diff, with bodies and decorators elided.

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

Six things are elided from that and named here so nothing arrives unannounced. The import line changes, and it changes in both directions: `BoxMap` and `size_of` come in, `Account`, `Box`, and `Bytes` go out. Reconstruct the fixed contract from the diff alone without touching the imports and it will not compile --- which is the ordinary fate of every diff that shows a body and hides a header. `ENTRY = 40` is replaced by two constants, `BOX_FLAT = 2_500` and `BOX_BYTE = 400`, which are the two halves of the pricing formula. The forty bytes become an `arc4.Struct` called `Entry`, holding an `arc4.Address` and an `arc4.UInt64`. Every method on both versions carries `@arc4.abimethod`, and `has_signed`, `all_entries`, `entry_at`, and `count` carry `readonly=True`. Three names used in `sign` are bound just above the lines shown --- `index = self.signed.value`, the index about to be written; `name_len = self.entry.key_prefix.length + UInt64(8)`, the box name's length in bytes; and `app = Global.current_application_address`, whose balance the guard reads --- and `sign` ends by storing `index + UInt64(1)` back into `self.signed`. And three methods do not appear in the diff at all: the broken version's `all_entries`, which returns the whole blob and disappears along with `has_signed`; the broken version's organizer-only `clear`, which deleted the single box and has no counterpart in the fixed version, because there is no longer one box to clear; and the fixed version's new `retire(index)`, which is discussed at the end of this section.

Deploy the fixed contract, fund it with the same one Algo, and sign it forty-one times:

```python
>>> guestbook.send.sign().abi_return
39
>>> guestbook.send.sign().abi_return
LogicError: Txn 5KDA...92QP had error 'assert failed: app account
underfunded' at PC 412 and Source Line 28:
    ... 9 lines of TEAL trace ...
```

It stops *sooner* --- at the forty-first signature rather than the fifty-sixth --- and that is the correction working, not failing. The broken contract got further on the same Algo because a shared blob is cheaper per entry, and it got there by accumulating three walls it could not see. One Algo genuinely does not pay for more than forty boxes, and no code can conjure a minimum balance. What changed is that the contract now says so, in a sentence an organizer at a check-in desk can act on, and says it before writing anything rather than after.

**Correction one: one box per signature.** `self.entries` became `self.entry`, a `BoxMap[UInt64, Entry]` keyed by an index the contract maintains in global state. Signing creates a box instead of rewriting one, and that changes both currencies at once --- so it is worth being explicit about which is which, because they are easy to blur and they behave differently.

{{tbl:guestbook-two-currencies}} prices the next signature both ways, in both currencies, with *n* signatures already stored. Everything the correction did is in the four rows of it.

Table: One shared box against one box per signature, with *n* signatures already stored {#tbl:guestbook-two-currencies}

| What is charged | Broken: one shared box | Fixed: one box per signature |
|----------------|------------------------------|------------------------------|
| **Read budget** | 40*n* --- the whole blob | 0 --- the box does not exist yet |
| **Write budget** | 40(*n*+1) --- the whole new blob | 40 --- the one box written |
| **Minimum balance** | 400 × 40 = **16,000** per signature | 2,500 + 400 × (9 + 40) = **22,100** |
| **First budget wall** | 52nd signature, on one reference | none --- the MBR guard binds first, at the 41st |

Read the top two rows as one fact: the broken version's cost per signature was the *whole history*, charged twice over, and the fixed version's is one record. That is why the fifty-second-signature wall is gone --- along with the four hundred and tenth it became once algokit's padding was spending eight references at a time, the 103rd-signature `concat` limit, and the 820th-signature ceiling the box's own maximum size imposed.

The third row is the bill for it, and the chapter would be lying to skip it: every signature is 6,100 microAlgos dearer, about 38% more, because the 2,500-microAlgo per-box constant and the nine bytes of name are now paid once per entry instead of once for all of them.

Those two currencies are the whole trade, and the shapes matter more than the numbers. The MBR went up by a *constant*; the I/O budget went from a *curve* to a constant. A constant you can pay by funding the account once. A curve you cannot pay at all --- it eventually exceeds any allowance, and the only question is which signature discovers that. Trading a higher constant for a flat curve is the trade you almost always want.

{{ex:box-list-append}} is the design that keeps one growing box on purpose, and it is the cheaper one up to sixty-four entries --- flat MBR per entry, no 2,500 to spare --- but it cannot escape the middle row of that table. `resize` charges the box's whole new size, so at 32 bytes an entry the sixty-fifth append dies on a single reference. `BoxMap` is the one with no such number in it.

Which is the choice {{fig:storage-decision-tree}} was drawing all along. The guestbook's data is per-signature, unbounded, and owned by the contract, and following those three answers down the tree lands on boxes every time --- the correction is what the figure said, applied.

**Correction two: price the write before making it.** This is the defect that was a line that was not there --- there was nothing in the broken `sign` to point at, because the missing thing was the guard. `sign` computes the box's minimum-balance cost from the map's own prefix and the record's own size, and asserts the application account can cover it. Nothing in that assertion is a magic number transcribed from a wiki --- `self.entry.key_prefix.length` and `size_of(Entry)` both come from the declarations three lines above, so adding a field to `Entry` updates the check automatically.

Two things it still does not do, and both are worth naming rather than leaving for a reader to discover in production.

The first is that it does not make the *signer* pay. The organizer funds the application account, and every attendee spends the organizer's Algo. Having the caller cover the box they create requires a payment transaction grouped with the app call, so that the contract can inspect the payment and refuse to write the box unless the exact MBR arrived with it. {{ch:token-vesting}} does precisely that on its first contract method, and {{ch:zk-voting}} generalizes it. For now the check is honest about a cost it cannot shift.

The second is that it does not enforce one signature per attendee, and neither did the broken version --- `has_signed` was a question the contract answered for other people, never one `sign` asked itself. Nothing stops one address from calling `sign` a thousand times, and with the organizer paying 22,100 microAlgos a call, that is a way to spend somebody else's Algo at the cost of a fee. The guard makes it fail politely rather than corrupt anything, which is the difference between a bad afternoon and a lost guestbook, but it does not make it not happen. The fix is a one-line change of shape: key the map by `Txn.sender` instead of a counter, and the ledger enforces the rule by construction, because an account cannot have two boxes with the same name. That costs the indexed reads `entry_at` gives you, which is why this version does not do it --- but if you are building the real thing and the rule is "once per attendee," let the key say so.

**Correction three: stop iterating on chain.** `has_signed` and `all_entries` are gone, replaced by `entry_at(index)` and `count()`. This is not a cop-out or a reduction in capability. The check-in desk still gets its answer; it gets it by calling `count()` once and `entry_at` as many times as it needs, from a client with no opcode budget and no reference cap. What moved is not the work but where the work happens --- and a contract that exposes an indexed read has a knowable cost per call, which is the only kind of cost you can build a conference on.

There is also a `retire(index)` the broken version had no way to offer, because you cannot delete the middle of a blob. Deleting a box refunds its 22,100 microAlgos to the application account, which is the only mechanism in this chapter that makes the minimum balance go *down*. It is organizer-only, and the `assert Txn.sender == self.organizer.value` on its first line is not decoration: a `retire` anyone could call would let a stranger erase a signature and pocket nothing, which is the worst kind of bug --- damage with no motive to explain it away. The line under it, `assert index in self.entry`, is doing something quieter but no less deliberate. `del` on a `BoxMap` entry that does not exist is not an error --- the underlying `box_del` reports a `False` that PuyaPy discards --- so without that check, retiring an index that was never signed would succeed silently, and an organizer would have no way to tell "removed" from "was never there."

Note what `retire` does to `count()`. `self.signed` counts signatures ever taken, not boxes currently present, so once anything is retired `count()` is a high-water mark and `entry_at` on a retired index fails rather than returning an empty entry. That is a deliberate choice and not an oversight --- reusing indices would make a signature's index meaningless, and an index that means something is worth more than a count that is exact. The client walks `0..count()` and tolerates gaps.

This is the point at which the chapter's one transferable rule can be stated, because you now have everything you need to apply it: **a box is charged at its whole size, in both currencies, no matter how few of its bytes you touch.** Against the **I/O budget** it is charged twice, and the two charges are never added: once at its current size the moment the transaction references it, before your first opcode runs, and again at its new size when the program writes to it. Against **minimum balance** it is charged for the size it currently is, for as long as it exists --- which is why that charge moves only when the size does. The rule deliberately says nothing about the third currency this chapter opened with, the opcode budget, because that is the one place where touching fewer bytes genuinely is cheaper: reading a box through `.value` costs opcodes in proportion to its size, while `extract` and `replace` cost the same however large the box is. That exception, and the 4,096-byte stack limit, are the whole reason those two operations exist --- neither of them makes either of the other two charges smaller. Hold that sentence against every box operation you write for the rest of this book.

## What Bites People Here
Five, in the order you are likely to meet them: one about money, one about budget, one about naming, one about an operation that does not do what it says, and one about loops.

::: {.gotcha #box-growth-raises-app-mbr topic="Resource references, MBR, and budget" title="Writing a box can make a contract that worked yesterday stop working today"}
Creating or growing a box raises the *application account's* minimum balance by 400 microAlgos per byte, plus 2,500 for each new box --- and nothing about that shows up in the source, in a compiler warning, or in a test. The contract keeps working until the account's balance meets a floor that has been rising underneath it, and then every call that writes a box fails at once, with an error about an account rather than about a box: `account <address> balance <n> below min <m> (<k> assets)`. That is not a `LogicError` and it will not be caught by anything asserting on your messages, because the check happens after your program has already run and returned success --- there is no assertion of yours left to fire. A contract whose storage grows with usage needs either a funding plan that grows with it or a pre-flight check like {{ex:app-mbr-floor}} that refuses in a sentence a caller can act on. Deleting or shrinking a box gives the whole charge back, which is the only thing in this chapter that makes the floor go down.
:::

::: {.gotcha #box-charged-at-full-size topic="Resource references, MBR, and budget" title="A box is charged at its full size, however few bytes you touch"}
Each box reference grants 2,048 bytes of I/O budget, and that allowance is checked as **two separate budgets that are never added together**. The *read* budget is charged before your program runs, as the sum of the full current sizes of every referenced box that exists --- even one you never intended to read. The *write* budget is charged as the full size of each box written, once per box, with `box_resize` charging the full **new** size. Neither charges the bytes you touched: `extract`, `replace`, and `.length` all cost the same as `.value`, because the charge happened before and around them. Both budgets pool across the whole transaction group, and references need not be distinct --- duplicate and empty references each grant another 2,048 bytes, which is the fix. algokit-utils pads up to eight references for you by default, so a budget failure that padding can cover will not appear until the call is assembled by something that does not pad: another contract, a hand-built transaction, a different SDK.
:::

::: {.gotcha #box-prefix-collision topic="Box storage" title="Two BoxMaps with variable-length keys can name the same box"}
A `BoxMap` box name is nothing but `key_prefix + encode(key)`, so a map with prefix `b"a"` and key `b"bc"` names the same box as a map with prefix `b"ab"` and key `b"c"`. The second write silently overwrites the first and no tool warns you, because concatenation cannot tell where you meant the seam to be. Fixed-width keys --- `Account`, `UInt64`, a fixed-size struct, a `FixedArray` --- are immune, since every name in the family is the same length. With `Bytes`, `String`, or dynamic array keys, give every map a prefix of the same length or include a separator that cannot occur in a key.
:::

::: {.gotcha #splice-does-not-resize topic="Box storage" title="Box.splice never changes a box's size"}
`splice(start, length, value)` looks like a list insertion and is not one: after removing and inserting, it forces the result back to the box's original size. Inserting eight bytes pushes eight bytes off the end; removing eight appends eight zero bytes. `resize` is the only operation that changes a box's size, and it is also the only one that changes the minimum balance --- so if you want an insertion that grows the box, `resize` first and `splice` second.
:::

::: {.gotcha #unbounded-box-scan topic="Resource references, MBR, and budget" title="A loop bounded by a runtime value has a ceiling you did not choose"}
`while index < count` over box entries compiles cleanly, because `count` is a runtime value and the compiler has no opinion about it. What stops it is the box-reference cap or the 700-unit opcode budget, and in practice the reference cap arrives first, because the cap --- eight on the legacy foreign arrays, sixteen on the v41 `Access` list --- is a much lower ceiling than 700 units of arithmetic. Both arrive as a failed transaction in production rather than as an error at build time. Marking the method `readonly=True` buys you a delay and not a reprieve: the tooling simulates it with a 320,000-unit opcode budget, so the loop that dies on chain at entry 30 may run to entry 8,000 in your tests and then die anyway. Bound the loop by a constant the contract chose and let the caller page.
:::

## Retrieval
Answer these from memory before moving on. Three of them reach back into earlier chapters on purpose.

1. What does a box cost in minimum balance, and which account is charged?
2. How many bytes of I/O budget does one box reference grant, and what are the *two* separate budgets that allowance is checked against? Which one is charged before your program runs?
3. State the chapter's transferable rule in one sentence.
4. What must a transaction declare before a contract may touch a box, and what happens if it does not?
5. Name the only operation that changes a box's size, and the one that looks like it does and does not.
6. The broken guestbook's write-budget wall is at the fifty-second signature, but the conference organizer never saw a budget error. What was paying for it, and name two ways of assembling the same call that stop paying.
7. Which of the four array types you choose between cannot go in a box at all, and which one makes a `BoxMap` key whose cost is the same for every entry?
8. *(From {{ch:state}})* Which storage tier can a user delete without your contract's consent, and what does that imply about where a liability may live?
9. *(From {{ch:mental-model}})* Minimum balance is locked rather than spent. What happens to the locked Algo when a box is deleted?
10. *(From {{ch:contracts}})* A method marked `readonly=True` is simulated rather than submitted. Does that exempt it from the opcode budget on chain?

## Exercises
1. **(Trace)** The broken guestbook is deployed and its application account is funded with exactly 1.5 Algo. Every call is sent with exactly one box reference --- no padding. The single box is named `b"entries"` and each signature appends 40 bytes.

   The first wall is the **write budget, at the 52nd signature**: `box_put` charges the box's whole new size, and 40 × 52 = 2,080, which is over the 2,048 one reference grants. That one is worked for you. Find the other three, in the order they would arrive if each previous one were somehow removed: the minimum balance, the 4,096-byte limit on a value the AVM will put on the stack, and the box's own maximum size. Show the arithmetic for each, and note that the minimum-balance figure needs the application account's own 100,000 base and the box's 7-byte name, not just 400 a byte.

   Then answer the part that is not arithmetic. Two of the four walls move if the *caller* assembles the transaction differently, and two do not. Say which are which, and what that tells you about where a wall really lives.

2. **(Parsons + Analyze)** Below are six statements. Four of them form the body of a `withdraw` method that decrements a balance stored in a `BoxMap[Account, UInt64]` named `self.balance`; two do not belong in it at all. The decorator and signature are given.

   ```python
   @arc4.abimethod
   def withdraw(self, amount: UInt64) -> UInt64:
       ...
   ```

   The statements: (a) `current = self.balance.get(Txn.sender, default=UInt64(0))`; (b) `assert current >= amount, "insufficient balance"`; (c) `self.balance[Txn.sender] = current - amount`; (d) `return current - amount`; (e) `current = self.balance[Txn.sender]`; (f) `assert self.balance.box(Txn.sender).length == 8, "no balance box"`.

   Select the four that belong and order them. Both rejects fail on the same call --- a first-time caller who has never deposited --- and the interesting part is that they fail *differently*, which is why only one of them would survive a code review.

   For each, say exactly what the caller sees. Then say which of the two a reviewer would wave through and why: one of them wears the costume of a safety check, and it costs nothing in I/O budget to wear it, because the box's full size was charged the moment the transaction referenced it and `.length` adds nothing on top. Say what that check silently converts a well-defined behaviour into, and why "it's just a safety check" is the wrong defence for a line that changes what the method means. Finally: what should the method do when `current - amount` is zero, and what does that decision cost?

3. **(Debug)** A contract stores a 5,000-byte configuration blob in a single box and exposes `update_field(index, value)`, which reads `self.config.value`, splices eight bytes in at `index * 8`, and writes the whole thing back. Unit tests pass --- and the premise matters, because `algopy_testing` emulates box *contents* faithfully and does not enforce the AVM's I/O budgets or its stack limits at all, so a passing unit test says nothing about either. Called on LocalNet through a default algokit-utils client, it fails.

   Before working through anything else, write down which of the two limits you expect to fail and what its message will be arithmetic *about* --- a box, or a value. Then answer three things. First: which of the two limits does it hit, and which does it *not* hit even though the naive arithmetic says it should? Second: why not --- what did the client do on your behalf, and what is the number that ran out anyway? Third: give the fix, and say honestly which of the two limits it removes and which one it does not, because it is only one of them.

4. **(Compare)** You need to store one 64-byte record per user, the user count is unbounded, and the records are read one at a time by the user they belong to. The record is a **liability**: it is the contract's own accounting of what it owes that user, and if it disappears the contract's books are wrong in the user's favour. Keep that in view, because it decides one of the three designs on its own. Compare all three on four axes --- MBR cost per user, who pays it, I/O budget per read, and what happens when a user stops using the contract: (i) a `BoxMap[Account, Record]`; (ii) one large box holding records at computed offsets, accessed with `extract` and `replace`; (iii) local state, packed into a single byte slot. One of the three is disqualified by a hard ceiling; name it, give the number, and say where the number comes from. A second is disqualified by the liability requirement in the paragraph above, for a reason that has nothing to do with any ceiling --- name it and say what the reason is. That leaves one design standing: say what it costs per user, who pays that cost, and what single change to the requirements would make one of the two disqualified designs the right answer after all.

5. **(Extend)** Extend the fixed guestbook so that the *signer* pays for their own box rather than the organizer. You will hit a problem the chapter has not solved: making the signer pay requires a payment transaction grouped with the application call, and reading a grouped transaction from inside a contract is not covered here. Write the method with the payment check left as a comment, and write down precisely what you need to know to fill it in --- including what the contract must verify about that payment, and what goes wrong if it verifies only the amount.

## Before You Continue
You should be able to check off all five of these:

- [ ] Given a piece of data, I can walk the decision tree to global state, local state, or a box and defend the answer --- and if it is a box, compute its minimum balance from its name and its contents, including the `BoxMap` prefix, and say which account is charged and when it is refunded.
- [ ] I can count the box references an app call needs by working out its read budget and its write budget separately, say what to do when one reference is not enough, and name the three places in this chapter where a limit is quietly paid for by tooling rather than by my contract --- and what happens the first time something else assembles the call.
- [ ] I can say why `extract` and `replace` exist --- to reach into a box the AVM cannot put on the stack --- name the size at which I have no other choice, name the only operation that changes a box's size, and explain what `splice` does instead of changing it.
- [ ] I can spot a loop whose bound is a runtime value, and restructure it into something with a ceiling I chose.
- [ ] I can pick between the four array types from the assignment rule alone, and say which one cannot be stored and which makes a fixed-price `BoxMap` key.

## Handoff: What the Vesting Project Needs
{{ch:token-vesting}} builds a real token vesting contract, and it stores every beneficiary's schedule in a box on the first page. {{tbl:box-handoff}} lists the examples from this chapter that it leans on, and what to predict before you read it.

Table: Examples from this chapter that the vesting project depends on {#tbl:box-handoff}

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| {{ex:boxmap-declare}} | One schedule box per beneficiary, keyed by address | Why can a vesting schedule not live in the beneficiary's local state? |
| {{ex:box-mbr-math}} | Funding the application account before the first schedule is created | A 32-byte address key, a 2-byte prefix, and a 41-byte record. What does one schedule cost? |
| {{ex:app-mbr-floor}} | The guard that refuses to create a schedule the contract cannot afford | What does the signer see if the guard is missing? |
| {{ex:box-refs-auto}} | Every client call that touches a schedule box | The method takes the beneficiary as an argument. Does that alone make the box available? |
| {{ex:boxmap-scan-cost}} | Why the project has no "list all schedules" method | How many schedules could such a method return before it failed, and would that number be stable? |
| Exercise 5 | The grouped payment that makes the beneficiary fund their own schedule box | You wrote down what the contract must verify about that payment. Which of your checks does the project actually make? |
