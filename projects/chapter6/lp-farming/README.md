# Chapter 6: LP Farming

This is the finished Chapter 6 project from *Building on Algorand*. It gives
readers a runnable LP farming contract before they walk through the accumulator
math and composition patterns line by line.

## Run It First

This project depends on the Chapter 5 AMM because the farm binds itself to the
LP token reported by the configured AMM. Build both projects first:

```bash
cd ../../chapter5/constant-product-amm
algokit project bootstrap all
algokit project run build

cd ../../chapter6/lp-farming
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_lp_farming
poetry run pytest -q
```

The workflow script creates two pool assets and one reward asset, deploys the
Chapter 5 AMM, mints LP tokens, deploys the farm, binds it to the AMM, deposits
rewards, stakes LP tokens, claims rewards, extends the lock, advances LocalNet
dev-mode time, and unstakes.

AMM setup: pool app ID and LP token ID printed; the farm later reads that AMM
global state.

Reward deposit: 58,400 reward base units over 100 seconds, producing the
chapter's maximum safe reward rate of 584 base units per second.

Stake: the farmer sends both LP tokens and the 32,100 microAlgos box MBR payment.

Claim: a positive reward amount after the script advances dev-mode time.

Extend: the lock changes from 30 days to 365 days, increasing effective weight
for future rewards.

Unstake: LocalNet's timestamp offset moves beyond the unlock time, then the
contract returns LP tokens and refunds the 32,100 microAlgos box MBR.

If Docker or Podman is not available, LocalNet cannot start. You can still run
`algokit project run build` and `poetry run pytest -q`; the integration tests
will skip and the static tests will keep checking the contract source for the
security patterns discussed in the chapter.

If pytest reports skipped LocalNet tests, you have checked compilation and
static properties only. Start LocalNet later to verify the AMM and farm workflow.

## Reader Path

Run the workflow first. Then inspect `scripts/run_lp_farming.py` to see the
client-side order of operations and the dependency on the Chapter 5 generated
client. Use `smart_contracts/lp_farming/contract.py` as an answer key while
building the chapter step by step. Save `tests/` for the testing section, and
skip generated artifacts on first read.

## Useful Files

- `smart_contracts/lp_farming/contract.py` contains the PuyaPy farm.
- `scripts/run_lp_farming.py` runs the end-to-end LocalNet workflow.
- `scripts/localnet_helpers.py` loads both generated clients and controls
  LocalNet dev-mode time.
- `tests/test_contract_shape.py` checks source-level safety properties.
- `tests/test_lp_farming.py` exercises the deployed AMM and farm when LocalNet
  is available.
