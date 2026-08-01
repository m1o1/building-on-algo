"""Static checks: the ABI shape, the guards, and the client's arithmetic.

Nothing here needs LocalNet. These are the properties that must hold before a
single transaction is submitted -- the method signatures integrators code
against, the eight guards the delegated program must carry, and the two places
where the keeper's off-chain arithmetic has to agree with the contract's.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BOOK = PROJECT_ROOT / "smart_contracts" / "limit_order_book" / "contract.py"
LSIG = PROJECT_ROOT / "smart_contracts" / "limit_order_lsig" / "contract.py"
ARTIFACTS = PROJECT_ROOT / "smart_contracts" / "artifacts"
APP_SPEC = ARTIFACTS / "limit_order_book" / "LimitOrderBook.arc56.json"
LSIG_TEAL = ARTIFACTS / "limit_order_lsig" / "limit_order.teal"


def read_book() -> str:
    return BOOK.read_text(encoding="utf-8")


def read_lsig() -> str:
    return LSIG.read_text(encoding="utf-8")


def app_spec() -> dict:
    if not APP_SPEC.exists():
        pytest.skip("Run `algokit project run build` first")
    return json.loads(APP_SPEC.read_text(encoding="utf-8"))


def lsig_teal() -> str:
    if not LSIG_TEAL.exists():
        pytest.skip("Run `algokit project run build` first")
    return LSIG_TEAL.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# The ABI surface integrators code against
# ---------------------------------------------------------------------------


def test_arc56_publishes_the_four_documented_signatures() -> None:
    spec = app_spec()
    signatures = {
        method["name"]
        + "("
        + ",".join(arg["type"] for arg in method["args"])
        + ")"
        + method["returns"]["type"]
        for method in spec["methods"]
    }
    assert signatures == {
        "place_order(uint64,uint64,uint64,uint64,uint64,uint64,byte[],pay)uint64",
        "fill_order(uint64,uint64,axfer)void",
        "cancel_order(uint64)void",
        "cleanup_expired_order(uint64)void",
    }


def test_arc56_global_schema_is_one_counter() -> None:
    # `next_order_id` and nothing else: no admin, no fee, no pause flag. A
    # schema cannot be changed after creation, so this is the one number
    # worth pinning.
    assert app_spec()["state"]["schema"]["global"] == {"ints": 1, "bytes": 0}


def test_arc56_declares_the_three_discovery_events() -> None:
    events = {event["name"] for event in app_spec()["events"]}
    assert events == {"NewOrder", "Filled", "Cancelled"}


def test_order_record_is_the_128_bytes_the_mbr_was_paid_for() -> None:
    widths = {"address": 32, "uint64": 8, "byte[32]": 32}
    fields = app_spec()["structs"]["OrderInfo"]
    assert sum(widths[field["type"]] for field in fields) == 128


def test_client_unpacking_agrees_with_the_contract_offsets() -> None:
    """`unpack_order` restates the struct's layout. Keep the two in step."""
    from scripts.keeper import U64_FIELDS, unpack_order

    fields = app_spec()["structs"]["OrderInfo"]
    assert fields[0]["name"] == "seller" and fields[0]["type"] == "address"
    assert tuple(f["name"] for f in fields[1:-1]) == U64_FIELDS
    assert fields[-1]["name"] == "lsig_hash" and fields[-1]["type"] == "byte[32]"

    seller = bytes(range(32))
    words = b"".join(
        (index + 1).to_bytes(8, "big") for index in range(len(U64_FIELDS))
    )
    lsig_hash = bytes(range(100, 132))
    order = unpack_order(b"o_" + (7).to_bytes(8, "big"), seller + words + lsig_hash)

    assert order["id"] == 7
    assert order["lsig_hash"] == lsig_hash
    assert [order[name] for name in U64_FIELDS] == list(
        range(1, len(U64_FIELDS) + 1)
    )


# ---------------------------------------------------------------------------
# The eight-item checklist (Table 21-3)
# ---------------------------------------------------------------------------


def test_logicsig_pins_the_three_theft_fields() -> None:
    source = read_lsig()
    assert "assert Txn.close_remainder_to == Global.zero_address" in source
    assert "assert Txn.asset_close_to == Global.zero_address" in source
    assert "assert Txn.rekey_to == Global.zero_address" in source


def test_logicsig_caps_the_fee_and_expires() -> None:
    source = read_lsig()
    assert "assert Txn.fee <= UInt64(10_000)" in source
    assert "assert Txn.last_valid <= EXPIRY_ROUND" in source


def test_logicsig_binds_to_one_network() -> None:
    source = read_lsig()
    assert "assert Global.genesis_hash == GENESIS_HASH" in source
    assert 'GENESIS_HASH = TemplateVar[Bytes]("GENESIS_HASH")' in source


def test_logicsig_pins_the_group_shape() -> None:
    source = read_lsig()
    assert "assert Global.group_size == UInt64(3)" in source
    assert "assert Txn.group_index == UInt64(1)" in source


def test_logicsig_binds_app_id_method_and_order_id() -> None:
    """App id alone would authorise every method the order book has."""
    source = read_lsig()
    assert "assert app_call.app_id == Application(ORDER_BOOK_APP_ID)" in source
    assert 'arc4.arc4_signature(\n        "fill_order(uint64,uint64,axfer)void"' in source
    assert "assert app_call.app_args(1) == arc4.UInt64(ORDER_ID).bytes" in source


def test_logicsig_reads_no_arguments() -> None:
    """Arguments arrive unsigned; every order parameter is a template variable."""
    source = read_lsig()
    assert "op.arg" not in source
    assert "Txn.application_args" not in source
    declared = set(re.findall(r'TemplateVar\[\w+\]\("(\w+)"\)', source))
    assert declared == {
        "ORDER_BOOK_APP_ID", "GENESIS_HASH", "SELL_ASSET", "BUY_ASSET",
        "PRICE_N", "PRICE_D", "MAX_SELL", "EXPIRY_ROUND", "ORDER_ID",
    }


def test_template_variables_survive_the_build_and_match_the_client() -> None:
    """One program per order: the artifact is a template, not a program.

    The client's substitution table has to cover every placeholder the build
    left behind. Miss one and algod's assembler reports
    `strconv.ParseUint: parsing "TMPL_EXPIRY_ROUND": invalid syntax`.
    """
    from scripts.localnet_helpers import compile_limit_order

    assert len(set(re.findall(r"TMPL_[A-Z_]+", lsig_teal()))) == 9
    filled = compile_limit_order(
        order_book_app_id=1, order_id=2, genesis_hash=bytes(32),
        sell_asset=3, buy_asset=0, price_n=250_000, price_d=1_000_000,
        max_sell=500, expiry_round=100,
    )
    assert "TMPL_" not in filled


def test_logicsig_price_check_is_a_cross_multiplication() -> None:
    """No division, so no quotient, no remainder and no rounding to argue."""
    source = read_lsig()
    assert (
        "assert gtxn.Transaction(0).amount * PRICE_D "
        ">= Txn.asset_amount * PRICE_N" in source
    )
    assert "received * PRICE_D >= Txn.asset_amount * PRICE_N" in source
    code = [line.split("#", 1)[0] for line in source.splitlines()]
    assert not any("//" in line for line in code), "no division anywhere"


# ---------------------------------------------------------------------------
# The order book's own guards
# ---------------------------------------------------------------------------


def test_order_book_validates_both_sides_of_the_trade() -> None:
    source = read_book()
    assert "assert sell_txn.xfer_asset == sell_asset" in source
    assert "assert sell_txn.asset_amount == fill_amount" in source
    assert "assert sell_txn.sender == seller" in source
    assert "assert buy_txn.receiver == seller" in source
    assert "assert buy_txn.asset_receiver == seller" in source
    assert "buy_txn_amount * price_d >= fill_amount * price_n" in source


def test_order_book_bounds_cumulative_fills() -> None:
    """MAX_SELL bounds one transfer; this bounds their sum."""
    source = read_book()
    assert "assert filled + fill_amount <= max_amount" in source
    assert "assert status == UInt64(ORDER_ACTIVE) or status == UInt64(" in source
    assert "assert Global.round <= order.expiry_round.as_uint64()" in source


def test_order_book_guards_group_size_on_both_entry_points() -> None:
    source = read_book()
    assert 'assert Global.group_size == UInt64(2), "expected payment + app call"' in source
    assert 'assert Global.group_size == UInt64(3), "expected buy, sell, this call"' in source


def test_only_the_seller_can_cancel() -> None:
    source = read_book()
    assert 'assert Txn.sender == order.seller.native, "only the seller may cancel"' in source


def test_the_book_has_no_admin_and_no_pause_switch() -> None:
    """ALG-15: the lifecycle stance is immutable, and it is the whole stance.

    A `paused` flag with no method that sets it is not a safety feature, it
    is a line that reads like one. Example 24-7 is where a switch with a
    lever behind it belongs; here there is neither, and no admin to pull it.
    """
    source = read_book()
    for absent in ("paused", "self.admin", "fee_bps"):
        assert absent not in source
    assert "GlobalState" in source and source.count("GlobalState(") == 1


def test_contract_is_immutable() -> None:
    """Half of the LogicSig's security argument lives here.

    A method selector binds to whatever the method comes to mean, so a
    delegation pinned to `fill_order` is only as trustworthy as this refusal.
    """
    source = read_book()
    assert '@arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])' in source
    assert 'assert False, "this order book is immutable"' in source


def test_every_order_book_assert_carries_a_message() -> None:
    """ALG-13: the reader of an assert message is the integrator, not you.

    A bare `assert` reaches a caller as `assert failed pc=469` and nothing
    else. Twenty-eight asserts, twenty-eight sentences somebody can act on.
    """
    bare = [
        node.lineno
        for node in ast.walk(ast.parse(read_book()))
        if isinstance(node, ast.Assert) and node.msg is None
    ]
    assert bare == [], f"bare asserts at lines {bare}"


def test_logicsig_asserts_are_bare_because_there_is_nowhere_to_put_them() -> None:
    """The one deliberate exception to the rule above.

    A LogicSig compiles to TEAL and nothing else -- no ARC-56 file, so no
    place for a message to travel. Every refusal arrives as `rejected by
    logic` plus a program counter, which is why this project maps that
    counter back through the order's own source map instead.
    """
    asserts = [
        node
        for node in ast.walk(ast.parse(read_lsig()))
        if isinstance(node, ast.Assert)
    ]
    assert len(asserts) == 22
    assert all(node.msg is None for node in asserts)


def test_mbr_is_charged_on_the_way_in_and_refunded_on_the_way_out() -> None:
    from scripts.localnet_helpers import BOX_COST

    source = read_book()
    box_cost = "UInt64(2500) + UInt64(400) * (UInt64(10) + UInt64(128))"
    assert source.count(box_cost) == 2      # charged in, refunded out
    assert "mbr_payment.receiver == Global.current_application_address" in source
    assert "assert mbr_payment.amount == box_cost" in source
    assert BOX_COST == 2_500 + 400 * (10 + 128) == 57_700


def test_inner_payment_pools_its_fee_to_the_caller() -> None:
    source = read_book()
    assert "fee=UInt64(0)," in source


def test_division_by_zero_is_guarded_where_the_denominator_is_set() -> None:
    source = read_book()
    assert "assert price_d > UInt64(0)" in source


def test_order_book_announces_every_state_change() -> None:
    source = read_book()
    assert "arc4.emit(NewOrder(" in source
    assert "arc4.emit(Filled(" in source
    assert "arc4.emit(Cancelled(" in source


# ---------------------------------------------------------------------------
# The keeper's arithmetic, where getting it backwards costs money quietly
# ---------------------------------------------------------------------------


def _order(price_n: int = 250_000, price_d: int = 1_000_000) -> dict:
    return {"price_n": price_n, "price_d": price_d,
            "max_amount": 500, "filled_amount": 0}


def test_keeper_fills_only_when_the_market_pays_more_than_the_order_asks() -> None:
    from scripts.keeper import LimitOrderKeeper

    order = _order()
    assert LimitOrderKeeper.is_profitable(order, (270_000, 1_000_000))
    assert not LimitOrderKeeper.is_profitable(order, (250_000, 1_000_000))
    assert not LimitOrderKeeper.is_profitable(order, (240_000, 1_000_000))


def test_keeper_never_reads_the_delegated_address_as_a_program_hash() -> None:
    """Once an lsig is signed, `address()` is the delegator, not the program.

    The keeper proves a relay blob is the right one by comparing its program
    hash against the 32 bytes `place_order` stored. Reach for `address()`
    instead and the comparison is an account against a program hash: every
    valid delegation is declined and nothing anywhere reports an error.
    """
    from algosdk import account, encoding, logic, transaction

    program = bytes([12, 129, 1])          # #pragma version 12; pushint 1
    lsig = transaction.LogicSigAccount(program)
    private_key, delegator = account.generate_account()
    assert lsig.address() == logic.address(program)     # before signing
    lsig.sign(private_key)
    assert lsig.address() == delegator                  # after signing
    assert encoding.decode_address(lsig.address()) != encoding.decode_address(
        logic.address(program)
    )

    keeper_source = (PROJECT_ROOT / "scripts" / "keeper.py").read_text()
    assert "logic.address(lsig.lsig.logic)" in keeper_source
    assert "lsig.address()" not in keeper_source


def test_keeper_rounds_the_buy_side_up() -> None:
    """The seller wins the rounding, because their program does the checking."""
    from scripts.keeper import LimitOrderKeeper

    order = _order()
    for fill_amount in (1, 3, 7, 999_999, 500_000_000):
        buy = LimitOrderKeeper.buy_amount_for(order, fill_amount)
        assert buy * order["price_d"] >= fill_amount * order["price_n"]
        assert (buy - 1) * order["price_d"] < fill_amount * order["price_n"]
