from algopy import ARC4Contract, GlobalState, Struct, UInt64, arc4


class Terms(Struct, frozen=True, kw_only=True):
    cliff: UInt64
    duration: UInt64


class Vault(ARC4Contract):
    def __init__(self) -> None:
        self.terms = GlobalState(Terms(cliff=UInt64(100), duration=UInt64(1000)))

    @arc4.abimethod(readonly=True)
    def cliff_round(self) -> UInt64:
        return self.terms.value.cliff
