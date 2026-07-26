from algopy import ARC4Contract, Asset, Global, Txn, UInt64, arc4, itxn


class Roles(ARC4Contract):
    """Reports an asset's four authorities, and ends one of them.

    Manager reconfigures, reserve is a label, freeze can suspend an
    account's holding, and clawback can move units without the
    holder's signature. Clearing a role address is permanent.
    """

    @arc4.abimethod(readonly=True)
    def authorities(self, token: Asset) -> arc4.Tuple[
        arc4.Address, arc4.Address, arc4.Address, arc4.Address
    ]:
        return arc4.Tuple((
            arc4.Address(token.manager),
            arc4.Address(token.reserve),
            arc4.Address(token.freeze),
            arc4.Address(token.clawback),
        ))

    @arc4.abimethod
    def renounce_clawback(self, token: Asset) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        # An AssetConfig writes all four roles at once. Every address
        # you want to survive has to be named again here; `clawback`
        # is left out on purpose, and cannot be restored afterwards.
        itxn.AssetConfig(
            config_asset=token,
            manager=token.manager,
            reserve=token.reserve,
            freeze=token.freeze,
            fee=UInt64(0),
        ).submit()
