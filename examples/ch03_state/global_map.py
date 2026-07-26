from algopy import Account, ARC4Contract, GlobalMap, StateTotals, UInt64, arc4


class Registry(ARC4Contract, state_totals=StateTotals(global_uints=16)):
    def __init__(self) -> None:
        self.credits = GlobalMap(Account, UInt64, key_prefix="c")

    @arc4.abimethod
    def award(self, member: Account, amount: UInt64) -> UInt64:
        total = self.credits.get(member, default=UInt64(0)) + amount
        self.credits[member] = total
        return total
