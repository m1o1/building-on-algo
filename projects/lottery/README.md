# A Lottery That Pays Out or Gives Back

This is the finished lottery project from *Building on Algorand*. It is a
lottery: entrants pay in and get a box each, the operator commits to a round
that does not exist yet, and once that round has passed anyone can ask an
ARC-21 randomness beacon what it published and pay the pot to whoever that
value picks.

The interesting half is the ending nobody plans for. A beacon is somebody
else's application, and if it never publishes for the round you committed to,
the draw can never happen. Neither can it if the operator takes the tickets
and never commits at all. The contract has one exit covering both, and this
project runs it.

## Prerequisites

- Python 3.12 or 3.13
- AlgoKit CLI 2.10 or later
- Poetry, installed by `algokit project bootstrap all` if it is not already
  present
- Docker or Podman for LocalNet

## Run It First!

```bash
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_lottery
```

Two lotteries run. The first draws; the second is abandoned by its beacon and
refunds everybody. The output is twelve lines and every number in it is worth
reading:

```console
Lottery deployed, reading a beacon it does not own
  app account seeded to 100,000 microAlgo, which is its whole min-balance
  operator's min-balance rose 349,500 for the app and its 7+1 slots
  5 entries, pot 10,000,000 microAlgo, 5 boxes at 19,300 each
  committed to a multiple of 8, at least 16 rounds ahead
  beacon published 32 bytes for the target round
  draw picked entrant 3 of 5, paid 10,000,000
  Won(address,uint64) logged 10,000,000 to the same account
  pot gone: balance and min-balance both 196,500 microAlgo
  5 boxes swept, 19,300 each returned, back to 100,000
Abandoned lottery: 3 entries, draw window 300 rounds
  beacon silent: each entrant took back 2,019,300, back to 100,000
```

Watch for these:

- **Two accounts, two bills.** The application account owes 100,000 and
  nothing else until a box exists. The seven uint64 and one byte-slice global
  slots are charged to the *creator*, whose own minimum balance goes up by
  349,500 the moment the app is created and stays up.

- **19,300 per entry.** Box minimum balance is `2,500 + 400 × (name + data)`,
  and an entry is a 10-byte name over a 32-byte address.

- **196,500.** After the pot is paid the application account holds
  `100,000 + 5 × 19,300` and its minimum balance is the same number. Every
  Algo it holds is one it owes, which is what makes `sweep` affordable.

- **Entrant 3 of 5.** The beacon value the stub publishes is fixed, so the
  winner is the same on every run. `tests/test_lottery.py` recomputes the
  index off chain from that value and asserts the contract agrees.

- **The Won event.** `draw` writes the result twice: `winner` in global
  state for whoever asks, and an ARC-28 log for whoever is listening. A
  results page finds `Won(address,uint64)` by the first four bytes of the
  hash of that signature, without holding this contract's source or
  polling its state. It costs eight opcode units, no fee and no extra
  transaction.

- **2,019,300 back.** Ticket plus box, to every entrant, when the beacon
  never speaks.

Then run the tests:

```bash
algokit project run test
```

Fifty-one tests: twelve source- and spec-level checks that need no chain, and
thirty-nine that deploy and play on LocalNet. Twenty-nine of the thirty-nine
turn on a refusal.

If Docker or Podman is not available, LocalNet cannot start. The static path
still runs:

```bash
algokit project bootstrap all
algokit project run build
algokit project run test-static
```

Those read the contract source and the compiled ARC-56 spec and assert the
properties that have no refusal to point at: every one of the four inner
transactions carries a zero fee, both exit paths delete the box they refund,
`draw` takes no arguments, and no method is marked `readonly`.

## Running It Against the Real Beacon on TestNet

The contract does not change. It stores whatever application id `initialize`
was handed and calls `get(uint64,byte[])byte[]` on it, so pointing it at a
beacon somebody else operates is one line in
`scripts/localnet_helpers.py`:

```python
BEACON_APP_ID = 600011887   # was 0, which deploys the stub
```

Then give the client a network and an account and run the same script:

```bash
export ALGOD_SERVER=https://testnet-api.4160.nodely.dev
export ALGOD_PORT=443
export ALGOD_TOKEN=
export DEPLOYER_MNEMONIC="your twenty five word testnet mnemonic ..."
poetry run python -m scripts.run_lottery
```

`resolve_beacon` sees a non-zero id, skips deploying the stub, and the
lottery reads the beacon at application 600011887. The MainNet beacon is
1615566206 and takes the same line.

What changes in the output, and what does not:

| Line | On TestNet |
|-------------------------------|------------------------------------|
| the two minimum-balance lines | identical; MBR is protocol arithmetic |
| entries, pot, box cost | identical |
| `committed to a multiple of 8` | identical, but the wait is real: 16 to 23 rounds is 44 to 63 seconds |
| `beacon published 32 bytes` | **gone.** Nobody publishes on your behalf; the beacon's own daemon already did |
| `draw picked entrant N of 5` | a different N, and a different one every time |
| `Won(address,uint64) logged` | identical; an event is a log write, not a network feature |
| the abandoned lottery | **skipped**, with a line saying why |

**This runbook has not been executed end to end in this repository, and
saying so is the point.** `validate.py --examples` runs against LocalNet, so
gating a TestNet run would mean committing a funded account and its
mnemonic to the build. The wait is the smaller cost --- reaching the target takes
the sixteen to twenty-three rounds `commit` rounds up to, about a minute here.
Sitting out the three-hundred-round draw window to exercise the refund path is
the expensive one, and this runbook draws rather than abandons. What *was* checked against the live beacon, with a
read-only `simulate` that needs no funding and submits nothing:

- application 600011887 answers `get(uint64,byte[])byte[]` (selector
  `189392c5`) and returns 32 bytes for a past round that is a multiple of 8
- it returns an **empty** byte slice for a round in the future, which is the
  behaviour the lottery's `assert value.native.length == UInt64(32)` depends
  on, and the reason the contract calls `get` rather than `must_get`
- values stay readable for about 1,500 rounds and then are gone: 64 global
  slots of 96 bytes hold 192 values eight rounds apart. It answers for any
  round at or below the newest stored multiple of eight, not only for the
  multiples themselves

That last number is why `DRAW_WINDOW_ROUNDS` is 300. A draw that has not
happened within 300 rounds of its target is still a thousand rounds away from
the value disappearing, and the refund path opens long before the evidence
does.

**The stub is not a fallback for readers without a TestNet account.** It is
the only way to run the branch that matters. A beacon somebody else operates
cannot be asked to go quiet, and a lottery that has never been tested against
silence has never been tested at all.

## Reader Path

Use Run It First to watch both endings, then work through the chapter's build.
`smart_contracts/lottery/contract.py` is one file and reads top to bottom in
lifecycle order. `scripts/run_lottery.py` is the executable transcript. Save
`tests/test_lottery.py` for the security section; it is a list of the
transactions this contract will not accept.

## Useful Files

- `smart_contracts/lottery/contract.py` is the lottery: seven methods,
  one `BoxMap`, one cross-application call.
- `smart_contracts/beacon_stub/contract.py` is ARC-21's two mandatory
  methods over global state, plus the `publish` knob production does not
  have.
- `scripts/localnet_helpers.py` holds the beacon switch, the minimum-balance
  arithmetic, and the round-advancing loop LocalNet needs.
- `scripts/run_lottery.py` is the end-to-end runbook.
- `tests/test_contract_shape.py` checks the properties a passing run cannot.
- `tests/test_lottery.py` deploys, draws, refunds, and proves the refusals.

## Two Things That Will Bite You

**Global state minimum balance is the creator's bill, not the application
account's.** Paying the application address 349,500 to "cover its state" funds
nothing that needed funding, and the operator's own account is short by that
amount whether or not you noticed. The application account's floor is 100,000
plus its boxes. `assert_app_sits_at_its_floor` and
`assert_creator_holds_the_schema` check the two separately against the
ledger's own `min-balance` field.

**The delete is the double-claim guard, and it is easy to leave out of one of
the two exits.** `sweep` and `refund` both pay an entrant and both
`del self.entrants[key]`; the payment is what the reader notices and the
delete is what makes the next call fail on `no such entry`. Omit it from one
branch and that branch is a faucet, with every other test still green.

## A Note on the Build

`algokit compile python` and `algokit generate client` both shell out to a
pipx-installed tool. `smart_contracts/__main__.py` falls back to
`python -m puyapy` and `python -m algokit_client_generator` when pipx is not
present, so `algokit project run build` works in a Poetry-only environment.
The compiler flags are the same either way, including
`--target-avm-version=12`.

`poetry.lock` pins the toolchain this project was last built and tested
against: puyapy 5.8.1, algorand-python 3.5.0, algokit-utils 4.2.3, and
pytest 9. `algokit project bootstrap all` installs from it rather than
resolving afresh, so the artifacts in `smart_contracts/artifacts/` are
reproducible byte for byte.
