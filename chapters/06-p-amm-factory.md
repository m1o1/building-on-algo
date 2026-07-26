\newpage

# AMM Factory and Pool Provenance

{{ch:amm}} built one AMM pool. That is enough to understand liquidity,
constant-product pricing, LP tokens, and swap safety. It is not enough to run a
DEX.

A DEX needs a way to answer questions like:

- Is there already a pool for this pair?
- Which pool is canonical for `asset_a`/`asset_b`?
- Did this pool come from our protocol, or did someone deploy a lookalike?
- Can another contract, such as a farm or router, safely trust this pool?

In {{ch:amm}}, the client deployed a pool directly. That is the *client-side
factory* pattern: the SDK creates an app, bootstraps it, and remembers the app
ID. In this chapter, we move that authority on-chain. The factory application
creates pool applications using inner transactions, stores the canonical pool
for each ordered pair in box storage, and exposes a verification method that
downstream contracts can use before trusting a pool.

The finished project lives in `projects/chapter6/amm-factory/`.

## Run It First

The finished project for this chapter is in `projects/chapter6/amm-factory/`. It
creates a factory, asks the factory to create a pool for two test ASAs, verifies
that the pool is the canonical one for that pair, runs an ordinary liquidity and
swap workflow against it, and then proves the two failure cases: a duplicate
pair is rejected, and a pool that a user deployed directly does not pass
verification.

```bash
cd projects/chapter6/amm-factory
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_amm_factory
algokit project run test
```

{{tbl:factory-run-it-first}} lists the output checkpoints to compare against the
workflow output.

Table: Output checkpoints for the AMM factory workflow {#tbl:factory-run-it-first}

| Output checkpoint | What to watch for |
|-------------------|-------------------|
| Factory app ID and address | The factory app account can send inner transactions |
| Factory-created pool app ID | The pool was created by the factory, not by the user directly |
| LP token ID | The child pool created its LP token during bootstrap |
| Registered pool accepted | Verification returned true for the factory-created pool |
| Initial LP minted | The pool accepted its first matched liquidity deposits |
| Swap output | The factory-created pool still behaves like an AMM |
| Later LP minted | A second LP added liquidity after prices moved |
| Removed liquidity | The second LP burned LP tokens and received both assets |
| Duplicate pool rejected | The pair registry prevented a second canonical pool |
| Fake pool rejected | A directly deployed pool did not pass provenance checks |

This chapter is a guided tour of that finished project rather than a
line-by-line scaffold. As you trace it, keep three ideas in view:

- the factory pays for and creates the child app
- the registry decides which pool is canonical for a pair
- verification combines registry state, app creator, and child global state


## From One Pool to a Protocol

The {{ch:amm}} pool is an excellent standalone contract. It holds exactly two
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

That gives us a useful provenance check:

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

The child pool is a close cousin of the {{ch:amm}} AMM. It keeps:

- the ordered asset IDs
- the LP token ID
- the reserves
- the LP token supply accounting
- the constant-product swap math
- sender and receiver validation for grouped asset transfers
- fee-zero inner transactions
- immutable update/delete behavior

It intentionally omits TWAP. That keeps the factory chapter focused on contract
creation and provenance. Adding TWAP back is a good exercise at the end of the
chapter.

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

The factory's state is intentionally small:

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

Because these are boxes, the caller must provide the box references. The factory
can create the boxes, but it cannot magically add them to the transaction's
access list.

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
funding for the factory and the child app. It covers:

- child app creation MBR, paid by the factory app account because the factory
  is the creator
- factory registry box MBR
- the inner payment that funds the child pool app account
- safety margin for LocalNet variation and future edits

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
schema, and extra program pages for `FactoryPool`. The submitted inner
application call returns an inner transaction object, and `created_app` is the
newly allocated application.

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

::: {.note}
**Note.** The manual `compile_contract` + `itxn.ApplicationCall` +
`arc4_signature` + `from_log` pattern shows exactly what happens on the
wire. In production code you can let the compiler do this plumbing with the
typed helpers `arc4.arc4_create(...)` / `arc4.abi_call(...)` (or
`itxn.abi_call`, puyapy 5.7+), which handle schema, pages, selector
encoding, and return-value decoding for you.
:::

The `assets=(asset_a, asset_b)` entry makes the dependency visible. The child
pool inspects the asset parameters and opts into both assets, so those assets
must be available to the inner app call. Under AVM v9+ group resource sharing
the outer call's `asset_references` would also make them available; the chapter
passes them explicitly so the dependency is easy to see.

Finally, the factory writes the canonical registry entries:

```python
self.pools[key] = pool_app.id
self.lp_tokens[key] = lp_token_id
return pool_app.id, lp_token_id
```

### Driving the Factory from a Client

The contract code above is only half of the picture. The caller has to name
every box and asset the factory will touch, because the AVM refuses to read a
resource the transaction did not declare. What follows is the client side of
the same `create_pool` call, taken from `scripts/run_amm_factory.py`; imports
and repeated funding boilerplate stay in the project.

The workflow connects to LocalNet, creates three throwaway accounts, and funds
them from the LocalNet dispenser:

```python
algorand = AlgorandClient.default_localnet()
algorand.set_suggested_params_cache_timeout(0)

dispenser = algorand.account.localnet_dispenser()
admin = algorand.account.random()
trader = algorand.account.random()
second_lp = algorand.account.random()

for account in (admin, trader, second_lp):
    algorand.send.payment(
        PaymentParams(
            sender=dispenser.address,
            signer=dispenser.signer,
            receiver=account.address,
            amount=AlgoAmount.from_micro_algo(10_000_000),
        )
    )
```

The factory is deployed like any other typed-client contract:

```python
factory_factory = amm_factory_client.AmmFactoryFactory(
    algorand,
    default_sender=admin.address,
    default_signer=admin.signer,
)
factory, create_result = factory_factory.send.create.bare()
```

The demo creates two ASAs and sorts them. This is the same canonical-ordering
rule used by the {{ch:amm}} pool:

```python
created_a = algorand.send.asset_create(
    AssetCreateParams(
        sender=admin.address,
        signer=admin.signer,
        total=1_000_000_000_000,
        decimals=6,
        asset_name="Factory A",
        unit_name="FCTA",
        default_frozen=False,
    )
)
created_b = algorand.send.asset_create(
    AssetCreateParams(
        sender=admin.address,
        signer=admin.signer,
        total=1_000_000_000_000,
        decimals=6,
        asset_name="Factory B",
        unit_name="FCTB",
        default_frozen=False,
    )
)
token_a = created_a.asset_id
token_b = created_b.asset_id
if token_a > token_b:
    token_a, token_b = token_b, token_a
```

The factory stores two boxes for the pair: one mapping the pair to the pool app
ID, and one mapping the pair to the LP token ID. Because boxes must be declared
on the transaction, the client constructs the exact box names:

```python
pair_key = token_a.to_bytes(8, "big") + token_b.to_bytes(8, "big")
pool_box = b"p_" + pair_key
lp_box = b"l_" + pair_key
```

Creating a pool is a single outer app call with one grouped payment. The payment
funds the factory account so it can pay the new child application's creation
MBR, create the registry boxes, and send bootstrap funding to the child pool:

```python
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
```

That one outer call pays for several inner transactions: the factory creates the
pool app, pays the pool app account, calls the pool's `bootstrap` method, and
the child pool creates its LP token and opts into both pool assets. The chapter
code sets every inner transaction fee to zero, so the outer app call must
provide enough pooled fee.

Past that point the workflow does nothing new. Users opt into the LP token, add
initial liquidity, swap, add liquidity again at the moved ratio, and remove
liquidity --- exactly as they did in {{ch:amm}}, in the same order, with the same
grouped-transaction shapes, because it **is** the same contract. The only
difference is where the client gets the app ID:

```python
pool = factory_pool_client.FactoryPoolClient(
    algorand=algorand,
    app_id=pool_id,
    default_sender=admin.address,
    default_signer=admin.signer,
)
```

In {{ch:amm}} that app ID came back from a deployment the user performed. Here it
came back from `create_pool`. The factory changes where a pool comes from and
who vouches for it; it does not change how the pool prices a swap. If you want
to re-read those calls, they are in {{ch:amm}} --- and in
`projects/chapter6/amm-factory/scripts/run_amm_factory.py`, which runs them
against the factory-created pool.


## Verifying a Pool

The factory exposes simple lookups:

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
pool's own state agrees."


### Calling Verification from a Client

The client side of `verify_pool` is short, and every line of it is a resource
declaration. Any downstream caller --- a farm, a router, a frontend --- asks the
factory this same question before it trusts an app ID:

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
```

The `app_references` entry lets the factory inspect the candidate pool's app
parameters and global state. The `box_references` entries let it read the
factory-owned registry boxes.


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

{{fig:provenance-trust-graph}} draws both claims side by side and marks which
arrows an attacker can forge. Every arrow that originates inside the caller is
forgeable, because the caller wrote it. The one arrow that is not is the entry
the factory itself recorded in its own box --- and that is the only one worth
checking.

{{include-fig:provenance-trust-graph}}

That is why the verification method combines both sides. {{tbl:factory-provenance-checks}} summarizes
the checks used by `verify_pool`.

Table: Provenance checks used by `verify_pool` {#tbl:factory-provenance-checks}

| Check | What it proves |
|-------|----------------|
| `candidate_pool.creator == factory_address` | The app was created by this factory address |
| `pools[pair] == candidate_pool.id` | The factory registry recognizes it as canonical |
| child `asset_a`/`asset_b` match | The pool state agrees with the requested pair |
| child `factory_app_id` matches | The child recorded the factory caller during bootstrap |
| child LP token matches registry | Consumers receive the token the factory recorded |

No single check carries the whole security argument. Together, they form a
useful provenance proof for this book's AMM architecture.

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
authority on which app is canonical for a pair --- so a second pool cannot claim
the slot, and a pool nobody registered cannot claim to be in it.

## Testing the Factory

The project includes both static shape tests and LocalNet integration tests.
The shape tests check the design invariants that should not disappear during
refactors:

```python
def test_verify_pool_uses_registry_creator_and_child_state() -> None:
    source = read_factory()
    assert "registered_pool != candidate_pool.id" in source
    assert "candidate_pool.creator != Global.current_application_address" in source
    assert 'Bytes(b"factory_app_id")' in source
    assert "pool_factory == Global.current_application_id.id" in source
    assert "pool_lp_token == self.lp_tokens.get" in source
```

The LocalNet tests exercise the behavior:

- factory creates and verifies a registered pool
- duplicate creation fails
- liquidity and swaps work on the factory-created pool
- a directly deployed fake pool fails factory verification

Before you read the fake-pool test, predict which check should fail. The fake
pool has the same code, but it was not created by the factory and it is not the
registered pool for the pair.

That test proves that "this contract has the same code" is not the same thing
as "this contract is the canonical pool for this pair."

## Summary

In this chapter you learned to:

- Move from client-side pool deployment to an on-chain AMM factory
- Create a child application from a PuyaPy contract using `compile_contract`
  and an inner `ApplicationCall`
- Fund the child app account before it creates assets or opts into ASAs
- Store canonical asset-pair mappings in factory-owned boxes
- Distinguish weak pool claims from strong factory-backed provenance
- Verify a pool using the factory registry, app creator, and child global state
- Test duplicate-pair and fake-pool rejection paths

{{tbl:factory-summary}} summarizes the chapter's key takeaways.

Table: Key takeaways for the AMM factory chapter {#tbl:factory-summary}

| Concept | Key Takeaway |
|---------|--------------|
| On-chain factory | The protocol, not the client, creates canonical pools |
| Pair registry | Ordered pair keys prevent duplicate or reversed pools |
| Child app creation | A factory can create contracts with inner app calls |
| MBR flow | The factory needs seed funding, and the child needs bootstrap funding |
| Provenance | Creator checks are useful but not sufficient alone |
| Verification | Registry + creator + child state gives downstream contracts confidence |

## Exercises

1. **(Understand)** Trace `verify_pool` for the happy path. For each check,
   write down which transaction reference or state value makes the check
   possible.
2. **(Analyze)** Trace `verify_pool` for the fake-pool path. Which check fails
   first? Which later checks would also fail if execution continued?
3. **(Analyze)** Explain why `factory_app_id` in the child pool is useful but
   insufficient. What can a malicious clone write in its own global state?
4. **(Create)** Design the change a yield farm would need to accept only
   factory-verified LP tokens. Which app, asset, and box references would the
   farm call need?
5. **(Create)** Sketch a router that asks the factory for the canonical pool
   before quoting a swap. Where should the router reject an unknown pair?
6. **(Apply)** Add the {{ch:amm}} TWAP oracle back to `FactoryPool` using the
   following hints.

### Exercise Hint: Adding TWAP Back

The factory-created pool omits TWAP so the chapter can focus on contract
creation and provenance. Adding TWAP back is deliberately left as an exercise.
It is not conceptually hard, but there are a few details to handle carefully:

1. Copy the {{ch:amm}} cumulative price fields into `FactoryPool`.
2. Initialize `twap_last_update` when initial liquidity is added, not during
   factory bootstrap. Before liquidity exists, there is no meaningful price.
3. Call `_update_twap()` before reserve mutations in `swap`, `add_liquidity`,
   and `remove_liquidity`.
4. Compile-test the factory after adding TWAP. The factory embeds the child
   pool's compiled bytecode, so child program size can affect the factory.
5. Keep `verify_pool` focused on identity. A TWAP consumer should separately
   verify the oracle fields it depends on.

If compile size becomes tight, split optional oracle functionality into a later
extension rather than obscuring the factory pattern with size workarounds.

## Before You Continue

Before starting the yield farming chapter, you should be able to:

- [ ] Create a child application from a factory contract using
  `compile_contract` and an inner `ApplicationCall`
- [ ] State the three provenance checks (registry entry, app creator, child
  global state) and explain why each alone is insufficient
- [ ] Explain who funds which MBR at each step: the caller seeds the factory,
  the factory pays the child-creation and registry-box MBR, and the factory's
  inner payment covers the child's opt-ins and LP token

If any of these are unclear, revisit the relevant section before proceeding.

Further reading:

- [Algorand Python transactions][algopy-transactions] --- inner transactions
  and inner application calls
- [PuyaPy compile_contract][puya-compile] --- obtaining child bytecode inside
  another contract
- [Algorand Python ARC-4][algopy-arc4] --- ARC-4 method encoding and inner
  ABI calls
- [Algorand Python storage][algopy-storage] --- `BoxMap` and box-reference
  requirements
- [Inner transaction fees][algorand-fees] --- fee pooling and why inner fees
  are set to zero

In the next chapter, we extend the AMM system with a yield farming contract.
That chapter keeps factory verification out of the main path so the reward
accumulator remains the central idea. Treat factory-backed provenance as the
natural production extension: before accepting LP tokens from an AMM pool, a
farm can ask the factory whether that pool is canonical.

[algopy-transactions]: https://dev.algorand.co/algokit/languages/python/lg-transactions/
[puya-compile]: https://algorandfoundation.github.io/puya/lg-compile.html
[algopy-arc4]: https://algorandfoundation.github.io/puya/api-algopy.arc4.html
[algopy-storage]: https://algorandfoundation.github.io/puya/lg-storage.html
[algorand-fees]: https://dev.algorand.co/concepts/transactions/fees/
