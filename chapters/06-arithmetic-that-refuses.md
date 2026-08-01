\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# Arithmetic That Refuses: Numbers and Time

The last chapter was about paying for storage. This one is about the two things you will store: numbers, and the moments they belong to. Neither behaves the way it does anywhere else you have programmed, and both fail in the same characteristic way: not by producing a wrong answer, but by refusing to produce one at all.

That refusal is the AVM's best feature and the source of most of the confusion around it. There is no float, no negative number, and no silent wraparound. A subtraction that would go below zero does not give you a large positive number; it kills the transaction. A division by zero does not give you infinity or a `NaN`; it kills the transaction.

You have already met this once without being told what it was: Chapter 5 insisted you write a funding check as `balance >= min_balance + cost` rather than `balance - min_balance >= cost`, and offered the underflow as the reason. That was never a fact about balances; it was this chapter's one arithmetic rule arriving early. Nothing is corrupted, nothing is half-written, and no attacker walks away with anything. In exchange for a contract that cannot be tricked by arithmetic, you get a contract that can become permanently uncallable on an input path you never tested. This chapter is about seeing those paths before a user finds one.

## Releasing a Grant Over Ninety Days

A company grants an employee a million tokens, released linearly over ninety days. The contract holding that grant answers one question: how much has vested by now. The schedule was designed in a spreadsheet, where the answer is one cell --- elapsed over duration, times the grant --- and the contract's whole job is to be that cell, on a machine that refuses most of the ways of writing it.

::: {.spec title="Your commission: a calculator for a ninety-day grant"}
The contract you build this chapter holds one vesting schedule and answers one question about it. It must:

1. Take its schedule --- a total, a start round, an end round --- from the account that deployed it, exactly once
2. Report the vested amount at any moment: zero before the start, the total at or after the end, the exact linear share in between
3. Hold any grant a real token can denominate: a `total` of 10^14 must not break the arithmetic anywhere in the schedule
4. Refuse a schedule whose end is not after its start at configuration time, with a message --- never by becoming uncallable
5. Give every caller in the same round the same answer: nothing a caller writes into their own transaction may move what has vested

Five requirements, three methods. At the end of the chapter you will re-run the finished calculator against this list.
:::

Requirements two and three have worked figures attached, and both matter later: the exact linear share means a third of the way through a million-token grant is 333,333, not zero, and 10^14 is what a hundred million tokens of a six-decimal ASA comes to.

By the end of this chapter you will be able to:

- Express a rate, a percentage, or a fraction without a float, and say which of the two orderings of a multiply-and-divide is the one that works
- Predict which arithmetic expressions abort the transaction, quote what the chain says when they do, and say why the message you see in a unit test is not the message a user will see
- Guard a division against a zero divisor and a subtraction against going negative, and place each guard where the value is *established* rather than where it is used
- Compute a product that does not fit in sixty-four bits using `op.mulw` and `op.divw`, and say why reaching for `op.divmodw` instead is the more dangerous choice
- Name the four values a contract can mistake for "now", say which one is the answer, and say what each of the other three is actually measuring
- Read a past block from inside a contract, name the exact window you are allowed to read, and get a number nobody chose by committing to a future round --- and say why the block seed itself cannot supply one no matter how carefully you use it
- Write a linear release schedule with a cliff, defend the direction it rounds, and say who gets the dust

## The Calculator, First Pass
Meeting that commission takes three things the AVM does not have.

It has no fractions. There is one numeric type for ordinary work, a whole number, so a proportion is a multiplication and a division and the order you write them in decides whether the answer survives. It does not approximate either: the subtraction that measures elapsed time and the division that turns it into a fraction are each one bad input away from ending the transaction outright. And it has no clock. A contract has four fields a reader will take for "now": three of them measure something else, and one of them the caller picks.

Figure 6-1 maps the four values a contract can mistake for "now". Every one of them compiles, and three of them are wrong.

![Figure 6-1. Four values that look like "now", on one timeline. Only `Global.round` is one. `Global.latest_timestamp` is always a block behind it, `Txn.first_valid_time` can be forty-six minutes behind that, and `Txn.last_valid` is a number the caller chose.](figures/four-clocks.svg)

The distances on that diagram are what matter. `Global.latest_timestamp` sits one block behind `Global.round`, always, by construction, not sometimes. `Txn.first_valid_time` can sit a thousand rounds behind that. `Txn.last_valid` is not on the timeline at all, because it is a number the caller wrote down before sending the transaction.

The spreadsheet has all three, which is what makes transcribing its formula feel like no decision at all. Here is that commission, as anyone with the spreadsheet open would first write it --- complete, and in full.

**Example 6-1.** The vesting calculator, as first written

<!-- finder: see a linear vesting calculation that returns zero for the whole schedule -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class VestingCalculator(ARC4Contract):
    """Reports how much of a grant has vested so far.

    It only reports. Actually paying the beneficiary needs an inner
    transaction, which is the next chapter. This much you can already
    deploy, call, and watch return the wrong number.
    """

    def __init__(self) -> None:
        self.total = GlobalState(UInt64(0))
        self.start = GlobalState(UInt64(0))
        self.end = GlobalState(UInt64(0))
        self.configured = GlobalState(False)

    @arc4.abimethod
    def configure(self, total: UInt64, start: UInt64, end: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert not self.configured.value, "already configured"
        self.total.value = total
        self.start.value = start
        self.end.value = end
        self.configured.value = True

    @arc4.abimethod(readonly=True)
    def vested_now(self) -> UInt64:
        assert self.configured.value, "not configured"
        now = Txn.last_valid
        elapsed = now - self.start.value
        span = self.end.value - self.start.value
        fraction = elapsed // span
        if now >= self.end.value:
            return self.total.value
        return fraction * self.total.value

    @arc4.abimethod(readonly=True)
    def schedule(self) -> tuple[UInt64, UInt64, UInt64]:
        assert self.configured.value, "not configured"
        return self.total.value, self.start.value, self.end.value
```

Example 6-1 is complete and deployable. It compiles without a warning, it has a creator-only guard on `configure` and an init-once flag beside it, and it contains four defects: three are wrong lines, and one is a guard that was never written. The missing guard is the harder kind to find and the more common kind to ship. On the happy path --- a schedule that has started, has not finished, and was configured sensibly --- every one of them behaves, which is why all four survive review and testing.

It only reports a number; paying the beneficiary needs an inner transaction, which is Chapter 7's material. Everything wrong with it is wrong before any money moves.

*Predict: four defects. Write your four down now, in whatever words you have; you are not expected to be right yet, and one of them is genuinely hard to see. Check them against the diff at the end of the chapter.*

Deploy it, configure a ninety-day schedule, and ask it what has vested. A round is roughly two and three-quarter seconds, so ninety days is about 2,830,000 rounds, and the grant is a million tokens:

```console
$ algokit project deploy localnet
vesting-calculator 1094 deployed
```

The transcript below is an **on-chain run** against LocalNet through an algokit-utils typed client; the strings it prints are the AVM's own. The schedule is configured with `start = 0`, so "one third of the way through" means round 943,333, and a LocalNet you started this morning is a few hundred rounds old. Reproducing these exact numbers means configuring `start` and `end` relative to the round you are actually on; the arithmetic is identical either way.

```python
>>> calc.send.configure(args=(1_000_000, 0, 2_830_000))
>>> calc.send.vested_now().abi_return   # one third of the way through
0
>>> calc.send.vested_now().abi_return   # eighty-nine days in
0
>>> calc.send.vested_now().abi_return   # day ninety
1000000
```

Zero a third of the way through is surprising but not alarming; perhaps there is a cliff nobody mentioned. Zero on day eighty-nine is a support ticket, and a million on day ninety, all at once, means the "linear" schedule was a switch all along --- nothing, then everything --- and nobody wrote a switch. What was written was the spreadsheet's `(elapsed / duration) * total`, which is exactly right in the spreadsheet it came from. That is defect one. `elapsed // span` is an integer, it is `0` until `elapsed` reaches `span`, and multiplying a million by zero is a very fast way to compute zero. **Divide last.** `(total * elapsed) // span` computes the same fraction and gets it right, because the multiplication happens while the numbers are still large enough to carry information.

*Predict: `total * elapsed` at a million tokens and 2,830,000 rounds is about 2.8 trillion, which is comfortably inside sixty-four bits. Now suppose the grant were a hundred million tokens of an ASA with six decimals, so `total` is 10^14. What is `total * elapsed` then, and does it still fit?*

It does not. 10^14 x 2,830,000 is 2.83 x 10^20, about fifteen times the largest number a `UInt64` can hold, and the wide-arithmetic section below is where it gets solved. The threshold is lower than it looks: on this ninety-day schedule any `total` at or above 6,518,286,428,268, six and a half million tokens at six decimals, overflows somewhere in the back half of the schedule.

::: {.gotcha #divide-last topic="Arithmetic and time" title="Dividing before multiplying silently returns zero"}
`(a // b) * c` is integer division first, so it returns zero for every input where `a < b`, which for a proportion means every input except the last one. It is the transcription every spreadsheet formula invites and it produces a contract that pays nothing at all until the moment it pays everything. Write `(a * c) // b` instead. That moves the risk from rounding to overflow --- a trade you want, since overflow aborts loudly and rounding-to-zero does not --- and routing the product through `op.mulw` and `op.divw` removes both problems at once. No test that checks only the endpoints of a schedule will catch this, because the endpoints are the two points the wrong form gets right.
:::

Now configure the same contract with `start` and `end` the same round: a schedule of zero length, which a deployment script produces the first time somebody passes a duration of zero:

```python
>>> calc.send.configure(args=(1_000_000, 1000, 1000))
>>> calc.send.vested_now().abi_return
LogicError: Txn 7QW3...M2LP had error '/ 0' at PC 185 and Source Line 152:
    ... 10 lines of TEAL trace ...
```

The quotes hold a message that has already been trimmed for you: the node's string ran `transaction 7QW3...M2LP: logic eval error: / 0. Details: app=1094, pc=185, opcodes=...`, and `LogicError` keeps the middle and drops the wrapper on both sides.

That tail keeps going because `vested_now` is `readonly=True`, and a readonly method is answered by a simulation rather than a submission, which is also why the full traceback carries a chained line above the one printed here: `Transaction failed at transaction(s) 0 in the group.` Getting from `PC 185` or `Source Line 152` back to the line you actually wrote is Chapter 8's subject.

That is defect two, and the message is not `assert failed`. No assertion of yours fired. The AVM's own divide opcode refused, and `/ 0` is the AVM speaking, not your contract. There is nothing in the contract that could have caught it, because there is nothing in the contract that looks at `span` before dividing by it.

TEAL line 152 is the bare `/`, and the comment PuyaPy wrote three lines above it in the trace names the Python: `fraction = elapsed // span`. The contract *does* have a branch that handles a schedule already finished, `if now >= self.end.value` on the next line, and on a zero-length schedule that branch is right and would have returned the total. It never runs. `fraction = elapsed // span` was hoisted above it, the way an intermediate gets hoisted when you are tidying a method and the value is wanted by both paths. A guard cannot protect arithmetic that has already happened above it, and that is the most common way an abort survives a code review: nobody deletes the guard, somebody moves the arithmetic.

Worse than the message is what it does to the contract. `configure` is init-once, so the schedule cannot be corrected. There is no other method. The contract is now a permanently uncallable object holding a grant, and the only thing wrong with it is that two numbers were equal.

Call the same contract before its schedule starts and a third failure appears, on a schedule that is configured perfectly well:

```python
>>> calc.send.configure(args=(1_000_000, 5_000_000, 7_830_000))
>>> calc.send.vested_now().abi_return
LogicError: Txn J4KD...81XR had error '- would result negative'
at PC 173 and Source Line 138:
    ... 10 lines of TEAL trace ...
```

`elapsed = now - self.start.value` with `now` before `start` is a subtraction that would go below zero, and the AVM does not go below zero: `- would result negative` is not a rounding message but the transaction ending. For the entire period between deployment and the schedule's start, routinely months for a hiring grant, the contract answers every question with a failure.

That is three. The fourth defect has not failed yet, which is what makes it the dangerous one. `now = Txn.last_valid` reads a field of the incoming transaction, and a transaction's last-valid round is chosen by whoever built it. Any caller may set it up to a thousand rounds beyond the current round, for free, on every call. The contract believes it is reading a clock; it is reading a caller's preference, the rightmost mark on Figure 6-1 and the one that is not on the timeline at all. Against a ninety-day schedule, a thousand rounds is about forty-six minutes of vesting, claimable as many times as the attacker can pay a fee. Every one of those calls looks like an honest one, because it *is* a well-formed transaction that the network is happy to accept.

*Predict: this contract's LocalNet tests pass. Before reading on, say how far apart you think `Txn.last_valid` and `Global.round` sit on LocalNet, and what that implies about a test's chances of catching defect four.*

The natural guess is that with one transaction in flight at a time the two sit a round or two apart, so the defect barely registers. It is backwards. AlgoKit Utils defaults to a ten-round validity window against every network, and then makes a deliberate exception for LocalNet, widening it to a thousand: the protocol maximum, with the source comment *set a bigger window to avoid dead transactions*. So on LocalNet `Txn.last_valid` sits roughly nine hundred and ninety-nine rounds ahead of `Global.round`, and every test run against this contract has exercised defect four at full strength. The tests pass anyway, because they assert that a call succeeded and a number came back, never that the number matches one computed independently of the contract. **A defect that reads a caller-supplied field is not caught by exercising it. It is caught only by asserting against a figure the contract did not produce.**

Four defects. The rest of the chapter takes AVM arithmetic and AVM time apart, returning to the calculator as each fix becomes possible.

## Overflow, Underflow, and Division by Zero
**The AVM has exactly one numeric type for ordinary work, and every operation on it that cannot produce a valid value of that type stops the program instead.**

That type is `UInt64` --- a whole number from 0 to 18,446,744,073,709,551,615. There is no signed integer, no fixed-point type, and no float. There is a wider type, `BigUInt`, which the AMM's pricing maths needs and which arrives in Chapter 13; this chapter does not use it.

**Example 6-2.** A rate without a float

<!-- finder: express a percentage or a fee without floating point -->

```python
from algopy import ARC4Contract, UInt64, arc4, subroutine

# There is no float on the AVM. A rate is an integer numerator over an
# agreed denominator; 10_000 basis points is one hundred percent.
BASIS_POINTS = 10_000


@subroutine
def fee_on(amount: UInt64, fee_bps: UInt64) -> UInt64:
    return (amount * fee_bps) // UInt64(BASIS_POINTS)


class Till(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def net_of_fee(self, amount: UInt64, fee_bps: UInt64) -> UInt64:
        assert fee_bps <= UInt64(BASIS_POINTS), "fee cannot exceed 100%"
        return amount - fee_on(amount, fee_bps)

    @arc4.abimethod(readonly=True)
    def fee_only(self, amount: UInt64, fee_bps: UInt64) -> UInt64:
        assert fee_bps <= UInt64(BASIS_POINTS), "fee cannot exceed 100%"
        return fee_on(amount, fee_bps)
```

The order in `return (amount * fee_bps) // UInt64(BASIS_POINTS)` is what matters: multiply, then divide. Reverse it and every fee below one hundred percent rounds to zero, which is the calculator's first defect in miniature.

That line has a domain limit. `amount * fee_bps` is a plain sixty-four-bit multiply, so it aborts once `amount` exceeds about 1.8 x 10^15: fine for an Algo amount in microAlgo, not fine for an ASA with eighteen decimals. Example 6-10, two sections down, is the fix. Every multiply-then-divide before it carries an unwritten "provided the product fits."

`fee_on` is also the first `@subroutine` in this book, and five of this chapter's examples use one. A `@subroutine` is a plain function that PuyaPy inlines into whichever method calls it: it is not an ABI method, it has no selector, it cannot be called from off-chain, and it does not appear in the contract's ARC-4 interface at all. It exists so that a piece of arithmetic can be written once and reasoned about once. Everything a method may do, a subroutine may do, including asserting, which is why the guards in the next few examples can live inside one.

A *basis point* is one hundredth of a percent, so ten thousand of them make one. The denominator is a constant everybody agrees on rather than a property of the number, which is what "no floats" means in practice: you do not store 0.025, you store 250 and remember that the scale is ten thousand. Pick the scale once, write it down as a named constant, and never let it appear as a bare literal in an expression.

**Example 6-3.** Addition that stops at the ceiling

<!-- finder: see what happens when a uint64 addition overflows -->

```python
from algopy import ARC4Contract, UInt64, arc4

MAX_UINT64 = 18_446_744_073_709_551_615


class Ledger(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def add(self, a: UInt64, b: UInt64) -> UInt64:
        # Aborts on overflow. It does not wrap, and there is no result
        # to inspect afterwards -- the whole transaction is discarded.
        return a + b

    @arc4.abimethod(readonly=True)
    def add_checked(self, a: UInt64, b: UInt64) -> UInt64:
        # Ask the question as a comparison. `MAX_UINT64 - a` cannot
        # itself underflow, because `a` is a UInt64.
        assert b <= UInt64(MAX_UINT64) - a, "sum would overflow"
        return a + b
```

`assert b <= UInt64(MAX_UINT64) - a, "sum would overflow"` is the general shape. `a + b` on values that exceed the ceiling does not wrap to a small number the way C would; the AVM reports `+ overflowed` and the transaction ends. Since there is no result to inspect afterwards, the check has to happen before, and it has to be a comparison, because any expression that computes the overflowing sum in order to test it has already overflowed.

`MAX_UINT64 - a` cannot itself go negative, because `a` is a `UInt64` and is therefore at most `MAX_UINT64`. Writing the same idea as `a + b >= a` --- the idiom from every unsigned-wraparound language --- is not just wrong here but unreachable, because the addition aborts before the comparison runs.

**Example 6-4.** Subtraction that stops at zero

<!-- finder: see what happens when a uint64 subtraction goes below zero -->

```python
from algopy import ARC4Contract, UInt64, arc4


class Vault(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def shortfall(self, owed: UInt64, balance: UInt64) -> UInt64:
        # Aborts when the vault is solvent. There is no negative number
        # to return, so the AVM refuses to produce one.
        return owed - balance

    @arc4.abimethod(readonly=True)
    def shortfall_or_zero(self, owed: UInt64, balance: UInt64) -> UInt64:
        # Order the comparison so the subtraction only runs when it can
        # succeed. This is the shape to reach for every time.
        if owed <= balance:
            return UInt64(0)
        return owed - balance
```

`if owed <= balance: return UInt64(0)` is the same rule as above, in the other direction: ask the question as a comparison, because the subtraction that would answer it is the thing that fails.

This makes operand order a correctness concern rather than a stylistic one, because it has no analogue in most languages. `a - b` and `b - a` are not two ways of getting the same magnitude with different signs. One of them is a number and the other is the end of your transaction, and which is which depends on runtime values. Any time you find yourself writing a subtraction whose operands you cannot order at a glance, the fix is to restructure it into a comparison and two branches.

*Predict: a contract holds a user's `deposit` and a `fee`, and refunds `deposit - fee`. What is the first user experience that goes wrong, and does the user get a message or a mystery?*

**Example 6-5.** A division that cannot be given a zero

<!-- finder: guard a division against a zero divisor -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class Splitter(ARC4Contract):
    """Divides a pot between shareholders.

    The divisor is checked once, where it is established -- not at every
    site that divides by it.
    """

    def __init__(self) -> None:
        self.shares = GlobalState(UInt64(0))

    @arc4.abimethod
    def set_shares(self, shares: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.shares.value == UInt64(0), "shares already set"
        assert shares > UInt64(0), "need at least one share"
        self.shares.value = shares

    @arc4.abimethod(readonly=True)
    def per_share(self, pot: UInt64) -> UInt64:
        assert self.shares.value > UInt64(0), "not initialised"
        return pot // self.shares.value

    @arc4.abimethod(readonly=True)
    def remainder(self, pot: UInt64) -> UInt64:
        assert self.shares.value > UInt64(0), "not initialised"
        return pot % self.shares.value
```

`assert shares > UInt64(0), "need at least one share"` sits in `set_shares`, the method that *establishes* the divisor. Guarding at the point of establishment costs one assertion; guarding at the point of use costs one per division site and quietly acquires a bug the day somebody adds a third.

The other two methods carry assertions as well, and they are not the same check wearing a different hat. `assert self.shares.value > UInt64(0), "not initialised"` tests whether the contract has been configured at all, because global state reads as zero before anything writes it; the failure it prevents is calling a contract that is not ready, not configuring one badly. The two guards compare the same value against the same bound. **When two assertions share a predicate but not a purpose, the message is the only thing that tells them apart in a failure log.**

`//` on a zero divisor reports `/ 0`, and `%` on a zero divisor reports `% 0`. Those are two different messages, which matters when you are reading a failure and working out which line produced it.

**Example 6-6.** The same contract without the guard

<!-- finder: see a division-by-zero that compiles cleanly and detonates later -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class SplitterWrong(ARC4Contract):
    def __init__(self) -> None:
        self.shares = GlobalState(UInt64(0))

    @arc4.abimethod
    def set_shares(self, shares: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        self.shares.value = shares  # zero is accepted here...

    @arc4.abimethod(readonly=True)
    def per_share(self, pot: UInt64) -> UInt64:
        return pot // self.shares.value  # ...and detonates here, as `/ 0`
```

Two lines matter here, in different methods. `self.shares.value = shares` accepts a zero without comment, and `return pot // self.shares.value` detonates on it, possibly weeks later, possibly on a call made by somebody who has never heard of `set_shares`. The distance between the cause and the symptom is the cost of guarding late.

This is a stripped version rather than a one-line edit of the previous example, and it drops two other things. There is no init-once guard on `set_shares`, so the divisor can be changed under a caller at any time, and there is no `remainder` method, so the second division site --- the one that would have produced `% 0` instead of `/ 0` --- is not there to be found.

PuyaPy will warn you about `x // UInt64(0)` written literally, because it can see the constant. It says nothing about a zero that arrives in a variable, which is every zero that has ever caused a production incident.

::: {.gotcha #guard-where-established topic="Arithmetic and time" title="Guard a divisor where it is set, not where it is used"}
A division-by-zero guard placed at the division site has to be repeated at every division site, and the day somebody adds a third one it will not be. Put it in the method that establishes the value --- `assert shares > UInt64(0)` in the setter, `assert end > start` in `configure` --- and it holds for every use forever. In practice the divisor is usually a *difference* (`end - start`, `total - claimed`), so one assertion about the ordering of two parameters retires both the `/ 0` and the `- would result negative` in a single line. PuyaPy warns about a literal `// UInt64(0)` and says nothing about a zero that arrives in a variable, which is every zero that has ever caused an incident.
:::

Table 6-1 collects the messages the chain produces, because you will read them in failure output long before you can recall which is which.

: Table 6-1. What the AVM says when arithmetic refuses

| Expression | What the chain reports | What the unit-test emulator reports |
|------------------------------|----------------------------|-------------------------------|
| `a + b`, sum too large | `+ overflowed` | `OverflowError: + overflows` |
| `a * b`, product too large | `* overflowed` | `OverflowError: * overflows` |
| `a - b`, with `b > a` | `- would result negative` | `ArithmeticError: - underflows` |
| `a // b`, with `b == 0` | `/ 0` | `ZeroDivisionError` |
| `a % b`, with `b == 0` | `% 0` | `ZeroDivisionError` |
| `op.divw(...)`, zero divisor | `divw 0` | --- |
| `op.divw(...)`, quotient too large | `divw overflow: <d> <= <hi>` | --- |

**The two columns do not match, and that is not a defect in either.** `algopy_testing` raises Python exceptions with Python-shaped wording; the AVM emits its own strings from its own evaluator. Every one of the five arithmetic rows differs between them. So a test that asserts on a message is asserting on the emulator's message, and a runbook that quotes a message must say which side of the boundary it was captured on. The examples in this chapter that ship tests say so in a comment on the assertion, and this book labels every transcript as either a unit-test run or an on-chain one.

Here is the other side of that boundary. This is an **emulator run**: Example 6-4 under `algopy_testing`, in a Python REPL, with no chain anywhere near it:

```python
>>> from algopy import UInt64
>>> from algopy_testing import algopy_testing_context
>>> from examples.numbers_time.underflow_panics import Vault
>>> with algopy_testing_context():
...     Vault().shortfall(UInt64(40), UInt64(100))
ArithmeticError: - underflows
```

Same contract, same line, same defect, different vocabulary. `ArithmeticError: - underflows` is a Python exception raised by a Python reimplementation of the AVM's semantics; `- would result negative` is a string emitted by the Go evaluator that actually runs consensus. The test shipped with that example asserts `pytest.raises(ArithmeticError)`, the exception *class* and never the text, and that is the habit to copy.

The chain wraps these in context before you see them. Both sit inside the `transaction {id}: ` prefix from the previous section: an application call produces `logic eval error: / 0. Details: app=<app-id>, pc=<n>`; a LogicSig produces `rejected by logic err=/ 0. Details: pc=<n>`. The message you want is in the middle.

::: {.gotcha #arithmetic-aborts topic="Arithmetic and time" title="Overflow and underflow end the transaction, they do not wrap"}
On the AVM, `a + b` past 2^64-1 reports `+ overflowed`, `a - b` with `b > a` reports `- would result negative`, and `a // 0` reports `/ 0` (while `a % 0` reports `% 0`). None of them wrap, none of them return a sentinel, and none of them are catchable: the transaction is discarded, so there is no state left to inspect and no assertion of yours to fire. The consequence is denial of service, not theft: a contract holding funds can become permanently uncallable on an input path nobody tested, especially if the offending value was set by an init-once method. Test the boundaries, not the middle.
:::

In the calculator, these fix defects two and three. `span` is a divisor established by `configure`, so `configure` is where it gets its guard; `now - start` is a subtraction whose operands are ordered only when the schedule has started, so the schedule-has-started case gets its own branch.

## Numbers Too Big for One Word
The last section's rule has an awkward consequence. `(total * elapsed) // span` is the right expression, and multiplying first is the thing most likely to overflow. Fixing the rounding bug creates an overflow bug, and the two cannot both be fixed by rearranging the expression. (Chapter 3's Exercise 5 met the same wall from the addition side --- `bump_many`'s running total had nowhere safe to grow. This section is the debt both were waiting on.)

They are fixed by leaving sixty-four bits. The AVM has opcodes that produce and consume 128-bit intermediate values, and they exist so that a product can be too large to represent while the quotient still is not.

**Example 6-7.** A product in two halves

<!-- finder: multiply two numbers whose product does not fit in 64 bits -->

```python
from algopy import ARC4Contract, UInt64, arc4, op


class Wide(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def product_words(self, a: UInt64, b: UInt64) -> tuple[UInt64, UInt64]:
        # The full 128-bit product, as a high word and a low word.
        # `mulw` never aborts: every uint64 pair has a 128-bit product.
        hi, lo = op.mulw(a, b)
        return hi, lo

    @arc4.abimethod(readonly=True)
    def fits_in_64(self, a: UInt64, b: UInt64) -> bool:
        # A non-destructive overflow test. `a * b` would have aborted.
        hi, _lo = op.mulw(a, b)
        return hi == UInt64(0)
```

`mulw` never fails: `hi, lo = op.mulw(a, b)` multiplies two `UInt64`s into a 128-bit result and hands it back as two `UInt64`s, the high sixty-four bits and the low sixty-four. If the product did fit in sixty-four bits, `hi` is zero, which makes `fits_in_64` in the same example a complete overflow test and a cheaper one than the comparison from the previous section.

**Example 6-8.** Putting the two halves back together

<!-- finder: divide a 128-bit value by a 64-bit divisor -->

```python
from algopy import ARC4Contract, UInt64, arc4, op


class Join(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def divide_wide(self, hi: UInt64, lo: UInt64, d: UInt64) -> UInt64:
        # Not "divw 0": that string is the AVM's, and a contract that
        # borrows it makes its own guard indistinguishable from the
        # opcode failing underneath it.
        assert d != UInt64(0), "divisor must be non-zero"
        # `divw` aborts unless the quotient fits in 64 bits, and the
        # test it applies is exactly `d > hi`.
        assert d > hi, "quotient would not fit in 64 bits"
        return op.divw(hi, lo, d)
```

`return op.divw(hi, lo, d)` takes a 128-bit numerator as its two halves and a 64-bit divisor and returns a single `UInt64`. `divw` refuses in two circumstances: `divw 0` for a zero divisor, and `divw overflow: <d> <= <hi>` when the quotient would not fit in sixty-four bits.

That second message is also the test. **`divw` succeeds exactly when `d > hi`.** The check is exact rather than conservative, so `divw(5, 0, 6)` succeeds and `divw(5, 0, 5)` fails. If you can bound the high word, you can prove at design time that the division will not abort.

**Example 6-9.** The wide division that fails quietly

<!-- finder: understand why divmodw is the more dangerous wide division -->

```python
from algopy import ARC4Contract, UInt64, arc4, op


class Contrast(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def quotient_low_only(self, a: UInt64, b: UInt64, d: UInt64) -> UInt64:
        # Wrong whenever the quotient needs more than 64 bits: the high
        # word is dropped and nothing complains.
        hi, lo = op.mulw(a, b)
        _qh, ql, _rh, _rl = op.divmodw(hi, lo, UInt64(0), d)
        return ql

    @arc4.abimethod(readonly=True)
    def remainder(self, a: UInt64, b: UInt64, d: UInt64) -> UInt64:
        # The remainder is the one thing `divw` cannot give you.
        hi, lo = op.mulw(a, b)
        _qh, _ql, _rh, rl = op.divmodw(hi, lo, UInt64(0), d)
        return rl
```

`op.divmodw` divides a 128-bit numerator by a 128-bit divisor and returns *four* words: a 128-bit quotient followed by a 128-bit remainder. It looks like the more capable tool, and for the multiply-then-divide problem it is the wrong one.

*Predict: `a` is 2^63, `b` is 10, and the divisor is 2, so the true quotient is 2^63 × 5, which needs sixty-six bits. `divw` aborts. Write down what you think `divmodw` does.*

It returns, successfully, with `q_hi = 2` and `q_lo = 9223372036854775808`. Nothing failed. If your code takes `q_lo` and ignores `q_hi` --- which is what a two-word return invites, since you only wanted one number --- you have a wrong answer with no indication anywhere that it is wrong. **`divw` fails loudly on an overflowing quotient; `divmodw` fails silently.** For money, take the loud one.

There is a second, smaller reason. PuyaPy rejects `_` as a variable name outright, with `error: _ is not currently supported as a variable name`, so a four-word return has to be unpacked into four real names and three of them are noise. The example uses `_qh`, `_rh`, `_rl`; a leading underscore inside a real identifier is fine, a bare underscore is not.

Reach for `divmodw` when you genuinely want one of the three things it offers: a divisor wider than sixty-four bits, the remainder, or a deliberately 128-bit quotient. Reach for `mulw` and `divw` for everything else.

**Example 6-10.** A reusable multiply-then-divide

<!-- finder: compute (a * b) / c safely as a reusable subroutine -->

```python
from algopy import ARC4Contract, UInt64, arc4, op, subroutine


@subroutine
def mul_div(a: UInt64, b: UInt64, d: UInt64) -> UInt64:
    """`(a * b) // d`, computed through the 128-bit intermediate.

    Aborts rather than truncating: `divw` refuses unless `d > hi`.
    """
    assert d != UInt64(0), "divide by zero"
    hi, lo = op.mulw(a, b)
    return op.divw(hi, lo, d)


class Rates(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def scale(self, amount: UInt64, num: UInt64, den: UInt64) -> UInt64:
        return mul_div(amount, num, den)

    @arc4.abimethod(readonly=True)
    def share_of(self, pot: UInt64, mine: UInt64, total: UInt64) -> UInt64:
        assert mine <= total, "share exceeds the whole"
        return mul_div(pot, mine, total)
```

`mul_div` is the most reusable subroutine in the chapter. Write it once, call it everywhere a proportion is computed, and the ordering question --- multiply first or divide first? --- stops being a decision you can get wrong in a hurry. It multiplies first, so nothing rounds early; it goes through 128 bits, so nothing overflows in between; and it aborts rather than truncating if the answer will not fit.

`op.addw(a, b)` exists too, returning a carry and a sum, but there is no add-with-carry opcode to build on it, so there is no clean way to accumulate a running 128-bit total. When you need one, the answer is `BigUInt`, which arrives in Chapter 13 with the AMM.

For the calculator, this closes the overflow that fixing defect one would otherwise introduce. `total * elapsed` is fine at a million tokens and dangerous at 10^14; routing it through `mulw` and `divw` makes the size of the grant stop being a thing the contract's correctness depends on.

## Which Clock Are You Reading?
A contract has no clock. It has a set of fields, four of which a reader will mistake for one, and Figure 6-1 is the map of which is which.

**Example 6-11.** The two globals that look like now

<!-- finder: read the current round and the current time inside a contract -->

```python
from algopy import ARC4Contract, Global, UInt64, arc4


class Clocks(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def now_round(self) -> UInt64:
        # The round currently being formed. Ledger-supplied, and the
        # only thing in this file that means "now".
        return Global.round

    @arc4.abimethod(readonly=True)
    def now_timestamp(self) -> UInt64:
        # The PREVIOUS block's timestamp -- one block behind the round
        # above, roughly 2.75 seconds in the past, always.
        return Global.latest_timestamp

    @arc4.abimethod(readonly=True)
    def rounds_since(self, past: UInt64) -> UInt64:
        assert past <= Global.round, "that round has not happened yet"
        return Global.round - past
```

`Global.round` is the round currently being formed, the block your transaction is going into, supplied by the ledger. `Global.latest_timestamp` is *the timestamp of the previous block*, not this one, because this one does not have a timestamp yet.

So the two never describe the same block. They are exactly one block apart, always, by construction, not intermittently and not only under load. A contract that stores `Global.round` in one method and compares it against something derived from `Global.latest_timestamp` in another is comparing measurements of two different moments, and the error is small, constant, and permanent.

**Use `Global.round` for "now" and denominate durations in rounds.** A round takes about two and three-quarter seconds, but the figure is not fixed: it has moved measurably over the chain's history, and dynamic round timing has been a consensus parameter since v39. So a schedule written in rounds and converted from days at deployment has an end date that drifts. That is usually the right trade, because the alternative drifts worse.

**Example 6-12.** A deadline in wall-clock time

<!-- finder: set and check a deadline using block timestamps -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class Auction(ARC4Contract):
    def __init__(self) -> None:
        self.closes_at = GlobalState(UInt64(0))
        self.bids = GlobalState(UInt64(0))

    @arc4.abimethod
    def open_for(self, seconds: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.closes_at.value == UInt64(0), "already opened"
        assert seconds > UInt64(0), "empty window"
        self.closes_at.value = Global.latest_timestamp + seconds
        return self.closes_at.value

    @arc4.abimethod
    def bid(self) -> UInt64:
        assert self.closes_at.value != UInt64(0), "not open"
        # `<`, not `<=`: at exactly the deadline the auction is closed.
        assert Global.latest_timestamp < self.closes_at.value, "closed"
        self.bids.value += UInt64(1)
        return self.bids.value
```

`assert Global.latest_timestamp < self.closes_at.value, "auction closed"`. Timestamps are the right choice when the deadline is a real-world commitment: an auction that a poster says closes at noon on Friday must close near noon on Friday, and a round count will not promise that.

What you are trusting when you use them is narrower than "the block has the right time". Consensus checks only that each block's timestamp is at least the previous block's and at most twenty-five seconds beyond it. That is a purely *relative* rule; no part of the protocol compares a block timestamp against real-world time. Honest proposers clamp to their own wall clock, so in practice the chain tracks reality closely, but what you are guaranteed is monotonicity and a bounded step, not accuracy. Do not build anything that needs sub-minute precision on it.

`<` rather than `<=` means a bid arriving in the block whose timestamp equals the closing time is rejected. Either choice is defensible; what is not defensible is not having decided.

**Example 6-13.** The one safe use of `Txn.last_valid`

<!-- finder: make a contract stop working after a chosen round -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class Sunset(ARC4Contract):
    """The one safe way to touch `Txn.last_valid`.

    Constraining a caller-chosen value downward costs the caller
    something. Reading it as elapsed time pays the caller instead.
    """

    def __init__(self) -> None:
        self.sunset_round = GlobalState(UInt64(0))

    @arc4.abimethod
    def set_sunset(self, rnd: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.sunset_round.value == UInt64(0), "already set"
        assert rnd > Global.round, "sunset is already behind us"
        self.sunset_round.value = rnd

    @arc4.abimethod
    def use(self) -> UInt64:
        assert self.sunset_round.value != UInt64(0), "not configured"
        assert Global.round < self.sunset_round.value, "sunset passed"
        # Refuse a call that could still be replayed after the sunset.
        assert Txn.last_valid < self.sunset_round.value, "window overruns"
        return Global.round
```

`Txn.last_valid` is a number the caller chose, and `assert Txn.last_valid < self.sunset_round.value, "window overruns"` puts a ceiling on it. **Asserting an upper bound on a number the caller chose is safe, because a caller who picks a bad one only hurts themselves.** Reading that same number as a measurement is not, because a caller who picks a bad one profits.

Here the contract wants a guarantee that no transaction can commit after the sunset round. The caller's own last-valid field is the only thing that expresses it, since `Global.round` at execution time tells you nothing about the range the transaction was eligible for. Constraining it is the right move. LogicSigs use the same pattern to expire.

::: {.gotcha #bounding-last-valid-is-safe topic="Arithmetic and time" title="Bounding Txn.last_valid is safe, and the two time globals never describe the same block"}
The safe use of `Txn.last_valid` runs in the opposite direction from reading it: `assert Txn.last_valid < SUNSET` puts a ceiling on a number the caller chose, and a caller who chooses badly only hurts themselves --- the pattern Example 6-13 uses to guarantee no transaction can commit after a sunset round, and the same pattern LogicSigs use to expire. When a deadline is a timestamp instead, remember that `Global.latest_timestamp` is the *previous* block's timestamp, one block behind `Global.round` always and by construction, so the two never describe the same block; a contract that stores one and compares against something derived from the other carries a small, constant, permanent error.
:::

**Example 6-14.** The unsafe use of the same field

<!-- finder: see how using Txn.last_valid as a clock gets exploited -->

```python
from algopy import ARC4Contract, GlobalState, Txn, UInt64, arc4


class Drainable(ARC4Contract):
    def __init__(self) -> None:
        self.start = GlobalState(UInt64(0))

    @arc4.abimethod(readonly=True)
    def elapsed(self) -> UInt64:
        # WRONG. `Txn.last_valid` is chosen by the caller, who may set
        # it up to 1000 rounds ahead -- about 46 minutes of elapsed time
        # conjured on every call, free, and repeatable.
        return Txn.last_valid - self.start.value
```

`elapsed = Txn.last_valid - self.start.value` is the calculator's fourth defect, isolated. A transaction's validity window may be up to a thousand rounds wide, and the caller sets both ends. Setting `last_valid` a thousand rounds in the future costs nothing, requires no privilege, and is not detectable as unusual, since plenty of honest wallets pad the window. Every call therefore reports up to forty-six minutes more elapsed time than has elapsed, and a schedule can be drained at `total × 1000 / duration` per transaction.

*Predict: the same contract, with `Txn.first_valid` substituted for `Txn.last_valid`. Is that safe? Say what a caller can and cannot do to the first-valid round.*

`Txn.first_valid` is not free to inflate: a transaction whose first-valid round is in the future is not accepted yet, so a caller cannot claim to be further along than they are. They can only claim to be *behind*, which costs them. That makes it safe in the narrow sense of being unprofitable to lie about, and still the wrong field, because it is a lower bound rather than a measurement. `Global.round` is the measurement. Use it.

::: {.gotcha #txn-last-valid-not-a-clock topic="Arithmetic and time" title="Txn.last_valid is a number the caller chose"}
Reading `Txn.last_valid` as "now" hands the caller control of your clock: they may set it up to a thousand rounds beyond the current round, for free, on every call, and nothing about such a transaction looks unusual. Against a time-based release schedule that is roughly forty-six minutes of unearned progress per transaction, repeatable as fast as fees can be paid. It survives testing for the opposite of the obvious reason: AlgoKit Utils widens the validity window to the protocol maximum of a thousand rounds on LocalNet, so your tests already run the attack at full strength and pass anyway, because they assert that a call returned rather than that it returned the right number. Use `Global.round` for "now", always.
:::

In the calculator, this fixes defect four: `Txn.last_valid` becomes `Global.round`, which no caller can move, and the entire class of attack disappears with it.

## Earlier Blocks, and a Number Nobody Chose
A contract sometimes needs a fact about a block other than the one it is running in, and two needs bring people here. The first is recent history. A contract that stored `posted_at = Global.round` when an oracle price arrived wants to know, twenty minutes later, what wall-clock moment that round was, because that is how it decides whether the price has gone stale, and `Global.latest_timestamp` can only name the block before this one. `op.Block` is the tool for that, and the window it reads inside has sharp edges.

The second is randomness. A raffle, a lottery, a fair mint: each wants a number nobody chose. The shape that supplies one is commit-reveal: publish a commitment to a round that does not exist yet, close entries, then read that round's value once the round arrives. The value comes from the ARC-21 randomness beacon, not from the block.

The block is where everyone looks first, because every Algorand block carries something that looks perfect --- a 32-byte seed, different every round, produced by the consensus protocol itself rather than by any participant. If you arrive from another chain you have probably already used block data this way, because a block hash is the folk source of randomness on most of them. It cannot be made safe here, not by hashing the seed, not by mixing in the caller, not by any arrangement of the code, and the reason is the window `op.Block` reads inside.

**Example 6-15.** Reading a block that has already happened

<!-- finder: read the timestamp of an earlier block from inside a contract -->

```python
from algopy import ARC4Contract, Txn, UInt64, arc4, op


class Lookback(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def previous_timestamp(self) -> UInt64:
        # The window is anchored to the TRANSACTION's fields, not to the
        # current round: it runs to `Txn.first_valid - 1` and no further.
        # `- 1` cannot underflow in practice: algod never builds a
        # transaction with `first_valid == 0`. A hand-rolled one would.
        return op.Block.blk_timestamp(Txn.first_valid - UInt64(1))

    @arc4.abimethod(readonly=True)
    def same_thing_without_the_lookup(self) -> UInt64:
        # Identical value, and it can never fall outside the window.
        return Txn.first_valid_time
```

In `op.Block.blk_timestamp(Txn.first_valid - UInt64(1))`, the argument is where every mistake lives. **The readable window is anchored to the transaction's own validity range, not to the current round.** You may read rounds from `last_valid - 1001` up to `first_valid - 1`, so the number of readable rounds is `1001 - (last_valid - first_valid)`. A transaction using the full thousand-round window can read exactly one block: `first_valid - 1`.

A transaction with `first_valid = 5000` and `last_valid = 5010` --- a ten-round window, which is AlgoKit Utils's default against every network but LocalNet --- may read rounds 4009 through 4999 inclusive: 991 of them, which is `1001 - 10`. Widen the window and the readable range shrinks from the bottom, one round for one round, until at a thousand rounds it is a single block. There is a floor as well: round 0 is never readable, so on a chain younger than about a thousand rounds the window starts at 1 rather than going negative.

The consequence is a trap, and not the trap it looks like. `blk_timestamp(Global.round - 1)` compiles, and it reads like the obvious way to ask for the block just gone. It does not work on LocalNet and then break in production; **it does not work at all, anywhere, on the very first call.** The upper bound of the window is `first_valid - 1`, and `first_valid` comes from algod's `last-round`, the last round already *committed* when the transaction was built. A transaction built at that moment cannot be included before the next round, so `Global.round` is at least `first_valid + 1`, which puts `Global.round - 1` at `first_valid` or later: one round above the ceiling at minimum, every time. The call fails with `round <n> is not available. It's outside [<lo>-<hi>]` on LocalNet and MainNet alike.

That is a better bug than the intermittent one, because it is honest. The window does not move with the chain at all; it is pinned to two numbers the caller wrote down before sending, and `Global.round` is not one of them. Any expression involving `Global.round` is the wrong shape for this argument.

Write `Txn.first_valid - 1` and it is correct by construction, because the window is defined in terms of that field. Or, when all you wanted was a timestamp, use `Txn.first_valid_time`: the second method in the example does what the first does, without the lookup and without the opportunity to get the argument wrong. It never fails the window. What it gives you is the timestamp of the block before the transaction became valid, a *lower bound on when the transaction was built* and up to forty-six minutes stale. It is a fine "not before" and a bad "now."

::: {.gotcha #block-window-anchored-to-transaction topic="Arithmetic and time" title="The op.Block window is anchored to the transaction, not to the current round"}
The readable window is `1001 - (last_valid - first_valid)` rounds wide and ends at `Txn.first_valid - 1`, so a transaction using the full validity window can read exactly one block. `blk_timestamp(Global.round - 1)` succeeds only when `Global.round == Txn.first_valid` --- the transaction landing in its own first-valid round. Under algosdk and algokit-utils that never happens: they set `first_valid` to a round already committed, so inclusion is a round later at the earliest, and the call fails on the very first attempt, everywhere. A client that sets `first_valid` one round ahead instead gets a call that passes every test and fails whenever a transaction slips a round. Reach for `Txn.first_valid - 1`, a number the caller wrote down.
:::

**Example 6-16.** Committing to a future round

<!-- finder: build a lottery whose outcome nobody can predict when they enter -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4

# The deployed beacon publishes on multiples of eight, keeping ~1,500.
BEACON_ROUND_MODULUS = 8
MIN_LEAD_ROUNDS = 16
MAX_LEAD_ROUNDS = 1_000


class CommitReveal(ARC4Contract):
    def __init__(self) -> None:
        self.target_round = GlobalState(UInt64(0))
        self.entrants = GlobalState(UInt64(0))

    @arc4.abimethod
    def enter(self) -> UInt64:
        assert self.target_round.value == UInt64(0), "draw is committed"
        self.entrants.value += UInt64(1)
        return self.entrants.value

    @arc4.abimethod
    def commit(self, lead: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.target_round.value == UInt64(0), "already committed"
        assert lead >= UInt64(MIN_LEAD_ROUNDS), "too close to predict"
        assert lead <= UInt64(MAX_LEAD_ROUNDS), "lead is too long"
        # Round UP: that can only lengthen the lead, never shorten it.
        raw = Global.round + lead
        m = UInt64(BEACON_ROUND_MODULUS)
        self.target_round.value = raw + (m - raw % m) % m
        return self.target_round.value

    @arc4.abimethod(readonly=True)
    def ready(self) -> bool:
        committed = self.target_round.value != UInt64(0)
        return committed and Global.round > self.target_round.value
```

`self.target_round.value = Global.round + lead` in one method and `Global.round > self.target_round.value` in another, with entries refused in between, is the commit-reveal shape, and it is the only shape in which on-chain randomness is sound: **the value everybody's outcome depends on must not exist yet at the moment they commit.**

The example commits to a round at least sixteen ahead and then refuses new entrants. That ordering is the whole security property: **the target round must not yet exist when the last entry is accepted.** Break it, by letting entries continue after the round is picked or by picking a round already in the past, and someone can act on information the mechanism assumed they did not have.

The example stops at establishing the target round and does not itself fetch a random value, because there is no safe way to fetch one from the block. What goes in that slot is the ARC-21 randomness beacon, an on-chain oracle you call with the round you committed to. Specification and deployment are different things here. **ARC-21 itself defines only two mandatory methods, `get(uint64,byte[])byte[]` and `must_get(uint64,byte[])byte[]` --- plus two optional `*_closest` search variants --- and says nothing about how often values are published, how long they are kept, or how many bytes come back.** Publishing on rounds that are multiples of eight and retaining roughly the last fifteen hundred rounds are properties of the beacon the Foundation runs, and a different deployment could choose differently. Read the deployed contract's own documentation for the numbers; read the ARC for the interface.

That is why `commit` in the example rounds its target *up* to the next multiple of eight rather than taking `Global.round + lead` as it stands. The beacon the Foundation runs stores on multiples of eight and answers for every round at or below the newest stored one, so a target that is not a multiple is readable one to seven rounds late rather than never. Rounding up removes that wait, and it can only lengthen the lead, so the security property the lead provides survives the adjustment. The rule itself is unchanged: commit publicly to a future round before that round's value exists, then read it.

**Example 6-17.** Randomness from the block, and why it fails

<!-- finder: see why a block seed cannot be used as a source of randomness -->

```python
from algopy import ARC4Contract, Txn, UInt64, arc4, op


class LotteryWrong(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def draw(self, slots: UInt64) -> UInt64:
        assert slots > UInt64(0), "no slots to draw from"
        # WRONG, and not fixable by choosing a different round. Every
        # round a contract CAN read is already public when the caller
        # builds the transaction, so the caller computes the outcome
        # off-chain and submits only when it suits them.
        seed = op.Block.blk_seed(Txn.first_valid - UInt64(1))
        # `% slots` is also biased toward low values, which would matter
        # if the seed were secret. It is not, so it is the lesser flaw.
        return op.btoi(op.extract(seed, 24, 8)) % slots
```

`op.Block.blk_seed` returns the block's VRF seed. The usual objection is that a block proposer could choose a favourable one, and that objection is wrong: the seed is a verifiable random function of the previous seed under the proposer's key, so a proposer can compute it but cannot select it. They can only choose whether to publish the block at all, and declining costs them the block reward.

The fatal problem is a different one, and it needs no proposer at all. Every round a contract can read is at or before `first_valid - 1`, and that round is already committed and public *at the moment the caller builds the transaction*. So the attacker computes the contract's answer off-chain, sees whether they win, and submits only if they do, repeating for free until they like the result. There is no way to arrange the code that fixes this, because the input is public before the transaction exists. **Anything readable by `op.Block` is known to the caller in advance. It is not a secret and cannot be made into one.**

::: {.gotcha #block-seed-is-public topic="Arithmetic and time" title="Block seeds are already public when the caller builds the transaction"}
`op.Block` can only read rounds at or before `Txn.first_valid - 1`, and that round is committed and public before the transaction exists, so a caller can compute your contract's "random" answer off-chain, check whether they win, and submit only when they do, for free, as many times as they like. The common objection to `blk_seed` --- that a proposer might choose a favourable seed --- is false: the seed is a VRF output the proposer can compute but not select. The real problem needs no proposer at all, and no arrangement of the code fixes it. Use a commit-reveal shape against the ARC-21 randomness beacon: commit publicly to a future round, close entries, then read that round's value once it exists.
:::

Nothing in the calculator changes here. Its fourth defect is the beginner's version of the mistake above, trusting a number the caller had a hand in, and the vesting project's successors reach for both `op.Block` and randomness within two chapters.

## Release Curves, Cliffs, and Cooldowns
The next project needs a function from "now" to "how much has been released."

**Example 6-18.** Linear release between two rounds

<!-- finder: compute how much of a grant has vested at a given round -->

```python
from algopy import (ARC4Contract, Global, GlobalState, Txn, UInt64, arc4, op,
                    subroutine)


@subroutine
def vested(total: UInt64, start: UInt64, end: UInt64, now: UInt64) -> UInt64:
    if now <= start:
        return UInt64(0)
    if now >= end:
        return total
    # Multiply first, through 128 bits; `divw` floors toward the pool.
    hi, lo = op.mulw(total, now - start)
    return op.divw(hi, lo, end - start)


class Vesting(ARC4Contract):
    def __init__(self) -> None:
        self.total = GlobalState(UInt64(0))
        self.start = GlobalState(UInt64(0))
        self.end = GlobalState(UInt64(0))

    @arc4.abimethod
    def configure(self, total: UInt64, start: UInt64, end: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.end.value == UInt64(0), "already configured"
        assert end > start, "schedule must have positive length"
        self.total.value = total
        self.start.value = start
        self.end.value = end

    @arc4.abimethod(readonly=True)
    def vested_now(self) -> UInt64:
        assert self.end.value != UInt64(0), "not configured"
        now = Global.round
        return vested(self.total.value, self.start.value, self.end.value, now)
```

`hi, lo = op.mulw(total, now - start)` followed by `return op.divw(hi, lo, end - start)` is Example 6-10's `mul_div` written out in place, because one example file does not import another. The two guards above it each do double duty. `if now <= start: return UInt64(0)` answers the question and stops `now - start` from going negative. `if now >= end: return total` answers the question and is also --- together with the first guard and `configure`'s `end > start` --- the reason `end - start` can never be zero on any reachable path.

The obvious way to write that pair is `(total * (now - start)) // (end - start)`, the form you will see everywhere, including in Exercise 1 below. It is correct on the ordering question and wrong on the width one. On the ninety-day schedule from the opening, the narrow multiply overflows for any `total` at or above 6,518,286,428,268 --- about six and a half million tokens at six decimals, an ordinary grant --- and it overflows only in the back half of the schedule, so a contract configured with one will work, pay out for weeks, and then abort permanently on every call for the rest of the term. **A proportion whose numerator is a token amount is a wide multiply. There is no size of grant at which the narrow form becomes the right answer; there is only a size at which you have not noticed yet.**

*Predict: floor division pays the beneficiary slightly less than the exact fraction. Suppose you decided that was mean and rounded up instead, by adding `end - start - 1` to the product before dividing. Name the party who is worse off after a year of claims, and say by roughly how much.*

The direction it rounds is a decision, not an accident. `divw` floors, exactly as `//` does, so the beneficiary is paid slightly less than the exact fraction and the difference stays in the contract. That is the right way round, though "round in the user's favour" sounds like the generous choice.

Claims are unbounded. If each claim rounds up, each claim over-pays by up to one unit, and a caller who claims once per round for a ninety-day schedule extracts millions of units the grant never contained. If each claim rounds down, the contract retains dust, and the `now >= end` branch pays out the exact total at the end regardless of what was claimed before, so the dust comes back. **When a division decides how much leaves the contract, floor it.**

**Example 6-19.** The same schedule with the operations reversed

<!-- finder: see why dividing before multiplying pays nothing -->

```python
from algopy import ARC4Contract, UInt64, arc4, subroutine


@subroutine
def vested_wrong(
    total: UInt64, start: UInt64, end: UInt64, now: UInt64
) -> UInt64:
    # WRONG. The division runs first, so the ratio is 0 for the whole
    # schedule and 1 only at the very end: this pays nothing at all
    # until the last round, then everything at once. The guards are gone
    # too, so `now < start` underflows and `end == start` divides by zero.
    return ((now - start) // (end - start)) * total


class VestingWrong(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def vested_at(
        self, total: UInt64, start: UInt64, end: UInt64, now: UInt64
    ) -> UInt64:
        return vested_wrong(total, start, end, now)
```

`((now - start) // (end - start)) * total` is the calculator's first defect as a subroutine. Its unit test states the problem plainly: at one third of the way through a ninety-day schedule the correct form returns 333,333 and this one returns 0, and it keeps returning 0 until the very last round.

**Example 6-20.** A cliff before the linear part

<!-- finder: add a cliff to a linear vesting schedule -->

```python
from algopy import ARC4Contract, UInt64, arc4, op, subroutine


@subroutine
def vested_with_cliff(
    total: UInt64, start: UInt64, cliff: UInt64, end: UInt64, now: UInt64
) -> UInt64:
    # `<`, not `<=`: the grant unlocks AT the cliff round, not after it.
    if now < cliff:
        return UInt64(0)
    if now >= end:
        return total
    # The linear term measures from `start`, so arriving at the cliff
    # releases a lump sum -- the usual employee-equity meaning. Wide,
    # so a large grant cannot overflow the product.
    hi, lo = op.mulw(total, now - start)
    return op.divw(hi, lo, end - start)


class CliffVesting(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def vested_at(
        self,
        total: UInt64,
        start: UInt64,
        cliff: UInt64,
        end: UInt64,
        now: UInt64,
    ) -> UInt64:
        assert end > start, "schedule must have positive length"
        assert cliff >= start, "cliff before the schedule opens"
        assert cliff < end, "cliff at or after the schedule closes"
        return vested_with_cliff(total, start, cliff, end, now)
```

`if now < cliff: return UInt64(0)` uses `<`, not `<=`, so arriving *at* the cliff round releases rather than one round later. Off-by-one errors in a comparison are ordinary; off-by-one errors in a comparison that gates a year of somebody's compensation get noticed.

There is a second decision in this example, easy to miss because both answers are defensible and the code only says which one it took. The linear term measures from `start`, not from `cliff`, so reaching the cliff releases a *lump sum* covering the whole period since the grant began, and vesting continues linearly from there. That is the standard meaning in employee equity. Measuring from `cliff` instead gives a schedule that pays nothing at the cliff and then ramps, a different deal for the same three parameters. Keep `start` and `cliff` as separate parameters, decide which you mean, and say so in the docstring, because nothing in the arithmetic will tell a reader which one you chose.

**Example 6-21.** One call per cooldown period

<!-- finder: stop an account from calling a method too often -->

```python
from algopy import Account, ARC4Contract, BoxMap, Global, Txn, UInt64, arc4

COOLDOWN_ROUNDS = 100
# 2,500 per-box base plus 400 a byte for 1 prefix + 32 key + 8 value.
BOX_MBR = 2_500 + 400 * (1 + 32 + 8)


class RateLimited(ARC4Contract):
    def __init__(self) -> None:
        self.last_call = BoxMap(Account, UInt64, key_prefix=b"l")

    @arc4.abimethod
    def act(self) -> UInt64:
        previous, seen = self.last_call.maybe(Txn.sender)
        if seen:
            # Compare, never subtract: `Global.round - COOLDOWN_ROUNDS`
            # aborts on a chain younger than the cooldown itself.
            assert Global.round >= previous + UInt64(COOLDOWN_ROUNDS), "cooling"
        else:
            # A new box is charged to the app account, not to the caller.
            # Refuse before the write rather than abort during it.
            app = Global.current_application_address
            assert app.balance >= app.min_balance + BOX_MBR, "underfunded"
        self.last_call[Txn.sender] = Global.round
        return Global.round
```

`assert Global.round >= previous + UInt64(COOLDOWN_ROUNDS), "cooling"` is a schedule wearing different clothes: a per-account release curve with one step in it. Three details are deliberate. The cooldown is a module constant rather than a method argument, because a caller who can pass their own cooldown can pass zero. The addition is on the right-hand side rather than `Global.round - COOLDOWN_ROUNDS` on the left, which would underflow on any chain younger than the cooldown itself.

And the guard sits *inside* `if seen`. `maybe` returns a value and a flag, and the tempting move is to keep the flag for the funding check and let the absent value fall through as zero. Do that and a first-time caller is compared against a `previous` of zero, indistinguishable from an account that really did call at round zero, so on any chain younger than the cooldown every new account is refused until round 100 with the message `cooling`, which is a lie. **A sentinel is only safe when it cannot collide with a real value, and round zero is a real value.** Branching on the flag costs one `else` and removes the question entirely.

In the calculator, this fixes defect one. Multiply first, divide last, guard both ends, and floor toward the contract.

## The Calculator, Finished
Four defects, four corrections. Here is the spine of the diff, with everything unchanged elided; the whole corrected contract follows it as Example 6-22.

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

The two unmarked context lines in the middle are the interesting part. `if now >= self.end.value: return self.total.value` is not new and is not modified; it is character-for-character what the broken version had. All that happened to it is that the arithmetic which used to sit above it now sits below it, and that alone retires the `/ 0`. **The guard was never wrong; it was in the wrong place relative to the thing it needed to guard.** Reviewers read added and deleted lines and skim the unchanged ones, which is how a fix that consists of two lines moving gets past them.

Three things the diff does not say, which the corrected listing settles:

- The import line gains `op`. No hunk shows it, and the hunks alone produce a file that does not compile.
- The new `configure` guard goes after the creator-only check and the init-once flag already there, not at the top of the method where the hunk floats it.
- `vested_now` keeps its opening `assert self.configured.value, "not configured"`. Without it, the method reads zeros out of unset global state and reports a perfectly-formed answer about a grant that does not exist.

**Example 6-22.** The vesting calculator, corrected

<!-- example: examples/numbers_time/vesting_calc_fixed.py mode=compile -->
<!-- finder: see the vesting calculator with all four defects fixed -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4, op


class VestingCalculator(ARC4Contract):
    """Reports how much of a grant has vested so far.

    It only reports. Actually paying the beneficiary needs an inner
    transaction, which is the next chapter.
    """

    def __init__(self) -> None:
        self.total = GlobalState(UInt64(0))
        self.start = GlobalState(UInt64(0))
        self.end = GlobalState(UInt64(0))
        self.configured = GlobalState(False)

    @arc4.abimethod
    def configure(self, total: UInt64, start: UInt64, end: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert not self.configured.value, "already configured"
        assert end > start, "schedule must have positive length"
        self.total.value = total
        self.start.value = start
        self.end.value = end
        self.configured.value = True

    @arc4.abimethod(readonly=True)
    def vested_now(self) -> UInt64:
        assert self.configured.value, "not configured"
        now = Global.round
        if now <= self.start.value:
            return UInt64(0)
        if now >= self.end.value:
            return self.total.value
        hi, lo = op.mulw(self.total.value, now - self.start.value)
        return op.divw(hi, lo, self.end.value - self.start.value)

    @arc4.abimethod(readonly=True)
    def schedule(self) -> tuple[UInt64, UInt64, UInt64]:
        assert self.configured.value, "not configured"
        return self.total.value, self.start.value, self.end.value
```

The docstring has lost one sentence, the one apologising for returning the wrong number. Configure the fixed contract with the same ninety-day schedule and ask it the same question. This is an **on-chain run** again, same LocalNet, same typed client:

```python
>>> calc.send.configure(args=(1_000_000, 0, 2_830_000))
>>> calc.send.vested_now().abi_return   # one third of the way through
333333
>>> calc.send.vested_now().abi_return   # eighty-nine days in
988888
>>> calc.send.vested_now().abi_return   # day ninety and after
1000000
```

**Correction one: multiply before dividing, through 128 bits.** The two-line replacement is Example 6-10 inlined rather than called; the subroutine is the better habit and either form is correct. What is not correct is the original ordering, at any width.

`op.divw` can still abort, and the contract has no guard against it. It aborts when the quotient will not fit in sixty-four bits, which needs `end - start` to be no greater than the high word of `total × (now - start)`. Since `now - start` is always less than `end - start` on this branch, the quotient is always less than `total`, which is a `UInt64`. It cannot abort here. That argument is why no fifth guard was added, and it is the kind of argument to write into a comment when you make it.

**Correction two: guard the divisor where it is established.** `assert end > start` in `configure` is one line in the method that sets the value, and it retires the `/ 0` permanently, including the case where an init-once contract configured with a zero-length schedule becomes an uncallable object holding a grant. Putting the same check in `vested_now` would have made the failure polite instead of retiring it. The diff fixes this defect twice over: the assertion retires it at the source, and moving the division below the `now >= end` branch would have caught the same case at the point of use. Both were worth doing, and only one of them is a line anybody added.

**Correction three: guard the subtraction with the branch that was already needed.** `if now <= self.start.value: return UInt64(0)` is not a new concept bolted on; it is the answer to "what has vested before the schedule starts", which the broken version never answered. That it also makes `now - start` safe is the usual pattern: the guard that makes the arithmetic legal is usually a guard the specification wanted anyway. When it is not --- when you find yourself adding an assertion purely to keep the AVM happy --- that is a sign the expression should be restructured rather than defended.

**Correction four: read the clock the caller cannot move.** `Txn.last_valid` becomes `Global.round`. This is the only correction of the four that is a security fix rather than a correctness fix, and it is the only one that could not have been caught by any test of the arithmetic, because the arithmetic was never wrong. It was reading a number that a caller supplies and the contract treated as a measurement.

Against the commission:

1. A schedule from the deployer, exactly once --- yes, and the creator-only check and the init-once flag were right from the first pass.
2. Zero before the start, the total at or after the end, the exact linear share in between --- yes: 333,333 a third of the way through, where the first pass said zero.
3. A `total` of 10^14 --- yes: the product travels through 128 bits, and on the linear branch the quotient is smaller than `total`, so `divw` has nothing to refuse.
4. A bad schedule refused when it is configured, with a message --- yes, `"schedule must have positive length"`, and the permanently uncallable contract retired with it.
5. The same answer for every caller in the same round --- yes: `Global.round` is the ledger's number, and no field of the caller's transaction is read at all.

Five for five, and the grant now releases a third of the way through instead of all of it on day ninety.

Two rules generalize past this chapter.

The first is arithmetic: **a proportion is a multiplication that has not been divided yet.** Taken literally, the rest follows: multiply before you divide, route the product through 128 bits when it might not fit, floor the division toward the contract, and guard every divisor and every subtraction where the value is established rather than where it is used.

The second is correction four generalized: **every field of the incoming transaction is an input, not an observation.** `Txn.last_valid`, `Txn.first_valid`, `Txn.fee`, `Txn.note`, the lot. You may assert bounds on them, and you may reject a transaction whose fields you dislike. You may not treat their values as facts about the world. The ledger's own fields --- `Global.round`, `Global.latest_timestamp`, `Global.current_application_address` --- are the observations, and there are not many of them.

## Retrieval
Answer these from memory before moving on. Three of them reach back into earlier chapters on purpose, and the last one reaches forward.

1. Why does `(elapsed // duration) * total` return zero for almost every input, and what is the correct ordering?
2. What does the AVM do when a subtraction would go below zero, and what exactly does it say? What does the unit-test emulator say instead?
3. `op.divw` and `op.divmodw` both divide a 128-bit numerator. What happens to each when the quotient will not fit in sixty-four bits?
4. Name the four values a contract can mistake for "now". Which one is the answer, and what is each of the other three actually measuring?
5. A contract reads `op.Block.blk_timestamp(Global.round - 1)` and the call fails on the very first attempt, on LocalNet and MainNet alike. Say what the two ends of the readable window are, and why no value of `Global.round` can ever land inside it.
6. When a division decides how much money leaves a contract, which way should it round, and what is the argument?
7. Where does a division-by-zero guard belong, and why is that usually the same line that prevents an underflow? *(From Chapter 5)* The guard you wrote there --- `balance >= min_balance + cost` rather than `balance - min_balance >= cost` --- is the same rule. Say which of this chapter's failure modes the second form produces.
8. *(From Chapter 5)* A `BoxMap` keyed by a counter charges the application account per box. Which of this chapter's failure modes does an unguarded box-cost subtraction produce, and what would the caller see?
9. *(From Chapter 4)* An init-once configuration method sets a value this chapter's arithmetic will later divide by. What is the worst case, and why is it worse than an ordinary failed transaction?
10. *(Preview --- Chapter 8 answers this)* A test asserts that a method raises `OverflowError`. Is that test asserting anything about what a user on MainNet will see? Commit to yes or no before Chapter 8 rules on it.

## Exercises
1. A grant of 250,000 tokens vests linearly from round 40,000,000 to round 42,592,000. The three implementations: (i) `((now - start) // (end - start)) * total`; (ii) `(total * (now - start)) // (end - start)`; (iii) the `mulw`/`divw` form from Example 6-10.

   a. **(Trace)** Work out what `vested_now` returns at round 41,296,000 --- exactly half way --- for each of the three implementations, and show the arithmetic.

   b. **(Compare)** Two of the three agree. Say which two and what the third returns.

   c. **(Trace)** Change one number: the grant is now 250 million tokens of an ASA with six decimals, so `total` is 250,000,000,000,000. Recompute all three.

   d. **(Debug)** One of them now aborts: say which, quote the message it produces, and say whether the abort is better or worse than what the implementation that does not abort returns.

2. Below are six statements. Four of them form the body of a `claim` method that pays out newly vested tokens and records what it paid; two do not belong. The decorator and signature are given, and `self.claimed` is a `GlobalState(UInt64)` holding the running total already paid.

   ```python
   @arc4.abimethod
   def claim(self) -> UInt64:
       ...
   ```

   The statements: (a) `earned = vested(self.total.value, self.start.value, self.end.value, Global.round)`; (b) `assert earned > self.claimed.value, "nothing new has vested"`; (c) `payable = earned - self.claimed.value`; (d) `self.claimed.value = earned`; (e) `earned = vested(self.total.value, self.start.value, self.end.value, Txn.last_valid)`; (f) `payable = self.claimed.value - earned`.

   Both rejects fail, and they fail in interestingly different ways: one of them fails on the very first honest call, loudly, with a message from the AVM rather than from the contract; the other never fails at all and is the more expensive of the two.

   a. **(Parsons)** Select the four that belong and order them.

   b. **(Debug)** For each reject, say what the caller sees and who ends up paying for it.

   c. **(Compare)** Statement (b) is an assertion rather than an early return. Say what changes if you make it `if earned <= self.claimed.value: return UInt64(0)` instead.

   d. **(Compare)** Name one caller for whom the assertion is better and one for whom the early return is, and say which you would ship.

3. A staking contract lets an account deposit, and computes its share of a reward pool as `(pool * my_stake) // total_stake`. It works for months. Then one morning every call to `share_of` fails with `logic eval error: / 0`, and the contract holds real money that nobody can now withdraw.

   a. **(Trace)** Before working anything else out, write down what must have happened to `total_stake` and say whether an attacker was needed to make it happen.

   b. **(Debug)** Name the sequence of ordinary user actions that produces this state, with no attacker involved.

   c. **(Debug)** The obvious fix is `assert total_stake > UInt64(0)` at the top of `share_of`. Say precisely what that fixes and what it leaves broken, because it does not fix the thing the users care about.

   d. **(Debug)** Give a fix that leaves the contract usable in the state that broke it, and say which of this chapter's two rules about guard placement you had to apply.

4. You are writing a subscription contract: an account pays once and gets access for thirty days. The three ways of storing and checking the expiry: (i) store `Global.round + 942_545` and compare against `Global.round`; (ii) store `Global.latest_timestamp + 2_592_000` and compare against `Global.latest_timestamp`; (iii) store `Txn.last_valid + 942_545` and compare against `Global.round`.

   a. **(Compare)** Compare the three on four axes: what a caller can manipulate, what happens if round timing changes, what a user sees when they check their remaining time, and what breaks if the contract is paused for a week.

   b. **(Compare)** One of the three is disqualified outright: name it and say by what.

   c. **(Compare)** Of the remaining two, neither is strictly better; say which axis decides between them, and give a concrete product requirement that would flip your answer.

5. Extend Example 6-16 so that it actually draws a winner, using the ARC-21 randomness beacon rather than the block seed. You will hit a problem this chapter has not solved: calling another application from inside your contract is Chapter 15's material.

   a. **(Extend)** Write the beacon call as a comment describing exactly what you would send and what you expect back.

   b. **(Extend)** Write down three things the contract must check that Example 6-16 does not check yet. At least one of your three should be about the beacon's retention window rather than about randomness.

   c. **(Debug)** For each of your three checks, name the specific thing that goes wrong if you skip it.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can write a proportion on the AVM without a float, in the ordering that does not round to zero, and route it through `op.mulw` and `op.divw` when the product might not fit in sixty-four bits, and say why `op.divmodw` is the more dangerous choice for the same job.
- [ ] I can name every arithmetic operation that ends a transaction, quote what the chain says for each, say why the message in my unit test is not the message my user will see, and place the guard for each at the point the value is established rather than at the point it is used.
- [ ] I can name the four values that look like "now", say which one a contract should use, and explain why `Txn.last_valid` is safe to bound and unsafe to read.
- [ ] I can say what `op.Block` may read, compute the width of that window from a transaction's validity range, and explain in one sentence why block randomness cannot be fixed.
- [ ] I can write a linear release schedule with a cliff, defend the direction it rounds by naming what goes wrong under the other direction, and say where the dust ends up.

## Handoff: The Arithmetic the Vesting Project Runs On
Chapter 9 builds a real token vesting contract: a schedule per beneficiary in a box, a claim method that pays out, and a revocation path for a grant that ends early. Table 6-2 lists the examples from this chapter it leans on, and what to predict before you read it.

: Table 6-2. Examples from this chapter that the vesting project depends on

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| Example 6-18 | The core release curve, one per beneficiary | The project's schedules are per beneficiary. What has to be stored per beneficiary that this example holds in three globals? |
| Example 6-10 | Every proportion the claim path computes | The grant is denominated in an ASA with decimals. Which of the two orderings survives that, and at what size does the other one abort? |
| Example 6-20 | Grants with a cliff, and the guard that keeps `cliff` between `start` and `end` | Three parameters, three orderings to enforce. Write the assertions before you read them. |
| Example 6-11 | Every method that asks what time it is | The project denominates schedules in seconds, not rounds, because a grant agreement does. Which of this example's two globals does that force, and what does it cost in precision? |
| Example 6-5 | `create_schedule`, which fixes the divisor for one beneficiary's whole schedule | The project's divisor is `vesting_end - start_time`, set once per beneficiary and never revisited. What is the cost of getting the guard wrong where a value is established, compared to getting it wrong where it is used? |
| Exercise 3 | The revocation path, which reduces a total that has already been partly claimed | You worked out how a divisor reaches zero without an attacker. Which of the project's methods could drive `end - start` or `total - claimed` to zero the same way? |
