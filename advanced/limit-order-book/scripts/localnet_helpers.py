"""LocalNet plumbing shared by the runbook and the tests (Chapter 21).

Nothing here is part of the system being taught: it is the deploy-fund-compile
scaffolding the chapter's walkthrough spells out inline, factored out so the
runbook and the test suite start from the same pieces.

The one part worth reading on its own is `refusal_source`. Every refusal in
this project arrives as a program counter: the sentence the contract's assert
carries travels in the ARC-56 file, not on the wire. Mapping pc -> TEAL line
-> the Python source PuyaPy left in a comment above it is what turns
"assert failed pc=469" back into "fill exceeds the remainder".
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path

from algokit_utils import (
    AlgoAmount,
    AlgorandClient,
    AppClient,
    AppClientMethodCallParams,
    AssetCreateParams,
    AssetOptInParams,
    AssetTransferParams,
    PaymentParams,
)
from algokit_utils.models.account import SigningAccount
from algosdk import encoding, transaction
from algosdk.error import AlgodHTTPError
from algosdk.source_map import SourceMap

from scripts.keeper import unpack_order

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = PROJECT_ROOT / "smart_contracts" / "artifacts"
APP_SPEC = ARTIFACTS / "limit_order_book" / "LimitOrderBook.arc56.json"
TEAL_TEMPLATE = ARTIFACTS / "limit_order_lsig" / "limit_order.teal"

# 2,500 + 400 x (10-byte name + 128-byte record): Chapter 5's box formula
# against this box's exact dimensions.
BOX_COST = 57_700
BOX_PREFIX = b"o_"

STATUS_NAMES = {1: "ACTIVE", 2: "FILLED", 3: "CANCELLED", 4: "PARTIAL"}


def get_localnet_algorand() -> AlgorandClient:
    algorand = AlgorandClient.default_localnet()
    try:
        algorand.client.algod.status()
    except Exception as exc:  # noqa: BLE001 - reported, not swallowed
        raise RuntimeError(
            "LocalNet is not reachable. Start it with `algokit localnet start`."
        ) from exc
    return algorand


def require_artifacts() -> None:
    """Fail with the build command rather than with a FileNotFoundError."""
    missing = [p.name for p in (APP_SPEC, TEAL_TEMPLATE) if not p.exists()]
    if missing:
        raise RuntimeError(
            f"Missing build artifacts ({', '.join(missing)}). "
            "Run `algokit project run build` first."
        )


# ---------------------------------------------------------------------------
# Accounts, assets, rounds
# ---------------------------------------------------------------------------


def fund_account(
    algorand: AlgorandClient, address: str, micro_algo: int = 10_000_000
) -> None:
    dispenser = algorand.account.localnet_dispenser()
    algorand.send.payment(
        PaymentParams(
            sender=dispenser.address,
            receiver=address,
            amount=AlgoAmount.from_micro_algo(micro_algo),
        )
    )


def create_test_usdc(
    algorand: AlgorandClient, creator: SigningAccount, total: int = 10_000_000_000
) -> int:
    return algorand.send.asset_create(
        AssetCreateParams(
            sender=creator.address,
            total=total,
            decimals=6,
            asset_name="Test USDC",
            unit_name="USDC",
        )
    ).asset_id


def opt_account_into_asset(
    algorand: AlgorandClient, account: SigningAccount, asset_id: int
) -> None:
    algorand.send.asset_opt_in(
        AssetOptInParams(sender=account.address, asset_id=asset_id)
    )


def transfer_asset(
    algorand: AlgorandClient,
    sender: SigningAccount,
    receiver: str,
    asset_id: int,
    amount: int,
) -> None:
    algorand.send.asset_transfer(
        AssetTransferParams(
            sender=sender.address,
            receiver=receiver,
            asset_id=asset_id,
            amount=amount,
        )
    )


def algo_balance(algorand: AlgorandClient, address: str) -> int:
    return algorand.client.algod.account_info(address)["amount"]


def asset_balance(algorand: AlgorandClient, address: str, asset_id: int) -> int:
    info = algorand.client.algod.account_info(address)
    for holding in info.get("assets", []):
        if holding["asset-id"] == asset_id:
            return holding["amount"]
    return 0


def current_round(algorand: AlgorandClient) -> int:
    return algorand.client.algod.status()["last-round"]


def genesis_hash(algorand: AlgorandClient) -> bytes:
    """The 32 bytes the LogicSig pins, decoded out of suggested params."""
    return base64.b64decode(algorand.client.algod.suggested_params().gh)


def advance_to(algorand: AlgorandClient, target_round: int) -> None:
    """Move the chain past `target_round`.

    LocalNet in developer mode produces a block per transaction and does not
    tick on its own, so an expiry test that sleeps waits forever. Sending
    anything at all is what advances the round.
    """
    dispenser = algorand.account.localnet_dispenser()
    while current_round(algorand) <= target_round:
        algorand.send.payment(
            PaymentParams(
                sender=dispenser.address,
                receiver=dispenser.address,
                amount=AlgoAmount.from_micro_algo(0),
                note=f"advance-{current_round(algorand)}".encode(),
            )
        )


def order_box_reference(order_id: int) -> bytes:
    return BOX_PREFIX + order_id.to_bytes(8, "big")


# ---------------------------------------------------------------------------
# The order book contract
# ---------------------------------------------------------------------------


def deploy_order_book(
    algorand: AlgorandClient, admin: SigningAccount
) -> AppClient:
    """Create and seed a fresh order book.

    A bare create rather than `factory.deploy()`: a bare create leaves no
    ARC-2 deployment note, so every caller gets its own book instead of
    adopting one an earlier run left behind. The contract has nothing to
    initialise -- no admin, no fee, no pause flag -- so creation is the whole
    of deployment.
    """
    require_artifacts()
    factory = algorand.client.get_app_factory(
        app_spec=APP_SPEC.read_text(),
        default_sender=admin.address,
    )
    book_client, _ = factory.send.bare.create()
    # The application account needs its own 100,000 microAlgo base minimum
    # before it can hold a box. Each order's box deposit arrives later, inside
    # that order's own place_order group.
    algorand.send.payment(
        PaymentParams(
            sender=admin.address,
            receiver=book_client.app_address,
            amount=AlgoAmount.from_micro_algo(200_000),
        )
    )
    return book_client


def read_next_order_id(algorand, app_id: int) -> int:
    """The id the next place_order call will assign."""
    app_info = algorand.client.algod.application_info(app_id)
    for kv in app_info["params"]["global-state"]:
        if base64.b64decode(kv["key"]) == b"next_order_id":
            return kv["value"]["uint"]
    raise LookupError("order book has no next_order_id")


def read_order(algorand: AlgorandClient, app_id: int, order_id: int) -> dict:
    """One order box, decoded with the keeper's own unpacking."""
    name = order_box_reference(order_id)
    raw = base64.b64decode(
        algorand.client.algod.application_box_by_name(app_id, name)["value"]
    )
    return unpack_order(name, raw)


def order_exists(algorand: AlgorandClient, app_id: int, order_id: int) -> bool:
    try:
        read_order(algorand, app_id, order_id)
    except AlgodHTTPError as exc:
        if "box not found" in str(exc).lower():
            return False
        raise
    return True


# ---------------------------------------------------------------------------
# One program per order
# ---------------------------------------------------------------------------


def compile_limit_order(
    *, order_book_app_id: int, order_id: int, genesis_hash: bytes,
    sell_asset: int, buy_asset: int, price_n: int, price_d: int,
    max_sell: int, expiry_round: int,
) -> str:
    """Fill the TEAL template with one order's parameters."""
    teal = TEAL_TEMPLATE.read_text()
    for name, value in {
        "TMPL_ORDER_BOOK_APP_ID": str(order_book_app_id),
        "TMPL_ORDER_ID": str(order_id),
        "TMPL_GENESIS_HASH": "0x" + genesis_hash.hex(),
        "TMPL_SELL_ASSET": str(sell_asset),
        "TMPL_BUY_ASSET": str(buy_asset),
        "TMPL_PRICE_N": str(price_n),
        "TMPL_PRICE_D": str(price_d),
        "TMPL_MAX_SELL": str(max_sell),
        "TMPL_EXPIRY_ROUND": str(expiry_round),
    }.items():
        teal = teal.replace(name, value)
    assert "TMPL_" not in teal, "unreplaced LogicSig template variable"
    return teal


@dataclass
class CompiledOrder:
    """One order's program, as three things that are all the same 32 bytes.

    `program` is what the seller signs, `address` is the escrow address algod
    reports for it, and `hash` is those same bytes raw -- which is the form
    `place_order` stores and the keeper compares against.
    """

    teal: str
    program: bytes
    address: str
    hash: bytes
    source_map: SourceMap


def assemble_limit_order(algorand: AlgorandClient, teal: str) -> CompiledOrder:
    compiled = algorand.client.algod.compile(teal, source_map=True)
    return CompiledOrder(
        teal=teal,
        program=base64.b64decode(compiled["result"]),
        address=compiled["hash"],
        hash=encoding.decode_address(compiled["hash"]),
        source_map=SourceMap(compiled["sourcemap"]),
    )


def sign_limit_order(
    compiled: CompiledOrder, seller: SigningAccount
) -> transaction.LogicSigAccount:
    """The delegation step: the seller's key signs the program bytes.

    There is no revoke. Everything that bounds this delegation is already
    compiled into the program, which is why the expiry and the order id are
    template variables rather than arguments.
    """
    lsig = transaction.LogicSigAccount(compiled.program)
    lsig.sign(seller.private_key)
    return lsig


def place_order(
    *,
    algorand: AlgorandClient,
    book_client: AppClient,
    seller: SigningAccount,
    compiled: CompiledOrder,
    sell_asset: int,
    buy_asset: int,
    price_n: int,
    price_d: int,
    max_amount: int,
    expiry_round: int,
) -> int:
    """Register one order and confirm it got the id its LogicSig was cut for."""
    order_id = read_next_order_id(algorand, book_client.app_id)
    result = book_client.send.call(
        AppClientMethodCallParams(
            method="place_order",
            args=[
                sell_asset, buy_asset, price_n, price_d, max_amount,
                expiry_round,
                compiled.hash,
                PaymentParams(
                    sender=seller.address,
                    receiver=book_client.app_address,
                    amount=AlgoAmount.from_micro_algo(BOX_COST),
                ),
            ],
            sender=seller.address,
            box_references=[order_box_reference(order_id)],
        )
    )
    assigned = result.abi_return
    if assigned != order_id:
        raise RuntimeError(
            f"order book assigned id {assigned} but the LogicSig is bound to "
            f"{order_id}; the signed delegation is unusable"
        )
    return assigned


# ---------------------------------------------------------------------------
# Reading refusals: pc -> TEAL line -> source
# ---------------------------------------------------------------------------


# algod names the two kinds of refusal differently, and the distinction
# matters: a program counter from one program means nothing in the other.
APP_REFUSAL = "logic eval error"
LSIG_REFUSAL = "rejected by logic"


def failing_pc(error: BaseException | str) -> int | None:
    """The program counter algod reported, or None if it reported none."""
    match = re.search(r"pc=(\d+)", str(error))
    return int(match.group(1)) if match else None


def _named_source(teal_lines: list[str], line_index: int, window: int = 15) -> str:
    """The failing opcode plus the source comment PuyaPy wrote above it.

    PuyaPy annotates each group of opcodes with the Python line that produced
    them, so the comment block nearest above the failing opcode is the reason
    for the refusal -- in the reader's own source, not in TEAL.
    """
    if not 0 <= line_index < len(teal_lines):
        return ""
    failing = teal_lines[line_index].strip()
    index = line_index
    for _ in range(window):
        index -= 1
        if index < 0:
            return failing
        if teal_lines[index].strip().startswith("//"):
            break
    else:
        return failing
    end = index + 1
    while index > 0 and teal_lines[index - 1].strip().startswith("//"):
        index -= 1
    comment = [line.strip() for line in teal_lines[index:end]]
    return "\n".join([*comment, failing])


_approval_cache: dict[str, tuple[list[str], SourceMap]] = {}


def _approval_source(algorand: AlgorandClient) -> tuple[list[str], SourceMap]:
    """The order book's TEAL and its pc -> line map, compiled once."""
    if "approval" not in _approval_cache:
        spec = json.loads(APP_SPEC.read_text())
        teal = base64.b64decode(spec["source"]["approval"]).decode()
        compiled = algorand.client.algod.compile(teal, source_map=True)
        _approval_cache["approval"] = (
            teal.split("\n"),
            SourceMap(compiled["sourcemap"]),
        )
    return _approval_cache["approval"]


def refusal_source(algorand: AlgorandClient, error: BaseException | str) -> str:
    """Name the contract source line the order book refused on.

    Every assert in the order book carries a message, and none of them
    reaches a raw SDK submission: what algod puts on the wire is
    `assert failed pc=469`. The message lives in the ARC-56 file, beside the
    TEAL it belongs to. algod's assembler hands back the pc -> line map for
    that TEAL, and PuyaPy left the Python source in a comment above every
    opcode -- which is the difference between a test that asserts a refusal
    happened and one that asserts *which* refusal happened.
    """
    if LSIG_REFUSAL in str(error):
        # A LogicSig's program counter resolves to a perfectly plausible line
        # of the contract's TEAL, and to entirely the wrong reason.
        return ""
    pc = failing_pc(error)
    if pc is None:
        return ""
    teal_lines, source_map = _approval_source(algorand)
    line = source_map.get_line_for_pc(pc)
    if line is None:
        return ""
    return _named_source(teal_lines, line)


def lsig_refusal_source(compiled: CompiledOrder, error: BaseException | str) -> str:
    """The same trick for one order's program, using its own source map."""
    if LSIG_REFUSAL not in str(error):
        return ""
    pc = failing_pc(error)
    if pc is None:
        return ""
    line = compiled.source_map.get_line_for_pc(pc)
    if line is None:
        return ""
    return _named_source(compiled.teal.split("\n"), line)
