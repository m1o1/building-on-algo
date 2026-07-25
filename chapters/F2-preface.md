\newpage

# Preface {-}

This book takes a senior software engineer from zero smart contract knowledge to deploying production-quality *DeFi* (decentralized finance, the ecosystem of financial applications built on blockchains instead of banks) applications on Algorand. It uses **[Algorand Python](https://dev.algorand.co/concepts/smart-contracts/languages/python/) (Puya)**, the newest and most idiomatic approach --- real Python code that compiles to TEAL bytecode via a multi-stage optimizing compiler.

## Who This Book Is For {-}

This book is written for experienced software engineers who know Python well but have never built a smart contract.

You should be comfortable with modern Python: type annotations, classes, decorators, and virtual environments.

The walkthroughs are validated on Python 3.12. You should also be comfortable with basic command-line tooling and Docker.

The projects assume you can read and write Python fluently --- the learning curve here is blockchain concepts and AVM constraints, not the programming language.

This book is *not* for you if you are looking for Solidity or EVM development (Algorand's execution model is fundamentally different), or if you want a theory-only treatment of blockchain concepts without building working software.

## How This Book Is Organized {-}

The book is structured around ten progressively complex chapters, each built incrementally so that every concept is introduced at the moment you need it:

- **{{ch:mental-model}} --- The Algorand Mental Model.** The execution model, account system, and constraints every developer must internalize, plus setting up your development environment and deploying your first contract.

- **{{ch:testing}} --- Testing Smart Contracts.** You build a simplified vesting contract, write comprehensive tests against it, and discover through failing tests exactly what the full implementation in {{ch:token-vesting}} must solve. This chapter establishes the testing patterns used throughout the rest of the book.

- **{{ch:token-vesting}} --- A Token Vesting Contract.** A complete token vesting contract that introduces every foundational concept: state management, ASA handling, inner transactions, box storage, integer math, and security patterns. By the end of {{ch:token-vesting}} you can build and deploy a production-quality smart contract from scratch.

- **{{ch:nfts}} --- NFTs --- Extending the Vesting Contract with Transferability.** You extend the vesting contract by minting an NFT for each schedule, introducing the ownership-by-asset pattern, ARC-3 metadata, clawback mechanics, and the mint-then-deliver coordination pattern.

- **{{ch:amm}} --- Project 2: A Constant Product AMM.** You apply the foundations to DeFi by building a Uniswap V2-style automated market maker with multi-token accounting, price curves, LP (liquidity provider) token mechanics, a TWAP price oracle, and security hardening.

- **{{ch:amm-factory}} --- AMM Factory and Pool Provenance.** You move AMM pool creation on-chain with a factory contract that deploys pool apps, registers canonical asset pairs, and teaches downstream contracts how to reject fake or unregistered pools.

- **{{ch:yield-farming}} --- Yield Farming: Extending the AMM with Staking Rewards.** You extend the AMM with a staking contract where LPs lock LP tokens to earn reward tokens, introducing the Synthetix-style reward accumulator pattern, duration multipliers, and smart contract composition via cross-contract state reads.

- **{{ch:patterns}} --- Common Patterns and Idioms.** A patterns chapter covers cross-cutting production concerns: fee subsidization, MBR lifecycle, canonical ordering, event emission, and opcode budget management.

- **{{ch:limit-order-book}} --- Project 3: A Delegated Limit Order Book with LogicSig Agents.** Algorand's second execution model --- Logic Signatures --- applied to a delegated limit order book. This introduces the hybrid stateful/stateless architecture, template variables, keeper bots, packed binary data, and composability with the AMM from {{ch:amm}}.

- **{{ch:zk-voting}} --- Project 4: Private Governance Voting with Zero-Knowledge Proofs.** Pushing the AVM to its limits with a private governance voting system using zero-knowledge proofs, elliptic curve operations (BN254), and the MiMC hash. Also covers Algorand's Falcon-based post-quantum security roadmap.

The chapters are also deliberately scaffolded. Chapters {{chn:testing}} through {{chn:yield-farming}} are full worked projects: every listing is complete, and you can type along from start to finish. {{ch:patterns}} shifts to a patterns reference that consolidates what the projects taught. Chapters {{chn:limit-order-book}} and {{chn:zk-voting}} are guided outlines --- the core contracts are complete and compilable, but helper functions and integration layers are deliberately left for you to implement, because by that point you have built everything they require. The training wheels come off gradually, on purpose.

Two appendices provide lasting reference value: the **Algorand Smart Contract Cookbook** contains 50+ standalone code examples organized by topic, and the **Consolidated Gotchas Cheat Sheet** catalogs the most common mistakes and how to avoid them.

## Conventions Used in This Book {-}

The following typographic conventions are used throughout:

- *Italic* indicates new terms when they are first introduced.
- `Monospace` is used for code elements: class names, method names, variables, file paths, and command-line input/output.
- **`Bold monospace`** indicates commands or text that you should type literally.

Code examples are presented incrementally --- each section adds to the contract built in previous sections. When a code block shows a complete method or class, it includes enough context (imports, class declaration) to be unambiguous about where the code belongs.

Boxed asides come in exactly nine kinds, and each kind always means the same thing. **Note** adds context you can read or skip. **Tip** offers a shortcut or a better habit. **Warning** marks something that can cost you funds or silently corrupt state; do not skip these. **Gotcha** marks a behavior that reliably surprises people the first time, and every one of them is collected in the gotchas appendix. **Setup** covers environment and tooling prerequisites rather than contract behavior. **How it works** goes a level below the API into what the AVM is actually doing. **Version** flags something that is true of a specific protocol or compiler version and may not be true of the next one. **Check your understanding** asks you to predict or explain before reading on. **Try it yourself** hands you something to go and run.

The last two are the ones readers skip and later wish they had not. They are part of the teaching sequence, not supplementary material: the point of predicting an answer before you read it is that being wrong is what makes the correction stick.

## Test Helpers and Client-Side Code {-}

{{ch:testing}} introduces the foundational testing setup --- pytest fixtures, reusable helpers (`advance_time`, `create_test_asa`, `fund_account`), and the integration testing patterns used throughout the book. Each subsequent chapter includes test outlines specific to its contract. The helper functions referenced in tests are straightforward wrappers around the AlgoKit Utils and algosdk calls shown in each chapter's deployment and interaction scripts. The client-side scripts in this book use the **AlgoKit Utils v4 API** --- `AppFactory` for deployment, `app_client.send.call()` for method invocations, and `algorand.send.*` for standalone transactions. For production projects, you can also generate **typed clients** via `algokit generate client` (see Cookbook recipe 16.3) for compile-time type safety.

::: {.note}
Admonitions like this one provide supplementary information, tips, or context that is useful but not essential to following the main narrative.
:::

Both types appear throughout the book.

::: {.warning}
Warning admonitions highlight security concerns, common mistakes, or behavior that could cause loss of funds in a production contract. Do not skip these.
:::

Client-side code uses two styles: **AlgoKit Utils v4** (`AlgorandClient`, `AppFactory`, `app_client.send.call(...)`) for deployment and ABI interactions, and **raw algosdk** (`transaction.PaymentTxn(...)`, `calculate_group_id(...)`) for atomic groups requiring fine-grained control over transaction fields (such as LogicSig-authorized transactions). Both are shown because production Algorand development uses both.

## Using Code Examples {-}

All contract code in this book is Algorand Python targeting AVM v12. Complete
project listings and runnable scripts are intended to compile and run on
LocalNet using the toolchain versions listed at the end of this section. Shorter snippets have a
specific role in the teaching sequence:

- **Complete listing** means the block is intended to be copied into the named
  file after completing the preceding steps.
- **Fragment** means the block belongs inside the surrounding class, function,
  or script already under construction.
- **Outline** means the block shows the structure of a test or client workflow;
  project-specific helpers are placeholders that you implement using the
  deployment and interaction patterns already shown.
- **Illustrative example** means the block is intentionally explanatory rather
  than a complete project listing; it is labeled in the surrounding prose.

You are free to use the code examples in your own projects --- no special
permission is required.

This book pins a dated, validated baseline toolchain rather than trying to track every new package release. As of July 24, 2026, the examples were reviewed against:

- AlgoKit CLI v2.10.2
- PuyaPy compiler v5.9.0
- `algorand-python` v3.5.1
- `algokit-utils` v4.2.3
- `algorand-python-testing` v1.1.0
- AVM version 12

Newer patch or minor releases may work, but treat this list as the last validated baseline, not a promise that it is always the latest. Avoid prerelease package lines unless you also rerun the affected chapter walkthroughs and tests.

After `algokit project bootstrap all`, check the generated project dependencies against this baseline; proceed with newer stable versions if they work, and return to the baseline first when a walkthrough behaves differently from the text.

## How to Contact Us {-}

The book's source, the example programs, and the continuous-integration
workflow that compiles them all live in one repository:

<https://github.com/m1o1/building-on-algo>

The HTML edition is published from that same source at
<https://m1o1.github.io/building-on-algo/>, so it is never out of step with the
PDF.

If an example does not compile, a command does not behave as described, or a
protocol detail has moved on since the baseline above, please open an issue at
<https://github.com/m1o1/building-on-algo/issues>. Two things make a report
easy to act on: the exact command you ran with its full output, and the
versions reported by `algokit --version` and `pip show puyapy algorand-python`.
Every numbered example in this book corresponds to a file under `examples/`
that CI compiles on every commit, so quoting the example's number tells us
precisely which file to look at.

Corrections and improvements are welcome as pull requests. Before opening one,
run `python scripts/validate.py --all --structure --examples` from the
repository root; that is the same suite CI runs, so a clean local run means a
clean check on the pull request.

::: {.warning}
Please do not report suspected vulnerabilities in deployed Algorand software
through this repository. The contracts here are teaching material and are not
deployed anywhere. Issues affecting Algorand itself belong with the Algorand
Foundation's security process at <https://github.com/algorand/go-algorand/security>.
:::

## Acknowledgments {-}

This book stands on documentation and source code written by other people. The
Algorand Foundation's developer portal, the `go-algorand` node implementation,
and the PuyaPy compiler repository were the primary references throughout; where
the documentation and the source disagreed, the source won, and several
explanations in this book exist only because the compiler's own test suite
showed what the prose had left out. The AlgoKit team's work is what makes a
chapter like {{ch:mental-model}} possible at all --- a decade ago the same
material would have opened with half a chapter of environment plumbing.

The Algorand developer community answered questions in public that this book
now answers again in print. Discussions on the Algorand Discord and the
Foundation's forum shaped several sections, particularly the treatment of
opcode budget pooling in {{ch:patterns}} and the LogicSig safety checklist in
{{ch:limit-order-book}}, both of which began as answers to questions somebody
else had already asked well.

Finally, this book was produced with the assistance of Claude, an AI system
built by Anthropic, working under human direction. The Legal Notice preceding
this preface sets out what that means for you as a reader and what it obliges
you to verify independently. It is not a disclaimer to skim.
