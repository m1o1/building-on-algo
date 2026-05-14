# Chapter 5: Constant Product AMM

This is the finished Chapter 5 project from *Building on Algorand*. It gives
readers a runnable constant product AMM before they walk through the chapter
line by line.

## Run It First

From this directory:

```bash
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_constant_product_amm
poetry run pytest -q
```

The workflow script creates two test ASAs, deploys a pool, bootstraps it,
adds initial liquidity, executes a swap, adds liquidity from a second account,
and removes part of that second liquidity-provider (LP) position.

Bootstrap: LP token ID printed; the pool created its own ASA.

Initial liquidity: initial LP minted; first deposits set the price.

Swap: roughly 98--99 Token B for 100 Token A; fee and price impact are applied.

Second LP deposit: second LP minted; later deposits mint proportional LP tokens.

Withdrawal: two withdrawn amounts; burning LP tokens withdraws a proportional
share of both assets.

The finished contract also contains the optional TWAP oracle from the end of
the chapter. The workflow above exercises the core AMM first.

If Docker or Podman is not available, LocalNet cannot start. You can still run
`algokit project run build` and `poetry run pytest -q`; the integration tests
will skip and the static tests will keep checking the contract source for the
security patterns discussed in the chapter.

If pytest reports skipped LocalNet tests, you have checked compilation and
static properties only. Start LocalNet later to verify the actual pool workflow.

## Reader Path

Run the workflow first. Then inspect `scripts/run_constant_product_amm.py` to
see the client-side order of operations. Use
`smart_contracts/constant_product_pool/contract.py` as an answer key while
building the chapter step by step. Save `tests/` for the testing section, and
skip generated artifacts on first read.

## Useful Files

- `smart_contracts/constant_product_pool/contract.py` contains the PuyaPy AMM.
- `scripts/run_constant_product_amm.py` runs the end-to-end LocalNet workflow.
- `tests/test_contract_shape.py` checks source-level safety properties.
- `tests/test_constant_product_amm.py` exercises the deployed contract when
  LocalNet is available.
