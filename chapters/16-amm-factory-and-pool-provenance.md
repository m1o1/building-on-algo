\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Project}}
```
# AMM Factory and Pool Provenance

Chapter 14 built one AMM pool. That is enough to understand liquidity,
constant-product pricing, LP tokens, and swap safety. It is not enough to run a
DEX.

A DEX needs a way to answer questions like:

- Is there already a pool for this pair?
- Which pool is canonical for `asset_a`/`asset_b`?
- Did this pool come from your protocol, or did someone deploy a lookalike?
- Can another contract, such as a farm or router, safely trust this pool?

In Chapter 14, the client deployed a pool directly. That is the *client-side
factory* pattern: the SDK creates an app, bootstraps it, and remembers the app
ID. This chapter moves that authority on-chain. The factory application
creates pool applications using inner transactions, stores the canonical pool
for each ordered pair in box storage, and exposes a verification method that
downstream contracts can use before trusting a pool.

## Run It First

The finished project for this chapter is in `projects/amm-factory/`. Run the
complete workflow once before reading the implementation: it deploys a factory,
asks the factory to create a pool for two test ASAs, verifies that the pool is
the canonical one for that pair, and then proves the two failure cases this
design exists for --- a duplicate pair is rejected, and a pool that a user
deployed directly does not pass verification. Before you run it, predict which
account will own the new pool: the one that signs the create transaction, or
something else.

```bash
cd projects/amm-factory
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_amm_factory
algokit project run test
```

Table 16-1 lists the output checkpoints that are new in this chapter. The
middle of the run --- LP token opt-ins, initial liquidity, a swap, a later
deposit at the moved ratio, a withdrawal --- is Chapter 14's workflow replayed
against the factory-created pool, and Table 14-1's checkpoints apply to it
unchanged, because it is the same pool contract.

: Table 16-1. Output checkpoints for the AMM factory workflow

| Output checkpoint | What to watch for |
|-------------------|-------------------|
| Factory app ID and address | The factory app account can send inner transactions |
| Factory-created pool app ID | The pool was created by the factory, not by the user directly |
| LP token ID | The child pool created its LP token during bootstrap |
| Registered pool accepted | Verification returned true for the factory-created pool |
| Duplicate pool rejected | The pair registry prevented a second canonical pool |
| Fake pool rejected | A directly deployed pool did not pass provenance checks |
| Test suite passes | If pytest reports skipped LocalNet tests, you have verified the static shape checks only |

This chapter is a guided tour of that finished project rather than a
line-by-line scaffold. Three ideas hold the design together:

- the factory pays for and creates the child app
- the registry decides which pool is canonical for a pair
- verification combines registry state, app creator, and child global state


## What You Need First

Chapter 15 ended with a Handoff table naming what this project would
lean on. Table 16-2 is the other side of it. Every row
is a mechanism you have already run in isolation; the factory is the first
place they carry money.

Answer the predict column before you follow the link.

: Table 16-2. What Chapter 15 built that this project assumes

| Prerequisite | Where it lands here | Predict before you read it |
|--------------|---------------------|----------------------------|
| Example 15-12 | `create_pool`, which compiles a pool and deploys it | The factory deploys many pools rather than one --- the several-workers problem Chapter 15's Exercise 5 left you holding, solved with a registry. What must it store per pool that the example stores in a single global? |
| Example 15-13 | The bootstrap payment every new pool receives | A pool opts into two assets and creates an LP token. Work out what it must hold before it can do any of that. |
| Example 15-10 | The provenance check a downstream contract runs on a pool | Which single fact about an application cannot be forged by that application, and what does checking it still fail to prove? |
| Example 15-4 | The factory calling a new pool's `bootstrap` | The factory has the pool's source, so it could use the typed form. Say why a project might reach for the signature string anyway. |
| Example 15-11 | `create_pool` funding and calling a pool in the same execution that created it | The pool did not exist when the group was assembled. Say what makes it reachable by the transaction after the one that made it. |
| Example 13-2 | The strict `<` on the pair key, and the registry it protects | Chapter 13 gave one reason for that ordering. This chapter has a different one. Name it before you read on. |

## From One Pool to a Protocol

The Chapter 14 pool is an excellent standalone contract. It holds exactly two
assets, mints one LP token, and enforces constant-product swap math. But if
every user can deploy a pool directly, the protocol has no single source of
truth.

Suppose Alice deploys a USDC/ALGO pool and Bob deploys another USDC/ALGO pool.
Both can be technically valid AMMs. Liquidity is now fragmented. A frontend,
farm, or router needs to choose which app ID represents "the" pool. If that
choice lives only in a web server or local config file, the on-chain protocol
cannot enforce it.

The factory solves this by becoming a registry:

```text
(asset_a, asset_b) -> pool_app_id
```

where `asset_a < asset_b`. The ordered pair prevents the protocol from treating
`USDC/ALGO` and `ALGO/USDC` as different pools.

The factory also becomes the creator of each pool application. On Algorand,
every application has an application account address, and an application can
send inner transactions from that account. When the factory creates a pool with
an inner application call, the new pool's creator is the factory app address,
not the human user who called the factory.

That gives you a useful provenance check:

```python
candidate_pool.creator == Global.current_application_address
```

But that check alone is not enough. It says the candidate was created by this
factory address; it does not prove it is the canonical pool for a specific pair,
nor does it prove the child pool was initialized with the pair the caller is
asking about. Strong verification combines three facts:

```text
candidate_pool.creator == factory_app_address
factory.registry[(asset_a, asset_b)] == candidate_pool.id
candidate_pool global state matches asset_a, asset_b, factory_app_id, lp_token
```

That is the difference between weak provenance and useful provenance.

## The Pool Contract

The child pool is a close cousin of the Chapter 14 AMM. It keeps:

- the ordered asset IDs
- the LP token ID
- the reserves
- the LP token supply accounting
- the constant-product swap math
- sender and receiver validation for grouped asset transfers
- fee-zero inner transactions
- immutable update/delete behavior

It omits TWAP. Adding it back is Exercise 4.

The new global field is `factory_app_id`:

```python
class FactoryPool(ARC4Contract):
    def __init__(self) -> None:
        self.factory_app_id = GlobalState(UInt64(0))
        self.asset_a = GlobalState(UInt64(0))
        self.asset_b = GlobalState(UInt64(0))
        self.lp_token_id = GlobalState(UInt64(0))
        self.reserve_a = GlobalState(UInt64(0))
        self.reserve_b = GlobalState(UInt64(0))
        self.lp_total_supply = GlobalState(UInt64(0))
        self.locked_liquidity = GlobalState(UInt64(0))
        self.is_bootstrapped = GlobalState(UInt64(0))
```

The pool still has a bare create method, but direct creation does not initialize
it:

```python
@arc4.baremethod(create="require")
def create(self) -> None:
    pass
```

The meaningful initialization happens in `bootstrap`, and `bootstrap` only
accepts an application-to-application call from the factory that created it:

```python
@arc4.abimethod
def bootstrap(self, asset_a_id: UInt64, asset_b_id: UInt64) -> UInt64:
    assert Global.caller_application_id != UInt64(0), "Factory call required"
    assert (
        Global.caller_application_address == Global.creator_address
    ), "Caller is not creator"
    assert Txn.sender == Global.creator_address, "Sender is not factory"
    assert self.is_bootstrapped.value == UInt64(0), "Already bootstrapped"
    assert asset_a_id < asset_b_id, "Assets must be in canonical order"
```

`Global.caller_application_id` is zero for a top-level call. During an inner app
call from the factory, it is the factory's app ID. `Global.caller_application_address`
is the factory's app address. Since the factory also created the pool, that
caller address should equal the pool's `Global.creator_address`.

After those checks, the pool validates the two assets, records the factory ID
and asset IDs, creates the LP token, and opts into both assets:

```python
self.factory_app_id.value = Global.caller_application_id
self.asset_a.value = asset_a_id
self.asset_b.value = asset_b_id

lp_create = itxn.AssetConfig(
    asset_name=b"FACTORY-CPMM-LP",
    unit_name=b"F-LP",
    total=UInt64(LP_TOKEN_SUPPLY),
    decimals=UInt64(6),
    default_frozen=False,
    manager=Global.current_application_address,
    reserve=Global.current_application_address,
    freeze=Global.zero_address,
    clawback=Global.zero_address,
    fee=UInt64(0),
).submit()
self.lp_token_id.value = lp_create.created_asset.id
```

The pool must already have enough Algo to create the LP token and opt into both
assets. That is why the factory sends an inner payment to the pool app account
before it calls `bootstrap`.

## The Factory Registry

The factory's state is small:

```python
class AMMFactory(ARC4Contract):
    def __init__(self) -> None:
        self.pools = BoxMap(Bytes, UInt64, key_prefix=b"p_")
        self.lp_tokens = BoxMap(Bytes, UInt64, key_prefix=b"l_")
```

Both maps use the same pair key:

```python
@subroutine
def _pair_key(asset_a_id: UInt64, asset_b_id: UInt64) -> Bytes:
    return op.itob(asset_a_id) + op.itob(asset_b_id)
```

That produces a stable 16-byte key: 8 bytes for `asset_a`, followed by 8 bytes
for `asset_b`. The prefixes keep the two maps separate:

```text
p_ + pair_key -> pool_app_id
l_ + pair_key -> lp_token_id
```

Because these are boxes, the caller must provide the box references (the
[Algorand Python storage guide](https://algorandfoundation.github.io/puya/language-guide/storage/)
documents `BoxMap` and the reference requirement). The factory can create the
boxes, but it cannot add them to the transaction's access list itself.

### The Factory's Lifecycle Stance

The factory takes the same stance the Chapter 14 pool took, in the same two
lines:

```python
    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "Contract is immutable"
```

Stating the stance is not the same as it being free, and here it costs more
than it did for a single pool. `compile_contract(FactoryPool)` freezes the
child's bytecode into the factory's own program at compile time, so an
immutable factory is a promise about every pool it will ever create, not just
about itself: a bug shipped in `FactoryPool` today is a bug in the pool this
factory deploys next year, and there is no update path that keeps the registry.
The alternative --- deploying a second factory with a fixed child --- starts an
empty registry, which means the pair mapping downstream contracts verify
against splits in two.

Immutable is still the right answer for this project, because a factory that
can be updated is a factory whose registry entries mean whatever its admin
currently says they mean, and the registry is the whole product. But it is a
choice with a bill attached, and the bill is paid by whoever needs a v2 pool.

## Creating the Child Pool

The factory starts by validating the outer group:

```python
assert Global.group_size == UInt64(2), "Create pool group must be size 2"
assert asset_a.id < asset_b.id, "Assets must be in canonical order"
assert seed_payment.sender == Txn.sender, "Seed sender mismatch"
assert seed_payment.receiver == Global.current_application_address
assert seed_payment.amount >= UInt64(FACTORY_CREATE_SEED), "Seed too small"
```

The grouped payment is not a user deposit into the pool. It is infrastructure
funding, and every line of its bill comes off Chapter 11's price list. What is
new is who each bill lands on: the factory app account is the creator of the
child, so the child's creation MBR raises the *factory's* minimum balance, not
the caller's, and the registry boxes are factory-owned, so their MBR lands
there too. Table 16-3 itemizes where the seed goes.

: Table 16-3. Where the 1,500,000-microAlgo seed goes

| Bill | Arithmetic | microAlgo |
|------|------------|-----------|
| Factory account's own floor | 100,000 flat | 100,000 |
| Child app creation, charged to the factory as its creator | 100,000 + 9 uint slots × 28,500 | 356,500 |
| Two registry boxes: 2-byte prefix + 16-byte pair key, 8-byte values | 2 × (2,500 + 400 × 26) | 25,800 |
| Inner payment funding the child pool | `POOL_BOOTSTRAP_FUNDING` | 500,000 |
| Headroom left in the factory account | remainder | 517,700 |

The child's 500,000 is its own bill: a 100,000 floor, 100,000 for creating
the LP token, and 100,000 for each of the two asset opt-ins --- 400,000
committed, 100,000 spare. The child's compiled program fits inside the free
2,048-byte program page, so no extra-page line appears; if you extend the
pool, recheck the slot count and the page count both. After `create_pool`
settles, algod's `account_info` confirms the arithmetic: the factory's
minimum balance reads exactly 482,300 and the child's reads 400,000.

The duplicate check reads the pair registry before creating anything:

```python
key = _pair_key(asset_a.id, asset_b.id)
existing_pool, exists = self.pools.maybe(key)
assert not exists, "Pool already exists"
```

Then the factory compiles the child contract and creates it with an inner
application call:

```python
compiled_pool = compile_contract(FactoryPool)
create_txn = itxn.ApplicationCall(
    approval_program=compiled_pool.approval_program,
    clear_state_program=compiled_pool.clear_state_program,
    global_num_uint=compiled_pool.global_uints,
    global_num_bytes=compiled_pool.global_bytes,
    local_num_uint=compiled_pool.local_uints,
    local_num_bytes=compiled_pool.local_bytes,
    extra_program_pages=compiled_pool.extra_program_pages,
    fee=UInt64(0),
).submit()
pool_app = create_txn.created_app
```

`compile_contract` gives the factory the approval program, clear program,
schema, and extra program pages for `FactoryPool` (the
[PuyaPy compile guide](https://algorandfoundation.github.io/puya/language-guide/compile/)
covers what it can embed). The submitted inner application call returns an
inner transaction object, and `created_app` is the newly allocated
application. The funding payment and the `bootstrap` call that follow can name
that application immediately, for Example 15-11's reason: each transaction,
inner ones included, evaluates against the ledger as the ones before it left
it.

The factory funds the child before asking it to create the LP token:

```python
itxn.Payment(
    receiver=pool_app.address,
    amount=UInt64(POOL_BOOTSTRAP_FUNDING),
    fee=UInt64(0),
).submit()
```

Then it calls the child's `bootstrap(uint64,uint64)uint64` ARC-4 method:

```python
bootstrap_txn = itxn.ApplicationCall(
    app_id=pool_app,
    app_args=(
        arc4.arc4_signature("bootstrap(uint64,uint64)uint64"),
        arc4.UInt64(asset_a.id),
        arc4.UInt64(asset_b.id),
    ),
    assets=(asset_a, asset_b),
    fee=UInt64(0),
).submit()
lp_token_id = arc4.UInt64.from_log(bootstrap_txn.last_log).as_uint64()
```

Example 15-4 spelled this same kind of signature *inside* `abi_call`; here the
selector travels as the first app argument and the return value is read back
out of the last log entry --- the encoding and decoding `abi_call` was doing
for you, laid out on the wire.

::: {.note}
**Note.** The manual `compile_contract` + `itxn.ApplicationCall` +
`arc4_signature` + `from_log` pattern shows exactly what happens on the
wire. In production code you can let the compiler do this plumbing with the
typed helpers `arc4.arc4_create(...)` / `arc4.abi_call(...)`, which handle
schema, pages, selector encoding, and return-value decoding for you (the
[ARC-4 reference](https://algorandfoundation.github.io/puya/api/algopy/algopyarc4/)
documents all three spellings, and the
[transactions guide](https://dev.algorand.co/algokit/languages/python/lg-transactions/)
covers inner application calls generally).
`itxn.abi_call(...)` is a third form and a different one: it
returns an `ApplicationCall` you still have to `.submit()`, which is what
lets several typed calls be staged into one `itxn.submit_txns(...)`.
:::

The child pool inspects the asset parameters and opts into both assets, so those
assets must be available to the inner app call. Under AVM v9+ group resource
sharing the outer call's `asset_references` would also make them available;
the `assets=(asset_a, asset_b)` entry states the dependency outright.

Finally, the factory writes the canonical registry entries:

```python
self.pools[key] = pool_app.id
self.lp_tokens[key] = lp_token_id
return pool_app.id, lp_token_id
```

### Driving the Factory from a Client

The caller has to name every box and asset the factory will touch, because the
AVM refuses to read a resource the transaction did not declare. The client
side of `create_pool` is short enough to run as a standalone script, and
running it now pays off the tour so far: it ends with algod naming the
factory, not you, as the pool's creator. If you have not built the project
since Run It First, rebuild it now.

The build regenerates the typed clients for both contracts under
`smart_contracts/artifacts/`. Save the following as `create_first_pool.py` in
the project root. Everything before the factory deployment is Chapter 14
plumbing: connect to LocalNet, fund one throwaway admin from the dispenser,
and create two test ASAs sorted into canonical order.

```python
from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    AssetCreateParams,
    CommonAppCallParams,
    PaymentParams,
)
from algosdk.atomic_transaction_composer import TransactionWithSigner

from smart_contracts.artifacts.amm_factory import amm_factory_client

algorand = AlgorandClient.default_localnet()
algorand.set_suggested_params_cache_timeout(0)

# One throwaway admin account, funded from the LocalNet dispenser
dispenser = algorand.account.localnet_dispenser()
admin = algorand.account.random()
algorand.send.payment(
    PaymentParams(
        sender=dispenser.address,
        signer=dispenser.signer,
        receiver=admin.address,
        amount=AlgoAmount.from_micro_algo(10_000_000),
    )
)

def create_test_asset(name: str, unit: str) -> int:
    result = algorand.send.asset_create(
        AssetCreateParams(
            sender=admin.address,
            signer=admin.signer,
            total=1_000_000_000_000,
            decimals=6,
            asset_name=name,
            unit_name=unit,
            default_frozen=False,
        )
    )
    return result.asset_id

# Two test ASAs in canonical order: the same lower-ID-first rule as
# the Chapter 14 pool
token_a = create_test_asset("Factory A", "FCTA")
token_b = create_test_asset("Factory B", "FCTB")
if token_a > token_b:
    token_a, token_b = token_b, token_a
print(f"Token A: {token_a}, Token B: {token_b}")

factory_factory = amm_factory_client.AmmFactoryFactory(
    algorand,
    default_sender=admin.address,
    default_signer=admin.signer,
)
factory, _ = factory_factory.send.create.bare()
print(f"Factory app ID: {factory.app_id}")
print(f"Factory address: {factory.app_address}")
```

The factory stores two boxes for the pair: one mapping the pair to the pool
app ID, and one mapping the pair to the LP token ID. The factory can create
those boxes, but only the caller can put them on the transaction's access
list, so the client constructs the exact names. The rest of the script is the
`create_pool` call itself, followed by the question this chapter turns on:
who does algod say created the pool?

```python
# The factory's two registry boxes for this pair, named by the caller
pair_key = token_a.to_bytes(8, "big") + token_b.to_bytes(8, "big")
pool_box = b"p_" + pair_key
lp_box = b"l_" + pair_key

seed_txn = algorand.create_transaction.payment(
    PaymentParams(
        sender=admin.address,
        receiver=factory.app_address,
        amount=AlgoAmount.from_micro_algo(1_500_000),
    )
)
created = factory.send.create_pool(
    amm_factory_client.CreatePoolArgs(
        seed_payment=TransactionWithSigner(seed_txn, admin.signer),
        asset_a=token_a,
        asset_b=token_b,
    ),
    params=CommonAppCallParams(
        sender=admin.address,
        signer=admin.signer,
        static_fee=AlgoAmount.from_micro_algo(7_000),
        asset_references=[token_a, token_b],
        box_references=[pool_box, lp_box],
    ),
)
pool_id, lp_token = created.abi_return
print(f"Factory-created pool: {pool_id}")
print(f"LP token: {lp_token}")

# Ask algod who created the pool
info = algorand.client.algod.application_info(pool_id)
print(f"Your address: {admin.address}")
print(f"Pool creator: {info['params']['creator']}")
assert info["params"]["creator"] == factory.app_address
```

The seed is Table 16-3's bill arriving as a grouped payment, and the
`static_fee` of 7,000 is Chapter 11's [fee pooling](https://dev.algorand.co/concepts/transactions/fees/)
at work: one outer call
plus six zero-fee inner transactions --- the app create, the funding payment,
the `bootstrap` call, and, inside `bootstrap`, the LP-token create and two
asset opt-ins --- is seven minimum fees (Example 8-11).

Run it from the project root (the script imports the generated client by its
package path, so the working directory matters):

```bash
poetry run python create_first_pool.py
```

```text
Token A: 131137, Token B: 131138
Factory app ID: 131139
Factory address: BYLWTP7TJ3QJMBN2I2HW5UOBZ7GGCG3QFSDCEHPU3XRJM7EVT3E6PUHDSI
Factory-created pool: 131142
LP token: 131145
Your address: Z247QV65OB6MD6EG6ZXJWYYRZMFSRPZXRPMO2O5XPUEII6YTCF5NX66MLA
Pool creator: BYLWTP7TJ3QJMBN2I2HW5UOBZ7GGCG3QFSDCEHPU3XRJM7EVT3E6PUHDSI
```

Your IDs and addresses will differ; the relationship in the last two lines
will not. You signed every transaction in this run, and the pool's creator is
still not you --- it is the factory's application address, which settles the
Run It First prediction, and the script's closing `assert` pins it.
Re-running the script is always safe: it creates two fresh ASAs each time,
and a fresh pair means a fresh registry slot. If the `amm_factory_client`
import fails, the build step has not run; if the first payment cannot
connect, LocalNet is not up (`algokit localnet start`).

The finished workflow script, `scripts/run_amm_factory.py`, is this same
client flow with the boilerplate factored into `scripts/localnet_helpers.py`
and two more funded accounts, a trader and a second LP. Past `create_pool` it
does nothing new: users opt into the LP token, add initial liquidity, swap,
add liquidity again at the moved ratio, and remove liquidity --- exactly as
they did in Chapter 14, in the same order, with the same grouped-transaction
shapes, because it **is** the same contract. The only difference is where the
client gets the app ID:

```python
pool = factory_pool_client.FactoryPoolClient(
    algorand=algorand,
    app_id=pool_id,
    default_sender=admin.address,
    default_signer=admin.signer,
)
```

In Chapter 14 that app ID came back from a deployment the user performed. Here it
came back from `create_pool`. The factory changes where a pool comes from and
who vouches for it; it does not change how the pool prices a swap.


## Verifying a Pool

The factory exposes lookups:

```python
@arc4.abimethod(readonly=True)
def get_pool(self, asset_a: Asset, asset_b: Asset) -> UInt64:
    assert asset_a.id < asset_b.id, "Assets must be in canonical order"
    return self.pools.get(_pair_key(asset_a.id, asset_b.id), default=UInt64(0))
```

But the important method is `verify_pool`:

```python
@arc4.abimethod(readonly=True)
def verify_pool(
    self,
    candidate_pool: Application,
    asset_a: Asset,
    asset_b: Asset,
) -> bool:
    if asset_a.id >= asset_b.id:
        return False

    key = _pair_key(asset_a.id, asset_b.id)
    registered_pool = self.pools.get(key, default=UInt64(0))
    if registered_pool != candidate_pool.id:
        return False

    if candidate_pool.creator != Global.current_application_address:
        return False
```

The first check rejects non-canonical order. The second check says the factory's
own registry maps this pair to the candidate. The third check says the candidate
application was created by the factory app address.

Then the factory reads the child's global state:

```python
pool_asset_a, has_asset_a = op.AppGlobal.get_ex_uint64(
    candidate_pool, Bytes(b"asset_a")
)
pool_asset_b, has_asset_b = op.AppGlobal.get_ex_uint64(
    candidate_pool, Bytes(b"asset_b")
)
pool_factory, has_factory = op.AppGlobal.get_ex_uint64(
    candidate_pool, Bytes(b"factory_app_id")
)
pool_lp_token, has_lp_token = op.AppGlobal.get_ex_uint64(
    candidate_pool, Bytes(b"lp_token_id")
)
```

And it finishes by requiring all of the claims to agree:

```python
return (
    has_asset_a
    and has_asset_b
    and has_factory
    and has_lp_token
    and pool_asset_a == asset_a.id
    and pool_asset_b == asset_b.id
    and pool_factory == Global.current_application_id.id
    and pool_lp_token == self.lp_tokens.get(key, default=UInt64(0))
)
```

This is the pattern a farming contract, router, or lending protocol should want
from an AMM factory: not merely "this app looks like a pool," but "the factory
that owns the registry says this is the canonical pool for this pair, and the
pool's own state agrees." The complete method, assembled from the four
fragments shown here --- the listing to diff your own against --- is in
`projects/amm-factory/smart_contracts/amm_factory/contract.py`.


### Calling Verification from a Client

The client side of `verify_pool` is short, and every line of it is a resource
declaration. Any downstream caller --- a farm, a router, a frontend --- asks the
factory this same question before it trusts an app ID. Append it to
`create_first_pool.py` and run the script again:

```python
canonical = factory.send.verify_pool(
    amm_factory_client.VerifyPoolArgs(
        candidate_pool=pool_id,
        asset_a=token_a,
        asset_b=token_b,
    ),
    params=CommonAppCallParams(
        sender=admin.address,
        signer=admin.signer,
        app_references=[pool_id],
        asset_references=[token_a, token_b],
        box_references=[pool_box, lp_box],
    ),
).abi_return
assert canonical is True
print(f"Registry says canonical: {canonical}")
```

The `app_references` entry lets the factory inspect the candidate pool's app
parameters and global state. The `box_references` entries let it read the
factory-owned registry boxes. A fresh factory and pool print first --- the
script creates them on every run --- and then the new last line:

```text
Registry says canonical: True
```

Where the checkpoint's algod query was an off-chain answer for a human, this
is the on-chain answer a contract can act on.


## Why Not Trust the Child Alone?

It is tempting to give the pool a global `factory_app_id` and stop there:

```python
self.factory_app_id.value = Global.caller_application_id
```

That field is useful, but it is not authoritative by itself. Anyone can deploy
a malicious contract with a global state key named `factory_app_id` and store
the same value. If your farm trusts only the child's global state, it can be
tricked by a clone.

The factory registry is harder to fake because only the factory application can
write its own boxes. A malicious pool can claim anything in its own state; it
cannot make the real factory map `(asset_a, asset_b)` to the malicious app ID.

::: {.gotcha #child-state-is-not-authoritative topic="Cross-contract calls" title="A contract's own global state is not evidence about its parent"}
Reading `factory_app_id` out of a pool and comparing it to the factory you trust proves only that the pool *claims* that parent. Global state is writable by its own application and by nothing else, which cuts both ways: nobody can forge the real factory's state, and anybody can forge a claim about it. Verification has to run in the direction where the trusted party is the writer --- ask the factory whether it created this pool, never ask the pool who created it. The same asymmetry governs every cross-contract trust decision in this book.
:::

Figure 16-1 draws both claims side by side and marks which
arrows an attacker can forge. Every arrow that originates inside the caller is
forgeable, because the caller wrote it. The one arrow that is not is the entry
the factory itself recorded in its own box, and that is the one to check.

![Figure 16-1. Why a factory cannot take a child contract's word for anything. Only the application ID the factory itself recorded proves the caller is one of its own.](figures/provenance-trust-graph.svg)

That is why the verification method combines both sides. Table 16-4 summarizes
the checks used by `verify_pool`.

: Table 16-4. Provenance checks used by `verify_pool`

| Check | What it proves |
|-------|----------------|
| `candidate_pool.creator == factory_address` | The app was created by this factory address |
| `pools[pair] == candidate_pool.id` | The factory registry recognizes it as canonical |
| child `asset_a`/`asset_b` match | The pool state agrees with the requested pair |
| child `factory_app_id` matches | The child recorded the factory caller during bootstrap |
| child LP token matches registry | Consumers receive the token the factory recorded |

No single check carries the whole security argument. Together, they form a
useful provenance proof for this AMM architecture.

The workflow closes by proving the two failure cases this design exists to
prevent. First, a second pool for the same pair is refused:

```python
try:
    duplicate_seed_txn = algorand.create_transaction.payment(
        PaymentParams(
            sender=admin.address,
            receiver=factory.app_address,
            amount=AlgoAmount.from_micro_algo(1_500_000),
        )
    )
    factory.send.create_pool(
        amm_factory_client.CreatePoolArgs(
            seed_payment=TransactionWithSigner(duplicate_seed_txn, admin.signer),
            asset_a=token_a,
            asset_b=token_b,
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(7_000),
            asset_references=[token_a, token_b],
            box_references=[pool_box, lp_box],
        ),
    )
except Exception:
    print("Duplicate pool rejected")
```

And a directly deployed pool is not canonical:

```python
fake_factory = factory_pool_client.FactoryPoolFactory(
    algorand,
    default_sender=admin.address,
    default_signer=admin.signer,
)
fake_pool, _ = fake_factory.send.create.bare()

fake_canonical = factory.send.verify_pool(
    amm_factory_client.VerifyPoolArgs(
        candidate_pool=fake_pool.app_id,
        asset_a=token_a,
        asset_b=token_b,
    ),
    params=CommonAppCallParams(
        sender=admin.address,
        signer=admin.signer,
        app_references=[fake_pool.app_id],
        asset_references=[token_a, token_b],
        box_references=[pool_box, lp_box],
    ),
).abi_return
assert fake_canonical is False
```

Both refusals come from the same place. The registry, not the pool, is the
authority on which app is canonical for a pair, so a second pool cannot claim
the slot, and a pool nobody registered cannot claim to be in it.

## Testing the Factory

The suite in `projects/amm-factory/tests/` is split the way Chapter 14's was:
`test_contract_shape.py` is the static half, reading both contract sources and
asserting the security properties stay present through refactors, and
`test_amm_factory.py` is the behavior half --- real factories and real pools on
LocalNet, driven through the same typed clients as the workflow script,
skipped by the same one-line `conftest.py` when there is no chain to talk to.
The listing below is the behavior suite's actual code, not an outline.

Every behavior test starts from `deploy_factory_and_pool`, a plain function
that replays the first half of the workflow script --- fund accounts, create
and sort two test ASAs, deploy a factory, call `create_pool` --- and returns
the clients, accounts, IDs, and box references a test needs. The helpers it
imports are Chapter 14's `localnet_helpers` with one addition:
`pair_box_reference` builds the prefixed box names the way
`create_first_pool.py` did by hand, and `FACTORY_CREATE_SEED` is the same
1,500,000 the contract asserts. Three tests build on it:

- `test_factory_creates_and_verifies_registered_pool` --- `get_pool` returns
  the registered app ID, and `verify_pool` accepts it
- `test_pool_supports_liquidity_and_swaps` --- Chapter 14's whole arc
  (opt-ins, initial liquidity, a swap, a later deposit at the moved ratio, a
  withdrawal) run as assertions against a factory-created pool
- `test_duplicate_and_fake_pool_are_rejected` --- the two refusals this design
  exists for

The third is the one to read closely. Before you do, predict which of
Table 16-4's checks the fake pool fails first: it runs the same code as the
canonical pool, but it was not created by the factory and it is not the
registered pool for the pair.

```python
def test_duplicate_and_fake_pool_are_rejected(algorand) -> None:
    (
        amm_factory_client,
        pool_client,
        factory,
        pool,
        admin,
        _trader,
        _second_lp,
        token_a,
        token_b,
        _lp_token,
        pair_boxes,
    ) = deploy_factory_and_pool(algorand)

    with pytest.raises(Exception, match="Pool already exists"):
        factory.send.create_pool(
            amm_factory_client.CreatePoolArgs(
                seed_payment=payment_arg(
                    algorand, admin, factory.app_address, FACTORY_CREATE_SEED
                ),
                asset_a=token_a,
                asset_b=token_b,
            ),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                static_fee=AlgoAmount.from_micro_algo(7_000),
                asset_references=[token_a, token_b],
                box_references=pair_boxes,
            ),
        )

    fake_factory = pool_client.FactoryPoolFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    fake_pool, _ = fake_factory.send.create.bare()

    assert (
        factory.send.verify_pool(
            amm_factory_client.VerifyPoolArgs(
                candidate_pool=fake_pool.app_id,
                asset_a=token_a,
                asset_b=token_b,
            ),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                app_references=[fake_pool.app_id, pool.app_id],
                asset_references=[token_a, token_b],
                box_references=pair_boxes,
            ),
        ).abi_return
        is False
    )
```

Two things separate this from the workflow demo that printed the same two
refusals. The duplicate half does not accept just any failure:
`match="Pool already exists"` pins the refusal to `create_pool`'s own assert
message, the discipline Chapter 14's negative tests applied to swaps.

And the two halves refuse differently. `create_pool` is a state-changing
method, so a duplicate dies inside `pytest.raises`; `verify_pool` is a
readonly lookup, so a fake pool is not an error at all --- the method returns
`False` and the test asserts on the value. That difference is the contract
downstream code lives with: a router that asks about an unregistered pool gets
an answer, not an exception. (The fake-pool call also declares the canonical
pool's app reference; the registry mismatch returns before anything reads it,
and declaring a resource you never touch is legal.)

The test proves that "this contract has the same code" is not the same thing
as "this contract is the canonical pool for this pair." Run the suite with
`algokit project run test` from the project directory; without a reachable
LocalNet the behavior half skips and reports why, and
`algokit project run test-static` still runs the static half alone.

## Exercises

1. **(Apply)** Trace `verify_pool` for the happy path. For each check,
   write down which transaction reference or state value makes the check
   possible.
2. **(Analyze)** Trace `verify_pool` for the fake-pool path. Which check fails
   first? Which later checks would also fail if execution continued?
3. **(Analyze)** Explain why `factory_app_id` in the child pool is useful but
   insufficient. What can a malicious clone write in its own global state?
4. **(Evaluate)** *(Assumes Chapter 14's optional TWAP section.)* Add the
   Chapter 14 TWAP oracle back to `FactoryPool`. Adding it is not conceptually
   hard, but a few details need care, and the last two hints are a judgement
   call to argue rather than a step to follow:

   1. Copy the Chapter 14 cumulative price fields into `FactoryPool`.
   2. Initialize `twap_last_update` when initial liquidity is added, not
      during factory bootstrap. Before liquidity exists, there is no
      meaningful price.
   3. Call `_update_twap()` before reserve mutations in `swap`,
      `add_liquidity`, and `remove_liquidity`.
   4. Compile-test the factory after adding TWAP, and watch the factory rather
      than the pool. As shipped, `FactoryPool`'s approval program assembles to
      1,357 bytes and the factory's to 1,988 --- of which the 1,357 is the
      child, carried inside it by `compile_contract`. That leaves 60 bytes
      under the free 2,048-byte page, so every byte the oracle adds to the
      child is a byte the factory has to find. On the Chapter 14 pool the same
      three fields, the same subroutine and the same read method cost 224
      bytes; sixty is not enough.
   5. Budget an `extra_program_pages` on the factory, or move the oracle
      behind a smaller child. Either is a real answer; guessing is not, which
      is why the measurement above comes before the code.
   6. Keep `verify_pool` focused on identity. A TWAP consumer should
      separately verify the oracle fields it depends on.

5. **(Create)** Design the change a yield farm would need to accept only
   factory-verified LP tokens. Which app, asset, and box references would the
   farm call need? Chapter 17's Exercise 5 asks for the same change from the
   farm's side --- sketch it here, and you will implement it there.
6. **(Create)** Sketch a router that asks the factory for the canonical pool
   before quoting a swap. Where should the router reject an unknown pair?

## Before You Continue

You should be able to check off all five of these:

- [ ] I can say what a client-deployed pool cannot promise a router or a farm, and
  what moving creation on-chain adds
- [ ] I can create a child application from a factory contract using
  `compile_contract` and an inner `ApplicationCall`
- [ ] I can build the 16-byte registry key from an ordered asset pair, and say what
  an unordered key would let someone create
- [ ] I can state the three provenance checks (registry entry, app creator, child
  global state) and explain why each alone is insufficient
- [ ] I can explain who funds which MBR at each step: the caller seeds the factory,
  the factory pays the child-creation and registry-box MBR, and the factory's
  inner payment covers the child's opt-ins and LP token

If any of these are unclear, revisit the relevant section before proceeding.

The next chapter extends the AMM system with a yield farming contract.
Factory-backed provenance is the natural production extension: before accepting
LP tokens from an AMM pool, a farm can ask the factory whether that pool is
canonical.
