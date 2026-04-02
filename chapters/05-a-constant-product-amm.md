\newpage

\part{Building a DEX}

Part II applies the foundations to DeFi. You will build a constant product AMM with multi-token accounting, price curves, and LP token mechanics, then extend it with a yield farming contract that introduces the reward accumulator pattern and smart contract composition. The part concludes with the cross-cutting production patterns --- fee subsidization, MBR lifecycle, event emission --- that separate tutorial code from production code.

# A Constant Product AMM

You have built a contract that holds tokens, tracks per-user data in boxes, performs safe integer math, and releases assets via inner transactions. Now we are going to apply all of that --- and introduce several new concepts --- to build something significantly more complex: an automated market maker.

An AMM is a smart contract that holds reserves of two tokens and allows anyone to swap one for the other. There is no order book, no matching engine, no counterparty. The contract itself is the market maker, using a mathematical formula to determine the exchange rate. Liquidity providers deposit both tokens into the pool and receive LP tokens representing their share. Traders swap against the pool, paying a small fee that accrues to LPs. This is the mechanism behind Uniswap, SushiSwap, and Tinyman --- the dominant DEX model in DeFi.

By the end of this chapter you will have a working AMM pool contract with creation, bootstrapping, swapping, liquidity provision, liquidity withdrawal, and comprehensive security hardening. Each section builds on the previous one, and new Algorand concepts are introduced only when the AMM requires them.

### Project Setup

Scaffold a new project for this chapter. The `--name` flag sets the project directory; the template always creates a `hello_world/` contract inside it, which we rename:

```bash
algokit init -t python --name constant-product-amm
cd constant-product-amm
algokit project bootstrap all
mv smart_contracts/hello_world smart_contracts/constant_product_pool
```

Your contract code goes in `smart_contracts/constant_product_pool/contract.py`. Replace the template-generated contents of `contract.py` with the code shown below --- do not append to the existing template code. Also delete the template-generated `deploy_config.py` in the renamed directory --- it references the old `HelloWorld` contract.

If you have never used a decentralized exchange, here is the core idea. Imagine you want to trade token A for token B, but there is nobody online right now who wants the opposite trade. An AMM solves this by replacing the human counterparty with a smart contract that holds reserves of both tokens. The contract uses a mathematical formula to set the price: the more of token A you buy, the more expensive it gets (because the pool is running out). Anyone can deposit tokens into the pool to earn trading fees --- these depositors are called *liquidity providers* (LPs), and the pool gives them *LP tokens* as receipts representing their share. When they want to exit, they burn their LP tokens and receive their proportional share of both reserves plus accumulated fees. A *DEX* (decentralized exchange) is simply a frontend that lets users interact with one or more AMM contracts.


## The Math Behind Constant Product Markets

Before writing any code, you need to understand the formula that governs every operation in this contract. A constant product AMM maintains the invariant:

$$x \times y = k$$

where $x$ is the reserve of token A, $y$ is the reserve of token B, and $k$ is a constant that can only increase (from fees). This equation defines a hyperbolic curve --- as you buy token B (decreasing $y$), the price rises because the product $k$ must be maintained, forcing $x$ to increase proportionally. The marginal price at any point along the curve is $y / x$.

When a trader swaps $\Delta x$ of token A for token B, the contract calculates how much token B to release. The new reserves must satisfy the invariant (with fees):

$$(x + \Delta x \times 0.997) \times (y - \Delta y) \geq x \times y$$

Solving for $\Delta y$ (the output amount):

$$\Delta y = \frac{\Delta x \times 997 \times y}{x \times 1000 + \Delta x \times 997}$$

The $997/1000$ factor represents a 0.3\% fee --- 0.3\% of every swap's input stays in the pool, gradually increasing $k$ and thus the value of LP tokens. This fee is not distributed separately. It accumulates naturally in the reserves, meaning each LP token becomes redeemable for slightly more underlying assets over time.

**Worked example.** Alice has 100 USDC and wants to swap for ALGO from a pool with reserves of 10,000 USDC ($x$) and 10,000 ALGO ($y$). Before the swap, $k = 10{,}000 \times 10{,}000 = 100{,}000{,}000$ and the spot price is $10{,}000 / 10{,}000 = 1.0$ ALGO per USDC. Plugging into the formula:

$$\Delta y = \frac{100 \times 997 \times 10{,}000}{10{,}000 \times 1{,}000 + 100 \times 997} = \frac{9{,}970{,}000}{10{,}099{,}700} \approx 98.71\ \textrm{ALGO}$$

Alice sends 100 USDC and receives 98.71 ALGO --- not 100, because of the 0.3% fee (0.3 USDC stays in the pool) and *price impact* (each marginal unit of USDC she adds makes ALGO slightly more expensive). After the swap, reserves are 10,100 USDC and 9,901.29 ALGO, giving a new spot price of $9{,}901.29 / 10{,}100 \approx 0.98$ ALGO per USDC. The product $k$ increased slightly (to $\approx 100{,}003{,}029$) because the fee was retained. A larger trade --- say 1,000 USDC --- would move the price much more (receiving only about 906 ALGO, a 9.3% price impact), which is why AMMs work best for trades that are small relative to the pool's reserves.

For initial liquidity, the number of LP tokens minted equals:

$$LP_{\text{initial}} = \sqrt{\Delta x \times \Delta y} - \text{MINIMUM\_LIQUIDITY}$$

For subsequent deposits:

$$LP_{new} = \min\left(\frac{\Delta x}{x}, \frac{\Delta y}{y}\right) \times LP_{total}$$

Taking the minimum of both ratios penalizes unbalanced deposits --- any excess tokens beyond the current ratio are effectively donated to the pool.

The $\text{MINIMUM\_LIQUIDITY}$ lock (typically 1,000 LP tokens) prevents a first-depositor attack where an attacker deposits 1 wei of each token, receives 1 LP token, then donates large amounts to inflate the value per share so high that subsequent depositors cannot afford meaningful positions.

These formulas are the entire economic engine of the AMM. Everything else is implementation details around making them work correctly, safely, and efficiently on the [AVM](https://dev.algorand.co/concepts/smart-contracts/avm/).

> **Design decision: why constant product?** If I were designing this from scratch, I would start with the simplest invariant: what relationship between reserves should never be violated? The product $x \times y = k$ is the simplest nonlinear invariant. It is not the only option.
>
> *Concentrated liquidity* (Uniswap V3 - no equivalent on Algorand) lets LPs provide liquidity within a chosen price range instead of across the entire curve. An LP who concentrates in a ±1% range provides ~4,000x the capital efficiency of a full-range V2 position --- but their position becomes an NFT (each range is unique), and they suffer amplified impermanent loss if price leaves their range. V3 is powerful but significantly more complex to implement, especially within Algorand's 8KB program size and 700-opcode budget constraints.
>
> *StableSwap* (Curve, and Pact stable pools on Algorand) uses a hybrid invariant tuned for assets that should trade near 1:1 (stablecoins, wrapped assets). It provides dramatically lower slippage for pegged pairs.
>
> Constant product is the right starting point because it is simple enough to reason about completely, requires no off-chain infrastructure for active management, and is the foundation that V3 and StableSwap build upon. Master this, and the others are variations on the theme.

## Pool Contract Creation and the Escrow Pattern

Each asset pair gets its own contract instance --- one pool per pair. This provides strong isolation: a vulnerability in one pool cannot drain another. The alternative (a single contract managing all pools) would be simpler to deploy but catastrophically worse if compromised.

The contract will hold both pool assets plus the LP token it creates. Its address acts as an autonomous escrow --- no private key exists, and the contract's logic is the sole authority over outflows. (See [Applications](https://dev.algorand.co/concepts/smart-contracts/apps/) for how contract addresses are derived.) This is the same escrow pattern from the vesting contract, but now holding three different assets and serving many concurrent users. In production, a *factory contract* handles deployment: it creates a new pool contract instance for each asset pair, registers the pair in its own state for lookup, and enforces that no duplicate pools exist. See Cookbook section 8.3 for the factory pattern (creating contracts from contracts via inner transactions).

We begin with the state declarations. These should look familiar from the vesting contract, with a few additions.

Add the following to `smart_contracts/constant_product_pool/contract.py`:

```python
from algopy import (
    ARC4Contract, Asset, BigUInt, Global, GlobalState, Txn, UInt64,
    arc4, itxn, op, subroutine, gtxn,
)

MINIMUM_LIQUIDITY = 1000
TWAP_PRECISION = 10**9

class ConstantProductPool(ARC4Contract):
    def __init__(self) -> None:
        self.asset_a = GlobalState(UInt64(0))
        self.asset_b = GlobalState(UInt64(0))
        self.lp_token_id = GlobalState(UInt64(0))
        # We track reserves explicitly rather than reading the contract's
        # asset balance. Pattern 11 in Chapter 7 compares both approaches.
        self.reserve_a = GlobalState(UInt64(0))
        self.reserve_b = GlobalState(UInt64(0))
        self.lp_total_supply = GlobalState(UInt64(0))
        self.locked_liquidity = GlobalState(UInt64(0))
        self.is_bootstrapped = GlobalState(UInt64(0))
        # TWAP oracle state
        self.cumulative_price_a = GlobalState(BigUInt(0))
        self.cumulative_price_b = GlobalState(BigUInt(0))
        self.twap_last_update = GlobalState(UInt64(0))

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "Contract is immutable"
```

We are using global state rather than box storage for the pool's reserves and configuration. This is the right choice here: the data is small (11 fields), belongs to the application itself (not per-user), and is accessed on every single operation. Global state has a 64-pair limit, but we are nowhere near that. The schema is declared once at deployment and cannot change, so we have allocated all the fields we will need upfront. The three TWAP fields (`cumulative_price_a`, `cumulative_price_b`, `twap_last_update`) support the price oracle that we will build later in this chapter. The two `BigUInt` cumulatives are stored as byte-slice global state slots (not uint slots), so the contract's schema needs both `global_uints` and `global_bytes` allocations. PuyaPy handles this automatically.


## Bootstrapping the Pool

Bootstrapping is the one-time initialization that creates the LP token, opts the contract into both pool assets, and establishes the pool's identity. This is more involved than the vesting contract's `initialize` because we are creating a new ASA (the LP token) and performing two asset opt-ins.

Canonical asset ordering --- always placing the lower ASA ID first --- prevents duplicate pools for the same pair. Without this, someone could create a USDC/ALGO pool and a separate ALGO/USDC pool, fragmenting liquidity. By enforcing `asset_a.id < asset_b.id`, there is exactly one valid pool per pair. (See [Asset Metadata](https://dev.algorand.co/concepts/assets/asset-metadata/) for how asset IDs are assigned.)

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
        assert self.is_bootstrapped.value == UInt64(0), "Already bootstrapped"
        assert asset_a.id < asset_b.id, "Assets must be in canonical order"

        # Seed payment covers MBR for LP token creation + 2 asset opt-ins
        assert seed_payment.receiver == Global.current_application_address
        assert seed_payment.amount >= UInt64(400_000)

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
            manager=Global.current_application_address,
            reserve=Global.current_application_address,
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

The LP token has a total supply of $2^{63}$ --- a very large number that the pool will never exhaust. Setting no freeze and no clawback address (by omitting them) makes the token fully permissionless. The manager and reserve are set to the pool contract itself, though in practice these have no operational significance for an LP token.

Notice the seed payment pattern: the caller sends Algo to cover the MBR for the LP token creation (100,000 microAlgos) plus two asset opt-ins (100,000 each) plus the global state MBR plus a buffer. This is the same MBR-funding-via-grouped-payment pattern from the vesting contract, but scaled up for more resources.

The group has 5 transactions total: 1 seed payment + 1 app call + 3 inner transactions (LP creation + 2 asset opt-ins). With fee pooling, `static_fee = 5000` on the app call, plus the seed payment's default 1,000 fee, provides sufficient coverage.

## Deploying and Bootstrapping on LocalNet

Let us walk through deploying the pool contract and bootstrapping it with two test tokens on LocalNet. This verifies that everything compiles and the bootstrap sequence works before we add more methods.

First, create a new project for the AMM (or add the pool contract to your existing project). Replace the contract file contents with the `ConstantProductPool` class including the `__init__`, `reject_lifecycle`, and `bootstrap` methods. Compile:

```bash
algokit project run build
```

The AMM contract uses more imports than the vesting contract --- make sure you have `Asset`, `BigUInt`, `Global`, `GlobalState`, `Txn`, `UInt64`, `arc4`, `itxn`, `op`, `subroutine`, and `gtxn`.

Now create a deployment and bootstrap script. Save the following as `deploy_pool.py` in your project root. This client-side script creates two test ASAs, deploys the pool, funds it, and calls bootstrap.

```python
from pathlib import Path
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
admin = algorand.account.localnet_dispenser()

# Create two test tokens
def create_test_asa(name, unit):
    result = algorand.send.asset_create(
        algokit_utils.AssetCreateParams(
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

# Deploy the pool contract
factory = algorand.client.get_app_factory(
    app_spec=Path("smart_contracts/artifacts/constant_product_pool/ConstantProductPool.arc56.json").read_text(),
    default_sender=admin.address,
)
# send.bare.create() always creates a new application.
# Earlier chapters used factory.deploy(), which is idempotent
# (it updates an existing app if one is found by name).
# For one-off contracts like this AMM, we want a fresh instance
# every time, so send.bare.create() is the right choice.
app_client, deploy_result = factory.send.bare.create()
print(f"Pool App ID: {app_client.app_id}")
print(f"Pool Address: {app_client.app_address}")

# Bootstrap: fund the pool + call bootstrap.
# The seed payment is passed as the first argument to the bootstrap method.
# AlgoKit automatically places it as the preceding transaction in the group.
result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="bootstrap",
        args=[
            algokit_utils.PaymentParams(
                sender=admin.address,
                receiver=app_client.app_address,
                amount=algokit_utils.AlgoAmount.from_micro_algo(500_000),  # 0.5 Algo for MBR
            ),
            token_a,
            token_b,
        ],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(5000),  # Covers inner txns
    )
)
lp_token_id = result.abi_return  # Return value from the bootstrap call
print(f"LP Token ID: {lp_token_id}")
print("Bootstrap complete!")
```

Run with `python deploy_pool.py`. You should see three IDs printed: the two test tokens and the LP token. If you get `"Already bootstrapped"`, you are calling bootstrap on a pool that was already initialized --- reset LocalNet with `algokit localnet reset` and try again.

You can verify the pool's state by reading its global state:

```bash
curl -s http://localhost:4001/v2/applications/YOUR_APP_ID \
  -H "X-Algo-API-Token: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" \
  | python -m json.tool
```

The global state should show `asset_a`, `asset_b`, and `lp_token_id` populated with the correct ASA IDs, `is_bootstrapped` set to 1, and `reserve_a` and `reserve_b` both at 0 (no liquidity yet).


## Initial Liquidity Provision

The first liquidity provider sets the pool's initial price ratio by choosing how much of each token to deposit. The ratio of their deposit defines the starting price: depositing 1,000 USDC and 4 ALGO sets the price at 250 USDC per ALGO (or equivalently, 0.004 ALGO per USDC).

LP tokens minted for the first deposit use the geometric mean of the two amounts, minus the minimum liquidity lock. (See [Algorand Python ops](https://dev.algorand.co/algokit/languages/python/lg-ops/) for the `bsqrt` and wide arithmetic opcodes used here.)

$$LP = \sqrt{\text{amount\_A} \times \text{amount\_B}} - \text{MINIMUM\_LIQUIDITY}$$

The geometric mean ensures the LP amount is independent of the price level --- depositing 1 USDC + 1,000 ALGO mints the same LP tokens as 1,000 USDC + 1 ALGO. The minimum liquidity lock permanently removes 1,000 LP tokens from circulation (the contract holds them and never transfers them), preventing the first-depositor attack described earlier.

Add this method to the `ConstantProductPool` class in `smart_contracts/constant_product_pool/contract.py`:

```python
    @arc4.abimethod
    def add_initial_liquidity(
        self,
        a_txn: gtxn.AssetTransferTransaction,
        b_txn: gtxn.AssetTransferTransaction,
    ) -> UInt64:
        """First deposit sets the price ratio and mints initial LP tokens."""
        assert self.is_bootstrapped.value == UInt64(1), "Not bootstrapped"
        assert self.lp_total_supply.value == UInt64(0), "Pool already has liquidity"

        assert a_txn.asset_receiver == Global.current_application_address
        assert b_txn.asset_receiver == Global.current_application_address
        assert a_txn.xfer_asset == Asset(self.asset_a.value)
        assert b_txn.xfer_asset == Asset(self.asset_b.value)

        amount_a = a_txn.asset_amount
        amount_b = b_txn.asset_amount
        assert amount_a > UInt64(0) and amount_b > UInt64(0)

        # LP tokens = sqrt(a * b) - MINIMUM_LIQUIDITY
        # Use BigUInt for the intermediate product to prevent overflow.
        # op.btoi converts the BigUInt result back to UInt64; this will panic
        # if the sqrt exceeds 2^64. In practice, this limits initial deposits
        # to ~3.4e19 base units per token (far beyond any realistic supply).
        product = BigUInt(amount_a) * BigUInt(amount_b)
        sqrt_product = op.bsqrt(product)
        lp_tokens = op.btoi(sqrt_product.bytes) - UInt64(MINIMUM_LIQUIDITY)
        assert lp_tokens > UInt64(0), "Insufficient initial liquidity"

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

        # Initialize TWAP tracking with the first reserves
        self.twap_last_update.value = Global.latest_timestamp

        return lp_tokens
```

The `BigUInt` multiplication prevents overflow in the product --- if both amounts are 10^12, the product is 10^24, far beyond uint64. The `op.bsqrt` opcode computes the integer floor square root natively on the AVM.

> **Warning:** The caller must have already opted into the LP token before calling this method. If they have not, the inner `AssetTransfer` sending LP tokens will fail, and the entire atomic group rolls back --- the pool receives no tokens and no state changes. This is the "lazy opt-in" pattern: the contract does not check the opt-in explicitly; the protocol enforces it automatically. Client code must perform a zero-amount self-transfer of the LP token before calling `add_initial_liquidity`.


## The Swap

*Before looking at the implementation: given reserves of 10,000 USDC and 10,000 ALGO, how many ALGO should a trader receive for 100 USDC? Try working it out with the constant product formula (with 0.3% fee). Then: what is the new spot price after the swap? The answer may surprise you --- it is not exactly 100, and the spot price shifts even for this relatively small trade.*

This is the operation users interact with most frequently. A trader sends token A to the pool and receives token B (or vice versa). The constant product formula determines the exchange rate, and a 0.3\% fee is deducted from the input.

The swap introduces a concept not needed in the vesting contract: *slippage protection*. (See [Atomic Groups](https://dev.algorand.co/concepts/transactions/atomic-txn-groups/) for how grouped transactions provide all-or-nothing execution guarantees.) Between when a user fetches a price quote (reading reserves off-chain) and when their transaction executes, other swaps may change the reserves. Without protection, the user could receive far less than expected. The `min_output` parameter sets a floor --- if the calculated output falls below this, the transaction fails.

Add this module-level subroutine to `smart_contracts/constant_product_pool/contract.py` (outside the class):

```python
@subroutine
def _calculate_swap_output(
    input_amount: UInt64, reserve_in: UInt64, reserve_out: UInt64,
) -> UInt64:
    """Constant product output with 0.3% fee.
    output = (input * 997 * reserve_out) / (reserve_in * 1000 + input * 997)
    """
    input_with_fee = input_amount * UInt64(997)
    # Use wide arithmetic: numerator = input_with_fee * reserve_out
    num_high, num_low = op.mulw(input_with_fee, reserve_out)
    denominator = reserve_in * UInt64(1000) + input_with_fee
    # Divide 128-bit numerator by 64-bit denominator
    q_hi, output, r_hi, r_lo = op.divmodw(num_high, num_low, UInt64(0), denominator)
    return output
```

This is the same wide arithmetic pattern from the vesting calculation in Chapter 3: `mulw` produces a 128-bit product, `divmodw` divides it back down. Here the numbers are different (trade amounts × reserves instead of token amounts × elapsed time) but the technique is identical. With reserves of 10^12 and an input of 10^9, the numerator `input_with_fee * reserve_out` reaches 10^21 --- overflowing uint64. The `mulw`/`divmodw` pair keeps the intermediate product in 128 bits.

Note that `input_amount * UInt64(997)` can itself overflow if `input_amount` exceeds approximately 1.85 × 10^16. For a 6-decimal token, this allows single swaps up to ~18.5 billion tokens --- far beyond any realistic supply. If your token has extreme parameters, you would need to apply wide arithmetic to this multiplication as well.

Floor division in the output calculation means the user gets slightly less than the mathematically exact amount. This is correct: the rounding dust stays in the pool, ensuring the constant product invariant is maintained or strengthened (never weakened) by rounding.

> **Check your understanding:** Why is floor division correct from the pool's perspective? What would happen if the contract rounded *up* instead? Think about the constant product invariant: would it be maintained, strengthened, or violated?

Add this method to the `ConstantProductPool` class in `smart_contracts/constant_product_pool/contract.py`:

```python
    @arc4.abimethod
    def swap(
        self,
        input_txn: gtxn.AssetTransferTransaction,
        min_output: UInt64,
    ) -> UInt64:
        """Swap one pool asset for the other."""
        self._update_twap()

        assert input_txn.asset_receiver == Global.current_application_address

        input_asset = input_txn.xfer_asset
        input_amount = input_txn.asset_amount
        assert input_amount > UInt64(0), "Zero input"

        # Determine swap direction
        if input_asset == Asset(self.asset_a.value):
            reserve_in = self.reserve_a.value
            reserve_out = self.reserve_b.value
            output_asset = Asset(self.asset_b.value)
        else:
            assert input_asset == Asset(self.asset_b.value), "Unknown asset"
            reserve_in = self.reserve_b.value
            reserve_out = self.reserve_a.value
            output_asset = Asset(self.asset_a.value)

        output_amount = _calculate_swap_output(input_amount, reserve_in, reserve_out)
        assert output_amount >= min_output, "Slippage exceeded"
        assert output_amount > UInt64(0), "Zero output"
        assert output_amount < reserve_out, "Insufficient reserves"

        # Send output tokens to the user
        itxn.AssetTransfer(
            xfer_asset=output_asset,
            asset_receiver=Txn.sender,
            asset_amount=output_amount,
            fee=UInt64(0),
        ).submit()

        # Update reserves
        new_reserve_in = reserve_in + input_amount
        new_reserve_out = reserve_out - output_amount
        if input_asset == Asset(self.asset_a.value):
            self.reserve_a.value = new_reserve_in
            self.reserve_b.value = new_reserve_out
        else:
            self.reserve_b.value = new_reserve_in
            self.reserve_a.value = new_reserve_out

        return output_amount
```

The invariant check --- verifying that `new_reserve_a * new_reserve_b >= old_reserve_a * old_reserve_b` --- is implicit in the formula. Because the output is calculated from the formula and rounded down, the invariant is mathematically guaranteed to hold. For additional defense-in-depth, you can add an explicit check using wide arithmetic. Insert this in the `swap` method, after calculating `new_reserve_in` and `new_reserve_out` and before writing them to global state, in `smart_contracts/constant_product_pool/contract.py`:

```python
        # Explicit invariant verification (defense-in-depth)
        old_k_high, old_k_low = op.mulw(reserve_in, reserve_out)
        new_k_high, new_k_low = op.mulw(new_reserve_in, new_reserve_out)
        # new_k >= old_k (compare 128-bit values)
        assert new_k_high > old_k_high or (
            new_k_high == old_k_high and new_k_low >= old_k_low
        ), "Invariant violated"
```

Tinyman V2 made this explicit check mandatory after every operation --- it was one of the key lessons from the V1 exploit. Even if the swap formula is correct, an explicit invariant check catches implementation bugs that the formula alone might not.

## Executing Your First Swap on LocalNet

With bootstrap, initial liquidity, and swap all implemented, you can now execute a complete trading workflow on LocalNet. Recompile after adding all three methods:

```bash
algokit project run build
```

Extend your deployment script (or create a new one) to add initial liquidity and execute a swap. The following client-side code continues from the `deploy_pool.py` bootstrap script above.

First, the admin must opt into the LP token (a zero-amount self-transfer), then provide initial liquidity by sending both tokens to the pool in an atomic group with the `add_initial_liquidity` call:

```python
# After bootstrap completes...

# The admin needs to opt into the LP token to receive LP shares
algorand.send.asset_transfer(
    algokit_utils.AssetTransferParams(
        sender=admin.address,
        receiver=admin.address,
        asset_id=lp_token_id,
        amount=0,  # opt-in
    )
)

# Add initial liquidity: 10,000 Token A + 10,000 Token B
# Asset transfers are passed as method args --- the SDK composes the group automatically
lp_result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="add_initial_liquidity",
        args=[
            algokit_utils.AssetTransferParams(
                sender=admin.address,
                receiver=app_client.app_address,
                asset_id=token_a,
                amount=10_000_000_000,  # 10,000 with 6 decimals
            ),
            algokit_utils.AssetTransferParams(
                sender=admin.address,
                receiver=app_client.app_address,
                asset_id=token_b,
                amount=10_000_000_000,
            ),
        ],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),  # Cover inner txn
    )
)
print(f"LP tokens received: {lp_result.abi_return}")
```

With liquidity in the pool, we can execute a swap. The user sends 100 Token A and receives Token B, with `min_output` providing slippage protection:

```python
# Now execute a swap: send 100 Token A, receive Token B
# The asset transfer is a method argument, just like deposit_tokens in Chapter 3
swap_result = app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="swap",
        args=[
            algokit_utils.AssetTransferParams(
                sender=admin.address,
                receiver=app_client.app_address,
                asset_id=token_a,
                amount=100_000_000,  # 100 tokens
            ),
            90_000_000,  # min_output: expect at least 90 Token B
        ],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(2000),
    )
)
print(f"Swap output: {swap_result.abi_return} base units of Token B")

# Verify reserves changed
app_info = algorand.client.algod.application_info(app_client.app_id)
print("Swap complete! Check global state to verify reserves.")
```

When you run this, you should see LP tokens minted from the initial deposit and a swap output of approximately 98--99 Token B (slightly less than 100 due to the 0.3\% fee plus the price impact of the trade against the pool). If the swap output is significantly lower than expected, check that your reserves are large enough --- a 100-token swap against a 10,000-token pool has minimal price impact, but a 100-token swap against a 100-token pool would move the price dramatically.

If you want to see the pool's state evolve over multiple swaps, add a loop that executes several swaps and prints the reserves after each one. You will see `reserve_a` increasing and `reserve_b` decreasing (or vice versa depending on direction), and the product `reserve_a * reserve_b` increasing with each swap due to fee accumulation.


## Adding Liquidity to an Existing Pool

After the initial deposit, subsequent liquidity providers must deposit in the current reserve ratio. If the pool is 70\% USDC and 30\% ALGO, new deposits must match that ratio (or the depositor loses value to existing LPs through the minimum-ratio calculation).

LP tokens minted for subsequent deposits use the minimum of both deposit ratios, multiplied by the outstanding LP supply:

$$LP_{new} = \min\left(\frac{\Delta x}{x}, \frac{\Delta y}{y}\right) \times LP_{total}$$

Taking the minimum means any tokens deposited beyond the current ratio are effectively donated to the pool. This incentivizes depositors to match the exact ratio and prevents price manipulation via unbalanced deposits. (See [Algorand Python transactions guide](https://dev.algorand.co/algokit/languages/python/lg-transactions/) for typed gtxn parameter handling.)

Add this method to the `ConstantProductPool` class in `smart_contracts/constant_product_pool/contract.py`:

```python
    @arc4.abimethod
    def add_liquidity(
        self,
        a_txn: gtxn.AssetTransferTransaction,
        b_txn: gtxn.AssetTransferTransaction,
    ) -> UInt64:
        """Add liquidity to an existing pool. Returns LP tokens minted."""
        self._update_twap()

        assert self.lp_total_supply.value > UInt64(0), "Use add_initial_liquidity"

        assert a_txn.asset_receiver == Global.current_application_address
        assert b_txn.asset_receiver == Global.current_application_address
        assert a_txn.xfer_asset == Asset(self.asset_a.value)
        assert b_txn.xfer_asset == Asset(self.asset_b.value)

        amount_a = a_txn.asset_amount
        amount_b = b_txn.asset_amount
        total_lp = self.lp_total_supply.value
        reserve_a = self.reserve_a.value
        reserve_b = self.reserve_b.value

        # LP from each side: (deposit / reserve) * total_lp
        # Cross-multiply to avoid division precision loss:
        # lp_from_a = (amount_a * total_lp) / reserve_a
        a_high, a_low = op.mulw(amount_a, total_lp)
        q_hi, lp_from_a, r_hi, r_lo = op.divmodw(a_high, a_low, UInt64(0), reserve_a)

        b_high, b_low = op.mulw(amount_b, total_lp)
        q_hi, lp_from_b, r_hi, r_lo = op.divmodw(b_high, b_low, UInt64(0), reserve_b)

        # Take the minimum --- penalizes unbalanced deposits
        lp_tokens = lp_from_a if lp_from_a < lp_from_b else lp_from_b
        assert lp_tokens > UInt64(0), "Insufficient deposit"

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

Wide arithmetic appears again: `amount_a * total_lp` can overflow if both are large. The pattern is identical to what we used in the vesting contract's claim calculation --- `mulw` for the multiplication, `divmodw` for the division.

The floor division on both `lp_from_a` and `lp_from_b` means depositors receive slightly fewer LP tokens than the mathematically precise amount. This is correct: existing LPs should not be diluted by rounding errors in new deposits.

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
        lp_txn: gtxn.AssetTransferTransaction,
        min_a: UInt64,
        min_b: UInt64,
    ) -> None:
        """Burn LP tokens to withdraw proportional reserves."""
        self._update_twap()

        assert lp_txn.asset_receiver == Global.current_application_address
        assert lp_txn.xfer_asset == Asset(self.lp_token_id.value)

        lp_amount = lp_txn.asset_amount
        assert lp_amount > UInt64(0)

        total_lp = self.lp_total_supply.value
        reserve_a = self.reserve_a.value
        reserve_b = self.reserve_b.value

        # Proportional withdrawal (floor division: favors pool)
        a_high, a_low = op.mulw(lp_amount, reserve_a)
        q_hi, amount_a, r_hi, r_lo = op.divmodw(a_high, a_low, UInt64(0), total_lp)

        b_high, b_low = op.mulw(lp_amount, reserve_b)
        q_hi, amount_b, r_hi, r_lo = op.divmodw(b_high, b_low, UInt64(0), total_lp)

        # Slippage protection
        assert amount_a >= min_a, "Slippage on asset A"
        assert amount_b >= min_b, "Slippage on asset B"
        assert amount_a > UInt64(0) and amount_b > UInt64(0)

        # Send both assets back
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

        # Update reserves and LP supply
        self.reserve_a.value = reserve_a - amount_a
        self.reserve_b.value = reserve_b - amount_b
        self.lp_total_supply.value = total_lp - lp_amount
```

The floor division on both withdrawal amounts ensures the pool never pays out more than its proportional share --- rounding dust stays in the reserves.


## Understanding Impermanent Loss

Now that you understand the complete AMM lifecycle --- bootstrapping, adding liquidity, swapping, and removing liquidity --- you are ready for the most important economic concept for liquidity providers.

Providing liquidity to an AMM is not free money. The 0.3% trading fees are real income, but they come with a hidden cost: *impermanent loss* (IL). Every liquidity provider must understand this before depositing. (See [Why Algorand?](https://dev.algorand.co/getting-started/why-algorand/) for how Algorand's low fees make frequent rebalancing practical.)

Impermanent loss is the difference in value between holding tokens in a pool versus simply holding them in your wallet. It occurs because the AMM rebalances your position as prices move --- you end up with more of whichever token became cheaper and less of whichever became more expensive.

**A concrete example.** Alice deposits 1,000 USDC and 1,000 ALGO (at $1 each) into a pool. Her position is worth $2,000. ALGO doubles to $2. If Alice had just held, she would have 1,000 USDC + 1,000 ALGO = $3,000. But the pool rebalanced: the constant product formula means the pool now holds more USDC and less ALGO. Alice's share is worth approximately $2,828. She lost $172 compared to holding --- that is her impermanent loss (about 5.7%).

The loss is called "impermanent" because it reverses if the price returns to its original ratio. But if Alice withdraws while the price is different, the loss becomes permanent.

The IL formula for a price change of ratio $r$ (where $r = \text{new price} / \text{original price}$):

$$IL = \frac{2\sqrt{r}}{1 + r} - 1$$

| Price Change | IL |
|-------------|-----|
| 1.25x (25% up) | -0.6% |
| 1.5x (50% up) | -2.0% |
| 2x (double) | -5.7% |
| 3x (triple) | -13.4% |
| 5x (5x) | -25.5% |

The same loss applies for equivalent price *decreases* (a 2x drop = same 5.7% IL as a 2x rise).

**When do fees overcome IL?** If the pool generates enough trading fees to exceed the IL, providing liquidity is profitable. This depends on trading volume relative to pool size. A pool with $100K TVL and $50K daily volume generates far more fee income per LP dollar than a pool with $10M TVL and the same volume. High-volume, tight-spread pools (like major stablecoin pairs) tend to overcome IL; low-volume, volatile pairs often do not.

> **Warning:** Impermanent loss is the primary risk for liquidity providers. The 0.3% swap fee partially offsets IL but does not eliminate it. Before providing liquidity in production, calculate the breakeven volume needed for your pool's volatility profile.

This is the fundamental reason Uniswap V3 introduced concentrated liquidity --- by letting LPs focus capital in a narrow price range, they earn higher fees per dollar (improving the fees-vs-IL tradeoff) but amplify the loss if price moves outside their range. No Algorand DEX currently implements a full Uniswap V3-style concentrated liquidity AMM; the ecosystem uses constant product (V2-style) pools and StableSwap variants. The constant product model we built here is what Tinyman and Pact use in production.


## Security Hardening and the Tinyman V1 Lesson

On January 1, 2022, attackers exploited a vulnerability in Tinyman V1's burn (remove liquidity) function, extracting approximately \$3 million. The root cause: the contract failed to verify that two different assets were being returned during liquidity removal. An attacker could construct a transaction that received the same token twice, effectively doubling their withdrawal of one asset while getting nothing of the other.

The key lessons from this exploit shape our contract's security posture.

First, **explicit invariant verification after every operation**. Our swap method calculates the output from the formula and relies on the math being correct. But the Tinyman exploit showed that complex TEAL logic can have subtle control flow bugs that bypass the intended math. Adding an explicit check that $k_{new} \geq k_{old}$ after every state-changing operation catches implementation bugs that the formula alone might miss.

Second, **immutable contracts cannot be patched**. When Tinyman discovered the exploit, they could not update the contracts because they were immutable. They could only recommend that users withdraw their liquidity. This is actually the correct tradeoff --- immutability is what makes the contracts trustless. But it means your code must be correct before deployment. There is no hot-fix option.

Third, **asset verification in every transfer**. Our contract explicitly checks `input_txn.xfer_asset == Asset(self.asset_a.value)` in the swap method. It checks `a_txn.xfer_asset == Asset(self.asset_a.value)` in add_liquidity. It checks `lp_txn.xfer_asset == Asset(self.lp_token_id.value)` in remove_liquidity. Never assume the correct asset was sent --- always verify.

Beyond the Tinyman case study, the Trail of Bits "Not So Smart Contracts" database and the Panda static analysis framework (USENIX Security 2023) identified systematic vulnerability patterns. Panda found that 27.73\% of deployed Algorand applications had at least one vulnerability. The most common categories include missing authorization checks, group size validation gaps, inner transaction fee drains, and --- for Logic Signatures --- missing close-to and rekey-to checks (the #1 finding, though not applicable to stateful contracts like ours).

Our contract addresses the categories that apply to stateful contracts: the contract is immutable (update/delete rejected), all inner transaction fees are zero (preventing fee drain), every incoming transfer is verified for asset ID and receiver, and all privileged methods check caller authorization.

Regarding reentrancy: classical reentrancy attacks are impossible on Algorand. The AVM has no fallback functions or callbacks triggered by token transfers. When your contract sends tokens via an inner transaction, no user code executes on the receiving side. The contract maintains full, uninterrupted control flow. This eliminates the entire class of *reentrancy* exploits that have caused hundreds of millions of dollars in losses on other blockchains. (See [Ethereum to Algorand](https://dev.algorand.co/getting-started/ethereum-to-algorand/) for a detailed security model comparison.)

Regarding MEV (Miner/Maximum Extractable Value): Algorand's block proposers are selected randomly each round via VRF. No one knows who the proposer will be in advance, making targeted collusion difficult. Transaction ordering follows first-come-first-served by default, not fee-based priority. Sandwich attacks --- where an attacker inserts transactions before and after a victim's swap --- are significantly harder than on Ethereum, but not impossible. A block proposer has some discretion over transaction ordering within their proposed block, and the mempool, while not publicly accessible like Ethereum's, is visible to relay nodes. Slippage protection via `min_output` remains the primary defense, and should always be set to a meaningful value --- never zero in production.


## Client-Side Quote Calculation

Never submit an on-chain transaction just to get a price quote. The swap output can be calculated client-side using the same constant-product formula, reading reserves from [global state](https://dev.algorand.co/concepts/smart-contracts/storage/global/) (which is a free API call --- no transaction, no fee). This is how frontends display real-time quotes and price impact warnings. Pattern 12 in the Common Patterns chapter provides the complete client-side `get_swap_quote` helper function with price impact calculation and slippage defaults.

## The TWAP Price Oracle

> **Optional section.** The core AMM is now complete --- you can bootstrap a pool, add liquidity, swap, and remove liquidity. The remainder of this chapter extends the AMM with a Time-Weighted Average Price (TWAP) oracle. This is an advanced topic that you can skip on first reading and return to later. The TWAP is not required for the farming contract in Chapter 6.

Our AMM stores its reserves in global state, which any other contract can read. This makes the pool a natural price oracle --- but one that must be used carefully.

### Why Spot Prices Are Dangerous

A lending protocol that needs to know the ALGO/USDC price could read our pool's reserves and compute a spot price: `reserve_b / reserve_a`. But spot prices are trivially manipulable. Consider a pool with reserves of 10,000 USDC and 10,000 ALGO (spot price: 1.0). An attacker with 100,000 USDC swaps into the pool, temporarily pushing the price to approximately 0.01 ALGO/USDC. If a liquidation contract checks the spot price at this moment, it would incorrectly conclude that ALGO is nearly worthless and liquidate healthy positions. The attacker then swaps back, restoring the price. This entire attack fits in a single atomic group.

Production price oracles solve this with a **Time-Weighted Average Price (TWAP)** --- a price that reflects the average over many blocks, not just the current instant. An attacker who manipulates the spot price for one block (2.85 seconds) barely affects a 1-hour TWAP: their manipulation contributes only $2.85 / 3600 \approx 0.08\%$ of the average.

> *Before reading on: if a single-block manipulation costs the attacker nothing and distorts the price completely, what property would an oracle need to make manipulation expensive?*

### Cumulative Price Tracking

A TWAP oracle tracks the cumulative sum of prices over time. The *cumulative price* at any moment is:

$$\text{cumulative\_price}_t = \text{cumulative\_price}_{t-1} + \text{spot\_price} \times \Delta t$$

The TWAP between two timestamps $t_1$ and $t_2$ is:

$$\text{TWAP} = \frac{\text{cumulative\_price}_{t_2} - \text{cumulative\_price}_{t_1}}{t_2 - t_1}$$

> *Quick check: if the cumulative price at t=100 is 500,000 and at t=200 is 1,200,000, what is the TWAP over that interval?*

In production AMMs (Uniswap V2, Tinyman V2), the cumulative price accumulators live inside the pool contract itself and update on every swap, mint, and burn. This is why we added the three TWAP state variables to `__init__` and the `_update_twap()` call at the top of every state-changing method. The price oracle is available to any external consumer --- lending protocols, liquidation engines, farming contracts --- without any of those consumers needing to maintain their own accumulator.

The `_update_twap` call happens *before* reserves change. This is the same design as Uniswap V2: the accumulated price is the price that *held* since the last update, not the price created by the current transaction.

### BigUInt: When UInt64 Is Not Enough

We used `BigUInt` briefly in `add_initial_liquidity` for the square root calculation. Now we need it for a different reason: the TWAP cumulative values grow without bound and will eventually exceed `UInt64`. `BigUInt` is an arbitrary-precision integer type (up to 512 bits) that works with standard Python operators (`+`, `-`, `*`, `//`) rather than the `mulw`/`divmodw` pair. `BigUInt` arithmetic compiles to the AVM's `b+`, `b*`, `b/` opcodes, which cost roughly 10--20 opcodes each (compared to 1 for `UInt64` operations). `BigUInt` values are stored in global state as byte-slice slots, not uint slots, so they count toward your `global_bytes` schema allocation. Use `BigUInt` when your values can exceed $2^{64}$; stick with `UInt64` and wide arithmetic when they cannot.

The cumulative price grows without bound. With a spot price of 1,000,000 (scaled by $10^9$) and 1 year of accumulation:

$$1{,}000{,}000{,}000 \times 31{,}536{,}000 = 3.15 \times 10^{16}$$

This fits in `UInt64`. But at higher prices or over longer periods --- or with a higher precision scale factor --- the cumulative value can exceed $2^{64}$. Uniswap V2 accumulates prices encoded as `UQ112.112` fixed-point values (224 bits) in `uint256` accumulators, intentionally allowing overflow --- the TWAP is computed via modular subtraction, which handles wrapping correctly.

On Algorand, `BigUInt` supports up to 512 bits --- more than enough for any practical TWAP accumulation. The tradeoff is that `BigUInt` arithmetic costs roughly 10x more opcodes than `UInt64`. For a single TWAP update per transaction (two multiplications, one addition), this is approximately 30 extra opcodes --- negligible within a 700-opcode budget. Compare this with the EVM, where Solidity's `uint256` arithmetic handles intermediate products natively and Uniswap V2 uses `uint224` as a deliberate overflow boundary. On the AVM, `UInt64` would overflow within days at moderate prices, so `BigUInt` is not optional --- it is a required design choice. The AVM's constraints force you to think about overflow earlier in the design process, which is arguably a safety benefit.

### The TWAP Update Subroutine

Add this method to the `ConstantProductPool` class. It reads the pool's own reserves (no cross-contract read needed --- they are local state) and accumulates the price:

```python
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
```

The method is already called at the top of `swap`, `add_liquidity`, and `remove_liquidity`. For `add_initial_liquidity`, we initialize `twap_last_update` instead (there are no pre-existing reserves to accumulate).

### Reading the TWAP

A read-only method returns the average price over a caller-specified window. The caller provides the cumulative price snapshot from their last interaction (stored client-side or in a separate contract's state):

```python
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

> **Note:** The `readonly=True` flag means this method can be called via `simulate` without submitting a transaction --- no fees, no state changes. Frontends use this to display real-time price data. The inline accumulation at the top of `get_twap_price` ensures the cumulative value is current even if the pool has not been interacted with recently --- the same approach Uniswap V2 takes in its `currentCumulativePrices` helper. Because the method is read-only, the state writes from this accumulation do not persist.

The method returns a `UInt64`, which means the TWAP result must fit in 64 bits. This is a deliberate design choice --- `UInt64` is easier for callers to work with than a variable-length `BigUInt` --- but it requires a bounds check.

> **Warning:** The `op.btoi` call accepts a byte array of 0--8 bytes and interprets it as a big-endian unsigned integer. A `BigUInt` that exceeds $2^{64} - 1$ would produce more than 8 bytes, causing `btoi` to fail at runtime. The `assert twap < BigUInt(2**64)` guard ensures the TWAP result fits in 64-bit range before the conversion. With `TWAP_PRECISION = 10^9` and typical asset prices, this bound is safe for years of accumulation. If you use a higher precision scale factor or expect extreme price ratios, return a `BigUInt` instead of converting to `UInt64`.

### Manipulation Resistance

A 1-hour TWAP window requires an attacker to sustain the manipulated price for the full hour to meaningfully distort the average. Sustaining the manipulation means keeping a large amount of capital locked in the pool for that duration --- capital that is exposed to arbitrageurs who would trade against the distortion for profit. The cost of manipulation scales linearly with the TWAP window length and the pool's liquidity depth. For pools with meaningful TVL and a 1-hour+ window, TWAP manipulation is economically irrational.

**Quantifying the cost.** Suppose a pool has \$1M in total value locked (500K USDC + equivalent ALGO). To move the spot price by 10\%, an attacker needs to add approximately \$52,600 in one-sided liquidity (from the constant product formula). To sustain this for 1 hour, that capital is locked and exposed to ~\$5,260 in arbitrage losses. The TWAP distortion from this 1-hour manipulation is only $10\% \times (2.85 / 3600) \approx 0.008\%$ per block of manipulation --- negligible. The attacker would need to sustain the manipulation for the entire window at a cost far exceeding any plausible profit.

### Reading Pool Prices From Other Contracts

External contracts consume the TWAP by reading the pool's cumulative price state via `op.AppGlobal.get_ex_bytes` (since `BigUInt` values are stored as byte slices, not uint64). This is an illustrative example showing a separate lending contract, not part of the AMM project code:

```python
# In a separate lending contract:
@arc4.abimethod
def get_price_from_amm(
    self, amm_app: Application
) -> UInt64:
    """Read AMM spot price from reserves."""
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

> **Warning:** The spot price example above is shown for educational purposes. In production, always use the TWAP. External contracts can read the cumulative price accumulators from the pool's global state, store periodic snapshots, and compute the TWAP over their desired window.

Multi-hop price derivation (reading prices across chained pools, e.g., ALGO/USDC via ALGO/TOKEN and TOKEN/USDC) follows the same pattern --- read reserves from each pool in the chain and multiply the ratios. (See [Opcodes Overview](https://dev.algorand.co/concepts/smart-contracts/opcodes-overview/) for the cross-app state reading opcodes.)


## Testing the AMM

> **Note:** The tests below are structural outlines showing *what* to test and *how* to assert. The patterns here --- lifecycle tests, failure-path tests, invariant tests --- are the ones you should implement for any production contract.

As with Chapter 3, here is one complete test helper showing how the Chapter 2 pattern translates to the AMM. The remaining helpers (`bootstrap_pool`, `add_liquidity`, `swap`) follow the same approach --- adapt the deployment script patterns from earlier in this chapter:

```python
from pathlib import Path
import algokit_utils

APP_SPEC = Path(
    "smart_contracts/artifacts/constant_product_pool/"
    "ConstantProductPool.arc56.json"
).read_text()

def deploy_pool(algorand, admin):
    """Deploy a fresh AMM pool and fund it for MBR."""
    factory = algorand.client.get_app_factory(
        app_spec=APP_SPEC,
        default_sender=admin.address,
    )
    # send.bare.create() for a fresh instance each time
    app_client, _ = factory.send.bare.create()
    # Fund for MBR: base (100K) + 3 ASA opt-ins (300K)
    # + box headroom + inner txn fees
    algorand.send.payment(
        algokit_utils.PaymentParams(
            sender=admin.address,
            receiver=app_client.app_address,
            amount=(
                algokit_utils.AlgoAmount
                .from_micro_algo(500_000)
            ),
        )
    )
    return app_client
```

> **Exercise:** Implement `bootstrap_pool(algorand, admin, pool, token_a, token_b)` using the bootstrap deployment script as a template. It should call the `bootstrap` method with a seed payment and both token IDs, then return the LP token ID.

The following test outlines go in `tests/test_amm.py` (not part of the contract code):

```python
class TestConstantProductPool:
    def test_bootstrap_creates_lp_token(self, algorand):
        pool = deploy_pool(algorand, admin)
        lp_id = call_method(pool, "bootstrap", [fund, usdc, algo])
        assert lp_id.abi_return > 0

    def test_initial_liquidity_sets_price(self, algorand):
        lp_tokens = call_method(pool, "add_initial_liquidity",
            [transfer_usdc(1000), transfer_algo(4)])
        assert lp_tokens.abi_return > 0

    def test_swap_respects_constant_product(self, algorand):
        old_k = reserve_a * reserve_b
        call_method(pool, "swap", [transfer_usdc(100), 0])
        new_k = get_reserve_a(pool) * get_reserve_b(pool)
        assert new_k >= old_k

    def test_swap_rejects_excessive_slippage(self, algorand):
        with pytest.raises(Exception, match="Slippage exceeded"):
            call_method(pool, "swap", [transfer_usdc(100), 999999999])

    def test_remove_liquidity_proportional(self, algorand):
        # Add liquidity, then remove half
        call_method(pool, "remove_liquidity", [burn_lp(half), 0, 0])
        # Verify reserves decreased proportionally

    def test_immutability(self, algorand):
        with pytest.raises(Exception):
            pool.update()
        with pytest.raises(Exception):
            pool.delete()

    def test_fee_accumulation(self, algorand):
        # Execute many swaps, verify k increases
        initial_k = reserve_a * reserve_b
        for _ in range(10):
            call_method(pool, "swap", [transfer_usdc(100), 0])
        final_k = get_reserve_a(pool) * get_reserve_b(pool)
        assert final_k > initial_k
```

## Moving to TestNet

Once your contract works on LocalNet, the next step is TestNet --- Algorand's public test network where you can interact with other contracts, test with real network conditions (block times, transaction propagation), and share your deployment with others for testing.

To deploy on TestNet, you need a funded TestNet account. Get free TestNet Algo from the faucet at https://lora.algokit.io/testnet/fund or by running `algokit dispenser login` and `algokit dispenser fund`.

Switch your `AlgorandClient` to TestNet. This is a client-side configuration change:

```python
# Instead of default_localnet():
algorand = AlgorandClient.testnet()
# Or connect to a specific algod endpoint:
algorand = AlgorandClient.from_clients(
    algod=AlgodClient("", "https://testnet-api.4160.nodely.dev"),
)
```

The deployment and interaction scripts are identical to LocalNet --- only the client connection changes. Deploy, bootstrap, and run through the full workflow. Verify every operation by checking the contract's global state and your account balances on a TestNet block explorer like https://testnet.explorer.perawallet.app/. (See [App Deployment](https://dev.algorand.co/algokit/utils/python/app-deploy/) for idempotent deployment strategies.)

Before deploying to MainNet, your TestNet testing checklist should include: bootstrap with real ASAs (not just test tokens), add liquidity from multiple accounts, execute swaps in both directions with varying sizes, remove liquidity and verify proportional withdrawal, test edge cases (very small swaps, swaps that would exceed reserves, swaps with zero min_output), and verify immutability by attempting update and delete.


## Summary

In this chapter you learned to:

- Derive and implement the constant product formula ($x \times y = k$) for automated market making
- Bootstrap a pool contract that creates its own LP token and opts into trading pair assets
- Implement safe swap logic with fee deduction, slippage protection, and explicit invariant verification
- Calculate LP token minting amounts using the geometric mean for initial liquidity and proportional ratios for subsequent deposits
- Implement proportional liquidity withdrawal with dual slippage protection
- Apply the Tinyman V1 lesson: defense-in-depth invariant checks that catch exploits even when individual validations fail
- Build a TWAP price oracle using `BigUInt` cumulative price tracking for manipulation-resistant price feeds
- Build client-side quote calculations using free global state reads

This chapter applied the foundational concepts from the vesting contract to a significantly more complex DeFi application. Some concepts were reused directly (inner transactions, group transactions, security checks), while others were introduced fresh.

| Feature | New Concepts |
|---------|-------------|
| Constant product formula | AMM theory, fee mechanics, invariant $x \times y = k$ |
| Bootstrapping | Multi-inner-transaction sequences, canonical asset ordering, LP token creation |
| Initial liquidity | Geometric mean, BigUInt square root, minimum liquidity lock |
| Swaps | Slippage protection, swap direction detection, explicit invariant verification |
| Add liquidity | Proportional minting with min() ratio, unbalanced deposit penalty |
| Remove liquidity | Proportional withdrawal, dual slippage protection |
| TWAP oracle | Cumulative price tracking, BigUInt, manipulation resistance |
| Security | Tinyman V1 case study, defense-in-depth invariant checks, MEV on Algorand |
| Client integration | Off-chain quote calculation, free state reads |

In the next chapter, we extend this AMM with a yield farming contract --- a staking system where LPs lock their LP tokens to earn reward tokens, introducing the reward accumulator pattern and smart contract composition.

## Exercises

1. **(Apply)** Write a client-side function that calculates the price impact of a swap as a percentage, given the input amount and current reserves.

2. **(Analyze)** The AMM uses tracked reserves (explicit `self.reserve_a.value`) rather than reading the contract's actual on-chain balance. What happens if someone accidentally sends tokens directly to the contract address without calling any method? Are those tokens recoverable? Is this a bug or a deliberate design choice?

3. **(Create)** Design an extension that adds a 0.05% protocol fee on top of the existing 0.3% LP fee. The protocol fee should accumulate in a separate global state variable and be withdrawable by the admin. Sketch the code changes needed in the `swap` method and write a new `withdraw_protocol_fees` method.

    *Hint:* Add `self.protocol_fees_a = GlobalState(UInt64(0))` and `self.protocol_fees_b = GlobalState(UInt64(0))` to `__init__`. In the `swap` method, after calculating `output_amount`, compute `protocol_fee = output_amount * UInt64(5) // UInt64(10000)` (0.05%), subtract it from the output sent to the user, and add it to the appropriate protocol fee accumulator. The `withdraw_protocol_fees` method should be admin-only, send both accumulated fee balances via inner transactions, and reset the accumulators to zero.

4. **(Analyze)** The TWAP oracle stops accumulating if no transactions interact with the pool. If there is a 24-hour gap with no swaps or liquidity operations, the TWAP becomes stale. Design a public `poke_twap` method that allows anyone (a keeper bot) to trigger a TWAP update without performing a swap. What should the method do, and what incentive does a keeper have to call it?

5. **(Create, cross-chapter)** Write a simulate-based test (Chapter 2's pattern) that verifies the AMM rejects a swap where `min_output` exceeds the available output. Use `.simulate()` to construct the failing swap and verify the failure message contains `"Slippage exceeded"`.

> **Practice with the Cookbook.** Reinforce this chapter's concepts with Cookbook recipes: 3.2–3.3 (BigUInt and wide arithmetic), 4.3 (reading another app's state), 7.2 (ASA opt-in), 8.4 (fee pooling), and 12.1 (module-level subroutines).

## Further Reading

- [Algorand Python Operations](https://dev.algorand.co/algokit/languages/python/lg-ops/) --- mulw, divmodw, bsqrt, and other op module functions
- [Uniswap V2 TWAP Oracle](https://docs.uniswap.org/contracts/v2/guides/smart-contract-integration/building-an-oracle) --- the reference implementation for cumulative price tracking
- [ARC-28: Event Logging](https://dev.algorand.co/arc-standards/arc-0028/) --- standardized event emission for off-chain indexing
- [App Deployment](https://dev.algorand.co/algokit/utils/python/app-deploy/) --- idempotent deployment strategies
- [Transaction Composer](https://dev.algorand.co/algokit/utils/python/transaction-composer/) --- building atomic groups with AlgoKit Utils
- [Testing](https://dev.algorand.co/algokit/utils/python/testing/) --- pytest patterns for Algorand contracts
