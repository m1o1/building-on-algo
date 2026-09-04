\newpage

\part{Further Reading}

Part V is a pointer, not a course. After the lottery, this book goes to
what cryptography costs on the AVM (Chapter 22) and then to shipping
(Chapter 24). The LogicSig material that used to occupy this slot — two
binding modes, a delegated limit-order book, and a mastery checkpoint
built around attacking a delegation — lives in the companion tree at
`advanced/`.

```{=latex}
\renewcommand{\BOAchapterkind}{}
```
# Further Reading: Logic Signatures

A LogicSig is a program that *replaces a private key*. The network runs
the program against the transaction; if it returns true, the transaction
is signed. Nothing was decrypted, nobody was consulted, and no contract
state was read.

Two bindings exist, and they are not interchangeable:

- **Contract account.** The program hash *is* the address. There is no
  private key. Anyone may submit a transaction from that address; the
  program alone decides whether it is allowed.
- **Delegated.** An existing account signs the program once. Anyone who
  holds the signed bytes may spend from that account, subject only to
  whatever bounds the program already contains. The signature cannot be
  taken back.

This book teaches the first shape in one listing, because Chapter 22
needs the 20,000-unit LogicSig opcode budget and a contract account is
how you get it. It does not teach the second.

## Why delegated signatures left the spine

Delegated LogicSigs are a high-security-risk product feature. The
signature is a cheque the account holder cannot cancel: copies live
wherever the first recipient put them, and the only revocation that does
not depend on the program is rekeying the account. Production wallets
such as **Pera will not allow a user to sign a delegated LogicSig** for
that reason.

Teaching a pattern readers largely cannot use in production wallets —
and that is easy to get dangerously wrong — is not worth the page budget
on this book's path (foundations → custody → DEX → randomness →
shipping). The full course is companion material, not a missing chapter
you should improvise.

::: {.gotcha #delegated-logicsig-wallets topic="Authorization" title="Production wallets will not sign a delegated LogicSig"}
A delegated LogicSig is a signature the account holder cannot revoke.
Pera and similar wallets refuse to present one for signing, because the
user cannot see, later, every copy of what they authorised. Do not
design a product that requires an end user to sign a delegation.
Contract-account LogicSigs are a different binding: the program *is* the
account, and nobody is asked to sign.
:::

## Contract accounts, briefly

The address of a contract-account LogicSig is the hash of its program.
Example 20-1 is the whole shape Chapter 22 will use: a vault that will
pay a named beneficiary after a named round, and that will not rekey,
close out, or overpay a fee.

**Example 20-1.** A contract account with no private key

<!-- example: examples/logicsigs/contract_account.py mode=compile -->
<!-- finder: see a LogicSig that is its own account, with no key anywhere -->

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

The guards that pin `close_remainder_to` and `rekey_to` to the zero
address are mandatory on a LogicSig, because the program is the only
thing standing between the account and anyone who submits a transaction
from it. They do **not** belong on a stateful contract's check of an
incoming grouped payment — Chapter 10 already showed that copying them
there only restricts the caller's wallet. Appendix B tables the LogicSig
opcode budget (20,000 units per group transaction, pooled) against an
application call's 700; Chapter 22 is where a pairing check spends that
larger pool.

If you ever write a LogicSig of either binding, pin at least: transaction
type, `close_remainder_to`, `rekey_to`, a fee cap, the receiver or
application the program is willing to talk to, and an expiry. A program
without an expiry is valid forever.

## Where the rest of it went

The companion tree keeps the original teaching, not a summary of it:

- Full LogicSig course (two bindings, four programs with one hole
  each, leases, selector binding, budget):
  `advanced/stateless-programs/20-signing-without-a-key.md`
- Delegated limit-order book (hybrid design, keepers, the
  eight-item checklist):
  `advanced/stateless-programs/21-delegated-limit-order-book.md`
- Mastery checkpoint: a one-shot delegation you then attack:
  `advanced/stateless-programs/21z-checkpoint-stateless-programs.md`
- Runnable AlgoKit project: `advanced/limit-order-book/`

Those files keep their original chapter numbers (20, 21) so internal
cross-references still resolve. They are out of this book's spine: they
are not in the table of contents, they are not drift-checked as if they
were, and Chapter 22 does not assume you have built any of them.

Private governance voting — the other split — is pointed from the end of
Chapter 22, after the cost survey that used to feed it.

## Before You Continue
- [ ] I can say why this book does not teach delegated LogicSigs as a
  product path, and name the wallet policy that makes the point
- [ ] I can tell a contract-account LogicSig from a delegation, and say
  which of the two this spine still uses
- [ ] I know where the companion files live if I need the full course

Part VI is next: what hashes, signatures, merkle proofs, VRFs and pairing
checks cost on the AVM, and the failure that makes an expensive check
worthless.
