from algopy import ARC4Contract, Global, GlobalState, Txn, UInt64, arc4, itxn

TOTAL_UNITS = 1_000_000_000_000
DECIMALS = 6


class Minter(ARC4Contract):
    """Creates one ASA and remembers its id.

    The application account becomes the asset's creator and holds the
    entire supply, so it needs 100,000 microAlgo of minimum balance
    for the holding before this call can succeed.
    """

    def __init__(self) -> None:
        self.token = GlobalState(UInt64(0))

    @arc4.abimethod
    def mint(self) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.token.value == UInt64(0), "already minted"
        created = itxn.AssetConfig(
            asset_name=b"Tip Jar Token",
            unit_name=b"TIP",
            total=UInt64(TOTAL_UNITS),
            decimals=UInt64(DECIMALS),
            manager=Global.current_application_address,
            fee=UInt64(0),
        ).submit()
        self.token.value = created.created_asset.id
        return self.token.value
