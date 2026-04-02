\newpage



\part{Appendices}

The appendices provide lasting reference value. The Cookbook contains 50+ standalone code examples organized by topic, and the Gotchas Cheat Sheet catalogs the most common mistakes and how to avoid them.

# Algorand Smart Contract Cookbook

**50+ minimal, self-contained examples demonstrating every major Algorand smart contract concept. Each example is the smallest possible program that illustrates one idea. Use this as a reference while working through Projects 1–3.**

All examples use **Algorand Python (Puya)** and target **AVM v12**. Each can be compiled with `puyapy` and tested on LocalNet.


## Table of Contents

1. [Contract basics](#1-contract-basics)
2. [ABI methods and routing](#2-abi-methods-and-routing)
3. [Types and arithmetic](#3-types-and-arithmetic)
4. [Global state](#4-global-state)
5. [Local state](#5-local-state)
6. [Box storage](#6-box-storage)
7. [Assets (ASAs)](#7-assets-asas)
8. [Inner transactions](#8-inner-transactions)
9. [Group transactions](#9-group-transactions)
10. [Logic signatures](#10-logic-signatures)
11. [Authorization and security](#11-authorization-and-security)
12. [Subroutines and code organization](#12-subroutines-and-code-organization)
13. [ARC-4 encoding and types](#13-arc-4-encoding-and-types)
14. [Cryptographic operations](#14-cryptographic-operations)
15. [Opcode budget and resource management](#15-opcode-budget-and-resource-management)
16. [Compilation and deployment](#16-compilation-and-deployment)


## 1. Contract Basics {#1-contract-basics}

(See [Smart Contracts Overview](https://dev.algorand.co/concepts/smart-contracts/overview/).)

### 1.1 --- The absolute minimum contract

```python
from algopy import ARC4Contract, arc4

class MinimalContract(ARC4Contract):
    @arc4.abimethod
    def hello(self, name: arc4.String) -> arc4.String:
        return "Hello, " + name
```

This compiles to an approval program with an ARC-4 method router and a default clear state program that returns true. The method selector is the first 4 bytes of `SHA512_256("hello(string)string")`.

### 1.2 --- Contract with `__init__` (runs once on creation)

```python
from algopy import ARC4Contract, GlobalState, UInt64, arc4

class WithInit(ARC4Contract):
    def __init__(self) -> None:
        # Runs exactly ONCE when the app is first created
        self.counter = GlobalState(UInt64(0))
        self.initialized = GlobalState(UInt64(1))

    @arc4.abimethod
    def get_counter(self) -> UInt64:
        return self.counter.value
```

`__init__` maps to the `create` application call. It never runs again.

### 1.3 --- Non-ARC4 contract (raw approval/clear programs)

```python
from algopy import Contract, UInt64

class RawContract(Contract):
    def approval_program(self) -> UInt64:
        return UInt64(1)  # Always approve

    def clear_state_program(self) -> UInt64:
        return UInt64(1)  # Always approve
```

Use `Contract` instead of `ARC4Contract` when you need full control over the approval program without ABI routing. Rarely needed.

### 1.4 --- Immutable contract (reject update and delete)

```python
from algopy import ARC4Contract, arc4

class ImmutableContract(ARC4Contract):
    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject(self) -> None:
        assert False, "Immutable"

    @arc4.abimethod
    def do_something(self) -> None:
        pass
```

AlgoKit templates are immutable by default. Always do this for production contracts.


## 2. ABI Methods and Routing {#2-abi-methods-and-routing}

(See [ABI](https://dev.algorand.co/concepts/smart-contracts/abi/).)

### 2.1 --- Multiple methods with different signatures

```python
from algopy import ARC4Contract, UInt64, arc4

class Calculator(ARC4Contract):
    @arc4.abimethod
    def add(self, a: UInt64, b: UInt64) -> UInt64:
        return a + b

    @arc4.abimethod
    def multiply(self, a: UInt64, b: UInt64) -> UInt64:
        return a * b
```

Each method gets a unique 4-byte selector. The router dispatches based on `ApplicationArgs[0]`.

### 2.2 --- Read-only method (no state changes)

```python
from algopy import ARC4Contract, UInt64, GlobalState, arc4

class ReadOnlyExample(ARC4Contract):
    def __init__(self) -> None:
        self.value = GlobalState(UInt64(42))

    @arc4.abimethod(readonly=True)
    def get_value(self) -> UInt64:
        return self.value.value
```

`readonly=True` signals to clients that this method doesn't modify state. Clients can use `simulate` instead of submitting a real transaction.

### 2.3 --- Bare methods (no ABI args, matched by OnComplete)

```python
from algopy import ARC4Contract, arc4

class BareMethodExample(ARC4Contract):
    @arc4.baremethod(allow_actions=["OptIn"])
    def opt_in(self) -> None:
        # Runs when a user opts into this app
        pass

    @arc4.baremethod(allow_actions=["CloseOut"])
    def close_out(self) -> None:
        # Runs when a user closes out of this app
        pass

    @arc4.baremethod(create="require")
    def create(self) -> None:
        # Runs only on app creation (bare NoOp with create flag)
        pass
```

Bare methods have no ABI arguments. They match on `OnCompletion` action type.

### 2.4 --- Method that allows multiple OnComplete actions

```python
from algopy import ARC4Contract, OnCompleteAction, Txn, arc4

class MultiAction(ARC4Contract):
    @arc4.abimethod(allow_actions=["NoOp", "OptIn"])
    def register(self) -> None:
        # This method works for both regular calls and opt-in calls
        if Txn.on_completion == OnCompleteAction.OptIn:
            pass  # Handle opt-in logic
```


## 3. Types and Arithmetic {#3-types-and-arithmetic}

(See [Algorand Python types](https://dev.algorand.co/algokit/languages/python/lg-types/).)

### 3.1 --- Native types: UInt64 and Bytes

```python
from algopy import ARC4Contract, Bytes, UInt64, arc4

class NativeTypes(ARC4Contract):
    @arc4.abimethod
    def uint_ops(self) -> UInt64:
        a = UInt64(100)
        b = UInt64(3)
        return a + b      # 103
        # a - b            # 97  (panics if result < 0)
        # a * b            # 300 (panics on overflow)
        # a // b           # 33  (floor division)
        # a % b            # 1   (modulo)

    @arc4.abimethod
    def bytes_ops(self) -> Bytes:
        a = Bytes(b"hello")
        b = Bytes(b" world")
        return a + b  # b"hello world" (concatenation)
```

The AVM has exactly two native types. Everything else is built on top of these.

### 3.2 --- BigUInt: up to 512-bit integers

> **When to use BigUInt vs wide arithmetic (3.3):** Use `BigUInt` when the *result itself* must exceed 64 bits (e.g., cumulative accumulators like TWAP that grow unboundedly). Use `mulw`/`divmodw` (Recipe 3.3) when the final result fits in 64 bits but an intermediate product might overflow (e.g., proportional calculations like `a * b / c`).

```python
from algopy import ARC4Contract, BigUInt, UInt64, arc4, op

class BigMath(ARC4Contract):
    @arc4.abimethod
    def safe_multiply(self, a: UInt64, b: UInt64) -> UInt64:
        # UInt64 * UInt64 can overflow. Use BigUInt for intermediate:
        big_a = BigUInt(a)
        big_b = BigUInt(b)
        result = big_a * big_b  # Up to 512-bit result
        # Divide back down to UInt64 range:
        return op.btoi((result // BigUInt(1000)).bytes)
```

### 3.3 --- Wide arithmetic opcodes (128-bit intermediate)

```python
from algopy import ARC4Contract, UInt64, arc4, op

class WideArith(ARC4Contract):
    @arc4.abimethod
    def wide_multiply_then_divide(
        self, a: UInt64, b: UInt64, divisor: UInt64
    ) -> UInt64:
        # (a * b) / divisor without overflow
        # op.mulw returns (high, low) of 128-bit product
        high, low = op.mulw(a, b)
        # op.divmodw divides 128-bit by 64-bit
        q_hi, result, r_hi, r_lo = op.divmodw(high, low, UInt64(0), divisor)
        return result
```

Essential for AMM math where reserve products overflow uint64.

### 3.4 --- Boolean logic

```python
from algopy import ARC4Contract, UInt64, arc4

class BooleanOps(ARC4Contract):
    @arc4.abimethod
    def check(self, a: UInt64, b: UInt64) -> bool:
        # Standard Python boolean operators work
        return a > UInt64(0) and b > UInt64(0) and a != b
```

`bool` in Algorand Python compiles to UInt64 (0 or 1).


## 4. Global State {#4-global-state}

(See [Global Storage](https://dev.algorand.co/concepts/smart-contracts/storage/global/).)

### 4.1 --- Declaring and using global state

```python
from algopy import ARC4Contract, Bytes, GlobalState, UInt64, arc4

class GlobalStateExample(ARC4Contract):
    def __init__(self) -> None:
        self.count = GlobalState(UInt64(0))
        self.name = GlobalState(Bytes(b"default"))

    @arc4.abimethod
    def increment(self) -> UInt64:
        self.count.value += UInt64(1)
        return self.count.value

    @arc4.abimethod
    def set_name(self, name: Bytes) -> None:
        self.name.value = name
```

Max 64 key-value pairs. Key + value ≤ 128 bytes each. Schema is immutable after creation.

### 4.2 --- Checking if a global state key has a value

```python
from algopy import ARC4Contract, GlobalState, UInt64, arc4

class OptionalState(ARC4Contract):
    def __init__(self) -> None:
        # Initial value type, but no default value set
        self.maybe_set = GlobalState(UInt64)

    @arc4.abimethod
    def set_it(self, val: UInt64) -> None:
        self.maybe_set.value = val

    @arc4.abimethod
    def is_set(self) -> bool:
        # Check if the key exists in state
        return bool(self.maybe_set)
```

### 4.3 --- Reading another app's global state

```python
from algopy import ARC4Contract, Application, Bytes, UInt64, arc4, op

class CrossAppReader(ARC4Contract):
    @arc4.abimethod
    def read_other_app(self, app: Application, key: Bytes) -> UInt64:
        # The target app must be in the foreign apps array
        value, exists = op.AppGlobal.get_ex_uint64(app, key)
        assert exists
        return value
```

Requires the target app ID in the transaction's foreign apps array.


## 5. Local State {#5-local-state}

(See [Local Storage](https://dev.algorand.co/concepts/smart-contracts/storage/local/).)

### 5.1 --- Per-user state with opt-in

> **When to use local state vs box storage (Section 6):** Use local state only for non-critical user preferences or caches --- data where unilateral deletion by the user is acceptable. For financial data, debts, or anything the application must control, use box storage (Section 6). Users can delete their local state via ClearState at any time; they cannot delete boxes.

```python
from algopy import ARC4Contract, LocalState, Txn, UInt64, arc4

class UserScore(ARC4Contract):
    def __init__(self) -> None:
        self.score = LocalState(UInt64)

    @arc4.baremethod(allow_actions=["OptIn"])
    def opt_in(self) -> None:
        self.score[Txn.sender] = UInt64(0)

    @arc4.abimethod
    def add_points(self, points: UInt64) -> UInt64:
        self.score[Txn.sender] += points
        return self.score[Txn.sender]
```

Max 16 key-value pairs per user. Users can clear local state at any time via ClearState (always succeeds). Never use local state as the sole store for critical financial data.

### 5.2 --- Reading another account's local state

```python
from algopy import ARC4Contract, Account, Application, Bytes, UInt64, arc4, op

class LocalReader(ARC4Contract):
    @arc4.abimethod
    def read_user_score(
        self, user: Account, app: Application, key: Bytes
    ) -> UInt64:
        value, exists = op.AppLocal.get_ex_uint64(user, app, key)
        assert exists
        return value
```


## 6. Box Storage {#6-box-storage}

(See [Box Storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/).)

### 6.1 --- Simple named box (Box)

> **When to use Box vs BoxMap (6.2) vs raw box (6.3):** Use `Box` for a single named value (e.g., a config struct). Use `BoxMap` for per-user or per-entity data keyed by address or ID (the most common pattern). Use raw box access (6.3) only when you need byte-level operations (`extract`, `replace`, `splice`) on packed binary data.

```python
from algopy import ARC4Contract, Box, UInt64, arc4

class SimpleBox(ARC4Contract):
    def __init__(self) -> None:
        self.total = Box(UInt64, key=b"total")

    @arc4.abimethod
    def set_total(self, value: UInt64) -> None:
        self.total.value = value

    @arc4.abimethod
    def get_total(self) -> UInt64:
        return self.total.value
```

MBR: `2,500 + 400 × (5 + 8) = 7,700 μAlgo` for this box.

### 6.2 --- Key-value map (BoxMap)

```python
from algopy import ARC4Contract, BoxMap, Txn, UInt64, arc4

class BalanceMap(ARC4Contract):
    def __init__(self) -> None:
        self.balances = BoxMap(arc4.Address, UInt64, key_prefix=b"b_")

    @arc4.abimethod
    def deposit(self, amount: UInt64) -> None:
        sender = arc4.Address(Txn.sender)
        if sender in self.balances:
            self.balances[sender] += amount
        else:
            self.balances[sender] = amount

    @arc4.abimethod
    def get_balance(self) -> UInt64:
        sender = arc4.Address(Txn.sender)
        if sender in self.balances:
            return self.balances[sender]
        return UInt64(0)

    @arc4.abimethod
    def withdraw(self) -> None:
        sender = arc4.Address(Txn.sender)
        assert sender in self.balances
        del self.balances[sender]  # Deletes the box, frees MBR
```

### 6.3 --- Raw box access (Box with low-level methods)

> **Note:** `BoxRef` is deprecated in current PuyaPy (see the `@deprecated` annotation in the [PuyaPy `_box` stubs](https://github.com/algorandfoundation/puya/blob/main/stubs/algopy-stubs/_box.pyi)). Use `Box` instead. Methods like `create`, `extract`, `replace`, `resize`, and `splice` are available directly on `Box`. Deletion uses the property deleter: `del box.value`.

```python
from algopy import ARC4Contract, Box, Bytes, UInt64, arc4

class RawBoxAccess(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(Bytes, key=b"data")

    @arc4.abimethod
    def create_data_box(self) -> None:
        self.data.create(size=UInt64(256))  # 256 bytes, zero-filled

    @arc4.abimethod
    def write_at_offset(self, offset: UInt64, data: Bytes) -> None:
        self.data.replace(offset, data)

    @arc4.abimethod
    def read_at_offset(self, offset: UInt64, length: UInt64) -> Bytes:
        return self.data.extract(offset, length)

    @arc4.abimethod
    def delete_box(self) -> None:
        del self.data.value  # Property deleter removes the box
```

`Box` gives byte-level access via `create`, `extract`, `replace`, `resize`, and `splice`. Essential for packed data structures.

### 6.4 --- Box MBR calculation helper

```python
from algopy import subroutine, UInt64

@subroutine
def box_mbr(name_length: UInt64, data_size: UInt64) -> UInt64:
    """Calculate minimum balance requirement for a box."""
    return UInt64(2500) + UInt64(400) * (name_length + data_size)

# Examples:
# box_mbr(5, 8)    →   7,700 μAlgo  (small counter)
# box_mbr(34, 64)  →  41,700 μAlgo  (per-user record)
# box_mbr(12, 32768)→ 13,114,500 μAlgo (max-size box ≈ 13.1 Algo)
```

### 6.5 --- Box references and I/O budget

```python
# CLIENT-SIDE: you must declare box references in the transaction
# Each reference grants 1KB of I/O budget

# For a box named "data" with 4KB of content:
app_call = transaction.ApplicationCallTxn(
    sender=user,
    sp=sp,
    index=app_id,
    app_args=["read_data"],
    boxes=[
        (app_id, b"data"),  # 1KB budget
        (app_id, b"data"),  # +1KB budget (same box, more budget)
        (app_id, b"data"),  # +1KB budget
        (app_id, b"data"),  # +1KB budget (total: 4KB)
    ],
)
```

Forgetting box references causes "box read/write budget exceeded" errors.


## 7. Assets (ASAs) {#7-assets-asas}

(See [Assets Overview](https://dev.algorand.co/concepts/assets/overview/).)

### 7.1 --- Creating an ASA from a contract

```python
from algopy import ARC4Contract, Global, UInt64, arc4, itxn

class TokenCreator(ARC4Contract):
    @arc4.abimethod
    def create_token(self) -> UInt64:
        result = itxn.AssetConfig(
            asset_name=b"MyToken",
            unit_name=b"MTK",
            total=UInt64(1_000_000_000_000),  # 1M with 6 decimals
            decimals=UInt64(6),
            manager=Global.current_application_address,
            reserve=Global.current_application_address,
            fee=UInt64(0),
        ).submit()
        return result.created_asset.id
```

### 7.2 --- Opting into an ASA (contract opts itself in)

```python
from algopy import ARC4Contract, Asset, Global, UInt64, arc4, itxn

class AssetOptIn(ARC4Contract):
    @arc4.abimethod
    def opt_in_to_asset(self, asset: Asset) -> None:
        itxn.AssetTransfer(
            xfer_asset=asset,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),  # Zero-amount self-transfer = opt-in
            fee=UInt64(0),
        ).submit()
```

Costs 100,000 μAlgo (0.1 Algo) in MBR per asset.

### 7.3 --- Sending an ASA from a contract

```python
from algopy import ARC4Contract, Account, Asset, UInt64, arc4, itxn

class AssetSender(ARC4Contract):
    @arc4.abimethod
    def send_tokens(
        self, receiver: Account, asset: Asset, amount: UInt64
    ) -> None:
        itxn.AssetTransfer(
            xfer_asset=asset,
            asset_receiver=receiver,
            asset_amount=amount,
            fee=UInt64(0),  # ALWAYS zero for inner txns
        ).submit()
```

### 7.4 --- Reading asset properties

```python
from algopy import ARC4Contract, Asset, UInt64, arc4

class AssetInfo(ARC4Contract):
    @arc4.abimethod
    def get_asset_decimals(self, asset: Asset) -> UInt64:
        return asset.decimals

    @arc4.abimethod
    def get_asset_total(self, asset: Asset) -> UInt64:
        return asset.total
```

The asset must be in the transaction's foreign assets array.

### 7.5 --- Checking an account's asset balance

```python
from algopy import ARC4Contract, Account, Asset, UInt64, arc4

class BalanceChecker(ARC4Contract):
    @arc4.abimethod
    def get_asset_balance(self, account: Account, asset: Asset) -> UInt64:
        # asset.balance() fails if the account has not opted in
        return asset.balance(account)
```


## 8. Inner Transactions {#8-inner-transactions}

(See [Inner Transactions](https://dev.algorand.co/concepts/smart-contracts/inner-txn/).)

### 8.1 --- Sending an Algo payment

```python
from algopy import ARC4Contract, Account, UInt64, arc4, itxn

class PaymentSender(ARC4Contract):
    @arc4.abimethod
    def send_algo(self, receiver: Account, amount: UInt64) -> None:
        itxn.Payment(
            receiver=receiver,
            amount=amount,
            fee=UInt64(0),  # Caller covers via fee pooling
        ).submit()
```

### 8.2 --- Calling another smart contract

```python
from algopy import ARC4Contract, Application, Bytes, UInt64, arc4, itxn

class CrossContractCaller(ARC4Contract):
    @arc4.abimethod
    def call_other_app(self, app: Application) -> None:
        itxn.ApplicationCall(
            app_id=app,
            app_args=[Bytes(b"some_method")],
            fee=UInt64(0),
        ).submit()
```

Each inner app call adds +700 to the pooled opcode budget.

### 8.3 --- Creating an app from another app (factory pattern)

```python
from algopy import ARC4Contract, Bytes, UInt64, arc4, itxn

class AppFactory(ARC4Contract):
    @arc4.abimethod
    def deploy_child(
        self, approval: Bytes, clear: Bytes
    ) -> UInt64:
        result = itxn.ApplicationCall(
            approval_program=approval,
            clear_state_program=clear,
            global_num_uint=UInt64(4),
            global_num_bytes=UInt64(2),
            fee=UInt64(0),
        ).submit()
        return result.created_app.id
```

### 8.4 --- Fee pooling: inner txn fees should ALWAYS be zero

```python
# WRONG --- contract pays fee from its own balance:
itxn.Payment(receiver=user, amount=amt).submit()  # fee defaults to min_fee

# RIGHT --- caller covers via fee pooling:
itxn.Payment(receiver=user, amount=amt, fee=UInt64(0)).submit()

# CLIENT SIDE --- caller overpays their outer transaction:
sp = algod.suggested_params()
sp.fee = 2000  # Covers outer txn (1000) + inner txn (1000)
sp.flat_fee = True
```


## 9. Group Transactions {#9-group-transactions}

(See [Atomic Groups](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/).)

### 9.1 --- Accepting a payment in a grouped transaction

```python
from algopy import ARC4Contract, Global, UInt64, arc4, gtxn

class ReceivePayment(ARC4Contract):
    @arc4.abimethod
    def deposit(self, payment: gtxn.PaymentTransaction) -> UInt64:
        # PuyaPy validates that this arg IS a payment transaction
        # YOU must validate the critical fields:
        assert payment.receiver == Global.current_application_address
        assert payment.amount > UInt64(0)
        return payment.amount
```

The `gtxn.PaymentTransaction` parameter type makes the ABI router expect a payment transaction at the corresponding group position.

### 9.2 --- Accepting an asset transfer in a group

```python
from algopy import ARC4Contract, Asset, Global, UInt64, arc4, gtxn

class ReceiveAsset(ARC4Contract):
    @arc4.abimethod
    def deposit_asset(
        self,
        transfer: gtxn.AssetTransferTransaction,
        expected_asset: Asset,
    ) -> UInt64:
        assert transfer.asset_receiver == Global.current_application_address
        assert transfer.xfer_asset == expected_asset
        assert transfer.asset_amount > UInt64(0)
        return transfer.asset_amount
```

### 9.3 --- Inspecting other transactions in the group via gtxn

Inside a smart contract, we use `TransactionType` enum values for clarity. The `TransactionType` enum maps to the same integer constants (`Payment` = 1, `AssetTransfer` = 4) but makes the code self-documenting.

```python
from algopy import ARC4Contract, Global, TransactionType, UInt64, arc4, gtxn

class GroupInspector(ARC4Contract):
    @arc4.abimethod
    def verify_group(self) -> None:
        # Check total group size
        assert Global.group_size == UInt64(3)

        # Inspect transaction at index 0
        assert gtxn.Transaction(0).type == TransactionType.Payment
        assert gtxn.Transaction(0).receiver == Global.current_application_address

        # Inspect transaction at index 1
        assert gtxn.Transaction(1).type == TransactionType.AssetTransfer
```


## 10. Logic Signatures {#10-logic-signatures}

(See [Logic Signatures](https://dev.algorand.co/concepts/smart-contracts/logic-sigs/).)

### 10.1 --- Minimal LogicSig (contract account)

```python
from algopy import Txn, UInt64, Global, logicsig, TransactionType

@logicsig
def simple_escrow() -> bool:
    """Allows payments up to 1 Algo to anyone. No signing required."""
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.amount <= UInt64(1_000_000)
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= UInt64(10_000)
    )
```

This program's hash is its address. Fund it, and anyone can trigger payments from it.

### 10.2 --- LogicSig with template variables

```python
from algopy import Account, Bytes, Txn, UInt64, Global, TemplateVar, logicsig, TransactionType

@logicsig
def parameterized_escrow() -> bool:
    """Template vars are baked in at compile time."""
    RECEIVER = TemplateVar[Bytes]("RECEIVER")
    MAX_AMOUNT = TemplateVar[UInt64]("MAX_AMOUNT")
    EXPIRY = TemplateVar[UInt64]("EXPIRY")

    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.receiver == Account(RECEIVER)
        and Txn.amount <= MAX_AMOUNT
        and Txn.last_valid <= EXPIRY
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= UInt64(10_000)
    )
```

Compile: `puyapy contract.py --template-var RECEIVER=0xABCD... --template-var MAX_AMOUNT=5000000 --template-var EXPIRY=40000000`

### 10.3 --- LogicSig reading group transaction fields

```python
from algopy import Application, Global, Txn, UInt64, gtxn, logicsig, TransactionType

@logicsig
def grouped_logicsig() -> bool:
    """Only valid when grouped with a specific app call."""
    return (
        Global.group_size == UInt64(2)
        and Txn.group_index == UInt64(0)
        and gtxn.Transaction(1).type == TransactionType.ApplicationCall
        and gtxn.Transaction(1).app_id == Application(12345)
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= UInt64(10_000)
    )
```

### 10.4 --- Using a delegated LogicSig (client-side)

```python
from algosdk import transaction
import base64

# Compile the TEAL
compiled = algorand.client.algod.compile(teal_source)
program = base64.b64decode(compiled["result"])

# Create LogicSig and DELEGATE by signing with Alice's key
lsig = transaction.LogicSigAccount(program)
lsig.sign(alice_private_key)  # ← This is the delegation

# Now anyone can use lsig to authorize txns from Alice's account:
txn = transaction.PaymentTxn(
    sender=alice_address,  # FROM Alice
    sp=suggested_params,
    receiver=bob_address,
    amt=100_000,
)
signed = transaction.LogicSigTransaction(txn, lsig)
algorand.client.algod.send_transaction(signed)
```

### 10.5 --- Using a contract account LogicSig (client-side)

```python
# Contract account: the LogicSig IS the account (no signing needed)
lsig = transaction.LogicSigAccount(program)

# The sender is the hash of the program:
escrow_address = lsig.address()

# Fund it first, then submit transactions from it:
txn = transaction.PaymentTxn(
    sender=escrow_address,
    sp=suggested_params,
    receiver=recipient,
    amt=50_000,
)
signed = transaction.LogicSigTransaction(txn, lsig)
algorand.client.algod.send_transaction(signed)
```


## 11. Authorization and Security {#11-authorization-and-security}

(See [Rekeying](https://dev.algorand.co/concepts/accounts/rekeying/) and [Signing](https://dev.algorand.co/concepts/transactions/signing/).)

### 11.1 --- Creator-only method

```python
from algopy import ARC4Contract, Global, Txn, arc4

class AdminOnly(ARC4Contract):
    @arc4.abimethod
    def admin_action(self) -> None:
        assert Txn.sender == Global.creator_address
        # ... privileged operation ...
```

### 11.2 --- Stored admin address (transferable)

```python
from algopy import ARC4Contract, Account, GlobalState, Txn, Bytes, arc4

class TransferableAdmin(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())

    @arc4.baremethod(create="require")
    def create(self) -> None:
        self.admin.value = Txn.sender.bytes

    @arc4.abimethod
    def transfer_admin(self, new_admin: Account) -> None:
        assert Txn.sender.bytes == self.admin.value
        self.admin.value = new_admin.bytes
```

### 11.3 --- Close-to and rekey-to fields: LogicSigs vs stateful contracts

These fields (`close_remainder_to`, `asset_close_to`, `rekey_to`) are **critical to check in Logic Signature programs** (see Section 10). A LogicSig authorizes transactions *from* its own account, so unchecked close-to or rekey-to fields let an attacker drain or steal the LogicSig's account. Missing these checks is the #1 finding in LogicSig audits.

For **stateful smart contracts** accepting incoming grouped transactions, these fields affect the *sender's* account (the user), not the contract's. The contract receives the specified amount regardless. Inner transactions default these fields to the zero address automatically. Checking them in a stateful contract just restricts what users can do with their own wallets --- it is the wallet's responsibility to warn about dangerous transaction fields, not the contract's.

### 11.4 --- Verifying group size

```python
from algopy import ARC4Contract, Global, UInt64, arc4

class GroupSizeCheck(ARC4Contract):
    @arc4.abimethod
    def swap(self) -> None:
        # Expect exactly: [asset_transfer, this_app_call]
        assert Global.group_size == UInt64(2)
        # Prevents attacker from appending extra transactions
```


## 12. Subroutines and Code Organization {#12-subroutines-and-code-organization}

(See [Algorand Python structure guide](https://dev.algorand.co/algokit/languages/python/lg-structure/).)

### 12.1 --- Module-level subroutine (shared across contracts)

```python
from algopy import UInt64, subroutine

@subroutine
def min_value(a: UInt64, b: UInt64) -> UInt64:
    return a if a < b else b

@subroutine
def max_value(a: UInt64, b: UInt64) -> UInt64:
    return a if a > b else b
```

### 12.2 --- Subroutine within a contract class

```python
from algopy import ARC4Contract, UInt64, arc4, subroutine

class MathContract(ARC4Contract):
    @subroutine
    def _calculate_fee(self, amount: UInt64) -> UInt64:
        """Private helper --- not callable externally."""
        return amount * UInt64(3) // UInt64(1000)  # 0.3%

    @arc4.abimethod
    def get_fee(self, amount: UInt64) -> UInt64:
        return self._calculate_fee(amount)
```

Subroutines compile to TEAL `callsub`/`retsub`, saving program bytes when called multiple times.

### 12.3 --- Importing subroutines across files

```python
# utils.py
from algopy import UInt64, subroutine

@subroutine
def safe_subtract(a: UInt64, b: UInt64) -> UInt64:
    assert a >= b
    return a - b

# contract.py
from algopy import ARC4Contract, UInt64, arc4
from utils import safe_subtract

class MyContract(ARC4Contract):
    @arc4.abimethod
    def withdraw(self, balance: UInt64, amount: UInt64) -> UInt64:
        return safe_subtract(balance, amount)
```


## 13. ARC-4 Encoding and Types {#13-arc-4-encoding-and-types}

(See [ARC-4 specification](https://dev.algorand.co/arc-standards/arc-0004/).)

### 13.1 --- ARC-4 types vs native types

```python
from algopy import ARC4Contract, UInt64, arc4

class TypeDemo(ARC4Contract):
    @arc4.abimethod
    def with_arc4_types(self, x: arc4.UInt64, s: arc4.String) -> arc4.String:
        # arc4 types are ABI-encoded (wire format)
        # Convert to native types for computation:
        native_x = x.as_uint64()  # → UInt64 (.native deprecated on numerics)
        native_s = s.native       # → algopy.String (.native valid on non-numerics)
        return arc4.String("Got: " + native_s)

    @arc4.abimethod
    def with_native_types(self, x: UInt64) -> UInt64:
        # Native types work directly, ABI encoding is automatic
        return x + UInt64(1)
```

Rule of thumb: use native types for method parameters and return types when possible. The ABI router handles encoding automatically. Use `arc4.*` types for box storage and struct definitions.

### 13.2 --- ARC-4 structs

```python
from algopy import ARC4Contract, Global, arc4

class Position(arc4.Struct):
    owner: arc4.Address
    amount: arc4.UInt64
    timestamp: arc4.UInt64

class StructExample(ARC4Contract):
    @arc4.abimethod
    def create_position(
        self, owner: arc4.Address, amount: arc4.UInt64
    ) -> Position:
        return Position(
            owner=owner,
            amount=amount,
            timestamp=arc4.UInt64(Global.latest_timestamp),
        )
```

Structs are ABI-encoded as concatenated fields. Useful for structured box storage.

### 13.3 --- ARC-4 static and dynamic arrays

```python
from typing import Literal
from algopy import ARC4Contract, arc4

class ArrayExample(ARC4Contract):
    @arc4.abimethod
    def static_array(self) -> arc4.StaticArray[arc4.UInt64, Literal[3]]:
        # Fixed-size array (3 elements, each 8 bytes = 24 bytes total)
        return arc4.StaticArray(
            arc4.UInt64(10), arc4.UInt64(20), arc4.UInt64(30)
        )

    @arc4.abimethod
    def dynamic_array(self) -> arc4.DynamicArray[arc4.String]:
        # Variable-length array
        arr = arc4.DynamicArray[arc4.String]()
        arr.append(arc4.String("hello"))
        arr.append(arc4.String("world"))
        return arr
```


## 14. Cryptographic Operations {#14-cryptographic-operations}

(See [Cryptographic Tools](https://dev.algorand.co/concepts/smart-contracts/cryptographic-tools/).)

### 14.1 --- SHA-256 hashing

```python
from algopy import ARC4Contract, Bytes, arc4, op

class HashExample(ARC4Contract):
    @arc4.abimethod
    def sha256_hash(self, data: Bytes) -> Bytes:
        return op.sha256(data)

    @arc4.abimethod
    def sha512_256_hash(self, data: Bytes) -> Bytes:
        return op.sha512_256(data)  # Algorand's preferred hash
```

### 14.2 --- Ed25519 signature verification

```python
from algopy import ARC4Contract, Bytes, arc4, op

class SigVerify(ARC4Contract):
    @arc4.abimethod
    def verify_signature(
        self, data: Bytes, signature: Bytes, public_key: Bytes
    ) -> bool:
        # ed25519verify_bare: 1,900 opcodes
        return op.ed25519verify_bare(data, signature, public_key)
```

### 14.3 --- ECDSA verification (secp256k1 --- Bitcoin/Ethereum compatible)

```python
from algopy import ARC4Contract, Bytes, UInt64, arc4, op

class ECDSAVerify(ARC4Contract):
    @arc4.abimethod
    def verify_eth_signature(
        self, data_hash: Bytes, v: UInt64, r: Bytes, s: Bytes
    ) -> Bytes:
        # Recover the public key from the signature
        pub_x, pub_y = op.ecdsa_pk_recover(
            op.ECDSA.Secp256k1, data_hash, v, r, s
        )
        return pub_x + pub_y
```

### 14.4 --- VRF (Verifiable Random Function) verification

```python
from algopy import ARC4Contract, Bytes, arc4, op

class VRFExample(ARC4Contract):
    @arc4.abimethod
    def verify_randomness(
        self, message: Bytes, proof: Bytes, public_key: Bytes
    ) -> Bytes:
        output, is_valid = op.vrf_verify(
            op.VrfVerify.VrfAlgorand, message, proof, public_key
        )
        assert is_valid
        return output  # 64 bytes of verifiable randomness
```

### 14.5 --- Elliptic curve point addition (BN254)

```python
from algopy import ARC4Contract, Bytes, arc4, op

class ECExample(ARC4Contract):
    @arc4.abimethod
    def add_points(self, point_a: Bytes, point_b: Bytes) -> Bytes:
        # BN254 G1 points are 64 bytes each
        return op.EllipticCurve.add(op.EC.BN254g1, point_a, point_b)
```


## 15. Opcode Budget and Resource Management {#15-opcode-budget-and-resource-management}

(See [Costs and Constraints](https://dev.algorand.co/concepts/smart-contracts/costs-constraints/).)

### 15.1 --- Ensure minimum opcode budget

```python
from algopy import ARC4Contract, OpUpFeeSource, arc4, ensure_budget

class BudgetExample(ARC4Contract):
    @arc4.abimethod
    def expensive_operation(self) -> None:
        # Request at least 2,800 opcodes
        # PuyaPy auto-generates inner app calls to pad the budget
        ensure_budget(2800, OpUpFeeSource.GroupCredit)
        # ... expensive computation ...
```

### 15.2 --- NoOp bare method for budget padding (client-side approach)

```python
from algopy import ARC4Contract, arc4

class BudgetPadded(ARC4Contract):
    @arc4.baremethod(allow_actions=["NoOp"])
    def noop(self) -> None:
        """Each call to this adds +700 to the pooled opcode budget."""
        pass

    @arc4.abimethod
    def heavy_computation(self) -> None:
        # Client adds 3 NoOp calls before this → 4 × 700 = 2,800 budget
        pass
```

### 15.3 --- Reading the contract's own address and balance

```python
from algopy import ARC4Contract, Bytes, Global, UInt64, arc4

class SelfInfo(ARC4Contract):
    @arc4.abimethod
    def my_address(self) -> Bytes:
        return Global.current_application_address.bytes

    @arc4.abimethod
    def my_balance(self) -> UInt64:
        return Global.current_application_address.balance

    @arc4.abimethod
    def my_min_balance(self) -> UInt64:
        return Global.current_application_address.min_balance

    @arc4.abimethod
    def my_app_id(self) -> UInt64:
        return Global.current_application_id.id
```

### 15.4 --- Accessing transaction fields

```python
from algopy import ARC4Contract, Global, Txn, UInt64, arc4

class TxnFields(ARC4Contract):
    @arc4.abimethod
    def tx_info(self) -> UInt64:
        _ = Txn.sender            # Who sent this transaction
        _ = Txn.fee               # Fee paid
        _ = Txn.first_valid       # First valid round
        _ = Txn.last_valid        # Last valid round
        _ = Txn.group_index       # Position in group (0-indexed)
        _ = Global.group_size     # Total transactions in group
        _ = Global.round          # Current round number
        _ = Global.latest_timestamp  # Block timestamp (±25 seconds)
        return Global.round
```


## 16. Compilation and Deployment {#16-compilation-and-deployment}

(See [AlgoKit CLI overview](https://dev.algorand.co/algokit/cli/overview/) and [Algorand Python compilation guide](https://dev.algorand.co/algokit/languages/python/lg-compile/).)

### 16.1 --- Compiling with PuyaPy

```bash
# Compile via AlgoKit (recommended)
algokit compile py contract.py

# Or directly via PuyaPy
puyapy contract.py

# Output: contract.approval.teal, contract.clear.teal, contract.arc56.json

# Compile with template variables
algokit compile py contract.py --template-var MY_VAR=42

# Compile to bytecode directly (skip TEAL)
algokit compile py contract.py --output-bytecode
```

### 16.2 --- Using compile_contract in Algorand Python

```python
from algopy import ARC4Contract, UInt64, arc4, compile_contract, itxn

class MyContract(ARC4Contract):
    @arc4.abimethod
    def deploy_child(self) -> UInt64:
        compiled = compile_contract(ChildContract)
        result = itxn.ApplicationCall(
            approval_program=compiled.approval_program,
            clear_state_program=compiled.clear_state_program,
            global_num_uint=compiled.global_uints,
            global_num_bytes=compiled.global_bytes,
            fee=UInt64(0),
        ).submit()
        return result.created_app.id
```

### 16.3 --- Generating typed clients

```bash
# From ARC-56 spec
algokit generate client artifacts/MyContract.arc56.json --output client.py

# Usage with typed client:
from client import MyContractClient, MyContractFactory

algorand = algokit_utils.AlgorandClient.default_localnet()
deployer = algorand.account.localnet_dispenser()

factory = MyContractFactory(algorand=algorand, default_sender=deployer.address)
client, deploy_result = factory.deploy()
result = client.send.my_method(args=MyMethodArgs(arg1=42))  # Type-safe method call
print(result.abi_return)
```

### 16.4 --- Deploying to LocalNet (AppFactory)

```python
from pathlib import Path
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
deployer = algorand.account.localnet_dispenser()

# Deploy using AppFactory
factory = algorand.client.get_app_factory(
    app_spec=Path("artifacts/MyContract.arc56.json").read_text(),
    default_sender=deployer.address,
)
app_client, deploy_result = factory.deploy()
print(f"App ID: {app_client.app_id}")
print(f"App Address: {app_client.app_address}")

# Call a method
result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(method="my_method", args=[42])
)
print(f"Return value: {result.abi_return}")
```

### 16.5 --- Building and submitting a transaction group (client-side)

```python
from algosdk import transaction

# Create individual transactions
pay_txn = transaction.PaymentTxn(sender=alice, sp=sp, receiver=pool, amt=100_000)
app_txn = transaction.ApplicationCallTxn(sender=alice, sp=sp, index=app_id, app_args=[b"swap"])

# Assign group ID (makes them atomic)
gid = transaction.calculate_group_id([pay_txn, app_txn])
pay_txn.group = gid
app_txn.group = gid

# Sign each transaction
signed_pay = pay_txn.sign(alice_key)
signed_app = app_txn.sign(alice_key)

# Submit as a group
algorand.client.algod.send_transactions([signed_pay, signed_app])
```


## 17. Additional Patterns {#17-additional-patterns}

### 17.1 --- ASA close-out (recover MBR)

When you no longer need to hold an ASA, close out to recover the 100,000 μAlgo MBR. The `asset_close_to` field sends the entire balance to a recipient and removes the ASA from the account.

```python
# Client-side: close out of an ASA to recover MBR
algorand.send.asset_transfer(
    algokit_utils.AssetTransferParams(
        sender=user.address,
        receiver=user.address,     # Send remaining balance to self
        asset_id=token_id,
        amount=0,                   # Amount is ignored when closing
        close_asset_to=user.address, # This triggers the close-out
    )
)
# After this, the account no longer holds the ASA
# and recovers 100,000 μAlgo of MBR.
```

> **Warning:** The `close_asset_to` field sends the *entire* balance of that ASA, not just the `amount` field. Double-check the recipient address. If you send it to the wrong address, all tokens are lost.

### 17.2 --- Account rekeying

Rekeying changes which private key controls an account. The account address stays the same, but transactions must be signed by the new "auth address." This is useful for key rotation, converting a regular account into a contract-controlled account, or migrating to a new signing scheme.

```python
# Client-side: rekey an account to a new address
algorand.send.payment(
    algokit_utils.PaymentParams(
        sender=old_key.address,
        receiver=old_key.address,  # Self-payment (any destination works)
        amount=algokit_utils.AlgoAmount.from_micro_algo(0),
        rekey_to=new_key.address,  # The new signing authority
    )
)
# After this, old_key can no longer sign for this account.
# All future transactions must be signed by new_key.

# To rekey back to the original key:
algorand.send.payment(
    algokit_utils.PaymentParams(
        sender=old_key.address,      # Still the account address
        signer=new_key,              # Must sign with current auth key
        receiver=old_key.address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(0),
        rekey_to=old_key.address,    # Restore original authority
    )
)
```

> **Warning:** Rekeying is irreversible without the new key. If you rekey to an address you do not control, the account is permanently lost. Always verify the `rekey_to` address before signing.


## Quick Reference: AVM Limits

(See [Costs and Constraints](https://dev.algorand.co/concepts/smart-contracts/costs-constraints/) for the full specification.)

| Limit | Value |
|-------|-------|
| Max group size | 16 transactions |
| Opcode budget per app call | 700 (pooled) |
| Opcode budget per LogicSig txn | 20,000 (pooled, separate pool) |
| Max inner transactions per group | 256 (16 per app call, pooled across group) |
| Inner call depth | 8 |
| Program size (approval + clear combined) | 2,048 bytes (base); up to 8,192 bytes with 3 extra pages (each adds 2,048) |
| Global state pairs | 64 max |
| Local state pairs per user | 16 max |
| Key + value size | 128 bytes max |
| Box size | 0–32,768 bytes |
| Box name | 1–64 bytes |
| Box MBR | 2,500 + 400 × (name_len + data_size) μAlgo |
| Foreign refs per txn | 8 per type (accounts, assets, apps); shared across group since AVM v9 |
| ASA opt-in MBR | 100,000 μAlgo |
| Min account balance | 100,000 μAlgo |
| Min transaction fee | 1,000 μAlgo |
