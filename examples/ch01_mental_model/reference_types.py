from algopy import ARC4Contract, Account, Application, Asset, UInt64, arc4


class Introspect(ARC4Contract):
    """Three reference types, three questions only the ledger can answer."""

    @arc4.abimethod(readonly=True)
    def units_held(self, who: Account, token: Asset) -> UInt64:
        assert who.is_opted_in(token), "account has not opted into this asset"
        return token.balance(who)

    @arc4.abimethod(readonly=True)
    def treasury_of(self, other: Application) -> arc4.Address:
        return arc4.Address(other.address)
