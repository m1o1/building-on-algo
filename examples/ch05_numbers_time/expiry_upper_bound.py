from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4


class Sunset(ARC4Contract):
    """The one safe way to touch `Txn.last_valid`.

    Constraining a caller-chosen value downward costs the caller
    something. Reading it as elapsed time pays the caller instead.
    """

    def __init__(self) -> None:
        self.sunset_round = GlobalState(UInt64(0))

    @arc4.abimethod
    def set_sunset(self, rnd: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.sunset_round.value == UInt64(0), "already set"
        assert rnd > Global.round, "sunset is already behind us"
        self.sunset_round.value = rnd

    @arc4.abimethod
    def use(self) -> UInt64:
        assert self.sunset_round.value != UInt64(0), "not configured"
        assert Global.round < self.sunset_round.value, "sunset passed"
        # Refuse a call that could still be replayed after the sunset.
        assert Txn.last_valid < self.sunset_round.value, "window overruns"
        return Global.round
