# book-example: mode=compile
from algopy import (Account, ARC4Contract, Global, Txn, UInt64, arc4, gtxn,
                    itxn)

SHARES = 3


class Splitter(ARC4Contract):
    """Split an incoming payment three ways. Every remainder has a destination."""

    a: Account
    b: Account
    c: Account
    dust: UInt64

    @arc4.abimethod
    def configure(self, a: Account, b: Account, c: Account) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        self.a = a
        self.b = b
        self.c = c
        self.dust = UInt64(0)

    @arc4.abimethod
    def split(self, payment: gtxn.PaymentTransaction) -> UInt64:
        assert payment.receiver == Global.current_application_address, "not ours"
        # The caller covers this call and the three inner payments it causes.
        assert Txn.fee >= Global.min_txn_fee * UInt64(1 + SHARES), "underpaid"
        share = payment.amount // UInt64(SHARES)
        # The remainder stays here, named, instead of blurring into the balance.
        self.dust += payment.amount - share * UInt64(SHARES)
        for who in (self.a, self.b, self.c):
            # fee=0 is a decision: the group's pooled fees pay, not the contract.
            itxn.Payment(receiver=who, amount=share, fee=UInt64(0)).submit()
        return share
