# Chapter 4: NFT Vesting

This is the finished project for Chapter 4 of *Building on Algorand*. It
contains the transferable vesting contract from the chapter plus a LocalNet
driver. You do not need to understand every step before running it: the demo
deploys and funds the app, creates a vesting ASA, deposits tokens, mints a
vesting NFT, delivers it to a beneficiary, transfers it to a buyer, claims from
both holders, revokes a second schedule, and cleans up settled boxes.

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
poetry run python -m scripts.run_nft_vesting
poetry run pytest -q
```

The driver prints the generated admin, beneficiary, and buyer accounts, the
vesting ASA ID, the app ID, both minted NFT IDs, claim amounts before and after
the NFT transfer, revocation settlement details, and cleanup messages. A
successful run ends with `Chapter 4 workflow complete`. With LocalNet running,
`poetry run pytest -q` runs both static source checks and LocalNet workflows.

If Docker or Podman is not available, use the compile-only path:

```bash
algokit project bootstrap all
algokit project run build
poetry run pytest tests/test_contract_shape.py -q
```

These are static source checks. They confirm that the expected contract guards and
source patterns are present; the LocalNet driver and full test suite provide behavioral
confirmation.

## Project Layout

- `smart_contracts/nft_vesting/contract.py` contains the PuyaPy contract.
- `scripts/run_nft_vesting.py` executes the full LocalNet workflow.
- `scripts/localnet_helpers.py` contains account, ASA, funding, time, transfer,
  and box-reference helpers used by the driver and tests.
- `tests/test_contract_shape.py` runs static source checks for important security
  and implementation patterns without LocalNet.
- `tests/test_nft_vesting.py` runs end-to-end LocalNet NFT claim, transfer,
  revocation, and cleanup flows after the contract is built.
