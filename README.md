<p align="center">
  <img src="building-on-algo.jpg" alt="Building on Algorand" width="400" />
</p>

# Building on Algorand

**Smart Contracts from First Principles to Production DeFi**

[**Read the book online**](https://m1o1.github.io/building-on-algo/)

Twenty-two chapters in seven parts. Concept chapters teach one mechanism
against a commission you build; project chapters assemble the mechanisms into
something you would actually ship; each part ends with a Mastery Checkpoint —
a novel build with an acceptance list and no walkthrough. Part V is a pointer
to companion material rather than a course. Chapters 21 and 23 are unused on
this spine: delegated LogicSigs and private governance voting live under
`advanced/`.

**Part I — Foundations**
1. [From Zero to Deployed](https://m1o1.github.io/building-on-algo/01-from-zero-to-deployed.html)
2. [The Algorand Mental Model](https://m1o1.github.io/building-on-algo/02-the-algorand-mental-model.html)
3. [Contracts That Exist and Respond](https://m1o1.github.io/building-on-algo/03-contracts-that-exist-and-respond.html)
4. [Remembering Things](https://m1o1.github.io/building-on-algo/04-remembering-things.html)
5. [Data That Grows](https://m1o1.github.io/building-on-algo/05-data-that-grows.html)
6. [Arithmetic That Refuses](https://m1o1.github.io/building-on-algo/06-arithmetic-that-refuses.html)
7. [Moving Value](https://m1o1.github.io/building-on-algo/07-moving-value.html)
8. [Proving It Works](https://m1o1.github.io/building-on-algo/08-proving-it-works.html)

**Part II — Value Under Management**

9. [A Token Vesting Contract](https://m1o1.github.io/building-on-algo/09-a-token-vesting-contract.html)
10. [Proving Who's Calling](https://m1o1.github.io/building-on-algo/10-proving-whos-calling.html)
11. [Paying for It](https://m1o1.github.io/building-on-algo/11-paying-for-it.html)
12. [NFT Vesting](https://m1o1.github.io/building-on-algo/12-nft-vesting.html)

**Part III — Building a DEX**

13. [Numbers That Price Things](https://m1o1.github.io/building-on-algo/13-numbers-that-price-things.html)
14. [A Constant Product AMM](https://m1o1.github.io/building-on-algo/14-a-constant-product-amm.html)
15. [Contracts That Talk to Contracts](https://m1o1.github.io/building-on-algo/15-contracts-that-talk-to-contracts.html)
16. [AMM Factory and Pool Provenance](https://m1o1.github.io/building-on-algo/16-amm-factory-and-pool-provenance.html)
17. [Yield Farming](https://m1o1.github.io/building-on-algo/17-yield-farming.html)

**Part IV — Chance**

18. [A Number Nobody Can Predict](https://m1o1.github.io/building-on-algo/18-a-number-nobody-can-predict.html)
19. [A Lottery That Pays Out or Gives Back](https://m1o1.github.io/building-on-algo/19-a-lottery-that-pays-out-or-gives-back.html)

**Part V — Further Reading**

20. [Further Reading: Logic Signatures](https://m1o1.github.io/building-on-algo/20-further-reading-logicsigs.html)

**Part VI — Cryptography**

22. [Proving Things Without Revealing Them](https://m1o1.github.io/building-on-algo/22-proving-things-without-revealing-them.html)

**Part VII — Shipping**

24. [Shipping and Surviving](https://m1o1.github.io/building-on-algo/24-shipping-and-surviving.html)

---

A hands-on guide that takes a senior software engineer from zero smart
contract knowledge to deploying production-quality DeFi applications on
Algorand. Written for developers who know Python well but have never built a
smart contract.

All contracts use **[Algorand Python (Puya)](https://dev.algorand.co/concepts/smart-contracts/languages/python/)**
— real Python code that compiles to TEAL bytecode via a multi-stage
optimizing compiler, pinned to a validated toolchain (PuyaPy 5.10.1,
algorand-python 4.0.0, AlgoKit CLI 2.10.2, AVM 13 / consensus v42).

## What You'll Build

| Project | Chapter | What it teaches |
|---------|---------|-----------------|
| **Token vesting contract** | 9 | State, ASA custody, inner transactions, box-backed schedules, floor math, a 36-test suite |
| **NFT vesting** | 12 | Ownership-by-asset, claim rights that travel with a token, ARC-28 events |
| **Constant product AMM** | 14 | Uniswap V2-style pool, LP tokens, slippage bounds, an optional TWAP oracle |
| **AMM factory** | 16 | On-chain pool creation, pair registry, provenance a stranger can verify |
| **LP farming** | 17 | Reward-per-token accumulator, lock multipliers, cross-contract reads |
| **Lottery** | 19 | ARC-21 randomness beacon, commit to a future round, pay out or refund — never strand money |
| **Shippable guestbook** | 24 | Events, error codes, pause, freeze, delete — the operability layer |

The delegated limit-order book and the private-governance vote are companion
projects under `advanced/`, not builds this spine asks you to assemble. Chapter
20 explains why delegated LogicSigs left; the end of Chapter 22 points at the
voting manuscript.

Plus four appendices: **A** the validated environment, **B** every limit and
cost on one page, **C** every gotcha in the book grouped by topic, and **D**
an example finder that maps "I need to do X" to a numbered example.
Appendices C and D are generated from the chapters themselves and
drift-checked in CI.

## Repository Layout

- `chapters/` — canonical book source (one file per chapter; the site and PDF
  are derived outputs)
- `examples/<topic>/` — standalone example programs, each carrying the mode
  (`compile`, `unit`, `script`, `localnet`) a harness verifies it in
- `projects/<name>/` — the AlgoKit projects on this spine, each with its own test
  suite and workflow script
- `advanced/` — companion material split out of the spine (LogicSig course,
  limit-order book, private governance voting). Not typeset into the main book.
- `scripts/` — build spine, drift checker, example harness, appendix
  generator
- `figures/` — hand-authored SVG diagrams

## Building Locally

### Prerequisites

- **Python 3.12** and **uv** (tests, compile checks, PDF assets)
- **mdBook** (HTML site): see the [installation guide](https://rust-lang.github.io/mdBook/guide/installation.html)
- **pandoc + XeLaTeX** (PDF): [Pandoc](https://pandoc.org/installing.html)
  plus a TeX distribution that includes XeLaTeX

### Build Commands

```bash
# Static HTML site → mdbook/book/
python3 build.py mdbook

# PDF (needs the "pdf" dependency group for SVG conversion)
uv run --group pdf python3 build.py pdf

# Reconstruct the single-file Building-on-Algorand.md
python3 build.py concat
```

### Validation Harness

```bash
# Book integrity: spine drift, cross-references, example numbering,
# generated-appendix sync
uv run --group test python -m pytest tests -q

# Structural drift checker on its own
python3 scripts/check_book.py

# Run every annotated example in its declared mode
uv run --group compile --group test python scripts/compile_examples.py
```

`validation/manifest.json` maps every promise the front matter makes to the
check that enforces it. CI (`.github/workflows/validate.yml`) runs the full
set on every push.

## Disclaimer

This book was generated with the assistance of AI (Claude, by Anthropic). The
cover image was generated with Grok (xAI). While the code has been compiled,
tested, and reviewed, it may contain errors or outdated information. **The
smart contracts are for educational purposes** — any code intended for
mainnet **must undergo a professional security audit**. See the full
[Legal Notice](https://m1o1.github.io/building-on-algo/) in the book.

## License

[MIT](LICENSE)
