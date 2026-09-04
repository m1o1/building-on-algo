\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Project}}
```
# A Constant Product AMM

Chapter 13 ended with a two-sided quote that rounds against the asker, and a promise: the pool those answers belong to. This chapter builds it. The quote becomes a `swap` that moves real ASAs instead of returning a number, the minting arithmetic of Example 13-5 and Example 13-10 becomes an LP token the contract creates for itself, and every division you classified in Example 13-6 gets a reserve to protect. The contract is the market maker --- no order book, no counterparty --- which is the model Uniswap runs on Ethereum and Tinyman and Pact run on Algorand.

By the end of this chapter you will have a working AMM pool contract with creation, bootstrapping, swapping, liquidity provision, liquidity withdrawal, and comprehensive security hardening.

## Run It First

The finished project for this chapter is in
`projects/constant-product-amm/`. Run the complete workflow once before
reading the implementation: it bootstraps a pool over two test ASAs, seeds it
with liquidity, executes a swap, adds and removes liquidity at the new ratio,
and prints every intermediate amount. Before you run it, predict why the two
asset IDs are sorted, why a swap needs a `min_output`, and why later liquidity
deposits mint LP tokens from the *current* reserve ratio rather than the
original one.

```bash
cd projects/constant-product-amm
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_constant_product_amm
algokit project run test
```

Table 14-1 lists the output checkpoints to compare against the
workflow output.

: Table 14-1. Output checkpoints for the constant-product AMM workflow

| Output checkpoint | What to watch for |
|-------------------|-------------------|
| Sorted asset IDs | The lower ID always becomes `asset_a`, so every caller agrees on which side is which |
| LP token ID | The pool created its own ASA during bootstrap and opted into both trading assets |
| Initial LP minted | The first deposits set the price; there is nothing to price them against yet |
| Swap output: roughly 98--99 Token B for 100 Token A | The 0.3% fee and the price impact are both visible. Amounts print in base units, so an output near `98,000,000` at 6 decimals is about 98 whole tokens |
| Second LP minted | A later deposit mints from the post-swap reserve ratio, not the original one |
| Two withdrawn amounts | Burning LP tokens returns a proportional share of *both* assets |
| Test suite passes | If pytest reports skipped LocalNet tests, only the source-level property checks ran; compilation was the earlier `build` step |

The finished contract also contains the optional TWAP oracle from the end of
this chapter; the workflow above exercises the core AMM only. Without Docker or
Podman, `algokit project run test-static` still reads the contract source and
asserts that the security properties this chapter teaches are present, with no
compiler and no network; the compile itself is the `algokit project run build`
step already in the runbook.

Keep the project nearby as you work: it is the answer key you can compile, run,
and compare against whenever a snippet feels abstract. The sections that follow
rebuild that workflow in the same order: scaffold the project, define pool
state, bootstrap the LP token, add the first liquidity, execute swaps, add and
remove later liquidity, add the optional TWAP oracle, and finish with tests.


## What You Need First

Chapter 13 ended with a Handoff table naming what this project would lean
on. Table 14-2 is the other side of it, together with the
examples from Part I the pool assumes on its first page. Use it
now, to see what the pool is made of before any of it is in front of you, and
later, when a line assumes something you would rather look up than reconstruct.

Answer the predict column before you follow the link.

: Table 14-2. What Chapter 13 built that this project assumes

| Prerequisite | Where it lands here | Predict before you read it |
|--------------|---------------------|----------------------------|
| Example 13-13 | `swap`, whose output calculation is that arithmetic with assets attached | The example returns a number; this method moves tokens. Which of its two quote directions does a swap need, and what happens to the other? |
| Example 13-5 | `add_initial_liquidity`, minting LP tokens against an empty pool | There is no exchange rate until somebody sets one. Say what the first depositor's shares should be worth, then check whether the geometric mean agrees. |
| Example 13-10 | `MINIMUM_LIQUIDITY = 1000` and the guard beside it | The pool locks 1,000 shares forever. Work out what that costs a pool seeded with 10,000 units, and decide whether you would raise or lower it. |
| Example 13-6 | Every division in the swap and in liquidity removal | This contract has more than two divisions. For each one, decide which way it leans before you look, and expect at least one to surprise you. |
| Example 13-11 | The optional TWAP section's `_update_twap`, wired in at the end of the chapter | The pool accumulates on every swap, mint and burn. Say why all three, and what would be wrong with accumulating on swaps alone. |
| Example 13-9 | The deployment scripts' expected-output checks | Those scripts assert on exact integers. Say what would have to be true for a float to be safe there, and whether it ever is. |
| Example 7-8 | Every method that takes tokens from a caller | The transfer arrives as a typed argument. Name the four questions it does not answer for you. |
| Example 7-17 | `bootstrap`, opting the pool into both assets before it can hold either | Two opt-ins and an LP token to create. Work out what the pool account must hold before any of it can run. |
| Example 7-14 | The strict `asset_a.id < asset_b.id` guard, and the exploit it exists for | Both sides of the pool are `Asset` arguments. Say what a swap computes when they name one asset. |
| Example 7-4 | Every inner transfer the pool sends | A swap is one app call and one inner transfer. Write the pooled-fee arithmetic before you read it. |

## Project Setup

You are already in `projects/constant-product-amm/` from Run It First. If you would rather scaffold your own, Chapter 9's setup note applies unchanged, with `constant_product_pool` in place of `token_vesting`.

Your contract code goes in `smart_contracts/constant_product_pool/contract.py`. Replace the template-generated contents of `contract.py` with the code shown below; do not append to the existing template code. Also delete the template-generated `deploy_config.py` in the renamed directory, which references the old `HelloWorld` contract.

## The Arithmetic This Pool Inherits

Every number in this contract was priced in Chapter 13; this chapter's job is to attach assets to it. The swap output is Example 13-13's repaired quote --- the expression that never forms a price and divides exactly once:

$$\Delta y = \frac{\Delta x \times 997 \times y}{x \times 1000 + \Delta x \times 997}$$

The $997/1000$ factor is the thirty basis points of Example 13-8, staying in the reserves so that the product $x \times y$ only ever rises across a trade. The first deposit mints $\sqrt{\Delta x \times \Delta y} - \text{MINIMUM\_LIQUIDITY}$ LP tokens, which is Example 13-5's geometric mean less Example 13-10's lock. One rule here *is* new: a later deposit of both assets mints the smaller of its two proportional claims, and the section that implements it says why.

What the formula bills this chapter's own pool: seed 10,000 of each token, send 100 of token A, and $\Delta y = 997{,}000{,}000 \, / \, 10{,}099{,}700 \approx 98.71$ comes out --- 0.3 withheld by the fee, the rest of the shortfall the price impact of walking down the curve. Figure 13-1, back in Chapter 13, plots that walk against a smaller pool, where it is impossible to miss. Those are the numbers to hold in mind at the first LocalNet checkpoint.

::: {.note}
**Design decision: why constant product?** If I were designing this from scratch, I would start with the simplest invariant: what relationship between reserves should never be violated? The product $x \times y = k$ is the simplest nonlinear invariant. It is not the only option.

*Concentrated liquidity* (Uniswap V3 - no equivalent on Algorand) lets LPs provide liquidity within a chosen price range instead of across the entire curve. An LP who concentrates in a ±1% range provides roughly 200x the capital efficiency of a full-range V2 position, and an extremely tight ±0.05% range (practical only for stable pairs) approaches ~4,000x, but their position becomes an NFT (each range is unique), and they suffer amplified impermanent loss if price leaves their range. V3 is powerful but significantly more complex to implement, especially within Algorand's 8,192-byte free program ceiling (2 KB base plus extra pages; Appendix B) and 700-opcode-per-call budget.

*StableSwap* (Curve, and Pact stable pools on Algorand) uses a hybrid invariant tuned for assets that should trade near 1:1 (stablecoins, wrapped assets). It provides dramatically lower slippage for pegged pairs.

Constant product is the right starting point because it is simple enough to reason about completely, requires no off-chain infrastructure for active management, and is the foundation that V3 and StableSwap build upon. Master this, and the others are variations on the theme.
:::

## Pool Contract Creation and the Escrow Pattern

Each asset pair gets its own contract instance, one pool per pair. This provides strong isolation: a vulnerability in one pool cannot drain another. The alternative (a single contract managing all pools) would be simpler to deploy but catastrophically worse if compromised.

The contract will hold both pool assets plus the LP token it creates. Its address acts as an autonomous escrow: no private key exists, and the contract's logic is the sole authority over outflows. (See [Applications](https://dev.algorand.co/concepts/smart-contracts/apps/) for how contract addresses are derived.) This is the same escrow pattern from the vesting contract, but now holding three different assets and serving many concurrent users. In production, a *factory contract* handles deployment: it creates a new pool contract instance for each asset pair, registers the pair in its own state for lookup, and enforces that no duplicate pools exist. (Chapter 16 builds it.)

The state declarations should look familiar from the vesting contract, with a few additions.

Add the following to `smart_contracts/constant_product_pool/contract.py`:

```python
from algopy import (
    ARC4Contract, Asset, BigUInt, Global, GlobalState, Txn, UInt64,
    arc4, itxn, op, subroutine, gtxn,
)

MINIMUM_LIQUIDITY = 1000

class ConstantProductPool(ARC4Contract):
    def __init__(self) -> None:
        self.asset_a = GlobalState(UInt64(0))
        self.asset_b = GlobalState(UInt64(0))
        self.lp_token_id = GlobalState(UInt64(0))
        # We track reserves explicitly rather than reading the contract's
        # asset balance. Chapter 7 compares both approaches.
        self.reserve_a = GlobalState(UInt64(0))
        self.reserve_b = GlobalState(UInt64(0))
        self.lp_total_supply = GlobalState(UInt64(0))
        self.locked_liquidity = GlobalState(UInt64(0))
        self.is_bootstrapped = GlobalState(UInt64(0))

    @arc4.baremethod(create="require")
    def create(self) -> None:
        pass

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "Contract is immutable"
```

The pool uses global state rather than box storage for its reserves and configuration, and it is the right choice here: the data is small (eight fields), belongs to the application itself rather than to any user, and is read on every operation. Global state has a 64-pair limit, but this contract is nowhere near it.

One property of application state deserves a moment before it costs you one.

::: {.gotcha #schema-for-future-fields topic="Global and local state" title="Declare schema for every field the deployed contract will ever need"}
This pool refuses updates, so its state schema is fixed at creation (Chapter 4: local schema can never grow; global schema grows only if you allow updates) and a field added after deployment has nowhere to live. Budget slots for planned features at deployment time, even ones you have not written yet. The TWAP oracle later in this chapter adds three fields the listing above does not reserve, which is why adding it costs a fresh deployment rather than an in-place grow. On LocalNet the mistake costs nothing, because every run deploys fresh; on MainNet it costs a redeployment and a liquidity migration.
:::


## Bootstrapping the Pool

Bootstrapping is the one-time initialization that creates the LP token, opts the contract into both pool assets, and establishes the pool's identity. This is more involved than the vesting contract's `initialize` because it creates a new ASA (the LP token) and performs two asset opt-ins.

The `asset_a.id < asset_b.id` guard is Example 13-2's line, now holding real assets: strict ordering fixes which asset every price is quoted in, refuses a pool of an asset against itself, and --- the reason Chapter 16's factory wants the same line --- leaves each pair exactly one place for its liquidity to live. (See [Asset Metadata](https://dev.algorand.co/concepts/assets/asset-metadata/) for how asset IDs are assigned.)

Add this method to the `ConstantProductPool` class in `smart_contracts/constant_product_pool/contract.py`:

```python
    @arc4.abimethod
    def bootstrap(
        self,
        seed_payment: gtxn.PaymentTransaction,
        asset_a: Asset,
        asset_b: Asset,
    ) -> UInt64:
        """One-time pool initialization. Creates LP token, opts into assets."""
        assert Txn.sender == Global.creator_address, "Only creator can bootstrap"
        assert Global.group_size == UInt64(2), "Bootstrap group must be size 2"
        assert self.is_bootstrapped.value == UInt64(0), "Already bootstrapped"
        assert asset_a.id < asset_b.id, "Assets must be in canonical order"

        assert asset_a.clawback == Global.zero_address, "Asset A has clawback"
        assert asset_a.freeze == Global.zero_address, "Asset A has freeze"
        assert not asset_a.default_frozen, "Asset A is frozen by default"
        assert asset_b.clawback == Global.zero_address, "Asset B has clawback"
        assert asset_b.freeze == Global.zero_address, "Asset B has freeze"
        assert not asset_b.default_frozen, "Asset B is frozen by default"

        # Seed payment funds app-account MBR for base balance,
        # LP token creation, and 2 asset opt-ins.
        assert seed_payment.sender == Txn.sender, "Seed payment sender mismatch"
        assert (
            seed_payment.receiver == Global.current_application_address
        ), "Seed payment receiver is not the pool"
        assert seed_payment.amount >= UInt64(400_000), "Insufficient MBR seed"

        self.asset_a.value = asset_a.id
        self.asset_b.value = asset_b.id

        # Create the LP token via inner transaction
        lp_create = itxn.AssetConfig(
            asset_name=b"CPMM-LP",
            unit_name=b"LP",
            # 2^63 ≈ 9.2 quintillion: large enough that LP math
            # never runs out, safely below UInt64 max (2^64-1).
            total=UInt64(2**63),
            decimals=UInt64(6),
            default_frozen=False,
            manager=Global.current_application_address,
            reserve=Global.current_application_address,
            freeze=Global.zero_address,
            clawback=Global.zero_address,
            fee=UInt64(0),
        ).submit()
        self.lp_token_id.value = lp_create.created_asset.id

        # Opt into both pool assets
        itxn.AssetTransfer(
            xfer_asset=asset_a,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()

        itxn.AssetTransfer(
            xfer_asset=asset_b,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()

        self.is_bootstrapped.value = UInt64(1)
        return self.lp_token_id.value
```

The LP token has a total supply of $2^{63}$, large enough that the pool will never exhaust it. Setting `freeze` and `clawback` to the zero address makes the token permissionless. The manager and reserve are set to the pool contract itself, though in practice these have no operational significance for an LP token.

In the seed payment pattern, the caller sends Algo to fund the application account's MBR for the LP token creation (100,000 microAlgos), the two asset opt-ins (100,000 each), the app account's base balance, and a buffer. The global-state schema MBR is different: it is paid by the creator account when the application is created, not by this bootstrap seed payment.

The outer group has two transactions: the seed payment and the app call. The app call submits three inner transactions (LP creation plus two asset opt-ins), so the app call needs to cover its own 1,000 microAlgo fee plus 3,000 microAlgos of inner transaction fees. With fee pooling, `static_fee = 4000` on the app call, plus the seed payment's default 1,000 fee, provides sufficient coverage.

Because `bootstrap` reads `asset_a.clawback`, `asset_a.freeze`, `asset_a.default_frozen`, and the same fields for `asset_b`, the client must include both ASAs in the app call's asset references. Algorand Python's default resource encoding passes resource arguments by value, but the protocol still needs those assets available to the transaction.

## Deploying and Bootstrapping on LocalNet

Deploy the pool contract and bootstrap it with two test tokens on LocalNet. This verifies that everything compiles and the bootstrap sequence works before you add more methods.

The contract file should now hold the `ConstantProductPool` class with the `__init__`, `create`, `reject_lifecycle`, and `bootstrap` methods. Compile:

```bash
algokit project run build
```

The AMM contract uses more imports than the vesting contract; make sure you have `Asset`, `BigUInt`, `Global`, `GlobalState`, `Txn`, `UInt64`, `arc4`, `itxn`, `op`, `subroutine`, and `gtxn`.

The build also regenerates the typed client in `smart_contracts/artifacts/constant_product_pool/`, and every client-side script in this chapter uses it --- the same style the finished project, its tests, and the next three chapters use.

Save the following as `deploy_pool.py` in your project root. This client-side script creates two test ASAs, deploys the pool, funds it, and calls bootstrap.

```python
from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    AssetCreateParams,
    CommonAppCallParams,
    PaymentParams,
)
from algosdk.atomic_transaction_composer import TransactionWithSigner

from smart_contracts.artifacts.constant_product_pool import (
    constant_product_pool_client as amm_client,
)

algorand = AlgorandClient.default_localnet()
admin = algorand.account.localnet_dispenser()

# Create two test tokens
def create_test_asa(name: str, unit: str) -> int:
    result = algorand.send.asset_create(
        AssetCreateParams(
            sender=admin.address,
            total=10_000_000_000_000, decimals=6,
            asset_name=name, unit_name=unit,
        )
    )
    return result.asset_id

token_a = create_test_asa("TokenA", "TKA")
token_b = create_test_asa("TokenB", "TKB")
# Ensure canonical ordering (lower ID first)
if token_a > token_b:
    token_a, token_b = token_b, token_a
print(f"Token A: {token_a}, Token B: {token_b}")

# Deploy the pool contract.
# send.create.bare() always creates a new application. Earlier
# chapters used deploy(), which is idempotent (it reuses an existing
# app found by name). Every pool is its own app, so a fresh instance
# every time is the right choice here.
factory = amm_client.ConstantProductPoolFactory(
    algorand,
    default_sender=admin.address,
    default_signer=admin.signer,
)
pool, _ = factory.send.create.bare()
print(f"Pool App ID: {pool.app_id}")
print(f"Pool Address: {pool.app_address}")

# Bootstrap: fund the pool + call bootstrap.
# The seed payment travels as the method's first argument; the client
# places it as the preceding transaction in the group.
seed = algorand.create_transaction.payment(
    PaymentParams(
        sender=admin.address,
        receiver=pool.app_address,
        amount=AlgoAmount.from_micro_algo(500_000),
    )
)
result = pool.send.bootstrap(
    amm_client.BootstrapArgs(
        seed_payment=TransactionWithSigner(seed, admin.signer),
        asset_a=token_a,
        asset_b=token_b,
    ),
    params=CommonAppCallParams(
        static_fee=AlgoAmount.from_micro_algo(4_000),
        asset_references=[token_a, token_b],
    ),
)
lp_token_id = result.abi_return  # Return value from the bootstrap call
print(f"LP Token ID: {lp_token_id}")
print("Bootstrap complete!")
```

Run with `poetry run python deploy_pool.py` from the project root (the script imports the generated client by its package path, so the working directory matters). You should see three IDs printed: the two test tokens and the LP token. If you get `Already bootstrapped`, you are calling bootstrap on a pool that was already initialized; reset LocalNet with `algokit localnet reset` and try again.

You can verify the pool's state by reading its global state:

```bash
curl -s http://localhost:4001/v2/applications/YOUR_APP_ID \
  -H "X-Algo-API-Token: $ALGOD_TOKEN" \
  | python -m json.tool
```

The global state should show `asset_a`, `asset_b`, and `lp_token_id` populated with the correct ASA IDs, `is_bootstrapped` set to 1, and `reserve_a` and `reserve_b` both at 0 (no liquidity yet).


## Initial Liquidity Provision

The first liquidity provider sets the pool's initial price ratio by choosing how much of each token to deposit. The ratio of their deposit defines the starting price: depositing 1,000 USDC and 4 ALGO sets the price at 250 USDC per ALGO (or equivalently, 0.004 ALGO per USDC).

The minting arithmetic is Example 13-5 with real deposits behind it: the geometric mean, so the amount minted does not depend on the price level, less the 1,000 shares Example 13-10 burns to nobody. Those locked shares and the `assert` beside them are the two lines that close the first-depositor donation attack --- reread that example's gotcha if the mechanism has gone soft. (See the [`algopy.op` API reference](https://algorandfoundation.github.io/puya/api/algopy/algopyop/) for the `bsqrt` and wide arithmetic opcodes used here.)

Add this method to the `ConstantProductPool` class in `smart_contracts/constant_product_pool/contract.py`:

```python
    @arc4.abimethod
    def add_initial_liquidity(
        self,
        deposit_a: gtxn.AssetTransferTransaction,
        deposit_b: gtxn.AssetTransferTransaction,
    ) -> UInt64:
        """First deposit sets the price ratio and mints initial LP tokens."""
        assert (
            Global.group_size == UInt64(3)
        ), "Initial liquidity group must be size 3"
        assert self.is_bootstrapped.value == UInt64(1), "Not bootstrapped"
        assert (
            self.lp_total_supply.value == UInt64(0)
        ), "Liquidity already exists"

        assert deposit_a.sender == Txn.sender, "Asset A sender mismatch"
        assert deposit_b.sender == Txn.sender, "Asset B sender mismatch"
        assert (
            deposit_a.asset_receiver == Global.current_application_address
        ), "Receiver is not the pool"
        assert (
            deposit_b.asset_receiver == Global.current_application_address
        ), "Receiver is not the pool"
        assert deposit_a.xfer_asset == Asset(self.asset_a.value), "Wrong asset A"
        assert deposit_b.xfer_asset == Asset(self.asset_b.value), "Wrong asset B"

        amount_a = deposit_a.asset_amount
        amount_b = deposit_b.asset_amount
        assert amount_a > UInt64(0), "Zero asset A"
        assert amount_b > UInt64(0), "Zero asset B"

        # LP tokens = sqrt(a * b) - MINIMUM_LIQUIDITY
        # Use BigUInt for the intermediate product to prevent overflow.
        # op.btoi converts the BigUInt result back to UInt64, and it is safe
        # by construction for the reason the pricing chapter gives: both
        # amounts are UInt64, so the product is at most (2^64 - 1)^2 and its
        # root at most 2^64 - 1 -- exactly eight bytes, never nine.
        product = BigUInt(amount_a) * BigUInt(amount_b)
        sqrt_product = op.bsqrt(product)
        assert sqrt_product > MINIMUM_LIQUIDITY, "Initial liquidity too small"
        # Strictly greater, so the subtraction below lands on at least one
        # token. A second `lp_tokens > 0` check here would never fire.
        lp_tokens = op.btoi(sqrt_product.bytes) - UInt64(MINIMUM_LIQUIDITY)

        self.reserve_a.value = amount_a
        self.reserve_b.value = amount_b
        self.lp_total_supply.value = lp_tokens + UInt64(MINIMUM_LIQUIDITY)
        self.locked_liquidity.value = UInt64(MINIMUM_LIQUIDITY)

        # Send LP tokens to the provider
        itxn.AssetTransfer(
            xfer_asset=Asset(self.lp_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=lp_tokens,
            fee=UInt64(0),
        ).submit()

        return lp_tokens
```

The `BigUInt` multiplication prevents overflow in the product: if both amounts are 10^12, the product is 10^24, far beyond uint64. The `op.bsqrt` opcode computes the integer floor square root natively on the AVM.

The sender-binding checks are not redundant. The ABI router verifies that `deposit_a` and `deposit_b` are asset-transfer transactions, but it does not know that the LP tokens should go only to the account that sent both deposits. If Alice signs a group containing her two deposits and Bob's app call, Bob would receive the LP tokens unless the contract checks that both deposit senders equal `Txn.sender`.

::: {.check}
What relationship does the typed transaction argument prove, and what relationship does it *not* prove?
:::

One requirement sits outside the contract entirely, and the group's atomicity is what enforces it.

::: {.gotcha #lp-token-optin-first topic="ASAs" title="The caller must opt into the LP token before the pool can send it"}
The caller must have already opted into the LP token before calling `add_initial_liquidity`. If they have not, the inner `AssetTransfer` sending LP tokens will fail, and the entire atomic group rolls back: the pool receives no tokens and no state changes. This is the "lazy opt-in" pattern: the contract does not check the opt-in explicitly; the protocol enforces it automatically. Client code must perform a zero-amount self-transfer of the LP token before calling `add_initial_liquidity`.
:::


## The Swap

*Before looking at the implementation: given reserves of 10,000 USDC and 10,000 ALGO, how many ALGO should a trader receive for 100 USDC? Try working it out with the constant product formula (with 0.3% fee). Then: what is the new spot price after the swap? The answer may surprise you: it is not exactly 100, and the spot price shifts even for this relatively small trade.*

This is the operation users interact with most frequently. A trader sends token A to the pool and receives token B (or vice versa). The constant product formula determines the exchange rate, and a 0.3\% fee is deducted from the input.

The swap introduces a concept not needed in the vesting contract: *slippage protection*. (See [Atomic Groups](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/) for how grouped transactions provide all-or-nothing execution guarantees.) Between when a user fetches a price quote (reading reserves off-chain) and when their transaction executes, other swaps may change the reserves. Without protection, the user could receive far less than expected. The `min_output` parameter sets a floor: if the calculated output falls below it, the transaction fails.

Add this module-level subroutine to `smart_contracts/constant_product_pool/contract.py` (outside the class):

```python
@subroutine
def _calculate_swap_output(
    input_amount: UInt64, reserve_in: UInt64, reserve_out: UInt64,
) -> UInt64:
    """Constant product output with 0.3% fee.
    output = (input * 997 * reserve_out) / (reserve_in * 1000 + input * 997)
    """
    input_fee_high, input_with_fee = op.mulw(input_amount, UInt64(997))
    assert input_fee_high == UInt64(0), "Swap input too large"

    # Numerator: input_with_fee * reserve_out
    numerator_high, numerator_low = op.mulw(input_with_fee, reserve_out)

    # Denominator: reserve_in * 1000 + input_with_fee
    reserve_high, reserve_low = op.mulw(reserve_in, UInt64(1000))
    carry, denominator_low = op.addw(reserve_low, input_with_fee)
    denominator_high = reserve_high + carry

    q_hi, output, r_hi, r_lo = op.divmodw(
        numerator_high,
        numerator_low,
        denominator_high,
        denominator_low,
    )
    assert q_hi == UInt64(0), "Swap output overflow"
    return output
```

This is the same wide arithmetic pattern from the vesting calculation in Chapter 9: `mulw` produces a 128-bit product, `addw` combines low words with carry, and `divmodw` divides the wide value back down. It is Example 13-4's rule choosing the wide pair over `BigUInt`: only the intermediate is large --- the output is smaller than a reserve by construction --- and the divisor fits the type. With reserves of 10^12 and an input of 10^9, the numerator `input_with_fee * reserve_out` reaches 10^21, overflowing uint64. The wide arithmetic keeps the intermediate product in 128 bits.

::: {.gotcha #uint64-overflow-panics topic="Arithmetic and time" title="UInt64 overflow fails the transaction; it does not wrap"}
The swap numerator is `delta_x * 997 * y`. With reserves in the billions of base units (entirely ordinary for a six-decimal stablecoin) that product passes $2^{64}$ long before anything looks large in human terms. The AVM does not wrap on overflow, it panics, so the failure mode is a swap that stops working once the pool gets deep enough, in production, having passed every test written against a small pool. Any multiplication whose operands are both user-scaled needs `op.mulw`, `op.divmodw`, or `BigUInt`. Test the arithmetic at the top of the range, not the middle.
:::

The helper also checks that `input_amount * 997` fits in `UInt64` before using it in the numerator. For a 6-decimal token, that still allows single swaps up to about 18.5 billion tokens, far beyond normal tutorial-scale supplies. For assets with extreme supply parameters, keep these bounds explicit rather than relying on accidental overflow behavior.

The division floors, and by Example 13-6's rule that is the correct direction: this quotient decides what *leaves* the contract, so the fraction stays behind, and --- Example 13-7's point --- what stays behind raises what every LP share is worth.

::: {.check}
Why is floor division correct from the pool's perspective? What would happen if the contract rounded *up* instead? Think about the constant product invariant: would it be maintained, strengthened, or violated?
:::

Add this method to the `ConstantProductPool` class in `smart_contracts/constant_product_pool/contract.py`:

```python
    @arc4.abimethod
    def swap(
        self,
        input_txn: gtxn.AssetTransferTransaction,
        min_output: UInt64,
    ) -> UInt64:
        """Swap one pool asset for the other."""
        assert Global.group_size == UInt64(2), "Swap group must be size 2"
        assert self.is_bootstrapped.value == UInt64(1), "Not bootstrapped"
        assert self.lp_total_supply.value > UInt64(0), "No liquidity"

        assert input_txn.sender == Txn.sender, "Input sender mismatch"
        assert (
            input_txn.asset_receiver == Global.current_application_address
        ), "Receiver is not the pool"
        assert input_txn.asset_amount > UInt64(0), "Zero input"

        input_asset = input_txn.xfer_asset
        input_amount = input_txn.asset_amount
        reserve_a = self.reserve_a.value
        reserve_b = self.reserve_b.value
        asset_a = Asset(self.asset_a.value)
        asset_b = Asset(self.asset_b.value)

        # Determine swap direction, and both new reserves with it
        if input_asset == asset_a:
            output_amount = _calculate_swap_output(
                input_amount, reserve_a, reserve_b
            )
            output_asset = asset_b
            new_reserve_a = reserve_a + input_amount
            new_reserve_b = reserve_b - output_amount
        else:
            assert input_asset == asset_b, "Wrong input asset"
            output_amount = _calculate_swap_output(
                input_amount, reserve_b, reserve_a
            )
            output_asset = asset_a
            new_reserve_a = reserve_a - output_amount
            new_reserve_b = reserve_b + input_amount

        assert output_amount > UInt64(0), "Zero output"
        assert output_amount >= min_output, "Slippage exceeded"
        assert new_reserve_a > UInt64(0), "Reserve A depleted"
        assert new_reserve_b > UInt64(0), "Reserve B depleted"

        # Defense-in-depth: the rounded swap must never reduce k.
        old_k_high, old_k_low = op.mulw(reserve_a, reserve_b)
        new_k_high, new_k_low = op.mulw(new_reserve_a, new_reserve_b)
        assert new_k_high > old_k_high or (
            new_k_high == old_k_high and new_k_low >= old_k_low
        ), "Invariant violated"

        self.reserve_a.value = new_reserve_a
        self.reserve_b.value = new_reserve_b

        # Send output tokens to the user, last: every refusal above it
        # costs the group nothing but a fee.
        itxn.AssetTransfer(
            xfer_asset=output_asset,
            asset_receiver=Txn.sender,
            asset_amount=output_amount,
            fee=UInt64(0),
        ).submit()
        return output_amount
```

The `input_txn.sender == Txn.sender` check binds the grouped asset transfer to the app-call sender who receives the swap output. If Alice signs a group containing her asset transfer and Bob's app call, the transaction argument is still a valid asset transfer, but without sender binding the contract would send the output tokens to Bob. Typed transaction arguments prove transaction shape; your contract must still validate the business relationship between that transfer and the app call.

The explicit invariant check verifies that `new_reserve_a * new_reserve_b >= old_reserve_a * old_reserve_b` using wide arithmetic. The formula and floor rounding should already guarantee this, but defense-in-depth matters for AMMs: production AMMs since the V1 exploit, including Tinyman V2, treat the post-condition as mandatory.

## Executing Your First Swap on LocalNet

With bootstrap, initial liquidity, and swap implemented, you can execute a complete trading workflow on LocalNet. Recompile after adding all three methods:

```bash
algokit project run build
```

Extend your deployment script (or create a new one) to add initial liquidity and execute a swap. The following client-side code continues from the `deploy_pool.py` bootstrap script above.

First, the admin must opt into the LP token (a zero-amount self-transfer, which is what `asset_opt_in` sends), then provide initial liquidity by sending both tokens to the pool in an atomic group with the `add_initial_liquidity` call:

```python
# After bootstrap completes...
from algokit_utils import AssetOptInParams, AssetTransferParams

# The admin needs to opt into the LP token to receive LP shares
algorand.send.asset_opt_in(
    AssetOptInParams(sender=admin.address, asset_id=lp_token_id)
)

def transfer_to_pool(asset_id: int, amount: int) -> TransactionWithSigner:
    """An asset transfer built, signed, and handed over as a method arg."""
    txn = algorand.create_transaction.asset_transfer(
        AssetTransferParams(
            sender=admin.address,
            receiver=pool.app_address,
            asset_id=asset_id,
            amount=amount,
        )
    )
    return TransactionWithSigner(txn, admin.signer)

# Add initial liquidity: 10,000 Token A + 10,000 Token B.
# Asset transfers are method args; the client composes the group.
lp_result = pool.send.add_initial_liquidity(
    amm_client.AddInitialLiquidityArgs(
        deposit_a=transfer_to_pool(token_a, 10_000_000_000),  # 6 decimals
        deposit_b=transfer_to_pool(token_b, 10_000_000_000),
    ),
    params=CommonAppCallParams(
        static_fee=AlgoAmount.from_micro_algo(2_000),  # covers the inner txn
        asset_references=[token_a, token_b, lp_token_id],
    ),
)
print(f"LP tokens received: {lp_result.abi_return}")
```

With liquidity in the pool, the swap can run. The trader sends 100 Token A and receives Token B, with `min_output` providing slippage protection:

```python
# Now execute a swap: send 100 Token A, receive Token B
swap_result = pool.send.swap(
    amm_client.SwapArgs(
        input_txn=transfer_to_pool(token_a, 100_000_000),  # 100 tokens
        min_output=90_000_000,  # accept no fewer than 90 Token B
    ),
    params=CommonAppCallParams(
        static_fee=AlgoAmount.from_micro_algo(2_000),
        asset_references=[token_a, token_b],
    ),
)
print(f"Swap output: {swap_result.abi_return} base units of Token B")
```

When you run this, you should see LP tokens minted from the initial deposit and a swap output of approximately 98--99 Token B (slightly less than 100 due to the 0.3\% fee plus the price impact of the trade against the pool). If the swap output is significantly lower than expected, check that your reserves are large enough: a 100-token swap against a 10,000-token pool has minimal price impact, but a 100-token swap against a 100-token pool would move the price dramatically.

If you want to see the pool's state evolve over multiple swaps, add a loop that executes several swaps and prints the reserves after each one. You will see `reserve_a` increasing and `reserve_b` decreasing (or vice versa depending on direction), and the product `reserve_a * reserve_b` increasing with each swap due to fee accumulation.


## Adding Liquidity to an Existing Pool

After the initial deposit, subsequent liquidity providers must deposit in the current reserve ratio. If the pool is 70\% USDC and 30\% ALGO, new deposits must match that ratio (or the depositor loses value to existing LPs through the minimum-ratio calculation).

LP tokens minted for subsequent deposits use the minimum of both deposit ratios, multiplied by the outstanding LP supply:

$$LP_{new} = \min\left(\frac{\Delta x}{x}, \frac{\Delta y}{y}\right) \times LP_{total}$$

Taking the minimum means any tokens deposited beyond the current ratio are effectively donated to the pool. This incentivizes depositors to match the exact ratio and prevents price manipulation via unbalanced deposits. (See the [Algorand Python transactions guide](https://dev.algorand.co/algokit/languages/python/lg-transactions/) for typed gtxn parameter handling.)

Add this method to the `ConstantProductPool` class in `smart_contracts/constant_product_pool/contract.py`:

```python
    @arc4.abimethod
    def add_liquidity(
        self,
        deposit_a: gtxn.AssetTransferTransaction,
        deposit_b: gtxn.AssetTransferTransaction,
    ) -> UInt64:
        """Add liquidity to an existing pool. Returns LP tokens minted."""
        assert Global.group_size == UInt64(3), "Add liquidity group must be size 3"
        assert self.is_bootstrapped.value == UInt64(1), "Not bootstrapped"
        assert self.lp_total_supply.value > UInt64(0), "No liquidity"

        assert deposit_a.sender == Txn.sender, "Asset A sender mismatch"
        assert deposit_b.sender == Txn.sender, "Asset B sender mismatch"
        assert (
            deposit_a.asset_receiver == Global.current_application_address
        ), "Receiver is not the pool"
        assert (
            deposit_b.asset_receiver == Global.current_application_address
        ), "Receiver is not the pool"
        assert deposit_a.xfer_asset == Asset(self.asset_a.value), "Wrong asset A"
        assert deposit_b.xfer_asset == Asset(self.asset_b.value), "Wrong asset B"

        amount_a = deposit_a.asset_amount
        amount_b = deposit_b.asset_amount
        assert amount_a > UInt64(0), "Zero asset A"
        assert amount_b > UInt64(0), "Zero asset B"
        total_lp = self.lp_total_supply.value
        reserve_a = self.reserve_a.value
        reserve_b = self.reserve_b.value

        # LP from each side: (deposit / reserve) * total_lp
        # Cross-multiply to avoid division precision loss:
        # lp_from_a = (amount_a * total_lp) / reserve_a
        a_high, a_low = op.mulw(amount_a, total_lp)
        q_hi, lp_from_a, r_hi, r_lo = op.divmodw(a_high, a_low, UInt64(0), reserve_a)
        assert q_hi == UInt64(0), "LP token overflow"

        b_high, b_low = op.mulw(amount_b, total_lp)
        q_hi, lp_from_b, r_hi, r_lo = op.divmodw(b_high, b_low, UInt64(0), reserve_b)
        assert q_hi == UInt64(0), "LP token overflow"

        # Take the minimum --- penalizes unbalanced deposits
        lp_tokens = lp_from_a if lp_from_a < lp_from_b else lp_from_b
        assert lp_tokens > UInt64(0), "Zero LP tokens"

        # Update state
        self.reserve_a.value = reserve_a + amount_a
        self.reserve_b.value = reserve_b + amount_b
        self.lp_total_supply.value = total_lp + lp_tokens

        # Send LP tokens
        itxn.AssetTransfer(
            xfer_asset=Asset(self.lp_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=lp_tokens,
            fee=UInt64(0),
        ).submit()

        return lp_tokens
```

Wide arithmetic appears again: `amount_a * total_lp` can overflow if both are large. The pattern is identical to the vesting contract's claim calculation: `mulw` for the multiplication, `divmodw` for the division.

The floor division on both `lp_from_a` and `lp_from_b` means depositors receive slightly fewer LP tokens than the mathematically precise amount. This is correct: existing LPs should not be diluted by rounding errors in new deposits.

As in `add_initial_liquidity`, sender binding ensures the account receiving LP tokens is the account that sent the deposits. For normal asset transfers, ask: *did the same account fund the operation that benefits `Txn.sender`?* If yes, assert it directly. Clawback-enabled assets add an additional `asset_sender` wrinkle; this AMM uses ordinary user-sent transfers.

## Removing Liquidity

Withdrawal is the inverse of deposit: burn LP tokens, receive proportional shares of both reserves. The calculation is straightforward:

$$amount_A = \frac{LP_{burned}}{LP_{total}} \times reserve_A$$
$$amount_B = \frac{LP_{burned}}{LP_{total}} \times reserve_B$$

The `min_a` and `min_b` parameters provide slippage protection, just like `min_output` in the swap. Between fetching the quote and executing the withdrawal, the reserves may change.

Add this method to the `ConstantProductPool` class in `smart_contracts/constant_product_pool/contract.py`:

```python
    @arc4.abimethod
    def remove_liquidity(
        self,
        lp_deposit: gtxn.AssetTransferTransaction,
        min_a: UInt64,
        min_b: UInt64,
    ) -> tuple[UInt64, UInt64]:
        """Burn LP tokens to withdraw proportional reserves."""
        assert (
            Global.group_size == UInt64(2)
        ), "Remove liquidity group must be size 2"
        assert self.is_bootstrapped.value == UInt64(1), "Not bootstrapped"
        assert self.lp_total_supply.value > UInt64(0), "No liquidity"

        assert lp_deposit.sender == Txn.sender, "LP sender mismatch"
        assert (
            lp_deposit.asset_receiver == Global.current_application_address
        ), "Receiver is not the pool"
        assert (
            lp_deposit.xfer_asset == Asset(self.lp_token_id.value)
        ), "Wrong LP token"

        lp_amount = lp_deposit.asset_amount
        assert lp_amount > UInt64(0), "Zero LP amount"

        total_lp = self.lp_total_supply.value
        assert (
            lp_amount <= total_lp - self.locked_liquidity.value
        ), "Locked liquidity"
        reserve_a = self.reserve_a.value
        reserve_b = self.reserve_b.value

        # Proportional withdrawal (floor division: favors pool)
        a_high, a_low = op.mulw(lp_amount, reserve_a)
        q_hi, amount_a, r_hi, r_lo = op.divmodw(a_high, a_low, UInt64(0), total_lp)
        assert q_hi == UInt64(0), "Proportional amount overflow"

        b_high, b_low = op.mulw(lp_amount, reserve_b)
        q_hi, amount_b, r_hi, r_lo = op.divmodw(b_high, b_low, UInt64(0), total_lp)
        assert q_hi == UInt64(0), "Proportional amount overflow"

        # Slippage protection
        assert amount_a >= min_a, "Asset A slippage exceeded"
        assert amount_b >= min_b, "Asset B slippage exceeded"
        assert amount_a > UInt64(0), "Zero asset A output"
        assert amount_b > UInt64(0), "Zero asset B output"

        # Update reserves and LP supply
        self.reserve_a.value = reserve_a - amount_a
        self.reserve_b.value = reserve_b - amount_b
        self.lp_total_supply.value = total_lp - lp_amount

        # Send both assets back, after every refusal has had its chance
        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_a.value),
            asset_receiver=Txn.sender,
            asset_amount=amount_a,
            fee=UInt64(0),
        ).submit()

        itxn.AssetTransfer(
            xfer_asset=Asset(self.asset_b.value),
            asset_receiver=Txn.sender,
            asset_amount=amount_b,
            fee=UInt64(0),
        ).submit()
        return amount_a, amount_b
```

The floor division on both withdrawal amounts ensures the pool never pays out more than its proportional share; rounding dust stays in the reserves.

The `lp_deposit.sender == Txn.sender` check applies the same sender-binding rule in reverse: the account sending LP tokens to the pool is the account receiving the underlying assets.

## Depositing and Withdrawing on LocalNet

Recompile, then append the round trip to the script: a second deposit priced by the post-swap reserves, and a burn of half of what it mints.

```python
second = pool.send.add_liquidity(
    amm_client.AddLiquidityArgs(
        deposit_a=transfer_to_pool(token_a, 1_000_000_000),
        deposit_b=transfer_to_pool(token_b, 1_000_000_000),
    ),
    params=CommonAppCallParams(
        static_fee=AlgoAmount.from_micro_algo(2_000),
        asset_references=[token_a, token_b, lp_token_id],
    ),
).abi_return
print(f"Second LP minted: {second}")

withdrawn = pool.send.remove_liquidity(
    amm_client.RemoveLiquidityArgs(
        lp_deposit=transfer_to_pool(lp_token_id, second // 2),
        min_a=1, min_b=1,
    ),
    params=CommonAppCallParams(
        static_fee=AlgoAmount.from_micro_algo(3_000),  # two inner transfers
        asset_references=[token_a, token_b, lp_token_id],
    ),
).abi_return
print(f"Withdrawn A: {withdrawn[0]}")
print(f"Withdrawn B: {withdrawn[1]}")
```

```text
Second LP minted: 990099009
Withdrawn A: 499999999
Withdrawn B: 491048836
```

A thousand tokens of each side minted 990,099,009 rather than a round billion, because the swap moved the pool off 1:1 and the mint takes the smaller of the two proportional claims: the deposit's token A was worth 990,099,009.9 claims, its token B was worth more, and the surplus B is donated to the reserves.

Burning half of that returns 499,999,999 of token A, one base unit short of half a billion. Two floors account for it --- the mint dropped 0.9 of a claim, the payout dropped another 0.08 of a token --- and both fractions stayed with the pool, which is Example 13-7's dust being inherited by everyone who did not withdraw.

Token B comes back about nine whole tokens short of token A because the swap drew the B reserve down. A withdrawal returns a share of the reserves *as they are now*, never the two amounts that went in, which is Example 13-12's impermanent loss arriving as an inventory rather than as a percentage.

## What Providing Liquidity Costs the Provider

The pool you just built rebalances every LP's position on every trade, and Example 13-12 already priced what that costs: two roots over one plus the ratio, symmetric in a move and its reciprocal, and nothing impermanent about it once the position is closed. Table 14-3 evaluates that example's `value_ratio` at a few representative moves --- the numbers an LP in *this* pool is signing up for.

: Table 14-3. Impermanent loss at selected price ratios (Example 13-12's formula)

| Price Change | IL |
|-------------|-----|
| 1.25x (25% up) | -0.6% |
| 1.5x (50% up) | -2.0% |
| 2x (double) | -5.7% |
| 3x (triple) | -13.4% |
| 5x (5x) | -25.5% |

**When do fees overcome IL?** If the pool generates enough trading fees to exceed the IL, providing liquidity is profitable. This depends on trading volume relative to pool size. A pool with $100K TVL and $50K daily volume generates far more fee income per LP dollar than a pool with $10M TVL and the same volume. High-volume, tight-spread pools (like major stablecoin pairs) tend to overcome IL; low-volume, volatile pairs often do not.

::: {.warning}
Impermanent loss is the primary risk for liquidity providers. The 0.3% swap fee partially offsets IL but does not eliminate it. Before providing liquidity in production, calculate the breakeven volume needed for your pool's volatility profile.
:::

Concentrated liquidity --- the V3 design the note at the top of this chapter priced --- is Uniswap's answer to this tradeoff; no Algorand DEX currently ships it, and the constant product model built here is what Tinyman and Pact run in production.


## Security Hardening and the Tinyman V1 Lesson

On January 1, 2022, attackers exploited a vulnerability in Tinyman V1's burn (remove liquidity) function, extracting approximately \$3 million. The root cause: the contract failed to verify that two different assets were being returned during liquidity removal. An attacker could construct a transaction that received the same token twice, effectively doubling their withdrawal of one asset while getting nothing of the other.

The key lessons from this exploit shape this contract's security posture.

First, **explicit invariant verification after state-changing AMM operations**. The swap method calculates the output from the formula and then checks that $k_{new} \geq k_{old}$. The Tinyman exploit showed that complex TEAL logic can have subtle control flow bugs that bypass intended math. This tutorial demonstrates the post-condition in `swap`; production AMMs should apply equivalent post-condition reasoning across liquidity operations too.

Second, **immutable contracts cannot be patched**. When Tinyman discovered the exploit, they could not update the contracts because they were immutable. They could only recommend that users withdraw their liquidity. This is the correct tradeoff: immutability is what makes the contracts trustless. But it means your code must be correct before deployment. There is no hot-fix option.

Third, **asset verification in every transfer**. The contract explicitly checks `input_txn.xfer_asset == Asset(self.asset_a.value)` in the `swap` method. It checks `deposit_a.xfer_asset == Asset(self.asset_a.value)` in `add_liquidity`. It checks `lp_deposit.xfer_asset == Asset(self.lp_token_id.value)` in `remove_liquidity`. Never assume the correct asset was sent; always verify.

Fourth, **sender binding for transaction arguments**. Typed transaction arguments prove that the argument has the expected transaction type, but they do not prove that the transfer came from the app-call sender. When a grouped payment or asset transfer funds an operation whose benefit goes to `Txn.sender`, assert the transaction argument's `sender == Txn.sender`.

Beyond the Tinyman case study, the Trail of Bits "Not So Smart Contracts" database and the Panda static analysis framework (USENIX Security 2023) identified systematic vulnerability patterns. Panda found that 27.73\% of deployed Algorand applications had at least one vulnerability. The most common categories include missing authorization checks, group size validation gaps, inner transaction fee drains, and --- for Logic Signatures --- missing close-to and rekey-to checks (the #1 finding, though not applicable to stateful contracts like this one).

This contract addresses the categories that apply to stateful contracts: the contract is immutable (update/delete rejected), all inner transaction fees are zero (preventing fee drain), every incoming transfer is verified for asset ID, receiver, and sender binding where needed, and all privileged methods check caller authorization.

Reentrancy is not on the list, because an inner transaction runs no code on the receiving side --- Example 8-7 demonstrated exactly that, and it is why the checks-effects-interactions contortions of other chains have no work to do here. (See [Ethereum to Algorand](https://dev.algorand.co/getting-started/ethereum-to-algorand/) for a detailed security model comparison.)

Regarding MEV (Miner/Maximum Extractable Value): Algorand's block proposers are selected randomly each round via VRF, so no one knows who the proposer will be in advance, making targeted collusion difficult. Transaction ordering follows first-come-first-served by default, not fee-based priority.

Sandwich attacks, where an attacker inserts transactions before and after a victim's swap, are therefore significantly harder than on Ethereum but not impossible: a block proposer has some discretion over transaction ordering within their proposed block, and the mempool, while not publicly accessible like Ethereum's, is visible to relay nodes. Slippage protection via `min_output` remains the primary defense, and should always be set to a meaningful value, never zero in production.


## Client-Side Quote Calculation

Never submit an on-chain transaction just to get a price quote. The swap output can be calculated client-side using the same constant-product formula, reading reserves from [global state](https://dev.algorand.co/concepts/smart-contracts/storage/global/) (a free API call: no transaction, no fee). This is how frontends display real-time quotes and price impact warnings. Example 13-9 in Chapter 13 is the complete client-side quote helper function with price impact calculation and slippage defaults.

## Optional Hardening: The TWAP Price Oracle

::: {.note}
**Optional section.** The core AMM is complete: you can bootstrap a pool, add liquidity, swap, and remove liquidity, and the contract as built so far compiles and runs without any of the code in this section. Skip it and nothing else in the book breaks: no later contract requires the oracle, and the three places that mention it again --- this chapter's Exercise 3, Chapter 16's Exercise 4, and Chapter 17's frontend valuation flow --- either declare the assumption or run against the finished project's pool, which ships it either way. What follows hardens the pool into a price oracle by implementing Example 13-11's accumulator against real reserves.
:::

The AMM stores its reserves in global state, which any other contract can read. This makes the pool a natural price oracle, but one that must be used carefully.

### Why Spot Prices Are Dangerous

A lending protocol that needs to know the ALGO/USDC price could read this pool's reserves and compute a spot price: `reserve_b / reserve_a`. That is the instantaneous reading Chapter 13 warned has a manipulator: an attacker with 100,000 USDC swaps into a 10,000/10,000 pool, pushes the spot to roughly 0.01, lets a liquidation contract read it and liquidate healthy positions, then swaps back --- the entire attack inside a single atomic group. The repair is Example 13-11's: stop reading instants. Accumulate price times elapsed, let any two snapshots give the mean between them, and manipulation costs the attacker the whole window rather than one block --- a one-block distortion contributes only $2.75 / 3600 \approx 0.08\%$ of a one-hour average.

> *Quick check, from that example's read side: if the cumulative price at t=100 is 500,000 and at t=200 is 1,200,000, what is the TWAP over that interval?*

In production AMMs (Uniswap V2, Tinyman V2), the cumulative price accumulators live inside the pool contract itself and update on every swap, mint, and burn, so the oracle is available to any external consumer --- lending protocols, liquidation engines, farming contracts --- without any of them maintaining their own accumulator. That is what this section wires into the pool: one accumulator per direction, because a caller might want either, which is exactly the extension Chapter 13's Exercise 5 asked you to design.

### The State the Oracle Needs

The oracle adds one constant and three global state fields. This is the diff against the contract as built so far; the complete listing every diff in this section lands in is cited at the end of the section:

```diff
 MINIMUM_LIQUIDITY = 1000
+TWAP_PRECISION = 10**9
```

```diff
         self.locked_liquidity = GlobalState(UInt64(0))
         self.is_bootstrapped = GlobalState(UInt64(0))
+        # TWAP oracle: Example 13-11's accumulator, one per direction
+        self.cumulative_price_a = GlobalState(BigUInt(0))
+        self.cumulative_price_b = GlobalState(BigUInt(0))
+        self.twap_last_update = GlobalState(UInt64(0))
```

`TWAP_PRECISION` is Example 13-3's scale constant --- one billion, arbitrary in value, load-bearing in agreement. The accumulators are `BigUInt` by Example 13-4's rule: the stored value is the thing with no ceiling, so the stored value is what must be wide. Two schema consequences are worth naming, because this is where they are paid for. `BigUInt` values are stored as byte-slice slots, not uint slots, so these two fields raise the contract's `global_bytes` allocation (PuyaPy computes both allocations for you), which raises the creator's schema MBR at deployment. And because this pool refuses updates, this diff must be in the contract *before* the pool you care about is deployed; on LocalNet, deploy a fresh pool after recompiling.

Why wide is not optional here: Example 13-11 worked the horizon arithmetic --- at a $10^9$ scale a price near one has centuries of `UInt64` headroom, but the headroom collapses in proportion to the price ratio, and a ratio of a million turns years into hours. [Uniswap V2](https://docs.uniswap.org/contracts/v2/guides/smart-contract-integration/building-an-oracle), the reference implementation for cumulative price tracking, solves the same problem in the opposite style, accumulating 224-bit fixed-point values in `uint256` and letting them overflow on purpose, with modular subtraction making the wraparound harmless. On the AVM, `BigUInt` (up to 512 bits) absorbs any practical accumulation without wrapping. The bill: byte-math opcodes cost roughly 10--20 budget units each, so a full `_update_twap` pass (four `b*`, two `b/`, two `b+`) is roughly 140 units --- real, and still small against the 700-unit budget.

### The Oracle in One Piece

Three things go into the class: the amended `__init__`, the subroutine that accumulates, and the read-only method that averages. Here they are together, because an oracle met as three fragments is an oracle wired wrong.

```python
    def __init__(self) -> None:
        self.asset_a = GlobalState(UInt64(0))
        self.asset_b = GlobalState(UInt64(0))
        self.lp_token_id = GlobalState(UInt64(0))
        self.reserve_a = GlobalState(UInt64(0))
        self.reserve_b = GlobalState(UInt64(0))
        self.lp_total_supply = GlobalState(UInt64(0))
        self.locked_liquidity = GlobalState(UInt64(0))
        self.is_bootstrapped = GlobalState(UInt64(0))
        # TWAP oracle: Example 13-11's accumulator, one per direction
        self.cumulative_price_a = GlobalState(BigUInt(0))
        self.cumulative_price_b = GlobalState(BigUInt(0))
        self.twap_last_update = GlobalState(UInt64(0))

    @subroutine
    def _update_twap(self) -> None:
        last = self.twap_last_update.value
        now = Global.latest_timestamp
        if last == UInt64(0) or now <= last:
            return

        delta_t = now - last
        res_a = self.reserve_a.value
        res_b = self.reserve_b.value

        if res_a == UInt64(0) or res_b == UInt64(0):
            self.twap_last_update.value = now
            return

        # price_a = reserve_b * TWAP_PRECISION / reserve_a
        # price_b = reserve_a * TWAP_PRECISION / reserve_b
        # Accumulate: cumulative += price * delta_t
        price_a = (
            BigUInt(res_b) * BigUInt(TWAP_PRECISION)
            // BigUInt(res_a)
        )
        price_b = (
            BigUInt(res_a) * BigUInt(TWAP_PRECISION)
            // BigUInt(res_b)
        )

        self.cumulative_price_a.value += (
            price_a * BigUInt(delta_t)
        )
        self.cumulative_price_b.value += (
            price_b * BigUInt(delta_t)
        )
        self.twap_last_update.value = now

    @arc4.abimethod(readonly=True)
    def get_twap_price(
        self,
        old_cumulative_a: arc4.UInt512,
        old_timestamp: UInt64,
    ) -> UInt64:
        """Returns TWAP of asset A in terms of B (how many B per one A)."""
        # Accumulate any pending price data up to the current block.
        # The inline accumulation computes the up-to-date cumulative value
        # into a local variable without writing to state.  Because the method
        # is read-only, it can be called via simulate with no fees or on-chain
        # side effects.
        now = Global.latest_timestamp
        last = self.twap_last_update.value
        current = self.cumulative_price_a.value
        if last > UInt64(0) and now > last:
            res_a = self.reserve_a.value
            res_b = self.reserve_b.value
            if res_a > UInt64(0) and res_b > UInt64(0):
                delta_t = now - last
                price_a = (
                    BigUInt(res_b) * BigUInt(TWAP_PRECISION)
                    // BigUInt(res_a)
                )
                current += price_a * BigUInt(delta_t)

        old = old_cumulative_a.as_biguint()
        assert current > old, "No price data"
        elapsed = now - old_timestamp
        assert elapsed > UInt64(0), "Zero elapsed"

        diff = current - old
        twap = diff // BigUInt(elapsed)
        assert twap < BigUInt(2**64), "TWAP overflow"
        return op.btoi(twap.bytes)
```

`_update_twap` reads the pool's own reserves and credits the interval to both directions. `get_twap_price` differences two snapshots over the gap between them, and the older snapshot arrives from the caller: a cumulative value and the timestamp it was taken at.

That pair has to come from a single read of the pool's state, and the method cannot check that it did. A cumulative read this minute against a timestamp read an hour ago divides the right numerator by the wrong denominator and returns a number that looks like a price. Nothing in the two arguments records where either came from, so the discipline lives in the consumer: read both in one call, store them together, hand them back together.

::: {.note}
The `readonly=True` flag means this method can be called via `simulate` without submitting a transaction: no fees, no state changes. Frontends use this to display real-time price data. The inline accumulation at the top of `get_twap_price` ensures the cumulative value is current even if the pool has not been interacted with recently, the same approach Uniswap V2 takes in its `currentCumulativePrices` helper. That accumulation happens entirely in a local variable; nothing is written to state.
:::

The method returns a `UInt64`, so the TWAP result must fit in 64 bits. That is a deliberate design choice, since `UInt64` is easier for callers to work with than a variable-length `BigUInt`, but it requires a bounds check.

::: {.gotcha #btoi-needs-eight-bytes topic="Arithmetic and time" title="op.btoi fails on a BigUInt wider than eight bytes"}
The `op.btoi` call accepts a byte array of 0--8 bytes and interprets it as a big-endian unsigned integer. A `BigUInt` that exceeds $2^{64} - 1$ would produce more than 8 bytes, causing `btoi` to fail at runtime. The `assert twap < BigUInt(2**64)` guard ensures the TWAP result fits in 64-bit range before the conversion. With `TWAP_PRECISION = 10^9` and typical asset prices, this bound is safe for years of accumulation. If you use a higher precision scale factor or expect extreme price ratios, return a `BigUInt` instead of converting to `UInt64`.
:::

### Wiring It Into the Pool

Wiring it in is one line in each state-changing method, placed *before* the reserves move. In `swap`:

```diff
         assert self.is_bootstrapped.value == UInt64(1), "Not bootstrapped"
         assert self.lp_total_supply.value > UInt64(0), "No liquidity"
+        self._update_twap()
```

The same line goes in the same position --- after the liveness asserts, before anything touches a reserve --- in `add_liquidity` and `remove_liquidity`. In `add_initial_liquidity` there is no earlier price to credit, so it starts the clock instead:

```diff
         self.lp_total_supply.value = lp_tokens + UInt64(MINIMUM_LIQUIDITY)
         self.locked_liquidity.value = UInt64(MINIMUM_LIQUIDITY)
+        # Start the TWAP clock; there is no earlier price to credit.
+        self.twap_last_update.value = Global.latest_timestamp
```

The before-the-reserves-move placement is the ordering Example 13-11 made you watch fail: the interval must be credited to the price that *held* over it, and the swapped-lines variant there credited it to the new price and was silently wrong by the size of the move.

### Manipulation Resistance

A 1-hour TWAP window requires an attacker to sustain the manipulated price for the full hour to meaningfully distort the average. Sustaining the manipulation means keeping a large amount of capital locked in the pool for that duration, capital that is exposed to arbitrageurs who would trade against the distortion for profit. The cost of manipulation scales linearly with the TWAP window length and the pool's liquidity depth. For pools with meaningful TVL and a 1-hour+ window, TWAP manipulation is economically irrational.

**Quantifying the cost.** Suppose a pool has \$1M in total value locked (500K USDC + equivalent ALGO). To move the spot price by 10\%, an attacker needs to swap in roughly \$25,000 of one-sided input (from the constant product formula). To sustain this for 1 hour, that capital is locked and exposed to ~\$2,500 in arbitrage losses. The TWAP distortion from this 1-hour manipulation is only $10\% \times (2.75 / 3600) \approx 0.008\%$ per block of manipulation, which is negligible. The attacker would need to sustain the manipulation for the entire window at a cost far exceeding any plausible profit.

### Reading Pool Prices from Other Contracts

Reading another application's state is Chapter 15's subject; the two snippets below are a preview of its shape, in an illustrative lending contract that is not part of the AMM project code. The first is the read a consumer reaches for first, and it is the wrong one:

```python
from algopy import (
    Application, ARC4Contract, BigUInt, Bytes, UInt64, arc4, op,
)


class Lender(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def spot_price_from_amm(self, amm_app: Application) -> UInt64:
        """The read a consumer reaches for first."""
        reserve_a, a_ok = op.AppGlobal.get_ex_uint64(
            amm_app, Bytes(b"reserve_a")
        )
        reserve_b, b_ok = op.AppGlobal.get_ex_uint64(
            amm_app, Bytes(b"reserve_b")
        )
        assert a_ok and b_ok, "AMM not found"

        # Spot price of B in terms of A (scaled by 10^6)
        high, low = op.mulw(reserve_b, UInt64(1_000_000))
        q_hi, price, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), reserve_a
        )
        return price
```

Every line of that works, and the number it returns is the one an attacker moves inside a single atomic group. The read that survives a block takes the accumulator instead of the reserves. Because `BigUInt` values live in byte-slice slots rather than uint slots, that read is `get_ex_bytes` rather than `get_ex_uint64`, and the bytes come back as a `BigUInt`:

```python
    @arc4.abimethod(readonly=True)
    def cumulative_from_amm(self, amm_app: Application) -> arc4.UInt512:
        """The read that survives a single block: the accumulator itself."""
        raw, ok = op.AppGlobal.get_ex_bytes(
            amm_app, Bytes(b"cumulative_price_a")
        )
        assert ok, "AMM has no cumulative price"
        # Store this beside the timestamp it was read at. The pair is what
        # `get_twap_price` differences against later.
        return arc4.UInt512(BigUInt.from_bytes(raw))
```

::: {.gotcha #spot-price-is-manipulable topic="Pricing math" title="Never price against spot: a single atomic group can move it"}
A spot price is one division away from the current reserves, and the reserves are one swap away from wherever an attacker wants them: push, read, restore, all inside one atomic group, at no cost beyond fees and slippage. Any contract that prices collateral, liquidations, or payouts against `reserve_b / reserve_a` is reading a number its caller can choose. Price against the cumulative accumulators instead --- store periodic snapshots and difference them over a window --- so that distorting the answer costs the attacker the whole window rather than one block. Chapter 14's pool ships the accumulators in its global state for exactly this consumer.
:::

Multi-hop price derivation (reading prices across chained pools, e.g., ALGO/USDC via ALGO/TOKEN and TOKEN/USDC) follows the same pattern: read reserves from each pool in the chain and multiply the ratios. (See [Opcodes Overview](https://dev.algorand.co/concepts/smart-contracts/opcodes-overview/) for the cross-app state reading opcodes.)

Recompile, and deploy a fresh pool: the schema changed, and an existing one cannot grow the fields. What the pool holds now is three state fields, one subroutine called from four methods, and one read-only method any consumer can simulate for free. The complete contract with all of it wired in --- the listing to diff your own against --- is `projects/constant-product-amm/smart_contracts/constant_product_pool/contract.py`.


## Testing the AMM

The finished project ships two suites in `projects/constant-product-amm/tests/`, split the way Chapter 8 split them. `test_contract_shape.py` is the fast half: it never touches a network, reading the contract source and asserting that the security properties this chapter taught are actually present --- sender binding on every grouped transfer, asset-ID verification, zero-fee inner transactions, the k-invariant check. `test_constant_product_amm.py` is the slow half: real pools on LocalNet, driven through the same typed client as the deployment scripts, in the pytest patterns the [AlgoKit Utils testing guide](https://dev.algorand.co/algokit/utils/python/testing/) documents. The listings below are that suite's actual code, not outlines.

The whole LocalNet file is marked with one line, and `conftest.py` turns the marker into a skip when there is no chain to talk to:

```python
# tests/conftest.py
from __future__ import annotations

import pytest

from scripts.localnet_helpers import get_localnet_algorand


@pytest.fixture
def algorand():
    try:
        return get_localnet_algorand()
    except RuntimeError as exc:
        pytest.skip(str(exc))
```

`get_localnet_algorand` and the other names imported below live in `projects/constant-product-amm/scripts/localnet_helpers.py`. Each is a thin, named wrapper over exactly one call the deployment scripts already made: `fund_account` sends a dispenser payment, `create_test_asset` is `asset_create` with six decimals, `opt_account_into_asset` is the zero-amount opt-in, `payment_arg` and `asset_transfer_arg` build a signed transaction argument the way `transfer_to_pool` did above, and `quote_swap` is Example 13-9's `amount_out` in the 997/1000 spelling. Nothing in them is new; they exist so every test reads as intent. The one exception is `distinct_create_params`, which returns create parameters carrying a random note: a test that deploys two pools from the same admin and the same program would otherwise build the same transaction twice inside AlgoKit Utils' suggested-params cache window, and the ledger rejects the second as a duplicate of the first.

Every test starts from a freshly deployed, bootstrapped pool. That setup is a plain function rather than a fixture so each test can hold onto all six values it returns:

```python
# tests/test_constant_product_amm.py
from __future__ import annotations

import pytest
from algokit_utils import AlgoAmount, CommonAppCallParams, SendParams

from scripts.localnet_helpers import (
    MICRO_UNITS,
    asset_transfer_arg,
    create_test_asset,
    distinct_create_params,
    fund_account,
    opt_account_into_asset,
    payment_arg,
    quote_swap,
    transfer_asset,
)


pytestmark = pytest.mark.localnet


def deploy_bootstrapped_pool(algorand):
    from smart_contracts.artifacts.constant_product_pool import (
        constant_product_pool_client as amm_client,
    )

    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    trader = algorand.account.random()
    fund_account(algorand, dispenser, admin)
    fund_account(algorand, dispenser, trader)

    token_a = create_test_asset(algorand, admin, name="Token A", unit="TKNA")
    token_b = create_test_asset(algorand, admin, name="Token B", unit="TKNB")
    if token_a > token_b:
        token_a, token_b = token_b, token_a

    factory = amm_client.ConstantProductPoolFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    pool, _ = factory.send.create.bare()
    result = pool.send.bootstrap(
        amm_client.BootstrapArgs(
            seed_payment=payment_arg(algorand, admin, pool.app_address, 500_000),
            asset_a=token_a,
            asset_b=token_b,
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(4_000),
            asset_references=[token_a, token_b],
        ),
    )
    lp_token = result.abi_return
    assert lp_token is not None
    for account in (admin, trader):
        for asset_id in (token_a, token_b, lp_token):
            opt_account_into_asset(algorand, account, asset_id)
    return pool, admin, trader, token_a, token_b, lp_token


def add_initial_liquidity(algorand, pool, admin, token_a, token_b, lp_token):
    from smart_contracts.artifacts.constant_product_pool import (
        constant_product_pool_client as amm_client,
    )

    amount_a = 10_000 * MICRO_UNITS
    amount_b = 10_000 * MICRO_UNITS
    result = pool.send.add_initial_liquidity(
        amm_client.AddInitialLiquidityArgs(
            deposit_a=asset_transfer_arg(
                algorand, admin, pool.app_address, token_a, amount_a
            ),
            deposit_b=asset_transfer_arg(
                algorand, admin, pool.app_address, token_b, amount_b
            ),
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[token_a, token_b, lp_token],
        ),
    )
    assert result.abi_return is not None
    return amount_a, amount_b, result.abi_return
```

With those two builders, the negative test for this chapter's signature guard is short. The trader signs the input transfer, the admin submits the app call, and the suite asserts not merely that the group fails but that it fails *for the sender-binding reason* --- a negative test that does not check the refusal's message would pass for any accidental breakage:

```python
def test_swap_rejects_mismatched_sender(algorand) -> None:
    from smart_contracts.artifacts.constant_product_pool import (
        constant_product_pool_client as amm_client,
    )

    pool, admin, trader, token_a, token_b, lp_token = deploy_bootstrapped_pool(
        algorand
    )
    add_initial_liquidity(algorand, pool, admin, token_a, token_b, lp_token)
    transfer_asset(algorand, admin, trader, token_a, 1_000 * MICRO_UNITS)

    with pytest.raises(Exception, match="Input sender mismatch"):
        pool.send.swap(
            amm_client.SwapArgs(
                input_txn=asset_transfer_arg(
                    algorand, trader, pool.app_address, token_a, 100 * MICRO_UNITS
                ),
                min_output=1,
            ),
            params=CommonAppCallParams(
                sender=admin.address,
                signer=admin.signer,
                static_fee=AlgoAmount.from_micro_algo(2_000),
                asset_references=[token_a, token_b],
            ),
        )
```

The rest of the file follows the same shape, and between them the two suites cover every flow this chapter built:

- `test_full_amm_workflow` --- bootstrap, initial liquidity, a swap whose output is checked against `quote_swap`'s client-side prediction, a second deposit at the moved ratio, and a withdrawal that returns both assets. The Run It First workflow, as an assertion instead of a printout.
- `test_swap_rejects_excessive_slippage` --- an absurd `min_output`, refused with `Slippage exceeded`.
- `test_swap_rejects_wrong_asset_and_wrong_receiver` --- pays the pool in LP tokens (refused with `Wrong input asset`), then sends the input transfer to the wrong receiver.
- `test_bootstrap_requires_asset_references_and_fee_pooling` --- the two client-side mistakes you are most likely to make, committed on purpose. The underpaid pooled fee is refused with `too small`. The missing `asset_references` is refused with `unavailable Asset`, but only because the test also passes `send_params=SendParams(populate_app_call_resources=False)`.
- `test_contract_shape.py` --- the source-property checks, runnable with no Docker at all via `algokit project run test-static`.

That `populate_app_call_resources=False` is the whole point of the first half of that test. Automatic resource population is on by default in AlgoKit Utils 4.x (Chapter 5 met it when boxes were the resource being filled in), so a bootstrap call with no `asset_references` at all *succeeds*: the client simulates the group, reads back the assets the simulation wanted, and puts them on the transaction before sending it. A negative test written without turning population off passes while proving nothing. Turning it off is what hands the reference list back to the reader, whose omission is the thing under test --- and it is also the honest model of the call arriving from somewhere that does no populating at all, which is where the missing reference will actually bite you.

Run the whole thing with `algokit project run test` from the project directory; without a reachable LocalNet the integration file skips and reports why, which is exactly the checkpoint-table row from Run It First.

::: {.tryit}
**Exercise.** The suite tests the sender binding on `swap` but not on `add_liquidity`. Add `test_add_liquidity_rejects_mismatched_sender` to `tests/test_constant_product_amm.py`: the trader signs both deposit transfers, the admin submits the app call, and the group must fail with `Asset A sender mismatch`. Every piece you need is in the worked test above --- the only new decision is which builder runs first.
:::

## Moving to TestNet

Once your contract works on LocalNet, the next step is TestNet, Algorand's public test network where you can interact with other contracts, test with real network conditions (block times, transaction propagation), and share your deployment with others for testing.

To deploy on TestNet, you need a funded TestNet account. Get free TestNet Algo from the [TestNet faucet](https://lora.algokit.io/testnet/fund) or by running `algokit dispenser login` and `algokit dispenser fund`.

Switch your `AlgorandClient` to TestNet. This is a client-side configuration change:

```python
# Instead of default_localnet():
algorand = AlgorandClient.testnet()
# Or connect to a specific algod endpoint:
algorand = AlgorandClient.from_clients(
    algod=AlgodClient("", "https://testnet-api.4160.nodely.dev"),
)
```

The deployment and interaction scripts are identical to LocalNet; only the client connection changes. Deploy, bootstrap, and run through the full workflow. Verify every operation by checking the contract's global state and your account balances on a TestNet block explorer like [Pera Explorer](https://testnet.explorer.perawallet.app/). (See [App Deployment](https://dev.algorand.co/algokit/utils/python/app-deploy/) for idempotent deployment strategies.)

Before deploying to MainNet, your TestNet testing checklist should include: bootstrap with real ASAs (not just test tokens), add liquidity from multiple accounts, execute swaps in both directions with varying sizes, remove liquidity and verify proportional withdrawal, test edge cases (very small swaps, swaps that would exceed reserves, swaps with zero `min_output`), and verify immutability by attempting update and delete.


## Exercises

1. **(Apply)** Write a client-side function that calculates the price impact of a swap as a percentage, given the input amount and current reserves.

2. **(Analyze)** The AMM uses tracked reserves (explicit `self.reserve_a.value`) rather than reading the contract's actual on-chain balance. What happens if someone accidentally sends tokens directly to the contract address without calling any method? Are those tokens recoverable? Is this a bug or a deliberate design choice?

3. **(Analyze)** *(Assumes the optional TWAP section.)* The TWAP oracle stops accumulating if no transactions interact with the pool. If there is a 24-hour gap with no swaps or liquidity operations, the TWAP becomes stale. Design a public `poke_twap` method that allows anyone (a keeper bot) to trigger a TWAP update without performing a swap. What should the method do, and what incentive does a keeper have to call it?

4. **(Create)** Design an extension that adds a 0.05% protocol fee on top of the existing 0.3% LP fee. The protocol fee should accumulate in a separate global state variable and be withdrawable by the admin. Sketch the code changes needed in the `swap` method and write a new `withdraw_protocol_fees` method.

    *Hint:* Add `self.protocol_fees_a = GlobalState(UInt64(0))` and `self.protocol_fees_b = GlobalState(UInt64(0))` to `__init__`. In the `swap` method, after calculating `output_amount`, compute `protocol_fee = output_amount * UInt64(5) // UInt64(10000)` (0.05%), subtract it from the output sent to the user, and add it to the appropriate protocol fee accumulator. The `withdraw_protocol_fees` method should be admin-only, send both accumulated fee balances via inner transactions, and reset the accumulators to zero.

5. **(Create, cross-chapter)** Write a simulate-based test (Chapter 8's pattern) that verifies the AMM rejects a swap where `min_output` exceeds the available output. Use `.simulate()` to construct the failing swap and verify the failure message contains `"Slippage exceeded"`.

::: {.tryit}
**Practice.** Look up wide arithmetic, reading another application's state, an ASA opt-in and fee handling in Appendix D, which indexes every numbered example in the book by the task it performs.
:::

## Before You Continue

You should be able to check off all five of these:

- [ ] I can compute a swap's output from the two reserves and the 0.3% fee, and say what `min_output` protects a trader from between quote and execution
- [ ] I can explain why `bootstrap` creates the LP token and both opt-ins from inside the contract, and what the caller's seed payment has to cover before those three inner transactions can run
- [ ] I can say why the first deposit mints the geometric mean of the two amounts minus 1,000 LP tokens, and what locking those 1,000 forever prevents
- [ ] I can state what a typed `gtxn.AssetTransferTransaction` argument proves and what it does not, and why every method taking one still asserts `sender == Txn.sender`
- [ ] I can point at the check that proves `k` did not shrink across a swap, and say why Tinyman V1 is the argument for keeping it when the formula above it is already correct

If any of these are unclear, revisit the relevant section before proceeding.

The next chapter teaches the one mechanism this project deliberately kept off-chain: contracts calling contracts. Chapter 16 then spends it on this pool, moving deployment on-chain into a factory that registers canonical pairs and gives later contracts a way to verify that a pool belongs to the protocol.
