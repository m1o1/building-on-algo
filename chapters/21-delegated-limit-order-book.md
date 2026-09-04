\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Project}}
```
# Delegated Limit Order Book with LogicSig Agents

**Building an on-chain limit order system where traders encode orders as delegated Logic Signatures and market-making bots ("keepers") execute them --- Chapter 20's stateless programs put to work beside the stateful contracts they coordinate with.**

Chapter 20 ended holding a signed delegation and an uncomfortable fact: every bound it will ever have is already inside it. This project is where that discipline pays for itself. A limit order is a price one trader names in advance --- "sell up to 500 USDC for ALGO at 0.25 ALGO per USDC, expiring in 24 hours" --- and Alice places one by signing a LogicSig program encoding exactly those rules. The order then rests off-chain, costing nothing and moving nothing, until any keeper fills it by submitting the atomic group the program was written to audit.

The system is the hybrid pattern some production Algorand DeFi protocols use: a stateful order book contract coordinates shared state, while stateless LogicSig programs encode per-trader rules that keepers execute permissionlessly.

::: {.spec title="Your commission: a resting order a stranger can safely fill"}
1. A trader states an order --- asset pair, limit price, size cap, expiry --- and signs it once. Until filled, it rests off-chain and costs nothing.
2. Any keeper can fill any resting order, wholly or in parts, without holding the trader's key or asking anyone's permission.
3. A fill settles atomically: the trader's tokens move only in a group that pays the trader at their price or better.
4. The trader can cancel on-chain, and cancellation stops future fills even though the signature cannot be withdrawn.
5. Anyone can clean up an expired order, and the order's box deposit returns to the trader.
:::

## Run It First
The finished system for this chapter is in `projects/limit-order-book/`. Run it before you read, because a limit order book with nobody matching orders cannot be demonstrated at all --- the interesting half is the keeper, and the keeper is off chain. Before running it, predict which transaction in the fill group carries the seller's signature, and what the seller's account has to have agreed to for that transaction to be valid.

```bash
cd projects/limit-order-book
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_limit_order_book
algokit project run test
```

Table 21-1 lists the output checkpoints to compare against the workflow output.

: Table 21-1. Output checkpoints for the limit order workflow

| Output checkpoint | What to watch for |
|-------------------|-------------------|
| Order book app ID | The stateful half exists and holds the order registry |
| Order placed, id returned | The id came back from the contract rather than being assumed; a signed delegation bound to the wrong id is unusable |
| Signature type on the transfer | The middle transaction reads `lsig`, not `sig` --- the seller's asset moved under a program, submitted by an account that never held their key |
| Partial fill, then filled | 200 of 500 leaves the order live; the remaining 300 closes it |
| Cancelled order refuses a fill | The keeper still holds a valid signed program, and the contract refuses anyway |
| Expired order cleaned up | 57,700 microAlgo of box minimum balance comes back |

The keeper polls, decides, assembles and submits; nothing about that is on chain. What is on chain is the refusal of everything it is not allowed to do.

## What You Need First

Chapter 20 ended with a Handoff table (Table 20-1) naming what this project would draw on. Table 21-2 is the other side of it. Every row is a program or a defect you have already run; this chapter is where each one either spends money or refuses to.

Answer the predict column before you follow the link.

: Table 21-2. What Chapter 20 built that this project assumes

| Prerequisite | Where it lands here | Predict before you read it |
|--------------|---------------------|----------------------------|
| Example 20-3 | The mandatory-checks block of the order program, two guards longer | Chapter 20 promised this project's checklist runs to eight items where its own ran to four. Name the additions an *order* needs that a fixed-payee allowance did not, before Table 21-3 lists them. |
| Example 20-5 | Every order: the trader signs once, a keeper submits, and the trader's tokens move | Cancellation is in the commission, and a signature cannot be withdrawn. Predict where "cancelled" must live so that every possible fill is forced to look at it. |
| Example 20-7 | The last three asserts of the order program, pinning `fill_order` on the book | That example warned that a selector on an upgradeable app binds to whatever the method comes to mean. Say what the order book must promise about its own lifecycle before selector binding is worth anything. |
| Example 20-9 | Nowhere --- no order carries a lease, and what replaces it is the design Chapter 20's Exercise 5 asked you for | A lease reserves `(sender, lease)` once per validity window; an order may fill five times in parts. Work out what plays the lease's role here, and which of the two programs enforces it. |
| Example 20-10 | The keeper chooses `fill_amount` and assembles the whole group | The keeper is not the trader. Count the checks that number must pass before Alice's tokens move, and say what each one compares it against. |

## Project Setup

You are already in `projects/limit-order-book/` from Run It First. If you would rather scaffold your own, Chapter 9's setup note applies, with `limit_order_book` in place of `token_vesting`, and add a second directory, `smart_contracts/limit_order_lsig/`.

The contract goes in `smart_contracts/limit_order_book/contract.py` and the LogicSig in `smart_contracts/limit_order_lsig/contract.py`. Delete the template-generated `deploy_config.py` in `smart_contracts/limit_order_book/`; it references the old `HelloWorld` contract.


## From Chapter 20 to a Resting Order

An order is a delegated LogicSig with a job, and everything that makes one dangerous was Chapter 20's subject. None of it is re-derived here:

- A program that signs instead of a key --- stateless, inner-transaction-less, one transaction in and a verdict out --- is Example 20-1. The two ways it binds, contract account or delegation (Figure 20-1's two columns), are Examples 20-4 and 20-5. Every program in this project is delegated: an order spends from the trader's own account, submitted by a keeper the trader has never met.
- The guards no delegated program ships without --- close-to, rekey-to, the fee cap, the expiry --- are Example 20-3, and the fact that there is no revoke, only rekey, is Example 20-5.
- Binding to one method of one application is Example 20-7. The selector pinned here is `fill_order`'s.
- Example 20-9 bounded replay with a lease. No order carries one --- the order program substitutes something better suited to partial fills.
- Arguments arrive unsigned and submitter-chosen (Example 20-10), which is why every order parameter in this project is a `TemplateVar` and none is an `op.arg`.
- The budget is Example 20-11's: 20,000 cost units per group transaction, pooled, separate from the 700 an app call gets ([the puya budget reference](https://algorandfoundation.github.io/puya/language-guide/opcode-budget/) documents both pools). The three-transaction fill group carries 60,000, of which this chapter's program needs under 1,000. Chapter 23 is where the pool earns its keep.

Three things are genuinely new: the completed checklist, the network binding, and the group binding.

### The Eight-Item Checklist

Chapter 20 shipped four guards and named the ones it could not yet justify. Table 21-3 is the completed list --- the checklist every program in this project is audited against, and the one Chapter 23 holds a generated verifier to.

: Table 21-3. The delegated LogicSig guard checklist

| # | Check | What its absence permits | Taught |
|---|-------|--------------------------|--------|
| 1 | `close_remainder_to` pinned to zero | the balance drained as a payment's side effect | Example 20-3 |
| 2 | `asset_close_to` pinned to zero | every ASA holding closed out alongside a transfer | named in Chapter 20, first exercised here |
| 3 | `rekey_to` pinned to zero | the account handed over, permanently | Example 20-3 |
| 4 | fee capped | the balance drained to proposers as fees | Example 20-3 |
| 5 | expiry via `last_valid` | a delegation valid forever | Examples 20-3, 20-5 |
| 6 | genesis hash pinned | the same signature spent on every Algorand network | this chapter |
| 7 | group bound: size, index, and the exact app call | the program approving in a context it never imagined | this chapter |
| 8 | no argument trusted | bounds the submitter chose for themselves | Example 20-10 |

Item 2 earns its place the moment a program authorizes an asset transfer, which Chapter 20's payment-only programs never did and every order here does. Items 6 and 7 are the rest of this part.

### The Network Is Not in the Signature

A signed delegated LogicSig validates on every Algorand network: nothing in a signature says *where*. Application and asset ids are no defense --- they are per-network counters, and the id your order book has on TestNet belongs to somebody else's contract on MainNet. The pin is the network's genesis hash, 32 bytes the program compares against `Global.genesis_hash`, compiled in as a template variable like every other order parameter.

The same 32 bytes wear three costumes in this workflow, and mixing them up is the most common compile-side failure. Table 21-4 lists all three.

: Table 21-4. Genesis hash representations across the workflow

| Place | Representation |
|-------|----------------|
| algod suggested params | base64 string in `suggested_params().gh` |
| Python client code | raw `bytes` after `base64.b64decode(...)` |
| TEAL template replacement | byte literal such as `0x0123...` |

### Bound to a Group, Not Just a Method

Example 20-7 pinned a method. An order must pin the company that method call keeps, because a resting order is one card in a hand somebody else plays: the program approves a single asset transfer, and everything that makes the transfer *a trade* --- the payment coming back, the contract call accounting for it --- is elsewhere in the group. So the program checks the group's size, its own position in it, whom the transaction before it pays, and the exact application call after it. The LogicSig build writes those checks and makes the argument the rest of the chapter cites.


## Architecture: The Hybrid Stateful + Stateless Pattern

### When This Architecture Is Right

Delegation is the sharp end of Algorand, and most systems should not pick it up. The default architecture on modern Algorand is a stateful contract that takes deposits and holds them in escrow: every guarantee enforced by code, nothing resting in anyone's wallet that a missing check could spend. What that default cannot give you is an order that costs nothing until it fills. An escrowed order book locks Alice's 500 USDC in the contract the moment she places the order, for a fill that may never come; a delegated one leaves the tokens in her wallet --- spendable, stakeable, hers --- and still lets a keeper settle the instant the price crosses. That is the trade: delegation buys capital efficiency and standing intent, and its price is that every guarantee must be written into a program before it is signed, with no revoke and no patch release. Take the deal when resting intent over un-escrowed funds *is* the product, as it is for a limit order book; refuse it when a deposit is acceptable, which is almost everywhere else. Table 21-5 compresses the choice.

: Table 21-5. Choosing between a LogicSig and a smart contract

| Use case | Recommendation | Rationale |
|----------|---------------|-----------|
| DEX pool / AMM | Smart contract | Needs state (reserves, LP supply) --- Chapter 14 |
| Limit order rules | LogicSig (delegated) | Stateless, per-user, parameterized --- this chapter |
| Order book tracking | Smart contract | Needs shared mutable state --- this chapter |
| ZK proof verification | LogicSig (contract account) | Needs the 20,000-unit pooled cost budget --- Chapter 23 |

Every row is a build this book performs, which is what makes the recommendations checkable rather than folklore.

### Why You Need Both

*Before reading on, think about what a limit order system needs. It must enforce per-user trading rules trustlessly (correct asset, acceptable price, expiry) while also tracking global state (which orders exist, partial fills, double-fill prevention). Could you build this with just a smart contract? Just a LogicSig? What would you lose in each case?*

A limit order system needs two things that pull in opposite directions. (This hybrid pattern combines [smart contracts](https://dev.algorand.co/concepts/smart-contracts/overview/) with [LogicSigs](https://dev.algorand.co/concepts/smart-contracts/logic-sigs/).)

1. **Per-user trading rules.** Each user has unique parameters: which assets, what price, how much, when it expires. These rules must be enforced trustlessly when a keeper fills the order.

2. **Shared order book state.** The system needs to track which orders exist, prevent double-fills, record partial fills, and manage the matching engine.

LogicSigs handle #1: each order is a unique program encoding that user's exact trading rules. Smart contracts handle #2: the order book contract maintains state across all orders.

Figure 21-1 is the architecture.

![Figure 21-1. The hybrid: one stateful order book coordinating every order's shared record, one stateless program per order enforcing that trader's rules, and the atomic group as the weld between them.](figures/fig-21-1-hybrid-architecture.svg)

### The Flow: Placing an Order

1. **Alice decides** to sell 500 USDC for ALGO at 0.25 ALGO per USDC, expiring in ~24 hours (~20,000 rounds)
2. **Client compiles** the limit order LogicSig with Alice's parameters as template variables, including the order ID the order book will assign (read from the contract's `next_order_id` global state; verify it matches the ID `place_order` returns)
3. **Alice signs** the compiled LogicSig with her private key (delegation)
4. **Client submits** a two-transaction atomic group: the box minimum-balance payment, then the app call to `place_order(sell_asset, buy_asset, price_n, price_d, max_amount, expiry, lsig_hash)`. The order book records the order in box storage
5. **Client stores** the signed LogicSig and broadcasts it to keepers (via an off-chain relay, API, or indexer event)

### The Flow: Filling an Order

1. **Keeper observes** Alice's open order (via indexer or off-chain relay)
2. **Keeper constructs** an atomic group:
   - [0] `Keeper → Alice: Payment of ALGO`, signed by keeper's private key
   - [1] `Alice → Keeper: Asset transfer of USDC`, authorized by Alice's signed LogicSig
   - [2] `Keeper → OrderBook: App call to fill_order(order_id)`, signed by keeper
3. **AVM executes** the group atomically:
   - Alice's LogicSig validates that the USDC transfer is grouped with a `fill_order` call for her specific order on the order book, the price is correct, and safety checks pass
   - The keeper's payment sends ALGO to Alice
   - The order book contract verifies the fill, updates the filled amount, and emits events
4. If **any** transaction fails, the **entire** group is rejected. Alice's USDC never leaves without her receiving the correct ALGO amount.

### The Flow: Cancellation

Alice can cancel anytime by calling `cancel_order` directly. The order book marks the order as cancelled, and any later fill attempt fails because `fill_order` checks that the order is still active. Why a keeper holding a still-valid signature cannot simply route around that check is the order program's binding argument.


## Building the Limit Order LogicSig

### The Complete LogicSig Program

The LogicSig is structured in six sections: template variable declarations, mandatory safety checks, transaction type validation, group structure validation, buy-side price verification, and order book call binding. (See [Algorand Python compilation](https://algorandfoundation.github.io/puya/language-guide/compile/) for template variable usage.) Add the following to `smart_contracts/limit_order_lsig/contract.py`:

```python
from algopy import (
    Asset, Application, Bytes, Global, Txn, UInt64, arc4, gtxn, logicsig,
    TemplateVar, TransactionType,
)

@logicsig
def limit_order() -> bool:
    """Delegated LogicSig encoding a limit sell order."""
    # ── Template variables (filled at compile time) ──────────
    ORDER_BOOK_APP_ID = TemplateVar[UInt64]("ORDER_BOOK_APP_ID")
    GENESIS_HASH = TemplateVar[Bytes]("GENESIS_HASH")
    SELL_ASSET = TemplateVar[UInt64]("SELL_ASSET")
    BUY_ASSET = TemplateVar[UInt64]("BUY_ASSET")
    PRICE_N = TemplateVar[UInt64]("PRICE_N")   # Numerator of price
    PRICE_D = TemplateVar[UInt64]("PRICE_D")   # Denominator of price
    MAX_SELL = TemplateVar[UInt64]("MAX_SELL")
    EXPIRY_ROUND = TemplateVar[UInt64]("EXPIRY_ROUND")
    ORDER_ID = TemplateVar[UInt64]("ORDER_ID")

    # ── Safety checks (MANDATORY --- never remove) ──────────
    assert Txn.close_remainder_to == Global.zero_address
    assert Txn.asset_close_to == Global.zero_address
    assert Txn.rekey_to == Global.zero_address
    assert Txn.fee <= UInt64(10_000)
    assert Txn.last_valid <= EXPIRY_ROUND
    assert Global.genesis_hash == GENESIS_HASH

    # ── Transaction type and amount check ────────────────────
    assert Txn.type_enum == TransactionType.AssetTransfer
    assert Txn.xfer_asset == Asset(SELL_ASSET)
    assert Txn.asset_amount <= MAX_SELL
    assert Txn.asset_amount > UInt64(0)

    # ── Group structure validation ───────────────────────────
    # [0] Keeper's buy-side payment, [1] This sell txn, [2] Order book app call
    assert Global.group_size == UInt64(3)
    assert Txn.group_index == UInt64(1)

    # ── Verify the buy-side payment meets the price ──────────
    if BUY_ASSET == UInt64(0):
        assert gtxn.Transaction(0).type == TransactionType.Payment
        assert gtxn.Transaction(0).receiver == Txn.sender
        # Cross-multiply: buy_amount * PRICE_D >= sell_amount * PRICE_N
        assert gtxn.Transaction(0).amount * PRICE_D >= Txn.asset_amount * PRICE_N
    else:
        assert gtxn.Transaction(0).type == TransactionType.AssetTransfer
        assert gtxn.Transaction(0).xfer_asset == Asset(BUY_ASSET)
        assert gtxn.Transaction(0).asset_receiver == Txn.sender
        received = gtxn.Transaction(0).asset_amount
        assert received * PRICE_D >= Txn.asset_amount * PRICE_N

    # ── Bind to the exact order book call ────────────────────
    # gtxn.ApplicationCallTransaction asserts the type is appl
    app_call = gtxn.ApplicationCallTransaction(2)
    assert app_call.app_id == Application(ORDER_BOOK_APP_ID)
    assert app_call.app_args(0) == arc4.arc4_signature(
        "fill_order(uint64,uint64,axfer)void"
    )
    assert app_call.app_args(1) == arc4.UInt64(ORDER_ID).bytes

    return True
```

The mandatory safety block is Table 21-3's items 1 through 6, in program order; the group checks and the final section are item 7, and item 8 is satisfied by omission --- the program reads no arguments at all.

Not one of those twenty-two asserts carries a message, and every one of the order book's twenty-eight does. The difference is where a message can live. An application ships an ARC-56 file beside its TEAL, and the compiler writes each assert's sentence into it against a program counter, so a client holding the spec turns `assert failed pc=469` back into `fill exceeds the remainder`. A LogicSig ships TEAL and a source map and nothing else: `puyapy` accepts a message and puts it in a comment, but no artifact carries it to a caller, and what the caller gets is `rejected by logic` plus a counter into a program they may not even hold. Naming the reason means holding that order's own compiled TEAL --- which is what `lsig_refusal_source` in `projects/limit-order-book/scripts/localnet_helpers.py` does for the tests, and what a keeper has to do in production.

Each of the final section's three asserts closes a distinct hole. Checking `app_id` alone would be dangerously incomplete: a delegated LogicSig that binds only the app ID authorizes *any* method of that app, so an attacker could pair Alice's asset transfer with a call to `cancel_order` or `cleanup_expired_order` instead of `fill_order`, and none of the fill-side accounting would run. The second assert pins the ARC-4 method selector (`app_args(0)`) to `fill_order`, forcing every group that spends Alice's tokens through the contract's status, expiry, and price checks. The third pins the first ABI argument (`app_args(1)`) to Alice's specific `ORDER_ID`, so the fill is accounted against *her* order's `filled_amount`/`max_amount` record rather than some other order the attacker controls. Together they make the contract's per-order state authoritative: cumulative fills across every use of the signed LogicSig cannot exceed `max_amount`, and cancellation genuinely revokes the delegation. One caveat from Example 20-7 carries over whole: a selector is a hash of a *signature*, so on an updatable application it binds to whatever `fill_order` comes to mean. The binding is only trustworthy because the order book refuses updates --- the order book's `reject_lifecycle` is this argument's other half.

### What the LogicSig Validates vs What It Delegates

The LogicSig handles **trustless enforcement of the user's trading rules**: correct asset, acceptable price, maximum amount, expiry, and safety. It does NOT handle order tracking, partial fill accounting, or double-fill prevention; that is the smart contract's job.

The split follows from what each program can do. LogicSigs are stateless and cannot read contract state; the smart contract is stateful and maintains the order book.

### One Program per Order

Example 20-8 fixed a LogicSig's parameters at compile time and measured the consequence: one parameter set, one program, one address. An order book mints a new parameter set per order, so this project splits compilation in two:

1. **Build time.** `algokit project run build` compiles the `@logicsig` with no template values. The artifact TEAL carries `TMPL_`-prefixed placeholders --- `TMPL_PRICE_N`, `TMPL_ORDER_ID`, and the rest --- and is the one reusable template.
2. **Order time.** The client substitutes one order's values into that TEAL text --- plain string replacement --- and sends the result to `algod.compile()`, which returns the program bytes and their hash.
3. **Signing.** The trader signs those exact bytes: `LogicSigAccount(program).sign(...)`, Example 20-5's delegation performed once per order.

(PuyaPy will happily substitute at build time instead --- `--template-var PRICE_N=250000` and so on --- which is the right tool when the parameter sets are enumerable in advance. Per-order parameters are not.)

Build it now. The LogicSig is everything this part asked you to write, and the artifact it leaves is what every later step consumes:

```bash
algokit project run build
grep -o 'TMPL_[A-Z_]*' \
  smart_contracts/artifacts/limit_order_lsig/limit_order.teal | sort -u
```

Nine names come back, one per template variable:

```console
TMPL_BUY_ASSET
TMPL_EXPIRY_ROUND
TMPL_GENESIS_HASH
TMPL_MAX_SELL
TMPL_ORDER_BOOK_APP_ID
TMPL_ORDER_ID
TMPL_PRICE_D
TMPL_PRICE_N
TMPL_SELL_ASSET
```

A compiled program with nine holes in it, which is what a template is: the assembler has already rejected everything it can reject, and what is left to supply is one order's numbers. That list is also the client's substitution table. Miss an entry and the TEAL you hand `algod.compile()` still has a word where a number belongs --- `1 error: 6:47: strconv.ParseUint: parsing "TMPL_EXPIRY_ROUND": invalid syntax` --- and no signature is involved in that failure at all.

Table 21-6 follows one order's values from source names to runtime sources.

: Table 21-6. Template variable naming chain at runtime

| Source template variable | TEAL placeholder | Runtime value source |
|--------------------------|------------------|----------------------|
| `ORDER_BOOK_APP_ID` | `TMPL_ORDER_BOOK_APP_ID` | Deployed order book app ID |
| `ORDER_ID` | `TMPL_ORDER_ID` | `next_order_id` read from the book's global state |
| `GENESIS_HASH` | `TMPL_GENESIS_HASH` | `suggested_params().gh`, decoded, as `0x...` (Table 21-4) |
| `SELL_ASSET`, `BUY_ASSET` | `TMPL_SELL_ASSET`, `TMPL_BUY_ASSET` | The pair Alice is trading |
| `PRICE_N`, `PRICE_D` | `TMPL_PRICE_N`, `TMPL_PRICE_D` | Rational price numerator and denominator |
| `MAX_SELL` | `TMPL_MAX_SELL` | Maximum sell amount Alice delegates |
| `EXPIRY_ROUND` | `TMPL_EXPIRY_ROUND` | Last valid round for the order |

Two client-side functions do the order-time half, and the LocalNet walkthrough later in this chapter starts from both. `read_next_order_id` exists because the program binds to an order id the contract has not assigned yet: ids are sequential, so the id the *next* `place_order` call will return is sitting in global state now.

```python
import base64
from pathlib import Path

TEAL_TEMPLATE = Path(
    "smart_contracts/artifacts/limit_order_lsig/limit_order.teal"
)


def read_next_order_id(algorand, app_id: int) -> int:
    """The id the next place_order call will assign."""
    app_info = algorand.client.algod.application_info(app_id)
    for kv in app_info["params"]["global-state"]:
        if base64.b64decode(kv["key"]) == b"next_order_id":
            return kv["value"]["uint"]
    raise LookupError("order book has no next_order_id")


def compile_limit_order(
    *, order_book_app_id: int, order_id: int, genesis_hash: bytes,
    sell_asset: int, buy_asset: int, price_n: int, price_d: int,
    max_sell: int, expiry_round: int,
) -> str:
    """Fill the TEAL template with one order's parameters."""
    teal = TEAL_TEMPLATE.read_text()
    for name, value in {
        "TMPL_ORDER_BOOK_APP_ID": str(order_book_app_id),
        "TMPL_ORDER_ID": str(order_id),
        "TMPL_GENESIS_HASH": "0x" + genesis_hash.hex(),
        "TMPL_SELL_ASSET": str(sell_asset),
        "TMPL_BUY_ASSET": str(buy_asset),
        "TMPL_PRICE_N": str(price_n),
        "TMPL_PRICE_D": str(price_d),
        "TMPL_MAX_SELL": str(max_sell),
        "TMPL_EXPIRY_ROUND": str(expiry_round),
    }.items():
        teal = teal.replace(name, value)
    assert "TMPL_" not in teal, "unreplaced LogicSig template variable"
    return teal
```

Every distinct value set produces distinct program bytes, hence a distinct hash and a distinct signature. `ORDER_ID` is in the program for that reason as much as for the binding: it is a nonce. Two orders with otherwise identical parameters still compile to different programs, so a delegation signed for one can never fill the other.

### A Price the AVM Can Check Without Dividing

A limit price is two integers: `PRICE_N` units of the buy asset per `PRICE_D` units of the sell asset --- Example 13-3's agreed-denominator move, made per-order instead of protocol-wide. Alice's 0.25 ALGO per USDC is `PRICE_N = 250_000` (microAlgo) over `PRICE_D = 1_000_000` (micro-USDC). Neither program ever divides. The check is cross-multiplied ---

```text
buy_amount × PRICE_D ≥ sell_amount × PRICE_N
```

--- so there is no quotient, no remainder, and no rounding winner to pick. What is left to worry about is the products: two uint64 factors can need 128 bits, which is Example 13-4's subject. With 6-decimal tokens and order sizes under 10^12 base units both products stay under 10^18, inside uint64; size past that and the multiplications belong in `mulw`/`BigUInt`, as that example showed.


## Building the Order Book Smart Contract

### The Order Record

Each order lives in [box storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/), keyed by order id, as an `arc4.Struct` --- the same move as Chapter 9's vesting schedules. Every field is fixed-width, so the record encodes to the same 128 bytes every time: 32 for the seller, eight 8-byte integers, and the 32-byte hash of the order's compiled LogicSig. The three event structs are ARC-28 events (Example 8-17's device): keepers and indexers find `NewOrder` by its four-byte log prefix instead of polling boxes.

Add the following to `smart_contracts/limit_order_book/contract.py`:

```python
import typing

from algopy import (
    ARC4Contract, Asset, BoxMap, Bytes, Global, GlobalState,
    TransactionType, Txn, UInt64, arc4, gtxn, itxn,
)

ORDER_ACTIVE = 1
ORDER_FILLED = 2
ORDER_CANCELLED = 3
ORDER_PARTIAL = 4

LsigHash: typing.TypeAlias = arc4.StaticArray[arc4.Byte, typing.Literal[32]]


class OrderInfo(arc4.Struct):
    seller: arc4.Address
    sell_asset: arc4.UInt64
    buy_asset: arc4.UInt64
    price_n: arc4.UInt64
    price_d: arc4.UInt64
    max_amount: arc4.UInt64
    filled_amount: arc4.UInt64
    status: arc4.UInt64
    expiry_round: arc4.UInt64
    lsig_hash: LsigHash


class NewOrder(arc4.Struct):
    order_id: arc4.UInt64
    seller: arc4.Address
    sell_asset: arc4.UInt64
    buy_asset: arc4.UInt64
    price_n: arc4.UInt64
    price_d: arc4.UInt64
    max_amount: arc4.UInt64


class Filled(arc4.Struct):
    order_id: arc4.UInt64
    fill_amount: arc4.UInt64
    total_filled: arc4.UInt64
    keeper: arc4.Address


class Cancelled(arc4.Struct):
    order_id: arc4.UInt64


class LimitOrderBook(ARC4Contract):
    """An immutable order book: no admin, no pause switch, no upgrade path."""

    def __init__(self) -> None:
        self.next_order_id = GlobalState(UInt64(1))
        # Order storage: order_id -> OrderInfo (128 bytes per order)
        self.orders = BoxMap(arc4.UInt64, OrderInfo, key_prefix=b"o_")
```

One global slot, one counter, and nothing else: no admin address, no fee setting, and in particular no `paused` flag. A flag no method can set is not a safety feature, it is a line that reads like one, and an auditor who traces it to nowhere has spent that time on your behalf. The stance is the one `reject_lifecycle` states below: immutable, and therefore adminless. A pause is the lever an operator throws while a replacement is being written, and a contract that can never be replaced has nothing to throw it for. Example 24-7 builds the working switch --- the flag, the method that flips it, and the event that announces the throw --- for a contract whose operator has somewhere to go afterwards.

::: {.note}
**Packed binary storage.** Production Algorand codebases often hand-pack records instead of declaring structs: fixed-width fields concatenated with `op.itob`/`op.concat`, read back by byte offset with `op.extract`, patched in place with `op.replace`. It is C struct packing without a compiler --- every offset is a constant maintained by hand, and a wrong one silently reads one field's bytes as another's. This chapter does not use it: `OrderInfo` encodes to the same 128 bytes while the compiler owns the offsets and catches a reordered field at build time. Recognize the packed idiom when you read it; write `arc4.Struct`.
:::

The `place_order` method registers a new order. The seller calls it after signing the corresponding LogicSig, in a two-transaction group: the box's minimum-balance payment, then the call. Who *sent* that payment is the one question the method deliberately does not ask --- a stranger funding your order's box hurts nobody, and the refund path is pinned to the seller regardless. The 57,700 microAlgo figure is Chapter 5's box formula against this box's exact dimensions: `2,500 + 400 × (10 + 128)` --- a 10-byte name (the `o_` prefix plus an 8-byte id) and the 128-byte record:

```python
    @arc4.abimethod
    def place_order(
        self,
        sell_asset: UInt64,
        buy_asset: UInt64,
        price_n: UInt64,
        price_d: UInt64,
        max_amount: UInt64,
        expiry_round: UInt64,
        lsig_hash: Bytes,
        mbr_payment: gtxn.PaymentTransaction,
    ) -> UInt64:
        """Register a new limit order."""
        assert Global.group_size == UInt64(2), "expected payment + app call"
        assert price_d > UInt64(0), "price denominator must not be zero"
        assert max_amount > UInt64(0), "order size must be above zero"
        assert expiry_round > Global.round, "expiry must be in the future"
        assert lsig_hash.length == UInt64(32), "lsig hash must be 32 bytes"

        # Verify MBR payment for box storage
        # Box key: 10 bytes (prefix + uint64), box value: 128 bytes
        box_cost = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(128))
        assert (
            mbr_payment.receiver == Global.current_application_address
        ), "pay the box deposit to the order book"
        assert mbr_payment.amount == box_cost, "box deposit is 57,700 exactly"

        order_id = self.next_order_id.value
        self.next_order_id.value = order_id + UInt64(1)

        self.orders[arc4.UInt64(order_id)] = OrderInfo(
            seller=arc4.Address(Txn.sender),
            sell_asset=arc4.UInt64(sell_asset),
            buy_asset=arc4.UInt64(buy_asset),
            price_n=arc4.UInt64(price_n),
            price_d=arc4.UInt64(price_d),
            max_amount=arc4.UInt64(max_amount),
            filled_amount=arc4.UInt64(0),
            status=arc4.UInt64(ORDER_ACTIVE),
            expiry_round=arc4.UInt64(expiry_round),
            lsig_hash=LsigHash.from_bytes(lsig_hash),
        )

        # Announce the order so keepers can discover it
        arc4.emit(NewOrder(
            order_id=arc4.UInt64(order_id),
            seller=arc4.Address(Txn.sender),
            sell_asset=arc4.UInt64(sell_asset),
            buy_asset=arc4.UInt64(buy_asset),
            price_n=arc4.UInt64(price_n),
            price_d=arc4.UInt64(price_d),
            max_amount=arc4.UInt64(max_amount),
        ))

        return order_id
```

Build again before writing anything else. Four methods are still to come and the contract compiles without them:

```bash
algokit project run build
python - <<'PY'
import json, pathlib
spec = json.loads(pathlib.Path(
    "smart_contracts/artifacts/limit_order_book/LimitOrderBook.arc56.json"
).read_text())
print(spec["state"]["schema"]["global"])
print([m["name"] for m in spec["methods"]])
PY
```

```console
{'ints': 1, 'bytes': 0}
['place_order']
```

One method so far, and one global slot for the whole application. The second line will grow with every method you add; the first will not, and cannot --- this contract refuses updates, so the schema printed here is the schema it dies with. If that is a surprise, it is Chapter 4's rule arriving where it costs money.

The deposit is checked with `==` rather than `>=`, which is the question Chapter 19's Exercise 2 left open: when is the loose form safe? Only when the contract can do something with the excess. This one cannot. It is immutable, it has no method that pays out anything but the box formula's own 57,700, and `cleanup_expired_order` refunds that figure rather than whatever arrived --- so a generous client's extra microAlgo sits in the application account forever, visible to everyone and spendable by nobody. `==` converts that into a refusal the client can act on before any money moves.

The `fill_order` method validates the 3-transaction atomic group, checks the order's state and price, and updates the fill status. The expected group structure is `[0]` keeper's buy-side payment to the seller, `[1]` seller's LogicSig-authorized asset transfer, `[2]` this app call.

**Stage 1: load the order.** The group shape is pinned and the record is read out of its box. `.copy()` is Chapter 9's rule --- box storage hands back a reference to encoded data --- and, as in that chapter's `claim`, the ARC-4 fields arrive encoded, so the arithmetic below opens with conversions:

```python
    @arc4.abimethod
    def fill_order(
        self,
        order_id: UInt64,
        fill_amount: UInt64,
        sell_txn: gtxn.AssetTransferTransaction,
    ) -> None:
        """Execute a fill against an open order."""
        assert Global.group_size == UInt64(3), "expected buy, sell, this call"

        order_key = arc4.UInt64(order_id)
        assert order_key in self.orders, "no order with that id"
        # .copy() is required: box storage returns a reference to
        # encoded data.
        order = self.orders[order_key].copy()
        seller = order.seller.native
```

**Stage 2: order state validation.** Before processing the fill, verify the order is still active (not cancelled or fully filled), has not expired, and the fill amount would not exceed the remaining capacity:

```python
        # Validate order state
        status = order.status.as_uint64()
        assert status == UInt64(ORDER_ACTIVE) or status == UInt64(
            ORDER_PARTIAL
        ), "order is cancelled or already filled"
        assert Global.round <= order.expiry_round.as_uint64(), "order expired"
        assert fill_amount > UInt64(0), "fill amount must be above zero"
        filled = order.filled_amount.as_uint64()
        max_amount = order.max_amount.as_uint64()
        assert filled + fill_amount <= max_amount, "fill exceeds the remainder"
```

**Stage 3: transaction validation and price check.** The contract verifies both sides of the trade. The sell-side transaction (position `[1]` in the group) is the LogicSig-authorized asset transfer; the contract confirms it matches the order's parameters. The buy-side transaction (position `[0]`) is the keeper's payment to the seller. The price check uses cross-multiplication, exactly as the LogicSig's does:

```python
        # Validate the sell-side transaction (LogicSig authorized)
        sell_asset = Asset(order.sell_asset.as_uint64())
        assert sell_txn.xfer_asset == sell_asset, "wrong asset on the sell side"
        assert sell_txn.asset_amount == fill_amount, "sell side != fill_amount"
        assert sell_txn.sender == seller, "sell side must come from the seller"

        # Validate the buy-side transaction
        buy_txn = gtxn.Transaction(0)
        buy_asset = order.buy_asset.as_uint64()
        if buy_asset == UInt64(0):
            buy_txn_amount = buy_txn.amount
            assert buy_txn.type == TransactionType.Payment, "buy side not a pay"
            assert buy_txn.receiver == seller, "buy side must pay the seller"
        else:
            buy_txn_amount = buy_txn.asset_amount
            assert (
                buy_txn.type == TransactionType.AssetTransfer
            ), "buy side must be an asset transfer for an ASA order"
            assert buy_txn.asset_receiver == seller, "buy side must pay seller"
            assert buy_txn.xfer_asset == Asset(
                buy_asset
            ), "wrong asset on the buy side"

        # Price verification (cross-multiply to avoid division)
        price_n = order.price_n.as_uint64()
        price_d = order.price_d.as_uint64()
        assert (
            buy_txn_amount * price_d >= fill_amount * price_n
        ), "buy side is below the order's limit price"
```

**Stage 4: state update and event.** With all validations passed, the contract updates the order's filled amount and status --- two field assignments and one box write --- then emits `Filled` for keepers and indexers to track:

```python
        # Update filled amount and status
        new_filled = filled + fill_amount
        new_status = (
            UInt64(ORDER_FILLED) if new_filled == max_amount
            else UInt64(ORDER_PARTIAL)
        )
        order.filled_amount = arc4.UInt64(new_filled)
        order.status = arc4.UInt64(new_status)
        self.orders[order_key] = order.copy()

        arc4.emit(Filled(
            order_id=arc4.UInt64(order_id),
            fill_amount=arc4.UInt64(fill_amount),
            total_filled=arc4.UInt64(new_filled),
            keeper=arc4.Address(Txn.sender),
        ))
```

The `cancel_order` method lets the seller cancel their open order. Only the original seller can cancel, and the order must still be active or partially filled. The `cleanup_expired_order` method allows anyone to clean up an expired order, deleting its box to free MBR and refunding the seller --- the same 57,700 microAlgo the seller's `place_order` group paid in:

```python
    @arc4.abimethod
    def cancel_order(self, order_id: UInt64) -> None:
        """Cancel an open order. Only the seller can cancel."""
        order_key = arc4.UInt64(order_id)
        assert order_key in self.orders, "no order with that id"
        order = self.orders[order_key].copy()

        assert Txn.sender == order.seller.native, "only the seller may cancel"

        status = order.status.as_uint64()
        assert status == UInt64(ORDER_ACTIVE) or status == UInt64(
            ORDER_PARTIAL
        ), "order is cancelled or already filled"

        order.status = arc4.UInt64(ORDER_CANCELLED)
        self.orders[order_key] = order.copy()
        arc4.emit(Cancelled(order_id=arc4.UInt64(order_id)))

    @arc4.abimethod
    def cleanup_expired_order(self, order_id: UInt64) -> None:
        """Anyone can clean up an expired order and free the MBR."""
        order_key = arc4.UInt64(order_id)
        assert order_key in self.orders, "no order with that id"
        order = self.orders[order_key].copy()

        assert (
            Global.round > order.expiry_round.as_uint64()
        ), "order has not expired yet"

        seller = order.seller.native
        del self.orders[order_key]

        box_cost = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(128))
        itxn.Payment(
            receiver=seller,
            amount=box_cost,
            fee=UInt64(0),
        ).submit()

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "this order book is immutable"
```

`reject_lifecycle` is not boilerplate here; it is half of the LogicSig's security argument. The order program pins `fill_order`'s selector, and a selector on an updatable application binds to whatever the method comes to mean --- so the delegations traders sign are only as trustworthy as this refusal to ever change what `fill_order` means.


## The Keeper Bot: Executing Orders Off-Chain

### Keeper Architecture

A keeper is an off-chain service that monitors the order book and executes fills when profitable. Keepers are permissionless: anyone can run one. They earn profit from the spread between the order's price and the market price (or from explicit keeper fees built into the protocol). The keeper reads state via the [algod REST API](https://dev.algorand.co/reference/rest-api/overview/) and submits [atomic groups](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/).

A keeper is four jobs in a loop: discover orders, price them, assemble fills, submit. Only the first touches on-chain data structures; the rest is ordinary trading-bot judgment. The discovery half is below, complete and runnable as written; the judgment half lives in the shipped keeper at `projects/limit-order-book/scripts/keeper.py`.

### Order Discovery, Complete

`unpack_order` is the client-side mirror of `OrderInfo`. An all-static ARC-4 struct encodes to its fields laid end to end, so the layout is knowable from the declaration: 32 bytes of seller, eight 8-byte big-endian integers, 32 bytes of LogicSig hash.

```python
# The on-chain half of a keeper: find every fillable order.
import base64

from algosdk import encoding
from algosdk.v2client import algod

ORDER_ACTIVE, ORDER_FILLED, ORDER_CANCELLED, ORDER_PARTIAL = 1, 2, 3, 4

U64_FIELDS = ("sell_asset", "buy_asset", "price_n", "price_d",
              "max_amount", "filled_amount", "status", "expiry_round")


def unpack_order(box_name: bytes, raw: bytes) -> dict:
    """Decode one order box: OrderInfo's fields, laid end to end."""
    order = {
        "id": int.from_bytes(box_name[2:], "big"),  # after the b"o_" prefix
        "seller": encoding.encode_address(raw[0:32]),
        "lsig_hash": raw[96:128],
        "box_key": box_name,
    }
    for i, field in enumerate(U64_FIELDS):
        start = 32 + 8 * i
        order[field] = int.from_bytes(raw[start:start + 8], "big")
    return order


def scan_open_orders(client: algod.AlgodClient, app_id: int) -> list[dict]:
    """Read every order box and keep the fillable ones."""
    orders = []
    for box in client.application_boxes(app_id)["boxes"]:
        # algod returns box names base64-encoded; pass the encoded form
        # straight back and the lookup finds no box, hence no orders.
        name = base64.b64decode(box["name"])
        raw = base64.b64decode(
            client.application_box_by_name(app_id, name)["value"]
        )
        order = unpack_order(name, raw)
        if order["status"] in (ORDER_ACTIVE, ORDER_PARTIAL):
            orders.append(order)
    return orders
```

The status filter admits `ORDER_PARTIAL` deliberately: a half-filled order's remainder is still for sale, and a keeper that filters for `ORDER_ACTIVE` alone leaves money on the table.

The shipped keeper wraps these two functions in the three judgment jobs, each short:

- **Pricing.** `is_profitable` compares the order's price against the market's. The keeper buys at the order price and sells into the market, so it wants the market *above* the order --- write the comparison backwards and the bot declines every profitable fill and takes every losing one, and no happy-path test notices.
- **Assembly.** `execute_fill` builds exactly the three-transaction group the LocalNet walkthrough later in this chapter builds: `AtomicTransactionComposer`, the signed LogicSig authorizing index 1, fees pooled onto the app call, the fill sized to the order's remainder.
- **The loop.** Poll `scan_open_orders` every block (under three seconds), fill whatever profits.

::: {.note}
**Design decision: separate enforcement from coordination.** LogicSigs enforce rules; they cannot be cheated. Smart contracts coordinate; they track shared state. When I see a system that needs both trustless rules and shared mutable state, this hybrid pattern is my first instinct: the LogicSig guarantees Alice's price is honored, the smart contract guarantees the order book is consistent, and the order program's binding welds the two halves together.
:::

### Where Do Keepers Get the Signed LogicSigs?

The signed LogicSig (Alice's signed delegation) must be shared with keepers somehow. Several approaches:

**Off-chain relay (simplest):** The frontend posts the signed LogicSig to a centralized API or peer-to-peer network. Keepers poll this relay for new orders. As of this writing, this is how most Algorand DEXs with limit orders work. The relay is a convenience layer; it doesn't affect security, because the LogicSig itself enforces all trading rules.

**On-chain storage:** Store the signed LogicSig in box storage. This makes the system fully on-chain but expensive: a LogicSig's free size is 1,000 bytes per transaction (up to 16,000 with a per-byte surcharge), plus the signature. The MBR for a 1,100-byte box is `2,500 + 400 × (10 + 1,100) = 446,500 microAlgo` ≈ 0.45 Algo per order.

**Hybrid (recommended):** Store only the LogicSig program hash on-chain (32 bytes, stored in the order data). Distribute the actual signed LogicSig off-chain. Keepers verify the hash matches before using it. This gives you on-chain order discovery with off-chain LogicSig distribution.

Compute that hash with `algosdk.logic.address(program)`.

::: {.gotcha #logicsigaccount-address-is-the-delegator topic="LogicSigs" title="`LogicSigAccount.address()` on a signed delegation returns the delegator, not the program hash"}
Once a delegation is signed, `LogicSigAccount.address()` reports the *delegating account's* address; the program hash comes from `algosdk.logic.address(program)`. Code that confuses them compiles and runs: a keeper checking an order's stored hash against `address()` compares an account against a program hash, silently declines every valid order, and reports nothing wrong.
:::

### Keeper Incentives and MEV

Keepers profit from the spread. If Alice's order sells USDC at 0.25 ALGO/USDC and the market price is 0.27 ALGO/USDC, the keeper buys USDC from Alice at 0.25 and sells on the AMM at 0.27, pocketing 0.02 ALGO per USDC.

On Algorand, keeper competition is a **latency race** rather than a fee auction: there is no priority gas auction like Ethereum's, and most of the time the first keeper to reach a proposer wins. The nuance is the node's own queue --- the transaction pool orders candidates by fee-per-byte, so under load a higher fee does break ties. Keeper infrastructure is simpler than Ethereum's, but it rewards low-latency connections to relay nodes first and fee headroom second.

To prevent keeper-vs-keeper waste (multiple keepers submitting fills for the same order simultaneously), the order book contract's `fill_order` method is the arbiter: only the first valid fill succeeds, and subsequent attempts fail because the order status has changed.

## Running the Limit Order System on LocalNet

The full lifecycle on LocalNet has three steps: deploy the order book, place an order, and fill it the way a keeper would.

First, compile both programs:

```bash
algokit project run build
```

Save the client-side walkthrough as a script (e.g., `test_deploy.py` in your project root). It starts with the LogicSig build's two client-side functions --- `read_next_order_id` and `compile_limit_order` --- and continues with the following, which deploys the order book, creates a test token, and funds Alice:

```python
from pathlib import Path
import algokit_utils
from algosdk import encoding, transaction
import base64

algorand = algokit_utils.AlgorandClient.default_localnet()
admin = algorand.account.localnet_dispenser()

# Deploy the order book
spec_path = Path(
    "smart_contracts/artifacts/limit_order_book/LimitOrderBook.arc56.json"
)
factory = algorand.client.get_app_factory(
    app_spec=spec_path.read_text(),
    default_sender=admin.address,
)
book_client, deploy_result = factory.deploy()
print(f"Order Book App ID: {book_client.app_id}")

# Seed the app account: its own 100,000 microAlgo base minimum,
# plus headroom. Box minimum balance is not part of this payment;
# it arrives later, inside each order's own group.
algorand.send.payment(
    algokit_utils.PaymentParams(
        sender=admin.address,
        receiver=book_client.app_address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(200_000),
    )
)

# A test USDC (6 decimals), and Alice funded with Algo and tokens
usdc_id = algorand.send.asset_create(
    algokit_utils.AssetCreateParams(
        sender=admin.address, total=10_000_000_000, decimals=6,
        asset_name="Test USDC", unit_name="USDC",
    )
).asset_id
alice = algorand.account.random()
algorand.send.payment(algokit_utils.PaymentParams(
    sender=admin.address, receiver=alice.address,
    amount=algokit_utils.AlgoAmount.from_micro_algo(10_000_000),
))
algorand.send.asset_transfer(algokit_utils.AssetTransferParams(
    sender=alice.address, receiver=alice.address,
    asset_id=usdc_id, amount=0,        # opt in first (Chapter 7's rule)
))
algorand.send.asset_transfer(algokit_utils.AssetTransferParams(
    sender=admin.address, receiver=alice.address,
    asset_id=usdc_id, amount=500_000_000,
))
```

The application account's own 100,000 microAlgo base minimum has to exist before the first box can be created; without the seed payment, the first `place_order` fails with `account <address> balance <n> below min <m>`. Each order then carries its own 57,700 microAlgo inside the `place_order` group, and `cleanup_expired_order`'s refund hands the same amount back to the seller, so the account's balance rides at base plus one box deposit per resting order.

Next, compile Alice's limit order LogicSig against the id her order is about to receive, have her sign (delegate) it, and place the order:

```python
# Compile Alice's order: sell 500 USDC for ALGO at 0.25 ALGO/USDC
genesis_hash = base64.b64decode(
    algorand.client.algod.suggested_params().gh
)
expiry_round = algorand.client.algod.status()["last-round"] + 5000
order_id = read_next_order_id(algorand, book_client.app_id)
lsig_teal = compile_limit_order(
    order_book_app_id=book_client.app_id,
    order_id=order_id,
    genesis_hash=genesis_hash,
    sell_asset=usdc_id, buy_asset=0,
    price_n=250_000, price_d=1_000_000,
    max_sell=500_000_000,
    expiry_round=expiry_round,
)
compiled = algorand.client.algod.compile(lsig_teal)
program = base64.b64decode(compiled["result"])
lsig = transaction.LogicSigAccount(program)
lsig.sign(alice.private_key)  # Alice delegates

# Place the order: box MBR payment + app call, one group
order_result = book_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="place_order",
        args=[usdc_id, 0, 250_000, 1_000_000, 500_000_000,
              expiry_round,
              encoding.decode_address(compiled["hash"]),
              algokit_utils.PaymentParams(
                  sender=alice.address,
                  receiver=book_client.app_address,
                  # box MBR: 2,500 + 400 x (10 + 128)
                  amount=algokit_utils.AlgoAmount.from_micro_algo(57_700),
              )],
        sender=alice.address,
        box_references=[b"o_" + order_id.to_bytes(8, "big")],
    )
)
assert order_result.abi_return == order_id, "an order landed in between"
print(f"Order placed: ID {order_result.abi_return}")
```

The closing assert is Table 21-1's second checkpoint. The delegation was compiled against a *predicted* id; if another order reached the book first, Alice's program is bound to an id her order does not have, and the only fix is to recompile and re-sign.

::: {.note}
**ARC-4 method signatures.** When constructing transactions manually (without a typed client), you need the exact method signatures for `Method.from_signature()` or `AtomicTransactionComposer`. These are derived from the contract's method definitions and can also be found in the generated `.arc56.json` file:

```text
"place_order(uint64,uint64,uint64,uint64,uint64,uint64,byte[],pay)uint64"
"fill_order(uint64,uint64,axfer)void"
"cancel_order(uint64)void"
"cleanup_expired_order(uint64)void"
```
:::

Finally, a keeper fills the order by constructing the 3-transaction atomic group: buy-side payment, LogicSig-authorized sell-side transfer, and order book app call. Because `fill_order` has signature `fill_order(uint64,uint64,axfer)void`, the sell-side transfer is a **transaction argument** (not an `app_args` value) and must be passed via the `AtomicTransactionComposer`. This is the one walkthrough in the book assembled with the raw SDK composer rather than a typed client: one group member is signed by a program and another takes it as an argument, which is field-level control the typed wrappers are built to hide:

```python
keeper = algorand.account.random()
algorand.send.payment(algokit_utils.PaymentParams(
    sender=admin.address, receiver=keeper.address,
    amount=algokit_utils.AlgoAmount.from_micro_algo(200_000_000),
))
# Keeper must opt into the sell asset to receive it
algorand.send.asset_opt_in(
    algokit_utils.AssetOptInParams(
        sender=keeper.address, asset_id=usdc_id
    )
)

fill_amount = 500_000_000  # Fill the full order
buy_amount = 125_000_000   # 0.25 ALGO per USDC x 500 USDC = 125 ALGO

from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer, TransactionWithSigner,
    AccountTransactionSigner, LogicSigTransactionSigner,
)
from algosdk.abi import Method

atc = AtomicTransactionComposer()
sp = algorand.client.algod.suggested_params()
sp.last = min(sp.last, expiry_round)  # Cap to LogicSig expiry
sp.fee = 0
sp.flat_fee = True  # Fee pooling: app call covers all fees

# [0] Keeper's buy-side payment (precedes the ATC-managed txns)
buy_txn = transaction.PaymentTxn(
    sender=keeper.address, sp=sp,
    receiver=alice.address, amt=buy_amount,
)
atc.add_transaction(TransactionWithSigner(
    buy_txn, AccountTransactionSigner(keeper.private_key),
))

# [1] LogicSig-authorized sell-side asset transfer, passed as
# the `axfer` transaction argument to fill_order
sell_txn = transaction.AssetTransferTxn(
    sender=alice.address, sp=sp,
    receiver=keeper.address, amt=fill_amount, index=usdc_id,
)
sell_signer = LogicSigTransactionSigner(lsig)

# [2] ARC-4 app call --- the ATC encodes order_id and fill_amount
# as ABI arguments and attaches sell_txn as the txn reference
sp_fee = algorand.client.algod.suggested_params()
sp_fee.fee = 3000        # three transactions, no inner ones
sp_fee.flat_fee = True

fill_method = Method.from_signature(
    "fill_order(uint64,uint64,axfer)void"
)
atc.add_method_call(
    app_id=book_client.app_id,
    method=fill_method,
    sender=keeper.address,
    sp=sp_fee,
    signer=AccountTransactionSigner(keeper.private_key),
    method_args=[
        order_id,
        fill_amount,
        TransactionWithSigner(sell_txn, sell_signer),
    ],
    foreign_assets=[usdc_id],
    accounts=[alice.address],
    boxes=[(book_client.app_id,
            b"o_" + order_id.to_bytes(8, "big"))],
)

atc.execute(algorand.client.algod, wait_rounds=4)
print("Order filled! Alice received ALGO, keeper received USDC.")
```

**The fill group costs 3,000 microAlgo and the keeper pays all of it.** Three transactions, one minimum fee each; none of the three makes an inner transaction, so nothing is added on top --- compare `cleanup_expired_order`, one call that makes one inner payment, which needs 2,000. The buy side and the sell side are built with `fee = 0` and the app call carries 3,000, which the group's shared fee credit accepts. That is not only tidiness: a fee is paid by the transaction's own sender, so a non-zero fee on index `[1]` would be *Alice* paying for a stranger's trade. Her program's `Txn.fee <= UInt64(10_000)` is the cap on how much a careless keeper can make that cost her.

If the group is rejected before the LogicSig program runs at all, check that the template variables you compiled match the parameters Alice signed over exactly. Her signature covers the program *bytes*, so a mismatch in any field produces a different program and her signature no longer validates it: the failure is in signature verification, not in the program's logic. If the failure comes from the program and mentions `box read budget (2048) exceeded`, add box references to the app call transaction. That budget is charged before the program runs, against the full stored size of every box referenced, whether you read it or not.

::: {.gotcha #lsig-last-valid-vs-expiry topic="LogicSigs" title="suggested_params() can hand you a last_valid past the LogicSig's expiry"}
A LogicSig that bounds itself with `Txn.last_valid <= EXPIRY` rejects any transaction `suggested_params()` dated past that round --- the default validity window knows nothing about the program's own deadline. Cap it before building: `sp.last = min(sp.last, expiry_round)`. Here, the sell side of every fill group needs the cap or the order program refuses it near its expiry.
:::

The place-order side of the flow carries a second encoding pitfall.

::: {.gotcha #arc4-encoding-of-byte-args topic="Compilation, tooling, and shipping" title="byte[] application arguments need their ARC-4 length prefix"}
A `byte[]` ABI argument must carry its two-byte ARC-4 length prefix; a raw 32-byte value is not one, and the router mis-reads or refuses it. Build calls through `AtomicTransactionComposer`, `algosdk.abi`, or a typed client from `algokit generate client` --- all of which write the prefix; hand-packed `app_args` do not. `place_order`'s 32-byte `lsig_hash` is where this bites here.
:::

This end-to-end flow (place order, compile LogicSig, delegate, fill via atomic group) is the pattern every Algorand limit order system follows.

## Security Deep Dive

### Attack: LogicSig Replay Across Orders and Methods

**Risk:** A signed delegated LogicSig is a bearer authorization: anyone holding it can submit it as many times, and in as many contexts, as the program itself allows. Bind only the app ID and the delegation authorizes *any* method of the book, replayable until expiry, `MAX_SELL` at a time --- the contract's `filled_amount` accounting never runs, because nothing forces the group through `fill_order`.

**Mitigation:** The order program's binding argument. Every group that spends Alice's tokens must contain `fill_order` for her `ORDER_ID`, so the contract's per-order accounting is authoritative and cumulative fills cannot exceed `max_amount`. `ORDER_ID` is also the nonce that separates *orders*: two delegations with otherwise identical parameters are different programs, so neither's signature validates the other.

### Attack: Keeper Front-Running

**Risk:** Keeper A sees Keeper B's pending fill transaction in the mempool and submits their own fill first.

**Mitigation:** This is inherent to permissionless keeper systems and acceptable: it is how competitive market-making works. The seller (Alice) does not care which keeper fills her order, because she gets the same price regardless, and competition between keepers makes fills happen quickly.

### Attack: Stale LogicSig After Cancellation

**Risk:** Alice cancels her order, but keepers still hold her signed program --- still a valid signature over a program that still approves.

**Mitigation:** `fill_order` refuses any status but active or partial, and the order program's binding leaves the delegation no path around that read. That is the general trick, worth stating as a rule: **on-chain state can revoke a delegated LogicSig only if the program forces every use through the method that reads that state.** Expiry aside (Example 20-3's last guard), it is the only revocation a delegation ever has. It is also Chapter 20's Exercise 5 answered: "at most once, ever" needs state no LogicSig can hold, and this is where that state lives and how the program is made to read it.

### Attack: Price Manipulation via Group Restructuring

**Risk:** An attacker constructs a group that satisfies the LogicSig but with a different intent than expected.

**Mitigation:** The LogicSig explicitly validates the group size (3), its own position in the group (index 1), the buy-side transaction's receiver (must be the seller), and the app call's application ID, method selector, and order ID. An attacker cannot insert additional transactions, rearrange the group, or substitute a different method or order without violating these checks.

### Attack: LogicSig Args Manipulation

**Risk:** LogicSig arguments are unsigned; the submitter chooses them (Example 20-10).

**Mitigation:** The programs in this project read none. Every order parameter is a template variable, baked into the bytes Alice signed, and changing one changes the program hash her signature no longer matches.

### Attack: Cross-Network Replay

**Risk:** A signed LogicSig validates on every Algorand network, and app or asset ids do not distinguish networks.

**Mitigation:** Checklist item 6: the program asserts `Global.genesis_hash == GENESIS_HASH`. A LogicSig compiled for LocalNet or TestNet fails on MainNet, and vice versa, whatever coincidental ids exist on the other network.


## What the Test Suite Pins Down

You already ran the suite in Run It First: `algokit project run test`, against the same LocalNet the workflow used. It lives in `projects/limit-order-book/tests/`, and its fixtures are the walkthrough's own pieces --- deploy the book, create the test ASA, fund the accounts, compile and sign a per-order LogicSig, and assemble the same three-transaction fill group with `AtomicTransactionComposer`. Table 21-7 is the contract between the suite and this chapter. Chapter 8's rule for negative tests applies to every failure row: each one asserts the *specific* refusal, not merely that something failed.

: Table 21-7. What each test in the suite proves

| Test | Scenario | The assertion that matters |
|------|----------|----------------------------|
| `test_full_order_lifecycle` | Place a 500-USDC order, fill it whole | Alice +125 ALGO, keeper +500 USDC, status `ORDER_FILLED` |
| `test_partial_fill` | Fill 400, then the remaining 600 of a 1,000 order | `ORDER_PARTIAL` and `filled_amount` accumulate between fills |
| `test_cancel_prevents_fill` | Cancel, then attempt a fill | Refused by `fill_order`'s status check --- the keeper's still-valid signature does not help |
| `test_expired_order_rejected` | Advance past expiry, attempt a fill | Refused by the LogicSig's own `last_valid` bound --- the app's `expiry_round` twin is defense in depth that a well-formed order program can never reach |
| `test_overfill_rejected` | Fill 400, then 200, against a 500-unit order | The second fill is refused by `filled + fill_amount <= max_amount`: `MAX_SELL` bounds one transfer, the box record bounds their sum |
| `test_wrong_price_rejected` | Keeper pays under the limit price | Refused by the LogicSig's cross-multiplication: `rejected by logic` |
| `test_safety_checks` | Sell transaction carrying `asset_close_to` or `rekey_to` (`close_remainder_to` is payment-only and cannot appear on an asset transfer) | Refused by the zero-address pins before anything else is consulted |
| `test_wrong_genesis_hash_rejected` | Program compiled against another network's hash | Refused by the `Global.genesis_hash` assert on LocalNet |
| `test_cleanup_expired_order` | Clean up after expiry | Box deleted; 57,700 microAlgo back to the seller |


## Composing with the AMM from Chapter 14

### The Real Power: Keepers Routing Through Your AMM

The limit order system becomes far more useful when keepers can atomically fill limit orders using the AMM from Chapter 14 as a liquidity source. The keeper does not need to hold inventory: they borrow from the AMM in the same [atomic group](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/).

```text
Atomic Group (5 transactions):
[0] Keeper → Alice: 125 ALGO (keeper's payment)
[1] Alice → Keeper: 500 USDC (LogicSig: limit order)
[2] Keeper → OrderBook: App call to fill_order
[3] Keeper → AMM Pool: 500 USDC (input to swap)
[4] Keeper → AMM Pool: App call to swap (receive ~135 ALGO)
```

The keeper receives ~135 ALGO from the AMM swap but only pays 125 ALGO to Alice, pocketing ~10 ALGO profit (minus fees). This is an atomic arbitrage: if any transaction fails, none execute, and the keeper takes zero inventory risk.

A limit order fill plus an AMM swap in a single atomic group is how professional Algorand DEX aggregators work. The keeper scans for price discrepancies between limit orders and AMM pools, and captures the spread.

**Group size constraint:** Algorand allows 16 transactions per group. A fill + AMM swap uses 5 transactions minimum. More complex multi-hop routes (fill → swap A/B → swap B/C) use more. Plan your group layout carefully.

### When the Contract Should Take a Side Itself

The keeper coordinates the two protocols *externally*: it assembles the group, so it is trusted with nothing but its own money. Chapter 15 is the toolkit for moving that coordination *inside* a contract, and none of it changes here. The order book could read the AMM's reserves without calling it --- Example 15-8 pointed at the pool's `reserve_a`/`reserve_b` --- and refuse fills that undercut the pool price; it could swap inventory itself through an inner application call (Example 15-4's signature-string form), budgeted and depth-bounded exactly as Example 15-7 measured. This chapter keeps the contract neutral and the routing in the keeper: the book's job is custody of *orders*, and every capability it grows is surface a bug can grow in too.

## Exercises

1. **(Apply)** Modify the LogicSig to support "buy limit" orders (the user wants to buy a specific ASA when the price drops below a threshold) instead of only sell orders. What fields in the LogicSig validation logic need to change?

2. **(Analyze)** Two keepers submit fills for the same 500-unit order in the same round, one for 300 and one for 400. Trace both groups at the box level: what each one reads from the order's box, which read refuses the loser and with which assertion, whether that refusal comes from the LogicSig or the contract, and what the attempt costs the losing keeper.

3. **(Evaluate)** Argue the order book's central choice in both directions: escrowed (deposits held by the contract, fills paid out by inner transactions) against delegated (this chapter's design). Judge them on capital efficiency while an order rests, how revocation works and how fast it takes effect, the blast radius of one missing guard, and what each costs a market maker running hundreds of orders. Then name the evidence that would flip your recommendation.

4. **(Create)** Design a "stop-loss" order type where Alice's tokens are sold if the AMM price drops below a threshold. What changes to the LogicSig and order book contract are needed? How does the keeper determine when to trigger the stop-loss?

5. **(Create)** Design an order that survives a contract migration: Alice signs once, and her order is still fillable after the order book is replaced by a V2 at a new application id. Work out what the LogicSig would have to bind to instead of `ORDER_BOOK_APP_ID`, and what checks that unbinding costs her. This chapter's own argument stands in your way --- the selector binding is only trustworthy because the book refuses updates --- so state precisely what you gave up to get migration, and whether you would sign such an order yourself.

## Before You Continue

You should be able to check off all five of these:

- [ ] I can say why this order book delegates instead of escrowing, and name the price that choice carries
- [ ] I can recite the eight-item checklist and point to the line in the order program that satisfies each item
- [ ] I can explain how cancellation actually stops fills, given that Alice's signature remains valid forever
- [ ] I can trace the three-transaction fill group and say what the LogicSig checks, what the contract checks, and why neither list makes the other redundant
- [ ] I can compile one program per order and say why `ORDER_ID` makes each delegation a nonce

If any of these are unclear, revisit the relevant part of this chapter --- or Chapter 20, if the trouble is with the LogicSig fundamentals themselves.

## Mastery Checkpoint
That is the end of Part V. The checklist above asks whether you followed the chapters. The Mastery Checkpoint printed on the next page asks something harder: whether you can build a thing this part did not show you. It is a small program with a stated acceptance test, and a fallback if you stall.
