# book-example: mode=unit
from algopy import ARC4Contract, GlobalState, UInt64, arc4

# Minted to nobody at open, so `join`'s division cannot be driven to zero.
MINIMUM_LIQUIDITY = 1_000


class Mint(ARC4Contract):
    """Shares for a depositor who is not the first."""
    def __init__(self) -> None:
        self.supply = GlobalState(UInt64(0))
        self.reserve = GlobalState(UInt64(0))

    @arc4.abimethod
    def open(self, deposit: UInt64) -> UInt64:
        assert self.supply.value == UInt64(0), "already open"
        assert deposit > UInt64(MINIMUM_LIQUIDITY), "initial deposit too small"
        self.supply.value = deposit
        self.reserve.value = deposit
        return deposit - UInt64(MINIMUM_LIQUIDITY)

    @arc4.abimethod
    def join(self, deposit: UInt64) -> UInt64:
        assert self.supply.value > UInt64(0), "not open"
        minted = deposit * self.supply.value // self.reserve.value
        # Refuse rather than accept a deposit for nothing. Without this the
        # contract keeps the money and hands back no claim on it.
        assert minted > UInt64(0), "deposit too small for this pool"
        self.supply.value += minted
        self.reserve.value += deposit
        return minted

    @arc4.abimethod
    def donate(self, amount: UInt64) -> None:
        """Anybody may raise the reserve without minting. That is the lever."""
        self.reserve.value += amount
