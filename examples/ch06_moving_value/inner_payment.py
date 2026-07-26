from algopy import ARC4Contract, Account, Global, Txn, UInt64, arc4, itxn


class Faucet(ARC4Contract):
    """Sends Algo out of the application's own account."""

    @arc4.abimethod
    def pay(self, recipient: Account, amount: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        account = Global.current_application_address
        headroom = account.balance - account.min_balance
        assert amount <= headroom, "would breach the minimum balance"
        # `.submit()` runs the payment immediately, inside this call.
        # If it fails, this method fails, and nothing before it commits.
        itxn.Payment(
            receiver=recipient,
            amount=amount,
            fee=UInt64(0),
        ).submit()
        return headroom - amount
