\newpage

# A Token Vesting Contract

A startup has raised funds and needs to distribute tokens to its team. The tokens should not arrive all at once --- team members receive their allocation gradually over 12 months, with nothing released during the first 3 months (the "cliff"). If someone leaves early, the company can revoke their unvested tokens. This is a **token vesting contract**, and building one will teach you every foundational concept in Algorand smart contract development.

In Chapter 2, you built a simplified version of this contract and discovered its limitations through testing --- overflow on large amounts, no multi-beneficiary support, no revocation. Now we build the production version that solves every gap those tests revealed.

We will build it one capability at a time. Each section adds a new feature to the contract and introduces the Algorand concepts required to implement it. By the end, you will have a production-quality contract and a thorough understanding of how Algorand smart contracts work.

## Project Setup

If you scaffolded `my-first-contract` in Chapter 1, use that project. Otherwise, scaffold a new one. The `--name` flag sets the project directory name; the template always creates a `hello_world/` contract directory inside it, which we rename to match the chapter:

```bash
algokit init -t python --name token-vesting
cd token-vesting
algokit project bootstrap all
mv smart_contracts/hello_world smart_contracts/token_vesting
```

Your contract code goes in `smart_contracts/token_vesting/contract.py`. The build system discovers contracts by directory, so renaming the folder is all that is needed. Delete the template-generated `deploy_config.py` inside the renamed directory --- it references the old `HelloWorld` contract and is not needed for the scripts in this chapter.

## The Data Model

Before we write the contract class, we define the data structure that represents a vesting schedule. Each beneficiary's vesting terms are stored as an ARC-4 struct in box storage. We define it first because the contract's `__init__` method references it:

Add the following to `smart_contracts/token_vesting/contract.py`:

```python
from algopy import arc4

class VestingSchedule(arc4.Struct):
    total_amount: arc4.UInt64
    claimed_amount: arc4.UInt64
    start_time: arc4.UInt64
    cliff_end: arc4.UInt64
    vesting_end: arc4.UInt64
    is_revoked: arc4.Bool
```

Each `arc4.UInt64` occupies 8 bytes (big-endian), `arc4.Bool` occupies 1 byte, so the struct totals 41 bytes. We will use this struct throughout the contract --- for creating schedules, tracking claims, and reading vesting status. (See [Algorand Python ARC-4 guide](https://dev.algorand.co/algokit/languages/python/lg-arc4/) for struct encoding details.)

Notice the `arc4.UInt64` fields in the struct --- these are not the same as the plain `UInt64` you will see in the contract's `__init__` method below. Algorand Python has two parallel type systems that you will encounter throughout this book. **Native types** (`UInt64`, `Bytes`) are what the AVM operates on directly --- arithmetic, comparisons, and most function parameters use these. **ARC-4 types** (`arc4.UInt64`, `arc4.String`, `arc4.Bool`, `arc4.Struct`) are the ABI-encoded wire format used for method arguments, return values, and struct fields stored in boxes. When you read a field from an `arc4.Struct`, you get an ARC-4 value and must convert it to native before doing arithmetic: `schedule.total_amount.as_uint64()` converts `arc4.UInt64` to `UInt64`. We will see this conversion pattern in detail when we build the `claim` method later in this chapter.


## A Contract That Exists

Before we can vest tokens, we need a contract on the blockchain. Let us start with the absolute minimum: a contract that can be created and that knows who created it.

Recall from Chapter 1 that a smart contract executes once per transaction --- it validates, decides to approve or reject, and stops. With that model in mind, let us build our first contract. The clear state program handles a special case we will discuss later --- for now, just know it exists and that we will give it a default implementation that simply returns true.

ARCs (Algorand Requests for Comments) are community standards for the Algorand ecosystem, similar to Python's PEPs or internet RFCs. Modern Algorand contracts inherit from `ARC4Contract`, which implements the [ARC-4 Application Binary Interface](https://dev.algorand.co/concepts/smart-contracts/abi/). ARC-4 is the standard calling convention for Algorand smart contracts. It defines how method names are mapped to 4-byte selectors (computed as the first 4 bytes of `SHA-512/256` of the method signature string), how arguments are encoded on the wire, and how return values are communicated back to the caller via transaction logs. When you inherit from `ARC4Contract`, the PuyaPy compiler generates all of this routing logic automatically --- you never write a manual switch statement or parse raw bytes. (See the [ARC-4 specification](https://dev.algorand.co/arc-standards/arc-0004/) and the [Algorand Python ARC-4 guide](https://dev.algorand.co/algokit/languages/python/lg-arc4/).)

Methods decorated with `@arc4.abimethod` become publicly callable endpoints. Each method gets a unique selector derived from its full signature, including parameter types. For example, `hello(string)string` and `greet(string)string` produce different selectors even though they take the same parameter types, because the method name differs.

The `__init__` method has special semantics: it runs exactly once, during the application creation transaction. After that initial execution, the state it sets up persists on-chain, but `__init__` itself never runs again. Think of deploying a contract as instantiating a class --- `__init__` is the constructor, and every subsequent transaction is a method call on that instance.

Add the following class to `smart_contracts/token_vesting/contract.py`, below the `VestingSchedule` struct defined in the previous section:

```python
from algopy import ARC4Contract, GlobalState, Txn, Bytes, UInt64, arc4, BoxMap, Account

class TokenVesting(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())          # Admin address (set during creation)
        self.asset_id = GlobalState(UInt64(0))
        self.is_initialized = GlobalState(UInt64(0))
        self.beneficiary_count = GlobalState(UInt64(0))
        # Per-beneficiary vesting data, keyed by address.
        # Declared here but boxes are created on demand in create_schedule.
        self.schedules = BoxMap(Account, VestingSchedule, key_prefix=b"v_")

    @arc4.baremethod(create="require")
    def create(self) -> None:
        """Runs on app creation. Records who deployed it."""
        # Txn.sender is an Account object; .bytes extracts the raw 32-byte
        # public key, which is what our Bytes-typed GlobalState expects.
        self.admin.value = Txn.sender.bytes

    @arc4.abimethod(readonly=True)
    def get_admin(self) -> arc4.Address:
        return arc4.Address.from_bytes(self.admin.value)
```

We declare `beneficiary_count` and `schedules` in `__init__` even though they are not used until later sections. As with `asset_id`, the global state schema is fixed at deployment, so all fields must be declared upfront. The `BoxMap` declaration uses box storage (introduced in Chapter 1) --- it does not create any boxes on-chain. It tells the compiler the type signature for the mapping: keys are `Account` addresses, values are `VestingSchedule` structs, and each box name is prefixed with `b"v_"`. Boxes are created individually on demand when `create_schedule` is called later.

`GlobalState` declares a piece of persistent storage tied to this application. The AVM has exactly two native types: `UInt64` (unsigned 64-bit integer, maximum value approximately 1.8 times 10 to the 19th power) and `Bytes` (a byte array, maximum 4,096 bytes in the AVM stack). Everything else --- addresses, strings, structs, arrays --- is encoding on top of these two primitives. Here we store the admin address as raw `Bytes` and the asset ID as `UInt64`.

`Txn.sender` provides the address of whoever sent the current transaction. By recording it during creation, we establish an admin identity that we will check in later methods to enforce authorization.

The `@arc4.baremethod(create="require")` decorator marks this as a **bare method** --- one that matches on the transaction's OnCompletion action rather than an ABI method selector. The `create="require"` parameter means this method only runs during the initial app creation transaction. Bare methods are used for lifecycle events (creation, opt-in, close-out, update, delete) where no ABI arguments are needed.

The `readonly=True` flag on `get_admin` signals to client libraries that this method does not modify state. Clients can use Algorand's `simulate` endpoint to execute the method without submitting a real transaction --- getting the result instantly without paying fees. This is purely an optimization hint for clients; it does not enforce read-only behavior at the protocol level.

We also declared `asset_id` and `is_initialized` in `__init__` even though we do not use them yet. This is deliberate: the **global state schema** --- how many `UInt64` slots and how many `Bytes` slots the contract uses --- is fixed at deployment and can never be changed afterward. If you need 5 uint slots later but only declared 3, you must deploy an entirely new contract. The marginal cost of extra slots is small (28,500 microAlgos per uint slot, 50,000 per byte-slice slot), so it is good practice to allocate a few spares. The maximum is 64 key-value pairs, with each key plus value limited to 128 bytes combined.

To deploy this contract, you compile it with PuyaPy and use AlgoKit. If you set up the environment as described in Chapter 1 and renamed the contract directory as shown in the Project Setup section above, your contract code should be in `smart_contracts/token_vesting/contract.py`. Compile:

```bash
algokit project run build
```

If compilation succeeds, you will see output indicating the approval and clear programs were generated. Check the `smart_contracts/artifacts/token_vesting/` directory --- you should find `TokenVesting.approval.teal`, `TokenVesting.clear.teal`, `TokenVesting.arc56.json`, and a generated typed client `token_vesting_client.py`. The subdirectory name matches the contract directory name.

If you get an error about missing imports, make sure `algorand-python` is installed (it should be if you ran `algokit project bootstrap all`). If PuyaPy reports a type error, check that your type annotations match exactly --- Algorand Python is strictly typed.

With LocalNet running (`algokit localnet start`), create a deployment script. Save the following as `deploy.py` in your project root:

```python
from pathlib import Path
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
deployer = algorand.account.localnet_dispenser()

factory = algorand.client.get_app_factory(
    app_spec=Path("smart_contracts/artifacts/token_vesting/TokenVesting.arc56.json").read_text(),
    default_sender=deployer.address,
)
app_client, deploy_result = factory.deploy()
print(f"App ID: {app_client.app_id}")
print(f"App Address: {app_client.app_address}")

# Call the read-only method to verify
result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(method="get_admin")
)
print(f"Admin: {result.abi_return}")
```

Run it:

```bash
python deploy.py
```

You should see output like:

```
App ID: 1001
App Address: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAY5HFKQ
Admin: DEPLOYER_ADDRESS_HERE
```

If you see an error like "balance below minimum," your deployer account may not have enough Algo. The LocalNet dispenser account is pre-funded with millions of Algo, so this should not happen with the default setup. If you are using a different account, fund it first.

You can inspect the deployed contract's state using the Algorand REST API. With LocalNet running, the algod endpoint is typically at `http://localhost:4001`:

```bash
# Check the application info (requires curl and jq)
curl -s http://localhost:4001/v2/applications/1001 \
  -H "X-Algo-API-Token: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
  | python -m json.tool
```

This returns the application's global state, the approval and clear program hashes, and other metadata. You will use this pattern throughout development to verify that state changes happen as expected.

The compilation step produces three artifacts: `TokenVesting.approval.teal` (the approval program in human-readable TEAL assembly), `TokenVesting.clear.teal` (the clear state program), and `TokenVesting.arc56.json` (the ARC-56 application specification containing method signatures, state schema, type information, and source maps for debugging). The ARC-56 spec is what clients use to construct properly formatted transactions --- it is the equivalent of an ABI JSON file in the Ethereum ecosystem.

Every deployed contract gets a deterministic address derived from its application ID: `SHA512_256("appID" || big_endian_8_byte(app_id))`. This address can hold Algos and Algorand Standard Assets. No one has a private key for this address --- the contract's code is the sole authority over outgoing transactions. This is what makes smart contracts trustless: the rules are enforced by code, not by any individual's goodwill.

Your contract now exists on-chain. It knows who created it. It cannot do anything else yet.


## Making It Immutable

Before we add any real functionality, we need to lock the contract down. Every Algorand application call includes an **OnCompletion** field --- a misnomer that confuses everyone the first time they see it. Despite the name, it does not describe something that happens *after* the call. It specifies the *type* of operation being requested: a normal method call, an opt-in to the app's local state, a state cleanup, a code update, or a deletion. Think of it as the "action verb" of the application call. The possible actions are: `NoOp` (a normal method call), `OptIn` (user opts into the app's local state), `CloseOut` (user exits the app), `UpdateApplication` (replace the contract's code), and `DeleteApplication` (remove the contract entirely). (See [Lifecycle](https://dev.algorand.co/concepts/smart-contracts/lifecycle/).)

If you do not explicitly handle `UpdateApplication` and `DeleteApplication`, the default behavior depends on your base class. For `ARC4Contract`, unhandled actions are rejected by default --- but relying on defaults for security-critical behavior is risky. It is better to be explicit. Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        """Make the contract immutable. No one can change or delete it."""
        assert False, "Contract is immutable"
```

This is not optional for financial contracts. Consider what happens without it: the admin deploys the vesting contract, team members see the code and trust it, and then the admin calls `UpdateApplication` to replace the vesting logic with code that sends all tokens to their own address. The contract was audited, but the audit is meaningless if the code can be changed post-deployment.

Immutability is the foundation of trustlessness. Once deployed, the rules encoded in the contract are the rules forever. Users can verify the source code, confirm it matches the deployed bytecode, and trust that it will behave consistently. This is the entire value proposition of smart contracts over traditional custodial arrangements.

There are legitimate reasons to want upgradeable contracts --- bug fixes, feature additions, regulatory compliance. If you need upgradeability during an initial stabilization period, use a multisig with a timelock and publicly commit to making the contract immutable by a specific date. But the default should always be immutability, especially for contracts that hold other people's money.


## Accepting Tokens

Our vesting contract needs to hold the tokens it will distribute. On Algorand, fungible tokens are implemented as **Algorand Standard Assets (ASAs)** --- protocol-level primitives built directly into the blockchain. This is a fundamental architectural difference from other blockchains where every token is its own smart contract with its own transfer logic, its own potential bugs, and its own execution costs.

On Algorand, the blockchain itself handles ASA creation, transfers, freezing, and destruction. Every ASA benefits from the same speed (approximately 2.8-second finality), security, and atomic transfer guarantees as native Algo. When you transfer an ASA, there is no token contract to call, no fallback function that might reenter your code, no custom transfer logic that might behave unexpectedly. It is a native protocol operation, as fundamental as sending Algo. (See [Assets Overview](https://dev.algorand.co/concepts/assets/overview/).)

Every ASA has four configurable role addresses that determine who can manage it. The **Manager** can reconfigure the other three roles; setting this to the zero address makes the asset permanently immutable. The **Reserve** is purely informational --- some block explorers display it, but it has no protocol-level power. The **Freeze** address can freeze or unfreeze any account's holdings of this asset, preventing transfers; setting to zero means no one can ever freeze the asset. The **Clawback** address can transfer tokens from any account without the account owner's consent; this enables regulatory compliance use cases but also custodial control, and setting to zero makes the token fully permissionless. For vesting tokens and LP tokens, you almost always want no freeze and no clawback.

Before any account --- including your smart contract --- can hold an ASA, it must explicitly **opt in** to that asset. An opt-in is a zero-amount asset transfer to yourself. On some blockchains, anyone can send you tokens you never asked for, polluting your wallet with worthless or malicious assets. Algorand prevents this by requiring you to choose to accept each asset. The cost of opting in is 100,000 microAlgos (0.1 Algo) in additional **Minimum Balance Requirement (MBR)**.

MBR is Algorand's anti-spam mechanism. Every account must maintain a minimum Algo balance proportional to the resources it consumes on-chain. The base MBR is 100,000 microAlgos (0.1 Algo) just to exist. Each ASA opt-in adds 100,000 more. Each piece of global state, local state, or box storage adds more (with its own formula). If a transaction would cause an account's balance to drop below its MBR, the transaction fails. This is one of the most common errors new developers encounter: the contract cannot opt into an asset because no one has sent it enough Algo to cover the MBR.

To opt the contract into the vesting token, we use an *inner transaction* --- a transaction generated and executed by the contract during its own execution. When your contract executes an inner transaction, it acts as an autonomous agent, sending from its own address. The contract can send payments, transfer assets, create new assets, and even call other contracts via inner transactions.

There is one critical security rule for *inner transactions*: **always set the fee to zero**. If you do not explicitly set `fee=UInt64(0)`, the inner transaction uses the default minimum fee of 1,000 microAlgos, and this fee is deducted from the contract's own Algo balance, not from the caller's. An attacker can exploit this by calling your contract in a loop, triggering inner transactions that slowly drain the contract's Algo balance. Eventually, the balance drops below MBR and the contract can no longer operate.

> **Warning:** If you omit `fee=UInt64(0)` on an inner transaction, the default minimum fee (1,000 microAlgos) is deducted from the contract's own Algo balance. An attacker can call your contract repeatedly, draining its balance through accumulated fees until it falls below MBR and becomes inoperable.

The solution is *fee pooling*: the Algorand protocol validates fees at the group level, not per-transaction. The sum of all fees in an atomic group must meet the sum of all minimum fees (including inner transactions). So the caller's outer transaction overpays its fee to cover everything.

Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
from algopy import Asset, Global, UInt64, itxn

    @arc4.abimethod
    def initialize(self, vesting_asset: Asset) -> None:
        """Set the token to be vested and opt the contract into it."""
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert self.is_initialized.value == UInt64(0), "Already initialized"

        self.asset_id.value = vesting_asset.id
        self.is_initialized.value = UInt64(1)

        itxn.AssetTransfer(
            xfer_asset=vesting_asset,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),  # CRITICAL: always zero. Caller covers via fee pooling.
                            # Omitting this drains the contract's Algo balance.
        ).submit()
```

Before calling `initialize`, the client must fund the contract with enough Algo for the MBR and set the outer transaction fee high enough to cover the inner transaction. The following script demonstrates the complete initialize flow using AlgoKit Utils.

The `foreign_assets` parameter (populated automatically by AlgoKit Utils) is part of Algorand's **resource reference system**. Every application call must declare which blockchain resources it will access --- accounts, assets, applications, and boxes. The AVM node pre-loads these resources into memory before execution, ensuring predictable performance. Think of it as declaring your read-set before running a database query --- the node needs to know which accounts, assets, applications, and boxes your program will touch so it can load them into memory. The limit is 8 total references per transaction. Since AVM v9, references are shared across the transaction group, effectively allowing up to 128 references for complex operations.

## Compiling and Running What We Have So Far

At this point our contract can be created, reject updates/deletes, and initialize itself by opting into a vesting token. Let us compile and run through the full workflow on LocalNet to make sure everything works before adding more features.

Recompile after adding the `initialize` method and the immutability bare method:

```bash
algokit project run build
```

Check that the artifacts were updated (the file timestamps should change). If you get compilation errors, the most common causes are missing imports (make sure all of `Asset`, `Global`, `UInt64`, `itxn` are imported from `algopy`) or type mismatches in the method signature.

Now create a test script that deploys the contract, creates a test ASA, and calls `initialize`. Save the following as `test_initialize.py` in your project root:

```python
from pathlib import Path
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
admin = algorand.account.localnet_dispenser()

# Step 1: Create a test token (ASA) to use as the vesting asset
result = algorand.send.asset_create(
    algokit_utils.AssetCreateParams(
        sender=admin.address,
        total=10_000_000_000,  # 10,000 tokens with 6 decimals
        decimals=6,
        default_frozen=False,
        asset_name="TestVestingToken",
        unit_name="TVT",
    )
)
token_id = result.asset_id
print(f"Created test token: ASA ID {token_id}")

# Step 2: Deploy the vesting contract
factory = algorand.client.get_app_factory(
    app_spec=Path("smart_contracts/artifacts/token_vesting/TokenVesting.arc56.json").read_text(),
    default_sender=admin.address,
)
app_client, deploy_result = factory.deploy()
print(f"Deployed contract: App ID {app_client.app_id}")
print(f"Contract address: {app_client.app_address}")

# Step 3: Fund the contract (for MBR) and call initialize
# Use a transaction group: payment + app call
composer = algorand.new_group()
composer.add_payment(
    algokit_utils.PaymentParams(
        sender=admin.address,
        receiver=app_client.app_address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(200_000),  # 0.2 Algo for MBR
    )
)
composer.add_app_call_method_call(
    app_client.params.call(
        algokit_utils.AppClientMethodCallParams(
            method="initialize",
            args=[token_id],
            static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),  # Cover inner txn fee
        )
    )
)
composer.send()
print(f"Initialized with token {token_id}")

# Verify: check the contract's global state
app_info = algorand.client.algod.application_info(app_client.app_id)
print("Global state:")
for kv in app_info["params"]["global-state"]:
    print(f"  {kv}")
```

Run it with `python test_initialize.py`. If everything works, you will see the token creation, deployment, and initialization succeed. If you see `"balance below minimum"`, increase the funding amount. If you see `"Only admin"`, make sure the same account that deployed the contract is calling `initialize`.

This workflow --- edit, compile, deploy, call, verify --- is the loop you will follow for the rest of this chapter. Each new method we add can be tested incrementally on LocalNet before moving on.


## Depositing Tokens

The admin needs to deposit the tokens that will be distributed. This means the contract must accept an incoming asset transfer bundled in an atomic group with the method call.

Algorand's **atomic groups** bundle up to 16 transactions that all succeed or all fail. The protocol guarantees there is no partial execution. If any transaction in the group is rejected, the entire group is rolled back atomically. This is the foundation of DeFi on Algorand: a user bundles "send tokens to the pool" and "call the swap method" into one group, guaranteeing they never lose tokens without receiving the expected output.

In Algorand Python, you declare **typed transaction parameters** in your method signature. The ABI router expects a transaction of that type at the corresponding position in the group and gives you type-safe access to its fields.

Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
from algopy import gtxn

    @arc4.abimethod
    def deposit_tokens(
        self,
        deposit_txn: gtxn.AssetTransferTransaction,
    ) -> UInt64:
        """Admin deposits tokens into the vesting pool."""
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert Global.group_size == UInt64(2), "Expected 2 transactions"
        assert self.is_initialized.value == UInt64(1), "Not initialized"

        assert deposit_txn.asset_receiver == Global.current_application_address
        assert deposit_txn.xfer_asset == Asset(self.asset_id.value)
        assert deposit_txn.asset_amount > UInt64(0)

        return deposit_txn.asset_amount
```

The essential validations for an incoming grouped transaction in a stateful contract are: **who sent it** (authorization), **what asset** (correct token), **how much** (positive amount), and **where it went** (to the contract's address). These are the checks shown above.

You may see Algorand tutorials that also add `asset_close_to == Global.zero_address` and `rekey_to == Global.zero_address` assertions on every incoming grouped transaction. These checks are **critical for Logic Signatures** (covered in Chapter 7), where the LogicSig authorizes transactions *from* its own account and the program is the sole line of defense against draining or rekeying that account. But in a stateful smart contract, these fields on the *caller's* transaction affect the *caller's* account, not the contract's:

- **`close_remainder_to`** / **`asset_close_to`** --- drain the *sender's* balance to another address. The sender is the user, not the contract. The contract receives the specified `amount` regardless.
- **`rekey_to`** --- reassigns the *sender's* signing authority. Again, the user's account, not the contract's.

A stateful contract's own account can only be affected by transactions it signs itself (inner transactions), and inner transactions default these fields to the zero address automatically. Asserting them on incoming grouped transactions just restricts what the user's wallet can do for no security benefit to the contract. It is the wallet's responsibility to warn users about dangerous fields on their own transactions. (See [Transactions Overview](https://dev.algorand.co/concepts/transactions/overview/) for the full set of transaction fields, and [Rekeying](https://dev.algorand.co/concepts/accounts/rekeying/) for the `rekey_to` field and its security implications.)


## Creating Vesting Schedules

Now we need to record each team member's vesting schedule. This is per-user data, and the choice of where to store it is the most important architectural decision in this contract. Recall from Chapter 1 that Algorand offers three storage types --- global state, local state, and box storage --- each with different ownership and deletion semantics.

*Before reading on: which of the three storage types would you choose for per-user vesting data? Consider what happens if a user can delete their own data. Think about this for a moment before we discuss the solution.*

Your first instinct might be **local state**. The MBR is charged to the opting-in account, which seems fair, and each user gets their own key-value pairs.

But recall local state's fatal flaw: **users can clear their local state at any time by sending a ClearState transaction, and this always succeeds regardless of what your clear state program does**. For a vesting contract, the implication is devastating. If Bob has claimed 500 of his 1,000 vesting tokens and clears his local state, the contract loses track of his claims. Bob could potentially re-register and claim another 1,000 tokens.

> **Warning:** Users can delete their local state at any time via ClearState, and the protocol guarantees this always succeeds. Never use local state as the sole record of financial obligations, debts, or token claims.

Refer to the storage comparison in Chapter 1 for a full breakdown of each type's ownership semantics, limits, and tradeoffs. The critical distinction here is: local state is user-deletable, box storage is application-controlled.

> **Check your understanding:** Without looking back at Chapter 1, name the three Algorand storage types and state one key constraint of each. Which one can users delete unilaterally? Which one has an immutable schema? Which one does the application fully control?

The correct solution is **box storage** --- application-controlled key-value storage where the application decides when boxes are created and deleted. Users cannot unilaterally remove them. (See [Box Storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/).)

> **Design decision: why box storage over local state.** When I encounter per-user data, I ask three questions: (1) Can the user delete it unilaterally? If yes, local state is dangerous. (2) Is the data small enough for local state's 128-byte limit? (3) Does the application need to control the data's lifecycle? For vesting schedules, the answers are yes, maybe, and definitely yes --- making box storage the clear choice.

Recall the `VestingSchedule` struct we defined at the start of the chapter. We use `arc4.Struct` for typed, ABI-encoded data structures and `BoxMap` for a typed mapping where each entry is its own box. The box name (with prefix `"v_"` plus 32-byte address) is 34 bytes. The MBR per beneficiary: `2,500 + 400 * (34 + 41) = 32,500 microAlgos`, about 0.033 Algo.

`Global.latest_timestamp` returns a Unix epoch timestamp from the current block header. The block proposer sets it from their system clock, constrained to be monotonically non-decreasing and at most 25 seconds ahead of the previous block. For vesting schedules measured in months, this imprecision is negligible.

Now we encounter **box references** in practice --- the concept introduced in Chapter 1. Every transaction that reads or writes a box must declare which boxes it will access in a `boxes` array on the transaction. The AVM uses these declarations to allocate I/O budget: each reference grants 1,024 bytes (1KB) of read/write capacity. For `create_schedule`, the box name is 34 bytes (`"v_"` prefix + 32-byte address) and the data is 41 bytes, totaling 75 bytes --- well within a single reference.

On the client side, you declare box references like this (this is client-side code, not part of the contract):

```python
# Client must declare the box this transaction will access
app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="create_schedule",
        args=[beneficiary_address, 1_000_000, 7_776_000, 31_536_000, mbr_txn],
        # decode_address is from algosdk.encoding
        box_references=[b"v_" + decode_address(beneficiary_address)],
    )
)
```

Forgetting this declaration produces "box read/write budget exceeded" --- the single most common error new Algorand developers encounter. If you see this error, your first check should always be: did I declare the box references? For boxes larger than 1KB, you need multiple references to the same box (e.g., a 4KB box needs four references). The Cookbook (Recipe 6.5) shows this pattern in detail.

> **Warning:** Every method that accesses box storage requires box references on the client side --- not just `create_schedule`. The `claim`, `revoke`, `cleanup_schedule`, `get_vesting_info`, and `get_claimable` methods all read or write the beneficiary's box and must include the same `box_references` declaration. Forgetting this on read-only methods like `get_vesting_info` is a common mistake --- the AVM enforces the I/O budget regardless of whether the access is a read or write.

Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
    @arc4.abimethod
    def create_schedule(
        self,
        beneficiary: Account,
        total_amount: UInt64,
        cliff_duration: UInt64,
        vesting_duration: UInt64,
        mbr_payment: gtxn.PaymentTransaction,
    ) -> None:
        """Create a vesting schedule for a team member."""
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert beneficiary not in self.schedules, "Schedule already exists"
        assert total_amount > UInt64(0), "Amount must be positive"
        assert vesting_duration > cliff_duration, "Vesting must exceed cliff"

        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(34) + UInt64(41))
        assert mbr_payment.receiver == Global.current_application_address
        assert mbr_payment.amount >= box_mbr

        now = Global.latest_timestamp
        self.schedules[beneficiary] = VestingSchedule(
            total_amount=arc4.UInt64(total_amount),
            claimed_amount=arc4.UInt64(0),
            start_time=arc4.UInt64(now),
            cliff_end=arc4.UInt64(now + cliff_duration),
            vesting_end=arc4.UInt64(now + vesting_duration),
            is_revoked=arc4.Bool(False),
        )
        self.beneficiary_count.value += UInt64(1)
```


## Claiming Vested Tokens

This is the core logic. A beneficiary calls `claim` and receives whatever tokens have vested since their last claim. The math must be exact.

The AVM has no floating point. All math is `UInt64`. The vesting calculation is straightforward conceptually --- linear interpolation between start and end --- but requires careful handling of integer overflow. (See [Costs and Constraints](https://dev.algorand.co/concepts/smart-contracts/costs-constraints/) for AVM type and budget details.)

Consider a 100 million token allocation with 6 decimal places: that is 10 to the 14th base units. Multiplied by an elapsed time of approximately 31 million seconds (one year), the product is approximately 3 times 10 to the 21st --- exceeding `UInt64`'s maximum. The AVM panics on overflow rather than wrapping silently (which is better than getting a wrong answer), but you must handle it.

The solution is **wide arithmetic**. `op.mulw(a, b)` returns a 128-bit product as two `UInt64` values (high and low 64 bits). `op.divmodw` divides a 128-bit value by another. The intermediate product never overflows, and the final result fits in `UInt64` because vested is always less than or equal to total_amount.

Integer division rounds down (floor). This means beneficiaries get slightly less than their exact entitlement at each intermediate claim. This is correct --- the contract should never release more than the total allocation. The rounding dust resolves on the final claim when the `now >= vesting_end` branch bypasses the division entirely.

We extract the vesting calculation into a **subroutine** because it appears in three places (claim, revoke, get_claimable). The `@subroutine` decorator makes the compiler emit a single TEAL subroutine called via `callsub`/`retsub`, saving program bytes.

Add this module-level function to `smart_contracts/token_vesting/contract.py`, placed **between** the `VestingSchedule` struct definition and the `TokenVesting` class (outside the class, not as a method). Subroutines must be defined at module scope --- they cannot be class methods:

```python
from algopy import op, subroutine

@subroutine
def calculate_vested(
    total: UInt64, start: UInt64, cliff_end: UInt64,
    vesting_end: UInt64, now: UInt64,
) -> UInt64:
    if now < cliff_end:
        return UInt64(0)
    if now >= vesting_end:
        return total
    elapsed = now - start
    duration = vesting_end - start
    high, low = op.mulw(total, elapsed)
    q_hi, vested, r_hi, r_lo = op.divmodw(high, low, UInt64(0), duration)
    assert q_hi == 0, "Overflow in vesting calculation"
    return vested
```

Algorand Python has two parallel type systems. **Native types** (`UInt64`, `Bytes`) are what the AVM works with directly --- they are what arithmetic, comparisons, and function parameters use. **ARC-4 types** (`arc4.UInt64`, `arc4.String`, `arc4.Bool`) are the ABI-encoded wire format used for method arguments, return values, and struct fields stored in boxes. When you read a field from an `arc4.Struct`, you get an ARC-4 value and must convert it to native before doing arithmetic or comparisons. The conversion method `.as_uint64()` is the explicit numeric conversion for `arc4.UInt64`, and it is the recommended approach. An older alternative, `.native`, returns the corresponding native type generically (`arc4.UInt64.native` yields `UInt64`, `arc4.Bool.native` yields `bool`), but `.native` is deprecated since PuyaPy 5.0 because it returns `Any`, losing type safety. This book uses `.as_uint64()` for numeric fields and `.native` only for booleans (where it remains the natural conversion).

Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
    @arc4.abimethod
    def claim(self) -> UInt64:
        """Beneficiary claims their vested tokens."""
        beneficiary = Txn.sender
        assert beneficiary in self.schedules, "No vesting schedule"

        # .copy() is required: box storage returns a reference to encoded data.
        # To modify fields, we need a mutable, detached copy --- similar to
        # how an ORM returns a detached object that you modify then save back.
        schedule = self.schedules[beneficiary].copy()

        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            Global.latest_timestamp,
        )

        claimable = vested - schedule.claimed_amount.as_uint64()
        assert claimable > UInt64(0), "Nothing to claim"

        # Send tokens to the beneficiary
        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_id.value),
            asset_receiver=beneficiary,
            asset_amount=claimable,
            fee=UInt64(0),
        ).submit()

        # Record the claim
        schedule.claimed_amount = arc4.UInt64(
            schedule.claimed_amount.as_uint64() + claimable
        )
        self.schedules[beneficiary] = schedule.copy()

        return claimable
```

> **Beneficiary prerequisites:** Before calling `claim`, the beneficiary must (1) have a funded account (at least 0.2 Algo for the base MBR plus ASA opt-in MBR), and (2) have opted into the vesting ASA (a zero-amount self-transfer of the asset). Without the opt-in, the inner `AssetTransfer` will fail with "receiver not opted in." In a production system, you might add an `opt_in_beneficiary` method that handles this in one atomic group, but for this contract the beneficiary manages it themselves.

Notice that we send the tokens *before* updating the schedule's `claimed_amount`. On Ethereum, this would be a critical reentrancy vulnerability --- the recipient could call back into `claim()` before `claimed_amount` is updated, draining the contract. On Algorand, this is perfectly safe.

> **No reentrancy on Algorand.** When your contract sends tokens via an inner transaction, no user code executes on the receiving side. There are no fallback functions, no callbacks, no hooks triggered by token receipt. The contract maintains uninterrupted control flow throughout its entire execution. If any part of the execution fails --- including the inner transaction --- *all* state changes roll back atomically. This means the ordering of state updates and inner transactions has no security implications. Write your code in whatever order tells the clearest story. This eliminates the entire class of reentrancy exploits that has caused hundreds of millions of dollars in losses on Ethereum.


## Revoking Unvested Tokens

If a team member leaves, the admin reclaims the unvested portion. Already-vested tokens remain claimable. The revoke method uses [inner transactions](https://dev.algorand.co/concepts/smart-contracts/inner-txn/) to return the unvested tokens to the admin.

Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
    @arc4.abimethod
    def revoke(self, beneficiary: Account) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert beneficiary in self.schedules, "No schedule"

        schedule = self.schedules[beneficiary].copy()
        assert not schedule.is_revoked.native, "Already revoked"

        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            Global.latest_timestamp,
        )
        unvested = schedule.total_amount.as_uint64() - vested

        schedule.is_revoked = arc4.Bool(True)
        schedule.total_amount = arc4.UInt64(vested)
        self.schedules[beneficiary] = schedule.copy()

        if unvested > UInt64(0):
            itxn.AssetTransfer(
                xfer_asset=Asset(self.asset_id.value),
                asset_receiver=Account(self.admin.value),
                asset_amount=unvested,
                fee=UInt64(0),
            ).submit()

        return unvested
```

Setting `total_amount = vested` after revocation means the claim math works without a special branch: the beneficiary gets exactly what they earned, no more.


## Cleaning Up Completed Schedules

After a beneficiary has claimed everything, their box consumes storage and locks MBR. Cleaning up deletes the box and refunds the freed MBR.

Add this method to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
    @arc4.abimethod
    def cleanup_schedule(self, beneficiary: Account) -> None:
        assert beneficiary in self.schedules, "No schedule"

        schedule = self.schedules[beneficiary].copy()
        assert schedule.claimed_amount.as_uint64() >= schedule.total_amount.as_uint64()

        del self.schedules[beneficiary]
        self.beneficiary_count.value -= UInt64(1)

        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(34) + UInt64(41))
        itxn.Payment(
            receiver=Account(self.admin.value),
            amount=box_mbr,
            fee=UInt64(0),
        ).submit()
```

If the contract were deleted while boxes still exist, the MBR would be locked forever. Always clean up boxes before deleting an app. (See [Storage Overview](https://dev.algorand.co/concepts/smart-contracts/storage/overview/) for box lifecycle details.)


## Querying Vesting Status

Read-only methods let beneficiaries check their status without paying fees.

Add these methods to the `TokenVesting` class in `smart_contracts/token_vesting/contract.py`:

```python
    @arc4.abimethod(readonly=True)
    def get_vesting_info(self, beneficiary: Account) -> VestingSchedule:
        assert beneficiary in self.schedules, "No schedule"
        return self.schedules[beneficiary].copy()

    @arc4.abimethod(readonly=True)
    def get_claimable(self, beneficiary: Account) -> UInt64:
        assert beneficiary in self.schedules, "No schedule"
        schedule = self.schedules[beneficiary].copy()
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            Global.latest_timestamp,
        )
        return vested - schedule.claimed_amount.as_uint64()
```

The `calculate_vested` subroutine is now used in three places. Without it, the vesting math would be duplicated three times in compiled TEAL, consuming precious program bytes within the 8,192-byte limit. (See [Algorand Python structure guide](https://dev.algorand.co/algokit/languages/python/lg-structure/) for subroutine usage.)


## Testing the Vesting Contract

> **Note:** The project template from `algokit init` does not include `pytest` in its dependencies or create a `tests/` directory. Before running tests, install pytest (`pip install pytest` or add it to `pyproject.toml` under `[project.optional-dependencies]`) and create a `tests/` directory in your project root. This applies to all four projects in this book. (See [Testing](https://dev.algorand.co/algokit/utils/python/testing/) for AlgoKit testing patterns.)

The tests below are structural outlines showing *what* to test and *how* to assert. The helper functions (`create_test_asa`, `deploy_vesting`, `deposit_tokens`, `create_schedule`, `get_claimable`, `advance_time`, etc.) are project-specific wrappers around the AlgoKit Utils calls shown earlier in this chapter --- implement them using the deployment and interaction patterns demonstrated above. The patterns here --- lifecycle tests, failure-path tests, invariant tests --- are the ones you should implement for any production contract.

Before diving into the test code, there are two LocalNet behaviors that will affect how you write your test helpers.

> **LocalNet time advancement:** On LocalNet, block timestamps only advance when new blocks are produced, and blocks are produced on demand (when transactions are submitted). Calling `time.sleep(N)` alone does NOT advance the block timestamp --- you must also submit a transaction (even a zero-amount self-payment) to produce a block with the updated timestamp. A typical `advance_time` helper sleeps for the desired duration, then sends a dummy transaction to trigger a new block:
>
> ```python
> import time
> def advance_time(algorand, seconds):
>     """Sleep, then send a dummy txn to produce a block with updated timestamp."""
>     time.sleep(seconds)
>     dispenser = algorand.account.localnet_dispenser()
>     algorand.send.payment(
>         algokit_utils.PaymentParams(
>             sender=dispenser.address,
>             receiver=dispenser.address,
>             amount=algokit_utils.AlgoAmount.from_micro_algo(0),
>         )
>     )
> ```
>
> For testing, use short durations (seconds rather than months) for cliff and vesting periods. For example, set a cliff of 8 seconds and total vesting of 30 seconds instead of 90 days and 365 days.

A second LocalNet quirk affects rapid-fire test transactions.

> **LocalNet tip: transaction deduplication.** Sending identical app calls in rapid succession on LocalNet can produce identical transaction IDs, causing `"transaction already in ledger"` errors. To avoid this, add a unique `note` field to each transaction (e.g., `note=os.urandom(8)` or `note=f"test-{i}".encode()`). This ensures every transaction has a distinct ID even when the parameters are otherwise identical. In practice, add `note=os.urandom(8)` to every `AppClientMethodCallParams` and `PaymentParams`/`AssetTransferParams` in your test helpers --- it costs nothing and prevents intermittent test failures.

With those LocalNet behaviors in mind, the following test outlines go in `tests/test_vesting.py` (not part of the contract code):

```python
import pytest
import algokit_utils

class TestTokenVesting:
    def test_full_lifecycle(self, algorand):
        admin = algorand.account.localnet_dispenser()
        beneficiary = algorand.account.random()
        token_id = create_test_asa(algorand, admin, total=10_000_000_000)

        # Fund the beneficiary (MBR + ASA opt-in MBR + fee headroom)
        algorand.send.payment(algokit_utils.PaymentParams(
            sender=admin.address, receiver=beneficiary.address,
            amount=algokit_utils.AlgoAmount.from_micro_algo(500_000),
        ))
        # Beneficiary opts into the vesting ASA (required before claiming)
        algorand.send.asset_transfer(algokit_utils.AssetTransferParams(
            sender=beneficiary.address, receiver=beneficiary.address,
            asset_id=token_id, amount=0,
        ))

        vesting = deploy_vesting(algorand, admin)
        call_method(vesting, "initialize", [token_id])
        deposit_tokens(algorand, admin, vesting, token_id, 1_000_000_000)

        # Use short durations for LocalNet testing (seconds, not months).
        # Production contracts would use cliff_duration=90*86400, vesting_duration=365*86400.
        create_schedule(algorand, admin, vesting, beneficiary.address,
            total=1_000_000_000,
            cliff_duration=8,
            vesting_duration=30)

        assert get_claimable(vesting, beneficiary) == 0
        advance_time(algorand, 10)  # Past cliff
        claimable = get_claimable(vesting, beneficiary)
        assert 0 < claimable < 1_000_000_000

        call_method(vesting, "claim", [], sender=beneficiary.address)
        advance_time(algorand, 30)  # Past full vesting
        call_method(vesting, "claim", [], sender=beneficiary.address)
        call_method(vesting, "cleanup_schedule", [beneficiary.address])

    def test_revocation_returns_unvested(self, algorand):
        admin = algorand.account.localnet_dispenser()
        beneficiary = algorand.account.random()
        token_id = create_test_asa(algorand, admin, total=10_000_000_000)
        vesting = deploy_vesting(algorand, admin)
        call_method(vesting, "initialize", [token_id])
        deposit_tokens(algorand, admin, vesting, token_id, 1_000_000_000)
        create_schedule(algorand, admin, vesting, beneficiary.address,
            total=1_000_000_000,
            cliff_duration=8,
            vesting_duration=30)

        advance_time(algorand, 15)  # Past cliff, mid-vesting
        unvested = call_method(vesting, "revoke", [beneficiary.address])
        assert unvested.abi_return > 0
        claimed = call_method(vesting, "claim", [], sender=beneficiary.address)
        assert claimed.abi_return > 0

    def test_double_claim_fails(self, algorand):
        admin = algorand.account.localnet_dispenser()
        beneficiary = algorand.account.random()
        token_id = create_test_asa(algorand, admin, total=10_000_000_000)
        vesting = deploy_vesting(algorand, admin)
        call_method(vesting, "initialize", [token_id])
        deposit_tokens(algorand, admin, vesting, token_id, 1_000_000_000)
        create_schedule(algorand, admin, vesting, beneficiary.address,
            total=1_000_000_000,
            cliff_duration=8,
            vesting_duration=30)

        advance_time(algorand, 10)  # Past cliff
        call_method(vesting, "claim", [], sender=beneficiary.address)
        with pytest.raises(Exception, match="Nothing to claim"):
            call_method(vesting, "claim", [], sender=beneficiary.address)

# Helper: wraps the v4 send.call pattern for concise test code
def call_method(app_client, method, args, sender=None):
    return app_client.send.call(
        algokit_utils.AppClientMethodCallParams(
            method=method, args=args, sender=sender,
        )
    )
```

> **Tip:** Use the `simulate` endpoint for debugging and security testing, not just read-only queries. Simulate executes the full transaction logic without committing state changes or charging fees --- ideal for diagnosing failures and verifying security checks.

This is a client-side script illustrating the simulate pattern (not part of the contract code):

```python
import algokit_utils

# Build a transaction you expect to fail (e.g., an unauthorized claim)
attacker = algorand.account.random()

# Simulate without submitting --- see what would happen
result = algorand.new_group().add_app_call_method_call(
    app_client.params.call(
        algokit_utils.AppClientMethodCallParams(
            method="claim",
            sender=attacker.address,
        )
    )
).simulate()

# If the call would fail, the simulate response includes the failure reason.
# This confirms the contract correctly rejects unauthorized callers.
```

> Use this pattern to verify every security invariant: construct the attack, simulate it, and confirm rejection. Build a library of these "negative tests" alongside your positive test suite.


## Consolidated Imports

Throughout this chapter, imports were introduced incrementally as each feature required them. Here is the complete set of imports needed at the top of `smart_contracts/token_vesting/contract.py`:

```python
from algopy import (
    ARC4Contract, Account, Asset, BoxMap, Bytes, Global, GlobalState,
    Txn, UInt64, arc4, gtxn, itxn, op, subroutine,
)
```

## Summary

In this chapter you learned to:

- Write an ARC4 contract with `__init__`, bare methods, and ABI methods
- Use GlobalState and BoxMap for persistent on-chain storage
- Perform an ASA opt-in via inner transaction with fee=0
- Build an atomic group with a funding payment and an app call
- Calculate MBR for boxes and explain why it exists
- Implement safe integer math using wide arithmetic and explicit rounding
- Understand why reentrancy is impossible on Algorand (no callbacks from inner transactions)
- Explain why local state is unsafe for financial data (the ClearState trapdoor)

| Step | Feature | Concepts Introduced |
|------|---------|---------------------|
| 1 | Deploy and admin | Contract structure, ARC4Contract, __init__, GlobalState, ABI methods, ARC-56, contract addresses, schema immutability |
| 2 | Immutability | OnCompletion actions, bare methods, trust model |
| 3 | Token opt-in | ASAs, inner transactions, MBR, fee pooling, resource references |
| 4 | Deposit tokens | Atomic groups, typed gtxn parameters, verifying asset/receiver/amount |
| 5 | Vesting schedules | Local state's ClearState trapdoor, box storage, BoxMap, arc4.Struct, timestamps, I/O budget |
| 6 | Claim tokens | Integer math, overflow, wide arithmetic, rounding, subroutines, reentrancy safety |
| 7 | Revocation | Authorization, design patterns for capping allocations |
| 8 | Cleanup | Box lifecycle, MBR refunds |
| 9 | Read-only queries | Subroutine reuse, program size budgeting |

> **A note on typed clients.** Throughout this book, deployment and test scripts use the `AppFactory` and `app_client.send.call()` pattern with string method names. For larger production projects, use the **typed client** that `algokit project run build` generates automatically (e.g., `token_vesting_client.py` in the artifacts directory). The typed client provides method-specific functions with type-checked arguments (`app_client.send.initialize(args=InitializeArgs(vesting_asset=token_id))`), eliminating string method names and catching parameter errors at development time. See Cookbook recipe 16.3 for a complete example.

In the next chapter, we extend the vesting contract with NFTs for transferability. Then in Chapter 5, these same concepts reappear in a higher-stakes context as we build a constant product AMM with multi-token accounting, price curves, and LP token mechanics.

## Exercises

1. **(Apply)** Modify the vesting contract to support a second cliff: tokens vest 25% immediately at the first cliff (3 months), then the remaining 75% linearly from 3 to 12 months. What changes to `calculate_vested` are needed?

2. **(Apply)** Add a `pause` method that prevents all claims until unpaused, callable only by admin. What state field do you add, and which methods need to check it?

3. **(Analyze)** The `cleanup_schedule` method sends the freed MBR to the admin, not the beneficiary. Argue both sides: should the MBR refund go to the admin (who funded it) or the beneficiary (whose data it stored)? What are the security implications of each choice?

4. **(Create)** Design an extension where the admin can increase a beneficiary's total allocation after the schedule is already created. What new method is needed? What happens to already-vested tokens? What security checks prevent abuse?

5. **(Create)** The vesting contract uses a single admin address. Design a modification where admin operations (initialize, create_schedule, revoke) require approval from 2-of-3 multisig signers. What changes to the admin check pattern are needed? How does Algorand's native multisig support simplify this compared to implementing multisig logic in the contract itself?

## Further Reading

- [Algorand Python Language Guide](https://dev.algorand.co/algokit/languages/python/lg-structure/) --- program structure, decorators, `__init__` semantics
- [Types](https://dev.algorand.co/algokit/languages/python/lg-types/) --- UInt64, Bytes, BigUInt, ARC-4 types
- [Storage](https://dev.algorand.co/algokit/languages/python/lg-storage/) --- GlobalState, LocalState, Box, BoxMap
- [Transactions](https://dev.algorand.co/algokit/languages/python/lg-transactions/) --- gtxn parameters, inner transactions
- [ARC-4 in Python](https://dev.algorand.co/algokit/languages/python/lg-arc4/) --- abimethod, baremethod, ARC4Contract
- [Box Storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/) --- MBR formula, I/O budget, lifecycle
- [App Client](https://dev.algorand.co/algokit/utils/python/app-client/) --- deployment, method calls, simulation
- [Costs and Constraints](https://dev.algorand.co/concepts/smart-contracts/costs-constraints/) --- program size, opcode budget, stack limits
- [Rekeying](https://dev.algorand.co/concepts/accounts/rekeying/) --- the rekey_to field and its security implications
- [AVM Opcodes](https://dev.algorand.co/reference/algorand-teal/opcodes/) --- mulw, divmodw, bsqrt, and all other opcodes

## Before You Continue

Before starting the next chapter, you should be able to:

- [ ] Explain the difference between the approval program and clear state program
- [ ] Write an ARC4 contract with `__init__`, bare methods, and ABI methods
- [ ] Use GlobalState and BoxMap for persistent storage
- [ ] Perform an ASA opt-in via inner transaction with fee=0
- [ ] Build an atomic group with a funding payment and an app call
- [ ] Calculate MBR for boxes and explain why it exists
- [ ] Explain why local state is unsafe for financial data

If any of these are unclear, revisit the relevant section before proceeding.
