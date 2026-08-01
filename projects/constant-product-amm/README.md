# Chapter 14: Constant Product AMM

This is the finished Chapter 14 project from *Building on Algorand*. It gives
readers a runnable constant product AMM before they walk through the chapter
line by line.

## Prerequisites

- Python 3.12 or 3.13
- AlgoKit CLI 2.10 or later
- Poetry, installed by `algokit project bootstrap all` if it is not already
  present
- Docker or Podman for LocalNet

## Run It First!

From this directory:

```bash
algokit project bootstrap all
algokit project run build
algokit localnet start
```

The chapter walks through the specific lines in
`scripts/run_constant_product_amm.py`. In summary, that script:

- creates and funds admin, trader, and second LP accounts
- creates two test ASAs and sorts their IDs
- deploys and bootstraps the pool
- opts users into the trading assets and LP token
- adds initial liquidity
- quotes and executes a swap with a minimum-output guard
- adds and removes liquidity from the second LP position

```bash
poetry run python -m scripts.run_constant_product_amm
algokit project run test
```

Watch for these checkpoints:

- **Bootstrap:** LP token ID printed; the pool created its own ASA.

- **Initial liquidity:** initial LP minted; first deposits set the price.

- **Swap:** roughly 98--99 Token B for 100 Token A; fee and price impact are
  applied. Amounts are printed in base units, so an output near `98,000,000`
  with 6 decimals means about `98` whole tokens.

- **Second LP deposit:** second LP minted; later deposits mint proportional LP
  tokens.

- **Withdrawal:** two withdrawn amounts; burning LP tokens withdraws a
  proportional share of both assets.

The finished contract also contains the optional TWAP oracle from the end of
the chapter. The workflow above exercises the core AMM first.

If Docker or Podman is not available, LocalNet cannot start. You can still run
the static path:

```bash
algokit project bootstrap all
algokit project run build
algokit project run test-static
```

Those static tests keep checking the contract source for the security patterns
discussed in the chapter.

If pytest reports skipped LocalNet tests, you have checked compilation and
static properties only. Start LocalNet later to verify the actual pool workflow.

## Reader Path

Use Run It First to trace and run the workflow, then continue through the
chapter's line-by-line build. Inspect `scripts/run_constant_product_amm.py` as
the executable transcript. Use
`smart_contracts/constant_product_pool/contract.py` as an answer key while
building the chapter step by step. Save `tests/` for the testing section, and
skip generated artifacts on first read.

## Useful Files

- `smart_contracts/constant_product_pool/contract.py` contains the PuyaPy AMM.
- `scripts/run_constant_product_amm.py` is a convenience shortcut for the
  runbook.
- `tests/test_contract_shape.py` checks source-level safety properties.
- `tests/test_constant_product_amm.py` exercises the deployed contract when
  LocalNet is available.
