from algopy import ARC4Contract, UInt64, arc4


class Vault(ARC4Contract):
    @arc4.abimethod(readonly=True)
    def shortfall(self, owed: UInt64, balance: UInt64) -> UInt64:
        # Aborts when the vault is solvent. There is no negative number
        # to return, so the AVM refuses to produce one.
        return owed - balance

    @arc4.abimethod(readonly=True)
    def shortfall_or_zero(self, owed: UInt64, balance: UInt64) -> UInt64:
        # Order the comparison so the subtraction only runs when it can
        # succeed. This is the shape to reach for every time.
        if owed <= balance:
            return UInt64(0)
        return owed - balance
