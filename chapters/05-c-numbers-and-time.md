\newpage

# Arithmetic That Refuses: Numbers and Time

The last chapter was about paying for storage. This one is about the two things you will store: numbers, and the moments they belong to. Neither behaves the way it does anywhere else you have programmed, and both fail in the same characteristic way --- not by producing a wrong answer, but by refusing to produce one at all.

That refusal is the AVM's best feature and the source of most of the confusion around it. There is no float, no negative number, and no silent wraparound. A subtraction that would go below zero does not give you a large positive number; it kills the transaction. A division by zero does not give you infinity or a `NaN`; it kills the transaction. You have already met this once without being told what it was: {{ch:boxes}} insisted you write a funding check as `balance >= min_balance + cost` rather than `balance - min_balance >= cost`, and offered the underflow as the reason. That was never a fact about balances. It was this chapter's one arithmetic rule arriving early, and by the last page you should be able to derive it rather than recall it. Nothing is corrupted, nothing is half-written, and no attacker walks away with anything --- which means that in exchange for a contract that cannot be tricked by arithmetic, you get a contract that can become permanently uncallable on an input path you never tested. The whole chapter is about seeing those paths before a user finds one.

## The Problem
Here is a failure with a name: **the vesting calculator that paid nothing for eighty-nine days.**

A company grants an employee a million tokens, vesting linearly over ninety days. The contract is nine lines of arithmetic. It is reviewed, it is unit tested, the tests pass, and it goes to MainNet with the grant funded on day zero.

On day thirty the employee calls `vested_now` and it returns zero. That is surprising but not alarming --- perhaps there is a cliff nobody mentioned. On day sixty it returns zero. On day eighty-nine it returns zero. On day ninety it returns one million, all at once, and the finance team discovers that the "linear" vesting schedule was a switch: nothing, then everything.

Nobody wrote a switch. What was written was `(elapsed / duration) * total`, transcribed out of a spreadsheet where that is exactly right. On the AVM, `elapsed / duration` is integer division, so for the first eighty-nine days it is `0`, and zero times a million is zero. There is no float to notice the loss and no warning anywhere: the expression is well typed, the compiler is content, the tests --- which checked day zero and day ninety, the two days the expression happens to get right --- are green.

That is defect one, and three more live in the same nine lines. All four share a character: they turn the contract off rather than make it lie. Two of them end the transaction outright --- one when the schedule is configured a particular way, one for every caller during the whole period before the grant starts --- and the fourth never fails at all, which is exactly what makes it the dangerous one.

All four survive review, and all four survive testing, for the same reason: on the happy path --- a schedule that has started, has not finished, and was configured sensibly --- every one of them behaves.

## What You'll Be Able to Do
By the end of this chapter you will be able to:

- Express a rate, a percentage, or a fraction without a float, and say which of the two orderings of a multiply-and-divide is the one that works
- Predict which arithmetic expressions abort the transaction, quote what the chain says when they do, and say why the message you see in a unit test is not the message a user will see
- Guard a division against a zero divisor and a subtraction against going negative, and place each guard where the value is *established* rather than where it is used
- Compute a product that does not fit in sixty-four bits using `op.mulw` and `op.divw`, and say why reaching for `op.divmodw` instead is the more dangerous choice
- Name the four values a contract can mistake for "now", say which one is the answer, and say what each of the other three is actually measuring
- Read a past block from inside a contract, name the exact window you are allowed to read, and explain why block randomness cannot be made safe no matter how carefully you use it
- Write a linear release schedule with a cliff, defend the direction it rounds, and say who gets the dust

{{fig:four-clocks}} is the half of this chapter that cannot be discovered by reading code, because every one of those four values compiles, and three of them are wrong. Read it before any of the examples; the second half of the chapter is that picture in contract form.

{{include-fig:four-clocks}}

The distances on that diagram are what matter. `Global.latest_timestamp` sits one block behind `Global.round` --- always, by construction, not sometimes. `Txn.first_valid_time` can sit a thousand rounds behind that. And `Txn.last_valid` is not on the timeline in any meaningful sense at all, because it is a number the caller wrote down before sending the transaction.

## The Mini-Build, Broken
Example: The vesting calculator, as first written {#ex:vesting-calc-broken}

<!-- finder: see a linear vesting calculation that returns zero for the whole schedule -->

{{include-ex:vesting-calc-broken}}

{{ex:vesting-calc-broken}} is complete and deployable. It compiles without a warning, it has a creator-only guard on `configure` and an init-once flag beside it, and it contains four defects: three are wrong lines, and one is a guard that was never written. The missing guard is the harder kind to find and the more common kind to ship.

It only reports a number; paying the beneficiary needs an inner transaction, which is {{ch:moving-value}}'s material. Everything wrong with it is wrong before any money moves, which is the point of stopping here.

*Predict: four defects. Write your four down now, in whatever words you have --- you are not expected to be right yet, and one of them is genuinely hard to see. Check them against the diff at the end of the chapter.*

Deploy it, configure a ninety-day schedule, and ask it what has vested. A round is roughly two and three-quarter seconds, so ninety days is about 2,830,000 rounds, and the grant is a million tokens:

```console
$ algokit project deploy localnet
vesting-calculator 1094 deployed
```

Every transcript in this chapter is labelled, because this chapter is the one where it matters. The one below is an **on-chain run** against LocalNet through an algokit-utils typed client; the strings it prints are the AVM's own. One liberty is taken for legibility: the schedule is configured with `start = 0`, so "one third of the way through" means round 943,333, and a LocalNet you started this morning is a few hundred rounds old. Reproducing these exact numbers means configuring `start` and `end` relative to the round you are actually on. The arithmetic is identical either way, and absolute rounds read better than offsets.

```python
>>> calc.send.configure(args=(1_000_000, 0, 2_830_000))
>>> calc.send.vested_now().abi_return   # one third of the way through
0
>>> calc.send.vested_now().abi_return   # eighty-nine days in
0
>>> calc.send.vested_now().abi_return   # day ninety
1000000
```

That transcript is the first defect and nothing else. `elapsed // span` is an integer, it is `0` until `elapsed` reaches `span`, and multiplying a million by zero is a very fast way to compute zero. **Divide last.** `(total * elapsed) // span` computes the same fraction and gets it right, because the multiplication happens while the numbers are still large enough to carry information.

*Predict: `total * elapsed` at a million tokens and 2,830,000 rounds is about 2.8 trillion, which is comfortably inside sixty-four bits. Now suppose the grant were a hundred million tokens of an ASA with six decimals, so `total` is 10^14. What is `total * elapsed` then, and does it still fit?*

It does not --- 10^14 x 2,830,000 is 2.83 x 10^20, about fifteen times the largest number a `UInt64` can hold --- and that is the second half of the fix rather than a separate concern; the wide-arithmetic section is where it gets solved. The threshold is lower than it looks: on this ninety-day schedule any `total` above 6,518,284,124,985 --- call it six and a half million tokens at six decimals --- overflows somewhere in the back half of the schedule.

Now configure the same contract with `start` and `end` the same round --- a schedule of zero length, which a deployment script produces the first time somebody passes a duration of zero:

```python
>>> calc.send.configure(args=(1_000_000, 1000, 1000))
>>> calc.send.vested_now().abi_return
LogicError: Txn 7QW3...M2LP had error 'logic eval error: / 0.
Details: app=1094, pc=214' at PC 214 and Source Line 33:
    ... 11 lines of TEAL trace ...
```

Every `LogicError` in this book is printed in full the first time it appears in a chapter and then trimmed to its `.message` in the prose --- the transaction ID, the program counter, and the TEAL trace are real, and they are noise for everything this chapter is about.

That is defect two, and read the message carefully, because it is not `assert failed`. No assertion of yours fired. The AVM's own divide opcode refused, and the phrase `logic eval error: / 0` is the AVM speaking, not your contract. There is nothing in the contract that could have caught it, because there is nothing in the contract that looks at `span` before dividing by it.

Look at where line 33 sits, though, because the shape is worth more than the message. The contract *does* have a branch that handles a schedule already finished --- `if now >= self.end.value` on the next line --- and on a zero-length schedule that branch is exactly right and would have returned the total. It never runs. `fraction = elapsed // span` was hoisted above it, the way an intermediate gets hoisted when you are tidying a method and the value is wanted by both paths. **A guard cannot protect arithmetic that has already happened above it.** That is the single most common way an abort survives a code review: nobody deletes the guard, somebody moves the arithmetic.

Worse than the message is what it does to the contract. `configure` is init-once, so the schedule cannot be corrected. There is no other method. The contract is now a permanently uncallable object holding a grant, and the only thing wrong with it is that two numbers were equal.

Call the same contract before its schedule starts and a third failure appears, on a schedule that is configured perfectly well:

```python
>>> calc.send.configure(args=(1_000_000, 5_000_000, 7_830_000))
>>> calc.send.vested_now().abi_return
LogicError: Txn J4KD...81XR had error 'logic eval error:
- would result negative. Details: app=1094, pc=198' at PC 198
and Source Line 31:
    ... 9 lines of TEAL trace ...
```

`elapsed = now - self.start.value` with `now` before `start` is a subtraction that would go below zero, and the AVM does not go below zero. **`- would result negative` is not a rounding message; it is the transaction ending.** For the entire period between deployment and the schedule's start --- which for a hiring grant is routinely months --- the contract answers every question with a failure.

That is three. The fourth defect has not failed yet, which is what makes it the dangerous one. `now = Txn.last_valid` reads a field of the incoming transaction, and a transaction's last-valid round is chosen by whoever built it. Any caller may set it up to a thousand rounds beyond the current round, for free, on every call. The contract believes it is reading a clock; it is reading a caller's preference --- the rightmost mark on {{fig:four-clocks}}, the one that is not on the timeline at all. Against a ninety-day schedule, a thousand rounds is about forty-six minutes of vesting, claimable as many times as the attacker can pay a fee --- and every one of those calls looks exactly like an honest one, because it *is* a well-formed transaction that the network is happy to accept.

*Predict: this contract's LocalNet tests pass. Before reading on, say how far apart you think `Txn.last_valid` and `Global.round` sit on LocalNet, and what that implies about a test's chances of catching defect four.*

The natural guess --- that with one transaction in flight at a time the two are a round or two apart, so the defect barely registers --- is exactly backwards. AlgoKit Utils defaults to a ten-round validity window against every network, and then makes a deliberate exception for LocalNet, widening it to a thousand: the protocol maximum, with the source comment *set a bigger window to avoid dead transactions*. So on LocalNet `Txn.last_valid` sits roughly nine hundred and ninety-nine rounds ahead of `Global.round`, and every test run you have ever done against this contract has exercised defect four at its full strength. The tests pass anyway. They pass because they assert that a call succeeded and a number came back, never that the number matches one computed independently of the contract. **A defect that reads a caller-supplied field is not caught by exercising it. It is caught only by asserting against a figure the contract did not produce.**

Four defects. The five sections that follow take AVM arithmetic and AVM time apart, and each one ends by naming what it repairs in the calculator. By the end you will be able to state all four in a sentence each.

## Overflow, Underflow, and Division by Zero
Everything in this section is one idea seen five ways: **the AVM has exactly one numeric type for ordinary work, and every operation on it that cannot produce a valid value of that type stops the program instead.**

That type is `UInt64` --- a whole number from 0 to 18,446,744,073,709,551,615. There is no signed integer, no fixed-point type, and no float. There is a wider type, `BigUInt`, which the AMM's pricing maths needs --- a chapter of its own later in the book --- and this chapter deliberately does not use.

Example: A rate without a float {#ex:no-floats}

<!-- finder: express a percentage or a fee without floating point -->

{{include-ex:no-floats}}

The load-bearing line is `return (amount * fee_bps) // UInt64(BASIS_POINTS)`, and the thing to notice is the order: multiply, then divide. Reverse it and every fee below one hundred percent rounds to zero, which is the calculator's first defect in miniature.

That line has a domain limit, and it is worth naming now rather than discovering later. `amount * fee_bps` is a plain sixty-four-bit multiply, so it aborts once `amount` exceeds about 1.8 x 10^15 --- fine for an Algo amount in microAlgo, not fine for an ASA with eighteen decimals. The fix is {{ex:mul-div}}, two sections down, and until then read every multiply-then-divide in this section as carrying an unwritten "provided the product fits."

`fee_on` is also the first `@subroutine` in this book, and it is worth thirty seconds because five of this chapter's examples use one. A `@subroutine` is a plain function that PuyaPy inlines into whichever method calls it: it is not an ABI method, it has no selector, it cannot be called from off-chain, and it does not appear in the contract's ARC-4 interface at all. It exists so that a piece of arithmetic can be written once and reasoned about once. Everything a method may do, a subroutine may do --- including asserting, which is why the guards in the next few examples can live inside one.

A *basis point* is one hundredth of a percent, so ten thousand of them make one. The denominator is a constant everybody agrees on rather than a property of the number, which is what "no floats" means in practice: you do not store 0.025, you store 250 and remember that the scale is ten thousand. Pick the scale once, write it down as a named constant, and never let it appear as a bare literal in an expression.

Example: Addition that stops at the ceiling {#ex:overflow-panics}

<!-- finder: see what happens when a uint64 addition overflows -->

{{include-ex:overflow-panics}}

The load-bearing line is `assert b <= UInt64(MAX_UINT64) - a, "sum would overflow"`, and its shape is the general one. `a + b` on values that exceed the ceiling does not wrap to a small number the way C would; the AVM reports `+ overflowed` and the transaction ends. Since there is no result to inspect afterwards, the check has to happen before --- and the only way to write it is as a comparison, because any expression that computes the overflowing sum in order to test it has already overflowed.

Note which subtraction the guard uses. `MAX_UINT64 - a` cannot itself go negative, because `a` is a `UInt64` and is therefore at most `MAX_UINT64`. Writing the same idea as `a + b >= a` --- the idiom from every unsigned-wraparound language --- is not just wrong here but unreachable, because the addition aborts before the comparison runs.

Example: Subtraction that stops at zero {#ex:underflow-panics}

<!-- finder: see what happens when a uint64 subtraction goes below zero -->

{{include-ex:underflow-panics}}

The load-bearing line is `if owed <= balance: return UInt64(0)`. The same rule as above, in the other direction: ask the question as a comparison, because the subtraction that would answer it is the thing that fails.

This makes operand order a correctness concern rather than a stylistic one, which is worth stating flatly because it has no analogue in most languages. `a - b` and `b - a` are not two ways of getting the same magnitude with different signs. One of them is a number and the other is the end of your transaction, and which is which depends on runtime values. Any time you find yourself writing a subtraction whose operands you cannot order at a glance, the fix is to restructure it into a comparison and two branches.

*Predict: a contract holds a user's `deposit` and a `fee`, and refunds `deposit - fee`. What is the first user experience that goes wrong, and does the user get a message or a mystery?*

Example: A division that cannot be given a zero {#ex:divide-by-zero}

<!-- finder: guard a division against a zero divisor -->

{{include-ex:divide-by-zero}}

The load-bearing line is `assert shares > UInt64(0), "need at least one share"` --- and where it sits is the whole lesson. It is in `set_shares`, the method that *establishes* the divisor. Guarding at the point of establishment costs one assertion; guarding at the point of use costs one per division site and quietly acquires a bug the day somebody adds a third.

There are assertions in the other two methods as well, and they are not the same check wearing a different hat. `assert self.shares.value > UInt64(0), "not initialised"` is testing whether the contract has been configured at all, because global state reads as zero before anything writes it --- the failure it prevents is calling a contract that is not ready, not configuring one badly. The two guards happen to compare the same value against the same bound, which is exactly why it is worth reading the messages. **When two assertions share a predicate but not a purpose, the message is the only thing that tells them apart in a failure log.**

`//` on a zero divisor reports `/ 0`, and `%` on a zero divisor reports `% 0`. Those are two different messages, which matters only when you are reading a failure and trying to work out which line produced it.

Example: The same contract without the guard {#ex:divide-by-zero-wrong}

<!-- finder: see a division-by-zero that compiles cleanly and detonates later -->

{{include-ex:divide-by-zero-wrong}}

Two lines are load-bearing, and they are in different methods. `self.shares.value = shares` accepts a zero without comment, and `return pot // self.shares.value` detonates on it --- possibly weeks later, possibly on a call made by somebody who has never heard of `set_shares`. The distance between the cause and the symptom is the entire cost of guarding late.

This is a stripped version rather than a one-line edit of the previous example, and the other things it drops are worth noticing on your own: there is no init-once guard on `set_shares`, so the divisor can be changed under a caller at any time, and there is no `remainder` method, so the second division site --- the one that would have produced `% 0` instead of `/ 0` --- is not there to be found. Count the differences before reading on; the exercise of diffing a correct contract against its plausible-looking sibling is the exercise.

PuyaPy will warn you about `x // UInt64(0)` written literally, because it can see the constant. It says nothing whatever about a zero that arrives in a variable, which is every zero that has ever caused a production incident.

The messages the chain produces are worth having in one place, because you will read them in failure output long before you can recall which is which. {{tbl:avm-arith-messages}} collects them.

Table: What the AVM says when arithmetic refuses {#tbl:avm-arith-messages}

| Expression | What the chain reports | What the unit-test emulator reports |
|------------------------------|----------------------------|-------------------------------|
| `a + b`, sum too large | `+ overflowed` | `OverflowError: + overflows` |
| `a * b`, product too large | `* overflowed` | `OverflowError: * overflows` |
| `a - b`, with `b > a` | `- would result negative` | `ArithmeticError: - underflows` |
| `a // b`, with `b == 0` | `/ 0` | `ZeroDivisionError` |
| `a % b`, with `b == 0` | `% 0` | `ZeroDivisionError` |
| `op.divw(...)`, zero divisor | `divw 0` | --- |
| `op.divw(...)`, quotient too large | `divw overflow: <d> <= <hi>` | --- |

**The two columns do not match, and that is not a defect in either.** `algopy_testing` raises Python exceptions with Python-shaped wording; the AVM emits its own strings from its own evaluator. Every one of the five arithmetic rows differs between them. So a test that asserts on a message is asserting on the emulator's message, and a runbook that quotes a message must say which side of the boundary it was captured on. The examples in this chapter that ship tests say so in a comment on the assertion, and this book labels every transcript as either a unit-test run or an on-chain one for exactly this reason.

Here is the other side of that boundary, so you have now seen both. This is an **emulator run** --- {{ex:underflow-panics}} under `algopy_testing`, in a Python REPL, with no chain anywhere near it:

```python
>>> from algopy import UInt64
>>> from algopy_testing import algopy_testing_context
>>> from examples.ch05_numbers_time.underflow_panics import Vault
>>> with algopy_testing_context():
...     Vault().shortfall(UInt64(40), UInt64(100))
ArithmeticError: - underflows
```

Same contract, same line, same defect, different vocabulary. `ArithmeticError: - underflows` is a Python exception raised by a Python reimplementation of the AVM's semantics; `- would result negative` is a string emitted by the Go evaluator that actually runs consensus. The test shipped with that example asserts `pytest.raises(ArithmeticError)` --- the exception *class*, never the text --- and that is the habit to copy.

The chain also wraps these in a little context before you see them. An application call produces `logic eval error: / 0. Details: app=1234, pc=57`; a LogicSig produces `rejected by logic err=/ 0. Details: pc=57`. The message you are looking for is in the middle.

*What this section repairs in the vesting calculator:* defects two and three. `span` is a divisor established by `configure`, so `configure` is where it gets its guard; `now - start` is a subtraction whose operands are ordered only when the schedule has started, so the schedule-has-started case gets its own branch.

## Numbers Too Big for One Word
The last section's rule has an awkward consequence. `(total * elapsed) // span` is the right expression, and multiplying first is exactly the thing most likely to overflow. Fixing the rounding bug creates an overflow bug, and the two cannot both be fixed by rearranging the expression.

They are fixed by leaving sixty-four bits. The AVM has opcodes that produce and consume 128-bit intermediate values, and they exist precisely so that a product can be too large to represent while the quotient still is not.

Example: A product in two halves {#ex:mulw-split}

<!-- finder: multiply two numbers whose product does not fit in 64 bits -->

{{include-ex:mulw-split}}

The load-bearing line is `hi, lo = op.mulw(a, b)`. `mulw` never fails: it multiplies two `UInt64`s into a 128-bit result and hands it back as two `UInt64`s, the high sixty-four bits and the low sixty-four. If the product did fit in sixty-four bits, `hi` is zero --- which makes `fits_in_64` in the same example a complete overflow test, and a cheaper one than the comparison from the previous section.

Example: Putting the two halves back together {#ex:divw-join}

<!-- finder: divide a 128-bit value by a 64-bit divisor -->

{{include-ex:divw-join}}

The load-bearing line is `return op.divw(hi, lo, d)`. `divw` takes a 128-bit numerator as its two halves and a 64-bit divisor, and returns a single `UInt64`. It refuses in two circumstances: `divw 0` for a zero divisor, and `divw overflow: <d> <= <hi>` when the quotient would not fit in sixty-four bits.

That second message is also the test. **`divw` succeeds exactly when `d > hi`** --- the check is exact rather than conservative, so `divw(5, 0, 6)` succeeds and `divw(5, 0, 5)` fails. That is a rule you can reason about at design time rather than discover in production: if you can bound the high word, you can prove the division will not abort.

Example: The wide division that fails quietly {#ex:divmodw-silent}

<!-- finder: understand why divmodw is the more dangerous wide division -->

{{include-ex:divmodw-silent}}

`op.divmodw` divides a 128-bit numerator by a 128-bit divisor and returns *four* words --- a 128-bit quotient followed by a 128-bit remainder. It looks like the more capable tool, and for the multiply-then-divide problem it is the wrong one.

*Predict: `a` is 2^63, `b` is 10, and the divisor is 2, so the true quotient is 2^63 × 5, which needs sixty-six bits. `divw` aborts. Write down what you think `divmodw` does.*

It returns, successfully, with `q_hi = 2` and `q_lo = 9223372036854775808`. Nothing failed. If your code takes `q_lo` and ignores `q_hi` --- which is exactly what a two-word return invites, since you only wanted one number --- you have a wrong answer with no indication anywhere that it is wrong. **`divw` fails loudly on an overflowing quotient; `divmodw` fails silently.** For money, take the loud one.

There is a second, smaller reason. PuyaPy rejects `_` as a variable name outright --- `error: _ is not currently supported as a variable name` --- so a four-word return has to be unpacked into four real names, and three of them are noise you now have to read past. The example uses `_qh`, `_rh`, `_rl`; a leading underscore inside a real identifier is fine, a bare underscore is not.

Reach for `divmodw` when you genuinely want one of the three things it offers: a divisor wider than sixty-four bits, the remainder, or a deliberately 128-bit quotient. Reach for `mulw` and `divw` for everything else.

Example: A reusable multiply-then-divide {#ex:mul-div}

<!-- finder: compute (a * b) / c safely as a reusable subroutine -->

{{include-ex:mul-div}}

The load-bearing three lines are the whole body of `mul_div`, and this subroutine is the single most reusable thing in the chapter. Write it once, call it everywhere a proportion is computed, and the ordering question --- multiply first or divide first? --- stops being a decision you can get wrong in a hurry. It multiplies first, so nothing rounds early; it goes through 128 bits, so nothing overflows in between; and it aborts rather than truncating if the answer genuinely will not fit.

`op.addw(a, b)` exists too, returning a carry and a sum, but there is no add-with-carry opcode to build on it --- so there is no clean way to accumulate a running 128-bit total this way. When you need one, the answer is `BigUInt`, and it arrives in the pricing-maths chapter later in the book, because the AMM is the first thing that needs one.

*What this section repairs in the vesting calculator:* the overflow that fixing defect one would otherwise introduce. `total * elapsed` is fine at a million tokens and dangerous at 10^14; routing it through `mulw` and `divw` makes the size of the grant stop being a thing the contract's correctness depends on.

## Which Clock Are You Reading?
A contract has no clock. It has a set of fields, four of which a reader will mistake for one, and {{fig:four-clocks}} is the map of which is which. This section is that figure in code.

Example: The two globals that look like now {#ex:two-clocks}

<!-- finder: read the current round and the current time inside a contract -->

{{include-ex:two-clocks}}

Two load-bearing lines, and their relationship is the point. `Global.round` is the round currently being formed --- the block your transaction is going into, supplied by the ledger. `Global.latest_timestamp` is *the timestamp of the previous block*, not this one, because this one does not have a timestamp yet.

So the two never describe the same block. They are exactly one block apart, always, by construction --- not intermittently, not under load. A contract that stores `Global.round` in one method and compares it against something derived from `Global.latest_timestamp` in another is comparing measurements of two different moments, and the error is small, constant, and permanent.

The practical rule is short: **use `Global.round` for "now" and denominate durations in rounds.** A round is roughly two and three-quarter seconds, and *roughly* is doing real work in that sentence --- the figure has moved measurably over the chain's history, and dynamic round timing has been in the consensus parameters since v39, so a schedule written in rounds and converted from days at deployment is a schedule whose end date drifts. That is usually the right trade, because the alternative drifts in a worse way.

Example: A deadline in wall-clock time {#ex:deadline-timestamp}

<!-- finder: set and check a deadline using block timestamps -->

{{include-ex:deadline-timestamp}}

The load-bearing line is `assert Global.latest_timestamp < self.closes_at.value, "auction closed"`. Timestamps are the right choice when the deadline is a real-world commitment --- an auction that a poster says closes at noon on Friday must close near noon on Friday, and a round count will not promise that.

What you are trusting when you use them is worth stating precisely, because it is narrower than "the block has the right time." Consensus checks only that each block's timestamp is at least the previous block's and at most twenty-five seconds beyond it. That is a purely *relative* rule; no part of the protocol compares a block timestamp against real-world time. Honest proposers clamp to their own wall clock, so in practice the chain tracks reality closely, but what you are guaranteed is monotonicity and a bounded step, not accuracy. Do not build anything that needs sub-minute precision on it.

Note the comparison operator, too. `<` rather than `<=` means a bid arriving in the block whose timestamp equals the closing time is rejected. Either choice is defensible; the one thing that is not defensible is not having decided.

Example: The one safe use of `Txn.last_valid` {#ex:expiry-upper-bound}

<!-- finder: make a contract stop working after a chosen round -->

{{include-ex:expiry-upper-bound}}

The load-bearing line is `assert Txn.last_valid < self.sunset_round.value, "window overruns"`, and the distinction it embodies is the one this section exists to teach. `Txn.last_valid` is a number the caller chose. **Asserting an upper bound on a number the caller chose is safe, because a caller who picks a bad one only hurts themselves.** Reading that same number as a measurement is not, because a caller who picks a bad one profits.

Here the contract wants a guarantee that no transaction can commit after the sunset round. The caller's own last-valid field is the only thing that expresses it, since `Global.round` at execution time tells you nothing about the range the transaction was eligible for. Constraining it is exactly the right move. LogicSigs use the same pattern to expire.

Example: The unsafe use of the same field {#ex:last-valid-clock-wrong}

<!-- finder: see how using Txn.last_valid as a clock gets exploited -->

{{include-ex:last-valid-clock-wrong}}

`elapsed = Txn.last_valid - self.start.value` is the calculator's fourth defect, isolated. A transaction's validity window may be up to a thousand rounds wide, and the caller sets both ends. Setting `last_valid` a thousand rounds in the future costs nothing, requires no privilege, and is not detectable as unusual --- plenty of honest wallets pad the window. Every call therefore reports up to forty-six minutes more elapsed time than has elapsed, and a schedule can be drained at `total × 1000 / duration` per transaction.

*Predict: the same contract, with `Txn.first_valid` substituted for `Txn.last_valid`. Is that safe? Say what a caller can and cannot do to the first-valid round.*

`Txn.first_valid` is not free to inflate --- a transaction whose first-valid round is in the future is not accepted yet, so a caller cannot claim to be further along than they are. They can only claim to be *behind*, which costs them. That makes it safe in the narrow sense of being unprofitable to lie about, and still the wrong field, because it is a lower bound rather than a measurement. `Global.round` is the measurement. Use it.

*What this section repairs in the vesting calculator:* defect four. `Txn.last_valid` becomes `Global.round`, which no caller can move, and the entire class of attack disappears with it.

## Reading the Past, and the Randomness It Is Not
There is one more clock-shaped thing: `op.Block`, which reads fields of a block that has already been committed. It is the natural place to reach when you want a timestamp older than the previous block, and it is the natural place to reach when you want randomness. It is right for the first and irreparably wrong for the second.

Example: Reading a block that has already happened {#ex:past-block}

<!-- finder: read the timestamp of an earlier block from inside a contract -->

{{include-ex:past-block}}

The load-bearing line is `op.Block.blk_timestamp(Txn.first_valid - UInt64(1))`, and the argument is where every mistake lives. **The readable window is anchored to the transaction's own validity range, not to the current round.** You may read rounds from `last_valid - 1001` up to `first_valid - 1`, which means the number of readable rounds is `1001 - (last_valid - first_valid)`. A transaction using the full thousand-round window can read exactly one block: `first_valid - 1`.

Work one instance to make the shape concrete. A transaction with `first_valid = 5000` and `last_valid = 5010` --- a ten-round window, which is AlgoKit Utils's default against every network but LocalNet --- may read rounds 4009 through 4999 inclusive: 991 of them, which is `1001 - 10`. Widen the window and the readable range shrinks from the bottom, one round for one round, until at a thousand rounds it is a single block. There is a floor as well: round 0 is never readable, so on a chain younger than about a thousand rounds the window starts at 1 rather than going negative.

The consequence is a trap, and it is not the trap it looks like. `blk_timestamp(Global.round - 1)` compiles, and it reads like the obvious way to ask for the block just gone. It does not work on LocalNet and then break in production; **it does not work at all, anywhere, on the very first call.** The upper bound of the window is `first_valid - 1`, and `first_valid` comes from algod's `last-round` --- the last round already *committed* when the transaction was built. A transaction built at that moment cannot be included before the next round, so `Global.round` is at least `first_valid + 1`, which puts `Global.round - 1` at `first_valid` or later: at minimum one round above the ceiling, every single time. The call fails with `round <n> is not available. It's outside [<lo>-<hi>]` on LocalNet and MainNet alike.

That is a better bug than the intermittent one, because it is honest. The window does not move with the chain at all --- it is pinned to two numbers the caller wrote down before sending, and `Global.round` is not one of them. Any expression involving `Global.round` is the wrong shape for this argument.

Write `Txn.first_valid - 1` and it is correct by construction, because the window is defined in terms of that field. Or, when all you wanted was a timestamp, use `Txn.first_valid_time` --- the second method in the example does exactly what the first does, without the lookup and without the opportunity to get the argument wrong. It never fails the window. What it gives you is the timestamp of the block before the transaction became valid, which is a *lower bound on when the transaction was built* and up to forty-six minutes stale. Honest framing matters here: it is a fine "not before" and a bad "now."

Example: Committing to a future round {#ex:commit-reveal}

<!-- finder: build a lottery whose outcome nobody can predict when they enter -->

{{include-ex:commit-reveal}}

The load-bearing pair is `self.target_round.value = Global.round + lead` in one method and `Global.round > self.target_round.value` in another, with entries refused in between. This is the commit-reveal shape, and it is the only shape in which on-chain randomness is sound: **the value everybody's outcome depends on must not exist yet at the moment they commit.**

The example commits to a round at least sixteen ahead and then refuses new entrants. That ordering is the entire security property, and the invariant behind it is one sentence: **the target round must not yet exist when the last entry is accepted.** Break it --- let entries continue after the round is picked, or pick a round already in the past --- and someone can act on information the mechanism assumed they did not have.

The example stops at establishing the target round and does not itself fetch a random value, because there is no safe way to fetch one from the block. What goes in that slot is the ARC-21 randomness beacon, an on-chain oracle you call with the round you committed to. Be careful about what is specification and what is deployment: **ARC-21 itself defines only two mandatory methods, `get(uint64,byte[])byte[]` and `must_get(uint64,byte[])byte[]` --- plus two optional `*_closest` search variants --- and says nothing about how often values are published, how long they are kept, or how many bytes come back.** Those are properties of the beacon the Foundation actually runs --- which publishes on rounds that are multiples of eight and retains roughly the last fifteen hundred rounds --- and a different deployment could choose differently. Read the deployed contract's own documentation for the numbers; read the ARC for the interface.

That is why `commit` in the example rounds its target *up* to the next multiple of eight rather than taking `Global.round + lead` as it stands. Seven target rounds out of eight have no published value, and a draw committed to one of them is stuck permanently --- there is nothing to read and no way to re-commit. Rounding up rather than down is deliberate too: it can only lengthen the lead, so the security property the lead is there to provide survives the adjustment. The security rule itself is unchanged: commit publicly to a future round before that round's value exists, then read it.

Example: Randomness from the block, and why it fails {#ex:block-seed-wrong}

<!-- finder: see why a block seed cannot be used as a source of randomness -->

{{include-ex:block-seed-wrong}}

`op.Block.blk_seed` returns the block's VRF seed. The usual objection is that a block proposer could choose a favourable one, and that objection is actually wrong: the seed is a verifiable random function of the previous seed under the proposer's key, so a proposer can compute it but cannot select it. They can only choose whether to publish the block at all, and declining costs them the block reward.

The fatal problem is a different one, and it needs no proposer at all. Look at the window from the first example in this section: every round a contract can read is at or before `first_valid - 1`. That round is already committed and public *at the moment the caller builds the transaction*. So the attacker computes the contract's answer off-chain, sees whether they win, and submits only if they do --- repeating for free until they like the result. There is no way to arrange the code that fixes this, because the input is public before the transaction exists. **Anything readable by `op.Block` is known to the caller in advance. It is not a secret and cannot be made into one.**

*What this section repairs in the vesting calculator:* nothing, and it is the only section that repairs nothing. It is here because the calculator's fourth defect is the beginner's version of a mistake this section is the advanced version of --- trusting a number the caller had a hand in --- and because the vesting project's successors reach for both `op.Block` and randomness within two chapters.

## Schedules
Everything so far assembles into the thing the next project actually needs: a function from "now" to "how much has been released."

Example: Linear release between two rounds {#ex:linear-vesting}

<!-- finder: compute how much of a grant has vested at a given round -->

{{include-ex:linear-vesting}}

The load-bearing pair is `hi, lo = op.mulw(total, now - start)` followed by `return op.divw(hi, lo, end - start)` --- which is {{ex:mul-div}}'s `mul_div` written out in place, because one example file does not import another. The two guards above it are load-bearing twice each. `if now <= start: return UInt64(0)` is the answer to the question and also the thing that stops `now - start` from going negative. `if now >= end: return total` is the answer to the question and also --- together with the first guard and `configure`'s `end > start` --- the reason `end - start` can never be zero on any reachable path. Three guards, each doing a job the reader can see and a second job in this chapter's currency.

The obvious way to write that pair is `(total * (now - start)) // (end - start)`, and it is the form you will see everywhere, including in this book's own Exercise 1. It is correct on the ordering question and wrong on the width one. On the ninety-day schedule from the opening, the narrow multiply overflows for any `total` at or above 6,518,286,428,268 --- about six and a half million tokens at six decimals, an ordinary grant --- and it overflows only in the back half of the schedule, so a contract configured with one will work, pay out for weeks, and then abort permanently on every call for the rest of the term. **A proportion whose numerator is a token amount is a wide multiply. There is no size of grant at which the narrow form becomes the right answer; there is only a size at which you have not noticed yet.**

*Predict: floor division pays the beneficiary slightly less than the exact fraction. Suppose you decided that was mean and rounded up instead, by adding `end - start - 1` to the product before dividing. Name the party who is worse off after a year of claims, and say by roughly how much.*

The direction it rounds is a decision, not an accident. `divw` floors, exactly as `//` does, so the beneficiary is paid slightly less than the exact fraction and the difference stays in the contract. That is the right way round, and the argument is worth having explicitly because "round in the user's favour" sounds like the generous choice.

Claims are unbounded. If each claim rounds up, each claim over-pays by up to one unit, and a caller who claims once per round for a ninety-day schedule extracts millions of units the grant never contained. If each claim rounds down, the contract retains dust, and the `now >= end` branch pays out the exact total at the end regardless of what was claimed before --- so the dust comes back. **When a division decides how much leaves the contract, floor it.** That rule is going to be repeated in every project chapter that touches money.

Example: The same schedule with the operations reversed {#ex:linear-vesting-wrong}

<!-- finder: see why dividing before multiplying pays nothing -->

{{include-ex:linear-vesting-wrong}}

`((now - start) // (end - start)) * total` is the calculator's first defect as a subroutine. Its unit test is the clearest statement of the problem in the chapter: at one third of the way through a ninety-day schedule the correct form returns 333,333 and this one returns 0, and this one keeps returning 0 until the very last round.

Example: A cliff before the linear part {#ex:vesting-cliff}

<!-- finder: add a cliff to a linear vesting schedule -->

{{include-ex:vesting-cliff}}

The load-bearing line is `if now < cliff: return UInt64(0)` --- `<`, not `<=`, so that arriving *at* the cliff round releases rather than one round later. Off-by-one errors in a comparison are ordinary; off-by-one errors in a comparison that gates a year of somebody's compensation get noticed.

There is a second decision in this example and it is easy to miss, because both answers are defensible and the code only says which one it took. The linear term measures from `start`, not from `cliff`, so reaching the cliff releases a *lump sum* covering the whole period since the grant began, and vesting continues linearly from there. That is the standard meaning in employee equity. Measuring from `cliff` instead gives a schedule that pays nothing at the cliff and then ramps, which is a different deal for the same three parameters. Keep `start` and `cliff` as separate parameters, decide which you mean, and say so in the docstring --- because nothing in the arithmetic will tell a reader which one you chose.

Example: One call per cooldown period {#ex:rate-limit}

<!-- finder: stop an account from calling a method too often -->

{{include-ex:rate-limit}}

The load-bearing line is `assert Global.round >= previous + UInt64(COOLDOWN_ROUNDS), "cooling"`, and it is a schedule wearing different clothes: a per-account release curve with one step in it. Three details are deliberate. The cooldown is a module constant rather than a method argument, because a caller who can pass their own cooldown can pass zero. The addition is on the right-hand side rather than `Global.round - COOLDOWN_ROUNDS` on the left, which would be the section-one underflow on any chain younger than the cooldown itself.

And the guard sits *inside* `if seen`, which is the detail worth slowing down for. `maybe` returns a value and a flag, and the tempting move is to keep the flag for the funding check and let the absent value fall through as zero. Do that and a first-time caller is compared against a `previous` of zero --- indistinguishable from an account that really did call at round zero --- so on any chain younger than the cooldown, every new account is refused until round 100 with the message `cooling`, which is a lie. **A sentinel is only safe when it cannot collide with a real value, and round zero is a real value.** Branching on the flag costs one `else` and removes the question entirely.

*What this section repairs in the vesting calculator:* defect one, and the shape of everything the next two chapters build. Multiply first, divide last, guard both ends, and floor toward the contract.

## The Mini-Build, Fixed
Four defects, four corrections. The full corrected contract is on disk at `examples/ch05_numbers_time/vesting_calc_fixed.py` and compiles in CI; here is the spine of the diff, with everything unchanged elided.

```diff
     def configure(self, total: UInt64, start: UInt64, end: UInt64) -> None:
+        assert end > start, "schedule must have positive length"
     def vested_now(self) -> UInt64:
-        now = Txn.last_valid
-        elapsed = now - self.start.value
-        span = self.end.value - self.start.value
-        fraction = elapsed // span
+        now = Global.round
+        if now <= self.start.value:
+            return UInt64(0)
         if now >= self.end.value:
             return self.total.value
-        return fraction * self.total.value
+        hi, lo = op.mulw(self.total.value, now - self.start.value)
+        return op.divw(hi, lo, self.end.value - self.start.value)
```

Read the two unmarked context lines in the middle carefully, because they are the most interesting thing in the diff. `if now >= self.end.value: return self.total.value` is not new and is not modified. It is character-for-character what the broken version had. All that happened to it is that the arithmetic which used to sit above it now sits below it, and that alone retires the `/ 0`. **The guard was never wrong; it was in the wrong place relative to the thing it needed to guard.** A diff that shows a fix as two lines moving is a fix worth remembering, because reviewers read added and deleted lines and skim the unchanged ones.

Seven things are elided from that diff and named here so nothing arrives unannounced. The import line gains `op` and loses nothing --- reconstruct the fixed contract from the diff alone without touching the imports and it will not compile, which is the ordinary fate of every diff that shows a body and hides a header. `__init__` is unchanged and is where all four of the `self.` names the diff reads through are bound: `total`, `start`, `end`, and `configured`. `configure` keeps its plain `@arc4.abimethod` decorator and both of its existing guards, the creator-only check and the init-once flag, and gains only the third one shown, which goes *after* both of them rather than at the top of the method where the diff's framing might suggest. `vested_now` keeps its opening `assert self.configured.value, "not configured"`, which the diff never touches and which is doing real work --- without it the whole method reads zeros out of unset global state and reports a perfectly-formed answer about a grant that does not exist. `vested_now` and `schedule` both keep `@arc4.abimethod(readonly=True)`. `schedule` is unchanged in full. And the docstring loses one sentence, the one apologising for returning the wrong number.

Configure the fixed contract with the same ninety-day schedule and ask it the same question. This is an **on-chain run** again, same LocalNet, same typed client:

```python
>>> calc.send.configure(args=(1_000_000, 0, 2_830_000))
>>> calc.send.vested_now().abi_return   # one third of the way through
333333
>>> calc.send.vested_now().abi_return   # eighty-nine days in
988888
>>> calc.send.vested_now().abi_return   # day ninety and after
1000000
```

**Correction one: multiply before dividing, through 128 bits.** The two-line replacement is {{ex:mul-div}} inlined rather than called, which is a choice worth naming: the subroutine is the better habit and the inline version is here so that the diff shows the mechanism rather than hiding it behind a name. Either is correct. What is not correct is the original ordering, at any width.

`op.divw` can still abort, and it is worth knowing exactly when, since the contract has no guard against it. It aborts when the quotient will not fit in sixty-four bits, which needs `end - start` to be no greater than the high word of `total × (now - start)`. Since `now - start` is always less than `end - start` on this branch, the quotient is always less than `total`, which is a `UInt64`. It cannot abort here. That argument is the reason no fifth guard was added, and it is the kind of argument worth writing in a comment when you make it.

**Correction two: guard the divisor where it is established.** `assert end > start` in `configure` is one line in the method that sets the value, and it retires the `/ 0` permanently --- including the specific catastrophe where an init-once contract configured with a zero-length schedule becomes an uncallable object holding a grant. Putting the same check in `vested_now` would have made the failure polite instead of retiring it. Note that the diff fixes this defect twice over: the assertion retires it at the source, and moving the division below the `now >= end` branch would have caught the same case at the point of use. Both were worth doing, and only one of them is a line anybody added.

**Correction three: guard the subtraction with the branch that was already needed.** `if now <= self.start.value: return UInt64(0)` is not a new concept bolted on; it is the answer to "what has vested before the schedule starts", which the broken version never answered. That it also makes `now - start` safe is the pattern from the schedules section: the guard that makes the arithmetic legal is usually a guard the specification wanted anyway. When it is not --- when you find yourself adding an assertion purely to keep the AVM happy --- that is a sign the expression should be restructured rather than defended.

**Correction four: read the clock the caller cannot move.** `Txn.last_valid` becomes `Global.round`. This is the only correction of the four that is a security fix rather than a correctness fix, and it is the only one that could not have been caught by any test of the arithmetic, because the arithmetic was never wrong. It was reading a number that a caller supplies and the contract treated as a measurement.

Two rules generalize past this chapter, and both are short enough to carry out of it.

The first is the arithmetic one: **a proportion is a multiplication that has not been divided yet.** Take that literally and the rest follows without being memorised --- multiply before you divide, route the product through 128 bits when it might not fit, floor the division toward the contract, and guard every divisor and every subtraction where the value is established rather than where it is used.

The second is the one correction four is an instance of: **every field of the incoming transaction is an input, not an observation.** `Txn.last_valid`, `Txn.first_valid`, `Txn.fee`, `Txn.note`, the lot. You may assert bounds on them, and you may reject a transaction whose fields you dislike. You may not treat their values as facts about the world. The ledger's own fields --- `Global.round`, `Global.latest_timestamp`, `Global.current_application_address` --- are the observations, and there are not many of them, which is the point.

## What Bites People Here
Five, in the order you are likely to meet them: one about rounding, two about arithmetic that stops, one about clocks, and one about randomness.

::: {.gotcha #divide-last topic="Arithmetic and time" title="Dividing before multiplying silently returns zero"}
`(a // b) * c` is integer division first, so it returns zero for every input where `a < b` --- which for a proportion means every input except the last one. It is the transcription every spreadsheet formula invites and it produces a contract that pays nothing at all until the moment it pays everything. Write `(a * c) // b` instead. Doing so moves the risk from rounding to overflow, which is a trade you want, because overflow aborts loudly and rounding-to-zero does not: route the product through `op.mulw` and `op.divw` and both problems are gone at once. No test that checks only the endpoints of a schedule will catch this, because the endpoints are the two points the wrong form gets right.
:::

::: {.gotcha #arithmetic-aborts topic="Arithmetic and time" title="Overflow and underflow end the transaction, they do not wrap"}
On the AVM, `a + b` past 2^64-1 reports `+ overflowed`, `a - b` with `b > a` reports `- would result negative`, and `a // 0` reports `/ 0` (while `a % 0` reports `% 0`). None of them wrap, none of them return a sentinel, and none of them are catchable --- the transaction is discarded, so there is no state left to inspect and no assertion of yours to fire. The consequence is denial of service, not theft: a contract holding funds can become permanently uncallable on an input path nobody tested, especially if the offending value was set by an init-once method. Test the boundaries, not the middle. And note that the wording differs between the chain and `algopy_testing`, which reports `OverflowError: + overflows` and `ArithmeticError: - underflows` --- never quote one as the other in a runbook.
:::

::: {.gotcha #guard-where-established topic="Arithmetic and time" title="Guard a divisor where it is set, not where it is used"}
A division-by-zero guard placed at the division site has to be repeated at every division site, and the day somebody adds a third one it will not be. Put it in the method that establishes the value --- `assert shares > UInt64(0)` in the setter, `assert end > start` in `configure` --- and it holds for every use forever, including uses that do not exist yet. This matters more than it sounds because in practice the divisor is usually a *difference* (`end - start`, `total - claimed`), so one assertion about the ordering of two parameters retires both the `/ 0` and the `- would result negative` in a single line. PuyaPy warns about a literal `// UInt64(0)` and says nothing at all about a zero that arrives in a variable, which is every zero that has ever caused an incident.
:::

::: {.gotcha #txn-last-valid-not-a-clock topic="Arithmetic and time" title="Txn.last_valid is a number the caller chose"}
Reading `Txn.last_valid` as "now" hands the caller control of your clock: they may set it up to a thousand rounds beyond the current round, for free, on every call, and nothing about such a transaction looks unusual. Against a time-based release schedule that is roughly forty-six minutes of unearned progress per transaction, repeatable as fast as fees can be paid. It survives testing for the opposite of the obvious reason: AlgoKit Utils widens the validity window to the protocol maximum of a thousand rounds on LocalNet, so your tests already run the attack at full strength and pass anyway, because they assert that a call returned rather than that it returned the right number. The safe use of the field is the opposite direction: `assert Txn.last_valid <= EXPIRY` bounds a number the caller chose, which is fine, because a caller who chooses badly only hurts themselves. Use `Global.round` for "now", always --- and remember that `Global.latest_timestamp` is the *previous* block's timestamp, so the two are never describing the same block.
:::

::: {.gotcha #block-seed-is-public topic="Arithmetic and time" title="Block seeds are already public when the caller builds the transaction"}
`op.Block` can only read rounds at or before `Txn.first_valid - 1`, and that round is committed and public before the transaction exists --- so a caller can compute your contract's "random" answer off-chain, check whether they win, and submit only when they do, for free, as many times as they like. The common objection to `blk_seed` --- that a proposer might choose a favourable seed --- is actually false, since the seed is a VRF output the proposer can compute but not select. The real problem is worse and needs no proposer at all, and no arrangement of the code fixes it. Use a commit-reveal shape against the ARC-21 randomness beacon: commit publicly to a future round, close entries, then read that round's value once it exists. Note also that the readable window is `1001 - (last_valid - first_valid)` rounds wide, so a transaction with a full validity window can read exactly one block --- and that `blk_timestamp(Global.round - 1)` never works at all. The readable window ends at `first_valid - 1`, and `first_valid` is the last round already committed when the transaction was built, so `Global.round - 1` is always at least one round too new. Reach for `Txn.first_valid - 1` instead.
:::

## Retrieval
Answer these from memory before moving on. Four of them reach back into earlier chapters on purpose.

1. Why does `(elapsed // duration) * total` return zero for almost every input, and what is the correct ordering?
2. What does the AVM do when a subtraction would go below zero, and what exactly does it say? What does the unit-test emulator say instead?
3. `op.divw` and `op.divmodw` both divide a 128-bit numerator. What happens to each when the quotient will not fit in sixty-four bits?
4. Name the four values a contract can mistake for "now". Which one is the answer, and what is each of the other three actually measuring?
5. A contract reads `op.Block.blk_timestamp(Global.round - 1)` and the call fails on the very first attempt, on LocalNet and MainNet alike. Say what the two ends of the readable window are, and why no value of `Global.round` can ever land inside it.
6. When a division decides how much money leaves a contract, which way should it round, and what is the argument?
7. Where does a division-by-zero guard belong, and why is that usually the same line that prevents an underflow? *(From {{ch:boxes}})* The guard you wrote there --- `balance >= min_balance + cost` rather than `balance - min_balance >= cost` --- is the same rule. Say which of this chapter's failure modes the second form produces.
8. *(From {{ch:boxes}})* A `BoxMap` keyed by a counter charges the application account per box. Which of this chapter's failure modes does an unguarded box-cost subtraction produce, and what would the caller see?
9. *(From {{ch:state}})* An init-once configuration method sets a value this chapter's arithmetic will later divide by. What is the worst case, and why is it worse than an ordinary failed transaction?
10. *(From {{ch:testing}})* A test asserts that a method raises `OverflowError`. Is that test asserting anything about what a user on MainNet will see?

## Exercises
1. **(Trace)** A grant of 250,000 tokens vests linearly from round 40,000,000 to round 42,592,000. Work out what `vested_now` returns at round 41,296,000 --- exactly half way --- for each of three implementations, and show the arithmetic.

   The three: (i) `((now - start) // (end - start)) * total`; (ii) `(total * (now - start)) // (end - start)`; (iii) the `mulw`/`divw` form from {{ex:mul-div}}.

   Two of the three agree. Say which two and what the third returns. Then change one number: the grant is now 250 million tokens of an ASA with six decimals, so `total` is 250,000,000,000,000. Recompute all three. One of them now aborts --- say which, quote the message it produces, and say whether the abort is better or worse than what the implementation that does not abort returns.

2. **(Parsons + Analyze)** Below are six statements. Four of them form the body of a `claim` method that pays out newly vested tokens and records what it paid; two do not belong. The decorator and signature are given, and `self.claimed` is a `GlobalState(UInt64)` holding the running total already paid.

   ```python
   @arc4.abimethod
   def claim(self) -> UInt64:
       ...
   ```

   The statements: (a) `earned = vested(self.total.value, self.start.value, self.end.value, Global.round)`; (b) `assert earned > self.claimed.value, "nothing new has vested"`; (c) `payable = earned - self.claimed.value`; (d) `self.claimed.value = earned`; (e) `earned = vested(self.total.value, self.start.value, self.end.value, Txn.last_valid)`; (f) `payable = self.claimed.value - earned`.

   Select the four that belong and order them. Both rejects fail, and they fail in interestingly different ways: one of them fails on the very first honest call, loudly, with a message from the AVM rather than from the contract; the other never fails at all and is the more expensive of the two.

   For each reject, say what the caller sees and who ends up paying for it. Then answer the part that is not about the rejects: statement (b) is an assertion rather than an early return. Say what changes if you make it `if earned <= self.claimed.value: return UInt64(0)` instead, name one caller for whom the assertion is better and one for whom the early return is, and say which you would ship.

3. **(Debug)** A staking contract lets an account deposit, and computes its share of a reward pool as `(pool * my_stake) // total_stake`. It works for months. Then one morning every call to `share_of` fails with `logic eval error: / 0`, and the contract holds real money that nobody can now withdraw.

   Before working anything else out, write down what must have happened to `total_stake` and say whether an attacker was needed to make it happen.

   Then answer three things. First: name the sequence of ordinary user actions that produces this state, with no attacker involved. Second: the obvious fix is `assert total_stake > UInt64(0)` at the top of `share_of` --- say precisely what that fixes and what it leaves broken, because it does not fix the thing the users care about. Third: give a fix that leaves the contract usable in the state that broke it, and say which of this chapter's two rules about guard placement you had to apply.

4. **(Compare)** You are writing a subscription contract: an account pays once and gets access for thirty days. Compare three ways of storing and checking the expiry, on four axes --- what a caller can manipulate, what happens if round timing changes, what a user sees when they check their remaining time, and what breaks if the contract is paused for a week.

   The three: (i) store `Global.round + 942_545` and compare against `Global.round`; (ii) store `Global.latest_timestamp + 2_592_000` and compare against `Global.latest_timestamp`; (iii) store `Txn.last_valid + 942_545` and compare against `Global.round`.

   One of the three is disqualified outright --- name it and say by what. Of the remaining two, neither is strictly better; say which axis decides between them, and give a concrete product requirement that would flip your answer.

5. **(Extend)** Extend {{ex:commit-reveal}} so that it actually draws a winner, using the ARC-21 randomness beacon rather than the block seed. You will hit a problem this chapter has not solved: calling another application from inside your contract is {{ch:patterns}}'s material, so write the beacon call as a comment describing exactly what you would send and what you expect back.

   Write down three things the contract must check that {{ex:commit-reveal}} does not check yet, and for each one, name the specific thing that goes wrong if you skip it. At least one of your three should be about the beacon's retention window rather than about randomness.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can write a proportion on the AVM without a float, in the ordering that does not round to zero, and route it through `op.mulw` and `op.divw` when the product might not fit in sixty-four bits --- and say why `op.divmodw` is the more dangerous choice for the same job.
- [ ] I can name every arithmetic operation that ends a transaction, quote what the chain says for each, say why the message in my unit test is not the message my user will see, and place the guard for each at the point the value is established rather than at the point it is used.
- [ ] I can name the four values that look like "now", say which one a contract should use, and explain why `Txn.last_valid` is safe to bound and unsafe to read.
- [ ] I can say what `op.Block` may read, compute the width of that window from a transaction's validity range, and explain in one sentence why block randomness cannot be fixed.
- [ ] I can write a linear release schedule with a cliff, defend the direction it rounds by naming what goes wrong under the other direction, and say where the dust ends up.

## Handoff: What the Vesting Project Needs
{{ch:token-vesting}} builds a real token vesting contract: a schedule per beneficiary in a box, a claim method that pays out, and a revocation path for a grant that ends early. {{tbl:numbers-handoff}} lists the examples from this chapter it leans on, and what to predict before you read it.

Table: Examples from this chapter that the vesting project depends on {#tbl:numbers-handoff}

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| {{ex:linear-vesting}} | The core release curve, one per beneficiary | The project's schedules are per beneficiary. What has to be stored per beneficiary that this example holds in three globals? |
| {{ex:mul-div}} | Every proportion the claim path computes | The grant is denominated in an ASA with decimals. Which of the two orderings survives that, and at what size does the other one abort? |
| {{ex:vesting-cliff}} | Grants with a cliff, and the guard that keeps `cliff` between `start` and `end` | Three parameters, three orderings to enforce. Write the assertions before you read them. |
| {{ex:two-clocks}} | Every method that asks what time it is | The project denominates schedules in rounds and shows the user days. Where does that conversion happen, and why not on chain? |
| {{ex:divide-by-zero}} | `configure`, which establishes every divisor the contract will ever use | The project's configure method is init-once. What is the cost of getting this wrong there, compared to getting it wrong in a method that can be called again? |
| Exercise 3 | The revocation path, which reduces a total that has already been partly claimed | You worked out how a divisor reaches zero without an attacker. Which of the project's methods could drive `end - start` or `total - claimed` to zero the same way? |
