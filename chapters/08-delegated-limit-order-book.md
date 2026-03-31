\newpage

\part{Logic Signatures and Stateless Programs}

Part III introduces Algorand's second execution model --- Logic Signatures --- and demonstrates the hybrid stateful/stateless architecture that most production DeFi protocols use. You will build a delegated limit order book where stateless LogicSig programs encode per-user trading rules and keeper bots execute them permissionlessly.

# Delegated Limit Order Book with LogicSig Agents

**Building an on-chain limit order system where users encode trading rules as Logic Signatures and market-making bots ("keepers") execute them against AMM pools --- bridging the stateful smart contract world from Project 2 into Algorand's stateless smart signature layer.**

> **Important:** This chapter is primarily for informational purposes. The Algorand developer community strongly recommends modern stateful smart contracts for almost all use cases. Logic Signatures are extremely prone to security vulnerabilities --- every missing check (close-to, rekey-to, fee caps, expiration, group validation) is directly exploitable, and the attack surface is large. If you are building a new application, you almost certainly want a stateful contract, not a LogicSig. This chapter exists so you understand how LogicSigs work and can recognize them in production codebases, but you should default to stateful contracts unless you have a specific, well-justified reason to use LogicSigs.

This project introduces the other half of Algorand's programmable layer: **Logic Signatures (LogicSigs)**. Where the AMM chapter used stateful smart contracts exclusively, this project demonstrates the hybrid pattern that some production Algorand DeFi protocols use --- a stateful order book contract coordinates state, while stateless LogicSig programs encode per-user trading rules that keepers can execute permissionlessly.

The end result is a system where Alice says "sell up to 500 USDC for ALGO at a price of 0.25 ALGO per USDC, expiring in 24 hours" by signing a LogicSig program encoding those rules, and any keeper bot can fill that order by submitting the right atomic group --- with the LogicSig validating that the trade meets Alice's conditions.

### Project Setup

Scaffold a new project for this chapter. The template creates a `hello_world/` contract directory which we rename. This project has two separate compilable components --- the order book contract and the LogicSig --- so create a second directory after renaming:

```bash
algokit init -t python --name limit-order-book
cd limit-order-book
algokit project bootstrap all
mv smart_contracts/hello_world smart_contracts/limit_order_book
mkdir smart_contracts/limit_order_lsig
```

The contract goes in `smart_contracts/limit_order_book/contract.py` and the LogicSig in `smart_contracts/limit_order_lsig/contract.py`. Delete the template-generated `deploy_config.py` in `smart_contracts/limit_order_book/` --- it references the old `HelloWorld` contract.


## Part 1: Logic Signatures --- Algorand's Stateless Authorization Layer

### What LogicSigs Are (and Are Not)

Every Algorand transaction needs authorization --- proof that the sender approves the transaction. Normally, this is an Ed25519 private key signature. A [Logic Signature](https://dev.algorand.co/concepts/smart-contracts/logic-sigs/) replaces that signature with a TEAL program. When the transaction is submitted, the AVM executes the program. If it returns true, the transaction is authorized. If it returns false or fails, the transaction is rejected.

LogicSigs are **stateless**: they cannot read or write global state, local state, or box storage. They cannot issue inner transactions. They cannot create assets. They are pure validators --- they inspect the transaction they're attached to (and the other transactions in the group) and render a yes/no verdict.

In Algorand Python, a LogicSig is a decorated function. This is an illustrative example, not part of the project code:

```python
from algopy import logicsig, Txn, Global, UInt64

@logicsig
def always_approve() -> bool:
    """DANGEROUS: approves any transaction. Never use this."""
    return True
```

The `@logicsig` decorator tells the PuyaPy compiler to produce a smart signature program instead of a smart contract. The function takes no arguments and returns `bool` or `UInt64`. A truthy return authorizes the transaction.

### The Two Modes: Contract Account vs Delegated Signature

**Mode 1 --- Contract account:** When no one signs the LogicSig, its program hash becomes a deterministic Algorand address: `SHA512_256("Program" || program_bytes)`. This address can hold Algos and ASAs. The program logic is the sole authority over outgoing transactions. No private key exists. This is an illustrative example, not part of the project code:

```python
@logicsig
def escrow_to_bob() -> bool:
    """Contract account: anyone can trigger a payment to Bob
    if the amount is ≤ 1 Algo and safety checks pass."""
    BOB = Account(b"\x01\x02...")  # Bob's address
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.receiver == BOB
        and Txn.amount <= UInt64(1_000_000)
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= UInt64(10_000)
    )
```

Anyone can fund this address. Anyone can submit a transaction from it --- as long as the program approves.

**Mode 2 --- Delegated signature:** An existing account owner signs the LogicSig program with their private key. This creates an authorization token: "I, Alice, authorize any transaction from my account that this program approves." Anyone holding this signed LogicSig can submit transactions from Alice's account, subject to the program's constraints. This is an illustrative example, not part of the project code:

```python
@logicsig
def recurring_payment() -> bool:
    """Alice signs this and gives it to her utility company.
    They can withdraw up to 200 Algo every 50,000 rounds."""
    UTILITY = Account(b"\x03\x04...")  # Utility's address
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.receiver == UTILITY
        and Txn.amount <= UInt64(200_000_000)
        and Txn.first_valid % UInt64(50_000) == UInt64(0)
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= UInt64(2_000)
    )
```

Client-side, the delegation works like this (illustrative client-side code):

```python
from algosdk import transaction
import base64

# Compile the LogicSig TEAL
compiled = algorand.client.algod.compile(teal_source)
program = base64.b64decode(compiled["result"])

# Alice signs the program --- this is the delegation step
lsig = transaction.LogicSigAccount(program)
lsig.sign(alice_private_key)

# Now the utility company (or any keeper) can use lsig:
payment = transaction.PaymentTxn(
    sender=alice_address,       # Sending FROM Alice's account
    sp=suggested_params,
    receiver=utility_address,
    amt=100_000_000,            # 100 Algo
)
signed = transaction.LogicSigTransaction(payment, lsig)
algorand.client.algod.send_transaction(signed)
```

**This is the core mechanism for limit orders.** Alice signs a LogicSig that says "authorize an asset transfer from my account if the price is right and the order book contract confirms the trade." A keeper submits the transaction when market conditions match.

### Template Variables: Parameterizing LogicSigs

Hardcoding addresses, amounts, and asset IDs into every LogicSig would be impractical. Algorand Python supports **template variables** --- placeholders that are filled in at compile time, producing a unique program (and unique contract account address) for each set of parameters. This is an early version showing just the template variable declarations; the complete LogicSig follows in Part 3:

```python
from algopy import logicsig, Txn, UInt64, TemplateVar

@logicsig
def limit_order_lsig() -> bool:
    """A parameterized limit order LogicSig."""
    # Template variables --- filled at compile time
    ORDER_BOOK_APP_ID = TemplateVar[UInt64]("ORDER_BOOK_APP_ID")
    SELL_ASSET = TemplateVar[UInt64]("SELL_ASSET")
    BUY_ASSET = TemplateVar[UInt64]("BUY_ASSET")
    PRICE_N = TemplateVar[UInt64]("PRICE_N")   # Numerator of price
    PRICE_D = TemplateVar[UInt64]("PRICE_D")   # Denominator of price
    MAX_SELL = TemplateVar[UInt64]("MAX_SELL")  # Max sell amount
    EXPIRY_ROUND = TemplateVar[UInt64]("EXPIRY_ROUND")

    # ... validation logic using these variables ...
    return True  # Placeholder --- full logic below
```

Compile with specific values:

```bash
puyapy limit_order.py \
  --template-var ORDER_BOOK_APP_ID=12345 \
  --template-var SELL_ASSET=31566704 \
  --template-var BUY_ASSET=0 \
  --template-var PRICE_N=25 \
  --template-var PRICE_D=100 \
  --template-var MAX_SELL=500000000 \
  --template-var EXPIRY_ROUND=35000000
```

Or from within another PuyaPy contract at compile time (this function runs during PuyaPy compilation, not at runtime on the client side; the actual client-side workflow is described in the next section):

```python
from algopy import compile_logicsig

compiled = compile_logicsig(
    limit_order_lsig,
    template_vars={
        "ORDER_BOOK_APP_ID": 12345,
        "SELL_ASSET": 31566704,
        "BUY_ASSET": 0,
        "PRICE_N": 25,
        "PRICE_D": 100,
        "MAX_SELL": 500_000_000,
        "EXPIRY_ROUND": 35_000_000,
    },
)
```

Each unique set of template values produces a different program hash, and thus a different contract account address. This is by design --- each order is a unique LogicSig.

### Template Variable Workflow at Runtime

The template variable workflow involves two compilation steps that are easy to conflate. Understanding the distinction is critical:

1. **PuyaPy compilation** (build time): PuyaPy compiles your Algorand Python LogicSig to TEAL assembly. If you compile *without* `--template-var` flags, the output TEAL contains `TMPL_`-prefixed placeholders (e.g., `TMPL_ORDER_BOOK_APP`, `TMPL_SELL_ASSET`). This is the reusable template.

2. **String replacement** (runtime): At runtime, your client-side code reads the TEAL source and performs string replacement to fill in actual values: `teal_source.replace("TMPL_ORDER_BOOK_APP", str(app_id))` and so on for each placeholder.

3. **algod compilation** (runtime): You send the filled-in TEAL to `algod.compile()`, which returns the program bytes and the program hash (the contract account address).

4. **LogicSig creation**: You create the `LogicSigAccount` from those program bytes and optionally sign it (for delegated mode).

If you compile with `--template-var` flags, PuyaPy substitutes the values directly and you skip step 2 --- but then you cannot reuse the TEAL for different parameter sets. The two-step approach (compile once to a template, substitute at runtime) is more practical for systems like the limit order book where each order has unique parameters.

Here is the concrete client-side code for the two-step approach (steps 2--4 above):

```python
import base64
from algosdk import transaction

# Step 2: Read the compiled TEAL template (contains TMPL_ placeholders)
with open("smart_contracts/artifacts/limit_order_lsig/limit_order.teal") as f:
    teal_template = f.read()

# Substitute template variables with actual values
teal_source = (
    teal_template
    .replace("TMPL_ORDER_BOOK_APP", str(app_id))
    .replace("TMPL_SELL_ASSET", str(usdc_id))
    .replace("TMPL_BUY_ASSET", str(0))
    .replace("TMPL_PRICE_N", str(250_000))
    .replace("TMPL_PRICE_D", str(1_000_000))
    .replace("TMPL_MAX_SELL", str(500_000_000))
    .replace("TMPL_EXPIRY_ROUND", str(expiry_round))
)

# Step 3: Compile the filled-in TEAL to get program bytes
compiled = algorand.client.algod.compile(teal_source)
program = base64.b64decode(compiled["result"])

# Step 4: Create the LogicSig and sign it (delegated mode)
lsig = transaction.LogicSigAccount(program)
lsig.sign(alice.private_key)

# The contract account address is compiled["hash"]
order_address = compiled["hash"]
```

### LogicSig Security Rules --- the Checklist You Must Never Skip

*Before reading the security rules: imagine you wrote a LogicSig that authorizes payments to Bob. What could go wrong? List as many attack vectors as you can think of, then compare with the checklist below.*

LogicSigs have a distinct security surface. Every LogicSig you write must enforce ALL of these checks, or it's exploitable.

**1. Close-remainder-to check (CRITICAL).** Without `Txn.close_remainder_to == Global.zero_address`, an attacker submits a zero-amount payment with `close_remainder_to` set to their address, draining the entire Algo balance.

**2. Asset-close-to check (CRITICAL for asset transfers).** Same attack vector for ASAs: `Txn.asset_close_to == Global.zero_address` prevents closing the entire ASA balance to an attacker.

**3. Rekey-to check (CRITICAL).** Without `Txn.rekey_to == Global.zero_address`, an attacker rekeys the account to themselves, permanently stealing it.

**4. Fee cap.** Without a fee limit, an attacker submits your LogicSig-authorized transaction with an absurd fee, draining balance to the block proposer. Always cap: `Txn.fee <= UInt64(10_000)` or similar.

**5. Expiration.** For delegated LogicSigs, always include a round-based expiry: `Txn.last_valid <= EXPIRY_ROUND`. A LogicSig without expiration is valid forever --- if it leaks, it can be used indefinitely.

**6. Genesis hash check.** A signed LogicSig works on ALL Algorand networks. Check `Global.genesis_hash` to restrict to a specific network, preventing cross-network replay.

**7. Group validation.** If your LogicSig is meant to be used in an atomic group with a smart contract call, verify `Global.group_size`, the group index of transactions, and the application ID of the grouped app call. Without this, someone can use your LogicSig in a different context than intended.

**8. Arguments are public.** LogicSig arguments (`Arg[0]`, etc.) are visible on-chain. Never put secrets in them. They're also not signed --- anyone can change them when submitting.

> **Check your understanding:** Why do LogicSigs use template variables instead of arguments for order parameters like price and maximum amount? What is the fundamental security difference? (Hint: consider what happens to the program hash.)

### Opcode Budget and Pooling

Every transaction in the group contributes **20,000 opcodes** to a shared LogicSig pool, regardless of whether that particular transaction uses a LogicSig. In a 16-transaction group, that's 320,000 pooled opcodes. In our 3-transaction limit order group, the LogicSig has 60,000 opcodes available. This budget is **separate** from the smart contract opcode budget (700 per app call). The two pools don't interfere with each other.

For our limit order system, a simple order validation LogicSig uses well under 1,000 opcodes. The generous budget becomes relevant in Project 4 when we use LogicSigs for ZK proof verification.


## Part 2: Architecture --- the Hybrid Stateful + Stateless Pattern

### Why You Need Both

*Before reading on, think about what a limit order system needs. It must enforce per-user trading rules trustlessly (correct asset, acceptable price, expiry) while also tracking global state (which orders exist, partial fills, double-fill prevention). Could you build this with just a smart contract? Just a LogicSig? What would you lose in each case?*

A limit order system needs two things that pull in opposite directions. (This hybrid pattern combines [smart contracts](https://dev.algorand.co/concepts/smart-contracts/overview/) with [LogicSigs](https://dev.algorand.co/concepts/smart-contracts/logic-sigs/).)

1. **Per-user trading rules** --- Each user has unique parameters: which assets, what price, how much, when it expires. These rules must be enforced trustlessly when a keeper fills the order.

2. **Shared order book state** --- The system needs to track which orders exist, prevent double-fills, record partial fills, and manage the matching engine.

LogicSigs handle #1 perfectly --- each order is a unique program encoding that user's exact trading rules. Smart contracts handle #2 --- the order book contract maintains state across all orders.

The architecture:

```
┌─────────────────────────────────────────────────┐
│                 ORDER BOOK                       │
│            (Smart Contract)                      │
│                                                  │
│  Global State:                                   │
│    - admin, fee_bps, paused                      │
│                                                  │
│  Box Storage:                                    │
│    - orders/{order_id} → OrderInfo               │
│      (seller, sell_asset, buy_asset, price,      │
│       max_amount, filled_amount, status, expiry) │
│                                                  │
│  Methods:                                        │
│    - place_order(...)     ← registers an order   │
│    - fill_order(...)      ← keeper executes fill │
│    - cancel_order(...)    ← seller cancels       │
│    - partial_fill(...)    ← partial execution    │
│                                                  │
└──────────────┬──────────────────────────────────┘
               │
               │ Atomic Group
               │
┌──────────────┴──────────────────────────────────┐
│              LIMIT ORDER LOGICSIG                │
│            (Smart Signature)                     │
│                                                  │
│  Template Variables:                             │
│    ORDER_BOOK_APP_ID, SELL_ASSET, BUY_ASSET,     │
│    PRICE_N, PRICE_D, MAX_SELL, EXPIRY_ROUND      │
│                                                  │
│  Validates:                                      │
│    - Grouped with correct order book app call    │
│    - Asset transfer matches price constraints    │
│    - Amount ≤ MAX_SELL                            │
│    - Not expired                                 │
│    - Safety checks (close-to, rekey, fee)        │
│                                                  │
└─────────────────────────────────────────────────┘
```

### The Flow: Placing an Order

1. **Alice decides** to sell 500 USDC for ALGO at 0.25 ALGO per USDC, expiring in ~24 hours (~20,000 rounds)
2. **Client compiles** the limit order LogicSig with Alice's parameters as template variables
3. **Alice signs** the compiled LogicSig with her private key (delegation)
4. **Client submits** an atomic group:
   - App call to `place_order(sell_asset, buy_asset, price_n, price_d, max_amount, expiry, lsig_address)`
   - The order book records the order in box storage
5. **Client stores** the signed LogicSig and broadcasts it to keepers (via an off-chain relay, API, or indexer event)

### The Flow: Filling an Order

1. **Keeper observes** Alice's open order (via indexer or off-chain relay)
2. **Keeper constructs** an atomic group:
   - [0] `Keeper → Alice: Payment of ALGO` --- signed by keeper's private key
   - [1] `Alice → Keeper: Asset transfer of USDC` --- authorized by Alice's signed LogicSig
   - [2] `Keeper → OrderBook: App call to fill_order(order_id)` --- signed by keeper
3. **AVM executes** the group atomically:
   - Alice's LogicSig validates that the USDC transfer is grouped with the correct order book call, the price is correct, and safety checks pass
   - The keeper's payment sends ALGO to Alice
   - The order book contract verifies the fill, updates the filled amount, and emits events
4. If **any** transaction fails, the **entire** group is rejected. Alice's USDC never leaves without her receiving the correct ALGO amount.

### The Flow: Cancellation

Alice can cancel anytime by calling `cancel_order` directly. The order book marks the order as cancelled. Any subsequent attempt to use Alice's LogicSig in a fill will fail because `fill_order` checks that the order is still active.


## Part 3: Building the Limit Order LogicSig

### The Complete LogicSig Program

The LogicSig is structured in five sections: template variable declarations, mandatory safety checks, transaction type validation, group structure validation, and buy-side price verification. (See [Algorand Python compilation](https://dev.algorand.co/algokit/languages/python/lg-compile/) for template variable usage.) Add the following to `smart_contracts/limit_order_lsig/contract.py`:

```python
from algopy import (
    Asset, Application, Global, Txn, UInt64, gtxn, logicsig, TemplateVar,
    TransactionType,
)

@logicsig
def limit_order() -> bool:
    """Delegated LogicSig encoding a limit sell order."""
    # ── Template variables (filled at compile time) ──────────
    ORDER_BOOK_APP = TemplateVar[UInt64]("ORDER_BOOK_APP")
    SELL_ASSET = TemplateVar[UInt64]("SELL_ASSET")
    BUY_ASSET = TemplateVar[UInt64]("BUY_ASSET")
    PRICE_N = TemplateVar[UInt64]("PRICE_N")   # Numerator of price
    PRICE_D = TemplateVar[UInt64]("PRICE_D")   # Denominator of price
    MAX_SELL = TemplateVar[UInt64]("MAX_SELL")
    EXPIRY_ROUND = TemplateVar[UInt64]("EXPIRY_ROUND")

    # ── Safety checks (MANDATORY --- never remove) ──────────
    assert Txn.close_remainder_to == Global.zero_address
    assert Txn.asset_close_to == Global.zero_address
    assert Txn.rekey_to == Global.zero_address
    assert Txn.fee <= UInt64(10_000)
    assert Txn.last_valid <= EXPIRY_ROUND

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
        assert gtxn.Transaction(0).asset_amount * PRICE_D >= Txn.asset_amount * PRICE_N

    # ── Verify the order book app call ───────────────────────
    assert gtxn.Transaction(2).type == TransactionType.ApplicationCall
    assert gtxn.Transaction(2).app_id == Application(ORDER_BOOK_APP)

    return True
```

> **Why no genesis hash check?** The security checklist in Part 1 requires a `Global.genesis_hash` check to prevent cross-network replay. This LogicSig omits it because the `ORDER_BOOK_APP` template variable already pins the LogicSig to a specific network --- application IDs are unique per network, so a LogicSig compiled with a MainNet app ID is useless on TestNet (and vice versa). The app ID check on line `assert gtxn.Transaction(2).app_id == Application(ORDER_BOOK_APP)` provides equivalent network binding.

### What the LogicSig Validates vs What It Delegates

The LogicSig handles **trustless enforcement of the user's trading rules**: correct asset, acceptable price, maximum amount, expiry, and safety. It does NOT handle order tracking, partial fill accounting, or double-fill prevention --- that's the smart contract's job.

This separation is deliberate. LogicSigs are stateless and cannot read contract state. The smart contract is stateful and can maintain the order book. Together, they provide both trustless rule enforcement (LogicSig) and coordinated state management (contract).

### Price Representation: the N/D Rational Number Pattern

Prices on Algorand are represented as rational numbers (numerator/denominator) because the AVM has no floating point. The convention: "I want at least N units of buy_asset per D units of sell_asset."

Example: Alice wants 0.25 ALGO per USDC → `PRICE_N = 250_000` (0.25 ALGO in microAlgos), `PRICE_D = 1_000_000` (1 USDC with 6 decimals).

The price check uses cross-multiplication to avoid division and potential precision loss:

```
buy_amount × PRICE_D ≥ sell_amount × PRICE_N
```

**Overflow warning:** If `buy_amount` and `PRICE_D` are both large, their product can overflow uint64. For production, validate that your expected ranges stay within uint64 bounds, or use `BigUInt` / wide arithmetic. With 6-decimal tokens and reasonable order sizes (< 10^12 base units), the product stays under 10^18 --- safely within uint64's ~1.8 × 10^19 limit.


## Part 4: Building the Order Book Smart Contract

### Order Data Structure

Each order is stored in [box storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/), keyed by a unique order ID. The order data is packed as a 128-byte binary blob --- we will discuss this design choice after the contract code.

The contract starts with imports, status constants, and state declarations. Add the following to `smart_contracts/limit_order_book/contract.py`:

```python
from algopy import (
    ARC4Contract, Account, Asset, BoxMap, Bytes, Global, GlobalState,
    TransactionType, Txn, UInt64, arc4, gtxn, itxn, log, op,
)

ORDER_ACTIVE = 1
ORDER_FILLED = 2
ORDER_CANCELLED = 3
ORDER_PARTIAL = 4

class LimitOrderBook(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.next_order_id = GlobalState(UInt64(1))
        self.fee_bps = GlobalState(UInt64(10))  # 0.1% keeper fee (reserved for future use)
        self.paused = GlobalState(UInt64(0))

        # Order storage: order_id -> packed order data
        # Data layout (packed bytes):
        #   seller:       32 bytes (address)
        #   sell_asset:    8 bytes (uint64)
        #   buy_asset:     8 bytes (uint64)
        #   price_n:       8 bytes (uint64)
        #   price_d:       8 bytes (uint64)
        #   max_amount:    8 bytes (uint64)
        #   filled_amount: 8 bytes (uint64)
        #   status:        8 bytes (uint64)
        #   expiry_round:  8 bytes (uint64)
        #   lsig_hash:    32 bytes (LogicSig program hash)
        # Total: 128 bytes per order
        self.orders = BoxMap(arc4.UInt64, Bytes, key_prefix=b"o_")

    @arc4.abimethod
    def initialize(self, fee_bps: UInt64) -> None:
        assert Txn.sender == Global.creator_address
        assert self.admin.value == Bytes()  # One-time initialization only
        self.admin.value = Txn.sender.bytes
        self.fee_bps.value = fee_bps
```

The `place_order` method registers a new order in box storage. The seller calls this after signing the corresponding LogicSig. Order data is packed as a concatenation of fixed-width fields using `op.concat` and `op.itob`, and a structured event is logged for keepers to discover new orders:

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
        assert Global.group_size == UInt64(2), "Expected payment + app call"
        assert self.paused.value == UInt64(0)
        assert price_d > UInt64(0)  # No division by zero
        assert max_amount > UInt64(0)
        assert expiry_round > Global.round  # Must be in the future
        assert lsig_hash.length == UInt64(32)

        # Verify MBR payment for box storage
        # Box key: 10 bytes (prefix + uint64), Box data: 128 bytes
        box_cost = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(128))
        assert mbr_payment.receiver == Global.current_application_address
        assert mbr_payment.amount >= box_cost

        order_id = self.next_order_id.value
        self.next_order_id.value = order_id + UInt64(1)

        # Pack order data (128 bytes total)
        order_data = Txn.sender.bytes              # seller: 32 bytes
        order_data = op.concat(order_data, op.itob(sell_asset))
        order_data = op.concat(order_data, op.itob(buy_asset))
        order_data = op.concat(order_data, op.itob(price_n))
        order_data = op.concat(order_data, op.itob(price_d))
        order_data = op.concat(order_data, op.itob(max_amount))
        order_data = op.concat(order_data, op.itob(UInt64(0)))             # filled_amount
        order_data = op.concat(order_data, op.itob(UInt64(ORDER_ACTIVE)))  # status
        order_data = op.concat(order_data, op.itob(expiry_round))
        order_data = op.concat(order_data, lsig_hash)

        self.orders[arc4.UInt64(order_id)] = order_data

        # Log event for keepers to discover
        event = op.concat(b"new_order", op.itob(order_id))
        event = op.concat(event, Txn.sender.bytes)
        event = op.concat(event, op.itob(sell_asset))
        event = op.concat(event, op.itob(buy_asset))
        event = op.concat(event, op.itob(price_n))
        event = op.concat(event, op.itob(price_d))
        event = op.concat(event, op.itob(max_amount))
        log(event)

        return order_id
```

The `fill_order` method is the most complex in this project --- it validates the 3-transaction atomic group, unpacks the order data, verifies price constraints, and updates the fill status. We will walk through it in four stages. The expected group structure is: `[0]` keeper's buy-side payment to the seller, `[1]` seller's LogicSig-authorized asset transfer, `[2]` this app call.

**Stage 1: Data unpacking.** The method signature and order data deserialization. Each field is extracted from the packed binary box at its known byte offset:

```python
    @arc4.abimethod
    def fill_order(
        self,
        order_id: UInt64,
        fill_amount: UInt64,
        sell_txn: gtxn.AssetTransferTransaction,
    ) -> None:
        """Execute a fill against an open order."""
        assert Global.group_size == UInt64(3), "Expected 3 transactions"
        assert self.paused.value == UInt64(0)

        # Load and unpack order data
        order_key = arc4.UInt64(order_id)
        assert order_key in self.orders
        data = self.orders[order_key]

        seller = op.extract(data, UInt64(0), UInt64(32))
        sell_asset = op.btoi(op.extract(data, UInt64(32), UInt64(8)))
        buy_asset = op.btoi(op.extract(data, UInt64(40), UInt64(8)))
        price_n = op.btoi(op.extract(data, UInt64(48), UInt64(8)))
        price_d = op.btoi(op.extract(data, UInt64(56), UInt64(8)))
        max_amount = op.btoi(op.extract(data, UInt64(64), UInt64(8)))
        filled_amount = op.btoi(op.extract(data, UInt64(72), UInt64(8)))
        status = op.btoi(op.extract(data, UInt64(80), UInt64(8)))
        expiry_round = op.btoi(op.extract(data, UInt64(88), UInt64(8)))
```

**Stage 2: Order state validation.** Before processing the fill, verify the order is still active (not cancelled or fully filled), has not expired, and the fill amount would not exceed the remaining capacity:

```python
        # Validate order state
        assert status == UInt64(ORDER_ACTIVE) or status == UInt64(ORDER_PARTIAL)
        assert Global.round <= expiry_round
        assert fill_amount > UInt64(0)
        assert filled_amount + fill_amount <= max_amount
```

**Stage 3: Transaction validation and price check.** The contract verifies both sides of the trade. The sell-side transaction (position `[1]` in the group) is the LogicSig-authorized asset transfer --- the contract confirms it matches the order's parameters and includes the mandatory close-to and rekey-to safety checks. The buy-side transaction (position `[0]`) is the keeper's payment to the seller. The price check uses cross-multiplication (`buy_amount * price_d >= sell_amount * price_n`) to avoid division and the precision loss it would introduce:

```python
        # Validate the sell-side transaction (LogicSig authorized)
        assert sell_txn.xfer_asset == Asset(sell_asset)
        assert sell_txn.asset_amount == fill_amount
        assert sell_txn.sender.bytes == seller

        # Validate the buy-side transaction
        if buy_asset == UInt64(0):
            buy_txn_amount = gtxn.Transaction(0).amount
            assert gtxn.Transaction(0).type == TransactionType.Payment
            assert gtxn.Transaction(0).receiver.bytes == seller
        else:
            buy_txn_amount = gtxn.Transaction(0).asset_amount
            assert gtxn.Transaction(0).type == TransactionType.AssetTransfer
            assert gtxn.Transaction(0).asset_receiver.bytes == seller
            assert gtxn.Transaction(0).xfer_asset == Asset(buy_asset)

        # Price verification (cross-multiply to avoid division)
        assert buy_txn_amount * price_d >= fill_amount * price_n
```

**Stage 4: State update and event logging.** With all validations passed, the contract updates the order's filled amount and status in the packed binary box, then emits a fill event for keepers and indexers to track:

```python
        # Update filled amount and status
        new_filled = filled_amount + fill_amount
        new_status = UInt64(ORDER_FILLED) if new_filled == max_amount else UInt64(ORDER_PARTIAL)
        updated = op.replace(data, UInt64(72), op.itob(new_filled))
        updated = op.replace(updated, UInt64(80), op.itob(new_status))
        self.orders[order_key] = updated

        # Log fill event
        event = op.concat(b"fill", op.itob(order_id))
        event = op.concat(event, op.itob(fill_amount))
        event = op.concat(event, op.itob(new_filled))
        event = op.concat(event, Txn.sender.bytes)
        log(event)
```

The `cancel_order` method lets the seller cancel their open order. Only the original seller can cancel, and the order must still be active or partially filled. The `cleanup_expired_order` method allows anyone to clean up an expired order, deleting its box to free MBR and refunding the seller:

```python
    @arc4.abimethod
    def cancel_order(self, order_id: UInt64) -> None:
        """Cancel an open order. Only the seller can cancel."""
        order_key = arc4.UInt64(order_id)
        assert order_key in self.orders
        data = self.orders[order_key]

        seller = op.extract(data, UInt64(0), UInt64(32))
        assert Txn.sender.bytes == seller

        status = op.btoi(op.extract(data, UInt64(80), UInt64(8)))
        assert status == UInt64(ORDER_ACTIVE) or status == UInt64(ORDER_PARTIAL)

        updated = op.replace(data, UInt64(80), op.itob(UInt64(ORDER_CANCELLED)))
        self.orders[order_key] = updated
        log(op.concat(b"cancel", op.itob(order_id)))

    @arc4.abimethod
    def cleanup_expired_order(self, order_id: UInt64) -> None:
        """Anyone can clean up an expired order and free the MBR."""
        order_key = arc4.UInt64(order_id)
        assert order_key in self.orders
        data = self.orders[order_key]

        expiry_round = op.btoi(op.extract(data, UInt64(88), UInt64(8)))
        assert Global.round > expiry_round

        seller = op.extract(data, UInt64(0), UInt64(32))
        del self.orders[order_key]

        box_cost = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(128))
        itxn.Payment(
            receiver=Account(seller),
            amount=box_cost,
            fee=UInt64(0),
        ).submit()

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "Contract is immutable"
```

### Packed Binary Data vs ARC-4 Structs

The order data is stored as a packed 128-byte binary blob rather than an ARC-4 struct. This is a deliberate design choice for this tutorial --- it teaches you the `op.extract`, `op.replace`, `op.itob`, and `op.btoi` operations that are essential for working with raw box data. In production, you might use `arc4.Struct` for cleaner code at the cost of slightly larger encoding overhead.

The extraction pattern (illustrative, showing the approach used throughout the contract):

```python
# Reading a uint64 from a packed byte array:
# op.extract(data, offset, length) → Bytes
# op.btoi(bytes) → UInt64
sell_asset = op.btoi(op.extract(data, UInt64(32), UInt64(8)))

# Writing back:
# op.itob(uint64) → 8-byte big-endian Bytes
# op.replace(original, offset, new_bytes) → Bytes
updated = op.replace(data, UInt64(72), op.itob(new_filled))
```

This is the Algorand equivalent of struct packing in C. It's efficient (minimal storage overhead), but requires careful offset management. Define constants for your offsets (optionally add these to `smart_contracts/limit_order_book/contract.py` at module level):

```python
OFFSET_SELLER = 0        # 32 bytes
OFFSET_SELL_ASSET = 32   # 8 bytes
OFFSET_BUY_ASSET = 40    # 8 bytes
OFFSET_PRICE_N = 48      # 8 bytes
OFFSET_PRICE_D = 56      # 8 bytes
OFFSET_MAX_AMOUNT = 64   # 8 bytes
OFFSET_FILLED = 72       # 8 bytes
OFFSET_STATUS = 80       # 8 bytes
OFFSET_EXPIRY = 88       # 8 bytes
OFFSET_LSIG_HASH = 96   # 32 bytes
ORDER_SIZE = 128         # Total
```

> **ARC-4 method signatures.** When constructing transactions manually (without a typed client), you need the exact method signatures for `Method.from_signature()` or `AtomicTransactionComposer`. These are derived from the contract's method definitions and can also be found in the generated `.arc56.json` file:
>
> | Method | ARC-4 Signature |
> |--------|----------------|
> | `initialize` | `"initialize(uint64)void"` |
> | `place_order` | `"place_order(uint64,uint64,uint64,uint64,uint64,uint64,byte[],pay)uint64"` |
> | `fill_order` | `"fill_order(uint64,uint64,axfer)void"` |
> | `cancel_order` | `"cancel_order(uint64)void"` |
> | `cleanup_expired_order` | `"cleanup_expired_order(uint64)void"` |


## Part 5: The Keeper Bot --- Executing Orders Off-Chain

### Keeper Architecture

A keeper is an off-chain service that monitors the order book and executes fills when profitable. Keepers are permissionless --- anyone can run one. They earn profit from the spread between the order's price and the market price (or from explicit keeper fees built into the protocol). The keeper reads state via the [algod REST API](https://dev.algorand.co/reference/rest-api/overview/) and submits [atomic groups](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/).

The following is a structural outline of a keeper bot showing the key components and logic flow. It is illustrative --- a complete implementation would need concrete order unpacking, market price feeds, error handling, and configuration. Save it as `keeper.py` for reference.

The keeper class starts with initialization and order discovery. The `scan_open_orders` method reads all order boxes from the contract via the algod REST API and filters for active orders:

```python
# keeper.py --- simplified keeper bot
from algosdk.v2client import algod, indexer
from algosdk import transaction
import time

class LimitOrderKeeper:
    def __init__(self, algod_client, indexer_client, keeper_account):
        self.algod = algod_client
        self.indexer = indexer_client
        self.keeper = keeper_account
        self.order_book_app_id = ORDER_BOOK_APP_ID

    def scan_open_orders(self):
        """Read all order boxes from the order book contract."""
        boxes = self.algod.application_boxes(self.order_book_app_id)
        orders = []
        for box_info in boxes["boxes"]:
            box_name = box_info["name"]
            box_data = self.algod.application_box_by_name(
                self.order_book_app_id, box_name
            )
            order = self.unpack_order(box_data["value"], box_name)
            if order["status"] == ORDER_ACTIVE:
                orders.append(order)
        return orders

    def is_profitable(self, order, market_price):
        """Check if filling this order is profitable for the keeper."""
        order_price = order["price_n"] / order["price_d"]
        remaining = order["max_amount"] - order["filled_amount"]
        return market_price < order_price and remaining > 0
```

The `execute_fill` method builds the 3-transaction atomic group required to fill an order: the keeper's buy-side payment to the seller, the seller's LogicSig-authorized asset transfer, and the order book app call. Note that the keeper overpays the fee on the app call to cover all three transactions via fee pooling:

```python
    def execute_fill(self, order, fill_amount, signed_lsig):
        """Build and submit the atomic fill group."""
        sp = self.algod.suggested_params()
        sp.fee = 0
        sp.flat_fee = True

        # [0] Keeper → Seller: buy_asset
        buy_amount = calculate_buy_amount(
            fill_amount, order["price_n"], order["price_d"]
        )
        if order["buy_asset"] == 0:
            buy_txn = transaction.PaymentTxn(
                sender=self.keeper.address, sp=sp,
                receiver=order["seller"], amt=buy_amount,
            )
        else:
            buy_txn = transaction.AssetTransferTxn(
                sender=self.keeper.address, sp=sp,
                receiver=order["seller"],
                amt=buy_amount, index=order["buy_asset"],
            )

        # [1] Seller → Keeper: sell_asset (LogicSig authorized)
        sell_txn = transaction.AssetTransferTxn(
            sender=order["seller"], sp=sp,
            receiver=self.keeper.address,
            amt=fill_amount, index=order["sell_asset"],
        )

        # [2] App call to fill_order (keeper overpays fee for group)
        sp_fee = self.algod.suggested_params()
        sp_fee.fee = 4000
        sp_fee.flat_fee = True
        app_txn = transaction.ApplicationCallTxn(
            sender=self.keeper.address, sp=sp_fee,
            index=self.order_book_app_id,
            on_complete=transaction.OnComplete.NoOpOC,
            app_args=["fill_order", order["id"], fill_amount],
            foreign_assets=[order["sell_asset"]],
            accounts=[order["seller"]],
            boxes=[(self.order_book_app_id, order["box_key"])],
        )
```

Finally, the group is assembled, signed, and submitted atomically. The `run` method polls for orders every block (~2.8 seconds) and fills any profitable ones:

```python
        # Group, sign, and submit
        gid = transaction.calculate_group_id([buy_txn, sell_txn, app_txn])
        buy_txn.group = sell_txn.group = app_txn.group = gid

        signed_buy = buy_txn.sign(self.keeper.private_key)
        signed_sell = transaction.LogicSigTransaction(sell_txn, signed_lsig)
        signed_app = app_txn.sign(self.keeper.private_key)
        # Submit atomic group (algosdk concatenates the signed txns internally)
        self.algod.send_transactions([signed_buy, signed_sell, signed_app])

    def run(self):
        """Main keeper loop."""
        while True:
            orders = self.scan_open_orders()
            for order in orders:
                market_price = self.get_market_price(
                    order["sell_asset"], order["buy_asset"]
                )
                if self.is_profitable(order, market_price):
                    remaining = order["max_amount"] - order["filled_amount"]
                    self.execute_fill(order, remaining, order["signed_lsig"])
            time.sleep(3)  # Check every block
```

> **Design decision: separate enforcement from coordination.** The key architectural insight in this system is the separation of concerns. LogicSigs enforce rules --- they cannot be cheated. Smart contracts coordinate --- they track shared state. When I see a system that needs both trustless rules AND shared mutable state, this hybrid pattern is my first instinct. The LogicSig guarantees Alice's price is honored; the smart contract guarantees the order book is consistent.

### Where Do Keepers Get the Signed LogicSigs?

The signed LogicSig (Alice's signed delegation) must be shared with keepers somehow. Several approaches:

**Off-chain relay (simplest):** The frontend posts the signed LogicSig to a centralized API or peer-to-peer network. Keepers poll this relay for new orders. This is how most existing Algorand DEXs with limit orders work. The relay is a convenience layer --- it doesn't affect security because the LogicSig itself enforces all trading rules.

**On-chain storage:** Store the signed LogicSig in box storage. This makes the system fully on-chain but is expensive --- a LogicSig can be up to 1,000 bytes, plus the signature. The MBR for a 1,100-byte box is `2,500 + 400 × (10 + 1,100) = 446,500 μAlgo` ≈ 0.45 Algo per order.

**Hybrid (recommended):** Store only the LogicSig program hash on-chain (32 bytes, stored in the order data). Distribute the actual signed LogicSig off-chain. Keepers verify the hash matches before using it. This gives you on-chain order discovery with off-chain LogicSig distribution.

### Keeper Incentives and MEV

Keepers profit from the spread. If Alice's order sells USDC at 0.25 ALGO/USDC and the market price is 0.27 ALGO/USDC, the keeper buys USDC from Alice at 0.25 and sells on the AMM at 0.27, pocketing 0.02 ALGO per USDC.

On Algorand, keeper competition is a **latency race**, not a fee auction. The first keeper to submit a valid fill transaction wins. There's no priority gas auction like Ethereum's. This makes keeper infrastructure simpler but rewards low-latency network connections to relay nodes.

To prevent keeper-vs-keeper waste (multiple keepers submitting fills for the same order simultaneously), the order book contract's `fill_order` method is the arbiter --- only the first valid fill succeeds, and subsequent attempts fail because the order status has changed.

## Running the Limit Order System on LocalNet

Let us walk through the full lifecycle on LocalNet: deploy the order book, place an order, and fill it with a keeper.

First, compile and deploy the order book contract:

```bash
algokit project run build
```

Save the following as a client-side deployment and test script (e.g., `test_deploy.py` in your project root).

The first part deploys the order book, creates a test token, and sets up Alice's account:

```python
from pathlib import Path
import algokit_utils
from algosdk import encoding, transaction
import base64

algorand = algokit_utils.AlgorandClient.default_localnet()
admin = algorand.account.localnet_dispenser()

# Deploy the order book
factory = algorand.client.get_app_factory(
    app_spec=Path("smart_contracts/artifacts/limit_order_book/LimitOrderBook.arc56.json").read_text(),
    default_sender=admin.address,
)
book_client, deploy_result = factory.deploy()
book_client.send.call(
    algokit_utils.AppClientMethodCallParams(method="initialize", args=[10])
)
print(f"Order Book App ID: {book_client.app_id}")

# Fund the app account for MBR and inner transaction fees
algorand.send.payment(
    algokit_utils.PaymentParams(
        sender=admin.address,
        receiver=book_client.app_address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(1_000_000),
    )
)

# Create a test USDC token and fund Alice
usdc_id = create_test_asa(algorand, admin, "USDC", "USDC", decimals=6)
alice = algorand.account.random()
fund_account(algorand, admin, alice, algo=10_000_000, asa_id=usdc_id, asa_amount=500_000_000)
```

The app account needs seed funding to cover its minimum balance requirement (which increases as orders create box storage) and to pay for inner transactions such as MBR refunds in `cleanup_expired_order`. Without this funding, the first `place_order` call will fail with "balance below minimum."

Next, compile Alice's limit order LogicSig with her specific trading parameters, then have Alice sign (delegate) it and place the order on the order book:

```python
# Compile Alice's limit order LogicSig: sell 500 USDC for ALGO at 0.25 ALGO/USDC
lsig_teal = compile_limit_order(
    order_book_app=book_client.app_id,
    sell_asset=usdc_id, buy_asset=0,
    price_n=250_000, price_d=1_000_000,
    max_sell=500_000_000,
    expiry_round=algorand.client.algod.status()["last-round"] + 5000,
)
expiry_round = algorand.client.algod.status()["last-round"] + 5000
compiled = algorand.client.algod.compile(lsig_teal)
program = base64.b64decode(compiled["result"])
lsig = transaction.LogicSigAccount(program)
lsig.sign(alice.private_key)  # Alice delegates

# Place the order (Alice calls the order book)
order_result = book_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="place_order",
        args=[usdc_id, 0, 250_000, 1_000_000, 500_000_000,
              expiry_round,
              encoding.decode_address(compiled["hash"]),
              fund_mbr(admin, book_client)],
        sender=alice.address,
        box_references=[b"o_" + (1).to_bytes(8, "big")],
    )
)
print(f"Order placed: ID {order_result.abi_return}")
```

Finally, a keeper fills the order by constructing the 3-transaction atomic group --- buy-side payment, LogicSig-authorized sell-side transfer, and order book app call. Because `fill_order` has signature `fill_order(uint64,uint64,axfer)void`, the sell-side transfer is a **transaction argument** (not an `app_args` value) and must be passed via the `AtomicTransactionComposer`:

```python
keeper = algorand.account.random()
fund_account(algorand, admin, keeper, algo=200_000_000)  # 200 ALGO
# Keeper must opt into the sell asset to receive it
algorand.send.asset_opt_in(
    algokit_utils.AssetOptInParams(
        sender=keeper.address, asset_id=usdc_id
    )
)

fill_amount = 500_000_000  # Fill the full order
buy_amount = 125_000_000   # 0.25 ALGO per USDC x 500 USDC = 125 ALGO
order_id = order_result.abi_return

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
sp_fee.fee = 4000
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

If you see `"Logic eval error"`, check that the LogicSig's template variables match the order parameters exactly --- a mismatch in any field produces a different program hash, invalidating Alice's signature. If you see `"box read budget exceeded"`, add box references to the app call transaction.

> **Warning: `last_valid` must respect EXPIRY_ROUND.** The LogicSig asserts `Txn.last_valid <= EXPIRY_ROUND`. If `suggested_params()` returns a `last_valid` round beyond the LogicSig's expiry, the fill transaction will be rejected by the LogicSig. Always set `sp.last = min(sp.last, expiry_round)` on the sell-side transaction before submitting.

> **Warning: ARC-4 encoding for `byte[]` parameters.** The `place_order` method's `lsig_hash` parameter has type `Bytes`, which requires proper ARC-4 encoding when called via `app_args`. Do not pass raw 32-byte values directly in `app_args` --- use `AtomicTransactionComposer` or `algosdk.abi` for correct length-prefixed encoding. The typed client generated by `algokit generate client` handles this automatically.

This end-to-end flow --- place order, compile LogicSig, delegate, fill via atomic group --- is the pattern every Algorand limit order system follows.

> **Note:** The helper functions (`create_test_asa`, `fund_account`, `compile_limit_order`, `fund_mbr`) are wrappers around the AlgoKit Utils and algosdk calls shown earlier in this chapter --- implement them using the deployment and interaction patterns demonstrated above.

## Part 6: Security Deep Dive

### Attack: LogicSig replay across orders

**Risk:** If Alice creates two orders with the same parameters, the same signed LogicSig could be replayed against both orders' fills. (See the [LogicSig security checklist](https://dev.algorand.co/concepts/smart-contracts/logic-sigs/) for replay prevention.)

**Mitigation:** Each order has a unique ID in the order book. The `fill_order` method verifies the order exists and has remaining capacity. Even if the same LogicSig is used twice, the fills are tracked separately in box storage. The `max_amount` and `filled_amount` fields prevent over-filling.

For additional safety, the LogicSig can include a unique nonce as a template variable, making each LogicSig program unique even for identical order parameters.

### Attack: keeper front-running

**Risk:** Keeper A sees Keeper B's pending fill transaction in the mempool and submits their own fill first.

**Mitigation:** This is inherent to permissionless keeper systems and is acceptable --- it's how competitive market-making works. The seller (Alice) doesn't care which keeper fills her order; she gets the same price regardless. The competition between keepers ensures fills happen quickly.

### Attack: stale LogicSig after cancellation

**Risk:** Alice cancels her order via the smart contract, but a keeper still has her signed LogicSig and tries to fill.

**Mitigation:** The `fill_order` method checks `status == ORDER_ACTIVE || status == ORDER_PARTIAL`. After cancellation, the status is `ORDER_CANCELLED`, and any fill attempt fails. The LogicSig's group validation ensures it can only be used in a group with a `fill_order` call, which will reject the fill.

### Attack: price manipulation via group restructuring

**Risk:** An attacker constructs a group that satisfies the LogicSig but with a different intent than expected.

**Mitigation:** The LogicSig explicitly validates the group size (3), its own position in the group (index 1), the buy-side transaction's receiver (must be the seller), and the app call's application ID (must be the order book). An attacker cannot insert additional transactions or rearrange the group without violating these checks.

### Attack: LogicSig args manipulation

**Risk:** LogicSig arguments are not signed --- anyone can change them when submitting.

**Mitigation:** Our LogicSig uses **template variables**, not arguments. Template variables are baked into the program bytecode at compile time. Changing them changes the program hash, which invalidates Alice's signature. This is a key architectural choice: template variables for all order parameters, arguments for nothing.


## Part 7: Testing the Complete System

> **Note:** The tests below are structural outlines showing *what* to test and *how* to assert. The helper functions (`create_test_asa`, `fund_account`, `deploy_order_book`, `compile_and_sign_limit_order`, `execute_fill`, `advance_rounds`, etc.) are project-specific wrappers around the [AlgoKit Utils](https://dev.algorand.co/algokit/utils/python/testing/) calls shown earlier in this chapter --- implement them using the deployment and interaction patterns demonstrated above. The patterns here --- lifecycle tests, failure-path tests, invariant tests --- are the ones you should implement for any production contract.

The following test outlines go in `tests/test_limit_order.py` (not part of the contract code):

```python
class TestLimitOrderBook:
    def test_full_order_lifecycle(self, algorand):
        """Place → Fill → Verify state"""
        # Setup
        admin = algorand.account.localnet_dispenser()
        alice = algorand.account.random()
        keeper = algorand.account.random()

        # Fund accounts, create test ASA, deploy order book
        usdc = create_test_asa(algorand, admin, "USDC", 6)
        fund_account(algorand, alice, algo=10, usdc=1000)
        fund_account(algorand, keeper, algo=100)

        book = deploy_order_book(algorand, admin)

        # Alice places a limit sell: 500 USDC for ALGO at 0.25 ALGO/USDC
        lsig = compile_and_sign_limit_order(
            alice, sell_asset=usdc, buy_asset=0,
            price_n=250_000, price_d=1_000_000,
            max_amount=500_000_000, expiry_round=current_round + 20_000,
            order_book_app=book.app_id,
        )
        order_id = call_method(book, "place_order", [...])

        # Keeper fills the full order
        execute_fill(keeper, book, order_id, 500_000_000, lsig)

        # Verify: Alice received 125 ALGO, keeper received 500 USDC
        assert get_algo_balance(alice) >= 125_000_000
        assert get_asa_balance(keeper, usdc) == 500_000_000

        # Verify: order is marked FILLED
        order = read_order(book, order_id)
        assert order["status"] == ORDER_FILLED
        assert order["filled_amount"] == 500_000_000

    def test_partial_fill(self, algorand):
        """Fill half the order, then fill the rest."""
        # ... place order for 1000 USDC ...
        # First fill: 400 USDC
        execute_fill(keeper, book, order_id, 400_000_000, lsig)
        order = read_order(book, order_id)
        assert order["status"] == ORDER_PARTIAL
        assert order["filled_amount"] == 400_000_000

        # Second fill: 600 USDC (remaining)
        execute_fill(keeper, book, order_id, 600_000_000, lsig)
        order = read_order(book, order_id)
        assert order["status"] == ORDER_FILLED

    def test_cancel_prevents_fill(self, algorand):
        """After cancellation, fills must fail."""
        # ... place order, then cancel ...
        call_method(book, "cancel_order", [order_id], sender=alice.address)

        # Attempt fill should fail
        with pytest.raises(Exception):
            execute_fill(keeper, book, order_id, 500_000_000, lsig)

    def test_expired_order_rejected(self, algorand):
        """Orders past their expiry round cannot be filled."""
        # ... place order expiring in 10 rounds ...
        advance_rounds(algorand, 15)

        with pytest.raises(Exception):
            execute_fill(keeper, book, order_id, 500_000_000, lsig)

    def test_overfill_rejected(self, algorand):
        """Cannot fill more than max_amount."""
        # Order for 500 USDC, try to fill 600
        with pytest.raises(Exception):
            execute_fill(keeper, book, order_id, 600_000_000, lsig)

    def test_wrong_price_rejected(self, algorand):
        """Keeper paying below the limit price must fail."""
        # LogicSig checks: buy_amount * PRICE_D >= sell_amount * PRICE_N
        # If keeper underpays, the LogicSig rejects the transaction
        pass

    def test_safety_checks(self, algorand):
        """Attempts to drain via close-to or rekey must fail."""
        # Construct a malicious transaction with close_remainder_to set
        # The LogicSig must reject it
        pass

    def test_cleanup_expired_order(self, algorand):
        """Expired orders can be cleaned up and MBR refunded."""
        pass
```


## Part 8: Composing with the AMM From Project 2

### The Real Power: Keepers Routing Through Your AMM

The limit order system becomes dramatically more useful when keepers can atomically fill limit orders using the AMM from Project 2 as a liquidity source. The keeper doesn't need to hold inventory --- they borrow from the AMM in the same [atomic group](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/).

```
Atomic Group (5 transactions):
[0] Keeper → Alice: 125 ALGO (keeper's payment)
[1] Alice → Keeper: 500 USDC (LogicSig: limit order)
[2] Keeper → OrderBook: App call to fill_order
[3] Keeper → AMM Pool: 500 USDC (input to swap)
[4] Keeper → AMM Pool: App call to swap (receive ~135 ALGO)
```

The keeper receives ~135 ALGO from the AMM swap but only pays 125 ALGO to Alice, pocketing ~10 ALGO profit (minus fees). This is an atomic arbitrage --- if any transaction fails, none execute. The keeper takes zero inventory risk.

This pattern --- limit order fill + AMM swap in a single atomic group --- is how professional Algorand DEX aggregators work. The keeper scans for price discrepancies between limit orders and AMM pools, and captures the spread.

**Group size constraint:** Algorand allows 16 transactions per group. A fill + AMM swap uses 5 transactions minimum. More complex multi-hop routes (fill → swap A/B → swap B/C) use more. Plan your group layout carefully.

## Cross-Contract Calls via Inner Transactions

The keeper's atomic group from the previous section coordinates multiple contracts *externally* --- the keeper constructs the group client-side. But contracts can also call other contracts *internally* via inner `ApplicationCall` transactions. This is the Algorand equivalent of Solidity's external function calls.

When one contract calls another via inner transaction:
- The called contract's approval program runs within the caller's execution
- Each inner app call adds **+700 opcodes** to the shared budget
- The call stack depth is limited to **8 levels** (the 8th-level contract cannot call further apps)
- The calling contract can read the called contract's return value from the inner transaction result

Here is how the order book contract could verify an AMM price directly, rather than relying on the keeper. This is an illustrative extension, not part of the base project code:

```python
    @arc4.abimethod
    def check_amm_price(
        self,
        amm_app: Application,
        asset_a: Asset,
        asset_b: Asset,
    ) -> UInt64:
        """Read the current price from an AMM pool's global state."""
        # Read the AMM's reserves via cross-app state read
        reserve_a, reserve_a_exists = op.AppGlobal.get_ex_uint64(amm_app, Bytes(b"reserve_a"))
        reserve_b, reserve_b_exists = op.AppGlobal.get_ex_uint64(amm_app, Bytes(b"reserve_b"))
        assert reserve_a_exists and reserve_b_exists, "AMM state not found"

        # Price = reserve_b / reserve_a (as a ratio in base units)
        # Return reserve_b per 1 unit of reserve_a (scaled by 10^6 for precision)
        high, low = op.mulw(reserve_b, UInt64(1_000_000))
        q_hi, price_scaled, r_hi, r_lo = op.divmodw(high, low, UInt64(0), reserve_a)
        return price_scaled
```

The `op.AppGlobal.get_ex_uint64` opcode reads another application's global state without calling it. The target app must be in the transaction's foreign apps array. This is a read-only operation --- you cannot modify another app's state, only read it. (See [Resource Usage](https://dev.algorand.co/concepts/smart-contracts/resource-usage/) for foreign reference requirements.)

For operations that need to *modify* another contract's state, use an inner `ApplicationCall`:

```python
        # Call the AMM's swap method from within this contract
        itxn.ApplicationCall(
            app_id=amm_app,
            app_args=[Bytes(b"swap"), ...],  # ARC-4 encoded method call
            assets=[sell_asset],
            fee=UInt64(0),
        ).submit()
```

> **Note:** Cross-contract calls consume opcode budget and count toward the 256 inner transaction limit. Complex multi-contract DeFi protocols (lending → AMM → liquidation) must carefully budget their call depth and opcode usage. The 8-level depth limit means Algorand DeFi compositions are shallower than on Ethereum (which has no depth limit), but this simplicity also eliminates entire classes of reentrancy and composability bugs.

This cross-contract pattern is how production Algorand DeFi protocols work: lending protocols read AMM pool prices to value collateral, liquidation bots call AMM swaps via inner transactions to convert seized collateral, and aggregators route through multiple pools in a single atomic group.

## Summary

In this chapter you learned to:

- Explain the difference between LogicSig contract accounts and delegated signatures, and choose the right mode for a given use case
- Write a LogicSig in Algorand Python using the `@logicsig` decorator and template variables
- Design a hybrid stateful/stateless architecture where LogicSigs enforce rules and smart contracts coordinate shared state
- Implement packed binary box storage using `op.extract` and `op.replace` for efficient on-chain data
- Represent prices as N/D rational numbers and validate them via cross-multiplication
- Build a keeper bot that monitors on-chain state and submits fill transactions
- Compose limit order fills with AMM swaps in a single atomic group for zero-inventory-risk arbitrage
- Apply the LogicSig security checklist: verify close-to, rekey-to, fee, asset amounts, and receiver fields

| Feature Built | New Concepts Introduced |
|--------------|------------------------|
| Limit order LogicSig | Delegated signatures, template variables, `@logicsig` decorator |
| Order book smart contract | Packed binary box storage, `op.extract`/`op.replace` |
| Keeper bot | Off-chain monitoring, permissionless execution, relayer pattern |
| Atomic arbitrage | Multi-transaction group composition, AMM integration |
| Security hardening | LogicSig replay prevention, front-running resistance, stale delegation |

## Exercises

1. **(Apply)** Modify the LogicSig to support "buy limit" orders (the user wants to buy a specific ASA when the price drops below a threshold) instead of only sell orders. What fields in the LogicSig validation logic need to change?

2. **(Analyze)** Two keepers submit fills for the same order simultaneously. Trace what happens at the protocol level. Why is this safe --- why can't the order be double-filled?

3. **(Create)** Design a "stop-loss" order type where Alice's tokens are sold if the AMM price drops below a threshold. What changes to the LogicSig and order book contract are needed? How does the keeper determine when to trigger the stop-loss?

## Appendix A: New Concepts Introduced in This Project

See [Logic Signatures](https://dev.algorand.co/concepts/smart-contracts/logic-sigs/) for the official reference on all LogicSig concepts below.

| Concept | Where it appears | Why it matters |
|---------|-----------------|---------------|
| LogicSig (smart signature) | Limit order authorization | Stateless transaction validation --- the other half of Algorand's smart layer |
| Delegated signature mode | User signs LogicSig for keeper use | Enables permissionless execution of user intents |
| Contract account mode | Mentioned for comparison | LogicSig-based escrow (less common since inner txns) |
| Template variables | Order parameters in LogicSig | Parameterized programs without runtime arguments |
| `@logicsig` decorator | Algorand Python LogicSig definition | PuyaPy compiles to smart signature TEAL |
| `compile_logicsig()` | Client-side compilation with parameters | Produces unique program per order |
| Packed binary box storage | Order data in 128-byte blobs | Efficient storage with `op.extract`/`op.replace` |
| `op.extract`, `op.replace` | Reading/writing packed fields | Low-level byte manipulation for box data |
| Keeper/relayer pattern | Off-chain bot executing fills | Permissionless market-making infrastructure |
| N/D rational prices | Cross-multiplication price checks | Integer-only price representation |
| Atomic arbitrage | Keeper fills order + swaps on AMM | Zero-inventory-risk market making |
| `gtxn.Transaction(n)` field access | LogicSig inspecting grouped transactions | Cross-transaction validation in stateless programs |
| LogicSig opcode pooling | Background (20,000 per txn) | Sets up the ZK verification pattern in Project 4 |

## Appendix B: LogicSig vs Smart Contract Decision Matrix

See [Smart Contracts Overview](https://dev.algorand.co/concepts/smart-contracts/overview/) and [Logic Signatures](https://dev.algorand.co/concepts/smart-contracts/logic-sigs/) for the capabilities and constraints of each.

| Use case | Recommendation | Rationale |
|----------|---------------|-----------|
| DEX pool / AMM | Smart contract | Needs state (reserves, LP supply) |
| Limit order rules | LogicSig (delegated) | Stateless, per-user, parameterized |
| Order book tracking | Smart contract | Needs shared mutable state |
| ZK proof verification | LogicSig (contract account) | Needs 20,000 opcode budget |
| Recurring payments | LogicSig (delegated) | Simple, no state needed |
| Escrow / treasury | Smart contract | Inner transactions preferred |
| Fee sponsorship | LogicSig (contract account) | Simple conditional payment |
| Multi-sig governance | Smart contract | Needs state for proposal tracking |

## Appendix C: Resources

| Resource | URL |
|----------|-----|
| Logic Signatures | [dev.algorand.co/concepts/smart-contracts/logic-sigs/](https://dev.algorand.co/concepts/smart-contracts/logic-sigs/) |
| Algorand Python Compilation | [dev.algorand.co/algokit/languages/python/lg-compile/](https://dev.algorand.co/algokit/languages/python/lg-compile/) |
| Algorand Python Operations | [dev.algorand.co/algokit/languages/python/lg-ops/](https://dev.algorand.co/algokit/languages/python/lg-ops/) |
| Opcode Budget Management | [dev.algorand.co/algokit/languages/python/lg-opcode-budget/](https://dev.algorand.co/algokit/languages/python/lg-opcode-budget/) |
| Transaction Reference | [dev.algorand.co/concepts/transactions/reference/](https://dev.algorand.co/concepts/transactions/reference/) |
| AVM Opcodes | [dev.algorand.co/reference/algorand-teal/opcodes/](https://dev.algorand.co/reference/algorand-teal/opcodes/) |
| SDK: LogicSigAccount | [dev.algorand.co/concepts/smart-contracts/logic-sigs/](https://dev.algorand.co/concepts/smart-contracts/logic-sigs/) |
| AVM specification | [dev.algorand.co/concepts/smart-contracts/avm/](https://dev.algorand.co/concepts/smart-contracts/avm/) |

## Before You Continue

Before starting the next chapter, you should be able to:

- [ ] Write a LogicSig in Algorand Python using the `@logicsig` decorator
- [ ] Explain the difference between contract account and delegated signature modes
- [ ] Apply the LogicSig security checklist (close-to, rekey-to, fee, receiver, amount)
- [ ] Use template variables to parameterize LogicSig programs
- [ ] Build hybrid architectures combining stateful contracts with stateless LogicSigs
- [ ] Explain LogicSig opcode pooling and the 20,000-opcode budget

If any of these are unclear, revisit the Limit Order Book chapter before proceeding.
