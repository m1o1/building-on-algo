\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# Moving Value: Assets, Payments, and Groups

The last chapter left you with a contract that could compute exactly what somebody was owed and no way to give it to them. That was deliberate: every defect in the vesting calculator was wrong before any money moved, so you could study arithmetic without also studying custody. This chapter removes the restriction, and everything it adds rests on one fact. **A contract on Algorand has an account, and it is the only signer that account will ever have.**

Every application address is derived from the application ID, and no private key exists for it anywhere. Nobody lost it; there was never one to lose. The only way a microAlgo or an asset unit leaves that account is that some line of your code submitted an inner transaction, and the only way value *arrives* is that somebody sent it in a transaction your contract may or may not have looked at. The two halves fail in different ways. Sending is a question about authorization and fees. Receiving is a question about *evidence*: the transaction that pays you and the transaction that calls you are two different transactions, and nothing but an assertion you write connects them. Chapter 4's Exercise 5 stalled on exactly this --- the registry could compute a member's credits and had no way to pay them out --- and both halves of its answer are this chapter's two questions.

## A Contract That Can Be Paid, and Can Pay

The smallest useful thing a contract can do with value is take some in and let it back out again, and both directions have to be built. Holding an account gives a contract no ability to spend from it; being called in a group tells it nothing about whether the money in that group was ever meant for it.

Figure 7-1 is the chapter in one picture, and it draws the half people find hardest to believe: when a contract sends, the payment happens *inside* the app call, not after it. The caller signs one transaction; the transfers the contract stages are signed by nobody. The two details on that diagram --- the zero fee on the inner payment, and the note at the bottom --- each have a section of this chapter behind them.

![Figure 7-1. A contract has an account of its own, and it can send. The caller signs one transaction; the inner transfers are signed by nobody.](figures/contract-as-sender.svg)

::: {.spec title="Your commission: a tip jar that can be emptied"}
The contract you build this chapter holds other people's money, which makes every mistake in it a custody mistake. It must:

1. Accept tips of 0.001 Algo or more, from anyone, and report the running total
2. Count a tip only if the money actually reached the jar
3. Credit the tip to the account that paid it, not to whoever asked for the credit
4. Let the creator --- and only the creator --- withdraw
5. Hold the float safely: everything above what the account must keep comes out on demand, and the network is never paid out of the jar

Five requirements, three methods. At the end of the chapter you will re-run the finished jar against this list.
:::

By the end of this chapter you will be able to:

- Name the account an application controls, say why no private key exists for it, and compute how much of its balance is actually spendable
- Send Algo and asset units out of a contract with inner transactions, and say who pays the fee under each of the two possible settings
- Validate an incoming payment or asset transfer against all four of the questions a group argument does *not* answer for you
- Bound the group a method will accept, and explain why an index check without a size check guarantees almost nothing
- Create an asset from a contract, opt the contract into somebody else's asset, and say what each of those costs in minimum balance
- Name an asset's four authority roles, say which of them is custody in disguise, and say what happens to a role you leave out of a reconfiguration
- Say, for any contract holding value, why its own account balance is the wrong number to do accounting with

## The Tip Jar, First Pass
Here is that commission, as anyone arriving from Chapter 6 would first write it --- complete, and in full.

**Example 7-1.** The tip jar, as first written

<!-- finder: see a working tip jar whose money cannot be withdrawn -->

```python
from algopy import (ARC4Contract, Global, GlobalState, LocalState, Txn, UInt64,
                    arc4, gtxn, itxn)


class TipJar(ARC4Contract):
    """Collects tips for one creator and pays them out on request.

    Deployed, funded, and demonstrably working: a tip arrives and
    the counter moves. Four things about how value moves through it
    are wrong, and none of them raise a compile error. Three are on
    this book's danger list.
    """

    def __init__(self) -> None:
        self.owner = GlobalState(Global.creator_address)
        self.tips_received = GlobalState(UInt64(0))
        self.tipped = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def tip(self, payment: gtxn.PaymentTransaction) -> UInt64:
        """Credit the caller for a tip they sent in this group."""
        assert payment.amount >= UInt64(1_000), "tips start at 0.001 Algo"
        given = self.tipped.get(Txn.sender, UInt64(0))
        self.tipped[Txn.sender] = given + payment.amount
        self.tips_received.value += payment.amount
        return self.tips_received.value

    @arc4.abimethod
    def withdraw(self) -> UInt64:
        """Send the jar's contents to the owner."""
        assert Txn.sender == self.owner.value, "owner only"
        app = Global.current_application_address
        amount = app.balance
        itxn.Payment(
            receiver=self.owner.value,
            amount=amount,
            fee=Global.min_txn_fee,
        ).submit()
        return amount

    @arc4.abimethod(readonly=True)
    def total(self) -> UInt64:
        return self.tips_received.value
```

Example 7-1 is complete and deployable. It compiles without a warning, it has an owner-only guard on `withdraw`, it refuses tips below a thousand microAlgo, and it credits both a global counter and per-account local state. Three of its four defects are checks that audits of deployed Algorand contracts flag again and again (Chapter 14 quotes a study that measured how common such findings are). None of the four is a missing feature; each one is a check you know from some other context and did not think to make here.

*Predict: four defects. Write your four down now, in whatever words you have. Two of them are about money arriving, one is about money leaving, and one is about who pays the network.*

Deploy it, fund it into existence with exactly its 100,000-microAlgo minimum, and tip it honestly. This is an **on-chain run** against LocalNet through an algokit-utils typed client:

```console
$ algokit project deploy localnet
tip-jar 1211 deployed
```

```python
>>> jar.send.opt_in.tip(args=(pay(jar.app_address, 5_000_000),))
>>> jar.send.total().abi_return
5000000
```

The money arrived, the counter moved, and the block explorer agrees. Now build the same group with one field changed, the payment's receiver being the caller's own account rather than the jar's:

```python
>>> jar.send.tip(args=(pay(attacker.address, 5_000_000),))
>>> jar.send.total().abi_return
10000000
```

Nothing failed, because nothing was checked. That is defect one: the contract never asked where the money went. The parameter is declared `payment: gtxn.PaymentTransaction`, and that declaration buys exactly one thing. The ABI router insists that the transaction immediately before this call is a payment, and it will reject a group where that slot holds an asset transfer or another app call. **A group argument's type pins what kind of transaction it is and where it sits. It says nothing about where the money went, how much of it there was, or whose it was.** The attacker's five Algo really did move, from their left hand to their right, and the jar credited them for it.

Change a different field and defect two appears. The payment is genuine, and it goes to the jar, but somebody else sent it (a pending transaction lifted out of the mempool, or a friend's payment reused):

```python
>>> jar.send.tip(args=(someone_elses_payment,))
```

The tip is credited to `Txn.sender`, who is the caller, who is not the payer. Nothing about the group is malformed. The contract has two accounts in front of it and has assumed they are the same one without saying so.

*Predict: `tip` reads its payment through a typed parameter, and a group may hold up to sixteen transactions. Before reading on, say what happens if the attacker puts one real payment at index 0 and then two copies of `tip` behind it, hoping to be credited twice for the same money.*

The second copy fails, for a reason you did not write and should not rely on. PuyaPy lowers a typed group parameter *position-relatively*: `payment: gtxn.PaymentTransaction` compiles to a read of the transaction immediately before this one, followed by an assertion that its type is a payment. The second `tip` therefore reads the *first* `tip`, which is an application call, and aborts with `transaction type is pay`. The same lowering is why a `tip` submitted at group index 0 dies before any of your code runs: zero minus one is a subtraction, and it underflows.

Take the win and do not bank on it. What the parameter bought you is one position, chosen by the compiler and never stated in the source. It is not a group-size check, it does not stop the group being padded to sixteen, and a method that names its own index, `gtxn.PaymentTransaction(0)`, gets none of it.

Now the leaving side. The jar holds 5.1 Algo --- your honest five, plus the 0.1 that funded it into existence; the attacker's "tip" never arrived. Call `withdraw` as the owner:

```python
>>> jar.send.withdraw()
LogicError: Txn 5HRP...9QK2 had error 'inner tx 0 failed: overspend
(account KRT4...5DVQ, data {...}, tried to spend 5.100000A)'
at PC 204 and Source Line 166:
    ... 10 lines of TEAL trace ...
```

`overspend` is not a complaint about the minimum balance. `amount = app.balance` instructs the account to send every microAlgo it holds, and the inner transaction's fee is taken from that same account *before* the payment is applied. The jar is a thousand microAlgo short of its own instruction before the payment is attempted. That is defect four firing, with defect three standing immediately behind it.

Set the fee to zero and defect three has not moved. `app.balance` counts the hundred thousand microAlgo the account is required to keep in order to exist, and an account that keeps anything at all may not settle below that figure. Correcting only the fee leaves a `withdraw` that asks the jar to empty itself down to nothing, reserve included, which is not what "withdraw the balance" was ever meant to mean. Correcting only the subtraction is worse, because it looks right: `app.balance - app.min_balance` with the fee left in place instructs the account to pay a thousand microAlgo and then send 5 Algo, which would settle it at 99,000, a thousand under its own floor. So that version fails too, and not just for large amounts: for every amount, permanently, on a contract with no other way out.

That is all four. On this contract the fee drain is contained: `withdraw` is owner-only, so the drain is one owner paying a fee they did not know they were paying. Put the same line on a method anybody may call and it is a withdrawal with extra steps, at a thousand microAlgo a call, forever.

Now ship Example 7-1 anyway, and watch what the four defects cost once other people depend on the jar. It is reviewed by two people, it is deployed to MainNet, and it is linked from a profile page. Tips arrive, the counter climbs, and the block explorer confirms every deposit at the application address. Six weeks later the jar holds 33.3 Algo and you call `withdraw` for the first time. It fails --- the same `overspend` you just read, with a larger number in it --- and it will fail every time it is ever called. There is no admin method, no upgrade path, and no key: the application address has no private key, so no wallet anywhere can reach past the contract and move the money by hand. The 33.3 Algo is not stolen. It is somewhere nobody can go.

That is the defect you notice, and the diagnosis --- "there is a bug in `withdraw`" --- is true and nowhere near specific enough to act on, because two defects share that one visible failure. The audit that untangles them finds the other two, and both are worse. The jar's counter says 41.4 Algo across a hundred and nine tips. Only 33.2 Algo of that ever arrived (the account holds 33.3 because your 0.1 Algo of funding is in there too), and the missing 8.2 is thirty-one tips that were never paid to the jar at all: groups whose "tip" was a payment to the tipper's own account, credited anyway, so the leaderboard on the profile page has been ranking people by money they still have. Another sixteen tips were real, arrived, and were credited to somebody who had not sent them.

Four defects, one contract, and the same shape as the last chapter's: every one of them behaves perfectly on the happy path. A tip that is honestly paid, in a two-transaction group, by the person calling the method, is credited correctly. The jar was tested exclusively that way, by the person who wrote it and knew how it was meant to be used.

The rest of the chapter covers the contract as a sender, the contract as a receiver, the atomicity that ties both to the rest of the group, the assets a contract can hold, and who controls an asset and why a contract's own balance is the wrong number to keep books with.

## The Contract Has an Account
**An application controls an account whose address is derived from its ID, for which no private key exists, and the only transactions that account will ever send are the ones this code submits.**

**Example 7-2.** The account an application controls

<!-- finder: read the application account's address and spendable balance -->

```python
from algopy import ARC4Contract, Global, UInt64, arc4


class Treasury(ARC4Contract):
    """Reports the account this application controls.

    Every application has an address derived from its ID. No private
    key exists for it, so the only way value ever leaves it is an
    inner transaction that this code chose to submit.
    """

    @arc4.abimethod(readonly=True)
    def address(self) -> arc4.Address:
        return arc4.Address(Global.current_application_address)

    @arc4.abimethod(readonly=True)
    def held(self) -> UInt64:
        return Global.current_application_address.balance

    @arc4.abimethod(readonly=True)
    def spendable(self) -> UInt64:
        # Everything above the minimum balance. Sending more than this
        # does not overdraw the account; it fails the transaction.
        account = Global.current_application_address
        return account.balance - account.min_balance
```

Three read-only methods and no state. `Global.current_application_address` is the account, and the key line is the one in `spendable`: `account.balance - account.min_balance`. The balance is what the account holds. The minimum balance is what it may never go below: 100,000 microAlgo to exist, plus 100,000 for every asset it holds, plus the box charges from Chapter 5. The schema an application declares is *not* in that sum. As Chapter 4 established, an application's *global* schema and extra pages are billed to the account that created it, and its *local* schema is billed to each account that opts in; the application account pays for what it holds, not for what it declares. The difference between balance and minimum is the only figure a contract may actually spend, and computing it wrong is the tip jar's third defect.

The direction of that subtraction matters, and the compiler will not remind you. Chapter 6's rule applies here. `balance - min_balance` is safe on *this* account, because the protocol will not let a funded account settle below its own minimum. It is not safe as a habit. Apply the same shape to an account you do not control (a recipient, a beneficiary, an address that arrived as an argument) and you are subtracting two numbers whose order you have not established; an underflow ends the transaction with a message about arithmetic rather than about funding. The form that never has the problem is `balance >= min_balance + cost`, and the opt-in example later in this chapter is written that way.

*Predict: this contract has no methods that spend anything, holds no assets, and declares no state. On an application that was deployed and never funded, what do `held` and `spendable` return?*

Neither returns; both calls fail, and the reason generalises. `Account.balance` and `Account.min_balance` compile to `acct_params_get`, whose did-this-account-exist flag is nothing more sophisticated than *balance greater than zero*. PuyaPy asserts on that flag, so the failure the reader gets is `account funded`, an assertion nobody in this file wrote. An account holding nothing does not read as an account holding nothing; it reads as an account that is not there. An application's account is *not* funded by deployment. It comes into existence empty, which is why the first thing every deployment script in this book does after creating an application is pay its address enough to be useful. Fund it, and `min_balance` is 100,000 for this contract and `spendable` is whatever arrived above that.

::: {.gotcha #spendable-is-not-the-balance topic="Inner transactions" title="An application account's balance is not what it can spend"}
An inner payment of `app.balance` fails for every account that will still exist afterwards --- not for large amounts, for every amount. The fee comes out of the same account first, so the instruction is short by one fee before the payment is attempted; fix that with `fee=UInt64(0)` and the ledger still refuses to let the account settle below its minimum balance. Spend `app.balance - app.min_balance`, with the fee at zero so nothing is taken ahead of it.
:::

The two refusals read differently, and the difference decides where you go looking. The fee shortfall is reported by the AVM as `overspend`, with no mention of any minimum --- the misdirection the first pass ran into. The minimum-balance refusal arrives only when the group settles, comes from the ledger rather than from your program, and does name the figure. `fee=UInt64(0)` silences only the first: an account holding one asset owes 200,000 microAlgo, and a payment that would settle it below that is refused whatever the fee was.

One account slips past both refusals: an account holding nothing else at all can be emptied to zero and deleted. That is a closure, not a withdrawal, and not what `withdraw` was for.

The floor under the subtraction also moves. Opting into one more asset raises `app.min_balance` by 100,000 microAlgo and silently reduces what a previously-working withdrawal may send; the first exercise at the end of this chapter turns exactly that movement into a failing trace.

**Example 7-3.** Sending Algo out of the application account

<!-- finder: send Algo from a contract with an inner transaction -->

```python
from algopy import ARC4Contract, Account, Global, Txn, UInt64, arc4, itxn


class Faucet(ARC4Contract):
    """Sends Algo out of the application's own account."""

    @arc4.abimethod
    def pay(self, recipient: Account, amount: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        account = Global.current_application_address
        headroom = account.balance - account.min_balance
        assert amount <= headroom, "would breach the minimum balance"
        # `.submit()` runs the payment immediately, inside this call.
        # If it fails, this method fails, and nothing before it commits.
        itxn.Payment(
            receiver=recipient,
            amount=amount,
            fee=UInt64(0),
        ).submit()
        return headroom - amount
```

This is the diagram in contract form. `itxn.Payment(...).submit()` builds a payment and sends it immediately, in the middle of this method: not queued for later, not returned to the caller to sign. `.submit()` is what makes it real, and the comment above it states the consequence: if the payment fails, this method fails. There is no error to catch and no partial success to clean up, which is why the guard above it is an assertion rather than a branch.

The return value is deliberately *not* `account.balance`. Reading the balance back after submitting an inner payment is the obvious thing to write, and it makes the method's answer depend on the environment it ran in rather than on the arithmetic. `headroom - amount` is computed from figures established before the payment, so it is the same number wherever you run it.

**Example 7-4.** Making the caller pay for the contract's transactions

<!-- finder: charge the caller for a contract's inner transaction fees -->

```python
from algopy import ARC4Contract, Account, Global, Txn, UInt64, arc4, itxn

# One app call plus two inner payments. The contract asserts a floor of
# one min-fee each; the client's actual fee is not this product.
INNER_PAYMENTS = 2


class Splitter(ARC4Contract):
    """Pays two accounts, and makes the caller cover all three fees."""

    @arc4.abimethod
    def split(self, a: Account, b: Account, amount: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        needed = Global.min_txn_fee * UInt64(1 + INNER_PAYMENTS)
        assert Txn.fee >= needed, "cover the whole group"
        half = amount // UInt64(2)
        # `fee=UInt64(0)` is already PuyaPy's default. Writing it out
        # says the omission was a decision, not an oversight.
        itxn.Payment(receiver=a, amount=half, fee=UInt64(0)).submit()
        itxn.Payment(
            receiver=b,
            amount=amount - half,
            fee=UInt64(0),
        ).submit()
```

`fee: UInt64 | int = 0` is the declared default on every `itxn` builder in algorand-python. Leaving the field out does not produce a default fee; it produces a zero fee. **The danger is never an omitted fee. It is a fee somebody wrote a non-zero value into.** Writing `fee=UInt64(0)` explicitly changes no behaviour, and it turns an omission a reviewer has to assume was intentional into a line they can see was.

A zero fee is not free money. Algorand pools fees across an atomic group: the group is valid if the total fee paid across it meets the total minimum required, including every inner transaction any of them submits. So a zero-fee inner payment means somebody else in the group is covering it, and the line that matters is `assert Txn.fee >= needed`. One app call plus two inner payments is three transactions; `Global.min_txn_fee * 3` is the *floor* the contract can assert without baking in today's 1,000. The app call is the only one of the three a caller can attach a fee to. Omit the assertion and you have not created a vulnerability, only a method that fails at submission when the caller under-pays. Omit the `fee=UInt64(0)` and you have created one. The section on groups covers why the network lets one transaction pay for another's fee.

**Example 7-5.** A method that charges the contract a thousand microAlgo per call

<!-- finder: see how a non-zero inner fee drains a contract -->

```python
from algopy import ARC4Contract, Global, Txn, UInt64, arc4, itxn


class SelfFundedEcho(ARC4Contract):
    """Anyone may call this, and every call costs the app 1,000 microAlgo.

    The fee on an inner transaction is paid by the application account,
    never by the caller. A zero-Algo payment that charges itself a fee
    is a withdrawal with extra steps.
    """

    @arc4.abimethod
    def ping(self) -> None:
        itxn.Payment(
            receiver=Txn.sender,
            amount=UInt64(0),
            fee=Global.min_txn_fee,
        ).submit()
```

Eighteen lines, no authorization, and a zero-Algo payment, which looks harmless because it moves nothing. It moves 1,000 microAlgo per call out of the application account, forever, to nobody. A hundred thousand calls is 100 Algo, and the attacker's own cost is the outer fee they were going to pay anyway. The contract does not need to hold a treasury for this to matter: draining it to its minimum balance is enough to make every *other* inner transaction it wants to send start failing.

::: {.gotcha #inner-fee-zero topic="Inner transactions" title="A non-zero inner transaction fee is paid out of the contract's own balance"}
The fee on an inner transaction comes from the application account. `fee: UInt64 | int = 0` is already the default on every `itxn` builder, so the danger is a fee somebody wrote a non-zero value into, most often `Global.min_txn_fee`. On a public method that is an unbounded drain of one min-fee per call, and an account drained toward its minimum fails every other inner transaction it wants to send. Write `fee=UInt64(0)` explicitly, and make the caller cover the group with `assert Txn.fee >= Global.min_txn_fee * UInt64(N)` --- a floor, not the fee the client attaches. Chapter 8's `simulate` reports `group-usage`; that, not this product, is the client's fee.
:::

Back at the tip jar, these fix defects three and four: `withdraw` sends `app.balance - app.min_balance`, and its inner payment carries `fee=UInt64(0)` so that the owner's own transaction covers the network.

## Requiring the Other Half of the Deal
A contract cannot reach into an account and take anything. It has no authority over anybody's balance but its own, so every design that involves a user *giving* the contract something has the same shape: the user signs the transfer, the user signs the app call, the two travel together in a group, and the contract's entire job is to convince itself that the transfer it was handed is the transfer it wanted.

There are exactly four questions to ask of an incoming transfer, and a typed group parameter answers none of them: **which asset, how much, where it went, and whose it was.**

**Example 7-6.** Crediting a caller for Algo they sent in the same group

<!-- finder: accept and validate an Algo payment sent alongside a call -->

```python
from algopy import (ARC4Contract, Global, GlobalState, LocalState, Txn, UInt64,
                    arc4, gtxn)

MIN_DEPOSIT = 100_000


class Deposits(ARC4Contract):
    """Credits a caller for Algo they sent in the same group."""

    def __init__(self) -> None:
        self.total = GlobalState(UInt64(0))
        self.credited = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def deposit(self, payment: gtxn.PaymentTransaction) -> UInt64:
        app = Global.current_application_address
        # The parameter type pins the transaction's type and position.
        # It says nothing about where the money went, or whose it was.
        assert payment.receiver == app, "pay this application"
        assert payment.sender == Txn.sender, "fund your own balance"
        assert payment.amount >= UInt64(MIN_DEPOSIT), "below the minimum"
        held = self.credited.get(Txn.sender, UInt64(0))
        self.credited[Txn.sender] = held + payment.amount
        self.total.value += payment.amount
        return self.credited[Txn.sender]
```

The method makes three checks. `assert payment.receiver == app` catches a payment that went somewhere else, the check people skip because the group *looks* like it means what they want. `assert payment.sender == Txn.sender` catches a payment made by somebody other than the caller, skipped because nobody imagines the two accounts differing. `assert payment.amount >= MIN_DEPOSIT` is the one everybody remembers to write.

Cheapest and most decisive first is a good habit, but the reason to check the receiver before the amount is legibility, not cost: a reader who sees the destination checked on the first line stops wondering whether it was checked at all.

**Example 7-7.** The same method with the destination unchecked

<!-- finder: see a deposit method credit a payment that went elsewhere -->

```python
from algopy import ARC4Contract, LocalState, Txn, UInt64, arc4, gtxn


class LooseDeposits(ARC4Contract):
    """Credits the caller for a payment that may have gone anywhere.

    A payment to the attacker's own account satisfies this method just
    as well as a payment to the application, so the balance is free.
    """

    def __init__(self) -> None:
        self.credited = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def deposit(self, payment: gtxn.PaymentTransaction) -> UInt64:
        held = self.credited.get(Txn.sender, UInt64(0))
        self.credited[Txn.sender] = held + payment.amount
        return self.credited[Txn.sender]
```

`LooseDeposits` is `Deposits` with two assertions deleted, and it is the tip jar's first defect isolated. Its unit test says it plainly: the same self-payment, in the same group shape, is refused by one contract and credited by the other. The attacker's money never left their control and their position is real.

*Predict: `LooseDeposits` credits `payment.amount` for a payment that went to the attacker. What is the largest position an attacker can open, and what does it cost them?*

Whatever they can briefly hold, and roughly one fee. A payment to yourself of a million Algo costs a thousand microAlgo and leaves your balance exactly where it started.

**Example 7-8.** Accepting exactly one asset and refusing all the others

<!-- finder: validate an incoming ASA transfer against a stored asset id -->

```python
from algopy import (ARC4Contract, Asset, Global, GlobalState, LocalState, Txn,
                    UInt64, arc4, gtxn)


class TokenVault(ARC4Contract):
    """Accepts one specific ASA, and refuses every other one."""

    def __init__(self) -> None:
        self.token = GlobalState(UInt64(0))
        self.deposited = LocalState(UInt64)

    @arc4.abimethod
    def configure(self, token: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.token.value == UInt64(0), "already configured"
        self.token.value = token.id

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def deposit(self, transfer: gtxn.AssetTransferTransaction) -> UInt64:
        app = Global.current_application_address
        # Without the first assert, any worthless ASA buys a position.
        assert transfer.xfer_asset.id == self.token.value, "wrong asset"
        assert transfer.asset_receiver == app, "send it to this app"
        assert transfer.sender == Txn.sender, "fund your own balance"
        held = self.deposited.get(Txn.sender, UInt64(0))
        self.deposited[Txn.sender] = held + transfer.asset_amount
        return self.deposited[Txn.sender]
```

The same shape with a fourth question added, and the fourth is the dangerous one: `assert transfer.xfer_asset.id == self.token.value` refuses every asset except the one the contract was configured for. Anyone may create an asset on Algorand for a fee; an attacker can mint a trillion units of a token that nobody wants, in about a second, and if your vault checks the destination and the amount but not the identity, those units buy a real position.

The expected id comes from state: `configure` writes it once, guarded by both a creator check and an init-once flag, and `deposit` reads it. It is never a method argument. **An asset id supplied by the caller is not a check; it is a formality the caller performs on themselves.**

**Example 7-9.** The same vault with the asset unchecked

<!-- finder: see a vault credit a worthless asset as if it were the real one -->

```python
from algopy import ARC4Contract, Global, LocalState, Txn, UInt64, arc4, gtxn


class AnyTokenVault(ARC4Contract):
    """Checks that an asset arrived, never which asset it was.

    An attacker mints their own ASA for free, sends a billion units of
    it, and is credited exactly as if they had sent the real one.
    """

    def __init__(self) -> None:
        self.deposited = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def deposit(self, transfer: gtxn.AssetTransferTransaction) -> UInt64:
        app = Global.current_application_address
        assert transfer.asset_receiver == app, "send it to this app"
        held = self.deposited.get(Txn.sender, UInt64(0))
        self.deposited[Txn.sender] = held + transfer.asset_amount
        return self.deposited[Txn.sender]
```

`AnyTokenVault` checks the destination faithfully. The units really do arrive at the application account, which is what makes this one harder to spot in review than the missing-receiver bug: something did move, and the block explorer will happily show it.

::: {.gotcha #group-arg-is-not-a-check topic="Atomic groups" title="A typed group argument checks the type, never the contents"}
`payment: gtxn.PaymentTransaction` guarantees that the named slot holds a payment. It guarantees nothing about the receiver, the amount, the sender, or, for an asset transfer, which asset. A payment the caller sent to their own account satisfies the type perfectly, costs one fee, and leaves their balance where it started, so an unchecked deposit method hands out positions for free. Ask all four questions on every incoming transfer: `xfer_asset` against a stored id, `amount` against a floor, `receiver` against `Global.current_application_address`, and `sender` against `Txn.sender`. The asset id in particular must come from state your contract wrote, never from a method argument: an id the caller supplies is a formality the caller performs on themselves.
:::

**Example 7-10.** Refusing every group shape but the one intended

<!-- finder: bound the size and position of the group a method accepts -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4, gtxn

GROUP_SIZE = 2


class Escrow(ARC4Contract):
    """Reads the payment directly before it, and no other group shape."""

    def __init__(self) -> None:
        self.received = GlobalState(UInt64(0))

    @arc4.abimethod
    def claim(self) -> UInt64:
        # Two assertions doing two different jobs: the first says how
        # long the group is, the second says where in it this call sits.
        assert Global.group_size == UInt64(GROUP_SIZE), "expected two"
        assert Txn.group_index == UInt64(1), "the call goes second"
        # Position-relative, so the pair still works if it is ever
        # nested inside a larger group with the size check relaxed.
        payment = gtxn.PaymentTransaction(Txn.group_index - 1)
        app = Global.current_application_address
        assert payment.receiver == app, "pay this application"
        assert payment.sender == Txn.sender, "fund your own claim"
        self.received.value += payment.amount
        return self.received.value
```

Two assertions doing two different jobs. `Global.group_size == UInt64(GROUP_SIZE)` says how long the group is. `Txn.group_index == UInt64(1)` says where in it this call sits. Neither implies the other, and a method that reads a group position while asserting only one of them is not bounded.

`gtxn.PaymentTransaction(Txn.group_index - 1)` reads the transaction immediately before this one rather than the transaction at absolute index zero. Position-relative reads survive being nested in a larger group later, when the size check is deliberately relaxed; absolute reads do not.

**Example 7-11.** A claim that can be made as many times as the group is long

<!-- finder: see one payment credited sixteen times in a single group -->

```python
from algopy import ARC4Contract, Global, GlobalState, UInt64, arc4, gtxn


class ReplayableEscrow(ARC4Contract):
    """Reads transaction zero, and never asks how long the group is.

    One payment at index 0, followed by fifteen copies of this call,
    credits the same money sixteen times. The payment is real; the
    accounting is not.
    """

    def __init__(self) -> None:
        self.received = GlobalState(UInt64(0))

    @arc4.abimethod
    def claim(self) -> UInt64:
        payment = gtxn.PaymentTransaction(0)
        assert payment.receiver == Global.current_application_address
        self.received.value += payment.amount
        return self.received.value
```

`ReplayableEscrow` reads `gtxn.PaymentTransaction(0)` and never asks how long the group is. One real payment at index 0, followed by fifteen copies of `claim`, credits the same money sixteen times inside one atomic group, and every transaction in that group is individually valid, correctly signed, and does exactly what it says. The payment is real. The accounting is fiction.

::: {.gotcha #group-index-without-a-size-check topic="Atomic groups" title="A group index check without a group size check bounds nothing"}
Checking `Txn.group_index` says where your call sits; it says nothing about how many other transactions ride alongside it, and a group may hold sixteen. A method that reads a payment at a fixed index and never asserts `Global.group_size` can be called once per remaining slot against the same payment, crediting the same money up to sixteen times in one atomic group --- every transaction in which is valid, correctly signed, and honest about what it is. An attacker who cannot forge a transfer can still restructure the group around one, which is what makes the receiver and asset checks matter. Assert the size and the index together, and read neighbours position-relative (`Txn.group_index - 1`) rather than absolutely, so the pattern survives being nested later.
:::

Back at the tip jar, these fix defects one and two: `tip` bounds the group to two transactions, checks the payment's receiver against the application address, and checks its sender against the caller.

## All of It, or None of It
Figure 2-4 in Chapter 2 introduced the guarantee: a group of up to sixteen transactions either all commit or none do. What that means changes once your contract is one of the transactions and value is moving in the others. The note at the bottom of Figure 7-1 was this guarantee in a new costume: a rejection anywhere in the group undoes an inner payment along with everything else, because the payment was never a separate event.

The guarantee is about the *commit*, not about isolation. The transactions in a group execute in order against a single shared, copy-on-write view of the ledger, and only that view's final state reaches the ledger, and only if every transaction approved. So a write your contract performs is visible to a later transaction in the same group, and is discarded entirely if anything after it rejects.

That shared fate is also why fees pool. A group is validated as a unit, so the network asks only whether the total fee paid across it meets the total minimum required, counting every inner transaction any member of it submits. It has no reason to care which transaction carried the money, because there is no outcome in which some of them commit and the rest do not. That is what makes `fee=UInt64(0)` on an inner transaction legal rather than a way of getting something for nothing: somebody in the group paid, and the group is the only unit the fee rule has ever applied to.

Figure 7-2 draws both halves of it: the shared copy the transactions write into, and the single moment at which that copy either reaches the ledger or is thrown away.

![Figure 7-2. State writes are staged, not applied. The whole group approves or the ledger keeps none of it.](figures/group-commit.svg)

**Example 7-12.** Booking the withdrawal before making it

<!-- finder: order a state write and an inner payment without a rollback path -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4, itxn


class AllOrNothing(ARC4Contract):
    """Books the withdrawal first, then makes it. Both, or neither."""

    def __init__(self) -> None:
        self.paid_out = GlobalState(UInt64(0))

    @arc4.abimethod
    def withdraw(self, amount: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        # The counter moves before the money does. If the payment below
        # fails --- or if any later transaction in the group fails ---
        # this assignment is discarded along with it.
        self.paid_out.value += amount
        itxn.Payment(
            receiver=Txn.sender,
            amount=amount,
            fee=UInt64(0),
        ).submit()
        return self.paid_out.value
```

`self.paid_out.value += amount` runs *before* the payment it accounts for. In most runtimes that ordering leaves a window: the state is updated and the transfer then fails. Here there is no window, and the comment says why. If the payment fails, or if any later transaction in the group fails, the assignment is discarded along with it. There is no state to unwind because there is no state until the whole group commits.

**Do not write rollback paths, compensating updates, or partial-failure handling into an AVM contract.** There is no partial failure to handle. Write the state in whatever order reads most clearly, and let the group be the transaction boundary it already is.

*Predict: Algorand has no reentrancy: an inner transaction cannot call back into the contract that submitted it. Given that, and given that a failed group leaves no state behind to clean up, is there any correctness reason left to prefer one ordering of a state write and an inner transaction over the other?*

Not for safety, no. One reason is left, and it is arithmetic: a figure derived *from* other state has to be computed after that state is current, or it is derived from a stale number. In this contract nothing is derived from anything, so the ordering genuinely does not matter. In the AMM and the farming projects it will, because those contracts keep running totals that every per-user payout is measured against, and a payout computed before the total is brought up to date is measured against last time's answer. File that under arithmetic and never under safety; read it as a reentrancy guard and you will contort clear code against a threat the AVM does not have.

**Example 7-13.** Forwarding money that arrived moments earlier

<!-- finder: take a fee from an incoming payment and forward the remainder -->

```python
from algopy import (ARC4Contract, Account, Global, Txn, UInt64, arc4, gtxn,
                    itxn)

FEE_BASIS_POINTS = 50


class Forwarder(ARC4Contract):
    """Takes a cut, forwards the rest, and holds no float.

    The Algo leaving in the inner payment arrived in the same group,
    moments earlier. The application account is a conduit here, not a
    treasury: nothing accumulates in it between calls.
    """

    @arc4.abimethod
    def forward(
        self, payment: gtxn.PaymentTransaction, recipient: Account
    ) -> UInt64:
        app = Global.current_application_address
        assert Global.group_size == UInt64(2), "payment, then call"
        assert payment.receiver == app, "pay this application"
        assert payment.sender == Txn.sender, "forward your own money"
        cut = payment.amount * UInt64(FEE_BASIS_POINTS) // UInt64(10_000)
        itxn.Payment(
            receiver=recipient,
            amount=payment.amount - cut,
            fee=UInt64(0),
        ).submit()
        return cut
```

Both halves of the chapter in one method. A payment arrives in the group and is validated for destination, sender, and group shape; a cut is computed with Chapter 6's ordering, multiply before divide; and the remainder leaves in an inner payment with a zero fee. The application account holds nothing between calls (a conduit, not a treasury), which is why `Forwarder` needs no funding beyond its bare minimum balance.

Integer division floors in `cut = payment.amount * UInt64(FEE_BASIS_POINTS) // UInt64(10_000)`, so the dust from every fractional microAlgo stays with the contract rather than with the recipient. That is the correct direction, always: rounding that favours the caller is a rounding error an attacker can call in a loop.

**Example 7-14.** Two asset arguments that must not be one asset

<!-- finder: reject a pool bootstrapped with the same asset on both sides -->

```python
from algopy import ARC4Contract, Asset, Global, GlobalState, Txn, UInt64, arc4


class Pair(ARC4Contract):
    """Registers a two-asset pool, and insists the two are different."""

    def __init__(self) -> None:
        self.asset_a = GlobalState(UInt64(0))
        self.asset_b = GlobalState(UInt64(0))

    @arc4.abimethod
    def bootstrap(self, a: Asset, b: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.asset_a.value == UInt64(0), "already bootstrapped"
        # The whole example. Two arguments of the same type are two
        # names, not two things; nothing stops them naming one asset.
        assert a.id != b.id, "a pair needs two different assets"
        self.asset_a.value = a.id
        self.asset_b.value = b.id
```

`assert a.id != b.id` is the whole example. Two arguments of the same type are two *names*; nothing in the type system, the ABI, or the AVM makes them two things. Every later method in a pool contract reads `asset_a` and `asset_b` as opposing sides of a trade, and each of those methods is correct in isolation.

*Predict: `SelfPair` is `Pair` with that one assertion deleted, and it stores `asset_a` and `asset_b` as the same id. Before you read it, say what a later `swap` method (individually correct, and one you will not see) computes when the asset going in and the asset coming out are one asset. Then put an order of magnitude on what that is worth to whoever notices first.*

**Example 7-15.** The pool that accepts an asset against itself

<!-- finder: see the one-line omission behind Tinyman V1's $3M exploit -->

```python
from algopy import ARC4Contract, Asset, Global, GlobalState, Txn, UInt64, arc4


class SelfPair(ARC4Contract):
    """Accepts a pool of an asset against itself.

    Every later method reads `asset_a` and `asset_b` as two sides of a
    trade. When they are one asset, a deposit on one side is instantly
    withdrawable from the other, at whatever rate rounding allows.
    """

    def __init__(self) -> None:
        self.asset_a = GlobalState(UInt64(0))
        self.asset_b = GlobalState(UInt64(0))

    @arc4.abimethod
    def bootstrap(self, a: Asset, b: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        self.asset_a.value = a.id
        self.asset_b.value = b.id
```

The deleted assertion is the only difference between the two contracts, and the deletion is roughly a three-million-dollar mistake: this is the core of the Tinyman V1 exploit of January 2022, reduced to the line that was missing. When both sides name one asset, a deposit on one side is instantly withdrawable from the other at whatever rate the pricing maths happens to produce, and the pricing maths was never wrong.

::: {.gotcha #two-asset-args-can-be-one-asset topic="ASAs" title="Two asset arguments may name the same asset"}
Two parameters of type `Asset` are two names, not two things, and neither the ABI nor the AVM will stop a caller passing one asset for both. In a pool contract, every later method reads the two as opposing sides of a trade; with one asset on both sides, a deposit becomes instantly withdrawable from the other side at whatever the pricing arithmetic produces. This is the core of the Tinyman V1 exploit of January 2022, worth roughly three million dollars, and the fix is `assert a.id != b.id` in the method that stores them. The same reasoning applies to any pair of same-typed arguments that the contract will later treat as distinct: two accounts, two boxes, two application ids.
:::

None of this changes the jar directly: it has one state write and one inner payment and would behave identically under any ordering. But the group-size assertion the previous section added is meaningful only because groups are the unit of commit.

## Assets a Contract Can Hold
An Algorand Standard Asset is a first-class ledger object, not a contract. Creating one, holding one, and sending one are transaction types the protocol implements directly, which means a contract does all three with inner transactions and none of it requires a token contract to exist.

Three rules govern every asset a contract did not create for itself. An account holds an asset only after opting in. Opting in costs 100,000 microAlgo of minimum balance, per asset, held for as long as the holding exists. And a transfer to an account that has not opted in fails, taking the rest of its group down with it. An asset's creator is opted in from the moment the asset exists and never submits an opt-in of its own, which is the first example below and the one exception you will meet.

**Example 7-16.** Creating an asset from a contract

<!-- finder: mint an ASA whose creator is the application account -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4, itxn

TOTAL_UNITS = 1_000_000_000_000
DECIMALS = 6


class Minter(ARC4Contract):
    """Creates one ASA and remembers its id.

    The application account becomes the asset's creator and holds the
    entire supply, so it needs 100,000 microAlgo of minimum balance
    for the holding before this call can succeed.
    """

    def __init__(self) -> None:
        self.token = GlobalState(UInt64(0))

    @arc4.abimethod
    def mint(self) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.token.value == UInt64(0), "already minted"
        created = itxn.AssetConfig(
            asset_name=b"Tip Jar Token",
            unit_name=b"TIP",
            total=UInt64(TOTAL_UNITS),
            decimals=UInt64(DECIMALS),
            manager=Global.current_application_address,
            fee=UInt64(0),
        ).submit()
        self.token.value = created.created_asset.id
        return self.token.value
```

`itxn.AssetConfig` with no `config_asset` creates an asset; `created_asset.id` on the result is how you learn its id, and storing that id immediately is not optional bookkeeping: it is the only thing that lets every later method check what it is being handed.

The application account becomes the creator, receives the entire supply, and is opted in automatically, which is why the docstring names the 100,000 microAlgo. The creator of an asset is always opted into it and cannot close out of it while the asset exists.

*Predict: `mint` is guarded by a creator check and an init-once flag. `manager` is set to the application address and no `reserve`, `freeze`, or `clawback` is given. What are those three set to, and can they be set later?*

All three are the zero address, and no, they cannot. A role omitted from the creating `AssetConfig` is cleared, and a cleared role on an Algorand asset is permanent. The next section has the rest of the answer.

**Example 7-17.** Opting a contract into somebody else's asset

<!-- finder: opt an application account into an ASA it did not create -->

```python
from algopy import (ARC4Contract, Asset, Global, GlobalState, Txn, UInt64,
                    arc4, itxn)

OPT_IN_MBR = 100_000


class Holder(ARC4Contract):
    """Opts the application account into an ASA it did not create.

    An account holds an asset only after a zero-amount transfer to
    itself. A contract does that for itself with an inner transaction;
    it is the one opt-in on Algorand that needs nobody's signature.
    """

    def __init__(self) -> None:
        self.token = GlobalState(UInt64(0))

    @arc4.abimethod
    def opt_in_to(self, token: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.token.value == UInt64(0), "already holding one"
        app = Global.current_application_address
        # The 100,000 microAlgo of new minimum balance has to already
        # be in the account, or the transfer below fails.
        assert app.balance >= app.min_balance + UInt64(OPT_IN_MBR), "fund me"
        itxn.AssetTransfer(
            xfer_asset=token,
            asset_receiver=app,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()
        self.token.value = token.id
```

An opt-in is a zero-amount transfer of the asset to yourself. That is the entire mechanism, for every account on Algorand, and a contract performs it for itself with an inner transaction: the one opt-in on the chain that requires nobody's signature.

The assertion matters more than the transfer: `assert app.balance >= app.min_balance + UInt64(OPT_IN_MBR)`. Opting in raises the account's own minimum balance by 100,000 microAlgo, and an account that cannot afford its new minimum cannot complete the opt-in. The form is `balance >= min_balance + cost`, not `balance - min_balance >= cost`, which is Chapter 5's rule and Chapter 6's reason. The second form is a subtraction whose safety rests on an invariant you have asserted rather than one the language guarantees; it is correct exactly when the account is at or above its minimum, which is the thing the line was written to find out. Get it wrong (an account below its floor, an address handed in as an argument, a minimum that rose since you last looked) and the transaction ends with a message about arithmetic rather than about funding. The addition never has a wrong answer to give.

**Example 7-18.** Sending asset units out of the application account

<!-- finder: transfer ASA units from a contract to an account -->

```python
from algopy import (ARC4Contract, Account, Asset, Global, Txn, UInt64, arc4,
                    itxn)


class Distributor(ARC4Contract):
    """Sends units of an ASA out of the application account.

    Identical in shape to an inner payment, with three fields renamed.
    The receiver must already hold the asset or the transfer fails.
    """

    @arc4.abimethod
    def send(self, token: Asset, recipient: Account, amount: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        app = Global.current_application_address
        assert amount <= token.balance(app), "more than the app holds"
        itxn.AssetTransfer(
            xfer_asset=token,
            asset_receiver=recipient,
            asset_amount=amount,
            fee=UInt64(0),
        ).submit()
```

Structurally identical to Example 7-3 with three fields renamed: `xfer_asset` names the asset, `asset_receiver` the destination, `asset_amount` the quantity. The guard is the asset analogue of the headroom check: `token.balance(app)` is what the application holds of this asset, and there is no minimum-balance carve-out to subtract, because an asset holding has no reserved floor.

One sharp edge in that guard: **`token.balance(account)` fails if that account has not opted in.** It does not return zero. A contract that has not opted into the asset it is being asked to send gets no clean refusal from this assertion; it gets a failed transaction with a message about a missing holding.

**Example 7-19.** Refusing a recipient who cannot receive the asset

<!-- finder: check that a recipient has opted in before sending them an asset -->

```python
from algopy import (ARC4Contract, Account, Asset, Global, GlobalState, Txn,
                    UInt64, arc4, itxn)

REWARD_UNITS = 1_000


class Rewards(ARC4Contract):
    """Refuses to pay a recipient who cannot receive the asset.

    Without the check the transfer still fails and the group still
    rolls back --- but the caller reads a ledger error, not a sentence.
    """

    def __init__(self) -> None:
        self.token = GlobalState(UInt64(0))

    @arc4.abimethod
    def configure(self, token: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.token.value == UInt64(0), "already configured"
        self.token.value = token.id

    @arc4.abimethod
    def reward(self, recipient: Account) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        token = Asset(self.token.value)
        # A boolean for any account; token.balance would fail instead.
        assert recipient.is_opted_in(token), "recipient must opt in first"
        itxn.AssetTransfer(
            xfer_asset=token,
            asset_receiver=recipient,
            asset_amount=UInt64(REWARD_UNITS),
            fee=UInt64(0),
        ).submit()
        return UInt64(REWARD_UNITS)
```

`recipient.is_opted_in(token)` is the primitive the previous example's warning was pointing at. It takes an account and an asset and returns a boolean, for any account, opted in or not, which is the whole of the difference. When you want the holding *and* the gate in one read, `op.AssetHoldingGet.asset_balance(account, asset)` returns a two-tuple of the balance and a did-this-holding-exist flag, and you branch on the flag rather than assert on it.

The check is about error messages, not about safety. Without it, the inner transfer fails, the app call fails, and the whole group rolls back; the money is exactly as safe either way. What changes is what the caller reads: a sentence somebody wrote for them, or a ledger error about an asset id they have to go look up. **A check that only improves the failure message still earns its line.**

Two things in this contract are not about the gate: `reward` is creator-only, and the asset id comes from state that `configure` wrote once. Leaving them out would make the example exploitable rather than minimal. A version that took the asset as a method argument and let anybody call it would hand out a thousand units of *whatever asset the caller named*, which is the receiving section's rule doing damage a few pages after it was stated.

**Example 7-20.** Giving up a holding to recover the minimum balance

<!-- finder: close a contract out of an asset and recover its 100,000 MBR -->

```python
from algopy import ARC4Contract, Asset, Global, Txn, UInt64, arc4, itxn


class Retiring(ARC4Contract):
    """Gives up a holding and recovers the 100,000 microAlgo.

    `asset_close_to` sends the entire remaining balance whatever
    `asset_amount` says. The creator is always opted in.
    """

    @arc4.abimethod
    def stop_holding(self, token: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        itxn.AssetTransfer(
            xfer_asset=token,
            asset_receiver=token.creator,
            asset_amount=UInt64(0),
            asset_close_to=token.creator,
            fee=UInt64(0),
        ).submit()
```

Closing to the creator rather than to yourself is not a stylistic choice. The ledger requires the holding to be zero *after* the close, so closing to yourself is valid only when the balance is already zero. A non-zero balance closed to self is rejected, and the close-out that was supposed to reclaim the 100,000 microAlgo fails with it.

`asset_close_to` is the field that ends a holding, and it does not care what `asset_amount` says: it sends the entire remaining balance to the named account and releases the 100,000 microAlgo. This example sends the remainder to `token.creator`, which is safe because the creator of an asset is always opted into it, so the close-out cannot fail for want of a holding on the other end.

The jar does not need any of this yet. It is the material the jar would need first if it were to accept tips in a token rather than in Algo: an opt-in, a stored asset id, and one more question on every incoming transfer.

## Who Controls an Asset, and What Your Ledger Is
Every ASA carries four addresses, and each one is an authority somebody holds over the asset after it exists. They are visible to anybody with a block explorer, and the decisions you make about them are among the few decisions on Algorand that cannot be revised.

An asset carries numbers as well as addresses, and two of them decide whether an amount means what you think:

```python
supply = token.total          # in the asset's smallest unit
places = token.decimals       # how many of those make one whole unit
```

`total` is denominated in the smallest unit, so a token with `total=1_000_000` and `decimals=6` has a supply of one. Reading either requires the asset to be available to the transaction, exactly as Chapter 11's reference list requires for everything else. A contract that reads an asset it was merely told about aborts with `unavailable Asset`, and does so only once something other than the default client assembles the call, since algokit-utils pads the reference list for you.

**Example 7-21.** An asset's four authorities, and ending one of them

<!-- finder: reconfigure an ASA's roles and permanently clear its clawback -->

```python
from algopy import ARC4Contract, Asset, Global, Txn, UInt64, arc4, itxn


class Roles(ARC4Contract):
    """Names an asset's four authorities, and ends one of them.

    Manager reconfigures, reserve is a label, freeze can suspend an
    account's holding, and clawback can move units without the
    holder's signature. Clearing a role address is permanent.
    """

    @arc4.abimethod
    def renounce_clawback(self, token: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        # An AssetConfig writes all four roles at once. Every address
        # you want to survive has to be named again here; `clawback`
        # is left out on purpose, and cannot be restored afterwards.
        itxn.AssetConfig(
            config_asset=token,
            manager=token.manager,
            reserve=token.reserve,
            freeze=token.freeze,
            fee=UInt64(0),
        ).submit()
```

Two of the four matter to anyone who merely *holds* the asset, and they are the pair custody questions turn on. `freeze` may suspend a specific account's holding, so that units exist but cannot move. `clawback` may move units out of any account without that account's signature. The other two are administrative --- `manager` may reconfigure the asset, which includes reassigning the other three roles, and `reserve` is a label with no protocol power at all, marking holdings that tooling should read as un-circulated supply --- and this chapter needs nothing more from either.

`clawback` is the one to sit with. **An asset with a clawback address is an asset whose holders do not fully control their own units, and a contract holding the clawback address is custody, on-chain, legible to anyone who looks.** There are legitimate reasons for it (regulated instruments, ticketing, recoverable credentials); the point is not to avoid it but to know you have chosen it.

The detail in `renounce_clawback` is a property of `AssetConfig` rather than of clawback: **an asset reconfiguration writes all four role addresses at once, and any role you leave out is set to the zero address, permanently.** There is no partial update. Every role you want to survive has to be named again in every reconfiguration, which is why the example names three of them explicitly, omits exactly one on purpose, and cannot undo it. Nor can anything else: a role you read as blank and re-submit as blank stays blank, so a reconfiguration built from the asset's current on-chain state can only ever preserve or destroy, never restore. The only source that can tell you a role was *supposed* to be there is a record you kept yourself.

**Example 7-22.** Moving an asset out of an account that signed nothing

<!-- finder: perform a clawback transfer from a contract -->

```python
from algopy import (ARC4Contract, Account, Asset, Global, Txn, UInt64, arc4,
                    itxn)


class Recall(ARC4Contract):
    """Moves an asset out of an account that signed nothing.

    `asset_sender` is the field that makes this a clawback, and it
    works only while the app is the asset's clawback address.
    """

    @arc4.abimethod
    def recall(self, token: Asset, victim: Account, amount: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        app = Global.current_application_address
        assert token.clawback == app, "not the clawback address"
        itxn.AssetTransfer(
            xfer_asset=token, asset_sender=victim, asset_receiver=app,
            asset_amount=amount, fee=UInt64(0),
        ).submit()
```

`asset_sender` is the field that makes an asset transfer a clawback. Set it and the units come out of that account rather than out of the sender's; leave it out and the same builder sends the contract's own units. One field is the entire distance between the two, which is a good argument for never writing `asset_sender` unless the line above it says why.

The guard `assert token.clawback == app` is there because the operation silently becomes impossible the moment somebody reconfigures the asset, which the previous example showed can happen by omission rather than by intent.

::: {.note #asset-roles-iou topic="ASAs" title="Where the other two roles earn their keep"}
`manager` and `reserve` are IOUs in this chapter, and Chapter 12 redeems them. Its vesting NFT keeps `manager` on the contract, because destroying the NFT when a schedule is revoked is a manager operation; the same chapter shows ARC-19 repurposing `reserve` as a metadata pointer. `clawback` is spent there too: Example 7-22's `asset_sender`, at project scale, moving a revoked NFT out of its holder's account.
:::

**Example 7-23.** A vault that tracks what it was given

<!-- finder: account for deposits with stored state rather than with the balance -->

```python
from algopy import (ARC4Contract, Global, GlobalState, LocalState, Txn, UInt64,
                    arc4, gtxn, itxn)


class Vault(ARC4Contract):
    """Tracks what it was given, not what it happens to hold.

    `self.reserve` is the ledger. The account's balance also counts
    the minimum balance, the funding that got the app running, and
    anything a stranger has sent it. None of that is anyone's money.
    """

    def __init__(self) -> None:
        self.reserve = GlobalState(UInt64(0))
        self.credited = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def deposit(self, payment: gtxn.PaymentTransaction) -> UInt64:
        app = Global.current_application_address
        assert payment.receiver == app, "pay this application"
        assert payment.sender == Txn.sender, "fund your own balance"
        self.reserve.value += payment.amount
        held = self.credited.get(Txn.sender, UInt64(0))
        self.credited[Txn.sender] = held + payment.amount
        return self.reserve.value

    @arc4.abimethod
    def withdraw(self, amount: UInt64) -> UInt64:
        # Checked against the books, never against `app.balance`.
        assert amount <= self.credited[Txn.sender], "more than you put in"
        self.credited[Txn.sender] -= amount
        self.reserve.value -= amount
        itxn.Payment(receiver=Txn.sender, amount=amount, fee=UInt64(0)).submit()
        return self.reserve.value
```

`self.reserve` is the ledger. `app.balance` is a fact about an Algorand account, and it counts the minimum balance, whatever the deployer sent to get the contract running, and anything at all that a stranger decided to send it. None of that is anybody's claim on anything, and the assertion in `withdraw` is checked against `self.credited`, never against the account.

**Your balance is what you hold. Your ledger is what you owe. A contract that confuses them has no way to tell a deposit from a donation.**

**Example 7-24.** The same vault priced off its balance

<!-- finder: see a donation re-price every position in a vault -->

```python
from algopy import ARC4Contract, Global, LocalState, Txn, UInt64, arc4, itxn


class DonatableVault(ARC4Contract):
    """Prices every share off the balance instead of off the books.

    A stranger's donation re-prices every position at once.
    """

    def __init__(self) -> None:
        self.shares = LocalState(UInt64)

    @arc4.abimethod
    def withdraw(self, share: UInt64) -> UInt64:
        assert share <= self.shares[Txn.sender], "more than you hold"
        app = Global.current_application_address
        payout = app.balance * share // UInt64(1_000_000)
        self.shares[Txn.sender] -= share
        itxn.Payment(receiver=Txn.sender, amount=payout, fee=UInt64(0)).submit()
        return payout
```

`payout = app.balance * share // UInt64(1_000_000)` prices every share off the account. Send the account money and every open position is worth more, instantly, without the accounts holding them doing anything at all. That sounds like a gift. It is an attack, because the arithmetic runs in both directions and the first depositor into an empty pool can set the price to whatever they like. Chapter 13 meets it again as the first-depositor donation attack, with a minimum-liquidity lock that only looks arbitrary if you have not seen this example.

::: {.gotcha #balance-is-not-a-ledger topic="Global and local state" title="An account balance is not an accounting record"}
`Global.current_application_address.balance` tells you what the account holds. It does not say what anyone is owed: it also counts the minimum balance, the funding that got the contract running, fee refunds, and anything a stranger chose to send. A contract that prices positions off its balance can have every position re-valued by an outsider making a payment, which in an empty pool means the first depositor sets the price to whatever they like: the first-depositor donation attack, met again in Chapter 13. Keep the ledger in state you write, check withdrawals against the ledger, and treat the balance as a liveness signal at most. When the two disagree, the difference is information --- fees you paid, donations you received, or a bug.
:::

The jar makes a near-miss of this mistake. `tips_received` is a real counter, faithfully incremented, and `withdraw` ignores it and sends the balance instead, so nothing the counter says can lose money. The two numbers still disagree: the counter says 41.4 Algo, the account holds 33.3. That gap is 8.1 Algo, two independent things pulling in opposite directions: 8.2 Algo of tips the jar counted and never received, less the 0.1 Algo of funding the deployer sent that no tip ever accounted for. Neither number is lying about what it measures. The contract never decided which of the two it was keeping books with, and none of the four corrections decides it either. The fix is to pick one number as authoritative and never consult the other.

## The Tip Jar, Finished
The fee and the subtraction are a single repair. The group bound answers no defect on the list: the jar never asked the question at all, and it is here because the other two `tip` checks mean nothing without it. No new methods. The spine of the diff follows, with everything unchanged elided; the whole corrected contract follows it as Example 7-25.

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

Two things did change and are not shown. The class docstring described four defects and now describes four corrections. And `withdraw`'s docstring gains one word, *spendable*, the smallest edit in the file and the one that would have prevented all of this. The import line, for its part, needed nothing new: every name the corrections use was already there for something else, which is part of why these defects are easy to ship.

**Example 7-25.** The tip jar, corrected

<!-- example: examples/moving_value/tip_jar_fixed.py mode=compile -->
<!-- finder: see the tip jar with all four defects fixed -->

```python
from algopy import (ARC4Contract, Global, GlobalState, LocalState, Txn, UInt64,
                    arc4, gtxn, itxn)

TIP_GROUP_SIZE = 2


class TipJar(ARC4Contract):
    """Collects tips for one creator and pays them out on request.

    The four corrections over the first draft: the group's shape is
    pinned before any payment field is trusted; a tip counts only if
    the money reached the jar; the credit goes to the account that
    paid it; and the withdrawal sends only what is spendable, with
    the network's fee carried by the caller rather than the jar.
    """

    def __init__(self) -> None:
        self.owner = GlobalState(Global.creator_address)
        self.tips_received = GlobalState(UInt64(0))
        self.tipped = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def tip(self, payment: gtxn.PaymentTransaction) -> UInt64:
        """Credit the caller for a tip they sent in this group."""
        assert Global.group_size == UInt64(TIP_GROUP_SIZE), "pay, then call"
        app = Global.current_application_address
        assert payment.receiver == app, "tip this jar, not an account"
        assert payment.sender == Txn.sender, "credit goes to the payer"
        assert payment.amount >= UInt64(1_000), "tips start at 0.001 Algo"
        given = self.tipped.get(Txn.sender, UInt64(0))
        self.tipped[Txn.sender] = given + payment.amount
        self.tips_received.value += payment.amount
        return self.tips_received.value

    @arc4.abimethod
    def withdraw(self) -> UInt64:
        """Send the jar's spendable contents to the owner."""
        assert Txn.sender == self.owner.value, "owner only"
        app = Global.current_application_address
        amount = app.balance - app.min_balance
        itxn.Payment(
            receiver=self.owner.value,
            amount=amount,
            fee=UInt64(0),
        ).submit()
        return amount

    @arc4.abimethod(readonly=True)
    def total(self) -> UInt64:
        return self.tips_received.value
```

Redeploy and run the same three things that failed. This is an **on-chain run** against the same LocalNet:

```python
>>> jar.send.opt_in.tip(args=(pay(jar.app_address, 5_000_000),))
>>> jar.send.tip(args=(pay(attacker.address, 5_000_000),))
LogicError: Txn KQ7T...4WM3 had error 'Runtime error when executing TipJar
(appId: 1211) in transaction 1: tip this jar, not an account'
at PC 143 and Source Line 90:
    ... 10 lines of TEAL trace ...
>>> jar.send.withdraw()
5000000
```

That middle message is the shape you will read for the rest of this book. The sentence inside the quotes is yours: `tip this jar, not an account` is the comment on the assertion, carried through compilation into the ARC-56 file beside the program counter it belongs to, and substituted back in by the client when the failure comes home. The AVM itself said only that an assertion at PC 143 failed. Everything legible in that line is legible because somebody wrote a comment on an `assert`.

**Correction one: bound the group.** `Global.group_size == UInt64(TIP_GROUP_SIZE)` is the assertion that gives the other two their meaning. It is first in the method for legibility rather than cost: a reader who wants to know what shape of group this method accepts should not have to reconstruct it from three separate checks further down.

**Correction two: check where the money went.** `payment.receiver == app` is one comparison, and it is the difference between a tip jar and a leaderboard of people's own money. A single test written from the attacker's side would have caught it, which is the general lesson: the happy-path test and the adversarial test are not the same test with different numbers.

**Correction three: check whose money it was.** `payment.sender == Txn.sender` says out loud that the payer and the caller are the same account. If you genuinely want third-party sponsorship (somebody tipping on another person's behalf), model the beneficiary as an explicit argument rather than leaving it implied by an unasserted coincidence.

**Correction four: leave the minimum balance where it belongs, and stop paying the network out of the jar.** `app.balance - app.min_balance` and `fee=UInt64(0)` are two lines and two different ideas, grouped because they are the same defect from the account's point of view: the contract was treating its own balance as though every microAlgo in it were spendable. The transcript only ever showed the two of them failing together; patch one and the other is still there. This is also where the jar finally picks its authoritative number: the *balance* wins, because the commission pays out the float rather than the tally --- `tips_received` stays a statistic, and the two are allowed to disagree by exactly the unsolicited payments the counter never sees.

One omission is deliberate: `withdraw` carries no `assert Txn.fee >= Global.min_txn_fee * UInt64(2)`. The fee section offered one and said you could skip it; this contract skips it. Nothing is at risk either way, because with `fee=UInt64(0)` on the inner payment a group whose outer fees do not cover it is rejected at submission and no money moves. The assertion buys a legible refusal instead of a node-level one, and on an owner-only method the only person it would explain anything to is the owner. On a method anybody may call, write it. The rule is not *always assert the pooled fee*; it is *decide who is reading the failure, and whether they will understand it*.

That is the finished jar. Against the commission:

1. Accept tips of 0.001 Algo or more from anyone, and report the running total --- yes; the honest tip cleared unchanged, and `total` still answers.
2. Count a tip only if the money reached the jar --- yes; the self-payment that used to inflate the counter now dies with `tip this jar, not an account`.
3. Credit the account that paid --- yes; `payment.sender == Txn.sender` refuses a borrowed payment with `credit goes to the payer`.
4. Let the creator, and only the creator, withdraw --- yes; the one requirement the first pass already met.
5. Hold the float safely --- yes; `withdraw` returned 5000000, everything above the account's floor, with the network's fee carried by the owner's own transaction.

Five for five, and for the first time the jar's two numbers agree: the counter says five Algo arrived, and five Algo is what came out.

Two rules generalize past this chapter.

The first is about receiving: **a transaction in your group is evidence of nothing until you have checked which asset, how much, where it went, and whose it was, plus the group's size, which decides whether those four answers can be trusted at all.** The typed parameter is a convenience for reading fields, not a validation.

The second is about sending: **value leaves a contract only through an inner transaction it chose to submit, so every departure is a line of code you can point at.** That makes the audit tractable. Find every `.submit()`, and for each one ask who is authorized to reach it, what bounds the amount, and who pays the fee.

## Retrieval
Answer these from memory before moving on. Four of them reach back into earlier chapters on purpose.

1. What is the address an application controls derived from, and where is its private key?
2. Name the four questions a contract must ask of an incoming payment or asset transfer. Then say exactly what a typed group parameter such as `payment: gtxn.PaymentTransaction` does guarantee, and how much of those four it covers.
3. A method asserts `Txn.group_index == UInt64(1)` and reads `gtxn.PaymentTransaction(0)`. What can an attacker still do, and how many times?
4. What is the default value of `fee` on an `itxn` builder, and who pays it when you set it to `Global.min_txn_fee` instead?
5. An asset reconfiguration sets `manager` and `freeze` and nothing else. What has happened to `reserve` and `clawback`, and what would it take to restore them?
6. Why does `Asset.balance(account)` need a companion check, and what is the non-failing primitive that answers "is this account opted in?"
7. *(From Chapter 2)* You already knew an application address has no private key. Say what that implies about a contract whose only withdrawal method can never succeed.
8. *(From Chapter 6)* `app.balance - app.min_balance` is a subtraction with no guard in front of it. Say what has to be true of the account for it to be safe, and give the form of funding check that is safe without needing that to be true.
9. *(From Chapter 5)* Opting into an asset raises the application account's minimum balance by 100,000 microAlgo. Which of the box chapter's rules is that the same rule as, and what does it imply about a withdrawal method that worked yesterday?
10. *(From Chapter 4)* A vault stores each depositor's credit in local state. Say what happens to the contract's books when a depositor clears their local state, and which of this chapter's two numbers now disagrees with the other.

## Exercises
1. An application account holds 2,400,000 microAlgo, has opted into three assets, and has no boxes and no local or global schema beyond two `UInt64` globals. Assume a contract that has both Example 7-3's `pay` and Example 7-17's `opt_in_to`, deployed to that account. The three holdings it already has did not arrive through `opt_in_to`, so its init-once flag is clear and the fourth opt-in is allowed to run.

   a. **(Trace)** Work out the account's minimum balance and its spendable balance, showing each component, including the one component that looks like it belongs in the sum and does not.

   b. **(Trace)** Trace four operations in order: `pay(recipient, 1_500_000)`, then `pay(recipient, 100_000)`, then `opt_in_to` a fourth asset, then `pay(recipient, 400_000)`. For each, say whether it succeeds and what the account's balance and minimum balance are afterwards.

   c. **(Debug)** One of the four fails. Say which, quote the message it produces, and say who wrote that message: the protocol or the contract.

   d. **(Trace)** Name one message from earlier in this chapter that the other one wrote.

   e. **(Trace)** Swap the last two operations and trace the sequence again. Something still fails; say what.

   f. **(Compare)** Say what the pair of traces tells you about ordering a funding check against an operation that raises the floor it checks against.

2. Below are seven statements. Five of them form the body of a `deposit` method that accepts an ASA transfer in the same group and credits the caller; two do not belong. The decorator and signature are given, `self.token` is a `GlobalState(UInt64)` holding the configured asset id, and `self.deposited` is a `LocalState(UInt64)`.

   ```python
   @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
   def deposit(self, transfer: gtxn.AssetTransferTransaction) -> UInt64:
       ...
   ```

   The statements: (a) `assert Global.group_size == UInt64(2), "transfer, then call"`; (b) `assert transfer.xfer_asset.id == self.token.value, "wrong asset"`; (c) `assert transfer.asset_receiver == Global.current_application_address, "send it here"`; (d) `assert transfer.sender == Txn.sender, "fund your own balance"`; (e) `self.deposited[Txn.sender] = self.deposited.get(Txn.sender, UInt64(0)) + transfer.asset_amount`; (f) `assert transfer.asset_amount <= self.token.value, "too much"`; (g) `self.token.value = transfer.xfer_asset.id`.

   a. **(Parsons)** Select the five that belong and order them.

   b. **(Debug)** For each of the two rejects, say what it does: one of them is nonsense that happens to compile and will reject almost every honest deposit, and the other is a live vulnerability that turns a configured vault into an unconfigured one on every call.

   c. **(Compare)** Statement (a) is what makes (b), (c) and (d) trustworthy. Explain that dependency in one sentence.

   d. **(Compare)** Decide whether relaxing (a) to `>= UInt64(2)` would require changing anything at all about (b), (c) and (d): either say yes and name the changes, or say no and say what (a) was protecting against, given that it was not these three.

3. A rewards contract has been running for four months. It holds a reward ASA, and `claim` sends a fixed number of units to any caller who has opted in. It has worked for every caller, every time. This morning it started failing for everybody, with `logic eval error: inner tx 0 failed: asset 1057 missing from KRT4...5DVQ`. The contract's code has not been changed and nobody has called any administrative method. The reward asset still exists and the contract's Algo balance is 3.1 Algo.

   a. **(Trace)** Before working anything else out, write down what must be true of the application account right now, given that error.

   b. **(Debug)** Name the sequence of ordinary operations --- no attacker, no code change --- that produces this state, and say which of this chapter's costs is the mechanism.

   c. **(Trace)** Say why the contract's 3.1 Algo balance is not the reassurance it appears to be, and compute what it would actually need.

   d. **(Debug)** Give a fix that makes the failure legible to a caller *and* a separate fix that makes it not happen, and say which of the two you would ship first and why.

4. You are designing a token whose issuer must be able to recover units from an account under a court order. The three arrangements: (i) the clawback address is a hot wallet the issuer controls; (ii) the clawback address is an application account, with recovery gated by a contract method behind a multi-signature admin; (iii) there is no clawback address, and recovery is handled by burning and re-issuing, with the issuer as freeze address.

   a. **(Compare)** Compare the three on four axes: what a holder can verify before acquiring the token, what the issuer can do unilaterally, what happens if the controlling key or contract is lost, and what happens if the controlling party is compromised.

   b. **(Compare)** One of the three is not actually a recovery mechanism at all for units already in circulation. Name it and say precisely what it can and cannot do.

   c. **(Compare)** Of the remaining two, say which axis decides between them, and give a concrete regulatory or product requirement that would flip your answer.

5. Extend the fixed tip jar so it can also accept tips in a single ASA rather than only in Algo, keeping the Algo path working. The full corrected contract is Example 7-25, and you will want it in front of you. You will need four things this chapter gave you and one it did not. The four: a configured asset id in state, a self-opt-in guarded by a minimum-balance check, an asset-transfer variant of `tip` with all four incoming checks, and an asset-transfer variant of `withdraw`. The one it did not give you is the ordering problem: the jar must be opted in before anybody can tip it, and opting in raises the minimum balance, which changes what the *Algo* withdrawal may send.

   a. **(Extend)** Write the contract.

   b. **(Extend)** Write down three things that can now go wrong that could not go wrong before. At least one of your three should be about the Algo path breaking as a consequence of something on the asset path.

   c. **(Debug)** For each of the three, name the specific check or ordering constraint that prevents it.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can name the account an application controls, explain why no private key exists for it, compute its spendable balance, and say what an inner payment of the full balance does.
- [ ] I can send Algo and asset units out of a contract, say who pays the fee under each setting of `fee`, and write the assertion that makes the caller cover a whole group's pooled fees.
- [ ] I can list the four questions an incoming transfer must answer, say exactly what a typed group parameter does and does not guarantee, and say why a group-size assertion is what makes those four checks worth writing.
- [ ] I can create an asset from a contract, opt a contract into somebody else's asset, price both in minimum balance, and say what happens to a role address left out of a reconfiguration.
- [ ] I can say why an account balance is not an accounting record, name the attack that follows from confusing them, and say what it means when a contract's balance and its books disagree.

## Handoff: How the Vesting Project Pays Out
Chapter 9 builds a real token vesting contract: an admin deposits a supply of an ASA, schedules are written per beneficiary, and a claim method pays out what has vested. Every one of those three sentences is this chapter's material with last chapter's arithmetic inside it. Table 7-1 lists the examples the project leans on, and what to predict before you read it.

: Table 7-1. Examples from this chapter that the vesting project depends on

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| Example 7-8 | `deposit_tokens`, which takes the grant supply from the admin | The project checks the transfer's asset, amount and destination but authorizes on the *app call's* sender rather than the transfer's. Say why those are different accounts and why that is the right choice there. |
| Example 7-17 | Bootstrapping the contract into the grant asset before any deposit | The project must be opted in before a deposit can arrive. Who pays the 100,000 microAlgo, and what breaks if they pay it late? |
| Example 7-3 | `claim`, whose terminal act is an inner asset transfer | The payout is an ASA transfer, not a payment. Which of the two guards in this example still applies, and what replaces the other? |
| Example 7-4 | Every method that pays out | A claim is one app call and one inner transfer. Write the pooled-fee assertion before you read the project's. |
| Example 7-10 | The deposit path, which reads a transfer from the group | The project's deposit takes the transfer as a typed argument rather than by index. Say what that changes about the size check, and what it does not. |
| Example 7-23 | `available_tokens`, which is decremented when a schedule is created | The project tracks unpromised supply in state rather than reading its own asset holding. Work out what an outsider could do to the contract if it read the holding instead. |
| Example 7-19 | The payout path, against a beneficiary who may never have opted in | A beneficiary who has not opted into the grant asset cannot be paid, and the project lets the transfer fail rather than gating on it. Predict what the beneficiary sees when it does, and what one line would change that. |
