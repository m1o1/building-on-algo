\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# The Algorand Mental Model

Chapter 1 left you with a running toolchain, a deployed application, and no account of what that application actually *is*. This chapter pays that debt, and it pays it the expensive way: you will build a contract of your own from an empty file, watch it fail three different ways, and use the failures to assemble a working model of the machine underneath.

Algorand is a *proof-of-stake* blockchain with *instant finality*, a block time of roughly two and three-quarter seconds, and no forking. Every confirmed transaction is final: there is no "wait for six confirmations." Block proposers and committee voters are selected secretly by a *Verifiable Random Function*, so there is nobody to attack before they reveal themselves. None of that is what makes writing a contract feel strange the first time. The thing that does is smaller and closer to your keyboard: a contract is not a program that runs. It is a *transaction validator* --- asked once per call whether to approve or reject, and then it stops.

## Execution Model: Smart Contracts Are Transaction Validators
Algorand smart contracts do not run continuously. They are not servers. They are not daemons. They execute once per transaction, validate whether the transaction should be approved or rejected, and then stop.

When a user submits a transaction that calls your smart contract, the *Algorand Virtual Machine (AVM)* loads your contract's bytecode, runs it against the transaction data, and produces a boolean result. If the program returns true, the transaction is approved and its effects are committed atomically. If it returns false or fails at any point, the entire transaction is rejected as if it never happened --- with one exception you will meet in Chapter 4: a ClearState call opts the account out regardless of what the clear program returns.

This means your contract code is a set of validation rules. State changes happen as side effects of successful validation. On Algorand, the transaction *is* the input, and your contract decides whether to accept it. The developer portal's [Smart Contracts Overview](https://dev.algorand.co/concepts/smart-contracts/overview/) states the same model in the portal's own words.

The bytecode the AVM runs is *TEAL* --- Transaction Execution Approval Language. You will never write TEAL directly: PuyaPy compiles your Python to it automatically. The name is worth knowing because it is the one Algorand documentation uses, and because it names the job.

Everything else follows from that one idea.

## Getting a Contract onto the Chain, and Off It Again
An application has three jobs before it has a single feature. It has to exist on the chain, so there is something to call. It has to answer callers who have never seen your source, including when the answer is no. And it has to stay something you can pull, because the version you deploy on a Tuesday is not the version you want running a year later.

Algorand does all three in a handful of lines. `algokit project deploy` puts the compiled program into the ledger and hands back an application ID; behind that ID is code that has never run and will not run until somebody calls it. Any account may call it. And one of the six actions a call can request is `DeleteApplication`, which removes the program and releases the minimum balance that creating it cost.

The second and third jobs have edges the first does not, and both edges are about the same two things: what the machine reports when it says no, and whom it believes when code names an account. The commission below walks straight into both.

Figure 2-1 is the whole machine in one picture: everything a contract is allowed to look at, everything it is allowed to stage, and the single approve-or-reject decision that stands between the two. Every limit in this chapter is somewhere in that diagram.

![Figure 2-1. What the AVM lets a contract see and what it lets a contract do. Everything in the lower band is staged rather than applied; nothing lands until the branch at the foot approves.](figures/notional-machine.svg)

::: {.spec title="Your commission: a greeter with an off switch"}
The contract you build this chapter is small enough to hold in your head and public enough to be dangerous. It must:

1. Greet anyone who asks, by name
2. Refuse an empty name --- with an error the caller can actually read
3. Accept any reasonable name, and refuse oversized ones by naming the limit
4. Let the people who deployed it --- and only them --- shut it down

Four requirements, two methods. At the end of the chapter you will re-run the finished contract against this list.
:::

By the end of this chapter you will be able to:

- Explain that a contract is a transaction validator, not a running process, and say precisely when its state changes become real
- Write a complete, deployable contract from an empty file, and read the TEAL it compiles into well enough to recognize the parts
- Name the four accounts a contract can talk about --- sender, creator, application, and an arbitrary referenced account --- and say which of them can sign a transaction
- Attach a diagnostic message to a failing assertion and then find that message again from a client, knowing where it was stored
- Compute the minimum balance of an account holding assets, applications, and boxes, and say which account pays it
- Compile a contract, generate a typed client from its app spec, and call a method with real Python types
- Predict which of your contract's assumptions a stranger can violate, given that every method is a public entry point

## Building the Greeter
Here is that commission, as anyone coming from Python would first write it --- complete, and in full.

**Example 2-1.** The greeter, as first written

<!-- finder: see the smallest useful contract that has an admin method -->

```python
from algopy import ARC4Contract, Global, String, Txn, arc4


class Greeter(ARC4Contract):
    """Greet anyone who asks. Let the people who deployed it shut it down."""

    @arc4.abimethod
    def greet(self, name: String) -> String:
        assert name.bytes.length > 0
        return "Hello, " + name

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def shut_down(self) -> None:
        assert Txn.sender == Global.current_application_address, "admin only"
```

Example 2-1 is complete and deployable. It compiles, it runs on LocalNet, and it contains three decisions that are wrong. Two of them will fail with a transcript in a moment; the third sits in plain sight and stays invisible until a stranger goes looking for it.

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
>>> greeter.send.delete.shut_down()
LogicError: Txn W2LD...R7B had error 'Runtime error when executing Greeter
(appId: 1042) in transaction 0: admin only'
at PC 115 and Source Line 92:
    ... 10 lines of TEAL trace ...
```

Three failures, in three different ways. The first is correct behavior reported uselessly: the contract meant to reject an empty name, and the only thing it can tell you is a number --- Chapter 1's first habit applies, and reading past the traceback's last line is exactly how you learned that the machine refused *on purpose*, at a specific place; what the habit cannot recover is *why*, and that gap is this chapter's business. The second is a limit the contract never mentions and never checked, and the number in it, 1,113, is larger than the name you sent. The third is a correct-looking guard that no caller on Earth can satisfy; the message is readable, which makes it worse, because it confidently describes a rule that cannot ever be met.

::: {.note title="How this book quotes a failure"}
Every `LogicError` in this book is shown the way those three are: the message's first line, wrapped where it is too long for the page, then the ten lines of *generated TEAL* the real exception prints around the failure, cut under the marker --- always spelled `... 10 lines of TEAL trace ...`. The `Source Line` is a line of that TEAL, counted from zero, not of your Python; a client that compiled the contract holds the map from program counters to TEAL lines, and nothing makes the next hop back to the file you wrote (Chapter 8 closes that gap). Two more rules hold book-wide: an inline `...` shortens one value while keeping enough to identify it, as in `6ZQK...H2A` above, and nothing is cut from inside a quoted error without a mark at the cut. What a transcript never reproduces is the wrapper: Python traceback frames above the exception line, and the `transaction {id}: logic eval error:` prefix that `LogicError` strips.
:::

Now ship Example 2-1 anyway, and watch what those three failures cost once other people depend on the contract. The empty-name rejection is *correct behavior*, but the first stranger it refuses gets `assert failed pc=78` and nothing else; you have the source open and can guess, but the developer integrating from another company cannot, and that support thread runs three days. The unsatisfiable guard is worse, because you meet it at the worst possible moment: you decide to pull the contract and redeploy it with better errors, call `shut_down` from the deployer account --- rejected --- then the admin account, then every account you control. Rejected, all of them. The application is now permanently deployed, permanently broken, and permanently undeletable, and the 100,000 microAlgos of minimum balance its creation locked in your account will never come back. Why no account on Earth can pass that guard is taught where the four accounts are, later in this chapter; the bill arrives now either way.

Nothing in that contract is a typo. It compiles, it deploys, every line does exactly what it says. The mistake is upstream of the code: a belief about who is who on this chain, and about what a contract is allowed to assume. The rest of this chapter replaces that belief with the actual machine, one piece at a time, and each piece is the diagnosis of a failure you have now watched happen.

## A Program That Only Says No
Start with the smallest contract that is still a real one.

**Example 2-2.** The smallest deployable contract

<!-- finder: write the smallest complete Algorand contract that actually does something -->

```python
from algopy import ARC4Contract, String, arc4


class Smallest(ARC4Contract):
    """One method, one answer, no memory. This is a whole application."""

    @arc4.abimethod
    def ping(self) -> String:
        return String("pong")
```

The key line is `class Smallest(ARC4Contract)`. Inheriting from `ARC4Contract` is what turns a Python class into an application: it generates the *router*, the dispatch code that reads the first application argument, matches it against the method selectors of every `@arc4.abimethod`, and rejects anything it does not recognize. The [ARC-4](https://dev.algorand.co/arc-standards/arc-0004) calling convention is the standard every Algorand tool assumes, and you get it by subclassing.

There is no `main`, no server, no loop. When somebody calls `ping()`, this program runs from the top, returns, and stops. When nobody is calling it, it is not running at all. It is bytes in the ledger.

**Example 2-3.** An assertion that says why

<!-- finder: attach a readable error message to a failing check -->

```python
from algopy import ARC4Contract, Global, Txn, UInt64, arc4


class Doubler(ARC4Contract):
    @arc4.abimethod
    def double(self, amount: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "double: creator only"
        assert amount > UInt64(0), "double: amount must be positive"
        assert amount < UInt64(2**63), "double: amount would overflow"
        return amount * UInt64(2)
```

The part that matters is the string after each comma. `assert amount > UInt64(0)` and `assert amount > UInt64(0), "double: amount must be positive"` compile to the same on-chain behavior (the transaction is rejected either way), but only the second one leaves the compiler anything to record.

The message is **not on chain**. The AVM has no notion of an error string; a failing `assert` aborts the program at a program counter and that is all the network reports. The compiler puts your message in the ARC-56 app spec instead, keyed by that program counter, and the client SDK maps the number back to the string when it builds the exception. Write an assertion without a message, and there is nothing to ship. You will see that absence in "From a Python File to a Call You Can Make" later in this chapter, when you print the greeter's app spec and count the entries.

The person who most needs the message is not you. It is the integrator calling your contract from a codebase you will never see, whose only view of your failure is whatever the SDK can reconstruct.

This is the greeter's first failure. `assert name.bytes.length > 0` carries no message, so the compiler had nothing to record and the caller got `assert failed pc=78` and nothing else.

::: {.gotcha #assert-without-a-message topic="Compilation, tooling, and shipping" title="An assert with no message produces a program counter and nothing else"}
Assertion messages do not exist on chain. The AVM aborts at a program counter; the compiler stores your message in the ARC-56 app spec under `sourceInfo.approval.sourceInfo[]`, keyed by that counter, and the client SDK maps the number back to the string. An `assert` written without a message contributes no entry at all, so there is nothing to map and your caller sees `assert failed pc=78`. This bites hardest on contracts other teams integrate against, because they may not have your source, and it bites in production, where you are reading a failed transaction hours after the fact. Give every assertion a message, and ship the app spec alongside the contract.
:::

## Four Accounts, and Only Two of Them Can Sign
A contract can name four different accounts, and telling them apart is not a naming convention. It is the difference between a working guard and an unsatisfiable one.

**Example 2-4.** The three reference types

<!-- finder: ask the ledger a question about an account, an asset, or another app -->

```python
from algopy import ARC4Contract, Account, Application, Asset, UInt64, arc4


class Introspect(ARC4Contract):
    """Three reference types, three questions only the ledger can answer."""

    @arc4.abimethod(readonly=True)
    def units_held(self, who: Account, token: Asset) -> UInt64:
        assert who.is_opted_in(token), "account has not opted into this asset"
        return token.balance(who)

    @arc4.abimethod(readonly=True)
    def treasury_of(self, other: Application) -> arc4.Address:
        return arc4.Address(other.address)
```

`Account`, `Asset`, and `Application` are not data you receive. They are *handles you are given permission to look up*. An `Account` argument does not carry a balance across the wire; it carries 32 bytes, and `token.balance(who)` reaches into the ledger to answer. That is why these three types have methods at all, and why the transaction must declare them (a topic that becomes urgent in Chapter 9).

Four accounts matter in almost every contract you will write. `Txn.sender` is whoever signed this call. `Global.creator_address` is the account that created the application, fixed forever at creation. `Global.current_application_address` is the application's *own* account, derived from the app ID, which holds the contract's Algo and assets. And an `Account` argument is an arbitrary third party the caller named. Only two of those four can ever sign a transaction.

Here is what happens when you pick the wrong one --- a variation of Example 2-1, its `shut_down` isolated into a contract of its own:

```python
from algopy import ARC4Contract, Global, Txn, arc4


class GatedWrong(ARC4Contract):
    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def shut_down(self) -> None:
        # Compiles. Deploys. Can never pass: nobody holds the key to an
        # application's own account, and the AVM refuses to let an
        # application call itself.
        assert Txn.sender == Global.current_application_address, "admin only"
```

This is the greeter's third failure, isolated. Every deployed smart contract has a deterministic address derived from its application ID: `SHA512_256("appID" || big_endian_8_byte(app_id))`, where `"appID"` is a literal ASCII domain separator and `||` is concatenation. That derivation is completely unlike the Ed25519 key generation that produces wallet addresses, which is exactly the point: application addresses can never collide with user accounts, and *no private key exists* for one. The contract's code is the sole custodian of everything that address holds. An address with no key is an address that cannot sign, and an account that cannot sign can never be `Txn.sender`.

*Predict: is there any transaction --- any group, any inner transaction, any sequence at all --- whose `Txn.sender` is an application address? Answer before reading the next paragraph.*

Not for this contract. No key exists for an application address, so no *top-level* transaction can carry one as its sender; and an application can never appear twice in its own call stack, so no inner call can hand a contract its own address either. A *different* application's address can be a sender: when app A submits an inner application call to app B, the program B runs sees A's application address in `Txn.sender` --- a fact Chapter 15 builds an entire architecture on. None of that helps the greeter. A guard comparing `Txn.sender` to the contract's *own* address is unsatisfiable in every configuration.

`shut_down` guards against the application's own address, which no sender can ever be. It meant `Global.creator_address`.

::: {.gotcha #creator-is-not-the-application topic="Authorization" title="The application address has no private key and can never be a sender"}
`Global.current_application_address` is the account derived from the application ID. It holds the contract's Algo and assets, it is the sender of every inner transaction the contract emits, and *no private key exists for it*. It can therefore never be `Txn.sender` on a top-level call, so a guard of the form `assert Txn.sender == Global.current_application_address` is not merely wrong but unsatisfiable; if it guards `DeleteApplication`, the application is undeletable forever. `Global.creator_address` is the account that created the application, is fixed at creation, and is a real signer. Use the creator for authorization, and the application address for balances and inner transactions.
:::

## What ARC4Contract Writes for You
*Predict, in three bullets, what `ARC4Contract` must be generating for you --- three things Example 2-2 never wrote and could not work without. This section is the check.*

Which of the two programs in a contract runs, and what the network does afterward, is decided by a field on the transaction called its *OnComplete*. `shut_down` in Example 2-1 declares `allow_actions=["DeleteApplication"]`, which is one of six. Figure 2-2 shows all six as the lifecycle they describe. ClearState is the one transition your contract has no power to refuse, and Chapter 4 is largely about the consequences.

![Figure 2-2. The six OnCompletes, as the lifecycle they actually describe. ClearState is the one transition a contract cannot refuse.](figures/oncompletes.svg)

Every contract has two programs. The **approval program** handles creation, method calls, opt-ins, close-outs, updates and deletes: all your business logic. The **clear state program** runs only when a user forcibly detaches from your application, and the protocol guarantees their local state is deleted whether it approves or not.

Here is the router written out by hand:

**Example 2-5.** The same contract without `ARC4Contract`

<!-- finder: understand what ARC4Contract generates for me -->

```python
from algopy import Bytes, Contract, OnCompleteAction, Txn, UInt64, log

# sha512_256("ping()string")[:4], then ARC-4's return-value log prefix and the
# encoded return value: two length bytes, then "pong".
PING = b"\xb1\x32\xc0\x56"
RETURN = b"\x15\x1f\x7c\x75\x00\x04pong"


class SmallestByHand(Contract):
    """The same application as `Smallest`, with the router written out."""

    def approval_program(self) -> bool:
        is_create = Txn.application_id.id == UInt64(0)
        if Txn.num_app_args == UInt64(0):
            return is_create and Txn.on_completion == OnCompleteAction.NoOp
        assert Txn.application_args(0) == Bytes(PING), "unknown method"
        assert Txn.on_completion == OnCompleteAction.NoOp, "unsupported action"
        log(Bytes(RETURN))
        return True

    def clear_state_program(self) -> bool:
        return True
```

The line that matters is `assert Txn.application_args(0) == Bytes(PING)`. A method selector is not a name lookup. It is the first four bytes of `SHA-512/256("ping()string")`, compared as bytes. `arc4.abimethod` computes that constant for you and emits the comparison; here you type both yourself.

::: {.gotcha #every-abimethod-is-public topic="Authorization" title="There is no private method: every abimethod is a public entry point"}
Nothing about `@arc4.abimethod` makes a method internal, and nothing about naming it `_helper` or omitting it from your client hides it. The router dispatches on a selector computed from the method signature, and anybody who can read your app spec --- or hash a signature they guessed --- can call it. A method is protected only by the assertions inside it. Before you ship, list every `abimethod` and name the check that stops the wrong caller; if a method has no such check, either it is genuinely public or you have a hole.
:::

Compile both and the shape is the same, though the hand-written one is looser: it checks the OnComplete but never checks that the application already exists, so it would accept a `ping` call that also created the application. The generated router checks both, in one expression. Compiled, `Smallest`'s router reads like this, with the compiler's source-line comments removed:

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

In the constant `0x151f7c750004706f6e67`, the first four bytes are ARC-4's return-value prefix, which is how a caller tells "this log line is my return value" from "this log line is a debug message." Then `0004`, the length of a four-byte string. Then `pong`. **An ABI return value is a log entry.** The AVM has no return channel; returning a value means writing bytes to the transaction's log and agreeing on a convention for reading them back. That is the greeter's second failure.

`main___algopy_default_create@5` is the bare-create path: a call with no arguments is accepted only if it is a creation with OnComplete NoOp. The clear state program is the second half of the pair. `Smallest` never writes one, so `ARC4Contract` generates `pushint 1 / return`, approving unconditionally, since refusing changes nothing. Example 2-5 has no `ARC4Contract` to generate it, so it has to write that same two-line program itself; that is the one piece of the pair the router does not cover.

The ABI return value is a log entry, the log is a budget, and the greeter never bounded what it returns. Example 2-6 shows the exact byte count.

## Who Owns What: Accounts, Balances, and the Application's Address
Algorand tracks balances per account, the way a bank ledger tracks yours in a single row that moves up and down. (This is an *account-based model*. Bitcoin uses the alternative, *UTXO*, which tracks individual coins that are created and consumed; you will not need it here.) Accounts are 32-byte public keys written as 58-character base32 strings, and each one holds Algos plus whatever Algorand Standard Assets it has opted into.

Every account must keep a *minimum balance* to exist at all. This is the anti-spam mechanism: without it, an attacker could create billions of empty accounts and bloat every node's ledger. The base is **100,000 microAlgos (0.1 Algo)**, and every resource an account holds raises it:

- Each ASA opted into: +100,000 microAlgos
- Each application created: +100,000 microAlgos, plus the declared state schema
- Each application opted into: +100,000 microAlgos, plus the local schema
- Each declared global slot: +28,500 for a `uint64`, +50,000 for a byte slot
- Each box created: +2,500, plus 400 × (name bytes + value bytes)

Minimum balance is not a fee. Nothing is deducted. The floor simply rises, and only the Algo above the floor is spendable. A transaction that would push an account below its floor fails with `account <address> balance <n> below min <m> (<k> assets)`, the error new developers meet most often. Figure 2-3 draws it to scale for a contract account holding two assets and one box: the balance an explorer reports, and the sliver of it the contract can actually move.

![Figure 2-3. A pool contract's account funded with one Algo, drawn to scale. Just over half of it is spendable; the rest is locked by the account's own minimum balance requirement.](figures/mbr-slab.svg)

**Worked example.** A vesting contract opts into 2 ASAs and stores schedules for 10 beneficiaries in boxes, each with a 10-byte name and a 40-byte value. The application account's minimum balance is 100,000 (base) + 2 × 100,000 (opt-ins) + 10 × (2,500 + 400 × 50) (boxes) = 525,000 microAlgos, about 0.53 Algo. Fund it before creating the boxes or the transactions fail.

Two facts about *who* pays are asymmetric, and people get them backwards. Box minimum balance is charged to the **application account**, which is why contracts that create boxes must be funded. Global and local schema minimum balance is charged to a **user**: the creator for global, the opting-in account for local. A generous local schema you never fill is a tax you levy on every one of your users.

The opt-in requirement is the other half of the same idea. On some chains anyone can push tokens into your wallet; on Algorand you must explicitly *opt in* to each ASA first, at a cost of 0.1 Algo in minimum balance. Your contract must opt into every asset it will hold, and users must opt into anything you send them.

Contracts persist data in three places, each with a different owner: **global state** (a fixed schema of up to 64 key/value pairs belonging to the application), **local state** (up to 16 pairs per opted-in account, which that account can delete unilaterally), and **box storage** (independently created keys of up to 32,768 bytes that only the application can remove). Which one you choose is an architectural decision with money attached, and it gets two chapters of its own: Chapter 4 for the two schema-bound slabs, Chapter 5 for the unbounded third. Anything the contract *owes* somebody must not live anywhere that somebody can erase.

None of this changes the greeter's code, but it explains the story's ending. The 100,000 microAlgos locked in the creator's minimum balance are locked because the application still exists, and it still exists because `shut_down` names an address with no key.

## All or Nothing
A rejected transaction does not partially happen. This is the property that makes an `assert` worth writing.

Start with the shortest lifecycle you will ever meet. You sign a transaction and submit it to a node. That node evaluates it right away --- signatures, minimum balances, well-formedness, and, for an application call, your approval program --- and gossips it onward only if it passes. This is where the `LogicError` in the preceding transcripts comes from: it arrives in milliseconds, from your own node, before any block exists. A block proposer selected by the Verifiable Random Function then includes the transaction in a block, and every node validating that block runs your approval program again. The program is deterministic, so they all reach the same verdict; what makes the block run special is that it is the only one whose effects are recorded. Approve, and the transaction's effects (balance changes, state writes, boxes created) are applied as the block is written. Reject, and nothing is applied and the transaction is not in the block at all.

Inside the block, your program sees the ledger as it stands at that instant, not a snapshot taken beforehand. A payment earlier in your group has already moved the money by the time the application call after it runs, and a state write by an earlier call is visible to a later one. That is what makes atomic groups useful rather than merely tidy.

Then the part that is genuinely different from other chains: **the block is final when it is written.** Under three seconds after you submitted, with no confirmations to wait for, no reorganization that can undo it, and no probabilistic settlement. There is exactly one moment when your state changes become real, and it is the moment the block containing them is agreed. Everything before that moment is a proposal; everything after it is history. This is why an Algorand contract has no notion of a pending write, no callback for "later," and no need for the confirmation-counting machinery you may be carrying in from elsewhere.

Algorand has seven developer-facing [transaction types](https://dev.algorand.co/concepts/transactions/types/): payment, asset transfer, asset configuration, asset freeze, application call, key registration, and state proof. (An eighth, heartbeat, is internal to consensus.) For contract work you will mostly see the first, the second, and the fifth.

Up to 16 of them can be submitted as an [atomic group](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/). Every transaction in the group succeeds or every one fails; there is no partial execution, and no rollback either, because nothing was ever applied. Groups are assembled *off-chain*: the client builds all the transactions, computes a group ID from their individual hashes with the group field zeroed, stamps it on each one, and submits the bundle. This is the foundation of Algorand DeFi: a user can bundle "send tokens to the pool" and "call swap" and know they cannot lose one without the other.

Figure 2-4 runs the same three transactions twice: once where all three pass, and once where the third is rejected. In the failing run the first two are not undone. They were never applied.

![Figure 2-4. The same three transactions, twice. One rejection anywhere in a group discards every transaction in it — there is no partial application.](figures/atomic-group.svg)

The minimum [fee](https://dev.algorand.co/concepts/transactions/fees/) is **1,000 microAlgos** per ordinary transaction *today* --- a consensus parameter, not a constant to bake into a client. Fees are validated across the group rather than per transaction: the sum of all fees must cover the group's required total, which means one transaction can overpay to cover others. That is *fee pooling*, and you will use it constantly, because a contract that sends money pays for that send out of the group's fee budget. Signature type and size can raise what a group owes; Chapter 8 shows how a client asks `simulate` for the number to attach.

Contracts can also emit [inner transactions](https://dev.algorand.co/concepts/smart-contracts/inner-txn/): transactions created *on-chain*, by contract logic, during execution. When your contract needs to pay someone or transfer an asset, this is how. Inner transactions are atomic with the outer call (if the call fails, they never happened), and the budget for them is pooled across the whole group: 256 inner transactions shared by every application call in it, which one call may spend by itself. The distinction from atomic groups matters: a group is a client-side bundle of transactions the user signed, an inner transaction is one the *contract* authorized with its own address. Chapter 9 uses them from its first payout onward.

It also explains why the greeter's bugs are survivable. Every failed `greet` call in the story left the ledger exactly as it found it. The only permanent damage was done by the call that *succeeded*: the creation.

## The Edges of the Machine
Knowing what the AVM refuses to do matters as much as knowing what it does, because most first designs assume at least one thing on this list. Every number below is a boundary drawn somewhere in Figure 2-1; the full table is in Appendix B.

- **No floating point.** There are two types: `uint64` and `bytes`. Prices are rationals, held as a numerator and a denominator, and rounded deliberately. Chapter 9 does this for real.
- **No unbounded loops.** Each instruction costs from an *opcode budget* of 700 per application call; most cost 1, cryptographic operations cost far more. The budget pools across the application calls in a group, so four app calls share 2,800, and padding a group with no-op calls to buy budget is a real technique (Chapter 11). LogicSig programs get a separate 20,000 per transaction (pooled; Chapter 20). You cannot iterate over an arbitrarily large data set in one call.
- **A hard log budget.** An application call may write **1,024 bytes** to its log, across at most 32 `log` calls. Since an ABI return value *is* a log entry, this is a ceiling on what your methods can return, and it is not the same ceiling as the 2,048 bytes a call may carry in its *arguments*. A caller can therefore hand you more data than you are able to hand back.
- **No callbacks.** When your contract sends tokens by inner transaction, no code runs on the receiving side. Classical reentrancy does not exist here, which means you should not write defenses against it (Chapter 7 explains what to write instead).
- **Constrained app-to-app interaction.** A contract can submit an inner application call, but that is transaction coordination, not a call stack with an arbitrary synchronous return. Your contract can *read* another application's global state; it cannot write it.
- **No private on-chain data.** Global state, local state and boxes are all readable off-chain through algod and the indexer. Boxes are private to the AVM --- only the owning application can read them in TEAL --- and completely public over REST.
- **No upgradeability unless you allow it.** Reject `UpdateApplication` and the code is immutable. For anything holding value, that is the right default.

The greeter's second failure now has its arithmetic. `greet` returns `"Hello, " + name` with no bound on `name`. A name of 1,100 bytes fits comfortably in the 2,048 bytes of argument space; what gets logged is the 4-byte ARC-4 return prefix, a 2-byte length header, the 7 bytes of `"Hello, "`, and the name itself: 1,113 bytes against a 1,024-byte ceiling. That is the number in the failure transcript. Any stranger can make the method fail, from outside, with a well-formed call, and the contract never mentions the limit it is breaking.

::: {.gotcha #abi-return-is-a-log-entry topic="Resource references, MBR, and budget" title="An ABI return value is a log entry, and the log budget is smaller than the argument budget"}
The AVM has no return channel. `return` from an `abimethod` compiles to a `log` of the four-byte prefix `0x151f7c75` followed by the ARC-4 encoding of the value. An application call may log **1,024 bytes** in total across at most 32 `log` calls, while it may carry **2,048 bytes** of arguments, so a method that echoes or expands its input can be made to fail by a caller who does nothing more unusual than sending a large argument. Bound anything variable-length that you return, and bound it well below the ceiling so the number means something to the caller.
:::

## From a Python File to a Call You Can Make
You have a contract. Turning it into something you can call takes four steps, and each one is a small program you can read.

The toolchain that runs them --- AlgoKit installed, LocalNet running, one contract already deployed --- is Chapter 1, and from here on it is assumed. If you skipped it, go run it now; nothing below works from a cold machine.

**Example 2-6.** What the compiler writes to disk

<!-- finder: see what algokit project run build actually produced -->

```python
"""Read back what `algokit project run build` left on disk."""

import base64
import json
from pathlib import Path

SPEC = Path("smart_contracts/artifacts/greeter/Greeter.arc56.json")


def main() -> None:
    spec = json.loads(SPEC.read_text())
    teal = base64.b64decode(spec["source"]["approval"]).decode()
    print(f"{spec['name']}: {len(teal.splitlines())} lines of approval TEAL")
    for method in spec["methods"]:
        args = ",".join(arg["type"] for arg in method["args"])
        print(f"  {method['name']}({args}){method['returns']['type']}")
    for entry in spec["sourceInfo"]["approval"]["sourceInfo"]:
        if "errorMessage" in entry:
            print(f"  pc {entry['pc'][0]} -> {entry['errorMessage']}")


if __name__ == "__main__":
    main()
```

The loop over `spec["sourceInfo"]["approval"]["sourceInfo"]` is where assertion messages live, keyed by program counter, exactly as Example 2-3 claimed. Run it against the broken greeter:

```console
$ python -m smart_contracts.compile_output
Greeter: 97 lines of approval TEAL
  greet(string)string
  shut_down()void
  pc 115 -> admin only
  pc 64 -> invalid array length header
  pc 72 -> invalid number of bytes for arc4.dynamic_array<arc4.uint8>
```

Three messages, and one of your own is missing. You wrote two assertions in this contract: the empty-name check and the admin guard. Only the admin guard appears, at pc 115. The other two entries --- `invalid array length header` and `invalid number of bytes` --- are ARC-4 decoding checks the compiler inserted on your behalf to validate the incoming `String` before your code ever runs. Your messageless `assert name.bytes.length > 0` is simply not there. `pc 78` is absent from the spec, which is why the client had nothing to print but the number. A messageless assertion does not produce an empty entry; it produces no entry at all.

The `.arc56.json` file this reads is the *ARC-56 app spec*, the portable description of your contract's public API: method signatures, argument and return types, state schema, and this source map. Think of it as an OpenAPI document for a contract. It is what you publish so that other people can build against you.

**Example 2-7.** Pointing at a network with a funded account

<!-- finder: connect to a network and get an account that can pay for things -->

```python
"""Point at a network, and get an account that can pay for things."""

from algokit_utils import AlgoAmount, AlgorandClient


def main() -> str:
    algorand = AlgorandClient.from_environment()
    deployer = algorand.account.from_environment("DEPLOYER")
    algorand.account.ensure_funded_from_environment(
        account_to_fund=deployer.address,
        min_spending_balance=AlgoAmount.from_algo(10),
    )
    info = algorand.account.get_information(deployer.address)
    print(f"{deployer.address}\n  holds {info.amount}, {info.min_balance} locked")
    return deployer.address


if __name__ == "__main__":
    main()
```

The line to watch is `AlgorandClient.from_environment()`. It reads algod and indexer settings from the environment rather than from your code, so the same script runs against LocalNet, TestNet and MainNet with no edit. `ensure_funded_from_environment` then tops the account up, and it is the one line that is *not* portable. It uses `DISPENSER_MNEMONIC` from the environment if you have set one, and otherwise falls back to asking KMD for the LocalNet dispenser, which only exists on LocalNet. Off LocalNet with no mnemonic it fails looking for a dispenser that is not there. Treat it as a development convenience, not a line you leave in a deployment script.

`info.min_balance` in the output is the floor from "Who Owns What: Accounts, Balances, and the Application's Address" earlier in this chapter, reported by the ledger.

**Example 2-8.** Creating the app through a generated client

<!-- finder: deploy a contract using the typed client algokit generated -->

```python
"""Create the greeter through the client `algokit generate client` wrote."""

from algokit_utils import AlgorandClient

from smart_contracts.artifacts.greeter.greeter_client import GreeterFactory


def main() -> int:
    algorand = AlgorandClient.from_environment()
    deployer = algorand.account.from_environment("DEPLOYER")
    factory = algorand.client.get_typed_app_factory(
        GreeterFactory, default_sender=deployer.address
    )
    client, _result = factory.send.create.bare()
    print(f"greeter {client.app_id} lives at {client.app_address}")
    return client.app_id


if __name__ == "__main__":
    main()
```

The key line is `factory.send.create.bare()`. `algokit generate client` reads the app spec and writes a Python class with real methods on it; `get_typed_app_factory` hands you the factory half of that class, which knows the compiled bytecode and can create the application. `bare` means a creation call with no ABI method behind it: the `main___algopy_default_create` path you read in the generated TEAL earlier in this chapter.

**Example 2-9.** Calling a method with real types

<!-- finder: call a contract method and read the value it returned -->

```python
"""Call a method through the typed client and read back what it returned."""

import sys

from algokit_utils import AlgorandClient

from smart_contracts.artifacts.greeter.greeter_client import GreeterClient


def main(app_id: int) -> str:
    algorand = AlgorandClient.from_environment()
    caller = algorand.account.from_environment("DEPLOYER")
    greeter = algorand.client.get_typed_app_client_by_id(
        GreeterClient, app_id=app_id, default_sender=caller.address
    )
    result = greeter.send.greet(args=("Ada",))
    print(f"{result.tx_ids[0][:8]} returned {result.abi_return!r}")
    return str(result.abi_return)


if __name__ == "__main__":
    main(int(sys.argv[1]))
```

The line that matters is `greeter.send.greet(args=("Ada",))`. Not a string method name, not an untyped argument list, but an actual method, checked by your type checker before you run it. The alternative is the *generic* client --- `method="greet"` as a string, typos found at runtime --- which this book uses only where no generated client exists; Appendix A shows it for connecting to a contract you did not build.

`result.abi_return` is the log entry from earlier, decoded: the SDK strips the `0x151f7c75` prefix and reads the remaining bytes as the return type in the app spec.

Underneath both clients, an ABI call is just an application call with a particular byte layout in its argument array. Figure 2-5 lays one out byte by byte. Every "invalid argument" error you will ever debug is a disagreement about this picture.

![Figure 2-5. An ABI call on the wire, byte by byte. Client and contract must agree on every boundary drawn here, from `args[0]` onward, which is why a decoding failure is usually about a value's width rather than the value.](figures/abi-call-wire.svg)

For the greeter, these four examples are the diagnosis kit. Example 2-6 shows which assertions carry messages and which silently do not; Example 2-7 and Example 2-8 get the contract onto a network you can hit; and Example 2-9 shows the return value that the log budget bounds.

## Completing the Greeter
Three decisions, three corrections. Here is the diff that matters; the whole corrected contract follows as Example 2-10.

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

**Example 2-10.** The greeter, corrected

<!-- example: examples/mental_model/greeter_fixed.py mode=compile -->
<!-- finder: see the greeter with all three defects fixed -->

```python
"""The greeter with its three corrections applied (Chapter 2).

Corrections against the first pass: every assertion carries a message, the
returned greeting is bounded below the log budget, and the shutdown guard
names an account that exists and can sign.
"""

from algopy import ARC4Contract, Global, String, Txn, UInt64, arc4

MAX_NAME_BYTES = 64


class Greeter(ARC4Contract):
    """Greet anyone who asks. Let the people who deployed it shut it down."""

    @arc4.abimethod
    def greet(self, name: String) -> String:
        length = name.bytes.length
        assert length > UInt64(0), "greet: name must not be empty"
        assert length <= UInt64(MAX_NAME_BYTES), "greet: name is over 64 bytes"
        return "Hello, " + name

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def shut_down(self) -> None:
        assert Txn.sender == Global.creator_address, "shut_down: creator only"
```

Compile it and read the spec back with Example 2-6. *Predict first: the broken spec carried three entries, only one of them yours. How many will the corrected spec carry, and how many of those are yours?* The same script, the same contract, eight lines longer:

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

Five messages instead of three, and every failure a caller can trigger now has a sentence attached to it.

**Correction one: give every assertion a message.** The bound checks now read `"greet: name must not be empty"` and `"greet: name is over 64 bytes"`. Nothing about the on-chain program changed: the same instruction rejects the same transactions at the same program counter. What changed is that the compiler now has something to write into `sourceInfo`, and the client has something to find there. Prefixing with the method name costs four bytes of a file nobody pays for and saves the reader a grep.

**Correction two: bound what you return.** `MAX_NAME_BYTES = 64` is not an arbitrary tidiness. The return value is a log entry, the log budget is 1,024 bytes per call, and the argument space is 2,048, so without a bound the gap between those two numbers is a denial-of-service surface that any stranger can reach. Sixty-four is far below the real ceiling on purpose: a limit the caller can hold in their head beats a limit derived from a budget they have never heard of.

**Correction three: name the account that actually exists.** `Global.current_application_address` became `Global.creator_address`. The application's address holds the contract's money and has no private key; the creator's address is a real account with a real signer, fixed at creation and unforgeable afterward. One is the contract's wallet, the other is its owner, and the greeter asked the wallet to prove it was the owner.

The fix has a limit. `Global.creator_address` is immutable: lose that key and you lose the ability to shut the application down, permanently. Real contracts usually store an admin address in global state at creation instead, so it can be rotated. Chapter 4 shows how, and shows why capturing it at creation is the only moment `Txn.sender` and `Global.creator_address` are guaranteed to be the same account.

Deploy the fixed greeter and run it against the commission from the top of the chapter:

```python
>>> greeter.send.greet(args=("Ada",)).abi_return
'Hello, Ada'
>>> greeter.send.greet(args=("",))
LogicError: Txn 3KMR...T2A had error 'greet: name must not be empty'
    ... 10 lines of TEAL trace ...
>>> greeter.send.greet(args=("A" * 1100,))
LogicError: Txn UV5H...M8Q had error 'greet: name is over 64 bytes'
    ... 10 lines of TEAL trace ...
>>> greeter.send.delete.shut_down()   # from the creator account
(confirmed --- application deleted, minimum balance released)
```

Against the spec: greet anyone who asks --- yes. Refuse an empty name with an error the caller can read --- yes, and the sentence names the method and the rule. Refuse oversized names by naming the limit --- yes, before the log budget can fail first. Let the people who deployed it, and only them, shut it down --- yes, guarded on an account that exists and can sign. Four for four, and the 100,000 microAlgos come back this time.

## Retrieval
Answer these from memory before moving on. All of them are from this chapter; in later chapters, some will reach backwards on purpose.

1. A contract is a transaction validator, not a running process. When, exactly, do its state changes become real?
2. What are the only two AVM value types?
3. What is the base minimum balance of any Algorand account, in microAlgos?
4. Which account pays the minimum balance for a box: the creator, the caller, or the application?
5. Where does the string in `assert x > 0, "x must be positive"` end up, and what reads it back?
6. Name the four accounts a contract routinely talks about, and say which two can sign a transaction.
7. How many bytes may one application call write to its log, and why does that number bound what a method can return?
8. What is a method selector, and what is it computed from?

## Exercises
1. Walk the broken greeter through this exact sequence: the creator deploys it; Ada calls `greet("Ada")`; Ada calls `greet("")`; a stranger calls `greet` with a 1,100-byte name; the creator calls `shut_down()`; the creator funds the application account with 1 Algo and calls `shut_down()` again.

   a. **(Trace)** Write down what the caller sees after each of the six steps.

   b. **(Trace)** For each of the six, say whether the ledger changed.

   c. **(Trace)** State which single step is responsible for the 100,000 microAlgos the creator can never recover.

2. Below are six statements. Four of them form the body of the fixed greeter's `greet` method; two do not belong in it at all. The decorator and signature are given, so syntax will not do your ordering for you.

   ```python
   @arc4.abimethod
   def greet(self, name: String) -> String:
       ...
   ```

   The statements: (a) `length = name.bytes.length`; (b) `assert length > UInt64(0), "greet: name must not be empty"`; (c) `assert length <= UInt64(MAX_NAME_BYTES), "greet: name is over 64 bytes"`; (d) `return "Hello, " + name`; (e) `assert Txn.sender == Global.creator_address, "greet: creator only"`; (f) `assert name.bytes.length > 0`.

   a. **(Parsons)** Select the four that belong and order them.

   b. **(Debug)** For each of the two you rejected, name the specific thing that goes wrong if you keep it: one of them would make the method useless for its stated purpose, and the other re-introduces the bug this chapter opened with.

   c. **(Parsons)** Two of the four you kept are forced into their positions by dataflow, and two are not. Say which are which.

   d. **(Compare)** Explain why the ordering the AVM would accept is still not the ordering you should write.

3. A developer wants an admin-only method and writes `assert Txn.sender == Global.current_application_address, "admin only"`. Their unit test passes.

   a. **(Debug)** Explain how a unit test can pass against an unsatisfiable guard: what the test must be doing, and what it is therefore not testing.

   b. **(Debug)** Say what the test should assert instead.

   c. **(Debug)** Name the one deployment scenario in which discovering this bug is unrecoverable rather than merely embarrassing.

4. You need to let exactly one party shut an application down. Three designs: guarding on `Global.creator_address`; storing an admin address in global state at creation and guarding on that; and requiring the caller to hold a specific ASA.

   a. **(Compare)** Compare them on four axes: whether the authority can be transferred after deployment, what an attacker must compromise to gain it, what it costs in minimum balance, and what happens if the authorized key is lost.

   b. **(Compare)** One of the three is strictly worse than another on three of the four axes; identify the pair and say which axis saves it.

   c. **(Compare)** Name the requirement that would force each of the other two.

5. Extend the fixed greeter with a `greet_many` method that takes a `arc4.DynamicArray[arc4.String]` of names and returns all the greetings. You will hit a limit this chapter named but did not solve.

   a. **(Extend)** Write the method.

   b. **(Trace)** Write down the largest number of 10-byte names it can accept before something fails, and which of the two budgets fails first.

   c. **(Extend)** Say what the error message should say so that a caller can act on it without reading your source.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can explain what a contract *is* --- a transaction validator, not a running process --- and say what that implies about when its state changes commit.
- [ ] I can name `Txn.sender`, `Global.creator_address`, `Global.current_application_address` and an `Account` argument, say which of them can sign a transaction, and pick the right one for an authorization check.
- [ ] I can compute the minimum balance of an account given its assets, applications and boxes, and say which account is charged for each.
- [ ] I can explain where an assertion message is stored, why it is not on chain, and what a caller sees when I omit it.
- [ ] I can trace a method call from a typed Python client through the selector and argument encoding to the log entry that carries the return value back.

## Handoff: The Lifecycle the Vesting Project Assumes
Chapter 9 builds a real token vesting contract, and it assumes every one of these on its first page. Table 2-1 lists the examples from this chapter that it leans on, and what to predict before you read it.

: Table 2-1. Examples from this chapter that the vesting project depends on

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| Example 2-2 | The vesting contract's class declaration and first method | What does subclassing `ARC4Contract` generate that you would otherwise write by hand? |
| Example 2-4 | The beneficiary `Account` and the vested `Asset`, passed as method arguments | The contract receives an `Account`. What does it actually receive, and what must the transaction declare? |
| Example 2-3 | Every guard in the contract: admin checks, cliff checks, amount checks | A beneficiary claims before the cliff. What should the failure tell them, and where will that sentence be stored? |
| Example 2-5 | The `OnComplete` handling that rejects updates and deletes | Which of the six OnCompletes must a contract holding other people's tokens refuse, and why? |
| Example 2-9 | Every deployment and interaction script in the chapter | The contract returns a claimed amount. By what mechanism does that number get back to your Python? |
