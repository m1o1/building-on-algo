# book-example: mode=unit
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
