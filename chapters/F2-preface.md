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
