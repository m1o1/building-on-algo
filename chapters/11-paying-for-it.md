\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# Paying For It: Minimum Balance, Fees, and Budget

Every chapter so far has been able to defer this one. Chapter 5 said a box costs minimum balance and moved on. Chapter 7 said an inner transaction's fee comes from somewhere and set it to zero. Chapter 10 put a role set in global state and mentioned a ceiling. Each of those was a real answer to the question in front of it, and each left an invoice on the table. This chapter collects them all --- back to back with Chapter 10 on purpose, because the NFT vesting project one chapter ahead needs both at once: it will charge users for the storage they create, refund it when they leave, and mint assets whose bills land on three different accounts.

A contract is billed four separate times by four unrelated mechanisms, and the four differ in *what* they charge for, *when* they charge it, and *who* receives the bill. They are easy to confuse and expensive to confuse, so this chapter picks them all up at once. Readers arrive believing there is one number called cost. There is not, and the most common production failure in this area is not extravagance but paying one of the four and being surprised by another.

::: {.spec title="Your commission: a revenue splitter that pays its own way"}
The contract you build this chapter is a revenue splitter for three collaborators: pay it, and it divides what arrives three ways and sends each share on. It must:

1. Split any incoming payment three ways and forward the shares immediately
2. Never lose a microAlgo silently --- every remainder has a stated destination
3. Pay for its own transactions with somebody's money *on purpose*, not by accident
4. Keep working in month nine exactly as it worked in week one

Four requirements, two methods, and three of the four bills land on it. At the end of the chapter you will re-run the finished splitter against this list.
:::

By the end of this chapter you will be able to:

- Name the four things a contract is billed for, and say who receives each bill and when
- Compute an application's minimum balance from its schema, its pages and its boxes, and say which of those the *creator* pays and which the *application account* pays
- Charge a user for the storage they create, and refund it to the account that actually paid
- Say where an inner transaction's fee comes from, and make the caller cover a group instead
- Measure a method's opcode budget from the AVM rather than estimating it, and buy more from either of two sources
- Say which of those two sources is a drain vector on a public method, and why
- Say what a transaction is allowed to touch, how that list is built, and the two situations in which it is built wrong

## Four Bills, and Only Two Are Money
A contract that takes money in and pays it out needs a balance it can spend from. Part of what it holds is never spendable, and every transaction it sends comes out of the rest.

Figure 11-1 sets out the four bills: what each charges for, when it charges, and who receives it.

![Figure 11-1. Four separate bills for one application call, drawn without arrows because they are concurrent facts rather than stages. Schema is billed to the creator and box storage to the application account --- the pair most often reversed.](figures/four-bills.svg)

Schema minimum balance is billed to the *creator* and box minimum balance to the *application account*, and those two are the pair this book has warned since Chapter 2 that people reverse. The drawing carries no arrows on purpose. These are four concurrent facts about one call, not four stages of it: the schema was billed weeks ago, the fee is being billed now, the budget will be spent and discarded inside the next few milliseconds, and the reference list is checked as each read happens, not before the program started.

## Building a Fee Splitter
**Example 11-1.** The fee splitter, as first written

<!-- finder: see a working revenue splitter that spends itself to a halt -->

```python
from algopy import (Account, ARC4Contract, Global, Txn, UInt64, arc4, gtxn,
                    itxn)


class Splitter(ARC4Contract):
    """Split an incoming payment three ways. Three ways to lose a microAlgo."""

    a: Account
    b: Account
    c: Account

    @arc4.abimethod
    def configure(self, a: Account, b: Account, c: Account) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        self.a = a
        self.b = b
        self.c = c

    @arc4.abimethod
    def split(self, payment: gtxn.PaymentTransaction) -> UInt64:
        assert payment.receiver == Global.current_application_address, "not ours"
        share = payment.amount // UInt64(3)
        for who in (self.a, self.b, self.c):
            itxn.Payment(receiver=who, amount=share,
                         fee=Global.min_txn_fee).submit()
        return share
```

Example 11-1 is complete and deployable. It has a creator-only guard on `configure`, it checks that the payment came to the application rather than to somebody else (the check Chapter 10 spent a section on), and its division is the obvious one. Twenty-six lines, no cleverness, and two of the four bills unpaid.

Deploy it, fund it with one Algo, and pay it. This is an **on-chain run** against LocalNet through an algokit-utils typed client:

```console
>>> def held():   # what the splitter's own account holds
...     info = algorand.account.get_information(splitter.app_address)
...     return info.amount.micro_algo
...
>>> held()                       # funded on deployment
1000000
>>> splitter.send.split(args=(pay(9_000),)).abi_return
3000
>>> splitter.send.split(args=(pay(10_000),)).abi_return
3333
>>> held()
994001
```

The second line is the test everybody writes, and it hides both defects: nine divides by three, so three thousand each, nine thousand paid, nothing left over.

*Predict: two defects, and one of them is invisible on any test with a round number in it. Write down what you think the contract spends money on, on a line that reads as diligence, and where the missing microAlgo go. Then look at the two numbers below before reading the sections.*



Neither defect announces itself. Three shares of 3,333 is 9,999 against the 10,000 that arrived: one microAlgo is somewhere. And the account, funded with a full Algo and having taken in 19,000 microAlgo across the two calls and paid out 18,999, now holds **994,001**. It is five thousand, nine hundred and ninety-nine microAlgo down, on a contract that has only ever received money and forwarded it.

Ship it anyway and the two defects compound on a schedule. Nine weeks out, the account has bled its way down to 100,300 microAlgo and `split` starts failing for every caller --- including you --- on payments identical to ones that succeeded a fortnight earlier, with nothing deployed and nothing changed. It has not been drained; it has been *spending*, three thousand microAlgo at a time, on something the code never mentions, and it has finally hit the floor it cannot spend past. And while you are reading the ledger to find that, you find the other one: across nine weeks the three collaborators are collectively short --- a microAlgo here, two there, never the same amount twice, and never on the round-number test payments. Neither defect is a wrong line. The splitter does exactly what its twenty-six lines say. What it does not do is say what it costs.

## What It Costs to Exist
An account's minimum balance is the amount it must still hold when a transaction settles, and every structure a contract carries raises it. The parts are simple; the trap is who pays for each.

**Example 11-2.** What a schema costs

<!-- finder: work out what an application's declared schema costs, and who pays it -->

```python
from algopy import ARC4Contract, StateTotals, UInt64, arc4

UINT_SLOT = 28_500
BYTES_SLOT = 50_000


class Budgeted(ARC4Contract,
               state_totals=StateTotals(global_uints=4, global_bytes=1)):
    """The schema is a bill, and it is sent to the creator, not the app."""

    counter: UInt64

    @arc4.abimethod(readonly=True)
    def schema_cost(self) -> UInt64:
        # 100,000 to exist plus 28,500 per uint slot and 50,000 per byte
        # slot -- charged to whoever created the application, once, and
        # never refunded while it exists.
        return UInt64(100_000 + 4 * UINT_SLOT + 1 * BYTES_SLOT)
```

The key line is the class declaration, not the method. `state_totals=StateTotals(global_uints=4, global_bytes=1)` is a *bill*: 100,000 microAlgo for the application to exist, 28,500 for each uint slot and 50,000 for each byte slot. It is charged to the account that created the application, once, at creation, and never refunded while the application lives. Not to the application's own account. **That asymmetry is the single most reversed pair in this subject**, which is why the figure names the payer on every row and why Chapter 2 flagged it early.

**Example 11-3.** Program pages

<!-- finder: work out what an application's extra program pages cost -->

```python
from algopy import ARC4Contract, Application, UInt64, arc4, op


class Sizing(ARC4Contract):
    """Report an application's extra program pages, which are not free."""

    @arc4.abimethod(readonly=True)
    def pages(self, app: Application) -> UInt64:
        # A program is one 2,048-byte page by default. Each extra page is
        # another 100,000 microAlgo on the creator's minimum balance.
        # Consensus v42 lets an update change the count, but only if the
        # contract approves UpdateApplication --- this one does not.
        extra, _exists = op.AppParamsGet.app_extra_program_pages(app)
        return extra
```

An application gets one 2,048-byte page free, and that is approval and clear-state *combined*, not each. Every additional page costs another 100,000 microAlgo of the creator's minimum balance. Consensus v42 lets an update grow pages (and global schema), moving the extra MBR onto the updater --- but only if the contract approves `UpdateApplication`. A program approaching the boundary is still a deployment decision for every contract in this book that refuses updates.

**Example 11-4.** Charge the user for the box they create

<!-- finder: make the caller pay the minimum balance for storage they cause -->

```python
from algopy import (ARC4Contract, Account, BoxMap, Global, String, Txn, UInt64,
                    arc4, gtxn)

BOX_FLAT = 2_500
BYTE_COST = 400


class Registry(ARC4Contract):
    """Make the caller fund the box they are about to create."""

    def __init__(self) -> None:
        self.note = BoxMap(Account, String, key_prefix=b"n_")

    @arc4.abimethod
    def write(self, funding: gtxn.PaymentTransaction, text: String) -> UInt64:
        # 2,500 flat plus 400 per byte of key AND value. The key here is the
        # 2-byte prefix plus a 32-byte address; the value is the string.
        size = UInt64(2 + 32) + text.bytes.length
        owed = UInt64(BOX_FLAT) + UInt64(BYTE_COST) * size
        assert funding.receiver == Global.current_application_address, "not ours"
        assert funding.amount >= owed, "fund the box you are creating"
        # The box is booked to Txn.sender, so the money must be theirs too
        # (Chapter 10's rule: the funder must be the credited account).
        assert funding.sender == Txn.sender, "fund your own box"
        self.note[Txn.sender] = text
        return owed
```

Boxes are the exception on the payer line: their minimum balance falls on the *application account*, which has no income of its own. So a contract that lets anybody create a box and does not charge for it is a contract that funds strangers' storage out of its own floor, until it cannot act. The arithmetic to keep is `2,500 + 400 × (len(key) + len(value))`, and both lengths are yours to know: the key here is a two-byte prefix plus a thirty-two-byte address.

**Example 11-5.** Refund the funder, not the caller

<!-- finder: return a box deposit to whoever actually paid it -->

```python
from algopy import ARC4Contract, Account, BoxMap, UInt64, arc4, itxn


class Registry(ARC4Contract):
    """Give the minimum balance back to whoever actually paid it."""

    def __init__(self) -> None:
        self.funder = BoxMap(Account, Account, key_prefix=b"f_")
        self.paid = BoxMap(Account, UInt64, key_prefix=b"p_")

    @arc4.abimethod
    def release(self, holder: Account) -> UInt64:
        owed = self.paid[holder]
        # The funder is stored because it is NOT always the caller: a relayer,
        # a sponsor or an earlier owner may have paid. Refunding Txn.sender
        # pays the wrong person with somebody else's money.
        recipient = self.funder[holder]
        del self.funder[holder]
        del self.paid[holder]
        itxn.Payment(receiver=recipient, amount=owed, fee=UInt64(0)).submit()
        return owed
```

`recipient = self.funder[holder]` is the line that matters, precisely because it is *not* `Txn.sender`. The same method written the obvious way:

```python
from algopy import ARC4Contract, Account, BoxMap, Txn, UInt64, arc4, itxn


class Registry(ARC4Contract):
    """The same release, refunding whoever happens to be calling."""

    def __init__(self) -> None:
        self.funder = BoxMap(Account, Account, key_prefix=b"f_")
        self.paid = BoxMap(Account, UInt64, key_prefix=b"p_")

    @arc4.abimethod
    def release(self, holder: Account) -> UInt64:
        owed = self.paid[holder]
        del self.funder[holder]
        del self.paid[holder]
        # `Txn.sender` is whoever called release, which on any contract with a
        # public cleanup method is whoever wants the money.
        itxn.Payment(receiver=Txn.sender, amount=owed, fee=UInt64(0)).submit()
        return owed
```

`Txn.sender` on a public cleanup method is whoever wants the money. The funder and the caller are the same account on the happy path and on every test anybody writes, which is exactly why this ships: a relayer, a sponsor, or a previous owner paid the deposit, and the refund goes to whoever calls `release` first. Store the payer at the moment they pay, because it is the only moment you know it.

**Example 11-6.** Ask an account what it is carrying

<!-- finder: ask an account what storage it holds, and what floor that implies -->

```python
from algopy import Account, ARC4Contract, UInt64, arc4, op


class BoxCensus(ARC4Contract):
    """Ask an account what it is carrying, and what that carriage costs."""

    @arc4.abimethod(readonly=True)
    def census(self, who: Account) -> tuple[UInt64, UInt64, UInt64, UInt64]:
        # What the ledger says an account holds, rather than what your
        # bookkeeping believes. The second value of each pair is the exists
        # flag, which is only `balance > 0`; this raw form hands it to you,
        # where `Account.min_balance` would assert on it instead.
        boxes, _e = op.AcctParamsGet.acct_total_boxes(who)
        box_bytes, _e = op.AcctParamsGet.acct_total_box_bytes(who)
        assets, _e = op.AcctParamsGet.acct_total_assets(who)
        # The floor, which the ledger computes from these three AND from the
        # applications this account created or opted into, their schema and
        # their pages. An account holding nothing still reads 100,000 here.
        floor, _e = op.AcctParamsGet.acct_min_balance(who)
        return boxes, box_bytes, assets, floor
```

Four reads. The fourth settles arguments: `acct_min_balance` is the ledger's own arithmetic rather than yours.

*Predict:* deploying an application bills somebody 264,000 microAlgo. Which of the two accounts moves, the creator's or the application's own?

Deploy `Budgeted`, `Registry` and `BoxCensus` and ask. This is a **LocalNet run** through an algokit-utils typed client. Its two `readonly` lines are answered by simulation rather than submitted, the arrangement Chapter 5 warned about; that is harmless here, because neither of them is claiming anything about budget:

```console
>>> def floor(who):    # the ledger's own arithmetic, in microAlgo
...     info = algorand.account.get_information(who)
...     return info.min_balance.micro_algo
...
>>> floor(creator)                          # owns nothing yet
100000
>>> # deployed Budgeted(global_uints=4, global_bytes=1) as creator
>>> floor(creator)
364000
>>> 364000 - 100000                         # what the schema cost
264000
>>> floor(budgeted.app_address)             # the app's own floor
100000
>>> budgeted.send.schema_cost().abi_return  # what the contract says
264000

>>> floor(registry.app_address)             # no boxes yet
100000
>>> registry.send.write(args=(pay(20_000), "hello")).abi_return
18100
>>> floor(registry.app_address)
118100
>>> 118100 - 100000                         # what the box cost
18100

>>> # the floor again, and what it is made of, asked
>>> # by a contract rather than of the ledger
>>> # returns (boxes, box_bytes, assets, floor)
>>> census.send.census(args=(registry.app_address,)).abi_return
(1, 39, 0, 118100)
```

That is two bills landing on two different accounts. The creator begins at the 100,000 every account owes simply for existing and ends at 364,000, a rise of 264,000: 100,000 for the application plus four uint slots at 28,500 plus one byte slot at 50,000. `schema_cost` returns the same figure, but it computes those three constants from a listing without asking the chain anything, so it is a restatement rather than a corroboration. The ledger reading is the evidence.

The application's own account is still sitting at 100,000. That is not a vacuous reading: 100,000 is what *any* address reports, but this one would read 364,000 had the schema landed on it. **There is the asymmetry, measured:** the schema its own class declared did not cost it a microAlgo.

Then the box, and the direction reverses. The registry's account rises from 100,000 to 118,100, exactly the figure `write` quoted: 2,500 flat plus 400 for each of 39 bytes. Thirty-nine rather than forty-one, because the key is the two-byte prefix and the thirty-two-byte address while the value is five raw UTF-8 bytes: a `String` is stored as its bytes, where an `arc4.String` would carry a two-byte length prefix and cost you 800 more. The caller sent 20,000 against that quote, because a caller cannot know it until the method returns it; the 1,900 above the floor is the contract's to keep or to hand back.

The census then reports that same 118,100, which is the point of asking on chain at all: a contract can find out what it is actually carrying rather than what your deployment script believed. One catch, and it is this chapter's fourth bill arriving early: `census` reads an account it was handed, and a program may only read an account the *transaction* declared. Nothing in the transcript says so, because two separate conveniences are covering for it. A `readonly` method is answered by a simulate that is allowed to invent its own reference list; and on a submitted call, algokit-utils assembles that list for you anyway, as Chapter 5 warned it does for box references. Take both away, dropping the `readonly` *and* the padding, and the read comes back `unavailable Account`, at the opcode that reads rather than before the program starts, which is why it arrives carrying a program counter. Example 11-14 takes it up.

Two more lines of that floor belong to Chapter 4 and Chapter 7: 100,000 for each ASA an account opts into or creates, and 100,000 plus the local schema for each application it opts into. Both follow the box rule rather than the schema rule. The account that *holds* the thing pays, not the account that created it, which for a contract's own opt-ins means the application account and for a user's means the user. Table B-3 has the complete list on one page.

None of this is what emptied the splitter, which has no boxes and no schema to speak of. Its bill was of a different kind entirely.

## What It Costs to Send
Every transaction carries a fee, and the fee is where the splitter's money went.

**Example 11-7.** The network's own floor

<!-- finder: read the network's minimum fee instead of hard-coding 1,000 -->

```python
from algopy import ARC4Contract, Global, Txn, UInt64, arc4


class FeeAware(ARC4Contract):
    """Read the network's own floor rather than hard-coding 1,000."""

    @arc4.abimethod
    def require_two_fees(self) -> UInt64:
        # `Global.min_txn_fee` is a consensus parameter, not a constant of
        # nature. Writing 1_000 works today and is a claim about a value the
        # protocol reserves the right to change.
        needed = Global.min_txn_fee * UInt64(2)
        assert Txn.fee >= needed, "cover the inner transaction too"
        return needed
```

`Global.min_txn_fee` is a consensus parameter. Writing `1_000` works today and is a claim about a number the protocol reserves the right to change; reading it costs one opcode and cannot go stale.

::: {.gotcha #min-fee-is-a-parameter-not-a-constant topic="Resource references, MBR, and budget" title="The minimum fee is a consensus parameter, not a constant"}
1,000 microAlgo is the minimum *today*. Client code that multiplies a hard-coded 1,000 by a group size underpays the whole group the moment the protocol raises it, and the failure is a rejected group rather than anything that points at the constant. Read the fee from `suggested_params()` and scale that.

Inside a contract, `Global.min_txn_fee` is the same number and costs one opcode, so a fee cap written as `Global.min_txn_fee * UInt64(10)` cannot go stale, where `UInt64(10_000)` can.
:::

**Example 11-8.** Fee pooling, and who covers the group

<!-- finder: make the caller pay for the inner transactions your contract sends -->

```python
from algopy import ARC4Contract, Account, Global, Txn, UInt64, arc4, itxn


class Payout(ARC4Contract):
    """The caller funds the inner transaction, because fees pool."""

    @arc4.abimethod
    def send_to(self, who: Account, amount: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        # Two transactions in this group's fee arithmetic: this call and the
        # inner payment. Requiring the caller to cover both is what makes
        # `fee=0` below legal -- the group pays, not the contract.
        assert Txn.fee >= Global.min_txn_fee * UInt64(2), "underpaid fee"
        itxn.Payment(
            receiver=who,
            amount=amount,
            fee=UInt64(0),
        ).submit()
```

Two lines do the work, and they only work together. `fee=UInt64(0)` on the inner payment says the contract pays nothing, which is legal only because fees pool across an atomic group, so a surplus on one transaction covers a shortfall on another. `assert Txn.fee >= Global.min_txn_fee * UInt64(2)` is what makes the surplus exist: the caller is required to cover this call *and* the inner payment it will cause.

**This is the splitter's first defect, and it is one word.** The broken splitter writes `fee=Global.min_txn_fee` on each of its three inner payments, which reads like diligence: a transaction needs a fee, so give it one. It does not read like an instruction to spend three thousand microAlgo of the contract's own balance on every call, but that is what it is, and nothing in the contract ever puts money in. The arithmetic closes. A full Algo funds it; the account must still hold 100,000 when any transaction settles; so 900,000 microAlgo at 3,000 a call is three hundred calls. Nine weeks is sixty-three days, so five calls a day is a little over three hundred. The three-hundred-and-first is refused, and refused as a *group*, so the payment the caller made is rolled back with it, which is why the symptom is "`split` fails for everyone" rather than "the contract is short":

```console
ValueError: Error resolving execution info via simulate in transaction 1:
transaction HHVJ...4MJQ: account LCP5...6IBA balance 97301 below min
100000 (0 assets)
```

The ledger will not let an account settle below its floor. The splitter never spent its last 100,000 microAlgo because it was never allowed to; it spent everything above that and then stopped being able to act at all.

::: {.gotcha #inner-fee-from-app-balance topic="Resource references, MBR, and budget" title="An inner transaction's fee is spent from the contract's own balance"}
The fee on an inner transaction comes from the application account, and `fee=0` is already the default on every `itxn` builder in algorand-python. So the hazard is not a forgotten fee but a fee somebody wrote a value into, usually `Global.min_txn_fee`, believing a transaction must carry one. On a method anybody may call, that is an unbounded withdrawal, a minimum fee per inner transaction per call from an account with no income --- and spending toward the minimum makes every *other* inner transaction the contract sends start failing, so the symptom is a contract that stops working entirely rather than one that reports a shortfall. Write `fee=UInt64(0)` explicitly so the omission reads as a decision, and require the caller to cover the group with one assertion counting every transaction, inner ones included.
:::

**Example 11-9.** Sponsored fees

<!-- finder: let a relayer pay the fee so your user signs a zero-fee transaction -->

```python
from algopy import ARC4Contract, Global, Txn, UInt64, arc4, gtxn


class Relayed(ARC4Contract):
    """A relayer covers the fee; the user signs a zero-fee transaction."""

    @arc4.abimethod
    def act(self, sponsor: gtxn.PaymentTransaction) -> None:
        # Fees pool across a group, so one transaction may carry the whole
        # group's fees and the rest may carry none. That is the entire
        # mechanism behind "gasless" UX on Algorand.
        assert Global.group_size == UInt64(2), "sponsor, then call"
        assert sponsor.receiver == Global.current_application_address, "not ours"
        assert Txn.fee == UInt64(0), "the sponsor pays this one"
```

The key line is `assert Txn.fee == UInt64(0)`: the user's own transaction carries no fee at all, and the group still settles because the sponsor's payment carries enough for both. One account runs the surplus, the rest run none, and no special support from the protocol is involved.

Figure 11-2 draws four versions of the same call on one fee axis. Nothing in it reduces the total (fees are owed per transaction, inner transactions included), so every arrangement is a decision about *whose* balance the total comes out of. That matters most for a user holding an ASA and no Algo, who cannot pay for a single transaction and is therefore locked out of a contract they have the assets to use.

![Figure 11-2. Four versions of the same call on one fee axis. Setting an inner transaction's fee to zero does not remove the cost; it moves it.](figures/who-pays.svg)

In the splitter, this is the fix for the balance: `fee=UInt64(0)` on the three inner payments, and one assertion making the caller cover four transactions instead of one.

## What It Costs to Run
The third bill is not money. An application call gets 700 opcodes, application calls in a group pool their budgets, and anything left over at the end is discarded rather than banked.

**Example 11-10.** Ask the AVM what is left

<!-- finder: find out how much opcode budget a method actually has left -->

```python
from algopy import ARC4Contract, UInt64, arc4, op


class Measured(ARC4Contract):
    """Report what is left, so the number comes from the AVM not a guess."""

    @arc4.abimethod
    def remaining(self) -> UInt64:
        # 700 per application call in the group, pooled. NOT `readonly`, and
        # that is the whole point: a readonly method is answered by a
        # simulate carrying 320,000 units, so a budget meter marked readonly
        # reports 320,688 where the real answer is 688.
        return op.Global.opcode_budget()
```

The method is deliberately *not* `readonly`. Chapter 5 warned that the tooling answers a readonly method with a simulate carrying a 320,000-unit budget, and this is where that warning collects its debt: mark this method `readonly` and it reports 320,688 where the true answer is 688. Submit it for real and the number that comes back is the only one that counts. Estimating from a listing is guessing about a compiler; measuring through the wrong door is worse, because it answers.

**Example 11-11.** Buy more budget

<!-- finder: buy opcode budget when a method needs more than 700 -->

```python
from algopy import (ARC4Contract, OpUpFeeSource, UInt64, arc4, ensure_budget,
                    urange)


class Hasher(ARC4Contract):
    """Buy more opcodes by issuing inner app calls, paid by the group."""

    @arc4.abimethod
    def digest_many(self, rounds: UInt64) -> UInt64:
        # `GroupCredit` is also the default, and it spends fee the CALLER
        # already put in the group. `Any` falls back to the app's own balance
        # when the group is short; naming it is how you decide whose money
        # pays, rather than finding out from a drained contract.
        ensure_budget(rounds * UInt64(35), fee_source=OpUpFeeSource.GroupCredit)
        total = UInt64(0)
        for _i in urange(rounds):
            total += UInt64(1)
        return total
```

`ensure_budget` issues inner application calls until the budget is at least what you asked for, and each of those adds another 700. The second argument decides *whose money* pays for them.

Example 11-11 does **not** ask the caller for anything. `GroupCredit` spends a surplus the caller must have put there, and this method never requires one, so an ordinary caller paying an ordinary fee gets `group fee 0.0A too small (needs 1mA more)` from inside the op-up loop, a message about a transaction they did not write. Example 11-8 shows the assertion that would prevent it. Whether to write that assertion is the same decision as the fee source itself, one layer out.

The same method with one argument changed:

```python
from algopy import (ARC4Contract, OpUpFeeSource, UInt64, arc4, ensure_budget,
                    urange)


class Drainable(ARC4Contract):
    """The same contract, paying for its own op-up. Anyone may call this."""

    @arc4.abimethod
    def digest_many(self, rounds: UInt64) -> UInt64:
        # `AppAccount` takes the fee from the application's own balance. On a
        # method anybody may call, with a caller-supplied count, that is an
        # unmetered withdrawal: each op-up costs a minimum fee of the
        # contract's money and the caller chooses how many.
        ensure_budget(rounds * UInt64(35), fee_source=OpUpFeeSource.AppAccount)
        total = UInt64(0)
        for _i in urange(rounds):
            total += UInt64(1)
        return total
```

`OpUpFeeSource.GroupCredit`, which is also the default, spends fee the caller already put in the group, so a caller who wants more budget pays for it. `OpUpFeeSource.AppAccount` takes it from the application's own balance. On a public method whose budget requirement is a function of a caller-supplied argument, that is an unmetered withdrawal: each op-up costs a minimum fee of the contract's money and the caller chooses how many. The tell is the same as the splitter's: money leaving an account that has no income.

**Example 11-12.** Buy budget from the client instead

<!-- finder: get more opcode budget without the contract sending anything -->

```python
"""Buy opcode budget from the client instead of from the contract."""

import sys
from pathlib import Path

from algokit_utils import (AlgoAmount, AlgorandClient, AppClient,
                           AppClientMethodCallParams, AppClientParams)


def main(app_id: int, spec_path: str) -> int:
    algorand = AlgorandClient.from_environment()
    caller = algorand.account.localnet_dispenser()
    client = AppClient(AppClientParams(
        app_spec=Path(spec_path).read_text(), algorand=algorand,
        app_id=app_id, default_sender=caller.address))
    # Every application call in a group contributes 700 opcodes to one pool,
    # so padding the group with cheap calls buys budget without the contract
    # issuing an inner transaction and without spending its balance.
    group = algorand.new_group()
    for i in range(3):
        # The note only makes each call distinct. Three byte-identical
        # transactions share one id, and the second is rejected as already
        # in the ledger -- padding calls need something to tell them apart.
        group.add_app_call_method_call(client.params.call(
            AppClientMethodCallParams(method="remaining",
                                      note=f"pad {i}".encode())))
    result = group.send()
    return int(result.returns[-1].value)


if __name__ == "__main__":
    print(main(int(sys.argv[1]), sys.argv[2]))
```

Because budget pools across the application calls in a group, a client can pad the group with cheap calls and hand the expensive one a larger pool. No inner transactions, nothing spent from the contract, and the padding calls are ordinary transactions the caller is already paying fees for. Measured on LocalNet, a group of three calls gives the last one 2,050 opcodes against the 700 it would have had alone.

The padding calls above went to the splitter itself, but nothing requires that. A dedicated *padding contract* --- one that exists only to contribute budget --- is the smallest contract in the book, and it has a trap in it. Give it a bare NoOp method and nothing else, and it will not compile: defining a bare method suppresses the create path the compiler would otherwise insert for you, so there is no way to deploy it.

```python
@arc4.baremethod(allow_actions=["NoOp"], create="allow")
def noop(self) -> None:
    pass
```

`create="allow"` restores it. Adding a *second* bare method marked `create="require"` does not: two bare methods cannot both handle NoOp, and the compiler says so.

::: {.gotcha #budget-is-not-money topic="Resource references, MBR, and budget" title="Opcode budget pools across application calls and is discarded, not banked"}
An application call gets 700 opcodes and the application calls in a group pool them, so three calls share 2,100 regardless of which does the work. Two consequences catch people. Unused budget is discarded rather than banked, so there is nothing to conserve and no reason to write a cheaper method that is harder to read. And because the pool is shared, a method that fits comfortably alone can fail when a caller groups it beside something expensive: the failure is in your method, the cause is in theirs, and the message names an opcode rather than a group. `ensure_budget` and client-side padding are the two ways to buy more; they differ only in who pays, which makes that the question to answer first.
:::

**Example 11-13.** What a loop costs

<!-- finder: measure what a loop costs in opcodes rather than guessing -->

```python
from algopy import ARC4Contract, UInt64, arc4, op, urange


class Looper(ARC4Contract):
    """Measure what a loop actually costs, rather than estimating it."""

    @arc4.abimethod
    def cost_of(self, n: UInt64) -> UInt64:
        before = op.Global.opcode_budget()
        total = UInt64(0)
        for _i in urange(n):
            total += UInt64(1)
        # The answer is the difference, read from the AVM. A loop whose
        # bound is a caller argument makes this a function of the caller.
        return before - op.Global.opcode_budget()
```

Example 11-13 is the measuring instrument for everything in this section: a loop whose bound is a caller argument makes your opcode budget a function of your caller, which is the same shape as the `OpUpFeeSource.AppAccount` drain, in a different currency.

The splitter never comes near 700 opcodes: three inner payments and a division. The fee source is the same mistake as the splitter's fee, made about a different resource.

## What It May Touch
The fourth bill is not charged in money or opcodes but in *permission to look*. A transaction carries a list of the accounts, assets, applications and boxes it intends to touch, and a program that reaches outside that list fails at the opcode that reached, with none of your assert messages attached.

**Example 11-14.** Reading a declared resource

<!-- finder: read an account's asset holding that the transaction declared -->

```python
from algopy import Account, ARC4Contract, Asset, UInt64, arc4, op


class Reader(ARC4Contract):
    """A method may only touch what its transaction declared.

    Availability is not permission -- it is the list of things this
    transaction is allowed to look at, and a read outside the list is a
    failure of the transaction rather than of your logic.
    """

    @arc4.abimethod(readonly=True)
    def holding(self, who: Account, token: Asset) -> UInt64:
        # Both arguments are resources the client had to declare. The
        # two-tuple return is how you read one without asserting it
        # exists -- the second value is the existence flag.
        amount, _exists = op.AssetHoldingGet.asset_balance(who, token)
        return amount
```

Availability is not permission. The list does not say the caller may do something; it says the node has been told to fetch these, and a read outside it is a failure of the *transaction* rather than of your logic. The check happens inside the opcode that reads, not before the program starts, so the failure carries a program counter and a TEAL line and none of your own wording.

**Example 11-15.** Resources as typed arguments

<!-- finder: pass an account or asset as a typed argument -->

```python
from algopy import Account, ARC4Contract, Asset, UInt64, arc4, op


class Modern(ARC4Contract):
    """The same thing, as a typed argument the client resolves for you."""

    @arc4.abimethod(readonly=True)
    def by_value(self, who: Account, token: Asset) -> UInt64:
        # The argument travels BY VALUE -- a 32-byte address, an 8-byte
        # asset id -- and the SDK separately adds each one to the
        # transaction's reference list. Two independent things on one
        # transaction; neither is an index into the other.
        amount, _e = op.AssetHoldingGet.asset_balance(who, token)
        return amount
```

Since PuyaPy 5.0 an `Account` or `Asset` parameter travels **by value** (a 32-byte address, an eight-byte asset id, sitting in the application arguments) while the SDK *separately* adds each one to the transaction's reference list. Two independent things on one transaction, and neither is an index into the other. It was not always so: the older form, where the argument really was an index into a foreign array, still exists on the wire and in other people's contracts, and Appendix B keeps it --- together with the consensus-v41 unified access list --- as reference material about transactions you may meet rather than lines you will write.

**Example 11-16.** When automatic population fails

<!-- finder: know when your client cannot work out your resources for you -->

```python
from algopy import ARC4Contract, Bytes, UInt64, arc4, op


class Dynamic(ARC4Contract):
    """A box name the client cannot predict, so it cannot declare it."""

    @arc4.abimethod
    def touch(self, seed: Bytes) -> UInt64:
        # Automatic resource population works by simulating the call and
        # collecting what it reached for. That works when the reach is a
        # function of the arguments. Here the name depends on the round,
        # so the simulate and the real call can disagree and the second
        # fails on a box it never declared.
        name = seed + op.itob(op.Global.round)
        value, _exists = op.Box.get(name)
        return value.length
```

Modern clients build the list for you by simulating the call and collecting what it reached for, which works whenever the reach is a function of the arguments. Example 11-16 is the case where it is not: the box name depends on the round, so the simulate and the real submission can disagree, and the failure lands on a box the transaction never declared. Anything whose resources depend on the *time* of the call rather than on its arguments needs its references declared by hand.

The splitter itself needs none of this yet. Its successor will hold a box per collaborator, and the moment it does, both the payer question and this one arrive together.

## Completing the Splitter
Two things are missing. The second is the smaller and would have survived longer.

```diff
     def split(self, payment: gtxn.PaymentTransaction) -> UInt64:
         assert payment.receiver == Global.current_application_address, "not ours"
+        assert Txn.fee >= Global.min_txn_fee * UInt64(1 + SHARES), "underpaid"
-        share = payment.amount // UInt64(3)
+        share = payment.amount // UInt64(SHARES)
+        self.dust += payment.amount - share * UInt64(SHARES)
         for who in (self.a, self.b, self.c):
-            itxn.Payment(receiver=who, amount=share,
-                         fee=Global.min_txn_fee).submit()
+            itxn.Payment(receiver=who, amount=share, fee=UInt64(0)).submit()
```

Four things outside that hunk did not change: the import line, which already carried every name the additions use; the class declaration and its `a`, `b` and `c` attributes; and both `@arc4.abimethod` decorators, neither of which is `readonly`. Two changed and are not shown: a module constant `SHARES = 3` above the class, which lets the fee arithmetic and the division agree by construction rather than by coincidence, and a `dust: UInt64` attribute beside `a`, `b` and `c`, initialised to zero by the one line `configure` gains. The docstring is reworded and three explanatory comments are added, which accounts for the corrected contract --- Example 11-17, on disk at `examples/costs/fee_splitter_fixed.py`, compiled in CI --- being thirty-four lines against the broken version's twenty-six.

**Example 11-17.** The splitter, corrected

<!-- example: examples/costs/fee_splitter_fixed.py mode=compile -->
<!-- finder: the corrected fee splitter, caller-funded fees and accounted dust -->

```python
from algopy import (Account, ARC4Contract, Global, Txn, UInt64, arc4, gtxn,
                    itxn)

SHARES = 3


class Splitter(ARC4Contract):
    """Split an incoming payment three ways. Every remainder has a destination."""

    a: Account
    b: Account
    c: Account
    dust: UInt64

    @arc4.abimethod
    def configure(self, a: Account, b: Account, c: Account) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        self.a = a
        self.b = b
        self.c = c
        self.dust = UInt64(0)

    @arc4.abimethod
    def split(self, payment: gtxn.PaymentTransaction) -> UInt64:
        assert payment.receiver == Global.current_application_address, "not ours"
        # The caller covers this call and the three inner payments it causes.
        assert Txn.fee >= Global.min_txn_fee * UInt64(1 + SHARES), "underpaid"
        share = payment.amount // UInt64(SHARES)
        # The remainder stays here, named, instead of blurring into the balance.
        self.dust += payment.amount - share * UInt64(SHARES)
        for who in (self.a, self.b, self.c):
            # fee=0 is a decision: the group's pooled fees pay, not the contract.
            itxn.Payment(receiver=who, amount=share, fee=UInt64(0)).submit()
        return share
```

`payment.amount // UInt64(3)` loses up to two microAlgo, every time, for any amount not divisible by three, which is every amount that was not chosen by somebody writing a test. The money did not go anywhere: it stayed in the application account, unaccounted, which is the worst place for it because the contract's own balance is now the sum of a floor it must keep and a remainder it does not know it has. Chapter 7 made the general point that a contract's balance is not its ledger; this is what that looks like when it accumulates one microAlgo at a time.

Floor division leaves the remainder with the contract, never with a recipient, and that is the direction to prefer in every division you write: dust that favours the contract is an accounting problem, and dust that favours the caller is a withdrawal.

::: {.gotcha #dust-favours-the-contract topic="Resource references, MBR, and budget" title="Integer division loses value on every call and the remainder has to live somewhere"}
There is no fractional arithmetic on the AVM, so any split, share, rate or fee calculation loses a remainder to floor division --- small, silent, and absent from any test built on round numbers. Decide where the remainder goes and write it down: added to one recipient's share, carried in a named accumulator, or left in the contract's balance. The one option that is not available is ignoring it, because the remainder does not evaporate: it stays in the application account and quietly stops being distinguishable from the account's minimum balance or from an operator's float. Prefer floor division over any rounding that could favour the caller: dust that accumulates toward the contract is a bookkeeping task, and dust that accumulates toward callers is a slow withdrawal.
:::

Deploy the corrected splitter, fund it with the same one Algo, and replay the two calls from the start of the chapter. The caller now covers four transactions instead of one, so the fee is the only thing about the client that changes:

```console
>>> def split(amount):     # the caller now covers four transactions
...     return splitter.send.split(
...         args=(pay(amount),),
...         params=CommonAppCallParams(
...             static_fee=AlgoAmount.from_micro_algo(4_000)),
...     ).abi_return
...
>>> def dust():            # the remainder, named
...     return splitter.get_global_state()["dust"].value
...
>>> held()                       # funded on deployment
1000000
>>> split(9_000)
3000
>>> split(10_000)
3333
>>> held()
1000001
>>> dust()
1
```

The two returns are the numbers the first version produced, because the division was never the part that was wrong. The account is where the difference is: **994,001** then, **1,000,001** now, on identical calls. And the microAlgo that went missing on the second call is the `1` --- still in the contract, but now in a slot with a name on it rather than in a balance nobody can reconcile.

Send the same call with an ordinary fee and it is refused rather than subsidised:

```console
>>> splitter.send.split(args=(pay(10_000),))    # fee of 1,000
LogicError: Txn KAPV...GC5Q had error 'Runtime error when executing
Splitter (appId: 3103) in transaction 1: underpaid' at PC 133
    ... 10 lines of TEAL trace ...
```

Then run it twenty more times, which is the fourth requirement asking its question:

```console
>>> for _ in range(20):
...     paid = split(10_000)      # the same call, twenty more times
...
>>> held()
1000021
>>> dust()
21
```

The commission, requirement by requirement. Split any incoming payment three ways and forward the shares --- yes, and the three collaborators are 72,993 microAlgo better off apiece, which is 3,000 plus 3,333 plus twenty more 3,333s. Never lose a microAlgo silently --- yes: 219,000 arrived, 218,979 went out, and the 21 that remain are in `dust`, where a query can find them and a later method can spend them. Pay for its own transactions with somebody's money on purpose --- yes, and the refusal above is what *on purpose* means, because a contract that cannot be underpaid cannot be drained by being called. Keep working in month nine exactly as it worked in week one --- yes, and the balance is the whole answer: twenty-two calls in, the account holds *more* than it was funded with rather than less, and every microAlgo of the difference is accounted for. Four for four, and the only number moving in an unexpected direction is one the contract is now keeping deliberately.

## Retrieval
Answer these from memory before moving on. Four of them reach back into earlier chapters on purpose.

1. Four bills, four payers: name each bill and who receives it.
2. Within the first bill, which components are fixed at creation and which can still move?
3. Where does an inner transaction's fee come from if you do not set one, and where does it come from if you do?
4. What does `OpUpFeeSource.AppAccount` spend, and why is that a hazard on a public method?
5. *(From Chapter 5)* A box's minimum balance is a function of what, exactly?
6. *(From Chapter 7)* Why is an application account's balance the wrong number to do accounting with?
7. *(From Chapter 4)* How many key/value pairs does a global slab hold, and who is billed for them?
8. *(From Chapter 10)* A role set in global state has a ceiling. What sets it, and when?
9. How does a client work out which resources a transaction must declare, and name the case where it cannot.
10. Where does the remainder of a floor division go, and why is that the direction to prefer?

## Exercises

1. **(Trace)** A caller sends a two-transaction group to Example 11-1: a payment of 10,000 microAlgo carrying a fee of 1,000, then the `split` call also carrying a fee of exactly 1,000. The contract's account holds 105,000 and its floor is 100,000.
   - **a.** Walk the call and say what the account holds when it settles.
   - **b.** Say how much each collaborator received.
   - **c.** Say how much of the 10,000 is unaccounted for, and where it sits.
   - **d.** Say how many further calls this contract has left before it stops working, and show the arithmetic.

2. **(Parsons)** These lines are the body of a correct `split`, scrambled, with two distractors:

   ```python
   self.dust += payment.amount - share * UInt64(SHARES)
   share = payment.amount // UInt64(SHARES)
   assert Txn.fee >= Global.min_txn_fee * UInt64(1 + SHARES), "underpaid"
   share = payment.amount // UInt64(SHARES) + UInt64(1)
   assert Txn.fee >= Global.min_txn_fee, "underpaid"
   ```

   - **a.** Put the correct lines in an order that works.
   - **b.** Say which pair has a forced order and why.
   - **c.** Say which line could legally sit anywhere, and why the fixed contract puts it first anyway.
   - **d.** Say what each distractor would cost.

3. **(Debug)** A contract charges its users for the boxes they create, using Example 11-4's arithmetic, and refunds them on deletion using the `Txn.sender` variant of Example 11-5. It has been live for a month and its account is slowly losing balance despite every box being paid for.
   - **a.** Say what is happening.
   - **b.** Say who is taking the money.
   - **c.** Say whether they are doing anything the contract forbids.
   - **d.** Say what the contract must store, and at what moment, to close the gap.

4. **(Compare)** Example 11-11 and Example 11-12 both buy opcode budget. Build a table comparing them on: who pays, what appears on chain, whether the contract needs any balance at all, and what happens when the caller does not cooperate. Then name a situation where each is the only workable answer.

5. **(Extend)** The fixed splitter parks the remainder in `dust` and never decides what to do with it.
   - **a.** Find a resolution that makes the accumulator unnecessary altogether.
   - **b.** Find one that keeps it, and say which of the two you would ship and why.
   - **c.** Say at what point the accumulated dust becomes worth a transaction's fee to move.
   - **d.** Say what your answer implies about contracts that split very small payments.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can name the four bills, say who receives each of the two charged in money, and say why that question has no answer for the other two.
- [ ] I can compute an application's minimum balance from its schema, pages and boxes, and say which parts the creator pays.
- [ ] I can explain where an inner transaction's fee comes from and make the caller cover a whole group.
- [ ] I can measure a method's opcode budget from the AVM, buy more, and say whose money each source spends.
- [ ] I can say what a transaction is allowed to touch, and name a case where a client cannot work that out for me.

## Handoff: What the NFT Project Is Billed For
Chapter 12 turns a vesting position into a tradable asset, which means the contract acquires an asset, boxes per position, and a transfer path: new charges under three of the four bills at once. Table 11-1 is what it draws on from here.

: Table 11-1. What Chapter 12 draws on from this chapter

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------------|--------------------------------------|
| Example 11-4 | Charging for the storage a position needs | Each position is a box. Who should pay for it (the minter, the holder, or the contract), and does your answer change when the position is sold? |
| Example 11-5 | Returning a deposit when a position closes | The funder and the holder are now different accounts by design, because the asset moved. Which one gets the refund, and what does the contract have to have stored to know? |
| Example 11-8 | The inner transfers a claim performs | A claim sends an asset. Count the transactions the caller must cover, and say what happens if you count wrong in each direction. |
| Example 11-2 | What the application declares at creation | The project holds an asset and boxes but very little global state. Predict which of its four bills is largest, then check. |
| Exercise 5 | The remainder every partial claim leaves with the contract | You decided when parked dust is worth a fee to move. The project's claims floor toward the contract on every call. Predict where its design finally hands the remainder back, and to whom. |
