\newpage

\part{Building a DEX}

Part III builds an automated market maker the way production teams do: the pricing math first (Chapter 13), then the pool (Chapter 14), contract-to-contract calls (Chapter 15), a factory that gives pools provenance (Chapter 16), and a yield farm that pays for liquidity (Chapter 17). By the end, three contracts are in conversation on your LocalNet --- pools, the factory that vouches for them, and the farm that rewards their liquidity tokens --- with one deliberate gap between them: the farm trusts the pool it is configured with without asking the factory, and its final exercise closes that gap.

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# Numbers That Price Things

Chapter 6 taught arithmetic that refuses. Overflow aborts, division by zero aborts, a subtraction that would go negative aborts, and the discipline that chapter asks for is to keep every number inside the range where the AVM will still cooperate.

This chapter's arithmetic decides what two counterparties owe each other, and once a number is the boundary between somebody's money and somebody else's, being *inside the range* is no longer the same thing as being right. Every division now has a winner. Every instantaneous reading has a manipulator. Every empty pool has a first depositor.

There, wrong arithmetic gets refused. Here, **correct arithmetic can still be robbed.**

## Two Questions a Pool Must Answer
A two-asset pool holds a reserve of each and settles trades between them. Everything it does rests on two answers: how much of B comes out if I send this much A, and how much A must I send to get this much B. Both are read-only, so anybody can ask for free, and a wallet, an arbitrageur and a router all ask before they trade.

Chapter 14 builds the pool those answers belong to. This chapter builds the engine that gives them, and every division in that project is one of the divisions here.

::: {.spec title="Your commission: a two-sided quote engine"}
The contract you build this chapter prices a constant-product pool: two reserves whose product defines the curve every trade walks along. It must:

1. Answer both questions: how much B comes out for a given A in, and how much A must go in for a wanted B out
2. Charge the thirty-basis-point fee every pool in this book charges --- into the reserves, never out of them
3. Refuse the edges by name: a pool nobody has seeded, a request for more than the reserve holds
4. Round every division against the asker, in both directions --- no quote may lower the product of the reserves
5. Agree with an off-chain copy of itself to the unit, so a wallet never shows a number the chain will not settle

Five requirements, three methods. At the end of the chapter you will run the finished engine against this list.
:::

By the end of this chapter you will be able to:

- Say why a ratio of two integers is not a price, and store one that is
- Choose between `BigUInt` and the wide-multiply pair on the rule that decides it
- Round a division in the direction that protects the pool, in *both* directions of a two-sided quote
- Say where a fee actually goes in a constant-product pool, and who receives it
- Name what a minimum-liquidity lock defends against, and what it costs to keep
- Accumulate a price over time so that any two readings give an average
- Quote a price from a client that the chain will honour to the unit

Figure 13-1 is the shape all of it is about.

![Figure 13-1. One swap against a constant product pool. The gap between what the curve pays and what the quoted price implied is slippage, and it grows with the size of the trade.](figures/constant-product-curve.svg)

The pool does not quote you a price and then honour it. It quotes the slope of the curve where you are standing, and then you walk down the curve as you trade. The gap between those two is slippage, and it is a property of the size of your order against the reserves, not a fee anybody charges you.

## Building the Two-Sided Quote
The obvious way to meet that commission is a ratio. Divide the reserve of B by the reserve of A and that is the price; multiply by what comes in, take the fee off the top, and both questions are answered. It is arithmetic a reviewer can check against a calculator. Here it is, as anyone would first write it --- complete, and in full.

**Example 13-1.** The two-sided quote, as first written

<!-- finder: see a price quote that gives value away in both directions -->

```python
from algopy import ARC4Contract, GlobalState, UInt64, arc4, subroutine

# Thirty basis points, the fee every pool in this book charges. Basis points
# because that is the unit the numbers chapter established; 9,970/10,000 is
# the same ratio as the 997/1000 spelling used elsewhere.
FEE_BPS = 30
BPS = 10_000


class PriceQuote(ARC4Contract):
    """Quote both directions of a swap."""

    def __init__(self) -> None:
        self.reserve_a = GlobalState(UInt64(0))
        self.reserve_b = GlobalState(UInt64(0))

    @arc4.abimethod
    def seed(self, a: UInt64, b: UInt64) -> None:
        assert self.reserve_a.value == UInt64(0), "already seeded"
        assert a > UInt64(0) and b > UInt64(0), "a pool needs both sides"
        self.reserve_a.value = a
        self.reserve_b.value = b

    @subroutine
    def _price(self) -> UInt64:
        return self.reserve_b.value // self.reserve_a.value

    @arc4.abimethod(readonly=True)
    def quote_in_to_out(self, amount_in: UInt64) -> UInt64:
        """How much B comes out if I send amount_in of A?"""
        net = amount_in * UInt64(BPS - FEE_BPS) // UInt64(BPS)
        return net * self._price()

    @arc4.abimethod(readonly=True)
    def quote_out_to_in(self, amount_out: UInt64) -> UInt64:
        """How much A must I send to get amount_out of B?"""
        assert amount_out < self.reserve_b.value, "not that much liquidity"
        gross = amount_out * self.reserve_a.value // self.reserve_b.value
        return gross * UInt64(BPS) // UInt64(BPS - FEE_BPS)
```

Example 13-1 is complete and deployable. It refuses to quote more than the reserve holds, and its fee is thirty basis points spelled the way Chapter 6 spells one. On an unseeded pool it dies in a division by zero rather than saying so, the first hint that a bare ratio cannot carry a price. Two of its lines are wrong and both look like care.

*Predict: two lines, and write both down now in whatever words you have. One of them you can point at. The other is the previous chapter's rule, obeyed exactly. Check yourself against the diagnosis after the run, and against the diff at the end.*

Deploy it and ask it for prices. This is a **LocalNet run** through an algokit-utils typed client, against a pool holding five million of A and two million of B:

*Before you read it: the pool holds more A than B. Say what `quote_in_to_out` returns for a thousand, and whether sending a million changes your answer.*

```console
>>> pool.send.seed(args=(5_000_000, 2_000_000))
>>> pool.send.quote_in_to_out(args=(1_000,)).abi_return
0
>>> pool.send.quote_in_to_out(args=(1_000_000,)).abi_return
0
>>> pool.send.quote_out_to_in(args=(1,)).abi_return
2
>>> (5_000_000 + 2) * (2_000_000 - 1)      # the product after
9999998999998
>>> 5_000_000 * 2_000_000                   # the product before
10000000000000
```

Nothing comes out, whatever goes in. That is `_price`: a ratio of two integers is not a price, and whenever the pool holds less B than A the quotient is zero --- and so is every quote built on it.

And one unit of B was quoted at two units of A, which sounds like the pool being careful until you notice the product fell. Chapter 6's rule was to floor a division that decides what *leaves* the contract; the division in `quote_out_to_in` decides what *enters* it, and the floor hands the difference to whoever asked. Hold slippage apart from the fee as you read quotes like these --- they are different things arriving in the same number, and neither one is what lowered this product.

A constant-product pool is defined by that product: **across a swap**, reserves may move in either direction but their product may only ever *rise*, because the fee accrues into it. Minting and burning move it too, which is what they are for, so the invariant is a statement about trades, and every quote in this chapter is a trade. A quote that lowers it has given away something the pool was holding for everybody.

Ship a pool that settles on those quotes and nothing announces the leak: no assert compares the product before and after a trade, so the reserves fall while every call reports success. The party collecting is whoever read the code first --- in practice a market maker, inside a day of the pool holding enough to be worth the trip.

## A Price Is a Direction and a Scale
A price is a fraction, and the AVM has no fractions. Two things have to be supplied before a ratio of two integers means anything: which way round it goes, and what it is measured in.

**Example 13-2.** One pair, one order

<!-- finder: fix which asset a pool's price is quoted in, once and for all -->

```python
from algopy import ARC4Contract, Asset, GlobalState, UInt64, arc4

class PairKey(ARC4Contract):
    """A pool is an unordered pair. A price is not."""

    def __init__(self) -> None:
        self.asset_a = GlobalState(UInt64(0))
        self.asset_b = GlobalState(UInt64(0))

    @arc4.abimethod
    def open(self, first: Asset, second: Asset) -> None:
        assert self.asset_a.value == UInt64(0), "already open"
        # Strict less-than does two jobs at once. It fixes which asset is the
        # denominator, so "the price" names one number instead of a pair of
        # reciprocals nobody can tell apart in a log; and because it is strict
        # rather than <=, it refuses a pool of an asset against itself.
        assert first.id < second.id, "assets must be in canonical order"
        self.asset_a.value = first.id
        self.asset_b.value = second.id

    @arc4.abimethod(readonly=True)
    def denominator(self) -> UInt64:
        """Which asset every price from this pool is quoted in."""
        assert self.asset_a.value > UInt64(0), "not open"
        return self.asset_a.value
```

A pool is an unordered pair (ALGO and USDC is the same pool as USDC and ALGO), but a price is not. `reserve_b / reserve_a` and its reciprocal are different numbers, and nothing on the wire distinguishes them, so two honest programs can disagree about "the price" and both be right. The key line is `assert first.id < second.id`, strict rather than `<=` for a second reason: it refuses a pool of an asset against itself. Chapter 7 met that shape already, where two arguments of the same type are two *names* and nothing stops both naming the same thing; a pool of an asset against itself is that hazard wearing a price.

The factory in Chapter 16 enforces this same ordering for a different reason, so that one pair cannot have two pools splitting its liquidity, and both reasons want exactly the same line.

**Example 13-3.** A price with a denominator everybody agrees on

<!-- finder: store a fractional price in a type that has no fractions -->

```python
from algopy import ARC4Contract, GlobalState, UInt64, arc4

# One billion. Every stored price is multiplied by this before the division
# and divided by it again on the way out. The number itself is arbitrary; that
# both sides of every exchange agree on it is not.
SCALE = 1_000_000_000


class ScaledPrice(ARC4Contract):
    """The only fraction the AVM has is an integer with an agreed denominator."""

    def __init__(self) -> None:
        self.reserve_a = GlobalState(UInt64(1))
        self.reserve_b = GlobalState(UInt64(1))

    @arc4.abimethod
    def set_reserves(self, a: UInt64, b: UInt64) -> None:
        assert a > UInt64(0) and b > UInt64(0), "a pool needs both sides"
        self.reserve_a.value = a
        self.reserve_b.value = b

    @arc4.abimethod(readonly=True)
    def spot_unscaled(self) -> UInt64:
        """What gets written first, and what it costs."""
        return self.reserve_b.value // self.reserve_a.value

    @arc4.abimethod(readonly=True)
    def spot_scaled(self) -> UInt64:
        """Multiply first: the scale is exactly the precision that survives.

        The domain limit is worth knowing rather than discovering. This
        product overflows once reserve_b passes about 1.8 x 10^10, which is
        an ordinary reserve for a six-decimal asset.
        """
        return self.reserve_b.value * UInt64(SCALE) // self.reserve_a.value
```

*Predict: `spot_unscaled` on a pool holding five million A and two million B. Write the number down before you read the next sentence.*

`spot_unscaled` is what gets written first and it is zero for every pool holding less B than A, which is most pools, since the two assets are rarely worth the same. `spot_scaled` multiplies before dividing, and the scale is exactly the precision that survives. The number itself is arbitrary; that everyone touching the pool agrees on it is not, which is why it is a constant with a name rather than a literal at each site.

The domain limit is named in the source rather than discovered in production: `reserve_b * SCALE` overflows once `reserve_b` passes about 1.8 × 10^10^, which is an ordinary reserve for a six-decimal asset. That is the fact the next example exists to answer.

**Example 13-4.** When the value itself outgrows the type

<!-- finder: decide between BigUInt and a wide multiply -->

```python
from algopy import ARC4Contract, BigUInt, GlobalState, UInt64, arc4


class Accumulator(ARC4Contract):
    """Wide when the VALUE outgrows 64 bits, not when the product does."""

    def __init__(self) -> None:
        self.cumulative = GlobalState(BigUInt(0))

    @arc4.abimethod
    def accrue(self, scaled_price: UInt64, elapsed: UInt64) -> None:
        # `mulw` would carry this product. Nothing carries the running total,
        # and the running total is the thing with no ceiling -- so the total
        # is what has to be wide, and the product only follows it.
        self.cumulative.value += BigUInt(scaled_price) * BigUInt(elapsed)
```

Chapter 6 gave you `op.mulw` and `op.divw` for a product that outgrows sixty-four bits on its way to a quotient that does not, and promised that the wider type belonged to this chapter. **Reach for the wide-multiply pair when only the intermediate is large *and* the divisor still fits a `UInt64`; reach for `BigUInt` when the stored value is large, or when the expression has no `mulw` shape at all.** `op.mulw` takes two operands and `op.divw` takes a sixty-four-bit divisor, so a product of three terms and a divisor that outgrows the type are both outside what the pair can express. A running total with no ceiling is the clearest case for the wide type, because nothing later brings it down, but it is not the only one, and Example 13-13 at the end of this chapter is the other: every result there is a `UInt64` and both sides are still `BigUInt`, because one of them multiplies three things together.

**Example 13-5.** The square root, and what it is for

<!-- finder: price a share of a pool in a unit that did not exist before -->

```python
from algopy import ARC4Contract, BigUInt, UInt64, arc4, op

MINIMUM_LIQUIDITY = 1_000


class InitialMint(ARC4Contract):
    """What the first deposit is worth, in a unit that did not exist before."""

    @arc4.abimethod(readonly=True)
    def initial_lp(self, amount_a: UInt64, amount_b: UInt64) -> UInt64:
        # The geometric mean rather than the sum, so the amount minted does
        # not depend on the price level: one unit against a thousand mints
        # exactly what a thousand against one does.
        product = BigUInt(amount_a) * BigUInt(amount_b)
        root = op.bsqrt(product)
        # Eight bytes or fewer by construction. Both inputs are UInt64, so the
        # product is at most (2^64 - 1)^2 and its root at most 2^64 - 1.
        minted = op.btoi(root.bytes)
        assert minted > UInt64(MINIMUM_LIQUIDITY), "initial liquidity too small"
        return minted - UInt64(MINIMUM_LIQUIDITY)
```

The first deposit into a pool has a problem no later one has: there is no exchange rate yet, because the pool is what defines it. The geometric mean is the answer because it is the one function of the two amounts that does not depend on the price level: a unit of A against a thousand of B mints exactly what a thousand of A against one of B does.

`op.bsqrt` takes and returns a `BigUInt`, so the result comes back as bytes and `op.btoi` converts it. That conversion accepts eight bytes at most, and here it is safe for a reason the comment states rather than assumes: both inputs are `UInt64`, so their product is at most (2^64^ − 1)^2^ and its root at most 2^64^ − 1. An absent bound that is provable should say so; an absent bound that is not is a defect.

## Every Division Picks a Winner
Chapter 6 left you a rule: when a division decides how much leaves the contract, floor it, so the residue accumulates on the contract's side. That rule is correct, and it is half of one.

**Example 13-6.** The same rule, in both directions

<!-- finder: round a division that decides what ENTERS the contract -->

```python
from algopy import ARC4Contract, UInt64, arc4

class Rounding(ARC4Contract):
    """Two divisions, opposite directions, one rule underneath both.

    Widths are the previous chapter's subject and the mini-build's job. These
    products are deliberately narrow so that nothing distracts from which way
    each division leans; in production both belong in `BigUInt`.
    """

    @arc4.abimethod(readonly=True)
    def payout(self, shares: UInt64, supply: UInt64, reserve: UInt64) -> UInt64:
        """What LEAVES. Floor, so the fraction stays behind."""
        assert supply > UInt64(0), "no supply"
        return shares * reserve // supply

    @arc4.abimethod(readonly=True)
    def owed(self, shares: UInt64, supply: UInt64, reserve: UInt64) -> UInt64:
        """What ENTERS. Ceiling, so the fraction is paid rather than forgiven."""
        assert supply > UInt64(0), "no supply"
        # Add one less than the divisor, then floor. There is no ceiling
        # opcode; this identity is how you get one.
        return (shares * reserve + supply - UInt64(1)) // supply
```

Two divisions, and they lean opposite ways. `payout` decides what leaves, so it floors, exactly as you were told. `owed` decides what the caller must *send*, and flooring that is a discount, so it takes the ceiling, which the AVM has no opcode for and which the expression `(n + d - 1) // d` produces instead.

*Predict: one of the two methods below is about to be written the wrong way. Before you look, say which one, and say what the wrong version would return that the right one does not.*

Here is the same pair written by somebody who took the rule literally, a
bare variant carrying no number of its own:

```python
from algopy import ARC4Contract, UInt64, arc4

class Rounding(ARC4Contract):
    """The same pair, both floored -- which is the rule applied too literally."""

    @arc4.abimethod(readonly=True)
    def payout(self, shares: UInt64, supply: UInt64, reserve: UInt64) -> UInt64:
        assert supply > UInt64(0), "no supply"
        return shares * reserve // supply

    @arc4.abimethod(readonly=True)
    def owed(self, shares: UInt64, supply: UInt64, reserve: UInt64) -> UInt64:
        assert supply > UInt64(0), "no supply"
        # Floored, because "floor a division" was the rule. But this division
        # decides what the caller OWES, so the floor is a discount.
        return shares * reserve // supply
```

That is not careless code. It is the previous chapter's rule applied exactly as that chapter states it, and it is wrong because the rule was written about divisions that decide what *leaves*. One unit per call, in the asker's favour, on a method anybody may call as often as they like.

::: {.gotcha #round-against-the-asker topic="Pricing math" title="Floor the payout, ceil the charge --- the rule is directional"}
"Round in the contract's favour" is one rule with two spellings, and using the wrong one is invisible in testing because both agree whenever the division comes out exact. A division that decides how much *leaves* the contract floors, so the fraction stays behind. A division that decides how much the caller must *send in* takes the ceiling, so the fraction is paid rather than forgiven. Getting the second one wrong is a discount of up to one unit per call, unbounded because calls are unbounded, and it is the shape that drains a pool one microunit at a time while every integration test passes. The AVM has no ceiling opcode: `(numerator + denominator - 1) // denominator` is how you write one.
:::

**Example 13-7.** Where the fractions end up

<!-- finder: follow the residue a floored payout leaves behind -->

```python
from algopy import ARC4Contract, GlobalState, UInt64, arc4

# Burned at creation so the supply never reaches zero. Cost, not gain, here.
MINIMUM_LIQUIDITY = 1_000


class Pool(ARC4Contract):
    """Every floor leaves a residue. Follow where each one ends up."""
    def __init__(self) -> None:
        self.supply = GlobalState(UInt64(0))
        self.reserve = GlobalState(UInt64(0))

    @arc4.abimethod
    def seed(self, supply: UInt64, reserve: UInt64) -> None:
        assert self.supply.value == UInt64(0), "already seeded"
        assert supply > UInt64(MINIMUM_LIQUIDITY), "below the locked minimum"
        self.supply.value = supply
        self.reserve.value = reserve

    @arc4.abimethod
    def burn(self, shares: UInt64) -> UInt64:
        assert shares > UInt64(0), "nothing to burn"
        # The locked shares belong to nobody, so nobody can ever present them.
        left = self.supply.value - UInt64(MINIMUM_LIQUIDITY)
        assert shares <= left, "more than exists"
        # Floor: the fraction raises what every other share is worth.
        paid = shares * self.reserve.value // self.supply.value
        self.supply.value -= shares
        self.reserve.value -= paid
        return paid

    @arc4.abimethod(readonly=True)
    def unclaimable(self) -> UInt64:
        """The reserve behind shares nobody holds -- what the lock costs."""
        return UInt64(MINIMUM_LIQUIDITY) * self.reserve.value // self.supply.value
```

Every floored payout leaves a fraction in the pool, and that fraction is not lost: it raises what each remaining share is worth. Dust is inherited, which is exactly the behaviour you want and the reason flooring the payout is safe rather than merely conservative.

There is one residue that is *not* inherited, and it is the `unclaimable` method's whole subject. Shares burned at creation belong to nobody, so nobody can present them, so the reserve behind them stays in the contract for as long as the contract exists.

**Example 13-8.** Thirty basis points, taken on the way in

<!-- finder: say where a swap fee actually goes -->

```python
from algopy import ARC4Contract, UInt64, arc4

FEE_BPS = 30
BPS = 10_000


class Fee(ARC4Contract):
    """Thirty basis points, and where they actually end up.

    Deliberately narrow, the way Example 13-6 is: `amount_in * 9970`
    overflows a `UInt64` once `amount_in` passes about 1.85 x 10^15, so a
    production pool takes its fee inside the wider expression at the end of
    this chapter rather than in a method of its own.
    """

    @arc4.abimethod(readonly=True)
    def net_of_fee(self, amount_in: UInt64) -> UInt64:
        # The fee is not sent anywhere and is not held in a separate balance.
        # It is the part of the input the curve is never told about, so it
        # stays in the reserves -- and the product every holder owns a share
        # of goes up. Nobody is paid a fee; everybody's share is worth more.
        return amount_in * UInt64(BPS - FEE_BPS) // UInt64(BPS)
```

Chapter 6 defined the unit; this is what the unit is doing in a pool. The fee is not transferred anywhere, is not held in a separate balance, and is not paid to anybody. It is the part of the input the curve is never told about, so it stays in the reserves, and the product every holder owns a share of goes up. Nobody receives a fee. Everybody's share becomes worth slightly more.

**Example 13-9.** A quote a wallet can trust

<!-- example: examples/pricing/quote_client.py mode=script -->
<!-- finder: reproduce a contract's quote off-chain, to the unit -->

```python
"""Quote a swap from a client, without re-implementing the contract wrong.

The pairing is the point. A wallet that shows a number the chain will not
honour is worse than one that shows nothing, and the only way to be sure is
to reproduce the contract's arithmetic exactly -- including which way each
division leans. Integers for anything the user will act on; floats only for
something a human reads.
"""

FEE_BPS = 30
BPS = 10_000


def amount_out(amount_in: int, res_in: int, res_out: int) -> int:
    """Floors, because the contract floors. Use this for `min_output`."""
    net = amount_in * (BPS - FEE_BPS)
    return net * res_out // (res_in * BPS + net)


def amount_in_for(wanted_out: int, res_in: int, res_out: int) -> int:
    """Rounds up, because the contract rounds up. Quote this, not one less."""
    if wanted_out >= res_out:
        raise ValueError("not that much liquidity")
    num = res_in * wanted_out * BPS
    den = (res_out - wanted_out) * (BPS - FEE_BPS)
    return -(-num // den)          # Python's ceiling idiom for integers


def display_price(res_in: int, res_out: int) -> float:
    """The one place a float belongs: a number a person reads and nothing else."""
    return res_out / res_in
```

Two things a client quote is usually asked for on top of the amount. **Price impact** is how far the trade moves the price away from the spot rate, which is what a user is deciding about when they look at a big order:

```text
price_impact = abs(spot - effective) / spot
```

where `spot` is the pool's current ratio and `effective` is what the trade actually pays per unit. Like `display_price`, this is a float and it is display-only: it decides what a user is shown, never what a contract settles.

And a pair with no pool between it is routed through one that exists: `TOKEN_A -> ALGO -> TOKEN_B` as two swap calls in one atomic group, so either both legs happen or neither does. Aggregators automate the search for that path.

A wallet that shows a number the chain will not honour is worse than one that shows nothing, because the user acts on it. The only way to be sure is to reproduce the contract's arithmetic exactly, integer division and rounding direction included, which is why `amount_in_for` carries Python's own ceiling idiom rather than `math.ceil` on a float.

`display_price` returns a float, because a price on a screen is read by a person and never acted on by a program. Everything a transaction will carry stays an integer the whole way. Here is the client half against a pool of ten million A and four million B:

```console
>>> amount_out(1, 10_000_000, 4_000_000)
0
>>> amount_out(100, 10_000_000, 4_000_000)
39
>>> amount_out(1_000, 10_000_000, 4_000_000)
398
>>> display_price(10_000_000, 4_000_000)
0.4
```

The deployed contract returns the same three integers for the same three sizes --- the commission's fifth requirement, agreement to the unit. The transcript shows three sizes; the driver in `examples/pricing/two_sided_quote_test.py` checks nine, in both directions, against the contract itself on every build.

## Prices Over Time
Every number so far has been read at an instant. Two things go wrong with instants: the first one, before anybody else has arrived, and any single one, when somebody can afford to move it.

**Example 13-10.** The lock that makes the first deposit safe

<!-- example: examples/pricing/first_depositor.py mode=unit -->
<!-- finder: stop the first depositor from taking the second one's money -->

```python
from algopy import ARC4Contract, GlobalState, UInt64, arc4

# Minted to nobody at open, so `join`'s division cannot be driven to zero.
MINIMUM_LIQUIDITY = 1_000


class Mint(ARC4Contract):
    """Shares for a depositor who is not the first."""
    def __init__(self) -> None:
        self.supply = GlobalState(UInt64(0))
        self.reserve = GlobalState(UInt64(0))

    @arc4.abimethod
    def open(self, deposit: UInt64) -> UInt64:
        assert self.supply.value == UInt64(0), "already open"
        assert deposit > UInt64(MINIMUM_LIQUIDITY), "initial deposit too small"
        self.supply.value = deposit
        self.reserve.value = deposit
        return deposit - UInt64(MINIMUM_LIQUIDITY)

    @arc4.abimethod
    def join(self, deposit: UInt64) -> UInt64:
        assert self.supply.value > UInt64(0), "not open"
        minted = deposit * self.supply.value // self.reserve.value
        # Refuse rather than accept a deposit for nothing. Without this the
        # contract keeps the money and hands back no claim on it.
        assert minted > UInt64(0), "deposit too small for this pool"
        self.supply.value += minted
        self.reserve.value += deposit
        return minted

    @arc4.abimethod
    def donate(self, amount: UInt64) -> None:
        """Anybody may raise the reserve without minting. That is the lever."""
        self.reserve.value += amount
```

Later deposits mint proportionally: your share of the new supply matches your share of the new reserve. That division is the attack surface, because anyone may raise the reserve without minting anything at all. `donate` is that written out honestly, and it has to be a *method*, because this pool tracks its reserve in state. A plain transfer would raise the account's balance and leave `self.reserve` untouched, which is Chapter 7's distinction arriving where it decides an exploit: a pool that reads its balance instead can be donated to by anybody with a payment and no method call at all.

Here is the same contract with no lock and no floor guard:

```python
from algopy import ARC4Contract, GlobalState, UInt64, arc4


class Mint(ARC4Contract):
    """The same contract with no lock and no floor guard."""
    def __init__(self) -> None:
        self.supply = GlobalState(UInt64(0))
        self.reserve = GlobalState(UInt64(0))

    @arc4.abimethod
    def open(self, deposit: UInt64) -> UInt64:   # any deposit, even one unit
        assert self.supply.value == UInt64(0), "already open"
        self.supply.value = deposit
        self.reserve.value = deposit
        return deposit

    @arc4.abimethod
    def join(self, deposit: UInt64) -> UInt64:
        assert self.supply.value > UInt64(0), "not open"
        # Floors to zero once the reserve has been inflated past the supply.
        minted = deposit * self.supply.value // self.reserve.value
        self.supply.value += minted
        self.reserve.value += deposit
        return minted

    @arc4.abimethod
    def donate(self, amount: UInt64) -> None:
        self.reserve.value += amount

    @arc4.abimethod
    def redeem(self, shares: UInt64) -> UInt64:
        paid = shares * self.reserve.value // self.supply.value
        self.supply.value -= shares
        self.reserve.value -= paid
        return paid
```

*Predict: the attacker opens with one unit and then transfers ten million to the pool without minting anything. What does the next depositor's ten million mint them? Commit to a number.*

Open the pool with one unit. Donate ten million. Now the next depositor's ten million mints `10_000_000 * 1 // 10_000_001`, which is **zero**, and the contract keeps the deposit. The attacker holds the only share and redeems the lot. It costs them the donation and returns them the victim's deposit.

Two lines stop it, and they stop it in different places. The `MINIMUM_LIQUIDITY` floor under the supply means collapsing the proportional division now costs an attacker a donation `MINIMUM_LIQUIDITY` times the victim's deposit rather than one merely the size of it. It raises the price of the attack; it does not make it impossible, and Example 13-10's own tests show a locked pool still flooring to zero against a large enough donation. The `assert minted > UInt64(0)` is what catches the case somebody is still willing to pay for: it refuses a deposit it cannot credit rather than swallowing it. Neither line is sufficient alone, which is why both are there.

::: {.gotcha #first-depositor-donation topic="Pricing math" title="An empty pool is an attack surface, and the first depositor owns it"}
A pool that mints shares in proportion to reserves can be opened with a single unit, inflated by a direct transfer that mints nothing, and then handed a victim's deposit that rounds to zero shares, leaving the attacker holding the only claim on both. The defence is two lines that do different jobs: burn a fixed minimum of shares to nobody at creation, which multiplies the donation the attack needs by that minimum, *and* refuse any deposit that would mint zero rather than accepting it. The first raises the price; only the second closes the door. The lock is not free, since the reserve behind those burned shares is unclaimable for the life of the pool, so it is a trade and the first depositor is the one who pays for it.
:::

**Example 13-11.** A price multiplied by the time it held

<!-- example: examples/pricing/price_accrual.py mode=unit -->
<!-- finder: accumulate a price so any two readings give an average -->

```python
from algopy import (ARC4Contract, BigUInt, Global, GlobalState, UInt64, arc4,
                    op)

MAX_UINT64 = 18_446_744_073_709_551_615


class Accrual(ARC4Contract):
    """A price multiplied by the time it held, added up."""
    def __init__(self) -> None:
        self.cumulative = GlobalState(BigUInt(0))
        self.last_update = GlobalState(UInt64(0))
        self.price = GlobalState(UInt64(0))

    @arc4.abimethod
    def touch(self, new_price: UInt64) -> None:
        """Take a scaled price; credit the interval to the one it replaces."""
        now = Global.latest_timestamp
        last = self.last_update.value
        if last > UInt64(0) and now > last:
            # The price that HELD over the interval, credited before it is
            # replaced. The new one did not exist for any of that time.
            self.cumulative.value += (BigUInt(self.price.value)
                                      * BigUInt(now - last))
        self.last_update.value = now
        self.price.value = new_price

    @arc4.abimethod(readonly=True)
    def average_since(self, past: arc4.UInt512, past_time: UInt64) -> UInt64:
        """Two snapshots differenced over their gap."""
        assert self.last_update.value > past_time, "no interval"
        gap = BigUInt(self.last_update.value - past_time)
        mean = (self.cumulative.value - past.as_biguint()) // gap
        # Not provable: the caller picks the snapshot, so nothing bounds this.
        assert mean <= BigUInt(MAX_UINT64), "average does not fit a UInt64"
        return op.btoi(mean.bytes)
```

A spot price is whatever the last trade left behind, and one trade is cheap. The repair is to stop reading instants: accumulate price × elapsed, and let any two snapshots give the mean between them by subtraction. Manipulating that costs the attacker the whole window rather than one block, and the cost scales with the window. The "now" in `touch` is `Global.latest_timestamp` --- of Chapter 6's four now-shaped values, the timestamp the ledger supplies rather than anything the caller wrote, and the right clock here because the accrual is priced in seconds, not rounds.

The accrual happens *before* the stored price is replaced, because the price credited with an interval must be the one that held over it. Here is the same method with those two lines swapped:

```python
from algopy import ARC4Contract, BigUInt, Global, GlobalState, UInt64, arc4


class Accrual(ARC4Contract):
    """The same accrual, crediting the interval to the wrong price."""
    def __init__(self) -> None:
        self.cumulative = GlobalState(BigUInt(0))
        self.last_update = GlobalState(UInt64(0))
        self.price = GlobalState(UInt64(0))

    @arc4.abimethod
    def touch(self, new_price: UInt64) -> None:
        now = Global.latest_timestamp
        last = self.last_update.value
        self.price.value = new_price            # replaced first, and that is
        if last > UInt64(0) and now > last:     # the whole of the defect
            self.cumulative.value += (BigUInt(self.price.value)
                                      * BigUInt(now - last))
        self.last_update.value = now
```

That is the ordering error every such loop invites, and it is silent: no assert fires and no number looks wrong. On a single hour during which the price went from one to five, the two accumulators differ by a factor of five, and the example's tests say so. And the accumulator is a `BigUInt` while the price is not, which is Example 13-4's rule arriving where it was always headed.

The scale factor sets the overflow horizon. At the 10^9^ scale, a steady price of one gives the cumulative centuries of `UInt64` headroom; at the 10^18^ scale a reader arriving from Solidity reaches for by reflex, it overflows in under a minute. A price far from one shortens both in proportion --- a ratio of a million turns years into hours. That is the other half of why the accumulator is wide, and why the snapshot a caller hands back to `average_since` is 512 bits rather than 64.

The last price in this chapter is not one a contract quotes. It is the number an LP reads before deciding to provide at all, and it belongs on the same side of the wire as `display_price`.

**Example 13-12.** What providing cost, against holding

<!-- finder: compute what an LP gave up by providing rather than holding -->

```python
"""What providing liquidity cost, measured against simply holding.

No contract computes this. It prices a decision, not a settlement, so it
lives in the client next to `display_price` --- and by Example 13-9's rule,
a number only a person reads is the one place a float belongs.
"""

import math


def value_ratio(price_ratio: float) -> float:
    """Pool value over hold value: two roots over one plus the ratio."""
    return 2 * math.sqrt(price_ratio) / (1 + price_ratio)
```

An LP whose pool's price ratio has moved ends up with less than they would have had holding the two assets, and the gap depends only on how far the ratio moved. Two roots over one plus the ratio is the whole formula. A doubling costs 5.7%, a five-fold move 25.5%, and a halving costs exactly what a doubling does, because the expression is symmetric in the ratio and its reciprocal.

Nothing about it is impermanent once the position is closed. The name is a historical accident; the arithmetic is not, and it is what fees have to beat for providing liquidity to have been worth doing.

Deliberately, there is no contract behind this example: a pool gains nothing by spending opcode budget on a judgement its LPs make before they ever send a transaction, and Example 13-5 already owns the one square root a pool does settle on.

None of this is a defect in the two-sided quote. It is the reason a pool needs more than a correct one to survive contact with people who read its code.

## Completing the Quote
Two changes complete it, and the second is the one that would have survived longer. Here is the spine of the diff, with comments and docstrings elided; Example 13-13 is the whole repaired file it lands in.

```diff
-    @subroutine
-    def _price(self) -> UInt64:
-        return self.reserve_b.value // self.reserve_a.value
-
-    @arc4.abimethod(readonly=True)
-    def quote_in_to_out(self, amount_in: UInt64) -> UInt64:
-        net = amount_in * UInt64(BPS - FEE_BPS) // UInt64(BPS)
-        return net * self._price()
+    @subroutine
+    def _amount_out(
+        self, amount_in: UInt64, res_in: UInt64, res_out: UInt64
+    ) -> UInt64:
+        net = BigUInt(amount_in) * BigUInt(BPS - FEE_BPS)
+        out = net * BigUInt(res_out) // (BigUInt(res_in) * BigUInt(BPS) + net)
+        return op.btoi(out.bytes)

-        gross = amount_out * self.reserve_a.value // self.reserve_b.value
-        return gross * UInt64(BPS) // UInt64(BPS - FEE_BPS)
+        num = BigUInt(res_in) * BigUInt(amount_out) * BigUInt(BPS)
+        den = BigUInt(res_out - amount_out) * BigUInt(BPS - FEE_BPS)
+        need = (num + den - BigUInt(1)) // den
```

**Example 13-13.** The two-sided quote, repaired

<!-- example: examples/pricing/two_sided_quote.py mode=unit -->
<!-- finder: quote both directions of a swap without ever forming a price -->

```python
from algopy import ARC4Contract, BigUInt, GlobalState, UInt64, arc4, op, subroutine

FEE_BPS = 30
BPS = 10_000
MAX_UINT64 = 18_446_744_073_709_551_615


class PriceQuote(ARC4Contract):
    """Quote both directions of a swap, each rounded against the asker."""

    def __init__(self) -> None:
        self.reserve_a = GlobalState(UInt64(0))
        self.reserve_b = GlobalState(UInt64(0))

    @arc4.abimethod
    def seed(self, a: UInt64, b: UInt64) -> None:
        assert self.reserve_a.value == UInt64(0), "already seeded"
        assert a > UInt64(0) and b > UInt64(0), "a pool needs both sides"
        self.reserve_a.value = a
        self.reserve_b.value = b

    @subroutine
    def _amount_out(
        self, amount_in: UInt64, res_in: UInt64, res_out: UInt64
    ) -> UInt64:
        """What comes out. Floors, so the remainder stays with the pool.

        No price is formed anywhere in here. That is the repair for the
        truncating ratio: not a wider ratio, but an expression that never
        divides until the last step.
        """
        net = BigUInt(amount_in) * BigUInt(BPS - FEE_BPS)
        out = net * BigUInt(res_out) // (BigUInt(res_in) * BigUInt(BPS) + net)
        # Eight bytes or fewer by construction: the fraction multiplying
        # res_out is strictly below one, so out < res_out, and res_out is a
        # UInt64. An unexplained absent bound reads as an oversight.
        return op.btoi(out.bytes)

    @subroutine
    def _amount_in(
        self, amount_out: UInt64, res_in: UInt64, res_out: UInt64
    ) -> UInt64:
        """What must go in. Rounds UP, because this decides what ENTERS."""
        assert amount_out < res_out, "not that much liquidity"
        num = BigUInt(res_in) * BigUInt(amount_out) * BigUInt(BPS)
        den = BigUInt(res_out - amount_out) * BigUInt(BPS - FEE_BPS)
        # The ceiling idiom over integers. Rounding down here would let the
        # asker pay less than the curve requires, which lowers the product
        # the pool exists to defend.
        need = (num + den - BigUInt(1)) // den
        # Not provable this time: as amount_out approaches res_out the
        # denominator collapses and the quote runs away. Say so out loud.
        assert need <= BigUInt(MAX_UINT64), "quote does not fit a UInt64"
        return op.btoi(need.bytes)

    @arc4.abimethod(readonly=True)
    def quote_in_to_out(self, amount_in: UInt64) -> UInt64:
        """How much B comes out if I send amount_in of A?"""
        assert self.reserve_a.value > UInt64(0), "not seeded"
        return self._amount_out(
            amount_in, self.reserve_a.value, self.reserve_b.value
        )

    @arc4.abimethod(readonly=True)
    def quote_out_to_in(self, amount_out: UInt64) -> UInt64:
        """How much A must I send to get amount_out of B?"""
        assert self.reserve_a.value > UInt64(0), "not seeded"
        return self._amount_in(
            amount_out, self.reserve_a.value, self.reserve_b.value
        )
```

The first defect does not get a wider price. It gets **no price at all**. `_amount_out` never forms a ratio; it multiplies everything that has to be multiplied and divides exactly once, at the end, so there is no truncating intermediate left to compute.

The second repair is a single operator: the ceiling. `quote_out_to_in` decides what enters the contract, so its fraction is charged rather than forgiven, and the product the pool exists to defend stops falling.

Three things sit outside that hunk. The `BigUInt` and `op` imports arrive, because the repaired arithmetic needs both. `MAX_UINT64` arrives as a named constant for the one bound that is not provable: as `amount_out` approaches the reserve, the denominator collapses and the quote runs away, so it is asserted rather than argued. And `_amount_out`'s own bound *is* provable and says so in a comment: the fraction multiplying `res_out` is strictly below one, so the result is below `res_out`, which is a `UInt64` already.

Deploy Example 13-13 and put the same three questions to the same pool:

```console
>>> pool.send.seed(args=(5_000_000, 2_000_000))
>>> pool.send.quote_in_to_out(args=(1_000,)).abi_return
398
>>> pool.send.quote_in_to_out(args=(1_000_000,)).abi_return
332499
>>> pool.send.quote_out_to_in(args=(1,)).abi_return
3
>>> (5_000_000 + 3) * (2_000_000 - 1)      # the product after
10000000999997
>>> 5_000_000 * 2_000_000                   # the product before
10000000000000
```

Every answer changed. A thousand units buys 398 where the first pass paid nothing, a million buys 332,499, and one unit of B costs three units of A rather than two --- the ceiling charging a fraction the floor was forgiving. That last trade raised the product by 999,997; the same trade at the first pass's quote lowered it by 1,000,002.

Against the commission: both questions answered --- yes, and the run above is the two of them answering. The fee into the reserves --- yes: the net-of-fee amount is all the curve is shown, so what the fee withholds stays behind. The edges refused by name --- yes: `"not seeded"` where the first pass died in a bare division by zero, and `"not that much liquidity"` kept from the first pass. No quote lowers the product --- yes, and not by inspection: the fixed version's tests assert the invariant across four trade sizes, in both directions. Agreement with the client to the unit --- yes: Example 13-9 floors where this floors and ceils where this ceils, and the driver behind its transcript checks nine sizes each way. Five for five, and the number a wallet quotes is now one the chain will settle.

The rounding direction and the empty pool are both in Appendix C with the rest. The pattern underneath them is the same: **arithmetic that is correct in the sense the compiler cares about can still be wrong in the sense your users care about, and the two failures look identical in a test suite.** A floored charge and a ceiled one agree on every input that divides exactly. A pool with a lock and one without behave identically until somebody opens an empty one on purpose. In both cases the test that would have caught it is the test nobody writes, because it encodes an adversary rather than a use case.

## Retrieval
Answer from memory before looking anything up.

1. Why is a ratio of two integers not a price, and what two things must you supply before it becomes one?
2. *(From Chapter 6)* You were told to floor a division that decides how much leaves the contract. State the other half of that rule and say which direction it applies to.
3. A contract needs the product of two `UInt64`s and then divides it back down to something small. Does that want `BigUInt` or the wide-multiply pair, and what is the rule you used to decide?
4. Where does a constant-product pool's fee go, and who receives it?
5. A pool mints shares in proportion to reserves. Describe the attack an empty one enables, and name the two separate lines that stop it.
6. *(From Chapter 7)* The minimum-liquidity lock leaves a residue no holder can ever redeem. In a pool holding real assets, which account is actually holding that value, and for how long?
7. Why does a price accumulator credit the interval to the *old* price rather than the new one?
8. A wallet computes a quote and the chain computes a different one, by a single unit. Name the likeliest cause.

## Exercises

1. **(Trace)** Take Example 13-1 and a pool holding 5,000,000 of A and 2,000,000 of B. By hand, compute `quote_out_to_in(1)` line by line, then compute the product of the reserves before and after a trade at that quote. Then do the same for the repaired version at the end of the chapter. Show every intermediate; the interesting one is where the two diverge.

2. **(Parsons)** The lines below implement `owed` from Example 13-6, in the wrong order. Put them in the right one, and say which single line would have to change to turn it back into the wrong variant.

   ```text
       return (shares * reserve + supply - UInt64(1)) // supply
       assert supply > UInt64(0), "no supply"
   ```

3. **(Debug)** The unlocked variant of Example 13-10 has two missing defences, and a colleague proposes fixing both by rejecting `donate` entirely.

   a. Explain why that does not work: what can an attacker do instead?
   b. Say what rejecting donations would break even if it did work.

4. **(Compare)** Example 13-3 and Example 13-4 both handle a number too large for the obvious type, and they do it differently.

   a. Build a table with a row for each and columns for: what actually overflows, what the fix costs in opcodes, and what the fix costs in readability.
   b. Name a third case from an earlier chapter that belongs in the table, and say which row it joins.

5. **(Extend)** Example 13-11 accumulates one price. A pool has two directions, and a caller might want either. Add a second accumulator without duplicating the accrual logic, and say what has to be true about `touch` for the two to stay consistent with each other. Then say what happens to both if nobody calls `touch` for a week.

## Before You Continue
- [ ] I can say why a ratio of two integers is not a price, and name the two things that make one
- [ ] I can state the rounding rule for a division that decides what *enters* a contract, and write the ceiling that the AVM has no opcode for
- [ ] I can choose between `BigUInt` and `op.mulw`/`op.divw` by asking whether the stored value or only the intermediate is large
- [ ] I can describe the first-depositor donation attack end to end, and name the two separate lines that stop it
- [ ] I can say why a price accumulator credits an interval to the price that held over it, and what breaks if it does not

## Handoff: What the AMM Project Needs
Chapter 14 builds a constant product market maker: two reserves, an LP token, a swap that walks the curve, and liquidity that arrives and leaves. Every number in it comes from this chapter. Table 13-1 is what it draws on.

: Table 13-1. What Chapter 14 draws on from this chapter

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------------|--------------------------------------|
| Example 13-13 | The swap method's output calculation | The project's swap moves real assets rather than returning a number. Which of the two quote directions does it need, and what does it do with the other? |
| Example 13-5 | Minting LP tokens for the first deposit | The pool has no exchange rate until somebody sets one. Say what the first depositor's shares should be worth, then check whether the geometric mean agrees. |
| Example 13-10 | The `MINIMUM_LIQUIDITY` constant and the guard beside it | The project locks 1,000 shares. Work out what that costs a pool seeded with 10,000 units, and decide whether you would raise or lower it. |
| Example 13-6 | Every division in the swap and in liquidity removal | The project has more than two divisions. For each one, decide which way it leans before you look, and expect at least one to surprise you. |
| Example 13-11 | The optional TWAP section's cumulative price | The project accumulates on every swap, mint and burn. Say why all three, and what would be wrong with accumulating on swaps alone --- your Exercise 5 answer is what the project ships. |
| Example 13-9 | The deployment scripts' expected-output checks | Those scripts assert on exact integers. Say what would have to be true for a float to be safe there, and whether it ever is. |
