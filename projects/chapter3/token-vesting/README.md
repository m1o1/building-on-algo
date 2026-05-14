# Chapter 3: A Token Vesting Contract

This is the finished project for Chapter 3 of *Building on Algorand*. It
contains the production token vesting contract from the chapter plus a LocalNet
driver. You do not need to understand every step before running it: the demo
shows the whole loop by deploying and funding the app, creating vesting
schedules, then exercising claim, revoke, and cleanup workflows with a test
Algorand Standard Asset (ASA).

Generated artifacts under `smart_contracts/artifacts/` are intentionally not
committed. Build the project before running the driver or LocalNet tests.

## Prerequisites

Required for all paths:
- Python 3.12 or 3.13
- AlgoKit 2.x
- Poetry

Required only for the LocalNet demo and LocalNet tests:
- Docker or Podman for AlgoKit LocalNet

## Run It First

From this directory:

```bash
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_token_vesting
poetry run pytest -q
```

The driver prints the generated admin, Alice, and Bob accounts, the ASA ID, the
app ID, Alice's full claim, Bob's claimable amount before revocation, Bob's
unvested amount returned to the admin, and the final cleanup messages. A
successful run ends with `Chapter 3 workflow complete`. With LocalNet running,
`poetry run pytest -q` runs both source-shape checks and LocalNet workflows.

If Docker or Podman is not available, use the compile-only path:

```bash
algokit project bootstrap all
algokit project run build
poetry run pytest tests/test_contract_shape.py -q
```

## Project Layout

- `smart_contracts/token_vesting/contract.py` contains the PuyaPy contract.
- `scripts/run_token_vesting.py` executes the full LocalNet workflow.
- `scripts/localnet_helpers.py` contains small account, ASA, funding, and box
  reference helpers used by the driver and tests.
- `tests/test_contract_shape.py` checks source-shape guards for important
  security and implementation properties without LocalNet.
- `tests/test_token_vesting.py` runs end-to-end LocalNet claim and revocation
  flows after the contract is built.
