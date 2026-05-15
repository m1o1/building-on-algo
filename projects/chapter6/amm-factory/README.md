# AMM Factory

This project is the finished example for Chapter 6 of *Building on Algorand*.
It extends the Chapter 5 AMM with an on-chain factory that creates pools,
records the canonical pool for each ordered asset pair, and rejects fake or
unregistered pools.

## Run

Prerequisites:

- AlgoKit
- Python 3.12 or 3.13
- Poetry, installed by `algokit project bootstrap all` if it is not already
  present
- Docker or Podman for LocalNet

The project is self-contained. It reuses the Chapter 5 AMM ideas, but it does
not import Chapter 5 generated clients or artifacts.

```bash
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_amm_factory
algokit project run test
```

The workflow creates two test ASAs, deploys the factory, asks the factory to
create and bootstrap a pool, verifies the pool, rejects a duplicate pair, and
shows that a directly deployed pool is not canonical.

Expected output markers:

- `Factory app ID:`
- `Factory-created pool:`
- `LP token:`
- `Factory verification accepted the registered pool.`
- `Initial LP minted:`
- `Swap output:`
- `Later LP minted:`
- `Removed liquidity:`
- `Duplicate pool creation was rejected.`
- `A directly deployed fake pool was rejected.`
