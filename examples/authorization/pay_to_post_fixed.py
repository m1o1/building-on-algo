# book-example: mode=compile
from algopy import (Account, ARC4Contract, BoxMap, Global, String, Txn, UInt64,
                    arc4, gtxn)


class PayToPost(ARC4Contract):
    """A board where posting costs a microAlgo fee. Three ways in, closed."""

    admin: Account
    price: UInt64
    next_id: UInt64
    ready: bool

    def __init__(self) -> None:
        self.ready = False
        self.author = BoxMap(UInt64, Account, key_prefix=b"a_")
        self.body = BoxMap(UInt64, String, key_prefix=b"b_")
        self.next_id = UInt64(0)

    @arc4.abimethod
    def initialize(self, admin: Account, price: UInt64) -> None:
        assert not self.ready, "already initialized"
        self.admin = admin
        self.price = price
        self.ready = True

    @arc4.abimethod
    def post(self, payment: gtxn.PaymentTransaction, body: String) -> UInt64:
        assert payment.receiver == Global.current_application_address, "not ours"
        assert payment.sender == Txn.sender, "pay for your own post"
        assert payment.amount >= self.price, "underpaid"
        post_id = self.next_id
        self.author[post_id] = Txn.sender
        self.body[post_id] = body
        self.next_id = post_id + UInt64(1)
        return post_id

    @arc4.abimethod
    def edit(self, post_id: UInt64, body: String) -> None:
        assert self.author[post_id] == Txn.sender, "not your post"
        self.body[post_id] = body

    @arc4.abimethod
    def set_price(self, price: UInt64) -> None:
        assert Txn.sender == self.admin, "admin only"
        self.price = price
