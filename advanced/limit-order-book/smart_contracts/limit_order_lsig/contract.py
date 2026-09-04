from algopy import (
    Asset, Application, Bytes, Global, Txn, UInt64, arc4, gtxn, logicsig,
    TemplateVar, TransactionType,
)

@logicsig
def limit_order() -> bool:
    """Delegated LogicSig encoding a limit sell order."""
    # ── Template variables (filled at compile time) ──────────
    ORDER_BOOK_APP_ID = TemplateVar[UInt64]("ORDER_BOOK_APP_ID")
    GENESIS_HASH = TemplateVar[Bytes]("GENESIS_HASH")
    SELL_ASSET = TemplateVar[UInt64]("SELL_ASSET")
    BUY_ASSET = TemplateVar[UInt64]("BUY_ASSET")
    PRICE_N = TemplateVar[UInt64]("PRICE_N")   # Numerator of price
    PRICE_D = TemplateVar[UInt64]("PRICE_D")   # Denominator of price
    MAX_SELL = TemplateVar[UInt64]("MAX_SELL")
    EXPIRY_ROUND = TemplateVar[UInt64]("EXPIRY_ROUND")
    ORDER_ID = TemplateVar[UInt64]("ORDER_ID")

    # ── Safety checks (MANDATORY --- never remove) ──────────
    assert Txn.close_remainder_to == Global.zero_address
    assert Txn.asset_close_to == Global.zero_address
    assert Txn.rekey_to == Global.zero_address
    assert Txn.fee <= UInt64(10_000)
    assert Txn.last_valid <= EXPIRY_ROUND
    assert Global.genesis_hash == GENESIS_HASH

    # ── Transaction type and amount check ────────────────────
    assert Txn.type_enum == TransactionType.AssetTransfer
    assert Txn.xfer_asset == Asset(SELL_ASSET)
    assert Txn.asset_amount <= MAX_SELL
    assert Txn.asset_amount > UInt64(0)

    # ── Group structure validation ───────────────────────────
    # [0] Keeper's buy-side payment, [1] This sell txn, [2] Order book app call
    assert Global.group_size == UInt64(3)
    assert Txn.group_index == UInt64(1)

    # ── Verify the buy-side payment meets the price ──────────
    if BUY_ASSET == UInt64(0):
        assert gtxn.Transaction(0).type == TransactionType.Payment
        assert gtxn.Transaction(0).receiver == Txn.sender
        # Cross-multiply: buy_amount * PRICE_D >= sell_amount * PRICE_N
        assert gtxn.Transaction(0).amount * PRICE_D >= Txn.asset_amount * PRICE_N
    else:
        assert gtxn.Transaction(0).type == TransactionType.AssetTransfer
        assert gtxn.Transaction(0).xfer_asset == Asset(BUY_ASSET)
        assert gtxn.Transaction(0).asset_receiver == Txn.sender
        received = gtxn.Transaction(0).asset_amount
        assert received * PRICE_D >= Txn.asset_amount * PRICE_N

    # ── Bind to the exact order book call ────────────────────
    # gtxn.ApplicationCallTransaction asserts the type is appl
    app_call = gtxn.ApplicationCallTransaction(2)
    assert app_call.app_id == Application(ORDER_BOOK_APP_ID)
    assert app_call.app_args(0) == arc4.arc4_signature(
        "fill_order(uint64,uint64,axfer)void"
    )
    assert app_call.app_args(1) == arc4.UInt64(ORDER_ID).bytes

    return True
