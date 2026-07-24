\newpage

# AMM Factory and Pool Provenance

Chapter 5 built one AMM pool. That is enough to understand liquidity,
constant-product pricing, LP tokens, and swap safety. It is not enough to run a
DEX.

A DEX needs a way to answer questions like:

- Is there already a pool for this pair?
- Which pool is canonical for `asset_a`/`asset_b`?
- Did this pool come from our protocol, or did someone deploy a lookalike?
- Can another contract, such as a farm or router, safely trust this pool?

In Chapter 5, the client deployed a pool directly. That is the *client-side
factory* pattern: the SDK creates an app, bootstraps it, and remembers the app
ID. In this chapter, we move that authority on-chain. The factory application
creates pool applications using inner transactions, stores the canonical pool
for each ordered pair in box storage, and exposes a verification method that
downstream contracts can use before trusting a pool.

The finished project lives in `projects/chapter6/amm-factory/`.

## Run It First!

The finished project creates a factory, asks it to create a pool for two test
ASAs, verifies the pool, performs a normal liquidity/swap workflow, rejects a
duplicate pair, and rejects a fake pool that was deployed directly by a user.

Run the workflow once:

```bash
cd projects/chapter6/amm-factory
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_amm_factory
```

Then run the tests:

```bash
algokit project run test
```

Table 6-1 lists the output checkpoints to compare against the workflow output.

Table 6-1. Output checkpoints for the AMM factory workflow

| Output checkpoint | What to watch for |
|-------------------|-------------------|
| Factory app ID and address | The factory app account can send inner transactions |
| Factory-created pool app ID | The pool was created by the factory, not by the user directly |
| LP token ID | The child pool created its LP token during bootstrap |
| Registered pool accepted | `verify_pool` returned true for the factory-created pool |
| Initial LP minted | The pool accepted its first matched liquidity deposits |
| Swap output | The factory-created pool still behaves like an AMM |
| Later LP minted | A second LP added liquidity after prices moved |
| Removed liquidity | The second LP burned LP tokens and received both assets |
| Duplicate pool rejected | The pair registry prevented a second canonical pool |
| Fake pool rejected | A directly deployed pool did not pass provenance checks |

This chapter is a guided tour of the finished factory project rather than a
line-by-line scaffold. As you trace it, keep three ideas in view:

- the factory pays for and creates the child app
- the registry decides which pool is canonical for a pair
- verification combines registry state, app creator, and child global state

The runnable script uses helpers to keep the file short while you iterate, but
the important setup and contract calls are shown here explicitly.

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
rule used by the Chapter 5 pool:

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

Once the factory has registered the pool, downstream callers can ask the factory
whether an app is the canonical pool for a pair:

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

The rest of the workflow uses the factory-created pool like the Chapter 5 pool:
users opt into the LP token, add initial liquidity, swap, add later liquidity,
and remove liquidity. The opt-in loop is just ordinary asset opt-in calls:

```python
for account in (admin, trader, second_lp):
    for asset_id in (token_a, token_b, lp_token):
        algorand.send.asset_opt_in(
            AssetOptInParams(
                sender=account.address,
                signer=account.signer,
                asset_id=asset_id,
            ),
            send_params=SendParams(suppress_log=True),
        )
```

The factory changes where the pool comes from, not how the pool prices swaps.
The workflow instantiates the pool client by using the app ID returned by the
factory:

```python
pool = factory_pool_client.FactoryPoolClient(
    algorand=algorand,
    app_id=pool_id,
    default_sender=admin.address,
    default_signer=admin.signer,
)
```

Initial liquidity is two grouped asset transfers plus the pool app call:

```python
initial_a = 10_000 * MICRO_UNITS
initial_b = 10_000 * MICRO_UNITS
deposit_a_txn = algorand.create_transaction.asset_transfer(
    AssetTransferParams(
        sender=admin.address,
        receiver=pool.app_address,
        asset_id=token_a,
        amount=initial_a,
    )
)
deposit_b_txn = algorand.create_transaction.asset_transfer(
    AssetTransferParams(
        sender=admin.address,
        receiver=pool.app_address,
        asset_id=token_b,
        amount=initial_b,
    )
)
initial_lp = pool.send.add_initial_liquidity(
    factory_pool_client.AddInitialLiquidityArgs(
        deposit_a=TransactionWithSigner(deposit_a_txn, admin.signer),
        deposit_b=TransactionWithSigner(deposit_b_txn, admin.signer),
    ),
    params=CommonAppCallParams(
        sender=admin.address,
        signer=admin.signer,
        static_fee=AlgoAmount.from_micro_algo(2_000),
        asset_references=[token_a, token_b, lp_token],
    ),
).abi_return
```

A swap is one grouped asset transfer plus the pool app call. The caller chooses
`min_output` off-chain to express slippage tolerance:

```python
swap_input = 100 * MICRO_UNITS
input_with_fee = swap_input * 997
expected_output = (input_with_fee * initial_b) // (
    initial_a * 1000 + input_with_fee
)
algorand.send.asset_transfer(
    AssetTransferParams(
        sender=admin.address,
        signer=admin.signer,
        receiver=trader.address,
        asset_id=token_a,
        amount=1_000 * MICRO_UNITS,
    )
)
swap_txn = algorand.create_transaction.asset_transfer(
    AssetTransferParams(
        sender=trader.address,
        receiver=pool.app_address,
        asset_id=token_a,
        amount=swap_input,
    )
)
swap_output = pool.send.swap(
    factory_pool_client.SwapArgs(
        input_txn=TransactionWithSigner(swap_txn, trader.signer),
        min_output=expected_output * 99 // 100,
    ),
    params=CommonAppCallParams(
        sender=trader.address,
        signer=trader.signer,
        static_fee=AlgoAmount.from_micro_algo(2_000),
        asset_references=[token_a, token_b],
    ),
).abi_return
```

After the swap, the second LP adds roughly proportional liquidity at the new
reserve ratio:

```python
reserve_a_after_swap = initial_a + swap_input
reserve_b_after_swap = initial_b - swap_output
later_a = 1_000 * MICRO_UNITS
later_b = later_a * reserve_b_after_swap // reserve_a_after_swap
algorand.send.asset_transfer(
    AssetTransferParams(
        sender=admin.address,
        signer=admin.signer,
        receiver=second_lp.address,
        asset_id=token_a,
        amount=later_a,
    )
)
algorand.send.asset_transfer(
    AssetTransferParams(
        sender=admin.address,
        signer=admin.signer,
        receiver=second_lp.address,
        asset_id=token_b,
        amount=later_b,
    )
)
later_a_txn = algorand.create_transaction.asset_transfer(
    AssetTransferParams(
        sender=second_lp.address,
        receiver=pool.app_address,
        asset_id=token_a,
        amount=later_a,
    )
)
later_b_txn = algorand.create_transaction.asset_transfer(
    AssetTransferParams(
        sender=second_lp.address,
        receiver=pool.app_address,
        asset_id=token_b,
        amount=later_b,
    )
)
later_lp = pool.send.add_liquidity(
    factory_pool_client.AddLiquidityArgs(
        deposit_a=TransactionWithSigner(later_a_txn, second_lp.signer),
        deposit_b=TransactionWithSigner(later_b_txn, second_lp.signer),
    ),
    params=CommonAppCallParams(
        sender=second_lp.address,
        signer=second_lp.signer,
        static_fee=AlgoAmount.from_micro_algo(2_000),
        asset_references=[token_a, token_b, lp_token],
    ),
).abi_return
```

Then the same LP burns part of that position and receives both pool assets:

```python
burn_lp = later_lp // 2
burn_txn = algorand.create_transaction.asset_transfer(
    AssetTransferParams(
        sender=second_lp.address,
        receiver=pool.app_address,
        asset_id=lp_token,
        amount=burn_lp,
    )
)
removed_a, removed_b = pool.send.remove_liquidity(
    factory_pool_client.RemoveLiquidityArgs(
        lp_deposit=TransactionWithSigner(burn_txn, second_lp.signer),
        min_a=1,
        min_b=1,
    ),
    params=CommonAppCallParams(
        sender=second_lp.address,
        signer=second_lp.signer,
        static_fee=AlgoAmount.from_micro_algo(3_000),
        asset_references=[token_a, token_b, lp_token],
    ),
).abi_return
```

Finally, the workflow proves the failure cases:

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

The important security lesson is subtle: a pool claiming "my factory is app
123" is not enough. A malicious clone can store the same global-state value.
The factory's own registry has to be part of the answer.

## From One Pool to a Protocol

The Chapter 5 pool is an excellent standalone contract. It holds exactly two
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

The child pool is a close cousin of the Chapter 5 AMM. It keeps:

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

> **Note.** The manual `compile_contract` + `itxn.ApplicationCall` +
> `arc4_signature` + `from_log` pattern shows exactly what happens on the
> wire. In production code you can let the compiler do this plumbing with the
> typed helpers `arc4.arc4_create(...)` / `arc4.abi_call(...)` (or
> `itxn.abi_call`, puyapy 5.7+), which handle schema, pages, selector
> encoding, and return-value decoding for you.

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

That is why the verification method combines both sides. Table 6-2 summarizes
the checks used by `verify_pool`.

Table 6-2. Provenance checks used by `verify_pool`

| Check | What it proves |
|-------|----------------|
| `candidate_pool.creator == factory_address` | The app was created by this factory address |
| `pools[pair] == candidate_pool.id` | The factory registry recognizes it as canonical |
| child `asset_a`/`asset_b` match | The pool state agrees with the requested pair |
| child `factory_app_id` matches | The child recorded the factory caller during bootstrap |
| child LP token matches registry | Consumers receive the token the factory recorded |

No single check carries the whole security argument. Together, they form a
useful provenance proof for this book's AMM architecture.

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

Table 6-3 summarizes the chapter's key takeaways.

Table 6-3. Key takeaways for the AMM factory chapter

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
6. **(Apply)** Add the Chapter 5 TWAP oracle back to `FactoryPool` using the
   following hints.

### Exercise Hint: Adding TWAP Back

The factory-created pool omits TWAP so the chapter can focus on contract
creation and provenance. Adding TWAP back is deliberately left as an exercise.
It is not conceptually hard, but there are a few details to handle carefully:

1. Copy the Chapter 5 cumulative price fields into `FactoryPool`.
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
