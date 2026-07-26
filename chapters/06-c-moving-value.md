\newpage

# Moving Value: Assets, Payments, and Groups

The last chapter left you with a contract that could compute exactly what somebody was owed and had no way whatsoever to give it to them. That was deliberate: every defect in the vesting calculator was wrong before any money moved, which made it possible to study arithmetic without also studying custody. This chapter removes that restriction, and everything it adds is about the same single fact --- **a contract on Algorand has an account, and it is the only signer that account will ever have.**

That fact is worth more than it first sounds. Every application address is derived from the application ID, and no private key exists for it anywhere. Nobody lost it; there was never one to lose. So the only way a microAlgo or an asset unit ever leaves that account is that some line of your code decided to submit an inner transaction, and the only way value ever *arrives* is that somebody sent it in a transaction your contract may or may not have bothered to look at. Both halves of that sentence produce a family of failures, and they are not the same family. Sending is a question about authorization and fees. Receiving is a question about *evidence* --- because the transaction that pays you and the transaction that calls you are two different transactions, and nothing but an assertion you write connects them.

## The Problem
Here is a failure with a name: **the tip jar that could not be emptied.**

A creator deploys a tip jar. It is forty-three lines. Somebody sends a tip, the counter goes up, and a block explorer confirms the money arrived at the application address. It is reviewed by two people, it is deployed to MainNet, and it is linked from a profile page.

Six weeks later the jar holds 33.3 Algo and the creator calls `withdraw` for the first time. It fails. It fails again the next day, and the day after that, and it will fail every time it is ever called, for two reasons stacked one behind the other. There is no admin method, no upgrade path, and no key --- the application address has no private key, so there is no wallet anywhere that can reach past the contract and move the money by hand. The 33.3 Algo is not stolen. It is somewhere nobody can go.

That is the defect the creator noticed, and it is really two. The audit that follows finds two more, and both of them are worse. The jar's counter says 41.4 Algo across a hundred and nine tips. Only 33.2 Algo of that ever arrived --- the account holds 33.3 because the deployer's 0.1 Algo of funding is in there too --- and the missing 8.2 is thirty-one tips that were never paid to the jar at all. The caller built a group in which the "tip" was a payment to their own account, the contract credited them anyway, and the leaderboard on the profile page has been ranking people by money they still have. Another sixteen tips were real, arrived, and were credited to somebody who had not sent them.

Four defects, one contract, and the same shape as the last chapter's: every one of them behaves perfectly on the happy path. A tip that is honestly paid, in a two-transaction group, by the person calling the method, is credited correctly. The contract was tested exclusively that way, by the person who wrote it, who knew how it was meant to be used.

## What You'll Be Able to Do
By the end of this chapter you will be able to:

- Name the account an application controls, say why no private key exists for it, and compute how much of its balance is actually spendable
- Send Algo and asset units out of a contract with inner transactions, and say who pays the fee under each of the two possible settings
- Validate an incoming payment or asset transfer against all four of the questions a group argument does *not* answer for you
- Bound the group a method will accept, and explain why an index check without a size check is worth almost nothing
- Create an asset from a contract, opt the contract into somebody else's asset, and say what each of those costs in minimum balance
- Name an asset's four authority roles, say which of them is custody in disguise, and say what happens to a role you leave out of a reconfiguration
- Say, for any contract holding value, why its own account balance is the wrong number to do accounting with

{{fig:contract-as-sender}} is the picture the whole chapter hangs on, and it is worth reading before any code, because the thing it shows is the thing that is hardest to believe from a listing: the payment happens *inside* the app call, not after it.

{{include-fig:contract-as-sender}}

Two details on that diagram carry more weight than the arrows. The inner payment's fee is zero and the *caller's* transaction is the one that covers it --- that is a decision the contract made, and the section on fees is about what happens when it does not make it. And the note at the bottom is the atomicity guarantee arriving in a new costume: a rejection anywhere above undoes the payment along with everything else, because the payment was never a separate event in the first place.

## The Mini-Build, Broken
Example: The tip jar, as first written {#ex:tip-jar-broken}

<!-- finder: see a working tip jar whose money cannot be withdrawn -->

{{include-ex:tip-jar-broken}}

{{ex:tip-jar-broken}} is complete and deployable. It compiles without a warning, it has an owner-only guard on `withdraw`, it refuses tips below a thousand microAlgo, and it credits both a global counter and per-account local state. Three of its four defects are on this book's danger list. None of the four is a missing feature; each one is a check the author knew about in some other context and did not think to make here.

*Predict: four defects. Write your four down now, in whatever words you have. Two of them are about money arriving, one is about money leaving, and one is about who pays the network. The next four pages name them one at a time --- except for two, which arrive together, because that is how they fail; score yourself as each one lands.*

Deploy it, fund it into existence with exactly its 100,000-microAlgo minimum, and tip it honestly. This is an **on-chain run** against LocalNet through an algokit-utils typed client, and the transcript is what a satisfied author sees:

```console
$ algokit project deploy localnet
tip-jar 1211 deployed
```

```python
>>> jar.send.opt_in.tip(args=(pay(jar.app_address, 5_000_000),))
>>> jar.send.total().abi_return
5000000
```

The money arrived, the counter moved, and the block explorer agrees. Now build the same group with one field changed --- the payment's receiver is the caller's own account rather than the jar's:

```python
>>> jar.send.tip(args=(pay(attacker.address, 5_000_000),))
>>> jar.send.total().abi_return
10000000
```

Nothing failed, because nothing was checked. That is defect one, and it is danger-list item 4. The parameter is declared `payment: gtxn.PaymentTransaction`, which does real work --- the ABI router insists that the transaction immediately before this call is a payment, and it will reject a group where that slot holds an asset transfer or another app call. **A group argument's type pins what kind of transaction it is and where it sits. It says nothing about where the money went, how much of it there was, or whose it was.** The attacker's five Algo really did move; it moved from their left hand to their right, and the jar credited them for it.

Change a different field and defect two appears. The payment is genuine, to the jar, but it was sent by somebody else --- a pending transaction lifted out of the mempool, or a friend's payment reused:

```python
>>> jar.send.tip(args=(someone_elses_payment,))
```

The tip is credited to `Txn.sender`, who is the caller, who is not the payer. Nothing about the group is malformed. The contract has two accounts in front of it and has assumed they are the same one without saying so.

*Predict: `tip` reads its payment through a typed parameter, and a group may hold up to sixteen transactions. Before reading on, say what happens if the attacker puts one real payment at index 0 and then two copies of `tip` behind it, hoping to be credited twice for the same money.*

The second copy fails, and it fails for a reason you did not write and should not rely on. PuyaPy lowers a typed group parameter *position-relatively*: `payment: gtxn.PaymentTransaction` compiles to a read of the transaction immediately before this one, followed by an assertion that its type is a payment. The second `tip` therefore reads the *first* `tip`, which is an application call, and aborts with `transaction type is pay`. The same lowering is why a `tip` submitted at group index 0 dies before any of your code runs: zero minus one is a subtraction, and it underflows.

Take the win and do not bank on it. What the parameter bought you is one position, chosen by the compiler and never stated in the source. It is not a group-size check, it does not stop the group being padded to sixteen, and a method that names its own index --- `gtxn.PaymentTransaction(0)` --- gets none of it. That is danger-list item 20, and the section on group bounds is where it bites.

Now the defect the creator actually noticed. Call `withdraw` as the owner, on a jar holding 33.3 Algo:

```python
>>> jar.send.withdraw()
LogicError: Txn 5HRP...9QK2 had error 'inner tx 0 failed: overspend
(account KRT4...5DVQ, data {...}, tried to spend 33.300000A)' at PC 204:
    ... no source line: PuyaPy's ARC-56 output carries no TEAL map ...
```

Read the message rather than the program counter. `overspend` is not a complaint about the minimum balance, and the reason it is not is the first thing to explain. `amount = app.balance` instructs the account to send every microAlgo it holds --- and the inner transaction's fee is taken from that same account *before* the payment is applied. The jar is a thousand microAlgo short of its own instruction before the payment is even attempted. That is defect four firing, and defect three is standing immediately behind it.

Set the fee to zero and defect three has not moved. `app.balance` counts the hundred thousand microAlgo the account is required to keep in order to exist, and an account that keeps anything at all may not settle below that figure. Correcting only the fee leaves a `withdraw` that asks the jar to empty itself down to nothing --- the reserve included --- which is not what "withdraw the balance" was ever meant to mean. Correcting only the subtraction is worse, because it looks right: `app.balance - app.min_balance` with the fee left in place instructs the account to pay a thousand microAlgo and then send 33.2 Algo, which would settle it at 99,000 --- a thousand under its own floor. So that version fails too, and not just for large amounts: for every amount, permanently, on a contract with no other way out.

That is all four, and two of them share a single visible failure --- which is why the creator's diagnosis, "there is a bug in `withdraw`", was true and nowhere near specific enough to act on. The fee is danger-list item 1, and on this contract it is contained: `withdraw` is owner-only, so the drain is one owner paying a fee they did not know they were paying. Put the same line on a method anybody may call and it is a withdrawal with extra steps, at a thousand microAlgo a call, forever.

Five sections follow. The first is the contract as a sender and the second is the contract as a receiver; the third is the atomicity that ties both to everything else in the group; the fourth is the assets a contract can hold, and the fifth is who controls an asset, and why a contract's own balance is the wrong number to keep books with. Each ends by naming what it repairs in the jar --- and three of them repair nothing in the jar at all. That is said here in advance so it reads as the truth about a forty-three-line contract rather than as a promise the chapter failed to keep.

## The Contract Has an Account
Everything in this section follows from one sentence: **an application controls an account whose address is derived from its ID, for which no private key exists, and the only transactions that account will ever send are the ones this code submits.**

Example: The account an application controls {#ex:app-account}

<!-- finder: read the application account's address and spendable balance -->

{{include-ex:app-account}}

Three read-only methods and no state. `Global.current_application_address` is the account, and the load-bearing line is the one in `spendable`: `account.balance - account.min_balance`. The balance is what the account holds. The minimum balance is what it may never go below --- 100,000 microAlgo to exist, plus 100,000 for every asset it holds, plus the box charges from {{ch:boxes}}. The schema an application declares is *not* in that sum. As {{ch:state}} established, an application's *global* schema and extra pages are billed to the account that created it, and its *local* schema is billed to each account that opts in; the application account pays for what it holds, not for what it declares. The difference between balance and minimum is the only figure a contract may actually spend, and computing it wrong is the tip jar's third defect.

Note which way that subtraction is written, because {{ch:numbers-and-time}}'s rule applies here and the compiler will not remind you. `balance - min_balance` is safe on *this* account, because the protocol will not let a funded account settle below its own minimum. It is not safe as a habit. Apply the same shape to an account you do not control --- a recipient, a beneficiary, an address that arrived as an argument --- and you are subtracting two numbers whose order you have not established, and an underflow ends the transaction with a message about arithmetic rather than about funding. The form that never has the problem is `balance >= min_balance + cost`, and the opt-in example later in this chapter is written that way on purpose.

*Predict: this contract has no methods that spend anything, holds no assets, and declares no state. On an application that was deployed and never funded, what do `held` and `spendable` return?*

Neither of them returns. Both calls fail, and the reason is worth carrying with you: `Account.balance` and `Account.min_balance` compile to `acct_params_get`, whose did-this-account-exist flag is nothing more sophisticated than *balance greater than zero*. PuyaPy asserts on that flag, so the failure the reader gets is `account funded` --- an assertion nobody in this file wrote. An account holding nothing does not read as an account holding nothing; it reads as an account that is not there. An application's account is *not* funded by deployment --- it comes into existence empty --- which is why the first thing every deployment script in this book does after creating an application is pay its address enough to be useful. Fund it, and `min_balance` is 100,000 for this contract and `spendable` is whatever arrived above that.

Example: Sending Algo out of the application account {#ex:inner-payment}

<!-- finder: send Algo from a contract with an inner transaction -->

{{include-ex:inner-payment}}

This is the diagram in contract form. `itxn.Payment(...).submit()` builds a payment and sends it, immediately, in the middle of this method --- not queued for later, not returned to the caller to sign. The load-bearing word is `.submit()`, and the comment above it says the part that matters: if the payment fails, this method fails. There is no error to catch and no partial success to clean up, which is why the guard above it is an assertion rather than a branch.

The return value is worth a second look because it is deliberately *not* `account.balance`. Reading the balance back after submitting an inner payment is the obvious thing to write, and it makes the method's answer depend on the environment it ran in rather than on the arithmetic. `headroom - amount` is computed from figures established before the payment, so it is the same number wherever you run it.

Example: Making the caller pay for the contract's transactions {#ex:inner-fee-zero}

<!-- finder: charge the caller for a contract's inner transaction fees -->

{{include-ex:inner-fee-zero}}

Here is the fee rule stated properly, because it is danger-list item 1 and the phrasing usually given for it is wrong. `fee: UInt64 | int = 0` is the declared default on every `itxn` builder in algorand-python. Leaving the field out does not produce a default fee; it produces a zero fee. **The danger is never an omitted fee. It is a fee somebody wrote a non-zero value into.** Writing `fee=UInt64(0)` explicitly changes no behaviour at all and is worth doing anyway, because it turns an omission a reviewer has to assume was intentional into a line they can see was.

A zero fee is not free money. Algorand pools fees across an atomic group: the group is valid if the total fee paid across it meets the total minimum required, including every inner transaction any of them submits. So a zero-fee inner payment means somebody else in the group is covering it, and the load-bearing line is `assert Txn.fee >= UInt64(POOLED_FEE)` --- one app call plus two inner payments is three transactions and 3,000 microAlgo, and the app call is the only one of the three that a caller can attach a fee to. Omit that assertion and you have not created a vulnerability, only a method that fails at submission when the caller under-pays. Omit the `fee=UInt64(0)` and you have created one. Why the network is willing to let one transaction pay for another's fee at all is the atomic group's doing, and the section on groups is where that is worth unpacking.

Example: A method that charges the contract a thousand microAlgo per call {#ex:inner-fee-zero-wrong}

<!-- finder: see how a non-zero inner fee drains a contract -->

{{include-ex:inner-fee-zero-wrong}}

Eighteen lines, no authorization, and a zero-Algo payment --- which looks harmless, since it moves nothing. It moves 1,000 microAlgo per call out of the application account, forever, to nobody. A hundred thousand calls is 100 Algo, and the attacker's own cost is the outer fee they were going to pay anyway. The contract does not need to hold a treasury for this to matter: draining it to its minimum balance is enough to make every *other* inner transaction it wants to send start failing.

*What this section repairs in the tip jar:* defects three and four. `withdraw` sends `app.balance - app.min_balance`, and its inner payment carries `fee=UInt64(0)` so that the owner's own transaction covers the network.

## Requiring the Other Half of the Deal
A contract cannot reach into an account and take anything. It has no authority over anybody's balance but its own, so every design that involves a user *giving* the contract something has the same shape: the user signs the transfer, the user signs the app call, the two travel together in a group, and the contract's entire job is to convince itself that the transfer it was handed is the transfer it wanted.

There are exactly four questions to ask of an incoming transfer, and a typed group parameter answers none of them: **which asset, how much, where it went, and whose it was.**

Example: Crediting a caller for Algo they sent in the same group {#ex:grouped-payment}

<!-- finder: accept and validate an Algo payment sent alongside a call -->

{{include-ex:grouped-payment}}

Three assertions and one comment, and the comment is the section. `assert payment.receiver == app` is danger-list item 4, and it is the one people skip because the group *looks* like it means what they want. `assert payment.sender == Txn.sender` is the one people skip because they never imagined the two accounts differing. `assert payment.amount >= MIN_DEPOSIT` is the one people remember.

Note the order they are in. Cheapest and most decisive first is a habit worth having, but the reason to check the receiver before the amount is legibility, not gas: a reader who sees the destination checked on the first line stops wondering whether it was checked at all.

Example: The same method with the destination unchecked {#ex:grouped-payment-wrong}

<!-- finder: see a deposit method credit a payment that went elsewhere -->

{{include-ex:grouped-payment-wrong}}

`LooseDeposits` is `Deposits` with two assertions deleted, and it is the tip jar's first defect isolated. Its unit test is the clearest statement in the chapter: the same self-payment, in the same group shape, is refused by one contract and credited by the other. The attacker's money never left their control and their position is real.

*Predict: `LooseDeposits` credits `payment.amount` for a payment that went to the attacker. What is the largest position an attacker can open, and what does it cost them?*

Whatever they can briefly hold, and roughly one fee. A payment to yourself of a million Algo costs a thousand microAlgo and leaves your balance exactly where it started.

Example: Accepting exactly one asset and refusing all the others {#ex:grouped-asset-transfer}

<!-- finder: validate an incoming ASA transfer against a stored asset id -->

{{include-ex:grouped-asset-transfer}}

The same shape with a fourth question added, and the fourth question is the dangerous one. `assert transfer.xfer_asset.id == self.token.value` is danger-list item 5. Anyone may create an asset on Algorand for a fee; an attacker can mint a trillion units of a token that nobody wants, in about a second, and if your vault checks the destination and the amount but not the identity, those units buy a real position.

Note where the expected id comes from: `configure` writes it once, guarded by both a creator check and an init-once flag, and `deposit` reads it. It is never a method argument. **An asset id supplied by the caller is not a check; it is a formality the caller performs on themselves.**

Example: The same vault with the asset unchecked {#ex:grouped-asset-transfer-wrong}

<!-- finder: see a vault credit a worthless asset as if it were the real one -->

{{include-ex:grouped-asset-transfer-wrong}}

`AnyTokenVault` checks the destination faithfully. The units really do arrive at the application account, which is what makes this one harder to spot in review than the missing-receiver bug: something did move, and the block explorer will happily show it.

Example: Refusing every group shape but the one intended {#ex:group-bounds}

<!-- finder: bound the size and position of the group a method accepts -->

{{include-ex:group-bounds}}

Two assertions doing two different jobs, and this is danger-list item 20. `Global.group_size == UInt64(GROUP_SIZE)` says how long the group is. `Txn.group_index == UInt64(1)` says where in it this call sits. Neither implies the other, and a method that reads a group position while asserting only one of them is not bounded.

The third line worth naming is `gtxn.PaymentTransaction(Txn.group_index - 1)`, which reads the transaction immediately before this one rather than the transaction at absolute index zero. Position-relative reads survive being nested in a larger group later, when the size check is deliberately relaxed; absolute reads do not.

Example: A claim that can be made as many times as the group is long {#ex:group-bounds-wrong}

<!-- finder: see one payment credited sixteen times in a single group -->

{{include-ex:group-bounds-wrong}}

`ReplayableEscrow` reads `gtxn.PaymentTransaction(0)` and never asks how long the group is. One real payment at index 0, followed by fifteen copies of `claim`, credits the same money sixteen times inside one atomic group --- and every transaction in that group is individually valid, correctly signed, and does exactly what it says. The payment is real. The accounting is fiction.

*What this section repairs in the tip jar:* defects one and two. `tip` bounds the group to two transactions, checks the payment's receiver against the application address, and checks its sender against the caller.

## All of It, or None of It
{{fig:atomic-group}} in {{ch:mental-model}} introduced the guarantee: a group of up to sixteen transactions either all commit or none do. This section is about what that means once your contract is one of the transactions and value is moving in the others.

The guarantee is about the *commit*, not about isolation. The transactions in a group execute in order against a single shared, copy-on-write view of the ledger, and only that view's final state reaches the ledger, and only if every transaction approved. So a write your contract performs is visible to a later transaction in the same group, and is discarded entirely if anything after it rejects.

That shared fate is also why fees pool, which is the answer the fee section deferred. A group is validated as a unit, so the network asks only whether the total fee paid across it meets the total minimum required, counting every inner transaction any member of it submits. It has no reason to care which transaction carried the money, because there is no outcome in which some of them commit and the rest do not. That is what makes `fee=UInt64(0)` on an inner transaction a legal thing to write rather than a way of getting something for nothing --- somebody in the group paid, and the group is the only unit the fee rule has ever applied to.

{{fig:group-commit}} draws both halves of it: the shared copy the transactions write into, and the single moment at which that copy either reaches the ledger or is thrown away.

{{include-fig:group-commit}}

Example: Booking the withdrawal before making it {#ex:group-all-or-nothing}

<!-- finder: order a state write and an inner payment without a rollback path -->

{{include-ex:group-all-or-nothing}}

`self.paid_out.value += amount` runs *before* the payment it accounts for, and in most runtimes that line is unremarkable. Here it is a line with a crash waiting behind it --- except that it is fine, and the comment says why: if the payment fails, or if any later transaction in the group fails, the assignment is discarded along with it. There is no state to unwind because there is no state until the whole group commits.

This retires a habit rather than teaching one. **Do not write rollback paths, compensating updates, or partial-failure handling into an AVM contract.** There is no partial failure to handle. Write the state in whatever order reads most clearly, and let the group be the transaction boundary it already is.

*Predict: Algorand has no reentrancy --- an inner transaction cannot call back into the contract that submitted it. Given that, and given that a failed group leaves no state behind to clean up, is there any correctness reason left to prefer one ordering of a state write and an inner transaction over the other?*

Not for safety, no --- and that is the point of the section. There is one reason left, and it is arithmetic: a figure that is derived *from* other state has to be computed after that state is current, or it is derived from a stale number. In this contract nothing is derived from anything, so the ordering genuinely does not matter. In the AMM and the farming projects it will, because those contracts keep running totals that every per-user payout is measured against, and a payout computed before the total is brought up to date is measured against last time's answer. Keep that filed under arithmetic and never under safety; read it as a reentrancy guard and you will contort clear code against a threat the AVM does not have.

Example: Forwarding money that arrived moments earlier {#ex:pay-from-payload}

<!-- finder: take a fee from an incoming payment and forward the remainder -->

{{include-ex:pay-from-payload}}

Both halves of the chapter in one method. A payment arrives in the group and is validated for destination, sender, and group shape; a cut is computed with {{ch:numbers-and-time}}'s ordering, multiply before divide; and the remainder leaves in an inner payment with a zero fee. The application account holds nothing between calls --- it is a conduit, not a treasury --- which is why `Forwarder` needs no funding beyond its bare minimum balance.

The line worth pausing on is `cut = payment.amount * UInt64(FEE_BASIS_POINTS) // UInt64(10_000)`, and specifically the direction it rounds. Integer division floors, so the dust from every fractional microAlgo stays with the contract rather than with the recipient. That is the correct direction, always: rounding that favours the caller is a rounding error an attacker can call in a loop.

Example: Two asset arguments that must not be one asset {#ex:same-asset-twice}

<!-- finder: reject a pool bootstrapped with the same asset on both sides -->

{{include-ex:same-asset-twice}}

`assert a.id != b.id` is the whole example, and it is danger-list item 21. Two arguments of the same type are two *names*; nothing in the type system, the ABI, or the AVM makes them two things. Every later method in a pool contract reads `asset_a` and `asset_b` as opposing sides of a trade, and each of those methods is correct in isolation.

*Predict: `SelfPair` is `Pair` with that one assertion deleted, and it stores `asset_a` and `asset_b` as the same id. Before you read it, say what a later `swap` method --- one that is individually correct, and that you will not see --- computes when the asset going in and the asset coming out are one asset. Then put an order of magnitude on what that is worth to whoever notices first.*

Example: The pool that accepts an asset against itself {#ex:same-asset-twice-wrong}

<!-- finder: see the one-line omission behind Tinyman V1's $3M exploit -->

{{include-ex:same-asset-twice-wrong}}

The deleted assertion is the only difference between the two contracts, and the deletion is roughly a three-million-dollar mistake --- this is the core of the Tinyman V1 exploit of January 2022, reduced to the line that was missing. When both sides name one asset, a deposit on one side is instantly withdrawable from the other at whatever rate the pricing maths happens to produce, and the pricing maths was never wrong.

*What this section repairs in the tip jar:* nothing directly, and that is worth saying plainly. The jar has one state write and one inner payment and would behave identically under any ordering. What this section supplies is the reason you may stop worrying about that, and the group-size assertion the previous section added is only meaningful because groups are the unit of commit.

## Assets a Contract Can Hold
An Algorand Standard Asset is a first-class ledger object, not a contract. Creating one, holding one, and sending one are transaction types the protocol implements directly, which means a contract does all three with inner transactions and none of it requires a token contract to exist.

Every asset in this section is one the contract did not create for itself, and three rules govern all of them. An account holds an asset only after opting in. Opting in costs 100,000 microAlgo of minimum balance, per asset, held for as long as the holding exists. And a transfer to an account that has not opted in fails --- which, inside a group, takes everything else down with it. An asset's creator is opted in from the moment the asset exists and never submits an opt-in of its own, which is the first example below and the one exception you will meet.

Example: Creating an asset from a contract {#ex:asa-create}

<!-- finder: mint an ASA whose creator is the application account -->

{{include-ex:asa-create}}

`itxn.AssetConfig` with no `config_asset` creates an asset; `created_asset.id` on the result is how you learn its id, and storing that id immediately is not optional bookkeeping --- it is the only thing that lets every later method check what it is being handed.

The application account becomes the creator, receives the entire supply, and is opted in automatically, which is why the docstring names the 100,000 microAlgo. The creator of an asset is always opted into it and cannot close out of it while the asset exists.

*Predict: `mint` is guarded by a creator check and an init-once flag. `manager` is set to the application address and no `reserve`, `freeze`, or `clawback` is given. What are those three set to, and can they be set later?*

All three are the zero address, and no, they cannot. A role omitted from the creating `AssetConfig` is cleared, and a cleared role on an Algorand asset is permanent --- the rest of that answer is the next section.

Example: Opting a contract into somebody else's asset {#ex:asa-self-optin}

<!-- finder: opt an application account into an ASA it did not create -->

{{include-ex:asa-self-optin}}

An opt-in is a zero-amount transfer of the asset to yourself. That is the entire mechanism, for every account on Algorand, and a contract performs it for itself with an inner transaction --- the one opt-in on the chain that requires nobody's signature.

The load-bearing line is the assertion, not the transfer: `assert app.balance >= app.min_balance + UInt64(OPT_IN_MBR)`. Opting in raises the account's own minimum balance by 100,000 microAlgo, and an account that cannot afford its new minimum cannot complete the opt-in. Note the form of that check --- `balance >= min_balance + cost`, not `balance - min_balance >= cost`. That is {{ch:boxes}}'s rule and {{ch:numbers-and-time}}'s reason. The second form is a subtraction whose safety rests on an invariant you have asserted rather than one the language guarantees: it is correct exactly when the account is at or above its minimum, which is the thing the line was written to find out. Get it wrong --- an account below its floor, an address handed in as an argument, a minimum that rose since you last looked --- and the transaction ends with a message about arithmetic rather than about funding. The addition never has a wrong answer to give.

Example: Sending asset units out of the application account {#ex:asa-send}

<!-- finder: transfer ASA units from a contract to an account -->

{{include-ex:asa-send}}

Structurally identical to {{ex:inner-payment}} with three fields renamed: `xfer_asset` names the asset, `asset_receiver` the destination, `asset_amount` the quantity. The guard is the asset analogue of the headroom check --- `token.balance(app)` is what the application holds of this asset, and there is no minimum-balance carve-out to subtract, because an asset holding has no reserved floor.

One sharp edge in that guard, and it is the reason `Asset.balance` deserves its own sentence: **`token.balance(account)` fails if that account has not opted in.** It does not return zero. So a contract that has not opted into the asset it is being asked to send does not get a clean refusal from this assertion; it gets a failed transaction with a message about a missing holding.

Example: Refusing a recipient who cannot receive the asset {#ex:optin-gate-eager}

<!-- finder: check that a recipient has opted in before sending them an asset -->

{{include-ex:optin-gate-eager}}

`recipient.is_opted_in(token)` is the primitive the previous example's warning was pointing at. It takes an account and an asset and returns a boolean, for any account, opted in or not --- which is the whole of the difference. When you want the holding *and* the gate in one read, `op.AssetHoldingGet.asset_balance(account, asset)` returns a two-tuple of the balance and a did-this-holding-exist flag, and you branch on the flag rather than assert on it.

Read the docstring carefully, because it is a claim about error messages rather than about safety. Without the check, the inner transfer fails, the app call fails, and the whole group rolls back --- the money is exactly as safe either way. What changes is what the caller reads: a sentence somebody wrote for them, or a ledger error about an asset id they have to go look up. **A check that only improves the failure message is still worth writing, and saying so out loud stops the next reader from deleting it as redundant.**

Two things in this contract are not about the gate at all, and they take only a few lines between them. They are here because leaving them out would make the example exploitable rather than minimal: `reward` is creator-only, and the asset id comes from state that `configure` wrote once. A version that took the asset as a method argument and let anybody call it would hand out a thousand units of *whatever asset the caller named*, which is the receiving section's rule --- an asset id supplied by the caller is not a check --- doing damage a few pages after it was stated.

Example: Giving up a holding to recover the minimum balance {#ex:asa-close-out}

<!-- finder: close a contract out of an asset and recover its 100,000 MBR -->

{{include-ex:asa-close-out}}

`asset_close_to` is the field that ends a holding, and it does not care what `asset_amount` says: it sends the entire remaining balance to the named account and releases the 100,000 microAlgo. This example sends the remainder to `token.creator`, which is safe for a reason worth stating --- the creator of an asset is always opted into it, so the close-out cannot fail for want of a holding on the other end.

*What this section repairs in the tip jar:* nothing yet, and it is the material the jar would need first if it were to accept tips in a token rather than in Algo. Work out what that would take before reading the next section: an opt-in, a stored asset id, and one more question on every incoming transfer.

## Who Controls an Asset, and What Your Ledger Is
Every ASA carries four addresses, and each one is an authority somebody holds over the asset after it exists. They are visible to anybody with a block explorer, and the decisions you make about them are among the few decisions on Algorand that cannot be revised.

Example: An asset's four authorities, and ending one of them {#ex:asa-roles}

<!-- finder: read an ASA's manager, reserve, freeze and clawback addresses -->

{{include-ex:asa-roles}}

`manager` may reconfigure the asset, including reassigning the other three roles. `reserve` is a *label* and nothing more --- it holds no protocol power at all; it marks an account whose holdings tooling should treat as un-circulated supply. `freeze` may suspend a specific account's holding, so that units exist but cannot move. `clawback` may move units out of any account without that account's signature.

That last one is the one to sit with. **An asset with a clawback address is an asset whose holders do not fully control their own units, and a contract holding the clawback address is custody, on-chain, legible to anyone who looks.** There are legitimate reasons for it --- regulated instruments, ticketing, recoverable credentials --- and the point is not to avoid it but to know you have chosen it.

The load-bearing detail is in `renounce_clawback`, and it is a property of `AssetConfig` rather than of clawback: **an asset reconfiguration writes all four role addresses at once, and any role you leave out is set to the zero address, permanently.** There is no partial update. Every role you want to survive has to be named again in every reconfiguration, which is why the example names three of them explicitly and omits exactly one, on purpose, and cannot undo it.

*Predict: you hold the manager address on a regulated asset. Its clawback address is a contract you deployed, its freeze address is a key you are about to rotate, and its reserve address marks your un-circulated supply. Write out the fields of the `AssetConfig` you would submit. Then say what goes wrong if you build it from whatever the asset's current on-chain roles happen to be rather than from your own record of what they are meant to be.*

All five: `config_asset`, `manager`, `reserve`, `freeze`, `clawback`, with only `freeze` different from what is there now. The second half is the part that catches people. A role you read as blank and re-submit as blank stays blank, and a role you forget to include is cleared whether or not it was ever set --- so a reconfiguration built from the asset's current state can only ever preserve or destroy, never restore. The only source that can tell you a role was *supposed* to be there is a record you kept yourself.

Example: Moving an asset out of an account that signed nothing {#ex:asa-clawback}

<!-- finder: perform a clawback transfer from a contract -->

{{include-ex:asa-clawback}}

`asset_sender` is the field that makes an asset transfer a clawback. Set it and the units come out of that account rather than out of the sender's; leave it out and the same builder sends the contract's own units. One field is the entire distance between the two, which is a good argument for never writing `asset_sender` unless the line above it says why.

The guard `assert token.clawback == app` is there because the operation silently becomes impossible the moment somebody reconfigures the asset --- and, as the previous example established, that can happen by omission rather than by intent.

Example: A vault that tracks what it was given {#ex:balance-is-not-ledger}

<!-- finder: account for deposits with stored state rather than with the balance -->

{{include-ex:balance-is-not-ledger}}

This is danger-list item 6 and the most transferable idea in the chapter. `self.reserve` is the ledger. `app.balance` is a fact about an Algorand account, and it counts the minimum balance, whatever the deployer sent to get the contract running, and anything at all that a stranger decided to send it. None of that is anybody's claim on anything, and the load-bearing line is the assertion in `withdraw`, which is checked against `self.credited` and never against the account.

**Your balance is what you hold. Your ledger is what you owe. A contract that confuses them has no way to tell a deposit from a donation.**

Example: The same vault priced off its balance {#ex:balance-is-not-ledger-wrong}

<!-- finder: see a donation re-price every position in a vault -->

{{include-ex:balance-is-not-ledger-wrong}}

`payout = app.balance * share // UInt64(1_000_000)` prices every share off the account. Send the account money and every open position is worth more, instantly, without the accounts holding them doing anything at all. That sounds like a gift. It is an attack, because the arithmetic runs in both directions and the first depositor into an empty pool can set the price to whatever they like. {{ch:amm}} meets this again under a name --- the first-depositor donation attack --- and with a minimum-liquidity lock that only looks arbitrary if you have not seen this example.

*What this section repairs in the tip jar:* a mistake the jar does not quite make, and it gets no credit for that. `tips_received` is a real counter, faithfully incremented --- and `withdraw` ignores it and sends the balance instead, so nothing the counter says can lose money. Look at the two numbers anyway. The counter says 41.4 Algo; the account holds 33.3. That gap is 8.1 Algo, and it is two independent things pulling in opposite directions: 8.2 Algo of tips the jar counted and never received, less the 0.1 Algo of funding the deployer sent that no tip ever accounted for. Neither number is lying about what it measures. The contract never decided at all which of the two it was keeping books with --- and none of the four corrections decides it either. The general fix is to pick one number as authoritative and never consult the other.

## The Mini-Build, Fixed
Four defects and four corrections, and they do not line up one to one. Two of the defects --- the fee and the subtraction --- are a single repair, and the diff groups them accordingly. And one of the corrections answers no defect on the list: the group bound was never something the jar got wrong, because the jar never asked the question. It is here because the other two `tip` checks are not worth writing without it. No new methods. The full corrected contract is on disk at `examples/ch06_moving_value/tip_jar_fixed.py` and compiles in CI; here is the spine of the diff, with everything unchanged elided.

```diff
+TIP_GROUP_SIZE = 2
     def tip(self, payment: gtxn.PaymentTransaction) -> UInt64:
+        assert Global.group_size == UInt64(TIP_GROUP_SIZE), "pay, then call"
+        app = Global.current_application_address
+        assert payment.receiver == app, "tip this jar, not an account"
+        assert payment.sender == Txn.sender, "credit goes to the payer"
         assert payment.amount >= UInt64(1_000), "tips start at 0.001 Algo"
     def withdraw(self) -> UInt64:
-        amount = app.balance
+        amount = app.balance - app.min_balance
         itxn.Payment(
             amount=amount,
-            fee=Global.min_txn_fee,
+            fee=UInt64(0),
         ).submit()
```

Ten things are elided from that diff and named here so that nothing arrives unannounced. Eight of them did not change. The import line is one --- every name the additions use was already imported for something else, which is a small part of why these defects are easy to ship. The `class TipJar(ARC4Contract):` line is another, and `__init__` is a third, where `owner`, `tips_received` and `tipped` are bound. `tip` keeps its `@arc4.abimethod(allow_actions=["OptIn", "NoOp"])` decorator, its docstring, and all four of its existing body lines below the assertions --- the local-state read, the local-state write, the counter increment, and the return. `withdraw` keeps its `@arc4.abimethod` decorator, its `assert Txn.sender == self.owner.value` guard, which the diff never touches and which was never the problem, its `app = Global.current_application_address` binding, which the corrected `amount` line reads, and its `return amount`. `itxn.Payment` keeps its `receiver=self.owner.value` argument, elided here only for width. And `total` is unchanged in full.

Two things did change and are not shown. The class docstring described four defects and now describes four corrections. And `withdraw`'s docstring gains one word --- *spendable* --- which is the smallest edit in the file and the one that would have prevented all of this.

Redeploy and run the same three things that failed. This is an **on-chain run** against the same LocalNet:

```python
>>> jar.send.opt_in.tip(args=(pay(jar.app_address, 5_000_000),))
>>> jar.send.tip(args=(pay(attacker.address, 5_000_000),))
LogicError: Txn KQ7T...4WM3 had error 'Runtime error when executing TipJar
(appId: 1211) in transaction KQ7T...4WM3: tip this jar, not an account' at PC 143:
    ... no source line: PuyaPy's ARC-56 output carries no TEAL map ...
>>> jar.send.withdraw()
5000000
```

That middle message is worth pausing on, because it is the shape you will read for the rest of this book. The sentence inside the quotes is yours: `tip this jar, not an account` is the comment on the assertion, carried through compilation into the ARC-56 file beside the program counter it belongs to, and substituted back in by the client when the failure comes home. The AVM itself said only that an assertion at PC 143 failed. Everything legible in that line is legible because somebody wrote a comment on an `assert`.

**Correction one: bound the group.** `Global.group_size == UInt64(TIP_GROUP_SIZE)` is the assertion that makes the other two worth writing. It is first in the method for a reason that is about reading rather than about cost: a reader who wants to know what shape of group this method accepts should not have to reconstruct it from three separate checks further down.

**Correction two: check where the money went.** `payment.receiver == app` is one comparison, and it is the difference between a tip jar and a leaderboard of people's own money. This is the correction that would have been caught by a single test written from the attacker's side, which is the general lesson: the happy-path test and the adversarial test are not the same test with different numbers.

**Correction three: check whose money it was.** `payment.sender == Txn.sender` says out loud that the payer and the caller are the same account. If you genuinely want third-party sponsorship --- somebody tipping on another person's behalf --- model the beneficiary as an explicit argument rather than leaving it implied by an unasserted coincidence.

**Correction four: leave the minimum balance where it belongs, and stop paying the network out of the jar.** `app.balance - app.min_balance` and `fee=UInt64(0)` are two lines and two different ideas, and they are grouped because they are the same defect from the account's point of view: the contract was treating its own balance as though every microAlgo in it were spendable. And the transcript only ever showed you the two of them failing together; patch one and the other is still there.

One thing the fixed jar does *not* do, and the omission is deliberate: `withdraw` carries no `assert Txn.fee >= UInt64(2_000)`. The fee section offered one and said you could skip it; this contract skips it. Nothing is at risk either way --- with `fee=UInt64(0)` on the inner payment, a group whose outer fees do not cover it is rejected at submission and no money moves. What the assertion buys is a legible refusal instead of a node-level one, and on an owner-only method the only person it would be explaining anything to is the owner. On a method anybody may call, write it. The rule is not *always assert the pooled fee*; it is *decide who is reading the failure, and whether they will understand it*.

Two rules generalize past this chapter.

The first is about receiving: **a transaction in your group is evidence of nothing until you have checked which asset, how much, where it went, and whose it was --- and the group's size, which decides whether those four answers can be trusted at all.** The typed parameter is a convenience for reading fields, not a validation.

The second is about sending: **value leaves a contract only through an inner transaction it chose to submit, so every departure is a line of code you can point at.** That makes the audit tractable. Find every `.submit()`, and for each one ask who is authorized to reach it, what bounds the amount, and who pays the fee.

## What Bites People Here
Six, in the order you are likely to meet them: two about money leaving, two about money arriving, one about arguments that are not as distinct as they look, and one about what your numbers mean.

::: {.gotcha #inner-fee-zero topic="Inner transactions" title="A non-zero inner transaction fee is paid out of the contract's own balance"}
The fee on an inner transaction comes from the application account, never from the caller. `fee: UInt64 | int = 0` is already the default on every `itxn` builder in algorand-python, so the danger is not an omitted fee --- it is a fee somebody wrote a non-zero value into, most often `Global.min_txn_fee` in the belief that a transaction must carry one. On a method anybody may call, that is an unbounded drain at 1,000 microAlgo per call, and it does not stop being a problem when the balance is large: draining the account toward its minimum makes every other inner transaction the contract wants to send start failing. Write `fee=UInt64(0)` explicitly so the omission reads as a decision, and make the caller cover the group with `assert Txn.fee >= UInt64(TOTAL)`, counting one minimum fee per transaction including the inner ones. Fees pool across an atomic group; that is what makes a zero-fee inner transaction valid in the first place.
:::

::: {.gotcha #spendable-is-not-the-balance topic="Inner transactions" title="An application account's balance is not what it can spend"}
Every Algorand account that still exists when a transaction settles must hold at least its minimum balance, and an application's account is no exception: 100,000 microAlgo to exist, plus 100,000 per asset it holds, plus its box charges. Its declared schema is not in that sum --- schema minimum balance is billed to the creator and to the accounts that opt in, never to the application account. An inner payment of `app.balance` therefore fails for every account that will still exist afterwards --- not for large amounts, for every amount --- and it fails twice over. The fee is the first reason: an inner transaction's fee is taken from the application account *before* the payment is applied, so an instruction to send the whole balance is short by exactly one fee before it is ever attempted, and the message says `overspend` rather than anything about a minimum balance, which sends people looking in the wrong place. The second reason survives `fee=UInt64(0)` entirely: an account holding one asset owes 200,000, and a payment leaving it at zero is refused when the group settles --- this time with a message that does name the minimum, and from the ledger rather than from your program. The only account that slips past both is one holding nothing else at all, which is emptied and deleted rather than checked, and that is a closure, not a withdrawal. Spend `app.balance - app.min_balance`, set `fee=UInt64(0)` so nothing is taken first, and remember that this figure moves: opting into one more asset raises the floor by 100,000 microAlgo and silently reduces what a previously-working withdrawal may send. The failure mode is worse than a rejected transaction, because a contract whose only withdrawal path is unconditionally broken and whose account has no private key is holding money nobody can ever reach.
:::

::: {.gotcha #group-arg-is-not-a-check topic="Atomic groups" title="A typed group argument checks the type, never the contents"}
`payment: gtxn.PaymentTransaction` guarantees that the named slot holds a payment. It guarantees nothing about the receiver, the amount, the sender, or --- for an asset transfer --- which asset. A payment the caller sent to their own account satisfies the type perfectly, costs one fee, and leaves their balance where it started, so an unchecked deposit method hands out positions for free. Ask all four questions on every incoming transfer: `xfer_asset` against a stored id, `amount` against a floor, `receiver` against `Global.current_application_address`, and `sender` against `Txn.sender`. The asset id in particular must come from state your contract wrote, never from a method argument --- an id the caller supplies is a formality the caller performs on themselves.
:::

::: {.gotcha #group-index-without-a-size-check topic="Atomic groups" title="A group index check without a group size check bounds nothing"}
Checking `Txn.group_index` says where your call sits; it says nothing about how many other transactions ride alongside it, and a group may hold sixteen. A method that reads a payment at a fixed index and never asserts `Global.group_size` can be called once per remaining slot against the same payment, crediting the same money up to sixteen times in one atomic group --- every transaction in which is valid, correctly signed, and honest about what it is. This is what makes the receiver and asset checks worth having: an attacker who cannot forge a transfer can still restructure the group around one. A typed group parameter already reads position-relatively --- PuyaPy lowers it that way --- but that is the compiler's choice, not your assertion, and it bounds one slot and nothing else. Assert the size and the index together, and read neighbours position-relative (`Txn.group_index - 1`) rather than absolutely, so the pattern survives being nested later.
:::

::: {.gotcha #two-asset-args-can-be-one-asset topic="ASAs" title="Two asset arguments may name the same asset"}
Two parameters of type `Asset` are two names, not two things, and neither the ABI nor the AVM will stop a caller passing one asset for both. In a pool contract, every later method reads the two as opposing sides of a trade and each of those methods is individually correct; with one asset on both sides, a deposit becomes instantly withdrawable from the other side at whatever the pricing arithmetic produces. This is the core of the Tinyman V1 exploit of January 2022, worth roughly three million dollars, and the fix is `assert a.id != b.id` in the method that stores them. The same reasoning applies to any pair of same-typed arguments that the contract will later treat as distinct --- two accounts, two boxes, two application ids.
:::

::: {.gotcha #balance-is-not-a-ledger topic="Global and local state" title="An account balance is not an accounting record"}
`Global.current_application_address.balance` tells you what the account holds. It does not tell you what anyone is owed, because it also counts the minimum balance, the funding that got the contract running, fee refunds, and anything a stranger chose to send. A contract that prices positions off its balance can have every position re-valued by an outsider making a payment, which in an empty pool means the first depositor sets the price to whatever they like --- the first-depositor donation attack, met again in the AMM. Keep the ledger in state you write, check withdrawals against the ledger, and treat the balance as a liveness signal at most. When the two disagree, the difference is information: it is fees you paid, donations you received, or a bug, and all three are worth knowing about.
:::

## Retrieval
Answer these from memory before moving on. Four of them reach back into earlier chapters on purpose.

1. What is the address an application controls derived from, and where is its private key?
2. Name the four questions a contract must ask of an incoming payment or asset transfer. Then say exactly what a typed group parameter such as `payment: gtxn.PaymentTransaction` does guarantee, and how much of those four it covers.
3. A method asserts `Txn.group_index == UInt64(1)` and reads `gtxn.PaymentTransaction(0)`. What can an attacker still do, and how many times?
4. What is the default value of `fee` on an `itxn` builder, and who pays it when you set it to `Global.min_txn_fee` instead?
5. An asset reconfiguration sets `manager` and `freeze` and nothing else. What has happened to `reserve` and `clawback`, and what would it take to restore them?
6. Why does `Asset.balance(account)` need a companion check, and what is the non-failing primitive that answers "is this account opted in?"
7. *(From {{ch:mental-model}})* You already knew an application address has no private key. Say what that implies about a contract whose only withdrawal method can never succeed.
8. *(From {{ch:numbers-and-time}})* `app.balance - app.min_balance` is a subtraction with no guard in front of it. Say what has to be true of the account for it to be safe, and give the form of funding check that is safe without needing that to be true.
9. *(From {{ch:boxes}})* Opting into an asset raises the application account's minimum balance by 100,000 microAlgo. Which of the box chapter's rules is that the same rule as, and what does it imply about a withdrawal method that worked yesterday?
10. *(From {{ch:state}})* A vault stores each depositor's credit in local state. Say what happens to the contract's books when a depositor clears their local state, and which of this chapter's two numbers now disagrees with the other.

## Exercises
1. **(Trace)** An application account holds 2,400,000 microAlgo, has opted into three assets, and has no boxes and no local or global schema beyond two `UInt64` globals. Work out its minimum balance and its spendable balance, showing each component --- including the one component that looks like it belongs in the sum and does not.

   Now assume a contract that has both {{ex:inner-payment}}'s `pay` and {{ex:asa-self-optin}}'s `opt_in_to`, deployed to that account. The three holdings it already has did not arrive through `opt_in_to`, so its init-once flag is clear and the fourth opt-in is allowed to run. Trace four operations in order: `pay(recipient, 1_500_000)`, then `pay(recipient, 100_000)`, then `opt_in_to` a fourth asset, then `pay(recipient, 400_000)`. For each, say whether it succeeds and what the account's balance and minimum balance are afterwards.

   One of the four fails. Say which, quote the message it produces, and say who wrote that message --- the protocol or the contract --- and name one message from earlier in this chapter that the other one wrote. Then swap the last two operations and trace it again. Something still fails; say what, and say what the pair of traces tells you about ordering a funding check against an operation that raises the floor it checks against.

2. **(Parsons + Analyze)** Below are seven statements. Five of them form the body of a `deposit` method that accepts an ASA transfer in the same group and credits the caller; two do not belong. The decorator and signature are given, `self.token` is a `GlobalState(UInt64)` holding the configured asset id, and `self.deposited` is a `LocalState(UInt64)`.

   ```python
   @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
   def deposit(self, transfer: gtxn.AssetTransferTransaction) -> UInt64:
       ...
   ```

   The statements: (a) `assert Global.group_size == UInt64(2), "transfer, then call"`; (b) `assert transfer.xfer_asset.id == self.token.value, "wrong asset"`; (c) `assert transfer.asset_receiver == Global.current_application_address, "send it here"`; (d) `assert transfer.sender == Txn.sender, "fund your own balance"`; (e) `self.deposited[Txn.sender] = self.deposited.get(Txn.sender, UInt64(0)) + transfer.asset_amount`; (f) `assert transfer.asset_amount <= self.token.value, "too much"`; (g) `self.token.value = transfer.xfer_asset.id`.

   Select the five that belong and order them. Then, for each of the two rejects, say what it does: one of them is nonsense that happens to compile and will reject almost every honest deposit, and the other is a live vulnerability that turns a configured vault into an unconfigured one on every call.

   Finally, the part that is not about the rejects: statement (a) is what makes (b), (c) and (d) trustworthy. Explain that dependency in one sentence. Then decide whether relaxing (a) to `>= UInt64(2)` would require changing anything at all about (b), (c) and (d) --- either say yes and name the changes, or say no and say what (a) was protecting against, given that it was not these three.

3. **(Debug)** A rewards contract has been running for four months. It holds a reward ASA, and `claim` sends a fixed number of units to any caller who has opted in. It has worked for every caller, every time.

   This morning it started failing for everybody, with `logic eval error: inner tx 0 failed: asset 1057 missing from KRT4...5DVQ`. The contract's code has not been changed and nobody has called any administrative method. The reward asset still exists and the contract's Algo balance is 3.1 Algo.

   Before working anything else out, write down what must be true of the application account right now, given that error.

   Then answer three things. First: name the sequence of ordinary operations --- no attacker, no code change --- that produces this state, and say which of this chapter's costs is the mechanism. Second: say why the contract's 3.1 Algo balance is not the reassurance it appears to be, and compute what it would actually need. Third: give a fix that makes the failure legible to a caller *and* a separate fix that makes it not happen, and say which of the two you would ship first and why.

4. **(Compare)** You are designing a token whose issuer must be able to recover units from an account under a court order. Compare three ways of arranging it, on four axes --- what a holder can verify before acquiring the token, what the issuer can do unilaterally, what happens if the controlling key or contract is lost, and what happens if the controlling party is compromised.

   The three: (i) the clawback address is a hot wallet the issuer controls; (ii) the clawback address is an application account, with recovery gated by a contract method behind a multi-signature admin; (iii) there is no clawback address, and recovery is handled by burning and re-issuing, with the issuer as freeze address.

   One of the three is not actually a recovery mechanism at all for units already in circulation --- name it and say precisely what it can and cannot do. Of the remaining two, say which axis decides between them, and give a concrete regulatory or product requirement that would flip your answer.

5. **(Extend)** Extend the fixed tip jar so it can also accept tips in a single ASA rather than only in Algo, keeping the Algo path working. Only the diff was printed in this chapter; the full corrected contract is on disk at `examples/ch06_moving_value/tip_jar_fixed.py`, and you will want it in front of you.

   You will need four things this chapter gave you and one it did not. The four: a configured asset id in state, a self-opt-in guarded by a minimum-balance check, an asset-transfer variant of `tip` with all four incoming checks, and an asset-transfer variant of `withdraw`. The one it did not give you is the ordering problem --- the jar must be opted in before anybody can tip it, and opting in raises the minimum balance, which changes what the *Algo* withdrawal may send.

   Write the contract, then write down three things that can now go wrong that could not go wrong before, and for each one name the specific check or ordering constraint that prevents it. At least one of your three should be about the Algo path breaking as a consequence of something on the asset path.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can name the account an application controls, explain why no private key exists for it, compute its spendable balance, and say what an inner payment of the full balance does.
- [ ] I can send Algo and asset units out of a contract, say who pays the fee under each setting of `fee`, and write the assertion that makes the caller cover a whole group's pooled fees.
- [ ] I can list the four questions an incoming transfer must answer, say exactly what a typed group parameter does and does not guarantee, and say why a group-size assertion is what makes those four checks worth writing.
- [ ] I can create an asset from a contract, opt a contract into somebody else's asset, price both in minimum balance, and say what happens to a role address left out of a reconfiguration.
- [ ] I can say why an account balance is not an accounting record, name the attack that follows from confusing them, and say what it means when a contract's balance and its books disagree.

## Handoff: What the Vesting Project Needs
{{ch:token-vesting}} builds a real token vesting contract: an admin deposits a supply of an ASA, schedules are written per beneficiary, and a claim method pays out what has vested. Every one of those three sentences is this chapter's material with last chapter's arithmetic inside it. {{tbl:moving-value-handoff}} lists the examples the project leans on, and what to predict before you read it.

Table: Examples from this chapter that the vesting project depends on {#tbl:moving-value-handoff}

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| {{ex:grouped-asset-transfer}} | `deposit_tokens`, which takes the grant supply from the admin | The project checks the transfer's asset, amount and destination but authorizes on the *app call's* sender rather than the transfer's. Say why those are different accounts and why that is the right choice there. |
| {{ex:asa-self-optin}} | Bootstrapping the contract into the grant asset before any deposit | The project must be opted in before a deposit can arrive. Who pays the 100,000 microAlgo, and what breaks if they pay it late? |
| {{ex:inner-payment}} | `claim`, whose terminal act is an inner asset transfer | The payout is an ASA transfer, not a payment. Which of the two guards in this example still applies, and what replaces the other? |
| {{ex:inner-fee-zero}} | Every method that pays out | A claim is one app call and one inner transfer. Write the pooled-fee assertion before you read the project's. |
| {{ex:group-bounds}} | The deposit path, which reads a transfer from the group | The project's deposit takes the transfer as a typed argument rather than by index. Say what that changes about the size check, and what it does not. |
| {{ex:balance-is-not-ledger}} | `available_tokens`, which is decremented when a schedule is created | The project tracks unpromised supply in state rather than reading its own asset holding. Work out what an outsider could do to the contract if it read the holding instead. |
| {{ex:optin-gate-eager}} | The payout path, against a beneficiary who may never have opted in | A beneficiary who has not opted into the grant asset cannot be paid, and the project lets the transfer fail rather than gating on it. Predict what the beneficiary sees when it does, and what one line would change that. |
