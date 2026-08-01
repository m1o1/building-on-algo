# book-example: mode=compile
from algopy import (Account, Global, TemplateVar, TransactionType, Txn, UInt64,
                    logicsig)


@logicsig
def vault() -> bool:
    """A contract account: the LogicSig IS the account, and nobody signs for it.

    The address is the hash of this program. Anyone may submit a transaction
    from it, and the program alone decides whether that transaction is
    allowed -- there is no private key anywhere and no delegator to blame.
    """
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        and Txn.receiver == TemplateVar[Account]("BENEFICIARY")
        and Txn.first_valid >= TemplateVar[UInt64]("UNLOCK_ROUND")
    )
