# book-example: mode=compile
from algopy import ARC4Contract, GlobalState, UInt64, arc4


class Mint(ARC4Contract):
    """The same contract with no lock and no floor guard."""
    def __init__(self) -> None:
        self.supply = GlobalState(UInt64(0))
        self.reserve = GlobalState(UInt64(0))

    @arc4.abimethod
    def open(self, deposit: UInt64) -> UInt64:   # any deposit, even one unit
        assert self.supply.value == UInt64(0), "already open"
        self.supply.value = deposit
        self.reserve.value = deposit
        return deposit

    @arc4.abimethod
    def join(self, deposit: UInt64) -> UInt64:
        assert self.supply.value > UInt64(0), "not open"
        # Floors to zero once the reserve has been inflated past the supply.
        minted = deposit * self.supply.value // self.reserve.value
        self.supply.value += minted
        self.reserve.value += deposit
        return minted

    @arc4.abimethod
    def donate(self, amount: UInt64) -> None:
        self.reserve.value += amount

    @arc4.abimethod
    def redeem(self, shares: UInt64) -> UInt64:
        paid = shares * self.reserve.value // self.supply.value
        self.supply.value -= shares
        self.reserve.value -= paid
        return paid
