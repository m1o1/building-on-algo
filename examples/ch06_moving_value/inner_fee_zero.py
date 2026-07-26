from algopy import ARC4Contract, Account, Global, Txn, UInt64, arc4, itxn

# One app call plus two inner payments is three transactions. At the
# 1,000 microAlgo minimum that is 3,000 microAlgo, and the app call is
# the only one of the three a caller can attach a fee to.
POOLED_FEE = 3_000


class Splitter(ARC4Contract):
    """Pays two accounts, and makes the caller cover all three fees."""

    @arc4.abimethod
    def split(self, a: Account, b: Account, amount: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert Txn.fee >= UInt64(POOLED_FEE), "cover the whole group"
        half = amount // UInt64(2)
        # `fee=UInt64(0)` is already PuyaPy's default. Writing it out
        # says the omission was a decision, not an oversight.
        itxn.Payment(receiver=a, amount=half, fee=UInt64(0)).submit()
        itxn.Payment(
            receiver=b,
            amount=amount - half,
            fee=UInt64(0),
        ).submit()
