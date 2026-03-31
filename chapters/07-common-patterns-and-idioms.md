\newpage

# Common Patterns and Idioms

The gap between a contract that works on LocalNet and one that users actually want to use is wider than most developers expect. These patterns bridge that gap --- they solve the UX friction, the MBR lifecycle headaches, and the security footguns that separate tutorial code from production code. Each pattern appears in at least one of the projects in this book; here we collect them in one place for reference.


## Pattern 1: Fee Subsidization --- Users Should Not Need Algo Dust

On Algorand, every transaction requires a minimum [fee](https://dev.algorand.co/concepts/transactions/fees/) of 0.001 Algo (1,000 microAlgos). A typical AMM swap involves 2–3 transactions in a group (asset transfer + app call, possibly a second asset transfer for the output). That's 0.002–0.003 Algo per swap. Seems trivial, but for users coming from a CEX with only ASA tokens in their wallet, **having zero Algo is a hard blocker**.

There are several approaches to solving this, each with different tradeoffs.

### Approach A: Fee pooling within the group (most common)

Algorand validates fees at the **group level**, not the individual transaction level. If a group of 3 transactions requires 3 × 1,000 = 3,000 microAlgos total, one transaction can pay 3,000 and the other two can pay 0. The protocol only checks that the sum of fees across the group meets the sum of minimums.

```python
# Client-side: one transaction overpays to cover the group
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()

# Build a group where the app call overpays to cover the asset transfer + inner txn
composer = algorand.new_group()
composer.add_asset_transfer(
    algokit_utils.AssetTransferParams(
        sender=user.address,
        receiver=pool_address,
        asset_id=token_a_id,
        amount=swap_amount,
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(0),  # fee=0
    )
)
composer.add_app_call_method_call(
    app_client.params.call(
        algokit_utils.AppClientMethodCallParams(
            method="swap",
            args=[min_output],
            static_fee=algokit_utils.AlgoAmount.from_micro_algo(3000),  # Covers group + inner txn
        )
    )
)
composer.send()
```

This is what "always set inner transaction fees to zero" relies on. The user's outer app call overpays enough to cover the inner asset transfer the contract sends back. The total fee math is:

```
sum(all outer fees) >= num_outer_txns × min_fee + num_inner_txns × min_fee
```

So for a swap (1 asset transfer + 1 app call + 1 inner asset transfer back):

```
total_fee_needed = 3 × 1,000 = 3,000 microAlgos
```

The user's app call pays 3,000; the asset transfer pays 0; the inner transaction pays 0. Everyone's happy.

### Approach B: Deducting fees from swap output

The protocol deducts the equivalent of the user's transaction fee cost from whatever tokens they're receiving. The user still pays the on-chain fee in Algo, but the frontend calculates a "net output" that accounts for the cost. A more sophisticated version: the contract itself keeps a small operational fee in the output asset.

```python
# In the contract swap method:
@arc4.abimethod
def swap(
    self,
    input_txn: gtxn.AssetTransferTransaction,
    min_output: UInt64,
) -> UInt64:
    # ... standard swap calculation ...
    output_amount = calculated_output

    # Deduct a small protocol fee (separate from the 0.3% swap fee)
    # This accumulates in the contract for operational costs (MBR, etc.)
    protocol_fee = output_amount * UInt64(1) // UInt64(10000)  # 0.01%
    net_output = output_amount - protocol_fee

    assert net_output >= min_output
    # ... send net_output to user ...
```

This pattern is used by protocols that want to build up an operational treasury to fund MBR, cover infrastructure costs, or subsidize future user fees. The key insight: the user is already making a trade and expecting some fee --- adding a tiny operational fee on top is barely noticeable but compounds into real operational runway.

### Approach C: Sponsored transactions via a relayer

A backend service (the "relayer") co-signs and pays for transactions on behalf of users. The user signs only the application-specific transactions; the relayer adds a funding payment to cover all fees. This requires the relayer to be part of the atomic group.

```python
# Relayer adds a payment transaction to the group that covers all fees
# Group structure:
# [0] Relayer -> Pool: Payment covering all fees    -- signed by relayer
# [1] User -> Pool: Asset transfer (fee=0)          -- signed by user
# [2] User -> Pool: App call to swap (fee=0)        -- signed by user

# The relayer's payment transaction overpays its own fee
# to cover transactions [1], [2], and any inner transactions
relayer_txn = algorand.create_transaction.payment(
    algokit_utils.PaymentParams(
        sender=relayer.address,
        receiver=relayer.address,  # Self-payment (or to pool for MBR)
        amount=algokit_utils.AlgoAmount.from_micro_algo(0),
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(4000),  # Covers all 3 outer + 1 inner
    )
)
```

The user experience becomes: sign one or two transactions, pay zero Algo. The relayer bears the cost and recoups it through swap fees, a subscription model, or protocol treasury.

**How Tinyman and Pact handle this in practice:** Their SDKs compose the transaction group client-side and consolidate all fees into a single overpaying transaction. The user's wallet shows one total fee for the entire operation. The SDK handles the arithmetic of "how many inner transactions does this operation trigger" and sets the fee accordingly.

### Approach D: LogicSig-based fee delegation

A LogicSig (Logic Signature) is a program that authorizes transactions without a private key signature. A sponsor can create a delegated LogicSig that approves fee payments for specific contract interactions:

```python
from algopy import (
    Application, Global, TransactionType, Txn, UInt64,
    gtxn, logicsig, TemplateVar,
)

# LogicSig program: "I authorize payment transactions that:"
# - Are payment type (not asset transfer, not app call)
# - Have amount = 0 (just fee coverage, no value transfer)
# - Are grouped with a call to pool app ID X
# - Have fee below 10,000 microAlgos (cap exposure)
# - Cannot close out balance, rekey, or be used in unexpected groups

@logicsig
def fee_sponsor() -> bool:
    POOL_APP_ID = TemplateVar[UInt64]("POOL_APP_ID")

    # --- Security checks (mandatory for every LogicSig) ---
    assert Txn.close_remainder_to == Global.zero_address
    assert Txn.rekey_to == Global.zero_address
    assert Global.group_size == UInt64(2)

    # --- Business logic ---
    assert Txn.type_enum == TransactionType.Payment
    assert Txn.amount == 0
    assert Txn.fee < UInt64(10000)
    assert gtxn.Transaction(1).app_id == Application(POOL_APP_ID)
    return True
```

The LogicSig account needs to be pre-funded with Algo. Anyone can submit transactions authorized by the LogicSig as long as they satisfy its conditions. This enables gasless transactions without an always-online relayer --- the funded LogicSig account acts as an autonomous fee sponsor.

**Security consideration:** Carefully constrain what the LogicSig approves. An overly permissive LogicSig can be drained by crafting transactions that technically satisfy its conditions but weren't intended. Always cap the fee, restrict the group structure, and verify the target application.

### Approach E: "Algo-less" swaps via intermediary

The most user-friendly pattern for users who have zero Algo but hold ASA tokens. The protocol runs a service that:

1. User submits a signed asset transfer of their ASA tokens to the relayer
2. Relayer wraps this in a group: relayer funds the user with just enough Algo for fees, user's asset transfer executes, app call executes
3. The "loan" of Algo for fees is repaid implicitly by the swap output --- the relayer takes a slightly larger cut of the output

This is architecturally complex but provides the best UX for onboarding users who arrive with only bridged tokens and no native Algo.

We used Approach A in the vesting contract's `initialize` method (Chapter 3) and the AMM's `swap` method (Chapter 5). The keeper bot in Chapter 8 uses Approach C (relayer).


## Pattern 2: The "Fund-Then-Call" Atomic Group

Almost every DeFi interaction on Algorand follows this pattern: the user sends assets to the contract in one transaction and calls the contract method in another, all within an atomic group. The contract verifies the transfer happened by inspecting the group transaction.

```python
# Contract verifies the preceding transaction in the group
@arc4.abimethod
def deposit(
    self,
    payment_txn: gtxn.PaymentTransaction,  # Type-checked by ABI router
) -> None:
    # The gtxn parameter type tells the ABI router to expect a payment
    # transaction at the corresponding position in the group.
    # PuyaPy automatically validates:
    #   - The transaction IS a payment type
    #   - It's in the correct group position

    # YOU must still validate the critical fields:
    assert payment_txn.receiver == Global.current_application_address
    assert payment_txn.amount >= UInt64(100_000)
```

The `gtxn.AssetTransferTransaction` and `gtxn.PaymentTransaction` parameter types in Algorand Python are powerful --- they give you type-safe access to the grouped transaction's fields and the ABI router validates the transaction type automatically. But **you must still validate receiver, amount, and asset ID yourself**. The type check doesn't verify the *contents*, only the *type*. (See [Transaction Types](https://dev.algorand.co/concepts/transactions/types/) for field definitions.)

**Why not just have the contract pull assets directly?** Because Algorand's security model requires the asset holder to sign the transfer. The contract cannot unilaterally debit a user's account (unless the user previously granted approval via a delegated LogicSig, which is rare). This "push" model --- user pushes assets, then tells the contract what to do --- is fundamental to Algorand's design.

Every `deposit_tokens`, `create_schedule`, and `add_liquidity` call in Chapters 2 and 3 follows this pattern.


## Pattern 3: The Escrow Contract Account Pattern

Every Algorand application has a deterministic address derived from its app ID. This address acts as an autonomous escrow --- it can hold Algos and ASAs, and the contract logic governs all outflows via inner transactions.

```python
# The contract's address is:
# SHA512_256("appID" + big_endian_8_byte(app_id))
# Available in-contract as:
contract_address = Global.current_application_address

# Fund the escrow as part of deployment:
# Client sends Algo to this address to cover MBR for:
#   Account minimum balance:     100,000 μAlgo
#   Each ASA opt-in:             100,000 μAlgo each
#   Each box:                    2,500 + 400 × (name_len + data_size) μAlgo
#   Buffer for safety:           ~50,000 μAlgo
```

**The key insight:** The contract address has no private key. Nobody can sign transactions from it directly. The *only* way assets leave this address is through inner transactions approved by the contract logic. This is what makes it trustless --- the code is the sole custodian. If the contract is immutable (UpdateApplication rejected), then the rules governing this escrow can never change. (See [Lifecycle](https://dev.algorand.co/concepts/smart-contracts/lifecycle/).)

**Practical tip:** Calculate the total MBR needed at deployment and fund the contract account in the same atomic group as the `create_application` call. If you fund it separately, there's a window where the contract exists but can't operate. Here's a typical bootstrap group:

```
Group:
[0] Creator -> Contract: Payment of 0.6 Algo (MBR funding)
[1] Creator -> Contract: App call to bootstrap(asset_a, asset_b)
    ↳ Inner: Contract creates LP token
    ↳ Inner: Contract opts into asset_a
    ↳ Inner: Contract opts into asset_b
```

Both the vesting contract (Chapter 3) and the AMM pool (Chapter 5) use this escrow pattern. The limit order system (Chapter 8) adds a second layer: the LogicSig contract account is also an escrow, but governed by a program instead of an application.


## Pattern 4: MBR Funding as Part of User Operations

*Before reading on, consider: when a user action requires the contract to create a new box (increasing its MBR), who should pay for it? The user (who benefits from the data), the admin (who deployed the contract), or the contract itself (from its reserves)? What are the tradeoffs of each approach?*

When a user's action requires the contract to allocate new storage (creating a box, opting into an asset), someone must fund the MBR increase. The clean pattern is to require the user to send the MBR payment as part of the atomic group:

```python
@arc4.abimethod
def register_position(
    self,
    mbr_payment: gtxn.PaymentTransaction,
) -> None:
    # Calculate the cost for the user's position box
    # Box name: 32 bytes (sender address), Box data: 64 bytes (position struct)
    box_cost = UInt64(2500) + UInt64(400) * (UInt64(32) + UInt64(64))

    assert mbr_payment.receiver == Global.current_application_address
    assert mbr_payment.amount >= box_cost

    # Now create the box --- contract has sufficient MBR
    self.positions[arc4.Address(Txn.sender)] = Position(...)  # BoxMap write
```

This keeps the contract's MBR accounting clean: users pay for the storage they consume. The contract never needs to dip into its own reserves for user-initiated storage. (See [Protocol Parameters](https://dev.algorand.co/concepts/protocol/protocol-parameters/) for the complete MBR schedule.)


## Pattern 5: MBR Refund on Cleanup

The complement to Pattern 4. When a user closes their position and the box is deleted, the freed MBR should be returned:

```python
@arc4.abimethod
def close_position(self) -> None:
    sender = arc4.Address(Txn.sender)
    assert sender in self.positions

    # Read position data before deletion
    position = self.positions[sender]

    # Delete the box --- this frees MBR in the contract's balance
    del self.positions[sender]

    # Calculate and refund the freed MBR to the user
    box_cost = UInt64(2500) + UInt64(400) * (UInt64(32) + UInt64(64))
    itxn.Payment(
        receiver=Txn.sender,
        amount=box_cost,
        fee=UInt64(0),
    ).submit()

    # ... also return any held assets to the user ...
```

This creates a complete lifecycle: user pays MBR on entry, gets it back on exit. It's the Algorand equivalent of Ethereum's gas refund for clearing storage slots, except it's explicit, deterministic, and the user gets real Algo back rather than a gas discount. Users appreciate getting their deposit back --- it signals a well-designed protocol. (See [Accounts Overview](https://dev.algorand.co/concepts/accounts/overview/) for MBR mechanics.)

The vesting contract's `cleanup_schedule` method (Chapter 3) implements this pattern.


## Pattern 6: Canonical Asset Ordering to Prevent Duplicate Pools

Two users could create pools for the same pair but with assets swapped (Token A/Token B vs Token B/Token A). Without enforcement, you'd get fragmented liquidity across duplicate pools. Enforce canonical ordering:

```python
@arc4.abimethod
def bootstrap(self, asset_a: Asset, asset_b: Asset) -> UInt64:
    # ALWAYS enforce lower ID first --- this is deterministic and unique
    assert asset_a.id < asset_b.id, "Assets must be in canonical order (lower ID first)"
    # ...
```

In the factory contract, use the ordered pair as the box key for O(1) pool lookup:

```python
# Factory: store pool reference keyed by canonical pair
pair_key = op.itob(asset_a.id) + op.itob(asset_b.id)  # 16 bytes, unique
assert pair_key not in self.pools, "Pool already exists for this pair"
self.pools[pair_key] = op.itob(new_pool_app_id)
```

**Client-side helper:** Your SDK should sort the pair before any pool interaction:

```python
def get_pool(asset_x: int, asset_y: int) -> int:
    a, b = sorted([asset_x, asset_y])  # Canonical order
    result = factory_client.send.call(
        algokit_utils.AppClientMethodCallParams(method="get_pool", args=[a, b])
    )
    return result.abi_return
```

This pattern applies everywhere pairs appear: LP token names (`"LP-{min_id}-{max_id}"`), analytics keys, router lookups. (See [Assets Overview](https://dev.algorand.co/concepts/assets/overview/) for ASA ID assignment.)

The AMM's `bootstrap` method (Chapter 5) enforces `asset_a.id < asset_b.id` for exactly this reason.


*Before reading on: your AMM contract needs to send LP tokens to liquidity providers, but they might not have opted into the LP token yet. How would you handle this? Should the contract check and fail, or should it handle the opt-in automatically?*

## Pattern 7: The "Opt-In Gate" --- Lazy vs Eager Asset Opt-In

Users must opt into the LP token before they can receive it. Two approaches:

### Eager (user opts in first)

The user opts into the LP token in a transaction preceding the add-liquidity call. The contract verifies they're already opted in before sending LP tokens. Simple and explicit.

```
Group:
[0] User -> User: ASA opt-in to LP token (0-amount self-transfer)
[1] User -> Pool: Asset A transfer
[2] User -> Pool: Asset B transfer
[3] User -> Pool: App call to add_liquidity
    ↳ Inner: Contract sends LP tokens to user (works because [0] happened)
```

### Lazy (let the failure be the message)

Skip the explicit opt-in verification in the contract. If the user isn't opted in, the inner transaction sending LP tokens will fail, and the entire group rolls back atomically. The error message from algod will indicate the opt-in issue, and the frontend can prompt the user.

The lazy approach saves a few lines of contract code but produces a worse error message. For production, **eager with the opt-in in the same group** is preferred --- the user sees one "Confirm" prompt in their wallet for the whole operation. (See [Asset Operations](https://dev.algorand.co/concepts/assets/asset-operations/) for the opt-in mechanism.)

### Contract-initiated opt-in (for the contract itself)

When the contract needs to opt into a new asset (e.g., during bootstrap), it does so via inner transaction. This is the only case where opt-in happens autonomously:

```python
# Contract opts itself into an asset
itxn.AssetTransfer(
    xfer_asset=asset,
    asset_receiver=Global.current_application_address,
    asset_amount=UInt64(0),  # 0-amount self-transfer = opt-in
    fee=UInt64(0),
).submit()
```


## Pattern 8: Subroutine Extraction for Opcode Efficiency and Readability

In Algorand Python, use `@subroutine` for shared logic that should be compiled to a single TEAL subroutine and called from multiple methods. Without this, the compiler inlines the code at every call site, bloating program size.

```python
from algopy import Global, UInt64, gtxn, subroutine

@subroutine
def calculate_output(
    input_amount: UInt64,
    reserve_in: UInt64,
    reserve_out: UInt64,
) -> UInt64:
    """Constant product swap output with 0.3% fee."""
    input_with_fee = input_amount * UInt64(997)
    numerator = input_with_fee * reserve_out
    denominator = reserve_in * UInt64(1000) + input_with_fee
    return numerator // denominator

```

Subroutines compile to TEAL `callsub`/`retsub` instructions. For an AMM with swap, add-liquidity, and remove-liquidity all needing the same output calculation, extracting it to a subroutine saves significant program bytes. Given the 8KB program size limit, this matters. (See [Algorand Python structure guide](https://dev.algorand.co/algokit/languages/python/lg-structure/) for subroutine best practices.)

**When to subroutine vs inline:**
- **Subroutine:** Logic used in 2+ methods, or logic longer than ~10 TEAL instructions
- **Inline:** Short expressions used once, or where the overhead of `callsub`/`retsub` (stack management) exceeds the savings


## Pattern 9: Opcode Budget Management for Complex Operations

If a single operation needs more than 700 opcodes (the per-call budget), you have two options:

### Option A: Pad with dummy app calls in the group

Each additional app call in the group adds 700 to the pooled budget. The "dummy" calls can be bare NoOp calls to your own contract that do nothing:

```python
@arc4.baremethod(allow_actions=["NoOp"])
def noop(self) -> None:
    """Budget padding --- does nothing but adds 700 opcodes to pool."""
    pass
```

Client-side, prepend the group with as many NoOp calls as needed:

```python
# Need ~2,800 opcodes? Add 3 extra NoOp calls (4 × 700 = 2,800)
group = [
    app_call(method="noop"),   # +700
    app_call(method="noop"),   # +700
    app_call(method="noop"),   # +700
    asset_transfer(...),       # The actual input
    app_call(method="swap"),   # +700, runs the real logic
]
```

### Option B: Use `ensure_budget()` in Algorand Python

This is the cleaner approach --- the compiler automatically issues inner app calls to pad the budget:

```python
from algopy import OpUpFeeSource, ensure_budget

@arc4.abimethod
def complex_operation(self) -> None:
    # Request 2,800 opcodes minimum available
    # PuyaPy inserts inner app calls as needed to reach this budget
    ensure_budget(2800, OpUpFeeSource.GroupCredit)

    # ... expensive computation that needs the extra budget ...
```

The second parameter controls the fee source (`OpUpFeeSource.GroupCredit` = caller-funded via fee pooling, `OpUpFeeSource.AppAccount` = from contract balance). Always use `GroupCredit` and have the caller overpay fees. The caller's fee must account for the extra inner transactions that `ensure_budget` generates. (See [Algorand Python opcode budget guide](https://dev.algorand.co/algokit/languages/python/lg-opcode-budget/).)

**How many opcodes does your AMM need?** A standard constant product swap with fee calculation, safety checks, and one inner transaction typically fits within 700 opcodes. Add-liquidity with the square root calculation for initial minting may need ~1,400. Budget padding is more commonly needed for operations involving multiple box reads/writes or cryptographic operations.


## Pattern 10: Emitting Events via Logs for Off-Chain Indexing

Algorand doesn't have Ethereum-style events, but you can emit structured data by logging from your contract. Indexers and off-chain services parse these logs to build analytics, trigger notifications, or update UI state.

```python
@arc4.abimethod
def swap(self, ...) -> UInt64:
    # ... swap logic ...

    # Emit an ARC-28 event for indexers.
    # arc4.emit() computes the 4-byte selector (SHA-512/256 of the event
    # signature) and ARC-4-encodes the arguments automatically.
    arc4.emit(
        "Swap(address,uint64,uint64,uint64,uint64)",
        arc4.Address(Txn.sender),
        arc4.UInt64(input_amount),
        arc4.UInt64(output_amount),
        arc4.UInt64(self.reserve_a.value),
        arc4.UInt64(self.reserve_b.value),
    )

    return output_amount
```

**Note on ARC-4 return values:** When you return a value from an `@arc4.abimethod`, PuyaPy automatically logs it with the `0x151f7c75` prefix. `arc4.emit()` produces separate log entries with ARC-28-compliant selectors. Indexers can distinguish return values from event logs by checking the prefix.

For production, follow the [ARC-28 event specification](https://dev.algorand.co/arc-standards/arc-0028/) for standardized event definitions and parsing across the ecosystem.

Here is how to read those events from the Algorand Indexer, the off-chain service that indexes all on-chain data into a searchable REST API:

```python
import base64
import requests

# Search for all swap events from our AMM (by application ID)
indexer_url = "http://localhost:8980"  # LocalNet indexer
response = requests.get(
    f"{indexer_url}/v2/transactions",
    params={
        "application-id": pool_app_id,
        "tx-type": "appl",
        "limit": 10,
    },
)

for txn in response.json().get("transactions", []):
    # Each app call transaction includes logs
    logs = txn.get("logs", [])
    for log in logs:
        # Decode base64 log entry
        raw = base64.b64decode(log)
        # Check for our "swap" event prefix
        if raw[:4] == b"swap":
            input_amount = int.from_bytes(raw[4:12], "big")
            output_amount = int.from_bytes(raw[12:20], "big")
            print(f"Swap: {input_amount} in → {output_amount} out")
```

For production, use Nodely's indexer at `https://mainnet-idx.4160.nodely.dev` (free tier, no API key). The indexer supports filtering by time range (`after-time`, `before-time`), round range (`min-round`, `max-round`), and sender address. Pagination uses cursor-based `next` tokens for efficient traversal of large result sets.


## Pattern 11: Reserve Tracking vs Balance Reading

Your AMM tracks reserves in global state (`self.reserve_a`, `self.reserve_b`). An alternative design reads the contract's actual asset balances each time. Both approaches have tradeoffs:

### Tracked reserves (recommended, used in this book)

```python
# Update reserves explicitly after each operation
self.reserve_a.value = self.reserve_a.value + input_amount
self.reserve_b.value = self.reserve_b.value - output_amount
```

**Pros:** Deterministic, no surprises. The contract's accounting is self-consistent. You know exactly what the contract considers its reserves to be.

**Cons:** If someone sends tokens to the contract outside of the defined methods (a "donation" or accident), the reserves don't reflect the actual balance. Those tokens are effectively stuck.

### Balance reading (Uniswap V2 style)

```python
# Read actual balance, calculate delta
actual_balance = asset.balance(Global.current_application_address)
input_amount = actual_balance - last_known_reserve
```

**Pros:** Automatically accounts for any tokens sent to the contract, including donations. Enables flash-loan patterns where tokens are borrowed and returned in the same transaction.

**Cons:** More complex, requires careful handling of the "sync" between actual balance and expected reserves. On Algorand, reading asset holdings requires the account and asset to be in the foreign arrays, consuming reference slots.

**For this book, tracked reserves are simpler and sufficient.** Uniswap V2's balance-reading pattern is more relevant in environments with flash loans. If you later want to add flash swaps, you'd switch to balance reading. (See [Global Storage](https://dev.algorand.co/concepts/smart-contracts/storage/global/) for how tracked reserves are persisted.)


## Pattern 12: Client-Side Quote Calculation

Never call the contract on-chain just to get a price quote. Calculate swap outputs client-side using the same formula, reading the reserves from the contract's global state:

```python
# Client-side (Python SDK)
def get_swap_quote(
    input_amount: int,
    reserve_in: int,
    reserve_out: int,
    fee_bps: int = 30,
) -> dict:
    """Calculate expected swap output without submitting a transaction."""
    fee_factor = 10_000 - fee_bps  # 9970 for 0.3% fee
    input_with_fee = input_amount * fee_factor
    numerator = input_with_fee * reserve_out
    denominator = reserve_in * 10_000 + input_with_fee
    output = numerator // denominator

    # Price impact = how much the price moves due to this trade
    spot_price = reserve_out / reserve_in
    effective_price = output / input_amount if input_amount > 0 else 0
    price_impact = abs(spot_price - effective_price) / spot_price

    return {
        "output": output,
        "min_output": output * 995 // 1000,  # 0.5% slippage default
        "price_impact": price_impact,
        "fee_paid": input_amount * fee_bps // 10_000,
    }

# Read reserves from global state (free, no transaction needed).
# AlgoKit Utils provides a typed state reader:
state = app_client.get_global_state()
reserve_a = state["reserve_a"]
reserve_b = state["reserve_b"]

quote = get_swap_quote(1_000_000, reserve_a, reserve_b)
print(f"Expected output: {quote['output']}")
print(f"Price impact: {quote['price_impact']:.4%}")
```

Reading global state is a free API call to any algod node --- no transaction, no fee. This is how frontends display real-time quotes and price impact warnings. (See [App Client](https://dev.algorand.co/algokit/utils/python/app-client/) for AlgoKit Utils state reading.)

**Multi-hop routing.** When no direct pool exists for a pair (e.g., TOKEN\_A/TOKEN\_B), the swap can be routed through an intermediate asset: TOKEN\_A → ALGO → TOKEN\_B. On Algorand, this is a single atomic group containing two swap app calls (one per pool). The client computes the optimal route by comparing output across all available paths. DEX aggregators like Vestige and Deflex automate this for users. Building a multi-hop router is one of the best exercises for mastering atomic group composition.


## Before You Continue

Before starting the next chapter, you should be able to:

- [ ] Implement a complete smart contract with state management, inner transactions, and security checks
- [ ] Explain the constant product invariant and how swaps, minting, and burning maintain it
- [ ] Use atomic groups to coordinate multi-step DeFi operations
- [ ] Apply fee pooling so inner transactions never pay fees from the contract's balance
- [ ] Manage MBR lifecycle: fund on creation, refund on cleanup
- [ ] Implement canonical asset ordering and explain why it prevents duplicate pools

If any of these are unclear, revisit the AMM chapter or the Patterns chapter before proceeding.
