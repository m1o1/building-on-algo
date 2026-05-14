# Simple Vesting

This is the completed Chapter 2 integration-test project from *Building on Algorand*. It intentionally preserves the simplified `SimpleVesting` contract from the chapter: one beneficiary, global-state storage, plain `UInt64` vesting math, and no revoke method.

## Prerequisites

- Python 3.12 or 3.13. The project is pinned to `<3.14` because one transitive dependency currently fails to build cleanly on Python 3.14.
- AlgoKit CLI 2.10 or later.
- Poetry, installed by `algokit project bootstrap all` if it is not already present.
- Docker or Podman for LocalNet.

If Poetry chooses the wrong interpreter, set it explicitly before bootstrapping:

```bash
poetry env use 3.12
```

## Run It First

Before running, predict three things: why the pre-cliff claim returns `0`, why the contract account must opt into the ASA before the deposit, and which limitations the tests document.

Full LocalNet demo:

```bash
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_simple_vesting
poetry run pytest -q
```

The workflow script deploys `SimpleVesting`, creates a test ASA, funds a beneficiary, opts the beneficiary and contract into the asset, atomically deposits tokens while initializing the vesting schedule, attempts a claim before the cliff, advances LocalNet time, and claims the fully vested amount.

Expected output shape:

```text
1. Deploy SimpleVesting
   app id: <localnet app id>
   app address: <application address>
2. Create a test ASA
   asset id: <localnet asset id>
3. Funded beneficiary: <address>
4. Fund, opt in, deposit, and initialize the vesting schedule
5. Claim before cliff returned: 0
6. Advance past full vesting
7. Final claim returned: 1000000
8. Beneficiary ASA balance: 1000000
```

No Docker or LocalNet yet? You can still build the contract and run the static known-gap checks:

```bash
algokit project bootstrap all
algokit project run build
poetry run pytest tests/test_simple_vesting_gaps.py -q
```

## Tests

The full pytest suite is expected to pass. It includes:

- LocalNet integration tests for deploy, initialize, claim, and rejected operations.
- Static known-gap checks documenting three production limitations: overflow-prone arithmetic, one-beneficiary global state, and no revoke method.

The chapter discusses a fourth limitation, rounding across multiple claims, in the step-by-step "Tests That Fail" section. The static gap tests are documentation tests: they pass because they prove the simplified contract is intentionally limited, not because it is production-ready.

## Project Layout

- `smart_contracts/simple_vesting/contract.py` contains the Chapter 2 contract.
- `scripts/run_simple_vesting.py` runs the complete LocalNet user workflow.
- `scripts/localnet_helpers.py` contains shared deploy, funding, opt-in, and time helpers.
- `tests/test_simple_vesting.py` contains LocalNet integration tests.
- `tests/test_simple_vesting_gaps.py` contains static known-gap checks.

Build artifacts are generated under `smart_contracts/artifacts/` by `algokit project run build` and are intentionally not committed.
