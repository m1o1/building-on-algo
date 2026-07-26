"""One requirement, two contracts, and only one assertion tells them apart.

The requirement: a withdrawal above the cap must be refused. One of
these contracts refuses. The other quietly pays the cap instead.
"""

from algopy import ARC4Contract, GlobalState, UInt64, arc4

CAP = 100


class ClampingVault(ARC4Contract):
    """Pays whatever it can. A request over the cap comes back reduced."""

    def __init__(self) -> None:
        self.paid = GlobalState(UInt64(0))

    @arc4.abimethod
    def withdraw(self, amount: UInt64) -> UInt64:
        paid = amount if amount <= UInt64(CAP) else UInt64(CAP)
        self.paid.value += paid
        return paid


class RefusingVault(ARC4Contract):
    """Pays the request or refuses it. Never a third thing."""

    def __init__(self) -> None:
        self.paid = GlobalState(UInt64(0))

    @arc4.abimethod
    def withdraw(self, amount: UInt64) -> UInt64:
        assert amount <= UInt64(CAP), "over the cap"
        self.paid.value += amount
        return amount
