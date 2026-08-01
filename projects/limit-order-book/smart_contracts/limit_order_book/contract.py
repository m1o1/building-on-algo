import typing

from algopy import (
    ARC4Contract, Asset, BoxMap, Bytes, Global, GlobalState,
    TransactionType, Txn, UInt64, arc4, gtxn, itxn,
)

ORDER_ACTIVE = 1
ORDER_FILLED = 2
ORDER_CANCELLED = 3
ORDER_PARTIAL = 4

LsigHash: typing.TypeAlias = arc4.StaticArray[arc4.Byte, typing.Literal[32]]


class OrderInfo(arc4.Struct):
    seller: arc4.Address
    sell_asset: arc4.UInt64
    buy_asset: arc4.UInt64
    price_n: arc4.UInt64
    price_d: arc4.UInt64
    max_amount: arc4.UInt64
    filled_amount: arc4.UInt64
    status: arc4.UInt64
    expiry_round: arc4.UInt64
    lsig_hash: LsigHash


class NewOrder(arc4.Struct):
    order_id: arc4.UInt64
    seller: arc4.Address
    sell_asset: arc4.UInt64
    buy_asset: arc4.UInt64
    price_n: arc4.UInt64
    price_d: arc4.UInt64
    max_amount: arc4.UInt64


class Filled(arc4.Struct):
    order_id: arc4.UInt64
    fill_amount: arc4.UInt64
    total_filled: arc4.UInt64
    keeper: arc4.Address


class Cancelled(arc4.Struct):
    order_id: arc4.UInt64


class LimitOrderBook(ARC4Contract):
    """An immutable order book: no admin, no pause switch, no upgrade path."""

    def __init__(self) -> None:
        self.next_order_id = GlobalState(UInt64(1))
        # Order storage: order_id -> OrderInfo (128 bytes per order)
        self.orders = BoxMap(arc4.UInt64, OrderInfo, key_prefix=b"o_")

    @arc4.abimethod
    def place_order(
        self,
        sell_asset: UInt64,
        buy_asset: UInt64,
        price_n: UInt64,
        price_d: UInt64,
        max_amount: UInt64,
        expiry_round: UInt64,
        lsig_hash: Bytes,
        mbr_payment: gtxn.PaymentTransaction,
    ) -> UInt64:
        """Register a new limit order."""
        assert Global.group_size == UInt64(2), "expected payment + app call"
        assert price_d > UInt64(0), "price denominator must not be zero"
        assert max_amount > UInt64(0), "order size must be above zero"
        assert expiry_round > Global.round, "expiry must be in the future"
        assert lsig_hash.length == UInt64(32), "lsig hash must be 32 bytes"

        # Verify MBR payment for box storage
        # Box key: 10 bytes (prefix + uint64), box value: 128 bytes
        box_cost = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(128))
        assert (
            mbr_payment.receiver == Global.current_application_address
        ), "pay the box deposit to the order book"
        assert mbr_payment.amount == box_cost, "box deposit is 57,700 exactly"

        order_id = self.next_order_id.value
        self.next_order_id.value = order_id + UInt64(1)

        self.orders[arc4.UInt64(order_id)] = OrderInfo(
            seller=arc4.Address(Txn.sender),
            sell_asset=arc4.UInt64(sell_asset),
            buy_asset=arc4.UInt64(buy_asset),
            price_n=arc4.UInt64(price_n),
            price_d=arc4.UInt64(price_d),
            max_amount=arc4.UInt64(max_amount),
            filled_amount=arc4.UInt64(0),
            status=arc4.UInt64(ORDER_ACTIVE),
            expiry_round=arc4.UInt64(expiry_round),
            lsig_hash=LsigHash.from_bytes(lsig_hash),
        )

        # Announce the order so keepers can discover it
        arc4.emit(NewOrder(
            order_id=arc4.UInt64(order_id),
            seller=arc4.Address(Txn.sender),
            sell_asset=arc4.UInt64(sell_asset),
            buy_asset=arc4.UInt64(buy_asset),
            price_n=arc4.UInt64(price_n),
            price_d=arc4.UInt64(price_d),
            max_amount=arc4.UInt64(max_amount),
        ))

        return order_id

    @arc4.abimethod
    def fill_order(
        self,
        order_id: UInt64,
        fill_amount: UInt64,
        sell_txn: gtxn.AssetTransferTransaction,
    ) -> None:
        """Execute a fill against an open order."""
        assert Global.group_size == UInt64(3), "expected buy, sell, this call"

        order_key = arc4.UInt64(order_id)
        assert order_key in self.orders, "no order with that id"
        # .copy() is required: box storage returns a reference to
        # encoded data.
        order = self.orders[order_key].copy()
        seller = order.seller.native

        # Validate order state
        status = order.status.as_uint64()
        assert status == UInt64(ORDER_ACTIVE) or status == UInt64(
            ORDER_PARTIAL
        ), "order is cancelled or already filled"
        assert Global.round <= order.expiry_round.as_uint64(), "order expired"
        assert fill_amount > UInt64(0), "fill amount must be above zero"
        filled = order.filled_amount.as_uint64()
        max_amount = order.max_amount.as_uint64()
        assert filled + fill_amount <= max_amount, "fill exceeds the remainder"

        # Validate the sell-side transaction (LogicSig authorized)
        sell_asset = Asset(order.sell_asset.as_uint64())
        assert sell_txn.xfer_asset == sell_asset, "wrong asset on the sell side"
        assert sell_txn.asset_amount == fill_amount, "sell side != fill_amount"
        assert sell_txn.sender == seller, "sell side must come from the seller"

        # Validate the buy-side transaction
        buy_txn = gtxn.Transaction(0)
        buy_asset = order.buy_asset.as_uint64()
        if buy_asset == UInt64(0):
            buy_txn_amount = buy_txn.amount
            assert buy_txn.type == TransactionType.Payment, "buy side not a pay"
            assert buy_txn.receiver == seller, "buy side must pay the seller"
        else:
            buy_txn_amount = buy_txn.asset_amount
            assert (
                buy_txn.type == TransactionType.AssetTransfer
            ), "buy side must be an asset transfer for an ASA order"
            assert buy_txn.asset_receiver == seller, "buy side must pay seller"
            assert buy_txn.xfer_asset == Asset(
                buy_asset
            ), "wrong asset on the buy side"

        # Price verification (cross-multiply to avoid division)
        price_n = order.price_n.as_uint64()
        price_d = order.price_d.as_uint64()
        assert (
            buy_txn_amount * price_d >= fill_amount * price_n
        ), "buy side is below the order's limit price"

        # Update filled amount and status
        new_filled = filled + fill_amount
        new_status = (
            UInt64(ORDER_FILLED) if new_filled == max_amount
            else UInt64(ORDER_PARTIAL)
        )
        order.filled_amount = arc4.UInt64(new_filled)
        order.status = arc4.UInt64(new_status)
        self.orders[order_key] = order.copy()

        arc4.emit(Filled(
            order_id=arc4.UInt64(order_id),
            fill_amount=arc4.UInt64(fill_amount),
            total_filled=arc4.UInt64(new_filled),
            keeper=arc4.Address(Txn.sender),
        ))

    @arc4.abimethod
    def cancel_order(self, order_id: UInt64) -> None:
        """Cancel an open order. Only the seller can cancel."""
        order_key = arc4.UInt64(order_id)
        assert order_key in self.orders, "no order with that id"
        order = self.orders[order_key].copy()

        assert Txn.sender == order.seller.native, "only the seller may cancel"

        status = order.status.as_uint64()
        assert status == UInt64(ORDER_ACTIVE) or status == UInt64(
            ORDER_PARTIAL
        ), "order is cancelled or already filled"

        order.status = arc4.UInt64(ORDER_CANCELLED)
        self.orders[order_key] = order.copy()
        arc4.emit(Cancelled(order_id=arc4.UInt64(order_id)))

    @arc4.abimethod
    def cleanup_expired_order(self, order_id: UInt64) -> None:
        """Anyone can clean up an expired order and free the MBR."""
        order_key = arc4.UInt64(order_id)
        assert order_key in self.orders, "no order with that id"
        order = self.orders[order_key].copy()

        assert (
            Global.round > order.expiry_round.as_uint64()
        ), "order has not expired yet"

        seller = order.seller.native
        del self.orders[order_key]

        box_cost = UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(128))
        itxn.Payment(
            receiver=seller,
            amount=box_cost,
            fee=UInt64(0),
        ).submit()

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "this order book is immutable"
