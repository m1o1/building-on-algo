# Chapter 6: LP Farming

This is the finished Chapter 6 project from *Building on Algorand*. It gives
readers a runnable LP farming contract before they walk through the accumulator
math and composition patterns line by line.

## Prerequisites

- Python 3.12 or 3.13
- AlgoKit CLI 2.10 or later
- Poetry, installed by `algokit project bootstrap all` if it is not already
  present
- Docker or Podman for LocalNet
- The Chapter 5 AMM project built first; Chapter 6 imports its generated client

## Run It First!

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
```

The chapter walks through the specific lines in `scripts/run_lp_farming.py`.
In summary, that script:

- creates and funds admin and farmer accounts
- creates pool and reward assets
- deploys and bootstraps the Chapter 5 AMM
- transfers LP tokens to the farmer
- deploys, funds, and initializes the farm
- deposits rewards
- stakes LP tokens with the exact `32,100` microAlgos box MBR
- advances developer-mode time, claims, extends, advances again, and unstakes

```bash
poetry run python -m scripts.run_lp_farming
algokit project run test
```

Watch for these checkpoints:

- **AMM setup:** pool app ID and LP token ID printed; the farm later reads that
  AMM global state.

- **Reward deposit:** 58,400 reward base units over 100 seconds, producing the
  chapter's maximum safe reward rate of 584 base units per second.

- **Stake:** the farmer sends both LP tokens and the 32,100 microAlgos box MBR
  payment.

- **Claim:** a positive reward amount after dev-mode time advances.

- **Extend:** the lock changes from 30 days to 365 days, increasing effective
  weight for future rewards.

- **Unstake:** LocalNet's timestamp offset moves beyond the unlock time, then
  the contract returns LP tokens and refunds the 32,100 microAlgos box MBR.

If Docker or Podman is not available, LocalNet cannot start. You can still run
the static path:

```bash
cd ../../chapter5/constant-product-amm
algokit project bootstrap all
algokit project run build

cd ../../chapter6/lp-farming
algokit project bootstrap all
algokit project run build
algokit project run test-static
```

Those static tests keep checking the contract source for the security patterns
discussed in the chapter.

If pytest reports skipped LocalNet tests, you have checked compilation and
static properties only. Start LocalNet later to verify the AMM and farm workflow.

## Reader Path

Use Run It First to trace and run the workflow, then continue through the
chapter's line-by-line build. Inspect `scripts/run_lp_farming.py` as the
executable transcript, including its dependency on the Chapter 5 generated
client. Use
`smart_contracts/lp_farming/contract.py` as an answer key while building the
chapter step by step. Save `tests/` for the testing section, and skip generated
artifacts on first read.

## Useful Files

- `smart_contracts/lp_farming/contract.py` contains the PuyaPy farm.
- `scripts/run_lp_farming.py` is a convenience shortcut for the runbook.
- `scripts/localnet_helpers.py` loads both generated clients and controls
  LocalNet dev-mode time.
- `tests/test_contract_shape.py` checks source-level safety properties.
- `tests/test_lp_farming.py` exercises the deployed AMM and farm when LocalNet
  is available.
