from algopy import Account, ARC4Contract, Global, LocalState, Txn, UInt64, arc4


class Registry(ARC4Contract):
    def __init__(self) -> None:
        self.credits = LocalState(UInt64)

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.credits[Txn.sender] = UInt64(0)

    @arc4.abimethod(readonly=True)
    def credits_of(self, member: Account) -> UInt64:
        if not member.is_opted_in(Global.current_application_id):
            return UInt64(0)
        return self.credits.get(member, default=UInt64(0))
