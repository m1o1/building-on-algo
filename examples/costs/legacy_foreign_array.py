# book-example: mode=compile
"""The pre-ARC-4 resource form: an index into a foreign array (Appendix B)."""

from algopy import Account, ARC4Contract, Txn, UInt64, arc4


class Legacy(ARC4Contract):
    """The pre-ARC-4 way: an index into a foreign array."""

    @arc4.abimethod(readonly=True)
    def by_index(self, which: UInt64) -> Account:
        # `Txn.accounts(0)` is always the sender, so caller-supplied indexes
        # are one-based in practice. `<=`, not `<`: index 0 is the sender and
        # `num_accounts` counts only the DECLARED accounts.
        assert which <= Txn.num_accounts, "not declared"
        return Txn.accounts(which)
