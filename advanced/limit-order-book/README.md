# Companion project: Delegated Limit Order Book with LogicSig Agents

This AlgoKit project is **out of the main book spine** (issue #44). The
reader-facing book points here from Chapter 20. The preserved project
chapter is `advanced/stateless-programs/21-delegated-limit-order-book.md`.

This is the finished project that used to be Chapter 21 of *Building on Algorand*. It
contains both halves of the hybrid system the chapter builds: a stateful order
book contract that owns the shared state, and a delegated Logic Signature that
encodes one trader's order and is signed once, off chain, before it ever rests.
The off-chain keeper that turns a resting order into a trade is here too --
that is the half a limit order book cannot be demonstrated without.

Generated artifacts under `smart_contracts/artifacts/` are intentionally not
committed. Build the project before following the runbook or the LocalNet
tests.

## Prerequisites

Required for all paths:

- Python 3.12 or 3.13
- AlgoKit CLI 2.10 or later
- Poetry, installed by `algokit project bootstrap all` if it is not already
  present

Required only for the LocalNet runbook and LocalNet tests:

- Docker or Podman for AlgoKit LocalNet

## Run It First!

From this directory:

```bash
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_limit_order_book
algokit project run test
```

`scripts/run_limit_order_book.py` walks the whole lifecycle and prints the
output checkpoints of Table 21-1:

- deploys and initialises the order book, and seeds its application account
- creates a test USDC and funds Alice and a keeper
- compiles one LogicSig for one order id, has Alice sign it, and places the
  order in a two-transaction group with its box deposit
- fills 200 of the 500 as a keeper would, and shows that the sell-side
  transaction carries `lsig`, not `sig`
- lets the keeper's own polling pass close the remaining 300
- cancels an order, attempts a fill with the still-valid signature, and prints
  the line of contract source that refused
- cleans up an expired order and shows the 57,700 microAlgo deposit come back

It ends by leaving one order resting, with its signed delegation published to a
local relay file, so the keeper can also be run as its own process:

```bash
poetry run python -m scripts.keeper --passes 1
```

The same two scripts are wired as project commands: `algokit project run demo`
and `algokit project run keeper`.

If Docker or Podman is not available, use the static path:

```bash
algokit project bootstrap all
algokit project run build
algokit project run test-static
```

## Project Layout

- `smart_contracts/limit_order_book/contract.py` is the order book contract:
  order records in box storage, ARC-28 events for discovery, and the fill,
  cancel and cleanup methods.
- `smart_contracts/limit_order_lsig/contract.py` is the delegated LogicSig.
  It is compiled once at build time with `TMPL_` placeholders and once per
  order at run time with that order's values.
- `scripts/keeper.py` is the keeper: order discovery out of box storage,
  pricing, the three-transaction fill group, and the polling loop. Runnable as
  `python -m scripts.keeper`.
- `scripts/localnet_helpers.py` holds the deploy, fund, compile and sign
  plumbing shared by the runbook and the tests, plus the pc-to-source mapping
  that turns `assert failed pc=492` back into the line that refused.
- `scripts/run_limit_order_book.py` is the runbook above.
- `tests/test_contract_shape.py` checks the ABI surface, the eight-item
  LogicSig guard checklist and the keeper's arithmetic without LocalNet.
- `tests/test_limit_order_book.py` is Table 21-7: two happy paths and seven
  refusals, each asserting the specific line that refused.

## Safety

The LogicSig in this project is a *delegated* one: it spends from the trader's
own account, and there is no revoke. Every bound it will ever have is compiled
into the bytes the trader signs. Read Part 3 of the chapter before adapting it,
and keep all eight guards.

The `.localnet-keeper.json` file the runbook writes contains a LocalNet keeper
mnemonic. It is gitignored, and LocalNet accounts are worthless, but do not
copy that pattern to a network where the key is worth something.
