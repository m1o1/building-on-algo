\newpage

# Proving It Works: Tests, Simulation, and Failure

Every chapter of Part I so far has ended with a contract that works. This one starts with a contract that works, and spends its length on the difference between *works* and *is known to work*. The gap between those two is not filled by writing more code. It is filled by three skills the rest of the book will assume you have: making a contract explain its own refusals, running a call without committing it, and writing a test that can actually fail.

That last one is the whole chapter in a phrase. **A test suite is not evidence unless some arrangement of the world would have turned it red.** The Mini-Build here is a vesting contract with a green suite and three defects, and the suite is green *because of* how it was written, not in spite of it.

## The Problem
Here is a failure with a name: **the vesting contract that passed.**

A team ships a four-year linear vesting contract for their token. It has a cliff, a beneficiary, a schedule fixed at deposit time, and an inner asset transfer that pays out. It has a test suite: seven tests, all green, run on every commit for two months. The suite covers the cliff, covers the linear ramp, covers a claim, covers a stranger being rejected.

Three things are wrong with the contract. The first is a claim that moves nothing: calling `claim` a second time in the same block returns `0` and reports success, so a wallet shows a confirmed transaction and no tokens. The second is arithmetic: the vested amount is computed as `total * elapsed // duration`, and that product exceeds sixty-four bits for any supply above 146,235,605,498 base units --- which at six decimals is a little over 146,000 tokens, a figure that sounds small because it is. The third is a rejection with no reason: a `claim` from the wrong account fails with a program counter and an empty message.

None of the three is caught, and the reason is the same for all three. The tests were written by reading the contract. `test_a_claim_returns_zero_when_nothing_is_due` asserts that `claim()` returns `0` --- which is what the contract does, and the opposite of what the requirement says. The overflow test uses four Algo of supply because that is what the fixture had. The rejection test asserts that an `AssertionError` is raised and never looks at its message.

The defect is not in any of the three tests. It is in what a test was taken to be for: **a test that asserts what the code does can never disagree with the code.** Two months of green means two months of asking the contract to confirm itself.

## What You'll Be Able to Do
By the end of this chapter you will be able to:

- Say exactly where the string in `assert cond, "message"` ends up, why it is not in the bytecode, and what a caller who does not hold your app spec sees instead
- Choose between `assert`, `logged_assert()`, `logged_err()` and `op.err()` for a given contract, and state what each one costs and buys
- Name the validation the ARC-4 router already performs, so you stop writing assertions that restate it, and write the ones it cannot perform
- Explain why there is no reentrancy on Algorand, in two separate facts, and say what that does and does not license you to do
- Run a method against real ledger state without committing it, read the opcodes it consumed, discover the resources it touched, and see the trace of its execution
- Turn a program counter reported by a failing call back into the line of Python that emitted it
- Write unit tests against an in-memory ledger you can rewrite, and negative tests that prove a rejection happened *for the reason you intended*

{{fig:simulate-trace}} is the picture this chapter hangs on, and it is worth reading before any code, because almost everything that follows is either a way to put more information into that response or a way to get more information out of it. It annotates what comes back when a simulated call is rejected.

{{include-fig:simulate-trace}}

The single most important thing on that page is at the top: the HTTP request itself *succeeded*. A rejected simulation is a `200 OK` whose body reports the failure, which is why a test that asserts on the status code will pass no matter what the contract does. The information you want --- which assertion fired, where, and what the program had done before it got there --- is in `failure-message`, `failed-at`, and the execution trace. The diagram draws that body as an object because that is what the node returned; whether your own code ever gets to hold it is a separate question this chapter answers later, and the answer surprises people.

The second most important thing is what is *not* on the page. There is no Python. There is a program counter, there is whatever string your app spec can associate with that program counter, and --- when the client compiled the contract itself, as the client behind every `LogicError` transcript so far did --- a line number into the *generated TEAL*. Getting from any of those back to a line in your source file is a hop the tooling does not make for you. The third of the four sections that follow closes that gap with a sixteen-line function.

## The Mini-Build, Broken
Example: A vesting contract that fails {#ex:simple-vesting-broken}

<!-- finder: see a contract whose green test suite proves nothing -->

{{include-ex:simple-vesting-broken}}

{{ex:simple-vesting-broken}} is the minimal working version of the vesting contract {{ch:token-vesting}} builds. It is complete, it compiles without a warning, and it does the job: an admin opts it into a token, deposits a supply against a schedule, and the beneficiary claims what has vested. It ships with a test suite at `examples/ch07_proving_it_works/simple_vesting_test.py`, and that suite is the point of this chapter rather than an accessory to it.

*Predict: three defects, and all three survive a seven-test suite. One is a success that should be a failure, one is arithmetic, and one is a failure that says nothing. Write down where in the sixty lines of logic you would look for each, before reading on.*

Run the suite. This is a real run, on your machine, with no LocalNet and no Docker:

```console
$ uv run --group test python -m pytest \
      examples/ch07_proving_it_works/simple_vesting_test.py -q
.......                                                     [100%]
7 passed in 0.15s
```

Seven green. Four of those seven exercise the repaired contract, which is on disk beside the broken one; the other three are the ones to read now:

```python
test_the_broken_version_reports_success_for_a_claim_that_moved_nothing
test_the_broken_version_rejects_a_stranger_without_saying_why
test_the_broken_schedule_overflows_at_a_production_supply
```

Those three are green because they assert what the broken contract does. They are not sabotage and they are not a straw man --- they are the exact shape a suite takes when it is written after the code, by the person who wrote the code, from the code. Every one of them is a true statement about the program. Not one of them is a statement about the requirement.

The move that separates the two is small enough to fit on one page. Here is a single behaviour, asserted both ways:

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

Do that to all three and the picture inverts. Same contract, same fixtures, three assertions changed from *what it does* to *what it is for*, in a scratch file so the shipped suite stays intact. The names below are deliberately not the names in `simple_vesting_test.py`: these run against the broken contract, and the shipped tests of similar name run against the repaired one.

```console
$ uv run --group test python -m pytest /tmp/req/requirement_tests_test.py -q
FFF                                                         [100%]

    def test_a_claim_that_moves_nothing_must_be_refused() -> None:
        ...
>           with pytest.raises(AssertionError, match="nothing vested"):
E           Failed: DID NOT RAISE <class 'AssertionError'>
```

That is defect one, and it is the one people ship most often. `claim` opens with an early return: if nothing has vested since the last claim, return `0`. The method succeeds, the transaction confirms, the beneficiary's wallet shows a green tick, and no tokens moved. A caller cannot distinguish "you have claimed everything available" from "the payout worked" without reading the return value, and most clients do not. **A method that cannot do its job should refuse, not report zero.** The version of this that costs real money is a claim button that appears to work and silently does nothing for four weeks.

*Predict: the second failure is the arithmetic. Before reading it, say what `total * elapsed // duration` does when `total` is ten billion tokens at six decimals and `elapsed` is two years in seconds --- and say which of the two operations is the problem.*

```console
    def test_the_schedule_must_survive_a_production_supply() -> None:
        ...
>           assert contract.vested(at_two_years) == BIG_TOTAL // 2
E           OverflowError: * overflows
```

`result = 630720000000000000000000, op = '*'`, reads pytest's dump of the emulator's own arithmetic frame, against a ceiling of about 1.8 x 10^19. Defect two is the multiply, not the divide, and the shape of it is exactly {{ex:mulw-split}} from {{ch:numbers-and-time}}: the intermediate product exceeds sixty-four bits even though the quotient is comfortably small. It is invisible at four Algo of supply and unconditional at production supply, which means it is a defect that appears on the day the contract matters and not before.

There is a band in between that is worse than either. Above roughly 146,000 tokens the product can overflow, but only once `elapsed` has grown large enough; below roughly 585,000 tokens it cannot overflow at the cliff. A supply between those two figures produces a contract that pays the first claims correctly and then bricks partway through the term --- `claimable()` included, so the beneficiary cannot even ask what they are owed. A defect that passes a testnet run at a plausible supply and detonates in month nine is the shape to be most afraid of.

It is worth being explicit that this *is* testable, because it is commonly assumed not to be. `algorand-python-testing` raises `ArithmeticError` and its subclasses for exactly the operations that would abort on the AVM, so a test that pins the overflow costs one line.

```console
    def test_a_stranger_must_be_told_why() -> None:
        ...
>           assert str(caught.value) == "not the beneficiary"
E           AssertionError: assert '' == 'not the beneficiary'
```

Defect three, and the empty string on the right of that comparison is the whole of it. `claim` opens with `assert Txn.sender == self.beneficiary.value` --- a bare assertion, no message. It rejects the stranger correctly. It is a security control that works. And what it produces, on-chain, is a program counter and nothing else: no string in the bytecode, no entry in the app spec, nothing for a client to substitute. The next section is about where that string would have gone.

Four sections follow. The first is what a contract can say when it refuses, and the four ways of saying it. The second is where the refusal belongs, which turns out to be later in the method than most people put it, and includes the reason a whole class of defensive code from other chains has nothing to defend against here. The third is how to run a call without committing it, which is where the program counter, the opcode cost, the touched resources and the execution trace all come from. The fourth is tests that can fail --- the requirement-shaped assertion, the in-memory ledger, and the negative test. Each ends by naming what it repairs in the vesting contract, and two of them repair nothing in it directly.

## Making the Contract Say Why
Start with the thing everyone assumes and nobody checks: **the string in `assert cond, "message"` is not in your program.**

Example: Where the assert message actually goes {#ex:assert-message-home}

<!-- finder: prove the assert message is absent from the compiled bytecode -->

{{include-ex:assert-message-home}}

{{ex:assert-message-home}} has two rejections in one method, and the difference between them is one comma. Compile it --- PuyaPy 5.9 writes the ARC-56 spec by default, so there is no flag to remember --- and go looking for the message:

```console
$ uv run --group compile python -m puyapy --target-avm-version 11 \
      --out-dir /tmp/ch07 examples/ch07_proving_it_works/assert_message_home.py
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

Two consequences follow immediately, and both matter more than they sound.

**A caller who does not hold your app spec gets a number.** Not a truncated message, not a generic one --- a program counter. Anyone integrating with your contract from a different toolchain, a different language, or a block explorer sees `assert failed pc=85` and has to come and ask you what it means.

**A bare assert has no entry at all.** Look at that table again. There are four rows for a method with two assertions, and three of the four are PuyaPy's own: `check self.owner exists` and `check self.entries exists` are existence assertions the compiler inserts in front of every global-state read, and `invalid number of bytes for arc4.uint64` is the ABI router validating an argument's width. Exactly one row belongs to the author. The second authored assertion, `assert count > UInt64(0)` with no message, is not in the table at all. It compiled to an `assert` opcode with no diagnostics attached, which makes it invisible to every tool that reads the app spec.

That is defect three of the Mini-Build, and it is worth seeing what it looks like from the outside. Compile the broken vesting contract --- the same command, which also writes the `.puya.map` file the next section is about --- and run the lookup at the two program counters that sit two bytes apart in `claim`:

```console
$ uv run --group compile python -m puyapy --target-avm-version 11 \
      --out-dir /tmp/ch07 examples/ch07_proving_it_works/simple_vesting_broken.py
$ uv run --group test python examples/ch07_proving_it_works/pc_to_source_line.py \
      /tmp/ch07/SimpleVesting.approval.puya.map 311
pc=311  simple_vesting_broken.py:75
   |  assert Txn.sender == self.beneficiary.value
   |  op=assert // check self.beneficiary exists
   |  error='check self.beneficiary exists'

$ uv run --group test python examples/ch07_proving_it_works/pc_to_source_line.py \
      /tmp/ch07/SimpleVesting.approval.puya.map 313
pc=313  simple_vesting_broken.py:75
   |  assert Txn.sender == self.beneficiary.value
   |  op=assert
```

Both are wrapped at the `|` separators to fit the page; the tool prints one line per lookup.

Two assertions, one source line, adjacent in the bytecode. The first is PuyaPy's --- it checks that the global-state key exists before reading it --- and it has a message. The second is the author's actual authorization check, and it has nothing. A stranger who is correctly rejected by that contract receives a program counter pointing at an assertion that no artifact anywhere can name, sitting immediately beside one the compiler wrote for its own bookkeeping.

*Predict: the message is not on-chain. Say what a contract would have to do to put it there, and what that would cost, before reading on.*

There is a way, it costs bytecode, and it is a shipped API rather than something you write yourself.

Example: `logged_assert()` writes the reason into the program {#ex:logged-assert}

<!-- finder: emit a machine-readable error code that survives without the app spec -->

{{include-ex:logged-assert}}

The load-bearing call is `logged_assert(...)`, and it comes from `algopy` directly along with its unconditional sibling `logged_err` --- these are not helpers this book invents. Each takes an `error_code`, an optional `error_message`, and an optional `prefix` of `"ERR"` or `"AER"`, and lowers to a `log` of `ERR:<code>[:<message>]` followed by a failure. That is ARC-65. Compile {{ex:logged-assert}} and the two probes from the previous example come back changed: the approval program is 158 bytes rather than 111 --- and a like-for-like comparison would be slightly worse still, since the logged version also drops a global-state read the earlier one paid for --- while `b"owner only" in bytecode` is still `False`, `b"ERR:ownerOnly" in bytecode` is now `True` --- the code is in the program, in the shape ARC-65 specifies, and the human sentence rides along with it as `b"ERR:positiveCount:count must be > 0"`. (The `arcs: [22, 28]` line in the app spec is not evidence of any of this; PuyaPy emits it for every `ARC4Contract`.)

Be precise about what that buys, because the obvious answer is wrong. On a *submitted* transaction that fails, it buys nothing: a node that rejects a transaction returns a message and no logs array, and no amount of logging inside your contract changes that. What it buys is one specific thing: **a caller who does not hold your app spec can recover the reason from `txn-result.logs` in a simulate.** For a public, composable contract that other teams will integrate against without asking you for artifacts, that is worth paying bytecode for. For an application you own end to end, whose only clients ship with your app spec, it is bytes you are paying for a lookup you could already do.

Example: `logged_err()` and the return-type deadlock {#ex:logged-err}

<!-- finder: place an unconditional failure inside a method that must return a value -->

{{include-ex:logged-err}}

{{ex:logged-err}} exists because of a trap that is annoying out of proportion to its size. `logged_err` is typed `-> None` in the stubs, so in a value-returning method it cannot be the last statement: without a trailing `return`, mypy reports `Missing return statement`; with one, PuyaPy reports unreachable code. The shape that works is the one in the example --- a local, an `if`/`elif`/`else` where the `else` fails, and exactly one `return` at the end. In a method returning `None` the problem does not arise.

Example: Two spellings of an unconditional failure {#ex:op-err}

<!-- finder: compare the two spellings of an unconditional failure -->

{{include-ex:op-err}}

The two methods in {{ex:op-err}} compile to the identical opcode. `op.err()` lowers to `err`. So does `assert False, "closed for now"` --- an assertion the compiler can prove always fails becomes an unconditional `err` rather than a comparison. The only difference is in the app spec, read the same way as before against `/tmp/ch07/Gate.arc56.json`:

```python
>>> spec["sourceInfo"]["approval"]["sourceInfo"]
[{'pc': [35], 'errorMessage': 'closed for now'}]
```

One entry, for the `assert False` form. `op.err()` produces none. There is no case in which `op.err()` is better than `assert False, "..."`, and there is a case in which it is actively worse: a trailing `op.err()` after an `if`/`elif` chain can be folded by the optimizer into a bare assertion on the preceding branch, at which point you have a rejection with no message in a place you did not write one.

*What this section repairs in the vesting contract:* defect three. The bare `assert Txn.sender == self.beneficiary.value` gains a message, and the fixed version chooses plain `assert` with a string over `logged_assert` --- a single-beneficiary contract with one known client does not need the bytes.

## Failing in the Right Place
The second question is not *how* to refuse but *where*, and the usual answer is too early. A great deal of defensive code in Algorand contracts is checking something that has already been checked, by the router, before a line of your method ran.

Example: Validate at the boundary, not before it {#ex:validate-at-boundary}

<!-- finder: see which checks the ARC-4 router has already performed for you -->

{{include-ex:validate-at-boundary}}

Every assertion in {{ex:validate-at-boundary}} checks *meaning*. None of them checks *shape*, because the router already did. Compile it and read the TEAL and you find, before your first line:

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

Read that as a list of things you do not have to write. The OnCompletion is NoOp. The application exists rather than being created. The selector matched a method you declared, and an unknown selector already hit `err`. Every ABI argument is the right width --- eight bytes for a `UInt64` here, and for other types the same check with the type named in the message, so an `arc4.Address` parameter that arrives short fails with `invalid number of bytes for arc4.static_array<arc4.uint8, 32>` and a dynamic array whose header disagrees with its contents fails on an `extract_uint16` with `invalid array length header`. And for a `gtxn.AssetTransferTransaction` parameter, both the type *and the position*: PuyaPy lowers a typed group argument position-relatively, as `GroupIndex - 1`, and asserts the type enum.

So `assert Txn.num_app_args == 3`, `assert len(addr.bytes) == 32`, and `assert Global.group_size == 2` in a method whose transfer arrives as a declared parameter are all redundant. The last one deserves a caveat. As {{ex:group-bounds}} showed, a size assertion is not redundant when you are reading a neighbour *by index*, and it is not redundant when the thing you are bounding is how many times the method can appear. It is redundant only as a restatement of what the typed parameter already pins.

One thing {{ex:validate-at-boundary}} does not do is bookkeeping. `stake` checks the deposit and returns its amount, and then the method ends --- nothing anywhere records that this account staked. That is scope rather than oversight: the subject is where validation belongs, and the credit would only be noise here. A staking contract you would actually deploy writes the depositor's balance before it returns, and {{ch:yield-farming}} is where that ledger gets built.

**The organizing principle is that the router validates shape and you validate meaning.** Meaning is everything the router cannot know: that this asset is the one you configured, that this amount is above your floor, that this receiver is your own application account, that this sender is the caller, that this contract has been initialized, that this caller is the admin. That list should look familiar --- it is the four questions from {{ch:moving-value}} with authorization and lifecycle added.

One more piece of vocabulary comes out of that TEAL. When a failure message reads `check self.admin exists`, it is not something you wrote and not a bug: PuyaPy inserts an existence assertion in front of every global-state read, and that is the message it attaches. Seeing it in a stack trace means a state key was read before anything wrote it.

*Predict: on Ethereum, the canonical ordering rule is checks-effects-interactions --- never send value before you have updated your state, because the recipient can call back in. Say what the equivalent rule is here, before reading the next example.*

Example: There is no reentrancy on Algorand {#ex:no-reentrancy}

<!-- finder: write interaction-before-effects deliberately and see why it is safe -->

{{include-ex:no-reentrancy}}

{{ex:no-reentrancy}} belongs in this section rather than a later one because it is the largest single case of a check in the wrong place: an entire family of guards, imported wholesale from other chains, defending against something the AVM does not permit. Its `withdraw` sends the money and only then zeroes the balance. On the EVM that is the reentrancy bug in its textbook form. Here it is safe, and it is safe for two separate reasons that are worth keeping separate, because they have different scopes.

The first is that **there are no callbacks.** An inner payment to an account does not run anything. The AVM has no mechanism by which the receiver of value gets control. There is nothing to re-enter because nothing was entered.

The second applies when the inner transaction *is* an application call, which is a case the first reason does not cover. The AVM refuses at `itxn_submit` if the application being called already appears in the current call stack: a self-call is rejected outright, and an ancestor appearing again produces `attempt to re-enter <appId>`. The check walks the ancestor chain only, so two *sibling* calls to the same application in one group are permitted --- this is not a global "at most once" rule. The same walk bounds recursion depth: a maximum of eight nested application calls beneath the top-level one.

One thing in {{ex:no-reentrancy}} is a shortcut rather than a lesson, and it is worth naming before anybody copies the file. The vault keeps balances in local state, which fits on one screen and is wrong for money: a ClearState transaction always succeeds --- the clear program cannot refuse, whatever you put in it --- so a depositor who takes the ordinary "opt out of this application" path in their wallet deletes their own balance and strands the funds in the application account with no method able to move them. Deposit records belong in a box. That is a separate chapter's material, and the example says so in its docstring rather than pretending the shortcut is free.

What this licenses is narrow, and it is worth stating narrowly. It licenses writing state in whatever order reads best. It does not license writing state in whatever order you like, because there is an ordering constraint that looks identical and is not about reentrancy at all: accumulators must be updated before per-user values are computed against them, because a global figure that has not caught up is arithmetically wrong regardless of who calls what. {{ch:yield-farming}} is built on that distinction. Getting the two confused costs you either way --- one direction you write guards against an attack that cannot happen, the other you skip an ordering rule that has nothing to do with attacks.

*What this section repairs in the vesting contract:* nothing. Both of the Mini-Build's remaining defects live elsewhere. This section is here because the next thing you do with a failing contract is read its execution, and you cannot read an execution without knowing which parts of it the toolchain performed on your behalf.

## Running a Call Without Committing It
Everything so far has been about what a contract says when it fails. This section is about running it in a place where failing is free.

Example: Simulate instead of submit {#ex:simulate-instead-of-submit}

<!-- finder: run a method against real ledger state without committing anything -->

{{include-ex:simulate-instead-of-submit}}

`simulate` runs the real compiled program against the real current ledger, honours the whole group, and throws the result away. It is not a mock and it is not an emulator: the state it reads is the state a submitted transaction would have read a moment earlier. What you get back is what the call *would* have returned and what it *would* have cost.

Two details in {{ex:simulate-instead-of-submit}} are the ones people get wrong. `result.returns` holds one entry per ABI method call, not one per transaction, so indexing it positionally against your group is a bug waiting for the first payment you add --- index from the end, or track the position yourself. And `app-budget-consumed` is per group, not per transaction, for the reason the next example is about.

Example: Simulate with extra opcode budget {#ex:simulate-extra-budget}

<!-- finder: measure what a call costs when it does not fit in one app call's budget -->

{{include-ex:simulate-extra-budget}}

An application call gets 700 opcodes. A group gets 700 times the number of application calls in it, pooled --- any one call may spend the whole pool. This is why the budget is a group figure and why the standard remedy for an expensive method is padding the group with extra calls to a cheap method, which {{ch:patterns}} covers as a pattern.

The awkward part is measuring. A method that needs 2,400 opcodes fails at 700 with `dynamic cost budget exceeded, executing <opcode>: local program cost was 700` --- a message that tells you the ceiling you hit and not the floor you needed. Guessing the multiple is a loop of deploy, fail, add a call, repeat. `extra_opcode_budget` collapses that loop: it is a simulate-only allowance, up to 320,000, that exists so the response can tell you the true cost. The load-bearing line in {{ex:simulate-extra-budget}} is the `extra_opcode_budget=20_000` argument; everything after it just reads `app-budget-consumed` and divides.

**The budget you buy exists only inside the simulation.** It buys a measurement, not a bigger program. A method that reports 2,400 still needs four application calls in the real group.

Example: Unnamed resources and an execution trace {#ex:simulate-unnamed-resources}

<!-- finder: ask the node which accounts, assets and boxes a call actually touched -->

{{include-ex:simulate-unnamed-resources}}

{{ex:simulate-unnamed-resources}} names two facilities explicitly, and both are already on --- algokit-utils enables them on every simulate it makes, so writing them out is documentation of what the call depends on rather than a switch. Note which direction each argument actually moves. `allow_unnamed_resources=True` lets the call reach accounts, assets, applications and boxes it never declared, and reports them back under `unnamed-resources-accessed`. That is a **discovery mechanism, not a permission**: the submitted transaction still has to declare every one of them, and algokit-utils will populate them for you from exactly this response. Turning it on to make a failing call pass, and then submitting, gets you the same failure with more steps.

`exec_trace_config` controls the opcode-by-opcode trace: one entry per executed opcode, each carrying a program counter and, if you asked for them, stack and scratch changes. algokit-utils already enables a full four-field trace on every simulate it makes, so passing `SimulateTraceConfig(enable=True, stack_change=True)` *narrows* the default to the two fields the example reads rather than switching anything on. The trace is the raw material behind {{fig:simulate-trace}} and behind the last example in this section. Note also what a trace unit does *not* carry: there is no log field on it. Logs are on the transaction result, not on the trace.

Example: One return value, three call paths, three shapes {#ex:abi-return-shapes}

<!-- finder: get the decoded return value from each of the three ways to call a method -->

{{include-ex:abi-return-shapes}}

{{ex:abi-return-shapes}} is here rather than in {{ch:contracts}} because the shapes only diverge once you are switching between submitting and simulating, which is what debugging consists of. `AppClient.send.call()` hands you the decoded Python value. `algorand.send.app_call_method_call()` hands you an `ABIReturn` wrapper, or `None` if there was no method call at all --- so `abi_return is None` and `abi_return.value is None` are different facts, and conflating them turns a missing method into a method that returned nothing. And a simulate has no `abi_return` at all; it has `returns`.

One thing in {{ex:abi-return-shapes}} is worth pausing on, because it is the second half of a fact {{ch:contracts}} started. You already know that `readonly=True` is a promise to callers rather than anything the compiler or the AVM enforces, and that a readonly method which writes state has its writes silently discarded. What this chapter adds is *how* the client keeps that promise: it answers the call with a simulate, and that simulate runs with signatures skipped and the maximum extra opcode budget granted. **A readonly method can therefore succeed in your client and fail the moment anyone submits it for real** --- because it exceeds 700 opcodes, or because it needed a signature the simulation waived. Submit every readonly method at least once before you trust it.

*Predict: you have a failing call. You have a program counter from the error and a message from the app spec. What is still missing, and where would it have to come from?*

Example: Reading a program counter back to a source line {#ex:pc-to-source-line}

<!-- finder: turn a program counter into the Python statement that produced it -->

{{include-ex:pc-to-source-line}}

What is missing is the line of Python, and the reason no tool gives it to you is a gap between two artifacts. The ARC-56 app spec carries `sourceInfo` keyed by program counter --- but PuyaPy never populates its `teal` field, and sets `pcOffsetMethod` to `none`, so `LogicError.line_no` comes back `None`. Meanwhile PuyaPy writes a second file next to the bytecode, `<Contract>.approval.puya.map`, by default, on every compile. It is a Source Map v3 whose `mappings` array has one segment per bytecode byte --- indexed, in other words, by program counter --- resolving to a zero-based line number in the Python source. **algokit-utils never reads that file.**

{{ex:pc-to-source-line}}'s `explain_pc` is the sixteen lines that close the gap, and the load-bearing line is `SourceMap(raw).get_line_for_pc(pc)`: `algosdk` already ships the Source Map v3 decoder, so the example is mostly plumbing around one call. Point it at the map and a program counter and it answers (wrapped here at the `|` separators to fit the page):

```console
$ uv run --group test python examples/ch07_proving_it_works/pc_to_source_line.py \
      /tmp/ch07/SimpleVesting.approval.puya.map 178
pc=178  simple_vesting_broken.py:39
   |  assert Txn.sender == self.admin.value, "admin only"
   |  op=assert // admin only  |  error='admin only'

$ uv run --group test python examples/ch07_proving_it_works/pc_to_source_line.py \
      /tmp/ch07/SimpleVesting.approval.puya.map 999
pc=999: no mapping
```

The second call is the honest half, though not for the reason people expect. `999` is simply past the end of a 450-byte program. Every program counter *inside* the program resolves, because the map carries one segment per byte --- so a failed lookup is not telling you "this byte has no source", it is telling you the number came from somewhere else. The two cases you will actually meet are a program counter from the clear-state program looked up in the approval map, and a map rebuilt from a commit other than the one deployed, which resolves to a line number that is real and wrong. A debugging tool that pretends otherwise is worse than one that says so.

Keep the map file. It is written on every compile, it is a few kilobytes, and it is the only artifact that connects the number in a production error report to a line you can go and read. If your deployment pipeline discards build outputs other than the app spec, this is the one to add back.

*What this section repairs in the vesting contract:* nothing directly, and everything about how you would have found the defects. The overflow shows up in a simulate as a rejection at a program counter; that program counter resolves, through the map, to `return self.total.value * elapsed // duration`.

## Tests That Can Actually Fail
Three things: the assertion that can fail, the ledger you can rewrite, and the negative test that pins a rejection to its reason.

Example: The same behaviour, asserted from the code and from the requirement {#ex:requirement-vs-code}

<!-- finder: see the one assertion that can tell a correct contract from an incorrect one -->

{{include-ex:requirement-vs-code}}

{{ex:requirement-vs-code}} is the chapter's thesis with everything else stripped away. Two vaults, one requirement --- *a withdrawal above the cap must be refused* --- and one of them meets it. `ClampingVault` quietly reduces an over-cap request to the cap and reports success. `RefusingVault` refuses.

The load-bearing difference is not in the contracts but in its test file. An assertion copied out of the code, `withdraw` returns what it paid, is true of both vaults. It is a fact about the implementation, and no implementation that is wrong in this particular way could ever make it fail. The assertion taken from the requirement is `pytest.raises(AssertionError, match="over the cap")`, and it separates them on the first run. **A test that both a correct and an incorrect implementation pass is not a test.**

*Predict: a third vault rejects over-cap requests but pays out one unit less than asked on every withdrawal. Which of the two assertions catches it? Say what that tells you about the limits of the rule you just read.*

Example: An in-memory ledger you are allowed to rewrite {#ex:unit-test-context}

<!-- finder: test time-dependent behaviour without waiting or deploying -->

{{include-ex:unit-test-context}}

`algorand-python-testing` runs your contract's methods as ordinary Python against an in-memory ledger. There is no compilation, no deployment, no network, and no Docker; a test takes milliseconds. What makes {{ex:unit-test-context}} worth a section is not the speed but the writability of the ledger. `ctx.ledger.patch_global_fields(latest_timestamp=...)` is time travel in one assignment, which turns a four-year vesting schedule into a test that runs instantly. `ctx.any.account()` produces a stranger, and `ctx.txn.create_group([...])` puts that stranger in the sender field so an authorization check can be exercised from the wrong side.

The contract's own test file, `unit_test_context_test.py`, is four tests: an entry before the deadline, an entry after the deadline with the clock moved between them, a deadline set in the past, and a stranger attempting an owner-only method. Every one of them is a negative test or a boundary, and none of them takes longer than a millisecond.

What you give up is fidelity, and it is a real loss rather than a formality. {{tbl:integration-vs-unit}} sets the two side by side.

Table: Integration tests compared with unit tests {#tbl:integration-vs-unit}

| Aspect | Integration tests | Unit tests |
|------------|--------------------------------|---------------------------|
| Speed | Seconds | Milliseconds |
| What runs | Compiled TEAL on a real AVM | Your Python source |
| What it covers | Contract, client, ABI encoding, resources | Contract logic only |
| What it catches | Opcode budget, encoding, real network behaviour | Logic errors, arithmetic |
| When one fails | The bug may be in the contract or the client | The bug is in the contract |
| Requires | LocalNet and Docker | Nothing |
| Best for | Final validation and security | Rapid iteration on logic |

The line worth internalizing is the third row. A unit test cannot fail for opcode budget, because it never ran an opcode. It cannot fail for a missing resource reference, an MBR shortfall, or an ABI encoding mismatch. Those are precisely the failures that appear for the first time on a real network, which is why the answer is not to choose. Iterate in the emulator; validate on LocalNet.

The emulator's error messages diverge from the AVM's in wording, too, and it is worth knowing which is which. On an overflow the emulator raises `OverflowError("* overflows")`; the AVM says `* overflowed`. Underflow is `- underflows` against `- would result negative`. Division by zero is `ZeroDivisionError` against `/ 0`. Since `OverflowError` and `ZeroDivisionError` are both subclasses of `ArithmeticError` in Python, **`pytest.raises(ArithmeticError)` is the form that stays true across both** --- matching on the message text is the form that breaks when you port a test to LocalNet.

Example: A negative test through simulate {#ex:negative-test-simulate}

<!-- finder: prove a rejection happens for the reason you intended -->

{{include-ex:negative-test-simulate}}

A negative test on a real network has a practical problem: to prove that a stranger is rejected you need a stranger, and a stranger is an account you hold no key for. `skip_signatures=True` solves it. algokit-utils rebuilds the group against a null signer and asks the node to evaluate it without checking signatures, so any address at all can stand in for an attacker. It is not a funding shortcut --- a simulate moves no value, so there was never a balance to top up.

Now the single most important mechanical fact in this chapter, and the one most likely to be wrong in code you find elsewhere. **A failing simulate raises.** `composer.simulate()` does not hand you back a response object with a failure inside it; it inspects the response, finds the group failed, and raises `LogicError`. Every field you want is on the exception: `.message`, `.pc`, `.traces`, `.transaction_id`. Code that reads `result.simulate_response[...]["failure-message"]` after a failing simulate never runs, because there is no `result`.

And note what {{ex:negative-test-simulate}} asserts. Not that an exception was raised, but that `"not the beneficiary" in rejected.message`. The `in` is deliberate: `LogicError.message` is your string wrapped in the contract name, application ID and transaction ID, so an equality comparison against the bare string never holds. **One negative test per security assertion, each pinned to its own message,** is the practice that separates a suite which proves your authorization works from one which proves that *something* went wrong. A test that catches any exception passes when your contract rejects the stranger for the wrong reason, and passes when it rejects everybody, and passes when it is broken.

### Every Example in This Book Ships With Its Test
This is the convention, stated once. Every numbered example in this book is a complete program in `examples/`, registered with an execution mode that CI enforces. Five modes: `compile` means it is compiled by PuyaPy on every commit; `compile-fail` means compilation is *expected* to fail and the error text is checked against a recorded substring; `unit` means it is compiled *and* a test file beside it is run under pytest; `script` means it is client-side code that is byte-compiled, because running it would need a funded LocalNet; `localnet` means it is run end to end. A `unit` example is two files and one printed artifact --- the contract is what appears on the page, and its test file sits next to it on disk under the same name with `_test` appended.

*What this section repairs in the vesting contract:* defects one and two, by being the thing that finds them. The suite that catches them is the same seven tests with three assertions rewritten from *what the contract does* to *what the contract is for*.

## The Mini-Build, Fixed
Three defects, three repairs, eleven changed lines. The complete corrected contract is on disk at `examples/ch07_proving_it_works/simple_vesting_fixed.py` and compiles in CI; here is the spine of the diff, with everything unchanged elided.

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

Six things are elided there, and none of them moves. Both classes keep their names; `__init__` is identical in both files; `opt_in_to_asset` and `initialize` are untouched; inside `vested`, the cliff and end branches and the `elapsed` and `duration` bindings that the diff's arithmetic reads are unchanged; `claim`'s inner asset transfer and its `self.claimed.value += claimable` are unchanged; and `claimable()`, still carrying `@arc4.abimethod(readonly=True)`, is unchanged in full. The only other difference between the two files is the class docstring, which described three defects and now describes three corrections.

Change the one import at the top of the scratch file from `simple_vesting_broken` to `simple_vesting_fixed` --- nothing else --- and run it again:

```console
$ uv run --group test python -m pytest /tmp/req/requirement_tests_test.py -q
...                                                         [100%]
3 passed in 0.13s
```

**Correction one: refuse instead of returning zero.** The early return becomes an assertion. A claim that would move nothing now fails, loudly, with a message that tells the beneficiary the truth --- that nothing has vested since their last claim. The transaction does not confirm, the wallet does not show a green tick, and no fee is wasted pretending.

**Correction two: multiply through 128 bits.** `op.mulw` returns the product as a high/low pair and `op.divw` divides that pair by a 64-bit divisor, so the intermediate never has to fit in sixty-four bits --- only the quotient does, and the quotient is bounded by `total`. This is {{ex:mulw-split}} and {{ex:divw-join}} applied to the one place in this contract where a product can exceed the word size. `divw` itself aborts when the quotient would not fit in sixty-four bits, and the reason it never can here is worth writing down rather than leaving as an absent guard: this branch runs only while `elapsed < duration`, so the quotient is strictly below `total`, which is a `UInt64` already. The floor is in the right direction: `divw` truncates, which means the beneficiary is credited with slightly less than the exact real-valued share and the remainder stays in the contract until the schedule ends, at which point `vested` returns `total` exactly and the dust is paid out.

**Correction three: say why.** One string on one assertion, and the resulting message is what the earlier probe showed as an empty string. The choice of plain `assert` over `logged_assert` here is deliberate: this contract has one beneficiary and one client, both of which hold the app spec.

Two things generalize past this contract.

The first is about tests. **Write the assertion from the requirement, then run it against the code --- not the other way around.** Every one of the three defects was findable by a test that stated what the contract was *for*, and invisible to a test that stated what it *did*. The mechanical version of this rule is the one to remember: if you cannot describe a change to the contract that would turn a given test red, that test is not testing anything.

The second is about failure. **A contract's failures are part of its interface.** The program counter is the AVM's; the message is yours; the source line is available only if you keep the artifact that maps between them. Decide, at the time you write each rejection, who will read it --- a beneficiary, an integrating team, your own on-call rotation at three in the morning --- and write the rejection for them.

## What Bites People Here
Six, in roughly the order you meet them: two about what an error message is and where it lives, two about simulate, one about a convention that looks like a guarantee, and one about a compiler error you will hit the first time you try to fail unconditionally.

::: {.gotcha #assert-message-not-onchain topic="Compilation, tooling, and shipping" title="The string in an assert message is not in your program"}
`assert cond, "message"` puts the string in two places and neither is the chain: a TEAL comment, which is discarded at assembly, and an ARC-56 `sourceInfo` entry keyed by the program counter of the `assert` opcode. The compiled bytes do not contain it --- `b"owner only" in bytecode` is `False` --- and the AVM reports only `assert failed pc=85`. Everything legible after that is a client-side lookup against the app spec, which means a caller integrating from a different toolchain, a different language, or a block explorer gets a number and has to come and ask you what it means. Worse, a *bare* `assert` with no message produces no `sourceInfo` entry at all, so it is invisible to every tool that reads the spec, and it will sit in the bytecode immediately beside the existence assertions PuyaPy inserts on state reads, which do have messages. If the reason must survive without the app spec, `logged_assert()` writes it into the program as an ARC-65 log. Expect the approval program to grow by roughly forty per cent or more for a couple of checks, and be clear that you are buying legibility for callers who lack your artifacts, not for anything on-chain.
:::

::: {.gotcha #logs-vanish-on-real-failure topic="Testing and simulation" title="A failed transaction returns no logs; a failed simulation does"}
It is natural to assume that if a contract logs its reason before failing, the reason comes back with the rejection. It does not, on a submitted transaction: the node's response to a failed `POST /v2/transactions` is a message and nothing else, with no logs array, no matter what the program logged before it aborted. Logs from a failing group survive in exactly one place --- the simulate response, at `txn-groups[g].txn-results[i].txn-result.logs`, which the simulator saves specifically because a debugging tool needs them. They are not on the execution trace either; a trace unit carries a program counter, stack and scratch changes, and spawned inner transactions, and has no log field. So ARC-65's promise that the failure reason is recoverable from the API response is true of simulate and false of a real submission. Plan your error reporting accordingly: for a client that can afford to re-run a failure through simulate, logs are recoverable; for one reacting to a rejection in the wild, the program counter is all there is.
:::

::: {.gotcha #simulate-raises-on-failure topic="Testing and simulation" title="A failing simulate raises rather than returning a failure"}
`composer.simulate()` and the group-level `.simulate()` in algokit-utils inspect the response before handing it back, and if the group failed they raise `LogicError` instead of returning. This catches out almost everyone writing a negative test for the first time, because the natural shape --- call simulate, then read `failure-message` off the result --- has no result to read. Everything you wanted is on the exception: `.message`, `.pc`, `.transaction_id`, and `.traces`, which carries the execution trace if you enabled it. Wrap the call in `try`/`except LogicError` and assert against `.message` specifically rather than merely that something was raised --- and assert with `in`, because `.message` wraps your string in the contract name, application ID and transaction ID. Two related facts are worth carrying. algokit-utils turns on `allow_more_logs`, `allow_unnamed_resources`, `allow_empty_signatures` and a full trace config on every simulate it makes, and always substitutes an empty signer, so a simulate that succeeds is not evidence that the same group would have been accepted with real signatures and declared resources. And `simulate` is the only endpoint for this job now: `dryrun` has been removed from go-algorand outright, not deprecated, so any older material or example code that reaches for it is dated by several protocol versions.
:::

::: {.gotcha #unnamed-resources-are-discovery topic="Resource references, MBR, and budget" title="Unnamed resources are a discovery tool, not a permission"}
Setting `allow_unnamed_resources=True` on a simulate lets the program reach accounts, assets, applications and boxes that the transaction never declared, and reports every one of them back under `unnamed-resources-accessed`. It is tempting to read a passing simulate as evidence the call works. It is not: the submitted transaction is still subject to the ordinary resource rules and will fail on the first undeclared reference. The flag exists so that tooling can *find out* what to declare --- algokit-utils uses exactly this response to populate the reference arrays for you --- and the correct use is to run the simulate, read the resources back, and put them in the real call. A related trap sits next to it: the resource arrays have a per-transaction cap, and a method that touches more than fits cannot be fixed by declaring harder. It has to be split across a group, which is a design change and better discovered here than in production.
:::

::: {.gotcha #readonly-is-client-side topic="Compilation, tooling, and shipping" title="A readonly call is simulated with skipped signatures and a huge budget"}
{{ch:contracts}} established that `readonly=True` is a promise to callers rather than anything the compiler or the AVM enforces, and that a readonly method which writes state has its writes silently discarded. The half that bites later is *how* the client keeps the promise. algokit-utils answers a readonly call with a simulate, and that simulate runs with signatures skipped and the maximum extra opcode budget granted --- which is why a readonly call is free and instant, and also why it is a much more permissive environment than a real submission. A readonly method that consumes 2,000 opcodes answers correctly in your client every time and fails the first time anybody submits it, as does one that needed a signature the simulation waived. The rule is to submit every readonly method at least once, on LocalNet, before you trust the numbers it gives you.
:::

::: {.gotcha #logged-err-return-deadlock topic="Compilation, tooling, and shipping" title="An unconditional failure in a value-returning method deadlocks the type checker"}
`logged_err()` and `logged_assert()` are typed `-> None` in the algopy stubs, because from Python's point of view they are ordinary calls. PuyaPy knows better and treats them as terminal. The two views collide in a method that returns a value: put `logged_err(...)` as the last statement and mypy reports `Missing return statement`, add a `return` after it to satisfy mypy and PuyaPy reports unreachable code. Neither tool is wrong and there is no flag that resolves it. The shape that compiles is to make the failure a branch rather than a terminator --- bind a local, use `if`/`elif`/`else` with the failure in the `else`, and return the local once at the end. Void methods have no such problem. While you are writing them, expect PuyaPy to warn if your error code is not alphanumeric or not camelCase, to warn once the whole `ERR:code:message` string passes 64 bytes, and avoid the `AER` prefix, which is reserved for specific ARC errors.
:::

## Retrieval
Answer these from memory before moving on. Four of them reach back into earlier chapters on purpose.

1. `assert cond, "too high"` fails on-chain. Name the two artifacts the string "too high" ended up in, and say which one the caller had to be holding for the message to appear in their error.
2. What appears in an ARC-56 `sourceInfo` table for a *bare* `assert` with no message, and what does a client show the caller when it fires?
3. Name three things the ARC-4 router has already validated before your method body runs, and one thing it has not that people frequently assume it has.
4. Give the two separate reasons there is no reentrancy on Algorand, and say which of the two still applies when the inner transaction is an application call.
5. A method reports 2,400 opcodes consumed under `extra_opcode_budget=20_000`. How many application calls does the real group need, and where does the extra budget exist?
6. Your simulate of a failing group returns no object at all. What happened, and where are `pc` and the failure message?
7. *(From {{ch:numbers-and-time}})* `total * elapsed // duration` overflows and `mulw`/`divw` does not, for the same inputs. Say precisely which value exceeds sixty-four bits in the first form and why it never has to in the second.
8. *(From {{ch:moving-value}})* {{ex:inner-fee-zero}} set every inner transaction's fee to zero and asserted that the caller's `Txn.fee` covered the whole pool. Say how you would find out, before deploying, how many transactions that pool actually has to cover for a given method.
9. *(From {{ch:contracts}})* A method marked `readonly=True` increments a counter. Say what happens to the counter when a client calls it, why nothing reports an error, and what this chapter adds about the environment that call ran in.
10. *(From {{ch:mental-model}})* You already knew a program counter identifies a byte in the compiled approval program. Name the file that maps it back to a line of Python, say which tool writes it, and say which tool does not read it.

## Exercises
1. **(Trace)** A contract's `claim` and `opt_in_to_asset` methods compile to an approval program in which four of the program counters carrying an `assert` opcode are 176 (`check self.admin exists`), 178 (`admin only`), 311 (`check self.beneficiary exists`), and 313 (no entry in `sourceInfo` at all). Three callers each make one call. The first is a stranger calling `claim`. The second is a non-admin calling `opt_in_to_asset`. The third is the beneficiary calling `claim` twice in the same block, after a successful first claim, on the broken contract.

   For each caller, say which program counter fails, what message the client displays if it holds the app spec, and what it displays if it does not. One of the three does not fail at all; say what it returns and why that is worse than failing.

   Then the harder half. Two of those four program counters --- 176 and 311 --- are PuyaPy's own bookkeeping rather than anything the author wrote, and in *this* contract neither of them can ever fire. Say why not, in one sentence about `__init__`. Then describe a contract in which one of them *would* fire, and say what the caller of that contract would see.

2. **(Parsons + Analyze)** Below are seven statements. Five form the body of a negative test that proves an unauthorized caller is rejected *for the right reason*; two do not belong. The contract is deployed at `app_id`, its spec is at `spec_path`, and `claim` is beneficiary-only.

   ```python
   def test_a_stranger_cannot_claim() -> None:
       algorand = AlgorandClient.from_environment()
       ...
   ```

   The statements: (a) `client = AppClient(AppClientParams(app_spec=Path(spec_path).read_text(), algorand=algorand, app_id=app_id, default_sender=algorand.account.random().address))`; (b) `group = algorand.new_group().add_app_call_method_call(client.params.call(AppClientMethodCallParams(method="claim", args=[])))`; (c) `with pytest.raises(LogicError) as rejected:`; (d) `group.simulate(skip_signatures=True)`; (e) `assert "not the beneficiary" in rejected.value.message`; (f) `result = group.simulate()` followed by `assert result.simulate_response["txn-groups"][0]["failure-message"]`; (g) `assert rejected.value is not None`.

   Select the five and order them. Then, for each reject, say what is wrong with it: one of them describes an API that cannot work the way it is written, and the other passes in situations the test was written to rule out --- name two such situations concretely.

   Finally: statement (e) uses `in` rather than `==`. Say what `LogicError.message` actually contains that makes the equality version fail, and say what you would lose if you weakened the assertion to `pytest.raises(LogicError)` alone.

3. **(Debug)** A team's contract has run in production for six weeks. This morning every call to `settle` fails. Their on-call engineer has one error string from a user's wallet and nothing else:

   ```console
   transaction 5KQD...7WPX: logic eval error:
   assert failed pc=1174. Details: app=7311, pc=1174
   ```

   They have the deployed app spec. They look up 1174 in `sourceInfo` and it is not there. They can reproduce the failure with a simulate and get the same program counter.

   Before working anything else out, write down the two distinct explanations for a program counter that is missing from `sourceInfo`, and say which artifact would tell them apart.

   Then answer three things. First: name the file that would resolve 1174 to a line of Python, say when it was written, and say why the team probably does not have it. Second: assume they still have the exact source commit that was deployed. Give the procedure that recovers the line anyway, and name the one thing that must be true for it to be valid. Third: `settle` worked for six weeks and now fails for everyone, with no deployment and no code change. Give two mechanisms that produce that pattern --- one arithmetic and one about resources --- and say which one the program counter's *absence* from `sourceInfo` makes more likely.

4. **(Compare)** You are choosing how a contract reports its refusals, and there are four options: a bare `assert`, an `assert` with a message, `logged_assert()`, and `op.err()`. Compare them on five axes --- bytecode cost, what appears in the app spec, what a caller holding the spec sees, what a caller *without* the spec sees, and what is recoverable after a real submitted transaction fails.

   Two of the four are dominated: they are worse than another option on at least one axis and better on none. Name them and name what dominates them.

   Of the two that survive, say which you would choose for a single-tenant application whose only client you also write, and which for a public contract that other teams will call from TypeScript without ever contacting you. Then give a concrete scenario in which you would pay `logged_assert()`'s bytecode on the single-tenant application anyway.

5. **(Extend)** Extend the fixed vesting contract with an admin method `revoke()` that ends the schedule immediately: everything vested up to the moment of the call stays claimable by the beneficiary, and everything not yet vested returns to the admin. Then write the test suite for it *first*, from the requirement, before you write the method.

   Do not start from the code, because there is no code yet --- that is the point of the ordering. Read the requirement in the paragraph above and derive the cases from it. Aim for at least five, and expect at least one of them to be about a second call to `revoke`.

   Write the tests, watch them fail against a contract with no `revoke` at all, then write the method. When they pass, add one more: at production supply, using {{ex:mulw-split}}'s arithmetic. Then write down which of your tests would still have passed if `revoke` had forgotten to stop the schedule, and fix that test rather than the contract.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can say where an assert message is stored, prove it is not in the bytecode, explain what a caller without the app spec sees, and choose between `assert`, `logged_assert()` and `op.err()` for a given contract.
- [ ] I can name what the ARC-4 router validates before my method runs, stop writing assertions that restate it, and give the two separate reasons there is no reentrancy on Algorand.
- [ ] I can run a method through simulate against live state, read its opcode cost with extra budget, discover the resources it touched, and say why none of that is permission to submit.
- [ ] I can turn a program counter into a line of Python using the `.puya.map` file, and say what it means when a program counter does not resolve.
- [ ] I can write a test that would go red if the contract were wrong, say why a test written from the code cannot, and pin a negative test to the specific message its assertion produces.

## Handoff: What the Vesting Project's Tests Need
{{ch:token-vesting}} builds the production version of this chapter's Mini-Build: multiple beneficiaries, schedules in box storage, a real deposit, and a payout that actually leaves the contract. Its test suite is where every technique in this chapter is used at once. {{tbl:proving-it-works-handoff}} lists the examples the project leans on and what each one is needed for, with something to predict before you get there.

Table: Examples from this chapter that the vesting project depends on {#tbl:proving-it-works-handoff}

| From this chapter | What the project needs it for | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| {{ex:assert-message-home}} | Giving every rejection on the claim path a message a beneficiary can act on | The project has more than a dozen assertions and no bare ones. Pick the authorization check on the claim path and write the message you would put on it, then compare. |
| {{ex:validate-at-boundary}} | `deposit_tokens`, which takes a typed transfer parameter | The project asserts the transfer's asset, amount and receiver, and never asserts that it is an asset transfer or that it sits directly before the app call. Say which of those the router already guaranteed, and why the group size is still checked by hand. |
| {{ex:requirement-vs-code}} | Deciding, for each of the project's methods, what the requirement says rather than what the draft does | Vesting has one requirement that is easy to state and easy to implement wrongly. Write it as one sentence, then write the assertion that would fail if the contract broke it. |
| {{ex:unit-test-context}} | The fast half of the suite, over the schedule arithmetic | Vesting is entirely a function of the clock. Say which of the project's methods can be tested with `patch_global_fields` alone, and which cannot and why. |
| {{ex:negative-test-simulate}} | One test per security assertion, each pinned to its message | The project's admin-only methods each need a stranger test. Write down what such a test must assert beyond "an exception was raised". |
| {{ex:simulate-extra-budget}} | Sizing the group for a multi-beneficiary payout | A payout loop's cost scales with beneficiaries. Say how you would find the point at which the group needs a second app call, without deploying twice. |
| {{ex:pc-to-source-line}} | The debugging procedure when a claim fails on LocalNet | The project's build writes a `.puya.map` beside its bytecode. Say what you would do with a `pc` from a failed claim, in order, and where the procedure stops working. |
