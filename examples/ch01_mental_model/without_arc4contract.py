from algopy import Bytes, Contract, OnCompleteAction, Txn, UInt64, log

# sha512_256("ping()string")[:4], then ARC-4's return-value log prefix and the
# encoded return value: two length bytes, then "pong".
PING = b"\xb1\x32\xc0\x56"
RETURN = b"\x15\x1f\x7c\x75\x00\x04pong"


class SmallestByHand(Contract):
    """The same application as `Smallest`, with the router written out."""

    def approval_program(self) -> bool:
        is_create = Txn.application_id.id == UInt64(0)
        if Txn.num_app_args == UInt64(0):
            return is_create and Txn.on_completion == OnCompleteAction.NoOp
        assert Txn.application_args(0) == Bytes(PING), "unknown method"
        assert Txn.on_completion == OnCompleteAction.NoOp, "unsupported action"
        log(Bytes(RETURN))
        return True

    def clear_state_program(self) -> bool:
        return True
