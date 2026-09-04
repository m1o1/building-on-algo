"""The off-chain half of the limit order book (Chapter 21, Part 5).

A limit order nobody matches is a box full of bytes. The keeper is what turns
it into a trade: it reads the open orders out of box storage, decides which
ones it can fill at a profit, assembles the three-transaction group the
seller's LogicSig demands, and submits it.

Nothing here is trusted. The keeper chooses the fill amount, the buy-side
amount and the moment, and every one of those choices is checked twice --
once by the seller's LogicSig, which will not authorise a transfer that
underpays, and once by the order book, which will not record a fill against a
cancelled, expired or exhausted order. A keeper that gets its arithmetic
wrong loses a fee and nothing else.

The one thing the keeper needs that is not on chain is the signed LogicSig
itself. `OrderRelay` stands in for that channel: a production deployment
publishes signed delegations to an API or a peer-to-peer network, and the
on-chain record carries only the 32-byte program hash so a keeper can prove
the blob it was handed is the one the seller signed.

Run it against the book `scripts/run_limit_order_book.py` left behind:

    poetry run python -m scripts.keeper --passes 3
"""

import argparse
import base64
import json
import time
from pathlib import Path

from algosdk import account, encoding, logic, mnemonic, transaction
from algosdk.abi import Method
from algosdk.atomic_transaction_composer import (
    AccountTransactionSigner,
    AtomicTransactionComposer,
    LogicSigTransactionSigner,
    TransactionWithSigner,
)
from algosdk.v2client import algod

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SESSION_FILE = PROJECT_ROOT / ".localnet-keeper.json"
RELAY_FILE = PROJECT_ROOT / ".localnet-relay.json"

FILL_ORDER_SIGNATURE = "fill_order(uint64,uint64,axfer)void"

# ---------------------------------------------------------------------------
# Order discovery: the on-chain half, complete.
# ---------------------------------------------------------------------------

ORDER_ACTIVE, ORDER_FILLED, ORDER_CANCELLED, ORDER_PARTIAL = 1, 2, 3, 4

U64_FIELDS = ("sell_asset", "buy_asset", "price_n", "price_d",
              "max_amount", "filled_amount", "status", "expiry_round")


def unpack_order(box_name: bytes, raw: bytes) -> dict:
    """Decode one order box: OrderInfo's fields, laid end to end."""
    order = {
        "id": int.from_bytes(box_name[2:], "big"),  # after the b"o_" prefix
        "seller": encoding.encode_address(raw[0:32]),
        "lsig_hash": raw[96:128],
        "box_key": box_name,
    }
    for i, field in enumerate(U64_FIELDS):
        start = 32 + 8 * i
        order[field] = int.from_bytes(raw[start:start + 8], "big")
    return order


def scan_open_orders(client: algod.AlgodClient, app_id: int) -> list[dict]:
    """Read every order box and keep the fillable ones."""
    orders = []
    for box in client.application_boxes(app_id)["boxes"]:
        # algod returns box names base64-encoded; pass the encoded form
        # straight back and the lookup finds no box, hence no orders.
        name = base64.b64decode(box["name"])
        raw = base64.b64decode(
            client.application_box_by_name(app_id, name)["value"]
        )
        order = unpack_order(name, raw)
        if order["status"] in (ORDER_ACTIVE, ORDER_PARTIAL):
            orders.append(order)
    return orders


# ---------------------------------------------------------------------------
# Distribution: where the signed delegations come from.
# ---------------------------------------------------------------------------


class OrderRelay:
    """The off-chain distribution channel, reduced to a dictionary.

    The relay cannot cheat: the LogicSig it hands out enforces every rule the
    seller cares about. What a relay *can* do is hand out the wrong blob,
    which is why `LimitOrderKeeper.delegation_for` checks the program hash
    against the hash `place_order` recorded on chain.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self.signed: dict[int, transaction.LogicSigAccount] = {}
        if path is not None and path.exists():
            for order_id, blob in json.loads(path.read_text()).items():
                self.signed[int(order_id)] = encoding.msgpack_decode(blob)

    def publish(self, order_id: int, lsig: transaction.LogicSigAccount) -> None:
        self.signed[order_id] = lsig
        if self.path is not None:
            self.path.write_text(json.dumps(
                {str(k): encoding.msgpack_encode(v)
                 for k, v in self.signed.items()},
                indent=2,
            ))

    def get(self, order_id: int) -> transaction.LogicSigAccount | None:
        return self.signed.get(order_id)


# ---------------------------------------------------------------------------
# The keeper: price, assemble, submit, repeat.
# ---------------------------------------------------------------------------


class LimitOrderKeeper:
    """One keeper: one key, one order book, one view of the market."""

    def __init__(
        self,
        client: algod.AlgodClient,
        app_id: int,
        private_key: str,
        price_feed,
        relay: OrderRelay | None = None,
    ) -> None:
        self.client = client
        self.app_id = app_id
        self.private_key = private_key
        self.address = account.address_from_private_key(private_key)
        self.signer = AccountTransactionSigner(private_key)
        self.price_feed = price_feed
        self.relay = relay if relay is not None else OrderRelay()
        self.skipped: list[tuple[int, str]] = []
        self.seen = 0

    # -- discovery ---------------------------------------------------------

    def scan(self) -> list[dict]:
        return scan_open_orders(self.client, self.app_id)

    def delegation_for(self, order: dict) -> transaction.LogicSigAccount | None:
        """Fetch the seller's delegation and prove it is the right one.

        `place_order` recorded the program's hash on chain, and that hash is
        the escrow address of the same bytes -- so `logic.address` over the
        program is the whole check, and it is what makes reading from an
        untrusted relay safe.

        Do NOT reach for `LogicSigAccount.address()` here. On a *delegated*
        LogicSig that method returns the delegator's address rather than the
        program hash, so the comparison fails on a perfectly valid delegation
        and the keeper quietly declines every order it is handed.
        """
        lsig = self.relay.get(order["id"])
        if lsig is None:
            return None
        program_hash = encoding.decode_address(logic.address(lsig.lsig.logic))
        if program_hash != order["lsig_hash"]:
            return None
        return lsig

    # -- pricing -----------------------------------------------------------

    @staticmethod
    def remaining(order: dict) -> int:
        return order["max_amount"] - order["filled_amount"]

    def is_fillable(self, order: dict, current_round: int) -> bool:
        return (
            order["status"] in (ORDER_ACTIVE, ORDER_PARTIAL)
            and self.remaining(order) > 0
            and current_round <= order["expiry_round"]
        )

    @staticmethod
    def is_profitable(order: dict, market: tuple[int, int]) -> bool:
        """Would filling this order leave the keeper better off?

        `price_n / price_d` is what the seller demands per base unit of the
        asset they are selling; `market` is the same rational for what the
        keeper can get for that unit elsewhere. The keeper buys from the
        seller and sells into the market, so it wants the market paying MORE
        than the seller is asking.

        Reverse this comparison and the bot declines every profitable fill
        and takes every losing one -- and no happy-path test notices, because
        a keeper that fills nothing looks exactly like a keeper with nothing
        to fill.
        """
        market_n, market_d = market
        return market_n * order["price_d"] > order["price_n"] * market_d

    @staticmethod
    def buy_amount_for(order: dict, fill_amount: int) -> int:
        """The smallest buy-side amount the order will accept.

        Both the LogicSig and the contract check
        `buy_amount * price_d >= fill_amount * price_n`, so this division
        rounds UP: the seller wins the rounding. Round down and the group is
        refused by the seller's own LogicSig, which reports no reason at all.
        """
        numerator = fill_amount * order["price_n"]
        return -(-numerator // order["price_d"])

    # -- assembly ----------------------------------------------------------

    def execute_fill(
        self,
        order: dict,
        lsig: transaction.LogicSigAccount,
        fill_amount: int | None = None,
    ) -> list[str]:
        """Assemble and submit the three-transaction fill group.

        The layout is fixed by the seller's LogicSig, which asserts both the
        group size and its own index:

            [0] keeper -> seller, the buy side
            [1] seller -> keeper, the sell side, authorised by the LogicSig
            [2] keeper -> order book, fill_order(order_id, fill_amount, [1])

        `fill_order` takes the sell-side transfer as an `axfer` argument, so
        the composer places it immediately before the app call -- the same
        constraint the LogicSig spells out as `group_index == 1`, seen from
        the other side.
        """
        if fill_amount is None:
            fill_amount = self.remaining(order)
        buy_amount = self.buy_amount_for(order, fill_amount)

        sp = self.client.suggested_params()
        # The LogicSig asserts last_valid <= EXPIRY_ROUND, and suggested
        # params routinely overshoot it.
        sp.last = min(sp.last, order["expiry_round"])
        sp.fee = 0
        sp.flat_fee = True  # Fee pooling: the app call covers all three

        # [0] the buy side, from the keeper's own account
        if order["buy_asset"] == 0:
            buy_txn = transaction.PaymentTxn(
                sender=self.address, sp=sp,
                receiver=order["seller"], amt=buy_amount,
            )
        else:
            buy_txn = transaction.AssetTransferTxn(
                sender=self.address, sp=sp,
                receiver=order["seller"], amt=buy_amount,
                index=order["buy_asset"],
            )

        atc = AtomicTransactionComposer()
        atc.add_transaction(TransactionWithSigner(buy_txn, self.signer))

        # [1] the sell side, authorised by the seller's signed program
        sell_txn = transaction.AssetTransferTxn(
            sender=order["seller"], sp=sp,
            receiver=self.address, amt=fill_amount,
            index=order["sell_asset"],
        )
        sell_signer = LogicSigTransactionSigner(lsig)

        # [2] the app call, carrying the whole group's fees: three
        # transactions, no inner transactions, so three minimum fees.
        sp_fee = self.client.suggested_params()
        sp_fee.fee = 3000
        sp_fee.flat_fee = True

        atc.add_method_call(
            app_id=self.app_id,
            method=Method.from_signature(FILL_ORDER_SIGNATURE),
            sender=self.address,
            sp=sp_fee,
            signer=self.signer,
            method_args=[
                order["id"],
                fill_amount,
                TransactionWithSigner(sell_txn, sell_signer),
            ],
            foreign_assets=[order["sell_asset"]],
            accounts=[order["seller"]],
            boxes=[(self.app_id, order["box_key"])],
        )

        result = atc.execute(self.client, wait_rounds=4)
        return list(result.tx_ids)

    def ensure_opted_in(self, asset_id: int) -> None:
        """A keeper cannot receive what it has not opted into (Chapter 7)."""
        holdings = self.client.account_info(self.address).get("assets", [])
        if any(h["asset-id"] == asset_id for h in holdings):
            return
        sp = self.client.suggested_params()
        opt_in = transaction.AssetTransferTxn(
            sender=self.address, sp=sp, receiver=self.address,
            amt=0, index=asset_id,
        )
        txid = self.client.send_transaction(opt_in.sign(self.private_key))
        transaction.wait_for_confirmation(self.client, txid, 4)

    # -- the loop ----------------------------------------------------------

    def poll_once(self) -> int:
        """One pass: scan, decide, fill. Returns the number of fills made.

        Every reason for declining an order is recorded in `self.skipped`
        rather than dropped on the floor. A keeper that silently fills
        nothing is indistinguishable from a keeper that has nothing to fill,
        and the two want very different debugging.
        """
        self.skipped = []
        current_round = self.client.status()["last-round"]
        open_orders = self.scan()
        self.seen = len(open_orders)
        fills = 0
        for order in open_orders:
            if not self.is_fillable(order, current_round):
                self.skipped.append((order["id"], "not fillable"))
                continue
            market = self.price_feed(order["sell_asset"], order["buy_asset"])
            if market is None or not self.is_profitable(order, market):
                self.skipped.append((order["id"], "not profitable"))
                continue
            lsig = self.delegation_for(order)
            if lsig is None:
                self.skipped.append((order["id"], "no matching delegation"))
                continue
            self.ensure_opted_in(order["sell_asset"])
            self.execute_fill(order, lsig)
            fills += 1
        return fills

    def run(self, max_passes: int = 1, interval: float = 2.8) -> int:
        """Poll until `max_passes` is exhausted.

        A production keeper loops forever, once per block -- Algorand blocks
        land in under three seconds, so that is the polling interval. This
        one counts passes so a script or a test can drive it without having
        to kill it.
        """
        total = 0
        for pass_number in range(max_passes):
            if pass_number:
                time.sleep(interval)
            total += self.poll_once()
        return total


def static_price_feed(quotes: dict[tuple[int, int], tuple[int, int]]):
    """A stand-in for a real quote source.

    A production keeper reads this from an AMM's reserves -- the pool from
    Chapter 14 exposes exactly the two numbers needed -- or from an off-chain
    price API. It is a parameter here so the runbook and the tests can decide
    what the market is doing.
    """

    def feed(sell_asset: int, buy_asset: int) -> tuple[int, int] | None:
        return quotes.get((sell_asset, buy_asset))

    return feed


# ---------------------------------------------------------------------------
# Running the keeper as its own process.
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a limit order keeper against LocalNet.",
    )
    parser.add_argument("--app-id", type=int, default=None,
                        help="order book app id (default: from session file)")
    parser.add_argument("--passes", type=int, default=1,
                        help="how many polling passes to make")
    parser.add_argument("--interval", type=float, default=2.8,
                        help="seconds between passes (one Algorand block)")
    args = parser.parse_args(argv)

    if not SESSION_FILE.exists():
        print(
            f"No keeper session at {SESSION_FILE.name}. Run the workflow "
            "first:\n    poetry run python -m scripts.run_limit_order_book"
        )
        return 1

    session = json.loads(SESSION_FILE.read_text())
    app_id = args.app_id or session["app_id"]
    client = algod.AlgodClient(session["algod_token"], session["algod_server"])
    private_key = mnemonic.to_private_key(session["keeper_mnemonic"])
    # The market the runbook told this keeper to assume, keyed by the pair.
    quotes = {(int(pair.split("/")[0]), int(pair.split("/")[1])): tuple(q)
              for pair, q in session["quotes"].items()}

    keeper = LimitOrderKeeper(
        client=client,
        app_id=app_id,
        private_key=private_key,
        price_feed=static_price_feed(quotes),
        relay=OrderRelay(RELAY_FILE),
    )

    print(f"Keeper {keeper.address[:8]}... watching order book {app_id}")
    fills = keeper.run(max_passes=args.passes, interval=args.interval)
    print(f"Open orders on the last pass: {keeper.seen}")
    print(f"Fills submitted: {fills}")
    for order_id, reason in keeper.skipped:
        print(f"  order {order_id}: skipped, {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
