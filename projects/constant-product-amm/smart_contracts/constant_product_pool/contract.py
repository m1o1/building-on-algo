from algopy import (
    ARC4Contract,
    Asset,
    BigUInt,
    Global,
    GlobalState,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
    op,
    subroutine,
)

MINIMUM_LIQUIDITY = 1000
TWAP_PRECISION = 10**9
LP_TOKEN_SUPPLY = 2**63


@subroutine
def _calculate_swap_output(
    input_amount: UInt64,
    reserve_in: UInt64,
    reserve_out: UInt64,
) -> UInt64:
    """Return the constant-product output with 0.3% fee."""
    input_fee_high, input_with_fee = op.mulw(input_amount, UInt64(997))
    assert input_fee_high == UInt64(0), "Swap input too large"

    numerator_high, numerator_low = op.mulw(input_with_fee, reserve_out)

    reserve_high, reserve_low = op.mulw(reserve_in, UInt64(1000))
    carry, denominator_low = op.addw(reserve_low, input_with_fee)
    denominator_high = reserve_high + carry

    quotient_high, output_amount, remainder_high, remainder_low = op.divmodw(
        numerator_high,
        numerator_low,
        denominator_high,
        denominator_low,
    )
    assert quotient_high == UInt64(0), "Swap output overflow"
    return output_amount


@subroutine
def _proportional_amount(
    amount: UInt64,
    reserve: UInt64,
    total_supply: UInt64,
) -> UInt64:
    high, low = op.mulw(amount, reserve)
    quotient_high, proportional, remainder_high, remainder_low = op.divmodw(
        high,
        low,
        UInt64(0),
        total_supply,
    )
    assert quotient_high == UInt64(0), "Proportional amount overflow"
    return proportional


class ConstantProductPool(ARC4Contract):
    def __init__(self) -> None:
        self.asset_a = GlobalState(UInt64(0))
        self.asset_b = GlobalState(UInt64(0))
        self.lp_token_id = GlobalState(UInt64(0))
        self.reserve_a = GlobalState(UInt64(0))
        self.reserve_b = GlobalState(UInt64(0))
        self.lp_total_supply = GlobalState(UInt64(0))
        self.locked_liquidity = GlobalState(UInt64(0))
        self.is_bootstrapped = GlobalState(UInt64(0))
        self.cumulative_price_a = GlobalState(BigUInt(0))
        self.cumulative_price_b = GlobalState(BigUInt(0))
        self.twap_last_update = GlobalState(UInt64(0))

    @arc4.baremethod(create="require")
    def create(self) -> None:
        pass

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "Contract is immutable"

    @arc4.abimethod
    def bootstrap(
        self,
        seed_payment: gtxn.PaymentTransaction,
        asset_a: Asset,
        asset_b: Asset,
    ) -> UInt64:
        """Create the LP token and opt the pool into both trading assets."""
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

        assert seed_payment.sender == Txn.sender, "Seed payment sender mismatch"
        assert (
            seed_payment.receiver == Global.current_application_address
        ), "Seed payment receiver is not the pool"
        assert seed_payment.amount >= UInt64(400_000), "Insufficient MBR seed"

        self.asset_a.value = asset_a.id
        self.asset_b.value = asset_b.id

        lp_create = itxn.AssetConfig(
            asset_name=b"CPMM-LP",
            unit_name=b"LP",
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

    @arc4.abimethod
    def add_initial_liquidity(
        self,
        deposit_a: gtxn.AssetTransferTransaction,
        deposit_b: gtxn.AssetTransferTransaction,
    ) -> UInt64:
        """Deposit the first reserves and mint the first transferable LP tokens."""
        assert (
            Global.group_size == UInt64(3)
        ), "Initial liquidity group must be size 3"
        assert self.is_bootstrapped.value == UInt64(1), "Not bootstrapped"
        assert self.lp_total_supply.value == UInt64(0), "Liquidity already exists"

        self._validate_deposit_pair(deposit_a, deposit_b)
        amount_a = deposit_a.asset_amount
        amount_b = deposit_b.asset_amount

        product = BigUInt(amount_a) * BigUInt(amount_b)
        sqrt_product = op.bsqrt(product)
        assert sqrt_product > MINIMUM_LIQUIDITY, "Initial liquidity too small"

        lp_tokens = op.btoi(sqrt_product.bytes) - UInt64(MINIMUM_LIQUIDITY)
        self.reserve_a.value = amount_a
        self.reserve_b.value = amount_b
        self.locked_liquidity.value = UInt64(MINIMUM_LIQUIDITY)
        self.lp_total_supply.value = lp_tokens + UInt64(MINIMUM_LIQUIDITY)
        self.twap_last_update.value = Global.latest_timestamp

        itxn.AssetTransfer(
            xfer_asset=self.lp_token_id.value,
            asset_receiver=Txn.sender,
            asset_amount=lp_tokens,
            fee=UInt64(0),
        ).submit()
        return lp_tokens

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
        self._update_twap()

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
        self._assert_invariant_not_decreased(
            reserve_a,
            reserve_b,
            new_reserve_a,
            new_reserve_b,
        )

        self.reserve_a.value = new_reserve_a
        self.reserve_b.value = new_reserve_b
        itxn.AssetTransfer(
            xfer_asset=output_asset,
            asset_receiver=Txn.sender,
            asset_amount=output_amount,
            fee=UInt64(0),
        ).submit()
        return output_amount

    @arc4.abimethod
    def add_liquidity(
        self,
        deposit_a: gtxn.AssetTransferTransaction,
        deposit_b: gtxn.AssetTransferTransaction,
    ) -> UInt64:
        """Deposit both assets at the current ratio and mint LP tokens."""
        assert Global.group_size == UInt64(3), "Add liquidity group must be size 3"
        assert self.is_bootstrapped.value == UInt64(1), "Not bootstrapped"
        assert self.lp_total_supply.value > UInt64(0), "No liquidity"
        self._update_twap()

        self._validate_deposit_pair(deposit_a, deposit_b)
        amount_a = deposit_a.asset_amount
        amount_b = deposit_b.asset_amount
        total_supply = self.lp_total_supply.value

        lp_from_a = self._quote_lp_tokens(
            amount_a,
            total_supply,
            self.reserve_a.value,
        )
        lp_from_b = self._quote_lp_tokens(
            amount_b,
            total_supply,
            self.reserve_b.value,
        )
        lp_tokens = lp_from_a if lp_from_a < lp_from_b else lp_from_b
        assert lp_tokens > UInt64(0), "Zero LP tokens"

        self.reserve_a.value += amount_a
        self.reserve_b.value += amount_b
        self.lp_total_supply.value = total_supply + lp_tokens

        itxn.AssetTransfer(
            xfer_asset=self.lp_token_id.value,
            asset_receiver=Txn.sender,
            asset_amount=lp_tokens,
            fee=UInt64(0),
        ).submit()
        return lp_tokens

    @arc4.abimethod
    def remove_liquidity(
        self,
        lp_deposit: gtxn.AssetTransferTransaction,
        min_a: UInt64,
        min_b: UInt64,
    ) -> tuple[UInt64, UInt64]:
        """Burn LP tokens and return the caller's proportional reserve share."""
        assert (
            Global.group_size == UInt64(2)
        ), "Remove liquidity group must be size 2"
        assert self.is_bootstrapped.value == UInt64(1), "Not bootstrapped"
        assert self.lp_total_supply.value > UInt64(0), "No liquidity"
        self._update_twap()

        assert lp_deposit.sender == Txn.sender, "LP sender mismatch"
        assert (
            lp_deposit.asset_receiver == Global.current_application_address
        ), "Receiver is not the pool"
        assert (
            lp_deposit.xfer_asset == Asset(self.lp_token_id.value)
        ), "Wrong LP token"
        assert lp_deposit.asset_amount > UInt64(0), "Zero LP amount"

        lp_amount = lp_deposit.asset_amount
        total_supply = self.lp_total_supply.value
        assert (
            lp_amount <= total_supply - self.locked_liquidity.value
        ), "Locked liquidity"

        amount_a = _proportional_amount(
            lp_amount,
            self.reserve_a.value,
            total_supply,
        )
        amount_b = _proportional_amount(
            lp_amount,
            self.reserve_b.value,
            total_supply,
        )
        assert amount_a >= min_a, "Asset A slippage exceeded"
        assert amount_b >= min_b, "Asset B slippage exceeded"
        assert amount_a > UInt64(0), "Zero asset A output"
        assert amount_b > UInt64(0), "Zero asset B output"

        self.reserve_a.value -= amount_a
        self.reserve_b.value -= amount_b
        self.lp_total_supply.value = total_supply - lp_amount

        itxn.AssetTransfer(
            xfer_asset=self.asset_a.value,
            asset_receiver=Txn.sender,
            asset_amount=amount_a,
            fee=UInt64(0),
        ).submit()
        itxn.AssetTransfer(
            xfer_asset=self.asset_b.value,
            asset_receiver=Txn.sender,
            asset_amount=amount_b,
            fee=UInt64(0),
        ).submit()
        return amount_a, amount_b

    @arc4.abimethod(readonly=True)
    def get_twap_price(
        self,
        old_cumulative_a: arc4.UInt512,
        old_timestamp: UInt64,
    ) -> UInt64:
        """Return the average price of asset A in asset B units."""
        now = Global.latest_timestamp
        last = self.twap_last_update.value
        current = self.cumulative_price_a.value
        if last > UInt64(0) and now > last:
            res_a = self.reserve_a.value
            res_b = self.reserve_b.value
            if res_a > UInt64(0) and res_b > UInt64(0):
                delta_t = now - last
                price_a = BigUInt(res_b) * BigUInt(TWAP_PRECISION) // BigUInt(res_a)
                current += price_a * BigUInt(delta_t)

        old = old_cumulative_a.as_biguint()
        assert current > old, "No price data"
        elapsed = now - old_timestamp
        assert elapsed > UInt64(0), "Zero elapsed"

        twap = (current - old) // BigUInt(elapsed)
        assert twap < BigUInt(2**64), "TWAP overflow"
        return op.btoi(twap.bytes)

    @subroutine
    def _validate_deposit_pair(
        self,
        deposit_a: gtxn.AssetTransferTransaction,
        deposit_b: gtxn.AssetTransferTransaction,
    ) -> None:
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
        assert deposit_a.asset_amount > UInt64(0), "Zero asset A"
        assert deposit_b.asset_amount > UInt64(0), "Zero asset B"

    @subroutine
    def _quote_lp_tokens(
        self,
        deposit_amount: UInt64,
        total_supply: UInt64,
        reserve: UInt64,
    ) -> UInt64:
        high, low = op.mulw(deposit_amount, total_supply)
        quotient_high, lp_tokens, remainder_high, remainder_low = op.divmodw(
            high,
            low,
            UInt64(0),
            reserve,
        )
        assert quotient_high == UInt64(0), "LP token overflow"
        return lp_tokens

    @subroutine
    def _assert_invariant_not_decreased(
        self,
        old_reserve_a: UInt64,
        old_reserve_b: UInt64,
        new_reserve_a: UInt64,
        new_reserve_b: UInt64,
    ) -> None:
        old_high, old_low = op.mulw(old_reserve_a, old_reserve_b)
        new_high, new_low = op.mulw(new_reserve_a, new_reserve_b)
        assert (
            new_high > old_high
            or (new_high == old_high and new_low >= old_low)
        ), "Invariant violated"

    @subroutine
    def _update_twap(self) -> None:
        last = self.twap_last_update.value
        now = Global.latest_timestamp
        if last == UInt64(0) or now <= last:
            return

        res_a = self.reserve_a.value
        res_b = self.reserve_b.value
        if res_a == UInt64(0) or res_b == UInt64(0):
            self.twap_last_update.value = now
            return

        delta_t = now - last
        price_a = BigUInt(res_b) * BigUInt(TWAP_PRECISION) // BigUInt(res_a)
        price_b = BigUInt(res_a) * BigUInt(TWAP_PRECISION) // BigUInt(res_b)
        self.cumulative_price_a.value += price_a * BigUInt(delta_t)
        self.cumulative_price_b.value += price_b * BigUInt(delta_t)
        self.twap_last_update.value = now
