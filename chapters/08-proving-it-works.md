\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# Proving It Works: Tests, Simulation, and Failure

Every chapter of Part I so far has ended with a contract that works. This one takes on the difference between *works* and *is known to work*. That gap is not closed by writing more code. It is closed by three skills the rest of the book assumes you have: making a contract explain its own refusals, running a call without committing it, and writing a test that can actually fail.

## Evidence That a Contract Does What You Think

A contract about to hold other people's money needs something stronger than a run that went well, and the obvious way to get it runs out in both directions almost at once.

A confirmed transaction tells you the approval program returned true. It does not tell you the program did the right thing: a method that pays nothing and reports success confirms exactly like one that pays, and the wallet shows the same green tick either way. A rejected transaction tells you less. What the AVM reports is `assert failed pc=<n>`, a byte offset into the compiled program, with no message, no line number, and no record of what the program had done before it stopped. Nor can you run the call again to find out, because the state it read has moved on and the transaction either committed or did not.

Three things close the gap. A contract can be made to explain its own refusals, though where that explanation ends up is not where most people assume. A call can be run against real ledger state without committing it, which turns a rejection into something you can watch happen opcode by opcode. And a test can be built to disagree with the contract rather than to echo it: **a test suite is not evidence unless some arrangement of the world would have turned it red.**

Figure 8-1 annotates what comes back when a simulated call is rejected. Almost everything in this chapter either puts more information into that response or gets more information out of it.

![Figure 8-1. A failed simulate response, annotated. The five numbered stops are the reading order for any failure: which transaction, what it said, where it stopped, what it cost, and why simulate could run it unsigned.](figures/simulate-trace.svg)

The HTTP request itself *succeeded*. A rejected simulation is a `200 OK` whose body reports the failure, which is why a test that asserts on the status code passes no matter what the contract does. The information you want (which assertion fired, where, and what the program had done before it got there) is in `failure-message`, `failed-at`, and the execution trace. The diagram draws that body as an object because that is what the node returned; whether your own code gets to hold it is a separate question, answered later.

What is *not* on the page matters as much. There is no Python. There is a program counter, whatever string your app spec can associate with that program counter, and --- when the client compiled the contract itself, as the client behind every `LogicError` transcript so far did --- a line number into the *generated TEAL*. Getting from any of those back to a line in your source file is a hop the tooling does not make for you; a sixteen-line function later in this chapter closes the gap.

::: {.spec title="Your commission: a vesting contract that can prove itself"}
The contract is the simplest version of Chapter 9's project --- one beneficiary, a cliff, a linear schedule, an inner transfer that pays out --- and with Chapters 6 and 7 open you could write it tonight. The commission is not the contract. It is the evidence:

1. Every refusal on the claim path names a reason a beneficiary can act on
2. A claim that would move nothing is refused, never reported as success
3. The schedule survives a production-sized supply, and a test says so
4. Every security assertion has a negative test pinned to its own message
5. Any failing call can be traced from its program counter back to the line of Python that refused

Five requirements, and not one of them is a feature. At the end of the chapter you will hold the corrected contract and its suite against this list.
:::

By the end of this chapter you will be able to:

- Say exactly where the string in `assert cond, "message"` ends up, why it is not in the bytecode, and what a caller who does not hold your app spec sees instead
- Choose between `assert`, `logged_assert()`, `logged_err()` and `op.err()` for a given contract, and state what each one costs and buys
- Name the validation the ARC-4 router already performs, so you stop writing assertions that restate it, and write the ones it cannot perform
- Explain why there is no reentrancy on Algorand, in two separate facts, and say what that does and does not license you to do
- Run a method against real ledger state without committing it, read the opcodes it consumed, discover the resources it touched, and see the trace of its execution
- Turn a program counter reported by a failing call back into the line of Python that emitted it
- Write unit tests against an in-memory ledger you can rewrite, and negative tests that prove a rejection happened *for the reason you intended*

## A Vesting Contract, and What Its Tests Establish

Here is that commission's contract half, as anyone arriving from Chapters 6 and 7 would first write it. A four-year linear vesting contract exercises all three skills: it has a cliff, a beneficiary, a schedule fixed at deposit time, and an inner asset transfer that pays out, which means it holds a supply that is not its own and decides, on every call, how much of it has become somebody else's.

**Example 8-1.** A vesting contract that fails

<!-- finder: see a contract whose green test suite proves nothing -->

```python
from algopy import (ARC4Contract, Asset, Global, GlobalState, Txn, UInt64,
                    arc4, gtxn, itxn, subroutine)


class SimpleVesting(ARC4Contract):
    """Vests one ASA to one beneficiary, linearly, after a cliff.

    Deployed, funded, and demonstrably working: the admin initializes
    it against a deposit, time passes, the beneficiary claims, tokens
    arrive. Three things about it are wrong. None raise a compile
    error, and --- this is the part that matters --- none of them are
    caught by a test suite that looks thorough.
    """

    def __init__(self) -> None:
        self.admin = GlobalState(Global.creator_address)
        self.beneficiary = GlobalState(Global.zero_address)
        self.asset_id = GlobalState(UInt64(0))
        self.total = GlobalState(UInt64(0))
        self.claimed = GlobalState(UInt64(0))
        self.start = GlobalState(UInt64(0))
        self.cliff = GlobalState(UInt64(0))
        self.end = GlobalState(UInt64(0))

    @subroutine
    def vested(self, now: UInt64) -> UInt64:
        """How much has vested in total by `now`, claimed or not."""
        if now < self.cliff.value:
            return UInt64(0)
        if now >= self.end.value:
            return self.total.value
        elapsed = now - self.start.value
        duration = self.end.value - self.start.value
        return self.total.value * elapsed // duration

    @arc4.abimethod
    def opt_in_to_asset(self, asset: UInt64) -> None:
        """Call before initialize; needs 200,000 microAlgo of MBR in the app."""
        assert Txn.sender == self.admin.value, "admin only"
        itxn.AssetTransfer(
            xfer_asset=Asset(asset),
            asset_receiver=Global.current_application_address,
            asset_amount=0,
            fee=UInt64(0),
        ).submit()

    @arc4.abimethod
    def initialize(
        self,
        beneficiary: arc4.Address,
        cliff_duration: UInt64,
        vesting_duration: UInt64,
        deposit: gtxn.AssetTransferTransaction,
    ) -> None:
        """Fix the schedule around the deposit that funds it."""
        assert Txn.sender == self.admin.value, "admin only"
        assert self.total.value == UInt64(0), "already initialized"
        assert vesting_duration > cliff_duration, "vesting must exceed cliff"
        assert deposit.asset_receiver == Global.current_application_address, (
            "deposit must go to the contract"
        )
        assert deposit.asset_amount > UInt64(0), "deposit must be positive"

        now = Global.latest_timestamp
        self.beneficiary.value = beneficiary.native
        self.asset_id.value = deposit.xfer_asset.id
        self.total.value = deposit.asset_amount
        self.start.value = now
        self.cliff.value = now + cliff_duration
        self.end.value = now + vesting_duration

    @arc4.abimethod
    def claim(self) -> UInt64:
        """Send the beneficiary everything vested since the last claim."""
        assert Txn.sender == self.beneficiary.value
        claimable = self.vested(Global.latest_timestamp) - self.claimed.value
        if claimable == UInt64(0):
            return UInt64(0)
        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_id.value),
            asset_receiver=Txn.sender,
            asset_amount=claimable,
            fee=UInt64(0),
        ).submit()
        self.claimed.value += claimable
        return claimable

    @arc4.abimethod(readonly=True)
    def claimable(self) -> UInt64:
        return self.vested(Global.latest_timestamp) - self.claimed.value
```

Example 8-1 is the minimal working version of the vesting contract Chapter 9 builds. It is complete, it compiles without a warning, and it does the job: an admin opts it into a token, deposits a supply against a schedule, and the beneficiary claims what has vested. Beside it sits the suite anyone would write the same evening --- `examples/proving_it_works/simple_vesting_test.py`, seven tests, all green, covering the cliff, the linear ramp, a claim, and a stranger being rejected. Your contract, your suite, your green run.

*Predict: three defects, and all three survive a seven-test suite. One is a success that should be a failure, one is arithmetic, and one is a failure that says nothing. Write down where in the sixty lines of logic you would look for each, before reading on.*

Run the suite. No LocalNet, no Docker:

```console
$ uv run --group test python -m pytest \
      examples/proving_it_works/simple_vesting_test.py -q
.......                                                     [100%]
7 passed in 0.15s
```

Seven green. Four exercise the repaired contract, which is on disk beside the broken one; the other three matter here:

```python
test_the_broken_version_reports_success_for_a_claim_that_moved_nothing
test_the_broken_version_rejects_a_stranger_without_saying_why
test_the_broken_schedule_overflows_at_a_production_supply
```

Those three are green because they assert what the broken contract does. They are the exact shape a suite takes when it is written after the code, by the person who wrote the code, from the code. Every one is a true statement about the program. Not one is a statement about the requirement.

Such a suite has a house style, and its names give it away. `test_a_claim_returns_zero_when_nothing_is_due` asserts that `claim()` returns `0`, which is what the contract does and the opposite of what the requirement says. Its overflow test uses four Algo of supply, because that is what the fixture had. Its rejection test asserts that an `AssertionError` is raised and never looks at the message. Not one of the three is wrong about the program, and a suite of them runs green on every commit for as long as you care to run it: **a test that asserts what the code does can never disagree with the code.** Two months of green means two months of asking the contract to confirm itself.

The move that separates the two is small --- Example 8-13 later isolates it into a pair of vaults; here is one behaviour, asserted both ways:

```python
# From the code. The contract returns 0 when nothing is due, so this
# is green, and it stays green no matter what the requirement says.
assert contract.claim() == 0

# From the requirement. "A claim that would move nothing is refused."
# Against this contract it is red, which is the only useful thing a
# test can be when the contract is wrong.
with pytest.raises(AssertionError, match="nothing vested"):
    contract.claim()
```

Do that to all three and the picture inverts. Same contract, same fixtures, three assertions changed from *what it does* to *what it is for*, in a scratch file so the shipped suite stays intact. The names below differ from those in `simple_vesting_test.py`: these run against the broken contract, and the shipped tests of similar name run against the repaired one.

```console
$ uv run --group test python -m pytest /tmp/req/requirement_tests_test.py -q
FFF                                                         [100%]

    def test_a_claim_that_moves_nothing_must_be_refused() -> None:
        ...
>           with pytest.raises(AssertionError, match="nothing vested"):
E           Failed: DID NOT RAISE <class 'AssertionError'>
```

That is defect one, and it is the one people ship most often. `claim` opens with an early return: if nothing has vested since the last claim, return `0`. Calling `claim` a second time in the same block returns `0` every time, since the clock has not moved. The method succeeds, the transaction confirms, the beneficiary's wallet shows a green tick, and no tokens moved. A caller cannot distinguish "you have claimed everything available" from "the payout worked" without reading the return value, and most clients do not. **A method that cannot do its job should refuse, not report zero.** The version of this that costs real money is a claim button that appears to work and silently does nothing for four weeks.

*Predict: the second failure is the arithmetic. Before reading it, say what `total * elapsed // duration` does when `total` is ten billion tokens at six decimals and `elapsed` is two years in seconds, and say which of the two operations is the problem.*

```console
    def test_the_schedule_must_survive_a_production_supply() -> None:
        ...
>           assert contract.vested(at_two_years) == BIG_TOTAL // 2
E           OverflowError: * overflows
```

`result = 630720000000000000000000, op = '*'`, reads pytest's dump of the emulator's own arithmetic frame, against a ceiling of about 1.8 x 10^19. Defect two is the multiply, not the divide, and the shape of it is exactly Example 6-7 from Chapter 6: the intermediate product exceeds sixty-four bits even though the quotient is comfortably small. It is invisible at four Algo of supply and unconditional at production supply, which means it is a defect that appears on the day the contract matters and not before.

The threshold is exact. `total * elapsed // duration` exceeds sixty-four bits for any supply above 146,235,605,498 base units, which at six decimals is a little over 146,000 tokens.

There is a band in between that is worse than either. Above roughly 146,000 tokens the product can overflow, but only once `elapsed` has grown large enough; below roughly 585,000 tokens it cannot overflow at the cliff. A supply between those two figures produces a contract that pays the first claims correctly and then bricks partway through the term, `claimable()` included, so the beneficiary cannot even ask what they are owed. A defect that passes a testnet run at a plausible supply and detonates in month nine is the shape to be most afraid of.

Overflow is testable. `algorand-python-testing` raises `ArithmeticError` and its subclasses for exactly the operations that would abort on the AVM, so a test that pins the overflow costs one line.

```console
    def test_a_stranger_must_be_told_why() -> None:
        ...
>           assert str(caught.value) == "not the beneficiary"
E           AssertionError: assert '' == 'not the beneficiary'
```

Defect three, and the empty string on the right of that comparison is the whole of it. `claim` opens with `assert Txn.sender == self.beneficiary.value`, a bare assertion with no message, so a `claim` from the wrong account is rejected correctly and told nothing. It is a security control that works. And what it produces, on-chain, is a program counter and nothing else: no string in the bytecode, no entry in the app spec, nothing for a client to substitute. The next section is about where that string would have gone.

## Making the Contract Say Why
**The string in `assert cond, "message"` is not in your program.**

**Example 8-2.** Where the assert message actually goes

<!-- finder: prove the assert message is absent from the compiled bytecode -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class Registry(ARC4Contract):
    """Two rejections, one of which can explain itself.

    Both compile to the same `assert`. The string in the first never
    reaches the chain: PuyaPy turns it into a TEAL comment and an
    ARC-56 `sourceInfo` entry keyed by program counter, and the
    compiled bytes do not contain it. The second has no message at
    all, so there is no `sourceInfo` entry to look up --- the node
    reports a program counter and that is the whole story.
    """

    def __init__(self) -> None:
        self.owner = GlobalState(Global.creator_address)
        self.entries = GlobalState(UInt64(0))

    @arc4.abimethod
    def record(self, count: UInt64) -> UInt64:
        assert Txn.sender == self.owner.value, "owner only"
        assert count > UInt64(0)
        self.entries.value += count
        return self.entries.value
```

Example 8-2 has two rejections in one method, and the difference between them is one comma. Compile it --- PuyaPy 5.9 writes the ARC-56 spec by default, so there is no flag to remember --- and go looking for the message:

```console
$ uv run --group compile python -m puyapy --target-avm-version 11 \
      --out-dir /tmp/ch07 examples/proving_it_works/assert_message_home.py
```

```python
>>> spec = json.loads(Path("/tmp/ch07/Registry.arc56.json").read_text())
>>> bytecode = base64.b64decode(spec["byteCode"]["approval"])
>>> len(bytecode)
111
>>> b"owner only" in bytecode
False
>>> spec["sourceInfo"]["approval"]["sourceInfo"]
[{'pc': [92], 'errorMessage': 'check self.entries exists'},
 {'pc': [83], 'errorMessage': 'check self.owner exists'},
 {'pc': [75], 'errorMessage': 'invalid number of bytes for arc4.uint64'},
 {'pc': [85], 'errorMessage': 'owner only'}]
```

The message went to two places, neither of them the chain. It became a TEAL comment --- `assert // owner only` --- which is discarded when the TEAL is assembled. And it became an entry in the ARC-56 app spec's `sourceInfo`, keyed by the program counter of the `assert` opcode. The AVM, when that assertion fails, reports `assert failed pc=85`. Everything legible after that is a client-side lookup: the client holds the app spec, matches `85` against the table, and substitutes `owner only` into the exception it raises.

Two consequences follow.

**A caller who does not hold your app spec gets a number.** Not a truncated message, not a generic one: a program counter. Anyone integrating with your contract from a different toolchain, a different language, or a block explorer sees `assert failed pc=85` and has to come and ask you what it means.

**A bare assert has no entry at all.** That table has four rows for a method with two assertions, and three of the four are PuyaPy's own: `check self.owner exists` and `check self.entries exists` are existence assertions the compiler inserts in front of every global-state read, and `invalid number of bytes for arc4.uint64` is the ABI router validating an argument's width. Exactly one row belongs to the author. The second authored assertion, `assert count > UInt64(0)` with no message, is not in the table at all. It compiled to an `assert` opcode with no diagnostics attached, which makes it invisible to every tool that reads the app spec.

::: {.gotcha #assert-message-not-onchain topic="Compilation, tooling, and shipping" title="The string in an assert message is not in your program"}
`assert cond, "message"` puts the string in two places and neither is the chain: a TEAL comment, discarded at assembly, and an ARC-56 `sourceInfo` entry keyed by the program counter of the `assert` opcode. The compiled bytes do not contain it (`b"owner only" in bytecode` is `False`), and the AVM reports only `assert failed pc=85`; everything legible after that is a client-side lookup against the app spec, so a caller integrating from a different toolchain, a different language, or a block explorer gets a number and has to come and ask you what it means. A *bare* `assert` produces no `sourceInfo` entry at all --- invisible to every tool that reads the spec, sitting beside the messaged existence assertions PuyaPy inserts on state reads.
:::

That is the vesting contract's defect three, seen from the outside. Compile the broken vesting contract with the same command, which also writes the `.puya.map` file, and run the lookup at the two program counters that sit two bytes apart in `claim`:

```console
$ uv run --group compile python -m puyapy --target-avm-version 11 \
      --out-dir /tmp/ch07 examples/proving_it_works/simple_vesting_broken.py
$ uv run --group test python examples/proving_it_works/pc_to_source_line.py \
      /tmp/ch07/SimpleVesting.approval.puya.map 311
pc=311  simple_vesting_broken.py:75
   |  assert Txn.sender == self.beneficiary.value
   |  op=assert // check self.beneficiary exists
   |  error='check self.beneficiary exists'

$ uv run --group test python examples/proving_it_works/pc_to_source_line.py \
      /tmp/ch07/SimpleVesting.approval.puya.map 313
pc=313  simple_vesting_broken.py:75
   |  assert Txn.sender == self.beneficiary.value
   |  op=assert
```

Both are wrapped at the `|` separators to fit the page; the tool prints one line per lookup.

Two assertions, one source line, adjacent in the bytecode. The first is PuyaPy's --- it checks that the global-state key exists before reading it --- and it has a message. The second is the author's actual authorization check, and it has nothing. A stranger who is correctly rejected by that contract receives a program counter pointing at an assertion that no artifact anywhere can name, sitting immediately beside one the compiler wrote for its own bookkeeping.

*Predict: the message is not on-chain. Say what a contract would have to do to put it there, and what that would cost, before reading on.*

There is a way, it costs bytecode, and it is a shipped API rather than something you write yourself.

**Example 8-3.** `logged_assert()` writes the reason into the program

<!-- finder: emit a machine-readable error code that survives without the app spec -->

```python
from algopy import (ARC4Contract, Global, GlobalState, Txn, UInt64, arc4,
                    logged_assert)


class LoggedRegistry(ARC4Contract):
    """The same two checks, written to ARC-65.

    Each logs `ERR:<code>[:<message>]` and then fails, so the reason
    is in the bytecode and reaches a caller who has no app spec.
    """

    def __init__(self) -> None:
        self.entries = GlobalState(UInt64(0))

    @arc4.abimethod
    def record(self, count: UInt64) -> UInt64:
        logged_assert(Txn.sender == Global.creator_address, "ownerOnly")
        logged_assert(count > UInt64(0), "positiveCount", "count must be > 0")
        self.entries.value += count
        return self.entries.value
```

`logged_assert(...)` comes from `algopy` directly, along with its unconditional sibling `logged_err`; neither is a helper this book invents. Each takes an `error_code`, an optional `error_message`, and an optional `prefix` of `"ERR"` or `"AER"`, and lowers to a `log` of `ERR:<code>[:<message>]` followed by a failure. That is ARC-65. Compile Example 8-3 and the two probes from the previous example come back changed. The approval program is 158 bytes rather than 111, and a like-for-like comparison would be slightly worse still, since the logged version also drops a global-state read the earlier one paid for. `b"owner only" in bytecode` is still `False`, `b"ERR:ownerOnly" in bytecode` is now `True`: the code is in the program, in the shape ARC-65 specifies, and the human sentence rides along with it as `b"ERR:positiveCount:count must be > 0"`. (The `arcs: [22, 28]` line in the app spec is not evidence of any of this; PuyaPy emits it for every `ARC4Contract`.)

On a *submitted* transaction that fails, the log buys nothing: a node that rejects a transaction returns a message and no logs array, and no amount of logging inside your contract changes that. What it buys is one thing: **a caller who does not hold your app spec can recover the reason from `txn-result.logs` in a simulate.** For a public, composable contract that other teams will integrate against without asking you for artifacts, that is worth paying bytecode for. For an application you own end to end, whose only clients ship with your app spec, it is bytes you are paying for a lookup you could already do.

::: {.gotcha #logged-assert-costs-bytecode topic="Compilation, tooling, and shipping" title="logged_assert buys spec-free legibility, priced in bytecode"}
If a rejection's reason must survive without the app spec, `logged_assert()` writes it into the program as an ARC-65 log entry --- `ERR:<code>[:<message>]`, emitted before the failure. That is the one form a caller holding none of your artifacts can recover, from `txn-result.logs` in a simulate, and it is priced in program size: expect the approval program to grow by roughly forty per cent or more for a couple of checks. You are buying legibility for callers who lack your artifacts, not for anything on-chain --- a submitted transaction that fails still returns no logs. For an application whose only clients ship with your app spec, a plain `assert` with a message is the same information at no bytecode cost.
:::

**Example 8-4.** `logged_err()` and the return-type deadlock

<!-- finder: place an unconditional failure inside a method that must return a value -->

```python
from algopy import ARC4Contract, UInt64, arc4, logged_err


class Tiers(ARC4Contract):
    """`logged_err` in a value-returning method needs somewhere to land.

    As the last statement it deadlocks: the stubs type it `-> None`,
    so mypy wants a return and PuyaPy calls that return unreachable.
    """

    @arc4.abimethod(readonly=True)
    def rate_for(self, tier: UInt64) -> UInt64:
        rate = UInt64(0)
        if tier == UInt64(1):
            rate = UInt64(100)
        elif tier == UInt64(2):
            rate = UInt64(250)
        else:
            logged_err("unknownTier", "no such tier")
        return rate
```

::: {.gotcha #logged-err-return-deadlock topic="Compilation, tooling, and shipping" title="An unconditional failure in a value-returning method deadlocks the type checker"}
`logged_err()` and `logged_assert()` are typed `-> None` in the algopy stubs; PuyaPy treats them as terminal. The two views collide in a value-returning method: make `logged_err(...)` the last statement and mypy reports `Missing return statement`; add a `return` to satisfy mypy and PuyaPy reports unreachable code. Neither tool is wrong and no flag resolves it. The shape that compiles is Example 8-4's: bind a local, put the failure in an `else` branch, return the local once at the end. Void methods have no such problem.
:::

House rules for the codes themselves, in one breath: PuyaPy warns on error codes that are not alphanumeric camelCase, warns when the whole `ERR:code:message` string passes 64 bytes, and the `AER` prefix is reserved for specific ARC errors --- leave it alone.

**Example 8-5.** Two spellings of an unconditional failure

<!-- finder: compare the two spellings of an unconditional failure -->

```python
from algopy import ARC4Contract, arc4, op


class Gate(ARC4Contract):
    """Two spellings of the same opcode, with different diagnostics.

    Both methods compile to a bare `err`. Only the second produces an
    ARC-56 `sourceInfo` entry, which is the only thing that lets a
    client say anything more useful than the program counter.
    `op.err()` is `assert False` with the diagnostics deleted.
    """

    @arc4.abimethod
    def closed_for_now(self) -> None:
        op.err()

    @arc4.abimethod
    def also_closed(self) -> None:
        assert False, "closed for now"  # noqa: B011
```

The two methods in Example 8-5 compile to the identical opcode. `op.err()` lowers to `err`. So does `assert False, "closed for now"`: an assertion the compiler can prove always fails becomes an unconditional `err` rather than a comparison. The only difference is in the app spec, read the same way as before against `/tmp/ch07/Gate.arc56.json`:

```python
>>> spec["sourceInfo"]["approval"]["sourceInfo"]
[{'pc': [35], 'errorMessage': 'closed for now'}]
```

One entry, for the `assert False` form. `op.err()` produces none. There is no case in which `op.err()` is better than `assert False, "..."`, and there is a case in which it is actively worse: a trailing `op.err()` after an `if`/`elif` chain can be folded by the optimizer into a bare assertion on the preceding branch, at which point you have a rejection with no message in a place you did not write one.

In the vesting contract, this fixes defect three: the bare `assert Txn.sender == self.beneficiary.value` gains a message, and the fixed version chooses plain `assert` with a string over `logged_assert`, since a single-beneficiary contract with one known client does not need the bytes.

## Failing in the Right Place
The question is not *how* to refuse but *where*, and the usual answer is too early. A great deal of defensive code in Algorand contracts checks something the router has already checked, before a line of your method ran.

**Example 8-6.** Validate at the boundary, not before it

<!-- finder: see which checks the ARC-4 router has already performed for you -->

```python
from algopy import (ARC4Contract, Asset, Global, GlobalState, Txn, UInt64,
                    arc4, gtxn)

MAX_FEE_BPS = 500


class Staking(ARC4Contract):
    """Every assertion checks meaning. The router already checked shape.

    It proved this is a NoOp on a live app, `fee_bps` is eight bytes,
    and `deposit` is an axfer directly before this call in the group.
    """

    def __init__(self) -> None:
        self.admin = GlobalState(Global.creator_address)
        self.stake_asset = GlobalState(UInt64(0))
        self.fee_bps = GlobalState(UInt64(0))

    @arc4.abimethod
    def configure(self, stake_asset: Asset, fee_bps: UInt64) -> None:
        assert Txn.sender == self.admin.value, "admin only"
        assert self.stake_asset.value == UInt64(0), "already initialized"
        assert stake_asset.id != UInt64(0), "asset required"
        assert fee_bps <= UInt64(MAX_FEE_BPS), "fee too high"
        self.stake_asset.value = stake_asset.id
        self.fee_bps.value = fee_bps

    @arc4.abimethod
    def stake(self, deposit: gtxn.AssetTransferTransaction) -> UInt64:
        assert self.stake_asset.value != UInt64(0), "not initialized"
        assert deposit.xfer_asset.id == self.stake_asset.value, "wrong asset"
        app = Global.current_application_address
        assert deposit.asset_receiver == app, "wrong receiver"
        assert deposit.sender == Txn.sender, "deposit must be from the caller"
        return deposit.asset_amount
```

Every assertion in Example 8-6 checks *meaning*. None of them checks *shape*, because the router already did. Compiled, the TEAL in front of your first line reads:

```teal
txn NumAppArgs
bz main___algopy_default_create@11
txn OnCompletion / ! / assert
txn ApplicationID / assert
pushbytess 0xb99e94e3 0xda4af034 // method "configure(...)", method "stake(...)"
txna ApplicationArgs 0
match configure stake
err
txna ApplicationArgs 1 / dup / len / intc_2 // 8 / ==
assert // invalid number of bytes for arc4.uint64
txn GroupIndex / intc_1 // 1 / - / dup / gtxns TypeEnum / pushint 4 // axfer / ==
assert // transaction type is axfer
```

That is a list of things you do not have to write. The OnCompletion is NoOp. The application exists rather than being created. The selector matched a method you declared, and an unknown selector already hit `err`. Every ABI argument is the right width: eight bytes for a `UInt64` here, and for other types the same check with the type named in the message, so an `arc4.Address` parameter that arrives short fails with `invalid number of bytes for arc4.static_array<arc4.uint8, 32>` and a dynamic array whose header disagrees with its contents fails on an `extract_uint16` with `invalid array length header`. And for a `gtxn.AssetTransferTransaction` parameter, both the type *and the position*: PuyaPy lowers a typed group argument position-relatively, as `GroupIndex - 1`, and asserts the type enum.

So `assert Txn.num_app_args == 3`, `assert len(addr.bytes) == 32`, and `assert Global.group_size == 2` in a method whose transfer arrives as a declared parameter are all redundant. The last one deserves a caveat. As Example 7-10 showed, a size assertion is not redundant when you are reading a neighbour *by index*, and it is not redundant when the thing you are bounding is how many times the method can appear. It is redundant only as a restatement of what the typed parameter already pins.

One thing Example 8-6 does not do is bookkeeping. `stake` checks the deposit and returns its amount, and then the method ends; nothing records that this account staked. A staking contract you would actually deploy writes the depositor's balance before it returns, and Chapter 17 is where that ledger gets built.

**The organizing principle is that the router validates shape and you validate meaning.** Meaning is everything the router cannot know: that this asset is the one you configured, that this amount is above your floor, that this receiver is your own application account, that this sender is the caller, that this contract has been initialized, that this caller is the admin. That list is the four questions from Chapter 7 with authorization and lifecycle added.

When a failure message reads `check self.admin exists`, it is not something you wrote and not a bug: PuyaPy inserts an existence assertion in front of every global-state read, and that is the message it attaches. Seeing it in a stack trace means a state key was read before anything wrote it.

*Predict: on Ethereum, the canonical ordering rule is checks-effects-interactions: never send value before you have updated your state, because the recipient can call back in. Say what the equivalent rule is here, before reading the next example.*

**Example 8-7.** There is no reentrancy on Algorand

<!-- finder: write interaction-before-effects deliberately and see why it is safe -->

```python
from algopy import (ARC4Contract, Global, LocalState, Txn, UInt64, arc4, gtxn,
                    itxn)


class Vault(ARC4Contract):
    """Interaction before effects --- and it is still safe.

    `withdraw` pays out and only then zeroes the balance: on the EVM
    that is the reentrancy bug; here nothing gets control back, and
    `itxn_submit` refuses an app already on the stack. Balances sit
    in local state to keep this short, which is wrong for money:
    ClearState always succeeds, so opting out strands your funds.
    """

    def __init__(self) -> None:
        self.balance = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def deposit(self, payment: gtxn.PaymentTransaction) -> UInt64:
        app = Global.current_application_address
        assert payment.receiver == app, "pay the vault"
        assert payment.sender == Txn.sender, "credit goes to the payer"
        held = self.balance.get(Txn.sender, UInt64(0))
        self.balance[Txn.sender] = held + payment.amount
        return held + payment.amount

    @arc4.abimethod
    def withdraw(self) -> UInt64:
        amount = self.balance.get(Txn.sender, UInt64(0))
        assert amount > UInt64(0), "nothing deposited"
        itxn.Payment(
            receiver=Txn.sender, amount=amount, fee=UInt64(0)
        ).submit()
        self.balance[Txn.sender] = UInt64(0)
        return amount
```

Example 8-7 is the largest single case of a check in the wrong place: an entire family of guards, imported wholesale from other chains, defending against something the AVM does not permit. Its `withdraw` sends the money and only then zeroes the balance. On the EVM that is the reentrancy bug in its textbook form. Here it is safe, for two separate reasons with different scopes.

The first is that **there are no callbacks.** An inner payment to an account does not run anything. The AVM has no mechanism by which the receiver of value gets control. There is nothing to re-enter because nothing was entered.

The second applies when the inner transaction *is* an application call, which is a case the first reason does not cover. The AVM refuses at `itxn_submit` if the application being called already appears in the current call stack: a self-call is rejected outright, and an ancestor appearing again produces `attempt to re-enter <appId>`. The check walks the ancestor chain only, so two *sibling* calls to the same application in one group are permitted; this is not a global "at most once" rule. The same walk bounds recursion depth: a maximum of eight nested application calls beneath the top-level one.

One thing in Example 8-7 is a shortcut rather than a lesson. The vault keeps balances in local state, which fits on one screen and is wrong for money: a ClearState transaction always succeeds, since the clear program cannot refuse whatever you put in it, so a depositor who takes the ordinary "opt out of this application" path in their wallet deletes their own balance and strands the funds in the application account with no method able to move them. Deposit records belong in a box, which the example says in its docstring.

This licenses writing state in whatever order reads best. It does not license writing state in whatever order you like, because there is an ordering constraint that looks identical and is not about reentrancy at all: accumulators must be updated before per-user values are computed against them, because a global figure that has not caught up is arithmetically wrong regardless of who calls what. Chapter 17 is built on that distinction. Getting the two confused costs you either way: in one direction you write guards against an attack that cannot happen, in the other you skip an ordering rule that has nothing to do with attacks.

Both of the vesting contract's remaining defects live elsewhere. The next thing you do with a failing contract is read its execution, and you cannot read an execution without knowing which parts of it the toolchain performed on your behalf.

## Running a Call Without Committing It
A simulated call commits nothing, which makes it the right place to watch a contract fail.

**Example 8-8.** Simulate instead of submit

<!-- finder: run a method against real ledger state without committing anything -->

```python
"""Run `claim` against real ledger state without committing it."""

import sys
from pathlib import Path

from algokit_utils import (AlgorandClient, AppClient, AppClientMethodCallParams,
                           AppClientParams)


def main(app_id: int, spec_path: str) -> int:
    algorand = AlgorandClient.from_environment()
    beneficiary = algorand.account.from_environment("BENEFICIARY")
    client = AppClient(AppClientParams(
        app_spec=Path(spec_path).read_text(),
        algorand=algorand,
        app_id=app_id,
        default_sender=beneficiary.address,
    ))
    group = algorand.new_group().add_app_call_method_call(
        client.params.call(AppClientMethodCallParams(method="claim", args=[]))
    )
    result = group.simulate()

    # `returns` holds one entry per ABI method call, not per transaction.
    would_return = result.returns[-1].value
    consumed = result.simulate_response["txn-groups"][0]["app-budget-consumed"]
    print(f"claim() would return {would_return}, using {consumed} opcodes")
    print(f"group {result.group_id} was evaluated and thrown away")
    return int(would_return)


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
```

`simulate` runs the real compiled program against the real current ledger, honours the whole group, and throws the result away. It is not a mock and it is not an emulator: the state it reads is the state a submitted transaction would have read a moment earlier. What you get back is what the call *would* have returned and what it *would* have cost.

Two details in Example 8-8 are the ones people get wrong. `result.returns` holds one entry per ABI method call, not one per transaction, so indexing it positionally against your group is a bug waiting for the first payment you add; index from the end, or track the position yourself. And the *group-level* `app-budget-consumed` is the whole group's. There is a same-named key on each transaction result too, and once a group holds more than one app call the two are not the same number. Read the one whose level you meant.

**Example 8-9.** Simulate with extra opcode budget

<!-- finder: measure what a call costs when it does not fit in one app call's budget -->

```python
"""Find out what a call really costs when 700 opcodes are not enough."""

import sys
from pathlib import Path

from algokit_utils import (AlgorandClient, AppClient, AppClientMethodCallParams,
                           AppClientParams)

PER_APP_CALL_BUDGET = 700


def main(app_id: int, spec_path: str) -> int:
    algorand = AlgorandClient.from_environment()
    client = AppClient(AppClientParams(
        app_spec=Path(spec_path).read_text(),
        algorand=algorand,
        app_id=app_id,
        default_sender=algorand.account.from_environment("DEPLOYER").address,
    ))
    group = algorand.new_group().add_app_call_method_call(
        client.params.call(AppClientMethodCallParams(method="sweep", args=[]))
    )
    # The extra budget exists only inside the simulation. It buys a
    # measurement, not a bigger program.
    result = group.simulate(extra_opcode_budget=20_000)

    consumed = result.simulate_response["txn-groups"][0]["app-budget-consumed"]
    needed = -(-consumed // PER_APP_CALL_BUDGET)
    print(f"sweep() burns {consumed} opcodes")
    print(f"pool {needed} app calls into the real group to afford it")
    return int(consumed)


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
```

An application call gets 700 opcodes. A group gets 700 times the number of application calls in it, pooled, and any one call may spend the whole pool. This is why the budget is a group figure and why the standard remedy for an expensive method is padding the group with extra calls to a cheap method, which Chapter 11 prices.

The awkward part is measuring. A method that needs 2,400 opcodes fails at 700 with `pc=<n> dynamic cost budget exceeded, executing <opcode>: local program cost was 685`. That last number is neither the ceiling nor what you needed: it is the total spent *before* the opcode that would not fit, so on a 700 budget it comes back as 685, or 691, or whatever the running total happened to be. The message tells you where you ran out and not how far short you were. Guessing the multiple is a loop of deploy, fail, add a call, repeat. `extra_opcode_budget` collapses that loop: it is a simulate-only allowance, up to 320,000, that exists so the response can tell you the true cost. Example 8-9 passes `extra_opcode_budget=20_000`; everything after that reads `app-budget-consumed` and divides.

**The budget you buy exists only inside the simulation.** It buys a measurement, not a bigger program. A method that reports 2,400 still needs four application calls in the real group.

**Example 8-10.** Unnamed resources and an execution trace

<!-- finder: ask the node which accounts, assets and boxes a call actually touched -->

```python
"""Ask the node which resources a call touched, and watch it execute."""

import sys
from pathlib import Path

from algokit_utils import (AlgorandClient, AppClient, AppClientMethodCallParams,
                           AppClientParams)
from algosdk.v2client.models import SimulateTraceConfig


def main(app_id: int, spec_path: str) -> int:
    algorand = AlgorandClient.from_environment()
    client = AppClient(AppClientParams(
        app_spec=Path(spec_path).read_text(),
        algorand=algorand,
        app_id=app_id,
        default_sender=algorand.account.from_environment("DEPLOYER").address,
    ))
    group = algorand.new_group().add_app_call_method_call(
        client.params.call(AppClientMethodCallParams(method="sweep", args=[]))
    )
    result = group.simulate(
        allow_unnamed_resources=True,
        exec_trace_config=SimulateTraceConfig(enable=True, stack_change=True),
    )
    txn_group = result.simulate_response["txn-groups"][0]
    # Discovery, not permission: the real call must still declare these.
    print(f"touched: {txn_group.get('unnamed-resources-accessed', {})}")
    trace = txn_group["txn-results"][0]["exec-trace"]["approval-program-trace"]
    print(f"{len(trace)} opcodes, last at pc={trace[-1]['pc']}")
    return len(trace)


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
```

Example 8-10 names two facilities explicitly, and both are already on: algokit-utils enables them on every simulate it makes, so writing them out documents what the call depends on rather than switching anything. `allow_unnamed_resources=True` lets the call reach accounts, assets, applications and boxes it never declared, and reports them back under `unnamed-resources-accessed`. That is a **discovery mechanism, not a permission**: the submitted transaction still has to declare every one of them, and algokit-utils will populate them for you from exactly this response. Turning it on to make a failing call pass, and then submitting, gets you the same failure with more steps.

::: {.gotcha #unnamed-resources-are-discovery topic="Resource references, MBR, and budget" title="Unnamed resources are a discovery tool, not a permission"}
A passing simulate with `allow_unnamed_resources=True` is not evidence the call works: the submitted transaction is still subject to the ordinary resource rules and fails on the first undeclared reference. The flag exists so tooling can *find out* what to declare --- run the simulate, read `unnamed-resources-accessed`, and put the results on the real call, which is what algokit-utils does for you. A related trap sits next to it: the resource arrays have a per-transaction cap, and a method that touches more than fits cannot be fixed by declaring harder. It has to be split across a group, which is a design change and better discovered here than in production.
:::

`exec_trace_config` controls the opcode-by-opcode trace: one entry per executed opcode, each carrying a program counter and, if you asked for them, stack and scratch changes. algokit-utils already enables a full four-field trace on every simulate it makes, so passing `SimulateTraceConfig(enable=True, stack_change=True)` *narrows* the default to the two fields the example reads rather than switching anything on. The trace is the raw material behind Figure 8-1. A trace unit carries a program counter, stack and scratch changes, and spawned inner transactions --- and no log field. Logs are on the transaction result, not on the trace.

::: {.gotcha #logs-vanish-on-real-failure topic="Testing and simulation" title="A failed transaction returns no logs; a failed simulation does"}
A contract that logs its reason before failing does not get that reason back with the rejection. On a submitted transaction, the node's response to a failed `POST /v2/transactions` is a message and nothing else, with no logs array, no matter what the program logged before it aborted. Logs from a failing group survive in exactly one place: the simulate response, at `txn-groups[g].txn-results[i].txn-result.logs`, which the simulator saves specifically because a debugging tool needs them. ARC-65's promise that the failure reason is recoverable from the API response is therefore true of simulate and false of a real submission. For a client that can re-run a failure through simulate, logs are recoverable; for one reacting to a rejection in the wild, the program counter is all there is.
:::

**Example 8-11.** One return value, three call paths, three shapes

<!-- finder: get the decoded return value from each of the three ways to call a method -->

```python
"""One return value, three call paths, three different shapes."""

import sys
from pathlib import Path

from algokit_utils import (AlgorandClient, AppClient, AppClientMethodCallParams,
                           AppClientParams)


def main(app_id: int, spec_path: str, method: str) -> None:
    algorand = AlgorandClient.from_environment()
    client = AppClient(AppClientParams(
        app_spec=Path(spec_path).read_text(),
        algorand=algorand,
        app_id=app_id,
        default_sender=algorand.account.from_environment("DEPLOYER").address,
    ))
    call = AppClientMethodCallParams(method=method, args=[])
    params = client.params.call(call)

    # `AppClient.send` decodes for you: this is already a Python value.
    print("send.call:", client.send.call(call).abi_return)

    # `algorand.send.*` hands back the ABIReturn wrapper, or None.
    wrapped = algorand.send.app_call_method_call(params).abi_return
    print("app_call_method_call:", None if wrapped is None else wrapped.value)

    # A simulate has no `abi_return` at all. Index `returns` from the end:
    # it holds one entry per ABI method call, not per transaction.
    simulated = algorand.new_group().add_app_call_method_call(params).simulate()
    print("simulate:", simulated.returns[-1].value)


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2], sys.argv[3])
```

Example 8-11 belongs here rather than in Chapter 3: the shapes diverge only once you are switching between submitting and simulating, which is what debugging consists of. `AppClient.send.call()` hands you the decoded Python value. `algorand.send.app_call_method_call()` hands you an `ABIReturn` wrapper, or `None` if there was no method call at all, so `abi_return is None` and `abi_return.value is None` are different facts, and conflating them turns a missing method into a method that returned nothing. And a simulate has no `abi_return` at all; it has `returns`.

::: {.gotcha #readonly-is-client-side topic="Compilation, tooling, and shipping" title="A readonly call is simulated with skipped signatures and a huge budget"}
Chapter 3 established that `readonly=True` is a promise to callers, not something the AVM enforces. The half that bites later is *how* the client keeps the promise: algokit-utils answers a readonly call with a simulate, run with signatures skipped and the maximum extra opcode budget granted. That is why readonly calls are free and instant --- and why they run in a far more permissive environment than a real submission. A readonly method that consumes 2,000 opcodes answers correctly in your client every time and fails the first time anybody submits it. Submit every readonly method at least once, on LocalNet, before you trust its numbers.
:::

*Predict: you have a failing call. You have a program counter from the error and a message from the app spec. What is still missing, and where would it have to come from?*

**Example 8-12.** Reading a program counter back to a source line

<!-- finder: turn a program counter into the Python statement that produced it -->

```python
"""Turn a program counter back into the Python line that emitted it.

algokit-utils gives you a pc and, if you hold the app spec, a message.
It never reads the `.puya.map` PuyaPy writes next to the bytecode, so
the last hop --- pc to Python source line --- is yours to make.
"""

import json
import sys
from pathlib import Path

from algosdk.source_map import SourceMap


def explain_pc(puya_map: Path, python_root: Path, pc: int) -> str:
    raw = json.loads(puya_map.read_text())
    line_index = SourceMap(raw).get_line_for_pc(pc)
    if line_index is None:
        return f"pc={pc}: no mapping"

    # `sources` is relative to the map file; line numbers are 0-based.
    source = (python_root / raw["sources"][0]).resolve()
    statement = source.read_text().splitlines()[line_index].strip()
    event = raw.get("pc_events", {}).get(str(pc), {})
    parts = [f"{source.name}:{line_index + 1}", statement]
    if event.get("op"):
        parts.append(f"op={event['op']}")
    if event.get("error"):
        parts.append(f"error={event['error']!r}")
    return f"pc={pc}  " + "  |  ".join(parts)


if __name__ == "__main__":
    print(explain_pc(Path(sys.argv[1]), Path(sys.argv[1]).parent,
                     int(sys.argv[2])))
```

What is missing is the line of Python, and the reason no tool gives it to you is a gap between two artifacts. The ARC-56 app spec carries `sourceInfo` keyed by program counter, but PuyaPy never populates its `teal` field, and sets `pcOffsetMethod` to `none`, so `LogicError.line_no` comes back `None`. Meanwhile PuyaPy writes a second file next to the bytecode, `<Contract>.approval.puya.map`, by default, on every compile. It is a Source Map v3 whose `mappings` array has one segment per bytecode byte, indexed by program counter, resolving to a zero-based line number in the Python source. **algokit-utils never reads that file.**

Example 8-12's `explain_pc` is the sixteen lines that close the gap, and the key line is `SourceMap(raw).get_line_for_pc(pc)`: `algosdk` already ships the Source Map v3 decoder, so the example is mostly plumbing around one call. Point it at the map and a program counter and it answers (wrapped here at the `|` separators to fit the page):

```console
$ uv run --group test python examples/proving_it_works/pc_to_source_line.py \
      /tmp/ch07/SimpleVesting.approval.puya.map 178
pc=178  simple_vesting_broken.py:39
   |  assert Txn.sender == self.admin.value, "admin only"
   |  op=assert // admin only  |  error='admin only'

$ uv run --group test python examples/proving_it_works/pc_to_source_line.py \
      /tmp/ch07/SimpleVesting.approval.puya.map 999
pc=999: no mapping
```

The second call is the honest half, though not for the reason people expect. `999` is simply past the end of a 450-byte program. Every program counter *inside* the program resolves, because the map carries one segment per byte, so a failed lookup is not telling you "this byte has no source". It is telling you the number is out of range for *this* program, which nearly always means it belongs to a longer one than the map you built. That is the benign case, because it fails loudly. The two you will actually meet do not fail at all. A program counter from the clear-state program, looked up in the approval map, resolves: a clear program is a handful of bytes against an approval program of hundreds, so its counters land comfortably inside the approval map and come back pointing at line 0. And a map rebuilt from a commit other than the one deployed resolves to a line number that is real and wrong. **Both give you an answer; neither gives you the right one.** The tool cannot tell the difference, so you have to.

Keep the map file. It is written on every compile, it is a few kilobytes, and it is the only artifact that connects the number in a production error report to a line you can go and read. If your deployment pipeline discards build outputs other than the app spec, this is the one to add back.

For the vesting contract, this is how you would have found the defects. The overflow shows up in a simulate as a rejection at a program counter; that program counter resolves, through the map, to `return self.total.value * elapsed // duration`.

## Tests That Can Actually Fail
Three things: the assertion that can fail, the ledger you can rewrite, and the negative test that pins a rejection to its reason.

**Example 8-13.** The same behaviour, asserted from the code and from the requirement

<!-- finder: see the one assertion that can tell a correct contract from an incorrect one -->

```python
"""One requirement, two contracts, and only one assertion tells them apart.

The requirement: a withdrawal above the cap must be refused. One of
these contracts refuses. The other quietly pays the cap instead.
"""

from algopy import ARC4Contract, GlobalState, UInt64, arc4

CAP = 100


class ClampingVault(ARC4Contract):
    """Pays whatever it can. A request over the cap comes back reduced."""

    def __init__(self) -> None:
        self.paid = GlobalState(UInt64(0))

    @arc4.abimethod
    def withdraw(self, amount: UInt64) -> UInt64:
        paid = amount if amount <= UInt64(CAP) else UInt64(CAP)
        self.paid.value += paid
        return paid


class RefusingVault(ARC4Contract):
    """Pays the request or refuses it. Never a third thing."""

    def __init__(self) -> None:
        self.paid = GlobalState(UInt64(0))

    @arc4.abimethod
    def withdraw(self, amount: UInt64) -> UInt64:
        assert amount <= UInt64(CAP), "over the cap"
        self.paid.value += amount
        return amount
```

Example 8-13 has two vaults and one requirement: *a withdrawal above the cap must be refused*. One of them meets it. `ClampingVault` quietly reduces an over-cap request to the cap and reports success. `RefusingVault` refuses.

The difference that matters is not in the contracts but in the test file. An assertion copied out of the code, `withdraw` returns what it paid, is true of both vaults. It is a fact about the implementation, and no implementation that is wrong in this particular way could ever make it fail. The assertion taken from the requirement is `pytest.raises(AssertionError, match="over the cap")`, and it separates them on the first run. **A test that both a correct and an incorrect implementation pass is not a test.**

*Predict: a third vault rejects over-cap requests but pays out one unit less than asked on every withdrawal. Which of the two assertions catches it? Say what that tells you about the limits of the rule you just read.*

**Example 8-14.** An in-memory ledger you are allowed to rewrite

<!-- finder: test time-dependent behaviour without waiting or deploying -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class Deadline(ARC4Contract):
    """Behaviour that depends on the clock, tested without waiting.

    `algorand-python-testing` runs these methods as ordinary Python
    against an in-memory ledger you are allowed to write to, so "after
    the deadline" becomes an assignment instead of a sleep.
    """

    def __init__(self) -> None:
        self.owner = GlobalState(Global.creator_address)
        self.closes_at = GlobalState(UInt64(0))
        self.entries = GlobalState(UInt64(0))

    @arc4.abimethod
    def open_until(self, closes_at: UInt64) -> None:
        assert Txn.sender == self.owner.value, "owner only"
        assert self.closes_at.value == UInt64(0), "already open"
        assert closes_at > Global.latest_timestamp, "deadline already passed"
        self.closes_at.value = closes_at

    @arc4.abimethod
    def enter(self) -> UInt64:
        assert self.closes_at.value != UInt64(0), "not open"
        assert Global.latest_timestamp < self.closes_at.value, "closed"
        self.entries.value += UInt64(1)
        return self.entries.value
```

`algorand-python-testing` runs your contract's methods as ordinary Python against an in-memory ledger. There is no compilation, no deployment, no network, and no Docker; a test takes milliseconds. The payoff in Example 8-14 is not the speed but the writability of the ledger. `ctx.ledger.patch_global_fields(latest_timestamp=...)` is time travel in one assignment, which turns a four-year vesting schedule into a test that runs instantly. `ctx.any.account()` produces a stranger, and `ctx.txn.create_group([...])` puts that stranger in the sender field so an authorization check can be exercised from the wrong side.

The contract's own test file, `unit_test_context_test.py`, is four tests: an entry before the deadline, an entry after the deadline with the clock moved between them, a deadline set in the past, and a stranger attempting an owner-only method. Every one of them is a negative test or a boundary, and none of them takes longer than a millisecond.

What you give up is fidelity. Table 8-1 sets the two side by side.

: Table 8-1. Integration tests compared with unit tests

| Aspect | Integration tests | Unit tests |
|------------|--------------------------------|---------------------------|
| Speed | Seconds | Milliseconds |
| What runs | Compiled TEAL on a real AVM | Your Python source |
| What it covers | Contract, client, ABI encoding, resources | Contract logic only |
| What it catches | Opcode budget, encoding, real network behaviour | Logic errors, arithmetic |
| When one fails | The bug may be in the contract or the client | The bug is in the contract |
| Requires | LocalNet and Docker | Nothing |
| Best for | Final validation and security | Rapid iteration on logic |

A unit test cannot fail for opcode budget, because it never ran an opcode. It cannot fail for a missing resource reference, an MBR shortfall, or an ABI encoding mismatch. Those are precisely the failures that appear for the first time on a real network, which is why the answer is not to choose. Iterate in the emulator; validate on LocalNet.

The emulator's error messages also diverge from the AVM's in wording. On an overflow the emulator raises `OverflowError("* overflows")`; the AVM says `* overflowed`. Underflow is `- underflows` against `- would result negative`. Division by zero is `ZeroDivisionError` against `/ 0`. Since `OverflowError` and `ZeroDivisionError` are both subclasses of `ArithmeticError` in Python, **`pytest.raises(ArithmeticError)` is the form that stays true across both**; matching on the message text breaks when you port a test to LocalNet.

**Example 8-15.** A negative test through simulate

<!-- finder: prove a rejection happens for the reason you intended -->

```python
"""Prove a rejection happens, and read the reason off the exception."""

import sys
from pathlib import Path

from algokit_utils import (AlgoAmount, AlgorandClient, AppClient,
                           AppClientMethodCallParams, AppClientParams,
                           PaymentParams)
from algokit_utils.errors import LogicError


def main(app_id: int, spec_path: str) -> str:
    algorand = AlgorandClient.from_environment()
    stranger = algorand.account.random()
    # `skip_signatures` waives the signature, not the fee -- fund the stranger.
    algorand.send.payment(PaymentParams(
        sender=algorand.account.localnet_dispenser().address,
        receiver=stranger.address, amount=AlgoAmount.from_algo(1)))
    client = AppClient(AppClientParams(
        app_spec=Path(spec_path).read_text(), algorand=algorand,
        app_id=app_id, default_sender=stranger.address))
    group = algorand.new_group().add_app_call_method_call(
        client.params.call(AppClientMethodCallParams(method="claim", args=[])))
    try:
        group.simulate(skip_signatures=True)
    except LogicError as rejected:
        # A failing simulate raises. `.message` wraps your string in the
        # contract, app id and txn id, so match it, do not compare it.
        assert "not the beneficiary" in rejected.message, rejected.message
        return f"rejected at pc={rejected.pc}: {rejected.message}"
    raise AssertionError("a stranger claimed and the contract allowed it")


if __name__ == "__main__":
    print(main(int(sys.argv[1]), sys.argv[2]))
```

A negative test on a real network has a practical problem: to prove that a stranger is rejected you need a stranger, and a stranger is an account you hold no key for. `skip_signatures=True` solves it. algokit-utils rebuilds the group against a null signer and asks the node to evaluate it without checking signatures, so any address at all can stand in for an attacker. **It waives the signature and nothing else: your stranger still has to be able to pay its own fee.** A simulate moves no value, which is the reason it is safe, but the fee is checked before the approval program is reached: an unfunded address is refused with `overspend (account ..., tried to spend 1mA)`, and because that string carries no `app=` the client never recognises it as a contract failure. You do not get a `LogicError` you can assert on; you get a bare `Exception` that sails past `except LogicError`, and the assertion you wrote to prove the stranger was rejected never runs at all. Fund the stranger with a payment first, exactly as Chapter 9 does.

**A failing simulate raises.** That is the opposite of what the name suggests and the opposite of what a negative test wants, so the shape is a `pytest.raises` around the call rather than an assertion on a `result`. What you wanted is on the exception, and the raw response is reachable through `result.simulate_response[...]["failure-message"]` when you need more than the message.

::: {.gotcha #simulate-raises-on-failure topic="Testing and simulation" title="A failing simulate raises rather than returning a failure"}
`composer.simulate()` and the group-level `.simulate()` in algokit-utils inspect the response before handing it back, and if the group failed they raise `LogicError` instead of returning. The natural shape for a negative test --- call simulate, then read `failure-message` off the result --- has no result to read. Everything you wanted is on the exception: `.message`, `.pc`, and `.transaction_id`. Wrap the call in `try`/`except LogicError`, and assert against `.message` with `in` rather than `==`, because it wraps your string in the contract name, application ID and transaction ID.
:::

Two limits of the exception are worth knowing before you lean on it. `.traces` exists on the class and is `None` on every `LogicError` this toolchain raises --- the code path that builds a trace attaches it to a different exception type --- so code that reads it looks like it works and learns nothing; to see a trace, re-simulate and read the response. And every simulate algokit-utils makes turns on `allow_more_logs`, `allow_unnamed_resources`, and `allow_empty_signatures`, with an empty signer substituted throughout, so a simulate that *succeeds* is not evidence the same group would have been accepted with real signatures and declared resources. Simulate answers "would this program approve?"; only submission answers "would the network accept it?"

::: {.gotcha #dryrun-is-leaving topic="Testing and simulation" title="dryrun still answers, and is already deleted upstream"}
`simulate` is the endpoint for this job now. `dryrun` has been deleted from go-algorand's `master` branch and still answers on every *released* node, LocalNet included --- so code that reaches for it works today and stops working on an upgrade, which is worse than failing now. Older material using `dryrun` does not announce itself as dated; the endpoint's continued politeness is the trap.
:::

Example 8-15 asserts not that an exception was raised, but that `"not the beneficiary" in rejected.message`. The `in` matters: `LogicError.message` is your string wrapped in the contract name, application ID and transaction ID, so an equality comparison against the bare string never holds. **One negative test per security assertion, each pinned to its own message,** is the practice that separates a suite which proves your authorization works from one which proves that *something* went wrong. A test that catches any exception passes when your contract rejects the stranger for the wrong reason, and passes when it rejects everybody, and passes when it is broken.

### Every Example in This Book Ships With Its Test
Every numbered example in this book is a complete program in `examples/`, registered with an execution mode that CI enforces. Five modes: `compile` means it is compiled by PuyaPy on every commit; `compile-fail` means compilation is *expected* to fail and the error text is checked against a recorded substring; `unit` means it is compiled *and* a test file beside it is run under pytest; `script` means it is client-side code that is byte-compiled, because running it would need a funded LocalNet; `localnet` means it is run end to end. A `unit` example is two files and one printed artifact: the contract is what appears on the page, and its test file sits next to it on disk under the same name with `_test` appended.

For the vesting contract, this is what finds defects one and two. The suite that catches them is the same seven tests with three assertions rewritten from *what the contract does* to *what the contract is for*.

## Completing the Vesting Contract

Three defects, three repairs, eleven changed lines. The complete corrected contract is on disk at `examples/proving_it_works/simple_vesting_fixed.py` --- the one place this book substitutes a verified disk pointer for a printed page: the file is byte-identical to this diff applied to Example 8-1, and the harness compiles it. Here is the spine of the diff, with everything unchanged elided.

```diff
 from algopy import (ARC4Contract, Asset, Global, GlobalState, Txn, UInt64,
-                    arc4, gtxn, itxn, subroutine)
+                    arc4, gtxn, itxn, op, subroutine)
     def vested(self, now: UInt64) -> UInt64:
-        return self.total.value * elapsed // duration
+        # Multiply first, through 128 bits; `divw` floors toward the pool.
+        hi, lo = op.mulw(self.total.value, elapsed)
+        return op.divw(hi, lo, duration)
     def claim(self) -> UInt64:
-        assert Txn.sender == self.beneficiary.value
+        assert Txn.sender == self.beneficiary.value, "not the beneficiary"
         claimable = self.vested(Global.latest_timestamp) - self.claimed.value
-        if claimable == UInt64(0):
-            return UInt64(0)
+        assert claimable > UInt64(0), "nothing vested since the last claim"
```

None of the elided code moves. Both classes keep their names; `__init__` is identical in both files; `opt_in_to_asset` and `initialize` are untouched; inside `vested`, the cliff and end branches and the `elapsed` and `duration` bindings that the diff's arithmetic reads are unchanged; `claim`'s inner asset transfer and its `self.claimed.value += claimable` are unchanged; and `claimable()`, still carrying `@arc4.abimethod(readonly=True)`, is unchanged in full. The only other difference between the two files is the class docstring, which described three defects and now describes three corrections.

Change the one import at the top of the scratch file from `simple_vesting_broken` to `simple_vesting_fixed`, nothing else, and run it again:

```console
$ uv run --group test python -m pytest /tmp/req/requirement_tests_test.py -q
...                                                         [100%]
3 passed in 0.13s
```

**Correction one: refuse instead of returning zero.** The early return becomes an assertion. A claim that would move nothing now fails, loudly, with a message that tells the beneficiary the truth: nothing has vested since their last claim. The transaction does not confirm, the wallet does not show a green tick, and no fee is wasted pretending.

**Correction two: multiply through 128 bits.** `op.mulw` returns the product as a high/low pair and `op.divw` divides that pair by a 64-bit divisor, so the intermediate never has to fit in sixty-four bits; only the quotient does, and the quotient is bounded by `total`. This is Example 6-7 and Example 6-8 applied to the one place in this contract where a product can exceed the word size. `divw` itself aborts when the quotient would not fit in sixty-four bits, and here it never can: this branch runs only while `elapsed < duration`, so the quotient is strictly below `total`, which is a `UInt64` already. The floor is in the right direction: `divw` truncates, which means the beneficiary is credited with slightly less than the exact real-valued share and the remainder stays in the contract until the schedule ends, at which point `vested` returns `total` exactly and the dust is paid out.

**Correction three: say why.** One string on one assertion, and the resulting message is what the earlier probe showed as an empty string. The choice of plain `assert` over `logged_assert` here is deliberate: this contract has one beneficiary and one client, both of which hold the app spec.

Two things generalize past this contract.

The first is about tests. **Write the assertion from the requirement, then run it against the code, not the other way around.** Every one of the three defects was findable by a test that stated what the contract was *for*, and invisible to a test that stated what it *did*. The mechanical version: if you cannot describe a change to the contract that would turn a given test red, that test is not testing anything.

The second is about failure. **A contract's failures are part of its interface.** The program counter is the AVM's; the message is yours; the source line is available only if you keep the artifact that maps between them. Decide, at the time you write each rejection, who will read it --- a beneficiary, an integrating team, your own on-call rotation at three in the morning --- and write the rejection for them.

Against the commission, then:

1. Every refusal on the claim path names a reason --- the bare authorization assert gained `"not the beneficiary"`.
2. A claim that would move nothing is refused --- `"nothing vested since the last claim"` instead of a confirmation; requirements one and two settled by the same diff.
3. The schedule survives a production-sized supply, and a test says so: the assertion that was red against `total * elapsed // duration` is green against `mulw`/`divw`, in a suite you just watched flip.
4. Every security assertion has a negative test pinned to its own message with `in` --- the shape Example 8-15 turned from advice into a working pattern.
5. Any failing call can be traced back to the line of Python that refused: Example 8-12's sixteen lines, good for any program counter this contract can ever emit.

Five for five --- and unlike every earlier chapter's acceptance run, this one is not a transcript you read once. It is a suite you can run again tomorrow, which was the entire commission.

## Saying What Happened

The corrected contract now refuses well. What it still does badly is *succeed*: a beneficiary claims, tokens move, and the only records are a confirmed transaction and a changed number in state. The beneficiary's wallet learns of it because the beneficiary signed it. Nobody else --- a dashboard, a payroll system, an accountant's indexer query --- learns anything without polling the contract's state and diffing snapshots, which is expensive for them and invisible to you. The return value is no help: Example 8-11 showed it riding in the transaction log, addressed to the caller who knows how to decode it, and to no one else.

The mechanism for announcing success is the same log, used deliberately. An [ARC-28](https://dev.algorand.co/arc-standards/arc-0028) *event* is an ARC-4 struct whose class name is the event's name; `arc4.emit` writes a log entry whose first four bytes identify the event --- `sha512_256` of its signature, exactly the trick method selectors use --- followed by the ARC-4 encoding of the fields. Two declarations and one line in `claim` give the vesting contract a voice:

**Example 8-16.** The claim that announces itself

<!-- example: examples/proving_it_works/simple_vesting_events.py mode=compile -->
<!-- finder: emit an event a stranger can find without reading state -->

```python
class Claimed(arc4.Struct):
    """ARC-28 event: the class name and field types are its signature."""

    beneficiary: arc4.Address
    amount: arc4.UInt64


# inside SimpleVesting.claim(), after the inner transfer:
        arc4.emit(Claimed(arc4.Address(Txn.sender), arc4.UInt64(claimable)))
```

The event's signature is `Claimed(address,uint64)`; any consumer that knows that string can compute the four-byte prefix and filter every log entry on the chain for it, with no app spec, no source, and no conversation with you. Watch the difference land in bytes. Claim the whole 1,000,000-unit schedule with the event in place and read the confirmation's log array back (entries arrive base64-encoded; shown decoded to hex):

```text
logs[0]  c2a3d5f7 · 32 bytes of beneficiary address · 00000000000f4240
logs[1]  151f7c75 · 00000000000f4240
```

Two entries, one claim. The first is the event: `c2a3d5f7` is the first four bytes of `sha512_256("Claimed(address,uint64)")`, and behind it ride the ARC-4-encoded fields --- the address, then `0x0f4240`, which is your 1,000,000. The second is the return value behind the `151f7c75` prefix Chapter 2 taught. Same log array, same claim, same number --- but the second entry answers the caller who already knows to decode it, and the first addresses strangers you have not met. That prefix is the difference between an event and a return value.

One fact makes this a design decision rather than a garnish, and it is the same fact that decided the greeter's fate in Chapter 2: deployed code is what it is. An event you did not emit is a record that does not exist, and there is no adding it to history later --- consumers can only ever learn about claims made *after* you ship the version that announces them. Emit events from every state-changing method from the first deployment, even if nobody is listening yet. Chapter 24 finishes this story --- the three shapes a log entry can take, telling them apart with one discriminator, and reading events back by prefix from an indexer --- when the subject turns to operating a contract other people depend on.

## Retrieval
Answer these from memory before moving on. Four reach back into earlier chapters.

1. `assert cond, "too high"` fails on-chain. Name the two artifacts the string "too high" ended up in, and say which one the caller had to be holding for the message to appear in their error.
2. What appears in an ARC-56 `sourceInfo` table for a *bare* `assert` with no message, and what does a client show the caller when it fires?
3. Name three things the ARC-4 router has already validated before your method body runs, and one thing it has not that people frequently assume it has.
4. Give the two separate reasons there is no reentrancy on Algorand, and say which of the two still applies when the inner transaction is an application call.
5. A method reports 2,400 opcodes consumed under `extra_opcode_budget=20_000`. How many application calls does the real group need, and where does the extra budget exist?
6. Your simulate of a failing group returns no object at all. What happened, and where are `pc` and the failure message?
7. *(From Chapter 6)* `total * elapsed // duration` overflows and `mulw`/`divw` does not, for the same inputs. Say precisely which value exceeds sixty-four bits in the first form and why it never has to in the second.
8. *(From Chapter 7)* Example 7-4 set every inner transaction's fee to zero and asserted that the caller's `Txn.fee` covered the whole pool. Say how you would find out, before deploying, how many transactions that pool actually has to cover for a given method.
9. *(From Chapter 3)* A method marked `readonly=True` increments a counter. Say what happens to the counter when a client calls it, why nothing reports an error, and what this chapter adds about the environment that call ran in.
10. *(From Chapter 2)* You already knew a program counter identifies a byte in the compiled approval program. Name the file that maps it back to a line of Python, say which tool writes it, and say which tool does not read it.
11. A return value and an ARC-28 event both travel in the transaction log. Say who each one is addressed to, and what a consumer needs to know to find every `Claimed(address,uint64)` event without holding the app spec.

## Exercises
1. A contract's `claim` and `opt_in_to_asset` methods compile to an approval program in which four of the program counters carrying an `assert` opcode are 176 (`check self.admin exists`), 178 (`admin only`), 311 (`check self.beneficiary exists`), and 313 (no entry in `sourceInfo` at all). Three callers each make one call. The first is a stranger calling `claim`. The second is a non-admin calling `opt_in_to_asset`. The third is the beneficiary calling `claim` twice in the same block, after a successful first claim, on the broken contract.

   a. **(Trace)** For each caller, say which program counter fails, what message the client displays if it holds the app spec, and what it displays if it does not.

   b. **(Debug)** One of the three does not fail at all; say what it returns and why that is worse than failing.

   c. **(Trace)** Two of those four program counters --- 176 and 311 --- are PuyaPy's own bookkeeping rather than anything the author wrote, and in *this* contract neither of them can ever fire. Say why not, in one sentence about `__init__`.

   d. **(Extend)** Describe a contract in which one of them *would* fire, and say what the caller of that contract would see.

2. Below are seven statements. Five form the body of a negative test that proves an unauthorized caller is rejected *for the right reason*; two do not belong. The contract is deployed at `app_id`, its spec is at `spec_path`, and `claim` is beneficiary-only.

   ```python
   def test_a_stranger_cannot_claim() -> None:
       algorand = AlgorandClient.from_environment()
       ...
   ```

   The statements: (a) `client = AppClient(AppClientParams(app_spec=Path(spec_path).read_text(), algorand=algorand, app_id=app_id, default_sender=algorand.account.random().address))`; (b) `group = algorand.new_group().add_app_call_method_call(client.params.call(AppClientMethodCallParams(method="claim", args=[])))`; (c) `with pytest.raises(LogicError) as rejected:`; (d) `group.simulate(skip_signatures=True)`; (e) `assert "not the beneficiary" in rejected.value.message`; (f) `result = group.simulate()` followed by `assert result.simulate_response["txn-groups"][0]["failure-message"]`; (g) `assert rejected.value is not None`.

   a. **(Parsons)** Select the five and order them.

   b. **(Debug)** For each reject, say what is wrong with it: one of them describes an API that cannot work the way it is written, and the other passes in situations the test was written to rule out; name two such situations concretely.

   c. **(Debug)** Statement (e) uses `in` rather than `==`. Say what `LogicError.message` actually contains that makes the equality version fail.

   d. **(Compare)** Say what you would lose if you weakened the assertion to `pytest.raises(LogicError)` alone.

3. A team's contract has run in production for six weeks. This morning every call to `settle` fails. Their on-call engineer has one error string from a user's wallet and nothing else:

   ```console
   transaction 5KQD...7WPX: logic eval error:
   assert failed pc=1174. Details: app=7311, pc=1174
   ```

   They have the deployed app spec. They look up 1174 in `sourceInfo` and it is not there. They can reproduce the failure with a simulate and get the same program counter.

   a. **(Trace)** Before working anything else out, write down the two distinct explanations for a program counter that is missing from `sourceInfo`, and say which artifact would tell them apart.

   b. **(Debug)** Name the file that would resolve 1174 to a line of Python, say when it was written, and say why the team probably does not have it.

   c. **(Debug)** Assume they still have the exact source commit that was deployed. Give the procedure that recovers the line anyway, and name the one thing that must be true for it to be valid.

   d. **(Debug)** `settle` worked for six weeks and now fails for everyone, with no deployment and no code change. Give two mechanisms that produce that pattern --- one arithmetic and one about resources --- and say which one the program counter's *absence* from `sourceInfo` makes more likely.

4. You are choosing how a contract reports its refusals, and there are four options: a bare `assert`, an `assert` with a message, `logged_assert()`, and `op.err()`.

   a. **(Compare)** Compare them on five axes: bytecode cost, what appears in the app spec, what a caller holding the spec sees, what a caller *without* the spec sees, and what is recoverable after a real submitted transaction fails.

   b. **(Compare)** Two of the four are dominated: they are worse than another option on at least one axis and better on none. Name them and name what dominates them.

   c. **(Compare)** Of the two that survive, say which you would choose for a single-tenant application whose only client you also write, and which for a public contract that other teams will call from TypeScript without ever contacting you.

   d. **(Compare)** Give a concrete scenario in which you would pay `logged_assert()`'s bytecode on the single-tenant application anyway.

5. Extend the fixed vesting contract with an admin method `revoke()` that ends the schedule immediately: everything vested up to the moment of the call stays claimable by the beneficiary, and everything not yet vested returns to the admin. Write the test suite for it *first*, from the requirement, before you write the method --- there is no code yet, and that is the point of the ordering.

   a. **(Extend)** Derive the test cases from the requirement in the paragraph above. Aim for at least five, and expect at least one of them to be about a second call to `revoke`.

   b. **(Extend)** Write the tests, and watch them fail against a contract with no `revoke` at all.

   c. **(Extend)** Write the method, and run the suite until it passes.

   d. **(Extend)** Add one more test: at production supply, using Example 6-7's arithmetic.

   e. **(Debug)** Write down which of your tests would still have passed if `revoke` had forgotten to stop the schedule, and fix that test rather than the contract.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can say where an assert message is stored, prove it is not in the bytecode, explain what a caller without the app spec sees, and choose between `assert`, `logged_assert()` and `op.err()` for a given contract.
- [ ] I can name what the ARC-4 router validates before my method runs, stop writing assertions that restate it, and give the two separate reasons there is no reentrancy on Algorand.
- [ ] I can run a method through simulate against live state, read its opcode cost with extra budget, discover the resources it touched, and say why none of that is permission to submit.
- [ ] I can turn a program counter into a line of Python using the `.puya.map` file, and say what it means when a program counter does not resolve.
- [ ] I can write a test that would go red if the contract were wrong, say why a test written from the code cannot, and pin a negative test to the specific message its assertion produces.

## Handoff: What the Vesting Project's Tests Need
Chapter 9 builds the production version of this chapter's vesting contract: multiple beneficiaries, schedules in box storage, a real deposit, and a payout that actually leaves the contract. Its test suite is where every technique in this chapter is used at once. Table 8-2 lists the examples the project leans on and where each one appears.

: Table 8-2. Examples from this chapter that the vesting project depends on

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| Example 8-2 | Giving every rejection on the claim path a message a beneficiary can act on | The project has more than a dozen assertions and no bare ones. Pick the authorization check on the claim path and write the message you would put on it, then compare. |
| Example 8-6 | `deposit_tokens`, which takes a typed transfer parameter | The project asserts the transfer's asset, amount and receiver, and never asserts that it is an asset transfer or that it sits directly before the app call. Say which of those the router already guaranteed, and why the group size is still checked by hand. |
| Example 8-13 | Deciding, for each of the project's methods, what the requirement says rather than what the draft does | Vesting has one requirement that is easy to state and easy to implement wrongly. Write it as one sentence, then write the assertion that would fail if the contract broke it. |
| Example 8-14 | The fast half of the suite, over the schedule arithmetic | Vesting is entirely a function of the clock. Say which of the project's methods can be tested with `patch_global_fields` alone, and which cannot and why. |
| Example 8-15 | One test per security assertion, each pinned to its message | The project's admin-only methods each need a stranger test. Write down what such a test must assert beyond "an exception was raised". |
| Example 8-9 | Sizing the group for a multi-beneficiary payout | A payout loop's cost scales with beneficiaries. Say how you would find the point at which the group needs a second app call, without deploying twice. |
| Example 8-12 | The debugging procedure when a claim fails on LocalNet | The project's build writes a `.puya.map` beside its bytecode. Say what you would do with a `pc` from a failed claim, in order, and where the procedure stops working. |
| Example 8-16 | Events on every state-changing method, from the first deployment | The project has five state-changing methods. Decide which of them deserve an event and what belongs in each payload, then compare against what the project ships. |
