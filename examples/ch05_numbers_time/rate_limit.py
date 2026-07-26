from algopy import Account, ARC4Contract, BoxMap, Global, Txn, UInt64, arc4

COOLDOWN_ROUNDS = 100
# 2,500 per-box base plus 400 a byte for 1 prefix + 32 key + 8 value.
BOX_MBR = 2_500 + 400 * (1 + 32 + 8)


class RateLimited(ARC4Contract):
    def __init__(self) -> None:
        self.last_call = BoxMap(Account, UInt64, key_prefix=b"l")

    @arc4.abimethod
    def act(self) -> UInt64:
        previous, seen = self.last_call.maybe(Txn.sender)
        if seen:
            # Compare, never subtract: `Global.round - COOLDOWN_ROUNDS`
            # aborts on a chain younger than the cooldown itself.
            assert Global.round >= previous + UInt64(COOLDOWN_ROUNDS), "cooling"
        else:
            # A new box is charged to the app account, not to the caller.
            # Refuse before the write rather than abort during it.
            app = Global.current_application_address
            assert app.balance >= app.min_balance + BOX_MBR, "underfunded"
        self.last_call[Txn.sender] = Global.round
        return Global.round
