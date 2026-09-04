\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# Proving Who's Calling

Chapter 9 left you with a contract that could hold money and hand it back. Every guard it carried was a variation on one line, `assert Txn.sender == something`, and that line was always right, because the vesting contract had exactly one interesting party and the deployer was it. This chapter is about what happens when that stops being true. The line does not get harder; it gets *more*: more parties, more of them not people, and more places where the thing you compare against has to be stored somewhere and can therefore be wrong.

The last chapter established the fact underneath all of it from the other side. A contract has an account and nobody holds its key, so a contract can be a *caller* as easily as it can be a payer. When it is, `Txn.sender` is populated, plausible, and not what you think it is. Authorization on Algorand is not a permissions system you configure. It is a set of assertions you write, against fields whose meaning depends on how you were reached.

Exactly one authority comes free: the ledger records which account created an application, and nothing afterwards can change that record. Every other authority is a value you store, so it is a value something can write --- and where that value lives (in the ledger, in your own global state, beside the record it governs, or outside the call entirely, in a signature made off-chain or a transaction earlier in the same group) is the decision this chapter teaches you to make.

::: {.spec title="Your commission: a pay-to-post message board"}
The contract you build this chapter is a message board that charges for the privilege of writing to it. It must:

1. Accept a post from anyone --- for a fee, 1,000 microAlgo, paid *to the board* in the same atomic group as the call
2. Let the author of a post edit it later, and let nobody else touch it
3. Let one operator change the price, and nobody else
4. Take its operator from the team once, just after deployment

Four requirements, four methods, and every one of them is an authorization decision. At the end of the chapter you will re-run the finished board against this list.
:::

By the end of this chapter you will be able to:

- Choose between the creator address, a stored admin, and a role set, and say what each one costs and what each one survives
- Write a privileged method that cannot be called twice, and say why a creation guard does not give you that
- Attach authority to a *record* rather than to the contract, and say where that authority has to be stored
- Say what `Txn.sender` is when an application calls your method, and name the field that tells you whether a person is on the other end
- Refuse an inner call into a path that should only ever be walked by a human
- Accept authorization that was proved somewhere else: a signature made off-chain, or a transaction earlier in the same group
- Name the checks that belong to a LogicSig and do not belong in a stateful contract, and say what asserting them anyway costs you

## A Pay-to-Post Board, and Who Can Reach It

The commission needs authority from three of the four places it can live, and it is short enough to hold in your head while you check each one: a fee on every post funds moderation, an author owns each post, and an operator owns the price. Here is the board as anyone fresh from the vesting project would first write it --- complete, in full, thirty-eight lines.

**Example 10-1.** Pay-to-post, as first written

<!-- finder: see a working paid message board that anyone can take over -->

```python
from algopy import (Account, ARC4Contract, BoxMap, Global, String, Txn, UInt64,
                    arc4, gtxn)


class PayToPost(ARC4Contract):
    """A board where posting costs a microAlgo fee. Three ways in."""

    admin: Account
    price: UInt64
    next_id: UInt64

    def __init__(self) -> None:
        self.author = BoxMap(UInt64, Account, key_prefix=b"a_")
        self.body = BoxMap(UInt64, String, key_prefix=b"b_")
        self.next_id = UInt64(0)

    @arc4.abimethod
    def initialize(self, admin: Account, price: UInt64) -> None:
        self.admin = admin
        self.price = price

    @arc4.abimethod
    def post(self, payment: gtxn.PaymentTransaction, body: String) -> UInt64:
        assert payment.amount >= self.price, "underpaid"
        post_id = self.next_id
        self.author[post_id] = Txn.sender
        self.body[post_id] = body
        self.next_id = post_id + UInt64(1)
        return post_id

    @arc4.abimethod
    def edit(self, post_id: UInt64, body: String) -> None:
        self.body[post_id] = body

    @arc4.abimethod
    def set_price(self, price: UInt64) -> None:
        assert Txn.sender == self.admin, "admin only"
        self.price = price
```

Example 10-1 is complete and deployable. It compiles clean, it collects a fee, it stores each post's author, and it has an admin-only guard on `set_price` that is entirely correct. It is not a sketch but the shape a working board actually takes, which is why its three holes survive a first reading.

*Predict: three defects, and one of them is in a method that does carry a guard. Write down what each of the three is --- you have the whole contract, and you are not expected to be right yet. Then rank them worst to least, and keep the ranking: the end of the chapter comes back for it.*

Deploy it and use it honestly. This is an **on-chain run** against LocalNet through an algokit-utils typed client. The board's account is funded to one Algo first, because every post writes two boxes and the application account owes their minimum balance:

```console
>>> board.send.initialize(args=(admin.address, 1_000))
>>> board.send.post(args=(pay(board.app_address, 1_000), "hello")).abi_return
0
```

One post, one fee, one id. Now a stranger, on the same board, in the same session. Mallory has an account and five Algo and nothing else: no key of the team's, no role, no invitation:

```console
>>> board.send.edit(args=(0, "defaced"))
>>> board.send.initialize(args=(mallory.address, 0))
>>> board.send.set_price(args=(0,))
>>> board.send.post(args=(pay(mallory.address, 1_000), "free")).abi_return
1
```

**Four calls, no errors.** Not one of them raised, not one of them printed a warning, and the fourth returned a post id exactly as the honest one did. On the third line, `set_price` carries an admin guard, the guard ran, and it passed, because the line above it made Mallory the admin.

The last line's payment went to Mallory's own account, and the board's balance is 1,001,000 microAlgo before it and 1,001,000 microAlgo after. The fee never arrived, the post exists, and the only record the contract keeps says a post was made.

That is what these three defects look like from outside: nothing. No exception, no rejected transaction, no anomaly in a dashboard. The board is doing exactly what it was written to do.

Now ship it anyway, and let a month pass. Four hundred posts, fees apparently arriving, and then a user reports that their post says something they did not write. Not deleted, not reported: *edited*, in place, under their name, and the edit is a normal confirmed transaction the board accepted without complaint.

The second defect turns up while you are looking into the first. The price is zero. Nobody on the team set it to zero, nobody can find a transaction from any account the team controls that set it to zero, and the board has been posting free for eleven days without anything appearing to be wrong.

The third is in the money, and it has been running longest of all. Four hundred posts at a thousand microAlgo should be four hundred thousand in the board's account. It holds a fraction of that. Every one of those posts was accepted, every one of them was paid for, and the contract cannot say which payments arrived: it counted posts, not microAlgo, so the ledger that would settle the question was never written.

Three defects, one contract. As in Chapter 7, every one of them behaves correctly on the path you tested: post honestly, from your own account, paying the board, once. What they have in common is not carelessness. It is that each one checks something *true* and stops --- the payment is real, the caller did sign, the method did run --- without asking the question that would have given the check any force.

The first section below repairs the takeover, the second the edit, and the fourth the payment. The third, on callers that are contracts, repairs nothing in this board; Chapter 12 needs it.

## The Account That Deployed It
The cheapest authority in Algorand is the one you do not have to store. Every application carries a creator address, written by the ledger when the application is created and never writable afterwards: not by you, not by an update, not by anybody.

**Example 10-2.** Creator-only

<!-- finder: restrict a method to the account that deployed the contract -->

```python
from algopy import ARC4Contract, Global, String, Txn, arc4


class Bulletin(ARC4Contract):
    """Anyone may read the notice; only the deployer may change it."""

    notice: String

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.notice = String("")

    @arc4.abimethod
    def set_notice(self, text: String) -> None:
        # `creator_address` is written by the ledger at creation and can
        # never be written again -- not by you, not by anyone. That is the
        # whole of its value: it needs no storage and cannot drift.
        assert Txn.sender == Global.creator_address, "creator only"
        self.notice = text

    @arc4.abimethod(readonly=True)
    def read(self) -> String:
        return self.notice
```

The key line is `assert Txn.sender == Global.creator_address`. It needs no state, costs no minimum balance, and cannot drift out of sync with anything, because there is nothing to keep in sync. That is its appeal and its limit: the creator is fixed forever. If the deploying key is a laptop wallet that later gets rotated, the contract does not care and cannot be told.

For a contract with one permanent operator and no succession story, this is the correct answer and extra machinery is a liability. Reach for it first and move on only when you can name the succession you need.

**Example 10-3.** A stored admin

<!-- finder: hold an admin role in state so it can change hands -->

```python
from algopy import Account, ARC4Contract, String, Txn, arc4


class Bulletin(ARC4Contract):
    """An admin held in state, so the role can outlive the deployer."""

    admin: Account
    notice: String

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.admin = Txn.sender
        self.notice = String("")

    @arc4.abimethod
    def set_notice(self, text: String) -> None:
        assert Txn.sender == self.admin, "admin only"
        self.notice = text

    @arc4.abimethod
    def set_admin(self, new_admin: Account) -> None:
        # One line, and it is the most dangerous line in the contract: a
        # mistyped address here is not recoverable by anybody.
        assert Txn.sender == self.admin, "admin only"
        self.admin = new_admin
```

Storing the admin buys exactly one thing, the ability to change hands, and it costs a global state slot and the risk that comes with any writable authority. `set_admin` is four lines, it is correctly guarded, and it is the most dangerous method in the contract: it hands the role to whatever address it is given, in one transaction, with no confirmation that anyone holds a key for it. A mistyped address is not a mistake you fix. It is a contract with an admin that does not exist.

**Example 10-4.** A two-step handover

<!-- finder: hand an admin role over without a typo losing it forever -->

```python
from algopy import Account, ARC4Contract, Global, Txn, arc4


class Handover(ARC4Contract):
    """Transfer the admin role in two halves, so a typo cannot land."""

    admin: Account
    pending: Account

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.admin = Txn.sender
        self.pending = Global.zero_address

    @arc4.abimethod
    def propose(self, candidate: Account) -> None:
        assert Txn.sender == self.admin, "admin only"
        self.pending = candidate

    @arc4.abimethod
    def accept(self) -> None:
        # The nominee proves control by sending this transaction. An address
        # nobody holds a key for can be proposed, and can never accept, so
        # the role stays where it is.
        assert Txn.sender == self.pending, "not the nominee"
        self.admin = self.pending
        self.pending = Global.zero_address
```

The line that matters is `assert Txn.sender == self.pending`. Nomination and acceptance are separate transactions signed by different accounts, so the nominee proves control of the key by the only means that actually proves it: using it. An address nobody holds can be proposed all day and can never accept, and the role stays where it was.

*The wrong variant is the one above.* `set_admin` in Example 10-3 is not a simplification of this; it is this with the proof removed, and the failure it permits is silent and terminal. When a book shows you a one-step ownership transfer, that is what it is showing you. The two-step version costs four extra lines, and the four lines are the difference between a typo and a permanent loss of control.

::: {.gotcha #admin-transfer-one-step topic="Authorization" title="A one-step ownership transfer has no undo and no confirmation"}
`self.admin = new_admin`, guarded by the current admin, is the obvious implementation and it is a live hazard. The address is accepted without any evidence that a key exists for it: a truncated paste, a testnet address on mainnet, an exchange deposit address that does not sign, and the role is gone. There is no recovery path, because the only account that could fix it is the one that no longer exists. Split it in two --- the holder nominates, the nominee accepts by sending a transaction --- and the failure becomes a nomination that never completes. The same argument applies to any single-transaction transfer of a unique authority: an asset manager address, a stored oracle, a beneficiary.
:::

**Example 10-5.** Initialize once

<!-- finder: stop a configuration method being called a second time -->

```python
from algopy import Account, ARC4Contract, UInt64, arc4


class Vault(ARC4Contract):
    """Configuration that can be written exactly once."""

    owner: Account
    limit: UInt64
    ready: bool

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.ready = False

    @arc4.abimethod
    def initialize(self, owner: Account, limit: UInt64) -> None:
        # Without this line `initialize` is a permanent takeover method:
        # a creation guard protects creation, and this is not creation.
        assert not self.ready, "already initialized"
        self.owner = owner
        self.limit = limit
        self.ready = True
```

`assert not self.ready` is the whole example, and the guard people expect to cover this does not. `create="require"` protects *creation*. `initialize` is not creation; it is an ordinary method that a deploy script happens to call immediately after creation, and nothing enforces that convention. The board's second defect is exactly this: a configuration method with no gate, sitting in public, one call away from being the takeover it eventually was.

In the board, this is the takeover: `initialize` carries no `ready` flag, so it is a public method that hands over the admin role to whoever calls it last. The failure is quiet, because a board taken over this way keeps working perfectly for everyone except its owner.

::: {.gotcha #initialize-is-not-create topic="Authorization" title="A creation guard does not protect the method your deploy script calls next"}
`@arc4.abimethod(create="require")` says a method may only run in the transaction that creates the application, and that is a real guarantee. It says nothing about the method your deploy script calls on the next line. A contract that sets its admin, its price, its oracle or its beneficiary in a separate `initialize` has a public takeover method unless that method refuses to run twice, and the refusal has to be its own stored flag: there is no ledger field for "has this been configured". The usual defence, that only the deployer knows the app id in the seconds after creation, is not a defence: the id is in the block. Either fold the configuration into creation, where `create="require"` genuinely covers it, or carry a boolean and assert on it.
:::

## The Account That Owns the Row
Contract-level roles answer "may this person use the contract". They cannot answer "may this person touch *this*", and most defects in this family are the first check standing in for the second.

**Example 10-6.** Owner of a record

<!-- finder: let only the author of a stored record change it -->

```python
from algopy import Account, ARC4Contract, BoxMap, String, Txn, UInt64, arc4


class Posts(ARC4Contract):
    """Each row remembers who wrote it, because the caller will not."""

    def __init__(self) -> None:
        self.author = BoxMap(UInt64, Account, key_prefix=b"a_")
        self.body = BoxMap(UInt64, String, key_prefix=b"b_")

    @arc4.abimethod
    def post(self, post_id: UInt64, body: String) -> None:
        assert post_id not in self.author, "id taken"
        self.author[post_id] = Txn.sender
        self.body[post_id] = body

    @arc4.abimethod
    def edit(self, post_id: UInt64, body: String) -> None:
        # The check is against the row, not against a global role. "Who may
        # do this" is a property of the thing being acted on, and the only
        # place that fact can live is beside the thing.
        assert self.author[post_id] == Txn.sender, "not your post"
        self.body[post_id] = body
```

`assert self.author[post_id] == Txn.sender`. The authority lives beside the row: written when the row was created, read back when the row is touched. It is not a role and there is no list of who may edit what. The permission is a property of the thing, so it scales with the data and needs no administration at all.

This is the board's first defect in one line. `edit` in Example 10-1 stores an author and then never reads it, which is the particular sting of that bug: the contract had the fact it needed and did not consult it.

**Example 10-7.** A role set

<!-- finder: let a set of accounts share a role, and cap how many -->

```python
from algopy import (Account, ARC4Contract, GlobalMap, StateTotals, Txn,
                    UInt64, arc4)


class Moderated(ARC4Contract, state_totals=StateTotals(global_uints=8)):
    """A role held by a set of accounts, bounded by the global budget."""

    admin: Account

    def __init__(self) -> None:
        # A map reserves NO schema space of its own: `state_totals` above is
        # what makes a write possible, and the 8 there is the ceiling. Leave
        # it out and the contract still deploys, then fails on first write.
        self.moderators = GlobalMap(Account, bool, key_prefix="m")

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.admin = Txn.sender

    @arc4.abimethod
    def grant(self, who: Account) -> None:
        assert Txn.sender == self.admin, "admin only"
        self.moderators[who] = True

    @arc4.abimethod
    def hide(self, post_id: UInt64) -> None:
        assert self.moderators.get(Txn.sender, default=False), "not a moderator"
```

A `GlobalMap` gives you a keyed set inside the application's own slab, and Chapter 4 established the constraint that governs it: each entry is one of the 64 global key/value pairs the whole contract shares. Four facts about that arrangement decide when it is the right one:

- **The map reserves nothing.** `state_totals=StateTotals(global_uints=8)` on the class line is what makes a write possible at all, and the 8 is the ceiling.
- **Omitting the reservation fails late.** Leave it off and the compiler warns, the contract deploys anyway, and the first `grant` fails on chain with `store integer count 1 exceeds schema integer count 0`.
- **The ceiling makes it a roster.** A handful of moderators or a fixed set of operators fits. Anything whose size is a function of how popular you get does not, and belongs in boxes.
- **The two costs land on different accounts.** A global pair costs the *creator's* minimum balance once, at creation --- a figure you budgeted when you chose the schema --- where a box costs the *application account* a per-entry charge somebody has to keep funded.

Chapter 2 introduced that last asymmetry, and it is the pair people most often get backwards. It is also why the map is preferred whenever the set is genuinely bounded: the cost is paid once, by the party who chose the design.

::: {.gotcha #role-set-is-bounded topic="Authorization" title="A role set in global state has a hard ceiling you will hit without warning"}
A `GlobalMap` keyed by account spends one of the application's 64 global key/value pairs per member, and that budget is shared with everything else the contract stores and is fixed at creation unless the contract later approves an `UpdateApplication` that rewrites the global schema --- which none of the contracts in this book before Chapter 24 do. A moderator list built this way works, and then one day `grant` starts failing for a reason that has nothing to do with permissions, and no refused-update contract can widen the schema. Decide at design time whether the set is bounded by its nature (operators, signers, a committee) or by nothing (users, holders, applicants). The first belongs in global state. The second belongs in boxes, where each entry carries its own minimum-balance charge and somebody has to fund it, which is the cost that makes it unbounded in the first place.
:::

**Example 10-8.** A pause switch

<!-- finder: add a switch that stops the contract mutating during an incident -->

```python
from algopy import Account, ARC4Contract, Txn, UInt64, arc4


class Pausable(ARC4Contract):
    """One flag the admin can flip, checked by everything that mutates."""

    admin: Account
    paused: bool
    total: UInt64

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.admin = Txn.sender
        self.paused = False
        self.total = UInt64(0)

    @arc4.abimethod
    def set_paused(self, value: bool) -> None:
        assert Txn.sender == self.admin, "admin only"
        self.paused = value

    @arc4.abimethod
    def add(self, amount: UInt64) -> None:
        assert not self.paused, "paused"
        self.total += amount
```

One flag, flipped by the admin, asserted by everything that mutates. It is the smallest useful piece of incident response a contract can carry, and what it does *not* gate matters as much: `add` is stopped and a hypothetical `read` would not be. A pause that also stops withdrawals traps user funds during exactly the incident it was added for, which is a worse failure than the one it prevents.

## When the Caller Is a Contract
Every method a contract exposes has a set of accounts that may call it and a much larger set that may not, and the contract is the only thing standing between the two. The ledger keeps no access-control list on your behalf, the protocol understands no roles, and there is no modifier to attach to a method. What the AVM hands you is a transaction, and what a transaction carries about its origin is one field: `Txn.sender`, the account that signed it.

That field answers a narrower question than an authorization check is usually asking. It says who signed. It does not say whether that account is the one you meant, whether a person is behind it, or whether it may touch the particular row it is reaching for. Everything so far compares it against an address, and is correct only while the field means what you assumed. It stops meaning that the moment another application calls you.

Figure 10-1 shows what is hardest to believe from a listing: both columns are ordinary, and the field almost everybody reaches for cannot tell them apart.

![Figure 10-1. The two ways a method is reached, and the one field most guards read. Both paths populate `Txn.sender`; only `Global.caller_application_id` separates them, and it is zero exactly when a person called you directly.](figures/caller-identity.svg)

`Txn.sender` is not lying to you in the right-hand column: an application's address really did send that transaction. It is answering a question about *signing* when the guard was trying to ask a question about *authority*, and those two come apart the moment a contract can call you.

**Example 10-9.** Callable only by one application

<!-- finder: restrict a method so only a specific application may call it -->

```python
from algopy import ARC4Contract, Global, UInt64, arc4


class Downstream(ARC4Contract):
    """Callable only from one known application, never directly."""

    trusted: UInt64
    hits: UInt64

    @arc4.abimethod(create="require")
    def create(self, trusted: UInt64) -> None:
        self.trusted = trusted
        self.hits = UInt64(0)

    @arc4.abimethod
    def report(self) -> None:
        # Zero means "no application called me" -- a person did, directly.
        # Comparing against a stored non-zero id therefore excludes people
        # for free. Asserting merely that the id is non-zero excludes them
        # too -- it just tells you nothing about WHICH application called.
        assert Global.caller_application_id == self.trusted, "wrong caller"
        self.hits += UInt64(1)
```

The guard is `assert Global.caller_application_id == self.trusted`, and the *value* that matters is the one it excludes. `Global.caller_application_id` is **zero** when no application called you: when a person called directly. So a check written as "is my caller the app I trust" is also, for free, a check that the caller is not a human, and a contract that reads the field without considering zero has an open door in the shape of an ordinary top-level call.

**Example 10-10.** The caller's address

<!-- finder: compare a calling application against a stored address -->

```python
from algopy import ARC4Contract, Account, Global, arc4


class Downstream(ARC4Contract):
    """The caller's ADDRESS, for when you must compare against an account."""

    trusted: Account

    @arc4.abimethod(create="require")
    def create(self, trusted: Account) -> None:
        self.trusted = trusted

    @arc4.abimethod
    def report(self) -> None:
        # Same fact as the id, in the shape you need when the value is
        # stored beside other addresses. It is the zero address when the
        # call came from a person.
        assert Global.caller_application_address == self.trusted, "wrong caller"
```

The same fact in the shape you need when the value is stored beside other addresses; it is the zero address when a person called. Prefer the id where you can compare ids, because an application address is a hash of the id and comparing the id is both cheaper and harder to get wrong.

**Example 10-11.** No inner calls into an admin path

<!-- finder: insist a privileged method is reached by a person, not a contract -->

```python
from algopy import Account, ARC4Contract, Global, Txn, UInt64, arc4


class Treasury(ARC4Contract):
    """An admin path a contract may never walk, only a person."""

    admin: Account
    limit: UInt64

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.admin = Txn.sender
        self.limit = UInt64(0)

    @arc4.abimethod
    def set_limit(self, value: UInt64) -> None:
        assert Txn.sender == self.admin, "admin only"
        # `Txn.sender` on an inner call is the calling APPLICATION's address.
        # If the admin is ever a contract, or is tricked into a group with
        # one, this guard alone is satisfied by the wrong actor. Requiring
        # a top-level call closes it: no application called me.
        assert Global.caller_application_id == 0, "no inner calls"
        self.limit = value
```

Either assertion alone is insufficient in a way the other repairs. The first says the caller is the admin. The second says a person is on the other end. Without the second, a contract that is *itself* the admin, or an admin that can be induced to call through one, satisfies the guard perfectly, and `Txn.sender` reads as an application address that happens to equal the stored one.

::: {.gotcha #sender-is-not-a-person topic="Authorization" title="Txn.sender is an application address whenever an application called you"}
On an inner application call, `Txn.sender` is the calling application's own address, and every `assert Txn.sender == X` you have written continues to pass or fail on exactly the comparison you wrote. Nothing errors, and the field is not wrong: that application genuinely sent the transaction. `Global.caller_application_id` is the field that separates the cases, and it is zero exactly when a person called you directly. Add `assert Global.caller_application_id == 0` to any path where being reached through another contract would be surprising --- configuration, withdrawal, role changes --- and leave it off the paths where composition is the point, which by Chapter 16 will be most of them. Be explicit either way: a contract that never considered the question is not refusing inner calls, it is accepting them by default.
:::

None of this changes the board, since nothing calls a message board but people. Keep it anyway: Chapter 12 asks whether a vesting claim should be reachable from another contract, and the answer costs something either way.

## Proof From Outside the Call
The last family is authorization established somewhere other than the method you are in, earlier in the group or entirely off-chain. Your code's job is to check the evidence rather than to make the decision.

::: {.note title="Borrowed from Chapter 11: `ensure_budget` --- plumbing, not ideas"}
`op.ed25519verify_bare` costs 1,900 opcode units and an application call is given 700, so Example 10-12 cannot run unaided. The one borrowed line, `ensure_budget(2000)`, issues throwaway inner calls until the budget covers what was asked for, at a fee the caller pays --- 3,000 microAlgo here. Chapter 11 teaches and prices that machinery; nothing this example teaches depends on it.
:::

**Example 10-12.** A signed ticket

<!-- finder: authorize a caller with a signature made off-chain -->

```python
from algopy import ARC4Contract, Bytes, Global, Txn, arc4, ensure_budget, op


class Allowlist(ARC4Contract):
    """Authorization signed off-chain, checked on-chain."""

    signer: Bytes

    @arc4.abimethod(create="require")
    def create(self, signer: Bytes) -> None:
        self.signer = signer

    @arc4.abimethod
    def redeem(self, ticket: Bytes) -> None:
        # Chapter 11's machinery: the verify below cannot fit in one
        # call's opcode budget, so buy room and bill the caller.
        ensure_budget(2000)
        # The message binds the ticket to THIS caller and THIS application.
        # Sign only the ticket and the same signature works for everyone,
        # everywhere, forever -- which is the whole of the attack.
        message = Txn.sender.bytes + op.itob(Global.current_application_id.id)
        assert op.ed25519verify_bare(message, ticket, self.signer), "bad ticket"
```

What matters is the *message*, not the verification. `op.ed25519verify_bare` will happily confirm a valid signature over whatever bytes you hand it, so the security of the scheme is entirely in what those bytes commit to. Here they commit to the caller and to this application, which is what makes a ticket un-transferable and un-replayable across deployments. Sign only the ticket id and you have built a bearer token: valid for anyone who obtains it, against every contract that trusts the same key, forever.

**Example 10-13.** A client-side atomic group

<!-- finder: build a payment and an app call as one atomic group from the client -->

```python
"""Build the payment and the app call as ONE group, from the client."""

import sys
from pathlib import Path

from algokit_utils import (AlgoAmount, AlgorandClient, AppClient,
                           AppClientMethodCallParams, AppClientParams,
                           PaymentParams)


def main(app_id: int, spec_path: str) -> int:
    algorand = AlgorandClient.from_environment()
    author = algorand.account.localnet_dispenser()
    client = AppClient(AppClientParams(
        app_spec=Path(spec_path).read_text(), algorand=algorand,
        app_id=app_id, default_sender=author.address))
    pay = algorand.create_transaction.payment(PaymentParams(
        sender=author.address, receiver=client.app_address,
        amount=AlgoAmount.from_micro_algo(1_000)))
    # One group, built in order: the contract asserts the payment is at
    # index 0 and itself at index 1, so the order here is not cosmetic.
    result = client.send.call(AppClientMethodCallParams(
        method="post", args=[pay, "hello"],
        box_references=[b"a_" + (0).to_bytes(8, "big"),
                        b"b_" + (0).to_bytes(8, "big")]))
    return int(result.abi_return)


if __name__ == "__main__":
    print(main(int(sys.argv[1]), sys.argv[2]))
```

This is the other half of every grouped-payment check in Chapter 7, written from the caller's side: the contract's assertions about group shape are only meaningful against a client that builds the group deliberately. The order is not cosmetic, and it matters who enforces it. Nothing in the board's own listing mentions a group index. The ARC-4 router does it for you, and the check it emits is *relative*: the payment must sit immediately before the app call and must be of type `pay`. So a group with an unrelated transaction in front of both still works, and one that puts the payment after the call does not. Chapter 7 established that rule; this is the client side of it. Example 10-16 pins absolute positions instead, asserting its own `group_index` and `group_size` because it chooses to.

None of that says whose payment it is. A group an attacker assembles is as well-formed as one your client assembles, and the router checks the same things about both.

::: {.gotcha #funder-must-be-the-credited-account topic="Authorization" title="Assert that the funding transaction's sender is the account being credited"}
A method that reads a payment out of the group and credits `Txn.sender` names two accounts, and they are two different accounts unless you say they are the same one. Left unasserted, anyone can build a group that pairs *somebody else's* pending payment with their own app call and take the position it paid for: the payment is valid, the app call is valid, and the contract credits the wrong party. Whenever a grouped transfer funds something booked to `Txn.sender`, assert `payment_txn.sender == Txn.sender`. If you want third-party sponsorship, model the beneficiary as an explicit method argument rather than leaving it implied.
:::

A group can carry more than payments. An application call leaves something behind for the rest of the group to read --- its *scratch space*, working memory that lives exactly as long as the transaction that wrote it --- and that is enough to split an authorization in two: one contract makes the decision, and a later call in the same group acts on it. The pair below is a gatekeeper that holds the roster and a protected contract that never sees it.

**Example 10-14.** A gatekeeper that stashes its verdict

<!-- finder: stash who passed a check for a later transaction in the group to read -->

```python
from algopy import (Account, ARC4Contract, GlobalMap, StateTotals, Txn, arc4,
                    op)


class Gatekeeper(ARC4Contract, scratch_slots=(0,),
                 state_totals=StateTotals(global_uints=8)):
    """Holds the roster. Leaves WHO PASSED in slot 0, for one group."""

    admin: Account

    def __init__(self) -> None:
        self.members = GlobalMap(Account, bool, key_prefix="m")

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.admin = Txn.sender

    @arc4.abimethod
    def grant(self, who: Account) -> None:
        assert Txn.sender == self.admin, "admin only"
        self.members[who] = True

    @arc4.abimethod
    def approve(self) -> None:
        # The check runs against state only this contract holds. Scratch
        # is per-transaction and dies with it: slot 0 carries the verdict
        # for exactly as long as this group is still executing.
        assert self.members.get(Txn.sender, default=False), "not a member"
        op.Scratch.store(0, Txn.sender.bytes)
```

The roster and its `grant` are Example 10-7's role set again; the new lines are the last one and the class line. `scratch_slots=(0,)` is a reservation rather than a requirement: it marks slot 0 off-limits to the compiler, which otherwise spends slots on work of its own. And because scratch dies with the transaction that wrote it, the verdict in slot 0 is not storage. It is a message with the lifespan of the group, and only a *later* transaction in the same group can collect it.

**Example 10-15.** Acting on a verdict left earlier in the group

<!-- finder: read an approval an earlier app call left, checking who wrote it -->

```python
from algopy import ARC4Contract, Txn, UInt64, arc4, gtxn, op


class Protected(ARC4Contract):
    """Never sees the roster. Trusts the gatekeeper's verdict -- verified."""

    gatekeeper: UInt64

    @arc4.abimethod(create="require")
    def create(self, gatekeeper: UInt64) -> None:
        self.gatekeeper = gatekeeper

    @arc4.abimethod
    def act(self, index: UInt64) -> None:
        # Only backwards, and only application calls: `gload` cannot see
        # a transaction that has not run yet.
        assert index < Txn.group_index, "must be an earlier transaction"
        # Any application may write its own slot 0. The verdict is
        # evidence only if the app that wrote it is the one you trust.
        appl = gtxn.ApplicationCallTransaction(index)
        assert appl.app_id.id == self.gatekeeper, "not the gatekeeper"
        assert op.gload_bytes(index, 0) == Txn.sender.bytes, "not approved"
```

`op.gload_bytes` reads a scratch slot left by an earlier application call in the same group; the client builds the two calls into one group exactly as Example 10-13 built a payment and a call. Two restrictions make the read safe to build on, and both are enforced by the AVM rather than by the first assertion: reading forward fails with `gloads can't get future scratch space`, and reading a payment fails with `can't use gloads on non-app call txn`. The assertion buys a better message, not a guarantee. One more thing makes the design sound, and it is a property of the *gatekeeper*, not of this contract: the app-id pin authorizes every method of that application, and it is only sufficient here because `approve` is the only Gatekeeper method that writes slot 0. Add a second slot-writing method to the gatekeeper and this check authorizes it too, whether you meant it to or not.

The middle assertion is the one carrying the authorization. `gload` will read slot 0 of *any* earlier application call, and any application may write whatever it likes into its own scratch, so an attacker who deploys a contract whose only job is to stash the attacker's address has manufactured a verdict. Pinning the writer's app id against the stored one is what turns "a value was left for me" into "the contract holding the roster approved someone." The last assertion says *whom*: the account signing this call, not whoever happened to be approved earlier in the group.

**Example 10-16.** The checks that are not yours

<!-- finder: know which transaction fields a stateful contract should not police -->

```python
from algopy import ARC4Contract, Global, Txn, UInt64, arc4, gtxn


class Deposits(ARC4Contract):
    """Check what the payment PROVES. Nothing else is yours to police."""

    total: UInt64

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.total = UInt64(0)

    @arc4.abimethod
    def deposit(self, payment: gtxn.PaymentTransaction) -> None:
        # Chapter 7's four questions, narrowed: an Algo payment has
        # no asset to check, and the group's shape has to be pinned before
        # any of the rest means anything. Who sent it, who it went to, how
        # much, and where in the group it sits.
        assert Txn.group_index == 1, "app call must follow the payment"
        assert Global.group_size == 2, "exactly two transactions"
        assert payment.sender == Txn.sender, "deposit for yourself"
        assert payment.receiver == Global.current_application_address, "not ours"
        assert payment.amount > 0, "pay something"
        self.total += payment.amount
```

Example 10-16 checks four things about an incoming payment and stops, and what it stops short of is the point. **It is deliberately not the same four as Chapter 7's.** That chapter's four --- which asset, how much, where it went, whose it was --- were about a *transfer* arriving at a vault. An Algo payment has no asset to ask about, so that question goes; and a stateful contract validating a group has to pin the group's shape before any answer about the payment means anything, so the position takes its place. Same discipline, one question swapped, and the swap reflects the difference between the two situations rather than a correction of the first. Here is the same contract with two more assertions, of a kind that appears in a great deal of published Algorand code:

```python
from algopy import ARC4Contract, Global, UInt64, arc4, gtxn


class Deposits(ARC4Contract):
    """The same contract, plus two checks that belong to a LogicSig."""

    total: UInt64

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.total = UInt64(0)

    @arc4.abimethod
    def deposit(self, payment: gtxn.PaymentTransaction) -> None:
        assert payment.receiver == Global.current_application_address, "not ours"
        # These two protect nothing here: they are mandatory in a LogicSig,
        # which signs for an account, and this contract signs for nobody.
        assert payment.rekey_to == Global.zero_address, "no rekey"
        assert payment.close_remainder_to == Global.zero_address, "no close"
        self.total += payment.amount
```

Those two lines are mandatory in a **LogicSig**, which is a program that signs on an account's behalf and must therefore refuse to let the transaction it approves rekey or empty that account. Chapter 21 is where that checklist earns its place. A stateful contract signs for nobody. It has no key, it approves nothing on anyone's behalf, and a `rekey_to` on the caller's own payment is the caller's business with their own wallet.

So the two assertions protect nothing, and they are not free: they reject honest callers whose wallet batched a rekey or a close-out into the same group, which is a legitimate thing for a wallet to do and not something your user chose. The habit is contagious. It looks like diligence, it passes every review, and the only way to see it is to ask what the check would prevent and find that the answer is nothing.

::: {.gotcha #logicsig-checks-in-a-contract topic="Authorization" title="rekey_to and close_remainder_to are a LogicSig's job, not a stateful contract's"}
The checks a LogicSig must make --- `rekey_to` and `close_remainder_to` against the zero address, because a LogicSig signs on an account's behalf --- protect nothing when copied into a stateful contract's validation of an incoming grouped payment. The contract is not signing that payment; the caller is. The fields belong to the caller's own account, and the only effect of asserting on them is to refuse honest users whose wallet did something ordinary, like batching a rekey or a close-out into the same group. Check what the transaction proves about the money --- sender, receiver, amount, asset, and the group it sits in --- and leave the caller's wallet alone.
:::

There is one place the two fields are a stateful contract's business: the inner transactions it builds itself. There, an assertion is still the wrong tool.

::: {.gotcha #inner-rekey-yours-to-not-set topic="Authorization" title="An inner transaction's rekey_to is yours to not set, not yours to assert"}
An inner transaction's fields start at zero --- the AVM populates a sender, a fee, and a validity window, and nothing else --- so a contract that never sets `rekey_to` cannot get it wrong. It *can* set it, and `rekey_to` on an inner transaction hands your application account to whoever holds that key; no assert can undo a value you supplied. The defence is not a check but the absence of the line.
:::

In the board, this is the missing fee. Two of Example 10-16's four questions --- who paid, and who they paid --- are exactly the two the broken `post` never asked.

## Every Guard the Board Needs

Three defects, three corrections, and one of them is two lines because the check it replaces was never a single question.

```diff
     def __init__(self) -> None:
+        self.ready = False
     def initialize(self, admin: Account, price: UInt64) -> None:
+        assert not self.ready, "already initialized"
         self.admin = admin
         self.price = price
+        self.ready = True
     def post(self, payment: gtxn.PaymentTransaction, body: String) -> UInt64:
+        assert payment.receiver == Global.current_application_address, "not ours"
+        assert payment.sender == Txn.sender, "pay for your own post"
         assert payment.amount >= self.price, "underpaid"
     def edit(self, post_id: UInt64, body: String) -> None:
+        assert self.author[post_id] == Txn.sender, "not your post"
```

Three things the diff does not touch. The import line: every name the additions use was already imported for something else, `Global` included, which is a small part of why these defects are easy to ship. `set_price`: the diff never touches it, and Example 10-1 said it was correct, which it was. And every `@arc4.abimethod` decorator; none of them gains an argument, and in particular none gains `create="require"`, which would not have helped. One thing did change and is not shown: the class docstring, which described three ways in and now describes three ways in, closed. The complete corrected contract is Example 10-17 --- on disk at `examples/authorization/pay_to_post_fixed.py`, compiled in CI --- forty-five lines against the broken version's thirty-eight.

The `post` correction is two assertions because "was I paid" is two questions --- *to me* and *by the caller* --- and the original asked neither while appearing to ask about payment. The whole of the `edit` fix is a read of data the broken contract was already writing. Neither correction adds a feature. Both consult evidence that was already there.

**Example 10-17.** The board, corrected

<!-- example: examples/authorization/pay_to_post_fixed.py mode=compile -->
<!-- finder: the corrected pay-to-post board, every authorization guard in place -->

```python
from algopy import (Account, ARC4Contract, BoxMap, Global, String, Txn, UInt64,
                    arc4, gtxn)


class PayToPost(ARC4Contract):
    """A board where posting costs a microAlgo fee. Three ways in, closed."""

    admin: Account
    price: UInt64
    next_id: UInt64
    ready: bool

    def __init__(self) -> None:
        self.ready = False
        self.author = BoxMap(UInt64, Account, key_prefix=b"a_")
        self.body = BoxMap(UInt64, String, key_prefix=b"b_")
        self.next_id = UInt64(0)

    @arc4.abimethod
    def initialize(self, admin: Account, price: UInt64) -> None:
        assert not self.ready, "already initialized"
        self.admin = admin
        self.price = price
        self.ready = True

    @arc4.abimethod
    def post(self, payment: gtxn.PaymentTransaction, body: String) -> UInt64:
        assert payment.receiver == Global.current_application_address, "not ours"
        assert payment.sender == Txn.sender, "pay for your own post"
        assert payment.amount >= self.price, "underpaid"
        post_id = self.next_id
        self.author[post_id] = Txn.sender
        self.body[post_id] = body
        self.next_id = post_id + UInt64(1)
        return post_id

    @arc4.abimethod
    def edit(self, post_id: UInt64, body: String) -> None:
        assert self.author[post_id] == Txn.sender, "not your post"
        self.body[post_id] = body

    @arc4.abimethod
    def set_price(self, price: UInt64) -> None:
        assert Txn.sender == self.admin, "admin only"
        self.price = price
```

Deploy the corrected board, initialize it from the team's account, and replay the session from earlier in the chapter --- the honest post first, then Mallory's four calls:

```console
>>> board.send.post(args=(pay(board.app_address, 1_000), "hello")).abi_return
0
>>> board.send.edit(args=(0, "defaced"))          # Mallory, from here down
LogicError: Txn V3JQ...N4A had error 'not your post'
    ... 10 lines of TEAL trace ...
>>> board.send.initialize(args=(mallory.address, 0))
LogicError: Txn 7RKD...Q2M had error 'already initialized'
    ... 10 lines of TEAL trace ...
>>> board.send.set_price(args=(0,))
LogicError: Txn KX2W...B7T had error 'admin only'
    ... 10 lines of TEAL trace ...
>>> board.send.post(args=(pay(mallory.address, 1_000), "free"))
LogicError: Txn ZM8H...C5F had error 'not ours'
    ... 10 lines of TEAL trace ...
```

The third refusal is the guard that already existed, working now because the takeover it sat on top of is closed. The commission, requirement by requirement: anyone may post, for a fee paid to the board --- yes, and the board now holds one fee for every post it records, which is the invariant the broken version could not state. Only the author may edit --- yes, by a read of the author the board was storing all along. Only the operator may change the price --- yes. The operator is set once --- yes, and the second `initialize` is the transcript's second refusal. Four for four, and every refusal is a sentence a stranger can read.

Against the ranking you wrote down at the start: the payment was worst, because it ran longest and destroyed the record that would have measured it. The takeover was next, because it was recoverable only by luck: Mallory set the price to zero rather than draining anything. The defacement, the one found first and fixed in an afternoon, was least. Defects are found in the order they are visible, which is close to the reverse of the order they cost.

## Retrieval
Answer these from memory before moving on. Four of them reach back into earlier chapters on purpose.

1. Which authority costs no storage and can never change, and what does a one-step transfer of a stored one risk that a two-step transfer does not?
2. What is `Global.caller_application_id` when a person calls your method directly?
3. *(From Chapter 3)* What does `create="require"` actually promise, and why is that not enough to protect an `initialize` method?
4. Where does the authority to edit a record live, and when is it written?
5. What must the signed message in a ticket scheme commit to, and what breaks if it commits only to the ticket?
6. *(From Chapter 7)* Name four things a grouped payment does not prove by existing.
7. *(From Chapter 4)* A ClearState transaction deletes an account's local slab and the contract cannot refuse it. What does that mean for a permission you stored in local state?
8. *(From Chapter 5)* A box's minimum balance is a function of what, exactly, and which account pays it?
9. Why does asserting `rekey_to == Global.zero_address` on an incoming payment protect nothing in a stateful contract?
10. `gload` can read scratch from which transactions in the group, and which of Example 10-15's three assertions would the AVM still enforce if you deleted it?

## Exercises

1. **(Trace)** A group holds two transactions: a payment at index 0 and an application call at index 1 that invokes `post` on the corrected board. The payment's sender is Alice, its receiver is the application, its amount is 1,000. The application call is signed by Bob.
   - **a.** Walk the three assertions in `post` in order and name the one that fails.
   - **b.** Say what Bob, the caller, sees.
   - **c.** Say what Bob would have to change to make the group pass.
   - **d.** Say whether that change is one Bob can make alone.

2. **(Parsons)** These three lines are the body of a correct `accept` method for Example 10-4, in scrambled order:

   ```python
   self.pending = Global.zero_address
   self.admin = self.pending
   assert Txn.sender == self.pending, "not the nominee"
   ```

   - **a.** Put them in the only order that works.
   - **b.** For each line, say why it cannot come earlier.
   - **c.** Say what breaks if the **last two** are swapped: the contract still compiles, the method still returns, and the role lands somewhere nobody can reach.
   - **d.** Swapping the first and last instead gives a method that can never succeed at all. Say why that failure is the kinder of the two.

3. **(Debug)** A contract carries this guard on its withdrawal method, and an auditor has flagged it:

   ```python
   assert Txn.sender == self.admin, "admin only"
   assert Txn.rekey_to == Global.zero_address, "no rekey"
   ```

   - **a.** Say which of the two lines is doing nothing and which is insufficient.
   - **b.** Say what the insufficient one fails to exclude.
   - **c.** Write the line that closes the gap.
   - **d.** Say what would have to be true about this contract for the *first* line to be wrong as well.

4. **(Compare)** Example 10-2, Example 10-3 and Example 10-7 are three answers to "who may operate this contract".
   - **a.** Build a table with a row for each and columns for: storage cost, whether the authority can change hands, what happens if the holder loses their key, and what happens on an upgrade.
   - **b.** Name a contract for which each row is the *right* answer.
   - **c.** For each of your three contracts, say what would have to change about it to move it to the next row.

5. **(Extend)** Example 10-6 lets an author edit their own post and nobody else. Add moderation: an account in a role set may *hide* any post, but may not edit one, and the author may not un-hide.
   - **a.** Write the `hide` method and the state it needs.
   - **b.** When a moderator hides a post and the author edits it afterwards, what should happen? Decide, and say why.
   - **c.** Name the assertion in your answer to (a) that enforces your answer to (b).
   - **d.** The hidden flag in your answer to (a) is state beside every post, and posts are unbounded. Say where that state must live and which account's balance it raises --- and notice that this chapter has given you no way to put a number on it. Chapter 11 prices it; Chapter 12 pays it per record.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can name the authority that needs no storage, say the one thing it cannot do, and hand a role over without a typo losing it.
- [ ] I can accept authorization proved somewhere else (a signature made off-chain, or a value left by an earlier transaction in the group) and say what the signed message has to commit to.
- [ ] I can say what `Txn.sender` is when an application calls me, and which field tells me a person did.
- [ ] I can put the authority for a record beside the record, and say why a contract-level role cannot answer that question.
- [ ] I can name two assertions that belong in a LogicSig and not in a stateful contract, and say what asserting them anyway costs.

## Handoff: Who the NFT Project Lets In
Chapter 12 builds a transferable vesting position: the right to a stream of tokens becomes an asset that can change hands, which means the question "who may claim this" stops having a fixed answer. Table 10-1 is what that project draws on from here. Two of the five have answers this chapter will have led you to get wrong.

: Table 10-1. What Chapter 12 draws on from this chapter

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------------|--------------------------------------|
| Example 10-6 | Authority attached to a record rather than to the contract | The vesting schedule's owner changes when the NFT moves. Where must the check read from, if the answer has to change without any method being called? |
| Example 10-5 | A privileged method that cannot run twice | The project mints one NFT against one vesting stream. What goes wrong if the mint is re-runnable, and who ends up holding a claim? |
| Example 10-16 | Evidence a transaction does and does not carry | Claiming sends tokens out. The caller is proving they *hold* an asset, not that they sent one, so which of this chapter's four questions even applies, and is the honest answer "none of them"? |
| Example 10-9 | `Global.caller_application_id` and what zero means | Should a vesting claim be callable by another contract? Decide before you see the project's answer, and say what it costs either way. |
| Exercise 5 | The box each position pays for before `create_schedule` will write it | Your moderation flag needed a home beside every record, at a price this chapter could not name. Each vesting position carries a box and an asset. What did Chapter 11 have to teach before Chapter 12 could charge for either? |
