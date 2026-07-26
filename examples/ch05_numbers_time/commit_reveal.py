from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4

# The deployed beacon publishes on multiples of eight, keeping ~1,500.
BEACON_ROUND_MODULUS = 8
MIN_LEAD_ROUNDS = 16
MAX_LEAD_ROUNDS = 1_000


class CommitReveal(ARC4Contract):
    def __init__(self) -> None:
        self.target_round = GlobalState(UInt64(0))
        self.entrants = GlobalState(UInt64(0))

    @arc4.abimethod
    def enter(self) -> UInt64:
        assert self.target_round.value == UInt64(0), "draw is committed"
        self.entrants.value += UInt64(1)
        return self.entrants.value

    @arc4.abimethod
    def commit(self, lead: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.target_round.value == UInt64(0), "already committed"
        assert lead >= UInt64(MIN_LEAD_ROUNDS), "too close to predict"
        assert lead <= UInt64(MAX_LEAD_ROUNDS), "past beacon retention"
        # Round UP: that can only lengthen the lead, never shorten it.
        raw = Global.round + lead
        m = UInt64(BEACON_ROUND_MODULUS)
        self.target_round.value = raw + (m - raw % m) % m
        return self.target_round.value

    @arc4.abimethod(readonly=True)
    def ready(self) -> bool:
        committed = self.target_round.value != UInt64(0)
        return committed and Global.round > self.target_round.value
