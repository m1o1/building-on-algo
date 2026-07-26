from algopy import ARC4Contract, GlobalState, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.paused_at = GlobalState(UInt64)

    @arc4.abimethod
    def resume(self) -> bool:
        was_paused = bool(self.paused_at)
        del self.paused_at.value
        return was_paused
