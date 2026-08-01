"""A lottery that draws from a randomness beacon it does not control.

Read the methods in order; they are the lifecycle. Entrants pay in and are
recorded one box each. The operator commits to a round that does not exist
yet. Once that round has passed, anyone may draw: the contract asks an
ARC-21 beacon what it published for that round, derives an index from the
answer, and pays the pot to the account in that box. If the beacon never
publishes, `refund` gives every entrant their money back.

Two properties are worth naming before the code says them.

`draw` takes no arguments. Everything it decides comes from state written
before the target round and from the beacon's answer for that round, so a
caller chooses *when* the draw happens and nothing else.

The draw window and the refund window do not overlap. `draw` is legal in
(target_round, refund_round] and `refund` is legal after refund_round, which
is what stops a lottery from paying its pot out twice. `refund_round` is
written twice: once by `initialize`, so that entrants are not waiting on an
operator who never returns, and again by `commit`, which replaces it with the
end of the draw window.
"""

from algopy import (
    ARC4Contract,
    Account,
    BoxMap,
    Global,
    GlobalState,
    Txn,
    UInt64,
    arc4,
    gtxn,
    itxn,
    op,
)

# The deployed ARC-21 beacon stores one value every eight rounds and answers
# `get` for any round at or below the newest stored multiple. A target that
# is not a multiple is therefore readable one to seven rounds later than a
# multiple would be, rather than never. Rounding UP removes that wait and can
# only lengthen the lead, never shorten it.
BEACON_ROUND_MODULUS = 8
# The lead is how long entrants are locked in, so the ceiling is a product
# decision rather than a protocol one: 1,000 rounds is under an hour.
MIN_LEAD_ROUNDS = 16
MAX_LEAD_ROUNDS = 1_000

# How long entries stay open when the operator never commits. `initialize`
# sets the refund round to this far ahead, and `commit` overwrites it. An
# operator who goes quiet strands the entrants' money exactly as effectively
# as a beacon that does, so the refund path has to open without them.
ENTRY_WINDOW_ROUNDS = 1_000

# How long the draw stays legal after the target round. The ceiling is the
# beacon's retention: it holds 192 values eight rounds apart, so a value is
# readable for about 1,500 rounds and then it is gone for good. 300 rounds
# is well inside that and still about a quarter of an hour for somebody to
# notice. Past it, `draw` is refused and `refund` opens.
DRAW_WINDOW_ROUNDS = 300

# `BoxMap(arc4.UInt64, arc4.Address, key_prefix=b"e_")` names each box with
# 2 prefix bytes plus an 8-byte key and stores a 32-byte address. Box MBR is
# 2,500 + 400 x (name + data), so 2,500 + 400 x 42 = 19,300 microAlgo.
ENTRY_KEY_SIZE = 10
ENTRY_DATA_SIZE = 32
ENTRY_BOX_COST = 2_500 + 400 * (ENTRY_KEY_SIZE + ENTRY_DATA_SIZE)

# The pot is `entry_count x ticket_price`, so bounding both bounds the pot.
# 10,000 x 1,000 Algo is 10^13 microAlgo, six orders of magnitude below the
# uint64 ceiling of 18,446,744,073,709,551,615.
MAX_ENTRANTS = 10_000
MAX_TICKET_PRICE = 1_000_000_000


class Won(arc4.Struct):
    """ARC-28 event: the result, announced to whoever is listening."""

    winner: arc4.Address
    amount: arc4.UInt64


class Lottery(ARC4Contract):
    def __init__(self) -> None:
        self.beacon = GlobalState(UInt64(0), key=b"beacon")
        self.ticket_price = GlobalState(UInt64(0), key=b"ticket")
        self.entry_count = GlobalState(UInt64(0), key=b"entries")
        self.pot = GlobalState(UInt64(0), key=b"pot")
        self.target_round = GlobalState(UInt64(0), key=b"target")
        self.refund_round = GlobalState(UInt64(0), key=b"refund")
        self.drawn = GlobalState(UInt64(0), key=b"drawn")
        self.winner = GlobalState(Account(), key=b"winner")
        self.entrants = BoxMap(arc4.UInt64, arc4.Address, key_prefix=b"e_")

    @arc4.abimethod
    def initialize(self, beacon: UInt64, ticket_price: UInt64) -> None:
        """Name the beacon and the price. Once, by the operator."""
        assert Txn.sender == Global.creator_address, "operator only"
        assert self.beacon.value == UInt64(0), "already initialised"
        assert beacon != UInt64(0), "a beacon application id is required"
        assert ticket_price > UInt64(0), "a ticket must cost something"
        assert ticket_price <= UInt64(MAX_TICKET_PRICE), "ticket too dear"
        self.beacon.value = beacon
        self.ticket_price.value = ticket_price
        # The deadline exists before the operator has done anything, so the
        # exit does not depend on them doing it.
        self.refund_round.value = Global.round + UInt64(ENTRY_WINDOW_ROUNDS)

    @arc4.abimethod
    def enter(self, ticket: gtxn.PaymentTransaction) -> UInt64:
        """Buy one entry. Returns the index of the box it was written to."""
        assert Global.group_size == UInt64(2), "expected payment + app call"
        assert self.ticket_price.value != UInt64(0), "not initialised"
        assert self.target_round.value == UInt64(0), "entries are closed"
        assert Global.round <= self.refund_round.value, "entry window closed"
        assert self.entry_count.value < UInt64(MAX_ENTRANTS), "lottery full"

        # The entrant funds the box they are about to occupy. The contract
        # never pays box MBR out of the pot, which is why the pot can be paid
        # out in full without leaving the account below its minimum.
        due = self.ticket_price.value + UInt64(ENTRY_BOX_COST)
        app = Global.current_application_address
        assert ticket.receiver == app, "pay the lottery, not someone else"
        assert ticket.sender == Txn.sender, "pay for your own ticket"
        assert ticket.amount == due, "pay the ticket price plus the box"

        index = self.entry_count.value
        self.entrants[arc4.UInt64(index)] = arc4.Address(Txn.sender)
        self.entry_count.value = index + UInt64(1)
        self.pot.value += self.ticket_price.value
        return index

    @arc4.abimethod
    def commit(self, lead: UInt64) -> UInt64:
        """Close entries and name the future round the draw will read."""
        assert Txn.sender == Global.creator_address, "operator only"
        assert self.beacon.value != UInt64(0), "not initialised"
        assert self.target_round.value == UInt64(0), "already committed"
        assert self.entry_count.value > UInt64(0), "nobody entered"
        # Past the entry deadline the refunds have started, and `entry_count`
        # no longer counts the boxes that exist. A commit here would hand
        # `draw` a modulus larger than the map it indexes.
        assert Global.round <= self.refund_round.value, "entry window closed"
        assert lead >= UInt64(MIN_LEAD_ROUNDS), "too close to predict"
        assert lead <= UInt64(MAX_LEAD_ROUNDS), "lead is too long"

        raw = Global.round + lead
        modulus = UInt64(BEACON_ROUND_MODULUS)
        target = raw + (modulus - raw % modulus) % modulus
        self.target_round.value = target
        self.refund_round.value = target + UInt64(DRAW_WINDOW_ROUNDS)
        return target

    @arc4.abimethod
    def draw(self) -> UInt64:
        """Read the beacon, pick a winner, pay the pot. Anyone may call it."""
        assert self.drawn.value == UInt64(0), "already drawn"
        assert self.target_round.value != UInt64(0), "nothing committed yet"
        assert Global.round > self.target_round.value, "target round is future"
        assert Global.round <= self.refund_round.value, "draw window closed"

        # `get`, not `must_get`: a callee's assert message does not survive an
        # inner application call, so absence comes back as an empty slice this
        # contract can refuse in its own words.
        value, _txn = arc4.abi_call[arc4.DynamicBytes](
            "get(uint64,byte[])byte[]",
            arc4.UInt64(self.target_round.value),
            arc4.DynamicBytes(b""),
            app_id=self.beacon.value,
            fee=0,
        )
        assert value.native.length == UInt64(32), "beacon published nothing"

        digest = op.sha512_256(value.native)
        index = op.btoi(op.extract(digest, 24, 8)) % self.entry_count.value
        winner = self.entrants[arc4.UInt64(index)].native

        self.winner.value = winner
        self.drawn.value = UInt64(1)
        prize = self.pot.value
        self.pot.value = UInt64(0)
        itxn.Payment(receiver=winner, amount=prize, fee=UInt64(0)).submit()
        arc4.emit(Won(arc4.Address(winner), arc4.UInt64(prize)))
        return index

    @arc4.abimethod
    def sweep(self, index: UInt64) -> UInt64:
        """After a draw, return one entrant's box MBR and delete the box."""
        assert self.drawn.value == UInt64(1), "no draw yet"
        key = arc4.UInt64(index)
        assert key in self.entrants, "no such entry"
        entrant = self.entrants[key].native

        # The box goes and its minimum balance comes back with it. The order
        # of these two lines does not matter -- the ledger checks the
        # account's minimum once, at the end of the transaction, not after
        # each inner one -- but the pairing does: a delete with no payment
        # keeps the money, and a payment with no delete cannot be afforded a
        # second time.
        del self.entrants[key]
        refund = UInt64(ENTRY_BOX_COST)
        itxn.Payment(receiver=entrant, amount=refund, fee=UInt64(0)).submit()
        return refund

    @arc4.abimethod
    def refund(self, index: UInt64) -> UInt64:
        """Nothing is going to happen. Return one entrant's ticket and box.

        Two silences reach here. A beacon that never published for the
        committed round, and an operator who never committed at all: the
        deadline `initialize` wrote is what covers the second one.
        """
        assert self.drawn.value == UInt64(0), "the draw already happened"
        assert Global.round > self.refund_round.value, "draw still possible"
        key = arc4.UInt64(index)
        assert key in self.entrants, "no such entry"
        entrant = self.entrants[key].native

        refund = self.ticket_price.value + UInt64(ENTRY_BOX_COST)
        self.pot.value -= self.ticket_price.value
        del self.entrants[key]
        itxn.Payment(receiver=entrant, amount=refund, fee=UInt64(0)).submit()
        return refund

    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "the lottery is immutable"
