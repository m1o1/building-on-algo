# Building on Algorand

**Smart Contracts from First Principles to Production DeFi**

[**Read the book online**](https://m1o1.github.io/building-on-algo/)

---

A hands-on guide that takes a senior software engineer from zero smart contract knowledge to deploying production-quality DeFi applications on Algorand. Written for developers who know Python well but have never built a smart contract.

All contracts use **[Algorand Python (Puya)](https://dev.algorand.co/concepts/smart-contracts/languages/python/)** — real Python code that compiles to TEAL bytecode via a multi-stage optimizing compiler.

## What You'll Build

| Chapter | Project | Concepts |
|---------|---------|----------|
| 1 | **The Algorand Mental Model** | Execution model, account system, AVM constraints, dev environment setup |
| 2 | **Token Vesting Contract** | State management, ASA handling, inner transactions, box storage, integer math, security patterns |
| 3 | **NFT Extension** | Ownership-by-asset pattern, ARC-3 metadata, clawback mechanics, simulate-then-submit |
| 4 | **Constant Product AMM** | Uniswap V2-style AMM, multi-token accounting, price curves, LP token mechanics, TWAP oracle |
| 5 | **Yield Farming** | Staking rewards, reward-per-token accumulators, time-weighted multipliers, cross-contract state reads |
| 6 | **Common Patterns & Idioms** | Fee subsidization, MBR lifecycle, canonical ordering, event emission, opcode budget management |
| 7 | **Delegated Limit Order Book** | Logic Signatures, hybrid stateful/stateless architecture, template variables, keeper bots |
| 8 | **Private Governance Voting** | Zero-knowledge proofs, elliptic curve operations (BN254), MiMC hash, post-quantum security |

Plus two appendices: a **Smart Contract Cookbook** with 50+ standalone recipes, and a **Gotchas Cheat Sheet** of common mistakes and how to avoid them.

## Reading the Book

The easiest way to read is the [online version](https://m1o1.github.io/building-on-algo/) hosted on GitHub Pages. A PDF can also be built from the build.sh script in this repository.

## Building Locally

The canonical source is `Building-on-Algorand.md`. All other formats are derived from it.

```bash
# Build the mdbook (static HTML site) → outputs to mdbook/book/
python3 build_mdbook.py

# Build the PDF (requires pandoc + xelatex)
bash build.sh
```

## Disclaimer

This book was generated with the assistance of AI (Claude, by Anthropic). While the code has been compiled, tested, and reviewed, it may contain errors or outdated information. **The smart contracts are for educational purposes** — any code intended for mainnet **must undergo a professional security audit**. See the full [Legal Notice](https://m1o1.github.io/building-on-algo/) in the book.

## License

[MIT](LICENSE)
