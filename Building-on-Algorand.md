---
title: "Building on Algorand"
subtitle: "Smart Contracts from First Principles to Production DeFi"
author: "Generated with Claude"
date: "March 2026"
documentclass: report
classoption:
  - 11pt
  - twoside
  - openright
geometry:
  - margin=1in
  - top=1.2in
  - bottom=1.2in
mainfont: "DejaVu Serif"
sansfont: "DejaVu Sans"
monofont: "DejaVu Sans Mono"
fontsize: 11pt
linestretch: 1.15
toc: true
toc-depth: 2
numbersections: true
colorlinks: true
linkcolor: "blue!60!black"
urlcolor: "blue!60!black"
toccolor: "blue!60!black"
header-includes:
  - |
    ```{=latex}
    \usepackage{fvextra}
    \DefineVerbatimEnvironment{Highlighting}{Verbatim}{breaklines,commandchars=\\\{\},fontsize=\small}
    \usepackage{fancyhdr}
    \pagestyle{fancy}
    \fancyhf{}
    \fancyhead[LE]{\leftmark}
    \fancyhead[RO]{\rightmark}
    \fancyfoot[C]{\thepage}
    \renewcommand{\headrulewidth}{0.4pt}
    \setlength{\headheight}{14pt}
    \usepackage{titlesec}
    \titleformat{\chapter}[display]{\normalfont\huge\bfseries}{\chaptertitlename\ \thechapter}{20pt}{\Huge}
    \titlespacing*{\chapter}{0pt}{-20pt}{40pt}
    ```
---

\newpage

# Legal Notice {-}

> **DISCLAIMER --- AI-GENERATED CONTENT**
>
> This book was generated with the assistance of artificial intelligence (Claude, by Anthropic). While the code has been compiled, tested, and reviewed, AI-generated content may contain errors, inaccuracies, or outdated information. **Readers should always do their own research (DYOR)** and independently verify any claims, code patterns, or security assumptions presented here.
>
> **The smart contracts in this book are for educational purposes.** Any code intended for production use or deployment to Algorand mainnet **must undergo a professional, independent security audit** before handling real assets. **Use of smart contracts on mainnet can result in loss of funds.** Smart contract vulnerabilities, bugs, or misconfigurations can lead to irreversible loss of assets. Exercise extreme caution when deploying to mainnet, start with small amounts, and never deploy unaudited code that controls assets you cannot afford to lose.
>
> The authors and AI systems involved in producing this book accept no liability for any losses resulting from the use of the code or information contained herein.

\newpage

# Preface {-}

This book takes a senior software engineer from zero smart contract knowledge to deploying production-quality *DeFi* (decentralized finance, the ecosystem of financial applications built on blockchains instead of banks) applications on Algorand. It uses **[Algorand Python](https://dev.algorand.co/concepts/smart-contracts/languages/python/) (Puya)**, the newest and most idiomatic approach --- real Python code that compiles to TEAL bytecode via a multi-stage optimizing compiler.

### Who This Book Is For

This book is written for experienced software engineers who know Python well but have never built a smart contract. You should be comfortable with Python 3.12+ (type annotations, classes, decorators), basic command-line tooling, and Docker. The projects assume you can read and write Python fluently --- the learning curve here is blockchain concepts and AVM constraints, not the programming language.

This book is *not* for you if you are looking for Solidity or EVM development (Algorand's execution model is fundamentally different), or if you want a theory-only treatment of blockchain concepts without building working software.

### How This Book Is Organized

The book is structured around nine progressively complex chapters, each built incrementally so that every concept is introduced at the moment you need it:

- **Chapter 1 --- The Algorand Mental Model.** The execution model, account system, and constraints every developer must internalize, plus setting up your development environment and deploying your first contract.

- **Chapter 2 --- Testing Smart Contracts.** You build a simplified vesting contract, write comprehensive tests against it, and discover through failing tests exactly what the full implementation in Chapter 3 must solve. This chapter establishes the testing patterns used throughout the rest of the book.

- **Chapter 3 --- Project 1: A Token Vesting Contract.** A complete token vesting contract that introduces every foundational concept: state management, ASA handling, inner transactions, box storage, integer math, and security patterns. By the end of Chapter 3 you can build and deploy a production-quality smart contract from scratch.

- **Chapter 4 --- NFTs: Extending the Vesting Contract with Transferability.** You extend the vesting contract by minting an NFT for each schedule, introducing the ownership-by-asset pattern, ARC-3 metadata, clawback mechanics, and the mint-then-deliver coordination pattern.

- **Chapter 5 --- Project 2: A Constant Product AMM.** You apply the foundations to DeFi by building a Uniswap V2-style automated market maker with multi-token accounting, price curves, LP (liquidity provider) token mechanics, a TWAP price oracle, and security hardening.

- **Chapter 6 --- Yield Farming: Extending the AMM with Staking Rewards.** You extend the AMM with a staking contract where LPs lock LP tokens to earn reward tokens, introducing the Synthetix-style reward accumulator pattern, duration multipliers, and smart contract composition via cross-contract state reads.

- **Chapter 7 --- Common Patterns and Idioms.** A patterns chapter covers cross-cutting production concerns: fee subsidization, MBR lifecycle, canonical ordering, event emission, and opcode budget management.

- **Chapter 8 --- Project 3: A Delegated Limit Order Book with LogicSig Agents.** Algorand's second execution model --- Logic Signatures --- applied to a delegated limit order book. This introduces the hybrid stateful/stateless architecture, template variables, keeper bots, packed binary data, and composability with the AMM from Chapter 5.

- **Chapter 9 --- Project 4: Private Governance Voting with Zero-Knowledge Proofs.** Pushing the AVM to its limits with a private governance voting system using zero-knowledge proofs, elliptic curve operations (BN254), and the MiMC hash. Also covers Algorand's Falcon-based post-quantum security roadmap.

Two appendices provide lasting reference value: the **Algorand Smart Contract Cookbook** contains 50+ standalone code examples organized by topic, and the **Consolidated Gotchas Cheat Sheet** catalogs the most common mistakes and how to avoid them.

### Conventions Used in This Book

The following typographic conventions are used throughout:

- *Italic* indicates new terms when they are first introduced.
- `Monospace` is used for code elements: class names, method names, variables, file paths, and command-line input/output.
- **`Bold monospace`** indicates commands or text that you should type literally.

Code examples are presented incrementally --- each section adds to the contract built in previous sections. When a code block shows a complete method or class, it includes enough context (imports, class declaration) to be unambiguous about where the code belongs.

### Test Helpers and Client-Side Code

Chapter 2 introduces the foundational testing setup --- pytest fixtures, reusable helpers (`advance_time`, `create_test_asa`, `fund_account`), and the integration testing patterns used throughout the book. Each subsequent chapter includes test outlines specific to its contract. The helper functions referenced in tests are straightforward wrappers around the AlgoKit Utils and algosdk calls shown in each chapter's deployment and interaction scripts. The client-side scripts in this book use the **AlgoKit Utils v4 API** --- `AppFactory` for deployment, `app_client.send.call()` for method invocations, and `algorand.send.*` for standalone transactions. For production projects, you can also generate **typed clients** via `algokit generate client` (see Cookbook recipe 16.3) for compile-time type safety.

> **Note:** Admonitions like this one provide supplementary information, tips, or context that is useful but not essential to following the main narrative.

Both types appear throughout the book.

> **Warning:** Warning admonitions highlight security concerns, common mistakes, or behavior that could cause loss of funds in a production contract. Do not skip these.

Client-side code uses two styles: **AlgoKit Utils v4** (`AlgorandClient`, `AppFactory`, `app_client.send.call(...)`) for deployment and ABI interactions, and **raw algosdk** (`transaction.PaymentTxn(...)`, `calculate_group_id(...)`) for atomic groups requiring fine-grained control over transaction fields (such as LogicSig-authorized transactions). Both are shown because production Algorand development uses both.

### Using Code Examples

All contract code in this book is Algorand Python targeting AVM v12. Every example compiles and runs on LocalNet using the toolchain versions specified below. You are free to use the code examples in your own projects --- no special permission is required.

The toolchain reflects the state of Algorand development as of early 2026: AlgoKit CLI v2.9.1, PuyaPy compiler v5.7.1, and AVM version 12.

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

\newpage

# Testing Smart Contracts

On a blockchain, deployed code is immutable. A bug in a web application means a hotfix and an apology. A bug in a smart contract means funds locked or stolen --- permanently. There is no rollback, no patch, no "we'll fix it in the next release." The Tinyman V1 exploit drained $3 million because a single validation check was missing. The code was deployed, the exploit was discovered, and the funds were gone before anyone could react.

Testing is not optional. It is the most important skill in this book after the mental model itself.

In Chapter 1 you built the mental model --- how accounts work, how transactions execute atomically, how contracts validate rather than run continuously. You deployed a HelloAlgorand contract and called it from a script. That was the development loop: edit, compile, deploy, interact. Now we add the critical fourth leg: **test**.

This chapter follows a deliberate arc. First, we build a simplified vesting contract --- small enough to read in one sitting but complex enough to need real tests. Then we write comprehensive tests against it: positive tests that verify correct behavior, negative tests that verify security checks, and simulate-based tests that construct attacks without submitting them. Finally, we write tests that *fail* --- tests that expose the simplified contract's limitations. Those failing tests become the specification for the production contract we build in Chapter 3.

An important distinction before we begin: smart contract testing has two layers. **Contract logic testing** verifies that the on-chain code behaves correctly --- the right assertions fire, the math is accurate, state transitions are safe. **Client code testing** verifies that your off-chain scripts compose transactions correctly, encode ABI arguments properly, and handle errors gracefully. This chapter focuses on contract logic testing, which is the blockchain-specific skill. Client code testing is standard Python testing (pytest, mocking, assertions) and does not require special tooling. The integration tests we write here test *both layers simultaneously* --- when one fails, the bug could be in the contract or in the client code that calls it. The unit tests test *contract logic only*.

By the end of this chapter, you will have a working test suite and the testing patterns you will use for every contract in this book.


## The Simplified Vesting Contract

We need a contract to test. Rather than testing HelloAlgorand (too trivial to teach anything transferable), we will build a simplified version of the token vesting contract that Chapter 3 covers in full. This version strips away everything that is not essential to the core idea: one beneficiary, linear vesting with a cliff, admin deposits tokens, beneficiary claims.

Here is what "simplified" means in practice. The production contract in Chapter 3 uses box storage for unlimited beneficiaries, wide arithmetic for overflow safety, a separate `revoke` method, schedule cleanup with MBR refunds, and read-only query methods. Our simplified version uses global state (one beneficiary only), plain `UInt64` arithmetic, no revocation, and a combined initialize-and-deposit method. It is roughly 90 lines of PuyaPy compared to Chapter 3's 200+.

Here is the complete contract. Read it through, then we will discuss the key points:

```python
from algopy import (
    ARC4Contract,
    Asset,
    Bytes,
    Global,
    GlobalState,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
)


class SimpleVesting(ARC4Contract):
    """A simplified vesting contract for one beneficiary.
    Tokens vest linearly from start to vesting_end,
    with nothing claimable before cliff_end."""

    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.asset_id = GlobalState(UInt64(0))
        self.beneficiary = GlobalState(Bytes())
        self.total_amount = GlobalState(UInt64(0))
        self.claimed_amount = GlobalState(UInt64(0))
        self.start_time = GlobalState(UInt64(0))
        self.cliff_end = GlobalState(UInt64(0))
        self.vesting_end = GlobalState(UInt64(0))

    @arc4.baremethod(create="require")
    def create(self) -> None:
        """Record who deployed this contract."""
        self.admin.value = Txn.sender.bytes

    @arc4.baremethod(
        allow_actions=[
            "UpdateApplication",
            "DeleteApplication",
        ]
    )
    def reject_lifecycle(self) -> None:
        """Make the contract immutable."""
        assert False, "Contract is immutable"

    @arc4.abimethod
    def opt_in_to_asset(self, asset: UInt64) -> None:
        """Opt the contract into an ASA.
        Must be called before the deposit group."""
        assert Txn.sender.bytes == self.admin.value, \
            "Only admin"
        itxn.AssetTransfer(
            xfer_asset=Asset(asset),
            asset_receiver=(
                Global.current_application_address
            ),
            asset_amount=0,
            fee=UInt64(0),
        ).submit()

    @arc4.abimethod
    def initialize(
        self,
        asset: UInt64,
        beneficiary: arc4.Address,
        total_amount: UInt64,
        cliff_duration: UInt64,
        vesting_duration: UInt64,
        deposit_txn: gtxn.AssetTransferTransaction,
    ) -> None:
        """Set up the vesting schedule and accept the
        token deposit in one atomic group."""
        assert Txn.sender.bytes == self.admin.value, \
            "Only admin"
        assert self.asset_id.value == UInt64(0), \
            "Already initialized"
        assert vesting_duration > cliff_duration, \
            "Vesting must exceed cliff"
        assert total_amount > UInt64(0), \
            "Amount must be positive"

        # Verify the grouped deposit
        assert deposit_txn.xfer_asset == Asset(asset)
        assert deposit_txn.asset_receiver \
            == Global.current_application_address
        assert deposit_txn.asset_amount == total_amount

        self.asset_id.value = asset
        self.beneficiary.value = beneficiary.bytes
        self.total_amount.value = total_amount
        now = Global.latest_timestamp
        self.start_time.value = now
        self.cliff_end.value = now + cliff_duration
        self.vesting_end.value = now + vesting_duration

    @arc4.abimethod
    def claim(self) -> UInt64:
        """Beneficiary claims vested tokens."""
        assert Txn.sender.bytes \
            == self.beneficiary.value, "Only beneficiary"

        now = Global.latest_timestamp
        if now < self.cliff_end.value:
            return UInt64(0)

        if now >= self.vesting_end.value:
            vested = self.total_amount.value
        else:
            elapsed = now - self.start_time.value
            duration = (
                self.vesting_end.value
                - self.start_time.value
            )
            vested = (
                self.total_amount.value
                * elapsed
                // duration
            )

        claimable = vested - self.claimed_amount.value
        if claimable == UInt64(0):
            return UInt64(0)

        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_id.value),
            asset_receiver=Txn.sender,
            asset_amount=claimable,
            fee=UInt64(0),
        ).submit()

        self.claimed_amount.value = (
            self.claimed_amount.value + claimable
        )
        return claimable

    @arc4.abimethod(readonly=True)
    def get_claimable(self) -> UInt64:
        """How many tokens can the beneficiary
        claim right now?"""
        now = Global.latest_timestamp
        if now < self.cliff_end.value:
            return UInt64(0)

        if now >= self.vesting_end.value:
            vested = self.total_amount.value
        else:
            elapsed = now - self.start_time.value
            duration = (
                self.vesting_end.value
                - self.start_time.value
            )
            vested = (
                self.total_amount.value
                * elapsed
                // duration
            )

        return vested - self.claimed_amount.value

    @arc4.abimethod(readonly=True)
    def get_admin(self) -> arc4.Address:
        """Return the admin address."""
        return arc4.Address.from_bytes(
            self.admin.value
        )
```

Let us walk through the design decisions.

**Global state for everything.** The vesting parameters --- `total_amount`, `start_time`, `cliff_end`, `vesting_end`, `claimed_amount` --- are all global state fields. This limits us to a single beneficiary (one set of parameters), but it avoids the complexity of box storage, box references, and MBR management. That is 2 byte-slice slots (`admin` and `beneficiary`, stored as raw address bytes) and 6 uint slots --- well within the 64-slot limit.

**Separate opt-in, then initialize-and-deposit.** The contract needs to opt into the ASA before it can receive the deposit. On Algorand, an asset transfer to an account that has not opted in will fail. So we call `opt_in_to_asset` first, then send a grouped transaction: an asset transfer (the deposit) followed by the `initialize` app call. The contract verifies the deposit matches the declared amount and asset. This is simpler than Chapter 3's approach but less flexible --- you cannot add more tokens after initialization.

**No wide arithmetic.** The vesting calculation `total_amount * elapsed // duration` uses plain `UInt64` arithmetic. If `total_amount * elapsed` exceeds `UInt64` max (~1.8 x 10^19), the AVM panics. With small test amounts this is fine. With production amounts (100M tokens at 6 decimals = 10^14 base units times months of elapsed time), it overflows. We will test this gap explicitly.

**`claim` returns zero instead of asserting.** If nothing is claimable (before cliff, or everything already claimed), the method returns 0 rather than failing. This is a design choice --- the Chapter 3 version asserts because a zero-claim is likely a user error and should fail loudly. Here we return zero for simplicity.

**`fee=UInt64(0)` on every inner transaction.** This makes the fee pooling intent explicit --- the outer transaction overpays to cover inner fees. In PuyaPy, the default inner transaction fee is already 0, but writing it explicitly ensures anyone reading the code immediately sees the intent. If a non-zero fee were set (or if a lower-level language left the field defaulting to the minimum fee), that amount would be deducted from the contract's Algo balance. An attacker could then call your contract repeatedly, draining its balance through accumulated fees.

Save this contract as `smart_contracts/simple_vesting/contract.py`. If you are using a project from `algokit init`, rename the template's `hello_world/` directory to `simple_vesting/` first. Compile it:

```bash
algokit project run build
```

You should see `SimpleVesting.approval.teal`, `SimpleVesting.clear.teal`, and `SimpleVesting.arc56.json` in `smart_contracts/artifacts/simple_vesting/`.


## Setting Up pytest

The project template from `algokit init` includes pytest in its dependencies, but you need a `tests/` directory with proper fixtures. Create `tests/conftest.py` in your project root (next to `pyproject.toml`):

```python
# tests/conftest.py
import os
import time
import pytest
import algokit_utils


@pytest.fixture(scope="session")
def algorand() -> algokit_utils.AlgorandClient:
    """AlgorandClient connected to LocalNet.
    Session-scoped: one client for all tests."""
    return (
        algokit_utils.AlgorandClient.default_localnet()
    )


@pytest.fixture(scope="session")
def admin(algorand: algokit_utils.AlgorandClient):
    """The LocalNet dispenser account. Pre-funded
    with millions of Algo."""
    return algorand.account.localnet_dispenser()


def fund_account(
    algorand: algokit_utils.AlgorandClient,
    sender,
    receiver_address: str,
    amount: int = 500_000,
) -> None:
    """Send Algo to an account so it meets MBR."""
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=sender.address,
            receiver=receiver_address,
            amount=(
                algokit_utils.AlgoAmount
                .from_micro_algo(amount)
            ),
            note=os.urandom(8),
        )
    )


def create_test_asa(
    algorand: algokit_utils.AlgorandClient,
    creator,
    total: int = 10_000_000_000,
    decimals: int = 6,
) -> int:
    """Create a test ASA and return its ID."""
    result = algorand.send.asset_create(
        algokit_utils.AssetCreateParams(
            sender=creator.address,
            total=total,
            decimals=decimals,
            default_frozen=False,
            asset_name="TestToken",
            unit_name="TST",
            note=os.urandom(8),
        )
    )
    return result.asset_id


def advance_time(
    algorand: algokit_utils.AlgorandClient,
    seconds: int,
) -> None:
    """Advance the LocalNet block timestamp.

    On LocalNet, blocks are produced on demand --- only
    when a transaction is submitted. time.sleep() alone
    does NOT advance the block timestamp. This helper
    sleeps for the requested duration (so the system
    clock advances), then sends a dummy self-payment
    (so a new block is produced with the updated
    timestamp).
    """
    time.sleep(seconds)
    dispenser = algorand.account.localnet_dispenser()
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=dispenser.address,
            receiver=dispenser.address,
            amount=(
                algokit_utils.AlgoAmount
                .from_micro_algo(0)
            ),
            note=os.urandom(8),
        )
    )
```

Also create an empty `tests/__init__.py` so pytest treats the directory as a package.

There are several important things to understand about this setup.

**`localnet_dispenser()` vs `account.random()`.** The dispenser is a pre-funded account that comes with LocalNet --- it has millions of Algo and can pay for anything. `account.random()` creates a brand-new account with zero balance. Every random account needs explicit funding before it can do anything (even a simple payment requires 0.1 Algo MBR plus fee headroom). Use the dispenser as your admin/deployer and `account.random()` for beneficiaries and other secondary accounts.

**`note=os.urandom(8)` on every transaction.** LocalNet produces blocks on demand, and identical transactions submitted in rapid succession can produce identical transaction IDs, causing "transaction already in ledger" errors. Adding 8 random bytes to the note field guarantees uniqueness. This costs nothing and prevents intermittent test failures that are maddening to debug. Add it to every `PaymentParams`, `AssetTransferParams`, `AssetCreateParams`, and `AppClientMethodCallParams` in your test code.

> **Note:** The `advance_time` helper is the single most confusing aspect of LocalNet testing for newcomers. On a live network, block timestamps advance with wall-clock time because blocks are produced continuously. On LocalNet, blocks are only produced when you submit a transaction. If you `time.sleep(10)` but do not submit a transaction, the block timestamp stays where it was. You need both the sleep (to advance wall-clock time) and the dummy transaction (to produce a block reflecting that time).

**Session-scoped fixtures.** The `algorand` and `admin` fixtures use `scope="session"` so they are created once and reused across all tests. Each test deploys its own fresh contract instance, so tests do not interfere with each other despite sharing the same LocalNet connection.

> **Note:** For testing, use short durations --- seconds instead of months. Set a cliff of 5 seconds and total vesting of 20 seconds instead of 90 days and 365 days. This keeps your test suite fast while still exercising the time-dependent logic faithfully.


## Writing Tests That Pass

Create `tests/test_simple_vesting.py`. Every test follows the same rhythm: **deploy** the contract, **set up** the required state, **act** (call the method under test), and **assert** on the result.

We start with two helper functions that eliminate repetition:

```python
# tests/test_simple_vesting.py
import os
from pathlib import Path
import pytest
import algokit_utils

from tests.conftest import (
    advance_time,
    create_test_asa,
    fund_account,
)

APP_SPEC = Path(
    "smart_contracts/artifacts/simple_vesting/"
    "SimpleVesting.arc56.json"
).read_text()


def deploy(algorand, admin):
    """Deploy a fresh SimpleVesting contract."""
    factory = algorand.client.get_app_factory(
        app_spec=APP_SPEC,
        default_sender=admin.address,
    )
    app_client, _ = factory.deploy()
    return app_client


def setup_initialized_contract(
    algorand, admin, cliff, vesting, total
):
    """Deploy, fund, initialize, and return
    (app_client, token_id, beneficiary)."""

    # Step 1: Deploy a fresh contract
    app_client = deploy(algorand, admin)

    # Step 2: Create a test ASA with enough supply
    token_id = create_test_asa(
        algorand, admin, total=max(total, 10_000_000_000)
    )

    # Step 3: Create and fund beneficiary account
    beneficiary = algorand.account.random()
    fund_account(algorand, admin, beneficiary.address)

    # Step 4: Beneficiary opts into the ASA
    # (required before they can receive tokens)
    algorand.send.asset_transfer(
        algokit_utils.AssetTransferParams(
            sender=beneficiary.address,
            receiver=beneficiary.address,
            asset_id=token_id,
            amount=0,
            note=os.urandom(8),
        )
    )

    # Step 5: Fund the contract for MBR
    # (base + ASA opt-in)
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=admin.address,
            receiver=app_client.app_address,
            amount=(
                algokit_utils.AlgoAmount
                .from_micro_algo(300_000)
            ),
            note=os.urandom(8),
        )
    )

    # Step 6: Contract opts into the ASA
    # (must happen BEFORE the deposit transfer)
    app_client.send.call(
        algokit_utils.AppClientMethodCallParams(
            method="opt_in_to_asset",
            args=[token_id],
            static_fee=(
                algokit_utils.AlgoAmount
                .from_micro_algo(2000)
            ),
            note=os.urandom(8),
        )
    )

    # Step 7: Group the deposit + initialize call
    composer = algorand.new_group()
    composer.add_asset_transfer(
        algokit_utils.AssetTransferParams(
            sender=admin.address,
            receiver=app_client.app_address,
            asset_id=token_id,
            amount=total,
            note=os.urandom(8),
        )
    )
    composer.add_app_call_method_call(
        app_client.params.call(
            algokit_utils.AppClientMethodCallParams(
                method="initialize",
                args=[
                    token_id,
                    beneficiary.address,
                    total,
                    cliff,
                    vesting,
                ],
                note=os.urandom(8),
            )
        )
    )
    composer.send()

    return app_client, token_id, beneficiary
```

The `setup_initialized_contract` helper follows a 7-step sequence. Each step has a specific purpose:

1. **Deploy** creates a fresh contract instance (so tests do not interfere).
2. **Create ASA** makes a test token with sufficient supply.
3. **Fund beneficiary** gives the new account enough Algo for MBR and fees.
4. **Beneficiary opts into ASA** --- required before they can receive tokens via `claim`.
5. **Fund contract** covers the contract's MBR (base account + ASA opt-in).
6. **Contract opts into ASA** --- must happen *before* the deposit. On Algorand, an asset transfer to an account that has not opted in fails immediately.
7. **Grouped deposit + initialize** sends the tokens and configures the vesting schedule atomically.

*Before reading the tests below, pause and list three behaviors you would want to test in this contract. What is the most important security check?*

Each test targets one specific behavior. We test time-dependent logic with invariants (greater than zero, less than total) rather than exact values because LocalNet timestamps are precise only to the second. We write separate tests for each security assertion so a failure tells us exactly which check broke. Now the seven tests --- each one tells a story.

```python
class TestSimpleVesting:

    def test_create_sets_admin(
        self, algorand, admin
    ):
        """Deployer should be recorded as admin."""
        app_client = deploy(algorand, admin)
        result = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="get_admin",
                note=os.urandom(8),
            )
        )
        assert result.abi_return == admin.address

    def test_initialize_opts_into_asset(
        self, algorand, admin
    ):
        """After initialize, the contract should hold
        the deposited tokens."""
        total = 1_000_000
        app_client, token_id, _ = (
            setup_initialized_contract(
                algorand, admin,
                cliff=5, vesting=20, total=total,
            )
        )

        # Verify via algod API
        info = algorand.client.algod.account_asset_info(
            app_client.app_address, token_id
        )
        balance = info["asset-holding"]["amount"]
        assert balance == total

    def test_claim_before_cliff_returns_zero(
        self, algorand, admin
    ):
        """Claiming before the cliff should return 0
        and transfer nothing."""
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=8, vesting=30, total=1_000_000,
            )
        )

        result = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="claim",
                sender=beneficiary.address,
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )
        assert result.abi_return == 0

    def test_claim_after_cliff_returns_proportional(
        self, algorand, admin
    ):
        """After the cliff, vested tokens should be
        claimable proportionally."""
        total = 1_000_000
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=5, vesting=20, total=total,
            )
        )

        advance_time(algorand, 7)  # Past 5s cliff

        result = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="claim",
                sender=beneficiary.address,
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )
        claimed = result.abi_return
        assert claimed > 0
        assert claimed < total

        # Verify on-chain balance
        info = algorand.client.algod.account_asset_info(
            beneficiary.address, token_id
        )
        assert info["asset-holding"]["amount"] == claimed

    def test_claim_after_full_vesting_returns_total(
        self, algorand, admin
    ):
        """After vesting_end, all tokens are claimable."""
        total = 1_000_000
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=3, vesting=10, total=total,
            )
        )

        advance_time(algorand, 12)  # Past vesting_end

        result = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="claim",
                sender=beneficiary.address,
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )
        assert result.abi_return == total

    def test_only_admin_can_initialize(
        self, algorand, admin
    ):
        """A non-admin caller should be rejected."""
        app_client = deploy(algorand, admin)
        token_id = create_test_asa(algorand, admin)
        imposter = algorand.account.random()
        fund_account(
            algorand, admin, imposter.address
        )

        # Admin opts imposter into the ASA so the
        # asset transfer does not fail before the
        # app call
        algorand.send.asset_transfer(
            algokit_utils.AssetTransferParams(
                sender=imposter.address,
                receiver=imposter.address,
                asset_id=token_id,
                amount=0,
                note=os.urandom(8),
            )
        )
        # Transfer tokens to imposter so they can
        # deposit
        algorand.send.asset_transfer(
            algokit_utils.AssetTransferParams(
                sender=admin.address,
                receiver=imposter.address,
                asset_id=token_id,
                amount=1_000_000,
                note=os.urandom(8),
            )
        )

        # Fund the contract for MBR
        algorand.send.payment(
            algokit_utils.PaymentParams(
                sender=admin.address,
                receiver=app_client.app_address,
                amount=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(200_000)
                ),
                note=os.urandom(8),
            )
        )

        with pytest.raises(Exception):
            composer = algorand.new_group()
            composer.add_asset_transfer(
                algokit_utils.AssetTransferParams(
                    sender=imposter.address,
                    receiver=app_client.app_address,
                    asset_id=token_id,
                    amount=1_000_000,
                    note=os.urandom(8),
                )
            )
            composer.add_app_call_method_call(
                app_client.params.call(
                    algokit_utils
                    .AppClientMethodCallParams(
                        method="initialize",
                        args=[
                            token_id,
                            imposter.address,
                            1_000_000, 5, 20,
                        ],
                        sender=imposter.address,
                        static_fee=(
                            algokit_utils.AlgoAmount
                            .from_micro_algo(2000)
                        ),
                        note=os.urandom(8),
                    )
                )
            )
            composer.send()

    def test_only_beneficiary_can_claim(
        self, algorand, admin
    ):
        """A non-beneficiary should be rejected."""
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=3, vesting=15, total=1_000_000,
            )
        )

        advance_time(algorand, 5)

        attacker = algorand.account.random()
        fund_account(
            algorand, admin, attacker.address
        )

        with pytest.raises(Exception):
            app_client.send.call(
                algokit_utils
                .AppClientMethodCallParams(
                    method="claim",
                    sender=attacker.address,
                    static_fee=(
                        algokit_utils.AlgoAmount
                        .from_micro_algo(2000)
                    ),
                    note=os.urandom(8),
                )
            )
```

Run the tests:

```bash
pytest tests/test_simple_vesting.py -v
```

You should see all seven pass. The total runtime will be 30--50 seconds, dominated by the `advance_time` calls. If any test fails, check these common issues: LocalNet not running (`algokit localnet start`), contract not compiled (`algokit project run build`), or the ARC-56 spec path not matching your directory layout.

*Self-check: can you trace each test back to a specific contract method and explain what behavior it validates? If a test fails, can you predict which `assert` in the contract was triggered?*


## Using simulate for Negative Tests

The tests above use `pytest.raises(Exception)` to verify that unauthorized calls fail. This works, but it is a blunt instrument --- you know the call failed, but not *why*. Maybe it failed for the wrong reason (insufficient funds, a missing ASA opt-in, a different assertion). You want to verify that the *specific security check* caught the attack.

Algorand's *simulate* endpoint solves this. Simulate executes the full transaction logic --- including all contract assertions --- without committing state changes or charging fees. The response includes the failure reason if the transaction would have been rejected. This lets you construct an attack, simulate it, and verify the *exact* assertion that stopped it.

```python
    def test_simulate_unauthorized_claim(
        self, algorand, admin
    ):
        """Use simulate to verify the specific
        rejection reason for unauthorized claims."""
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=3, vesting=15, total=1_000_000,
            )
        )
        advance_time(algorand, 5)

        attacker = algorand.account.random()
        fund_account(
            algorand, admin, attacker.address
        )

        # Build the attack, simulate instead of sending
        result = (
            algorand.new_group()
            .add_app_call_method_call(
                app_client.params.call(
                    algokit_utils
                    .AppClientMethodCallParams(
                        method="claim",
                        sender=attacker.address,
                        static_fee=(
                            algokit_utils.AlgoAmount
                            .from_micro_algo(2000)
                        ),
                        note=os.urandom(8),
                    )
                )
            )
            .simulate()
        )

        # The simulate response tells us WHY it failed
        txn_result = (
            result.simulate_response[
                "txn-groups"
            ][0]
        )
        assert "failure-message" in txn_result
        assert "Only beneficiary" in (
            txn_result["failure-message"]
        )
```

The key difference is `.simulate()` instead of `.send()`. The transaction is constructed identically --- same method, same arguments, same sender --- but simulate executes it in a sandbox. The `simulate_response` dictionary contains detailed information about what happened, including the exact failure message from the contract's `assert` statement.

This is far more precise than `pytest.raises(Exception)`. You are not just testing that the call fails --- you are testing that it fails *because of the authorization check*, not because of insufficient funds, a missing box reference, or some other unrelated error.

> **Tip:** For every security assertion in your contract, write a test that constructs the specific attack and simulates it. Verify the failure message matches the assertion you intended. This builds a library of negative tests that proves each security check works for the right reason.

Here is the same pattern applied to the admin-only `initialize` check:

```python
    def test_simulate_non_admin_initialize(
        self, algorand, admin
    ):
        """Verify initialize rejects non-admin callers
        with the correct error message."""
        app_client = deploy(algorand, admin)
        token_id = create_test_asa(algorand, admin)
        imposter = algorand.account.random()
        fund_account(
            algorand, admin, imposter.address
        )

        # Fund contract for MBR
        algorand.send.payment(
            algokit_utils.PaymentParams(
                sender=admin.address,
                receiver=app_client.app_address,
                amount=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(200_000)
                ),
                note=os.urandom(8),
            )
        )

        result = (
            algorand.new_group()
            .add_asset_transfer(
                algokit_utils.AssetTransferParams(
                    sender=admin.address,
                    receiver=app_client.app_address,
                    asset_id=token_id,
                    amount=1_000_000,
                    note=os.urandom(8),
                )
            )
            .add_app_call_method_call(
                app_client.params.call(
                    algokit_utils
                    .AppClientMethodCallParams(
                        method="initialize",
                        args=[
                            token_id,
                            imposter.address,
                            1_000_000, 5, 20,
                        ],
                        sender=imposter.address,
                        static_fee=(
                            algokit_utils.AlgoAmount
                            .from_micro_algo(2000)
                        ),
                        note=os.urandom(8),
                    )
                )
            )
            .simulate()
        )

        txn_result = (
            result.simulate_response[
                "txn-groups"
            ][0]
        )
        assert "Only admin" in (
            txn_result["failure-message"]
        )
```

The simulate approach is especially valuable during development. When a test fails unexpectedly, simulating the same transaction gives you the exact failure reason and program counter, which you can map back to your source code using the ARC-56 source map.


## Tests That Fail --- Revealing the Gaps

The tests above prove the simplified contract works correctly within its design scope. But that scope is deliberately narrow. The following tests expose limitations that would matter in production --- and each one motivates a specific feature in Chapter 3's full implementation.

### Gap 1: Arithmetic overflow with large amounts

The simplified contract computes `total_amount * elapsed // duration` using plain `UInt64` arithmetic. What happens with production-scale amounts?

```python
class TestSimpleVestingGaps:

    def test_overflow_with_production_amounts(
        self, algorand, admin
    ):
        """100M tokens at 6 decimals produces an
        intermediate product that overflows UInt64 when
        combined with production-length time durations.

        With short test durations, the math works.
        With real durations (months), it would overflow.
        This test documents the vulnerability."""
        # 10^14 base units (100M tokens, 6 decimals)
        total = 100_000_000_000_000
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=3, vesting=20, total=total,
            )
        )

        # With 20-second vesting, 10^14 * 10 = 10^15
        # fits in UInt64. This claim succeeds.
        advance_time(algorand, 10)
        result = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="claim",
                sender=beneficiary.address,
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )
        assert result.abi_return > 0

        # But if vesting_duration were 31,536,000
        # (one year in seconds), the product
        # 10^14 * 31,536,000 = 3.15 * 10^21 would
        # exceed UInt64 max of ~1.8 * 10^19.
        # The AVM would panic with an overflow error.
```

The comment explains what *would* happen with production parameters. We cannot easily test the overflow with integration tests (we would need to sleep for a year), but we can document it as a known limitation.

*Chapter 3 solves this with wide arithmetic: `op.mulw(total, elapsed)` produces a 128-bit intermediate product as two `UInt64` values, and `op.divmodw` divides it back to `UInt64`. The intermediate product never overflows.*

### Gap 2: Only one beneficiary

```python
    def test_cannot_add_second_beneficiary(
        self, algorand, admin
    ):
        """The contract supports exactly one
        beneficiary. Calling initialize again fails
        because asset_id is already set."""
        app_client, token_id, first_ben = (
            setup_initialized_contract(
                algorand, admin,
                cliff=5, vesting=20, total=500_000,
            )
        )

        second_ben = algorand.account.random()
        fund_account(
            algorand, admin, second_ben.address
        )

        # Attempt to initialize again
        with pytest.raises(Exception):
            composer = algorand.new_group()
            composer.add_asset_transfer(
                algokit_utils.AssetTransferParams(
                    sender=admin.address,
                    receiver=app_client.app_address,
                    asset_id=token_id,
                    amount=500_000,
                    note=os.urandom(8),
                )
            )
            composer.add_app_call_method_call(
                app_client.params.call(
                    algokit_utils
                    .AppClientMethodCallParams(
                        method="initialize",
                        args=[
                            token_id,
                            second_ben.address,
                            500_000, 5, 20,
                        ],
                        static_fee=(
                            algokit_utils.AlgoAmount
                            .from_micro_algo(2000)
                        ),
                        note=os.urandom(8),
                    )
                )
            )
            composer.send()
```

The "Already initialized" assertion fires because `self.asset_id.value` is no longer zero. A real vesting contract serving a startup team needs to support dozens or hundreds of beneficiaries, each with independent schedules.

*Chapter 3 introduces `BoxMap(Account, VestingSchedule, key_prefix=b"v_")` for per-beneficiary storage. Each schedule gets its own box, independently created and deleted. The `initialize` method sets up the contract and token; a separate `create_schedule` method adds individual beneficiaries.*

### Gap 3: No revocation

```python
    def test_no_revocation_mechanism(
        self, algorand, admin
    ):
        """There is no way for the admin to reclaim
        unvested tokens if a team member leaves."""
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=5, vesting=20, total=1_000_000,
            )
        )

        advance_time(algorand, 10)

        # The contract has no revoke method. The only
        # methods are initialize, claim, get_claimable,
        # and get_admin. Once tokens are deposited,
        # only the beneficiary can claim them.
        # Admin tries to claim (fails: admin != beneficiary)
        result = (
            algorand.new_group()
            .add_app_call_method_call(
                app_client.params.call(
                    algokit_utils
                    .AppClientMethodCallParams(
                        method="claim",
                        note=os.urandom(8),
                    )
                )
            )
            .simulate()
        )
        # Admin can call claim, but the contract
        # rejects because admin != beneficiary
        txn_result = (
            result.simulate_response[
                "txn-groups"
            ][0]
        )
        assert "Only beneficiary" in (
            txn_result["failure-message"]
        )
```

Even the admin cannot retrieve unvested tokens. Once deposited, tokens are fully committed to the beneficiary's vesting schedule, regardless of whether they leave the team on day two.

*Chapter 3 adds a `revoke` method: it calculates how many tokens are vested at revocation time, caps the beneficiary's `total_amount` at the vested amount, and returns the unvested remainder to the admin via an inner transaction.*

### Gap 4: Rounding behavior across multiple claims

```python
    def test_multiple_claims_sum_to_total(
        self, algorand, admin
    ):
        """Intermediate claims use floor division.
        Do they sum to exactly the total?"""
        total = 1_000_000
        app_client, token_id, beneficiary = (
            setup_initialized_contract(
                algorand, admin,
                cliff=2, vesting=8, total=total,
            )
        )

        # First claim mid-vesting
        advance_time(algorand, 4)
        r1 = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="claim",
                sender=beneficiary.address,
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )
        first = r1.abi_return

        # Second claim after full vesting
        advance_time(algorand, 6)
        r2 = app_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="claim",
                sender=beneficiary.address,
                static_fee=(
                    algokit_utils.AlgoAmount
                    .from_micro_algo(2000)
                ),
                note=os.urandom(8),
            )
        )
        second = r2.abi_return

        # Should sum to exactly total
        assert first + second == total
```

This test should pass because the final claim uses the `now >= vesting_end` branch, which bypasses division entirely and returns the full remaining amount (`total - claimed`). Floor division during intermediate claims means the beneficiary gets slightly less than their exact entitlement, and the final claim resolves the dust. This is correct behavior --- but it only works because the simplified contract's arithmetic does not overflow. With production-scale amounts, the overflow from Gap 1 would make the rounding behavior moot --- the program panics before it can round at all.

*Chapter 3 extracts the vesting math into a `calculate_vested` subroutine using `op.mulw`/`op.divmodw`. Floor division consistently favors the contract: the beneficiary never receives more than their total allocation, and the dust resolves on the final claim when the full `total - claimed` remainder is released.*

These four gaps --- overflow, single-beneficiary limitation, missing revocation, and overflow-dependent rounding --- form the specification for Chapter 3. You now know exactly *what* the production contract must solve and *why*. When Chapter 3 introduces `BoxMap` or `op.mulw`, you will understand the motivation instead of taking it on faith.


## Unit Testing with algorand-python-testing

Every test so far is an *integration test*: it deploys a real contract to LocalNet, submits real transactions, and verifies real on-chain state. Integration tests are the gold standard for smart contracts because they test the actual compiled TEAL, the ABI encoding, the opcode budget, and the network interaction. But they are slow --- the `advance_time` sleeps alone add up to 30+ seconds per run.

The `algorand-python-testing` library provides a complementary approach: *unit testing* that executes your PuyaPy contract as a regular Python object, without compilation or deployment. You instantiate the contract class, set state directly, and call methods --- all in milliseconds.

Install the testing library if it is not already in your dependencies:

```bash
pip install algorand-python-testing
```

Then place a copy of your contract in `tests/contracts/simple_vesting.py` (create `tests/contracts/__init__.py` as well so Python treats the directory as a package) and import from there:

```python
# tests/test_simple_vesting_unit.py
import pytest
from algopy_testing import algopy_testing_context
from algopy import UInt64, OnCompleteAction

from tests.contracts.simple_vesting import (
    SimpleVesting,
)


class TestVestingMath:
    """Unit tests for the vesting calculation logic."""

    def test_before_cliff_returns_zero(self):
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            contract.total_amount.value = (
                UInt64(1_000_000)
            )
            contract.claimed_amount.value = UInt64(0)
            contract.start_time.value = UInt64(100)
            contract.cliff_end.value = UInt64(200)
            contract.vesting_end.value = UInt64(1000)

            ctx.ledger.patch_global_fields(
                latest_timestamp=150
            )
            result = contract.get_claimable()
            assert result == 0

    def test_midway_vesting(self):
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            contract.total_amount.value = (
                UInt64(1_000_000)
            )
            contract.claimed_amount.value = UInt64(0)
            contract.start_time.value = UInt64(0)
            contract.cliff_end.value = UInt64(0)
            contract.vesting_end.value = UInt64(1000)

            ctx.ledger.patch_global_fields(
                latest_timestamp=500
            )
            result = contract.get_claimable()
            # 1_000_000 * 500 / 1000 = 500_000
            assert result == 500_000

    def test_after_end_returns_total(self):
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            contract.total_amount.value = (
                UInt64(1_000_000)
            )
            contract.claimed_amount.value = UInt64(0)
            contract.start_time.value = UInt64(100)
            contract.cliff_end.value = UInt64(200)
            contract.vesting_end.value = UInt64(1000)

            ctx.ledger.patch_global_fields(
                latest_timestamp=2000
            )
            result = contract.get_claimable()
            assert result == 1_000_000

    def test_floor_division_rounds_down(self):
        """Integer division should favor the contract
        (beneficiary gets slightly less)."""
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            contract.total_amount.value = (
                UInt64(1_000_000)
            )
            contract.claimed_amount.value = UInt64(0)
            contract.start_time.value = UInt64(0)
            contract.cliff_end.value = UInt64(0)
            contract.vesting_end.value = UInt64(3)

            ctx.ledger.patch_global_fields(
                latest_timestamp=1
            )
            result = contract.get_claimable()
            # 1_000_000 / 3 = 333_333.33... -> 333_333
            assert result == 333_333

    def test_immutability_rejects_update(self):
        with algopy_testing_context() as ctx:
            contract = SimpleVesting()
            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction.NoOp
                    )
                }
            ):
                contract.create()

            with ctx.txn.create_group(
                active_txn_overrides={
                    "on_completion": (
                        OnCompleteAction
                        .UpdateApplication
                    )
                }
            ):
                with pytest.raises(
                    AssertionError,
                    match="immutable",
                ):
                    contract.reject_lifecycle()
```

Notice the key differences from integration tests:

- **No deployment.** `SimpleVesting()` is a regular Python object.
- **No transactions.** State is set by assigning directly to `GlobalState` properties.
- **No sleeps.** Timestamps are set instantly via `ctx.ledger.patch_global_fields(latest_timestamp=...)`.
- **No network.** No LocalNet, no algod, no Docker.
- **Milliseconds per test** instead of seconds.

The `algopy_testing_context()` context manager provides a mock AVM environment. `ctx.txn.create_group()` sets up the transaction context needed for methods that read `Txn.sender` or check `OnCompletion`. `ctx.ledger.patch_global_fields()` controls `Global.latest_timestamp`, `Global.round`, and other protocol-level values.

**When to use each approach:**

| | Integration Tests | Unit Tests |
|-|---|---|
| **Speed** | Slow (seconds) | Fast (milliseconds) |
| **Fidelity** | Tests compiled TEAL on real AVM | Tests Python source |
| **What it tests** | Contract logic + client code + ABI encoding | Contract logic only |
| **Catches** | Opcode budget, ABI encoding, real network behavior | Business logic bugs, math errors |
| **When a test fails** | Bug could be in the contract OR the client code | Bug is in the contract logic |
| **Dependencies** | LocalNet + Docker | None |
| **Best for** | Final validation, security | Rapid logic iteration |

Use unit tests for rapid development of business logic (especially math-heavy calculations), then write integration tests for the full contract lifecycle and all security paths. Both belong in your test suite.

> **Note:** In production applications, you will also have client-side code that deserves its own tests --- SDK wrappers, frontend transaction composers, error handling, retry logic. That is standard Python (or TypeScript) testing with no blockchain-specific tooling. This chapter covers the blockchain-specific skill: testing the smart contract itself.


## Test Organization

As your project grows to multiple contracts, a consistent structure keeps things manageable:

```
tests/
    __init__.py
    conftest.py                  # Shared fixtures
    contracts/                   # Contract copies for unit tests
        __init__.py
        simple_vesting.py
    test_simple_vesting.py       # Integration tests
    test_simple_vesting_unit.py  # Unit tests
```

**One test file per contract.** `test_simple_vesting.py`, `test_vesting.py`, `test_amm.py`, `test_farming.py`. Run tests for a single contract with `pytest tests/test_simple_vesting.py -v`.

**Group related tests in classes.** `TestSimpleVesting` for the happy path, `TestSimpleVestingGaps` for the limitation tests. This is organizational --- pytest discovers methods in classes the same way it discovers standalone functions.

**Name tests descriptively.** Follow the pattern `test_<feature>_<expected_behavior>`. Names like `test_claim_before_cliff_returns_zero` and `test_only_admin_can_initialize` make test output readable without inspecting the code.

**Fixtures for setup, helpers for operations.** Fixtures (`@pytest.fixture`) manage session-scoped resources like the `algorand` client and `admin` account. Helper functions (`deploy`, `setup_initialized_contract`, `create_test_asa`) are regular functions you call with different parameters in different tests.

**Every security assertion gets a negative test.** If your contract has `assert Txn.sender.bytes == self.admin.value`, write a test where a non-admin calls that method. If it has `assert total_amount > UInt64(0)`, write a test that passes zero. One negative test per assertion. This is the single most effective practice for preventing security bugs.

> **Note:** The `conftest.py` fixtures and helper functions from this chapter are reused throughout the book. When you reach Chapter 3, you will add contract-specific helpers (`create_schedule`, `deposit_tokens`) but the foundational `fund_account`, `create_test_asa`, and `advance_time` helpers remain unchanged.


## Summary

| Concept | Key Takeaway |
|---------|-------------|
| Integration tests | Deploy to LocalNet, submit real transactions, verify on-chain state. High fidelity but slow. |
| Unit tests | Instantiate contracts as Python objects, mock state, no network. Fast but does not test compiled TEAL. |
| `advance_time` | Sleep + dummy transaction to advance LocalNet block timestamp. Neither alone is sufficient. |
| Transaction dedup | `note=os.urandom(8)` on every test transaction prevents "already in ledger" errors. |
| `localnet_dispenser()` | Pre-funded account for admin/deployer. `account.random()` starts with zero balance. |
| Simulate | Execute transactions without committing. Returns failure reasons for precise negative tests. |
| Negative tests | For every `assert` in the contract, write a test that triggers the failure path. |
| Failing tests as specs | Tests exposing simplified contract limitations define what the production version must solve. |


## Exercises

1. **(Recall)** Explain why `time.sleep(10)` alone does not advance the LocalNet block timestamp. What additional step is required, and why?

2. **(Understand)** The simplified contract uses `fee=UInt64(0)` on every inner transaction. Explain what would happen if a non-zero fee were set and how an attacker could exploit it.

3. **(Apply)** Write a `@pytest.fixture` named `deployed_contract` that deploys the SimpleVesting contract, initializes it with a test ASA and beneficiary, and returns a tuple of `(app_client, token_id, beneficiary)`. Use it to simplify at least two of the existing tests.

4. **(Apply)** Write a test that verifies the contract rejects `DeleteApplication`. Use the simulate endpoint and check that the failure message contains "immutable."

5. **(Analyze)** The simplified contract does not check `Global.group_size` in the `initialize` method. Write a test that submits an `initialize` call with an extra payment transaction appended to the group. Does the contract reject it? If not, explain what an attacker could do with the extra transaction, and add a group size check to the contract.

6. **(Evaluate)** Review the four gaps identified in "Tests That Fail." Classify each as a **security issue** (could lead to loss of funds) or a **feature gap** (limits functionality but does not create a vulnerability). Justify each classification.

7. **(Create)** Add a `revoke` method to the simplified contract that lets the admin reclaim unvested tokens. Write both a positive test (admin revokes mid-vesting, receives unvested tokens) and a negative test via simulate (non-admin cannot revoke, failure message is "Only admin"). Hint: the method needs an inner `AssetTransfer` to send tokens back to the admin, and it should update `total_amount` to cap at the vested amount.


## Further Reading

- [AlgoKit Testing Patterns](https://dev.algorand.co/algokit/utils/python/testing/) --- Testing smart contracts with AlgoKit Utils
- [algorand-python-testing](https://dev.algorand.co/algokit/unit-testing/python/overview) --- Unit testing library for PuyaPy contracts
- [pytest documentation](https://docs.pytest.org/) --- Fixtures, parametrize, markers, and configuration
- [Simulate endpoint](https://dev.algorand.co/reference/rest-api/algod/) --- algod REST API reference including simulate
- [AlgoKit Utils Python](https://dev.algorand.co/algokit/utils/python/overview/) --- Client library used in all test scripts


## Before You Continue

Before starting Chapter 3, you should be able to:

- [ ] Write a pytest test that deploys a contract to LocalNet and calls a method
- [ ] Use `advance_time` to test time-dependent contract logic
- [ ] Write a negative test using `simulate` that verifies a specific security assertion
- [ ] Explain the difference between integration tests and unit tests for smart contracts
- [ ] Identify the four limitations of the simplified vesting contract that Chapter 3 addresses

If any of these are unclear, revisit the relevant section before proceeding. Chapter 3 assumes you are comfortable writing and running tests --- every feature we build there will be tested using the patterns established here.

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

\newpage


# NFTs --- Extending the Vesting Contract with Transferability

You have a working token vesting contract. It creates schedules, tracks claims, handles revocation, and manages MBR lifecycle. But it has a limitation you may have already noticed: vesting schedules are permanently bound to the beneficiary's address. If a team member wants to sell their future token allocation, transfer it to a different wallet, or use it as collateral in a lending protocol, they cannot. The schedule is locked to whoever the admin specified at creation time.

In this chapter we solve that by minting an *NFT* (Non-Fungible Token) for each vesting schedule. Whoever holds the NFT can claim the vested tokens --- and transferring the NFT is just a standard asset transfer that works with any Algorand wallet or marketplace. This single architectural change makes vesting positions composable: they can be traded, used as collateral, or transferred between wallets, all without modifying the contract.

We will rebuild the vesting contract from Chapter 3 with these changes. Along the way, you will learn how NFTs work on Algorand (they are just ASAs with `total=1`), how to mint assets from within a contract via inner transactions, the ARC-3 metadata standard, the ownership-by-asset verification pattern, and the clawback mechanism for revocation. Every concept from Chapter 3 carries forward --- this chapter extends your knowledge rather than replacing it.

## What Is an NFT on Algorand?

On some blockchains, NFTs require a dedicated token standard with special smart contract logic (ERC-721 on Ethereum, for example). On Algorand, NFTs are simply [Algorand Standard Assets](https://dev.algorand.co/concepts/assets/overview/) (ASAs) with specific parameters:

- **total = 1** --- exactly one unit exists
- **decimals = 0** --- the unit is indivisible

That is it. There is no separate NFT contract, no special opcode, no distinct token type. The same `AssetTransfer` transaction that moves fungible tokens also moves NFTs. The same opt-in mechanism applies. The same `AssetConfig` transaction creates them. The entire Algorand NFT ecosystem --- marketplaces, wallets, explorers --- is built on this convention.

This means everything you learned about ASAs in Chapter 3 (opt-in, transfers, inner transactions) applies directly to NFTs. The only new concept is *metadata* --- how an NFT communicates what it represents.

## ARC-3: The NFT Metadata Standard

When you create an ASA, the on-chain fields are limited: a name (max 32 bytes), a unit name (max 8 bytes), a URL (max 96 bytes), and a 32-byte metadata hash. These fields alone cannot describe a vesting schedule's terms, display an image in a wallet, or provide the structured data that marketplaces need.

[ARC-3](https://dev.algorand.co/arc-standards/arc-0003/) solves this by defining a convention: the ASA's `url` field points to a JSON metadata file (typically hosted on IPFS), and the `metadata_hash` field contains the SHA-256 hash of that JSON for integrity verification. The URL must end with `#arc3` to signal that the asset follows this standard.

An ARC-3 metadata file for a vesting NFT might look like:

```json
{
  "name": "Vesting Schedule #1",
  "description": "1,000,000 TVT vesting over 12 months with 3-month cliff",
  "properties": {
    "total_amount": 1000000,
    "cliff_months": 3,
    "vesting_months": 12,
    "vesting_asset_id": 12345,
    "contract_app_id": 67890
  }
}
```

The `properties` object is freeform --- you can put any domain-specific attributes there. Wallets and explorers that support ARC-3 will display the name and description; specialized UIs can read the properties to show vesting details.

For our contract, the admin prepares the metadata JSON and uploads it to IPFS *before* calling `create_schedule`. The resulting IPFS URL and metadata hash are passed as arguments, and the contract embeds them in the minted NFT. This keeps the contract simple --- it does not need to construct JSON or interact with IPFS.

> **Note:** An alternative standard, *ARC-19*, allows mutable metadata by encoding an IPFS content identifier in the ASA's reserve address. This is useful when metadata changes over time (e.g., updating a "percent vested" field). For this chapter, ARC-3's immutable approach is sufficient --- the vesting terms are fixed at creation.

## Project Setup

We will build the NFT vesting contract as a fresh project, reusing the structure from Chapter 3. If you still have your `token-vesting` project, you can duplicate it. Otherwise, scaffold a new one:

```bash
algokit init -t python --name nft-vesting
cd nft-vesting/projects/nft-vesting
algokit project bootstrap all
mv smart_contracts/hello_world smart_contracts/nft_vesting
```

Delete the template-generated `deploy_config.py` inside the renamed directory. Your contract code goes in `smart_contracts/nft_vesting/contract.py`.

## The Modified Data Model

In Chapter 3, vesting schedules were stored in a `BoxMap` keyed by the beneficiary's address. When the beneficiary called `claim`, the contract looked up `self.schedules[Txn.sender]`. This coupling between identity and ownership is what we are breaking.

The new design keys schedules by *NFT asset ID*. When a user calls `claim`, they pass the NFT's asset ID as an argument, and the contract verifies they hold the NFT before releasing tokens. The schedule does not care *who* holds the NFT --- only *that* the caller holds it.

Add the following to `smart_contracts/nft_vesting/contract.py`:

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

The struct is unchanged from Chapter 3 --- 41 bytes. We do not need to store the NFT asset ID inside the struct because it *is* the box key. We also do not store a beneficiary address because ownership is determined by who holds the NFT, not by a stored address.

The key difference is in the `BoxMap` declaration. (See [Algorand Python storage guide](https://dev.algorand.co/algokit/languages/python/lg-storage/) for BoxMap type parameters.) Add the contract class below the struct:

```python
from algopy import (
    ARC4Contract, Account, Asset, Bytes, Global, GlobalState,
    Txn, UInt64, arc4, gtxn, itxn, op, subroutine, BoxMap,
)

class NftVesting(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.asset_id = GlobalState(UInt64(0))
        self.is_initialized = GlobalState(UInt64(0))
        self.schedule_count = GlobalState(UInt64(0))
        # Schedules keyed by NFT asset ID (8 bytes) instead of address (32 bytes)
        self.schedules = BoxMap(arc4.UInt64, VestingSchedule, key_prefix=b"v_")
```

Compare with Chapter 3's `BoxMap(Account, VestingSchedule, key_prefix=b"v_")`. The key type changed from `Account` (32 bytes) to `arc4.UInt64` (8 bytes). This means box names are shorter: `b"v_"` prefix (2 bytes) + 8-byte key = 10 bytes total, compared to 34 bytes previously. The MBR per box drops accordingly: 2,500 + 400 × (10 + 41) = **22,900 microAlgos** per schedule box (down from 32,500).

However, each schedule now also requires an NFT, and creating an ASA from the contract adds **100,000 microAlgos** to the contract's MBR. So the total per-schedule cost is 122,900 microAlgos --- higher than before, but we gain transferability.

## Creation, Immutability, and Initialization

These methods are nearly identical to Chapter 3. The only change is in `initialize`, where we no longer need to worry about the contract opting into created NFTs (the creator automatically holds the full supply of assets it creates). (See [Lifecycle](https://dev.algorand.co/concepts/smart-contracts/lifecycle/) for the creation and OnCompletion actions.)

```python
    @arc4.baremethod(create="require")
    def create(self) -> None:
        self.admin.value = Txn.sender.bytes

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "This contract is immutable"

    @arc4.abimethod
    def initialize(self, vesting_asset: Asset) -> None:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert self.is_initialized.value == UInt64(0), "Already initialized"
        self.asset_id.value = vesting_asset.id
        self.is_initialized.value = UInt64(1)
        # Opt the contract into the vesting token
        itxn.AssetTransfer(
            xfer_asset=vesting_asset,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()
```

These are the same patterns from Chapter 3: bare methods for lifecycle control, admin authorization via `Txn.sender.bytes == self.admin.value`, and an inner transaction with `fee=UInt64(0)` for the ASA opt-in. If any of this is unfamiliar, revisit the corresponding sections in Chapter 3 before continuing.

## Depositing Tokens

The deposit method is unchanged from Chapter 3 --- the admin transfers vesting tokens to the contract in an [atomic group](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/):

```python
    @arc4.abimethod
    def deposit_tokens(self, deposit_txn: gtxn.AssetTransferTransaction) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert Global.group_size == UInt64(2), "Expected 2 transactions"
        assert deposit_txn.asset_receiver == Global.current_application_address
        assert deposit_txn.xfer_asset == Asset(self.asset_id.value)
        assert deposit_txn.asset_amount > UInt64(0)
        return deposit_txn.asset_amount
```

## Minting the Vesting NFT

This is where the contract diverges from Chapter 3. Instead of simply writing a schedule to box storage, `create_schedule` now mints an NFT that represents ownership of the vesting position. The NFT stays with the contract until the beneficiary opts in and the admin delivers it --- a two-step pattern we will explore shortly.

*Inner transactions* are the mechanism. You used them in Chapter 3 for ASA opt-ins and token transfers. Now we use `itxn.AssetConfig` to *create* an asset from within the contract. (See [Asset Operations](https://dev.algorand.co/concepts/assets/asset-operations/) for ASA creation fields.)

```python
    @arc4.abimethod
    def create_schedule(
        self,
        total_amount: UInt64,
        cliff_duration: UInt64,
        vesting_duration: UInt64,
        nft_url: Bytes,
        metadata_hash: Bytes,
        mbr_payment: gtxn.PaymentTransaction,
    ) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert Global.group_size == UInt64(2), "Expected 2 transactions"
        assert total_amount > UInt64(0), "Amount must be positive"
        assert vesting_duration > cliff_duration, "Vesting must exceed cliff"

        # Validate the MBR payment
        # Box MBR: 2,500 + 400 * (10 + 41) = 22,900
        # NFT ASA MBR: 100,000
        # Total: 122,900 microAlgos
        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(41))
        nft_mbr = UInt64(100_000)
        assert mbr_payment.receiver == Global.current_application_address
        assert mbr_payment.amount >= box_mbr + nft_mbr

        now = Global.latest_timestamp

        # Mint the vesting NFT (contract keeps it until deliver_nft)
        nft_txn = itxn.AssetConfig(
            total=1,
            decimals=0,
            asset_name=b"Vesting NFT",
            unit_name=b"VEST",
            url=nft_url,
            metadata_hash=metadata_hash,
            default_frozen=False,
            manager=Global.current_application_address,
            clawback=Global.current_application_address,
            reserve=Global.zero_address,
            freeze=Global.zero_address,
            fee=UInt64(0),
        ).submit()

        nft_id = nft_txn.created_asset.id

        # Store the schedule keyed by NFT asset ID
        schedule = VestingSchedule(
            total_amount=arc4.UInt64(total_amount),
            claimed_amount=arc4.UInt64(0),
            start_time=arc4.UInt64(now),
            cliff_end=arc4.UInt64(now + cliff_duration),
            vesting_end=arc4.UInt64(now + vesting_duration),
            is_revoked=arc4.Bool(False),
        )
        self.schedules[arc4.UInt64(nft_id)] = schedule.copy()
        self.schedule_count.value += 1

        return nft_id

    @arc4.abimethod
    def deliver_nft(self, nft_asset: Asset, beneficiary: Account) -> None:
        """Transfer a minted NFT to the beneficiary after they opt in."""
        assert Txn.sender.bytes == self.admin.value, "Only admin"
        schedule_key = arc4.UInt64(nft_asset.id)
        assert schedule_key in self.schedules, "No schedule for this NFT"

        # Verify the contract still holds the NFT
        assert nft_asset.balance(
            Global.current_application_address
        ) == 1, "Contract does not hold this NFT"

        itxn.AssetTransfer(
            xfer_asset=nft_asset,
            asset_receiver=beneficiary,
            asset_amount=1,
            fee=UInt64(0),
        ).submit()
```

There is a lot happening here. Let us unpack the new pieces.

### The NFT Role Addresses

When creating an ASA, four special addresses control what can be done with it after creation:

- **manager** --- can reconfigure or destroy the asset. We set this to the contract address so the contract can destroy the NFT during cleanup.
- **clawback** --- can transfer the asset out of any account without that account's permission. We set this to the contract address so revocation works. *This is the critical field for our design.*
- **reserve** --- informational only, no protocol authority. We set it to zero.
- **freeze** --- can freeze/unfreeze individual holdings. We set this to zero so the NFT is always freely transferable. Setting it to zero is permanent --- once zero, it can never be changed back.

> **Warning:** Setting `clawback` to the contract address means the contract can take the NFT from anyone at any time. This is necessary for revocation, but it means the NFT is not fully "sovereign" --- holders should understand that the vesting contract retains authority over it. This is visible on-chain and should be communicated clearly in your application's UI.

### The Opt-In Problem and the Two-Step Pattern

On Algorand, a recipient must opt into an ASA before they can receive it. But the NFT does not exist until the contract mints it, so the beneficiary cannot know the asset ID in advance. This is a fundamental coordination problem when minting NFTs from contracts.

*Before reading on: how would you handle this? Consider that the NFT's asset ID is only known after `create_schedule` executes.*

We solve it by splitting the process into two steps. `create_schedule` mints the NFT and stores the schedule, but the contract *keeps* the NFT. The method returns the NFT's asset ID. The admin reads this ID from the transaction result, tells the beneficiary to opt in, and then calls `deliver_nft` to transfer the NFT to the beneficiary's account.

This two-step pattern is common whenever a contract mints an ASA for a specific recipient:

1. **Mint** --- create the asset, contract holds it
2. **Coordinate** --- recipient learns the asset ID and opts in
3. **Deliver** --- contract transfers the asset to the now-opted-in recipient

The `deliver_nft` method is admin-only and verifies that the contract still holds the NFT and that a schedule exists for it. The beneficiary must be opted in before `deliver_nft` is called, or the inner asset transfer will fail.

> **Note:** An alternative approach is to call `create_schedule` using `simulate` first to predict the NFT asset ID, have the beneficiary opt in, then submit the real transaction. This works on LocalNet (where no other transactions intervene) but is fragile on TestNet or MainNet where concurrent asset creations can shift asset IDs. The two-step pattern is more robust and is what production systems use.

### MBR Accounting

Each `create_schedule` call requires the caller to send a payment covering two MBR costs:

1. **Box MBR**: 2,500 + 400 × (10 + 41) = 22,900 microAlgos for the schedule box
2. **NFT ASA MBR**: 100,000 microAlgos because creating an ASA from the contract increases the contract's minimum balance

The total is 122,900 microAlgos per schedule. The `mbr_payment` grouped transaction must cover at least this amount. Compare with Chapter 3's 32,500 microAlgos per schedule --- the NFT adds significant cost, but transferability is the tradeoff.

### Inner Transaction Fees

The `create_schedule` method executes one inner transaction (asset creation), plus the outer application call and the MBR payment. The minimum group fee is:

- 1,000 (MBR payment) + 1,000 (app call) + 1,000 (inner AssetConfig) = 3,000 microAlgos total

The `deliver_nft` call adds one more inner transaction (asset transfer), needing 1,000 (app call) + 1,000 (inner AssetTransfer) = 2,000 microAlgos. With fee pooling, a single transaction in each group can overpay to cover the inner fees.

## Claiming with NFT Ownership Verification

In Chapter 3, `claim()` took no arguments --- it identified the caller by `Txn.sender` and looked up `self.schedules[Txn.sender]`. Now the caller passes the NFT asset ID, and the contract verifies ownership:

```python
    @arc4.abimethod
    def claim(self, nft_asset: Asset) -> UInt64:
        # Verify the caller holds this NFT
        assert nft_asset.balance(Txn.sender) == 1, "Caller does not hold this NFT"

        schedule_key = arc4.UInt64(nft_asset.id)
        assert schedule_key in self.schedules, "No schedule for this NFT"
        schedule = self.schedules[schedule_key].copy()

        assert not schedule.is_revoked.native, "Schedule revoked"

        now = Global.latest_timestamp
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            now,
        )
        already_claimed = schedule.claimed_amount.as_uint64()
        claimable = vested - already_claimed
        assert claimable > UInt64(0), "Nothing to claim"

        # Cap to the contract's actual token balance.
        # If the admin over-committed schedules, this prevents a hard failure
        # and lets the holder claim whatever remains.
        vesting_asset = Asset(self.asset_id.value)
        contract_balance = vesting_asset.balance(Global.current_application_address)
        if claimable > contract_balance:
            claimable = contract_balance

        # Send tokens to the holder
        itxn.AssetTransfer(
            xfer_asset=vesting_asset,
            asset_receiver=Txn.sender,
            asset_amount=claimable,
            fee=UInt64(0),
        ).submit()

        # Record the claim
        schedule.claimed_amount = arc4.UInt64(already_claimed + claimable)
        self.schedules[schedule_key] = schedule.copy()

        return claimable
```

The core claim logic follows Chapter 3 --- `calculate_vested` computes how much has vested, subtracts what was already claimed, and transfers the difference. One important addition is the balance cap: if the admin created more schedules than the deposited token supply can cover, the `claimable` amount is capped to whatever the contract actually holds. This prevents a hard protocol-level failure and lets the holder claim whatever remains gracefully. The key architectural change is in the first two lines:

1. `nft_asset.balance(Txn.sender) == 1` --- this checks that the caller's account holds exactly one unit of the NFT. If the caller transferred the NFT to someone else, this check fails. If someone else transferred it *to* the caller, it succeeds. Ownership is determined by asset balance, not by a stored address.

2. `arc4.UInt64(nft_asset.id)` --- the NFT's asset ID is used directly as the box key to look up the schedule.

This is the *ownership-by-asset* pattern: instead of binding rights to an address, you bind them to a token. Anyone who holds the token can exercise the right. The token is transferable using standard ASA operations, so the right becomes transferable without any special logic in the contract. (See [Resource Usage](https://dev.algorand.co/concepts/smart-contracts/resource-usage/) for how asset balance reads consume foreign references.)

> **Note:** The caller must be opted into both the NFT *and* the vesting token. A secondary market buyer who purchases the NFT must also opt into the vesting token before calling `claim`, or the inner asset transfer will fail. Your application's UI should guide users through both opt-ins.

> **Design decision: why pass the NFT as an argument?** The contract could instead iterate over the caller's assets to find a matching vesting NFT, but the AVM has no iteration primitives for account holdings. The caller must tell the contract which NFT to check. This is a common pattern on Algorand --- the caller provides hints that the contract validates.

## The Vesting Calculation

The same `calculate_vested` subroutine from Chapter 3, unchanged. It uses [wide arithmetic](https://dev.algorand.co/reference/algorand-teal/opcodes/) (`mulw`/`divmodw`) to avoid overflow when multiplying large token amounts by time durations:

```python
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
    # Wide multiply: total * elapsed → 128-bit result (high, low)
    high, low = op.mulw(total, elapsed)
    # Wide divide: (high, low) / duration → (quotient_hi, quotient_lo, remainder_hi, remainder_lo)
    q_hi, vested, r_hi, r_lo = op.divmodw(high, low, UInt64(0), duration)
    assert q_hi == 0, "Overflow in vesting calculation"
    return vested
```

Place this function outside the class, between the `VestingSchedule` struct and the `NftVesting` class. Recall from Chapter 3 that `@subroutine` functions are compiled inline by PuyaPy --- they are not ABI methods and cannot be called externally. Extracting this logic into a subroutine saves program bytes because it is called in three places: `claim`, `revoke`, and `get_claimable`.

## Revocation with Clawback

When the admin revokes a schedule, the contract must handle the NFT. We use Algorand's [clawback](https://dev.algorand.co/concepts/assets/asset-operations/) mechanism: because the contract is the NFT's designated clawback address, it can transfer the NFT out of any account without that account's permission.

There is one complication: revocation *destroys the NFT*, so the holder can no longer call `claim` afterward. To handle this cleanly, the contract settles everything in one transaction --- it transfers any vested-but-unclaimed tokens to the holder, claws back and destroys the NFT, and returns the unvested tokens to the admin.

The complete revocation flow:

1. Calculate how much has vested
2. Settle vested-but-unclaimed tokens with the current holder
3. Cap the schedule and mark it as revoked
4. Clawback the NFT from whoever currently holds it
5. Destroy the NFT (since the contract now holds the total supply)
6. Return unvested tokens to the admin

```python
    @arc4.abimethod
    def revoke(self, nft_asset: Asset, current_holder: Account) -> UInt64:
        assert Txn.sender.bytes == self.admin.value, "Only admin"

        schedule_key = arc4.UInt64(nft_asset.id)
        assert schedule_key in self.schedules, "No schedule for this NFT"
        schedule = self.schedules[schedule_key].copy()
        assert not schedule.is_revoked.native, "Already revoked"

        # Verify the holder actually has the NFT
        assert nft_asset.balance(current_holder) == 1, "Holder does not have NFT"

        now = Global.latest_timestamp
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            now,
        )
        already_claimed = schedule.claimed_amount.as_uint64()
        unvested = schedule.total_amount.as_uint64() - vested
        claimable = vested - already_claimed

        # Settle: transfer any vested-but-unclaimed tokens to the holder
        if claimable > UInt64(0):
            itxn.AssetTransfer(
                xfer_asset=Asset(self.asset_id.value),
                asset_receiver=current_holder,
                asset_amount=claimable,
                fee=UInt64(0),
            ).submit()

        # Clawback the NFT from the current holder
        itxn.AssetTransfer(
            xfer_asset=nft_asset,
            asset_sender=current_holder,
            asset_receiver=Global.current_application_address,
            asset_amount=1,
            fee=UInt64(0),
        ).submit()

        # Destroy the NFT (contract holds total supply, so destruction is allowed)
        itxn.AssetConfig(
            config_asset=nft_asset,
            fee=UInt64(0),
        ).submit()

        # Return unvested tokens to admin
        if unvested > UInt64(0):
            itxn.AssetTransfer(
                xfer_asset=Asset(self.asset_id.value),
                asset_receiver=Txn.sender,
                asset_amount=unvested,
                fee=UInt64(0),
            ).submit()

        # Record the revocation
        schedule.total_amount = arc4.UInt64(vested)
        schedule.claimed_amount = arc4.UInt64(vested)  # All vested tokens are now settled
        schedule.is_revoked = arc4.Bool(True)
        self.schedules[schedule_key] = schedule.copy()

        return unvested
```

### How Clawback Works

The `asset_sender` field in `itxn.AssetTransfer` is what triggers a clawback. When present, the AVM treats the transaction as a clawback operation: the *sending contract* must be the asset's designated clawback address, and `asset_sender` specifies the account being clawed from. The NFT moves from `current_holder` to the contract without the holder's permission.

This is a protocol-level capability --- it does not require any special logic in the holder's account. It works because we set `clawback=Global.current_application_address` when minting the NFT.

### Why the Admin Must Pass `current_holder`

The contract needs to know who currently holds the NFT so it can clawback from that specific account. But the AVM cannot enumerate who holds an asset --- there is no "find holder of asset X" opcode. The admin must provide this information, and the contract validates it: `nft_asset.balance(current_holder) == 1`. If the admin provides the wrong address, the assertion fails.

The `current_holder` must also be included in the transaction's `accounts` foreign array on the client side. This is the same resource reference pattern you saw with box references in Chapter 3.

> **Warning --- Known Limitation:** The settlement step sends vesting tokens to `current_holder`. If the NFT was transferred to someone who has not opted into the vesting token, the inner asset transfer will fail and the entire revocation transaction reverts. This means a holder who refuses to opt into the vesting token can effectively block revocation. In production, you would address this by checking the holder's opt-in status before attempting settlement: if they are not opted in, skip the vested token transfer and instead store the unclaimed amount for later retrieval via a separate `withdraw_settled` method. We omit this for clarity, but Exercise 5 asks you to design the solution.

### Destroying the NFT

After clawback, the contract holds the NFT's entire supply (1 unit). An `AssetConfig` inner transaction with *only* the `config_asset` field set and no other fields destroys the asset. Destruction is only possible when the creator holds the entire supply. Since the contract both created and now holds the NFT, destruction succeeds.

Destroying the NFT frees 100,000 microAlgos of MBR from the contract's account. This is one reason we prefer destruction over leaving the NFT as a worthless token --- it recovers the cost.

> **Note:** Revocation executes up to four inner transactions (vested token settlement + clawback + destroy + unvested token return). The outer transaction must have enough fee pooling to cover the worst case: 1,000 (app call) + 4 × 1,000 (inner txns) = 5,000 microAlgos. If either `claimable` or `unvested` is zero, fewer inner transactions execute, but overpaying fees is harmless.

## Cleanup

After a beneficiary has fully claimed their tokens (or after revocation has settled everything), the schedule [box](https://dev.algorand.co/concepts/smart-contracts/storage/box/) can be deleted to free its MBR. Unlike Chapter 3, we do not need to worry about the NFT during cleanup for revoked schedules --- it was already destroyed during revocation. For fully-claimed schedules, the NFT still exists but is functionally complete.

```python
    @arc4.abimethod
    def cleanup_schedule(self, nft_asset_id: UInt64) -> None:
        schedule_key = arc4.UInt64(nft_asset_id)
        assert schedule_key in self.schedules, "No schedule"
        schedule = self.schedules[schedule_key].copy()

        # Either fully claimed or revoked and settled
        assert schedule.claimed_amount.as_uint64() >= schedule.total_amount.as_uint64(), \
            "Not fully claimed"

        del self.schedules[schedule_key]
        self.schedule_count.value -= 1

        # Refund freed box MBR to admin
        box_mbr = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(41))
        itxn.Payment(
            receiver=Account(self.admin.value),
            amount=box_mbr,
            fee=UInt64(0),
        ).submit()
```

> **Note:** For revoked schedules, the NFT was already destroyed during `revoke`, freeing 100,000 microAlgos of MBR. However, `cleanup_schedule` only refunds the *box* MBR (22,900 microAlgos) to the admin. The freed NFT MBR remains in the contract's general balance. In a production contract, you would add a separate `withdraw_surplus` admin method to recover these funds.

> **Design decision: what about the NFT for fully-claimed schedules?** When a schedule is fully claimed but not revoked, the NFT still exists. The holder might want to keep it as a receipt or proof of participation. The contract does not force destruction. If the holder wants to recover the NFT's MBR (100,000 microAlgos on the contract), they can send the NFT back to the contract (via a standard asset transfer using `asset_close_to`), and a separate method could handle the destruction. For simplicity, we leave this as an exercise.

## Read-Only Queries

These methods let clients query vesting status without submitting a transaction via [simulate](https://dev.algorand.co/algokit/utils/python/app-client/). They are nearly identical to Chapter 3, but take an NFT asset ID instead of a beneficiary address:

```python
    @arc4.abimethod(readonly=True)
    def get_vesting_info(self, nft_asset_id: UInt64) -> VestingSchedule:
        schedule_key = arc4.UInt64(nft_asset_id)
        assert schedule_key in self.schedules, "No schedule"
        return self.schedules[schedule_key].copy()

    @arc4.abimethod(readonly=True)
    def get_claimable(self, nft_asset_id: UInt64) -> UInt64:
        schedule_key = arc4.UInt64(nft_asset_id)
        assert schedule_key in self.schedules, "No schedule"
        schedule = self.schedules[schedule_key].copy()
        if schedule.is_revoked.native:
            # Revoked schedules are fully settled; remaining is zero
            return UInt64(0)
        now = Global.latest_timestamp
        vested = calculate_vested(
            schedule.total_amount.as_uint64(),
            schedule.start_time.as_uint64(),
            schedule.cliff_end.as_uint64(),
            schedule.vesting_end.as_uint64(),
            now,
        )
        return vested - schedule.claimed_amount.as_uint64()
```

These methods use `readonly=True`, so clients can call them via `simulate` without paying fees --- instant, free queries. Note that `get_claimable` returns zero for revoked schedules because all vested tokens were settled during revocation.

## Consolidated Imports

Here is the complete import block for the contract file:

```python
from algopy import (
    ARC4Contract, Account, Asset, BoxMap, Bytes, Global, GlobalState,
    Txn, UInt64, arc4, gtxn, itxn, op, subroutine,
)
```

## Compiling and Testing

Compile the contract:

```bash
algokit project run build
```

If compilation succeeds, check `smart_contracts/artifacts/nft_vesting/` for the generated files: `NftVesting.approval.teal`, `NftVesting.clear.teal`, `NftVesting.arc56.json`, and `nft_vesting_client.py`.

Now create a deployment and interaction script. Save the following as `deploy_nft_vesting.py` in your project root. This script deploys the contract, creates a test token, deposits tokens, and creates a vesting schedule with an NFT:

```python
from pathlib import Path
import os
import struct
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
admin = algorand.account.localnet_dispenser()

# Create a beneficiary and a third account (to demonstrate NFT transfer)
beneficiary = algorand.account.random()
new_holder = algorand.account.random()
for acct in [beneficiary, new_holder]:
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=admin.address, receiver=acct.address,
            amount=algokit_utils.AlgoAmount.from_algo(10),
            note=os.urandom(8),
        )
    )

# Step 1: Create a test vesting token
result = algorand.send.asset_create(
    algokit_utils.AssetCreateParams(
        sender=admin.address,
        total=10_000_000_000,
        decimals=6,
        asset_name="Vesting Token",
        unit_name="TVT",
    )
)
token_id = result.asset_id
print(f"Created vesting token: ASA ID {token_id}")

# Step 2: Deploy the NFT vesting contract
app_spec = Path("smart_contracts/artifacts/nft_vesting/NftVesting.arc56.json").read_text()
factory = algorand.client.get_app_factory(
    app_spec=app_spec,
    default_sender=admin.address,
)
app_client, deploy_result = factory.deploy()
print(f"Deployed contract: App ID {app_client.app_id}")
print(f"Contract address: {app_client.app_address}")

# Step 3: Fund the contract and initialize
composer = algorand.new_group()
composer.add_payment(
    algokit_utils.PaymentParams(
        sender=admin.address,
        receiver=app_client.app_address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(300_000),
        note=os.urandom(8),
    )
)
composer.add_app_call_method_call(
    app_client.params.call(
        algokit_utils.AppClientMethodCallParams(
            method="initialize",
            args=[token_id],
            static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        )
    )
)
composer.send()
print("Contract initialized")

# Step 4: Deposit tokens
# The asset transfer is passed as a method argument --- the SDK composes the group
app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="deposit_tokens",
        args=[
            algokit_utils.AssetTransferParams(
                sender=admin.address,
                receiver=app_client.app_address,
                asset_id=token_id,
                amount=1_000_000_000,
                note=os.urandom(8),
            )
        ],
        note=os.urandom(8),
    )
)
print("Deposited 1,000 tokens (with 6 decimals)")

# Step 5: Create a vesting schedule (mint → opt-in → deliver)
nft_url = b"ipfs://QmExample#arc3"
metadata_hash = b"\x00" * 32  # Placeholder hash for testing

# Phase A: Create the schedule (contract mints and keeps the NFT)
# The box key depends on the NFT asset ID, which is unknown until the inner
# transaction executes. AlgoKit Utils handles this automatically: it simulates
# the transaction first to discover which resources are needed, then rebuilds
# it with the correct box references before submitting.
create_result = algorand.new_group().add_app_call_method_call(
    app_client.params.call(
        algokit_utils.AppClientMethodCallParams(
            method="create_schedule",
            args=[
                1_000_000_000,   # 1000 tokens (6 decimals)
                0,               # 0 cliff (for easy testing)
                31_536_000,      # 365 days vesting
                nft_url,
                metadata_hash,
                algokit_utils.PaymentParams(
                    sender=admin.address,
                    receiver=app_client.app_address,
                    amount=algokit_utils.AlgoAmount.from_micro_algo(122_900),
                    note=os.urandom(8),
                ),
            ],
            static_fee=algokit_utils.AlgoAmount.from_micro_algo(3000),
            box_references=[
                algokit_utils.BoxReference(
                    app_id=app_client.app_id, name=placeholder_box_key,
                ),
            ],
            note=os.urandom(8),
        )
    )
).send()
nft_id = create_result.returns[-1].value
print(f"Created vesting schedule with NFT ID: {nft_id}")

# Phase B: Beneficiary opts into the NFT and the vesting token
for asset_id in [nft_id, token_id]:
    algorand.send.asset_opt_in(
        algokit_utils.AssetOptInParams(
            sender=beneficiary.address, asset_id=asset_id,
            note=os.urandom(8),
        )
    )
print(f"Beneficiary opted into NFT {nft_id} and vesting token {token_id}")

# Phase C: Deliver the NFT to the beneficiary
app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="deliver_nft",
        args=[nft_id, beneficiary.address],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        note=os.urandom(8),
    )
)
print(f"Delivered NFT {nft_id} to beneficiary")

# Step 6: Claim vested tokens as the beneficiary
box_key = b"v_" + struct.pack(">Q", nft_id)
beneficiary_client = algorand.client.get_app_client_by_id(
    app_spec=app_spec,
    app_id=app_client.app_id,
    default_sender=beneficiary.address,
)
claim_result = beneficiary_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="claim",
        args=[nft_id],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        box_references=[algokit_utils.BoxReference(app_id=app_client.app_id, name=box_key)],
        note=os.urandom(8),
    )
)
print(f"Beneficiary claimed {claim_result.abi_return} tokens")

# Step 7: Demonstrate transferability --- transfer the NFT to a new holder
# New holder opts into the NFT and vesting token
for asset_id in [nft_id, token_id]:
    algorand.send.asset_opt_in(
        algokit_utils.AssetOptInParams(
            sender=new_holder.address, asset_id=asset_id,
            note=os.urandom(8),
        )
    )

# Beneficiary transfers the NFT --- a standard asset transfer, no contract involved
algorand.send.asset_transfer(
    algokit_utils.AssetTransferParams(
        sender=beneficiary.address,
        receiver=new_holder.address,
        asset_id=nft_id,
        amount=1,
        note=os.urandom(8),
    )
)
print(f"NFT transferred from beneficiary to new holder")

# New holder claims --- the contract only checks who holds the NFT
new_holder_client = algorand.client.get_app_client_by_id(
    app_spec=app_spec,
    app_id=app_client.app_id,
    default_sender=new_holder.address,
)
claim_result = new_holder_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="claim",
        args=[nft_id],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        box_references=[algokit_utils.BoxReference(app_id=app_client.app_id, name=box_key)],
        note=os.urandom(8),
    )
)
print(f"New holder claimed {claim_result.abi_return} tokens")
```

> **Tip:** The mint-then-deliver flow is the key coordination pattern for minting NFTs from contracts. The admin creates the schedule (which mints the NFT and returns its ID), the beneficiary opts in, and then the admin calls `deliver_nft`. This avoids the fragile simulate-then-submit approach where predicted asset IDs can shift on a live network.

Run the script:

```bash
poetry run python deploy_nft_vesting.py
```

If everything works, you will see the app ID, contract address, token ID, NFT ID, and claimed amounts for both the original beneficiary and the new holder. If you get a "box read/write budget exceeded" error, make sure you are passing the correct box reference in the `box_references` parameter. If you get "balance below minimum," increase the initial funding amount.

## Testing the NFT Vesting Contract

> **Note:** Before writing tests, ensure `pytest` and `algokit-utils` are in your project's dependencies. If they are not, add them to `pyproject.toml` and run `poetry install`. See the Chapter 2 testing section for full setup details and [Testing](https://dev.algorand.co/algokit/utils/python/testing/) for AlgoKit patterns.

> **Reminder (from Chapter 2):** On LocalNet, block timestamps only advance when new blocks are produced. Use short durations (seconds, not months) for cliff and vesting periods in tests. Add `note=os.urandom(8)` to every test transaction to prevent deduplication errors.

Save the following as `tests/test_nft_vesting.py`. These tests cover the security-critical paths --- especially that only the NFT holder can claim, and that transferring the NFT transfers claim rights:

```python
import os
import struct
from pathlib import Path
import time
import pytest
import algokit_utils

APP_SPEC = Path("smart_contracts/artifacts/nft_vesting/NftVesting.arc56.json").read_text()


# --- Helpers ---

def fund(algorand, sender, receiver, micro_algo):
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=sender.address, receiver=receiver.address,
            amount=algokit_utils.AlgoAmount.from_micro_algo(micro_algo),
            note=os.urandom(8),
        )
    )

def deploy(algorand, admin):
    factory = algorand.client.get_app_factory(
        app_spec=APP_SPEC, default_sender=admin.address,
    )
    return factory.deploy()[0]  # app_client

def initialize(algorand, admin, app_client, token_id):
    composer = algorand.new_group()
    composer.add_payment(algokit_utils.PaymentParams(
        sender=admin.address, receiver=app_client.app_address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(300_000),
        note=os.urandom(8),
    ))
    composer.add_app_call_method_call(app_client.params.call(
        algokit_utils.AppClientMethodCallParams(
            method="initialize", args=[token_id],
            static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        )
    ))
    composer.send()

def deposit(algorand, admin, app_client, token_id, amount):
    app_client.send.call(
        algokit_utils.AppClientMethodCallParams(
            method="deposit_tokens",
            args=[
                algokit_utils.AssetTransferParams(
                    sender=admin.address, receiver=app_client.app_address,
                    asset_id=token_id, amount=amount, note=os.urandom(8),
                )
            ],
            note=os.urandom(8),
        )
    )

def box_key(nft_id):
    return b"v_" + struct.pack(">Q", nft_id)

def create_schedule(algorand, admin, app_client, beneficiary, total,
                    cliff, vest, token_id):
    """Mint → opt-in → deliver. Returns the NFT asset ID."""
    url = b"ipfs://QmTest#arc3"
    meta = b"\x00" * 32

    # Step 1: Create the schedule (contract keeps the NFT)
    result = algorand.new_group().add_app_call_method_call(
        app_client.params.call(
            algokit_utils.AppClientMethodCallParams(
                method="create_schedule",
                args=[
                    total, cliff, vest, url, meta,
                    algokit_utils.PaymentParams(
                        sender=admin.address,
                        receiver=app_client.app_address,
                        amount=algokit_utils.AlgoAmount.from_micro_algo(122_900),
                        note=os.urandom(8),
                    ),
                ],
                static_fee=algokit_utils.AlgoAmount.from_micro_algo(3000),
                box_references=[
                    algokit_utils.BoxReference(
                        app_id=app_client.app_id, name=box_key(0),
                    ),
                ],
                note=os.urandom(8),
            )
        )
    ).send()
    nft_id = result.returns[-1].value

    # Step 2: Beneficiary opts in
    for asset_id in [nft_id, token_id]:
        algorand.send.asset_opt_in(algokit_utils.AssetOptInParams(
            sender=beneficiary.address, asset_id=asset_id,
            note=os.urandom(8),
        ))

    # Step 3: Deliver the NFT
    app_client.send.call(algokit_utils.AppClientMethodCallParams(
        method="deliver_nft", args=[nft_id, beneficiary.address],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        note=os.urandom(8),
    ))
    return nft_id

def client_for(algorand, app_client, account):
    return algorand.client.get_app_client_by_id(
        app_spec=APP_SPEC, app_id=app_client.app_id,
        default_sender=account.address,
    )

def claim(client, app_client, nft_id):
    return client.send.call(algokit_utils.AppClientMethodCallParams(
        method="claim", args=[nft_id],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
        box_references=[algokit_utils.BoxReference(app_id=app_client.app_id, name=box_key(nft_id))],
        note=os.urandom(8),
    ))

def advance_time(algorand, seconds):
    """Sleep and submit a dummy transaction to advance LocalNet timestamp."""
    time.sleep(seconds)
    algorand.send.payment(algokit_utils.PaymentParams(
        sender=algorand.account.localnet_dispenser().address,
        receiver=algorand.account.localnet_dispenser().address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(0),
        note=os.urandom(8),
    ))


# --- Tests ---

class TestNftVesting:
    @pytest.fixture()
    def algorand(self):
        return algokit_utils.AlgorandClient.default_localnet()

    def test_full_lifecycle(self, algorand):
        """Deploy, create schedule, claim partially, claim fully, cleanup."""
        admin = algorand.account.localnet_dispenser()
        ben = algorand.account.random()
        fund(algorand, admin, ben, 10_000_000)
        token_id = algorand.send.asset_create(
            algokit_utils.AssetCreateParams(
                sender=admin.address, total=10_000_000_000, decimals=6,
            )
        ).asset_id
        app = deploy(algorand, admin)
        initialize(algorand, admin, app, token_id)
        deposit(algorand, admin, app, token_id, 1_000_000_000)
        nft_id = create_schedule(algorand, admin, app, ben,
                                 1_000_000_000, cliff=0, vest=10, token_id=token_id)

        advance_time(algorand, 5)
        ben_client = client_for(algorand, app, ben)
        r = claim(ben_client, app, nft_id)
        assert r.abi_return > 0

        advance_time(algorand, 10)
        r = claim(ben_client, app, nft_id)
        assert r.abi_return > 0

    def test_nft_ownership_required(self, algorand):
        """An account without the NFT cannot claim."""
        admin = algorand.account.localnet_dispenser()
        ben = algorand.account.random()
        attacker = algorand.account.random()
        fund(algorand, admin, ben, 10_000_000)
        fund(algorand, admin, attacker, 10_000_000)
        token_id = algorand.send.asset_create(
            algokit_utils.AssetCreateParams(
                sender=admin.address, total=10_000_000_000, decimals=6,
            )
        ).asset_id
        app = deploy(algorand, admin)
        initialize(algorand, admin, app, token_id)
        deposit(algorand, admin, app, token_id, 1_000_000_000)
        nft_id = create_schedule(algorand, admin, app, ben,
                                 1_000_000_000, cliff=0, vest=30, token_id=token_id)

        advance_time(algorand, 5)

        # Attacker opts into vesting token but does NOT hold the NFT
        algorand.send.asset_opt_in(algokit_utils.AssetOptInParams(
            sender=attacker.address, asset_id=token_id, note=os.urandom(8),
        ))
        attacker_client = client_for(algorand, app, attacker)
        with pytest.raises(Exception):
            claim(attacker_client, app, nft_id)

    def test_transfer_transfers_claim_rights(self, algorand):
        """After NFT transfer, only the new holder can claim."""
        admin = algorand.account.localnet_dispenser()
        ben = algorand.account.random()
        buyer = algorand.account.random()
        fund(algorand, admin, ben, 10_000_000)
        fund(algorand, admin, buyer, 10_000_000)
        token_id = algorand.send.asset_create(
            algokit_utils.AssetCreateParams(
                sender=admin.address, total=10_000_000_000, decimals=6,
            )
        ).asset_id
        app = deploy(algorand, admin)
        initialize(algorand, admin, app, token_id)
        deposit(algorand, admin, app, token_id, 1_000_000_000)
        nft_id = create_schedule(algorand, admin, app, ben,
                                 1_000_000_000, cliff=0, vest=30, token_id=token_id)

        advance_time(algorand, 5)

        # Buyer opts in and receives the NFT
        for aid in [nft_id, token_id]:
            algorand.send.asset_opt_in(algokit_utils.AssetOptInParams(
                sender=buyer.address, asset_id=aid, note=os.urandom(8),
            ))
        algorand.send.asset_transfer(algokit_utils.AssetTransferParams(
            sender=ben.address, receiver=buyer.address,
            asset_id=nft_id, amount=1, note=os.urandom(8),
        ))

        # Original holder cannot claim
        ben_client = client_for(algorand, app, ben)
        with pytest.raises(Exception):
            claim(ben_client, app, nft_id)

        # New holder can claim
        buyer_client = client_for(algorand, app, buyer)
        r = claim(buyer_client, app, nft_id)
        assert r.abi_return > 0

    def test_admin_only_rejects_non_admin(self, algorand):
        """Non-admin callers are rejected."""
        admin = algorand.account.localnet_dispenser()
        attacker = algorand.account.random()
        fund(algorand, admin, attacker, 10_000_000)
        token_id = algorand.send.asset_create(
            algokit_utils.AssetCreateParams(
                sender=admin.address, total=10_000_000_000, decimals=6,
            )
        ).asset_id
        app = deploy(algorand, admin)
        initialize(algorand, admin, app, token_id)

        attacker_client = client_for(algorand, app, attacker)
        with pytest.raises(Exception):
            attacker_client.send.call(algokit_utils.AppClientMethodCallParams(
                method="initialize", args=[token_id], note=os.urandom(8),
            ))

    def test_claim_before_cliff_fails(self, algorand):
        """Claiming before the cliff period ends fails."""
        admin = algorand.account.localnet_dispenser()
        ben = algorand.account.random()
        fund(algorand, admin, ben, 10_000_000)
        token_id = algorand.send.asset_create(
            algokit_utils.AssetCreateParams(
                sender=admin.address, total=10_000_000_000, decimals=6,
            )
        ).asset_id
        app = deploy(algorand, admin)
        initialize(algorand, admin, app, token_id)
        deposit(algorand, admin, app, token_id, 1_000_000_000)
        nft_id = create_schedule(algorand, admin, app, ben,
                                 1_000_000_000, cliff=15, vest=30, token_id=token_id)

        # Only 2 seconds in, cliff is 15 seconds
        advance_time(algorand, 2)
        ben_client = client_for(algorand, app, ben)
        with pytest.raises(Exception):
            claim(ben_client, app, nft_id)
```

The two most important tests are `test_nft_ownership_required` and `test_transfer_transfers_claim_rights`. Together they prove the contract's core security property: only the current NFT holder can claim, and that right moves with the NFT.

## How Transferability Works in Practice

With the contract deployed, here is what transferability looks like from a user's perspective. (Standard [ASA transfers](https://dev.algorand.co/concepts/assets/asset-operations/) handle the NFT movement --- no custom transfer logic needed.)

1. **Admin creates a schedule.** An NFT is minted and transferred to the beneficiary. The NFT appears in the beneficiary's wallet alongside their other assets.

2. **Beneficiary claims periodically.** They call `claim` with their NFT's asset ID. The contract verifies they hold the NFT and releases vested tokens.

3. **Beneficiary transfers the NFT.** They send it to another address using a standard asset transfer --- the same transaction type used for sending any Algorand token. No contract interaction is needed.

4. **New holder claims.** The new holder calls `claim` with the same NFT asset ID. The contract checks their balance, sees they hold the NFT, and releases tokens to them. The contract does not know or care that ownership changed.

5. **NFT on a marketplace.** The vesting NFT can be listed on any Algorand NFT marketplace. A buyer purchases it and receives the right to future token claims. The marketplace does not need special integration with the vesting contract --- it just facilitates an ASA transfer.

This composability is the power of the ownership-by-asset pattern. The vesting contract does not need to know about wallets, marketplaces, lending protocols, or any other system. It only checks one thing: does the caller hold the NFT?

## Summary

In this chapter you learned to:

- Explain what makes an ASA an NFT on Algorand (total=1, decimals=0) and why no special contract is needed
- Use the ARC-3 standard to attach metadata to NFTs via URL and metadata hash
- Mint an ASA from within a smart contract using `itxn.AssetConfig`
- Apply the ownership-by-asset pattern to decouple rights from addresses
- Use clawback to reclaim NFTs during revocation and destroy them to recover MBR
- Calculate MBR implications when a contract creates ASAs (100,000 microAlgos per asset)
- Coordinate opt-in timing using the mint-then-deliver pattern for contract-minted ASAs

| Step | Feature | Concepts Introduced |
|------|---------|---------------------|
| 1 | NFT minting | `itxn.AssetConfig` for ASA creation, role addresses (manager, clawback, freeze, reserve), inner transaction fee budgeting |
| 2 | ARC-3 metadata | Off-chain metadata via URL + hash, IPFS hosting pattern, `#arc3` convention |
| 3 | Ownership-by-asset | `Asset.balance()` for ownership verification, decoupling rights from addresses |
| 4 | Transferability | Standard ASA transfers for right transfer, composability with wallets and marketplaces |
| 5 | Clawback on revoke | `asset_sender` field for clawback, NFT destruction via empty `AssetConfig`, MBR recovery |
| 6 | Settle on revoke | Vested-but-unclaimed token transfer before NFT destruction, claimed_amount bookkeeping |
| 7 | Balance-capped claims | Defensive `Asset.balance()` check prevents hard failure if contract is under-funded |
| 8 | Box key design | Keying by asset ID instead of address, MBR tradeoffs |

In the next chapter, we build a constant product AMM (Chapter 5) where multi-token accounting, price curves, and LP token mechanics introduce a new level of complexity. The inner transaction and ASA creation patterns from this chapter will reappear --- the AMM mints its own LP token using the same `itxn.AssetConfig` approach.

## Exercises

1. **(Apply)** The `cleanup_schedule` method does not destroy the NFT for fully-claimed (non-revoked) schedules. Add a `close_nft` method where the NFT holder can voluntarily return the NFT to the contract for destruction, recovering the 100,000 microAlgo MBR. What should happen to the recovered MBR --- should it go to the holder, the admin, or be split?

2. **(Analyze)** A secondary market buyer purchases a vesting NFT from a team member. The buyer pays 500 Algo for a schedule with 10,000 tokens remaining. The next day, the admin calls `revoke`. The buyer loses their 500 Algo investment and receives only whatever had vested in that single day. Is this a bug or a feature? How would you modify the contract to protect secondary market buyers while still allowing revocation?

3. **(Analyze)** The contract sets `freeze=Global.zero_address` so NFTs are always transferable. What would happen if you set `freeze=Global.current_application_address` instead? Design a `freeze_schedule` method that freezes an NFT when the beneficiary is under investigation. What are the legal and trust implications?

4. **(Create)** Design an extension where vesting schedules can be *split*: a holder can divide their NFT into two new NFTs, each representing a portion of the remaining allocation. What new method is needed? How do you handle the box storage (one box becomes two)? What happens to the original NFT?

5. **(Create)** The Known Limitation in the Revocation section describes how a holder who has not opted into the vesting token can block revocation. Design a solution: add opt-in status checking to `revoke` so that when the holder is not opted in, vested-but-unclaimed tokens are stored in a `pending_settlements` BoxMap instead of being transferred immediately. Add a `withdraw_settlement` method the holder can call after opting in. What are the MBR implications of the extra box?

## Further Reading

- [Algorand Standard Assets](https://dev.algorand.co/concepts/assets/overview/) --- ASA architecture, role addresses (manager, clawback, freeze, reserve)
- [Asset Operations](https://dev.algorand.co/concepts/assets/asset-operations/) --- creation, transfer, opt-in, clawback, destruction
- [ARC-3: NFT Metadata](https://dev.algorand.co/arc-standards/arc-0003/) --- URL convention, metadata hash, JSON schema
- [ARC-19: Mutable Metadata](https://dev.algorand.co/arc-standards/arc-0019/) --- template-based URLs using the reserve address
- [ARC-56: Application Specification](https://dev.algorand.co/arc-standards/arc-0056/) --- the app spec format used by typed clients and tooling
- [Resource Usage](https://dev.algorand.co/concepts/smart-contracts/resource-usage/) --- foreign references, group-level sharing, box references

## Before You Continue

Before starting the AMM chapter, you should be able to:

- [ ] Explain what makes an ASA an NFT on Algorand (total=1, decimals=0)
- [ ] Use `itxn.AssetConfig` to mint an ASA from within a contract
- [ ] Apply the ownership-by-asset pattern to decouple rights from addresses
- [ ] Use clawback to reclaim NFTs and destroy them to recover MBR
- [ ] Pass grouped transactions (payment, asset transfer) as ABI method arguments
- [ ] Use the mint-then-deliver pattern to coordinate opt-in for contract-minted ASAs
- [ ] Calculate MBR implications when a contract creates ASAs

If any of these are unclear, revisit the relevant section before proceeding.

\newpage

\part{Building a DEX}

Part II applies the foundations to DeFi. You will build a constant product AMM with multi-token accounting, price curves, and LP token mechanics, then extend it with a yield farming contract that introduces the reward accumulator pattern and smart contract composition. The part concludes with the cross-cutting production patterns --- fee subsidization, MBR lifecycle, event emission --- that separate tutorial code from production code.

# A Constant Product AMM

You have built a contract that holds tokens, tracks per-user data in boxes, performs safe integer math, and releases assets via inner transactions. Now we are going to apply all of that --- and introduce several new concepts --- to build something significantly more complex: an automated market maker.

An AMM is a smart contract that holds reserves of two tokens and allows anyone to swap one for the other. There is no order book, no matching engine, no counterparty. The contract itself is the market maker, using a mathematical formula to determine the exchange rate. Liquidity providers deposit both tokens into the pool and receive LP tokens representing their share. Traders swap against the pool, paying a small fee that accrues to LPs. This is the mechanism behind Uniswap, SushiSwap, and Tinyman --- the dominant DEX model in DeFi.

By the end of this chapter you will have a working AMM pool contract with creation, bootstrapping, swapping, liquidity provision, liquidity withdrawal, and comprehensive security hardening. Each section builds on the previous one, and new Algorand concepts are introduced only when the AMM requires them.

### Project Setup

Scaffold a new project for this chapter. The `--name` flag sets the project directory; the template always creates a `hello_world/` contract inside it, which we rename:

```bash
algokit init -t python --name constant-product-amm
cd constant-product-amm
algokit project bootstrap all
mv smart_contracts/hello_world smart_contracts/constant_product_pool
```

Your contract code goes in `smart_contracts/constant_product_pool/contract.py`. Replace the template-generated contents of `contract.py` with the code shown below --- do not append to the existing template code. Also delete the template-generated `deploy_config.py` in the renamed directory --- it references the old `HelloWorld` contract.

If you have never used a decentralized exchange, here is the core idea. Imagine you want to trade token A for token B, but there is nobody online right now who wants the opposite trade. An AMM solves this by replacing the human counterparty with a smart contract that holds reserves of both tokens. The contract uses a mathematical formula to set the price: the more of token A you buy, the more expensive it gets (because the pool is running out). Anyone can deposit tokens into the pool to earn trading fees --- these depositors are called *liquidity providers* (LPs), and the pool gives them *LP tokens* as receipts representing their share. When they want to exit, they burn their LP tokens and receive their proportional share of both reserves plus accumulated fees. A *DEX* (decentralized exchange) is simply a frontend that lets users interact with one or more AMM contracts.


## The Math Behind Constant Product Markets

Before writing any code, you need to understand the formula that governs every operation in this contract. A constant product AMM maintains the invariant:

$$x \times y = k$$

where $x$ is the reserve of token A, $y$ is the reserve of token B, and $k$ is a constant that can only increase (from fees). This equation defines a hyperbolic curve --- as you buy token B (decreasing $y$), the price rises because the product $k$ must be maintained, forcing $x$ to increase proportionally. The marginal price at any point along the curve is $y / x$.

When a trader swaps $\Delta x$ of token A for token B, the contract calculates how much token B to release. The new reserves must satisfy the invariant (with fees):

$$(x + \Delta x \times 0.997) \times (y - \Delta y) \geq x \times y$$

Solving for $\Delta y$ (the output amount):

$$\Delta y = \frac{\Delta x \times 997 \times y}{x \times 1000 + \Delta x \times 997}$$

The $997/1000$ factor represents a 0.3\% fee --- 0.3\% of every swap's input stays in the pool, gradually increasing $k$ and thus the value of LP tokens. This fee is not distributed separately. It accumulates naturally in the reserves, meaning each LP token becomes redeemable for slightly more underlying assets over time.

**Worked example.** Alice has 100 USDC and wants to swap for ALGO from a pool with reserves of 10,000 USDC ($x$) and 10,000 ALGO ($y$). Before the swap, $k = 10{,}000 \times 10{,}000 = 100{,}000{,}000$ and the spot price is $10{,}000 / 10{,}000 = 1.0$ ALGO per USDC. Plugging into the formula:

$$\Delta y = \frac{100 \times 997 \times 10{,}000}{10{,}000 \times 1{,}000 + 100 \times 997} = \frac{9{,}970{,}000}{10{,}099{,}700} \approx 98.71\ \textrm{ALGO}$$

Alice sends 100 USDC and receives 98.71 ALGO --- not 100, because of the 0.3% fee (0.3 USDC stays in the pool) and *price impact* (each marginal unit of USDC she adds makes ALGO slightly more expensive). After the swap, reserves are 10,100 USDC and 9,901.29 ALGO, giving a new spot price of $9{,}901.29 / 10{,}100 \approx 0.98$ ALGO per USDC. The product $k$ increased slightly (to $\approx 100{,}003{,}029$) because the fee was retained. A larger trade --- say 1,000 USDC --- would move the price much more (receiving only about 906 ALGO, a 9.3% price impact), which is why AMMs work best for trades that are small relative to the pool's reserves.

For initial liquidity, the number of LP tokens minted equals:

$$LP_{\text{initial}} = \sqrt{\Delta x \times \Delta y} - \text{MINIMUM\_LIQUIDITY}$$

For subsequent deposits:

$$LP_{new} = \min\left(\frac{\Delta x}{x}, \frac{\Delta y}{y}\right) \times LP_{total}$$

Taking the minimum of both ratios penalizes unbalanced deposits --- any excess tokens beyond the current ratio are effectively donated to the pool.

The $\text{MINIMUM\_LIQUIDITY}$ lock (typically 1,000 LP tokens) prevents a first-depositor attack where an attacker deposits 1 wei of each token, receives 1 LP token, then donates large amounts to inflate the value per share so high that subsequent depositors cannot afford meaningful positions.

These formulas are the entire economic engine of the AMM. Everything else is implementation details around making them work correctly, safely, and efficiently on the [AVM](https://dev.algorand.co/concepts/smart-contracts/avm/).

> **Design decision: why constant product?** If I were designing this from scratch, I would start with the simplest invariant: what relationship between reserves should never be violated? The product $x \times y = k$ is the simplest nonlinear invariant. It is not the only option.
>
> *Concentrated liquidity* (Uniswap V3 - no equivalent on Algorand) lets LPs provide liquidity within a chosen price range instead of across the entire curve. An LP who concentrates in a ±1% range provides ~4,000x the capital efficiency of a full-range V2 position --- but their position becomes an NFT (each range is unique), and they suffer amplified impermanent loss if price leaves their range. V3 is powerful but significantly more complex to implement, especially within Algorand's 8KB program size and 700-opcode budget constraints.
>
> *StableSwap* (Curve, and Pact stable pools on Algorand) uses a hybrid invariant tuned for assets that should trade near 1:1 (stablecoins, wrapped assets). It provides dramatically lower slippage for pegged pairs.
>
> Constant product is the right starting point because it is simple enough to reason about completely, requires no off-chain infrastructure for active management, and is the foundation that V3 and StableSwap build upon. Master this, and the others are variations on the theme.

## Pool Contract Creation and the Escrow Pattern

Each asset pair gets its own contract instance --- one pool per pair. This provides strong isolation: a vulnerability in one pool cannot drain another. The alternative (a single contract managing all pools) would be simpler to deploy but catastrophically worse if compromised.

The contract will hold both pool assets plus the LP token it creates. Its address acts as an autonomous escrow --- no private key exists, and the contract's logic is the sole authority over outflows. (See [Applications](https://dev.algorand.co/concepts/smart-contracts/apps/) for how contract addresses are derived.) This is the same escrow pattern from the vesting contract, but now holding three different assets and serving many concurrent users. In production, a *factory contract* handles deployment: it creates a new pool contract instance for each asset pair, registers the pair in its own state for lookup, and enforces that no duplicate pools exist. See Cookbook section 8.3 for the factory pattern (creating contracts from contracts via inner transactions).

We begin with the state declarations. These should look familiar from the vesting contract, with a few additions.

Add the following to `smart_contracts/constant_product_pool/contract.py`:

```python
from algopy import (
    ARC4Contract, Asset, BigUInt, Global, GlobalState, Txn, UInt64,
    arc4, itxn, op, subroutine, gtxn,
)

MINIMUM_LIQUIDITY = 1000
TWAP_PRECISION = 10**9

class ConstantProductPool(ARC4Contract):
    def __init__(self) -> None:
        self.asset_a = GlobalState(UInt64(0))
        self.asset_b = GlobalState(UInt64(0))
        self.lp_token_id = GlobalState(UInt64(0))
        self.reserve_a = GlobalState(UInt64(0))
        self.reserve_b = GlobalState(UInt64(0))
        self.lp_total_supply = GlobalState(UInt64(0))
        self.locked_liquidity = GlobalState(UInt64(0))
        self.is_bootstrapped = GlobalState(UInt64(0))
        # TWAP oracle state
        self.cumulative_price_a = GlobalState(BigUInt(0))
        self.cumulative_price_b = GlobalState(BigUInt(0))
        self.twap_last_update = GlobalState(UInt64(0))

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "Contract is immutable"
```

We are using global state rather than box storage for the pool's reserves and configuration. This is the right choice here: the data is small (11 fields), belongs to the application itself (not per-user), and is accessed on every single operation. Global state has a 64-pair limit, but we are nowhere near that. The schema is declared once at deployment and cannot change, so we have allocated all the fields we will need upfront. The three TWAP fields (`cumulative_price_a`, `cumulative_price_b`, `twap_last_update`) support the price oracle that we will build later in this chapter. The two `BigUInt` cumulatives are stored as byte-slice global state slots (not uint slots), so the contract's schema needs both `global_uints` and `global_bytes` allocations. PuyaPy handles this automatically.


## Bootstrapping the Pool

Bootstrapping is the one-time initialization that creates the LP token, opts the contract into both pool assets, and establishes the pool's identity. This is more involved than the vesting contract's `initialize` because we are creating a new ASA (the LP token) and performing two asset opt-ins.

Canonical asset ordering --- always placing the lower ASA ID first --- prevents duplicate pools for the same pair. Without this, someone could create a USDC/ALGO pool and a separate ALGO/USDC pool, fragmenting liquidity. By enforcing `asset_a.id < asset_b.id`, there is exactly one valid pool per pair. (See [Asset Metadata](https://dev.algorand.co/concepts/assets/asset-metadata/) for how asset IDs are assigned.)

Add this method to the `ConstantProductPool` class in `smart_contracts/constant_product_pool/contract.py`:

```python
    @arc4.abimethod
    def bootstrap(
        self,
        seed_payment: gtxn.PaymentTransaction,
        asset_a: Asset,
        asset_b: Asset,
    ) -> UInt64:
        """One-time pool initialization. Creates LP token, opts into assets."""
        assert Txn.sender == Global.creator_address, "Only creator can bootstrap"
        assert self.is_bootstrapped.value == UInt64(0), "Already bootstrapped"
        assert asset_a.id < asset_b.id, "Assets must be in canonical order"

        # Seed payment covers MBR for LP token creation + 2 asset opt-ins
        assert seed_payment.receiver == Global.current_application_address
        assert seed_payment.amount >= UInt64(400_000)

        self.asset_a.value = asset_a.id
        self.asset_b.value = asset_b.id

        # Create the LP token via inner transaction
        lp_create = itxn.AssetConfig(
            asset_name=b"CPMM-LP",
            unit_name=b"LP",
            total=UInt64(2**63),
            decimals=UInt64(6),
            manager=Global.current_application_address,
            reserve=Global.current_application_address,
            fee=UInt64(0),
        ).submit()
        self.lp_token_id.value = lp_create.created_asset.id

        # Opt into both pool assets
        itxn.AssetTransfer(
            xfer_asset=asset_a,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()

        itxn.AssetTransfer(
            xfer_asset=asset_b,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()

        self.is_bootstrapped.value = UInt64(1)
        return self.lp_token_id.value
```

The LP token has a total supply of $2^{63}$ --- a very large number that the pool will never exhaust. Setting no freeze and no clawback address (by omitting them) makes the token fully permissionless. The manager and reserve are set to the pool contract itself, though in practice these have no operational significance for an LP token.

Notice the seed payment pattern: the caller sends Algo to cover the MBR for the LP token creation (100,000 microAlgos) plus two asset opt-ins (100,000 each) plus the global state MBR plus a buffer. This is the same MBR-funding-via-grouped-payment pattern from the vesting contract, but scaled up for more resources.

The group has 5 transactions total: 1 seed payment + 1 app call + 3 inner transactions (LP creation + 2 asset opt-ins). With fee pooling, `static_fee = 5000` on the app call, plus the seed payment's default 1,000 fee, provides sufficient coverage.

## Deploying and Bootstrapping on LocalNet

Let us walk through deploying the pool contract and bootstrapping it with two test tokens on LocalNet. This verifies that everything compiles and the bootstrap sequence works before we add more methods.

First, create a new project for the AMM (or add the pool contract to your existing project). Replace the contract file contents with the `ConstantProductPool` class including the `__init__`, `reject_lifecycle`, and `bootstrap` methods. Compile:

```bash
algokit project run build
```

The AMM contract uses more imports than the vesting contract --- make sure you have `Asset`, `BigUInt`, `Global`, `GlobalState`, `Txn`, `UInt64`, `arc4`, `itxn`, `op`, `subroutine`, and `gtxn`.

Now create a deployment and bootstrap script. Save the following as `deploy_pool.py` in your project root. This client-side script creates two test ASAs, deploys the pool, funds it, and calls bootstrap.

```python
from pathlib import Path
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
admin = algorand.account.localnet_dispenser()

# Create two test tokens
def create_test_asa(name, unit):
    result = algorand.send.asset_create(
        algokit_utils.AssetCreateParams(
            sender=admin.address,
            total=10_000_000_000_000, decimals=6,
            asset_name=name, unit_name=unit,
        )
    )
    return result.asset_id

token_a = create_test_asa("TokenA", "TKA")
token_b = create_test_asa("TokenB", "TKB")
# Ensure canonical ordering (lower ID first)
if token_a > token_b:
    token_a, token_b = token_b, token_a
print(f"Token A: {token_a}, Token B: {token_b}")

# Deploy the pool contract
factory = algorand.client.get_app_factory(
    app_spec=Path("smart_contracts/artifacts/constant_product_pool/ConstantProductPool.arc56.json").read_text(),
    default_sender=admin.address,
)
app_client, deploy_result = factory.send.bare.create()
print(f"Pool App ID: {app_client.app_id}")
print(f"Pool Address: {app_client.app_address}")

# Bootstrap: fund the pool + call bootstrap.
# The seed payment is passed as the first argument to the bootstrap method.
# AlgoKit automatically places it as the preceding transaction in the group.
result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="bootstrap",
        args=[
            algokit_utils.PaymentParams(
                sender=admin.address,
                receiver=app_client.app_address,
                amount=algokit_utils.AlgoAmount.from_micro_algo(500_000),  # 0.5 Algo for MBR
            ),
            token_a,
            token_b,
        ],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(5000),  # Covers inner txns
    )
)
lp_token_id = result.abi_return  # Return value from the bootstrap call
print(f"LP Token ID: {lp_token_id}")
print("Bootstrap complete!")
```

Run with `python deploy_pool.py`. You should see three IDs printed: the two test tokens and the LP token. If you get `"Already bootstrapped"`, you are calling bootstrap on a pool that was already initialized --- reset LocalNet with `algokit localnet reset` and try again.

You can verify the pool's state by reading its global state:

```bash
curl -s http://localhost:4001/v2/applications/YOUR_APP_ID \
  -H "X-Algo-API-Token: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
  | python -m json.tool
```

The global state should show `asset_a`, `asset_b`, and `lp_token_id` populated with the correct ASA IDs, `is_bootstrapped` set to 1, and `reserve_a` and `reserve_b` both at 0 (no liquidity yet).


## Initial Liquidity Provision

The first liquidity provider sets the pool's initial price ratio by choosing how much of each token to deposit. The ratio of their deposit defines the starting price: depositing 1,000 USDC and 4 ALGO sets the price at 250 USDC per ALGO (or equivalently, 0.004 ALGO per USDC).

LP tokens minted for the first deposit use the geometric mean of the two amounts, minus the minimum liquidity lock. (See [Algorand Python ops](https://dev.algorand.co/algokit/languages/python/lg-ops/) for the `bsqrt` and wide arithmetic opcodes used here.)

$$LP = \sqrt{\text{amount\_A} \times \text{amount\_B}} - \text{MINIMUM\_LIQUIDITY}$$

The geometric mean ensures the LP amount is independent of the price level --- depositing 1 USDC + 1,000 ALGO mints the same LP tokens as 1,000 USDC + 1 ALGO. The minimum liquidity lock permanently removes 1,000 LP tokens from circulation (the contract holds them and never transfers them), preventing the first-depositor attack described earlier.

Add this method to the `ConstantProductPool` class in `smart_contracts/constant_product_pool/contract.py`:

```python
    @arc4.abimethod
    def add_initial_liquidity(
        self,
        a_txn: gtxn.AssetTransferTransaction,
        b_txn: gtxn.AssetTransferTransaction,
    ) -> UInt64:
        """First deposit sets the price ratio and mints initial LP tokens."""
        assert self.is_bootstrapped.value == UInt64(1), "Not bootstrapped"
        assert self.lp_total_supply.value == UInt64(0), "Pool already has liquidity"

        assert a_txn.asset_receiver == Global.current_application_address
        assert b_txn.asset_receiver == Global.current_application_address
        assert a_txn.xfer_asset == Asset(self.asset_a.value)
        assert b_txn.xfer_asset == Asset(self.asset_b.value)

        amount_a = a_txn.asset_amount
        amount_b = b_txn.asset_amount
        assert amount_a > UInt64(0) and amount_b > UInt64(0)

        # LP tokens = sqrt(a * b) - MINIMUM_LIQUIDITY
        # Use BigUInt for the intermediate product to prevent overflow.
        # op.btoi converts the BigUInt result back to UInt64; this will panic
        # if the sqrt exceeds 2^64. In practice, this limits initial deposits
        # to ~3.4e19 base units per token (far beyond any realistic supply).
        product = BigUInt(amount_a) * BigUInt(amount_b)
        sqrt_product = op.bsqrt(product)
        lp_tokens = op.btoi(sqrt_product.bytes) - UInt64(MINIMUM_LIQUIDITY)
        assert lp_tokens > UInt64(0), "Insufficient initial liquidity"

        self.reserve_a.value = amount_a
        self.reserve_b.value = amount_b
        self.lp_total_supply.value = lp_tokens + UInt64(MINIMUM_LIQUIDITY)
        self.locked_liquidity.value = UInt64(MINIMUM_LIQUIDITY)

        # Send LP tokens to the provider
        itxn.AssetTransfer(
            xfer_asset=Asset(self.lp_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=lp_tokens,
            fee=UInt64(0),
        ).submit()

        # Initialize TWAP tracking with the first reserves
        self.twap_last_update.value = Global.latest_timestamp

        return lp_tokens
```

The `BigUInt` multiplication prevents overflow in the product --- if both amounts are 10^12, the product is 10^24, far beyond uint64. The `op.bsqrt` opcode computes the integer floor square root natively on the AVM.

> **Warning:** The caller must have already opted into the LP token before calling this method. If they have not, the inner `AssetTransfer` sending LP tokens will fail, and the entire atomic group rolls back --- the pool receives no tokens and no state changes. This is the "lazy opt-in" pattern: the contract does not check the opt-in explicitly; the protocol enforces it automatically. Client code must perform a zero-amount self-transfer of the LP token before calling `add_initial_liquidity`.


## The Swap

*Before looking at the implementation: given reserves of 10,000 USDC and 10,000 ALGO, how many ALGO should a trader receive for 100 USDC? Try working it out with the constant product formula (with 0.3% fee). Then: what is the new spot price after the swap? The answer may surprise you --- it is not exactly 100, and the spot price shifts even for this relatively small trade.*

This is the operation users interact with most frequently. A trader sends token A to the pool and receives token B (or vice versa). The constant product formula determines the exchange rate, and a 0.3\% fee is deducted from the input.

The swap introduces a concept not needed in the vesting contract: *slippage protection*. (See [Atomic Groups](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/) for how grouped transactions provide all-or-nothing execution guarantees.) Between when a user fetches a price quote (reading reserves off-chain) and when their transaction executes, other swaps may change the reserves. Without protection, the user could receive far less than expected. The `min_output` parameter sets a floor --- if the calculated output falls below this, the transaction fails.

Add this module-level subroutine to `smart_contracts/constant_product_pool/contract.py` (outside the class):

```python
@subroutine
def _calculate_swap_output(
    input_amount: UInt64, reserve_in: UInt64, reserve_out: UInt64,
) -> UInt64:
    """Constant product output with 0.3% fee.
    output = (input * 997 * reserve_out) / (reserve_in * 1000 + input * 997)
    """
    input_with_fee = input_amount * UInt64(997)
    # Use wide arithmetic: numerator = input_with_fee * reserve_out
    num_high, num_low = op.mulw(input_with_fee, reserve_out)
    denominator = reserve_in * UInt64(1000) + input_with_fee
    # Divide 128-bit numerator by 64-bit denominator
    q_hi, output, r_hi, r_lo = op.divmodw(num_high, num_low, UInt64(0), denominator)
    return output
```

The wide arithmetic here is essential. With reserves of 10^12 and an input of 10^9, the numerator `input_with_fee * reserve_out` reaches 10^21 --- overflowing uint64. The `mulw`/`divmodw` pair keeps the intermediate product in 128 bits.

Note that `input_amount * UInt64(997)` can itself overflow if `input_amount` exceeds approximately 1.85 × 10^16. For a 6-decimal token, this allows single swaps up to ~18.5 billion tokens --- far beyond any realistic supply. If your token has extreme parameters, you would need to apply wide arithmetic to this multiplication as well.

Floor division in the output calculation means the user gets slightly less than the mathematically exact amount. This is correct: the rounding dust stays in the pool, ensuring the constant product invariant is maintained or strengthened (never weakened) by rounding.

> **Check your understanding:** Why is floor division correct from the pool's perspective? What would happen if the contract rounded *up* instead? Think about the constant product invariant: would it be maintained, strengthened, or violated?

Add this method to the `ConstantProductPool` class in `smart_contracts/constant_product_pool/contract.py`:

```python
    @arc4.abimethod
    def swap(
        self,
        input_txn: gtxn.AssetTransferTransaction,
        min_output: UInt64,
    ) -> UInt64:
        """Swap one pool asset for the other."""
        self._update_twap()

        assert input_txn.asset_receiver == Global.current_application_address

        input_asset = input_txn.xfer_asset
        input_amount = input_txn.asset_amount
        assert input_amount > UInt64(0), "Zero input"

        # Determine swap direction
        if input_asset == Asset(self.asset_a.value):
            reserve_in = self.reserve_a.value
            reserve_out = self.reserve_b.value
            output_asset = Asset(self.asset_b.value)
        else:
            assert input_asset == Asset(self.asset_b.value), "Unknown asset"
            reserve_in = self.reserve_b.value
            reserve_out = self.reserve_a.value
            output_asset = Asset(self.asset_a.value)

        output_amount = _calculate_swap_output(input_amount, reserve_in, reserve_out)
        assert output_amount >= min_output, "Slippage exceeded"
        assert output_amount > UInt64(0), "Zero output"
        assert output_amount < reserve_out, "Insufficient reserves"

        # Send output tokens to the user
        itxn.AssetTransfer(
            xfer_asset=output_asset,
            asset_receiver=Txn.sender,
            asset_amount=output_amount,
            fee=UInt64(0),
        ).submit()

        # Update reserves
        new_reserve_in = reserve_in + input_amount
        new_reserve_out = reserve_out - output_amount
        if input_asset == Asset(self.asset_a.value):
            self.reserve_a.value = new_reserve_in
            self.reserve_b.value = new_reserve_out
        else:
            self.reserve_b.value = new_reserve_in
            self.reserve_a.value = new_reserve_out

        return output_amount
```

The invariant check --- verifying that `new_reserve_a * new_reserve_b >= old_reserve_a * old_reserve_b` --- is implicit in the formula. Because the output is calculated from the formula and rounded down, the invariant is mathematically guaranteed to hold. For additional defense-in-depth, you can add an explicit check using wide arithmetic. Insert this in the `swap` method, after calculating `new_reserve_in` and `new_reserve_out` and before writing them to global state, in `smart_contracts/constant_product_pool/contract.py`:

```python
        # Explicit invariant verification (defense-in-depth)
        old_k_high, old_k_low = op.mulw(reserve_in, reserve_out)
        new_k_high, new_k_low = op.mulw(new_reserve_in, new_reserve_out)
        # new_k >= old_k (compare 128-bit values)
        assert new_k_high > old_k_high or (
            new_k_high == old_k_high and new_k_low >= old_k_low
        ), "Invariant violated"
```

Tinyman V2 made this explicit check mandatory after every operation --- it was one of the key lessons from the V1 exploit. Even if the swap formula is correct, an explicit invariant check catches implementation bugs that the formula alone might not.

## Executing Your First Swap on LocalNet

With bootstrap, initial liquidity, and swap all implemented, you can now execute a complete trading workflow on LocalNet. Recompile after adding all three methods:

```bash
algokit project run build
```

Extend your deployment script (or create a new one) to add initial liquidity and execute a swap. The following client-side code continues from the `deploy_pool.py` bootstrap script above.

First, the admin must opt into the LP token (a zero-amount self-transfer), then provide initial liquidity by sending both tokens to the pool in an atomic group with the `add_initial_liquidity` call:

```python
# After bootstrap completes...

# The admin needs to opt into the LP token to receive LP shares
algorand.send.asset_transfer(
    algokit_utils.AssetTransferParams(
        sender=admin.address,
        receiver=admin.address,
        asset_id=lp_token_id,
        amount=0,  # opt-in
    )
)

# Add initial liquidity: 10,000 Token A + 10,000 Token B
# Asset transfers are passed as method args --- the SDK composes the group automatically
lp_result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="add_initial_liquidity",
        args=[
            algokit_utils.AssetTransferParams(
                sender=admin.address,
                receiver=app_client.app_address,
                asset_id=token_a,
                amount=10_000_000_000,  # 10,000 with 6 decimals
            ),
            algokit_utils.AssetTransferParams(
                sender=admin.address,
                receiver=app_client.app_address,
                asset_id=token_b,
                amount=10_000_000_000,
            ),
        ],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),  # Cover inner txn
    )
)
print(f"LP tokens received: {lp_result.abi_return}")
```

With liquidity in the pool, we can execute a swap. The user sends 100 Token A and receives Token B, with `min_output` providing slippage protection:

```python
# Now execute a swap: send 100 Token A, receive Token B
# The asset transfer is a method argument, just like deposit_tokens in Chapter 3
swap_result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="swap",
        args=[
            algokit_utils.AssetTransferParams(
                sender=admin.address,
                receiver=app_client.app_address,
                asset_id=token_a,
                amount=100_000_000,  # 100 tokens
            ),
            90_000_000,  # min_output: expect at least 90 Token B
        ],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
    )
)
print(f"Swap output: {swap_result.abi_return} base units of Token B")

# Verify reserves changed
app_info = algorand.client.algod.application_info(app_client.app_id)
print("Swap complete! Check global state to verify reserves.")
```

When you run this, you should see LP tokens minted from the initial deposit and a swap output of approximately 98--99 Token B (slightly less than 100 due to the 0.3\% fee plus the price impact of the trade against the pool). If the swap output is significantly lower than expected, check that your reserves are large enough --- a 100-token swap against a 10,000-token pool has minimal price impact, but a 100-token swap against a 100-token pool would move the price dramatically.

If you want to see the pool's state evolve over multiple swaps, add a loop that executes several swaps and prints the reserves after each one. You will see `reserve_a` increasing and `reserve_b` decreasing (or vice versa depending on direction), and the product `reserve_a * reserve_b` increasing with each swap due to fee accumulation.


## Adding Liquidity to an Existing Pool

After the initial deposit, subsequent liquidity providers must deposit in the current reserve ratio. If the pool is 70\% USDC and 30\% ALGO, new deposits must match that ratio (or the depositor loses value to existing LPs through the minimum-ratio calculation).

LP tokens minted for subsequent deposits use the minimum of both deposit ratios, multiplied by the outstanding LP supply:

$$LP_{new} = \min\left(\frac{\Delta x}{x}, \frac{\Delta y}{y}\right) \times LP_{total}$$

Taking the minimum means any tokens deposited beyond the current ratio are effectively donated to the pool. This incentivizes depositors to match the exact ratio and prevents price manipulation via unbalanced deposits. (See [Algorand Python transactions guide](https://dev.algorand.co/algokit/languages/python/lg-transactions/) for typed gtxn parameter handling.)

Add this method to the `ConstantProductPool` class in `smart_contracts/constant_product_pool/contract.py`:

```python
    @arc4.abimethod
    def add_liquidity(
        self,
        a_txn: gtxn.AssetTransferTransaction,
        b_txn: gtxn.AssetTransferTransaction,
    ) -> UInt64:
        """Add liquidity to an existing pool. Returns LP tokens minted."""
        self._update_twap()

        assert self.lp_total_supply.value > UInt64(0), "Use add_initial_liquidity"

        assert a_txn.asset_receiver == Global.current_application_address
        assert b_txn.asset_receiver == Global.current_application_address
        assert a_txn.xfer_asset == Asset(self.asset_a.value)
        assert b_txn.xfer_asset == Asset(self.asset_b.value)

        amount_a = a_txn.asset_amount
        amount_b = b_txn.asset_amount
        total_lp = self.lp_total_supply.value
        reserve_a = self.reserve_a.value
        reserve_b = self.reserve_b.value

        # LP from each side: (deposit / reserve) * total_lp
        # Cross-multiply to avoid division precision loss:
        # lp_from_a = (amount_a * total_lp) / reserve_a
        a_high, a_low = op.mulw(amount_a, total_lp)
        q_hi, lp_from_a, r_hi, r_lo = op.divmodw(a_high, a_low, UInt64(0), reserve_a)

        b_high, b_low = op.mulw(amount_b, total_lp)
        q_hi, lp_from_b, r_hi, r_lo = op.divmodw(b_high, b_low, UInt64(0), reserve_b)

        # Take the minimum --- penalizes unbalanced deposits
        lp_tokens = lp_from_a if lp_from_a < lp_from_b else lp_from_b
        assert lp_tokens > UInt64(0), "Insufficient deposit"

        # Update state
        self.reserve_a.value = reserve_a + amount_a
        self.reserve_b.value = reserve_b + amount_b
        self.lp_total_supply.value = total_lp + lp_tokens

        # Send LP tokens
        itxn.AssetTransfer(
            xfer_asset=Asset(self.lp_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=lp_tokens,
            fee=UInt64(0),
        ).submit()

        return lp_tokens
```

Wide arithmetic appears again: `amount_a * total_lp` can overflow if both are large. The pattern is identical to what we used in the vesting contract's claim calculation --- `mulw` for the multiplication, `divmodw` for the division.

The floor division on both `lp_from_a` and `lp_from_b` means depositors receive slightly fewer LP tokens than the mathematically precise amount. This is correct: existing LPs should not be diluted by rounding errors in new deposits.

## Understanding Impermanent Loss

Providing liquidity to an AMM is not free money. The 0.3% trading fees are real income, but they come with a hidden cost: *impermanent loss* (IL). Every liquidity provider must understand this before depositing. (See [Why Algorand?](https://dev.algorand.co/getting-started/why-algorand/) for how Algorand's low fees make frequent rebalancing practical.)

Impermanent loss is the difference in value between holding tokens in a pool versus simply holding them in your wallet. It occurs because the AMM rebalances your position as prices move --- you end up with more of whichever token became cheaper and less of whichever became more expensive.

**A concrete example.** Alice deposits 1,000 USDC and 1,000 ALGO (at $1 each) into a pool. Her position is worth $2,000. ALGO doubles to $2. If Alice had just held, she would have 1,000 USDC + 1,000 ALGO = $3,000. But the pool rebalanced: the constant product formula means the pool now holds more USDC and less ALGO. Alice's share is worth approximately $2,828. She lost $172 compared to holding --- that is her impermanent loss (about 5.7%).

The loss is called "impermanent" because it reverses if the price returns to its original ratio. But if Alice withdraws while the price is different, the loss becomes permanent.

The IL formula for a price change of ratio $r$ (where $r = \text{new price} / \text{original price}$):

$$IL = \frac{2\sqrt{r}}{1 + r} - 1$$

| Price Change | IL |
|-------------|-----|
| 1.25x (25% up) | -0.6% |
| 1.5x (50% up) | -2.0% |
| 2x (double) | -5.7% |
| 3x (triple) | -13.4% |
| 5x (5x) | -25.5% |

The same loss applies for equivalent price *decreases* (a 2x drop = same 5.7% IL as a 2x rise).

**When do fees overcome IL?** If the pool generates enough trading fees to exceed the IL, providing liquidity is profitable. This depends on trading volume relative to pool size. A pool with $100K TVL and $50K daily volume generates far more fee income per LP dollar than a pool with $10M TVL and the same volume. High-volume, tight-spread pools (like major stablecoin pairs) tend to overcome IL; low-volume, volatile pairs often do not.

> **Warning:** Impermanent loss is the primary risk for liquidity providers. The 0.3% swap fee partially offsets IL but does not eliminate it. Before providing liquidity in production, calculate the breakeven volume needed for your pool's volatility profile.

This is the fundamental reason Uniswap V3 introduced concentrated liquidity --- by letting LPs focus capital in a narrow price range, they earn higher fees per dollar (improving the fees-vs-IL tradeoff) but amplify the loss if price moves outside their range. No Algorand DEX currently implements a full Uniswap V3-style concentrated liquidity AMM; the ecosystem uses constant product (V2-style) pools and StableSwap variants. The constant product model we built here is what Tinyman and Pact use in production.

## Removing Liquidity

Withdrawal is the inverse of deposit: burn LP tokens, receive proportional shares of both reserves. The calculation is straightforward:

$$amount_A = \frac{LP_{burned}}{LP_{total}} \times reserve_A$$
$$amount_B = \frac{LP_{burned}}{LP_{total}} \times reserve_B$$

The `min_a` and `min_b` parameters provide slippage protection, just like `min_output` in the swap. Between fetching the quote and executing the withdrawal, the reserves may change.

Add this method to the `ConstantProductPool` class in `smart_contracts/constant_product_pool/contract.py`:

```python
    @arc4.abimethod
    def remove_liquidity(
        self,
        lp_txn: gtxn.AssetTransferTransaction,
        min_a: UInt64,
        min_b: UInt64,
    ) -> None:
        """Burn LP tokens to withdraw proportional reserves."""
        self._update_twap()

        assert lp_txn.asset_receiver == Global.current_application_address
        assert lp_txn.xfer_asset == Asset(self.lp_token_id.value)

        lp_amount = lp_txn.asset_amount
        assert lp_amount > UInt64(0)

        total_lp = self.lp_total_supply.value
        reserve_a = self.reserve_a.value
        reserve_b = self.reserve_b.value

        # Proportional withdrawal (floor division: favors pool)
        a_high, a_low = op.mulw(lp_amount, reserve_a)
        q_hi, amount_a, r_hi, r_lo = op.divmodw(a_high, a_low, UInt64(0), total_lp)

        b_high, b_low = op.mulw(lp_amount, reserve_b)
        q_hi, amount_b, r_hi, r_lo = op.divmodw(b_high, b_low, UInt64(0), total_lp)

        # Slippage protection
        assert amount_a >= min_a, "Slippage on asset A"
        assert amount_b >= min_b, "Slippage on asset B"
        assert amount_a > UInt64(0) and amount_b > UInt64(0)

        # Send both assets back
        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_a.value),
            asset_receiver=Txn.sender,
            asset_amount=amount_a,
            fee=UInt64(0),
        ).submit()

        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_b.value),
            asset_receiver=Txn.sender,
            asset_amount=amount_b,
            fee=UInt64(0),
        ).submit()

        # Update reserves and LP supply
        self.reserve_a.value = reserve_a - amount_a
        self.reserve_b.value = reserve_b - amount_b
        self.lp_total_supply.value = total_lp - lp_amount
```

The floor division on both withdrawal amounts ensures the pool never pays out more than its proportional share --- rounding dust stays in the reserves.


## Security Hardening and the Tinyman V1 Lesson

On January 1, 2022, attackers exploited a vulnerability in Tinyman V1's burn (remove liquidity) function, extracting approximately \$3 million. The root cause: the contract failed to verify that two different assets were being returned during liquidity removal. An attacker could construct a transaction that received the same token twice, effectively doubling their withdrawal of one asset while getting nothing of the other.

The key lessons from this exploit shape our contract's security posture.

First, **explicit invariant verification after every operation**. Our swap method calculates the output from the formula and relies on the math being correct. But the Tinyman exploit showed that complex TEAL logic can have subtle control flow bugs that bypass the intended math. Adding an explicit check that $k_{new} \geq k_{old}$ after every state-changing operation catches implementation bugs that the formula alone might miss.

Second, **immutable contracts cannot be patched**. When Tinyman discovered the exploit, they could not update the contracts because they were immutable. They could only recommend that users withdraw their liquidity. This is actually the correct tradeoff --- immutability is what makes the contracts trustless. But it means your code must be correct before deployment. There is no hot-fix option.

Third, **asset verification in every transfer**. Our contract explicitly checks `input_txn.xfer_asset == Asset(self.asset_a.value)` in the swap method. It checks `a_txn.xfer_asset == Asset(self.asset_a.value)` in add_liquidity. It checks `lp_txn.xfer_asset == Asset(self.lp_token_id.value)` in remove_liquidity. Never assume the correct asset was sent --- always verify.

Beyond the Tinyman case study, the Trail of Bits "Not So Smart Contracts" database and the Panda static analysis framework (USENIX Security 2023) identified systematic vulnerability patterns. Panda found that 27.73\% of deployed Algorand applications had at least one vulnerability. The most common categories include missing authorization checks, group size validation gaps, inner transaction fee drains, and --- for Logic Signatures --- missing close-to and rekey-to checks (the #1 finding, though not applicable to stateful contracts like ours).

Our contract addresses the categories that apply to stateful contracts: the contract is immutable (update/delete rejected), all inner transaction fees are zero (preventing fee drain), every incoming transfer is verified for asset ID and receiver, and all privileged methods check caller authorization.

Regarding reentrancy: classical reentrancy attacks are impossible on Algorand. The AVM has no fallback functions or callbacks triggered by token transfers. When your contract sends tokens via an inner transaction, no user code executes on the receiving side. The contract maintains full, uninterrupted control flow. This eliminates the entire class of *reentrancy* exploits that have caused hundreds of millions of dollars in losses on other blockchains. (See [Ethereum to Algorand](https://dev.algorand.co/getting-started/ethereum-to-algorand/) for a detailed security model comparison.)

Regarding MEV (Miner/Maximum Extractable Value): Algorand's block proposers are selected randomly each round via VRF. No one knows who the proposer will be in advance, making targeted collusion difficult. Transaction ordering follows first-come-first-served by default, not fee-based priority. Sandwich attacks --- where an attacker inserts transactions before and after a victim's swap --- are significantly harder than on Ethereum, but not impossible. A block proposer has some discretion over transaction ordering within their proposed block, and the mempool, while not publicly accessible like Ethereum's, is visible to relay nodes. Slippage protection via `min_output` remains the primary defense, and should always be set to a meaningful value --- never zero in production.


## Client-Side Quote Calculation

Never submit an on-chain transaction just to get a price quote. The swap output can be calculated client-side using the same constant-product formula, reading reserves from [global state](https://dev.algorand.co/concepts/smart-contracts/storage/global/) (which is a free API call --- no transaction, no fee). This is how frontends display real-time quotes and price impact warnings. Pattern 12 in the Common Patterns chapter provides the complete client-side `get_swap_quote` helper function with price impact calculation and slippage defaults.

## The TWAP Price Oracle

Our AMM stores its reserves in global state, which any other contract can read. This makes the pool a natural price oracle --- but one that must be used carefully.

### Why Spot Prices Are Dangerous

A lending protocol that needs to know the ALGO/USDC price could read our pool's reserves and compute a spot price: `reserve_b / reserve_a`. But spot prices are trivially manipulable. Consider a pool with reserves of 10,000 USDC and 10,000 ALGO (spot price: 1.0). An attacker with 100,000 USDC swaps into the pool, temporarily pushing the price to approximately 0.01 ALGO/USDC. If a liquidation contract checks the spot price at this moment, it would incorrectly conclude that ALGO is nearly worthless and liquidate healthy positions. The attacker then swaps back, restoring the price. This entire attack fits in a single atomic group.

Production price oracles solve this with a **Time-Weighted Average Price (TWAP)** --- a price that reflects the average over many blocks, not just the current instant. An attacker who manipulates the spot price for one block (2.85 seconds) barely affects a 1-hour TWAP: their manipulation contributes only $2.85 / 3600 \approx 0.08\%$ of the average.

> *Before reading on: if a single-block manipulation costs the attacker nothing and distorts the price completely, what property would an oracle need to make manipulation expensive?*

### Cumulative Price Tracking

A TWAP oracle tracks the cumulative sum of prices over time. The *cumulative price* at any moment is:

$$\text{cumulative\_price}_t = \text{cumulative\_price}_{t-1} + \text{spot\_price} \times \Delta t$$

The TWAP between two timestamps $t_1$ and $t_2$ is:

$$\text{TWAP} = \frac{\text{cumulative\_price}_{t_2} - \text{cumulative\_price}_{t_1}}{t_2 - t_1}$$

> *Quick check: if the cumulative price at t=100 is 500,000 and at t=200 is 1,200,000, what is the TWAP over that interval?*

In production AMMs (Uniswap V2, Tinyman V2), the cumulative price accumulators live inside the pool contract itself and update on every swap, mint, and burn. This is why we added the three TWAP state variables to `__init__` and the `_update_twap()` call at the top of every state-changing method. The price oracle is available to any external consumer --- lending protocols, liquidation engines, farming contracts --- without any of those consumers needing to maintain their own accumulator.

The `_update_twap` call happens *before* reserves change. This is the same design as Uniswap V2: the accumulated price is the price that *held* since the last update, not the price created by the current transaction.

### BigUInt: When UInt64 Is Not Enough

We used `BigUInt` briefly in `add_initial_liquidity` for the square root calculation. Now we need it for a different reason: the TWAP cumulative values grow without bound and will eventually exceed `UInt64`. `BigUInt` is an arbitrary-precision integer type (up to 512 bits) that works with standard Python operators (`+`, `-`, `*`, `//`) rather than the `mulw`/`divmodw` pair. `BigUInt` arithmetic compiles to the AVM's `b+`, `b*`, `b/` opcodes, which cost roughly 10--20 opcodes each (compared to 1 for `UInt64` operations). `BigUInt` values are stored in global state as byte-slice slots, not uint slots, so they count toward your `global_bytes` schema allocation. Use `BigUInt` when your values can exceed $2^{64}$; stick with `UInt64` and wide arithmetic when they cannot.

The cumulative price grows without bound. With a spot price of 1,000,000 (scaled by $10^9$) and 1 year of accumulation:

$$1{,}000{,}000{,}000 \times 31{,}536{,}000 = 3.15 \times 10^{16}$$

This fits in `UInt64`. But at higher prices or over longer periods --- or with a higher precision scale factor --- the cumulative value can exceed $2^{64}$. Uniswap V2 accumulates prices encoded as `UQ112.112` fixed-point values (224 bits) in `uint256` accumulators, intentionally allowing overflow --- the TWAP is computed via modular subtraction, which handles wrapping correctly.

On Algorand, `BigUInt` supports up to 512 bits --- more than enough for any practical TWAP accumulation. The tradeoff is that `BigUInt` arithmetic costs roughly 10x more opcodes than `UInt64`. For a single TWAP update per transaction (two multiplications, one addition), this is approximately 30 extra opcodes --- negligible within a 700-opcode budget. Compare this with the EVM, where Solidity's `uint256` arithmetic handles intermediate products natively and Uniswap V2 uses `uint224` as a deliberate overflow boundary. On the AVM, `UInt64` would overflow within days at moderate prices, so `BigUInt` is not optional --- it is a required design choice. The AVM's constraints force you to think about overflow earlier in the design process, which is arguably a safety benefit.

### The TWAP Update Subroutine

Add this method to the `ConstantProductPool` class. It reads the pool's own reserves (no cross-contract read needed --- they are local state) and accumulates the price:

```python
    @subroutine
    def _update_twap(self) -> None:
        last = self.twap_last_update.value
        now = Global.latest_timestamp
        if last == UInt64(0) or now <= last:
            return

        delta_t = now - last
        res_a = self.reserve_a.value
        res_b = self.reserve_b.value

        if res_a == UInt64(0) or res_b == UInt64(0):
            self.twap_last_update.value = now
            return

        # price_a = reserve_b * TWAP_PRECISION / reserve_a
        # price_b = reserve_a * TWAP_PRECISION / reserve_b
        # Accumulate: cumulative += price * delta_t
        price_a = (
            BigUInt(res_b) * BigUInt(TWAP_PRECISION)
            // BigUInt(res_a)
        )
        price_b = (
            BigUInt(res_a) * BigUInt(TWAP_PRECISION)
            // BigUInt(res_b)
        )

        self.cumulative_price_a.value += (
            price_a * BigUInt(delta_t)
        )
        self.cumulative_price_b.value += (
            price_b * BigUInt(delta_t)
        )
        self.twap_last_update.value = now
```

The method is already called at the top of `swap`, `add_liquidity`, and `remove_liquidity`. For `add_initial_liquidity`, we initialize `twap_last_update` instead (there are no pre-existing reserves to accumulate).

### Reading the TWAP

A read-only method returns the average price over a caller-specified window. The caller provides the cumulative price snapshot from their last interaction (stored client-side or in a separate contract's state):

```python
    @arc4.abimethod(readonly=True)
    def get_twap_price(
        self,
        old_cumulative_a: arc4.UInt512,
        old_timestamp: UInt64,
    ) -> UInt64:
        """Returns TWAP of asset A in terms of B (how many B per one A)."""
        # Accumulate any pending price data up to the current block.
        # The inline accumulation computes the up-to-date cumulative value
        # into a local variable without writing to state.  Because the method
        # is read-only, it can be called via simulate with no fees or on-chain
        # side effects.
        now = Global.latest_timestamp
        last = self.twap_last_update.value
        current = self.cumulative_price_a.value
        if last > UInt64(0) and now > last:
            res_a = self.reserve_a.value
            res_b = self.reserve_b.value
            if res_a > UInt64(0) and res_b > UInt64(0):
                delta_t = now - last
                price_a = (
                    BigUInt(res_b) * BigUInt(TWAP_PRECISION)
                    // BigUInt(res_a)
                )
                current += price_a * BigUInt(delta_t)

        old = old_cumulative_a.as_biguint()
        assert current > old, "No price data"
        elapsed = now - old_timestamp
        assert elapsed > UInt64(0), "Zero elapsed"

        diff = current - old
        twap = diff // BigUInt(elapsed)
        assert twap < BigUInt(2**64), "TWAP overflow"
        return op.btoi(twap.bytes)
```

> **Note:** The `readonly=True` flag means this method can be called via `simulate` without submitting a transaction --- no fees, no state changes. Frontends use this to display real-time price data. The inline accumulation at the top of `get_twap_price` ensures the cumulative value is current even if the pool has not been interacted with recently --- the same approach Uniswap V2 takes in its `currentCumulativePrices` helper. Because the method is read-only, the state writes from this accumulation do not persist.

The method returns a `UInt64`, which means the TWAP result must fit in 64 bits. This is a deliberate design choice --- `UInt64` is easier for callers to work with than a variable-length `BigUInt` --- but it requires a bounds check.

> **Warning:** The `op.btoi` call accepts a byte array of 0--8 bytes and interprets it as a big-endian unsigned integer. A `BigUInt` that exceeds $2^{64} - 1$ would produce more than 8 bytes, causing `btoi` to fail at runtime. The `assert twap < BigUInt(2**64)` guard ensures the TWAP result fits in 64-bit range before the conversion. With `TWAP_PRECISION = 10^9` and typical asset prices, this bound is safe for years of accumulation. If you use a higher precision scale factor or expect extreme price ratios, return a `BigUInt` instead of converting to `UInt64`.

### Manipulation Resistance

A 1-hour TWAP window requires an attacker to sustain the manipulated price for the full hour to meaningfully distort the average. Sustaining the manipulation means keeping a large amount of capital locked in the pool for that duration --- capital that is exposed to arbitrageurs who would trade against the distortion for profit. The cost of manipulation scales linearly with the TWAP window length and the pool's liquidity depth. For pools with meaningful TVL and a 1-hour+ window, TWAP manipulation is economically irrational.

**Quantifying the cost.** Suppose a pool has \$1M in total value locked (500K USDC + equivalent ALGO). To move the spot price by 10\%, an attacker needs to add approximately \$52,600 in one-sided liquidity (from the constant product formula). To sustain this for 1 hour, that capital is locked and exposed to ~\$5,260 in arbitrage losses. The TWAP distortion from this 1-hour manipulation is only $10\% \times (2.85 / 3600) \approx 0.008\%$ per block of manipulation --- negligible. The attacker would need to sustain the manipulation for the entire window at a cost far exceeding any plausible profit.

### Reading Pool Prices From Other Contracts

External contracts consume the TWAP by reading the pool's cumulative price state via `op.AppGlobal.get_ex_bytes` (since `BigUInt` values are stored as byte slices, not uint64). This is an illustrative example showing a separate lending contract, not part of the AMM project code:

```python
# In a separate lending contract:
@arc4.abimethod
def get_price_from_amm(
    self, amm_app: Application
) -> UInt64:
    """Read AMM spot price from reserves."""
    reserve_a, a_ok = op.AppGlobal.get_ex_uint64(
        amm_app, Bytes(b"reserve_a")
    )
    reserve_b, b_ok = op.AppGlobal.get_ex_uint64(
        amm_app, Bytes(b"reserve_b")
    )
    assert a_ok and b_ok, "AMM not found"

    # Spot price of B in terms of A (scaled by 10^6)
    high, low = op.mulw(reserve_b, UInt64(1_000_000))
    q_hi, price, r_hi, r_lo = op.divmodw(
        high, low, UInt64(0), reserve_a
    )
    return price
```

> **Warning:** The spot price example above is shown for educational purposes. In production, always use the TWAP. External contracts can read the cumulative price accumulators from the pool's global state, store periodic snapshots, and compute the TWAP over their desired window.

Multi-hop price derivation (reading prices across chained pools, e.g., ALGO/USDC via ALGO/TOKEN and TOKEN/USDC) follows the same pattern --- read reserves from each pool in the chain and multiply the ratios. (See [Opcodes Overview](https://dev.algorand.co/concepts/smart-contracts/opcodes-overview/) for the cross-app state reading opcodes.)


## Testing the AMM

> **Note:** The tests below are structural outlines showing *what* to test and *how* to assert. The helper functions (`deploy_pool`, `transfer_usdc`, `transfer_algo`, `get_reserve_a`, `get_reserve_b`, etc.) are project-specific wrappers around the [AlgoKit Utils](https://dev.algorand.co/algokit/utils/python/testing/) calls shown earlier in this chapter --- implement them using the deployment and interaction patterns demonstrated above. The patterns here --- lifecycle tests, failure-path tests, invariant tests --- are the ones you should implement for any production contract.

The following test outlines go in `tests/test_amm.py` (not part of the contract code):

```python
class TestConstantProductPool:
    def test_bootstrap_creates_lp_token(self, algorand):
        pool = deploy_pool(algorand, admin)
        lp_id = call_method(pool, "bootstrap", [fund, usdc, algo])
        assert lp_id.abi_return > 0

    def test_initial_liquidity_sets_price(self, algorand):
        lp_tokens = call_method(pool, "add_initial_liquidity",
            [transfer_usdc(1000), transfer_algo(4)])
        assert lp_tokens.abi_return > 0

    def test_swap_respects_constant_product(self, algorand):
        old_k = reserve_a * reserve_b
        call_method(pool, "swap", [transfer_usdc(100), 0])
        new_k = get_reserve_a(pool) * get_reserve_b(pool)
        assert new_k >= old_k

    def test_swap_rejects_excessive_slippage(self, algorand):
        with pytest.raises(Exception, match="Slippage exceeded"):
            call_method(pool, "swap", [transfer_usdc(100), 999999999])

    def test_remove_liquidity_proportional(self, algorand):
        # Add liquidity, then remove half
        call_method(pool, "remove_liquidity", [burn_lp(half), 0, 0])
        # Verify reserves decreased proportionally

    def test_immutability(self, algorand):
        with pytest.raises(Exception):
            pool.update()
        with pytest.raises(Exception):
            pool.delete()

    def test_fee_accumulation(self, algorand):
        # Execute many swaps, verify k increases
        initial_k = reserve_a * reserve_b
        for _ in range(10):
            call_method(pool, "swap", [transfer_usdc(100), 0])
        final_k = get_reserve_a(pool) * get_reserve_b(pool)
        assert final_k > initial_k
```

## Moving to TestNet

Once your contract works on LocalNet, the next step is TestNet --- Algorand's public test network where you can interact with other contracts, test with real network conditions (block times, transaction propagation), and share your deployment with others for testing.

To deploy on TestNet, you need a funded TestNet account. Get free TestNet Algo from the faucet at https://lora.algokit.io/testnet/fund or by running `algokit dispenser login` and `algokit dispenser fund`.

Switch your `AlgorandClient` to TestNet. This is a client-side configuration change:

```python
# Instead of default_localnet():
algorand = AlgorandClient.testnet()
# Or connect to a specific algod endpoint:
algorand = AlgorandClient.from_clients(
    algod=AlgodClient("", "https://testnet-api.4160.nodely.dev"),
)
```

The deployment and interaction scripts are identical to LocalNet --- only the client connection changes. Deploy, bootstrap, and run through the full workflow. Verify every operation by checking the contract's global state and your account balances on a TestNet block explorer like https://testnet.explorer.perawallet.app/. (See [App Deployment](https://dev.algorand.co/algokit/utils/python/app-deploy/) for idempotent deployment strategies.)

Before deploying to MainNet, your TestNet testing checklist should include: bootstrap with real ASAs (not just test tokens), add liquidity from multiple accounts, execute swaps in both directions with varying sizes, remove liquidity and verify proportional withdrawal, test edge cases (very small swaps, swaps that would exceed reserves, swaps with zero min_output), and verify immutability by attempting update and delete.


## Summary

In this chapter you learned to:

- Derive and implement the constant product formula ($x \times y = k$) for automated market making
- Bootstrap a pool contract that creates its own LP token and opts into trading pair assets
- Implement safe swap logic with fee deduction, slippage protection, and explicit invariant verification
- Calculate LP token minting amounts using the geometric mean for initial liquidity and proportional ratios for subsequent deposits
- Implement proportional liquidity withdrawal with dual slippage protection
- Apply the Tinyman V1 lesson: defense-in-depth invariant checks that catch exploits even when individual validations fail
- Build a TWAP price oracle using `BigUInt` cumulative price tracking for manipulation-resistant price feeds
- Build client-side quote calculations using free global state reads

This chapter applied the foundational concepts from the vesting contract to a significantly more complex DeFi application. Some concepts were reused directly (inner transactions, group transactions, security checks), while others were introduced fresh.

| Feature | New Concepts |
|---------|-------------|
| Constant product formula | AMM theory, fee mechanics, invariant $x \times y = k$ |
| Bootstrapping | Multi-inner-transaction sequences, canonical asset ordering, LP token creation |
| Initial liquidity | Geometric mean, BigUInt square root, minimum liquidity lock |
| Swaps | Slippage protection, swap direction detection, explicit invariant verification |
| Add liquidity | Proportional minting with min() ratio, unbalanced deposit penalty |
| Remove liquidity | Proportional withdrawal, dual slippage protection |
| TWAP oracle | Cumulative price tracking, BigUInt, manipulation resistance |
| Security | Tinyman V1 case study, defense-in-depth invariant checks, MEV on Algorand |
| Client integration | Off-chain quote calculation, free state reads |

In the next chapter, we extend this AMM with a yield farming contract --- a staking system where LPs lock their LP tokens to earn reward tokens, introducing the reward accumulator pattern and smart contract composition.

## Exercises

1. **(Apply)** Write a client-side function that calculates the price impact of a swap as a percentage, given the input amount and current reserves.

2. **(Analyze)** The AMM uses tracked reserves (explicit `self.reserve_a.value`) rather than reading the contract's actual on-chain balance. What happens if someone accidentally sends tokens directly to the contract address without calling any method? Are those tokens recoverable? Is this a bug or a deliberate design choice?

3. **(Create)** Design an extension that adds a 0.05% protocol fee on top of the existing 0.3% LP fee. The protocol fee should accumulate in a separate global state variable and be withdrawable by the admin. Sketch the code changes needed in the `swap` method and write a new `withdraw_protocol_fees` method.

    *Hint:* Add `self.protocol_fees_a = GlobalState(UInt64(0))` and `self.protocol_fees_b = GlobalState(UInt64(0))` to `__init__`. In the `swap` method, after calculating `output_amount`, compute `protocol_fee = output_amount * UInt64(5) // UInt64(10000)` (0.05%), subtract it from the output sent to the user, and add it to the appropriate protocol fee accumulator. The `withdraw_protocol_fees` method should be admin-only, send both accumulated fee balances via inner transactions, and reset the accumulators to zero.

4. **(Analyze)** The TWAP oracle stops accumulating if no transactions interact with the pool. If there is a 24-hour gap with no swaps or liquidity operations, the TWAP becomes stale. Design a public `poke_twap` method that allows anyone (a keeper bot) to trigger a TWAP update without performing a swap. What should the method do, and what incentive does a keeper have to call it?

## Further Reading

- [Algorand Python Operations](https://dev.algorand.co/algokit/languages/python/lg-ops/) --- mulw, divmodw, bsqrt, and other op module functions
- [Uniswap V2 TWAP Oracle](https://docs.uniswap.org/contracts/v2/guides/smart-contract-integration/building-an-oracle) --- the reference implementation for cumulative price tracking
- [ARC-28: Event Logging](https://dev.algorand.co/arc-standards/arc-0028/) --- standardized event emission for off-chain indexing
- [App Deployment](https://dev.algorand.co/algokit/utils/python/app-deploy/) --- idempotent deployment strategies
- [Transaction Composer](https://dev.algorand.co/algokit/utils/python/transaction-composer/) --- building atomic groups with AlgoKit Utils
- [Testing](https://dev.algorand.co/algokit/utils/python/testing/) --- pytest patterns for Algorand contracts

\newpage

# Yield Farming --- Extending the AMM with Staking Rewards

Your AMM works. Liquidity providers deposit tokens, traders swap against the pool, fees accumulate in the reserves, and LP tokens track each provider's share. But nothing stops an LP from providing liquidity for five minutes, collecting a fractional share of fees, and withdrawing. There is no incentive to commit capital for the long term, and no mechanism to reward the LPs who provide the stable, deep liquidity that makes a pool actually useful for traders.

This is the problem *yield farming* solves. In a yield farming system, LPs lock their LP tokens in a separate staking contract for a fixed duration --- 30 days, 90 days, a year --- and earn additional reward tokens on top of the trading fees they already collect from the pool. Longer lock-ups earn proportionally higher rewards, creating a direct incentive for the sticky liquidity that healthy markets depend on.

We are going to build a staking contract that composes with the AMM from the previous chapter. Users deposit LP tokens from that pool, lock them for a chosen duration, and earn a reward token distributed continuously over time. The contract reads the AMM's global state to verify that the LP tokens are genuine and demonstrates the reward-per-token accumulator pattern used by virtually every DeFi staking system.

Two core concepts drive this chapter. First, the *reward accumulator pattern* --- a mathematical technique (popularized by Synthetix) that distributes rewards fairly across any number of stakers without iterating over them. Second, *smart contract composition* --- reading another contract's state to make trust decisions, a fundamental DeFi building block that connects isolated contracts into composable protocols.

By the end of this chapter you will have a working staking contract, deployed on LocalNet alongside your AMM, with lock-up multipliers, continuous reward distribution, and cross-contract verification of LP token provenance.

> **Note:** This chapter assumes you have a working AMM from the previous chapter. The farming contract reads the AMM's global state and accepts its LP tokens. If you skipped the AMM chapter, go back and build it first --- the farming contract will not compile or deploy without it.


## The Junior Version --- A Simple Staking Contract

Before tackling the real accumulator math, let us build the simplest possible staking contract. This version has a fixed 30-day lock period, a single reward pool, and straightforward proportional math. It will work for a handful of stakers, and building it first makes the problems that motivate the accumulator pattern concrete rather than abstract.

The contract accepts LP tokens (passed as an initialization parameter), locks them for 30 days, and distributes rewards proportionally based on each staker's share of the total staked LP tokens.

Create a new project for this chapter:

```bash
algokit init -t python --name lp-farming
cd lp-farming/projects/lp-farming
algokit project bootstrap all
mv smart_contracts/hello_world smart_contracts/lp_farming
```

Delete the template-generated `deploy_config.py` inside the renamed directory. Your contract code goes in `smart_contracts/lp_farming/contract.py`.

Here is the junior version. Replace the contents of `contract.py`:

```python
from algopy import (
    Account, ARC4Contract, Asset, Bytes, Global,
    GlobalState, Txn, UInt64, arc4, gtxn, itxn, op,
    BoxMap,
)

SECONDS_PER_DAY = 86400
LOCK_DURATION = 30 * SECONDS_PER_DAY  # 30 days


class StakeInfo(arc4.Struct):
    lp_amount: arc4.UInt64
    stake_time: arc4.UInt64
    reward_claimed: arc4.UInt64


class SimpleFarm(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.lp_token_id = GlobalState(UInt64(0))
        self.reward_token_id = GlobalState(UInt64(0))
        self.total_staked = GlobalState(UInt64(0))
        self.total_rewards = GlobalState(UInt64(0))
        self.reward_end_time = GlobalState(UInt64(0))
        self.is_initialized = GlobalState(UInt64(0))
        self.stakes = BoxMap(
            arc4.Address, StakeInfo, key_prefix=b"s_"
        )

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.admin.value = Txn.sender.bytes

    @arc4.baremethod(
        allow_actions=["UpdateApplication", "DeleteApplication"]
    )
    def reject_lifecycle(self) -> None:
        assert False, "Contract is immutable"

    @arc4.abimethod
    def initialize(
        self,
        lp_token: Asset,
        reward_token: Asset,
    ) -> None:
        assert Txn.sender == Account(self.admin.value)
        assert self.is_initialized.value == UInt64(0)

        self.lp_token_id.value = lp_token.id
        self.reward_token_id.value = reward_token.id

        # Opt into both tokens
        itxn.AssetTransfer(
            xfer_asset=lp_token,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()
        itxn.AssetTransfer(
            xfer_asset=reward_token,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()

        self.is_initialized.value = UInt64(1)

    @arc4.abimethod
    def deposit_rewards(
        self,
        reward_txn: gtxn.AssetTransferTransaction,
        duration_days: UInt64,
    ) -> None:
        assert Txn.sender == Account(self.admin.value)
        assert reward_txn.xfer_asset == Asset(
            self.reward_token_id.value
        )
        assert reward_txn.asset_receiver == (
            Global.current_application_address
        )

        self.total_rewards.value = reward_txn.asset_amount
        self.reward_end_time.value = (
            Global.latest_timestamp
            + duration_days * UInt64(SECONDS_PER_DAY)
        )

    @arc4.abimethod
    def stake(
        self,
        lp_txn: gtxn.AssetTransferTransaction,
    ) -> None:
        assert lp_txn.xfer_asset == Asset(
            self.lp_token_id.value
        )
        assert lp_txn.asset_receiver == (
            Global.current_application_address
        )
        assert lp_txn.sender == Txn.sender
        assert lp_txn.asset_amount > UInt64(0)

        key = arc4.Address(Txn.sender)
        assert key not in self.stakes, "Already staked"
        self.stakes[key] = StakeInfo(
            lp_amount=arc4.UInt64(lp_txn.asset_amount),
            stake_time=arc4.UInt64(Global.latest_timestamp),
            reward_claimed=arc4.UInt64(0),
        )
        self.total_staked.value += lp_txn.asset_amount

    @arc4.abimethod
    def claim(self) -> UInt64:
        stake = self.stakes[arc4.Address(Txn.sender)].copy()
        lp_amount = stake.lp_amount.native
        stake_time = stake.stake_time.native
        claimed = stake.reward_claimed.native
        assert lp_amount > UInt64(0), "No stake"
        assert stake_time < self.reward_end_time.value, (
            "Reward period ended"
        )

        now = Global.latest_timestamp
        total_duration = (
            self.reward_end_time.value - stake_time
        )
        elapsed = now - stake_time
        if elapsed > total_duration:
            elapsed = total_duration

        # reward = (lp / total_lp) * (elapsed / duration)
        #        * total_rewards
        high1, low1 = op.mulw(
            lp_amount, self.total_rewards.value
        )
        q1_hi, numerator, r1_hi, r1_lo = op.divmodw(
            high1, low1, UInt64(0),
            self.total_staked.value,
        )
        high2, low2 = op.mulw(numerator, elapsed)
        q2_hi, reward, r2_hi, r2_lo = op.divmodw(
            high2, low2, UInt64(0), total_duration
        )

        payout: UInt64 = reward - claimed
        assert payout > UInt64(0), "Nothing to claim"

        stake.reward_claimed = arc4.UInt64(reward)
        self.stakes[arc4.Address(Txn.sender)] = stake.copy()

        itxn.AssetTransfer(
            xfer_asset=Asset(self.reward_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=payout,
            fee=UInt64(0),
        ).submit()

        return payout

    @arc4.abimethod
    def unstake(self) -> None:
        stake = self.stakes[arc4.Address(Txn.sender)].copy()
        lp_amount = stake.lp_amount.native
        stake_time = stake.stake_time.native
        assert lp_amount > UInt64(0), "No stake"
        assert Global.latest_timestamp >= (
            stake_time + UInt64(LOCK_DURATION)
        ), "Lock period not expired"

        # Return LP tokens
        itxn.AssetTransfer(
            xfer_asset=Asset(self.lp_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=lp_amount,
            fee=UInt64(0),
        ).submit()

        self.total_staked.value -= lp_amount
        del self.stakes[arc4.Address(Txn.sender)]
```

This contract works. You can deploy it, stake LP tokens, claim rewards after some time passes, and unstake after 30 days. But it has three problems that become serious at scale:

**Problem 1: The reward math does not scale.** The formula `(lp / total_lp) * (elapsed / duration) * total_rewards` looks correct for one staker, but it breaks when stakers enter and exit at different times. If Alice stakes 100 LP at time 0 and Bob stakes 200 LP at time 50, Alice's share retroactively drops from 100% to 33% --- but the formula does not account for the period when Alice was the only staker and deserved 100% of those rewards. Alice gets systematically underpaid, and Bob gets overpaid for time he was not staked.

**Problem 2: No incentive for longer locks.** Everyone locks for the same 30 days. A user who commits for a year gets no additional reward over someone who commits for a month. This means the contract cannot attract the long-term, stable liquidity that pools need most.

**Problem 3: No LP token verification.** The contract accepts any token with the right ASA ID, but it does not verify that the LP token actually came from a specific AMM pool. Someone could create a fake LP token with the same ID structure and stake it. We need cross-contract composition to verify the LP token's origin.

*Before reading the solution to Problem 1, think about this: if Alice stakes 100 LP at time 0 and Bob stakes 200 LP at time 50, and the reward rate is 10 tokens per second, how should rewards be distributed after 200 seconds? Alice was the sole staker for the first 50 seconds --- does her reward reflect that? Try to work out a fair distribution, then read on to see how the accumulator pattern solves it.*


## The Reward Accumulator Pattern

The junior version's core flaw is that it tries to compute each user's reward share from scratch every time. This requires knowing the exact staking history of every participant --- who was staked, how much, and for how long. With two stakers, the math is manageable. With ten thousand, it is impossible within the AVM's opcode budget.

### Why Per-User Tracking Fails

Consider the naive approach: maintain a list of all stakers and iterate through them whenever someone stakes, unstakes, or claims. For each staker, recalculate their share based on the new total. This is O(n) per operation, and with the AVM's 700-opcode-per-call budget (even pooled to ~11,200 across a 16-transaction group), you run out of gas with a few dozen stakers.

Even if you could iterate, the math is wrong. When Bob stakes at time 50, the per-second reward rate changes for everyone. Alice was earning 10 tokens/second alone; now she earns 3.33 tokens/second. But her earnings from time 0 to 50 should not change. You need to "settle" every staker's accrued rewards before changing the rate --- which brings us back to the O(n) iteration problem.

### The Snapshot-and-Diff Insight

The solution is a global accumulator that answers the question: "How many reward tokens has one unit of LP earned since the beginning of time?" This number is called `reward_per_token`. Each user stores a snapshot of `reward_per_token` at the time they last interacted with the contract. Their pending reward is simply:

$$\text{reward} = \text{lp\_amount} \times (\text{reward\_per\_token}_{\text{now}} - \text{reward\_per\_token}_{\text{snapshot}})$$

This is O(1) per operation. No iteration over stakers. No historical tracking. The global value accumulates continuously, and each user's snapshot captures "where they got on."

### The Update Formula

The accumulator updates on every state-changing call (stake, unstake, claim). The update adds the rewards that have accrued since the last update:

$$\text{reward\_per\_token} \mathrel{+}= \frac{\text{reward\_rate} \times \Delta t \times \text{PRECISION}}{\text{total\_staked}}$$

Where:
- `reward_rate` is tokens per second distributed to the entire pool
- `delta_t` is seconds since the last update (`min(now, reward_end) - last_update`)
- `PRECISION` is a scaling factor (we use $10^9$) to preserve fractional precision in integer math
- `total_staked` is the current total LP tokens in the contract

The `min(now, reward_end)` clamping ensures rewards stop accumulating after the reward period ends.

> **Warning:** The zero-balance guard is critical. If `total_staked` is zero, the update must be skipped entirely --- dividing by zero panics the AVM, and accumulating rewards when nobody is staked would create tokens from nowhere. Always check `total_staked > 0` before updating the accumulator.

### Wide Arithmetic

The multiplication `reward_rate * delta_t * PRECISION` can overflow `UInt64` (max $\approx 1.8 \times 10^{19}$). With `PRECISION = 10^9`, a `reward_rate` of 1,000,000 tokens/second, and a `delta_t` of 86,400 seconds (one day):

$$1{,}000{,}000 \times 86{,}400 \times 10^9 = 8.64 \times 10^{19}$$

This exceeds `UInt64`'s maximum. We must use `op.mulw` for the 128-bit intermediate product and `op.divmodw` for the 128-bit division:

```python
# reward_rate * delta_t fits in UInt64 for realistic
# parameters, so we compute it directly:
rate_time = reward_rate * delta_t
# Multiply by PRECISION (128-bit via mulw),
# then divide by total_staked:
high, low = op.mulw(rate_time, UInt64(PRECISION))
q_hi, increment, r_hi, r_lo = op.divmodw(
    high, low, UInt64(0), total_staked
)
```

> **Note:** The `rate_time = reward_rate * delta_t` product must fit in `UInt64`. With a maximum reward rate of $10^6$ tokens/second and a maximum delta of one year ($\approx 3.15 \times 10^7$ seconds), the product is $\approx 3.15 \times 10^{13}$ --- safely within the $1.84 \times 10^{19}$ `UInt64` limit. If your reward parameters are extreme (rate exceeding $\approx 5 \times 10^{11}$ tokens/second), use an additional `mulw` stage or switch to `BigUInt`.

### Visual Trace: Two Stakers

Let us trace through a concrete scenario with `reward_rate = 10` tokens/second and `PRECISION = 10^9`.

**Time 0: Alice stakes 100 LP**

| Event | `reward_per_token` | Alice snapshot | Bob snapshot | Alice pending | Bob pending |
|-------|-------------------|----------------|-------------|---------------|------------|
| Alice stakes 100 | 0 | 0 | --- | 0 | --- |

`total_staked = 100`. No time has passed, so no accumulator update.

**Time 100: Bob stakes 200 LP**

Before Bob's stake, update the accumulator:

$$increment = \frac{10 \times 100 \times 10^9}{100} = 10{,}000{,}000{,}000$$

$$\text{reward\_per\_token} = 0 + 10{,}000{,}000{,}000 = 10{,}000{,}000{,}000$$

| Event | `reward_per_token` | Alice snapshot | Bob snapshot | Alice pending | Bob pending |
|-------|-------------------|----------------|-------------|---------------|------------|
| Bob stakes 200 | 10,000,000,000 | 0 | 10,000,000,000 | 1,000 | 0 |

Alice's pending reward: $100 \times (10{,}000{,}000{,}000 - 0) / 10^9 = 1{,}000$ tokens. This is correct: she was the sole staker for 100 seconds at 10 tokens/second.

Bob's snapshot is set to the current accumulator value. His pending reward is zero --- he just arrived.

`total_staked = 300`.

**Time 200: Both claim**

Update the accumulator:

$$increment = \frac{10 \times 100 \times 10^9}{300} = 3{,}333{,}333{,}333$$

$$\text{reward\_per\_token} = 10{,}000{,}000{,}000 + 3{,}333{,}333{,}333 = 13{,}333{,}333{,}333$$

| Event | `reward_per_token` | Alice snapshot | Bob snapshot | Alice pending | Bob pending |
|-------|-------------------|----------------|-------------|---------------|------------|
| Claims at t=200 | 13,333,333,333 | 0 | 10,000,000,000 | 1,333 | 666 |

Alice: $100 \times (13{,}333{,}333{,}333 - 0) / 10^9 = 1{,}333$ tokens.
Bob: $200 \times (13{,}333{,}333{,}333 - 10{,}000{,}000{,}000) / 10^9 = 666$ tokens.

Total distributed: $1{,}333 + 666 = 1{,}999$ tokens. Total available: $10 \times 200 = 2{,}000$ tokens. The 1-token difference is rounding dust from integer division --- always in the contract's favor.

> **Warning:** The total rewards distributed must never exceed `reward_rate * elapsed_time`. Rounding in `op.divmodw` floors toward zero, ensuring the contract always retains dust. If you ever observe total distributions exceeding the reward pool, you have a bug. This is the single most important property to verify in your tests.

**Self-check:** If Charlie stakes 300 LP at time 200 and everyone claims at time 300, how much does each person receive for the t=200 to t=300 interval? (Answer: Alice gets 166, Bob gets 333, Charlie gets 500 --- proportional to their 100:200:300 stakes out of the new total of 600.)

### Overflow Analysis

With `PRECISION = 10^9`, the `reward_per_token_stored` value grows by `(reward_rate * delta_t * 10^9) / total_staked` per update. In the worst case --- a reward rate of $10^6$ tokens/second, a delta of 86,400 seconds (one day), and a total staked of 1 (a single user with 1 LP token) --- the increment is:

$$\frac{10^6 \times 86{,}400 \times 10^9}{1} = 8.64 \times 10^{19}$$

This exceeds `UInt64`'s maximum of $\approx 1.84 \times 10^{19}$. However, the numerator before division is computed in 128-bit via `mulw`, and the division via `divmodw` produces a 64-bit quotient. The quotient itself overflows only if `total_staked = 1` and the numerator is enormous --- which means a single user with 1 LP token is staked while $10^6$ reward tokens per second are distributed. In practice, total staked values are orders of magnitude larger, keeping the increment well within 64-bit range.

If your reward parameters are extreme, add a check: `assert increment < UInt64(2**63)` after the `divmodw`. This panic-on-overflow approach is safer than silently wrapping, which would corrupt the accumulator and allow some stakers to claim more than their share.

*Recall the wide arithmetic pattern from the AMM's swap calculation in the previous chapter. What was the purpose of `mulw` and `divmodw` there? The same pattern --- 128-bit intermediate product divided back to 64 bits --- reappears throughout this chapter.*


## Duration Multipliers

A flat reward rate treats a 30-day lock the same as a 365-day lock. To incentivize longer commitments, we assign a *multiplier* that scales the user's effective stake. The actual LP tokens deposited do not change --- the multiplier inflates the user's weight in the reward calculation.

We use a linear scale from 1x (30 days) to 4x (365 days):

$$\text{multiplier} = \text{SCALE} + \frac{(\text{duration} - \text{MIN\_LOCK}) \times 3 \times \text{SCALE}}{\text{MAX\_LOCK} - \text{MIN\_LOCK}}$$

Where `SCALE = 1000` (giving us 0.1% precision), `MIN_LOCK = 30 days`, and `MAX_LOCK = 365 days`. A 30-day lock gets multiplier 1000 (1.0x). A 365-day lock gets 4000 (4.0x). A 197-day lock (halfway) gets 2500 (2.5x).

The user's *effective balance* --- the value used in the accumulator --- is:

$$\text{effective} = \frac{\text{lp\_amount} \times \text{multiplier}}{\text{SCALE}}$$

**Worked example.** Alice locks 100 LP for 365 days (multiplier = 4000). Bob locks 200 LP for 30 days (multiplier = 1000).

- Alice's effective balance: $100 \times 4000 / 1000 = 400$
- Bob's effective balance: $200 \times 1000 / 1000 = 200$
- Total effective: 600
- Alice's share: $400 / 600 = 66.7\%$
- Bob's share: $200 / 600 = 33.3\%$

Despite depositing half as many LP tokens, Alice earns twice Bob's reward rate because her 4x multiplier more than compensates. This is the intended incentive: long-term LPs earn disproportionately more.

The `total_staked` global variable (renamed to `total_effective` in the production contract) now tracks the sum of effective balances, not raw LP amounts. When Alice stakes, we add 400. When she unstakes, we subtract 400. The accumulator formula is unchanged --- it already uses the total in the denominator. This is the beauty of the accumulator pattern: adding multipliers requires zero changes to the core distribution math. You only change how each user's weight is calculated.

> **Note:** Why not use a quadratic or exponential multiplier instead of linear? The choice affects game theory. A linear multiplier means the marginal benefit of each additional lock day is constant. An exponential multiplier would disproportionately reward the longest locks, potentially concentrating rewards among a few whales who can afford to lock for a year. A square-root multiplier (explored in Exercise 3) has diminishing returns --- the first extra month of locking is worth more than the last. Linear is the simplest to reason about and audit, which matters for a contract holding user funds.

```python
SCALE = 1000
MIN_LOCK = 30 * SECONDS_PER_DAY
MAX_LOCK = 365 * SECONDS_PER_DAY


@subroutine
def calculate_multiplier(duration: UInt64) -> UInt64:
    """Linear multiplier: 1x at 30 days, 4x at 365 days."""
    assert duration >= UInt64(MIN_LOCK), "Below minimum lock"
    assert duration <= UInt64(MAX_LOCK), "Exceeds maximum lock"
    lock_range = UInt64(MAX_LOCK - MIN_LOCK)
    excess = duration - UInt64(MIN_LOCK)
    # multiplier = 1000 + excess * 3000 / range
    high, low = op.mulw(excess, UInt64(3 * SCALE))
    q_hi, bonus, r_hi, r_lo = op.divmodw(
        high, low, UInt64(0), lock_range
    )
    return UInt64(SCALE) + bonus
```

Note the wide arithmetic: `excess * 3000` can approach $335 \times 86400 \times 3000 \approx 8.7 \times 10^{10}$, which fits in `UInt64`. The `mulw` is defensive --- it would only matter if someone passed durations in smaller units. Defensive arithmetic costs a few extra opcodes and prevents entire classes of bugs.


## Smart Contract Composition

*The farming contract needs to verify that LP tokens are genuine. Using only what you know about Algorand so far, how would you accomplish this? Think about what data the AMM stores on-chain and how another contract might access it.*

Until now, every contract we have built has operated in isolation. The vesting contract managed its own tokens. The AMM managed its own pool. But the farming contract needs to verify that the LP tokens it receives actually come from our AMM pool --- not from some random token with the same ASA ID.

Algorand makes cross-contract reads straightforward. Any contract can read another contract's global state using `op.AppGlobal.get_ex_uint64` (for integer values) or `op.AppGlobal.get_ex_bytes` (for byte values). The target application must be included in the transaction's foreign apps array.

```python
# Read the AMM's lp_token_id to verify our LP token
lp_id, exists = op.AppGlobal.get_ex_uint64(
    amm_app, Bytes(b"lp_token_id")
)
assert exists, "AMM app has no lp_token_id"
assert lp_id == self.lp_token_id.value, "LP token mismatch"
```

The `get_ex_uint64` opcode returns a tuple of `(value, exists)`. Always check `exists` --- if the key does not exist in the target app's global state, `value` is zero, and silently using zero as a valid value is a common bug.

> **Warning:** The foreign apps array has a maximum of 8 entries per transaction (shared across the group since AVM v9). Each cross-contract read consumes one slot. If your transaction already references several apps, you may not have room for the AMM reference. Plan your foreign reference budget carefully when designing multi-contract interactions.

**Design tradeoff: read-on-init vs. read-on-every-call.** We could verify the LP token once during initialization and store the result, or verify it on every stake call. Reading once is cheaper (fewer opcodes per stake) but trusts that the stored value remains correct forever. Reading every time costs ~5 extra opcodes per call but guarantees correctness even if someone deploys a new farming contract pointing at a different AMM. For this contract, we read the AMM's state during initialization --- the LP token ID cannot change after the AMM is bootstrapped, so a one-time read is safe and saves opcode budget on every subsequent stake.

### How Foreign Apps Work at the Protocol Level

When you include an application in the foreign apps array, you are telling the AVM: "This transaction may need to read state from this application." The AVM loads the target app's global state into a read-only cache at the start of execution. The `get_ex_uint64` opcode then reads from this cache --- it does *not* make a live query to the blockchain during execution.

This has two implications. First, the read is cheap --- just a few opcodes to look up a key in the cached state. There is no network round-trip or additional I/O cost beyond the initial load. Second, the state you read is the state as of the beginning of your transaction's execution. If another transaction in the same atomic group modifies the target app's state before your transaction executes, you see the *pre-modification* state. This is usually what you want for verification purposes (you are checking that a value exists and matches), but it matters if you are trying to read state that was just written by a preceding group transaction.

Since AVM v9, foreign references are shared across all transactions in an atomic group. This means the AMM app only needs to appear in *one* transaction's foreign apps array, and all transactions in the group can read its state. In practice, include it in the transaction that actually performs the read for clarity.

**Common error.** If you forget to include the AMM app in the foreign apps array, the `get_ex_uint64` call will fail at runtime with an "unavailable App" error. The fix is client-side --- add the AMM app ID to the `app_references` parameter when building the transaction:

```python
app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="initialize",
        args=[lp_token, reward_token, amm_app_id],
        app_references=[amm_app_id],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(
            4000
        ),
    )
)
```


## Project Setup and Full Contract

Now we build the production staking contract, incorporating the accumulator pattern, duration multipliers, and cross-contract verification. This replaces the junior version entirely.

The contract file is `smart_contracts/lp_farming/contract.py`. Compile with:

```bash
algokit project run build
```

### State Design

The per-user stake data is stored in boxes keyed by the staker's address. Each position is an `arc4.Struct`:

```python
class StakePosition(arc4.Struct):
    effective_balance: arc4.UInt64   # LP * multiplier / SCALE
    lp_amount: arc4.UInt64          # Raw LP tokens deposited
    reward_per_token_paid: arc4.UInt64  # Snapshot at last interaction
    accrued_rewards: arc4.UInt64    # Unclaimed rewards
    unlock_time: arc4.UInt64        # Timestamp when unstake allowed
```

Five `arc4.UInt64` fields = 40 bytes. Box key: `b"s_"` prefix (2 bytes) + 32-byte address = 34 bytes. Box MBR: $2{,}500 + 400 \times (34 + 40) = 32{,}100$ microAlgos per staker.

The global state schema uses 9 `UInt64` slots and 1 `Bytes` slot (the admin address). Since the default schema allows up to 64 of each, we have plenty of room.

> **Note:** `Global.latest_timestamp` is the timestamp of the block containing the current transaction, not the wall-clock time. It is accurate to within about 25 seconds and is set by the block proposer. For a staking contract with lock periods measured in days, this precision is more than adequate. Do not use timestamps for sub-minute precision requirements.

### Consolidated Imports and Constants

```python
from algopy import (
    ARC4Contract, Account, Application, Asset,
    Bytes, Global, GlobalState, Txn,
    UInt64, arc4, gtxn, itxn, op, subroutine,
    BoxMap,
)

PRECISION = 10**9
SCALE = 1000
SECONDS_PER_DAY = 86400
MIN_LOCK = 30 * SECONDS_PER_DAY
MAX_LOCK = 365 * SECONDS_PER_DAY
```


## Initialization and Reward Deposit

The contract class declaration and initialization method. The `initialize` method performs the cross-contract read to verify the LP token, then opts into both tokens.

```python
class StakePosition(arc4.Struct):
    effective_balance: arc4.UInt64
    lp_amount: arc4.UInt64
    reward_per_token_paid: arc4.UInt64
    accrued_rewards: arc4.UInt64
    unlock_time: arc4.UInt64


class LPFarm(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.lp_token_id = GlobalState(UInt64(0))
        self.reward_token_id = GlobalState(UInt64(0))
        self.amm_app_id = GlobalState(UInt64(0))
        self.total_effective = GlobalState(UInt64(0))
        self.reward_rate = GlobalState(UInt64(0))
        self.reward_end_time = GlobalState(UInt64(0))
        self.last_update_time = GlobalState(UInt64(0))
        self.reward_per_token_stored = GlobalState(UInt64(0))
        self.is_initialized = GlobalState(UInt64(0))
        self.stakes = BoxMap(
            arc4.Address, StakePosition, key_prefix=b"s_"
        )

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.admin.value = Txn.sender.bytes

    @arc4.baremethod(
        allow_actions=[
            "UpdateApplication",
            "DeleteApplication",
        ]
    )
    def reject_lifecycle(self) -> None:
        assert False, "Contract is immutable"

    @arc4.abimethod
    def initialize(
        self,
        lp_token: Asset,
        reward_token: Asset,
        amm_app: Application,
    ) -> None:
        assert Txn.sender == Account(self.admin.value)
        assert self.is_initialized.value == UInt64(0)

        # Cross-contract read: verify LP token belongs to AMM
        lp_id, exists = op.AppGlobal.get_ex_uint64(
            amm_app, Bytes(b"lp_token_id")
        )
        assert exists, "AMM has no lp_token_id"
        assert lp_id == lp_token.id, "LP token mismatch"

        self.lp_token_id.value = lp_token.id
        self.reward_token_id.value = reward_token.id
        self.amm_app_id.value = amm_app.id

        # Opt into both tokens
        itxn.AssetTransfer(
            xfer_asset=lp_token,
            asset_receiver=(
                Global.current_application_address
            ),
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()
        itxn.AssetTransfer(
            xfer_asset=reward_token,
            asset_receiver=(
                Global.current_application_address
            ),
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()

        self.is_initialized.value = UInt64(1)
```

The `initialize` method reads `lp_token_id` from the AMM's global state. If the AMM has not been bootstrapped (the key does not exist), the assertion fails. If someone passes a different AMM app that happens to have a `lp_token_id` key with a different value, the token mismatch check catches it. This two-layer verification ensures the farming contract is bound to a specific, legitimate AMM pool.

The `deposit_rewards` method funds the reward pool and sets the distribution rate:

```python
    @arc4.abimethod
    def deposit_rewards(
        self,
        reward_txn: gtxn.AssetTransferTransaction,
        duration_seconds: UInt64,
    ) -> None:
        assert Txn.sender == Account(self.admin.value)
        assert reward_txn.xfer_asset == Asset(
            self.reward_token_id.value
        )
        assert reward_txn.asset_receiver == (
            Global.current_application_address
        )
        assert duration_seconds > UInt64(0)

        # Settle any accrued rewards before changing rate
        self._update_reward()

        amount = reward_txn.asset_amount
        assert amount > UInt64(0), "Zero reward deposit"

        self.reward_rate.value = amount // duration_seconds
        self.last_update_time.value = (
            Global.latest_timestamp
        )
        self.reward_end_time.value = (
            Global.latest_timestamp + duration_seconds
        )
```

The reward rate is tokens per second. Integer division means some dust is lost --- depositing 1,000,000 tokens over 86,401 seconds yields a rate of 11 tokens/second, distributing $11 \times 86{,}401 = 950{,}411$ tokens total. The remaining 49,589 tokens stay in the contract. This is standard behavior; production systems often add a "sweep" function for the admin to recover undistributed dust after the reward period ends.

> **Warning:** The `deposit_rewards` method replaces an existing reward period rather than extending it. The `_update_reward()` call at the top settles accrued rewards at the old rate before the new rate takes effect --- without it, stakers would lose rewards earned under the previous period. However, any undistributed tokens from the old period (between `last_update_time` and the old `reward_end_time`) are effectively abandoned. A production contract should either prevent overlapping deposits or calculate a new rate that accounts for both the remaining and newly deposited rewards. For simplicity, our contract assumes a single reward period.


## Staking LP Tokens

The `stake` method is the heart of the contract. It updates the global accumulator, calculates the user's multiplier, creates or updates their position box, and records their accumulator snapshot.

```python
    @arc4.abimethod
    def stake(
        self,
        lp_txn: gtxn.AssetTransferTransaction,
        lock_days: UInt64,
    ) -> None:
        assert self.is_initialized.value == UInt64(1)
        assert lp_txn.xfer_asset == Asset(
            self.lp_token_id.value
        )
        assert lp_txn.asset_receiver == (
            Global.current_application_address
        )
        assert lp_txn.sender == Txn.sender
        assert lp_txn.asset_amount > UInt64(0)

        # 1. Update the global accumulator
        self._update_reward()

        # 2. Calculate lock duration and multiplier
        duration = lock_days * UInt64(SECONDS_PER_DAY)
        multiplier = _calculate_multiplier(duration)
        lp_amount = lp_txn.asset_amount
        high, low = op.mulw(lp_amount, multiplier)
        q_hi, effective, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), UInt64(SCALE)
        )

        # 3. Store the stake position
        key = arc4.Address(Txn.sender)
        assert key not in self.stakes, "Already staked"
        self.stakes[key] = StakePosition(
            effective_balance=arc4.UInt64(effective),
            lp_amount=arc4.UInt64(lp_amount),
            reward_per_token_paid=arc4.UInt64(
                self.reward_per_token_stored.value
            ),
            accrued_rewards=arc4.UInt64(0),
            unlock_time=arc4.UInt64(
                Global.latest_timestamp + duration
            ),
        )

        # 4. Update total effective stake
        self.total_effective.value += effective
```

The assertion `key not in self.stakes` prevents double-staking. A user who wants to add more LP must first unstake (after their lock expires) and re-stake with a new duration. This simplification keeps the position struct fixed-size and avoids the complexity of merging positions with different multipliers and unlock times. Production contracts sometimes support multiple positions per user via a position ID (using a `BoxMap(arc4.UInt64, StakePosition)` keyed by a sequential counter), but that adds significant complexity --- each position needs independent accumulator snapshots, and claiming requires iterating over all positions.

An alternative design is to allow "topping up" an existing stake by adding more LP tokens at the same multiplier and unlock time. This requires settling accrued rewards first (to avoid retroactively applying the new balance to past periods), then adding the new effective balance to both the position and the global total. The code changes are modest, but the UX complexity of explaining when top-ups are allowed (same lock duration only? extend the lock?) and the additional test surface area make it a poor tradeoff for a first implementation.

### The `_update_reward` Subroutine

This is the accumulator update, called at the top of every state-changing method:

```python
    @subroutine
    def _update_reward(self) -> None:
        if self.total_effective.value == UInt64(0):
            self.last_update_time.value = (
                Global.latest_timestamp
            )
            return

        now = Global.latest_timestamp
        end = self.reward_end_time.value
        effective_now = now if now < end else end
        last = self.last_update_time.value
        if effective_now <= last:
            return

        delta_t = effective_now - last
        rate = self.reward_rate.value
        total = self.total_effective.value

        # rate * delta_t fits in UInt64 for any realistic
        # parameters (max ~10^6 * 31536000 = 3.15e13)
        rate_time = rate * delta_t
        # Multiply by PRECISION via mulw (128-bit result),
        # then divide by total via divmodw
        high, low = op.mulw(
            rate_time, UInt64(PRECISION)
        )
        q_hi, increment, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), total
        )
        assert q_hi == UInt64(0), "Accumulator overflow"

        self.reward_per_token_stored.value += increment
        self.last_update_time.value = effective_now
```

The two-stage wide arithmetic is straightforward. First, `rate * delta_t` is computed as a plain `UInt64` product. For any realistic parameters --- a reward rate up to $10^6$ tokens/second and a maximum delta of one year (31,536,000 seconds) --- this product is at most $3.15 \times 10^{13}$, well within `UInt64` range. The `mulw` then multiplies this intermediate result by `PRECISION` ($10^9$) to produce a 128-bit value, and `divmodw` divides by `total` to yield the 64-bit increment. If your reward parameters are extreme enough that `rate * delta_t` itself could exceed $2^{64}$, you would need an additional `mulw` stage or `BigUInt` arithmetic --- but this would require a reward rate exceeding $5 \times 10^{14}$ tokens/second, far beyond any realistic deployment.

### The `_calculate_multiplier` Subroutine

Extracted as a module-level subroutine so it can be called from both `stake` and `extend_lock`:

```python
@subroutine
def _calculate_multiplier(duration: UInt64) -> UInt64:
    """1x at 30 days, 4x at 365 days, linear."""
    assert duration >= UInt64(MIN_LOCK), "Below minimum lock"
    assert duration <= UInt64(MAX_LOCK), "Above maximum lock"
    lock_range = UInt64(MAX_LOCK - MIN_LOCK)
    excess = duration - UInt64(MIN_LOCK)
    high, low = op.mulw(excess, UInt64(3 * SCALE))
    q_hi, bonus, r_hi, r_lo = op.divmodw(
        high, low, UInt64(0), lock_range
    )
    return UInt64(SCALE) + bonus
```

### Deployment Script

This script deploys the farming contract alongside the AMM from the previous chapter. Save it as `deploy_farm.py` in your project root:

```python
import os
from pathlib import Path
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
admin = algorand.account.localnet_dispenser()

# --- Step 1: Create test tokens ---
def create_asa(name, unit):
    result = algorand.send.asset_create(
        algokit_utils.AssetCreateParams(
            sender=admin.address,
            total=10**13, decimals=6,
            asset_name=name, unit_name=unit,
            note=os.urandom(8),
        )
    )
    return result.asset_id

token_a = create_asa("TokenA", "TKA")
token_b = create_asa("TokenB", "TKB")
reward_token = create_asa("RewardToken", "RWD")
if token_a > token_b:
    token_a, token_b = token_b, token_a
print(f"Token A: {token_a}, Token B: {token_b}")
print(f"Reward Token: {reward_token}")

# --- Step 2: Deploy and bootstrap AMM ---
amm_spec = Path(
    "smart_contracts/artifacts/"
    "constant_product_pool/"
    "ConstantProductPool.arc56.json"
).read_text()
amm_factory = algorand.client.get_app_factory(
    app_spec=amm_spec,
    default_sender=admin.address,
)
amm_client, _ = amm_factory.send.bare.create()
print(f"AMM App ID: {amm_client.app_id}")

# Bootstrap: the seed payment is the first ABI argument.
# The SDK places it as the preceding transaction in the
# group automatically.
result = amm_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="bootstrap",
        args=[
            algokit_utils.PaymentParams(
                sender=admin.address,
                receiver=amm_client.app_address,
                amount=(
                    algokit_utils.AlgoAmount.from_micro_algo(
                        500_000
                    )
                ),
            ),
            token_a,
            token_b,
        ],
        static_fee=(
            algokit_utils.AlgoAmount.from_micro_algo(
                5000
            )
        ),
    )
)
lp_token_id = result.abi_return
print(f"LP Token ID: {lp_token_id}")

# --- Step 3: Deploy the farming contract ---
farm_spec = Path(
    "smart_contracts/artifacts/"
    "lp_farming/LPFarm.arc56.json"
).read_text()
farm_factory = algorand.client.get_app_factory(
    app_spec=farm_spec,
    default_sender=admin.address,
)
farm_client, _ = farm_factory.send.create(
    algokit_utils.AppFactoryCreateMethodCallParams(
        method="create",
    )
)
print(f"Farm App ID: {farm_client.app_id}")

# Fund the farm contract
algorand.send.payment(
    algokit_utils.PaymentParams(
        sender=admin.address,
        receiver=farm_client.app_address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(
            400_000
        ),
        note=os.urandom(8),
    )
)

# Initialize with cross-contract verification
farm_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="initialize",
        args=[
            lp_token_id, reward_token,
            amm_client.app_id,
        ],
        app_references=[amm_client.app_id],
        asset_references=[lp_token_id, reward_token],
        static_fee=(
            algokit_utils.AlgoAmount.from_micro_algo(4000)
        ),
    )
)
print("Farm initialized!")
```

Compile and run:

```bash
algokit project run build
python deploy_farm.py
```

You should see the AMM and farm app IDs, the LP token ID, and "Farm initialized!" confirming that the cross-contract LP token verification succeeded.


## Claiming and Extending Locks

### Claiming Rewards

The `claim` method settles the user's accrued rewards and sends them as an inner transaction:

```python
    @arc4.abimethod
    def claim(self) -> UInt64:
        self._update_reward()

        key = arc4.Address(Txn.sender)
        pos = self.stakes[key].copy()
        effective = pos.effective_balance.native
        assert effective > UInt64(0), "No stake"

        # Calculate pending rewards
        current_rpt = self.reward_per_token_stored.value
        paid_rpt = pos.reward_per_token_paid.native
        diff = current_rpt - paid_rpt

        high, low = op.mulw(effective, diff)
        q_hi, new_rewards, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), UInt64(PRECISION)
        )
        total_pending: UInt64 = (
            pos.accrued_rewards.native + new_rewards
        )

        assert total_pending > UInt64(0), "Nothing to claim"

        # Update position: snapshot current accumulator,
        # zero out accrued
        pos.reward_per_token_paid = arc4.UInt64(current_rpt)
        pos.accrued_rewards = arc4.UInt64(0)
        self.stakes[key] = pos.copy()

        # Send rewards
        itxn.AssetTransfer(
            xfer_asset=Asset(self.reward_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=total_pending,
            fee=UInt64(0),
        ).submit()

        return total_pending
```

The `accrued_rewards` field captures rewards that were calculated during a previous interaction (like `_update_reward` during another user's stake) but not yet claimed. This ensures no rewards are lost between interactions.

### Extending a Lock

Imagine Alice staked for 30 days at a 1x multiplier. Two weeks in, she decides she is comfortable locking for the full year. Rather than waiting for her lock to expire, unstaking, and re-staking at a higher multiplier --- losing her position in the accumulator and paying box MBR twice --- she can extend her lock in place, upgrading her multiplier immediately.

This is more complex than it appears --- the effective balance changes, which affects the global total and the accumulator. The update must be performed in a precise order to avoid over- or under-counting rewards.

```python
    @arc4.abimethod
    def extend_lock(
        self, new_lock_days: UInt64
    ) -> None:
        # Step 1: Update global accumulator
        self._update_reward()

        key = arc4.Address(Txn.sender)
        pos = self.stakes[key].copy()
        old_effective = pos.effective_balance.native
        lp_amount = pos.lp_amount.native
        assert old_effective > UInt64(0), "No stake"

        # Step 2: Settle accrued rewards
        current_rpt = self.reward_per_token_stored.value
        paid_rpt = pos.reward_per_token_paid.native
        diff = current_rpt - paid_rpt
        high, low = op.mulw(old_effective, diff)
        q_hi, new_rewards, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), UInt64(PRECISION)
        )
        accrued = pos.accrued_rewards.native + new_rewards

        # Step 3: Calculate new multiplier and effective
        new_duration = new_lock_days * UInt64(SECONDS_PER_DAY)
        new_unlock = (
            Global.latest_timestamp + new_duration
        )
        assert new_unlock > pos.unlock_time.native, (
            "New lock must extend beyond current"
        )
        new_multiplier = _calculate_multiplier(new_duration)
        h, l = op.mulw(lp_amount, new_multiplier)
        q_hi, new_effective, r_hi, r_lo = op.divmodw(
            h, l, UInt64(0), UInt64(SCALE)
        )

        # Step 4: Update global total effective
        self.total_effective.value -= old_effective
        self.total_effective.value += new_effective

        # Step 5: Snapshot accumulator at current value
        pos.reward_per_token_paid = arc4.UInt64(
            current_rpt
        )

        # Step 6: Store settled rewards
        pos.accrued_rewards = arc4.UInt64(accrued)

        # Step 7: Update effective balance and unlock time
        pos.effective_balance = arc4.UInt64(new_effective)
        pos.unlock_time = arc4.UInt64(new_unlock)

        # Step 8: Write back
        self.stakes[key] = pos.copy()
```

The 8-step sequence is critical. Steps 1--2 settle all rewards at the old effective balance. Steps 3--4 change the effective balance and global total. Step 5 resets the snapshot so future rewards accrue at the new effective rate. Steps 6--8 persist everything atomically. The critical ordering constraint is between steps 1 and 4: `_update_reward()` must execute before `total_effective` changes, because the accumulator update uses `total_effective` as its denominator. If you changed the total *before* updating the accumulator, the increment would be calculated against the wrong total, distributing too many or too few rewards for the period before the effective balance changed.

*Without looking at the code above, list the steps that `extend_lock` must perform and explain why the ordering matters. Then compare your list to the 8-step sequence. The ordering constraint is the same invariant from the accumulator section: update before mutate.*


## Unstaking

The `unstake` method verifies the lock has expired, settles final rewards, returns LP tokens, deletes the position box, and refunds the box MBR.

```python
    @arc4.abimethod
    def unstake(self) -> None:
        self._update_reward()

        key = arc4.Address(Txn.sender)
        pos = self.stakes[key].copy()
        effective = pos.effective_balance.native
        lp_amount = pos.lp_amount.native
        assert effective > UInt64(0), "No stake"
        assert Global.latest_timestamp >= (
            pos.unlock_time.native
        ), "Lock not expired"

        # Settle final rewards
        current_rpt = self.reward_per_token_stored.value
        paid_rpt = pos.reward_per_token_paid.native
        diff = current_rpt - paid_rpt
        high, low = op.mulw(effective, diff)
        q_hi, new_rewards, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), UInt64(PRECISION)
        )
        total_pending: UInt64 = (
            pos.accrued_rewards.native + new_rewards
        )

        # Update global state BEFORE inner transactions
        self.total_effective.value -= effective

        # Return LP tokens
        itxn.AssetTransfer(
            xfer_asset=Asset(self.lp_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=lp_amount,
            fee=UInt64(0),
        ).submit()

        # Send final rewards (if any)
        if total_pending > UInt64(0):
            itxn.AssetTransfer(
                xfer_asset=Asset(
                    self.reward_token_id.value
                ),
                asset_receiver=Txn.sender,
                asset_amount=total_pending,
                fee=UInt64(0),
            ).submit()

        # Delete the position box --- refunds MBR
        del self.stakes[key]

        # Refund box MBR to the user
        itxn.Payment(
            receiver=Txn.sender,
            amount=UInt64(32_100),
            fee=UInt64(0),
        ).submit()
```

The MBR refund is 32,100 microAlgos --- the exact cost of the position box. When the box is deleted, the contract's MBR requirement drops by that amount, freeing the Algo for the refund payment. The contract must have been funded with enough Algo to cover all active boxes' MBR plus a buffer for inner transaction fees. This is the same MBR lifecycle pattern from the vesting contract: fund on creation, refund on cleanup.

> **Warning:** The `del self.stakes[key]` call and the MBR refund payment happen *after* the state update (`total_effective -= effective`). If the box deletion or payment fails (e.g., insufficient contract balance), the entire transaction rolls back atomically --- the state update is reverted too. This is safe on Algorand because of atomic rollback semantics, but it means you must ensure the contract always has enough Algo to cover the refund.

Notice that the accumulator update (`_update_reward()`) happens before computing the user's pending reward and before modifying the user's stake. This ordering is mathematically necessary --- the global `reward_per_token` must reflect the current state of the world before individual positions are calculated against it. This is an algorithmic correctness requirement, not a reentrancy guard (reentrancy is impossible on Algorand --- inner transactions do not trigger callbacks).

The `unstake` method requires a client-side fee that covers the outer transaction plus up to 3 inner transactions (LP return, reward send, MBR refund):

```python
farm_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="unstake",
        args=[],
        static_fee=(
            algokit_utils.AlgoAmount.from_micro_algo(5000)
        ),
    )
)
```


## Consuming the AMM's TWAP Oracle

The AMM from the previous chapter tracks cumulative price accumulators and exposes a `get_twap_price` read-only method. The farming contract does not need to maintain its own oracle --- it can consume the AMM's TWAP for position valuation.

A natural extension of the farming contract is displaying the dollar value of a staked position. A frontend would:

1. **Snapshot**: Read the AMM's raw global state --- `cumulative_price_a` and `twap_last_update` --- via the algod REST API (`GET /v2/applications/{app-id}`). Store both values along with the current wall-clock time. This is a free API read, not a contract call.
2. **Query**: After the desired TWAP window has elapsed (e.g., 1 hour), call `get_twap_price` via `simulate`, passing the stored cumulative price and timestamp as arguments. The method computes the time-weighted average over the window and returns it as a `UInt64`.
3. **Value**: Multiply the TWAP price by the user's staked LP amount to estimate the position's dollar value.

Because `get_twap_price` performs inline accumulation before computing the difference, the returned TWAP is current even if no swap, mint, or burn has occurred since the snapshot. This is a key advantage of placing the oracle in the AMM rather than in each consumer: one well-trafficked pool feeds price data to any number of downstream contracts.

If a farming contract needed to make on-chain decisions based on price (e.g., dynamic reward rates or position liquidation), it could read the AMM's cumulative price state directly via `op.AppGlobal.get_ex_bytes` (since `BigUInt` values are stored as byte slices). It would store its own periodic snapshots and compute the TWAP over its desired window. For our farming contract, position valuation is purely a frontend concern, so no additional on-chain code is needed.


## Testing

Test outlines for the farming contract. These follow the same structural pattern as the AMM tests from the previous chapter --- `deploy_pool` and similar helpers wrap the AlgoKit Utils calls shown in the deployment scripts.

Save the following in `tests/test_farm.py`:

```python
import pytest
from algokit_utils import AlgorandClient


class TestLPFarm:
    """Farming contract test suite."""

    def test_lifecycle_stake_claim_unstake(
        self, algorand
    ):
        """Deploy AMM + Farm, stake LP, claim, unstake."""
        # Deploy AMM, bootstrap, add liquidity
        # Deploy farm, initialize with AMM reference
        # Deposit rewards (1M tokens over 30 days)
        # User stakes LP for 30 days
        # Advance time (LocalNet: submit dummy txns)
        # Claim --- verify reward > 0
        # Advance past lock expiry
        # Unstake --- verify LP returned, box deleted

    def test_accumulator_two_stakers(self, algorand):
        """Alice stakes alone, Bob joins, verify shares."""
        # Alice stakes 100 LP at t=0
        # Advance 100 seconds
        # Bob stakes 200 LP at t=100
        # Advance 100 seconds
        # Alice claims --- should get ~1333 rewards
        # Bob claims --- should get ~666 rewards
        # Total <= reward_rate * elapsed

    def test_multiplier_scaling(self, algorand):
        """30-day lock gets 1x, 365-day gets 4x."""
        # Alice: 100 LP, 365 days (4x effective)
        # Bob: 100 LP, 30 days (1x effective)
        # After equal time, Alice's reward ~ 4x Bob's

    def test_composition_rejects_wrong_amm(
        self, algorand
    ):
        """Initialize fails if LP token doesn't match."""
        # Deploy a second AMM with different tokens
        # Attempt initialize with wrong AMM app
        # Expect failure: "LP token mismatch"

    def test_lock_enforcement(self, algorand):
        """Unstake before lock expires should fail."""
        # Stake for 30 days
        # Immediately attempt unstake
        # Expect failure: "Lock not expired"

    def test_rewards_cap_at_pool(self, algorand):
        """Total distributed never exceeds deposited."""
        # Deposit 1000 reward tokens
        # Stake, advance past reward_end_time
        # Claim --- verify total claimed <= 1000
        # No further rewards accrue after end time

    def test_extend_lock_increases_share(
        self, algorand
    ):
        """Extending lock increases multiplier."""
        # Stake 100 LP for 30 days (1x)
        # Extend to 365 days (4x)
        # Verify effective balance quadrupled
        # Verify rewards accrue at new rate

    def test_double_stake_rejected(self, algorand):
        """Cannot stake twice from same account."""
        # Stake once
        # Attempt second stake
        # Expect failure: "Already staked"
```

### Testing Time-Dependent Logic on LocalNet

LocalNet does not advance timestamps between blocks unless real time passes or you explicitly submit transactions that cause new blocks to be produced. To test time-dependent logic, you have two options: (1) insert `time.sleep(N)` between operations and submit a dummy transaction to produce a block with an updated timestamp, or (2) use the `dev-mode` time offset feature if your LocalNet supports it. Option 1 is simpler but makes tests slow.

For the accumulator test (`test_accumulator_two_stakers`), a 200-second sleep is impractical. The workaround is to use a very high reward rate --- say, $10^6$ reward tokens per second --- with short sleeps (2--3 seconds). This way, even a 2-second gap produces 2 million reward tokens of meaningful accumulation, and you can verify the proportional split within a reasonable test runtime.

```python
# Practical test timing pattern
import time

# Deposit 10^12 rewards over 100 seconds
# -> reward_rate = 10^10 tokens/second
farm_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="deposit_rewards",
        args=[reward_transfer, 100],
        # ...
    )
)

# Alice stakes
farm_client.send.call(...)
time.sleep(3)  # Wait 3 real seconds

# Submit a dummy payment to advance the block timestamp
algorand.send.payment(
    algokit_utils.PaymentParams(
        sender=admin.address,
        receiver=admin.address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(0),
        note=os.urandom(8),
    )
)

# Bob stakes --- the block timestamp is now ~3s later
# Alice earned ~3 * 10^10 tokens as sole staker
```

The `note=os.urandom(8)` on dummy payments is essential --- LocalNet deduplicates identical transactions, so the random note ensures each one is unique.

### What to Verify

The most important property to test is the **reward conservation invariant**: the total rewards claimed by all users must never exceed the total rewards deposited. After every claim in your test, track the running total of claimed rewards and assert it is less than or equal to the deposited amount. If this invariant ever fails, you have a critical bug in the accumulator math.

Second, verify **proportional fairness**: if Alice has 2x the effective balance of Bob and both stake for the same duration, Alice should receive approximately 2x the rewards. The "approximately" accounts for integer rounding --- the difference should be at most a few tokens, not a percentage.

Third, test **edge cases**: staking when the reward period has already ended (no new rewards should accrue), claiming when accrued rewards are zero (should revert), extending a lock to a shorter duration than the current lock (should revert), and unstaking immediately after the lock expires (should succeed and return the correct LP amount).


## Summary

In this chapter you learned to:

- Identify why naive per-user reward tracking fails at scale and implement the Synthetix-style reward-per-token accumulator pattern
- Use `op.mulw` and `op.divmodw` for two-stage wide arithmetic that prevents overflow in reward calculations
- Design duration-based multipliers that incentivize long-term liquidity commitment
- Read another contract's global state via `op.AppGlobal.get_ex_uint64` for cross-contract verification
- Consume the AMM's TWAP oracle for manipulation-resistant position valuation
- Manage the full staking lifecycle: stake, claim, extend, unstake with MBR refund

This chapter extended the AMM from the previous chapter into a two-contract system --- the first example of smart contract composition in this book. The farming contract does not modify the AMM; it reads its state and accepts its LP tokens. This *composability* --- contracts interacting through shared state and token standards without needing to trust each other --- is what makes DeFi protocols interoperable. Any contract that holds LP tokens can integrate with the farm. Any contract that needs a price feed can read the AMM's TWAP oracle. A lending protocol could accept staked LP positions as collateral by reading the farming contract's box state. Each contract is a building block, and the system's value comes from the combinations.

The accumulator pattern you learned here appears in virtually every DeFi staking system: Synthetix's StakingRewards, Curve's gauge system, Sushiswap's MasterChef, and their Algorand equivalents. The specific numbers change (precision factors, multiplier curves, reward schedules), but the core insight --- track a global per-unit accumulator and diff it against per-user snapshots --- is universal.

| Feature | New Concepts |
|---------|-------------|
| Reward distribution | Accumulator pattern, reward_per_token, snapshot-and-diff |
| Wide arithmetic | Two-stage mulw/divmodw for overflow-safe accumulator updates |
| Duration multipliers | Linear scaling, effective balance, SCALE factor |
| Composition | Cross-contract state reads, foreign apps array, get_ex_uint64 |
| Position management | Box lifecycle, MBR refund on cleanup, double-stake prevention |

In the next chapter, we cover common patterns and idioms that apply across all Algorand DeFi contracts --- fee subsidization strategies, MBR lifecycle management, canonical ordering, opcode budget management, and event emission for off-chain indexing.


## Exercises

1. **(Recall)** In the reward accumulator pattern, what happens if you update `total_effective` *before* settling a user's accrued rewards during an `extend_lock` call? Trace through the math with concrete numbers to show the error.

2. **(Apply)** Add an `emergency_withdraw` method that lets users retrieve their LP tokens before the lock expires, but forfeits all unclaimed rewards. The forfeited rewards should remain in the contract for distribution to other stakers. What state updates are needed, and in what order?

3. **(Analyze)** The linear multiplier gives 1x at 30 days and 4x at 365 days. Consider an alternative: a square-root multiplier where $\text{multiplier} = \sqrt{\text{duration} / \text{MIN\_LOCK}} \times \text{SCALE}$. A 30-day lock gets 1x, a 120-day lock gets 2x, a 365-day lock gets ~3.49x. What are the game-theoretic implications? Does this favor short-term or long-term stakers compared to linear?

4. **(Create)** Add an on-chain randomness bonus using `op.Block.blk_seed`. Every time a user claims, the contract reads the block seed from 2 rounds ago and hashes it with the user's address. If the resulting hash (mod 100) is less than 5, the user receives a 10% bonus on their claim. Implement the method and explain why reading the seed from 2 rounds ago (rather than the current round) prevents the user from choosing when to submit their claim based on a known seed.


## Further Reading

- [Synthetix StakingRewards](https://github.com/Synthetixio/synthetix/blob/develop/contracts/StakingRewards.sol) --- the original Solidity implementation of the reward accumulator pattern
- [Curve Finance](https://curve.fi/whitepaper) --- multi-token gauge reward systems with vote-escrow multipliers
- [Algorand Python Storage](https://dev.algorand.co/algokit/languages/python/lg-storage/) --- BoxMap, GlobalState, and BigUInt storage patterns
- [Algorand Python Operations](https://dev.algorand.co/algokit/languages/python/lg-ops/) --- mulw, divmodw, and wide arithmetic reference
- [Cross-App State Reading](https://dev.algorand.co/concepts/smart-contracts/opcodes-overview/) --- get_ex_uint64 and foreign app references


## Before You Continue

Before starting the next chapter, you should be able to:

- [ ] Explain why the naive per-user reward formula fails with concurrent stakers
- [ ] Implement the reward-per-token accumulator with correct wide arithmetic
- [ ] Calculate a user's pending rewards given their snapshot and the current accumulator value
- [ ] Read another contract's global state and handle the case where the key does not exist
- [ ] Explain how the farming contract consumes the AMM's TWAP oracle for position valuation
- [ ] Manage box lifecycle with creation, updates, deletion, and MBR refund

If any of these are unclear, revisit the relevant section before proceeding.

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

\newpage

\part{Cryptography and Zero-Knowledge Proofs}

Part IV pushes the AVM to its limits with advanced cryptography. You will build a privacy-preserving governance voting system using zero-knowledge proofs, explore Algorand's native elliptic curve opcodes and the MiMC hash, and learn about the Falcon-based post-quantum security roadmap.

# Private Governance Voting with Zero-Knowledge Proofs

Your DAO needs to hold a vote, but the community demands ballot secrecy --- no one should be able to see how anyone voted until results are final. On a public blockchain where all state is readable, this seems impossible. Zero-knowledge proofs make it possible.

In this project we build a privacy-preserving governance voting system where voters prove they cast a valid ballot without revealing their choice. Along the way, we explore the AVM's native elliptic curve opcodes, zero-knowledge proof construction and on-chain verification, advanced box storage patterns, and Algorand's Falcon-based post-quantum security architecture.

### Project Setup

Scaffold a new project for this chapter. The template creates a `hello_world/` contract directory which we rename:

```bash
algokit init -t python --name governance-voting
cd governance-voting
algokit project bootstrap all
mv smart_contracts/hello_world smart_contracts/governance_voting
```

Your contract code goes in `smart_contracts/governance_voting/contract.py`. Delete the template-generated `deploy_config.py` in the renamed directory --- it references the old `HelloWorld` contract.

> **Note: Technology stack for this chapter.** This project spans two languages and three components:
>
> 1. **Algorand Python** (PuyaPy) --- the voting smart contract (`contract.py`), compiled with `algokit project run build`
> 2. **Go** (gnark + AlgoPlonk) --- the ZK circuit definition and verifier LogicSig generator, compiled with `go build`. Requires Go 1.21+ and `go get github.com/consensys/gnark`
> 3. **Python client code** --- deployment scripts and test harnesses using AlgoKit Utils
>
> The data flow is: the Go program generates a TEAL verifier LogicSig from the circuit definition. The Python client compiles this TEAL via algod, then uses it in atomic groups alongside the voting contract. You can build and test the voting contract (component 1) independently; the Go components (component 2) are needed only for end-to-end ZK proof verification.

> **Note:** This chapter covers advanced cryptography. You do not need to understand elliptic curve math to build the voting system --- AlgoPlonk handles the heavy lifting. We explain the concepts so you can reason about what the system *proves* and where its security guarantees come from. If the math feels dense, focus on the architecture (phases, atomic groups, state management) and treat the curve operations as black boxes.

## LogicSig Recap: Why They Are the ZK Engine

This project builds on the LogicSig foundation from Chapter 8. If you skipped that chapter, read at least Part 1 (Logic Signatures) before continuing. Here we recap only the aspects relevant to ZK verification.

The critical property for this chapter is the [opcode budget](https://dev.algorand.co/concepts/smart-contracts/costs-constraints/). Each top-level transaction with a LogicSig contributes 20,000 opcodes to a pooled budget (since AVM v10). In a group of 8 LogicSig transactions, that is 160,000 opcodes --- enough to verify a BN254 PLONK proof that costs approximately 145,000 opcodes. Smart contracts, at 700 opcodes per app call, would need over 200 calls for the same verification, making them prohibitively expensive.

The LogicSig and smart contract opcode pools are independent. This means we can use LogicSigs for the cryptographic heavy lifting (proof verification) while preserving the full smart contract budget for application logic (recording votes, managing phases, tallying results). This separation is the architectural foundation of the system we are about to build.

For this project, we use LogicSigs in **contract account mode** --- the LogicSig program hash determines the account address. The verifier LogicSig does not need delegated authority; it simply needs enough opcode budget to run the elliptic curve operations. The security rules from Chapter 8 (close-to, rekey-to, fee caps, group validation) all apply and are enforced in our verifier implementation.

## Part 2: The AVM's Cryptographic Toolkit

### Native Elliptic Curve Opcodes (AVM v10+)

The AVM provides native support for two pairing-friendly elliptic curve families. (See [Cryptographic Tools](https://dev.algorand.co/concepts/smart-contracts/cryptographic-tools/) and the [opcodes reference](https://dev.algorand.co/reference/algorand-teal/opcodes/) for complete specifications.)

**BN254** (also called alt_bn128 or bn256): The curve used by Ethereum's precompiles, Zcash's original ceremony, and most existing Groth16 deployments. Points in G1 are 64 bytes, G2 are 128 bytes. Verification is cheaper on BN254 than BLS12-381.

**BLS12-381**: The curve used by Ethereum 2.0, Zcash Sapling, Algorand's state proofs, and most modern ZK systems. Provides higher security margins than BN254 (~128-bit vs ~100-bit post-Cheon attacks). Points in G1 are 96 bytes, G2 are 192 bytes.

The available opcodes:

| Opcode | Cost (BN254 G1) | Description |
|--------|-----------------|-------------|
| `ec_add` | 125 | Point addition: P + Q |
| `ec_scalar_mul` | 1,810 | Scalar multiplication: sP |
| `ec_multi_scalar_mul` | 3,600 + 90 per 32B of scalar | Multi-scalar: s₁P₁ + s₂P₂ + ... |
| `ec_pairing_check` | 8,000 + 7,400 per 64B of B | Pairing verification: e(A,B) = 1? |
| `ec_subgroup_check` | 20 | Verify point is in prime-order subgroup |
| `ec_map_to` | 630 | Hash-to-curve mapping |
| `mimc` | 10 + 550 per 32B of input | MiMC hash (ZK-friendly, known collisions outside ZK) |

The `ec_pairing_check` opcode is the workhorse for SNARK verification. A Groth16 verification requires checking:

```
e(A, B) · e(-vk_α, vk_β) · e(-∑(pub_i · vk_i), vk_γ) · e(-C, vk_δ) = 1
```

This is a single pairing check with 4 pairs, which `ec_pairing_check` handles natively.

### MiMC: the ZK-Friendly Hash

The AVM includes a native `mimc` opcode --- a hash function designed specifically for efficient evaluation inside ZK circuits. MiMC has **known collisions** for inputs that are multiples of the elliptic curve modulus, so it is NOT a general-purpose hash function. It exists solely for ZK applications where the hash must be efficiently provable in a SNARK/PLONK circuit.

For our governance voting system, MiMC will be used inside the ZK circuit to hash vote commitments. The on-chain verifier uses the native `mimc` opcode to validate the hash, and the ZK prover uses the same MiMC function in its circuit --- ensuring the hash values match without expensive SHA-256 circuit emulation.

> **Client-side MiMC computation.** The AVM provides a native `op.mimc()` opcode, but there is no standard Python library for computing MiMC hashes with the BN254Mp110 configuration. To test the commit-reveal flow, you need a client-side MiMC implementation that matches the AVM's output. Options: (1) use the Go gnark-crypto library's `mimc.NewMiMC()` from a Go test harness, (2) use AlgoPlonk's Go utilities which include compatible MiMC, or (3) compute the commitment on-chain via a `simulate` call and capture the result. Option 3 is the simplest approach: build a helper contract with a single method that takes `choice` and `randomness`, computes `op.mimc(MiMCConfigurations.BN254Mp110, ...)`, and returns the hash. Call it via `simulate` (no fees, no state changes) to get the commitment value for your tests.


## Part 3: Zero-Knowledge Proofs --- From Theory to Algorand

### What Zero-Knowledge Proofs Actually Prove

A zero-knowledge proof lets you convince someone that a statement is true without revealing why it's true. On Algorand, ZK proofs are verified using the AVM's native [cryptographic tools](https://dev.algorand.co/concepts/smart-contracts/cryptographic-tools/) --- elliptic curve opcodes on BN254 and BLS12-381. More precisely, a ZK proof system has three properties:

**Completeness:** If the statement is true and the prover is honest, the verifier will be convinced.

**Soundness:** If the statement is false, no cheating prover can convince the verifier (except with negligible probability).

**Zero-knowledge:** The verifier learns nothing beyond the truth of the statement. The proof itself reveals no information about the witness (the secret knowledge).

For our voting system, the statement is: "I cast a vote that is one of the valid choices (e.g., 0, 1, or 2) and my commitment hash is correctly computed." The witness (secret) is: which choice I actually made and the randomness I used in the commitment. The verifier learns: the vote is valid and the commitment is correct. The verifier does NOT learn: which choice was made.

### The ZK Proof Landscape Relevant to Algorand

**Groth16** --- The most compact proof system (3 group elements, ~192 bytes for BN254). Verification is fast: one pairing check. Requires a **trusted setup per circuit** (toxic waste that must be destroyed). Used by Zcash, Tornado Cash, and most deployed ZK applications. On Algorand, Groth16 verification via pairing checks costs substantially fewer opcodes than PLONK (~30,000-50,000), but requires the per-circuit trusted setup ceremony. PLONK verification costs ~145,000 opcodes on the AVM with BN254 but avoids per-circuit trusted setup.

**PLONK** --- A universal SNARK (one trusted setup works for all circuits up to a size bound). Proofs are slightly larger than Groth16 but the universal setup is a major practical advantage. The **AlgoPlonk** library implements PLONK verification on Algorand using LogicSig verifiers.

**STARKs** --- No trusted setup at all (transparent), post-quantum secure, but proofs are large (tens to hundreds of KB). Too large for efficient on-chain verification on Algorand given the 4KB AVM value limit and opcode budget constraints.

For this project, we'll use **PLONK over BN254** via AlgoPlonk, which provides the best balance of proof size, verification cost, and tooling maturity on Algorand.

### AlgoPlonk: the Bridge From gnark Circuits to Algorand Verification

AlgoPlonk is a Go library that takes a ZK circuit defined in **gnark** (the leading Go ZK framework from ConsenSys), generates a proof off-chain, and produces either a LogicSig or smart contract verifier that validates the proof on-chain.

The workflow:
1. **Define the circuit** in Go using gnark's constraint system
2. **Generate proving and verification keys** via trusted setup
3. **Generate a proof** off-chain for a specific witness
4. **Generate an Algorand verifier** (LogicSig) from the verification key using AlgoPlonk
5. **Submit the proof on-chain** in an atomic group where the LogicSig verifier checks it

A BN254 LogicSig verifier costs **~8 minimum transaction fees** (8 × 20,000 = 160,000 opcodes budget). A BLS12-381 verifier costs ~10 fees. These are paid once per proof verification.


## Part 4: Building the Private Governance Voting System

*Before reading on, consider the design challenge: you need a contract where voters submit secret ballots, but the contract must still enforce that each vote is valid (one of the allowed choices) and that no one votes twice. How would you structure the phases of such a system? What data needs to go on-chain, and what must stay off-chain?*

### System Architecture

The voting system has four phases, using [box storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/) for commitments and [global state](https://dev.algorand.co/concepts/smart-contracts/storage/global/) for phase tracking:

**Phase 1 --- Setup:** The governance admin deploys the voting smart contract, defines the proposal (description, valid choices, voting period), and publishes the ZK circuit's verification key.

**Phase 2 --- Commitment:** Voters compute `commitment = MiMC(choice, randomness)` off-chain and submit the commitment on-chain. The commitment reveals nothing about the vote.

**Phase 3 --- Proof submission:** After the voting period closes, voters submit ZK proofs that their commitment corresponds to a valid choice without revealing which choice. This prevents last-minute vote changes (the commitment is already locked) while proving validity.

**Phase 4 --- Tallying:** Once all proofs are verified, voters reveal their votes with their randomness. The contract verifies each reveal matches its commitment and tallies the results. (Alternatively, with a more advanced circuit, the ZK proof itself can include a homomorphic tally contribution, eliminating the reveal phase entirely.)

### The ZK Circuit: Proving Vote Validity

The circuit proves: "I know a `choice` and `randomness` such that `MiMC(choice, randomness) = commitment` AND `choice ∈ {0, 1, 2}`."

The circuit is defined in Go because gnark (by ConsenSys) is the most mature ZK circuit framework available, and AlgoPlonk is written in Go. If you are unfamiliar with Go, the syntax is close enough to Python that you can follow the logic. The key lines are the `api.AssertIsEqual` constraint declarations --- each one adds a rule that the proof must satisfy. Here is the circuit in gnark:

The following Go code defines the ZK circuit. Save it as `circuit/vote_circuit.go` in a separate Go module (not part of the Python project):

```go
package voting

import (
    "github.com/consensys/gnark/frontend"
    "github.com/consensys/gnark/std/hash/mimc"
)

// VoteCircuit defines the ZK circuit for valid vote proof
type VoteCircuit struct {
    // Public inputs (visible to verifier)
    Commitment frontend.Variable `gnark:",public"`
    NumChoices frontend.Variable `gnark:",public"` // e.g., 3

    // Private inputs (the witness --- known only to prover)
    Choice     frontend.Variable // The actual vote (0, 1, or 2)
    Randomness frontend.Variable // Random blinding factor
}

func (c *VoteCircuit) Define(api frontend.API) error {
    // Constraint 1: commitment = MiMC(choice, randomness)
    // MiMC is natively supported in gnark
    mimc, err := mimc.NewMiMC(api)
    if err != nil {
        return err
    }
    mimc.Write(c.Choice)
    mimc.Write(c.Randomness)
    computed := mimc.Sum()
    api.AssertIsEqual(computed, c.Commitment)

    // Constraint 2: choice is in valid range [0, NumChoices)
    // We prove choice < NumChoices using bit decomposition
    api.AssertIsLessOrEqual(c.Choice, api.Sub(c.NumChoices, 1))

    // Constraint 3: choice >= 0 (implicit in field arithmetic,
    // but we add a range check for safety)
    bits := api.ToBinary(c.Choice, 8) // 8 bits supports up to 255 choices
    recomposed := api.FromBinary(bits...)
    api.AssertIsEqual(recomposed, c.Choice)

    return nil
}
```

This circuit has ~100-200 constraints (PLONK uses a Sparse Constraint System, or SCS, rather than R1CS) --- very small. The MiMC hash dominates the constraint count. Proof generation is near-instant on any modern CPU.

> **Go project setup.** The Go code in this project is separate from the Python smart contract code. You need Go 1.21 or later installed (download from [go.dev/dl](https://go.dev/dl/)). Create a dedicated directory for the ZK components:
>
> ```bash
> mkdir -p zk-voting/{circuit,cmd}
> cd zk-voting
> go mod init zk-voting
> go get github.com/consensys/gnark@latest
> go get github.com/consensys/gnark-crypto@latest
> go get github.com/giuliop/algoplonk@latest
> ```
>
> Save the circuit code above as `circuit/vote_circuit.go`. The verifier generator code (shown later in this chapter) goes in `cmd/main.go`. The resulting `go.mod` will look approximately like this (exact versions may differ):
>
> ```
> module zk-voting
>
> go 1.21
>
> require (
>     github.com/consensys/gnark v0.11.0
>     github.com/consensys/gnark-crypto v0.14.0
>     github.com/giuliop/algoplonk v0.3.0
> )
> ```
>
> The `go get` commands populate the `require` block and download dependencies automatically. You do not need to write `go.mod` by hand.

### The Voting Smart Contract

The contract uses four phases tracked in global state, with three `BoxMap` instances for commitments, proof status, and tallies. Add the following to `smart_contracts/governance_voting/contract.py`:

```python
from algopy import (
    ARC4Contract, BoxMap, Bytes, Global,
    GlobalState, Txn, UInt64, arc4, op, gtxn, urange,
)
from algopy.op import MiMCConfigurations

PHASE_COMMIT = 1
PHASE_PROVE = 2
PHASE_REVEAL = 3
PHASE_TALLY = 4

class GovernanceVoting(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.num_choices = GlobalState(UInt64(0))
        self.commit_end_round = GlobalState(UInt64(0))
        self.prove_end_round = GlobalState(UInt64(0))
        self.phase = GlobalState(UInt64(0))
        self.total_votes = GlobalState(UInt64(0))
        self.verified_proofs = GlobalState(UInt64(0))

        self.commitments = BoxMap(arc4.Address, Bytes, key_prefix=b"c_")
        self.proof_status = BoxMap(arc4.Address, UInt64, key_prefix=b"p_")
        self.tallies = BoxMap(arc4.UInt64, UInt64, key_prefix=b"t_")

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        """Reject update and delete --- this contract is immutable."""
        assert False, "Contract is immutable"
```

The `reject_lifecycle` bare method explicitly rejects `UpdateApplication` and `DeleteApplication` on-completion actions. Without this, the default ARC4Contract routing would reject them anyway (no handler registered), but an explicit rejection with a clear error message is a security best practice --- it makes the contract's immutability self-documenting and auditable.

The `initialize` method sets up the proposal parameters and creates tally boxes for each choice. Note the fixed-maximum loop pattern --- the AVM requires compile-time constant loop bounds, so we iterate up to 16 and break early:

```python
    @arc4.abimethod
    def initialize(
        self,
        num_choices: UInt64,
        commit_duration: UInt64,
        prove_duration: UInt64,
    ) -> None:
        assert Txn.sender == Global.creator_address
        assert self.phase.value == UInt64(0)

        self.admin.value = Txn.sender.bytes
        self.num_choices.value = num_choices
        self.commit_end_round.value = Global.round + commit_duration
        self.prove_end_round.value = Global.round + commit_duration + prove_duration
        self.phase.value = UInt64(PHASE_COMMIT)

        assert num_choices <= UInt64(16), "Max 16 choices"
        for i in urange(16):
            if i >= num_choices:
                break
            self.tallies[arc4.UInt64(i)] = UInt64(0)
```

The `commit_vote` method accepts a voter's MiMC commitment hash during the commit phase. Each voter can commit only once, and must provide an MBR payment to cover the box storage cost:

```python
    @arc4.abimethod
    def commit_vote(
        self,
        commitment: Bytes,
        mbr_payment: gtxn.PaymentTransaction,
    ) -> None:
        """Submit a vote commitment. commitment = MiMC(choice, randomness)."""
        assert self.phase.value == UInt64(PHASE_COMMIT)
        assert Global.round <= self.commit_end_round.value

        sender = arc4.Address(Txn.sender)
        assert sender not in self.commitments

        box_cost = UInt64(2500) + UInt64(400) * (UInt64(34) + UInt64(32))
        assert mbr_payment.receiver == Global.current_application_address
        assert mbr_payment.amount >= box_cost

        self.commitments[sender] = commitment
        self.total_votes.value += UInt64(1)
```

The `record_verified_proof` method records that a voter's ZK proof was validated by the LogicSig verifier. This is the critical security link between the off-chain proof and the on-chain state. The production warning in the code comments describes the additional group validation needed for a secure deployment:

```python
    @arc4.abimethod
    def advance_to_prove_phase(self) -> None:
        """Transition from commit to prove phase."""
        assert Txn.sender == Global.creator_address
        assert self.phase.value == UInt64(PHASE_COMMIT)
        assert Global.round > self.commit_end_round.value
        self.phase.value = UInt64(PHASE_PROVE)

    @arc4.abimethod
    def record_verified_proof(self, voter: arc4.Address) -> None:
        """Called after a LogicSig verifier confirms the ZK proof."""
        assert self.phase.value == UInt64(PHASE_PROVE)
        assert Global.round <= self.prove_end_round.value
        assert voter in self.commitments
        assert voter not in self.proof_status

        # SECURITY: Restrict to admin for the simplified version.
        # A production implementation would verify that a transaction from the
        # ZK verifier LogicSig's known address exists in the current atomic
        # group AND that the proof's public inputs match the stored commitment.
        # Without this check, anyone could mark any voter's proof as verified.
        assert Txn.sender == Global.creator_address, "Only admin"

        self.proof_status[voter] = UInt64(1)
        self.verified_proofs.value += UInt64(1)
```

> **Warning:** The `record_verified_proof` method creates a proof status box (`p_` prefix + 32-byte address = 34-byte key, 8-byte UInt64 value). This costs `2,500 + 400 * (34 + 8) = 19,300 microAlgos` in MBR. The app account must have sufficient Algo to cover this MBR for each voter. Unlike `commit_vote`, which requires a caller-provided MBR payment, the code above does not --- either fund the app account with enough Algo before the prove phase begins, or add an `mbr_payment` parameter to `record_verified_proof` as we did for `commit_vote`.

The `reveal_vote` method completes the commit-reveal cycle. The voter provides their original choice and randomness, and the contract recomputes the MiMC hash to verify it matches the stored commitment. If valid, the tally is incremented:

```python
    @arc4.abimethod
    def reveal_vote(self, choice: UInt64, randomness: Bytes) -> None:
        """Reveal a vote by providing the preimage of the commitment."""
        assert self.phase.value == UInt64(PHASE_REVEAL)

        sender = arc4.Address(Txn.sender)
        assert sender in self.commitments
        assert sender in self.proof_status
        assert self.proof_status[sender] == UInt64(1)

        # MiMC requires input to be a multiple of 32 bytes (one BN254 field
        # element per 32-byte chunk).  op.itob returns 8 bytes, so we pad
        # the choice to 32 bytes to match gnark's native field-element size.
        choice_bytes = op.concat(op.bzero(24), op.itob(choice))
        computed_hash = op.mimc(
            MiMCConfigurations.BN254Mp110,
            op.concat(choice_bytes, randomness),
        )
        stored_commitment = self.commitments[sender]
        assert computed_hash == stored_commitment

        choice_key = arc4.UInt64(choice)
        assert choice_key in self.tallies
        self.tallies[choice_key] += UInt64(1)

        self.proof_status[sender] = UInt64(2)  # Mark as revealed

    @arc4.abimethod
    def advance_to_reveal_phase(self) -> None:
        assert Txn.sender == Global.creator_address
        assert self.phase.value == UInt64(PHASE_PROVE)
        assert Global.round > self.prove_end_round.value
        self.phase.value = UInt64(PHASE_REVEAL)

    @arc4.abimethod(readonly=True)
    def get_tally(self, choice: UInt64) -> UInt64:
        return self.tallies[arc4.UInt64(choice)]
```

> **Design gap --- exercise opportunity.** The contract accumulates tallies during the reveal phase but has no `advance_to_tally_phase` method to formally close voting and finalize results. In the current design, the reveal phase remains open indefinitely. As an exercise, add a `PHASE_CLOSED` state (see Exercise 2 below) with an `advance_to_closed_phase` method that transitions from `PHASE_REVEAL` after a configurable duration, prevents further reveals, and emits the final tally via an ARC-28 event.

> **Note: Voters who do not prove forfeit their vote.** A voter who submits a commitment during the commit phase but fails to provide a ZK proof during the prove phase cannot reveal their vote --- the `reveal_vote` method requires `proof_status == 1`. Their vote is effectively lost. Additionally, the box storage MBR for their commitment box (`c_` prefix) remains locked in the app account, since no cleanup method exists to delete orphaned commitment boxes. A production system should include an admin-callable cleanup method that can reclaim MBR from unproven commitments after the voting period ends.

> **Warning: Fund the app account before calling `initialize`.** The `initialize` method creates tally boxes (one per choice). Each tally box costs `2,500 + 400 * (10 + 8) = 9,700 microAlgos` in MBR. For 3 choices, the app account needs at least `3 * 9,700 = 29,100 microAlgos` plus its base MBR of `100,000 microAlgos` before `initialize` is called. Send a payment to the app's address before the `initialize` call, or you will see a "balance below minimum" error.

As with every contract that uses box storage, client-side code must declare which boxes each transaction will access. The voting contract has several methods that touch different boxes, so it is worth listing them all.

> **Warning: Box references are required for every method that touches boxes.** Callers must include box references in their transaction parameters:
>
> - `initialize`: include box references for all tally boxes being created (e.g., `[(app_id, b"t_" + i.to_bytes(8, "big")) for i in range(num_choices)]`)
> - `commit_vote`: include the commitment box reference (`(app_id, b"c_" + sender_address_bytes)`)
> - `record_verified_proof`: include both the commitment box and the proof status box for the voter
> - `reveal_vote`: include the commitment, proof status, and tally box references
> - `get_tally`: include the tally box reference for the queried choice
>
> Forgetting box references produces "box read/write budget exceeded." The typed client generated by `algokit generate client` does NOT automatically add these --- you must specify them manually.
>
> Constructing box references in client code (example for `commit_vote`):
> ```python
> from algosdk import encoding
> voter_bytes = encoding.decode_address(voter.address)
> boxes=[
>     (app_id, b"c_" + voter_bytes),  # commitment box
> ]
> # For reveal_vote, include commitment, proof status, and tally boxes:
> boxes=[
>     (app_id, b"c_" + voter_bytes),
>     (app_id, b"p_" + voter_bytes),
>     (app_id, b"t_" + choice.to_bytes(8, "big")),
> ]
> ```

Finally, a testing note specific to the phase-based design of this contract.

> **LocalNet round advancement:** On LocalNet with on-demand block production, rounds only advance when transactions are submitted. To test phase transitions (which depend on round numbers), you must send dummy transactions (e.g., zero-amount payments) to advance rounds past the commit or prove deadlines.

### The LogicSig ZK Verifier

This is where AlgoPlonk generates the verifier. The following Go code shows the workflow (save as `cmd/main.go` in a Go module, separate from the Python project):

```go
package main

import (
    "github.com/giuliop/algoplonk"
    "github.com/consensys/gnark-crypto/ecc"
    "github.com/consensys/gnark/backend/plonk"
    "github.com/consensys/gnark/frontend"
    "github.com/consensys/gnark/frontend/cs/scs"
    "github.com/consensys/gnark/test"
)

func main() {
    // 1. Compile the circuit
    var circuit VoteCircuit
    ccs, _ := frontend.Compile(ecc.BN254.ScalarField(), scs.NewBuilder, &circuit)

    // 2. Setup (trusted setup --- generates proving and verification keys)
    srs, _ := test.NewKZGSRS(ccs)  // In production, use a ceremony
    pk, vk, _ := plonk.Setup(ccs, srs)

    // 3. Generate the Algorand LogicSig verifier from the verification key
    verifier, _ := algoplonk.MakeVerifier(vk, algoplonk.LogicSig)
    // verifier.Address() gives the LogicSig contract account address

    // 4. Create a proof for a specific vote
    witness := VoteCircuit{
        Commitment: computedCommitment,  // Public
        NumChoices: 3,                    // Public
        Choice:     1,                    // Private --- the actual vote
        Randomness: myRandomness,         // Private --- blinding factor
    }
    fullWitness, _ := frontend.NewWitness(&witness, ecc.BN254.ScalarField())
    proof, _ := plonk.Prove(ccs, pk, fullWitness)

    // 5. Generate the Algorand transactions for on-chain verification
    // AlgoPlonk creates the transaction group with:
    //   - The LogicSig verifier attached to padding transactions
    //   - The proof and public inputs passed as LogicSig arguments
    //   - ~8 transactions in the group for BN254
    txns, _ := verifier.MakeVerifyTransactions(proof, publicWitness)

    // 6. In the same atomic group, add the app call to record_verified_proof
    // This binds the ZK verification to the governance contract state update
}
```

> **Building and running the Go code.** The `cmd/main.go` code above is illustrative --- it shows the AlgoPlonk workflow but uses placeholder variables (`computedCommitment`, `myRandomness`, `publicWitness`). To compile and run a working version, you would fill in concrete values and import the circuit package. From the `zk-voting` directory:
>
> ```bash
> # Verify everything compiles (after filling in placeholder values)
> go build ./...
>
> # Run the verifier generator
> go run ./cmd/main.go
> ```
>
> The `go build ./...` command compiles all packages in the module. If you see import errors, run `go mod tidy` to resolve dependency versions. The AlgoPlonk `MakeVerifier` call writes the generated LogicSig TEAL files to the current directory --- you then reference these from your Python deployment code.

The generated LogicSig verifier:
- Has a deterministic address (the hash of the verification program)
- Takes the proof and public inputs as arguments (`Arg[0]`, `Arg[1]`, etc.)
- Executes the PLONK verification algorithm using the AVM's `ec_*` opcodes
- Returns true if and only if the proof is valid for the given public inputs
- Costs ~8 minimum transaction fees per verification (for BN254)

### The Atomic Group That Ties Everything Together

The full proof submission is a single atomic group:

```
Transaction Group:
[0] LogicSig verifier txn 1 (budget: +20,000 opcodes)    ← ZK verification
[1] LogicSig verifier txn 2 (budget: +20,000 opcodes)    ← ZK verification
[2] LogicSig verifier txn 3 (budget: +20,000 opcodes)    ← ZK verification
[3] LogicSig verifier txn 4 (budget: +20,000 opcodes)    ← ZK verification
[4] LogicSig verifier txn 5 (budget: +20,000 opcodes)    ← ZK verification
[5] LogicSig verifier txn 6 (budget: +20,000 opcodes)    ← ZK verification
[6] LogicSig verifier txn 7 (budget: +20,000 opcodes)    ← ZK verification
[7] LogicSig verifier txn 8 (budget: +20,000 opcodes)    ← ZK verification (proof valid!)
[8] Voter -> Contract: App call to record_verified_proof  ← State update
```

All 9 transactions succeed or fail atomically. If the proof is invalid, the LogicSig returns false, the entire group fails, and no state changes occur. If the proof is valid, the app call records the verification in the contract's box storage.

The security binding: the smart contract's `record_verified_proof` method must verify that the LogicSig verifier is present in the group (by checking for a transaction from the verifier's known address) and that the proof's public inputs (the commitment hash and number of choices) match what's stored on-chain.


## Part 5: Advanced Box Storage Patterns for Vote Tracking

### Box Storage Iteration: the On-Chain Enumeration Problem

Boxes are key-value stores with no built-in enumeration. You can read a box if you know its key, but you cannot iterate over all boxes. This is a fundamental constraint for tallying. (See [Algorand Python data structures](https://dev.algorand.co/algokit/languages/python/lg-data-structures/) for BoxRef and BoxMap patterns.)

**Solution 1: Maintain an explicit index.** Store voter addresses in a separate "index" box as a concatenated byte array. Each address is 32 bytes. A 32KB box can hold 1,024 voter addresses. For larger electorates, use multiple index boxes with a counter in global state. This is an illustrative extension that could be added to the voting contract:

```python
# Index box: concatenated 32-byte addresses
INDEX_BOX_KEY = b"voter_index"
self.voter_count = GlobalState(UInt64(0))

@arc4.abimethod
def commit_vote(self, commitment: Bytes, ...) -> None:
    # ... existing logic ...

    # Append voter address to index
    count = self.voter_count.value
    # Write sender address at offset count * 32
    op.box_replace(INDEX_BOX_KEY, count * UInt64(32), Txn.sender.bytes)
    self.voter_count.value = count + UInt64(1)
```

**Solution 2: Use BoxRef for raw access.** `BoxRef` gives you direct byte-level access to box contents, useful for packed data structures. This is an illustrative extension:

```python
from algopy import BoxRef

@arc4.abimethod
def read_voter_at_index(self, index: UInt64) -> arc4.Address:
    ref = BoxRef(key=b"voter_index")
    # Read 32 bytes at the correct offset
    addr_bytes = ref.extract(index * UInt64(32), UInt64(32))
    return arc4.Address.from_bytes(addr_bytes)
```

**Solution 3: Off-chain indexing.** For most governance systems, the indexer reads all box storage off-chain and computes tallies client-side. This is the pragmatic approach when the number of voters exceeds what can be efficiently iterated on-chain within opcode budgets.

### Box Size Planning for the Voting Contract

| Box | Key format | Key size | Data | Data size | MBR per box |
|-----|-----------|----------|------|-----------|-------------|
| Commitment | `c_` + address | 34 bytes | MiMC hash | 32 bytes | 2,500 + 400 × 66 = 28,900 μAlgo |
| Proof status | `p_` + address | 34 bytes | uint64 | 8 bytes | 2,500 + 400 × 42 = 19,300 μAlgo |
| Tally | `t_` + uint64 | 10 bytes | uint64 | 8 bytes | 2,500 + 400 × 18 = 9,700 μAlgo |
| Voter index | `voter_index` | 12 bytes | addresses | 32,768 bytes | 2,500 + 400 × 32,780 = 13,114,500 μAlgo |

Each voter costs ~48,200 μAlgo in MBR (commitment box: 28,900 + proof status box: 19,300), paid by the voter via the MBR payment pattern from the AMM chapter. The `commit_vote` method requires MBR for the commitment box (28,900 μAlgo), and `record_verified_proof` creates the proof status box requiring an additional 19,300 μAlgo. In test code, ensure the app account is funded for both boxes before calling these methods.


## Part 6: Algorand's Post-Quantum Security --- Falcon and State Proofs

*Before reading on, consider: the ZK proofs in this chapter use BN254, an elliptic curve scheme. What happens to these proofs --- and to Algorand's Ed25519 transaction signatures --- when large-scale quantum computers arrive? Does your voting system need to be redesigned, or is there a way to layer post-quantum security on top?*

### Why Post-Quantum Matters for Blockchain

Every Algorand transaction today is signed with Ed25519, an elliptic curve scheme. Shor's algorithm, running on a sufficiently powerful quantum computer, can solve the discrete logarithm problem that Ed25519's security depends on. This means a quantum adversary could forge signatures, steal funds, and rewrite transaction histories.

The timeline is uncertain --- estimates range from 10 to 30+ years for a cryptographically relevant quantum computer --- but blockchains are designed to operate for decades. The "harvest now, decrypt later" threat is already real: an adversary can record today's signed transactions and break them later when quantum computers exist. For a system that needs to be trustworthy for the lifetime of the data it secures, post-quantum preparation is engineering prudence, not speculation.

### What Is Falcon?

Falcon (Fast Fourier Lattice-based Compact Signatures over NTRU) is one of the NIST-selected post-quantum digital signature algorithms, published as a standard in 2024. It was developed by Pierre-Alain Fouque, Jeffrey Hoffstein, Paul Kirchner, Vadim Lyubashevsky, Thomas Pornin, Thomas Prest, Thomas Ricosset, Gregor Seiler, William Whyte, and Zhenfei Zhang.

Falcon's security is based on the hardness of the **Short Integer Solution (SIS)** problem over NTRU lattices. Unlike the discrete logarithm and factoring problems that Shor's algorithm breaks, lattice problems have no known efficient quantum algorithms. The best known quantum attacks against lattices provide only modest speedups over classical attacks --- nothing like the exponential speedup Shor gives for ECC.

Key properties that make Falcon suitable for Algorand:

**Compact signatures:** Falcon-512 produces ~666-byte signatures (NIST Level 1, ~128-bit security). Falcon-1024 produces ~1,280-byte signatures (NIST Level 5, ~256-bit security). These are small for post-quantum schemes --- Dilithium signatures are ~2.4–4.6KB by comparison.

**Fast verification:** Verification requires only a few FFT (Fast Fourier Transform) operations over small polynomials, making it fast even on constrained hardware. This aligns with Algorand's need to verify thousands of signatures per second during consensus.

**Deterministic signing mode:** Algorand's implementation uses a deterministic signing mode (developed by David Lazar and Chris Peikert), meaning signing the same message with the same key always produces the same signature. This eliminates a class of side-channel attacks related to randomness quality.

The Algorand connection runs deep: Chris Peikert (CSO, Algorand Foundation; formerly Head of Cryptography, Algorand Technologies) and Craig Gentry (former Algorand Foundation research fellow) co-authored the foundational GPV framework (Gentry-Peikert-Vaikuntanathan, 2008) that Falcon is built on.

### How Algorand Uses Falcon Today: State Proofs

State Proofs are Algorand's mechanism for trustless cross-chain communication. (See [State Proofs](https://dev.algorand.co/concepts/protocol/state-proofs/).) Every 256 rounds (~12 minutes), the network produces a **State Proof**: a compact cryptographic certificate attesting to all transactions that occurred during that interval. State Proofs are signed by participation nodes holding a supermajority of online stake.

The key innovation: State Proof signatures use **Falcon-1024**, not Ed25519. This means the chain of State Proofs --- the authenticated history of every transaction on Algorand --- is quantum-secure today, even though regular transaction signatures still use Ed25519.

The architecture:

1. **Participation key generation:** When a node registers for consensus, it generates both Ed25519 participation keys (for voting) and Falcon-1024 keys (for State Proofs). The Falcon key's Merkle root (the `sprfkey` field) is registered on-chain.

2. **Signature collection:** After each 256-round interval, participating nodes sign the interval's transaction commitment using their Falcon keys.

3. **Proof aggregation:** The individual Falcon signatures are aggregated into a compact certificate using a Merkle tree committed with **SumHash512** --- a subset-sum based hash function chosen for its ZK-SNARK friendliness (it's more efficient to prove in a circuit than SHA-256).

4. **On-chain attestation:** The State Proof transaction (containing the proof and the message it attests to) goes through regular consensus and is written to the chain.

5. **External verification:** A light client on another chain (Ethereum, for example) can verify the State Proof using only the Falcon verification algorithm and the Merkle root --- no trust in intermediaries required.

This is why Algorand claims its **history is already quantum-secure**: even if someone breaks Ed25519 in the future, the chain of State Proofs (signed with quantum-resistant Falcon) still authenticates every past transaction. The attacker could potentially forge new Ed25519 transactions, but they cannot rewrite the State Proof-attested history.

### The Path to Fully Quantum-Secure Transactions

Algorand has demonstrated Falcon-signed transactions on MainNet using LogicSigs as the authorization mechanism. The approach:

1. Generate a Falcon-1024 keypair off-chain
2. Create a LogicSig program that verifies a Falcon signature against the user's Falcon public key
3. The LogicSig's contract account address becomes the user's "quantum-safe" address
4. Transactions from this address are authorized by the LogicSig, which verifies the Falcon signature passed as an argument

The AVM opcode `falcon_verify` (shipped in AVM v12, September 2024) makes Falcon verification native at a cost of 1,700 opcodes. The first Falcon-signed transaction on Algorand MainNet was executed on November 3, 2025, using a LogicSig-based Falcon account.

The full post-quantum transition roadmap involves:

1. **History protection (done):** State Proofs with Falcon-1024
2. **Transaction protection (done):** Falcon-based LogicSig accounts using the native `falcon_verify` opcode (AVM v12). First MainNet transaction: November 3, 2025.
3. **Consensus protection (research):** Replace the Ed25519-based VRF with a post-quantum VRF. Active research includes ZKBoo/ZKB++ based constructions and lattice-based VRF proposals.

### Implications for Our Voting System

Our governance voting system uses BN254 elliptic curves for ZK proofs. BN254 is NOT post-quantum secure --- a quantum computer running Shor's algorithm could break it. This means:

- **The vote commitments (MiMC hashes) are quantum-safe** --- hash functions are resistant to quantum attacks (Grover's algorithm provides only a quadratic speedup, manageable with larger hash sizes).
- **The ZK proofs themselves are NOT quantum-safe** --- the elliptic curve pairing used for PLONK/Groth16 verification is vulnerable to Shor's algorithm.
- **The vote reveals are quantum-safe** --- they're just preimage demonstrations against the MiMC hash.

For a production system that needs to be quantum-resistant end-to-end, you would need to replace the pairing-based ZK proofs with **ZK-STARKs** (which use hash functions instead of elliptic curves and are quantum-resistant). STARKs produce larger proofs, making on-chain verification more expensive, but they eliminate the quantum vulnerability entirely. This is an active area of research for all blockchain ZK systems.


## Part 7: Testing the Complete System

### Test Scenario: 3 Voters, 3 Choices

> **Note:** The tests below are structural outlines showing *what* to test and *how* to assert. The helper functions (`deploy_voting_contract`, `generate_random_scalar`, `mimc_hash`, `generate_vote_proof`, `fund_mbr`, `advance_rounds`, etc.) are project-specific wrappers around the [AlgoKit Utils](https://dev.algorand.co/algokit/utils/python/testing/) calls shown earlier in this chapter --- implement them using the deployment and interaction patterns demonstrated above. The patterns here --- lifecycle tests, failure-path tests, invariant tests --- are the ones you should implement for any production contract.

The following test outlines go in `tests/test_governance_voting.py` (not part of the contract code).

The end-to-end test walks through all four phases with three voters, each casting a different vote. It verifies that commitments, proofs, and reveals all work correctly and produce the expected tally:

```python
# test_governance_voting.py
import pytest
import algokit_utils

class TestGovernanceVoting:
    def test_full_voting_flow(self):
        """End-to-end: setup -> commit -> prove -> reveal -> tally"""
        algorand = algokit_utils.AlgorandClient.default_localnet()
        admin = algorand.account.localnet_dispenser()
        voting_client = deploy_voting_contract(algorand, admin)
        voting_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="initialize", args=[3, 100, 100],
            )
        )

        voters = [algorand.account.random() for _ in range(3)]
        choices = [0, 1, 2]
        randomness = [generate_random_scalar() for _ in range(3)]
        commitments = [
            mimc_hash(choice, rand) for choice, rand in zip(choices, randomness)
        ]

        # Phase 1: Submit commitments
        for voter, commitment in zip(voters, commitments):
            voting_client.send.call(
                algokit_utils.AppClientMethodCallParams(
                    method="commit_vote",
                    args=[commitment, fund_mbr(voter, voting_client)],
                )
            )

        # Phase 2: Generate and submit ZK proofs
        advance_rounds(algorand, 101)
        voting_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="advance_to_prove_phase",
            )
        )
        for voter, choice, rand, commitment in zip(
            voters, choices, randomness, commitments
        ):
            proof = generate_vote_proof(choice, rand, commitment, num_choices=3)
            verify_txns = algoplonk_verifier.make_verify_transactions(proof)
            record_params = voting_client.params.call(
                algokit_utils.AppClientMethodCallParams(
                    method="record_verified_proof",
                    args=[voter.address],
                )
            )
            submit_atomic_group(verify_txns + [record_params])

        # Phase 3: Reveal votes and check tallies
        advance_rounds(algorand, 101)
        voting_client.send.call(
            algokit_utils.AppClientMethodCallParams(
                method="advance_to_reveal_phase",
            )
        )
        for voter, choice, rand in zip(voters, choices, randomness):
            voting_client.send.call(
                algokit_utils.AppClientMethodCallParams(
                    method="reveal_vote",
                    args=[choice, rand],
                    sender=voter.address,
                )
            )

        tally_0 = voting_client.send.call(
            algokit_utils.AppClientMethodCallParams(method="get_tally", args=[0])
        )
        tally_1 = voting_client.send.call(
            algokit_utils.AppClientMethodCallParams(method="get_tally", args=[1])
        )
        tally_2 = voting_client.send.call(
            algokit_utils.AppClientMethodCallParams(method="get_tally", args=[2])
        )
        assert tally_0.abi_return == 1
        assert tally_1.abi_return == 1
        assert tally_2.abi_return == 1
```

The failure-path tests verify that invalid operations are correctly rejected. The invalid proof test confirms that the ZK circuit rejects out-of-range choices, and the double commit test ensures one-vote-per-voter:

```python
    def test_invalid_proof_rejected(self):
        """A proof for a choice outside valid range must fail."""
        admin = algorand.account.localnet_dispenser()
        voting_client = deploy_voting_contract(algorand, admin)
        call_method(voting_client, "initialize", [3, 100, 100])
        voter = algorand.account.random()
        bad_choice = 5
        rand = generate_random_scalar()
        commitment = mimc_hash(bad_choice, rand)
        # Commit succeeds (commitment is just a hash --- validity is proven later)
        call_method(voting_client, "commit_vote",
                    [commitment, fund_mbr(voter, voting_client)])
        advance_rounds(algorand, 101)
        call_method(voting_client, "advance_to_prove_phase", [])
        # Proof generation should fail: circuit rejects choice >= num_choices
        with pytest.raises(Exception):
            generate_vote_proof(bad_choice, rand, commitment, num_choices=3)

    def test_double_commit_rejected(self):
        """Same voter cannot commit twice."""
        admin = algorand.account.localnet_dispenser()
        voting_client = deploy_voting_contract(algorand, admin)
        call_method(voting_client, "initialize", [3, 100, 100])
        voter = algorand.account.random()
        rand = generate_random_scalar()
        commitment = mimc_hash(1, rand)
        call_method(voting_client, "commit_vote",
                    [commitment, fund_mbr(voter, voting_client)])
        rand2 = generate_random_scalar()
        commitment2 = mimc_hash(2, rand2)
        with pytest.raises(Exception):
            call_method(voting_client, "commit_vote",
                        [commitment2, fund_mbr(voter, voting_client)])
```

The reveal and timing tests verify the commit-reveal binding (revealing a different choice than committed must fail) and the phase deadline enforcement (commits after the deadline are rejected):

```python
    def test_reveal_must_match_commitment(self):
        """Revealing a different choice than committed fails."""
        admin = algorand.account.localnet_dispenser()
        voting_client = deploy_voting_contract(algorand, admin)
        call_method(voting_client, "initialize", [3, 100, 100])
        voter = algorand.account.random()
        rand = generate_random_scalar()
        commitment = mimc_hash(1, rand)
        call_method(voting_client, "commit_vote",
                    [commitment, fund_mbr(voter, voting_client)])
        advance_rounds(algorand, 201)
        call_method(voting_client, "advance_to_reveal_phase", [])
        with pytest.raises(Exception):
            call_method(voting_client, "reveal_vote", [2, rand],
                        sender=voter.address)

    def test_commitment_after_deadline_rejected(self):
        """Commits after the commit period are rejected."""
        admin = algorand.account.localnet_dispenser()
        voting_client = deploy_voting_contract(algorand, admin)
        call_method(voting_client, "initialize", [3, 50, 100])
        advance_rounds(algorand, 51)
        voter = algorand.account.random()
        rand = generate_random_scalar()
        commitment = mimc_hash(0, rand)
        with pytest.raises(Exception):
            call_method(voting_client, "commit_vote",
                        [commitment, fund_mbr(voter, voting_client)])
```

### Security Audit Checklist for the Voting System

- Commitments are binding (MiMC collision resistance within the field)
- Commitments are hiding (randomness is cryptographically random, 256-bit)
- ZK proofs cannot be forged (PLONK soundness)
- ZK proofs reveal nothing about the vote (zero-knowledge property)
- Double-voting is prevented (one commitment per address)
- Vote changes after commitment are prevented (phase transitions are irreversible)
- LogicSig verifier address is hardcoded/verified in the smart contract
- Public inputs to the ZK proof are bound to on-chain state (commitment, num_choices)
- Box storage MBR is properly funded and refundable
- Phase transitions check round numbers correctly and are admin-only
- Group size is validated in the proof-submission atomic group (production hardening)
- Admin cannot see or modify votes (only advance phases)
- The trusted setup ceremony is properly conducted (for PLONK, a universal setup from a ceremony)

## Summary

In this chapter you learned to:

- Explain the three properties of zero-knowledge proofs (completeness, soundness, zero-knowledge) and why each matters for private voting
- Describe the commit-reveal pattern and how it provides ballot secrecy on a public blockchain
- Use the AVM's native elliptic curve opcodes (BN254) for on-chain cryptographic verification
- Explain why MiMC is used inside ZK circuits instead of SHA-256, and the security tradeoffs involved
- Design a ZK circuit using gnark/AlgoPlonk that proves a vote is valid without revealing which choice was selected
- Build a multi-phase voting smart contract with registration, commitment, reveal, and tallying phases
- Use LogicSig opcode pooling (20,000 opcodes per transaction) to verify ZK proofs on-chain
- Describe Algorand's Falcon-based post-quantum security roadmap and its implications for long-term cryptographic design

| Feature Built | New Concepts Introduced |
|--------------|------------------------|
| ZK circuit (gnark) | Groth16/PLONK proof systems, R1CS/SCS, witness generation |
| MiMC commitments | ZK-friendly hashing, commitment schemes, nullifiers |
| Voting smart contract | Multi-phase state machine, box-based vote tracking, tally accumulation |
| LogicSig ZK verifier | BN254 curve operations, pairing checks, opcode budget pooling |
| Atomic verification group | Coordinating LogicSig verification with smart contract state updates |
| Post-quantum discussion | Falcon signatures, state proofs, hash-based commitments |

## Exercises

1. **(Recall)** What are the three properties of a zero-knowledge proof? Which one ensures the verifier learns nothing about which choice the voter selected?

2. **(Apply)** The voting contract uses a 4-phase system (commit, prove, reveal, tally). Add a `PHASE_CLOSED` state that activates after the reveal phase ends, preventing any further action. What state transitions and checks need to change?

3. **(Analyze)** Why is MiMC used for commitments inside the ZK circuit instead of SHA-256? What are the security tradeoffs of using a less battle-tested hash function?

4. **(Create)** Design an extension where voters can delegate their vote to another address before the commitment phase. What changes to the commitment scheme, ZK circuit, and smart contract are needed? How do you prevent a delegate from learning what vote they are casting?

## Appendix A: Opcode Costs for Cryptographic Operations

Costs from the [AVM opcodes reference](https://dev.algorand.co/reference/algorand-teal/opcodes/).

| Operation | Curve | Cost (opcodes) |
|-----------|-------|----------------|
| ec_add | BN254 G1 | 125 |
| ec_add | BLS12-381 G1 | 205 |
| ec_scalar_mul | BN254 G1 | 1,810 |
| ec_scalar_mul | BLS12-381 G1 | 2,950 |
| ec_multi_scalar_mul | BN254 G1 | 3,600 + 90 per 32B of B |
| ec_multi_scalar_mul | BLS12-381 G1 | 6,500 + 95 per 32B of B |
| ec_pairing_check | BN254 | 8,000 + 7,400 per 64B of B |
| ec_pairing_check | BLS12-381 | 13,000 + 10,000 per 128B of B |
| ec_subgroup_check | BN254 G1 | 20 |
| ec_subgroup_check | BLS12-381 G2 | 2,340 |
| mimc | BN254 | 10 + 550 per 32B of input |
| ed25519verify | --- | 1,900 |
| falcon_verify | --- | 1,700 |

## Appendix B: Key Differences Between Smart Contracts and LogicSigs

See [AVM](https://dev.algorand.co/concepts/smart-contracts/avm/) for the full specification of both execution modes.

| Property | Smart Contract | LogicSig |
|----------|---------------|----------|
| Opcode budget per txn | 700 (pooled) | 20,000 (pooled separately) |
| Max pooled budget | ~190,400 (16 outer × 700 + up to 256 inner × 700) | 320,000 (16 × 20,000; all txns contribute, not just those with LogicSigs) |
| Has state | Yes (global, local, boxes) | No |
| Can issue inner transactions | Yes | No |
| Persistent address | App ID → deterministic address | Program hash → deterministic address |
| Can be updated | If authorized | No (immutable by nature) |
| Modes | Application calls | Contract account OR delegated signature |
| Can read boxes | Yes | No |
| Can access other apps' state | Yes (with references) | No |
| Primary use case | Stateful dApps | ZK verification, delegation, specialized escrow |

## Appendix C: Resources

| Resource | URL |
|----------|-----|
| AlgoPlonk (ZK on Algorand) | [github.com/giuliop/AlgoPlonk](https://github.com/giuliop/AlgoPlonk) |
| gnark (ZK circuit framework) | [github.com/ConsenSys/gnark](https://github.com/ConsenSys/gnark) |
| Cryptographic Tools | [dev.algorand.co/concepts/smart-contracts/cryptographic-tools/](https://dev.algorand.co/concepts/smart-contracts/cryptographic-tools/) |
| AVM Opcodes Reference | [dev.algorand.co/reference/algorand-teal/opcodes/](https://dev.algorand.co/reference/algorand-teal/opcodes/) |
| State Proofs | [dev.algorand.co/concepts/protocol/state-proofs/](https://dev.algorand.co/concepts/protocol/state-proofs/) |
| Falcon CLI tool | [github.com/algorandfoundation/falcon-signatures](https://github.com/algorandfoundation/falcon-signatures) |
| Algorand Post-Quantum | [algorand.co/technology/post-quantum](https://algorand.co/technology/post-quantum) |
| Falcon Technical Brief | algorand.co/blog/technical-brief-quantum-resistant-transactions |
| LogicSig Security Guidelines | developer.algorand.org/docs/get-details/dapps/smart-contracts/guidelines/ |
| Building Secure Contracts (Algorand) | secure-contracts.com/not-so-smart-contracts/algorand/ |
| MiMC Hash Specification | eprint.iacr.org/2016/492 |
| PLONK Paper | eprint.iacr.org/2019/953 |
| Groth16 Paper | eprint.iacr.org/2016/260 |

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

> **Note:** `BoxRef` is deprecated in current PuyaPy. The same methods (`create`, `delete`, `extract`, `replace`, `resize`, `splice`) are now available directly on `Box`. Prefer `Box` over `BoxRef`.

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
        ref = BoxRef(key=b"data")
        ref.delete()
```

BoxRef gives byte-level access. Essential for packed data structures.

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
        # .native converts to Python-usable form:
        native_x = x.native   # → UInt64
        native_s = s.native   # → algopy.String
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

\newpage


# Consolidated Gotchas Cheat Sheet {-}

Every gotcha from every chapter in one scannable list.

## Box Storage

(See [Box Storage](https://dev.algorand.co/concepts/smart-contracts/storage/box/).)

- MBR formula includes name length: `2,500 + 400 × (name_len + data_size)` microAlgos
- Each box reference provides only 1KB of I/O budget --- a 4KB box needs 4 references
- Boxes cannot be accessed in the ClearStateProgram --- all box opcodes fail immediately
- Box size was immutable prior to AVM v10; since AVM v10, `box_resize` and `box_splice` allow in-place resizing without deleting and recreating
- If an app is deleted, its boxes are NOT deleted and the MBR is locked forever
- `box_get` fails if the box exceeds 4KB; use `box_extract` for larger boxes
- Box data is unstructured bytes --- you manage serialization yourself
- Box names with non-ASCII bytes produce confusing error messages

## Inner Transactions

(See [Inner Transactions](https://dev.algorand.co/concepts/smart-contracts/inner-txn/).)

- **Always** set `fee=UInt64(0)` on inner transactions; otherwise the contract's Algo balance pays
- Budget adds +700 opcodes per inner app call when submitted
- Maximum 16 inner transactions per application call (pooled to 256 across the group)
- Maximum call depth of 8 --- the 8th contract cannot make further app calls
- ClearState programs cannot issue inner transactions
- State changes from earlier transactions in a group ARE visible to later transactions in the same group (they share a single copy-on-write state object). The group's aggregate changes commit to the ledger only after every transaction succeeds.

## Local State

(See [Local Storage](https://dev.algorand.co/concepts/smart-contracts/storage/local/).)

- Users can clear local state at any time via ClearState; this **always** succeeds
- Maximum 16 key-value pairs per user per application
- Schema (number of uint/byte slots) is immutable after app creation --- plan ahead
- Never use local state as the sole store for financial obligations (debts, locked tokens)

## Global State

(See [Global Storage](https://dev.algorand.co/concepts/smart-contracts/storage/global/).)

- Maximum 64 key-value pairs per application
- Key + value combined maximum 128 bytes per pair
- Schema is immutable after creation --- allocate extra slots for future needs

## Assets (ASAs)

(See [Assets Overview](https://dev.algorand.co/concepts/assets/overview/).)

- Contracts (and users) must opt into each ASA before receiving it; costs 0.1 Algo MBR
- `asset_sender` is only for clawback, not for sending --- use `Txn.sender` for regular transfers
- `Txn.receiver` is for Payment transactions; `Txn.asset_receiver` is for AssetTransfer
- Similarly: `Txn.amount` vs `Txn.asset_amount`, `Txn.close_remainder_to` vs `Txn.asset_close_to`
- Setting freeze/clawback address to the zero address makes it permanently immutable

## Arithmetic

(See [AVM](https://dev.algorand.co/concepts/smart-contracts/avm/).)

- `UInt64` overflow panics (fails the transaction) --- it does not wrap around
- Use `mulw`/`divmodw` or `BigUInt` for intermediate calculations that may overflow
- Floor division is the default and rounds in favor of the pool (correct for DeFi)
- For ceiling division: `ceil(a/b) = (a + b - 1) / b`
- `BigUInt` supports up to 512-bit values via byte-array arithmetic

## Resource References

(See [Resource Usage](https://dev.algorand.co/concepts/smart-contracts/resource-usage/).)

- 8 foreign references (accounts + assets + apps + boxes) per transaction
- References are shared across the group since AVM v9 --- spread across multiple txns if needed
- For compound references (asset holdings), both account and asset must appear in the same top-level transaction's arrays
- The transaction sender and current application are implicitly available

## Logic Signatures

(See [Logic Signatures](https://dev.algorand.co/concepts/smart-contracts/logic-sigs/).)

- In LogicSig programs, always check the close field and `rekey_to` equal zero address (`close_remainder_to` for payments, `asset_close_to` for asset transfers, `rekey_to` for both) --- missing any one is directly exploitable
- Always cap the fee to prevent fee-drain attacks
- Include an expiration mechanism (check `Txn.last_valid` or `Txn.first_valid`)
- Check `Global.genesis_hash` to restrict to a specific network (MainNet/TestNet)
- Arguments (`Arg[0]`, etc.) are visible on-chain and are NOT signed --- anyone can change them
- LogicSig signed delegations are valid forever unless you build in expiration
- LogicSig opcode budget is 20,000 per transaction (separate pool from smart contracts). Since AVM v10, LogicSig budgets pool across the group --- e.g., 8 LogicSig transactions contribute 160,000 opcodes to a shared LogicSig pool
- Template variables are baked into the program at compile time and ARE covered by the signature

## Compilation and Tooling

(See [AlgoKit CLI overview](https://dev.algorand.co/algokit/cli/overview/).)

- PuyaPy versions below 5.3.2 had a missing-assert bug --- always use v5.7.1+
- Global and local state schemas are immutable after app creation
- `algokit localnet reset` between test suites for clean state
- Block timestamps come from the proposer's clock, accurate only within ~25 seconds
- The minimum fee (1,000 microAlgos) is a consensus parameter that can change --- never hardcode it in client code (use `suggested_params()` instead). In contracts, fee cap checks like `Txn.fee <= UInt64(10_000)` necessarily use constants; this is an accepted tradeoff since the cap is a safety bound, not an exact fee

## Security

(See [Rekeying](https://dev.algorand.co/concepts/accounts/rekeying/) for the rekey attack vector.)

- For Logic Signatures, missing close-to / rekey checks are the #1 audit finding: assert `close_remainder_to` (payments), `asset_close_to` (asset transfers), and `rekey_to` (all types). These checks are not needed in stateful contracts --- the fields affect the sender's account, not the contract's
- Always verify group size matches expectations
- Always verify asset IDs in every transfer (don't assume)
- Always verify the receiver of incoming transfers is the contract address
- ClearState always succeeds --- design for users being able to exit at any time
- Rejected UpdateApplication and DeleteApplication makes a contract immutable (recommended for DeFi)
- Run Tealer static analysis: `tealer approval.teal --detect all`

\newpage

# What's Next {-}

Look at what you have accomplished. You started with no smart contract knowledge and built a token vesting system with safe integer math and box storage, extended it with NFTs for transferable financial rights, constructed a constant product AMM with LP token mechanics, designed a hybrid stateful/stateless limit order book with keeper bots, and pushed the AVM to its limits with zero-knowledge proofs for private voting. Along the way, you internalized the security patterns that prevent real exploits, the MBR lifecycle that keeps contracts solvent, and the atomic group composition that makes DeFi composable. These are not toy examples --- they are the building blocks of production protocols.

Here is where to go next.

**Concentrated liquidity AMMs.** The constant product AMM in Chapter 5 is the Uniswap V2 model. The broader DeFi industry has moved toward concentrated liquidity (V3), where LPs choose price ranges for dramatically higher capital efficiency. No Algorand DEX has yet implemented a full V3-style concentrated liquidity AMM --- this is an open opportunity. Porting V3 concepts to the AVM would require creative use of box storage for tick data and careful opcode budget management for tick-crossing math.

**Lending and borrowing protocols.** Folks Finance and the now-sunset Algofi demonstrated that full lending/borrowing is possible on Algorand. Key concepts to study: overcollateralization, health factors, liquidation mechanics (calling AMM swaps via inner transactions to convert seized collateral), and interest rate models (utilization curves). These protocols compose heavily with AMMs for price oracles and liquidation execution.

**Cross-chain bridges and State Proofs.** Chapter 9 introduced State Proofs and Falcon signatures. The practical application: building a light client on Ethereum that verifies Algorand State Proofs, enabling trustless asset transfers between chains. This is active infrastructure work in the Algorand ecosystem.

**Ecosystem integration.** This book built everything from scratch. Production applications integrate with existing protocols. Study the ABIs of Tinyman, Pact, and Folks Finance to understand how to call their contracts from yours. The ARC-56 specs for deployed contracts are your entry point --- load them with AlgoKit Utils and call methods directly.

**Off-chain infrastructure.** Production DeFi needs indexer services, event-driven backends, keeper bots, and monitoring. The Algorand Indexer REST API, Conduit data pipeline, and Nodely public endpoints provide the building blocks. Start with a Python service that watches for swap events (by parsing ARC-28 logs) and updates a price feed.

**MainNet operations.** LocalNet and TestNet are training wheels. MainNet deployment requires: key management (hardware wallets or HSMs, never KMD), contract verification (proving source matches deployed bytecode), monitoring and alerting, and an emergency response plan for what to do when you find a bug in an immutable contract (answer: communicate immediately, recommend users withdraw, deploy V2).

**Consensus participation and staking rewards.** Since the end of governance period 14 (Q1 2025), Algorand rewards come from consensus participation rather than quarterly governance commitments. Validators earn 10 Algo per proposed block (decaying over time) plus 50% of transaction fees. Participation requires running a node with at least 30,000 Algo staked and registering participation keys with a 2-Algo fee. This is Algorand's long-term economic model --- understanding it matters if you are building protocols that interact with staking (like Folks Finance's liquid staking) or if you plan to operate your own infrastructure.

**Contract migration.** Immutable contracts cannot be patched, but they can be superseded. When Tinyman migrated from V1 to V2 after the exploit, the process was: deploy V2, publicly announce a migration deadline, build a migration UI that withdraws liquidity from V1 and deposits into V2 in a single atomic group, and eventually shut down the V1 frontend while leaving the V1 contracts on-chain for anyone who still needs to withdraw. The key principle: the old contract remains functional for withdrawals indefinitely (it is immutable, after all), but new deposits are directed exclusively to V2. Plan your state schema so that migration-critical data (user balances, LP positions) can be read by the new contract via `app_global_get_ex` or reconstructed from on-chain history via the indexer.

\newpage

# Glossary {-}

**ABI (Application Binary Interface)**
:   A standard defining how method calls are encoded, routed, and decoded. On Algorand, ARC-4 is the ABI standard.

**AMM (Automated Market Maker)**
:   A smart contract that provides liquidity for token swaps using a mathematical formula (e.g., constant product) instead of a traditional order book.

**ARC-4**
:   The Algorand Request for Comments defining the Application Binary Interface for smart contracts. Specifies method selectors, argument encoding, and return value conventions.

**ARC-56**
:   The application specification format that describes a contract's methods, state schema, and deployment metadata. Generated by the PuyaPy compiler.

**ARC-200**
:   A smart-contract-based token standard for Algorand, similar in concept to Ethereum's ERC-20. Unlike native ASAs, ARC-200 tokens are implemented as smart contracts with transfer logic. Less common than ASAs but used by some protocols.

**ASA (Algorand Standard Asset)**
:   A first-class on-chain asset (fungible token, NFT, or security token) created via an Asset Configuration transaction. Accounts must opt in before holding an ASA.

**AVM (Algorand Virtual Machine)**
:   The bytecode execution engine that runs TEAL programs. Supports `uint64` and `bytes` types, with a 700-opcode budget per app call and 20,000 per LogicSig transaction.

**BigUInt**
:   An arbitrary-precision unsigned integer type (up to 512 bits) available in Algorand Python for math that exceeds `uint64` range.

**Box storage**
:   Application-controlled key-value storage where each entry is an independent "box." Only the owning application can create, read, modify, or delete its boxes on-chain.

**Clear state program**
:   The second of the two programs in every smart contract. Runs when a user force-exits an application. The user's local state is always cleared regardless of the program's result.

**Constant product formula**
:   The AMM invariant $x \times y = k$, where $x$ and $y$ are token reserves. Ensures that removing one token requires adding the other in proportion.

**Concentrated liquidity**
:   An AMM design (Uniswap V3) where liquidity providers choose a price range for their capital, dramatically improving capital efficiency but making positions non-fungible and amplifying impermanent loss.

**Delegated signature**
:   A LogicSig mode where an existing account signs the program, authorizing anyone holding the signed program to submit transactions from that account subject to the program's constraints.

**DeFi (Decentralized Finance)**
:   Financial applications built on smart contracts that operate without centralized intermediaries.

**Escrow**
:   A smart contract account that holds assets and releases them only when programmatic conditions are met. On Algorand, the contract's deterministic address acts as the escrow.

**Fee pooling**
:   The ability for one transaction in an atomic group to overpay its fee to cover the minimum fees of other transactions in the same group.

**Global state**
:   Key-value storage attached to an application, readable by any transaction that references the app. Limited to 64 key-value pairs with keys up to 64 bytes and key + value combined up to 128 bytes.

**Inner transaction**
:   A transaction emitted by a smart contract during execution (e.g., sending tokens, creating assets). Inner transactions inherit the contract's authority.

**Impermanent loss**
:   The reduction in value that liquidity providers experience compared to simply holding their tokens, caused by the AMM rebalancing the position as prices move. Called "impermanent" because it reverses if the price returns to its original ratio.

**Local state**
:   Per-account key-value storage for each application a user opts into. Limited to 16 key-value pairs. Can be cleared unilaterally by the user via ClearState.

**LogicSig (Logic Signature)**
:   A TEAL program that authorizes a transaction in place of a private key signature. Operates in contract account mode or delegated signature mode.

**LP token (Liquidity Provider token)**
:   A token minted by an AMM to represent a liquidity provider's share of the pool. Redeemable for a proportional share of both reserve assets.

**MBR (Minimum Balance Requirement)**
:   The minimum Algo balance an account must maintain, calculated based on the resources it holds (ASAs, applications, boxes). The base MBR is 0.1 Algo.

**Multisig (Multi-Signature)**
:   An account that requires signatures from multiple parties (M-of-N) to authorize a transaction. Used for admin operations, treasury management, and governance in production protocols. Algorand supports multisig natively at the protocol level.

**Opcode budget**
:   The maximum computational cost allowed per execution context. Smart contracts get 700 opcodes per app call (poolable across a group); LogicSigs get 20,000 per transaction.

**Smart contract**
:   A stateful program deployed on Algorand that validates transactions and manages on-chain state. Consists of an approval program and a clear state program.

**Subroutine**
:   A reusable function within an Algorand Python contract, decorated with `@subroutine`. Compiled to a TEAL subroutine, reducing program size when called multiple times.

**TEAL (Transaction Execution Approval Language)**
:   The low-level bytecode language executed by the AVM. Algorand Python compiles to TEAL via the PuyaPy compiler.

**TEALScript**
:   A TypeScript-based smart contract language for Algorand that compiles to TEAL bytecode. An alternative to Algorand Python (PuyaPy) for developers who prefer TypeScript.

**Template variable**
:   A compile-time parameter in a smart contract or LogicSig program, substituted with a concrete value before compilation. Produces a unique program hash per parameter set.

**TWAP (Time-Weighted Average Price)**
:   A price derived by averaging spot prices over a time window, weighted by block time. Resistant to single-block manipulation. Used by lending protocols as a price oracle.

**VibeKit**
:   A CLI tool that configures AI coding agents for Algorand development. Installs agent skills, documentation tools, and blockchain interaction tools so AI assistants can write, compile, deploy, and debug contracts.

**Wide arithmetic**
:   128-bit intermediate arithmetic using `op.mulw` (multiply wide) and `op.divmodw` (divide-modulo wide) to prevent overflow in `uint64` calculations.

**ZK proof (Zero-Knowledge proof)**
:   A cryptographic proof that a statement is true without revealing why it is true. Used in this book for private voting where the proof shows a vote is valid without revealing the choice.

\newpage

# Bibliography {-}

Adams, H. et al. "Uniswap v2 Core." Uniswap, 2020. https://uniswap.org/whitepaper.pdf

Adams, H. et al. "Uniswap v3 Core." Uniswap, 2021. https://uniswap.org/whitepaper-v3.pdf

Adams, H. et al. "Uniswap v4 Core." Uniswap, 2023. https://github.com/Uniswap/v4-core/blob/main/docs/whitepaper-v4.pdf

Algorand Foundation. "AlgoKit CLI Documentation." https://github.com/algorandfoundation/algokit-cli

Algorand Foundation. "Algorand Python Documentation." https://algorandfoundation.github.io/puya/

AlgoPlonk. "PLONK verifier for the Algorand Virtual Machine." Algorand Foundation, 2024. https://github.com/algorand-foundation/algoplonk

Barton, J. et al. "Panda: Security Analysis of Algorand Smart Contracts." *Proceedings of the 32nd USENIX Security Symposium*, 2023.

Bowe, S., Gabizon, A., and Green, M. "A multi-party protocol for constructing the public parameters of the Pinocchio zk-SNARK." *Financial Cryptography and Data Security*, 2018.

Fouque, P.-A. et al. "Falcon: Fast-Fourier Lattice-based Compact Signatures over NTRU." NIST Post-Quantum Cryptography Standardization, Round 3 Submission, 2020. https://falcon-sign.info/

Gabizon, A., Williamson, Z. J., and Ciobotaru, O. "PLONK: Permutations over Lagrange-bases for Oecumenical Noninteractive arguments of Knowledge." *IACR Cryptology ePrint Archive*, 2019/953.

Gentry, C., Peikert, C., and Vaikuntanathan, V. "Trapdoors for Hard Lattices and New Cryptographic Constructions." *Proceedings of the 40th Annual ACM Symposium on Theory of Computing (STOC)*, 2008.

Gilad, Y. et al. "Algorand: Scaling Byzantine Agreements for Cryptocurrencies." *Proceedings of the 26th Symposium on Operating Systems Principles (SOSP)*, 2017.

Tinyman. "Tinyman V1.0 Vulnerability Report." January 2022. https://tinymanorg.medium.com/tinyman-v1-0-vulnerability-report-2f89e84a3e53

Algorand Technologies. "Algorand Developer Documentation." https://developer.algorand.org/
