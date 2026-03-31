\newpage




\part{Foundations}

Part I establishes the mental model, tooling, and core skills you need for everything that follows. You will learn how Algorand's execution model differs from traditional programming, set up your development environment, learn how to test smart contracts, and build your first two smart contracts --- a token vesting system and an NFT extension --- that introduce every foundational concept.

# The Algorand Mental Model

Every smart contract bug that lost real money on Algorand --- from the $3 million Tinyman exploit to common MBR miscalculations that lock funds forever --- traces back to a flawed mental model of how the blockchain works. This chapter gives you the accurate model that prevents those mistakes.

Before writing a single line of contract code, you need a mental model of how Algorand works that is accurate enough to reason about what your contracts can and cannot do.

## Algorand in One Paragraph

Algorand is a *proof-of-stake* blockchain with *instant finality*, a ~2.8-second block time, and no forking. Every confirmed transaction is final --- there is no "wait for 6 confirmations" like Bitcoin. The network runs a Byzantine agreement protocol where block proposers and committee voters are selected secretly via a *Verifiable Random Function* (VRF). Because selection is random and unpredictable, there is no way to target validators for attack before they reveal themselves. This design gives Algorand strong security guarantees with thousands of validator nodes participating in consensus. (See the [official overview](https://dev.algorand.co/concepts/protocol/overview/) and [Why Algorand?](https://dev.algorand.co/getting-started/why-algorand/) for details on the consensus protocol.)

Before we dive into the details, here is what a complete, deployable Algorand smart contract looks like. This is an illustrative example showing the simplest possible Algorand contract:

```python
from algopy import ARC4Contract, arc4

class HelloAlgorand(ARC4Contract):
    @arc4.abimethod
    def hello(self, name: arc4.String) -> arc4.String:
        return "Hello, " + name
```

This is a complete smart contract. It has one method that takes a string and returns a greeting. We will understand every line of this by the end of Chapter 3. For now, notice three things: it is plain Python with type annotations, it inherits from `ARC4Contract`, and methods are decorated with `@arc4.abimethod`. That is all it takes.

## Execution Model: Smart Contracts Are Transaction Validators

The most important conceptual shift for a developer coming from traditional software: **Algorand smart contracts do not run continuously**. They are not servers. They are not daemons. They execute once per transaction, validate whether the transaction should be approved or rejected, and then stop.

When a user submits a transaction that calls your smart contract, the *Algorand Virtual Machine (AVM)* loads your contract's bytecode, runs it against the transaction data, and produces a boolean result. If the program returns true, the transaction is approved and its effects are committed atomically. If it returns false or fails at any point, the entire transaction is rejected as if it never happened.

This means your contract code is a set of validation rules, not a running process. State changes happen as side effects of successful validation. This is fundamentally different from the model used by some other blockchains, where contracts are called imperatively and can modify state directly during execution. On Algorand, the transaction *is* the input, and your contract decides whether to accept it. (See [Smart Contracts Overview](https://dev.algorand.co/concepts/smart-contracts/overview/).)

## Two Programs per Contract

Every Algorand smart contract consists of two programs written in *TEAL* (Transaction Execution Approval Language), the AVM's low-level bytecode. You will never write TEAL directly --- PuyaPy compiles your Python code to TEAL automatically --- but the term appears throughout Algorand documentation, so it is worth knowing. (See [Applications](https://dev.algorand.co/concepts/smart-contracts/apps/) and the [AVM reference](https://dev.algorand.co/concepts/smart-contracts/avm/).)

**The *approval program*** handles all normal operations: creation, method calls, opt-ins, close-outs, updates, and deletes. When someone calls your contract, the approval program runs. This is where all your business logic lives.

**The *clear state program*** runs when a user wants to forcibly remove their local state from your application. The critical property: **the user's local state is always cleared regardless of whether the clear state program approves or rejects**. If the program fails, state changes to the *application's* state are rolled back, but the user's local state is still removed. This is a deliberate protocol-level guarantee that users can always exit an application. The security implication is severe: never store critical financial data exclusively in local state, because users can always delete it.

## The Account Model

Algorand tracks balances per account, the way a bank ledger tracks your balance in a single row that goes up or down with each transaction. (This is called an *account-based model*. The alternative, used by Bitcoin, is the *UTXO* (Unspent Transaction Output) model, which tracks individual "coins" that are created and consumed --- but we will not need to understand that here.) Every account has a balance of Algos and can hold Algorand Standard Assets (ASAs). Accounts are identified by 32-byte public keys encoded as 58-character base32 strings. (See [Accounts Overview](https://dev.algorand.co/concepts/accounts/overview/).)

### *Minimum Balance Requirement* (MBR)

Every account must maintain a minimum balance of Algos to exist on the chain. This is Algorand's anti-spam mechanism --- it prevents an attacker from creating billions of empty accounts to bloat the ledger. The base MBR is **100,000 microAlgos (0.1 Algo)**. Each additional resource the account holds increases the MBR:

- Each ASA opted into: +100,000 microAlgos (0.1 Algo)
- Each application created: +100,000 microAlgos + state schema costs
- Each application opted into: +100,000 microAlgos + local state schema costs
- Each box created by the application: +2,500 + 400 × (name_length + data_size) microAlgos, where name_length and data_size are in bytes. (Only application accounts can create boxes --- see [Smart Contract Accounts](#smart-contract-accounts) below.)

If a transaction would cause an account's balance to drop below its MBR, the transaction fails. This is one of the most common errors new developers encounter: "balance below minimum" after creating assets or boxes without sufficient funding. (See [Protocol Parameters](https://dev.algorand.co/concepts/protocol/protocol-parameters/) for the full MBR schedule.)

### The Opt-In Requirement

On some blockchains, anyone can send you tokens you never asked for, polluting your wallet with worthless or malicious assets. Algorand prevents this by requiring accounts to explicitly *opt in* to each ASA before they can hold it. An opt-in is a zero-amount asset transfer to yourself. This costs 0.1 Algo in MBR. (See [Asset Operations](https://dev.algorand.co/concepts/assets/asset-operations/).)

The practical impact for smart contract development: your contract must opt into every ASA it will hold, and users must opt into any ASA your contract sends to them before they can receive it.

### Smart Contract Accounts

Every deployed smart contract has a deterministic address derived from its application ID: `SHA512_256("appID" || big_endian_8_byte(app_id))`. In this formula, `"appID"` is the literal ASCII string used as a domain separator, and `||` denotes concatenation (not bitwise OR). This derivation is completely different from how user wallet addresses are generated (from Ed25519 public keys), so application addresses are guaranteed never to collide with user accounts. The resulting address can hold Algos and ASAs just like a regular account. The contract's logic governs all outflows via *inner transactions* (see below). No one has a private key for this address --- the code is the sole custodian.

### On-Chain Storage

Smart contracts need to persist data between transactions. Algorand provides three distinct storage mechanisms, each with different trade-offs. Understanding all three upfront will save you from costly architectural mistakes --- choosing the wrong one for financial data is the most common beginner error.

**Global state** is a fixed set of key-value pairs belonging to the application itself. Think of it as a single-row configuration table. You declare how many `UInt64` and `Bytes` slots the application needs at creation time, and the schema can never change afterward --- if you need 5 uint slots later but only declared 3, you must deploy an entirely new contract. Maximum 64 key-value pairs, each with key plus value limited to 128 bytes combined. Use global state for contract-wide settings: an admin address, a token ID, a counter, configuration flags. Every application has global state.

**Local state** is per-user storage. When a user opts into your application, they get their own set of key-value pairs (up to 16, same 128-byte limit per pair). The MBR cost is charged to the opting-in user, which seems fair. However, local state has a critical limitation: **users can delete their local state at any time** by sending a ClearState transaction, and the protocol guarantees this always succeeds regardless of what your contract's clear state program does. This is by design --- no application should be able to trap a user's account. The implication for financial contracts is severe: never store debts, balances, or vesting records exclusively in local state, because the user can erase them. Local state is suitable for user preferences, scores, or caches --- data where unilateral deletion is acceptable.

**Box storage** is application-controlled key-value storage. Each entry is an independent "box" with a name (1--64 bytes) containing up to 32,768 bytes of data. Only the application's code can create, read, modify, or delete its own boxes --- users cannot unilaterally remove them. This makes boxes the correct choice for any per-user data the application must control: balances, vesting schedules, order records, vote commitments.

Box storage introduces one concept that surprises newcomers: **box references**. Every transaction that reads or writes a box must declare which boxes it will access in a `boxes` array on the transaction. Each declared reference grants 1,024 bytes (1KB) of I/O budget. If a box's name plus contents exceed 1KB, you need multiple references to the same box. Forgetting to declare box references produces a "box read/write budget exceeded" error. We will see this in practice when we build the vesting contract in Chapter 3.

| Storage Type | Capacity | Who Controls Deletion | Best For |
|-------------|----------|----------------------|----------|
| Global state | 64 pairs, ≤128 bytes each | Only the application | Contract-wide configuration |
| Local state | 16 pairs per user, ≤128 bytes each | User can delete anytime via ClearState | Non-critical user preferences |
| Box storage | 32,768 bytes per box, unlimited count | Only the application | Financial data, per-user records |

A practical rule of thumb: use **global state** for contract-wide configuration, **local state** only for data that does not matter if the user erases it, and **box storage** for anything involving money or obligations. (See the official storage guides: [Global](https://dev.algorand.co/concepts/smart-contracts/storage/global/), [Local](https://dev.algorand.co/concepts/smart-contracts/storage/local/), [Box](https://dev.algorand.co/concepts/smart-contracts/storage/box/).)

## Transactions and Atomicity

### Transaction Types

Algorand has seven developer-facing [transaction types](https://dev.algorand.co/concepts/transactions/types/) (an eighth, heartbeat, is used internally by the consensus protocol and is not relevant to contract development):

1. **Payment** --- Send Algos from one account to another
2. **Asset Transfer** --- Send ASAs between accounts (also used for opt-in)
3. **Asset Configuration** --- Create, reconfigure, or destroy an ASA
4. **Asset Freeze** --- Freeze or unfreeze an account's holding of an ASA
5. **Application Call** --- Call a smart contract method
6. **Key Registration** --- Register participation keys for consensus
7. **State Proof** --- Submit state proof attestations

For smart contract development, you primarily work with payments, asset transfers, and application calls. (See the [Transaction Reference](https://dev.algorand.co/concepts/transactions/reference/) for complete field specifications.)

### Atomic Groups

Up to 16 transactions can be bundled into an [atomic group](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/). All transactions in a group either succeed together or fail together --- there is no partial execution. This is the foundation of DeFi on Algorand: a user can bundle "send tokens to a pool" and "call the swap method" into one atomic group, guaranteeing they never send tokens without receiving the swap output.

Atomic groups are coordinated off-chain: the client constructs all transactions, assigns them a common group ID (the hash of all transactions), and submits the bundle. The protocol validates and executes the group atomically.

### Fees

The minimum [transaction fee](https://dev.algorand.co/concepts/transactions/fees/) is **1,000 microAlgos (0.001 Algo)** per transaction. Fees are validated at the group level: the sum of all fees in a group must meet the sum of all minimum fees. This enables *fee pooling* --- one transaction can overpay to cover others in the group.

### Inner Transactions

So far we have described transactions submitted by users (off-chain). Smart contracts can also issue [inner transactions](https://dev.algorand.co/concepts/smart-contracts/inner-txn/) --- transactions sent from within contract code during execution. When your contract needs to send Algos, transfer an ASA, or call another contract, it does so by emitting an inner transaction. Inner transactions execute atomically within the outer transaction: if the outer transaction fails, all inner transactions are rolled back too.

The distinction from atomic groups is important: atomic groups are assembled *off-chain* by a client and submitted as a bundle, while inner transactions are created *on-chain* by contract logic during execution. A contract can issue up to 256 inner transactions per group. We will use inner transactions extensively starting in Chapter 3.

## What You Cannot Do

Understanding limits is as important as understanding capabilities:

- **No floating point.** The AVM has only `uint64` and `bytes` types. All math is integer-only. Prices must be represented as rational numbers (numerator/denominator). (See [AVM](https://dev.algorand.co/concepts/smart-contracts/avm/).)
- **No unbounded loops.** The *opcode budget* limits how much computation a single call can perform. Each AVM instruction costs a fixed number of units (called opcodes), and your contract gets a budget of 700 per application call. Since AVM v5, the budget is pooled across all application calls in a group --- a group with 4 app calls gets a total of 2,800. Contracts that need more computation can pad the group with no-op app calls to increase the shared budget (covered in Chapter 7). The pooled budget is roughly enough for several hundred arithmetic operations and dozens of state reads per call, but not enough for expensive cryptographic operations like signature verification without pooling. If your logic exceeds the budget, the transaction fails. (LogicSig programs get a separate pool of 20,000 per transaction in the group.) You cannot iterate over an arbitrarily large data set in one call. (See [Costs and Constraints](https://dev.algorand.co/concepts/smart-contracts/costs-constraints/).)
- **No callbacks or fallback functions.** When your contract sends tokens via an inner transaction, no code executes on the receiving side. This eliminates classical reentrancy attacks. (See [Ethereum to Algorand](https://dev.algorand.co/getting-started/ethereum-to-algorand/) for a comparison of security models.)
- **Cross-contract state is read-only from within TEAL.** Your contract can read another contract's global state via `app_global_get_ex`, but cannot write to it. Modifications to another contract's state require calling that contract via an inner transaction. State changes from earlier transactions in a group ARE visible to later transactions in the same group --- they share a single copy-on-write state object. The group's aggregate changes are committed to the ledger only after every transaction succeeds.
- **No private on-chain data.** All state (global, local, boxes) is publicly readable off-chain via algod and indexer APIs. Boxes are private *on-chain* (only the owning app can read them in TEAL), but anyone can read them via the REST API.
- **No upgradeable contracts by default.** If you reject `UpdateApplication`, the code is immutable. This is the recommended default for DeFi contracts. (See [Lifecycle](https://dev.algorand.co/concepts/smart-contracts/lifecycle/).)

## Setting Up Your Development Environment

Before starting the projects in the following chapters, you need a working development environment. The Algorand toolchain is centered on [AlgoKit](https://dev.algorand.co/algokit/algokit-intro/), a CLI that orchestrates project scaffolding, local network management, contract compilation, client generation, and deployment. Think of it as the `cargo` or `create-react-app` of Algorand --- one entry point to the entire toolchain. (See the [AlgoKit Quick Start](https://dev.algorand.co/getting-started/algokit-quick-start/) for installation.)

For AI-assisted development, the ecosystem also offers **VibeKit** (`vibekit init`), a CLI that configures AI coding agents (Claude Code, Cursor, VS Code Copilot) for Algorand development. VibeKit installs agent skills, documentation lookup tools, and blockchain interaction tools so your AI assistant can write, compile, deploy, and debug contracts within a single conversation --- with private keys kept safely isolated from the language model. VibeKit is complementary to AlgoKit: AlgoKit is the build system, VibeKit teaches your AI how to use it. See https://getvibekit.ai for setup.

You need three things installed: **Python 3.12 or later** (for writing Algorand Python contracts and running tests), **Docker with Compose v2.5.0 or later** (for running a local Algorand network in containers), and **AlgoKit itself**.

Install AlgoKit:

```bash
# macOS (via Homebrew)
brew install algorandfoundation/tap/algokit

# Any platform (via pipx --- recommended if you already manage Python tools this way)
pipx install algokit

# Verify the installation
algokit --version    # Should show 2.9.x or later
```

Run the doctor to check that all dependencies are present and correctly configured:

```bash
algokit doctor
```

This checks for Python, Docker, Docker Compose, git, and other prerequisites. Fix anything it flags before proceeding.

Start **LocalNet** --- a private Algorand network running in Docker with an algod node, an indexer, and a Key Management Daemon (KMD):

```bash
algokit localnet start
algokit localnet status    # Verify all containers are running
algokit localnet explore   # Open a block explorer UI for your local network
```

The `explore` command opens Lora (a web-based block explorer) pointed at your LocalNet, which is useful for inspecting transactions, accounts, and application state as you develop.

LocalNet gives you instant block finality, pre-funded test accounts (accessible via KMD), and zero dependence on TestNet faucets. Blocks are produced on-demand when transactions are submitted, so there is no waiting. You can reset the entire network to a clean state at any time:

```bash
algokit localnet reset     # Wipes all state, restarts fresh
```

Now scaffold your first project:

```bash
mkdir algorand-book && cd algorand-book
algokit init -t python --name my-first-contract
```

The template wizard may ask a few questions even with `-t python` --- it may prompt for the language (select Python), and whether to run `algokit project bootstrap`. Accept the defaults for now. AlgoKit generates a *workspace* structure with your contract project nested inside:

```
my-first-contract/                     # Workspace root
  .algokit.toml                        # Workspace configuration
  my-first-contract.code-workspace     # VS Code workspace file
  projects/
    my-first-contract/                 # Your contract project
      smart_contracts/
        hello_world/
          contract.py                  # Your Algorand Python contract
          deploy_config.py             # Deployment configuration
      .algokit.toml                    # Project configuration
      pyproject.toml                   # Python dependencies
```

The key directory is `projects/my-first-contract/smart_contracts/hello_world/` --- this is where your contract code lives. In subsequent chapters, you will rename this directory to match each project (e.g., `smart_contracts/token_vesting/`, `smart_contracts/constant_product_pool/`). You can also create additional contract directories in the same project. Navigate into the contract project before continuing:

```bash
cd my-first-contract/projects/my-first-contract
```

Install the project's Python dependencies:

```bash
algokit project bootstrap all
```

This command installs all project dependencies by running the appropriate package manager (Poetry, in the default Python template). It installs `algorand-python` (the type stubs that provide IDE autocompletion and type checking), `puyapy` (the compiler that transforms your Python code into TEAL bytecode), `algokit-utils` (the client library for interacting with Algorand), and testing dependencies. If you already ran bootstrap during `algokit init`, you can skip this step.

> **VS Code tip:** If VS Code shows import errors (yellow or red squiggly lines under `import algokit_utils`), it does not know which Python environment to use. Open the Command Palette (`Cmd+Shift+P` on macOS, `Ctrl+Shift+P` on Windows/Linux), run **Python: Select Interpreter**, and choose the `.venv` inside your `projects/my-first-contract/` directory. This points VS Code at the virtual environment where `algokit project bootstrap all` installed your dependencies, giving you autocompletion and type checking. Alternatively, open the `projects/my-first-contract/` folder directly in VS Code instead of the workspace root --- its `.vscode/settings.json` is already configured by AlgoKit to use the correct interpreter.

> **Note:** This book uses Algorand Python (PuyaPy) exclusively, but Algorand smart contracts can also be written in **TEALScript**, a TypeScript-based language that compiles to the same TEAL bytecode. If your team prefers TypeScript, scaffold with `algokit init -t typescript`. The AVM concepts, security patterns, and architectural decisions taught in this book apply identically regardless of which language you choose --- only the syntax differs.

Verify the compilation pipeline works by compiling the template contract:

```bash
algokit project run build
```

This should produce files in `smart_contracts/artifacts/hello_world/`: a `.approval.teal` file, a `.clear.teal` file, an `.arc56.json` application specification, and a generated typed client (`_client.py`). The artifacts are placed in a subdirectory matching the contract directory name. If compilation succeeds without errors, your environment is ready.

> **Note:** `algokit project run build` runs the full build pipeline defined in `.algokit.toml`, including compilation and typed client generation. You can also compile standalone files with `algokit compile py`, but `algokit project run build` is preferred when using the template project structure because it places artifacts in the correct location and generates typed clients automatically.

Now deploy the compiled contract to LocalNet and call its method. Create a file called `interact.py` in the project root (next to `pyproject.toml`):

```python
from pathlib import Path
import algokit_utils

# Connect to LocalNet and get a pre-funded account
algorand = algokit_utils.AlgorandClient.default_localnet()
deployer = algorand.account.localnet_dispenser()

# Deploy the contract using the compiled ARC-56 app spec
app_spec = Path("smart_contracts/artifacts/hello_world/HelloWorld.arc56.json").read_text()
factory = algorand.client.get_app_factory(
    app_spec=app_spec,
    default_sender=deployer.address,
)
app_client, deploy_result = factory.deploy()
print(f"Deployed app ID: {app_client.app_id}")
print(f"App address:     {app_client.app_address}")

# Call the hello method
result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="hello",
        args=["World"],
    )
)
print(f"Return value:    {result.abi_return}")  # "Hello, World"
```

Run it (make sure LocalNet is running):

```bash
poetry run python interact.py
```

You should see output like:

```
Deployed app ID: 1001
App address:     W3EP...
Return value:    Hello, World
```

That is the complete development loop: write a contract in Python, compile it to TEAL, deploy it to a running network, and call its methods from a client script. Every project in this book follows the same cycle --- **edit** the contract in `contract.py`, **compile** with `algokit project run build`, **deploy** using AlgoKit Utils, **interact** by calling methods, and **test** with pytest.

### Connecting to an Already-Deployed Contract

The script above deploys a fresh contract every time it runs. In practice, you will often want to interact with a contract that is already deployed --- for example, calling a contract on TestNet or MainNet, or reconnecting to a LocalNet contract you deployed earlier. Use `get_app_client_by_id` with the application ID instead of the factory:

```python
from pathlib import Path
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
caller = algorand.account.localnet_dispenser()

# Connect to an already-deployed contract by its application ID
app_client = algorand.client.get_app_client_by_id(
    app_spec=Path("smart_contracts/artifacts/hello_world/HelloWorld.arc56.json").read_text(),
    app_id=1001,  # replace with your contract's app ID
    default_sender=caller.address,
)

# Call methods exactly the same way as before
result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="hello",
        args=["World"],
    )
)
print(result.abi_return)  # "Hello, World"
```

You still need the ARC-56 app spec so the client knows the contract's method signatures and ABI encoding, but deployment is skipped entirely. This is the pattern you would use to build a frontend or backend service that talks to a live contract.

### App Specs and Typed Clients

The ARC-56 app spec (`.arc56.json`) is the portable description of your contract's public API --- its method signatures, argument types, return types, and state schema. Think of it like an OpenAPI/Swagger spec for a REST API. App developers typically publish their app specs in their GitHub repository or SDK package so that others can build integrations against their contracts.

The examples above use the **generic client** (`get_app_factory`, `get_app_client_by_id`), where method names are passed as strings and arguments are untyped:

```python
result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(method="hello", args=["World"])
)
```

This works, but you get no autocompletion and no compile-time type checking --- if you misspell a method name or pass the wrong argument type, you will not find out until runtime.

When you run `algokit project run build`, the build pipeline also generates a **typed client** (`_client.py`) from the app spec. This is an auto-generated Python class with real methods matching your contract:

```python
import algokit_utils
from smart_contracts.artifacts.hello_world.hello_world_client import (
    HelloArgs, HelloWorldClient, HelloWorldFactory
)

algorand = algokit_utils.AlgorandClient.default_localnet()
caller = deployer = algorand.account.localnet_dispenser()

# Option A: Deploy a new contract, then call it
factory = HelloWorldFactory(algorand=algorand, default_sender=deployer.address)
app_client, deploy_result = factory.deploy()

# Option B: Connect to an already-deployed contract by app ID
app_client = HelloWorldClient(algorand=algorand, app_id=1001, default_sender=caller.address)

# Either way, call methods the same way --- with real methods and typed args
result = app_client.send.hello(args=HelloArgs(name="World"))
print(result.abi_return)  # "Hello, World"
```

Typed clients catch errors earlier and make your code more readable. The projects in this book use the generic client for clarity (so you can see exactly what is happening), but in production code, typed clients are preferred. If you are integrating with a third-party contract, you can generate a typed client from their published app spec using `algokit generate client`.

## Summary

In this chapter you learned to:

- Explain Algorand's execute-once validation model and how it differs from traditional server-side or EVM-style programming
- Distinguish the approval program from the clear state program and explain why local state is unsafe for critical financial data
- Compare global state, local state, and box storage and explain when to use each
- Calculate Minimum Balance Requirements for accounts, ASAs, boxes, and application state
- Describe atomic groups and fee pooling and explain why they are foundational to DeFi on Algorand
- Distinguish atomic groups (off-chain bundling) from inner transactions (on-chain contract-issued transactions)
- Identify what the AVM cannot do: no floating point, no unbounded loops, no callbacks, no cross-contract mid-group state reads, no private on-chain data
- Set up a complete Algorand development environment with AlgoKit, LocalNet, and PuyaPy
- Deploy a contract to LocalNet and call its methods using AlgoKit Utils

| Concept | Key Takeaway |
|---------|-------------|
| Execution model | Contracts are transaction validators, not running processes |
| Two programs | Approval program = business logic; clear state program = forced exit |
| Account model | Account-based (not UTXO); every account has Algo balance + opted-in ASAs |
| MBR | Anti-spam mechanism; 0.1 Algo base + increments per resource held |
| Opt-in | Accounts must explicitly accept each ASA; prevents token spam |
| Atomic groups | Up to 16 transactions; all-or-nothing execution; foundation of DeFi composability |
| Fee pooling | Group-level fee validation; one transaction can overpay for others |
| Inner transactions | Contract-issued on-chain transactions; up to 256 per group; atomic with outer transaction |
| Smart contract accounts | Deterministic address from app ID; code is sole custodian |
| On-chain storage | Global state for config; local state for preferences (user-deletable); box storage for financial data |
| AVM constraints | uint64 + bytes only; 700 opcode budget per app call; no reentrancy |

## Exercises

1. **(Recall)** What happens if a transaction would reduce an account's balance below its Minimum Balance Requirement?

2. **(Recall)** Why can't you read another contract's mid-group state changes in the same atomic group?

3. **(Apply)** Calculate the MBR cost for a contract that creates 3 boxes (each 64 bytes with 10-byte keys), opts into 2 ASAs, and has 5 global uint state slots. Show your work using the MBR costs listed in this chapter.

4. **(Analyze)** A developer proposes storing all user balances in local state instead of box storage. What attack could exploit this? Describe the specific transaction sequence an attacker would use.

5. **(Analyze)** A DeFi protocol bundles a token transfer and a contract call into an atomic group, but does not verify the group size inside the contract. Describe how an attacker could exploit this by appending extra transactions to the group.

## Further Reading

The official Algorand developer documentation at [dev.algorand.co](https://dev.algorand.co/) provides comprehensive references for every concept in this chapter:

- [Smart Contracts Overview](https://dev.algorand.co/concepts/smart-contracts/overview/) --- execution model, two-program architecture
- [AVM](https://dev.algorand.co/concepts/smart-contracts/avm/) --- opcode budget, stack types, program constraints
- [Accounts Overview](https://dev.algorand.co/concepts/accounts/overview/) --- MBR, account types, address format
- [Storage Overview](https://dev.algorand.co/concepts/smart-contracts/storage/overview/) --- comparison of global, local, and box storage
- [Transaction Types](https://dev.algorand.co/concepts/transactions/types/) --- all seven transaction types with field specifications
- [Atomic Groups](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/) --- group construction and all-or-nothing semantics
- [Transaction Fees](https://dev.algorand.co/concepts/transactions/fees/) --- minimum fee, fee pooling
- [Inner Transactions](https://dev.algorand.co/concepts/smart-contracts/inner-txn/) --- contract-issued transactions, budget implications
- [Protocol Parameters](https://dev.algorand.co/concepts/protocol/protocol-parameters/) --- all consensus-level limits and costs
- [Algorand Python Overview](https://dev.algorand.co/algokit/languages/python/overview/) --- PuyaPy compiler, language guide
- [AlgoKit Quick Start](https://dev.algorand.co/getting-started/algokit-quick-start/) --- installation, LocalNet, first deployment
- [Ethereum to Algorand](https://dev.algorand.co/getting-started/ethereum-to-algorand/) --- mapping of concepts for developers with EVM experience
