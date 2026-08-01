\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# Contracts That Talk to Contracts

Chapter 10 was about inbound identity: somebody calls your method, and you decide whether they may. This chapter is the same question pointed the other way. Your contract is the caller now, and the thing it is reaching for is named by a number.

That number is an application id, and the AVM will not check it for you. It will not check that the application at that id is the one you meant, that it was deployed by anyone you trust, or that its `price()uint64` returns a price rather than a preference. It will dispatch the call, decode a `uint64` from the reply, and hand it to you. Everything the reply is worth rests on where the id came from.

## Reaching Another Application
A lending market has to know what the collateral is worth, and the price lives in an oracle somebody else deployed. A farm has to read a pool's reserves before it can value a stake. A factory has to deploy the pools it will later trust, and put enough in each one that it can hold what it is given. None of that fits inside a single program.

Three mechanisms cover all of it. A contract can call another application's method, which runs the callee's code and returns whatever the callee returns. It can read another application's state, which runs none of that code and needs no cooperation from whoever wrote it. And it can deploy an application outright, which hands back an id, an address, and an account with nothing in it.

All three need an application id, and the obvious place to get one is from the caller.

Figure 15-1 is the shape of it: your call, the calls it spawns, and the two places identity is decided --- once by the caller you validated on the way in, and once by the id you chose on the way out.

![Figure 15-1. One call, and the two places identity is decided. Inbound, your contract asserts on who is calling. Outbound, an application id decides what answers --- and the AVM checks nothing about it.](figures/call-tree.svg)

::: {.spec title="Your commission: a payroll that spawns its worker"}
The system you build this chapter is contract payroll for a studio: a parent contract, and a worker contract the parent itself deploys to keep the ledger. It must:

1. Spawn the worker from inside the parent --- program, schema and account
2. Record jobs on the worker, with nobody but the parent able to write them
3. Pay out what the worker reports owed --- to the studio, and to nobody else
4. Consult no worker the parent did not itself create
5. Leave the worker it spawns able to pay for its first box

Five requirements, six methods across two contracts. At the end of the chapter you will hold the corrected pair against this list.
:::

By the end of this chapter you will be able to:

- Call another application's method with the compiler deriving the selector, and by signature string when you have no source to import
- Say where an application id may come from, and name the shape that lets a caller aim your contract at one they wrote
- Read another application's global state, local state and creation parameters without calling it, and say what each read costs
- Say what a group-mate's writes and creations are visible to, and why that follows from one rule rather than two
- Stage several inner transactions and submit them as one group, and say when that is necessary rather than tidy
- Deploy a contract from inside a contract, fund it, and say what each of the two accounts is billed for it
- Say how deep a chain of application calls may go, and what the ninth one reports

## A Payroll Parent and Its Worker
Two contracts carry that commission: the worker records jobs as they are assigned and reports what it is owed; the parent spawns, assigns and settles. Three methods on each side, both deployed from the same repository, and the studio's own scripts are the only client. One call in `spawn` is an IOU --- `compile_contract`, the worker's program packaged inside the parent's --- and Example 15-12 redeems it.

**Example 15-1.** Payroll and its worker, as first written

<!-- finder: see a parent contract that pays whichever child it is handed -->

```python
from algopy import (Application, ARC4Contract, BoxMap, Global, GlobalState,
                    Txn, UInt64, arc4, compile_contract, itxn)


class Worker(ARC4Contract):
    """The child: keeps a ledger of assigned work, reports what is owed."""

    def __init__(self) -> None:
        self.parent = GlobalState(UInt64(0))
        self.owed = GlobalState(UInt64(0))
        self.jobs = BoxMap(UInt64, UInt64, key_prefix=b"j_")

    @arc4.baremethod(create="require")
    def create(self) -> None:
        # Created by an inner transaction, so the caller id is the parent's.
        self.parent.value = Global.caller_application_id

    @arc4.abimethod
    def record(self, job: UInt64, amount: UInt64) -> None:
        assert Global.caller_application_id == self.parent.value, "parent only"
        self.jobs[job] = amount
        self.owed.value += amount

    @arc4.abimethod(readonly=True)
    def amount_due(self) -> UInt64:
        return self.owed.value


class Payroll(ARC4Contract):
    """The parent: spawns the worker, assigns jobs, settles what is owed."""

    def __init__(self) -> None:
        self.spawned = GlobalState(UInt64(0))

    @arc4.abimethod
    def spawn(self) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.spawned.value == UInt64(0), "already spawned"
        compiled = compile_contract(Worker)
        created = itxn.ApplicationCall(
            approval_program=compiled.approval_program,
            clear_state_program=compiled.clear_state_program,
            global_num_uint=compiled.global_uints,
            global_num_bytes=compiled.global_bytes,
            fee=UInt64(0),
        ).submit()
        self.spawned.value = UInt64(1)
        return created.created_app.id

    @arc4.abimethod
    def assign(self, worker: Application, job: UInt64, amount: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        arc4.abi_call(
            Worker.record, job, amount, app_id=worker, fee=UInt64(0)
        )

    @arc4.abimethod
    def settle(self, worker: Application) -> UInt64:
        due, _txn = arc4.abi_call(Worker.amount_due, app_id=worker, fee=UInt64(0))
        itxn.Payment(receiver=Txn.sender, amount=due, fee=UInt64(0)).submit()
        return due
```

Example 15-1 is complete and deployable. `spawn` and `assign` refuse anybody but the creator, the worker's `record` refuses anybody but its parent, every inner transaction carries `fee=UInt64(0)`, and `spawn` cannot run twice. Two of its habits are defects, and only one of them ever announces itself.

*Predict: two defects in the parent. One fails on the first engagement, loudly, with an error about an account. The other fails once, eleven weeks in, and looks like a payment. Write both down before reading on.*

`spawn` succeeds and returns an id, so the loud one arrives a call later, when the first `assign` runs. `spawn` created the worker and sent it nothing, and a newly created application's account holds zero; creation allocates an address, not a balance. The worker's first `record` writes a box, and a box has to be paid for by the account that holds it, which Chapter 11 priced at 2,500 plus 400 a byte on top of the account's own 100,000 floor.

```console
>>> worker_id = payroll.send.spawn().abi_return
>>> payroll.send.assign(args=(worker_id, 1, 5_000))
AlgodHTTPError: TransactionPool.Remember: transaction QBRWBB3EYZBT...:
account ZKUEGI5E4ZJ26HZACKF74HZ57DRQ4IWBVAWOL7LAQGJK2ARFSHHCU75TBQ
balance 0 below min 109700 (0 assets)
```

The refusal comes from the ledger rather than from anybody's assertion, and the account it names is the worker's --- not the studio's, not the parent's. 109,700 is Chapter 11's formula out loud: 100,000 for the account to exist, plus 2,500 and 400 a byte over an eighteen-byte box. The balance beside it is zero. The studio funded the worker by hand, `assign` went through, and the engagement proceeded.

The quiet one is in a method signature:

```python
    def settle(self, worker: Application) -> UInt64:
```

`settle` asks its caller which worker to consult. On every engagement so far the caller was the studio and the id was the right one, so nothing distinguished a correct call from a lucky one. Eleven weeks in, the parent paid out twenty-five Algo against a worker that had recorded no jobs at all. That worker is real, deployed, and answering. It is also eleven lines long, it was deployed by somebody outside the studio, and its `amount_due` is a single `return`:

**Example 15-2.** The worker that is not one

<!-- finder: see how little it takes to impersonate a contract -->

```python
from algopy import ARC4Contract, UInt64, arc4


class Worker(ARC4Contract):
    """Eleven lines that answer to the same signature as the real thing."""

    @arc4.abimethod(readonly=True)
    def amount_due(self) -> UInt64:
        # No ledger, no jobs, no parent. Just a number that suits whoever
        # deployed it, waiting for a contract that trusts its argument.
        return UInt64(25_000_000)
```

There is no forgery in it. It is a contract with an `amount_due()uint64` method, which is all the selector matches on, and it was deployed by somebody who read the studio's repository. The parent called it, decoded a `uint64`, and paid the account that asked:

```console
>>> payroll.send.settle(args=(impostor_id,)).abi_return   # sent by a stranger
25000000
>>> stranger_after - stranger_before                      # microAlgo
24997000
```

Twenty-five Algo out of the parent, and the stranger is 24,997,000 better off --- the whole amount less the 3,000 microAlgo they paid to pool the fees for their own call. `settle` sends to `Txn.sender`, so the person who names the worker is the person who gets the money.

Neither defect is a wrong line. Both are habits: the parent handed the new id back to its caller instead of keeping it, and it gave the new account nothing to spend.

## Calling Another Application's Methods
An application call from inside a contract is an inner transaction like any other, and there are two spellings depending on whether you have the callee's source.

**Example 15-3.** A typed call

<!-- finder: call another contract's method with the compiler checking it -->

```python
from algopy import Application, ARC4Contract, UInt64, arc4


class Oracle(ARC4Contract):
    """The contract being called. Deployed separately; imported for its types."""

    @arc4.abimethod(readonly=True)
    def price(self) -> UInt64:
        return UInt64(42)


class Consumer(ARC4Contract):
    @arc4.abimethod
    def buy_at_oracle_price(self, oracle: Application) -> UInt64:
        # The method object, not a string: the compiler derives the selector,
        # encodes the arguments, and decodes the return value, so a typo is a
        # compile error here instead of a mismatched selector on chain.
        # The id arrives as a parameter to keep this to one idea. Where it is
        # allowed to come from is the subject of the next two examples.
        result, _txn = arc4.abi_call(Oracle.price, app_id=oracle)
        return result
```

Passing the method object rather than a name is what buys the checking. `arc4.abi_call(Oracle.price, app_id=oracle)` derives the selector from the signature, encodes the arguments to their ABI types, and decodes the reply to the declared return type. Rename `price` or change its return type and this stops compiling, which is the outcome you want; the alternative is a four-byte selector that matches nothing on chain and a router that answers `err` with nothing to say.

It returns a pair. The result comes first and the inner transaction second, which is why every call in this chapter unpacks two names even when it only wants one.

`itxn.abi_call` builds the same call and stops short of sending it.

**Example 15-4.** Calling by signature string

<!-- finder: call a contract whose source you do not have -->

```python
from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class Consumer(ARC4Contract):
    """Call a contract you do not have the source of."""

    def __init__(self) -> None:
        self.oracle_id = GlobalState(UInt64(0))

    @arc4.abimethod
    def configure(self, oracle_id: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.oracle_id.value == UInt64(0), "already configured"
        self.oracle_id.value = oracle_id

    @arc4.abimethod
    def read_price(self) -> UInt64:
        # No source to import, so the signature is spelled out and the return
        # type supplied in brackets. The id comes from state the creator wrote
        # once -- never from the caller, who could name any app they built.
        result, _txn = arc4.abi_call[arc4.UInt64](
            "price()uint64", app_id=self.oracle_id.value
        )
        return result.as_uint64()
```

Most contracts you integrate with are not in your repository. Spell the signature out, supply the return type in brackets so the decoder knows what it is reading, and the mechanism is otherwise identical, with the checking gone because there is no longer anything for the compiler to check against.

The line that matters is not the call. It is `self.oracle_id.value`, written once by `configure` under a creator guard and read here. Compare it with the same method aimed differently:

```python
from algopy import Application, ARC4Contract, UInt64, arc4


class Consumer(ARC4Contract):
    """The same call, aimed by whoever is calling."""

    @arc4.abimethod
    def read_price(self, oracle: Application) -> UInt64:
        # The caller picks the oracle. Anyone can deploy a contract with a
        # price()uint64 method that returns whatever number suits them, pass
        # its id here, and every check downstream runs against a fiction.
        result, _txn = arc4.abi_call[arc4.UInt64]("price()uint64", app_id=oracle)
        return result.as_uint64()
```

An application id is a `uint64`. Anybody can deploy a contract that answers to `price()uint64` and returns whatever number suits them, for the price of one transaction fee, and a method that takes the id as an argument has invited them to. **An application id supplied by the caller is not an integration, it is an instruction.** Store the ids you trust, under a guard, and read them.

::: {.gotcha #app-id-from-an-argument topic="Cross-contract calls" title="A caller-supplied application id lets the caller choose what your contract believes"}
An `Application` parameter is a `uint64` on the wire, and nothing in the ABI, the router or the AVM checks that the id names the contract you had in mind. A method that takes the id of an oracle, a pool, a registry or a child and then trusts what it returns is a method whose answers are chosen by whoever calls it: deploying a contract that answers to the same signature and returns a convenient number costs one fee and no privilege. The defect survives testing because every test passes the right id. Store the id in state, written once behind a creator or admin guard, and read it --- or, where the id must vary, check its provenance before trusting the reply, which is what Chapter 16's registry exists to make possible. The same reasoning covers asset ids, as Chapter 7 showed.
:::

**Example 15-5.** Staging a call and a payment together

<!-- finder: satisfy a callee that requires a grouped payment -->

```python
from algopy import (ARC4Contract, Application, Global, GlobalState, Txn, UInt64,
                    arc4, gtxn, itxn)


class Vault(ARC4Contract):
    """A callee with the shape every deposit method in this book has."""

    def __init__(self) -> None:
        self.credited = GlobalState(UInt64(0))

    @arc4.abimethod
    def deposit(self, payment: gtxn.PaymentTransaction) -> None:
        assert payment.receiver == Global.current_application_address, "not ours"
        self.credited.value += payment.amount


class Depositor(ARC4Contract):
    @arc4.abimethod
    def deposit_into(self, vault: Application, amount: UInt64) -> None:
        assert Txn.fee >= UInt64(3_000), "cover the two inner fees"
        # The vault insists on a payment beside the call. Passing the unsent
        # payment as the transaction argument makes abi_call compose the two
        # into one inner group, exactly the shape a client would build.
        pay = itxn.Payment(
            receiver=vault.address, amount=amount, fee=UInt64(0)
        )
        arc4.abi_call("deposit(pay)void", pay, app_id=vault, fee=UInt64(0))
```

Every deposit method in this book demands a payment beside the call, which raises a question the moment a contract is the caller: a contract cannot hand a client-built group to somebody. It builds one. `itxn.Payment(...)` without `.submit()` produces an unsent transaction, and passing it as the call's transaction argument makes `abi_call` compose the two into a single inner group, which is exactly the shape the vault is expecting and the reason `itxn.abi_call` returns a call you still have to submit.

The vault asks one of Example 7-8's four questions and skips the other three on purpose: `credited` is a statistic nobody spends, so a wrong payer or a short amount corrupts a number rather than a claim. Every deposit that credits something spendable asks all four --- Chapter 14's `add_initial_liquidity` is the same shape with the other three restored, because what it hands back is an LP token.

**Example 15-6.** Two payments, one group

<!-- finder: send several inner transactions atomically -->

```python
from algopy import Account, ARC4Contract, Txn, UInt64, arc4, itxn


class Treasurer(ARC4Contract):
    @arc4.abimethod
    def pay_both(self, first: Account, second: Account, each: UInt64) -> None:
        assert Txn.fee >= UInt64(3_000), "cover the two inner fees"
        # Building without sending is the manual form of what abi_call did
        # with its transaction argument: the pair goes out as one group,
        # so either both payments land or neither does.
        a = itxn.Payment(receiver=first, amount=each, fee=UInt64(0))
        b = itxn.Payment(receiver=second, amount=each, fee=UInt64(0))
        itxn.submit_txns(a, b)
```

`itxn.submit_txns` is the manual form of the same thing, for when the group is not a call and its payment. Both payments land or neither does, which matters whenever the second one failing would leave the first one wrong.

The fee assertion in both examples is Chapter 7's rule arriving with an extra transaction to count. Every inner transaction carries `fee=UInt64(0)`, so the caller covers the pool: one outer call plus two inner transactions is 3,000 microAlgo.

**Example 15-7.** How deep a chain may go

<!-- finder: find the limit on nested application calls -->

```python
from algopy import Application, ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class Relay(ARC4Contract):
    """One link in a chain of deployed copies."""

    def __init__(self) -> None:
        self.next_id = GlobalState(UInt64(0))

    @arc4.abimethod
    def set_next(self, next_relay: Application) -> None:
        assert Txn.sender == Global.creator_address, "creator wires the chain"
        self.next_id.value = next_relay.id

    @arc4.abimethod
    def go(self, hops: UInt64) -> UInt64:
        if hops == UInt64(0) or self.next_id.value == UInt64(0):
            return UInt64(0)
        # Each hop is one level deeper in the call tree. The AVM allows
        # eight nested application calls beneath the top-level one; the
        # ninth is refused with `appl depth (8) exceeded`.
        result, _txn = arc4.abi_call[arc4.UInt64](
            "go(uint64)uint64", hops - UInt64(1), app_id=self.next_id.value
        )
        return result.as_uint64() + UInt64(1)
```

A contract that calls a contract that calls a contract is a call tree, and the AVM bounds its depth at *eight* nested application calls beneath the top-level one (`maxAppCallDepth` in go-algorand's `data/transactions/logic/eval.go`). The ninth is refused with `appl depth (8) exceeded`. That is a separate limit from the sixteen transactions one `itxn_submit` may carry, and from the 256 inner transactions a group may hold across all its calls. Both of those bound *count* rather than nesting: a contract may submit sixteen payments at one level, or chain eight calls, and neither number constrains the other.

`set_next` is creator-only and writes `Relay`'s next hop to state; `go` reads it. A relay that took the hop as an argument would hand the same choice to a caller, one hop further along.

::: {.gotcha #clearstate-cannot-send-inners topic="Inner transactions" title="A ClearState program cannot send an inner transaction"}
Budget is not the reason: each inner application call *adds* 700 units to the pooled opcode budget when it is submitted, a gift rather than a cost. The restriction is the ClearState program itself, which the protocol runs with inner transactions forbidden outright --- so a clear-state exit can never refund a deposit, sweep a balance, or return anything to the account on its way out. Anything a leaving user should get back has to move in an ordinary method before the clear; Chapter 4's trapdoor rule about liabilities in local state is this restriction seen from the storage side.
:::

## Reading State Without Calling
Calling is not the only way to learn something from another contract, and it is usually not the cheapest. State is public.

*Predict: reading another contract's state runs none of its code. Say what that buys you, and name one thing a call can tell you that a read cannot.*

**Example 15-8.** Reading another contract's global state

<!-- finder: read a value out of another application without calling it -->

```python
from algopy import Application, ARC4Contract, Bytes, UInt64, arc4, op


class Watcher(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def reserve_of(self, pool: Application) -> UInt64:
        # A read, not a call: no method on the other contract runs, so this
        # works against contracts that never planned to be read. The flag
        # says whether the key exists -- absent is not zero.
        value, exists = op.AppGlobal.get_ex_uint64(pool, Bytes(b"reserve"))
        assert exists, "no such key on that app"
        return value
```

`op.AppGlobal.get_ex_uint64` reads a key out of an application's global slab. No method on that contract runs: there is no call, no selector, no opcode budget spent on the other side, and no cooperation required. It works against contracts that never anticipated being read, which is what makes composition possible between teams that have never spoken.

It returns a pair, and the second half is the one to respect: the flag says whether the key exists. Chapter 4's rule holds across the boundary exactly as it did inside it: absent is not zero, and a contract that treats a missing key as a zero balance has invented a fact.

**Example 15-9.** Reading local state

<!-- finder: read one account's local state for another application -->

```python
from algopy import Account, Application, ARC4Contract, Bytes, UInt64, arc4, op


class Watcher(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def stake_of(self, who: Account, farm: Application) -> UInt64:
        # Local state needs both halves of the address: whose slab, and which
        # application's columns in it.
        value, exists = op.AppLocal.get_ex_uint64(who, farm, Bytes(b"staked"))
        assert exists, "opted in, but never staked"
        return value
```

Local state needs both halves of its address: whose slab, and which application's columns in it. Both must be available to the transaction, which is Chapter 11's reference list arriving in a new place.

Absence has two shapes here rather than one. A key that was never written comes back with the flag clear, as it does for global state; an account that never opted in is a ledger error raised inside the opcode, which no flag can catch and Chapter 4 shows in full.

**Example 15-10.** Reading an application's parameters

<!-- finder: find out who created an application -->

```python
from algopy import Account, Application, ARC4Contract, arc4, op


class Inspector(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def creator_of(self, app: Application) -> Account:
        # The ledger's own record of who created an application -- the fact
        # provenance checks are built on, unforgeable by the app itself.
        creator, exists = op.AppParamsGet.app_creator(app)
        assert exists, "no such application"
        return creator
```

`op.AppParamsGet` reads the ledger's own record of an application rather than anything the application stores: its creator, its address, its schema, its program pages. The creator is the useful one, because it is the one fact about an application that the application cannot lie about. A contract that will only deal with pools its own factory deployed checks exactly this, and Chapter 16 builds the registry around it.

**Example 15-11.** What a group-mate has already done

<!-- finder: read state a transaction earlier in the same group just wrote -->

```python
from algopy import Application, ARC4Contract, Bytes, GlobalState, UInt64, arc4, op


class Writer(ARC4Contract):
    def __init__(self) -> None:
        self.counter = GlobalState(UInt64(0))

    @arc4.abimethod
    def bump(self, to: UInt64) -> UInt64:
        self.counter.value = to
        return self.counter.value


class Reader(ARC4Contract):
    @arc4.abimethod
    def peek(self, writer: Application) -> UInt64:
        # In a group where an earlier transaction wrote this key, the read
        # returns what that transaction wrote. There is no snapshot taken
        # when the group starts; each transaction sees the ledger as the
        # ones before it left it.
        value, exists = op.AppGlobal.get_ex_uint64(writer, Bytes(b"counter"))
        assert exists, "writer has never written"
        return value
```

Put `bump` and `peek` in one group, in that order, and `peek` returns what `bump` wrote, not the value from before the group. There is no snapshot taken when a group begins. Each transaction evaluates against the ledger as the transactions before it left it, which is the rule Chapter 2 stated about a single transaction's effects, applied to the group it sits in.

The same rule covers a case that looks separate and is not. `op.gaid(n)` returns the id of the asset or application *created* by transaction `n` of this group, so a contract can act on something that did not exist when the group was assembled. Writes and creations follow the same rule: everything a group-mate did is visible to what follows it.

::: {.gotcha #group-state-is-visible-within-the-group topic="Atomic groups" title="Transactions in a group see each other's state changes as they execute"}
Atomicity is about the *commit*, not about isolation. The transactions in a group execute in order against a single shared, copy-on-write view of the ledger, so the second app call in a group reads the state the first one wrote; the group's changes land in the ledger together only if every transaction succeeds. This is what makes fund-then-call work at all. It is also why "nobody can observe an intermediate state" is the wrong mental model: a contract you call in the same group absolutely can, and a design that assumes otherwise is assuming a guarantee the protocol never made.
:::

## Deploying a Child from Inside a Parent
A contract can deploy a contract. What it gets back is an id, an address, and an account with nothing in it.

*Predict: your contract creates a child application. Say which account is charged for the child's minimum balance, and what the child's own account holds the instant after it exists.*

**Example 15-12.** Compiling and deploying a child

<!-- finder: deploy one contract from inside another -->

```python
from algopy import ARC4Contract, GlobalState, UInt64, arc4, compile_contract, itxn


class Child(ARC4Contract):
    def __init__(self) -> None:
        self.parent = GlobalState(UInt64(0))


class Parent(ARC4Contract):
    def __init__(self) -> None:
        self.child_id = GlobalState(UInt64(0))

    @arc4.abimethod
    def spawn(self) -> UInt64:
        assert self.child_id.value == UInt64(0), "already spawned"
        # The child's program, schema and pages, produced at compile time.
        compiled = compile_contract(Child)
        created = itxn.ApplicationCall(
            approval_program=compiled.approval_program,
            clear_state_program=compiled.clear_state_program,
            global_num_uint=compiled.global_uints,
            global_num_bytes=compiled.global_bytes,
            local_num_uint=compiled.local_uints,
            local_num_bytes=compiled.local_bytes,
            fee=UInt64(0),
        ).submit()
        self.child_id.value = created.created_app.id
        return created.created_app.id
```

`compile_contract(Child)` produces the child's approval program, clear-state program, schema and page count at compile time, so the parent's bytecode contains the child's. The `itxn.ApplicationCall` that follows is an ordinary inner transaction with no `app_id`, which is what makes it a creation, and `created_app` on the result is how the parent learns what it made.

The schema is passed explicitly from `compiled.global_uints` and its siblings rather than typed out, because Chapter 4's rule that schema is fixed at creation and can never be widened applies to a child exactly as it does to anything else. A transcribed number that drifts from the child's actual declarations produces a contract that cannot write its own state.

Compile the pair now, before going further. Both classes have to reach the compiler in one run, because `compile_contract` needs the child's bytecode at the moment the parent is being built:

```bash
algokit compile py payroll.py
```

Two approval programs come out, one per class, and the parent's is the larger of the two: somewhere inside `Payroll.approval.teal` is a single `pushbytes` carrying the whole of `Worker.approval.teal`. That is what "the parent's bytecode contains the child's" looks like when you go and find it.

**Example 15-13.** Funding what you just made

<!-- finder: give a newly created application an account it can use -->

```python
from algopy import Application, ARC4Contract, UInt64, arc4, itxn


class Parent(ARC4Contract):
    @arc4.abimethod
    def fund(self, child: Application, amount: UInt64) -> None:
        # A new application's account exists with a zero balance, and its
        # first box, opt-in or inner transaction needs money the creation
        # did not give it. The parent funds it the way anybody funds an
        # account: a payment to its address.
        assert amount >= UInt64(100_000), "below the account's own floor"
        itxn.Payment(
            receiver=child.address, amount=amount, fee=UInt64(0)
        ).submit()
```

A new application's account holds nothing. It cannot write a box, opt into an asset, or send an inner transaction until somebody pays it, because all three raise a minimum balance the account has no money to meet. The parent funds it the way anybody funds an account.

The number is a decision rather than a default. 100,000 is the floor for the account to exist at all; anything the child will hold sits on top of that, and the guard in Example 15-13 refuses an amount below the floor rather than sending money that leaves the child still unable to act.

::: {.gotcha #child-account-starts-empty topic="Cross-contract calls" title="A newly created application has an address and no money"}
Creating an application allocates its account but funds nothing, so the child comes into existence unable to write a box, opt into an asset, or send an inner transaction: every one of those raises a minimum balance it cannot meet. The failure arrives from the ledger rather than from any assertion, names an account rather than an application, and appears on whatever method first tries to store something rather than on the creation that caused it. A parent that deploys a child should fund it in the same method, for the account's 100,000 floor plus whatever the child's first write will cost, and refuse an amount that leaves it still unable to act.
:::

The child's account is not the only bill, and the other one lands on the parent. Creating an application charges its **creator** 100,000 plus the child's declared schema, and the creator here is the parent's own account. The numbers below are the payroll worker, which declares two global uints; Example 15-12's `Child` declares one, so its bill is 128,500:

```console
>>> def floor(addr):   # what this account must keep
...     info = algorand.account.get_information(addr)
...     return info.min_balance.micro_algo
...
>>> floor(payroll.app_address)   # before spawn
100000
>>> floor(payroll.app_address)   # after spawn
257000
>>> after - before               # the child's bill, on the parent
157000
```

For a worker with two global uints that is 157,000 (100,000 for the application and 28,500 for each uint) on top of the 200,000 the parent sends. A parent holding only what it plans to send therefore fails on `spawn` itself. The child is created first, which moves the parent's floor to 257,000; the 200,000 payment then settles the parent under it, and the message names the *parent's* balance and minimum with nothing in it about a child. That is Chapter 11's rule that schema is billed to the creator, arriving where the creator is a contract.

## Funding the Worker and Keeping Its Id
Two habits, two corrections. Both are written in `spawn`, the second reaches `assign` and `settle` as well, and Example 15-14 is the corrected pair in full.

**Example 15-14.** Payroll and its worker, corrected

<!-- finder: keep a spawned child's id instead of taking it from the caller -->

```python
from algopy import (ARC4Contract, BoxMap, Global, GlobalState,
                    Txn, UInt64, arc4, compile_contract, itxn)

WORKER_FUNDING = 200_000


class Worker(ARC4Contract):
    """The child: keeps a ledger of assigned work, reports what is owed."""

    def __init__(self) -> None:
        self.parent = GlobalState(UInt64(0))
        self.owed = GlobalState(UInt64(0))
        self.jobs = BoxMap(UInt64, UInt64, key_prefix=b"j_")

    @arc4.baremethod(create="require")
    def create(self) -> None:
        # Zero means a person created this directly, and a parent of zero
        # would make `record`'s guard compare zero against zero and pass.
        assert Global.caller_application_id != UInt64(0), "a parent spawns me"
        self.parent.value = Global.caller_application_id

    @arc4.abimethod
    def record(self, job: UInt64, amount: UInt64) -> None:
        assert Global.caller_application_id == self.parent.value, "parent only"
        self.jobs[job] = amount
        self.owed.value += amount

    @arc4.abimethod(readonly=True)
    def amount_due(self) -> UInt64:
        return self.owed.value


class Payroll(ARC4Contract):
    """The parent, holding on to what it made."""

    def __init__(self) -> None:
        self.worker_id = GlobalState(UInt64(0))

    @arc4.abimethod
    def spawn(self) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.worker_id.value == UInt64(0), "already spawned"
        compiled = compile_contract(Worker)
        created = itxn.ApplicationCall(
            approval_program=compiled.approval_program,
            clear_state_program=compiled.clear_state_program,
            global_num_uint=compiled.global_uints,
            global_num_bytes=compiled.global_bytes,
            fee=UInt64(0),
        ).submit()
        # Both habits, corrected in two lines: the id is kept, and the new
        # account gets the money its first box will need.
        self.worker_id.value = created.created_app.id
        itxn.Payment(
            receiver=created.created_app.address,
            amount=UInt64(WORKER_FUNDING),
            fee=UInt64(0),
        ).submit()
        return created.created_app.id

    @arc4.abimethod
    def assign(self, job: UInt64, amount: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        arc4.abi_call(
            Worker.record, job, amount,
            app_id=self.worker_id.value, fee=UInt64(0),
        )

    @arc4.abimethod
    def settle(self) -> UInt64:
        # Two guards, not one. The deleted parameter stops the method being
        # aimed; this stops it being called at all by somebody who should not.
        assert Txn.sender == Global.creator_address, "creator only"
        due, _txn = arc4.abi_call(
            Worker.amount_due, app_id=self.worker_id.value, fee=UInt64(0)
        )
        itxn.Payment(receiver=Txn.sender, amount=due, fee=UInt64(0)).submit()
        return due
```

Set against Example 15-1, the creator guards on `spawn` and `assign`, which were already right, are untouched. Four things changed:

- The parent's `spawned` flag becomes `worker_id` --- the same slot doing a better job. A stored id is non-zero, so it still refuses a second `spawn`, and it now remembers which id.
- `spawn` pays the account it just created, from the new `WORKER_FUNDING` constant.
- `assign` and `settle` lose their `worker` parameter, and `settle` gains the creator guard the other two always had.
- `Worker.create` gains one assertion, which the gotcha that follows explains.

::: {.gotcha #stored-caller-id-of-zero topic="Cross-contract calls" title="A caller application id of zero, once stored, makes the guard that reads it vacuous"}
`Global.caller_application_id` is zero when a person called your contract directly, which Chapter 10 uses to tell a contract caller from a human one. Storing that value at creation is a different act with a different consequence: a child deployed by a person rather than by its parent keeps zero as its `parent`, and every later `assert Global.caller_application_id == self.parent.value` then compares zero against zero and passes. The guard is not permissive, it is *vacuous*: it admits exactly the caller it was written to exclude, and it reads correctly on the page. The corrected worker asserts the id is non-zero in `create`, which is the same check Chapter 16 carries. Any contract that stores an identity at creation and checks it later has this shape.
:::

**Correction one: fund the child.** Two hundred thousand microAlgo, chosen rather than rounded: 100,000 for the account and 9,700 for the first job's box, by Chapter 11's formula over a two-byte prefix, an eight-byte key and an eight-byte value. The rest is headroom for jobs after the first.

**Correction two: keep what you made.** `settle` loses its parameter, and with it the ability to be aimed. `assign` loses the same parameter for the same reason, and after both the only worker the parent can consult is the one it created.

A deletion closes one way in and leaves the others open, which is why `settle` gains a creator check at the same time. The parameter let a caller aim the method; the missing check let them call it at all, and since `settle` pays `Txn.sender`, a stranger who called it was paid. Removing the parameter does nothing about that.

Hold Example 15-14 against the commission. Requirements 1 and 2 were met by Example 15-1 and survive untouched; correction one settles requirement 5, correction two settles requirement 4, and the creator check `settle` gained settles requirement 3.

Where an id must be stored, store it; where it must vary, check its provenance with Example 15-10 before believing the reply. What you may not do is take it from the caller and trust what answers.

## Retrieval
Answer from memory before looking anything up.

1. What does the AVM check about an application id before dispatching a call to it?
2. Name the two spellings of a cross-contract call, and say what the typed one buys.
3. Where may an application id come from, and what is wrong with the answer "a method argument"?
4. Reading another contract's global state runs none of its code. What does that make possible?
5. *(From Chapter 4)* `get_ex_uint64` returns a pair. What does the second half mean, and what goes wrong if you ignore it?
6. A group holds a call to A at index 0 and a call to B at index 1, and B reads a key A just wrote. What does B see?
7. How deep may a chain of application calls go, and what does the one past the limit report?
8. *(From Chapter 11)* A parent deploys a child and the child's first method writes a box. Compute what the parent must send it.

## Exercises

1. **(Trace)** Walk the broken payroll through this sequence and say what happens at each step: the studio calls `spawn`; the studio calls `assign(worker, 1, 5_000)`; somebody funds the worker's account with 1 Algo; the studio calls `assign` again; a stranger deploys Example 15-2 and calls `settle` with its id. For each, say whether the transaction succeeds, what changes on chain, and which account is left holding what. Then say which single deleted parameter would have stopped the last step, and whether anything else in the contract would have had to change with it.

2. **(Parsons)** These four lines are the body of a corrected `spawn`, scrambled. Put them in a working order, say what forces each line that is forced, and name the one pair whose relative order does not matter and why.

   ```text
   self.worker_id.value = created.created_app.id
   created = itxn.ApplicationCall(...).submit()
   itxn.Payment(receiver=created.created_app.address, ...).submit()
   assert self.worker_id.value == UInt64(0), "already spawned"
   ```

3. **(Debug)** Two contracts trust a number that came back from another application, and both are wrong about what the number means.

   **The reserve that reads zero.** A contract reads a pool's reserve with `op.AppGlobal.get_ex_uint64` and prices a swap against it. It works for months, then starts pricing against zero and paying out accordingly. The pool is fine and its reserve is not zero.

   a. Give two distinct explanations for the zero.
   b. Say which of the two the returned flag would have caught, and what catching the other requires instead.

   **The payroll that settles twice.** The fixed payroll assigns two jobs worth 5,000 and 7,000, and `settle` pays 12,000. The studio calls `settle` again with no new work assigned, and is paid 12,000 a second time. Nothing is unguarded and no id is wrong.

   c. Name the missing state, and say whether it belongs in the worker's ledger or in the parent's record of what it has already paid.
   d. Say why `amount_due` as written cannot be the method that clears it.

   e. Then both together: state in one sentence what the two defects have in common, without naming a pool or a payroll.

4. **(Compare)** You need your contract to call an oracle. Compare three ways of deciding which oracle: the id as a method argument; the id stored at creation and immutable; the id stored in state and changeable by an admin. Compare on what an attacker must control, what happens when the oracle is deprecated, what a reader of your contract can verify before using it, and what happens if the admin key is lost. Name the requirement that would force each.

5. **(Extend)** Extend the fixed payroll so one parent can run several engagements at once: several workers, each with its own ledger, all spawned and settled by the same parent. You will hit the question this chapter answered by deleting a parameter --- with several workers, `settle` needs to name one. Say what it may take as an argument instead of an id, where the mapping lives, and what the parent must check before it trusts a reply. Write the state declaration and the guard; leave the rest as comments.

## Before You Continue
- [ ] I can call another contract with the compiler deriving the selector, and by signature string when there is no source to import
- [ ] I can say where an application id may come from, and recognise on sight the method signature that hands the choice to a caller
- [ ] I can read another contract's global state, local state and creator without calling it, and say what the existence flag is for
- [ ] I can say what a group-mate's writes and creations are visible to, and why that is one rule rather than two
- [ ] I can deploy a child contract, compute what it must be funded with before its first write, and say what creating it costs the parent's own account

## Handoff: What the Factory Project Needs
Chapter 16 moves pool creation on chain: a factory deploys pools, records which ones it made, and teaches downstream contracts to reject a pool it did not create. Every one of those three is this chapter with money attached. Table 15-1 is what it draws on.

: Table 15-1. What Chapter 16 draws on from this chapter

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------------|--------------------------------------|
| Example 15-12 | The factory's `create_pool`, which compiles and deploys a pool | The factory deploys many pools rather than one. What must it store per pool that this example stores in a single global? |
| Example 15-13 | The bootstrap payment every new pool receives | A pool opts into two assets and creates its LP token. Work out what it must hold before it can do any of that. |
| Example 15-10 | The `candidate_pool.creator` half of `verify_pool` | The factory is asked about a pool id it may not have created. Which single fact about that pool cannot be forged, and what does checking it still fail to prove? |
| Example 15-4 | The factory calling a new pool's `bootstrap`, with the signature spelled out inside a raw `itxn.ApplicationCall` | The factory has the pool's source, so it could use the typed form. Say why a project might spell the selector by hand anyway. |
| Example 15-11 | `create_pool` funding and calling a pool in the same execution that created it | The pool did not exist when the group was assembled. Say what makes it reachable by the transaction after the one that made it. |
