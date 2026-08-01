# Chapter 9: A Token Vesting Contract

This is the finished project for Chapter 9 of *Building on Algorand*. It
contains the production token vesting contract from the chapter plus a LocalNet
runbook and development shortcut. You do not need to understand every contract
line before trying it: the runbook shows the whole loop by deploying and funding
the app, creating vesting schedules, then exercising claim, revoke, and cleanup
workflows with a test Algorand Standard Asset (ASA).

Generated artifacts under `smart_contracts/artifacts/` are intentionally not
committed. Build the project before following the runbook or LocalNet tests.

## Prerequisites

Required for all paths:
- Python 3.12 or 3.13
- AlgoKit CLI 2.10 or later
- Poetry, installed by `algokit project bootstrap all` if it is not already
  present

Required only for the LocalNet demo and LocalNet tests:
- Docker or Podman for AlgoKit LocalNet

## Run It First!

From this directory:

```bash
algokit project bootstrap all
algokit project run build
algokit localnet start
```

The chapter walks through the specific lines in
`scripts/run_token_vesting.py`. In summary, that script:

- creates and funds admin, Alice, and Bob
- creates the vesting ASA
- deploys, funds, and initializes the app
- deposits vesting tokens
- creates, claims, and cleans up Alice's schedule
- creates, revokes, settles, and cleans up Bob's schedule

```bash
poetry run python -m scripts.run_token_vesting
algokit project run test
```

With LocalNet running, `algokit project run test` runs both source-shape checks and
LocalNet workflows.

If Docker or Podman is not available, use the static path:

```bash
algokit project bootstrap all
algokit project run build
algokit project run test-static
```

`scripts/run_token_vesting.py` is retained as a development shortcut for the
line-by-line workflow explained in the chapter.

## Project Layout

- `smart_contracts/token_vesting/contract.py` contains the PuyaPy contract.
- `scripts/run_token_vesting.py` is a convenience shortcut for the runbook.
- `scripts/localnet_helpers.py` contains small account, ASA, funding, and box
  reference helpers used by the shortcut script and tests.
- `tests/test_contract_shape.py` checks source-shape guards for important
  security and implementation properties without LocalNet.
- `tests/test_token_vesting.py` runs end-to-end LocalNet claim and revocation
  flows after the contract is built.
