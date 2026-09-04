"""The Chapter 21 workflow, end to end on LocalNet.

    poetry run python -m scripts.run_limit_order_book

Every printed checkpoint below is a row of Table 21-1. The interesting half
of a limit order book is the keeper, and the keeper is off chain: this script
plays both sides -- Alice, who signs orders and never watches them, and the
keeper, which watches everything and holds nobody's key.

It ends by leaving one order resting, so the keeper can also be run as its own
process:

    poetry run python -m scripts.keeper --passes 1
"""

from __future__ import annotations

import json

from algokit_utils import AlgoAmount, AppClientMethodCallParams
from algosdk import mnemonic
from algosdk.error import AlgodHTTPError

from scripts.keeper import (
    RELAY_FILE,
    SESSION_FILE,
    LimitOrderKeeper,
    OrderRelay,
    static_price_feed,
)
from scripts.localnet_helpers import (
    BOX_COST,
    STATUS_NAMES,
    advance_to,
    algo_balance,
    asset_balance,
    assemble_limit_order,
    compile_limit_order,
    create_test_usdc,
    current_round,
    deploy_order_book,
    fund_account,
    genesis_hash,
    get_localnet_algorand,
    opt_account_into_asset,
    order_box_reference,
    order_exists,
    read_next_order_id,
    read_order,
    refusal_source,
    sign_limit_order,
    place_order,
    transfer_asset,
)

MICRO = 1_000_000

# Alice's limit: 0.25 ALGO per USDC, as a rational the AVM can check by
# cross-multiplying instead of dividing.
PRICE_N, PRICE_D = 250_000, 1_000_000
# What the keeper believes it can get for the same USDC elsewhere.
MARKET_N, MARKET_D = 270_000, 1_000_000


def heading(text: str) -> None:
    print(f"\n{text}\n{'-' * len(text)}")


def signature_type(algorand, txid: str) -> str:
    """Which kind of signature authorised a confirmed transaction."""
    info = algorand.client.algod.pending_transaction_info(txid)
    signed = info.get("txn", {})
    for kind in ("lsig", "msig", "sig"):
        if kind in signed:
            return kind
    return "unknown"


def describe(algorand, app_id: int, order_id: int) -> str:
    order = read_order(algorand, app_id, order_id)
    return (
        f"status {STATUS_NAMES[order['status']]}, "
        f"filled {order['filled_amount'] // MICRO} of "
        f"{order['max_amount'] // MICRO} USDC"
    )


def new_order(
    *, algorand, book_client, alice, usdc_id, relay, max_amount, expiry_round
):
    """Compile one program for one order, sign it, register it, publish it."""
    order_id = read_next_order_id(algorand, book_client.app_id)
    compiled = assemble_limit_order(
        algorand,
        compile_limit_order(
            order_book_app_id=book_client.app_id,
            order_id=order_id,
            genesis_hash=genesis_hash(algorand),
            sell_asset=usdc_id,
            buy_asset=0,
            price_n=PRICE_N,
            price_d=PRICE_D,
            max_sell=max_amount,
            expiry_round=expiry_round,
        ),
    )
    lsig = sign_limit_order(compiled, alice)
    assigned = place_order(
        algorand=algorand,
        book_client=book_client,
        seller=alice,
        compiled=compiled,
        sell_asset=usdc_id,
        buy_asset=0,
        price_n=PRICE_N,
        price_d=PRICE_D,
        max_amount=max_amount,
        expiry_round=expiry_round,
    )
    relay.publish(assigned, lsig)
    return assigned, lsig


def main() -> int:
    algorand = get_localnet_algorand()
    admin = algorand.account.localnet_dispenser()

    heading("1. Deploy the order book")
    book_client = deploy_order_book(algorand, admin)
    print(f"Order Book App ID: {book_client.app_id}")
    print(f"Application address: {book_client.app_address}")

    usdc_id = create_test_usdc(algorand, admin)
    alice = algorand.account.random()
    keeper_account = algorand.account.random()
    fund_account(algorand, alice.address, 10 * MICRO)
    fund_account(algorand, keeper_account.address, 200 * MICRO)
    opt_account_into_asset(algorand, alice, usdc_id)
    opt_account_into_asset(algorand, keeper_account, usdc_id)
    transfer_asset(algorand, admin, alice.address, usdc_id, 1_000 * MICRO)
    print(f"Test USDC asset id: {usdc_id}")
    print(f"Alice: {alice.address}")
    print(f"Keeper: {keeper_account.address}")

    relay = OrderRelay(RELAY_FILE)
    keeper = LimitOrderKeeper(
        client=algorand.client.algod,
        app_id=book_client.app_id,
        private_key=keeper_account.private_key,
        price_feed=static_price_feed({(usdc_id, 0): (MARKET_N, MARKET_D)}),
        relay=relay,
    )

    heading("2. Alice places a 500 USDC order at 0.25 ALGO/USDC")
    expiry_round = current_round(algorand) + 5_000
    predicted = read_next_order_id(algorand, book_client.app_id)
    order_id, order_lsig = new_order(
        algorand=algorand, book_client=book_client, alice=alice,
        usdc_id=usdc_id, relay=relay,
        max_amount=500 * MICRO, expiry_round=expiry_round,
    )
    print(f"LogicSig compiled and signed for order id {predicted}")
    print(f"place_order returned id {order_id}")
    print(f"Box deposit paid by Alice: {BOX_COST} microAlgo")

    heading("3. The keeper fills 200 of the 500")
    order = read_order(algorand, book_client.app_id, order_id)
    tx_ids = keeper.execute_fill(order, order_lsig, fill_amount=200 * MICRO)
    print(f"Sell-side signature type: {signature_type(algorand, tx_ids[1])}")
    print(describe(algorand, book_client.app_id, order_id))

    heading("4. The keeper's own pass closes the order")
    alice_algo_before = algo_balance(algorand, alice.address)
    fills = keeper.run(max_passes=1)
    print(f"Fills submitted by one keeper pass: {fills}")
    print(describe(algorand, book_client.app_id, order_id))
    print(
        "Alice received "
        f"{(algo_balance(algorand, alice.address) - alice_algo_before) / MICRO}"
        " ALGO on the closing fill"
    )
    print(
        f"Keeper now holds "
        f"{asset_balance(algorand, keeper_account.address, usdc_id) // MICRO}"
        " USDC"
    )

    heading("5. A cancelled order refuses a fill")
    cancelled_id, cancelled_lsig = new_order(
        algorand=algorand, book_client=book_client, alice=alice,
        usdc_id=usdc_id, relay=relay,
        max_amount=100 * MICRO, expiry_round=expiry_round,
    )
    snapshot = read_order(algorand, book_client.app_id, cancelled_id)
    book_client.send.call(
        AppClientMethodCallParams(
            method="cancel_order",
            args=[cancelled_id],
            sender=alice.address,
            box_references=[order_box_reference(cancelled_id)],
        )
    )
    print(f"Order {cancelled_id}: {describe(algorand, book_client.app_id, cancelled_id)}")
    try:
        keeper.execute_fill(snapshot, cancelled_lsig, fill_amount=100 * MICRO)
    except AlgodHTTPError as exc:
        print("The keeper still holds Alice's signed program. The book refuses:")
        print("  " + refusal_source(algorand, exc).replace("\n", "\n  "))
    else:
        raise SystemExit("a cancelled order was filled")

    heading("6. An expired order is cleaned up")
    # Enough rounds for the compile-sign-place round trip to land: an
    # order that expires in three rounds can expire before it is placed,
    # and `place_order` refuses an expiry that is not in the future.
    short_expiry = current_round(algorand) + 20
    expired_id, _ = new_order(
        algorand=algorand, book_client=book_client, alice=alice,
        usdc_id=usdc_id, relay=relay,
        max_amount=100 * MICRO, expiry_round=short_expiry,
    )
    advance_to(algorand, short_expiry)
    alice_before = algo_balance(algorand, alice.address)
    book_client.send.call(
        AppClientMethodCallParams(
            method="cleanup_expired_order",
            args=[expired_id],
            sender=keeper_account.address,
            box_references=[order_box_reference(expired_id)],
            # 1,000 for the app call, 1,000 for the inner payment it makes:
            # the contract sets that inner fee to zero and pools it here.
            static_fee=AlgoAmount.from_micro_algo(2_000),
        )
    )
    refund = algo_balance(algorand, alice.address) - alice_before
    print(f"Order {expired_id} box deleted: {not order_exists(algorand, book_client.app_id, expired_id)}")
    print(f"Alice's box deposit came back: {refund} microAlgo")

    heading("7. One order left resting for a keeper of its own")
    resting_id, _ = new_order(
        algorand=algorand, book_client=book_client, alice=alice,
        usdc_id=usdc_id, relay=relay,
        max_amount=100 * MICRO, expiry_round=expiry_round,
    )
    # What a keeper reads from its own config: which book, which key, and
    # what it believes the market is paying. Gitignored -- it holds a key.
    algod = algorand.client.algod
    SESSION_FILE.write_text(json.dumps({
        "app_id": book_client.app_id,
        "algod_server": algod.algod_address,
        "algod_token": algod.algod_token,
        "keeper_mnemonic": mnemonic.from_private_key(
            keeper_account.private_key
        ),
        "quotes": {f"{usdc_id}/0": [MARKET_N, MARKET_D]},
    }, indent=2))
    print(f"Order {resting_id} is resting, and its delegation is on the relay.")
    print("Run the keeper as its own process:")
    print("    poetry run python -m scripts.keeper --passes 1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
