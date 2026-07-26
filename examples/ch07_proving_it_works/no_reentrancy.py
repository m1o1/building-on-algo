from algopy import (ARC4Contract, Global, LocalState, Txn, UInt64, arc4, gtxn,
                    itxn)


class Vault(ARC4Contract):
    """Interaction before effects --- and it is still safe.

    `withdraw` pays out and only then zeroes the balance: on the EVM
    that is the reentrancy bug; here nothing gets control back, and
    `itxn_submit` refuses an app already on the stack. Balances sit
    in local state to keep this short, which is wrong for money:
    ClearState always succeeds, so opting out strands your funds.
    """

    def __init__(self) -> None:
        self.balance = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn", "NoOp"])
    def deposit(self, payment: gtxn.PaymentTransaction) -> UInt64:
        app = Global.current_application_address
        assert payment.receiver == app, "pay the vault"
        assert payment.sender == Txn.sender, "credit goes to the payer"
        held = self.balance.get(Txn.sender, UInt64(0))
        self.balance[Txn.sender] = held + payment.amount
        return held + payment.amount

    @arc4.abimethod
    def withdraw(self) -> UInt64:
        amount = self.balance.get(Txn.sender, UInt64(0))
        assert amount > UInt64(0), "nothing deposited"
        itxn.Payment(
            receiver=Txn.sender, amount=amount, fee=UInt64(0)
        ).submit()
        self.balance[Txn.sender] = UInt64(0)
        return amount
