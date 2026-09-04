\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Project}}
```
# Yield Farming: Extending the AMM with Staking Rewards

`\chaptermark{Yield Farming with Staking Rewards}`{=latex}


Your AMM works. Liquidity providers deposit tokens, traders swap against the pool, fees accumulate in the reserves, and LP tokens track each provider's share. But nothing stops an LP from providing liquidity for five minutes, collecting a fractional share of fees, and withdrawing. There is no incentive to commit capital for the long term, and no mechanism to reward the LPs who provide the stable, deep liquidity that makes a pool useful for traders.

This is the problem *yield farming* solves. In a yield farming system, LPs lock their LP tokens in a separate staking contract for a fixed duration (30 days, 90 days, a year) and earn additional reward tokens on top of the trading fees they already collect from the pool. Longer lock-ups earn proportionally higher rewards, creating a direct incentive for the sticky liquidity that healthy markets depend on.

You are going to build a staking contract that composes with the AMM from Chapter 14. Users deposit LP tokens from that pool, lock them for a chosen duration, and earn a reward token distributed continuously over time. The contract reads the configured AMM's global state, binds itself to that AMM's reported LP token, and demonstrates the reward-per-token accumulator pattern used by virtually every DeFi staking system.

One concept in this chapter is new: the *reward accumulator pattern*, a mathematical technique (popularized by Synthetix) that distributes rewards fairly across any number of stakers without iterating over them. The composition it rides on --- reading another contract's state to make a trust decision --- is Chapter 15's material, spent here rather than re-taught.

By the end of this chapter you will have a working staking contract, deployed on LocalNet alongside your AMM, with lock-up multipliers, continuous reward distribution, and cross-contract binding to the configured AMM's reported LP token.

This chapter assumes you have a working AMM from Chapter 14. Chapter 16 showed
how a factory can make pool identity stronger; this first farm keeps the
composition surface simple by binding to one configured AMM app and verifying
the LP token it reports. A production farm would add the Chapter 16
factory check before accepting a pool; Exercise 5 restores it. The farming
workflow and integration tests require the Chapter 14 generated client and an
initialized AMM app.

## Run It First

The finished project for this chapter is in `projects/lp-farming/`. It
depends on the finished AMM in `projects/constant-product-amm/`,
because the farm binds itself to the LP token that the configured AMM reports,
so both generated clients have to exist before the workflow will run. Before
running it, predict which line binds the farm to the AMM's LP token, which line
funds the stake box MBR, and why the workflow advances LocalNet time twice.

```bash
cd projects/constant-product-amm
algokit project bootstrap all
algokit project run build

cd ../lp-farming
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_lp_farming
algokit project run test
```

Table 17-1 lists the output checkpoints to compare against the
workflow output.

: Table 17-1. Output checkpoints for the LP farming workflow

| Output checkpoint | What to watch for |
|-------------------|-------------------|
| AMM app ID | The farm has a concrete application to read during initialization |
| LP token ID | The AMM reported the ASA that represents pool shares |
| Farm initialized | The staking contract opted into the required assets, using an `app_references` entry to read the AMM's global state |
| Stake box funded | Staking pays an exact 32,100 microAlgo box MBR alongside the LP-token transfer |
| Claimed rewards above zero | The accumulator produced claimable rewards once time advanced |
| Lock extended | The lock lengthens without unstaking the position |
| Final unstake message | The unstake path returned LP tokens and refunded the box MBR |

LocalNet defaults to developer mode, so the workflow moves past the long lock
period with the official timestamp-offset endpoint. That endpoint is one-way:
the workflow only ever moves the clock forward, and `algokit localnet reset`
is the way back to wall-clock time --- the Testing section explains why.
Without Docker or Podman the integration tests skip and the workflow script
stops with a LocalNet message; `algokit project run test-static` still reads
the farm contract's source and asserts that the security patterns this chapter
teaches are present --- no compiler and no network. (It reads `lp_farming`
only; the AMM has its own shape suite in Chapter 14's project.) The compile
step is `algokit project run build`, already in the runbook.

Follow this runbook first, then build the chapter in a separate scratch project
with the `algokit init` commands below. `projects/lp-farming/` is the
answer key: compare its contract, workflow script, and tests against your
scratch project whenever something differs.


## What You Need First

This project composes two contracts you have already built with one you have
not. Table 17-2 is what it draws on, and the rows from
Chapter 15 are the ones that decide whether it is safe.

Answer the predict column before you follow the link.

: Table 17-2. What Chapters 13 and 15 built that this project assumes

| Prerequisite | Where it lands here | Predict before you read it |
|--------------|---------------------|----------------------------|
| Example 15-8 | Reading the configured AMM's LP token id out of its global state | The farm learns which token to accept by reading the pool rather than by being told. Say what that buys over a constructor argument. |
| Example 15-10 | The provenance check this farm deliberately skips --- Exercise 5 restores it | The farm is handed a pool id it did not choose. Say what must be checked before its LP token is trusted. |
| Table 16-4 | The five-check verification Exercise 5's full answer calls into | A lookalike pool runs the same code as the canonical one. Say which of the five checks it can still pass, and which it cannot. |
| Example 15-4 and its gotcha | The shape this contract must not have | The farm binds to one AMM. Say what goes wrong if the AMM's id arrives as a method argument instead. |
| Example 13-11 | The reward-per-token accumulator | Both accumulate a rate over time. Say what the farm accumulates that the price oracle does not, and why the ordering rule is the same. |
| Example 13-6 | Every division in the reward calculation | A reward split is a division that decides what leaves the contract. Say which way it must lean, and who holds the dust. |
| Example 9-2 | Every read-modify-write of a stake-position box | The position struct has value semantics. Say what the compiler refuses when a record is read, changed, and written back without `.copy()`. |
| Example 7-4 | Every reward payout | A claim is one app call and one inner transfer. Write the pooled-fee arithmetic before you read it. |

## A Simplified Staking Contract

Before tackling the real accumulator math, build the simplest staking contract that works. This version has a fixed 30-day lock period, a single reward pool, and straightforward proportional math. It will serve a handful of stakers, and the problems it runs into are what motivate the accumulator pattern.

The contract accepts LP tokens (passed as an initialization parameter), locks them for 30 days, and distributes rewards proportionally based on each staker's share of the total staked LP tokens.

You are already in `projects/lp-farming/` from Run It First. If you would rather scaffold your own, Chapter 9's setup note applies unchanged, with `lp_farming` in place of `token_vesting`.

Delete the template-generated `deploy_config.py` inside the renamed directory. Your contract code goes in `smart_contracts/lp_farming/contract.py`.

The per-staker record in the listing below, `StakeInfo`, is an `arc4.Struct` in a `BoxMap` keyed by address, and its design is settled business: Chapter 9 made the same three decisions for the vesting schedule --- the flat encoding in its data model, the fixed-length key beside its box arithmetic, and the value semantics of "What the Box Actually Holds" --- and the farm inherits them instead of remaking them. What is settled is how the record is stored, not what it stores.

Every field is a fixed-width `arc4.UInt64`, so the record encodes flat, with no offsets to trust. The box name is a two-byte `b"s_"` prefix plus a 32-byte address, so every entry costs the same and the map can be priced before it exists. And the struct has value semantics, so reading a position out of its box and writing it back goes through `.copy()` --- Example 9-2's rule, enforced by the same compile error. (If a record of yours wants an array rather than a struct, Table 9-3 is the decision table.)

Here is the simplified version. Replace the contents of `contract.py`:

```python
from algopy import (
    Account, ARC4Contract, Asset, Bytes, Global,
    GlobalState, Txn, UInt64, arc4, gtxn, itxn, op,
    BoxMap,
)

SECONDS_PER_DAY = 86400
LOCK_DURATION = 30 * SECONDS_PER_DAY  # <2>


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

        self.lp_token_id.value = lp_token.id  # <3>
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
        lp_amount = stake.lp_amount.as_uint64()
        stake_time = stake.stake_time.as_uint64()
        claimed = stake.reward_claimed.as_uint64()
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
            self.total_staked.value,  # <1>
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
        lp_amount = stake.lp_amount.as_uint64()
        stake_time = stake.stake_time.as_uint64()
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

Three lines carry markers, one per problem the rest of this section names:

- `<1>` --- the claim-time read of `total_staked`, applied to the whole of the staker's history (Problem 1)
- `<2>` --- one fixed lock for every staker, however long they commit (Problem 2)
- `<3>` --- an asset id taken on faith from the admin, with no AMM behind it (Problem 3)

This contract works. You can deploy it, stake LP tokens, claim rewards after some time passes, and unstake after 30 days. But it has three problems that become serious at scale:

**Problem 1: The reward math does not scale.** The formula `(lp / total_lp) * (elapsed / duration) * total_rewards` looks correct for one staker, but it breaks when stakers enter and exit at different times, because `total_lp` is read at claim time and applied to the whole of the staker's history.

Fund the farm with 2,000 reward tokens over 200 seconds --- ten tokens a second --- and walk two stakers through it. Alice stakes 100 LP at t=0 and claims at t=100; Bob stakes 200 LP at t=100; both come back at t=200. Table 17-3 puts what the formula computes beside what each of them is owed.

: Table 17-3. The naive formula over one hundred seconds of two stakers

| Call | Formula computes | Fair | Gap |
|------|------------------|------|-----|
| t=100, Alice claims (sole staker so far) | 1,000 | 1,000 | none --- one staker is the case it was written for |
| t=100, Bob stakes 200, so `total_staked` becomes 300 | --- | --- | every later claim now reprices Alice's history |
| t=200, Bob claims | 1,333 | 666 | +667 to Bob, for time he was not staked |
| t=200, Alice claims | `reward` of 666, against 1,000 already claimed | 333 still owed | `reward - claimed` underflows; the call aborts |

Row three is the overpayment: Bob's `total_duration` starts at his own stake time, so his 200 LP is priced against a 300-token total for the whole window, and the formula hands him twice his share. Row four is worse than a wrong number. Alice's recomputed `reward` came out *below* the 1,000 she was already paid, because the denominator grew under her, and `reward - claimed` is a `uint64` subtraction that cannot go negative. It panics. Every subsequent claim from Alice panics the same way, on the same line, forever: the bug does not merely misprice her rewards, it bricks her position.

Add the two payouts the formula computed and you get 2,333 tokens out of a 2,000-token pool. In practice Bob's transfer fails first, on the contract's asset balance --- a different error, in a different place, from the arithmetic that caused it.

**Problem 2: No incentive for longer locks.** Everyone locks for the same 30 days. A user who commits for a year gets no additional reward over someone who commits for a month. This means the contract cannot attract the long-term, stable liquidity that pools need most.

**Problem 3: No AMM binding.** The contract accepts any token with the right ASA ID, but it does not bind that token to the AMM app the deployer intended to trust. It needs cross-contract composition to read the configured AMM's LP token ID and reject mismatches.

*Before reading the solution to Problem 1, think about this: if Alice stakes 100 LP at time 0 and Bob stakes 200 LP at time 100, and the reward rate is 10 tokens per second, how should rewards be distributed after 200 seconds? Alice was the sole staker for the first 100 seconds. Does her reward reflect that? Work out a fair distribution and write the numbers down, then read on to see how the accumulator pattern solves it.*


## The Reward Accumulator Pattern

The simplified version's core flaw is that it tries to compute each user's reward share from scratch every time. This requires knowing the exact staking history of every participant: who was staked, how much, and for how long. With two stakers, the math is manageable. With ten thousand, it is impossible within the AVM's opcode budget.

### Why Per-User Tracking Fails

Consider the naive approach: maintain a list of all stakers and iterate through them whenever someone stakes, unstakes, or claims. For each staker, recalculate their share based on the new total. This is O(n) per operation, and with the AVM's 700-opcode-per-call budget (even pooled to ~11,200 across a 16-transaction group), you run out of gas with a few dozen stakers.

Even if you could iterate, the math is wrong. When Bob stakes at time 100, the per-second reward rate changes for everyone. Alice was earning 10 tokens/second alone; now she earns 3.33 tokens/second. But her earnings from time 0 to 100 should not change. You need to "settle" every staker's accrued rewards before changing the rate, which brings you back to the O(n) iteration problem.

### The Snapshot-and-Diff Insight

Think of `reward_per_token` as a running tally that answers one question: "If you had staked exactly 1 LP token since the very beginning, how many reward tokens would you have earned by now?" This number only goes up. When you stake, you snapshot where this number is. When you claim, you calculate: `(current tally - your snapshot) x your actual stake`. That is all the accumulator does; the rest is bookkeeping.

More precisely, the solution is a global accumulator that answers the question: "How many reward tokens has one unit of LP earned since the beginning of time?" This number is called `reward_per_token`. Each user stores a snapshot of `reward_per_token` at the time they last interacted with the contract. Their pending reward is:

$$\text{reward} = \text{lp\_amount} \times (\text{reward\_per\_token}_{\text{now}} - \text{reward\_per\_token}_{\text{snapshot}})$$

This is O(1) per operation. No iteration over stakers. No historical tracking. The global value accumulates continuously, and each user's snapshot captures "where they got on."

Figure 17-1 follows two stakers through four thousand rounds. The accumulator's *slope* is the whole idea: it climbs steeply while one account is alone in the pool and shallowly once four times as much LP is staked, and nobody had to be told about the change. Each staker's payout is one subtraction against a line that was already being maintained for everyone.

![Figure 17-1. Two stakers and one accumulator. The slope changes when the staked total changes, and each staker's share is the difference between the current value and the snapshot taken when they joined.](figures/reward-accumulator.svg)

### The Update Formula

The accumulator updates on every state-changing call (stake, unstake, claim). The update adds the rewards that have accrued since the last update:

$$\text{reward\_per\_token} \mathrel{+}= \frac{\text{reward\_rate} \times \Delta t \times \text{PRECISION}}{\text{total\_staked}}$$

Where:

- `reward_rate` is tokens per second distributed to the entire pool
- `delta_t` is seconds since the last update (`min(now, reward_end) - last_update`)
- `PRECISION` is a scaling factor (this contract uses $10^9$) to preserve fractional precision in integer math
- `total_staked` is the current total LP tokens in the contract

The `min(now, reward_end)` clamping ensures rewards stop accumulating after the reward period ends.

::: {.gotcha #accumulator-zero-divisor topic="Pricing math" title="Updating the accumulator with zero stake divides by zero"}
The zero-balance guard is critical. If `total_staked` is zero, the update must be skipped entirely: dividing by zero panics the AVM, and accumulating rewards when nobody is staked would create tokens from nowhere. Always check `total_staked > 0` before updating the accumulator.
:::

### Wide Arithmetic

The multiplication `reward_rate * delta_t * PRECISION` can overflow `UInt64` (max $\approx 1.8 \times 10^{19}$). With `PRECISION = 10^9`, a `reward_rate` of 1,000,000 tokens/second, and a `delta_t` of 86,400 seconds (one day):

$$1{,}000{,}000 \times 86{,}400 \times 10^9 = 8.64 \times 10^{19}$$

This exceeds `UInt64`'s maximum. The remedy is Chapter 6's: route the product through `op.mulw` (Example 6-7; the [`algopy.op` API reference](https://algorandfoundation.github.io/puya/api/algopy/algopyop/) collects the wide-arithmetic opcodes) and divide it back down while it is still wide. The division here is `op.divmodw` rather than Example 6-10's `divw`, and the difference matters: Example 6-9 showed `divmodw` handing back a truncated quotient without complaint, so every `divmodw` in the production contract is followed by an assert that the quotient's high word is zero, restoring the loud failure `divw` gives you for free. Table 17-8 audits every product in the contract against the same obligations.

```python
# Enforce the bounds that make reward_rate * delta_t safe:
assert reward_rate <= UInt64(MAX_REWARD_RATE)
assert delta_t <= UInt64(MAX_REWARD_DURATION)
rate_time = reward_rate * delta_t
# Multiply by PRECISION (128-bit via mulw),
# then divide by total_staked:
high, low = op.mulw(rate_time, UInt64(PRECISION))
q_hi, increment, r_hi, r_lo = op.divmodw(
    high, low, UInt64(0), total_staked
)
assert q_hi == UInt64(0), "Accumulator overflow"
```

::: {.note}
The derivation above used an unbounded rate; the contract does not have one. With `MAX_REWARD_RATE` at 584 base units per second and `MAX_REWARD_DURATION` at 365 days, even the worst-case `reward_rate * delta_t * PRECISION` is $1.842 \times 10^{19}$ --- under the $1.845 \times 10^{19}$ limit by about 0.2%. The bounds are what make the plain `rate_time` product legal; the wide path is what keeps correctness from depending on that razor margin.

That ceiling is also a product decision, not just an arithmetic one, and it is worth pricing before you write the deposit script. A rate capped at 584 base units per second funds at most $584 \times 2{,}592{,}000 = 1{,}513{,}728{,}000$ base units over a thirty-day programme --- about 1,513 whole tokens at six decimals. Ask for more than that and the deposit is refused with `Reward rate too high`, at the moment the treasury is trying to fund the farm. Raising `MAX_REWARD_RATE` is the obvious response and the wrong first move: the constant is what keeps `rate * delta_t` inside `UInt64`, so raising it means re-deriving the bound, and past the point where no bound survives, moving the accumulator to `BigUInt` (Chapter 13) --- which is the escape hatch precisely because it has no ceiling to re-derive.
:::

*Recall the wide arithmetic in the Chapter 14 AMM's swap calculation: what did `mulw` and `divmodw` do there, and which of this section's two safety arguments --- the bounds or the width --- did the swap not have? Commit to an answer, then check it against `_calculate_swap_output` in Chapter 14, asking what its asserts bound and what they leave unbounded.*

### Visual Trace: Two Stakers

Trace a concrete scenario with `reward_rate = 10` tokens/second and `PRECISION = 10^9`.

**Time 0: Alice stakes 100 LP**

Table 17-4 records the accumulator state at this point.

: Table 17-4. Accumulator state after Alice stakes

| Event | `reward_per_token` | Alice snapshot | Bob snapshot | Alice pending | Bob pending |
|-------|-------------------|----------------|-------------|---------------|------------|
| Alice stakes 100 | 0 | 0 | --- | 0 | --- |

`total_staked = 100`. No time has passed, so no accumulator update.

**Time 100: Bob stakes 200 LP**

Before Bob's stake, update the accumulator:

$$increment = \frac{10 \times 100 \times 10^9}{100} = 10{,}000{,}000{,}000$$

$$\text{reward\_per\_token} = 0 + 10{,}000{,}000{,}000 = 10{,}000{,}000{,}000$$

Table 17-5 records the state once Bob's stake lands.

: Table 17-5. Accumulator state after Bob stakes

| Event | `reward_per_token` | Alice snapshot | Bob snapshot | Alice pending | Bob pending |
|-------|-------------------|----------------|-------------|---------------|------------|
| Bob stakes 200 | 10,000,000,000 | 0 | 10,000,000,000 | 1,000 | 0 |

Alice's pending reward: $100 \times (10{,}000{,}000{,}000 - 0) / 10^9 = 1{,}000$ tokens. This is correct: she was the sole staker for 100 seconds at 10 tokens/second. Compare it against the numbers you wrote down before this section --- the 1,000 is Alice's solo interval arriving on schedule, the piece the naive formula lost.

Bob's snapshot is set to the current accumulator value. His pending reward is zero; he just arrived.

`total_staked = 300`.

**Time 200: Both claim**

Update the accumulator:

$$increment = \frac{10 \times 100 \times 10^9}{300} = 3{,}333{,}333{,}333$$

$$\text{reward\_per\_token} = 10{,}000{,}000{,}000 + 3{,}333{,}333{,}333 = 13{,}333{,}333{,}333$$

Table 17-6 records the state after Alice claims.

: Table 17-6. Accumulator state after Alice claims

| Event | `reward_per_token` | Alice snapshot | Bob snapshot | Alice pending | Bob pending |
|-------|-------------------|----------------|-------------|---------------|------------|
| Claims at t=200 | 13,333,333,333 | 0 | 10,000,000,000 | 1,333 | 666 |

Alice: $100 \times (13{,}333{,}333{,}333 - 0) / 10^9 = 1{,}333$ tokens.
Bob: $200 \times (13{,}333{,}333{,}333 - 10{,}000{,}000{,}000) / 10^9 = 666$ tokens.

Total distributed: $1{,}333 + 666 = 1{,}999$ tokens. Total available: $10 \times 200 = 2{,}000$ tokens. The 1-token difference is rounding dust from integer division, always in the contract's favor. The production contract tracks only the distributable portion in `rewards_remaining`; dust stays in the contract outside that pool. Here the dust is a single token, but its magnitude depends on how the staked total compares to `rate * delta_t * PRECISION`; the accumulator-precision warning later in this chapter derives the bound past which "dust" grows into whole stranded intervals.

::: {.gotcha #rounding-favors-the-contract topic="Pricing math" title="Distribution must never exceed rate times elapsed time"}
The total rewards distributed must never exceed `reward_rate * elapsed_time`. Rounding in `op.divmodw` floors toward zero, ensuring the contract always retains dust. If you ever observe total distributions exceeding the reward pool, you have a bug. This is the single most important property to verify in your tests.
:::

**Self-check:** If Charlie stakes 300 LP at time 200 and everyone claims at time 300, how much does each person receive for the t=200 to t=300 interval? (Answer: the accumulator increment is $\lfloor 10 \times 100 \times 10^9 / 600 \rfloor = 1{,}666{,}666{,}666$. Alice gets $\lfloor 100 \times 1{,}666{,}666{,}666 / 10^9 \rfloor = 166$, Bob gets 333, and Charlie gets 499 (500 minus one unit of rounding dust), proportional to their 100:200:300 stakes out of the new total of 600.)

## Duration Multipliers

A flat reward rate treats a 30-day lock the same as a 365-day lock. To incentivize longer commitments, the contract assigns a *multiplier* that scales the user's effective stake. The LP tokens deposited do not change; the multiplier inflates the user's weight in the reward calculation.

The multiplier uses a linear scale from 1x (30 days) to 4x (365 days):

$$\text{multiplier} = \text{SCALE} + \frac{(\text{duration} - \text{MIN\_LOCK}) \times 3 \times \text{SCALE}}{\text{MAX\_LOCK} - \text{MIN\_LOCK}}$$

Where `SCALE = 1000` (giving 0.1% precision), `MIN_LOCK = 30 days`, and `MAX_LOCK = 365 days`. A 30-day lock gets multiplier 1000 (1.0x). A 365-day lock gets 4000 (4.0x). A 197-day lock, just under halfway, gets 2495 --- not the 2500 the round number invites, because the division that produces the bonus floors, and every division in this book floors toward the pool.

The user's *effective balance*, the value used in the accumulator, is:

$$\text{effective} = \frac{\text{lp\_amount} \times \text{multiplier}}{\text{SCALE}}$$

**Worked example.** Alice locks 100 LP for 365 days (multiplier = 4000). Bob locks 200 LP for 30 days (multiplier = 1000).

- Alice's effective balance: $100 \times 4000 / 1000 = 400$
- Bob's effective balance: $200 \times 1000 / 1000 = 200$
- Total effective: 600
- Alice's share: $400 / 600 = 66.7\%$
- Bob's share: $200 / 600 = 33.3\%$

Despite depositing half as many LP tokens, Alice earns twice Bob's reward rate because her 4x multiplier more than compensates. This is the intended incentive: long-term LPs earn disproportionately more.

The `total_staked` global variable (renamed to `total_effective` in the production contract) now tracks the sum of effective balances, not raw LP amounts. When Alice stakes, the contract adds 400. When she unstakes, it subtracts 400. The accumulator formula is unchanged; it already uses the total in the denominator. Adding multipliers requires zero changes to the core distribution math: all that changes is how each user's weight is calculated.

::: {.note}
Why not use a quadratic or exponential multiplier instead of linear? The choice affects game theory. A linear multiplier means the marginal benefit of each additional lock day is constant. An exponential multiplier would disproportionately reward the longest locks, potentially concentrating rewards among a few whales who can afford to lock for a year. A square-root multiplier (explored in Exercise 3) has diminishing returns: the first extra month of locking is worth more than the last. Linear is the simplest to reason about and audit, which matters for a contract holding user funds.
:::

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
    assert q_hi == UInt64(0), "Multiplier overflow"
    return UInt64(SCALE) + bonus
```

The `mulw` here is defensive: `excess * 3000` peaks near $8.7 \times 10^{10}$ at the 365-day maximum, comfortably inside `UInt64`, and would start to matter only if durations arrived in smaller units. It costs a few extra opcodes; Table 17-8 carries this product in the contract's overflow audit alongside the ones that genuinely need the width.


## Smart Contract Composition

*The farming contract needs to bind itself to the LP token from the configured AMM. Using only what you know about Algorand so far, how would you accomplish this? Think about what data the AMM stores on-chain and how another contract might access it.*

Chapter 15 built every mechanism this section spends. The farm binds deposits to the LP token reported by the AMM app chosen at deployment time, and the read that does it is Example 15-8 --- `op.AppGlobal.get_ex_uint64` against another application's global state, existence flag and all ([Opcodes Overview](https://dev.algorand.co/concepts/smart-contracts/opcodes-overview/) is the reference).

```python
# Read the configured AMM's lp_token_id and bind to that LP token.
# `lp_token` is the Asset the admin passed to `initialize`; the farm has
# not stored anything yet, so this must compare against the argument.
lp_id, exists = op.AppGlobal.get_ex_uint64(
    amm_app, Bytes(b"lp_token_id")
)
assert exists, "AMM has no lp_token_id"
assert lp_id == lp_token.id, "LP token mismatch"
```

The right-hand side of the second assert is the one to look at twice. It compares the AMM's answer against `lp_token.id`, the asset the admin named in this very call --- not against `self.lp_token_id.value`, which is still zero at this point in `initialize` and would turn the check into `lp_id == 0`, a comparison the real AMM always fails and a fresh impostor always passes. A guard that runs before the state it reads has been written is not a weak guard; it is an inverted one.

The read costs no call, no inner transaction, and no extra fee; what it spends is one entry in the transaction's reference lists.

::: {.gotcha #foreign-app-slots topic="Cross-contract calls" title="A cross-contract read spends one of the transaction's reference slots"}
The foreign apps array has a maximum of 8 entries per transaction (shared across the group since AVM v9). Each cross-contract read consumes one slot. If your transaction already references several apps, you may not have room for the AMM reference. Plan your foreign reference budget carefully when designing multi-contract interactions.
:::

**Design tradeoff: read-on-init vs. read-on-every-call.** You could read the LP token once during initialization and store the result, or read it on every stake call. Reading once is cheaper (fewer opcodes per stake) but trusts that the stored value remains correct forever. Reading every time costs ~5 extra opcodes per call but guarantees that the stored farm value still matches the configured AMM. This contract reads the AMM's state during initialization: the LP token ID cannot change after the AMM is bootstrapped, so a one-time read is enough.

This is not a proof of code identity. The deployment process must choose the trusted AMM app ID. A malicious or unrelated application could expose a global key named `lp_token_id`; the check only proves that the supplied LP token matches the app ID the farm was configured to trust.

What the read sees is governed by a rule you already hold: each transaction, inner ones included, evaluates against the ledger as the ones before it left it (Example 15-11), so a read in a group reflects every earlier group-mate's writes --- one transaction writes, a later one reads, and that is how applications communicate inside a group.

**Common error.** If the AMM app is missing from the reference lists entirely, `get_ex_uint64` fails at runtime with an "unavailable App" error. The fix is client-side plumbing, not contract logic: add the AMM app ID to the `app_references` parameter when building the transaction:

```python
farm.send.initialize(
    farm_client.InitializeArgs(
        lp_token=lp_token,
        reward_token=reward_token,
        amm_app=pool.app_id,
    ),
    params=CommonAppCallParams(
        sender=admin.address,
        signer=admin.signer,
        static_fee=AlgoAmount.from_micro_algo(3_000),
        asset_references=[lp_token, reward_token],
        app_references=[pool.app_id],
    ),
)
```


## Project Setup

You are already in `projects/lp-farming/` from Run It First. If you would rather scaffold your own, Chapter 9's setup note applies unchanged, with `lp_farming` in place of `token_vesting`.

Now build the production staking contract, incorporating the accumulator pattern, duration multipliers, and cross-contract verification. This replaces the simplified version entirely.

The contract file is `smart_contracts/lp_farming/contract.py`. Compile with:

```bash
algokit project run build
```

## The Full Contract

### State Design

The per-user stake data is stored in boxes keyed by the staker's address (the [Algorand Python storage guide](https://algorandfoundation.github.io/puya/language-guide/storage/) collects the `BoxMap`, `GlobalState`, and `BigUInt` storage rules this design leans on). Each position is an `arc4.Struct`:

```python
class StakePosition(arc4.Struct):
    effective_balance: arc4.UInt64   # LP * multiplier / SCALE
    lp_amount: arc4.UInt64          # Raw LP tokens deposited
    reward_per_token_paid: arc4.UInt64  # Snapshot at last interaction
    accrued_rewards: arc4.UInt64    # Unclaimed rewards
    unlock_time: arc4.UInt64        # Timestamp when unstake allowed
```

Five `arc4.UInt64` fields = 40 bytes. Box key: `b"s_"` prefix (2 bytes) + 32-byte address = 34 bytes. Box MBR: $2{,}500 + 400 \times (34 + 40) = 32{,}100$ microAlgos per staker. That one-line bill is what the first two of Chapter 9's box decisions buy (fixed-width fields, fixed-length name); the third, value semantics, is why every read-modify-write below goes through `.copy()`. The record grew from `StakeInfo`'s three fields to five; the three decisions did not change. The production version makes the staker fund that MBR in the same atomic group as the LP-token transfer, then refunds the exact amount when the box is deleted during `unstake`.

Table 17-7 tracks who owns that minimum balance at each moment in a staker's life.

: Table 17-7. Stake box lifecycle and who pays the minimum balance

| Moment | Box lifecycle |
|--------|---------------|
| Before `stake` | No user box exists, so no per-user box MBR is locked |
| `stake` group | The user pays exactly 32,100 microAlgos and the app creates the box |
| During the lock | The box stores the position and the MBR remains locked |
| `unstake` | The app deletes the box and refunds exactly 32,100 microAlgos |

The global state schema uses 10 `UInt64` slots and 1 `Bytes` slot (the admin address). The protocol cap is 64 pairs in total, so eleven is plenty of room. The extra `rewards_remaining` slot is a circuit breaker: every payout decrements it, so a math bug cannot distribute more reward tokens than the funded pool.

Reward accounting follows one invariant:

```text
deposited = distributable + dust
distributable = reward_rate * duration_seconds
claimed + rewards_remaining = sum(accepted distributable deposits)
```

Dust is not a user reward. It remains in the contract until a production sweep path handles it.

::: {.note}
`Global.latest_timestamp` is the timestamp of the last confirmed block --- the block *before* the one your transaction lands in --- not the wall-clock time. It is accurate to within about 25 seconds and is set by the block proposer. For a staking contract with lock periods measured in days, this precision is more than adequate. Do not use timestamps for sub-minute precision requirements.
:::

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
MIN_LOCK_DAYS = 30
MAX_LOCK_DAYS = 365
MIN_LOCK = MIN_LOCK_DAYS * SECONDS_PER_DAY
MAX_LOCK = MAX_LOCK_DAYS * SECONDS_PER_DAY
MAX_REWARD_DURATION = 365 * SECONDS_PER_DAY
MAX_REWARD_RATE = 584
MAX_UINT64 = 2**64 - 1
STAKE_BOX_MBR = 32_100
```


## Initialization and Reward Deposit

The contract class comes first, then the two admin-only methods that set it running. The `initialize` method performs the cross-contract read to bind the farm to the configured AMM's LP token, then opts into both tokens.

```python
# 5 UInt64 fields = 40 bytes data. With 34-byte key,
# box MBR = 2,500 + 400 * (34 + 40) = 32_100 microAlgos.
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
        self.rewards_remaining = GlobalState(UInt64(0))
        self.is_initialized = GlobalState(UInt64(0))
        # arc4.Address gives a fixed 32-byte key with O(1)
        # lookup by staker address --- ideal for per-user data.
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
        assert Global.group_size == UInt64(1), "Unexpected group size"
        assert Txn.sender == Account(self.admin.value), "Admin only"
        assert self.is_initialized.value == UInt64(0), "Already initialized"

        # Cross-contract read: bind to the configured AMM's LP token
        lp_id, exists = op.AppGlobal.get_ex_uint64(
            amm_app, Bytes(b"lp_token_id")
        )
        assert exists, "AMM has no lp_token_id"
        assert lp_id == lp_token.id, "LP token mismatch"

        self.lp_token_id.value = lp_token.id
        self.reward_token_id.value = reward_token.id
        self.amm_app_id.value = amm_app.id
        self.last_update_time.value = Global.latest_timestamp

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

The `initialize` method reads `lp_token_id` from the configured AMM app's global state. If the AMM has not been bootstrapped (the key does not exist), the assertion fails. If someone passes an AMM app whose reported `lp_token_id` differs from the supplied LP asset, the token mismatch check catches it. The deployer still has to choose the trusted AMM app ID --- the limit the composition section already named. Exercise 5 adds the Chapter 16 provenance check that closes that gap.

The `deposit_rewards` method funds the reward pool and sets the distribution rate:

```python
    @arc4.abimethod
    def deposit_rewards(
        self,
        reward_txn: gtxn.AssetTransferTransaction,
        duration_seconds: UInt64,
    ) -> None:
        assert Global.group_size == UInt64(2), "Unexpected group size"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert Txn.sender == Account(self.admin.value), "Admin only"
        assert reward_txn.sender == Txn.sender, "Reward sender mismatch"
        assert reward_txn.xfer_asset == Asset(
            self.reward_token_id.value
        )
        assert reward_txn.asset_receiver == (
            Global.current_application_address
        )
        assert duration_seconds > UInt64(0)
        assert duration_seconds <= UInt64(MAX_REWARD_DURATION)
        assert Global.latest_timestamp >= self.reward_end_time.value, (
            "Reward period active"
        )

        # Settle any accrued rewards before changing rate
        self._update_reward()

        amount = reward_txn.asset_amount
        assert amount > UInt64(0), "Zero reward deposit"

        new_rate = amount // duration_seconds
        assert new_rate > UInt64(0), "Reward rate rounds to zero"
        assert new_rate <= UInt64(MAX_REWARD_RATE), "Reward rate too high"

        distributable = new_rate * duration_seconds
        capacity = UInt64(MAX_UINT64) - self.rewards_remaining.value
        assert distributable <= capacity, "Reward pool overflow"

        h, worst_increment = op.mulw(
            distributable, UInt64(PRECISION)
        )
        assert h == UInt64(0), "Accumulator capacity overflow"
        acc_capacity = (
            UInt64(MAX_UINT64)
            - self.reward_per_token_stored.value
        )
        assert worst_increment <= acc_capacity, (
            "Accumulator capacity overflow"
        )

        self.rewards_remaining.value += distributable
        self.reward_rate.value = new_rate
        self.last_update_time.value = (
            Global.latest_timestamp
        )
        self.reward_end_time.value = (
            Global.latest_timestamp + duration_seconds
        )
```

The reward rate is token base units per second. Integer division means some dust is left undistributed: depositing 1,000,000 base units over 86,401 seconds yields a rate of 11 base units/second, distributing $11 \times 86{,}401 = 950{,}411$ base units total. Only the distributable amount is added to `rewards_remaining`; the remaining 49,589 base units stay in the contract as dust. This is standard behavior; production systems often add a "sweep" function for the admin to recover undistributed dust after the reward period ends.

The duration and rate asserts are the deposit-side half of the Wide Arithmetic bargain: they are what entitles `_update_reward()` to compute `rate * delta_t` as a plain product, and what keeps the scaled increment inside `UInt64` even when `total_effective == 1`. Table 17-8 records both bounds alongside every other one the reward math relies on.

The accumulator-capacity check is intentionally conservative. It assumes the worst case: one effective staking unit receives the entire new schedule. If that worst-case increment would overflow the lifetime `reward_per_token_stored` accumulator, the deposit is rejected immediately instead of accepting a schedule that could later block `claim()` or `unstake()`.

::: {.warning}
The `deposit_rewards` method rejects overlapping reward periods. New rewards can be deposited after the previous period has ended, while unclaimed rewards from earlier periods remain covered by `rewards_remaining`. A production contract that accepts top-ups during an active period must explicitly roll the unearned old schedule into the new rate or account for it separately.
:::


## Staking LP Tokens

The `stake` method is the heart of the contract. It updates the global accumulator, calculates the user's multiplier, creates or updates their position box, and records their accumulator snapshot.

```python
    @arc4.abimethod
    def stake(
        self,
        mbr_payment: gtxn.PaymentTransaction,
        lp_txn: gtxn.AssetTransferTransaction,
        lock_days: UInt64,
    ) -> None:
        assert Global.group_size == UInt64(3), "Unexpected group size"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert mbr_payment.sender == Txn.sender, "MBR sender mismatch"
        assert mbr_payment.receiver == (
            Global.current_application_address
        )
        assert mbr_payment.amount == UInt64(STAKE_BOX_MBR), (
            "Wrong MBR payment"
        )
        assert lp_txn.xfer_asset == Asset(
            self.lp_token_id.value
        )
        assert lp_txn.asset_receiver == (
            Global.current_application_address
        )
        assert lp_txn.sender == Txn.sender, "LP sender mismatch"
        assert lp_txn.asset_amount > UInt64(0), "Zero stake"
        assert lock_days >= UInt64(MIN_LOCK_DAYS), (
            "Below minimum lock"
        )
        assert lock_days <= UInt64(MAX_LOCK_DAYS), (
            "Above maximum lock"
        )

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
        assert q_hi == UInt64(0), "Effective balance overflow"
        assert effective > UInt64(0), "Zero effective stake"
        capacity = UInt64(MAX_UINT64) - self.total_effective.value
        assert effective <= capacity, "Total effective overflow"

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

The `mbr_payment` funds the exact box MBR for the user's position. Because it is in the same atomic group as the LP transfer and app call, a failed stake returns both the LP tokens and the MBR payment automatically. The contract requires the exact amount so accidental overpayments do not get trapped in the app account.

The assertion `key not in self.stakes` prevents double-staking. A user who wants to add more LP must first unstake (after their lock expires) and re-stake with a new duration. This simplification keeps the position struct fixed-size and avoids the complexity of merging positions with different multipliers and unlock times.

Production contracts sometimes support multiple positions per user via a position ID (using a `BoxMap(arc4.UInt64, StakePosition)` keyed by a sequential counter), but that adds significant complexity: each position needs independent accumulator snapshots, and claiming requires iterating over all positions.

An alternative design is to allow "topping up" an existing stake by adding more LP tokens at the same multiplier and unlock time. This requires settling accrued rewards first (to avoid retroactively applying the new balance to past periods), then adding the new effective balance to both the position and the global total. The code changes are modest, but the UX complexity of explaining when top-ups are allowed (same lock duration only? extend the lock?) and the additional test surface area make it a poor tradeoff for a first implementation.

### Updating the Accumulator

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

        assert delta_t <= UInt64(MAX_REWARD_DURATION)
        assert rate <= UInt64(MAX_REWARD_RATE)

        # The deposit bounds make this UInt64 product safe.
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

        capacity = UInt64(MAX_UINT64) - self.reward_per_token_stored.value
        assert increment <= capacity, "Accumulator overflow"
        self.reward_per_token_stored.value += increment
        self.last_update_time.value = effective_now
```

This is the Wide Arithmetic section's code in its production home: `rate * delta_t` as a plain product behind the re-asserted bounds, `mulw` by `PRECISION` for the 128-bit numerator, `divmodw` back down, with the `q_hi == 0` and capacity asserts on the result.

::: {.gotcha #precision-floors-to-zero topic="Pricing math" title="Enough stake floors the per-token increment to zero and rewards stall"}
`PRECISION = 10^9` also sets a *usability bound* on the other side. Each update computes $increment = \lfloor rate \times \Delta t \times 10^9 / \text{total\_effective} \rfloor$, so whenever `total_effective` exceeds $rate \times \Delta t \times 10^9$, the increment floors to zero, yet `last_update_time` still advances, so that interval's rewards are permanently stranded. With very large stakes relative to the reward rate, most of a schedule's rewards can strand this way. Conservation still holds (the contract never overpays, and unstreamed rewards stay in `rewards_remaining`), but stakers receive less than the advertised rate. Production systems shrink the loss to negligible by using $10^{18}$-scale precision (with `BigUInt` arithmetic) or by carrying the division remainder forward between updates.
:::

Table 17-8 is the contract's overflow audit: every product and running sum that could leave sixty-four bits, where its bound is enforced, and what the check protects. The discipline in every row is Chapter 6's --- wide products go through `op.mulw` (Example 6-7), and every `divmodw` quotient carries the high-word assert. Five rows name checks in methods still to come (`_calculate_multiplier`, `claim`, `extend_lock`, `unstake`); they sit here so the audit reads as one page rather than six, and the table is worth a second visit once you have read them.

The two plain products that remain (`rate * delta_t` here, `excess * 3000` in the multiplier) are legal only because their operands are bounded first. If your parameters outgrow these bounds, do not merely raise `MAX_REWARD_RATE`: the obligation in every row is that the value is either bounded or computed wide, and `BigUInt` (Chapter 13) is the fallback when neither holds.

: Table 17-8. Every product and sum that could leave sixty-four bits, and the check that stops it

| Assumption | Checked where | Protects |
|------------|---------------|----------|
| Reward period is bounded | `deposit_rewards`, `_update_reward` | `rate * delta_t` fits in `UInt64` |
| Reward rate is bounded | `deposit_rewards`, `_update_reward` | Scaled increment fits even when total is 1 |
| Precision multiply nears the `UInt64` edge | `_update_reward` uses `mulw` | Correctness does not hang on the 0.2% margin |
| Division result must fit | `_update_reward` checks `q_hi == 0` | Accumulator increment is 64-bit |
| Stored accumulator must not wrap | `_update_reward` checks capacity | `reward_per_token_stored` stays monotonic |
| New schedules must fit lifetime capacity | `deposit_rewards` checks worst-case increment | Future updates cannot trap users |
| Distributable pool must not wrap | `deposit_rewards` checks `rewards_remaining` capacity | The conservation counter stays a true bound |
| Multiplier product must fit | `_calculate_multiplier` checks lock bounds and `q_hi` | Bonus arithmetic cannot wrap |
| Effective balance must fit | `stake`, `extend_lock` check `q_hi == 0` | A position's weight is not truncated |
| Total effective must not wrap | `stake`, `extend_lock` check capacity | The accumulator's denominator stays honest |
| Per-user reward quotient must fit | `claim`, `extend_lock`, `unstake` check `q_hi` | Pending reward is not truncated |
| Payouts must be funded | `claim`, `unstake` check `rewards_remaining` | Claims cannot exceed the distributable pool |

### Calculating the Multiplier

The multiplier lives in a module-level subroutine so it can be called from both `stake` and `extend_lock`:

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
    assert q_hi == UInt64(0), "Multiplier overflow"
    return UInt64(SCALE) + bonus
```

### Deployment Script

Deployment is `scripts/run_lp_farming.py`, and it is Chapter 14's workflow with
a second contract bolted on: create the test ASAs, deploy and bootstrap the
pool, deploy the farm, initialize the farm against the pool. Both halves run
through generated typed clients --- the AMM's, resolved from the Chapter 14
project, and the farm's, from this one --- so the only genuinely new line is
the call that joins them, which the previous section already showed.

Three decisions are packed into that one call, and each fails loudly on its
own terms:

- **Fund the farm's account before you initialize it.** `initialize` opts the
  contract into two ASAs, raising its minimum balance by 200,000 on top of the
  account's own 100,000 floor. The script sends 1,000,000 the line before. Call
  it unfunded and the refusal comes from the ledger, not from an assert.
- **Declare the AMM.** `app_references=[pool.app_id]` is what makes the
  cross-contract read legal; without it the read fails with `unavailable App`.
- **Pool the fees.** `static_fee=3_000` covers the outer call plus the two
  zero-fee opt-in inner transactions --- Chapter 11's arithmetic, one call
  later (Example 8-11).

Build, then run it:

```bash
algokit project run build
poetry run python -m scripts.run_lp_farming
```

You should see the AMM and farm app IDs, the LP token ID, a positive claimed
reward, and a final unstake message.


## Claiming and Extending Locks

Two methods operate on an open position without closing it: `claim` settles and pays what has accrued, and `extend_lock` upgrades the multiplier in place.

### Claiming Rewards

The `claim` method settles the user's accrued rewards and sends them as an inner transaction:

```python
    @arc4.abimethod
    def claim(self) -> UInt64:
        assert Global.group_size == UInt64(1), "Unexpected group size"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        self._update_reward()

        key = arc4.Address(Txn.sender)
        pos = self.stakes[key].copy()
        effective = pos.effective_balance.as_uint64()
        assert effective > UInt64(0), "No stake"

        # Calculate pending rewards
        current_rpt = self.reward_per_token_stored.value
        paid_rpt = pos.reward_per_token_paid.as_uint64()
        diff = current_rpt - paid_rpt

        high, low = op.mulw(effective, diff)
        q_hi, new_rewards, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), UInt64(PRECISION)
        )
        assert q_hi == UInt64(0), "Reward overflow"
        total_pending: UInt64 = (
            pos.accrued_rewards.as_uint64() + new_rewards
        )

        assert total_pending > UInt64(0), "Nothing to claim"
        assert total_pending <= self.rewards_remaining.value

        # Update position: snapshot current accumulator,
        # zero out accrued
        pos.reward_per_token_paid = arc4.UInt64(current_rpt)
        pos.accrued_rewards = arc4.UInt64(0)
        self.stakes[key] = pos.copy()
        self.rewards_remaining.value -= total_pending

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

The `rewards_remaining` check is the reward conservation invariant in code. The accumulator should already make over-distribution impossible, but the remaining-pool counter turns that assumption into a final guard: every reward payout must be backed by tokens that were added to the distributable pool during `deposit_rewards`.

::: {.note}
**Project vs. printed snippets.** The chapter keeps the pending-reward math inline in `claim`, `extend_lock`, and `unstake` so you can see each step where it is used. The finished project extracts that repeated calculation into `_pending_for(pos, current_rpt)`. When comparing the project to the printed snippets, map each inline `effective * (current_rpt - paid_rpt) / PRECISION` block to that helper. The helper also caps `accrued_rewards + new_rewards` against `MAX_UINT64` with a named assert; the inline listings rely on the AVM's own loud abort for that sum.
:::

### Extending a Lock

Imagine Alice staked for 30 days at a 1x multiplier. Two weeks in, she decides she is comfortable locking for the full year. Rather than waiting for her lock to expire, unstaking, and re-staking at a higher multiplier (losing her position in the accumulator and paying box MBR twice), she can extend her lock in place, upgrading her multiplier immediately.

`extend_lock` requires only that the new unlock time is *later* than the current one. A staker nearing the end of a long lock can therefore "extend" into a shorter-multiplier tier, from the tail of a 365-day lock into a fresh 30-day lock, and downgrade their own multiplier. That is self-harm only, so the contract permits it.

This is more complex than it appears: the effective balance changes, which affects the global total and the accumulator. The update must be performed in a precise order to avoid over- or under-counting rewards.

```python
    @arc4.abimethod
    def extend_lock(
        self, new_lock_days: UInt64
    ) -> None:
        assert Global.group_size == UInt64(1), "Unexpected group size"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        assert new_lock_days >= UInt64(MIN_LOCK_DAYS), (
            "Below minimum lock"
        )
        assert new_lock_days <= UInt64(MAX_LOCK_DAYS), (
            "Above maximum lock"
        )
        # Step 1: Update global accumulator
        self._update_reward()

        key = arc4.Address(Txn.sender)
        pos = self.stakes[key].copy()
        old_effective = pos.effective_balance.as_uint64()
        lp_amount = pos.lp_amount.as_uint64()
        assert old_effective > UInt64(0), "No stake"

        # Step 2: Settle accrued rewards
        current_rpt = self.reward_per_token_stored.value
        paid_rpt = pos.reward_per_token_paid.as_uint64()
        diff = current_rpt - paid_rpt
        high, low = op.mulw(old_effective, diff)
        q_hi, new_rewards, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), UInt64(PRECISION)
        )
        assert q_hi == UInt64(0), "Reward overflow"
        accrued = pos.accrued_rewards.as_uint64() + new_rewards

        # Step 3: Calculate new multiplier and effective
        new_duration = new_lock_days * UInt64(SECONDS_PER_DAY)
        new_unlock = (
            Global.latest_timestamp + new_duration
        )
        assert new_unlock > pos.unlock_time.as_uint64(), (
            "New lock must extend beyond current"
        )
        new_multiplier = _calculate_multiplier(new_duration)
        h, l = op.mulw(lp_amount, new_multiplier)
        q_hi, new_effective, r_hi, r_lo = op.divmodw(
            h, l, UInt64(0), UInt64(SCALE)
        )
        assert q_hi == UInt64(0), "Effective balance overflow"

        # Step 4: Update global total effective
        reduced_total = (
            self.total_effective.value - old_effective
        )
        capacity = UInt64(MAX_UINT64) - reduced_total
        assert new_effective <= capacity, (
            "Total effective overflow"
        )
        self.total_effective.value = (
            reduced_total + new_effective
        )

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

**What goes wrong with the wrong order?** Suppose Alice's effective balance increases from 100 to 400, and 1,000 reward tokens accumulated since the last update with `total_effective = 100`. The correct increment is `1000 / 100 = 10` per token. But if you update `total_effective` to 400 *before* calling `_update_reward()`, the increment becomes `1000 / 400 = 2.5` per token. Every staker would be underpaid by 75% for that period.

*Without looking at the preceding code, list the steps that `extend_lock` must perform and explain why the ordering matters. Then compare your list to the 8-step sequence. The ordering constraint is the same invariant from the accumulator section: update before mutate.*


## Unstaking

The `unstake` method verifies the lock has expired, settles final rewards, returns LP tokens, deletes the position box, and refunds the box MBR.

```python
    @arc4.abimethod
    def unstake(self) -> None:
        assert Global.group_size == UInt64(1), "Unexpected group size"
        assert self.is_initialized.value == UInt64(1), "Not initialized"
        self._update_reward()

        key = arc4.Address(Txn.sender)
        pos = self.stakes[key].copy()
        effective = pos.effective_balance.as_uint64()
        lp_amount = pos.lp_amount.as_uint64()
        assert effective > UInt64(0), "No stake"
        assert Global.latest_timestamp >= (
            pos.unlock_time.as_uint64()
        ), "Lock not expired"

        # Settle final rewards
        current_rpt = self.reward_per_token_stored.value
        paid_rpt = pos.reward_per_token_paid.as_uint64()
        diff = current_rpt - paid_rpt
        high, low = op.mulw(effective, diff)
        q_hi, new_rewards, r_hi, r_lo = op.divmodw(
            high, low, UInt64(0), UInt64(PRECISION)
        )
        assert q_hi == UInt64(0), "Reward overflow"
        total_pending: UInt64 = (
            pos.accrued_rewards.as_uint64() + new_rewards
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
            assert total_pending <= self.rewards_remaining.value
            self.rewards_remaining.value -= total_pending
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
            amount=UInt64(STAKE_BOX_MBR),
            fee=UInt64(0),
        ).submit()
```

The MBR refund is 32,100 microAlgos, the exact cost of the position box. The staker funded that amount in the `stake` group, and when the box is deleted the contract's MBR requirement drops by the same amount, freeing the Algo for the refund payment. This is the same MBR lifecycle pattern from the vesting contract: fund on creation, refund on cleanup.

::: {.warning}
The `del self.stakes[key]` call and the MBR refund payment happen *after* the state update (`total_effective -= effective`). If the box deletion or payment fails (e.g., insufficient contract balance), the entire transaction rolls back atomically, including the state update. This is safe on Algorand because of atomic rollback semantics, but it means you must ensure the contract always has enough Algo to cover the refund.
:::

The accumulator update (`_update_reward()`) happens before computing the user's pending reward and before modifying the user's stake. This ordering is mathematically necessary: the global `reward_per_token` must reflect the current state of the world before individual positions are calculated against it. This is an algorithmic correctness requirement, not a reentrancy guard (reentrancy is impossible on Algorand, because inner transactions do not trigger callbacks --- Example 8-7).

The `unstake` method requires a client-side fee that covers the outer transaction plus up to 3 inner transactions (LP return, reward send, MBR refund):

```python
farm.send.unstake(
    params=CommonAppCallParams(
        sender=farmer.address,
        signer=farmer.signer,
        static_fee=AlgoAmount.from_micro_algo(4_000),
        asset_references=[lp_token, reward_token],
        box_references=[stake_box_reference(farmer.address)],
    )
)
```

The `group_size == 1` asserts on `claim`, `extend_lock`, and `unstake` are why this bill is a per-call fact: the farm's user methods refuse to share a group, so there is no claim-and-unstake batched into one submission --- each call arrives alone and pays for exactly its own inner transactions.

### Checkpoint: One Position, Five Calls

Every method the farm needs is now written. Run the workflow and watch a single
position through the whole lifecycle --- stake, advance the clock, claim,
extend, unstake:

```text
Rewards deposited: 58400 base units over 100 seconds.
Farmer staked LP for 30 days.
Claimed rewards after 10 dev-mode seconds: 6422
Farmer extended the lock to 365 days.
Farmer unstaked LP and received the box MBR refund.
```

Those five lines settle four of Table 17-1's checkpoints: the stake box was
funded at its exact MBR, the claim came back above zero, the lock lengthened
without the position being closed, and the unstake returned both the LP tokens
and the 32,100 microAlgo the box cost. They also settle Run It First's third
prediction --- the workflow advances the clock twice because the two waits are
different in kind: ten seconds to put claimable accrual behind the
accumulator, then 366 days to carry the extended lock past expiry.

The claimed number is worth a minute. 58,400 base units over 100 seconds is 584
a second --- the `MAX_REWARD_RATE` ceiling exactly, which is why the deposit was
accepted at all. The farmer is the only staker and locked at 1x, so eleven
seconds of accrual is worth 6,424 base units, and the claim paid 6,422. The
missing two are the two floors: one dividing the accumulator's increment by the
effective total, one dividing the payout back down by `PRECISION`. Both lean
toward the contract, which is Example 13-6's rule wearing a farm's numbers.

Eleven seconds, not the ten the script asked for, because the claim seals its
own block and a resting LocalNet moves its clock one second per block. The farm
never reads a wall clock; it reads `Global.latest_timestamp`, and blocks are the
only thing that moves it.


## Consuming the AMM's TWAP Oracle

The Chapter 14 AMM tracks cumulative price accumulators and exposes a `get_twap_price` read-only method --- its optional oracle section, and the finished pool in `projects/constant-product-amm/` ships the oracle whether or not you built that section yourself. The farming contract does not need to maintain its own oracle: it can consume the AMM's TWAP for position valuation.

A natural extension of the farming contract is displaying the dollar value of a staked position. A frontend would:

1. **Snapshot**: Read the AMM's raw global state (`cumulative_price_a` and `twap_last_update`) via the algod REST API (`GET /v2/applications/{app-id}`). Store both values along with the current wall-clock time. This is a free API read, not a contract call.
2. **Query**: After the desired TWAP window has elapsed (e.g., 1 hour), call `get_twap_price` via `simulate`, passing the stored cumulative price and timestamp as arguments. The method computes the time-weighted average over the window and returns it as a `UInt64`.
3. **Value**: Multiply the TWAP price by the user's staked LP amount to estimate the position's dollar value.

Every one of those three steps names an application id, and the id is the whole of the trust. The one to use is the one the farm already stores: `amm_app_id`, written once during `initialize` under the admin guard. Reading a price from an id that arrived as an argument to whichever method wanted one is the shape Chapter 15's gotcha beside Example 15-4 is about --- a caller-supplied application id is not an integration, it is an instruction, and a contract answering `get_twap_price` with a flattering number costs one fee to deploy.

Because `get_twap_price` performs inline accumulation before computing the difference, the returned TWAP is current even if no swap, mint, or burn has occurred since the snapshot. This is a key advantage of placing the oracle in the AMM rather than in each consumer: one well-trafficked pool feeds price data to any number of downstream contracts.

If a farming contract needed to make on-chain decisions based on price (e.g., dynamic reward rates or position liquidation), it could read the AMM's cumulative price state directly via `op.AppGlobal.get_ex_bytes` (since `BigUInt` values are stored as byte slices). It would store its own periodic snapshots and compute the TWAP over its desired window. For this farming contract, position valuation is purely a frontend concern, so no additional on-chain code is needed.

The AMM is now the hub of a two-contract system, and nothing about the farm modified it: the farm reads its state and accepts its LP tokens. This *composability* --- contracts interacting through shared state and token standards without needing to trust each other --- is what makes DeFi protocols interoperable. Any contract that holds LP tokens can integrate with the farm. Any contract that needs a price feed can read the AMM's TWAP oracle. A lending protocol could accept staked LP positions as collateral by reading the farming contract's box state. Each contract is a building block, and the system's value comes from the combinations.

The accumulator pattern reaches at least as far. It appears in virtually every DeFi staking system: Synthetix's StakingRewards, the pattern's original implementation ([docs.synthetix.io](https://docs.synthetix.io) documents it), Curve's [gauge system](https://curve.fi/whitepaper), Sushiswap's MasterChef, and their Algorand equivalents. The specific numbers change --- precision factors, multiplier curves, reward schedules --- but the core insight is universal: track a global per-unit accumulator and diff it against per-user snapshots.


## Testing

The finished project ships two suites in `projects/lp-farming/tests/`, split
the way Chapter 14's suite is split. `test_contract_shape.py` is the fast
half: no network, just source-level assertions that the guards this chapter
taught are present --- the cross-contract LP binding, sender binding and the
exact-MBR check on the stake group, zero-fee inner transactions, the
wide-arithmetic bounds, the explicit group sizes. `test_lp_farming.py` is the
slow half: a real pool and a real farm on LocalNet, driven through both
generated clients. The listings below are that suite's actual code, not
outlines.

`tests/conftest.py` is the Chapter 14 fixture with one line added --- `algorand`
returns a LocalNet client or skips the file with the reason, and then calls
`normalize_localnet_time(client)`, which parks the developer-mode clock at one
second per block before the test starts. It parks it at one and never at zero;
the section on time-dependent logic that follows is where that number is argued. The
helpers imported below live in `scripts/localnet_helpers.py` under the same rule
as Chapter 14's: thin, named wrappers over calls the deployment script already
made. Three names are new to the farm:

- `load_amm_client` and `load_farm_client` resolve the two generated clients
  and raise a `RuntimeError` naming whichever build artifact is missing;
  `generated_clients` turns that into a skip, because a farm suite without an
  AMM client is unrunnable, not failing.
- `advance_localnet_time` moves the ledger clock forward by a chosen number
  of seconds --- and only forward; the same section explains the one-way
  rule.
- `stake_box_reference` builds the `b"s_"`-plus-address box name from
  Table 17-7.

The fourth unfamiliar name is not new: `distinct_create_params` is Chapter 14's
random-note create parameters, imported here because one test bootstraps two
pools from the same admin and the same program, and two byte-identical creates
inside the suggested-params cache window are one transaction submitted twice.

```python
# tests/test_lp_farming.py
from __future__ import annotations

import pytest
from algokit_utils import AlgoAmount, CommonAppCallParams, PaymentParams

from scripts.localnet_helpers import (
    MICRO_UNITS,
    STAKE_BOX_MBR,
    advance_localnet_time,
    asset_transfer_arg,
    create_test_asset,
    distinct_create_params,
    fund_account,
    load_amm_client,
    load_farm_client,
    opt_account_into_asset,
    payment_arg,
    stake_box_reference,
    transfer_asset,
)


pytestmark = pytest.mark.localnet


def generated_clients():
    try:
        return load_amm_client(), load_farm_client()
    except RuntimeError as exc:
        pytest.skip(str(exc))
```

Every test starts from a pool that already has liquidity in it, and that
setup is Chapter 14's material, not this chapter's: `bootstrap_pool(algorand,
amm_client, admin, *farmers)` fuses that suite's `deploy_bootstrapped_pool`
and `add_initial_liquidity` builders --- three test ASAs with the trading
pair in canonical order, bootstrap, initial liquidity --- opts every farmer
into all four assets, and returns six values in order: the pool, the two
trading assets, the LP token, the reward token, and the minted LP amount.
Nothing in it is new. The two farm-side builders are this chapter's, and
every argument in them is a decision the chapter made:

```python
def deploy_initialized_farm(
    algorand, farm_client, admin, pool, lp_token, reward_token
):
    factory = farm_client.LpFarmFactory(
        algorand,
        default_sender=admin.address,
        default_signer=admin.signer,
    )
    farm, _ = factory.send.create.create()
    algorand.send.payment(
        PaymentParams(
            sender=admin.address,
            signer=admin.signer,
            receiver=farm.app_address,
            amount=AlgoAmount.from_micro_algo(1_000_000),
        )
    )
    farm.send.initialize(
        farm_client.InitializeArgs(
            lp_token=lp_token,
            reward_token=reward_token,
            amm_app=pool.app_id,
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(3_000),
            asset_references=[lp_token, reward_token],
            app_references=[pool.app_id],
        ),
    )
    return farm


def stake_lp(algorand, farm_client, farm, farmer, lp_token, amount):
    farm.send.stake(
        farm_client.StakeArgs(
            mbr_payment=payment_arg(
                algorand, farmer, farm.app_address, STAKE_BOX_MBR
            ),
            lp_txn=asset_transfer_arg(
                algorand, farmer, farm.app_address, lp_token, amount
            ),
            lock_days=30,
        ),
        params=CommonAppCallParams(
            sender=farmer.address,
            signer=farmer.signer,
            static_fee=AlgoAmount.from_micro_algo(1_000),
            asset_references=[lp_token],
            box_references=[stake_box_reference(farmer.address)],
        ),
    )
```

The first line of `deploy_initialized_farm` is a decision, not boilerplate:
the farm's create method is declared `create="require"`, so the typed
factory's `create.create()` accessor sends the `create()void` ABI call ---
the pool tolerated a bare create; this contract does not. The builder then
funds the app account before `initialize` (the two opt-ins raise the farm's
own minimum balance) and passes `app_references=[pool.app_id]` --- the
client-side fix from the composition section's common error, in its
permanent home. `stake_lp` sends Table 17-7's stake group: the exact-MBR
payment, the LP transfer, and the app call carrying a box reference for a
box that does not exist yet, because the reference declares the name as one
this call may touch, creation included.

The test that matters most is the accumulator's fairness claim --- the
Tables 17-4 through 17-6 walkthrough as an assertion.

*Predict before reading it: Alice stakes alone for thirty seconds at 584
base units per second, then Bob joins with twice her stake until the
100-second schedule ends. Work out both totals. Which claim is larger, and
which way would it go under the simplified contract's Problem 1?*

```python
def test_accumulator_two_stakers_keeps_early_rewards(algorand) -> None:
    amm_client, farm_client = generated_clients()
    dispenser = algorand.account.localnet_dispenser()
    admin = algorand.account.random()
    alice = algorand.account.random()
    bob = algorand.account.random()
    fund_account(algorand, dispenser, admin)
    fund_account(algorand, dispenser, alice)
    fund_account(algorand, dispenser, bob)

    pool, _, _, lp_token, reward_token, initial_lp = bootstrap_pool(
        algorand, amm_client, admin, alice, bob
    )
    farm = deploy_initialized_farm(
        algorand, farm_client, admin, pool, lp_token, reward_token
    )

    farm.send.deposit_rewards(
        farm_client.DepositRewardsArgs(
            reward_txn=asset_transfer_arg(
                algorand, admin, farm.app_address, reward_token, 58_400
            ),
            duration_seconds=100,
        ),
        params=CommonAppCallParams(
            sender=admin.address,
            signer=admin.signer,
            static_fee=AlgoAmount.from_micro_algo(1_000),
            asset_references=[reward_token],
        ),
    )

    alice_stake = initial_lp // 10
    bob_stake = initial_lp // 5
    transfer_asset(algorand, admin, alice, lp_token, alice_stake)
    transfer_asset(algorand, admin, bob, lp_token, bob_stake)

    stake_lp(algorand, farm_client, farm, alice, lp_token, alice_stake)
    advance_localnet_time(algorand, admin, offset_seconds=30)
    stake_lp(algorand, farm_client, farm, bob, lp_token, bob_stake)
    advance_localnet_time(algorand, admin, offset_seconds=200)

    alice_claim = farm.send.claim(
        params=CommonAppCallParams(
            sender=alice.address,
            signer=alice.signer,
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[reward_token],
            box_references=[stake_box_reference(alice.address)],
        )
    ).abi_return
    bob_claim = farm.send.claim(
        params=CommonAppCallParams(
            sender=bob.address,
            signer=bob.signer,
            static_fee=AlgoAmount.from_micro_algo(2_000),
            asset_references=[reward_token],
            box_references=[stake_box_reference(bob.address)],
        )
    ).abi_return

    assert alice_claim is not None
    assert bob_claim is not None
    assert alice_claim > bob_claim
    assert alice_claim + bob_claim <= 58_400
```

Depositing 58,400 base units over 100 seconds sets `reward_rate` to 584 ---
the `MAX_REWARD_RATE` ceiling exactly --- so every simulated second moves a
visible amount of reward, and the 200-second jump lands both claims after
the schedule ends, where the accumulator is clamped and the arithmetic is
stable.

Check your prediction against what the suite collects: Alice 30,951 and Bob
25,695. The intervals are 31 solo seconds and 66 shared ones rather than the
30 and 70 the schedule reads like, because the ledger clock moves in blocks,
not continuously. Three blocks separate the deposit from Alice's stake ---
two LP transfers and the stake group, one second each under the fixture's
resting offset --- so the 30-second jump plus the block carrying Bob's stake
makes Alice's solo interval 31, and the 34 seconds spent by then leave 66 of
the schedule's 100 to share.

The rest is division. Alice banks $31 \times 584 = 18{,}104$ plus a third of
the shared $66 \times 584 = 38{,}544$, or $12{,}848$; Bob banks two-thirds of
that same 38,544, or $25{,}696$. Both land one unit lower on-chain because
the payout division floors and the stakes are 999,999,900 and 1,999,999,800
rather than round numbers --- Chapter 14's minimum-liquidity lock, still
visible in this chapter's arithmetic. Between them they collect 56,646 of the
58,400 deposited, and the missing 1,754 is those two floored units plus the
1,752 the schedule released in the three seconds before anyone had staked:
with `total_effective` at zero, `_update_reward` moves `last_update_time` and
returns without accumulating anything for anyone to claim.

Under the simplified contract's Problem-1 math the same scenario pays Alice
19,466 and Bob 38,933: once the schedule ends, stake
share alone decides, and Alice's solo interval vanishes from the ledger. The
two final assertions pin the accumulator's answer instead: the head start
survives, and the two claims together stay inside the deposited pool --- the
conservation inequality from the rounding gotcha, machine-checked.

The rest of the file follows the same shape:

- `test_lifecycle_stake_claim_extend_unstake` --- Table 17-1's checkpoint
  list as assertions: deposit, stake, an early `unstake` refused with `Lock
  not expired`, a positive `claim` after ten simulated seconds,
  `extend_lock` to 365 days, a 366-day jump, and a final `unstake` that must
  grow the farmer's Algo balance by at least the 32,100-microAlgo box refund
  minus the 4,000-microAlgo fee, leaving no stake box behind.
- `test_initialize_rejects_wrong_amm` --- two pools, and an `initialize`
  that pairs pool A's LP token with pool B's app ID, refused with `LP token
  mismatch`: the composition guard, exercised in the direction that matters.
- `test_stake_rejects_underfunded_mbr` and
  `test_stake_rejects_mbr_overpayment` --- a 1-microAlgo MBR payment and a
  32,101-microAlgo one, both refused with `Wrong MBR payment`. The box bill
  is exact in both directions, so no overpayment gets trapped in the app
  account.

Every negative test asserts the refusal's message, not just the failure ---
Chapter 14's rule that a negative test without a reason would pass for any
accidental breakage. Run the whole thing with `algokit project run test`
from the project directory. Without a reachable LocalNet the integration
file skips and reports why, which is the behavior Run It First promised;
`test_contract_shape.py` --- the source-property checks --- still runs with
no Docker at all via `algokit project run test-static`.

### Testing Time-Dependent Logic on LocalNet

LocalNet in developer mode seals one block per transaction and does not otherwise move its clock. `advance_localnet_time` uses the developer-mode timestamp-offset endpoint: it sets the offset, then submits a zero-Algo self-payment with a random note so a block exists at the shifted time. That is how the lifecycle test crosses 366 days without sleeping. The offset is not a one-shot jump, though: it is a standing per-block increment, so every later block also advances by it until a different value replaces it. Three rules follow from that, and the suite implements all three.

- **Normalize on the way in.** The `algorand` fixture calls `normalize_localnet_time`, which sets the offset to one second per block before each test runs. Whatever ran before --- including a test in this same file that jumped a year --- the clock starts every test at a known, sane rate. One second, never zero.
- **Park it on the way out.** `advance_localnet_time` sets the requested offset, seals one block with it, then sets the offset back to one. A jump has to be a jump and not a new speed: without that teardown a 366-day lock test would leave every later block, in this suite and in every other project sharing the node, 366 days apart.
- **Mind what you hand back.** Timestamps never move backward, so a node this suite has finished with is a node whose clock no longer answers to `time.sleep`. The vesting suites of Chapters 9 and 12 survive that because their `advance_time` reads the clock back and produces blocks until it has moved; a node left jumping a year a block, or frozen at a zero offset, would strand them. Run those suites first if you would rather not think about it, and `algokit localnet reset` is the only cure for a clock that has stopped.

The suite therefore treats the ledger clock as forward-only: each test asserts against clamped, schedule-relative values rather than hand-picked instants, which is why both claims in the accumulator test land after `reward_end`.

::: {.gotcha #localnet-offset-is-one-way topic="Testing and simulation" title="The LocalNet timestamp offset is one-way --- never set it to zero"}
Setting the offset to `0` does not restore the wall clock. A zero offset means every new block's timestamp is the previous one plus zero: the ledger clock freezes, the REST API cannot un-set the offset, and restarting the container does not heal it, because developer mode never moves timestamps backward. Advance with positive offsets only, and when you need real time back, `algokit localnet reset` is the only way home.
:::

If your LocalNet does not expose the offset endpoint at all, fall back to Chapter 9's sleep-then-force-a-block helper (the `time.sleep()` gotcha there), accepting that a 366-day lock is out of its reach.

### What a Production Suite Adds

The shipped suite pins the lifecycle, the fairness ordering, the conservation inequality, and three refusal reasons. Before real value flows through a farm, two of those deserve tighter versions and two more properties deserve tests the suite does not have:

- **Exact conservation.** The suite asserts `claimed <= deposited`. The full invariant is stronger: read the farm's global state after each claim and assert `claimed_total + rewards_remaining == sum(distributable_i)` across every accepted deposit, with `distributable = reward_rate * duration_seconds`. Any drift is a critical bug in the accumulator math.
- **Proportional fairness.** With equal lock durations, a staker with 2x the effective balance should earn approximately 2x the rewards --- "approximately" meaning a few base units of rounding, not a percentage. The same setup with different `lock_days` values pins the multiplier scaling.
- **Dust.** Deposit the 1,000,000-over-86,401 schedule from the reward-deposit section, drain the pool past its end, and assert the contract retains exactly `amount - reward_rate * duration_seconds`.
- **Edge cases.** One non-event and three refusals, each pinned by its message:
  - staking after the reward period ends accrues nothing new;
  - claiming with nothing pending refuses with `Nothing to claim`;
  - shortening a lock refuses with `New lock must extend beyond current`;
  - deposits that break the rate or duration bounds from Table 17-8 refuse.

::: {.tryit}
**Exercise.** The suite never commits the double-stake mistake the contract guards against. Add `test_double_stake_rejected` to `tests/test_lp_farming.py`: bootstrap, deploy, stake once with `stake_lp`, then call it a second time inside `pytest.raises` matching `Already staked` --- and then assert the claim the chapter made in prose but never machine-checked: because the group fails atomically, the farmer's Algo balance is unchanged apart from fees, and exactly one stake box exists. Every piece is in the builders above.
:::


## Exercises

1. **(Recall)** In the reward accumulator pattern, what happens if you update `total_effective` *before* settling a user's accrued rewards during an `extend_lock` call? Trace through the math with concrete numbers to show the error.

2. **(Apply)** Add an `emergency_withdraw` method that lets users retrieve their LP tokens before the lock expires, but forfeits all unclaimed rewards. The forfeited rewards should remain in the contract for distribution to other stakers. What state updates are needed, and in what order?

3. **(Analyze)** The linear multiplier gives 1x at 30 days and 4x at 365 days. Consider an alternative: a square-root multiplier where $\text{multiplier} = \sqrt{\text{duration} / \text{MIN\_LOCK}} \times \text{SCALE}$. A 30-day lock gets 1x, a 120-day lock gets 2x, a 365-day lock gets ~3.49x. What are the game-theoretic implications? Does this favor short-term or long-term stakers compared to linear?

4. **(Debug)** A pull request adds a lucky-claim bonus to the farm. Every claim reads the block seed from two rounds back, hashes it with the caller's address, and pays a 10% bonus when the result modulo 100 lands under 5. The PR description says two rounds back is the safe distance, because the caller cannot know a seed that has not been proposed yet.

   ```python
       @arc4.abimethod
       def claim_with_bonus(self) -> UInt64:
           payout = self.claim()
           seed = op.Block.blk_seed(Txn.first_valid - UInt64(2))
           roll = op.btoi(op.extract(op.sha256(
               seed + Txn.sender.bytes), 24, 8)) % UInt64(100)
           if roll < UInt64(5):
               bonus = payout // UInt64(10)
               self.rewards_remaining.value -= bonus
               itxn.AssetTransfer(
                   xfer_asset=Asset(self.reward_token_id.value),
                   asset_receiver=Txn.sender,
                   asset_amount=bonus,
                   fee=UInt64(0),
               ).submit()
               payout += bonus
           return payout
   ```

   a. Name the attack, citing Example 6-17 ("Randomness from the block, and why it fails") and its gotcha. Say precisely which value the caller knows, and when they know it relative to signing.

   b. The PR's rationale contains a claim that cannot be true of any round `op.Block` is allowed to read. State the rule that makes it false, and say what the "current round" alternative it contrasts against would actually do.

   c. Price one grinding attempt. The attacker computes `roll` off-chain for a candidate `first_valid`, and submits only on a winner. Given a 5% hit rate, what does the search cost them, and what do they pay in fees for the attempts they never submit?

   d. Say what Chapter 18 supplies in place of the seed, and which of the three properties in its rubric the seed fails.

   Do not merge the method. The exercise is the diagnosis.

5. **(Create, cross-chapter)** The chapter opened with an admission: this farm binds to whatever AMM app ID the deployer configures and never checks who deployed it. Restore the Chapter 16 provenance check it skips --- the change Chapter 16's Exercise 5 had you design from the factory's side.

   a. Add a `factory_app_id` global set during `initialize`, and pass the factory in the call's `app_references`.

   b. Reject the pool unless its ledger-recorded creator (Example 15-10's `op.AppParamsGet.app_creator`, exists flag and all) equals the factory's application address --- the one claim a pool cannot forge.

   c. For the full answer, replace that single check with an inner application call to the factory's `verify_pool` that must return `True`, adding the registry and child-state checks from Table 16-4. The inner call's fee is zero, so raise the outer fee to cover it.

   d. Prove it with a negative test: a pool deployed directly, with no factory anywhere in its history --- exactly what `bootstrap_pool` builds --- must now be refused at `initialize`. Choose the refusal message before you write the check, and assert on it.

::: {.tryit}
**Practice.** Look up reading another application's state, a `BoxMap` for per-user data, box minimum-balance arithmetic, and ARC-4 types in Appendix D, which indexes every numbered example in the book by the task it performs.
:::

## Before You Continue

You should be able to check off all five of these:

- [ ] I can say why the naive per-user reward formula fails once two people stake at different times, and write the reward-per-token accumulator that replaces it with bounded `mulw` and `divmodw` arithmetic
- [ ] I can calculate a staker's pending rewards from their snapshot, the current accumulator, and the effective balance their duration multiplier produced
- [ ] I can explain why payouts cannot exceed the funded distributable pool, and where the undistributed dust ends up
- [ ] I can read another contract's global state with `op.AppGlobal.get_ex_uint64`, handle the key-not-present case, and say what the AMM's TWAP gives the farm that a spot price read would not
- [ ] I can manage a position box across creation, update, deletion, and MBR refund

If any of these are unclear, revisit the relevant section before proceeding.

## Mastery Checkpoint
That is the end of Part III. The checklist above asks whether you followed the chapters. The Mastery Checkpoint printed on the next page asks something harder: whether you can build a thing this part did not show you. It is a small program with a stated acceptance test, and a fallback if you stall.
