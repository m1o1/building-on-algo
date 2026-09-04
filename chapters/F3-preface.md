\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Preface {-}

This book takes a senior software engineer from zero smart contract knowledge to deploying production-quality *DeFi* (decentralized finance, the ecosystem of financial applications built on blockchains instead of banks) applications on Algorand. It uses **[Algorand Python](https://dev.algorand.co/concepts/smart-contracts/languages/python/) (Puya)**, the newest and most idiomatic approach: real Python code that compiles to TEAL bytecode via a multi-stage optimizing compiler.

## Who This Book Is For {-}

This book is written for experienced software engineers who know Python well but have never built a smart contract. You should be comfortable with modern Python: type annotations, classes, decorators, and virtual environments. Basic command-line tooling and Docker are assumed as well. The walkthroughs are validated on Python 3.12. The learning curve here is blockchain concepts and AVM constraints, not the programming language.

This book is *not* for you if you are looking for Solidity or EVM development (Algorand's execution model is fundamentally different), or if you want a theory-only treatment of blockchain concepts without building working software.

## How This Book Is Organized {-}

The book is twenty-four chapters in seven parts, alternating between two kinds of chapter. A *concept chapter* takes one thing a decentralized application needs (somewhere to remember a number, somewhere to put data that grows, a way to move value) and works through several small, complete, runnable examples of it. A *project chapter* then spends those concepts on one program you build end to end. Nothing is introduced before the chapter that needs it.

**Part I** is the on-ramp: the toolchain, then the machine, one mechanism at a time.

- **Chapter 1 --- From Zero to Deployed.** An empty directory to a deployed, tested contract: the toolchain, LocalNet, the five-step loop every later chapter assumes, and three habits for when a step refuses.

- **Chapter 2 --- The Algorand Mental Model.** Smart contracts are transaction validators, not running processes: the execution model, the account system, and the constraints every developer has to internalize, taught as the diagnosis of a contract you build and break.

- **Chapter 3 --- Contracts That Exist and Respond.** What it takes for a contract to exist at all: creation, the OnCompletes that describe its lifecycle, the router that decides which method a call reaches, and the upgrade and delete authority you are choosing whether to keep.

- **Chapter 4 --- Remembering Things: Global and Local State.** The two fixed-size slabs a contract can write to, what each costs, who can destroy which, and why the schema you declare at creation is the one you are stuck with.

- **Chapter 5 --- Data That Grows: Box Storage.** Storage without a ceiling, priced per byte and paid for out of the contract's own balance. Box keys, the minimum balance arithmetic behind them, and what happens to a contract whose floor rises under it.

- **Chapter 6 --- Arithmetic That Refuses: Numbers and Time.** Integer math that reverts rather than wrapping, the ordering of operations that keeps precision, and the four different values on Algorand that all look like "now" and are not.

- **Chapter 7 --- Moving Value: Assets, Payments, and Groups.** The first point at which a contract sends rather than computes: inner transactions, grouped payments, asset opt-in and transfer, and who pays the fees.

- **Chapter 8 --- Proving It Works: Tests, Simulation, and Failure.** Assert messages that survive compilation, `simulate` as the read-only execution path, and tests arranged so that some state of the world actually turns them red. The testing patterns here are used for the rest of the book.

**Part II** puts value under management: the first full project, then who may call a contract and what a call costs, then a project that makes those permissions transferable.

- **Chapter 9 --- A Token Vesting Contract.** The first full project, built as the delta from Chapter 8's contract and spending every concept in Part I at once: state, ASA handling, inner transactions, box storage, integer math, and the security patterns that keep them honest.

- **Chapter 10 --- Proving Who's Calling.** Who is asking, and how a contract decides: `Txn.sender` and what it does and does not prove, the creator and the accounts a contract trusts, roles held in state, and the difference between a caller who signed and a contract that called.

- **Chapter 11 --- Paying For It: Minimum Balance, Fees, and Budget.** The costs the earlier chapters deferred, all due at once: the minimum balance and who is billed for which part of it, fee pooling, the opcode budget, and the reference lists that decide what a transaction may touch at all.

- **Chapter 12 --- NFTs: Extending the Vesting Contract with Transferability.** You extend the vesting contract by minting an NFT for each schedule, which introduces the ownership-by-asset pattern, ARC-3 metadata, clawback mechanics, and the mint-then-deliver coordination problem.

**Part III** builds one decentralized exchange, with the arithmetic and the composition it runs on.

- **Chapter 13 --- Numbers That Price Things.** The constant-product curve and the price it implies: why the invariant is what a swap preserves rather than a balance, how a fee changes it, what rounding does to a pool over many trades, and the accumulator behind a time-weighted price.

- **Chapter 14 --- A Constant Product AMM.** A Uniswap V2-style automated market maker: multi-token accounting, the price curve and the slippage it implies, LP (liquidity provider) token mechanics, a TWAP price oracle, and security hardening.

- **Chapter 15 --- Contracts That Talk to Contracts.** Your contract as the caller: reaching another application by method or by signature string, reading its state without calling it, spawning one and paying for it, and the one question the AVM will not answer for you: whether the application id you are about to trust is the one you meant.

- **Chapter 16 --- AMM Factory and Pool Provenance.** Pool creation moves on-chain. A factory deploys pool apps, registers canonical asset pairs, and teaches downstream contracts how to reject a pool it did not create.

- **Chapter 17 --- Yield Farming: Extending the AMM with Staking Rewards.** LPs lock LP tokens to earn reward tokens, which introduces the Synthetix-style reward accumulator, duration multipliers, and contract composition through cross-contract state reads.

**Part IV** is a number a contract can act on, and the project that spends one.

- **Chapter 18 --- A Number Nobody Can Predict.** Why anything derived from a block is readable by the caller before they decide to play, what a commitment binds without revealing, and how to read a number nobody chose from a beacon and check the proof that it was computed honestly.

- **Chapter 19 --- A Lottery That Pays Out or Gives Back.** Tickets in boxes, a committed draw round, a winner chosen by a beacon nobody controls, and a refund path for the day the beacon goes silent --- run against a stub you control and a deployed beacon you do not.

**Part V** is Algorand's second execution model.

- **Chapter 20 --- Signing Without a Key.** A program that replaces a private key rather than holding state: the two ways an account can be bound to one, the guards such a program cannot ship without, and why a signed delegation cannot be cancelled.

- **Chapter 21 --- Delegated Limit Order Book with LogicSig Agents.** Logic signatures applied to a delegated limit order book: the hybrid stateful/stateless architecture, template variables, keeper bots, and composability with the AMM from Chapter 14.

**Part VI** pushes the AVM to its limits.

- **Chapter 22 --- Proving Things Without Revealing Them.** Hashes and what each costs, commitments, signatures verified against keys the chain never saw, merkle proofs, and the priced elliptic-curve primitives a zero-knowledge verifier is assembled from.

- **Chapter 23 --- Private Governance Voting with Zero-Knowledge Proofs.** A private governance vote built on zero-knowledge proofs, elliptic curve operations over BN254, and the MiMC hash. (Algorand's Falcon-based post-quantum roadmap is covered in What's Next.)

**Part VII** is the part of a contract's life that starts after it works.

- **Chapter 24 --- Shipping and Surviving.** What an operator needs and a correct contract does not supply: a log an indexer can read, an error code that survives a client with no source map, an upgrade path bounded by a one-way freeze, and a way to delete an application and get its minimum balance back.

Figure P-1 shows how those chapters depend on one another. A solid arrow means you will be lost without the earlier chapter; a dashed one means the later chapter builds on it but stands on its own. To reach one specific chapter, follow the solid arrows backwards from it.

![Figure P-1. How the chapters depend on each other. A solid arrow means you will be lost without the earlier chapter; a dashed one means the later chapter builds on it but stands alone.](figures/book-map.svg)

The concept chapters are made of small complete programs rather than fragments of a project you have not seen yet; those carrying a source annotation are complete programs in the repository, verified in their declared modes, and the annotated set is growing toward the full example list. Every project chapter ships with a directory of runnable source under `projects/`. Six are full worked builds you can type along with from start to finish; Chapters 21 and 23 are guided builds --- the page shows every load-bearing decision and one fully worked representative of each repetitive layer --- and their directories are complete, so you can run the finished system before, during or after building your own.

Each part ends with a Mastery Checkpoint: a small program the part did not show you, with a stated acceptance test and a fallback. Four appendices follow: an environment reference for when the toolchain refuses, a one-page protocol reference of every limit and cost, a consolidated list of every gotcha in the book grouped by topic, and an Example Finder that indexes every numbered example by the task it performs.

## Conventions Used in This Book {-}

The following typographic conventions are used throughout:

- *Italic* indicates new terms when they are first introduced.
- `Monospace` is used for code elements: class names, method names, variables, file paths, and command-line input/output.
- **`Bold monospace`** indicates commands or text that you should type literally.

Code examples are presented incrementally: each section adds to the contract built in previous sections. When a code block shows a complete method or class, it includes enough context (imports, class declaration) to be unambiguous about where the code belongs.

Error messages and transcripts follow fixed quoting conventions --- what is reproduced, what is shortened, and how every cut is marked. The concrete rules for reproducing a failing transcript are explained beside the first one, in Chapter 2, where you can see each against a real example rather than memorize it here. What stays below is the notation for quoting a message's *form* rather than an instance of it, because form notation appears in prose before any transcript does.

Where a sentence quotes the *form* of a message rather than an instance of it, the varying parts are named rather than filled in: `{id}` for the transaction ID and angle brackets for everything else, as in `account <address> balance <n> below min <m> (<k> assets)`. In *form* notation the braces are reserved for the transaction ID; a bracketed part may well name something you have seen filled in elsewhere. Where a transcript quotes your own source back at you, as a pytest failure report does, a test body shown as Python's own `...` is that body omitted, not the tool's output cut. Prose that merely names a message quotes the message and nothing else, so a shorter form later in the book is a shorter *quotation* and never a correction of a longer one. Quotation marks inside a monospace span are always part of the code rather than the book's punctuation around it: they mark a string literal you would type, as `"require"` does where a method argument is meant and `"Slippage exceeded"` does inside an assertion, and a message the tool printed never carries them.

Boxed asides come in exactly eight kinds, and each kind always means the same thing. **Note** adds context you can read or skip. **Tip** offers a shortcut or a better habit. **Warning** marks something that can cost you funds or silently corrupt state; do not skip these. **Gotcha** marks a behavior that reliably surprises people the first time, and every one of them is collected in Appendix C. **Setup** covers environment and tooling prerequisites rather than contract behavior. **Your commission** opens every concept chapter with the build's requirements --- the list the chapter's ending is checked against. **Check your understanding** asks you to predict or explain before reading on. **Try it yourself** hands you something to go and run. The last three are part of the teaching sequence rather than supplementary material.

::: {.note}
Admonitions like this one provide supplementary information, tips, or context that is useful but not essential to following the main narrative.
:::

Notes and warnings appear throughout the book.

::: {.warning}
Warning admonitions highlight security concerns, common mistakes, or behavior that could cause loss of funds in a production contract. Do not skip these.
:::

Client-side code uses **typed generated clients** throughout: `algokit generate client` turns a compiled contract's ARC-56 specification into a Python class with one typed method per ABI method, and that class --- built for you by `algokit project run build` --- is what every deployment script and test in this book calls. The *generic* client (method names as strings) appears only where no generated client can exist, such as connecting to a contract you did not build (Appendix A), and **raw algosdk** appears only where field-level control over a transaction is itself the lesson --- the LogicSig-authorized groups of Chapters 20 and 21 --- and is labeled as the exception where it does.

## Using Code Examples {-}

All contract code in this book is Algorand Python targeting AVM v13, compiled
and run on LocalNet with the toolchain versions listed at the end of this
section. Every listing you are meant to learn from is a *numbered example*.
Where a numbered example carries a source annotation, it corresponds to a
complete program under `examples/` and declares how the repository's harness
verifies it --- compiled, expected-to-fail, byte-compiled, unit-tested, or run
end to end; the annotated set is growing toward the full example list, and
`validation/manifest.json` names the commands that enforce it. Everything else
on a page is either a fragment of the running build (the prose names the file
it belongs to) or tool output you are meant to read, never type.

You are free to use the code examples in your own projects; no special
permission is required.

This book pins a dated, validated baseline toolchain. As of September 4, 2026, the examples were reviewed against:

- AlgoKit CLI v2.10.2
- PuyaPy compiler v5.10.1
- `algorand-python` v4.0.0
- `algokit-utils` v4.2.3
- `algorand-python-testing` v1.1.0
- AVM version 13 (consensus v42; go-algorand 5.0.1)

Newer patch or minor releases may work, but this list is the last validated baseline, not the latest. Avoid prerelease package lines unless you also rerun the affected chapter walkthroughs and tests.

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
Where a numbered example carries a source annotation, it corresponds to a
file under `examples/` that the harness verifies in its declared mode, so
quoting the example's number tells us which file to look at; for the rest,
quote the chapter and section.

Corrections and improvements are welcome as pull requests. Before opening one,
run `uv run --group test python -m pytest tests -q` and
`uv run --group compile python scripts/compile_examples.py` from the
repository root; those are the suites CI runs, so a clean local run means a
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
chapter like Chapter 2 possible at all: a decade ago the same
material would have opened with half a chapter of environment plumbing.

The Algorand developer community answered questions in public that this book
now answers again in print. Discussions on the Algorand Discord and the
Foundation's forum shaped several sections, particularly the treatment of
opcode budget pooling in Chapter 11 and the LogicSig safety checklist in
Chapter 21, both of which began as answers to questions somebody
else had already asked well.

Finally, this book was produced with the assistance of Claude, an AI system
built by Anthropic, working under human direction. The Legal Notice preceding
this preface sets out what that means for you as a reader and what it obliges
you to verify independently.
