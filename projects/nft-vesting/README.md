# Chapter 12: NFT Vesting

This is the finished project for Chapter 12 of *Building on Algorand*. It
contains the transferable vesting contract from the chapter plus a LocalNet
runbook and development shortcut. You do not need to understand every contract
line before trying it: the runbook deploys and funds the app, creates a vesting
ASA, deposits tokens, mints a vesting NFT, delivers it to a beneficiary,
transfers it to a buyer, claims from both holders, revokes a second schedule,
and cleans up settled boxes.

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

The chapter walks through the specific lines in `scripts/run_nft_vesting.py`.
In summary, that script:

- creates and funds admin, beneficiary, and buyer
- creates the vesting ASA
- deploys, funds, and initializes the app
- deposits vesting tokens
- pays the combined schedule-box and NFT MBR before `create_schedule`
- delivers the NFT, transfers it to a buyer, and claims from both holders
- revokes a second schedule and cleans up both settled boxes

```bash
poetry run python -m scripts.run_nft_vesting
algokit project run test
```

With LocalNet running, `algokit project run test` runs both static source checks and
LocalNet workflows.

If Docker or Podman is not available, use the static path:

```bash
algokit project bootstrap all
algokit project run build
algokit project run test-static
```

These are static source checks. They confirm that the expected contract guards
and source patterns are present; the LocalNet workflow and full test suite
provide behavioral confirmation.

`scripts/run_nft_vesting.py` is retained as a development shortcut for the
line-by-line workflow explained in the chapter.

## Project Layout

- `smart_contracts/nft_vesting/contract.py` contains the PuyaPy contract.
- `scripts/run_nft_vesting.py` is a convenience shortcut for the runbook.
- `scripts/localnet_helpers.py` contains account, ASA, funding, time, transfer,
  and box-reference helpers used by the shortcut script and tests.
- `tests/test_contract_shape.py` runs static source checks for important security
  and implementation patterns without LocalNet.
- `tests/test_nft_vesting.py` runs end-to-end LocalNet NFT claim, transfer,
  revocation, and cleanup flows after the contract is built.
