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

The book is fifteen chapters in four parts. The chapters come in two kinds and they alternate on purpose. A *concept chapter* takes one thing a decentralized application needs --- somewhere to remember a number, somewhere to put data that grows, a way to move value --- and works through several small, complete, runnable examples of it. A *project chapter* then spends the concepts on one program you build end to end. Nothing is introduced before the chapter that needs it.

**{{part:foundations}}** is the on-ramp and the first two projects.

- **{{ch:mental-model}} --- The Algorand Mental Model.** The execution model, the account system, and the constraints every developer has to internalize, plus setting up a development environment and deploying a first contract.

- **{{ch:contracts}} --- Contracts That Exist and Respond.** What it takes for a contract to exist at all: creation, the OnCompletes that describe its lifecycle, the router that decides which method a call reaches, and the upgrade and delete authority you are choosing whether to keep.

- **{{ch:state}} --- Remembering Things: Global and Local State.** The two fixed-size slabs a contract can write to, what each costs, who can destroy which, and why the schema you declare at creation is the one you are stuck with.

- **{{ch:boxes}} --- Data That Grows: Box Storage.** Storage without a ceiling, priced per byte and paid for out of the contract's own balance. Box keys, the minimum balance arithmetic behind them, and what happens to a contract whose floor rises under it.

- **{{ch:numbers-and-time}} --- Arithmetic That Refuses: Numbers and Time.** Integer math that reverts rather than wrapping, the ordering of operations that keeps precision, and the four different values on Algorand that all look like "now" and are not.

- **{{ch:moving-value}} --- Moving Value: Assets, Payments, and Groups.** The first point at which a contract sends rather than computes: inner transactions, grouped payments, asset opt-in and transfer, and who pays the fees.

- **{{ch:testing}} --- Proving It Works: Tests, Simulation, and Failure.** Assert messages that survive compilation, `simulate` as the read-only execution path, and tests arranged so that some arrangement of the world actually turns them red. The testing patterns here are used for the rest of the book.

- **{{ch:token-vesting}} --- A Token Vesting Contract.** The first full project, and the one that spends every concept above at once: state, ASA handling, inner transactions, box storage, integer math, and the security patterns that keep them honest.

- **{{ch:nfts}} --- NFTs: Extending the Vesting Contract with Transferability.** You extend the vesting contract by minting an NFT for each schedule, which introduces the ownership-by-asset pattern, ARC-3 metadata, clawback mechanics, and the mint-then-deliver coordination problem.

**{{part:dex}}** builds one decentralized exchange across three chapters and then consolidates what they taught.

- **{{ch:amm}} --- A Constant Product AMM.** A Uniswap V2-style automated market maker: multi-token accounting, the price curve and the slippage it implies, LP (liquidity provider) token mechanics, a TWAP price oracle, and security hardening.

- **{{ch:amm-factory}} --- AMM Factory and Pool Provenance.** Pool creation moves on-chain. A factory deploys pool apps, registers canonical asset pairs, and teaches downstream contracts how to reject a pool it did not create.

- **{{ch:yield-farming}} --- Yield Farming: Extending the AMM with Staking Rewards.** LPs lock LP tokens to earn reward tokens, which introduces the Synthetix-style reward accumulator, duration multipliers, and contract composition through cross-contract state reads.

- **{{ch:patterns}} --- Common Patterns and Idioms.** The cross-cutting production concerns the projects kept running into: fee subsidization, MBR lifecycle, canonical ordering, event emission, and opcode budget management.

**{{part:logicsigs}}** is Algorand's second execution model.

- **{{ch:limit-order-book}} --- Delegated Limit Order Book with LogicSig Agents.** Logic signatures applied to a delegated limit order book: the hybrid stateful/stateless architecture, template variables, keeper bots, packed binary data, and composability with the AMM from {{ch:amm}}.

**{{part:cryptography}}** pushes the AVM to its limits.

- **{{ch:zk-voting}} --- Private Governance Voting with Zero-Knowledge Proofs.** A private governance vote built on zero-knowledge proofs, elliptic curve operations over BN254, and the MiMC hash, closing with Algorand's Falcon-based post-quantum roadmap.
{{fig:book-map}} shows how those chapters depend on one another. A solid arrow means you will be lost without the earlier chapter; a dashed one means the later chapter builds on it but stands on its own. If you are here for one specific thing, follow the solid arrows backwards from it and read only those.

{{include-fig:book-map}}

The chapters are also deliberately scaffolded. The seven concept chapters, {{chn:mental-model}} through {{chn:testing}}, are made of small complete programs: every one of them compiles, deploys and runs on its own, and none of them is a fragment of a larger project you have not seen yet. Chapters {{chn:token-vesting}} through {{chn:yield-farming}} are full worked projects with a directory of source beside them, and you can type along from start to finish. {{ch:patterns}} shifts to a reference that consolidates what the projects taught. Chapters {{chn:limit-order-book}} and {{chn:zk-voting}} are guided outlines --- the core contracts are complete and compilable, but helper functions and integration layers are left for you, because by that point you have built everything they require. The training wheels come off gradually, on purpose.

Two appendices provide lasting reference value: the **Algorand Smart Contract Cookbook** contains 50+ standalone code examples organized by topic, and the **Consolidated Gotchas Cheat Sheet** catalogs the most common mistakes and how to avoid them.

## Conventions Used in This Book {-}

The following typographic conventions are used throughout:

- *Italic* indicates new terms when they are first introduced.
- `Monospace` is used for code elements: class names, method names, variables, file paths, and command-line input/output.
- **`Bold monospace`** indicates commands or text that you should type literally.

Code examples are presented incrementally --- each section adds to the contract built in previous sections. When a code block shows a complete method or class, it includes enough context (imports, class declaration) to be unambiguous about where the code belongs.

Error messages are quoted at the depth the sentence needs. A fenced transcript reproduces what the tool actually printed, wrapper and all --- algod prefixes a failing application call with `transaction {id}: logic eval error: ` and appends a tail beginning `. Details:`, and Python's `LogicError` strips both and keeps the middle. Nothing is ever cut from inside a quoted error message without a mark at the place it was cut; a transcript begins at the exception line, and neither the Python traceback frames above it nor any chained exception line is reproduced. An inline `...` shortens one value and keeps enough of it to identify: a transaction ID appears as `TFWY...J4A`, an address as `KRT4...5DVQ`, and an oversized structured field keeps its braces and loses its interior, as `data {...}`. A trailing `...` with nothing after it promises no particular value at all --- either the value differs for every reader, as the hex in `invalid Box reference 0x...` does, or the quotation stops inside a field whose remainder is not what the sentence is about, as `opcodes=...` does. The generated TEAL an exception prints below its message is elided under one marker line inside the fence, always spelled `... 10 lines of TEAL trace ...` and indented to sit under the message.

Where a sentence quotes the *form* of a message rather than an instance of it, the varying parts are named rather than filled in: `{id}` for the transaction ID, which you have already met in its elided form, and angle brackets for everything else --- `account <address> balance <n> below min <m> (<k> assets)`. In *form* notation the braces are reserved for the transaction ID; a bracketed part may well name something you have seen filled in elsewhere. Where a transcript quotes your own source back at you, as a pytest failure report does, a test body shown as Python's own `...` is that body omitted, not the tool's output cut. Prose that merely names a message quotes the message and nothing else, so a shorter form later in the book is a shorter *quotation* and never a correction of a longer one. Quotation marks inside a monospace span are therefore always part of the code rather than the book's punctuation around it: they mark a string literal you would type, as `"require"` does where a method argument is meant and `"Slippage exceeded"` does inside an assertion, and a message the tool printed never carries them.

Boxed asides come in exactly nine kinds, and each kind always means the same thing. **Note** adds context you can read or skip. **Tip** offers a shortcut or a better habit. **Warning** marks something that can cost you funds or silently corrupt state; do not skip these. **Gotcha** marks a behavior that reliably surprises people the first time, and every one of them is collected in the gotchas appendix. **Setup** covers environment and tooling prerequisites rather than contract behavior. **How it works** goes a level below the API into what the AVM is actually doing. **Version** flags something that is true of a specific protocol or compiler version and may not be true of the next one. **Check your understanding** asks you to predict or explain before reading on. **Try it yourself** hands you something to go and run.

The last two are the ones readers skip and later wish they had not. They are part of the teaching sequence, not supplementary material: the point of predicting an answer before you read it is that being wrong is what makes the correction stick.

::: {.note}
Admonitions like this one provide supplementary information, tips, or context that is useful but not essential to following the main narrative.
:::

Both types appear throughout the book.

::: {.warning}
Warning admonitions highlight security concerns, common mistakes, or behavior that could cause loss of funds in a production contract. Do not skip these.
:::

Client-side code uses two styles: **AlgoKit Utils v4** (`AlgorandClient`, `AppFactory`, `app_client.send.call(...)`) for deployment and ABI interactions, and **raw algosdk** (`transaction.PaymentTxn(...)`, `calculate_group_id(...)`) for atomic groups requiring fine-grained control over transaction fields (such as LogicSig-authorized transactions). Both are shown because production Algorand development uses both. A third style exists and this book shows it once, in {{ex:typed-client}}: `algokit generate client` turns a compiled contract's ARC-56 specification into a Python class with one typed method per ABI method, which is what you would reach for on a real project and which teaches you nothing about the wire format while you are still learning what the wire format is.

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
