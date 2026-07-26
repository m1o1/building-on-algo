from algopy import ARC4Contract, Global, Txn, UInt64, arc4


class Doubler(ARC4Contract):
    @arc4.abimethod
    def double(self, amount: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "double: creator only"
        assert amount > UInt64(0), "double: amount must be positive"
        assert amount < UInt64(2**63), "double: amount would overflow"
        return amount * UInt64(2)
