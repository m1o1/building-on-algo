<!-- GENERATED FILE. Do not edit.
     Every entry below is a ::: {.gotcha} callout in a numbered chapter
     or a hand-written appendix.
     Edit it there and run `python3 scripts/generate_appendices.py`.
     tests/test_book_integrity.py fails if this file has drifted. -->

\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Appendix C: Gotchas by Topic {-}

Every mistake the book stops to warn you about, in one place. Each entry appears in full where it can actually save you --- in the chapter, at the paragraph where you are about to make it --- and is repeated here because six months from now you will remember that the book warned you about something to do with box names and not which chapter it was in.

The pointer after each entry names the chapter or appendix it is drawn from; go there for the surrounding code.

## Compilation, tooling, and shipping {-}

### LocalNet reset invalidates every hard-coded app ID {-}

`algokit localnet reset` wipes application IDs along with everything else. Any script that hard-codes an app ID stops working the moment you reset, and the error is a confusing "application does not exist" rather than anything about the reset. Re-deploy after every reset, or better, never hard-code the ID: the interact script later in this chapter re-derives it on every run, which is why it survives resets that break its hard-coded cousins.

*From Chapter 1.*

### Compiling a contract is not the same command as building a project {-}

`algokit compile py` and `algokit project run build` are not interchangeable. `compile py` compiles one file and drops artifacts wherever you point it; `project run build` runs the pipeline defined in `.algokit.toml`, placing artifacts where the template's scripts expect them and generating the typed client. Use `compile py` here and your deploy step will fail to find the app spec at the path every script in this book assumes.

*From Chapter 1.*

### An assert with no message produces a program counter and nothing else {-}

Assertion messages do not exist on chain. The AVM aborts at a program counter; the compiler stores your message in the ARC-56 app spec under `sourceInfo.approval.sourceInfo[]`, keyed by that counter, and the client SDK maps the number back to the string. An `assert` written without a message contributes no entry at all, so there is nothing to map and your caller sees `assert failed pc=78`. This bites hardest on contracts other teams integrate against, because they may not have your source, and it bites in production, where you are reading a failed transaction hours after the fact. Give every assertion a message, and ship the app spec alongside the contract.

*From Chapter 2.*

### from_bytes relabels bytes as an ARC-4 value and verifies nothing; validate is the check it skipped {-}

`arc4.String.from_bytes(raw)` emits no opcodes and performs no validation, as the stub documentation says, so a length prefix that disagrees with the payload behind it sails through and fails somewhere else, later, in code that had nothing to do with the decision. PuyaPy does insert argument validation on ABI methods by default, which is why this mostly bites on values you assembled yourself from boxes, logs, or arguments to a method carrying `validate_encoding="unsafe_disabled"`. Where you have disabled it for opcode budget, `.validate()` is not optional; it is the same check, moved to a line you chose.

*From Chapter 3.*

### A byte[] return arrives at the client as a list of integers, and no decoder will guess otherwise {-}

Returning `Bytes` from an ABI method gives the method a `byte[]` return type, and a conforming client decodes `byte[]` into a list of integers, because that is what the type means. Text that you concatenated by hand comes back as `[118, 105, 115, ...]`, and the caller has no way to know it was ever meant to be read. This never raises: it is a wrong answer that succeeds. If the value has structure, say so in the return type (`arc4.String`, a tuple, a struct) and let the encoding carry the meaning instead of a comment in your codebase.

*From Chapter 3.*

### BoxRef is deprecated and its methods are on Box {-}

Older code and older tutorials reach for `BoxRef` for the byte-level box operations (`create`, `resize`, `splice`, `extract`, `replace`) and for `.ref` to get at them from a typed `Box`. As of `algorand-python` 3.5.0 both are deprecated: the stub carries `@deprecated("Methods in BoxRef are now directly available on Box")`, and `.ref` carries one of its own. The methods live on `Box` now.

The deprecation is silent at compile time, so the old form keeps working and keeps being copied.

*From Chapter 5.*

### The string in an assert message is not in your program {-}

`assert cond, "message"` puts the string in two places and neither is the chain: a TEAL comment, discarded at assembly, and an ARC-56 `sourceInfo` entry keyed by the program counter of the `assert` opcode. The compiled bytes do not contain it (`b"owner only" in bytecode` is `False`), and the AVM reports only `assert failed pc=82`; everything legible after that is a client-side lookup against the app spec, so a caller integrating from a different toolchain, a different language, or a block explorer gets a number and has to come and ask you what it means. A *bare* `assert` produces no `sourceInfo` entry at all --- invisible to every tool that reads the spec, sitting beside the messaged existence assertions PuyaPy inserts on state reads.

*From Chapter 8.*

### logged_assert buys spec-free legibility, priced in bytecode {-}

If a rejection's reason must survive without the app spec, `logged_assert()` writes it into the program as an ARC-65 log entry --- `ERR:<code>[:<message>]`, emitted before the failure. That is the one form a caller holding none of your artifacts can recover, from `txn-result.logs` in a simulate, and it is priced in program size: expect the approval program to grow by roughly forty per cent or more for a couple of checks. You are buying legibility for callers who lack your artifacts, not for anything on-chain --- a submitted transaction that fails still returns no logs. For an application whose only clients ship with your app spec, a plain `assert` with a message is the same information at no bytecode cost.

*From Chapter 8.*

### An unconditional failure in a value-returning method deadlocks the type checker {-}

`logged_err()` and `logged_assert()` are typed `-> None` in the algopy stubs; PuyaPy treats them as terminal. The two views collide in a value-returning method: make `logged_err(...)` the last statement and mypy reports `Missing return statement`; add a `return` to satisfy mypy and PuyaPy reports unreachable code. Neither tool is wrong and no flag resolves it. The shape that compiles is Example 8-4's: bind a local, put the failure in an `else` branch, return the local once at the end. Void methods have no such problem.

*From Chapter 8.*

### A readonly call is simulated with skipped signatures and a huge budget {-}

Chapter 3 established that `readonly=True` is a promise to callers, not something the AVM enforces. The half that bites later is *how* the client keeps the promise: algokit-utils answers a readonly call with a simulate, run with signatures skipped and the maximum extra opcode budget granted. That is why readonly calls are free and instant --- and why they run in a far more permissive environment than a real submission. A readonly method that consumes 2,000 opcodes answers correctly in your client every time and fails the first time anybody submits it. Submit every readonly method at least once, on LocalNet, before you trust its numbers.

*From Chapter 8.*

### byte[] application arguments need their ARC-4 length prefix {-}

A `byte[]` ABI argument must carry its two-byte ARC-4 length prefix; a raw 32-byte value is not one, and the router mis-reads or refuses it. Build calls through `AtomicTransactionComposer`, `algosdk.abi`, or a typed client from `algokit generate client` --- all of which write the prefix; hand-packed `app_args` do not. `place_order`'s 32-byte `lsig_hash` is where this bites here.

*From Chapter 21.*

### The error code reaches a failed send only on a node running the developer API {-}

On LocalNet a rejected submission does carry the code, inside the `opcodes=` disassembly algod appends to the error. That tail comes from `EnableDeveloperAPI`, which AlgoKit's LocalNet sets true and which defaults to **false** everywhere else. Against a default node the same failure reads `logic eval error: err opcode executed. Details: app=<app-id>, pc=<n>`, with no code in it anywhere.

Test your error handling against `simulate`, which returns the logs, rather than against a LocalNet send that happens to be more generous than production.

*From Chapter 24.*

### The ARC-56 spec carries no error-code mapping {-}

`logged_assert`'s output is described as ARC-56 compatible, which is true of the *format* and not of a lookup table. PuyaPy 5.10.1 --- the version this book pins --- emits no `errors` key in the generated spec, so a client cannot resolve a code to a message by reading the app spec.

The code is recoverable because it is in the log and in the error string, not because anything published a dictionary. If your client wants human text for a code, it has to carry that mapping itself.

*From Chapter 24.*

### An update replaces the whole program, not the method you meant to fix {-}

`UpdateApplication` swaps the approval and clear programs entirely, keeping the application id, the global and local state, and the balance. There is no partial update and no diff.

Two consequences people meet late. Anyone auditing your deployed bytecode audited a snapshot, and an update invalidates it silently. And the new program inherits the old program's state without ever having declared it, so a schema the new code does not expect is still there and still counted against the creator's minimum balance --- unless that same update also supplies a larger global schema or extra pages, which consensus v42 now accepts. Local schema still cannot grow.

*From Chapter 24.*

### A box outlives its application, and its minimum balance with it {-}

Deleting an application does not delete its boxes, and a box holds minimum balance against the application *account*, which survives. An account still holding boxes cannot be closed, so a contract that can be deleted while boxes remain has a path to stranding its own funds permanently.

Delete every box first, then close. A contract that permits deletion should check this rather than trusting whoever calls it to remember: Example 24-10's `close` refuses while any entry remains, which means it also has to keep a count of what remains.

*From Chapter 24.*

### puyapy does not target the newest AVM version by default {-}

`puyapy` does not default to the newest AVM version the network supports --- it defaults to a conservative one, currently 11. Code that uses a v13 opcode fails the compile with a hard error naming both versions (`Opcode 'sha512' requires a min AVM version of 13 but the target AVM version is 11`). The quieter hazard is shipping a program whose assembly differs from the one you measured, because a lower target silently omits v12/v13 codegen. Pass `--target-avm-version` explicitly on every build, and pin it in the project's own build step --- `smart_contracts/__main__.py` in an AlgoKit project --- so that no one has to remember the flag. This book's projects pin `--target-avm-version=13`.

*From Appendix B.*

## Authorization {-}

### The application address has no private key and can never be a sender {-}

`Global.current_application_address` is the account derived from the application ID. It holds the contract's Algo and assets, it is the sender of every inner transaction the contract emits, and *no private key exists for it*. It can therefore never be `Txn.sender` on a top-level call, so a guard of the form `assert Txn.sender == Global.current_application_address` is not merely wrong but unsatisfiable; if it guards `DeleteApplication`, the application is undeletable forever. `Global.creator_address` is the account that created the application, is fixed at creation, and is a real signer. Use the creator for authorization, and the application address for balances and inner transactions.

*From Chapter 2.*

### There is no private method: every abimethod is a public entry point {-}

Nothing about `@arc4.abimethod` makes a method internal, and nothing about naming it `_helper` or omitting it from your client hides it. The router dispatches on a selector computed from the method signature, and anybody who can read your app spec --- or hash a signature they guessed --- can call it. A method is protected only by the assertions inside it. Before you ship, list every `abimethod` and name the check that stops the wrong caller; if a method has no such check, either it is genuinely public or you have a hole.

*From Chapter 2.*

### create=allow removes the application-ID check, and at ID zero every caller is the creator {-}

The three values of `create` are not three flavours of the same check. `"require"` asserts the application ID is zero and `"disallow"` asserts it is non-zero; `"allow"` deletes the assertion, and the generated router matches such a method *above* the `txn ApplicationID` branch entirely. A caller can therefore send it against application ID zero, which creates a fresh application from your program, runs `__init__`, and executes the method against empty state. Any guard of the form `Txn.sender == Global.creator_address` passes there, because the sender is the one doing the creating. Use `"allow"` only for a method genuinely designed to run in both worlds, and if you cannot say in one sentence what it should do at ID zero, you want `"disallow"`.

*From Chapter 3.*

### A one-step ownership transfer has no undo and no confirmation {-}

`self.admin = new_admin`, guarded by the current admin, is the obvious implementation and it is a live hazard. The address is accepted without any evidence that a key exists for it: a truncated paste, a testnet address on mainnet, an exchange deposit address that does not sign, and the role is gone. There is no recovery path, because the only account that could fix it is the one that no longer exists. Split it in two --- the holder nominates, the nominee accepts by sending a transaction --- and the failure becomes a nomination that never completes. The same argument applies to any single-transaction transfer of a unique authority: an asset manager address, a stored oracle, a beneficiary.

*From Chapter 10.*

### A creation guard does not protect the method your deploy script calls next {-}

`@arc4.abimethod(create="require")` says a method may only run in the transaction that creates the application, and that is a real guarantee. It says nothing about the method your deploy script calls on the next line. A contract that sets its admin, its price, its oracle or its beneficiary in a separate `initialize` has a public takeover method unless that method refuses to run twice, and the refusal has to be its own stored flag: there is no ledger field for "has this been configured". The usual defence, that only the deployer knows the app id in the seconds after creation, is not a defence: the id is in the block. Either fold the configuration into creation, where `create="require"` genuinely covers it, or carry a boolean and assert on it.

*From Chapter 10.*

### A role set in global state has a hard ceiling you will hit without warning {-}

A `GlobalMap` keyed by account spends one of the application's 64 global key/value pairs per member, and that budget is shared with everything else the contract stores and is fixed at creation unless the contract later approves an `UpdateApplication` that rewrites the global schema --- which none of the contracts in this book before Chapter 24 do. A moderator list built this way works, and then one day `grant` starts failing for a reason that has nothing to do with permissions, and no refused-update contract can widen the schema. Decide at design time whether the set is bounded by its nature (operators, signers, a committee) or by nothing (users, holders, applicants). The first belongs in global state. The second belongs in boxes, where each entry carries its own minimum-balance charge and somebody has to fund it, which is the cost that makes it unbounded in the first place.

*From Chapter 10.*

### Txn.sender is an application address whenever an application called you {-}

On an inner application call, `Txn.sender` is the calling application's own address, and every `assert Txn.sender == X` you have written continues to pass or fail on exactly the comparison you wrote. Nothing errors, and the field is not wrong: that application genuinely sent the transaction. `Global.caller_application_id` is the field that separates the cases, and it is zero exactly when a person called you directly. Add `assert Global.caller_application_id == 0` to any path where being reached through another contract would be surprising --- configuration, withdrawal, role changes --- and leave it off the paths where composition is the point, which by Chapter 16 will be most of them. Be explicit either way: a contract that never considered the question is not refusing inner calls, it is accepting them by default.

*From Chapter 10.*

### Assert that the funding transaction's sender is the account being credited {-}

A method that reads a payment out of the group and credits `Txn.sender` names two accounts, and they are two different accounts unless you say they are the same one. Left unasserted, anyone can build a group that pairs *somebody else's* pending payment with their own app call and take the position it paid for: the payment is valid, the app call is valid, and the contract credits the wrong party. Whenever a grouped transfer funds something booked to `Txn.sender`, assert `payment_txn.sender == Txn.sender`. If you want third-party sponsorship, model the beneficiary as an explicit method argument rather than leaving it implied.

*From Chapter 10.*

### rekey_to and close_remainder_to are a LogicSig's job, not a stateful contract's {-}

The checks a LogicSig must make --- `rekey_to` and `close_remainder_to` against the zero address, because a LogicSig signs on an account's behalf --- protect nothing when copied into a stateful contract's validation of an incoming grouped payment. The contract is not signing that payment; the caller is. The fields belong to the caller's own account, and the only effect of asserting on them is to refuse honest users whose wallet did something ordinary, like batching a rekey or a close-out into the same group. Check what the transaction proves about the money --- sender, receiver, amount, asset, and the group it sits in --- and leave the caller's wallet alone.

*From Chapter 10.*

### An inner transaction's rekey_to is yours to not set, not yours to assert {-}

An inner transaction's fields start at zero --- the AVM populates a sender, a fee, and a validity window, and nothing else --- so a contract that never sets `rekey_to` cannot get it wrong. It *can* set it, and `rekey_to` on an inner transaction hands your application account to whoever holds that key; no assert can undo a value you supplied. The defence is not a check but the absence of the line.

*From Chapter 10.*

## Resource references, MBR, and budget {-}

### An ABI return value is a log entry, and the log budget is smaller than the argument budget {-}

The AVM has no return channel. `return` from an `abimethod` compiles to a `log` of the four-byte prefix `0x151f7c75` followed by the ARC-4 encoding of the value. An application call may log **1,024 bytes** in total across at most 32 `log` calls, while it may carry **2,048 bytes** of arguments, so a method that echoes or expands its input can be made to fail by a caller who does nothing more unusual than sending a large argument. Bound anything variable-length that you return, and bound it well below the ceiling so the number means something to the caller.

*From Chapter 2.*

### ARC-4 bools share a byte only while they are adjacent, so field order changes the size {-}

Eight `arc4.Bool` values in a row occupy one byte. Put any non-bool field between two of them and each is rounded up to a byte of its own: `(bool,bool,uint64)` encodes in nine bytes and `(bool,uint64,bool)` in ten, for the same three values. In a tuple that is one byte. In a struct with sixteen flags interleaved with other fields it is fourteen wasted bytes on every read and every write, and in box storage those bytes are priced at 400 microAlgos each, forever. Group your bools.

*From Chapter 3.*

### Opting a user in raises the user's minimum balance, not the application's {-}

An application opt-in costs the *opting account* 100,000 microAlgos plus 28,500 per declared local uint and 50,000 per declared local byte slot. Declaring a generous local schema you never fill is therefore a tax you levy on every one of your users, forever, and the failure mode when they cannot pay it is a balance error that never mentions your application.

*From Chapter 4.*

### Deleting or shrinking a box refunds its minimum balance {-}

Box minimum balance is locked, not spent. Deleting a box refunds the entire charge --- the 2,500-microAlgo base and 400 per byte of name and contents --- to the application account, and shrinking one refunds the 400 per byte removed. It is the only mechanism in the box model that makes the account's floor go *down*, which is why a method that deletes a box moves real money even though no payment appears anywhere in it: an unguarded `clear` or `retire` is a withdrawal lever. Put a sender check on anything that deletes or shrinks a box, and treat the refund as part of the contract's economics rather than a rounding detail.

*From Chapter 5.*

### Writing a box can make a contract that worked yesterday stop working today {-}

Creating or growing a box raises the *application account's* minimum balance by 400 microAlgos per byte, plus 2,500 per new box, and none of it shows in the source, a compiler warning, or a test. The contract keeps working until the balance meets a floor that has been rising underneath it; then every call that writes a box fails, with an error about an account rather than a box: `account <address> balance <n> below min <m> (<k> assets)`. It is not a `LogicError`: the check runs after your program has already returned success. Storage that grows with usage needs a funding plan that grows with it, or a pre-flight check like Example 5-5 that refuses in a sentence a caller can act on.

*From Chapter 5.*

### algokit-utils pads box references, so budget failures wait for a different caller {-}

`populate_app_call_resources` does more than discover which boxes a call needs: it reads back how much extra I/O budget the simulation wanted and pads the transaction with empty box references, up to the eight-reference cap --- 16,384 bytes where the naive arithmetic says 2,048. A budget failure that padding can cover therefore never appears under the default client. It comes back, unchanged, the first time the same call is assembled by something that does not pad: another contract, a hand-built transaction, a different SDK. When a box-heavy method works in your scripts, rerun the arithmetic on one unpadded reference before concluding that it works.

*From Chapter 5.*

### A box is charged at its full size, however few bytes you touch {-}

Each box reference grants 2,048 bytes of I/O budget, and that allowance is checked as **two separate budgets that are never added together**. The *read* budget is charged before your program runs, as the sum of the full current sizes of every referenced box that exists, even one you never intended to read. The *write* budget is charged as the full size of each box written, once per box, with `box_resize` charging the full **new** size. Neither charges the bytes you touched: `extract`, `replace`, and `.length` all cost the same as `.value`. Both budgets pool across the whole transaction group, and references need not be distinct: duplicate and empty references each grant another 2,048 bytes, which is the fix.

*From Chapter 5.*

### A loop bounded by a runtime value has a ceiling you did not choose {-}

`while index < count` over box entries compiles cleanly, because `count` is a runtime value and the compiler has no opinion about it. What stops it is the box-reference cap or the 700-unit opcode budget --- in practice the cap first, since eight legacy references (sixteen on the v41 `Access` list) is a far lower ceiling --- and either arrives as a failed transaction in production, not a build-time error. Marking the method `readonly=True` buys a delay and not a reprieve: the tooling simulates it with a 320,000-unit opcode budget, so the loop that dies on chain at entry 30 may run to entry 8,000 in your tests and then die anyway. Bound the loop by a constant the contract chose and let the caller page.

*From Chapter 5.*

### Unnamed resources are a discovery tool, not a permission {-}

A passing simulate with `allow_unnamed_resources=True` is not evidence the call works: the submitted transaction is still subject to the ordinary resource rules and fails on the first undeclared reference. The flag exists so tooling can *find out* what to declare --- run the simulate, read `unnamed-resources-accessed`, and put the results on the real call, which is what algokit-utils does for you. A related trap sits next to it: the resource arrays have a per-transaction cap, and a method that touches more than fits cannot be fixed by declaring harder. It has to be split across a group, which is a design change and better discovered here than in production.

*From Chapter 8.*

### A min-fee times a group size is not the group's fee {-}

1,000 microAlgo is the minimum *today*. Multiplying it --- or even `suggested_params()`'s `minFee` --- by a group size underpays as soon as a transaction uses more than one min-fee: Falcon authorization costs three, and bytes past the free allowances (Appendix B) add a per-byte surcharge. Identify the signer's account type, then ask `simulate` for `group-usage` and scale it (Example 8-11); an empty Ed25519 envelope underprices a Falcon signature ([Heat](https://algorand.co/blog/enhancing-on-chain-flavor-in-algorand-5.0-part-4-heat)). Inside a contract, `Global.min_txn_fee * UInt64(N)` is a floor check that cannot go stale. It is not the client's fee.

*From Chapter 11.*

### Spending the application account toward its floor makes every other inner transaction fail {-}

Chapter 7 established where an inner fee comes from. The part that lands here is *which* balance it spends: the application account's spendable Algo, the same slab the splitter emptied. Drain it toward the minimum and the next inner payment fails as `balance below min`, not as a shortfall you can read off a return value. The symptom is a contract that stops working entirely. The floor assertion on `Txn.fee` does not prevent that drain; only `fee=UInt64(0)` on the inners does.

*From Chapter 11.*

### Opcode budget pools across application calls and is discarded, not banked {-}

An application call gets 700 opcodes and the application calls in a group pool them, so three calls share 2,100 regardless of which does the work. Two consequences catch people. Unused budget is discarded rather than banked, so there is nothing to conserve and no reason to write a cheaper method that is harder to read. And because the pool is shared, a method that fits comfortably alone can fail when a caller groups it beside something expensive: the failure is in your method, the cause is in theirs, and the message names an opcode rather than a group. `ensure_budget` and client-side padding are the two ways to buy more; they differ only in who pays, which makes that the question to answer first.

*From Chapter 11.*

### Integer division loses value on every call and the remainder has to live somewhere {-}

There is no fractional arithmetic on the AVM, so any split, share, rate or fee calculation loses a remainder to floor division --- small, silent, and absent from any test built on round numbers. Decide where the remainder goes and write it down: added to one recipient's share, carried in a named accumulator, or left in the contract's balance. The one option that is not available is ignoring it, because the remainder does not evaporate: it stays in the application account and quietly stops being distinguishable from the account's minimum balance or from an operator's float. Prefer floor division over any rounding that could favour the caller: dust that accumulates toward the contract is a bookkeeping task, and dust that accumulates toward callers is a slow withdrawal.

*From Chapter 11.*

### A method that makes inner transactions carries a fee its own source never states {-}

`fee=0` on an inner transaction means the caller pays for it, so a method making two inner transactions needs three minimum fees on the outer call and there is nothing in the contract that says three. Send one and the failure is `group fee 0.0A too small (needs 1mA more)` at whichever `itxn_submit` ran out --- not necessarily the first, because credit is checked as each inner submits. A first inner that succeeds and a second that fails is underpaid, not broken. Count inners to size the contract's floor; the client attaches `simulate`'s `group-usage` (Example 8-11).

*From Chapter 18.*

### Opcode budget and fees pool over different transactions {-}

Opcode budget and fees pool over different sets of transactions. Fees pool across the **whole group**: one transaction may overpay and cover a sibling of any type. Opcode budget pools only across the **application-call transactions** in the group --- adding a payment transaction to raise your compute ceiling does nothing at all. Two mechanisms, two scopes, and a group padded with the wrong transaction type fails with an opcode-budget error that looks like a fee problem.

*From Appendix B.*

### An undeclared resource fails the program, it does not read as empty {-}

An unavailable resource does not read as empty --- the program fails outright, with `unavailable Account` or `invalid Box reference`. This is why a method that works when called by the account that owns the box fails when called by anyone else: the sender is always implicitly available, and every *other* account has to be declared. algokit-utils 4.x populates most references automatically from the ABI method signature, which is a convenience and not a guarantee; anything the signature does not name, you declare yourself.

*From Appendix B.*

## Testing and simulation {-}

### A method marked readonly is answered by simulation, so anything it writes is silently discarded {-}

`readonly=True` is a permission granted to callers, not a restriction imposed on you: the compiler does not stop a readonly method from writing state, and if you submit one as a real transaction its writes commit normally. Instead, every conforming client reads the flag out of the app spec and answers the call with `simulate`, with no fee, no round and no ledger change, then reports the returned value as though it had happened. A readonly method that mutates therefore produces correct-looking answers forever while changing nothing, and the discrepancy only appears when somebody reads the chain directly. The rule is mechanical: if the method body can reach an assignment to state or an inner transaction, it is not readonly.

*From Chapter 3.*

### A failed transaction returns no logs; a failed simulation does {-}

A contract that logs its reason before failing does not get that reason back with the rejection. On a submitted transaction, the node's response to a failed `POST /v2/transactions` is a message and nothing else, with no logs array, no matter what the program logged before it aborted. Logs from a failing group survive in exactly one place: the simulate response, at `txn-groups[g].txn-results[i].txn-result.logs`, which the simulator saves specifically because a debugging tool needs them. ARC-65's promise that the failure reason is recoverable from the API response is therefore true of simulate and false of a real submission. For a client that can re-run a failure through simulate, logs are recoverable; for one reacting to a rejection in the wild, the program counter is all there is.

*From Chapter 8.*

### A failing simulate raises rather than returning a failure {-}

`composer.simulate()` and the group-level `.simulate()` in algokit-utils inspect the response before handing it back, and if the group failed they raise `LogicError` instead of returning. The natural shape for a negative test --- call simulate, then read `failure-message` off the result --- has no result to read. Everything you wanted is on the exception: `.message`, `.pc`, and `.transaction_id`. Wrap the call in `try`/`except LogicError`, and assert against `.message` with `in` rather than `==`, because it wraps your string in the contract name, application ID and transaction ID.

*From Chapter 8.*

### dryrun and tealdbg are gone; simulate is the endpoint {-}

`simulate` (`/v2/transactions/simulate`) is the endpoint for this job. go-algorand 5.0.0 removed the `dryrun` REST endpoint and the `tealdbg` tool. Older material that still calls dryrun fails on a 5.0.x node; LocalNet tracking this book's algod pin (5.0.1) has nothing to answer.

*From Chapter 8.*

### time.sleep() does not advance LocalNet's block timestamp {-}

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

*From Chapter 9.*

### Identical app calls in quick succession collide as duplicate transaction IDs {-}

Sending identical app calls in rapid succession on LocalNet can
produce identical transaction IDs, causing `transaction already in ledger`
errors. Add a unique `note` field to each transaction, such as
`note=os.urandom(8)` or `note=f"test-{i}".encode()`. In practice, add
`note=os.urandom(8)` to every `AppClientMethodCallParams` and
`PaymentParams`/`AssetTransferParams` in your test helpers; it costs nothing
and prevents intermittent test failures.

*From Chapter 9.*

### The LocalNet timestamp offset is one-way --- never set it to zero {-}

Setting the offset to `0` does not restore the wall clock. A zero offset means every new block's timestamp is the previous one plus zero: the ledger clock freezes, the REST API cannot un-set the offset, and restarting the container does not heal it, because developer mode never moves timestamps backward. Advance with positive offsets only, and when you need real time back, `algokit localnet reset` is the only way home.

*From Chapter 17.*

## Global and local state {-}

### Reading a state key that was never written fails the transaction; it does not return zero {-}

`self.fee.value` on a key that has never been written aborts the call, because PuyaPy compiles `.value` to a `*_get_ex` opcode plus an assertion that the key existed. Local state has a second, harsher absence: reading it for an account that never opted in, or that cleared, is a ledger error that no default argument can catch. Both bite hardest on `readonly` methods, where they turn into a denial-of-service surface: a non-member calls `credits_of(themselves)` and your dashboard shows an error instead of a zero. Use `.get(default=...)` when a missing key should read as a value, `.maybe()` when absence is information, and an explicit `is_opted_in` check before touching another account's local state at all.

*From Chapter 4.*

### Binding an ARC-4 struct to a variable aliases the stored bytes {-}

`entry = self.house.value` is a second name for the same encoded bytes, not a snapshot, and PuyaPy refuses to compile it rather than let you guess: *mutable reference to ARC-4-encoded value must be copied using .copy() when being assigned to another variable*. Add `.copy()` if you want a detached working copy; write through the attribute chain if you want to modify storage. Native `algopy.Struct` values do not have this restriction.

*From Chapter 4.*

### Returning False from the clear state program does not keep the account attached {-}

The clear state program's return value decides only whether its own logic is credited, not whether the account detaches. The local slab is deleted and the account's minimum balance released either way, and the same is true if the program errors or runs out of budget, which is the whole point of the guarantee: a user must never be able to be held to an application by a contract that refuses to let go. Anything you were planning to enforce on the way out belongs in `CloseOut`, which a contract *can* reject, and anything a user could lose by skipping `CloseOut` must not have been stored in their slab in the first place.

*From Chapter 4.*

### A counter maintained on CloseOut is wrong the first time somebody clears state {-}

Any global number that a close-out handler decrements (member counts, active-stake totals, open-position tallies) silently desynchronizes the first time an account uses ClearState instead of CloseOut, and there is no method you can add to repair it, because the contract was never told. If a number must be exact, derive it from something the contract controls, or rename it to something that only increases.

*From Chapter 4.*

### An account balance is not an accounting record {-}

`Global.current_application_address.balance` tells you what the account holds. It does not say what anyone is owed: it also counts the minimum balance, the funding that got the contract running, fee refunds, and anything a stranger chose to send. A contract that prices positions off its balance can have every position re-valued by an outsider making a payment, which in an empty pool means the first depositor sets the price to whatever they like: the first-depositor donation attack, met again in Chapter 13. Keep the ledger in state you write, check withdrawals against the ledger, and treat the balance as a liveness signal at most. When the two disagree, the difference is information --- fees you paid, donations you received, or a bug.

*From Chapter 7.*

### The local schema is fixed at creation; global schema grows only if you allow updates {-}

The number of *local* slots an application declares is written into the create transaction and is immutable for the life of the contract. Consensus v42 lets an update rewrite *global* slots and extra pages, but only if the contract approves `UpdateApplication` --- which every contract in this book before Chapter 24 refuses. For those contracts there is still no migration hatch: a contract that needs a sixty-fifth global key needs a new application and a state migration you write yourself. The MBR is charged for what you *declare*, not what you use, so a slot reserved against future need costs 28,500 or 50,000 microAlgos whether you ever write to it or not. That is the price of the option, and it is usually worth paying.

*From Chapter 9.*

### Declare schema for every field the deployed contract will ever need {-}

This pool refuses updates, so its state schema is fixed at creation (Chapter 4: local schema can never grow; global schema grows only if you allow updates) and a field added after deployment has nowhere to live. Budget slots for planned features at deployment time, even ones you have not written yet. The TWAP oracle later in this chapter adds three fields the listing above does not reserve, which is why adding it costs a fresh deployment rather than an in-place grow. On LocalNet the mistake costs nothing, because every run deploys fresh; on MainNet it costs a redeployment and a liquidity migration.

*From Chapter 14.*

## Box storage {-}

### Two BoxMaps with variable-length keys can name the same box {-}

A `BoxMap` box name is nothing but `key_prefix + encode(key)`, so a map with prefix `b"a"` and key `b"bc"` names the same box as a map with prefix `b"ab"` and key `b"c"`. The second write silently overwrites the first and no tool warns you, because concatenation cannot tell where you meant the seam to be. Fixed-width keys (`Account`, `UInt64`, a fixed-size struct, a `FixedArray`) are immune, since every name in the family is the same length. With `Bytes`, `String`, or dynamic array keys, give every map a prefix of the same length or include a separator that cannot occur in a key.

*From Chapter 5.*

### Box.splice never changes a box's size {-}

`splice(start, length, value)` looks like a list insertion and is not one: after removing and inserting, it forces the result back to the box's original size. Inserting eight bytes pushes eight bytes off the end; removing eight appends eight zero bytes. `resize` is the only operation that changes a box's size, and it is also the only one that changes the minimum balance, so if you want an insertion that grows the box, `resize` first and `splice` second.

*From Chapter 5.*

### Every method that touches a box needs its own box reference {-}

Every method that accesses box storage requires box references on the client side, not just `create_schedule`. The `claim`, `revoke`, `cleanup_schedule`, `get_vesting_info`, and `get_claimable` methods all read or write the beneficiary's box and must include the same `box_references` declaration. Forgetting this on read-only methods like `get_vesting_info` is a common mistake: the AVM enforces the I/O budget regardless of whether the access is a read or write.

*From Chapter 9.*

### Deleting an application does not delete its boxes, and the MBR is gone {-}

Delete an application while it still owns boxes and those boxes stay in the ledger with their MBR locked permanently: there is no application left to call `box_del`, and no protocol path that reclaims it. A contract that creates boxes therefore needs a *reachable* delete path --- either it refuses `DeleteApplication`, as a contract holding other people's assets should, or it asserts that no boxes remain before allowing deletion.

*From Chapter 9.*

### A counter that names the next box cannot also count the boxes that exist {-}

`entry_count` is read twice for two different purposes: as the index of the next box to create, and as the divisor that turns a beacon value into a winner. Those are a question about the past and a question about the present, and they part company the moment a box is deleted --- the next entry reuses an occupied index, silently overwrites a live entry, and the count stays permanently above the number of boxes. Compilation, unit tests and a happy-path run all pass, because the defect needs a create *after* a delete. A contract where entries and deletions interleave needs two counters, or box keys that never repeat.

*From Chapter 19.*

### A method that creates boxes fails unless the app account is funded first {-}

An application account must already hold a box's minimum balance when the method that creates the box runs. Fund the account first, or the creating call fails with `account <address> balance <n> below min <m> (<k> assets)` --- a ledger refusal no assert inside the contract can catch or rename. Here that means paying the app before `initialize`: for a three-choice election, three tally boxes at `2,500 + 400 × (10 + 8) = 9,700` microAlgos each is 29,100, on top of the 100,000 base.

*From Chapter 23.*

## Arithmetic and time {-}

### Dividing before multiplying silently returns zero {-}

`(a // b) * c` is integer division first, so it returns zero for every input where `a < b`, which for a proportion means every input except the last one. It is the transcription every spreadsheet formula invites and it produces a contract that pays nothing at all until the moment it pays everything. Write `(a * c) // b` instead. That moves the risk from rounding to overflow --- a trade you want, since overflow aborts loudly and rounding-to-zero does not --- and routing the product through `op.mulw` and `op.divw` removes both problems at once. No test that checks only the endpoints of a schedule will catch this, because the endpoints are the two points the wrong form gets right.

*From Chapter 6.*

### Guard a divisor where it is set, not where it is used {-}

A division-by-zero guard placed at the division site has to be repeated at every division site, and the day somebody adds a third one it will not be. Put it in the method that establishes the value --- `assert shares > UInt64(0)` in the setter, `assert end > start` in `configure` --- and it holds for every use forever. In practice the divisor is usually a *difference* (`end - start`, `total - claimed`), so one assertion about the ordering of two parameters retires both the `/ 0` and the `- would result negative` in a single line. PuyaPy warns about a literal `// UInt64(0)` and says nothing about a zero that arrives in a variable, which is every zero that has ever caused an incident.

*From Chapter 6.*

### Overflow and underflow end the transaction, they do not wrap {-}

On the AVM, `a + b` past 2^64-1 reports `+ overflowed`, `a - b` with `b > a` reports `- would result negative`, and `a // 0` reports `/ 0` (while `a % 0` reports `% 0`). None of them wrap, none of them return a sentinel, and none of them are catchable: the transaction is discarded, so there is no state left to inspect and no assertion of yours to fire. The consequence is denial of service, not theft: a contract holding funds can become permanently uncallable on an input path nobody tested, especially if the offending value was set by an init-once method. Test the boundaries, not the middle.

*From Chapter 6.*

### Bounding Txn.last_valid is safe, and the two time globals never describe the same block {-}

The safe use of `Txn.last_valid` runs in the opposite direction from reading it: `assert Txn.last_valid < SUNSET` puts a ceiling on a number the caller chose, and a caller who chooses badly only hurts themselves --- the pattern Example 6-13 uses to guarantee no transaction can commit after a sunset round, and the same pattern LogicSigs use to expire. When a deadline is a timestamp instead, remember that `Global.latest_timestamp` is the *previous* block's timestamp, one block behind `Global.round` always and by construction, so the two never describe the same block; a contract that stores one and compares against something derived from the other carries a small, constant, permanent error.

*From Chapter 6.*

### Txn.last_valid is a number the caller chose {-}

Reading `Txn.last_valid` as "now" hands the caller control of your clock: they may set it up to a thousand rounds beyond the current round, for free, on every call, and nothing about such a transaction looks unusual. Against a time-based release schedule that is roughly forty-six minutes of unearned progress per transaction, repeatable as fast as fees can be paid. It survives testing for the opposite of the obvious reason: AlgoKit Utils widens the validity window to the protocol maximum of a thousand rounds on LocalNet, so your tests already run the attack at full strength and pass anyway, because they assert that a call returned rather than that it returned the right number. Use `Global.round` for "now", always.

*From Chapter 6.*

### The op.Block window is anchored to the transaction, not to the current round {-}

The readable window is `1001 - (last_valid - first_valid)` rounds wide and ends at `Txn.first_valid - 1`, so a transaction using the full validity window can read exactly one block. `blk_timestamp(Global.round - 1)` succeeds only when `Global.round == Txn.first_valid` --- the transaction landing in its own first-valid round. Under algosdk and algokit-utils that never happens: they set `first_valid` to a round already committed, so inclusion is a round later at the earliest, and the call fails on the very first attempt, everywhere. A client that sets `first_valid` one round ahead instead gets a call that passes every test and fails whenever a transaction slips a round. Reach for `Txn.first_valid - 1`, a number the caller wrote down.

*From Chapter 6.*

### Block seeds are already public when the caller builds the transaction {-}

`op.Block` can only read rounds at or before `Txn.first_valid - 1`, and that round is committed and public before the transaction exists, so a caller can compute your contract's "random" answer off-chain, check whether they win, and submit only when they do, for free, as many times as they like. The common objection to `blk_seed` --- that a proposer might choose a favourable seed --- is false: the seed is a VRF output the proposer can compute but not select. The real problem needs no proposer at all, and no arrangement of the code fixes it. Use a commit-reveal shape against the ARC-21 randomness beacon: commit publicly to a future round, close entries, then read that round's value once it exists.

*From Chapter 6.*

### UInt64 overflow fails the transaction; it does not wrap {-}

The swap numerator is `delta_x * 997 * y`. With reserves in the billions of base units (entirely ordinary for a six-decimal stablecoin) that product passes $2^{64}$ long before anything looks large in human terms. The AVM does not wrap on overflow, it panics, so the failure mode is a swap that stops working once the pool gets deep enough, in production, having passed every test written against a small pool. Any multiplication whose operands are both user-scaled needs `op.mulw`, `op.divmodw`, or `BigUInt`. Test the arithmetic at the top of the range, not the middle.

*From Chapter 14.*

### op.btoi fails on a BigUInt wider than eight bytes {-}

The `op.btoi` call accepts a byte array of 0--8 bytes and interprets it as a big-endian unsigned integer. A `BigUInt` that exceeds $2^{64} - 1$ would produce more than 8 bytes, causing `btoi` to fail at runtime. The `assert twap < BigUInt(2**64)` guard ensures the TWAP result fits in 64-bit range before the conversion. With `TWAP_PRECISION = 10^9` and typical asset prices, this bound is safe for years of accumulation. If you use a higher precision scale factor or expect extreme price ratios, return a `BigUInt` instead of converting to `UInt64`.

*From Chapter 14.*

### Hashing a public seed with the caller does not make it unpredictable {-}

`sha512_256(seed || sender || salt)` looks like the repair, and it fixes something real: two accounts minting against the same block now get different answers, so one entrant's result no longer leaks another's. It does nothing about the attack that matters. The seed is public before the transaction exists, the sender and the salt are the caller's, so the whole expression is a function the caller can evaluate off chain --- and every extra input they control is one more dimension to search: fresh addresses, or salts at sixty-four tries on average for a one-in-sixty-four outcome. The only repair is to move the value's birth to after the deadline. Commit to a future round, close entries, then read that round's value once it exists.

*From Chapter 18.*

### A sixteen-round lead is really sixteen to twenty-three rounds {-}

`commit(lead=16)` rounded up to the next multiple of eight gives an effective lead of 16 to 23 rounds, never exactly 16, and which one you get depends on where the chain happened to be. Anything that quotes the lead to a user, times out on it, or computes a deadline from it has to carry the whole range: at two and three-quarter seconds a round that is between forty-four and sixty-three seconds, and a client that shows the low end will show a countdown that finishes before the draw does. Write the modulus and the minimum as named constants beside each other, so that whoever changes one is looking at the other.

*From Chapter 18.*

### Two settlement paths gated only on state can both be open at once {-}

A contract that pays out on success and refunds on failure needs the two to be mutually exclusive at every round, and a flag is only half of it. Gate the success path on a deadline it must beat and the failure path on the same deadline having passed, then gate the failure path on the success flag as well: the deadline separates them for a caller arriving late, and the flag separates them for a caller arriving after a success that already happened. Miss the flag and the contract pays twice; miss the deadline and a slow success path can run against an account that has already been refunded. Neither shows up in a happy-path test, because a happy-path test never asks for both.

*From Chapter 19.*

## Inner transactions {-}

### An application account's balance is not what it can spend {-}

An inner payment of `app.balance` fails for every account that will still exist afterwards --- not for large amounts, for every amount. The fee comes out of the same account first, so the instruction is short by one fee before the payment is attempted; fix that with `fee=UInt64(0)` and the ledger still refuses to let the account settle below its minimum balance. Spend `app.balance - app.min_balance`, with the fee at zero so nothing is taken ahead of it.

*From Chapter 7.*

### A non-zero inner transaction fee is paid out of the contract's own balance {-}

The fee on an inner transaction comes from the application account. `fee: UInt64 | int = 0` is already the default on every `itxn` builder, so the danger is a fee somebody wrote a non-zero value into, most often `Global.min_txn_fee`. On a public method that is an unbounded drain of one min-fee per call, and an account drained toward its minimum fails every other inner transaction it wants to send. Write `fee=UInt64(0)` explicitly, and make the caller cover the group with `assert Txn.fee >= Global.min_txn_fee * UInt64(N)` --- a floor, not the fee the client attaches. Chapter 8's `simulate` reports `group-usage`; that, not this product, is the client's fee.

*From Chapter 7.*

### A ClearState program cannot send an inner transaction {-}

Budget is not the reason: each inner application call *adds* 700 units to the pooled opcode budget when it is submitted, a gift rather than a cost. The restriction is the ClearState program itself, which the protocol runs with inner transactions forbidden outright --- so a clear-state exit can never refund a deposit, sweep a balance, or return anything to the account on its way out. Anything a leaving user should get back has to move in an ordinary method before the clear; Chapter 4's trapdoor rule about liabilities in local state is this restriction seen from the storage side.

*From Chapter 15.*

## Atomic groups {-}

### A typed group argument checks the type, never the contents {-}

`payment: gtxn.PaymentTransaction` guarantees that the named slot holds a payment. It guarantees nothing about the receiver, the amount, the sender, or, for an asset transfer, which asset. A payment the caller sent to their own account satisfies the type perfectly, costs one fee, and leaves their balance where it started, so an unchecked deposit method hands out positions for free. Ask all four questions on every incoming transfer: `xfer_asset` against a stored id, `amount` against a floor, `receiver` against `Global.current_application_address`, and `sender` against `Txn.sender`. The asset id in particular must come from state your contract wrote, never from a method argument: an id the caller supplies is a formality the caller performs on themselves.

*From Chapter 7.*

### A group index check without a group size check bounds nothing {-}

Checking `Txn.group_index` says where your call sits; it says nothing about how many other transactions ride alongside it, and a group may hold sixteen. A method that reads a payment at a fixed index and never asserts `Global.group_size` can be called once per remaining slot against the same payment, crediting the same money up to sixteen times in one atomic group --- every transaction in which is valid, correctly signed, and honest about what it is. An attacker who cannot forge a transfer can still restructure the group around one, which is what makes the receiver and asset checks matter. Assert the size and the index together, and read neighbours position-relative (`Txn.group_index - 1`) rather than absolutely, so the pattern survives being nested later.

*From Chapter 7.*

### Transactions in a group see each other's state changes as they execute {-}

Atomicity is about the *commit*, not about isolation. The transactions in a group execute in order against a single shared, copy-on-write view of the ledger, so the second app call in a group reads the state the first one wrote; the group's changes land in the ledger together only if every transaction succeeds. This is what makes fund-then-call work at all. It is also why "nobody can observe an intermediate state" is the wrong mental model: a contract you call in the same group absolutely can, and a design that assumes otherwise is assuming a guarantee the protocol never made.

*From Chapter 15.*

## ASAs {-}

### Two asset arguments may name the same asset {-}

Two parameters of type `Asset` are two names, not two things, and neither the ABI nor the AVM will stop a caller passing one asset for both. In a pool contract, every later method reads the two as opposing sides of a trade; with one asset on both sides, a deposit becomes instantly withdrawable from the other side at whatever the pricing arithmetic produces. This is the core of the Tinyman V1 exploit of January 2022, worth roughly three million dollars, and the fix is `assert a.id != b.id` in the method that stores them. The same reasoning applies to any pair of same-typed arguments that the contract will later treat as distinct: two accounts, two boxes, two application ids.

*From Chapter 7.*

### A contract-held clawback address is custody, and it is visible on-chain {-}

Setting `clawback` to the contract address means the contract can take the NFT from anyone at any time. This is necessary for revocation, but it means the NFT is not fully "sovereign": holders should understand that the vesting contract retains authority over it. This is visible on-chain and should be communicated clearly in your application's UI.

*From Chapter 12.*

### An inner transfer to a holder who never opted in reverts the whole call {-}

The settlement step sends vesting tokens to `current_holder`, and a holder who has not opted into the vesting token makes that inner transfer fail --- which reverts the entire revocation, so a holder can block being revoked by refusing one opt-in. The production form checks the holder's opt-in status before attempting settlement: if they are not opted in, skip the transfer and store the unclaimed amount for later retrieval through a separate `withdraw_settled` method. A refusal you cannot prevent must never be able to veto an action you must be able to take.

*From Chapter 12.*

### The caller must opt into the LP token before the pool can send it {-}

The caller must have already opted into the LP token before calling `add_initial_liquidity`. If they have not, the inner `AssetTransfer` sending LP tokens will fail, and the entire atomic group rolls back: the pool receives no tokens and no state changes. This is the "lazy opt-in" pattern: the contract does not check the opt-in explicitly; the protocol enforces it automatically. Client code must perform a zero-amount self-transfer of the LP token before calling `add_initial_liquidity`.

*From Chapter 14.*

## Pricing math {-}

### Floor the payout, ceil the charge --- the rule is directional {-}

"Round in the contract's favour" is one rule with two spellings, and using the wrong one is invisible in testing because both agree whenever the division comes out exact. A division that decides how much *leaves* the contract floors, so the fraction stays behind. A division that decides how much the caller must *send in* takes the ceiling, so the fraction is paid rather than forgiven. Getting the second one wrong is a discount of up to one unit per call, unbounded because calls are unbounded, and it is the shape that drains a pool one microunit at a time while every integration test passes. The AVM has no ceiling opcode: `(numerator + denominator - 1) // denominator` is how you write one.

*From Chapter 13.*

### An empty pool is an attack surface, and the first depositor owns it {-}

A pool that mints shares in proportion to reserves can be opened with a single unit, inflated by a direct transfer that mints nothing, and then handed a victim's deposit that rounds to zero shares, leaving the attacker holding the only claim on both. The defence is two lines that do different jobs: burn a fixed minimum of shares to nobody at creation, which multiplies the donation the attack needs by that minimum, *and* refuse any deposit that would mint zero rather than accepting it. The first raises the price; only the second closes the door. The lock is not free, since the reserve behind those burned shares is unclaimable for the life of the pool, so it is a trade and the first depositor is the one who pays for it.

*From Chapter 13.*

### Never price against spot: a single atomic group can move it {-}

A spot price is one division away from the current reserves, and the reserves are one swap away from wherever an attacker wants them: push, read, restore, all inside one atomic group, at no cost beyond fees and slippage. Any contract that prices collateral, liquidations, or payouts against `reserve_b / reserve_a` is reading a number its caller can choose. Price against the cumulative accumulators instead --- store periodic snapshots and difference them over a window --- so that distorting the answer costs the attacker the whole window rather than one block. Chapter 14's pool ships the accumulators in its global state for exactly this consumer.

*From Chapter 14.*

### Updating the accumulator with zero stake divides by zero {-}

The zero-balance guard is critical. If `total_staked` is zero, the update must be skipped entirely: dividing by zero panics the AVM, and accumulating rewards when nobody is staked would create tokens from nowhere. Always check `total_staked > 0` before updating the accumulator.

*From Chapter 17.*

### Distribution must never exceed rate times elapsed time {-}

The total rewards distributed must never exceed `reward_rate * elapsed_time`. Rounding in `op.divmodw` floors toward zero, ensuring the contract always retains dust. If you ever observe total distributions exceeding the reward pool, you have a bug. This is the single most important property to verify in your tests.

*From Chapter 17.*

### Enough stake floors the per-token increment to zero and rewards stall {-}

`PRECISION = 10^9` also sets a *usability bound* on the other side. Each update computes $increment = \lfloor rate \times \Delta t \times 10^9 / \text{total\_effective} \rfloor$, so whenever `total_effective` exceeds $rate \times \Delta t \times 10^9$, the increment floors to zero, yet `last_update_time` still advances, so that interval's rewards are permanently stranded. With very large stakes relative to the reward rate, most of a schedule's rewards can strand this way. Conservation still holds (the contract never overpays, and unstreamed rewards stay in `rewards_remaining`), but stakers receive less than the advertised rate. Production systems shrink the loss to negligible by using $10^{18}$-scale precision (with `BigUInt` arithmetic) or by carrying the division remainder forward between updates.

*From Chapter 17.*

## Cross-contract calls {-}

### A caller-supplied application id lets the caller choose what your contract believes {-}

An `Application` parameter is a `uint64` on the wire, and nothing in the ABI, the router or the AVM checks that the id names the contract you had in mind. A method that takes the id of an oracle, a pool, a registry or a child and then trusts what it returns is a method whose answers are chosen by whoever calls it: deploying a contract that answers to the same signature and returns a convenient number costs one fee and no privilege. The defect survives testing because every test passes the right id. Store the id in state, written once behind a creator or admin guard, and read it --- or, where the id must vary, check its provenance before trusting the reply, which is what Chapter 16's registry exists to make possible. The same reasoning covers asset ids, as Chapter 7 showed.

*From Chapter 15.*

### A newly created application has an address and no money {-}

Creating an application allocates its account but funds nothing, so the child comes into existence unable to write a box, opt into an asset, or send an inner transaction: every one of those raises a minimum balance it cannot meet. The failure arrives from the ledger rather than from any assertion, names an account rather than an application, and appears on whatever method first tries to store something rather than on the creation that caused it. A parent that deploys a child should fund it in the same method, for the account's 100,000 floor plus whatever the child's first write will cost, and refuse an amount that leaves it still unable to act.

*From Chapter 15.*

### A caller application id of zero, once stored, makes the guard that reads it vacuous {-}

`Global.caller_application_id` is zero when a person called your contract directly, which Chapter 10 uses to tell a contract caller from a human one. Storing that value at creation is a different act with a different consequence: a child deployed by a person rather than by its parent keeps zero as its `parent`, and every later `assert Global.caller_application_id == self.parent.value` then compares zero against zero and passes. The guard is not permissive, it is *vacuous*: it admits exactly the caller it was written to exclude, and it reads correctly on the page. The corrected worker asserts the id is non-zero in `create`, which is the same check Chapter 16 carries. Any contract that stores an identity at creation and checks it later has this shape.

*From Chapter 15.*

### A contract's own global state is not evidence about its parent {-}

Reading `factory_app_id` out of a pool and comparing it to the factory you trust proves only that the pool *claims* that parent. Global state is writable by its own application and by nothing else, which cuts both ways: nobody can forge the real factory's state, and anybody can forge a claim about it. Verification has to run in the direction where the trusted party is the writer --- ask the factory whether it created this pool, never ask the pool who created it. The same asymmetry governs every cross-contract trust decision in this book.

*From Chapter 16.*

### A cross-contract read spends one of the transaction's reference slots {-}

The foreign apps array has a maximum of 8 entries per transaction (shared across the group since AVM v9). Each cross-contract read consumes one slot. If your transaction already references several apps, you may not have room for the AMM reference. Plan your foreign reference budget carefully when designing multi-contract interactions.

*From Chapter 17.*

### A callee's assert message does not survive an inner application call {-}

When your contract calls another application and the callee's own `assert` fires, what reaches your user is `inner tx 0 failed: logic eval error: assert failed pc=<n>`. The callee's ARC-56 message is not in it, and the program counter is an offset into the callee rather than into anything the caller's specification can explain. The same failure raised by a direct client call to the callee is fully described, so this cannot be found by testing the callee. If the callee offers a variant that returns absence as a value, take it --- an error you can name is worth more than one you have to explain.

*From Chapter 18.*

## Cryptography {-}

### A commitment to a low-entropy value is not hiding anything {-}

`sha512_256(amount)` is a lookup table away from being plaintext when `amount` is one of a few thousand plausible numbers. The commitment hides a value only if the value is unguessable, so commit to `value || nonce` with at least 32 bytes of nonce and treat the nonce as a secret until the reveal.

The same reasoning applies to any commitment over a small domain: a vote among four options, a yes/no, a choice of counterparty. If it can be enumerated, hash it with something that cannot.

*From Chapter 18.*

### `keccak256` is for Ethereum compatibility, not for hashing {-}

It costs 130 units against `sha512_256`'s 45 and `sha256`'s 35, and buys nothing unless a digest has to match one computed on Ethereum: verifying an Ethereum signature, checking a merkle root produced by an Ethereum contract, deriving an Ethereum address. For anything internal to your own contract, the native hash is nearly three times cheaper and is what the rest of the protocol already uses.

*From Chapter 22.*

### A signature proves who signed, never what they meant {-}

Verification tells you a key produced a signature over some bytes. It says nothing about which of your code paths those bytes were intended for, so any two paths verifying a signature over the same message accept each other's signatures. Prefix every signed message with a domain string naming the operation, and include anything that scopes it --- the application id, a nonce, an expiry --- inside the signed bytes rather than beside them.

*From Chapter 22.*

### A `BN254g1` pairing check does not fit in one program's budget {-}

BN254 `ec_pairing_check` is 8,000 plus 7,400 per chunk of its second operand, where a chunk is the point size of the group you named. Under `BN254g1` you named the 64-byte group and the second operand holds 128-byte G2 points, so one pair is two chunks: 22,800, already over a LogicSig's 20,000 and thirty times an application call's 700, before any surrounding code. No rearrangement of that code helps; the opcode alone exceeds the budget.

Two things do. Naming `BN254g2` puts the 64-byte G1 points in the counted operand against a 128-byte chunk, so one chunk covers two pairings --- one pair drops to 15,400 and four pairs to 22,800 against `BN254g1`'s 67,200. And the budget itself comes from the group: `len(group) x 20,000` for LogicSigs, with every transaction contributing.

*From Chapter 22.*

### One mimc hash costs more than an application call's entire budget {-}

One `mimc` over 64 bytes costs 1,110 units --- 10 plus 550 per 32-byte block --- and an application call has 700. Any method hashing two field elements must raise its budget before the opcode: `ensure_budget(UInt64(1200), OpUpFeeSource.GroupCredit)` issues no-op inner app calls worth 700 units each, their fees drawn from the group's pooled fee credit, so the caller overpays the outer fee. Without it the call dies with `dynamic cost budget exceeded`. This chapter's instance is `reveal_vote`, whose recomputed `choice || randomness` commitment is exactly such a 64-byte hash.

*From Chapter 23.*

## LogicSigs {-}

### These checks belong in a LogicSig and nowhere else {-}

`close_remainder_to` and `rekey_to` are the fields a LogicSig must pin on every payment it approves, and `asset_close_to` is the third wherever it permits an asset transfer at all. A LogicSig *is* the sender's authority, so an unchecked field is authority it granted: any of the three can hand the account, its balance, or its holdings away inside a transaction the program said yes to. Chapter 10's twin gotcha rules on the other side of the line --- why a stateful contract must *not* copy these checks onto the transactions in its group.

*From Chapter 20.*

### A signed delegated LogicSig cannot be cancelled {-}

The delegator's key signs the program once and is never consulted again, so there is no later moment at which consent can be withdrawn. Deleting your copy of the signed blob changes nothing --- copies may be anywhere, and the network does not know or care where it came from.

The only exit is to rekey the delegating account, which invalidates the delegation by changing what authority the account has. Plan for that before signing: an expiry in `last_valid` costs one line and turns "forever" into "until round N".

*From Chapter 20.*

### Rekeying to an address you cannot sign for loses the account {-}

`rekey_to` moves signing authority with no confirmation step and no undo. If the destination is an address you do not hold the key for, every asset and every Algo in that account is unreachable --- the account still exists, still shows a balance, and can never send anything again.

Check the `rekey_to` value before signing, and check it again when it is a variable rather than a literal. This is the one transaction field where a typo is unrecoverable.

*From Chapter 20.*

### A parameterised LogicSig gives one address per parameter set, chosen at compile time {-}

The natural way to write "an escrow for this customer" takes the customer as an argument, and that is exactly the form that will not compile. A per-customer escrow is not a per-customer compile.

Two shapes work instead. Compile **one** program that reads the customer from somewhere it can verify, such as its own account's state or a value the calling contract passes and checks; or accept that the set of parameter combinations is fixed at build time and enumerate them. Reaching for the first is almost always right; the second is how people end up with a deployment script that compiles four hundred LogicSigs.

*From Chapter 20.*

### A LogicSig's arguments are supplied by the submitter, not the signer {-}

The signature covers the program, not the arguments. Anything read from `op.arg(n)` was chosen by whoever assembled the transaction, so it may bound nothing and prove nothing. A secret compared against an argument is worse still --- the program's bytes are public at an address anyone can query.

*From Chapter 20.*

### `LogicSigAccount.address()` on a signed delegation returns the delegator, not the program hash {-}

Once a delegation is signed, `LogicSigAccount.address()` reports the *delegating account's* address; the program hash comes from `algosdk.logic.address(program)`. Code that confuses them compiles and runs: a keeper checking an order's stored hash against `address()` compares an account against a program hash, silently declines every valid order, and reports nothing wrong.

*From Chapter 21.*

### suggested_params() can hand you a last_valid past the LogicSig's expiry {-}

A LogicSig that bounds itself with `Txn.last_valid <= EXPIRY` rejects any transaction `suggested_params()` dated past that round --- the default validity window knows nothing about the program's own deadline. Cap it before building: `sp.last = min(sp.last, expiry_round)`. Here, the sell side of every fill group needs the cap or the order program refuses it near its expiry.

*From Chapter 21.*
