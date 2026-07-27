\newpage




\part{Foundations}

Part I establishes the mental model, tooling, and core skills you need for everything that follows. You will learn how Algorand's execution model differs from traditional programming, set up your development environment, learn how to test smart contracts, and build your first two smart contracts --- a token vesting system and an NFT extension --- that introduce every foundational concept.

# The Algorand Mental Model

Algorand is a *proof-of-stake* blockchain with *instant finality*, a block time of roughly 2.85 seconds, and no forking. Every confirmed transaction is final --- there is no "wait for six confirmations." Block proposers and committee voters are selected secretly by a *Verifiable Random Function*, so there is nobody to attack before they reveal themselves. All of that is true, and none of it is what makes writing a contract feel strange the first time. What makes it feel strange is much smaller and much closer to your keyboard: a contract is not a program that runs. It is a program that is *asked a question*, once, and answers yes or no.

Everything in this chapter follows from that sentence.

## The Problem
Here is a failure with a name: **the greeter nobody could turn off.**

A team ships a small contract to LocalNet and then to TestNet. It has exactly two methods. `greet` takes a name and returns a greeting. `shut_down` deletes the application, so the team can pull it and redeploy when they want to change something. `greet` is tested thoroughly. `shut_down` is not tested at all, on the reasonable-sounding grounds that it is an admin method and the admin is the person writing the test.

The first problem arrives from a stranger. Somebody calls `greet` with an empty name, and the call is rejected --- correctly, the contract meant to reject it --- with this:

```console
LogicError: Txn TFWY...J4A had error 'assert failed pc=78'
at PC 78 and Source Line 63:
    ... 10 lines of TEAL trace ...
```

That is the entire diagnostic. Not which assertion. Not why. A number, twice. The team has the source in front of them and can guess, but the person integrating against the contract from another company cannot, and the support thread that follows is three days long.

(Every `LogicError` in this book is shown the same way: the message's first line, wrapped where it is too long for the page, and then the ten lines of *generated TEAL* the real exception prints around the failure, cut under the marker. The `Source Line` is a line of that TEAL, counted from zero, not of your Python --- a client that compiled the contract itself holds the map from program counters to TEAL lines, and nothing in the pipeline makes the next hop --- back to the file you wrote --- for you. {{ch:testing}} closes that gap.)

The second problem is worse. The team decides to pull the contract and redeploy it with better error messages. They call `shut_down` from the deployer account. Rejected. They try the admin account, then every account they control. Rejected, all of them. Then somebody reads the guard properly:

```python
assert Txn.sender == Global.current_application_address, "admin only"
```

That line does not name the creator. It names the *application's own account* --- the address derived from the app ID, the one the contract itself spends from. No human being holds the private key to that address, because it was never generated from a key; and an application cannot appear as the top-level sender of a transaction, so it cannot call itself either. The guard is not merely wrong. It is *unsatisfiable*. There is no account in existence, and none that can ever be created, that passes it.

The application is now permanently deployed, permanently broken, and permanently undeletable. It will sit on the chain until the network does, and the 100,000 microAlgos of minimum balance it costs the creator's account to have created it will never come back.

Nothing in that contract is a typo. It compiles, it deploys, every line does exactly what it says. The mistake is upstream of the code: a belief about who is who on this chain, and about what a contract is allowed to assume. The rest of this chapter is about fixing that belief before it costs you an application.

## What You'll Be Able to Do
By the end of this chapter you will be able to:

- Explain what happens between submitting a transaction and seeing it confirmed, and say precisely when your state changes become real
- Write a complete, deployable contract from an empty file, and read the TEAL it compiles into well enough to recognize the parts
- Name the four accounts a contract can talk about --- sender, creator, application, and an arbitrary referenced account --- and say which of them can sign a transaction
- Attach a diagnostic message to a failing assertion and then find that message again from a client, knowing where it was stored
- Compute the minimum balance of an account holding assets, applications, and boxes, and say which account pays it
- Compile a contract, generate a typed client from its app spec, and call a method with real Python types
- Predict which of your contract's assumptions a stranger can violate, given that every method is a public entry point

{{fig:notional-machine}} is the whole machine in one picture: everything a contract is allowed to look at, everything it is allowed to stage, and the single approve-or-reject decision that stands between the two. Read it before you read any code. Every limit described in this chapter is somewhere in that diagram.

{{include-fig:notional-machine}}

## The Mini-Build, Broken
Example: The greeter, as first written {#ex:greeter-broken}

<!-- finder: see the smallest useful contract that has an admin method -->

{{include-ex:greeter-broken}}

{{ex:greeter-broken}} is complete and deployable. It compiles, it runs on LocalNet, and it contains three decisions that are wrong. The story you just read has already shown you two of them; the one it has not is sitting in plain sight, and stays invisible until a stranger goes looking for it.

*Predict: three decisions in that contract are wrong. Write your three down now, in whatever words you have --- you are not expected to be right yet. Check them against the diff at the end of the chapter.*

Deploy it:

```console
$ algokit project deploy localnet
greeter 1042 deployed
```

Then call it. The happy path is perfectly happy:

```python
>>> greeter.send.greet(args=("Ada",)).abi_return
'Hello, Ada'
```

The unhappy paths are where it gets interesting:

```python
>>> greeter.send.greet(args=("",))
LogicError: Txn 6ZQK...H2A had error 'assert failed pc=78'
at PC 78 and Source Line 63:
    ... 10 lines of TEAL trace ...
>>> greeter.send.greet(args=("A" * 1100,))
LogicError: Txn PN4T...K9C had error 'program logs too large.
1113 bytes >  1024 bytes limit' at PC 106 and Source Line 80:
    ... 10 lines of TEAL trace ...
>>> greeter.send.shut_down()
LogicError: Txn W2LD...R7B had error 'Runtime error when executing Greeter
(appId: 1042) in transaction W2LD...R7B: admin only'
at PC 115 and Source Line 92:
    ... 10 lines of TEAL trace ...
```

Three failures, and they fail in three different ways. The first is correct behavior reported uselessly: the contract meant to reject an empty name, and the only thing it can tell you is a number. The second is a limit the contract never mentions and never checked --- and note that the number in it, 1,113, is larger than the name you sent, for reasons this chapter will make exact. The third is a correct-looking guard that no caller on Earth can satisfy; the message is readable, which makes it worse, because it is confidently describing a rule that cannot ever be met.

The sections that follow take that machine apart a piece at a time, and the pieces are chosen so that the three failures in that transcript become predictable rather than surprising.

## A Program That Only Says No
The fastest way to understand what a contract is is to write the smallest one that is still a real one.

Example: The smallest deployable contract {#ex:smallest-contract}

<!-- finder: write the smallest complete Algorand contract that actually does something -->

{{include-ex:smallest-contract}}

The load-bearing line is `class Smallest(ARC4Contract)`. Inheriting from `ARC4Contract` is what turns a Python class into an application: it generates the *router*, the dispatch code that reads the first application argument, matches it against the method selectors of every `@arc4.abimethod`, and rejects anything it does not recognize. The [ARC-4](https://dev.algorand.co/arc-standards/arc-0004) calling convention is the standard every Algorand tool assumes, and you get it by subclassing.

There is no `main`, no server, no loop. When somebody calls `ping()`, this program runs from the top, returns, and stops. When nobody is calling it, it is not running at all --- it is bytes in the ledger.

Example: An assertion that says why {#ex:assert-message}

<!-- finder: attach a readable error message to a failing check -->

{{include-ex:assert-message}}

The load-bearing element is the string after each comma. `assert amount > UInt64(0)` and `assert amount > UInt64(0), "double: amount must be positive"` compile to the same on-chain behavior --- the transaction is rejected either way --- but only the second one leaves the compiler anything to record.

This is where the mental model earns its keep, because the message is **not on chain**. The AVM has no notion of an error string; a failing `assert` aborts the program at a program counter and that is all the network reports. The compiler puts your message in the ARC-56 app spec instead, keyed by that program counter, and the client SDK maps the number back to the string when it builds the exception. Ship a contract without app spec, and your callers get numbers. Write an assertion without a message, and there is nothing to ship. You will see that absence literally in "From a Python File to a Call You Can Make" later in this chapter, when you print the greeter's app spec and count the entries.

*Why you would want this:* the person who most needs the message is not you. It is the integrator calling your contract from a codebase you will never see, whose only view of your failure is whatever the SDK can reconstruct.

*What this section repairs in the greeter:* the first failure. `assert name.bytes.length > 0` carries no message, so the compiler had nothing to record and the caller got `assert failed pc=78` and nothing else.

## Four Accounts, and Only Two of Them Can Sign
A contract can name four different accounts, and telling them apart is not a naming convention --- it is the difference between a working guard and an unsatisfiable one.

Example: The three reference types {#ex:reference-types}

<!-- finder: ask the ledger a question about an account, an asset, or another app -->

{{include-ex:reference-types}}

The load-bearing insight is that `Account`, `Asset`, and `Application` are not data you receive --- they are *handles you are given permission to look up*. An `Account` argument does not carry a balance across the wire; it carries 32 bytes, and `token.balance(who)` reaches into the ledger to answer. That is why these three types have methods at all, and why the transaction must declare them (a topic that becomes urgent in {{ch:token-vesting}}).

Four accounts matter in almost every contract you will write, and confusing any two of them is a security bug rather than a typo. `Txn.sender` is whoever signed this call. `Global.creator_address` is the account that created the application, fixed forever at creation. `Global.current_application_address` is the application's *own* account --- the one derived from the app ID, which holds the contract's Algo and assets. And an `Account` argument is an arbitrary third party the caller named. Only two of those four can ever sign a transaction.

Here is what happens when you pick the wrong one:

{{include-ex:reference-types-wrong}}

This is the greeter's third failure, isolated. Every deployed smart contract has a deterministic address derived from its application ID: `SHA512_256("appID" || big_endian_8_byte(app_id))`, where `"appID"` is a literal ASCII domain separator and `||` is concatenation. That derivation is completely unlike the Ed25519 key generation that produces wallet addresses, which is exactly the point --- application addresses can never collide with user accounts, and *no private key exists* for one. The contract's code is the sole custodian of everything that address holds. An address with no key is an address that cannot sign, and an account that cannot sign can never be `Txn.sender`.

*Predict: is there any transaction --- any group, any inner transaction, any sequence at all --- whose `Txn.sender` is an application address? Answer before reading the next paragraph.*

No. Inner transactions *are* sent by the application account, but an inner transaction is not a top-level transaction, and `Txn` inside a contract refers to the call being validated, not to anything the contract itself emits. The guard is unsatisfiable in every configuration.

*What this section repairs in the greeter:* the third failure. `shut_down` guards against the application's own address, which no sender can ever be. It meant `Global.creator_address`.

## What ARC4Contract Writes for You
Which of the two programs in a contract runs, and what the network does afterward, is decided by a field on the transaction called its *OnComplete*. `shut_down` in {{ex:greeter-broken}} declares `allow_actions=["DeleteApplication"]`, which is one of six. {{fig:oncompletes}} shows all six as the lifecycle they describe. Note where ClearState sits: it is the one transition your contract has no power to refuse, and {{ch:state}} is largely about the consequences.

{{include-fig:oncompletes}}

Every contract has two programs. The **approval program** handles creation, method calls, opt-ins, close-outs, updates and deletes --- all your business logic. The **clear state program** runs only when a user forcibly detaches from your application, and the protocol guarantees their local state is deleted whether it approves or not.

So far you have been told the router exists. Here it is written out by hand, so you can see that there is no magic in it:

Example: The same contract without `ARC4Contract` {#ex:without-arc4contract}

<!-- finder: understand what ARC4Contract generates for me -->

{{include-ex:without-arc4contract}}

The load-bearing line is `assert Txn.application_args(0) == Bytes(PING)`. A method selector is not a name lookup --- it is the first four bytes of `SHA-512/256("ping()string")`, compared as bytes. `arc4.abimethod` computes that constant for you and emits the comparison; here you type both yourself.

Compile both and the shape is the same, though the hand-written one is looser: it checks the OnComplete but never checks that the application already exists, so it would accept a `ping` call that also created the application. The generated router checks both, in one expression. This is `Smallest`, generated, with the compiler's source-line comments removed:

```teal
#pragma version 12
#pragma typetrack false

main:
    txn NumAppArgs
    bz main___algopy_default_create@5
    pushbytes 0xb132c056 // method "ping()string"
    txna ApplicationArgs 0
    match main_ping_route@3
    err

main_ping_route@3:
    txn OnCompletion
    !
    txn ApplicationID
    &&
    assert
    pushbytes 0x151f7c750004706f6e67
    log
    pushint 1
    return

main___algopy_default_create@5:
    txn OnCompletion
    !
    txn ApplicationID
    !
    &&
    return
```

Read the constant `0x151f7c750004706f6e67`. The first four bytes are ARC-4's return-value prefix, which is how a caller tells "this log line is my return value" from "this log line is a debug message." Then `0004`, the length of a four-byte string. Then `pong`. **An ABI return value is a log entry.** The AVM has no return channel; returning a value means writing bytes to the transaction's log and agreeing on a convention for reading them back. Hold on to that --- it is the greeter's second failure.

`main___algopy_default_create@5` is the bare-create path: a call with no arguments is accepted only if it is a creation with OnComplete NoOp. The clear state program is the second half of the pair. `Smallest` never writes one, so `ARC4Contract` generates `pushint 1 / return` --- approve unconditionally, since refusing changes nothing. {{ex:without-arc4contract}} has no `ARC4Contract` to generate it, so it has to write that same two-line program itself; that is the one piece of the pair the router does not cover.

*What this section sets up in the greeter:* the second failure. The ABI return value is a log entry, the log is a budget, and the greeter never bounded what it returns. {{ex:compile-output}} will show you the exact byte count.

## Who Owns What: Accounts, Balances, and the Application's Address
Algorand tracks balances per account, the way a bank ledger tracks yours in a single row that moves up and down. (This is an *account-based model*. Bitcoin uses the alternative, *UTXO*, which tracks individual coins that are created and consumed --- you will not need it here.) Accounts are 32-byte public keys written as 58-character base32 strings, and each one holds Algos plus whatever Algorand Standard Assets it has opted into.

Every account must keep a *minimum balance* to exist at all. This is the anti-spam mechanism: without it, an attacker could create billions of empty accounts and bloat every node's ledger. The base is **100,000 microAlgos (0.1 Algo)**, and every resource an account holds raises it:

- Each ASA opted into: +100,000 microAlgos
- Each application created: +100,000 microAlgos, plus the declared state schema
- Each application opted into: +100,000 microAlgos, plus the local schema
- Each declared global slot: +28,500 for a `uint64`, +50,000 for a byte slot
- Each box created: +2,500, plus 400 × (name bytes + value bytes)

Minimum balance is not a fee. Nothing is deducted --- the floor simply rises, and only the Algo above the floor is spendable. A transaction that would push an account below its floor fails with `account <address> balance <n> below min <m> (<k> assets)`, the error new developers meet most often. {{fig:mbr-slab}} draws it to scale for a contract account holding two assets and one box: the balance an explorer reports, and the sliver of it the contract can actually move.

{{include-fig:mbr-slab}}

**Worked example.** A vesting contract opts into 2 ASAs and stores schedules for 10 beneficiaries in boxes, each with a 10-byte name and a 40-byte value. The application account's minimum balance is 100,000 (base) + 2 × 100,000 (opt-ins) + 10 × (2,500 + 400 × 50) (boxes) = 525,000 microAlgos, about 0.53 Algo. Fund it before creating the boxes or the transactions fail.

Two facts about *who* pays are worth memorizing now, because they are asymmetric and people get them backwards. Box minimum balance is charged to the **application account**, which is why contracts that create boxes must be funded. Global and local schema minimum balance is charged to a **user** --- the creator for global, the opting-in account for local. A generous local schema you never fill is a tax you levy on every one of your users.

The opt-in requirement is the other half of the same idea. On some chains anyone can push tokens into your wallet; on Algorand you must explicitly *opt in* to each ASA first, at a cost of 0.1 Algo in minimum balance. Your contract must opt into every asset it will hold, and users must opt into anything you send them.

Contracts persist data in three places, each with a different owner: **global state** (a fixed schema of up to 64 key/value pairs belonging to the application), **local state** (up to 16 pairs per opted-in account, which that account can delete unilaterally), and **box storage** (independently created keys of up to 32,768 bytes that only the application can remove). Which one you choose is an architectural decision with money attached, and it gets two chapters of its own: {{ch:state}} for the two schema-bound slabs, {{ch:boxes}} for the unbounded third. The one-line version is that anything the contract *owes* somebody must not live anywhere that somebody can erase.

*What this section repairs in the greeter:* nothing in the code --- and everything in the story. The 100,000 microAlgos locked in the creator's minimum balance are locked because the application still exists, and it still exists because `shut_down` names an address with no key.

## All or Nothing
A rejected transaction does not partially happen. This is the property that makes an `assert` worth writing.

Start with the shortest lifecycle you will ever meet. You sign a transaction and submit it to a node. That node evaluates it right away --- signatures, minimum balances, well-formedness, and, for an application call, your approval program --- and gossips it onward only if it passes. This is where the `LogicError` in the preceding transcripts comes from: it arrives in milliseconds, from your own node, before any block exists. A block proposer selected by the Verifiable Random Function then includes the transaction in a block, and every node validating that block runs your approval program again. The program is deterministic, so they all reach the same verdict; what makes the block run special is that it is the only one whose effects are recorded. Approve, and the transaction's effects --- balance changes, state writes, boxes created --- are applied as the block is written. Reject, and nothing is applied and the transaction is not in the block at all.

Inside the block, your program sees the ledger as it stands at that instant, not a snapshot taken beforehand. A payment earlier in your group has already moved the money by the time the application call after it runs, and a state write by an earlier call is visible to a later one. That is what makes atomic groups useful rather than merely tidy.

Then the part that is genuinely different from other chains: **the block is final when it is written.** Roughly 2.85 seconds after you submitted, with no confirmations to wait for, no reorganization that can undo it, and no probabilistic settlement. There is exactly one moment when your state changes become real, and it is the moment the block containing them is agreed. Everything before that moment is a proposal; everything after it is history. This is why an Algorand contract has no notion of a pending write, no callback for "later," and no need for the confirmation-counting machinery you may be carrying in from elsewhere.

Algorand has seven developer-facing [transaction types](https://dev.algorand.co/concepts/transactions/types/) --- payment, asset transfer, asset configuration, asset freeze, application call, key registration, and state proof. (An eighth, heartbeat, is internal to consensus.) For contract work you will mostly see the first, the second, and the fifth.

Up to 16 of them can be submitted as an [atomic group](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/). Every transaction in the group succeeds or every one fails; there is no partial execution, and no rollback either, because nothing was ever applied. Groups are assembled *off-chain*: the client builds all the transactions, computes a group ID from their individual hashes with the group field zeroed, stamps it on each one, and submits the bundle. This is the foundation of Algorand DeFi --- a user can bundle "send tokens to the pool" and "call swap" and know they cannot lose one without the other.

{{fig:atomic-group}} runs the same four transactions twice: once where all four pass, and once where the third is rejected. Notice that the first two in the failing run are not undone. They were never applied.

{{include-fig:atomic-group}}

The minimum [fee](https://dev.algorand.co/concepts/transactions/fees/) is **1,000 microAlgos** per transaction, and fees are validated across the group rather than per transaction. The sum of all fees must cover the sum of all minimum fees, which means one transaction can overpay to cover others --- *fee pooling*. You will use it constantly, because a contract that sends money pays for that send out of the group's fee budget.

Contracts can also emit [inner transactions](https://dev.algorand.co/concepts/smart-contracts/inner-txn/): transactions created *on-chain*, by contract logic, during execution. When your contract needs to pay someone or transfer an asset, this is how. Inner transactions are atomic with the outer call --- if the call fails, they never happened --- and the budget for them is pooled across the whole group: 256 inner transactions shared by every application call in it, which one call may spend by itself. The distinction from atomic groups is worth keeping sharp: a group is a client-side bundle of transactions the user signed, an inner transaction is one the *contract* authorized with its own address. {{ch:token-vesting}} uses them from its first payout onward.

*What this section repairs in the greeter:* the reason its bugs are survivable. Every failed `greet` call in the story left the ledger exactly as it found it. The only permanent damage was done by the call that *succeeded* --- the creation.

## The Edges of the Machine
Knowing what the AVM refuses to do is as load-bearing as knowing what it does, because most first designs assume at least one thing on this list. Every number below is a boundary drawn somewhere in {{fig:notional-machine}}; when you need the full table rather than the shortlist, it is in {{ch:avm-limits}}.

- **No floating point.** There are two types: `uint64` and `bytes`. Prices are rationals, held as a numerator and a denominator, and rounded deliberately. {{ch:token-vesting}} does this for real.
- **No unbounded loops.** Each instruction costs from an *opcode budget* of 700 per application call --- most cost 1, cryptographic operations cost far more. The budget pools across the application calls in a group, so four app calls share 2,800, and padding a group with no-op calls to buy budget is a real technique ({{ch:patterns}}). LogicSig programs get a separate 20,000 per program. You cannot iterate over an arbitrarily large data set in one call.
- **A hard log budget.** An application call may write **1,024 bytes** to its log, across at most 32 `log` calls. Since an ABI return value *is* a log entry, this is a ceiling on what your methods can return --- and it is not the same ceiling as the 2,048 bytes a call may carry in its *arguments*. A caller can therefore hand you more data than you are able to hand back.
- **No callbacks.** When your contract sends tokens by inner transaction, no code runs on the receiving side. Classical reentrancy does not exist here, which means you should not write defenses against it ({{ch:patterns}} explains what to write instead).
- **Constrained app-to-app interaction.** A contract can submit an inner application call, but that is transaction coordination, not a call stack with an arbitrary synchronous return. Your contract can *read* another application's global state; it cannot write it.
- **No private on-chain data.** Global state, local state and boxes are all readable off-chain through algod and the indexer. Boxes are private to the AVM --- only the owning application can read them in TEAL --- and completely public over REST.
- **No upgradeability unless you allow it.** Reject `UpdateApplication` and the code is immutable. For anything holding value, that is the right default.

*What this section repairs in the greeter:* the second failure, at last, with the arithmetic. `greet` returns `"Hello, " + name` with no bound on `name`. A name of 1,100 bytes fits comfortably in the 2,048 bytes of argument space; what gets logged is the 4-byte ARC-4 return prefix, a 2-byte length header, the 7 bytes of `"Hello, "`, and the name itself --- 1,113 bytes against a 1,024-byte ceiling. That is the number in the failure transcript. Any stranger can make the method fail, from outside, with a well-formed call, and the contract never mentions the limit it is breaking.

## From a Python File to a Call You Can Make
You have a contract. Turning it into something you can call takes four steps, and each one is a small program you can read.

The toolchain that runs them --- AlgoKit installed, LocalNet running, one contract already deployed --- is a twenty-minute errand with no ideas in it, so it lives in {{ch:setup}}. Do it now if you have not.

Example: What the compiler writes to disk {#ex:compile-output}

<!-- finder: see what algokit project run build actually produced -->

{{include-ex:compile-output}}

The load-bearing line is the loop over `spec["sourceInfo"]["approval"]["sourceInfo"]`. That is where assertion messages live, keyed by program counter, exactly as {{ex:assert-message}} claimed. Run it against the broken greeter and the claim becomes a measurement:

```console
$ python -m smart_contracts.compile_output
Greeter: 97 lines of approval TEAL
  greet(string)string
  shut_down()void
  pc 115 -> admin only
  pc 64 -> invalid array length header
  pc 72 -> invalid number of bytes for arc4.dynamic_array<arc4.uint8>
```

Three messages, and count what is missing. You wrote two assertions in this contract: the empty-name check and the admin guard. Only the admin guard appears, at pc 115. The other two entries --- `invalid array length header` and `invalid number of bytes` --- are ARC-4 decoding checks the compiler inserted on your behalf to validate the incoming `String` before your code ever runs. Your messageless `assert name.bytes.length > 0` is simply not there. `pc 78` is absent from the spec, which is why the client had nothing to print but the number. A messageless assertion does not produce an empty entry; it produces no entry at all.

The `.arc56.json` file this reads is the *ARC-56 app spec*: the portable description of your contract's public API --- method signatures, argument and return types, state schema, and this source map. Think of it as an OpenAPI document for a contract. It is what you publish so that other people can build against you.

Example: Pointing at a network with a funded account {#ex:algorand-client}

<!-- finder: connect to a network and get an account that can pay for things -->

{{include-ex:algorand-client}}

The load-bearing line is `AlgorandClient.from_environment()`. It reads algod and indexer settings from the environment rather than from your code, so the same script runs against LocalNet, TestNet and MainNet with no edit. `ensure_funded_from_environment` then tops the account up --- and this is the one line that is *not* portable. It uses `DISPENSER_MNEMONIC` from the environment if you have set one, and otherwise falls back to asking KMD for the LocalNet dispenser, which only exists on LocalNet. Off LocalNet with no mnemonic it fails looking for a dispenser that is not there. Treat it as a development convenience, not a line you leave in a deployment script.

Note `info.min_balance` in the output. That is the floor from "Who Owns What: Accounts, Balances, and the Application's Address" earlier in this chapter, reported by the ledger.

Example: Creating the app through a generated client {#ex:typed-client}

<!-- finder: deploy a contract using the typed client algokit generated -->

{{include-ex:typed-client}}

The load-bearing line is `factory.send.create.bare()`. `algokit generate client` reads the app spec and writes a Python class with real methods on it; `get_typed_app_factory` hands you the factory half of that class, which knows the compiled bytecode and can create the application. `bare` means a creation call with no ABI method behind it --- the `main___algopy_default_create` path you read in the generated TEAL earlier in this chapter.

Read that line carefully, because there are two factories in the ecosystem and their method chains are transposed. A *generated* factory, the one you get from `get_typed_app_factory`, spells it `send.create.bare()`. An *untyped* factory, built from an app spec with `get_app_factory` when no client has been generated, spells it `send.bare.create()`. {{ch:testing}} uses the untyped form for exactly that reason. The two are not interchangeable, and the failure is an `AttributeError` rather than anything informative.

Example: Calling a method with real types {#ex:typed-call}

<!-- finder: call a contract method and read the value it returned -->

{{include-ex:typed-call}}

The load-bearing line is `greeter.send.greet(args=("Ada",))`. Not a string method name, not an untyped argument list --- an actual method, checked by your type checker before you run it. The alternative is the *generic* client used in {{ch:setup}}, which takes `method="greet"` as a string and finds your typos at runtime.

`result.abi_return` is the log entry from earlier, decoded: the SDK strips the `0x151f7c75` prefix and reads the remaining bytes as the return type in the app spec.

Underneath both clients, an ABI call is just an application call with a particular byte layout in its argument array. {{fig:abi-call-wire}} lays one out byte by byte. It repays a minute of study, because every "invalid argument" error you will ever debug is a disagreement about this picture.

{{include-fig:abi-call-wire}}

*What this section repairs in the greeter:* it gives you eyes. {{ex:compile-output}} shows you which assertions carry messages and which silently do not; {{ex:algorand-client}} and {{ex:typed-client}} get the contract onto a network you can hit; and {{ex:typed-call}} shows you the return value that the log budget bounds. Every diagnosis in the rest of this chapter is made with those four.

## The Mini-Build, Fixed
Three decisions, three corrections. The full corrected contract is on disk at `examples/ch01_mental_model/greeter_fixed.py` and compiles in CI; here is the diff that matters.

```diff
-from algopy import ARC4Contract, Global, String, Txn, arc4
+from algopy import ARC4Contract, Global, String, Txn, UInt64, arc4
+
+MAX_NAME_BYTES = 64

     @arc4.abimethod
     def greet(self, name: String) -> String:
-        assert name.bytes.length > 0
+        length = name.bytes.length
+        assert length > UInt64(0), "greet: name must not be empty"
+        assert length <= UInt64(MAX_NAME_BYTES), "greet: name is over 64 bytes"
         return "Hello, " + name

-        assert Txn.sender == Global.current_application_address, "admin only"
+        assert Txn.sender == Global.creator_address, "shut_down: creator only"
```

Compile it and read the spec back with {{ex:compile-output}}. The same script, the same contract, eight lines longer:

```console
$ python -m smart_contracts.compile_output
Greeter: 105 lines of approval TEAL
  greet(string)string
  shut_down()void
  pc 83 -> greet: name is over 64 bytes
  pc 79 -> greet: name must not be empty
  pc 64 -> invalid array length header
  pc 72 -> invalid number of bytes for arc4.dynamic_array<arc4.uint8>
  pc 120 -> shut_down: creator only
```

Five messages instead of three, and every failure a caller can trigger now has a sentence attached to it. That is the whole chapter in one screen of output.

**Correction one: give every assertion a message.** The bound checks now read `"greet: name must not be empty"` and `"greet: name is over 64 bytes"`. Nothing about the on-chain program changed --- the same instruction rejects the same transactions at the same program counter. What changed is that the compiler now has something to write into `sourceInfo`, and the client has something to find there. Prefixing with the method name costs four bytes of a file nobody pays for and saves the reader a grep.

**Correction two: bound what you return.** `MAX_NAME_BYTES = 64` is not an arbitrary tidiness. The return value is a log entry, the log budget is 1,024 bytes per call, and the argument space is 2,048 --- so without a bound, the gap between those two numbers is a denial-of-service surface that any stranger can reach. Sixty-four is far below the real ceiling on purpose: a limit the caller can hold in their head beats a limit derived from a budget they have never heard of.

**Correction three: name the account that actually exists.** `Global.current_application_address` became `Global.creator_address`. The application's address holds the contract's money and has no private key; the creator's address is a real account with a real signer, fixed at creation and unforgeable afterward. One is the contract's wallet, the other is its owner, and the greeter asked the wallet to prove it was the owner.

A word on what the fix does *not* do. `Global.creator_address` is immutable --- lose that key and you lose the ability to shut the application down, permanently. Real contracts usually store an admin address in global state at creation instead, so it can be rotated. {{ch:state}} shows how, and shows why capturing it at creation is the only moment `Txn.sender` and `Global.creator_address` are guaranteed to be the same account.

## What Bites People Here
Four, in the order you are likely to meet them: one about diagnostics, two about identity, and one about the size of what you send back.

::: {.gotcha #assert-without-a-message topic="Compilation, tooling, and shipping" title="An assert with no message produces a program counter and nothing else"}
Assertion messages do not exist on chain. The AVM aborts at a program counter; the compiler stores your message in the ARC-56 app spec under `sourceInfo.approval.sourceInfo[]`, keyed by that counter, and the client SDK maps the number back to the string. An `assert` written without a message contributes no entry at all, so there is nothing to map and your caller sees `assert failed pc=78`. This bites hardest on contracts other teams integrate against, because they may not have your source --- and it bites in production, where you are reading a failed transaction hours after the fact. Give every assertion a message, and ship the app spec alongside the contract.
:::

::: {.gotcha #creator-is-not-the-application topic="Authorization" title="The application address has no private key and can never be a sender"}
`Global.current_application_address` is the account derived from the application ID. It holds the contract's Algo and assets, it is the sender of every inner transaction the contract emits, and *no private key exists for it*. It can therefore never be `Txn.sender` on a top-level call, so a guard of the form `assert Txn.sender == Global.current_application_address` is not merely wrong but unsatisfiable --- and if it guards `DeleteApplication`, the application is undeletable forever. `Global.creator_address` is the account that created the application, is fixed at creation, and is a real signer. Use the creator for authorization, and the application address for balances and inner transactions.
:::

::: {.gotcha #every-abimethod-is-public topic="Authorization" title="There is no private method: every abimethod is a public entry point"}
Nothing about `@arc4.abimethod` makes a method internal, and nothing about naming it `_helper` or omitting it from your client hides it. The router dispatches on a selector computed from the method signature, and anybody who can read your app spec --- or hash a signature they guessed --- can call it. A method is protected only by the assertions inside it. Before you ship, list every `abimethod` and name the check that stops the wrong caller; if a method has no such check, either it is genuinely public or you have a hole.
:::

::: {.gotcha #abi-return-is-a-log-entry topic="Resource references, MBR, and budget" title="An ABI return value is a log entry, and the log budget is smaller than the argument budget"}
The AVM has no return channel. `return` from an `abimethod` compiles to a `log` of the four-byte prefix `0x151f7c75` followed by the ARC-4 encoding of the value. An application call may log **1,024 bytes** in total across at most 32 `log` calls, while it may carry **2,048 bytes** of arguments --- so a method that echoes or expands its input can be made to fail by a caller who does nothing more unusual than sending a large argument. Bound anything variable-length that you return, and bound it well below the ceiling so the number means something to the caller.
:::

## Retrieval
Answer these from memory before moving on. This is the first chapter, so all of them are from this chapter --- from {{ch:state}} onward, some will reach backwards on purpose.

1. A contract is asked a question once and answers yes or no. When, exactly, do its state changes become real?
2. What are the only two AVM value types?
3. What is the base minimum balance of any Algorand account, in microAlgos?
4. Which account pays the minimum balance for a box: the creator, the caller, or the application?
5. Where does the string in `assert x > 0, "x must be positive"` end up, and what reads it back?
6. Name the four accounts a contract routinely talks about, and say which two can sign a transaction.
7. How many bytes may one application call write to its log, and why does that number bound what a method can return?
8. What is a method selector, and what is it computed from?

## Exercises
1. **(Trace)** Walk the broken greeter through this exact sequence and write down what the caller sees after each step: the creator deploys it; Ada calls `greet("Ada")`; Ada calls `greet("")`; a stranger calls `greet` with a 1,100-byte name; the creator calls `shut_down()`; the creator funds the application account with 1 Algo and calls `shut_down()` again. For each of the six, say whether the ledger changed, and state which single one of them is responsible for the 100,000 microAlgos the creator can never recover.

2. **(Parsons)** Below are six statements. Four of them form the body of the fixed greeter's `greet` method; two do not belong in it at all. The decorator and signature are given, so syntax will not do your ordering for you.

   ```python
   @arc4.abimethod
   def greet(self, name: String) -> String:
       ...
   ```

   The statements: (a) `length = name.bytes.length`; (b) `assert length > UInt64(0), "greet: name must not be empty"`; (c) `assert length <= UInt64(MAX_NAME_BYTES), "greet: name is over 64 bytes"`; (d) `return "Hello, " + name`; (e) `assert Txn.sender == Global.creator_address, "greet: creator only"`; (f) `assert name.bytes.length > 0`.

   Select the four that belong and order them. For each of the two you rejected, name the specific thing that goes wrong if you keep it --- one of them would make the method useless for its stated purpose, and the other re-introduces the bug this chapter opened with. Then: two of the four you kept are forced into their positions by dataflow, and two are not. Say which are which, and explain why the ordering the AVM would accept is still not the ordering you should write.

3. **(Debug)** A developer wants an admin-only method and writes `assert Txn.sender == Global.current_application_address, "admin only"`. Their unit test passes. Explain how a unit test can pass against an unsatisfiable guard --- what the test must be doing, and what it is therefore not testing. Then say what the test should assert instead, and name the one deployment scenario in which discovering this bug is unrecoverable rather than merely embarrassing.

4. **(Compare)** You need to let exactly one party shut an application down. Compare three designs: guarding on `Global.creator_address`; storing an admin address in global state at creation and guarding on that; and requiring the caller to hold a specific ASA. Compare them on four axes: whether the authority can be transferred after deployment, what an attacker must compromise to gain it, what it costs in minimum balance, and what happens if the authorized key is lost. One of the three is strictly worse than another on three of the four axes --- identify the pair and say which axis saves it. Then name the requirement that would force each of the other two.

5. **(Extend)** Extend the fixed greeter with a `greet_many` method that takes a `arc4.DynamicArray[arc4.String]` of names and returns all the greetings. You will hit a limit this chapter named but did not solve. Write the method, and then write down: the largest number of 10-byte names it can accept before something fails, which of the two budgets fails first, and what the error message should say so that a caller can act on it without reading your source.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can explain what a contract *is* --- a program asked one question per transaction --- and say what that implies about when its state changes commit.
- [ ] I can name `Txn.sender`, `Global.creator_address`, `Global.current_application_address` and an `Account` argument, say which of them can sign a transaction, and pick the right one for an authorization check.
- [ ] I can compute the minimum balance of an account given its assets, applications and boxes, and say which account is charged for each.
- [ ] I can explain where an assertion message is stored, why it is not on chain, and what a caller sees when I omit it.
- [ ] I can trace a method call from a typed Python client through the selector and argument encoding to the log entry that carries the return value back.

## Handoff: What the Vesting Project Needs
{{ch:token-vesting}} builds a real token vesting contract, and it assumes every one of these on its first page. {{tbl:mental-model-handoff}} lists the examples from this chapter that it leans on, and what to predict before you read it.

Table: Examples from this chapter that the vesting project depends on {#tbl:mental-model-handoff}

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| {{ex:smallest-contract}} | The vesting contract's class declaration and first method | What does subclassing `ARC4Contract` generate that you would otherwise write by hand? |
| {{ex:reference-types}} | The beneficiary `Account` and the vested `Asset`, passed as method arguments | The contract receives an `Account`. What does it actually receive, and what must the transaction declare? |
| {{ex:assert-message}} | Every guard in the contract: admin checks, cliff checks, amount checks | A beneficiary claims before the cliff. What should the failure tell them, and where will that sentence be stored? |
| {{ex:without-arc4contract}} | The `OnComplete` handling that rejects updates and deletes | Which of the six OnCompletes must a contract holding other people's tokens refuse, and why? |
| {{ex:typed-call}} | Every deployment and interaction script in the chapter | The contract returns a claimed amount. By what mechanism does that number get back to your Python? |
