<!-- Companion material (out of spine, issue #44). Not in the main TOC.
     Reader-facing pointer: chapters/20-further-reading-logicsigs.md
     Runnable project for Ch 21: advanced/limit-order-book/
     Figures: figures/ at the repository root. Paths that still say
     projects/limit-order-book/ mean advanced/limit-order-book/. -->

\newpage

\part{Stateless Programs}

Part V leaves stateful contracts for the AVM's other kind of program: signatures with logic in them. Chapter 20 teaches the two binding modes and the guards no LogicSig can ship without; Chapter 21 uses them to build a limit order book whose orders rest off-chain as signed programs until a keeper executes them.

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# Signing Without a Key

Every contract in this book so far has been asked a question: somebody called a method, and the contract decided whether to allow it. A Logic Signature answers a different question, and it answers it *instead of a private key*.

A transaction needs a signature. Normally that signature is produced by a key, and the network checks it against the sender's address. A LogicSig replaces the key with a program: the network runs the program against the transaction, and if it returns true, the transaction is signed. Nothing was decrypted, nobody was consulted, and no state was read.

## Authority You Can Hand Over, and Cannot Take Back
Some of what an account needs to do cannot wait for its owner. A payment bot settles at midnight, a keeper fills a trader's order the moment the price crosses, a vault releases on a schedule. Each of those spends from an account, and none of them should be holding that account's key.

**The allowance that could not be cancelled.**

A team runs a payments service. Customers deposit into a service account, and a bot pays out on their behalf, so it needs to spend from customer accounts without holding customer keys. LogicSigs are exactly the mechanism: each customer signs a small program once, the bot holds the signed program, and the program allows payments up to an agreed limit.

It works. Six weeks in, a customer asks to cancel. The support engineer looks for the revoke endpoint and there is not one. They look for a database row to delete and find that deleting it changes nothing: the signed program is a file the bot already has, and copies may be anywhere.

The program has no expiry, because at the time nobody could think of a reason it should stop. It is still valid. It will be valid in ten years.

Revocation was never on offer. A signature cannot be withdrawn once it exists, so every bound a delegated LogicSig will ever have has to be written into it before it is signed. An expiry is one of those bounds. It is one line long, and it is the line the payments team did not write.

One program, two bindings, and the difference between them is whose money is at risk: Figure 20-1 puts them side by side.

![Figure 20-1. The two ways a logic signature is used. A contract account's address is the hash of its program; a delegated signature carries an account's authority instead.](figures/logicsig-modes.svg)

::: {.spec title="Your commission: the allowance, written so it can be signed"}
The payments team's allowance is above, and their mistake is not yours to inherit. Write the delegation they should have signed. It must:

1. Pay one named payee, up to 100,000 microAlgo per payment, and permit nothing a transaction can do on the side.
2. Expire on a stated round, with no action from anyone.
3. Never cost the customer more than a bounded fee when it fires.
4. Bound how *often* it can fire, not only how much.
5. Trust nothing that arrives with the transaction it signs.
:::

By the end of this chapter you will be able to:

- Say what a LogicSig is and what it replaces, and why it has no state to read
- Tell a contract account from a delegated LogicSig, and say who is spending in each
- Write the guards a LogicSig cannot ship without, and say why a stateful contract must *not* copy them
- Bind a LogicSig to a single method of a single application, and say what that binding still does not fix
- Compile a LogicSig from a contract, and say why its parameters are fixed before anything runs
- Bound a LogicSig in time and in count, and say which mechanism does which
- Say what the LogicSig opcode budget is, and where more of it comes from

## The Smallest LogicSig
**Example 20-1.** A program that approves almost nothing

<!-- finder: see the smallest complete LogicSig -->

```python
from algopy import Txn, logicsig


@logicsig
def always_reject() -> bool:
    """The smallest complete LogicSig, and it is a refusal.

    A LogicSig is a program that signs. It receives one transaction, returns
    true or false, and true means the transaction is authorised. There is no
    state, no method, and no caller -- only the transaction in front of it.

    One condition, and it can never hold: the protocol rejects a transaction
    whose `last_valid` precedes its `first_valid` before any program runs, so
    there is no transaction this approves. A program that merely looked
    harmless would not do -- a payment of zero, at zero fee, still empties
    the account it guards through `close_remainder_to`.
    """
    return Txn.first_valid > Txn.last_valid
```

One condition, nothing imported but the transaction and the decorator. There is no state to read, no method to dispatch, no caller to check. A LogicSig receives one transaction and returns a boolean, and that is the entire interface. Everything else in this chapter is that shape with more conditions in it.

The condition chosen is one no transaction can satisfy. Programs that look equally harmless and are not are the ordinary case, and there is a set of them at the end.

## Writing the Allowance
**Example 20-2.** The allowance, as the payments team wrote it

<!-- finder: see a LogicSig that authorises more than its author meant -->

```python
from algopy import (Account, TemplateVar, TransactionType, Txn, UInt64,
                    logicsig)


@logicsig
def pays_payee_unsafe() -> bool:
    """Authorises a payment to the customer's payee. It is a blank cheque.

    Three checks, all of them about the payment the author had in mind, and
    every one of them true of the transaction they meant to allow. Nothing
    here looks at what else the transaction does, and a transaction can do
    several things at once.
    """
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.receiver == TemplateVar[Account]("PAYEE")
        and Txn.amount <= UInt64(100_000)
    )
```

Three conditions, all about the payment, and all true of the transaction the team had in mind.

*Predict: this program authorises a class of transactions, not one. Name three things a transaction could do that these three checks permit and the author would not have. Write them down before reading on.*

The list is longer than most people's first guess, and it is not about the amount. A transaction carries fields this program never looks at, and each unexamined field is a permission.

`close_remainder_to` empties the sender's entire remaining balance into an account of the submitter's choosing, as a *side effect* of a payment. The amount can be 1 microAlgo and the account can still be drained. `rekey_to` hands the account's signing authority to a new key permanently, after which the LogicSig is irrelevant because the attacker simply signs. And `fee` is paid from the sender's balance, so a transaction with a fee of one Algo spends one Algo whatever the amount says.

There is no expiry either, which is the defect the support engineer found. But the first three are worse, because they are live now.

## The Guards a LogicSig Cannot Ship Without
Four checks and one import complete it, and nothing that was already there changes:

```diff
-from algopy import (Account, TemplateVar, TransactionType, Txn, UInt64,
+from algopy import (Account, Global, TemplateVar, TransactionType, Txn, UInt64,
                     logicsig)
...
     return (
         Txn.type_enum == TransactionType.Payment
+        and Txn.close_remainder_to == Global.zero_address
+        and Txn.rekey_to == Global.zero_address
+        and Txn.fee <= Global.min_txn_fee * UInt64(10)
         and Txn.receiver == TemplateVar[Account]("PAYEE")
         and Txn.amount <= UInt64(100_000)
+        and Txn.last_valid <= TemplateVar[UInt64]("EXPIRY")
     )
```

**Example 20-3.** The same program with its guards

<!-- finder: the checks a LogicSig cannot ship without -->

```python
from algopy import (Account, Global, TemplateVar, TransactionType, Txn, UInt64,
                    logicsig)


@logicsig
def pays_payee() -> bool:
    """The same intent with the checks a LogicSig cannot do without.

    Seven conditions. Three are the payment the author meant to allow --
    the same three the unsafe version had -- and four close doors the
    transaction format leaves open by default.
    """
    return (
        # 1. It is a payment. Without this the fields below read as whatever
        #    the equivalent offsets mean in an asset transfer or a key reg.
        Txn.type_enum == TransactionType.Payment
        # 2. It does not empty the account into somebody else's.
        and Txn.close_remainder_to == Global.zero_address
        # 3. It does not hand the account's signing authority away.
        and Txn.rekey_to == Global.zero_address
        # 4. It does not drain the account through the fee.
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        # 5-7. What this LogicSig is actually for.
        and Txn.receiver == TemplateVar[Account]("PAYEE")
        and Txn.amount <= UInt64(100_000)
        and Txn.last_valid <= TemplateVar[UInt64]("EXPIRY")
    )
```

The three payment checks are unchanged. Four are added, and they exist because a transaction is a struct with fields the author did not fill in, and unfilled is not the same as harmless.

The unsafe version already had `Txn.type_enum == TransactionType.Payment`, and the reason usually given for it is wrong. It is *not* that an asset transfer has a receiver your check would match --- `Receiver` and `AssetReceiver` are separate fields, and the protocol rejects a transaction carrying non-zero fields for the wrong type, so `Txn.receiver` on an asset transfer is provably the zero address. The hazard runs the other way. Every payment field a program inspects reads as **zero** on an asset transfer, so a program without `type_enum` does not fail those checks, it passes them *vacuously* --- and a program whose only condition was `Txn.receiver == Global.zero_address` will happily approve an ASA opt-in and then an ASA transfer out.

Pinning `type_enum` to `Payment` is also what makes `asset_close_to` unnecessary here: a payment cannot carry one. A LogicSig that permits asset transfers needs it explicitly.

Two more belong on a production program and are not in this one. `Txn.rekey_to` is pinned above, but nothing here binds the program to a *network*. `Global.genesis_hash` does that, and without it a signature collected on TestNet is a valid signature on MainNet for an account with the same address. And nothing binds it to a group. Those, with `asset_close_to` and Example 20-10's rule that arguments prove nothing, are why Chapter 21's checklist runs to eight items where this section has four.

The fee bound is `Global.min_txn_fee * UInt64(10)` rather than a literal. `MinTxnFee` is 1,000, so a literal 1,000 permits *exactly* the floor: the transaction can never be a fee-pooling payer, and it stops being submittable once congestion prices transactions at fee-per-byte times encoded length rather than at the flat minimum.

Four guards do not make it finished. Nothing here bounds how *many* times the payment may be made, so the holder can drain the delegator's account 100,000 at a time until `EXPIRY`. Example 20-9 takes that up later. A program can pass every field check and still be a standing withdrawal.

::: {.gotcha #logicsig-checks-are-logicsig-only topic="LogicSigs" title="These checks belong in a LogicSig and nowhere else"}
`close_remainder_to` and `rekey_to` are the fields a LogicSig must pin on every payment it approves, and `asset_close_to` is the third wherever it permits an asset transfer at all. A LogicSig *is* the sender's authority, so an unchecked field is authority it granted: any of the three can hand the account, its balance, or its holdings away inside a transaction the program said yes to. Chapter 10's twin gotcha rules on the other side of the line --- why a stateful contract must *not* copy these checks onto the transactions in its group.
:::

## Two Ways to Be Bound
A LogicSig program is just a program. What makes it dangerous, or safe, is which account it speaks for, and there are exactly two answers.

**Example 20-4.** A contract account

<!-- finder: a LogicSig that is its own account, with no key anywhere -->

```python
from algopy import (Account, Global, TemplateVar, TransactionType, Txn, UInt64,
                    logicsig)


@logicsig
def vault() -> bool:
    """A contract account: the LogicSig IS the account, and nobody signs for it.

    The address is the hash of this program. Anyone may submit a transaction
    from it, and the program alone decides whether that transaction is
    allowed -- there is no private key anywhere and no delegator to blame.
    """
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        and Txn.receiver == TemplateVar[Account]("BENEFICIARY")
        and Txn.first_valid >= TemplateVar[UInt64]("UNLOCK_ROUND")
    )
```

The address of a contract account *is* the hash of the program. Nobody holds a key for it, nobody can sign for it, and the only transactions it can ever send are the ones this program approves. Money sent there is governed by the code and by nothing else, which is why an escrow, a vesting lock or a fee sink is usually this shape. Note what pinning `close_remainder_to` costs here: the account can never be closed, so its 100,000 minimum balance is stranded for good. That is the right trade for a vault and it is a trade.

**Example 20-5.** A delegated LogicSig

<!-- finder: an account's own key signs a program once, and cannot unsign it -->

```python
from algopy import (Account, Global, TemplateVar, TransactionType, Txn,
                    UInt64, logicsig)


@logicsig
def allowance() -> bool:
    """A delegated LogicSig: an account's own key signs the program once.

    Everything this authorises is spent from the DELEGATOR's account, by
    whoever holds the signed program. The delegator cannot take it back
    without rekeying, so every condition here is a promise they cannot
    withdraw -- which is why the bound and the expiry are not optional.
    """
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        and Txn.receiver == TemplateVar[Account]("PAYEE")
        and Txn.amount <= UInt64(50_000)
        # A template, not a literal: an absolute round number goes
        # stale, and a signature that expired before it was written
        # teaches the wrong lesson about expiries.
        and Txn.last_valid <= TemplateVar[UInt64]("EXPIRY")
    )
```

Delegation is the other shape and the sharper one. An existing account signs the compiled program with its own key. Afterwards, anybody holding that signed blob can submit transactions **from the delegator's account**, spending the delegator's money, and the delegator is not consulted again.

The payments team's allowance lives here, and the three facts that matter are all about what happens on a chain rather than what the program says. Run against LocalNet, the delegated program above behaves like this: a payment inside its bound succeeds, and the money leaves the *delegator's* account rather than the submitter's; a payment over the bound is refused by the network, whose error carries `transaction {id}: rejected by logic` inside a much longer envelope that renders the whole signed transaction; and a second payment succeeds afterwards, because nothing revoked anything. None of the three is printed here, because each carries an address or a transaction id that changes every run, and each is asserted every time the example gate runs.

That third one is the answer to the support ticket. The delegator's key was used once, at signing time, and is never consulted again, so there is no later moment at which refusal is possible. The only exit is to change what the account's authority *is*, which means rekeying --- the same field Chapter 10 warned about on an inner transaction, turned deliberately on the delegator's own account.

So a delegated LogicSig needs its bounds written in at signing time, because they are the only bounds it will ever have. `Txn.last_valid <= TemplateVar[UInt64]("EXPIRY")` in Example 20-5 is not caution; it is the expiry the payments team did not write --- and it is a template rather than a literal because an absolute round number goes stale between writing a program and signing it.

::: {.gotcha #delegated-logicsig-cannot-be-revoked topic="LogicSigs" title="A signed delegated LogicSig cannot be cancelled"}
The delegator's key signs the program once and is never consulted again, so there is no later moment at which consent can be withdrawn. Deleting your copy of the signed blob changes nothing --- copies may be anywhere, and the network does not know or care where it came from.

The only exit is to rekey the delegating account, which invalidates the delegation by changing what authority the account has. Plan for that before signing: an expiry in `last_valid` costs one line and turns "forever" into "until round N".
:::

## Signing It, and Taking It Back
A delegated LogicSig is signed by a key, and everything about its lifecycle follows from that. On the client side the delegation is one line:

```python
lsig = LogicSigAccount(compiled_program)
lsig.sign(alice.private_key)          # this line is the delegation
```

`lsig` is now a value anybody can hold and use. Submitting with it names Alice as the sender, and the money is Alice's:

```python
txn = PaymentTxn(sender=alice.address, sp=sp, receiver=payee, amt=10_000)
algod.send_transaction(LogicSigTransaction(txn, lsig))
```

A contract account is the same object with no signature on it, and its own address as the sender: `lsig.address()`.

There is no revoke call, so the exit is to change what "Alice's key" means. Rekeying does that: a zero-amount self-payment carrying `rekey_to` moves the account's *signing authority* to another address while the account address stays exactly the same:

```python
algorand.send.payment(PaymentParams(
    sender=alice.address, receiver=alice.address,
    amount=AlgoAmount.from_micro_algo(0),
    rekey_to=rescue.address))          # future signatures must come from here
```

After that the signed LogicSig is refused, because the network no longer accepts Alice's key for Alice's account.

Rekeying back needs the *current* authority to sign, which is the part people get wrong under pressure. `sender` is still Alice's address, and `signer` is the key that now controls it:

```python
algorand.send.payment(PaymentParams(
    sender=alice.address, signer=rescue,
    receiver=alice.address, amount=AlgoAmount.from_micro_algo(0),
    rekey_to=alice.address))
```

And here is the fact that decides whether this counts as revocation: **rekeying back revives the delegation.** The signed program was never destroyed, only made unusable while the authority was elsewhere, so a delegation is revoked exactly as long as the key stays away. If the point was to end it permanently, the account has to stay rekeyed --- or never have been the account holding the money.

::: {.gotcha #rekey-to-an-address-you-do-not-control topic="LogicSigs" title="Rekeying to an address you cannot sign for loses the account"}
`rekey_to` moves signing authority with no confirmation step and no undo. If the destination is an address you do not hold the key for, every asset and every Algo in that account is unreachable --- the account still exists, still shows a balance, and can never send anything again.

Check the `rekey_to` value before signing, and check it again when it is a variable rather than a literal. This is the one transaction field where a typo is unrecoverable.
:::

## Binding to an Application
A LogicSig that authorises an application call has one more field to pin, and it is easy to pin too loosely.

*Predict: the next program pins the transaction type, the rekey field, the fee, and `application_id == 1234`. Write down what it authorises --- and what it will authorise after the application's next update.*

**Example 20-6.** Bound to an application

<!-- finder: see why naming an application is a wider permission than it looks -->

```python
from algopy import Global, TransactionType, Txn, UInt64, logicsig


@logicsig
def any_method_of_that_app() -> bool:
    """Binding to an application id authorises EVERY method on it.

    This looks like "only my app may use this key". It reads as a tight
    binding and is not one: an application id names the program, not the
    call, so every method the router dispatches is inside this permission --
    including ones added after the delegator signed.
    """
    return (
        Txn.type_enum == TransactionType.ApplicationCall
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        and Txn.application_id.id == UInt64(1234)
    )
```

This reads as "only my application may use this". It is not what it says. An application id names a *program*, and a program dispatches many methods --- so this authorises every method the router can reach, including methods added in a later upgrade the delegator never saw.

**Example 20-7.** Bound to one method

<!-- finder: narrow a LogicSig to a single method of a single application -->

```python
from algopy import Bytes, Global, TransactionType, Txn, UInt64, logicsig, op


@logicsig
def one_method_of_that_app() -> bool:
    """The same binding, narrowed to a single method.

    The first application argument of an ARC-4 call is the four-byte method
    selector. Checking it turns "this app" into "this method of this app",
    which is the permission the delegator thought they were granting.
    """
    return (
        Txn.type_enum == TransactionType.ApplicationCall
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        and Txn.application_id.id == UInt64(1234)
        # Two: the selector, and `claim`'s one uint64 argument.
        and Txn.num_app_args == UInt64(2)
        # The selector for `claim(uint64)void`.
        and op.Txn.application_args(0) == Bytes.from_hex("3d1d2f0f")
    )
```

The first application argument of an ARC-4 call is the four-byte method selector, and the count is the selector plus the method's own arguments: two here, because `claim` takes one `uint64`. Bind a method with more arguments and that number changes.

Checking the selector narrows "this application" to "this method of this application". It does not narrow it to *this code*: a selector is a hash of a **signature**, and an upgradeable application can rebind that signature to a different implementation after the delegator has signed. So a method-bound LogicSig on an application that can be updated is a permission over whatever `claim(uint64)void` comes to mean, which is the reason an expiry is not optional even here.

## Parameters Are Fixed When It Compiles
**Example 20-8.** Compiling a LogicSig from a contract

<!-- finder: get a LogicSig's address from inside a smart contract -->

```python
from algopy import Account, ARC4Contract, UInt64, arc4, compile_logicsig

from examples.logicsigs.contract_account import vault

WHO = "A7NMWS3NT3IUDMLVO26ULGXGIIOUQ3ND2TXSER6EBGRZNOBOUIQXHIBGDE"


class Deployer(ARC4Contract):
    @arc4.abimethod
    def vault_address(self) -> Account:
        # One parameter set is one address, both fixed at compile time.
        return compile_logicsig(
            vault,
            template_vars={"BENEFICIARY": Account(WHO),
                           "UNLOCK_ROUND": UInt64(30_000_000)},
        ).account
```

`compile_logicsig` returns a `CompiledLogicSig`, whose single field is `account`, the address the program hashes to once its template variables are substituted. A contract can therefore know an escrow's address without anyone telling it. (`vault` there is Example 20-4; the import path is this book's example package, and in your own project it is wherever you put the `@logicsig`.)

The constraint on that is severe and is not obvious from the signature.

*Predict: the next listing takes the beneficiary and the unlock round as method arguments and compiles the vault for them --- "an escrow for this customer". Say whether it compiles, and if not, what fact about a LogicSig's address stops it.*

```python
from algopy import Account, ARC4Contract, UInt64, arc4, compile_logicsig

from examples.logicsigs.contract_account import vault


class Deployer(ARC4Contract):
    """The obvious way to write "an escrow for this beneficiary", and it does
    not compile: `non-constant template value`.

    A LogicSig's address is the hash of its program bytes, so a template
    variable is substituted BEFORE compilation. There is no runtime value to
    substitute, and a method argument is a runtime value.
    """

    @arc4.abimethod
    def escrow_for(self, who: Account, unlock: UInt64) -> Account:
        compiled = compile_logicsig(
            vault, template_vars={"BENEFICIARY": who, "UNLOCK_ROUND": unlock}
        )
        return compiled.account
```

That does not compile. It reports `non-constant template value`, twice, once per template variable. And the reason is not a limitation of the compiler --- it is what a LogicSig address *is*. The address hashes the program bytes, so a template variable has to be substituted before there are bytes to hash, which is before anything runs. A method argument does not exist yet.

A module-level constant does not rescue it either: `PAYEE = Account("...")` at module scope reports `unsupported statement type at module level`, and the second error names a global constant reference rather than the template variable, which sends people looking in the wrong place. Put the literal inline at the call site.

::: {.gotcha #logicsig-params-are-compile-time topic="LogicSigs" title="A parameterised LogicSig gives one address per parameter set, chosen at compile time"}
The natural way to write "an escrow for this customer" takes the customer as an argument, and that is exactly the form that will not compile. A per-customer escrow is not a per-customer compile.

Two shapes work instead. Compile **one** program that reads the customer from somewhere it can verify, such as its own account's state or a value the calling contract passes and checks; or accept that the set of parameter combinations is fixed at build time and enumerate them. Reaching for the first is almost always right; the second is how people end up with a deployment script that compiles four hundred LogicSigs.
:::

## Bounding It in Time and in Count
A LogicSig has no state, so it cannot count. `first_valid` and `last_valid` bound *when* a transaction is valid and say nothing about how many times it may be submitted --- and a signed transaction can be resubmitted by anyone who has a copy, for as long as its window is open.

**Example 20-9.** A one-shot LogicSig

<!-- finder: stop a LogicSig-signed transaction being replayed -->

```python
from algopy import (Account, Bytes, Global, TemplateVar, TransactionType, Txn,
                    UInt64, logicsig)


@logicsig
def one_payment_per_window() -> bool:
    """A LogicSig cannot count how many transactions it has signed.

    It has no state. Replaying the same signed transaction is free, and
    `first_valid`/`last_valid` bound *when* a transaction is valid rather than
    *how often*. A lease is what bounds how often: the network refuses a
    second transaction carrying the same (sender, lease) pair while the first
    one's validity window is still open.
    """
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        and Txn.receiver == TemplateVar[Account]("PAYEE")
        and Txn.amount <= UInt64(100_000)
        and Txn.last_valid <= TemplateVar[UInt64]("EXPIRY")
        # The lease is pinned, so two transactions signed by this program
        # cannot both be live. Bounding the window bounds how soon the next
        # one may follow.
        and Txn.lease == Bytes.from_hex("00" * 31 + "01")
        # A MINIMUM, not a maximum. The lease is held until the accepted
        # transaction's `last_valid`, so a wide window is what spaces the
        # next one out; `<=` here would be vacuous, since the protocol
        # already caps a transaction's life at 1,000 rounds.
        and Txn.last_valid - Txn.first_valid >= UInt64(1_000)
    )
```

A lease is a 32-byte value that reserves the pair `(sender, lease)` for the transaction's validity window. While the first transaction is live, the network refuses a second one carrying the same pair from the same sender. Pinning the lease in the program and forcing a wide window is what turns "a payment up to 100,000" --- which Example 20-9 bounds, along with an expiry, because a lease is not a substitute for either --- into "a payment up to 100,000, at most once per thousand rounds".

The two mechanisms answer different questions and neither substitutes for the other: the window decides *when*, and the lease decides *how often within it*.

## Arguments Are Not Signed
**Example 20-10.** A LogicSig that believes what it is told

<!-- finder: the LogicSig version of trusting caller-supplied input -->

```python
from algopy import Bytes, Global, TransactionType, Txn, UInt64, logicsig, op


@logicsig
def trusts_its_arguments() -> bool:
    """LogicSig arguments are supplied by the submitter and signed by nobody.

    The delegator signed the PROGRAM. Arguments arrive with the transaction,
    from whoever assembled it, and the signature covers none of them. Reading
    an argument and believing it is the same mistake as reading an
    application id from a caller.
    """
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        # The submitter names their own limit. They will name a large one.
        and Txn.amount <= op.btoi(op.arg(0))
        and op.arg(1) == Bytes(b"approved")
    )
```

The delegator signed the program. Arguments are attached to the transaction by whoever submits it, and the signature covers none of them, so `op.arg(0)` is a number the attacker chose, and `Txn.amount <= op.btoi(op.arg(0))` is a bound the attacker sets.

The second check is worse and is a common shape: `op.arg(1) == Bytes(b"approved")` looks like a password. It is a string sitting in the program bytes, and those bytes are held by everybody the signed program was given to --- and become public to everyone the moment one transaction using it lands, where an indexer serves them as `signature.logicsig.logic`. A secret that has to be transmitted to be used is not a secret.

This is Chapter 15's rule in a different execution model. There, a caller-supplied application id was an instruction rather than an integration. Here, a caller-supplied argument is an instruction rather than an input. **What arrives with the transaction was chosen by whoever built the transaction.**

::: {.gotcha #logicsig-args-are-attacker-controlled topic="LogicSigs" title="A LogicSig's arguments are supplied by the submitter, not the signer"}
The signature covers the program, not the arguments. Anything read from `op.arg(n)` was chosen by whoever assembled the transaction, so it may bound nothing and prove nothing. A secret compared against an argument is worse still --- the program's bytes are public at an address anyone can query.
:::

## What It Costs
**Example 20-11.** A LogicSig that spends real budget

<!-- finder: see where a LogicSig's opcode budget comes from -->

```python
from algopy import (Account, Global, TemplateVar, TransactionType, Txn,
                    UInt64, logicsig, op, urange)


@logicsig
def expensive() -> bool:
    """A LogicSig gets 20,000 opcode units, and a group pools them.

    The pool is `len(group) x 20,000` and every transaction contributes,
    whether or not it carries a LogicSig -- so a program too costly to verify
    on its own becomes affordable beside transactions that do nothing.

    The guards below are not part of that demonstration and are here anyway.
    An example whose subject is the budget is still a program that authorises
    a payment, and a reader who copies the interesting half will copy whatever
    is around it.
    """
    total = UInt64(0)
    for i in urange(400):
        # The residue matters: summing whole 64-bit digest prefixes
        # overflows a UInt64 on the second iteration.
        total += op.btoi(op.sha256(op.itob(i))[:8]) % UInt64(1_000)
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        and Txn.receiver == TemplateVar[Account]("PAYEE")
        and Txn.amount <= UInt64(100_000)
        and Txn.last_valid <= TemplateVar[UInt64]("EXPIRY")
        and total > UInt64(0)
    )
```

A LogicSig gets 20,000 opcode units, which is a different and much larger allowance than an application call's 700. It also comes from a separate pool, so a LogicSig and the application call beside it are not competing.

The number that matters for expensive programs is the pooled one, and it is easier to see than to be told. Example 20-11 hashes in a loop until it is just past what one program is allowed --- 400 loop rounds at 51 units each, a `sha256` plus the arithmetic around it, a little over 20,400.

*Predict: that program is submitted alone. Say what happens --- and then name the cheapest change to the submission, not to the program, that makes it pass.*

Submitted on its own and then again with a single companion transaction that does nothing at all:

```console
>>> submit(1)   # the verifier alone
rejected: dynamic cost budget exceeded
>>> submit(2)   # the same program, one companion transaction
accepted
```

Same program, same arguments, same signature. The only thing that changed is that a second transaction was sitting beside it. Since AVM v10 the LogicSig budget is `len(group) x 20,000`, and **every transaction in the group contributes, whether or not it carries a LogicSig**. A verifier too costly to run on its own becomes affordable next to seven transactions that do nothing --- which is the mechanism Chapter 23 runs on, and the reason its proof verification is arithmetically possible at all.

Cost pooling arrived one consensus version before size pooling: cost at AVM v10, size at AVM v11. Size pooling raised a 1,000-byte limit, on the program *and its arguments* together, to `len(group) x 1,000`. Consensus v42 split those. The program's 1,000-byte-per-transaction allowance is now the *free* amount rather than a hard cap --- a single transaction may carry up to 16,000 bytes of program by paying a per-byte surcharge --- and LogicSig arguments get their own pooled 1,000 bytes per transaction, which you cannot buy past.

Which wall a program meets first depends on its shape rather than its ambition: a loop is tiny and expensive, and Example 20-11 exhausts the whole cost budget in well under a hundred bytes.

## Four Programs With One Hole Each
Each of the four below is a working LogicSig that does the job its author wrote it for, and each is missing something that lets a holder take money the author did not mean to give them. Cover the explanation under each one and find the hole before reading on.

**One.** Offered as a program that approves almost nothing: a payment of zero, at no fee.

```python
@logicsig
def surely_harmless() -> bool:
    return Txn.fee == UInt64(0) and Txn.amount == UInt64(0)
```

*A payment of zero moves nothing. What can this sign for?*

Everything the account holds. `close_remainder_to` is not pinned, and it empties the sender's balance into an address of the submitter's choosing *as a side effect of the payment*, so the amount being zero is not a limit but a disguise. `rekey_to` is not pinned either, which hands over the account permanently. Against an account funded with 3 Algo, one such transaction closed out the full 3,000,000 microAlgo to a stranger, who netted 2,998,000 once the group's 2,000 in fees was paid.

The zero fee is not even a cost charged to this transaction: fees pool across a group, so a companion transaction of the stranger's paid the 2,000 for both. A condition that looks like a restriction can be satisfied by somebody else's transaction.

**Two.** A delegated allowance: the delegator signs it once, and whoever holds it may spend up to 50,000 microAlgo at a time from the delegator's account.

```python
@logicsig
def allowance_v1() -> bool:
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        and Txn.amount <= UInt64(50_000)
        and Txn.last_valid <= TemplateVar[UInt64]("EXPIRY")
    )
```

*Where does the money go?*

Nothing says. There is no `Txn.receiver` check, so the holder names themselves and is paid 50,000 microAlgo. Then again. The amount cap bounds one transaction and nothing bounds the number of them, so the real limit is the delegator's balance and the expiry, whichever runs out first. A bound on *how much* is not a bound on *to whom*, and the second is the one that decides whether this is an allowance or a withdrawal.

**Three.** A one-shot payment, bounded by a lease so that the same transaction cannot be replayed inside its validity window.

```python
@logicsig
def once_per_window_v1() -> bool:
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        and Txn.receiver == TemplateVar[Account]("PAYEE")
        and Txn.lease == Bytes.from_hex("00" * 31 + "01")
        and Txn.last_valid - Txn.first_valid >= UInt64(1_000)
    )
```

*The receiver is pinned and the payment can only happen once per window. What is still unbounded?*

The amount. Once per thousand rounds is a rate, not a cap, and one payment can be the whole account: measured against a funded escrow, a single transaction took 19 Algo. There is no expiry either, so the rate continues for as long as the account has anything in it. The lease is doing exactly what it was written to do, which is what makes this one hard to see: the guard you are looking at works, and the one you need is absent.

**Four.** A program that hashes in a loop to spend most of a LogicSig's opcode budget, written to demonstrate group pooling.

```python
@logicsig
def pooled_v1() -> bool:
    total = UInt64(0)
    for i in urange(400):
        total += op.btoi(op.sha256(op.itob(i))[:8]) % UInt64(1_000)
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        and total > UInt64(0)
    )
```

*The loop is the point of this program. What did the loop distract you from?*

The last line. `total > UInt64(0)` is arithmetic on numbers the program made up, so it says nothing about the transaction --- and once you take it out, the guard list is four field checks and no receiver, no amount and no expiry. A holder can pay anyone anything until the account is empty; measured, 18 Algo to a stranger. The budget demonstration is correct and complete, and it is not the part that decides who gets paid.

**A LogicSig is not made safe by the checks it has. It is made unsafe by the ones it lacks**, and the fields it never mentions are invisible on the page in a way a wrong line is not --- there is nothing to read. Work down a list rather than down the program: type, close, rekey, fee, receiver, amount, expiry, and network --- plus `asset_close_to` wherever asset transfers are permitted, and the group binding Chapter 21 adds. Anything the list names and the program does not is a permission you granted without deciding to.

## Retrieval
Answer these from memory before moving on. Three of them reach back into earlier chapters on purpose.

1. A LogicSig replaces something. What?
2. Which transaction fields must a LogicSig pin on a payment, which is the third one and when does it apply, and why must a stateful contract *not* pin any of them on its group-mates?
3. A LogicSig checks `Txn.close_remainder_to == Global.zero_address` and nothing else. What does an asset transfer do to that check, and why?
4. A delegated LogicSig spends from whose account? Who submits the transaction?
5. Your customer asks you to cancel their delegated LogicSig. What are your options?
6. Why can a LogicSig's template variable not be a method argument?
7. `first_valid`/`last_valid` and a lease bound different things. Which bounds which?
8. A group of six transactions carries one LogicSig. How many opcode units does that program have?
9. *(From Chapter 11)* An application call starts with 700 opcode units and can buy more with `ensure_budget`. Where does a LogicSig's 20,000 sit relative to that pool --- and can either side buy budget for the other?
10. *(From Chapter 10)* An account is rekeyed. What does `Txn.sender` report on a transaction it sends afterwards, and what has changed about who may authorise one?
11. *(From Chapter 15)* A contract takes an application id as a method argument. State the rule that makes that dangerous, then say what the LogicSig version of the same mistake looks like.

## Exercises
1. **(Trace)** A contract account holds 40 Algo under a LogicSig that pins `close_remainder_to`, `rekey_to` and a fee cap, and requires `Txn.receiver == TemplateVar[Account]("PAYEE")`. It has no amount bound and no expiry. Walk through what the payee can extract and over what period, then say what changes if the program is delegated from a funded account rather than being a contract account --- and which of the two situations the delegator can still get out of.

2. **(Parsons)** These six lines are offered as the body of a safe delegated payment LogicSig. Five belong; one is dead under another and one is missing entirely. Assemble the program, name the dead line and say what makes it dead, and name what is missing and what it would cost to leave out.

   ```text
   and Txn.fee <= Global.min_txn_fee * UInt64(10)
   Txn.type_enum == TransactionType.Payment
   and Txn.last_valid <= TemplateVar[UInt64]("EXPIRY")
   and Txn.asset_close_to == Global.zero_address
   and Txn.rekey_to == Global.zero_address
   and Txn.close_remainder_to == Global.zero_address
   ```

3. **(Debug)** A team ships a LogicSig that authorises `claim(uint64)void` on their application, checking `Txn.application_id.id` and the first application argument. Six months later an auditor reports that the LogicSig authorises a method the team has never heard of. The application id is correct and the selector check is correct. What happened, and what would have prevented it?

4. **(Compare)** Compare a contract account and a delegated LogicSig on: who can spend, what happens if the program has a bug, what happens if the key holder is compromised, how you shut it down, and what it costs to set up. Name a use case that forces each.

5. **(Extend)** Example 20-9 makes a payment at most once per thousand rounds. Extend the idea to "at most once, ever". Say what the program must check, where the state that makes it possible has to live, and why a LogicSig alone cannot do it.

## Before You Continue
- [ ] I can say what a LogicSig replaces and why it has no state
- [ ] I can write the guards a LogicSig needs, and say why a stateful contract must not copy them
- [ ] I can tell a contract account from a delegated LogicSig by who spends
- [ ] I can bind a LogicSig to one method, and say what an upgradeable application does to that binding
- [ ] I can say what revoking a delegated LogicSig actually requires, and compute a group's pooled budget

## Handoff: What the Limit Order Book Needs
Chapter 21 gives every trader a LogicSig that encodes their order, and lets keeper bots fill those orders by putting up the other side themselves. Every LogicSig in it is delegated, which means every defect in this chapter is a defect somebody else can spend. Table 20-1 is what it draws on.

: Table 20-1. What Chapter 21 draws on from this chapter

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| Example 20-3 | The mandatory field checks on every order LogicSig | An order is a promise to trade at a price. Say which of Example 20-3's seven conditions stops a keeper filling it twice --- and if the answer is none of them, say what has to. |
| Example 20-5 | Every order the trader signs | The trader wants to cancel an unfilled order. Say what the project has to do, given that a signature cannot be withdrawn. |
| Example 20-7 | Binding an order to the book's `fill_order` method | The order authorises one method. Say what goes wrong if it names the application and not the method. |
| Example 20-9 | Nothing --- the project solves replay a different way | The order is signed once and sits on a public relay. Work out what stops the second fill when there is no lease, and what state has to exist for that to work. |
| Example 20-10 | The keeper supplies the fill amount | The keeper is not the trader. Say where that number must be checked, and against what the trader signed. |
