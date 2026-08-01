"""LocalNet tests for the hybrid limit order system --- Table 21-7, row by row.

The happy path is two tests. The rest are refusals, because a delegated
LogicSig is defined by what it will not authorise: a missing check leaves no
trace in the program, and every positive test still passes without it.

Each refusal below removes exactly one guard's worth of honesty from an
otherwise valid fill group and asserts the network says no *for the stated
reason*. A refusal arrives as a program counter, so naming the reason means
mapping that counter back through the TEAL to the source line that refused --
`refusal_source` for the order book, `lsig_refusal_source` for one order's
program. Asserting only that something failed would pass with the wrong guard
firing, which is the failure mode Chapter 8 warns about.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from algokit_utils import AlgoAmount, AppClientMethodCallParams
from algosdk import transaction
from algosdk.abi import Method
from algosdk.atomic_transaction_composer import (
    AccountTransactionSigner,
    AtomicTransactionComposer,
    LogicSigTransactionSigner,
    TransactionWithSigner,
)
from algosdk.error import AlgodHTTPError

from scripts.keeper import (
    FILL_ORDER_SIGNATURE,
    ORDER_CANCELLED,
    ORDER_FILLED,
    ORDER_PARTIAL,
    LimitOrderKeeper,
    OrderRelay,
    static_price_feed,
)
from scripts.localnet_helpers import (
    APP_REFUSAL,
    BOX_COST,
    LSIG_REFUSAL,
    advance_to,
    algo_balance,
    assemble_limit_order,
    asset_balance,
    compile_limit_order,
    create_test_usdc,
    current_round,
    deploy_order_book,
    fund_account,
    genesis_hash,
    lsig_refusal_source,
    opt_account_into_asset,
    order_box_reference,
    order_exists,
    place_order,
    read_next_order_id,
    read_order,
    refusal_source,
    sign_limit_order,
    transfer_asset,
)

MICRO = 1_000_000
PRICE_N, PRICE_D = 250_000, 1_000_000       # 0.25 ALGO per USDC
MARKET_N, MARKET_D = 270_000, 1_000_000     # what the keeper can get elsewhere
# Short enough to advance past in a test, long enough that the order does
# not expire during the compile-sign-place round trip that creates it.
SHORT_EXPIRY = 20


@dataclass
class Order:
    id: int
    lsig: transaction.LogicSigAccount
    compiled: object
    expiry_round: int


class System:
    """One deployment plus the accounts that trade on it."""

    def __init__(self, algorand) -> None:
        self.algorand = algorand
        self.admin = algorand.account.localnet_dispenser()
        self.book = deploy_order_book(algorand, self.admin)
        self.usdc = create_test_usdc(algorand, self.admin, total=10**15)

        self.alice = algorand.account.random()
        self.keeper_account = algorand.account.random()
        fund_account(algorand, self.alice.address, 20 * MICRO)
        fund_account(algorand, self.keeper_account.address, 2_000 * MICRO)
        opt_account_into_asset(algorand, self.alice, self.usdc)
        opt_account_into_asset(algorand, self.keeper_account, self.usdc)
        transfer_asset(
            algorand, self.admin, self.alice.address, self.usdc, 10_000 * MICRO
        )

        self.relay = OrderRelay()
        self.keeper = LimitOrderKeeper(
            client=algorand.client.algod,
            app_id=self.book.app_id,
            private_key=self.keeper_account.private_key,
            price_feed=static_price_feed({(self.usdc, 0): (MARKET_N, MARKET_D)}),
            relay=self.relay,
        )

    def new_order(
        self, max_amount: int, *, expiry_delta: int = 5_000,
        genesis: bytes | None = None,
    ) -> Order:
        """Compile, sign, register and publish one order."""
        order_id = read_next_order_id(self.algorand, self.book.app_id)
        expiry_round = current_round(self.algorand) + expiry_delta
        compiled = assemble_limit_order(self.algorand, compile_limit_order(
            order_book_app_id=self.book.app_id,
            order_id=order_id,
            genesis_hash=genesis or genesis_hash(self.algorand),
            sell_asset=self.usdc, buy_asset=0,
            price_n=PRICE_N, price_d=PRICE_D,
            max_sell=max_amount, expiry_round=expiry_round,
        ))
        lsig = sign_limit_order(compiled, self.alice)
        assigned = place_order(
            algorand=self.algorand, book_client=self.book, seller=self.alice,
            compiled=compiled, sell_asset=self.usdc, buy_asset=0,
            price_n=PRICE_N, price_d=PRICE_D, max_amount=max_amount,
            expiry_round=expiry_round,
        )
        self.relay.publish(assigned, lsig)
        return Order(assigned, lsig, compiled, expiry_round)

    def record(self, order: Order) -> dict:
        return read_order(self.algorand, self.book.app_id, order.id)


@pytest.fixture(scope="session")
def system(algorand) -> System:
    return System(algorand)


def submit_fill(
    system: System,
    order: Order,
    fill_amount: int,
    *,
    record: dict | None = None,
    buy_amount: int | None = None,
    cap_last_valid: bool = True,
    asset_close_to: str | None = None,
    rekey_to: str | None = None,
):
    """The keeper's own fill group, with room for exactly one defect.

    Every keyword corresponds to one line of the LogicSig. The defaults
    reproduce `LimitOrderKeeper.execute_fill` transaction for transaction, so
    a test that changes one argument has changed one thing.
    """
    algod = system.algorand.client.algod
    order_record = record if record is not None else system.record(order)
    if buy_amount is None:
        buy_amount = system.keeper.buy_amount_for(order_record, fill_amount)

    sp = algod.suggested_params()
    if cap_last_valid:
        sp.last = min(sp.last, order_record["expiry_round"])
    sp.fee = 0
    sp.flat_fee = True

    keeper_signer = AccountTransactionSigner(system.keeper_account.private_key)

    buy_txn = transaction.PaymentTxn(
        sender=system.keeper.address, sp=sp,
        receiver=order_record["seller"], amt=buy_amount,
    )
    atc = AtomicTransactionComposer()
    atc.add_transaction(TransactionWithSigner(buy_txn, keeper_signer))

    sell_txn = transaction.AssetTransferTxn(
        sender=order_record["seller"], sp=sp,
        receiver=system.keeper.address, amt=fill_amount,
        index=order_record["sell_asset"],
        close_assets_to=asset_close_to, rekey_to=rekey_to,
    )

    sp_fee = algod.suggested_params()
    # Three transactions, none of which makes an inner one: 3,000.
    sp_fee.fee = 3000
    sp_fee.flat_fee = True
    atc.add_method_call(
        app_id=system.book.app_id,
        method=Method.from_signature(FILL_ORDER_SIGNATURE),
        sender=system.keeper.address, sp=sp_fee, signer=keeper_signer,
        method_args=[
            order.id, fill_amount,
            TransactionWithSigner(sell_txn, LogicSigTransactionSigner(order.lsig)),
        ],
        foreign_assets=[order_record["sell_asset"]],
        accounts=[order_record["seller"]],
        boxes=[(system.book.app_id, order_record["box_key"])],
    )
    return atc.execute(algod, wait_rounds=4)


# ---------------------------------------------------------------------------
# The happy path
# ---------------------------------------------------------------------------


def test_full_order_lifecycle(system: System) -> None:
    """Place a 500-USDC order and let the keeper fill it whole."""
    order = system.new_order(500 * MICRO)

    alice_algo_before = algo_balance(system.algorand, system.alice.address)
    keeper_usdc_before = asset_balance(
        system.algorand, system.keeper.address, system.usdc
    )

    system.keeper.execute_fill(system.record(order), order.lsig)

    alice_gained = (
        algo_balance(system.algorand, system.alice.address) - alice_algo_before
    )
    keeper_gained = (
        asset_balance(system.algorand, system.keeper.address, system.usdc)
        - keeper_usdc_before
    )
    record = system.record(order)

    assert alice_gained == 125 * MICRO       # 500 USDC x 0.25 ALGO
    assert keeper_gained == 500 * MICRO
    assert record["status"] == ORDER_FILLED
    assert record["filled_amount"] == 500 * MICRO


def test_partial_fill(system: System) -> None:
    """Fill 400, then the remaining 600 of a 1,000 order."""
    order = system.new_order(1_000 * MICRO)

    submit_fill(system, order, 400 * MICRO)
    after_first = system.record(order)
    assert after_first["status"] == ORDER_PARTIAL
    assert after_first["filled_amount"] == 400 * MICRO

    submit_fill(system, order, 600 * MICRO)
    after_second = system.record(order)
    assert after_second["status"] == ORDER_FILLED
    assert after_second["filled_amount"] == 1_000 * MICRO


# ---------------------------------------------------------------------------
# The refusals
# ---------------------------------------------------------------------------


def test_cancel_prevents_fill(system: System) -> None:
    """The keeper still holds Alice's signed program. The book refuses.

    Cancellation cannot withdraw a signature. It works because the order
    program forces every group that spends Alice's tokens through
    `fill_order`, and `fill_order` reads the status first.
    """
    order = system.new_order(100 * MICRO)
    snapshot = system.record(order)          # the keeper's view, pre-cancel

    system.book.send.call(AppClientMethodCallParams(
        method="cancel_order", args=[order.id], sender=system.alice.address,
        box_references=[order_box_reference(order.id)],
    ))
    assert system.record(order)["status"] == ORDER_CANCELLED

    with pytest.raises(AlgodHTTPError, match=APP_REFUSAL) as caught:
        submit_fill(system, order, 100 * MICRO, record=snapshot)

    assert "order is cancelled or already filled" in (
        refusal_source(system.algorand, caught.value)
    )


def test_expired_order_rejected(system: System) -> None:
    """Past expiry, the round comparison against `expiry_round` refuses.

    Two programs make that comparison, and only one of them can ever be the
    one that fires: the order program caps `last_valid` at `EXPIRY_ROUND`, so
    a group that reaches the contract's `Global.round <= expiry_round` is one
    the network already accepted as live. The keeper caps `last_valid` and
    finds the transaction dead; the group below does not, and meets the
    LogicSig's own guard instead.
    """
    order = system.new_order(100 * MICRO, expiry_delta=SHORT_EXPIRY)
    advance_to(system.algorand, order.expiry_round)

    assert not system.keeper.is_fillable(
        system.record(order), current_round(system.algorand)
    )

    with pytest.raises(AlgodHTTPError, match=LSIG_REFUSAL) as caught:
        submit_fill(system, order, 100 * MICRO, cap_last_valid=False)

    assert "assert Txn.last_valid <= EXPIRY_ROUND" in (
        lsig_refusal_source(order.compiled, caught.value)
    )


def test_overfill_rejected(system: System) -> None:
    """600 filled against a 500-unit order, in two transfers of 400 and 200.

    `MAX_SELL` bounds one transfer; the box record bounds their sum. Each
    transfer below is under `MAX_SELL`, so the seller's program authorises
    both -- and the order book is what refuses, which is the whole reason the
    delegation is pinned to `fill_order` for this order id.
    """
    order = system.new_order(500 * MICRO)
    submit_fill(system, order, 400 * MICRO)

    with pytest.raises(AlgodHTTPError, match=APP_REFUSAL) as caught:
        submit_fill(system, order, 200 * MICRO)

    assert "assert filled + fill_amount <= max_amount" in (
        refusal_source(system.algorand, caught.value)
    )
    assert system.record(order)["filled_amount"] == 400 * MICRO


def test_wrong_price_rejected(system: System) -> None:
    """One base unit short of the limit price, and Alice's own program says no."""
    order = system.new_order(100 * MICRO)
    record = system.record(order)
    underpayment = system.keeper.buy_amount_for(record, 100 * MICRO) - 1

    with pytest.raises(AlgodHTTPError, match=LSIG_REFUSAL) as caught:
        submit_fill(system, order, 100 * MICRO, buy_amount=underpayment)

    assert "PRICE_D >= Txn.asset_amount * PRICE_N" in (
        lsig_refusal_source(order.compiled, caught.value)
    )


def test_safety_checks(system: System) -> None:
    """The theft fields, pinned to the zero address before anything else.

    The sell side is an asset transfer, so the field that would empty Alice's
    holding is `asset_close_to` -- `close_remainder_to` is the payment-side
    twin the same block pins. Without these two lines the group still looks
    like a 100-USDC fill, and takes everything.
    """
    order = system.new_order(100 * MICRO)

    with pytest.raises(AlgodHTTPError, match=LSIG_REFUSAL) as closing:
        submit_fill(system, order, 100 * MICRO,
                    asset_close_to=system.keeper.address)
    assert "assert Txn.asset_close_to == Global.zero_address" in (
        lsig_refusal_source(order.compiled, closing.value)
    )

    with pytest.raises(AlgodHTTPError, match=LSIG_REFUSAL) as rekeying:
        submit_fill(system, order, 100 * MICRO,
                    rekey_to=system.keeper.address)
    assert "assert Txn.rekey_to == Global.zero_address" in (
        lsig_refusal_source(order.compiled, rekeying.value)
    )


def test_wrong_genesis_hash_rejected(system: System) -> None:
    """A delegation compiled for another network cannot be used on this one."""
    order = system.new_order(100 * MICRO, genesis=bytes(32))

    with pytest.raises(AlgodHTTPError, match=LSIG_REFUSAL) as caught:
        submit_fill(system, order, 100 * MICRO)

    assert "assert Global.genesis_hash == GENESIS_HASH" in (
        lsig_refusal_source(order.compiled, caught.value)
    )


def test_cleanup_expired_order(system: System) -> None:
    """The box goes, and the deposit that paid for it comes back."""
    order = system.new_order(100 * MICRO, expiry_delta=SHORT_EXPIRY)
    advance_to(system.algorand, order.expiry_round)

    alice_before = algo_balance(system.algorand, system.alice.address)
    system.book.send.call(AppClientMethodCallParams(
        method="cleanup_expired_order", args=[order.id],
        sender=system.keeper_account.address,
        box_references=[order_box_reference(order.id)],
        # 1,000 for the app call and 1,000 for the inner payment it makes:
        # the contract sets that inner fee to zero and pools it here.
        static_fee=AlgoAmount.from_micro_algo(2_000),
    ))

    refund = algo_balance(system.algorand, system.alice.address) - alice_before
    assert refund == BOX_COST == 57_700
    assert not order_exists(system.algorand, system.book.app_id, order.id)
