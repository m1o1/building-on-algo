from algopy import ARC4Contract, Global, UInt64, arc4


class Treasury(ARC4Contract):
    """Reports the account this application controls.

    Every application has an address derived from its ID. No private
    key exists for it, so the only way value ever leaves it is an
    inner transaction that this code chose to submit.
    """

    @arc4.abimethod(readonly=True)
    def address(self) -> arc4.Address:
        return arc4.Address(Global.current_application_address)

    @arc4.abimethod(readonly=True)
    def held(self) -> UInt64:
        return Global.current_application_address.balance

    @arc4.abimethod(readonly=True)
    def spendable(self) -> UInt64:
        # Everything above the minimum balance. Sending more than this
        # does not overdraw the account; it fails the transaction.
        account = Global.current_application_address
        return account.balance - account.min_balance
