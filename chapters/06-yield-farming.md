\newpage

# Yield Farming --- Extending the AMM with Staking Rewards

Your AMM works. Liquidity providers deposit tokens, traders swap against the pool, fees accumulate in the reserves, and LP tokens track each provider's share. But nothing stops an LP from providing liquidity for five minutes, collecting a fractional share of fees, and withdrawing. There is no incentive to commit capital for the long term, and no mechanism to reward the LPs who provide the stable, deep liquidity that makes a pool actually useful for traders.

This is the problem *yield farming* solves. In a yield farming system, LPs lock their LP tokens in a separate staking contract for a fixed duration --- 30 days, 90 days, a year --- and earn additional reward tokens on top of the trading fees they already collect from the pool. Longer lock-ups earn proportionally higher rewards, creating a direct incentive for the sticky liquidity that healthy markets depend on.

We are going to build a staking contract that composes with the AMM from the previous chapter. Users deposit LP tokens from that pool, lock them for a chosen duration, and earn a reward token distributed continuously over time. The contract reads the AMM's global state to verify that the LP tokens are genuine and demonstrates the reward-per-token accumulator pattern used by virtually every DeFi staking system.

Two core concepts drive this chapter. First, the *reward accumulator pattern* --- a mathematical technique (popularized by Synthetix) that distributes rewards fairly across any number of stakers without iterating over them. Second, *smart contract composition* --- reading another contract's state to make trust decisions, a fundamental DeFi building block that connects isolated contracts into composable protocols.

By the end of this chapter you will have a working staking contract, deployed on LocalNet alongside your AMM, with lock-up multipliers, continuous reward distribution, and cross-contract verification of LP token provenance.

> **Note:** This chapter assumes you have a working AMM from the previous chapter. The farming contract reads the AMM's global state and accepts its LP tokens. If you skipped the AMM chapter, go back and build it first --- the farming contract will not compile or deploy without it.


## A Simplified Staking Contract

Before tackling the real accumulator math, let us build the simplest possible staking contract. This version has a fixed 30-day lock period, a single reward pool, and straightforward proportional math. It will work for a handful of stakers, and building it first makes the problems that motivate the accumulator pattern concrete rather than abstract.

The contract accepts LP tokens (passed as an initialization parameter), locks them for 30 days, and distributes rewards proportionally based on each staker's share of the total staked LP tokens.

Create a new project for this chapter:

```bash
algokit init -t python --name lp-farming
cd lp-farming/projects/lp-farming
algokit project bootstrap all
mv smart_contracts/hello_world smart_contracts/lp_farming
```

Delete the template-generated `deploy_config.py` inside the renamed directory. Your contract code goes in `smart_contracts/lp_farming/contract.py`.

Here is the simplified version. Replace the contents of `contract.py`:

```python
from algopy import (
    Account, ARC4Contract, Asset, Bytes, Global,
    GlobalState, Txn, UInt64, arc4, gtxn, itxn, op,
    BoxMap,
)

SECONDS_PER_DAY = 86400
LOCK_DURATION = 30 * SECONDS_PER_DAY  # 30 days


class StakeInfo(arc4.Struct):
    lp_amount: arc4.UInt64
    stake_time: arc4.UInt64
    reward_claimed: arc4.UInt64


class SimpleFarm(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.lp_token_id = GlobalState(UInt64(0))
        self.reward_token_id = GlobalState(UInt64(0))
        self.total_staked = GlobalState(UInt64(0))
        self.total_rewards = GlobalState(UInt64(0))
        self.reward_end_time = GlobalState(UInt64(0))
        self.is_initialized = GlobalState(UInt64(0))
        self.stakes = BoxMap(
            arc4.Address, StakeInfo, key_prefix=b"s_"
        )

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.admin.value = Txn.sender.bytes

    @arc4.baremethod(
        allow_actions=["UpdateApplication", "DeleteApplication"]
    )
    def reject_lifecycle(self) -> None:
        assert False, "Contract is immutable"

    @arc4.abimethod
    def initialize(
        self,
        lp_token: Asset,
        reward_token: Asset,
    ) -> None:
        assert Txn.sender == Account(self.admin.value)
        assert self.is_initialized.value == UInt64(0)

        self.lp_token_id.value = lp_token.id
        self.reward_token_id.value = reward_token.id

        # Opt into both tokens
        itxn.AssetTransfer(
            xfer_asset=lp_token,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()
        itxn.AssetTransfer(
            xfer_asset=reward_token,
            asset_receiver=Global.current_application_address,
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()

        self.is_initialized.value = UInt64(1)

    @arc4.abimethod
    def deposit_rewards(
        self,
        reward_txn: gtxn.AssetTransferTransaction,
        duration_days: UInt64,
    ) -> None:
        assert Txn.sender == Account(self.admin.value)
        assert reward_txn.xfer_asset == Asset(
            self.reward_token_id.value
        )
        assert reward_txn.asset_receiver == (
            Global.current_application_address
        )

        self.total_rewards.value = reward_txn.asset_amount
        self.reward_end_time.value = (
            Global.latest_timestamp
            + duration_days * UInt64(SECONDS_PER_DAY)
        )

    @arc4.abimethod
    def stake(
        self,
        lp_txn: gtxn.AssetTransferTransaction,
    ) -> None:
        assert lp_txn.xfer_asset == Asset(
            self.lp_token_id.value
        )
        assert lp_txn.asset_receiver == (
            Global.current_application_address
        )
        assert lp_txn.sender == Txn.sender
        assert lp_txn.asset_amount > UInt64(0)

        key = arc4.Address(Txn.sender)
        assert key not in self.stakes, "Already staked"
        self.stakes[key] = StakeInfo(
            lp_amount=arc4.UInt64(lp_txn.asset_amount),
            stake_time=arc4.UInt64(Global.latest_timestamp),
            reward_claimed=arc4.UInt64(0),
        )
        self.total_staked.value += lp_txn.asset_amount

    @arc4.abimethod
    def claim(self) -> UInt64:
        stake = self.stakes[arc4.Address(Txn.sender)].copy()
        lp_amount = stake.lp_amount.native
        stake_time = stake.stake_time.native
        claimed = stake.reward_claimed.native
        assert lp_amount > UInt64(0), "No stake"
        assert stake_time < self.reward_end_time.value, (
            "Reward period ended"
        )

        now = Global.latest_timestamp
        total_duration = (
            self.reward_end_time.value - stake_time
        )
        elapsed = now - stake_time
        if elapsed > total_duration:
            elapsed = total_duration

        # reward = (lp / total_lp) * (elapsed / duration)
        #        * total_rewards
        high1, low1 = op.mulw(
            lp_amount, self.total_rewards.value
        )
        q1_hi, numerator, r1_hi, r1_lo = op.divmodw(
            high1, low1, UInt64(0),
            self.total_staked.value,
        )
        high2, low2 = op.mulw(numerator, elapsed)
        q2_hi, reward, r2_hi, r2_lo = op.divmodw(
            high2, low2, UInt64(0), total_duration
        )

        payout: UInt64 = reward - claimed
        assert payout > UInt64(0), "Nothing to claim"

        stake.reward_claimed = arc4.UInt64(reward)
        self.stakes[arc4.Address(Txn.sender)] = stake.copy()

        itxn.AssetTransfer(
            xfer_asset=Asset(self.reward_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=payout,
            fee=UInt64(0),
        ).submit()

        return payout

    @arc4.abimethod
    def unstake(self) -> None:
        stake = self.stakes[arc4.Address(Txn.sender)].copy()
        lp_amount = stake.lp_amount.native
        stake_time = stake.stake_time.native
        assert lp_amount > UInt64(0), "No stake"
        assert Global.latest_timestamp >= (
            stake_time + UInt64(LOCK_DURATION)
        ), "Lock period not expired"

        # Return LP tokens
        itxn.AssetTransfer(
            xfer_asset=Asset(self.lp_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=lp_amount,
            fee=UInt64(0),
        ).submit()

        self.total_staked.value -= lp_amount
        del self.stakes[arc4.Address(Txn.sender)]
```

This contract works. You can deploy it, stake LP tokens, claim rewards after some time passes, and unstake after 30 days. But it has three problems that become serious at scale:

**Problem 1: The reward math does not scale.** The formula `(lp / total_lp) * (elapsed / duration) * total_rewards` looks correct for one staker, but it breaks when stakers enter and exit at different times. If Alice stakes 100 LP at time 0 and Bob stakes 200 LP at time 50, Alice's share retroactively drops from 100% to 33% --- but the formula does not account for the period when Alice was the only staker and deserved 100% of those rewards. Alice gets systematically underpaid, and Bob gets overpaid for time he was not staked.

**Problem 2: No incentive for longer locks.** Everyone locks for the same 30 days. A user who commits for a year gets no additional reward over someone who commits for a month. This means the contract cannot attract the long-term, stable liquidity that pools need most.

**Problem 3: No LP token verification.** The contract accepts any token with the right ASA ID, but it does not verify that the LP token actually came from a specific AMM pool. Someone could create a fake LP token with the same ID structure and stake it. We need cross-contract composition to verify the LP token's origin.

*Before reading the solution to Problem 1, think about this: if Alice stakes 100 LP at time 0 and Bob stakes 200 LP at time 50, and the reward rate is 10 tokens per second, how should rewards be distributed after 200 seconds? Alice was the sole staker for the first 50 seconds --- does her reward reflect that? Try to work out a fair distribution, then read on to see how the accumulator pattern solves it.*


## The Reward Accumulator Pattern

The simplified version's core flaw is that it tries to compute each user's reward share from scratch every time. This requires knowing the exact staking history of every participant --- who was staked, how much, and for how long. With two stakers, the math is manageable. With ten thousand, it is impossible within the AVM's opcode budget.

### Why Per-User Tracking Fails

Consider the naive approach: maintain a list of all stakers and iterate through them whenever someone stakes, unstakes, or claims. For each staker, recalculate their share based on the new total. This is O(n) per operation, and with the AVM's 700-opcode-per-call budget (even pooled to ~11,200 across a 16-transaction group), you run out of gas with a few dozen stakers.

Even if you could iterate, the math is wrong. When Bob stakes at time 50, the per-second reward rate changes for everyone. Alice was earning 10 tokens/second alone; now she earns 3.33 tokens/second. But her earnings from time 0 to 50 should not change. You need to "settle" every staker's accrued rewards before changing the rate --- which brings us back to the O(n) iteration problem.

### The Snapshot-and-Diff Insight

The solution is a global accumulator that answers the question: "How many reward tokens has one unit of LP earned since the beginning of time?" This number is called `reward_per_token`. Each user stores a snapshot of `reward_per_token` at the time they last interacted with the contract. Their pending reward is simply:

$$\text{reward} = \text{lp\_amount} \times (\text{reward\_per\_token}_{\text{now}} - \text{reward\_per\_token}_{\text{snapshot}})$$

This is O(1) per operation. No iteration over stakers. No historical tracking. The global value accumulates continuously, and each user's snapshot captures "where they got on."

### The Update Formula

The accumulator updates on every state-changing call (stake, unstake, claim). The update adds the rewards that have accrued since the last update:

$$\text{reward\_per\_token} \mathrel{+}= \frac{\text{reward\_rate} \times \Delta t \times \text{PRECISION}}{\text{total\_staked}}$$

Where:
- `reward_rate` is tokens per second distributed to the entire pool
- `delta_t` is seconds since the last update (`min(now, reward_end) - last_update`)
- `PRECISION` is a scaling factor (we use $10^9$) to preserve fractional precision in integer math
- `total_staked` is the current total LP tokens in the contract

The `min(now, reward_end)` clamping ensures rewards stop accumulating after the reward period ends.

> **Warning:** The zero-balance guard is critical. If `total_staked` is zero, the update must be skipped entirely --- dividing by zero panics the AVM, and accumulating rewards when nobody is staked would create tokens from nowhere. Always check `total_staked > 0` before updating the accumulator.

### Wide Arithmetic

The multiplication `reward_rate * delta_t * PRECISION` can overflow `UInt64` (max $\approx 1.8 \times 10^{19}$). With `PRECISION = 10^9`, a `reward_rate` of 1,000,000 tokens/second, and a `delta_t` of 86,400 seconds (one day):

$$1{,}000{,}000 \times 86{,}400 \times 10^9 = 8.64 \times 10^{19}$$

This exceeds `UInt64`'s maximum. We must use `op.mulw` for the 128-bit intermediate product and `op.divmodw` for the 128-bit division:

```python
# reward_rate * delta_t fits in UInt64 for realistic
# parameters, so we compute it directly:
rate_time = reward_rate * delta_t
# Multiply by PRECISION (128-bit via mulw),
# then divide by total_staked:
high, low = op.mulw(rate_time, UInt64(PRECISION))
q_hi, increment, r_hi, r_lo = op.divmodw(
    high, low, UInt64(0), total_staked
)
```

> **Note:** The `rate_time = reward_rate * delta_t` product must fit in `UInt64`. With a maximum reward rate of $10^6$ tokens/second and a maximum delta of one year ($\approx 3.15 \times 10^7$ seconds), the product is $\approx 3.15 \times 10^{13}$ --- safely within the $1.84 \times 10^{19}$ `UInt64` limit. If your reward parameters are extreme (rate exceeding $\approx 5 \times 10^{11}$ tokens/second), use an additional `mulw` stage or switch to `BigUInt`.

### Visual Trace: Two Stakers

Let us trace through a concrete scenario with `reward_rate = 10` tokens/second and `PRECISION = 10^9`.

**Time 0: Alice stakes 100 LP**

| Event | `reward_per_token` | Alice snapshot | Bob snapshot | Alice pending | Bob pending |
|-------|-------------------|----------------|-------------|---------------|------------|
| Alice stakes 100 | 0 | 0 | --- | 0 | --- |

`total_staked = 100`. No time has passed, so no accumulator update.

**Time 100: Bob stakes 200 LP**

Before Bob's stake, update the accumulator:

$$increment = \frac{10 \times 100 \times 10^9}{100} = 10{,}000{,}000{,}000$$

$$\text{reward\_per\_token} = 0 + 10{,}000{,}000{,}000 = 10{,}000{,}000{,}000$$

| Event | `reward_per_token` | Alice snapshot | Bob snapshot | Alice pending | Bob pending |
|-------|-------------------|----------------|-------------|---------------|------------|
| Bob stakes 200 | 10,000,000,000 | 0 | 10,000,000,000 | 1,000 | 0 |

Alice's pending reward: $100 \times (10{,}000{,}000{,}000 - 0) / 10^9 = 1{,}000$ tokens. This is correct: she was the sole staker for 100 seconds at 10 tokens/second.

Bob's snapshot is set to the current accumulator value. His pending reward is zero --- he just arrived.

`total_staked = 300`.

**Time 200: Both claim**

Update the accumulator:

$$increment = \frac{10 \times 100 \times 10^9}{300} = 3{,}333{,}333{,}333$$

$$\text{reward\_per\_token} = 10{,}000{,}000{,}000 + 3{,}333{,}333{,}333 = 13{,}333{,}333{,}333$$

| Event | `reward_per_token` | Alice snapshot | Bob snapshot | Alice pending | Bob pending |
|-------|-------------------|----------------|-------------|---------------|------------|
| Claims at t=200 | 13,333,333,333 | 0 | 10,000,000,000 | 1,333 | 666 |

Alice: $100 \times (13{,}333{,}333{,}333 - 0) / 10^9 = 1{,}333$ tokens.
Bob: $200 \times (13{,}333{,}333{,}333 - 10{,}000{,}000{,}000) / 10^9 = 666$ tokens.

Total distributed: $1{,}333 + 666 = 1{,}999$ tokens. Total available: $10 \times 200 = 2{,}000$ tokens. The 1-token difference is rounding dust from integer division --- always in the contract's favor.

> **Warning:** The total rewards distributed must never exceed `reward_rate * elapsed_time`. Rounding in `op.divmodw` floors toward zero, ensuring the contract always retains dust. If you ever observe total distributions exceeding the reward pool, you have a bug. This is the single most important property to verify in your tests.

**Self-check:** If Charlie stakes 300 LP at time 200 and everyone claims at time 300, how much does each person receive for the t=200 to t=300 interval? (Answer: Alice gets 166, Bob gets 333, Charlie gets 500 --- proportional to their 100:200:300 stakes out of the new total of 600.)

### Overflow Analysis

With `PRECISION = 10^9`, the `reward_per_token_stored` value grows by `(reward_rate * delta_t * 10^9) / total_staked` per update. In the worst case --- a reward rate of $10^6$ tokens/second, a delta of 86,400 seconds (one day), and a total staked of 1 (a single user with 1 LP token) --- the increment is:

$$\frac{10^6 \times 86{,}400 \times 10^9}{1} = 8.64 \times 10^{19}$$

This exceeds `UInt64`'s maximum of $\approx 1.84 \times 10^{19}$. However, the numerator before division is computed in 128-bit via `mulw`, and the division via `divmodw` produces a 64-bit quotient. The quotient itself overflows only if `total_staked = 1` and the numerator is enormous --- which means a single user with 1 LP token is staked while $10^6$ reward tokens per second are distributed. In practice, total staked values are orders of magnitude larger, keeping the increment well within 64-bit range.

If your reward parameters are extreme, add a check: `assert increment < UInt64(2**63)` after the `divmodw`. This panic-on-overflow approach is safer than silently wrapping, which would corrupt the accumulator and allow some stakers to claim more than their share.

*Recall the wide arithmetic pattern from the AMM's swap calculation in the previous chapter. What was the purpose of `mulw` and `divmodw` there? The same pattern --- 128-bit intermediate product divided back to 64 bits --- reappears throughout this chapter.*


## Duration Multipliers

A flat reward rate treats a 30-day lock the same as a 365-day lock. To incentivize longer commitments, we assign a *multiplier* that scales the user's effective stake. The actual LP tokens deposited do not change --- the multiplier inflates the user's weight in the reward calculation.

We use a linear scale from 1x (30 days) to 4x (365 days):

$$\text{multiplier} = \text{SCALE} + \frac{(\text{duration} - \text{MIN\_LOCK}) \times 3 \times \text{SCALE}}{\text{MAX\_LOCK} - \text{MIN\_LOCK}}$$

Where `SCALE = 1000` (giving us 0.1% precision), `MIN_LOCK = 30 days`, and `MAX_LOCK = 365 days`. A 30-day lock gets multiplier 1000 (1.0x). A 365-day lock gets 4000 (4.0x). A 197-day lock (halfway) gets 2500 (2.5x).

The user's *effective balance* --- the value used in the accumulator --- is:

$$\text{effective} = \frac{\text{lp\_amount} \times \text{multiplier}}{\text{SCALE}}$$

**Worked example.** Alice locks 100 LP for 365 days (multiplier = 4000). Bob locks 200 LP for 30 days (multiplier = 1000).

- Alice's effective balance: $100 \times 4000 / 1000 = 400$
- Bob's effective balance: $200 \times 1000 / 1000 = 200$
- Total effective: 600
- Alice's share: $400 / 600 = 66.7\%$
- Bob's share: $200 / 600 = 33.3\%$

Despite depositing half as many LP tokens, Alice earns twice Bob's reward rate because her 4x multiplier more than compensates. This is the intended incentive: long-term LPs earn disproportionately more.

The `total_staked` global variable (renamed to `total_effective` in the production contract) now tracks the sum of effective balances, not raw LP amounts. When Alice stakes, we add 400. When she unstakes, we subtract 400. The accumulator formula is unchanged --- it already uses the total in the denominator. This is the beauty of the accumulator pattern: adding multipliers requires zero changes to the core distribution math. You only change how each user's weight is calculated.

> **Note:** Why not use a quadratic or exponential multiplier instead of linear? The choice affects game theory. A linear multiplier means the marginal benefit of each additional lock day is constant. An exponential multiplier would disproportionately reward the longest locks, potentially concentrating rewards among a few whales who can afford to lock for a year. A square-root multiplier (explored in Exercise 3) has diminishing returns --- the first extra month of locking is worth more than the last. Linear is the simplest to reason about and audit, which matters for a contract holding user funds.

```python
SCALE = 1000
MIN_LOCK = 30 * SECONDS_PER_DAY
MAX_LOCK = 365 * SECONDS_PER_DAY


@subroutine
def calculate_multiplier(duration: UInt64) -> UInt64:
    """Linear multiplier: 1x at 30 days, 4x at 365 days."""
    assert duration >= UInt64(MIN_LOCK), "Below minimum lock"
    assert duration <= UInt64(MAX_LOCK), "Exceeds maximum lock"
    lock_range = UInt64(MAX_LOCK - MIN_LOCK)
    excess = duration - UInt64(MIN_LOCK)
    # multiplier = 1000 + excess * 3000 / range
    high, low = op.mulw(excess, UInt64(3 * SCALE))
    q_hi, bonus, r_hi, r_lo = op.divmodw(
        high, low, UInt64(0), lock_range
    )
    return UInt64(SCALE) + bonus
```

Note the wide arithmetic: `excess * 3000` can approach $335 \times 86400 \times 3000 \approx 8.7 \times 10^{10}$, which fits in `UInt64`. The `mulw` is defensive --- it would only matter if someone passed durations in smaller units. Defensive arithmetic costs a few extra opcodes and prevents entire classes of bugs.


## Smart Contract Composition

*The farming contract needs to verify that LP tokens are genuine. Using only what you know about Algorand so far, how would you accomplish this? Think about what data the AMM stores on-chain and how another contract might access it.*

Until now, every contract we have built has operated in isolation. The vesting contract managed its own tokens. The AMM managed its own pool. But the farming contract needs to verify that the LP tokens it receives actually come from our AMM pool --- not from some random token with the same ASA ID.

Algorand makes cross-contract reads straightforward. Any contract can read another contract's global state using `op.AppGlobal.get_ex_uint64` (for integer values) or `op.AppGlobal.get_ex_bytes` (for byte values). The target application must be included in the transaction's foreign apps array.

```python
# Read the AMM's lp_token_id to verify our LP token
lp_id, exists = op.AppGlobal.get_ex_uint64(
    amm_app, Bytes(b"lp_token_id")
)
assert exists, "AMM app has no lp_token_id"
assert lp_id == self.lp_token_id.value, "LP token mismatch"
```

The `get_ex_uint64` opcode returns a tuple of `(value, exists)`. Always check `exists` --- if the key does not exist in the target app's global state, `value` is zero, and silently using zero as a valid value is a common bug.

> **Warning:** The foreign apps array has a maximum of 8 entries per transaction (shared across the group since AVM v9). Each cross-contract read consumes one slot. If your transaction already references several apps, you may not have room for the AMM reference. Plan your foreign reference budget carefully when designing multi-contract interactions.

**Design tradeoff: read-on-init vs. read-on-every-call.** We could verify the LP token once during initialization and store the result, or verify it on every stake call. Reading once is cheaper (fewer opcodes per stake) but trusts that the stored value remains correct forever. Reading every time costs ~5 extra opcodes per call but guarantees correctness even if someone deploys a new farming contract pointing at a different AMM. For this contract, we read the AMM's state during initialization --- the LP token ID cannot change after the AMM is bootstrapped, so a one-time read is safe and saves opcode budget on every subsequent stake.

### How Foreign Apps Work at the Protocol Level

When you include an application in the foreign apps array, you are telling the AVM: "This transaction may need to read state from this application." The AVM loads the target app's global state into a read-only cache at the start of execution. The `get_ex_uint64` opcode then reads from this cache --- it does *not* make a live query to the blockchain during execution.

This has two implications. First, the read is cheap --- just a few opcodes to look up a key in the cached state. There is no network round-trip or additional I/O cost beyond the initial load. Second, the state you read is the state as of the beginning of your transaction's execution. If another transaction in the same atomic group modifies the target app's state before your transaction executes, you see the *pre-modification* state. This is usually what you want for verification purposes (you are checking that a value exists and matches), but it matters if you are trying to read state that was just written by a preceding group transaction.

Since AVM v9, foreign references are shared across all transactions in an atomic group. This means the AMM app only needs to appear in *one* transaction's foreign apps array, and all transactions in the group can read its state. In practice, include it in the transaction that actually performs the read for clarity.

**Common error.** If you forget to include the AMM app in the foreign apps array, the `get_ex_uint64` call will fail at runtime with an "unavailable App" error. The fix is client-side --- add the AMM app ID to the `app_references` parameter when building the transaction:

```python
app_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="initialize",
        args=[lp_token, reward_token, amm_app_id],
        app_references=[amm_app_id],
        static_fee=algokit_utils.AlgoAmount.from_micro_algo(
            4000
        ),
    )
)
```


## Project Setup and Full Contract

Now we build the production staking contract, incorporating the accumulator pattern, duration multipliers, and cross-contract verification. This replaces the simplified version entirely.

The contract file is `smart_contracts/lp_farming/contract.py`. Compile with:

```bash
algokit project run build
```

### State Design

The per-user stake data is stored in boxes keyed by the staker's address. Each position is an `arc4.Struct`:

```python
class StakePosition(arc4.Struct):
    effective_balance: arc4.UInt64   # LP * multiplier / SCALE
    lp_amount: arc4.UInt64          # Raw LP tokens deposited
    reward_per_token_paid: arc4.UInt64  # Snapshot at last interaction
    accrued_rewards: arc4.UInt64    # Unclaimed rewards
    unlock_time: arc4.UInt64        # Timestamp when unstake allowed
```

Five `arc4.UInt64` fields = 40 bytes. Box key: `b"s_"` prefix (2 bytes) + 32-byte address = 34 bytes. Box MBR: $2{,}500 + 400 \times (34 + 40) = 32{,}100$ microAlgos per staker.

The global state schema uses 9 `UInt64` slots and 1 `Bytes` slot (the admin address). Since the default schema allows up to 64 of each, we have plenty of room.

> **Note:** `Global.latest_timestamp` is the timestamp of the block containing the current transaction, not the wall-clock time. It is accurate to within about 25 seconds and is set by the block proposer. For a staking contract with lock periods measured in days, this precision is more than adequate. Do not use timestamps for sub-minute precision requirements.

### Consolidated Imports and Constants

```python
from algopy import (
    ARC4Contract, Account, Application, Asset,
    Bytes, Global, GlobalState, Txn,
    UInt64, arc4, gtxn, itxn, op, subroutine,
    BoxMap,
)

PRECISION = 10**9
SCALE = 1000
SECONDS_PER_DAY = 86400
MIN_LOCK = 30 * SECONDS_PER_DAY
MAX_LOCK = 365 * SECONDS_PER_DAY
```


## Initialization and Reward Deposit

The contract class declaration and initialization method. The `initialize` method performs the cross-contract read to verify the LP token, then opts into both tokens.

```python
class StakePosition(arc4.Struct):
    effective_balance: arc4.UInt64
    lp_amount: arc4.UInt64
    reward_per_token_paid: arc4.UInt64
    accrued_rewards: arc4.UInt64
    unlock_time: arc4.UInt64


class LPFarm(ARC4Contract):
    def __init__(self) -> None:
        self.admin = GlobalState(Bytes())
        self.lp_token_id = GlobalState(UInt64(0))
        self.reward_token_id = GlobalState(UInt64(0))
        self.amm_app_id = GlobalState(UInt64(0))
        self.total_effective = GlobalState(UInt64(0))
        self.reward_rate = GlobalState(UInt64(0))
        self.reward_end_time = GlobalState(UInt64(0))
        self.last_update_time = GlobalState(UInt64(0))
        self.reward_per_token_stored = GlobalState(UInt64(0))
        self.is_initialized = GlobalState(UInt64(0))
        self.stakes = BoxMap(
            arc4.Address, StakePosition, key_prefix=b"s_"
        )

    @arc4.abimethod(create="require")
    def create(self) -> None:
        self.admin.value = Txn.sender.bytes

    @arc4.baremethod(
        allow_actions=[
            "UpdateApplication",
            "DeleteApplication",
        ]
    )
    def reject_lifecycle(self) -> None:
        assert False, "Contract is immutable"

    @arc4.abimethod
    def initialize(
        self,
        lp_token: Asset,
        reward_token: Asset,
        amm_app: Application,
    ) -> None:
        assert Txn.sender == Account(self.admin.value)
        assert self.is_initialized.value == UInt64(0)

        # Cross-contract read: verify LP token belongs to AMM
        lp_id, exists = op.AppGlobal.get_ex_uint64(
            amm_app, Bytes(b"lp_token_id")
        )
        assert exists, "AMM has no lp_token_id"
        assert lp_id == lp_token.id, "LP token mismatch"

        self.lp_token_id.value = lp_token.id
        self.reward_token_id.value = reward_token.id
        self.amm_app_id.value = amm_app.id

        # Opt into both tokens
        itxn.AssetTransfer(
            xfer_asset=lp_token,
            asset_receiver=(
                Global.current_application_address
            ),
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()
        itxn.AssetTransfer(
            xfer_asset=reward_token,
            asset_receiver=(
                Global.current_application_address
            ),
            asset_amount=UInt64(0),
            fee=UInt64(0),
        ).submit()

        self.is_initialized.value = UInt64(1)
```

The `initialize` method reads `lp_token_id` from the AMM's global state. If the AMM has not been bootstrapped (the key does not exist), the assertion fails. If someone passes a different AMM app that happens to have a `lp_token_id` key with a different value, the token mismatch check catches it. This two-layer verification ensures the farming contract is bound to a specific, legitimate AMM pool.

The `deposit_rewards` method funds the reward pool and sets the distribution rate:

```python
    @arc4.abimethod
    def deposit_rewards(
        self,
        reward_txn: gtxn.AssetTransferTransaction,
        duration_seconds: UInt64,
    ) -> None:
        assert Txn.sender == Account(self.admin.value)
        assert reward_txn.xfer_asset == Asset(
            self.reward_token_id.value
        )
        assert reward_txn.asset_receiver == (
            Global.current_application_address
        )
        assert duration_seconds > UInt64(0)

        # Settle any accrued rewards before changing rate
        self._update_reward()

        amount = reward_txn.asset_amount
        assert amount > UInt64(0), "Zero reward deposit"

        self.reward_rate.value = amount // duration_seconds
        self.last_update_time.value = (
            Global.latest_timestamp
        )
        self.reward_end_time.value = (
            Global.latest_timestamp + duration_seconds
        )
```

The reward rate is tokens per second. Integer division means some dust is lost --- depositing 1,000,000 tokens over 86,401 seconds yields a rate of 11 tokens/second, distributing $11 \times 86{,}401 = 950{,}411$ tokens total. The remaining 49,589 tokens stay in the contract. This is standard behavior; production systems often add a "sweep" function for the admin to recover undistributed dust after the reward period ends.

> **Warning:** The `deposit_rewards` method replaces an existing reward period rather than extending it. The `_update_reward()` call at the top settles accrued rewards at the old rate before the new rate takes effect --- without it, stakers would lose rewards earned under the previous period. However, any undistributed tokens from the old period (between `last_update_time` and the old `reward_end_time`) are effectively abandoned. A production contract should either prevent overlapping deposits or calculate a new rate that accounts for both the remaining and newly deposited rewards. For simplicity, our contract assumes a single reward period.


## Staking LP Tokens

The `stake` method is the heart of the contract. It updates the global accumulator, calculates the user's multiplier, creates or updates their position box, and records their accumulator snapshot.

```python
    @arc4.abimethod
    def stake(
        self,
        lp_txn: gtxn.AssetTransferTransaction,
        lock_days: UInt64,
    ) -> None:
        assert self.is_initialized.value == UInt64(1)
        assert lp_txn.xfer_asset == Asset(
            self.lp_token_id.value
        )
        assert lp_txn.asset_receiver == (
            Global.current_application_address
        )
        assert lp_txn.sender == Txn.sender
        assert lp_txn.asset_amount > UInt64(0)

        # 1. Update the global accumulator
        self._update_reward()

        # 2. Calculate lock duration and multiplier
        duration = lock_days * UInt64(SECONDS_PER_DAY)
        multiplier = _calculate_multiplier(duration)
        lp_amount = lp_txn.asset_amount
        high, low = op.mulw(lp_amount, multiplier)
        q_hi, effective, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), UInt64(SCALE)
        )

        # 3. Store the stake position
        key = arc4.Address(Txn.sender)
        assert key not in self.stakes, "Already staked"
        self.stakes[key] = StakePosition(
            effective_balance=arc4.UInt64(effective),
            lp_amount=arc4.UInt64(lp_amount),
            reward_per_token_paid=arc4.UInt64(
                self.reward_per_token_stored.value
            ),
            accrued_rewards=arc4.UInt64(0),
            unlock_time=arc4.UInt64(
                Global.latest_timestamp + duration
            ),
        )

        # 4. Update total effective stake
        self.total_effective.value += effective
```

The assertion `key not in self.stakes` prevents double-staking. A user who wants to add more LP must first unstake (after their lock expires) and re-stake with a new duration. This simplification keeps the position struct fixed-size and avoids the complexity of merging positions with different multipliers and unlock times. Production contracts sometimes support multiple positions per user via a position ID (using a `BoxMap(arc4.UInt64, StakePosition)` keyed by a sequential counter), but that adds significant complexity --- each position needs independent accumulator snapshots, and claiming requires iterating over all positions.

An alternative design is to allow "topping up" an existing stake by adding more LP tokens at the same multiplier and unlock time. This requires settling accrued rewards first (to avoid retroactively applying the new balance to past periods), then adding the new effective balance to both the position and the global total. The code changes are modest, but the UX complexity of explaining when top-ups are allowed (same lock duration only? extend the lock?) and the additional test surface area make it a poor tradeoff for a first implementation.

### The `_update_reward` Subroutine

This is the accumulator update, called at the top of every state-changing method:

```python
    @subroutine
    def _update_reward(self) -> None:
        if self.total_effective.value == UInt64(0):
            self.last_update_time.value = (
                Global.latest_timestamp
            )
            return

        now = Global.latest_timestamp
        end = self.reward_end_time.value
        effective_now = now if now < end else end
        last = self.last_update_time.value
        if effective_now <= last:
            return

        delta_t = effective_now - last
        rate = self.reward_rate.value
        total = self.total_effective.value

        # rate * delta_t fits in UInt64 for any realistic
        # parameters (max ~10^6 * 31536000 = 3.15e13)
        rate_time = rate * delta_t
        # Multiply by PRECISION via mulw (128-bit result),
        # then divide by total via divmodw
        high, low = op.mulw(
            rate_time, UInt64(PRECISION)
        )
        q_hi, increment, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), total
        )
        assert q_hi == UInt64(0), "Accumulator overflow"

        self.reward_per_token_stored.value += increment
        self.last_update_time.value = effective_now
```

The two-stage wide arithmetic is straightforward. First, `rate * delta_t` is computed as a plain `UInt64` product. For any realistic parameters --- a reward rate up to $10^6$ tokens/second and a maximum delta of one year (31,536,000 seconds) --- this product is at most $3.15 \times 10^{13}$, well within `UInt64` range. The `mulw` then multiplies this intermediate result by `PRECISION` ($10^9$) to produce a 128-bit value, and `divmodw` divides by `total` to yield the 64-bit increment. If your reward parameters are extreme enough that `rate * delta_t` itself could exceed $2^{64}$, you would need an additional `mulw` stage or `BigUInt` arithmetic --- but this would require a reward rate exceeding $5 \times 10^{14}$ tokens/second, far beyond any realistic deployment.

### The `_calculate_multiplier` Subroutine

Extracted as a module-level subroutine so it can be called from both `stake` and `extend_lock`:

```python
@subroutine
def _calculate_multiplier(duration: UInt64) -> UInt64:
    """1x at 30 days, 4x at 365 days, linear."""
    assert duration >= UInt64(MIN_LOCK), "Below minimum lock"
    assert duration <= UInt64(MAX_LOCK), "Above maximum lock"
    lock_range = UInt64(MAX_LOCK - MIN_LOCK)
    excess = duration - UInt64(MIN_LOCK)
    high, low = op.mulw(excess, UInt64(3 * SCALE))
    q_hi, bonus, r_hi, r_lo = op.divmodw(
        high, low, UInt64(0), lock_range
    )
    return UInt64(SCALE) + bonus
```

### Deployment Script

This script deploys the farming contract alongside the AMM from the previous chapter. Save it as `deploy_farm.py` in your project root:

```python
import os
from pathlib import Path
import algokit_utils

algorand = algokit_utils.AlgorandClient.default_localnet()
admin = algorand.account.localnet_dispenser()

# --- Step 1: Create test tokens ---
def create_asa(name, unit):
    result = algorand.send.asset_create(
        algokit_utils.AssetCreateParams(
            sender=admin.address,
            total=10**13, decimals=6,
            asset_name=name, unit_name=unit,
            note=os.urandom(8),
        )
    )
    return result.asset_id

token_a = create_asa("TokenA", "TKA")
token_b = create_asa("TokenB", "TKB")
reward_token = create_asa("RewardToken", "RWD")
if token_a > token_b:
    token_a, token_b = token_b, token_a
print(f"Token A: {token_a}, Token B: {token_b}")
print(f"Reward Token: {reward_token}")

# --- Step 2: Deploy and bootstrap AMM ---
amm_spec = Path(
    "smart_contracts/artifacts/"
    "constant_product_pool/"
    "ConstantProductPool.arc56.json"
).read_text()
amm_factory = algorand.client.get_app_factory(
    app_spec=amm_spec,
    default_sender=admin.address,
)
amm_client, _ = amm_factory.send.bare.create()
print(f"AMM App ID: {amm_client.app_id}")

# Bootstrap: the seed payment is the first ABI argument.
# The SDK places it as the preceding transaction in the
# group automatically.
result = amm_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="bootstrap",
        args=[
            algokit_utils.PaymentParams(
                sender=admin.address,
                receiver=amm_client.app_address,
                amount=(
                    algokit_utils.AlgoAmount.from_micro_algo(
                        500_000
                    )
                ),
            ),
            token_a,
            token_b,
        ],
        static_fee=(
            algokit_utils.AlgoAmount.from_micro_algo(
                5000
            )
        ),
    )
)
lp_token_id = result.abi_return
print(f"LP Token ID: {lp_token_id}")

# --- Step 3: Deploy the farming contract ---
farm_spec = Path(
    "smart_contracts/artifacts/"
    "lp_farming/LPFarm.arc56.json"
).read_text()
farm_factory = algorand.client.get_app_factory(
    app_spec=farm_spec,
    default_sender=admin.address,
)
farm_client, _ = farm_factory.send.create(
    algokit_utils.AppFactoryCreateMethodCallParams(
        method="create",
    )
)
print(f"Farm App ID: {farm_client.app_id}")

# Fund the farm contract
algorand.send.payment(
    algokit_utils.PaymentParams(
        sender=admin.address,
        receiver=farm_client.app_address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(
            400_000
        ),
        note=os.urandom(8),
    )
)

# Initialize with cross-contract verification
farm_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="initialize",
        args=[
            lp_token_id, reward_token,
            amm_client.app_id,
        ],
        app_references=[amm_client.app_id],
        asset_references=[lp_token_id, reward_token],
        static_fee=(
            algokit_utils.AlgoAmount.from_micro_algo(4000)
        ),
    )
)
print("Farm initialized!")
```

Compile and run:

```bash
algokit project run build
python deploy_farm.py
```

You should see the AMM and farm app IDs, the LP token ID, and "Farm initialized!" confirming that the cross-contract LP token verification succeeded.


## Claiming and Extending Locks

### Claiming Rewards

The `claim` method settles the user's accrued rewards and sends them as an inner transaction:

```python
    @arc4.abimethod
    def claim(self) -> UInt64:
        self._update_reward()

        key = arc4.Address(Txn.sender)
        pos = self.stakes[key].copy()
        effective = pos.effective_balance.native
        assert effective > UInt64(0), "No stake"

        # Calculate pending rewards
        current_rpt = self.reward_per_token_stored.value
        paid_rpt = pos.reward_per_token_paid.native
        diff = current_rpt - paid_rpt

        high, low = op.mulw(effective, diff)
        q_hi, new_rewards, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), UInt64(PRECISION)
        )
        total_pending: UInt64 = (
            pos.accrued_rewards.native + new_rewards
        )

        assert total_pending > UInt64(0), "Nothing to claim"

        # Update position: snapshot current accumulator,
        # zero out accrued
        pos.reward_per_token_paid = arc4.UInt64(current_rpt)
        pos.accrued_rewards = arc4.UInt64(0)
        self.stakes[key] = pos.copy()

        # Send rewards
        itxn.AssetTransfer(
            xfer_asset=Asset(self.reward_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=total_pending,
            fee=UInt64(0),
        ).submit()

        return total_pending
```

The `accrued_rewards` field captures rewards that were calculated during a previous interaction (like `_update_reward` during another user's stake) but not yet claimed. This ensures no rewards are lost between interactions.

### Extending a Lock

Imagine Alice staked for 30 days at a 1x multiplier. Two weeks in, she decides she is comfortable locking for the full year. Rather than waiting for her lock to expire, unstaking, and re-staking at a higher multiplier --- losing her position in the accumulator and paying box MBR twice --- she can extend her lock in place, upgrading her multiplier immediately.

This is more complex than it appears --- the effective balance changes, which affects the global total and the accumulator. The update must be performed in a precise order to avoid over- or under-counting rewards.

```python
    @arc4.abimethod
    def extend_lock(
        self, new_lock_days: UInt64
    ) -> None:
        # Step 1: Update global accumulator
        self._update_reward()

        key = arc4.Address(Txn.sender)
        pos = self.stakes[key].copy()
        old_effective = pos.effective_balance.native
        lp_amount = pos.lp_amount.native
        assert old_effective > UInt64(0), "No stake"

        # Step 2: Settle accrued rewards
        current_rpt = self.reward_per_token_stored.value
        paid_rpt = pos.reward_per_token_paid.native
        diff = current_rpt - paid_rpt
        high, low = op.mulw(old_effective, diff)
        q_hi, new_rewards, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), UInt64(PRECISION)
        )
        accrued = pos.accrued_rewards.native + new_rewards

        # Step 3: Calculate new multiplier and effective
        new_duration = new_lock_days * UInt64(SECONDS_PER_DAY)
        new_unlock = (
            Global.latest_timestamp + new_duration
        )
        assert new_unlock > pos.unlock_time.native, (
            "New lock must extend beyond current"
        )
        new_multiplier = _calculate_multiplier(new_duration)
        h, l = op.mulw(lp_amount, new_multiplier)
        q_hi, new_effective, r_hi, r_lo = op.divmodw(
            h, l, UInt64(0), UInt64(SCALE)
        )

        # Step 4: Update global total effective
        self.total_effective.value -= old_effective
        self.total_effective.value += new_effective

        # Step 5: Snapshot accumulator at current value
        pos.reward_per_token_paid = arc4.UInt64(
            current_rpt
        )

        # Step 6: Store settled rewards
        pos.accrued_rewards = arc4.UInt64(accrued)

        # Step 7: Update effective balance and unlock time
        pos.effective_balance = arc4.UInt64(new_effective)
        pos.unlock_time = arc4.UInt64(new_unlock)

        # Step 8: Write back
        self.stakes[key] = pos.copy()
```

The 8-step sequence is critical. Steps 1--2 settle all rewards at the old effective balance. Steps 3--4 change the effective balance and global total. Step 5 resets the snapshot so future rewards accrue at the new effective rate. Steps 6--8 persist everything atomically. The critical ordering constraint is between steps 1 and 4: `_update_reward()` must execute before `total_effective` changes, because the accumulator update uses `total_effective` as its denominator. If you changed the total *before* updating the accumulator, the increment would be calculated against the wrong total, distributing too many or too few rewards for the period before the effective balance changed.

*Without looking at the code above, list the steps that `extend_lock` must perform and explain why the ordering matters. Then compare your list to the 8-step sequence. The ordering constraint is the same invariant from the accumulator section: update before mutate.*


## Unstaking

The `unstake` method verifies the lock has expired, settles final rewards, returns LP tokens, deletes the position box, and refunds the box MBR.

```python
    @arc4.abimethod
    def unstake(self) -> None:
        self._update_reward()

        key = arc4.Address(Txn.sender)
        pos = self.stakes[key].copy()
        effective = pos.effective_balance.native
        lp_amount = pos.lp_amount.native
        assert effective > UInt64(0), "No stake"
        assert Global.latest_timestamp >= (
            pos.unlock_time.native
        ), "Lock not expired"

        # Settle final rewards
        current_rpt = self.reward_per_token_stored.value
        paid_rpt = pos.reward_per_token_paid.native
        diff = current_rpt - paid_rpt
        high, low = op.mulw(effective, diff)
        q_hi, new_rewards, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), UInt64(PRECISION)
        )
        total_pending: UInt64 = (
            pos.accrued_rewards.native + new_rewards
        )

        # Update global state BEFORE inner transactions
        self.total_effective.value -= effective

        # Return LP tokens
        itxn.AssetTransfer(
            xfer_asset=Asset(self.lp_token_id.value),
            asset_receiver=Txn.sender,
            asset_amount=lp_amount,
            fee=UInt64(0),
        ).submit()

        # Send final rewards (if any)
        if total_pending > UInt64(0):
            itxn.AssetTransfer(
                xfer_asset=Asset(
                    self.reward_token_id.value
                ),
                asset_receiver=Txn.sender,
                asset_amount=total_pending,
                fee=UInt64(0),
            ).submit()

        # Delete the position box --- refunds MBR
        del self.stakes[key]

        # Refund box MBR to the user
        itxn.Payment(
            receiver=Txn.sender,
            amount=UInt64(32_100),
            fee=UInt64(0),
        ).submit()
```

The MBR refund is 32,100 microAlgos --- the exact cost of the position box. When the box is deleted, the contract's MBR requirement drops by that amount, freeing the Algo for the refund payment. The contract must have been funded with enough Algo to cover all active boxes' MBR plus a buffer for inner transaction fees. This is the same MBR lifecycle pattern from the vesting contract: fund on creation, refund on cleanup.

> **Warning:** The `del self.stakes[key]` call and the MBR refund payment happen *after* the state update (`total_effective -= effective`). If the box deletion or payment fails (e.g., insufficient contract balance), the entire transaction rolls back atomically --- the state update is reverted too. This is safe on Algorand because of atomic rollback semantics, but it means you must ensure the contract always has enough Algo to cover the refund.

Notice that the accumulator update (`_update_reward()`) happens before computing the user's pending reward and before modifying the user's stake. This ordering is mathematically necessary --- the global `reward_per_token` must reflect the current state of the world before individual positions are calculated against it. This is an algorithmic correctness requirement, not a reentrancy guard (reentrancy is impossible on Algorand --- inner transactions do not trigger callbacks).

The `unstake` method requires a client-side fee that covers the outer transaction plus up to 3 inner transactions (LP return, reward send, MBR refund):

```python
farm_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="unstake",
        args=[],
        static_fee=(
            algokit_utils.AlgoAmount.from_micro_algo(5000)
        ),
    )
)
```


## Consuming the AMM's TWAP Oracle

The AMM from the previous chapter tracks cumulative price accumulators and exposes a `get_twap_price` read-only method. The farming contract does not need to maintain its own oracle --- it can consume the AMM's TWAP for position valuation.

A natural extension of the farming contract is displaying the dollar value of a staked position. A frontend would:

1. **Snapshot**: Read the AMM's raw global state --- `cumulative_price_a` and `twap_last_update` --- via the algod REST API (`GET /v2/applications/{app-id}`). Store both values along with the current wall-clock time. This is a free API read, not a contract call.
2. **Query**: After the desired TWAP window has elapsed (e.g., 1 hour), call `get_twap_price` via `simulate`, passing the stored cumulative price and timestamp as arguments. The method computes the time-weighted average over the window and returns it as a `UInt64`.
3. **Value**: Multiply the TWAP price by the user's staked LP amount to estimate the position's dollar value.

Because `get_twap_price` performs inline accumulation before computing the difference, the returned TWAP is current even if no swap, mint, or burn has occurred since the snapshot. This is a key advantage of placing the oracle in the AMM rather than in each consumer: one well-trafficked pool feeds price data to any number of downstream contracts.

If a farming contract needed to make on-chain decisions based on price (e.g., dynamic reward rates or position liquidation), it could read the AMM's cumulative price state directly via `op.AppGlobal.get_ex_bytes` (since `BigUInt` values are stored as byte slices). It would store its own periodic snapshots and compute the TWAP over its desired window. For our farming contract, position valuation is purely a frontend concern, so no additional on-chain code is needed.


## Testing

Test outlines for the farming contract. These follow the same structural pattern as the AMM tests from the previous chapter --- `deploy_pool` and similar helpers wrap the AlgoKit Utils calls shown in the deployment scripts.

Save the following in `tests/test_farm.py`:

```python
import pytest
from algokit_utils import AlgorandClient


class TestLPFarm:
    """Farming contract test suite."""

    def test_lifecycle_stake_claim_unstake(
        self, algorand
    ):
        """Deploy AMM + Farm, stake LP, claim, unstake."""
        # Deploy AMM, bootstrap, add liquidity
        # Deploy farm, initialize with AMM reference
        # Deposit rewards (1M tokens over 30 days)
        # User stakes LP for 30 days
        # Advance time (LocalNet: submit dummy txns)
        # Claim --- verify reward > 0
        # Advance past lock expiry
        # Unstake --- verify LP returned, box deleted

    def test_accumulator_two_stakers(self, algorand):
        """Alice stakes alone, Bob joins, verify shares."""
        # Alice stakes 100 LP at t=0
        # Advance 100 seconds
        # Bob stakes 200 LP at t=100
        # Advance 100 seconds
        # Alice claims --- should get ~1333 rewards
        # Bob claims --- should get ~666 rewards
        # Total <= reward_rate * elapsed

    def test_multiplier_scaling(self, algorand):
        """30-day lock gets 1x, 365-day gets 4x."""
        # Alice: 100 LP, 365 days (4x effective)
        # Bob: 100 LP, 30 days (1x effective)
        # After equal time, Alice's reward ~ 4x Bob's

    def test_composition_rejects_wrong_amm(
        self, algorand
    ):
        """Initialize fails if LP token doesn't match."""
        # Deploy a second AMM with different tokens
        # Attempt initialize with wrong AMM app
        # Expect failure: "LP token mismatch"

    def test_lock_enforcement(self, algorand):
        """Unstake before lock expires should fail."""
        # Stake for 30 days
        # Immediately attempt unstake
        # Expect failure: "Lock not expired"

    def test_rewards_cap_at_pool(self, algorand):
        """Total distributed never exceeds deposited."""
        # Deposit 1000 reward tokens
        # Stake, advance past reward_end_time
        # Claim --- verify total claimed <= 1000
        # No further rewards accrue after end time

    def test_extend_lock_increases_share(
        self, algorand
    ):
        """Extending lock increases multiplier."""
        # Stake 100 LP for 30 days (1x)
        # Extend to 365 days (4x)
        # Verify effective balance quadrupled
        # Verify rewards accrue at new rate

    def test_double_stake_rejected(self, algorand):
        """Cannot stake twice from same account."""
        # Stake once
        # Attempt second stake
        # Expect failure: "Already staked"
```

### Testing Time-Dependent Logic on LocalNet

LocalNet does not advance timestamps between blocks unless real time passes or you explicitly submit transactions that cause new blocks to be produced. To test time-dependent logic, you have two options: (1) insert `time.sleep(N)` between operations and submit a dummy transaction to produce a block with an updated timestamp, or (2) use the `dev-mode` time offset feature if your LocalNet supports it. Option 1 is simpler but makes tests slow.

For the accumulator test (`test_accumulator_two_stakers`), a 200-second sleep is impractical. The workaround is to use a very high reward rate --- say, $10^6$ reward tokens per second --- with short sleeps (2--3 seconds). This way, even a 2-second gap produces 2 million reward tokens of meaningful accumulation, and you can verify the proportional split within a reasonable test runtime.

```python
# Practical test timing pattern
import time

# Deposit 10^12 rewards over 100 seconds
# -> reward_rate = 10^10 tokens/second
farm_client.send.call(
    algokit_utils.AppClientMethodCallParams(
        method="deposit_rewards",
        args=[reward_transfer, 100],
        # ...
    )
)

# Alice stakes
farm_client.send.call(...)
time.sleep(3)  # Wait 3 real seconds

# Submit a dummy payment to advance the block timestamp
algorand.send.payment(
    algokit_utils.PaymentParams(
        sender=admin.address,
        receiver=admin.address,
        amount=algokit_utils.AlgoAmount.from_micro_algo(0),
        note=os.urandom(8),
    )
)

# Bob stakes --- the block timestamp is now ~3s later
# Alice earned ~3 * 10^10 tokens as sole staker
```

The `note=os.urandom(8)` on dummy payments is essential --- LocalNet deduplicates identical transactions, so the random note ensures each one is unique.

### What to Verify

The most important property to test is the **reward conservation invariant**: the total rewards claimed by all users must never exceed the total rewards deposited. After every claim in your test, track the running total of claimed rewards and assert it is less than or equal to the deposited amount. If this invariant ever fails, you have a critical bug in the accumulator math.

Second, verify **proportional fairness**: if Alice has 2x the effective balance of Bob and both stake for the same duration, Alice should receive approximately 2x the rewards. The "approximately" accounts for integer rounding --- the difference should be at most a few tokens, not a percentage.

Third, test **edge cases**: staking when the reward period has already ended (no new rewards should accrue), claiming when accrued rewards are zero (should revert), extending a lock to a shorter duration than the current lock (should revert), and unstaking immediately after the lock expires (should succeed and return the correct LP amount).


## Summary

In this chapter you learned to:

- Identify why naive per-user reward tracking fails at scale and implement the Synthetix-style reward-per-token accumulator pattern
- Use `op.mulw` and `op.divmodw` for two-stage wide arithmetic that prevents overflow in reward calculations
- Design duration-based multipliers that incentivize long-term liquidity commitment
- Read another contract's global state via `op.AppGlobal.get_ex_uint64` for cross-contract verification
- Consume the AMM's TWAP oracle for manipulation-resistant position valuation
- Manage the full staking lifecycle: stake, claim, extend, unstake with MBR refund

This chapter extended the AMM from the previous chapter into a two-contract system --- the first example of smart contract composition in this book. The farming contract does not modify the AMM; it reads its state and accepts its LP tokens. This *composability* --- contracts interacting through shared state and token standards without needing to trust each other --- is what makes DeFi protocols interoperable. Any contract that holds LP tokens can integrate with the farm. Any contract that needs a price feed can read the AMM's TWAP oracle. A lending protocol could accept staked LP positions as collateral by reading the farming contract's box state. Each contract is a building block, and the system's value comes from the combinations.

The accumulator pattern you learned here appears in virtually every DeFi staking system: Synthetix's StakingRewards, Curve's gauge system, Sushiswap's MasterChef, and their Algorand equivalents. The specific numbers change (precision factors, multiplier curves, reward schedules), but the core insight --- track a global per-unit accumulator and diff it against per-user snapshots --- is universal.

| Feature | New Concepts |
|---------|-------------|
| Reward distribution | Accumulator pattern, reward_per_token, snapshot-and-diff |
| Wide arithmetic | Two-stage mulw/divmodw for overflow-safe accumulator updates |
| Duration multipliers | Linear scaling, effective balance, SCALE factor |
| Composition | Cross-contract state reads, foreign apps array, get_ex_uint64 |
| Position management | Box lifecycle, MBR refund on cleanup, double-stake prevention |

In the next chapter, we cover common patterns and idioms that apply across all Algorand DeFi contracts --- fee subsidization strategies, MBR lifecycle management, canonical ordering, opcode budget management, and event emission for off-chain indexing.


## Exercises

1. **(Recall)** In the reward accumulator pattern, what happens if you update `total_effective` *before* settling a user's accrued rewards during an `extend_lock` call? Trace through the math with concrete numbers to show the error.

2. **(Apply)** Add an `emergency_withdraw` method that lets users retrieve their LP tokens before the lock expires, but forfeits all unclaimed rewards. The forfeited rewards should remain in the contract for distribution to other stakers. What state updates are needed, and in what order?

3. **(Analyze)** The linear multiplier gives 1x at 30 days and 4x at 365 days. Consider an alternative: a square-root multiplier where $\text{multiplier} = \sqrt{\text{duration} / \text{MIN\_LOCK}} \times \text{SCALE}$. A 30-day lock gets 1x, a 120-day lock gets 2x, a 365-day lock gets ~3.49x. What are the game-theoretic implications? Does this favor short-term or long-term stakers compared to linear?

4. **(Create)** Add an on-chain randomness bonus using `op.Block.blk_seed`. Every time a user claims, the contract reads the block seed from 2 rounds ago and hashes it with the user's address. If the resulting hash (mod 100) is less than 5, the user receives a 10% bonus on their claim. Implement the method and explain why reading the seed from 2 rounds ago (rather than the current round) prevents the user from choosing when to submit their claim based on a known seed.


## Further Reading

- [Synthetix StakingRewards](https://github.com/Synthetixio/synthetix/blob/develop/contracts/StakingRewards.sol) --- the original Solidity implementation of the reward accumulator pattern
- [Curve Finance](https://curve.fi/whitepaper) --- multi-token gauge reward systems with vote-escrow multipliers
- [Algorand Python Storage](https://dev.algorand.co/algokit/languages/python/lg-storage/) --- BoxMap, GlobalState, and BigUInt storage patterns
- [Algorand Python Operations](https://dev.algorand.co/algokit/languages/python/lg-ops/) --- mulw, divmodw, and wide arithmetic reference
- [Cross-App State Reading](https://dev.algorand.co/concepts/smart-contracts/opcodes-overview/) --- get_ex_uint64 and foreign app references


## Before You Continue

Before starting the next chapter, you should be able to:

- [ ] Explain why the naive per-user reward formula fails with concurrent stakers
- [ ] Implement the reward-per-token accumulator with correct wide arithmetic
- [ ] Calculate a user's pending rewards given their snapshot and the current accumulator value
- [ ] Read another contract's global state and handle the case where the key does not exist
- [ ] Explain how the farming contract consumes the AMM's TWAP oracle for position valuation
- [ ] Manage box lifecycle with creation, updates, deletion, and MBR refund

If any of these are unclear, revisit the relevant section before proceeding.
