from algopy import ARC4Contract, Box, Global, UInt64, arc4


class Vault(ARC4Contract):
    def __init__(self) -> None:
        self.data = Box(UInt64, key=b"d")

    @arc4.abimethod(readonly=True)
    def spendable(self) -> UInt64:
        app = Global.current_application_address
        if app.balance <= app.min_balance:
            return UInt64(0)
        return app.balance - app.min_balance

    @arc4.abimethod
    def open_vault(self) -> None:
        app = Global.current_application_address
        cost = UInt64(2_500) + UInt64(400) * (UInt64(1) + UInt64(8))
        assert app.balance >= app.min_balance + cost, "app account underfunded"
        assert self.data.create(), "already open"
