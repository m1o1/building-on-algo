\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Project}}
```
# A Lottery That Pays Out or Gives Back

A lottery sells tickets, waits, picks a winner and pays. **The waiting is the hard part: the number that picks the winner has to arrive from outside the contract, after the last ticket is sold, from a source the operator does not control.** Chapter 18 built that source. This chapter builds the thing around it: the tickets, the money, the deadline, and the exit for the day the source says nothing at all.

Everything in the project is a consequence of one fact about a randomness beacon: it belongs to somebody else. A contract that reads one is depending on an application it did not deploy, cannot update, and cannot compel. That dependency buys unpredictability, and it costs a failure mode no amount of care inside your own contract removes. The lottery here has two endings for that reason, and the second one is where most of the design lives.

::: {.spec title="Your commission: a lottery that pays out or gives back"}
Put real money in front of Chapter 18's beacon. The lottery ships when:

1. A ticket is one exact payment: the price plus the cost of the entry it creates, refused at any other amount.
2. Entries close hard at a committed target round, and nothing the operator does can reopen them.
3. The draw pays the whole pot to a winner any losing entrant can recompute from public values.
4. When the beacon never speaks --- or the operator never commits --- every entrant takes back ticket and box in full.
5. Table 19-6's refusal ledger is the acceptance list: every guard on money and time has a test that proves the refusal.
:::

## Run It First
The finished system is in `projects/lottery/`, and it runs two lotteries: one that draws, and one whose beacon never publishes for the round it committed to. Before running it, predict which of the two accounts involved --- the operator's or the application's --- pays for the contract's global state, and what the application account is holding the moment after the pot has been paid out.

```bash
cd projects/lottery
algokit project bootstrap all
algokit project run build
algokit localnet start
poetry run python -m scripts.run_lottery
algokit project run test
```

Table 19-1 is what to check as each stage prints.

: Table 19-1. Output checkpoints for the lottery workflow

| Output checkpoint | What to watch for |
|--------|----------------------------|
| Application account seeded | 100,000 microAlgo, and that is its entire minimum balance |
| Operator's minimum balance | Up 349,500 for the application and its seven uint plus one byte-slice global slots |
| Five entries | Pot 10,000,000 microAlgo, five boxes at 19,300 each |
| Committed target round | A multiple of 8, at least 16 rounds ahead |
| Draw | Entrant 3 of 5, the same one every run, because on LocalNet you publish the beacon value yourself |
| The announcement | `Won(address,uint64)` in the draw's logs, carrying the winner and the 10,000,000 |
| After the payout | Balance and minimum balance both 196,500 |
| Five boxes swept | 19,300 back to each entrant, application account down to 100,000 |
| The silent beacon | Each of three entrants takes back 2,019,300, ticket and box together |

Nothing is ever published for the round the second lottery named, so the draw is impossible and stays impossible, and the only correct behaviour left is to give the money back.

## What You Need First

Chapter 18 built the source of randomness and stopped at a raffle. This project puts money in front of it. Table 19-2 is what it draws on, and the rows about closing entries are the ones that decide whether the draw is fair.

Answer the predict column before you follow the link.

: Table 19-2. What this project assumes

| Prerequisite | Where it lands here | Predict before you read it |
|--------|--------------------|--------------------------------------|
| Example 18-4 | The shape: `enter`, `commit`, `draw`, and a payment at the end | The raffle keeps its boxes forever and has one ending. This one gives the boxes back and has two. Name the method each of those facts adds. |
| Example 18-3 | `draw`'s cross-application call, unchanged | Say what the contract does with an answer the beacon does not have, and why that decides which of ARC-21's two methods it calls. |
| Example 6-16 | `commit`, which closes entries and names the target round in one call | Entries close hard, at the commit. Say what a late entrant would know that an early one did not, and which assertion stops them. |
| The lead range | `commit`'s rounding up to a beacon multiple | A request for sixteen rounds buys sixteen to twenty-three, and the draw may then land anywhere in a window three hundred rounds wide. Work out the earliest and the latest round a draw can happen on. |
| Chapter 18's third property | The winner derivation, and the test that recomputes it off chain | A losing entrant must be able to check the result. Name the values they need and where each is readable from. |
| Example 18-3's fee | `draw`, `sweep` and `refund`, none of which says what it costs | Each settlement call issues inner transactions and none of them states a fee. Count the transactions on each path before you read the numbers. |

## Scaffolding Two Contracts

This project compiles two contracts, so it needs two directories under `smart_contracts/`. You are already in `projects/lottery/` from Run It First. If you would rather scaffold your own, Chapter 9's setup note applies, with `lottery` in place of `token_vesting`, and add a second directory, `smart_contracts/beacon_stub/`.

The lottery replaces the template's contract in `smart_contracts/lottery/contract.py`, and the beacon stand-in goes in `smart_contracts/beacon_stub/contract.py`. Delete the template's `deploy_config.py` in the renamed directory; it refers to a `HelloWorld` class that no longer exists.

Leave `beacon_stub/` empty for now. Its contract comes nine sections from here, and the reason for having a stub at all is that there is no way to ask a beacon somebody else runs to go quiet.

## Two Accounts Pay for This Contract

Buying a ticket is two transactions, and the client hands the payment to `enter` rather than assembling a group by hand:

```python
payment = algorand.create_transaction.payment(
    PaymentParams(
        sender=entrant.address,
        receiver=lottery.app_address,
        amount=AlgoAmount.from_micro_algo(ticket_price + ENTRY_BOX_COST),
    )
)
result = lottery.send.call(
    AppClientMethodCallParams(
        method="enter",
        args=[TransactionWithSigner(payment, entrant.signer)],
        sender=entrant.address,
        signer=entrant.signer,
        static_fee=AlgoAmount.from_micro_algo(FEE_ENTER),
        box_references=[entry_box_reference(int(index))],
    )
)
```

The composer places the payment ahead of the application call, which is the group of two the contract checks for. The static fee and the box reference are plumbing the chapter comes back to: `FEE_ENTER` is a LocalNet Ed25519 floor of one min-fee, not a production constant (Example 8-11).

The bill for state lands before the first ticket is sold. Table 19-3 is every global key the lottery declares.

The amount is the argument to read now. An entrant pays the ticket price plus `ENTRY_BOX_COST`: one number for the ticket, one for the storage the entry takes up, and Table 19-4 is where each of them lands.

: Table 19-3. The lottery's global state

| Key | Attribute | Type | What it holds |
|-------|--------------|------|-------------------------------|
| `beacon` | `beacon` | uint64 | The application id `draw` reads. Zero until `initialize` |
| `ticket` | `ticket_price` | uint64 | Price of one entry, in microAlgo |
| `entries` | `entry_count` | uint64 | How many entries exist, and the index of the next one |
| `pot` | `pot` | uint64 | Ticket money held on behalf of the winner |
| `target` | `target_round` | uint64 | The round the draw reads. Zero until `commit` |
| `refund` | `refund_round` | uint64 | The round the refund path opens. Written twice |
| `drawn` | `drawn` | uint64 | One once a winner has been paid |
| `winner` | `winner` | bytes | The address that won, for anybody reading state afterwards |

The key is what the ledger stores and the attribute is what the contract calls it. They differ where a shorter key was worth having: a global key is bytes on chain, and eight of them are cheaper to write than eight of the longer form.

Seven uint64 slots and one byte slot. Chapter 11 priced that: 100,000 microAlgo for the application to exist, 28,500 for each uint slot and 50,000 for each byte slot. Here that is `100,000 + 7 × 28,500 + 50,000 = 349,500` microAlgo. **The account that created the application carries it, not the application's own account, for as long as the lottery exists.**

The application account's own floor is the plain account base, 100,000 microAlgo, plus whatever its boxes cost. Nothing else. Table 19-4 is the whole bill, and the workflow reads both halves out of the ledger's own `min-balance` field rather than computing them.

: Table 19-4. Who pays for what

| Cost | Amount | Paid by | When |
|----------------|-------|---------------|-----------------|
| Application plus global schema | 349,500 | The operator | At creation, once, never refunded |
| Application account base | 100,000 | The operator, by payment | Before the first entry |
| One entry's box | 19,300 | The entrant, inside `enter` | Per entry, refunded on the way out |
| One entry's ticket | 2,000,000 | The entrant, inside `enter` | Per entry, into the pot |

That box figure is `2,500 + 400 × (name + data)`. The name is ten bytes, a two-byte `e_` prefix over an eight-byte key, and the data is a 32-byte address, so `2,500 + 400 × 42 = 19,300`. Chapter 18's raffle paid 400 less for a box of the same shape, because its prefix is one byte rather than two.

The whole contract imports eleven names:

```python
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
```

Then the constants, the state they size, and the one method that writes the first two keys:

```python
BEACON_ROUND_MODULUS = 8
MIN_LEAD_ROUNDS = 16
MAX_LEAD_ROUNDS = 1_000
ENTRY_WINDOW_ROUNDS = 1_000
DRAW_WINDOW_ROUNDS = 300

ENTRY_KEY_SIZE = 10
ENTRY_DATA_SIZE = 32
ENTRY_BOX_COST = 2_500 + 400 * (ENTRY_KEY_SIZE + ENTRY_DATA_SIZE)

MAX_ENTRANTS = 10_000
MAX_TICKET_PRICE = 1_000_000_000


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
        assert Txn.sender == Global.creator_address, "operator only"
        assert self.beacon.value == UInt64(0), "already initialised"
        assert beacon != UInt64(0), "a beacon application id is required"
        assert ticket_price > UInt64(0), "a ticket must cost something"
        assert ticket_price <= UInt64(MAX_TICKET_PRICE), "ticket too dear"
        self.beacon.value = beacon
        self.ticket_price.value = ticket_price
        self.refund_round.value = Global.round + UInt64(ENTRY_WINDOW_ROUNDS)
```

The five round constants are argued for where they are used: the modulus and the two lead bounds inside `commit`, the entry and draw windows beside the refund path.

The last line writes a deadline before the operator has done anything else, and the refund section is where it earns its place.

`beacon` is written once, behind a creator check, and read forever after. Chapter 15 gave the reason: an application id that arrives as a method argument on every call is a choice handed to the caller, and the caller can deploy something that answers to `get(uint64,byte[])byte[]` and returns whatever number suits them. Storing it makes the beacon part of what the operator published rather than part of what a caller sends. That does not make the beacon trustworthy; it makes it checkable. `beacon` is public global state, and an entrant who does not read it before buying a ticket is trusting the operator not to have named an application the operator runs.

The two price bounds look like decoration and are not. `MAX_ENTRANTS` × `MAX_TICKET_PRICE` is 10^13^ microAlgo, six orders of magnitude below the uint64 ceiling of 18,446,744,073,709,551,615, so the pot cannot overflow no matter how the lottery is used. Without a bound on either factor the accumulation is unproven, and the failure mode is a transaction that aborts partway through `enter` with an arithmetic error nobody can explain.

## An Entry Is a Box Somebody Bought

An entry is one box holding one address. The entrant pays for the box and for the ticket in the same payment, and the contract checks the total to the microAlgo:

```python
    @arc4.abimethod
    def enter(self, ticket: gtxn.PaymentTransaction) -> UInt64:
        assert Global.group_size == UInt64(2), "expected payment + app call"
        assert self.ticket_price.value != UInt64(0), "not initialised"
        assert self.target_round.value == UInt64(0), "entries are closed"
        assert Global.round <= self.refund_round.value, "entry window closed"
        assert self.entry_count.value < UInt64(MAX_ENTRANTS), "lottery full"

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
```

Four checks stand between a payment and an entry, and each of them fails differently. Without the receiver check an entrant pays somebody else and still gets an entry. Without the sender check a caller reuses a bystander's payment: any payment in the group would do, including one the bystander sent for their own entry. The amount check is `==` rather than `>=`, and without it the pot stops being `entry_count` × `ticket_price`, which makes every later arithmetic statement about the pot false. The group-size check is what stops a third transaction being appended to the pair these four checks were written for.

The MBR arithmetic is the reason `enter` collects `ticket_price + ENTRY_BOX_COST` rather than a round number. Each entry hands the application account exactly what that entry will cost it, so the account's balance is always its floor plus the pot, and never anything else. That property is what makes the payout affordable later, and the workflow asserts it against the ledger's own `min-balance` field.

## The Operator's Only Privilege

`commit` is the one method only the operator may call, and it does two things: closes entries, and names the round the draw will read.

```python
    @arc4.abimethod
    def commit(self, lead: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "operator only"
        assert self.beacon.value != UInt64(0), "not initialised"
        assert self.target_round.value == UInt64(0), "already committed"
        assert self.entry_count.value > UInt64(0), "nobody entered"
        assert Global.round <= self.refund_round.value, "entry window closed"
        assert lead >= UInt64(MIN_LEAD_ROUNDS), "too close to predict"
        assert lead <= UInt64(MAX_LEAD_ROUNDS), "lead is too long"

        raw = Global.round + lead
        modulus = UInt64(BEACON_ROUND_MODULUS)
        target = raw + (modulus - raw % modulus) % modulus
        self.target_round.value = target
        self.refund_round.value = target + UInt64(DRAW_WINDOW_ROUNDS)
        return target
```

The rounding is Chapter 18's, and what it removes is a window of refusals rather than a wait for the value. The deployed beacon stores one value every eight rounds and answers for any round at or below the newest stored multiple. A target that is not a multiple still gets its answer --- once the next multiple lands --- but between the target round passing and that landing there are one to seven rounds where `draw`'s round guard is open and the call fails with `beacon published nothing`. Rounding up to the multiple closes that window, and can only lengthen the lead: a request for sixteen buys between sixteen and twenty-three rounds depending on where the commit landed.

`refund_round` is written here, at commit time, and not when the refund is asked for. A deadline computed at commit is a promise the operator made in front of the entrants; a deadline computed later is a number the contract could be argued into moving.

`assert self.entry_count.value > UInt64(0)` is what makes the draw's modulo safe. `entry_count` cannot be zero at commit, and nothing between commit and draw can lower it, so `% self.entry_count.value` inside `draw` has a divisor the contract has already proven non-zero. Division by zero on the AVM aborts the transaction outright.

## Reading a Beacon You Do Not Own

The draw is a cross-application call, four guards before it and one after:

```python
class Won(arc4.Struct):
    """ARC-28 event: the result, announced to whoever is listening."""

    winner: arc4.Address
    amount: arc4.UInt64
```

```python
    @arc4.abimethod
    def draw(self) -> UInt64:
        assert self.drawn.value == UInt64(0), "already drawn"
        assert self.target_round.value != UInt64(0), "nothing committed yet"
        assert Global.round > self.target_round.value, "target round is future"
        assert Global.round <= self.refund_round.value, "draw window closed"

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
```

The `arc4.emit` line is Example 8-17's device doing project work, and it is doing a different job than the `self.winner` write three lines above it. State answers whoever *asks*; the event reaches whoever is *listening* --- a results page or an entrant's indexer query finds `Won(address,uint64)` by its four-byte prefix without polling this contract's state or holding its source. It adds no transaction and no fee: an event is a log write inside the call that emitted it.

**`draw` takes no arguments.** Everything it decides comes from state written before the target round existed and from the beacon's answer for that round. A caller chooses when the draw happens and nothing else, which is why the method needs no authorization at all: gatekeeping a computation the caller cannot influence buys nothing, and a lottery whose draw only the operator can trigger is a lottery the operator can stall. The compiled ARC-56 spec records the empty argument list, and `tests/test_contract_shape.py` reads it back out and asserts it.

`get` rather than `must_get` is the choice Chapter 18 settled. Absence comes back as an empty byte slice, which this contract refuses in its own words; `must_get` would refuse inside the beacon's program, and a callee's assert message does not survive an inner application call.

Both inner transactions carry a zero fee, `fee=0` on the beacon call and `fee=UInt64(0)` on the payment, so the caller pays for the whole tree. Three transactions means 3,000 microAlgo: the outer call, the inner beacon read, and the inner payment. Setting 2,000 gets a failure opening `group fee 0.0A too small (needs 1mA more)` --- the rest of that message is an eight-thousand-character dump of the one inner transaction it could not pay for --- and the group never lands.

The opcode budget is comfortable. The outer call brings 700 units and the inner call to the beacon brings 700 more, because the pool is topped up per inner *application call* and an inner payment adds nothing. So `draw` runs against 1,400 and consumes 231 --- eight of those the `Won` event's log --- and `sweep`, whose one inner transaction is a payment, runs against the outer call's 700 alone and consumes 53. No `ensure_budget` anywhere.

Check that with simulate and it will report 2,100 added --- its tracer credits 700 per inner submit regardless of type; the AVM grants it only for application calls.

The winner comes from `sha512_256` of the beacon value, the last eight bytes of that digest read as a big-endian integer, modulo the entry count. Every input is public once the beacon publishes, which is the point. `tests/test_lottery.py` recomputes it off chain and asserts the contract agrees:

```python
def winner_index(value: bytes, entries: int) -> int:
    digest = hashlib.new("sha512_256", value).digest()
    return int.from_bytes(digest[24:32], "big") % entries
```

A losing entrant runs the same three lines against the beacon value and the entry count, both readable from the chain, and gets the same answer or a dispute worth having.

## Declaring What the Call Will Touch

The ticket purchase ahead of Table 19-3 declared `box_references=[entry_box_reference(int(index))]` and put off saying why. The reference is the box `enter` creates: the prefix the `BoxMap` declares, `b"e_"`, followed by the index as eight big-endian bytes. The client has to know that index before the call, and reads it out of `entries` in global state.

`draw` is where knowing in advance stops being possible. The method reads the winner's box, and which box that is depends on a beacon value that does not exist when the group is built. So the client declares the one reference it can name and lets the tooling find the other:

```python
result = lottery.send.call(
    AppClientMethodCallParams(
        method="draw",
        args=[],
        sender=caller.address,
        signer=caller.signer,
        static_fee=AlgoAmount.from_micro_algo(FEE_DRAW),
        app_references=[beacon_app_id],
    )
)
```

Both references are in fact discovered for you: delete `app_references` and the call still works, because every call algokit-utils sends is simulated first with unnamed resources allowed, and whatever the program reached comes back in the response and goes into the real transaction's reference arrays. The beacon is declared anyway because it is the only one a caller who does not pre-simulate could supply. Another contract, a hand-built group or a different SDK can name the beacon; none of them can name the winner's box without redoing `draw`'s arithmetic. Chapter 8 covers the mechanism and the trap that travels with it --- a passing simulate is not evidence a submitted call works, because the submitted call is still bound by the ordinary resource rules.

The purchase and the draw are both shown without the two seams `scripts/localnet_helpers.py` carries for the tests: an amount override, so a test can underpay for a box, and a fee override, so a test can prove that 2,000 microAlgo is one transaction short.

Nothing about that is specific to a beacon. It is what a method whose reads depend on its own computation looks like from the client side, and the alternative is a caller who computes the winner off chain and declares that box, which works and is worse: it is the same arithmetic maintained in two places. The test's copy above is fine because disagreeing is its whole job; a client's copy has to be right, and nothing goes red when it stops being.

## Paying the Winner and Letting the Boxes Go

After `draw`, the pot is gone and five boxes remain. The application account is holding `100,000 + 5 × 19,300 = 196,500` microAlgo, and its minimum balance is the same number. It owns nothing it does not owe --- absent an unsolicited payment, which anybody may send to any address and which no contract can refuse or reclaim.

`sweep` returns one box's minimum balance to the entrant who paid it and deletes the box:

```python
    @arc4.abimethod
    def sweep(self, index: UInt64) -> UInt64:
        assert self.drawn.value == UInt64(1), "no draw yet"
        key = arc4.UInt64(index)
        assert key in self.entrants, "no such entry"
        entrant = self.entrants[key].native

        del self.entrants[key]
        refund = UInt64(ENTRY_BOX_COST)
        itxn.Payment(receiver=entrant, amount=refund, fee=UInt64(0)).submit()
        return refund
```

Anybody may call it, and the money goes to the address in the box regardless of who did. That is the same reasoning as `draw`: the method has no discretion, so restricting it only creates a way for the lottery to strand money. It is also Chapter 18's Exercise 5 answered from the other side --- that exercise's first decision was who may retire a raffle, and retirement needed an operator because it reopened the contract; a sweep only gives deposits back, which is why "anybody" is safe here and was not there.

The delete is the double-claim guard rather than an accounting step. A second `sweep` for the same index has to fail, and `assert key in self.entrants` is what makes it fail once the box is gone. A refund path with no delete beside it is a faucet.

The two halves are symmetrical: `enter` collects 19,300 and creates a box, `sweep` destroys a box and pays 19,300 back. The application account's floor moves by the same amount in each direction, so after five sweeps it is back to 100,000, and the workflow asserts it against `min-balance` at both ends.

The index-reuse hazard that deletion usually brings stays theoretical here because creating and deleting are separated in time, by two guards rather than one: `enter` is refused once `commit` has run, which is what `sweep` waits behind, and refused again once the entry deadline passes, which is the earliest a `refund` can delete anything.

::: {.gotcha #one-counter-two-questions topic="Box storage" title="A counter that names the next box cannot also count the boxes that exist"}
`entry_count` is read twice for two different purposes: as the index of the next box to create, and as the divisor that turns a beacon value into a winner. Those are a question about the past and a question about the present, and they part company the moment a box is deleted --- the next entry reuses an occupied index, silently overwrites a live entry, and the count stays permanently above the number of boxes. Compilation, unit tests and a happy-path run all pass, because the defect needs a create *after* a delete. A contract where entries and deletions interleave needs two counters, or box keys that never repeat.
:::

## When the Beacon Never Speaks

A beacon is somebody else's application. The daemon that feeds it can stop, its account can run out of funding, or it can simply miss the round you committed to, and no assertion inside your contract prevents any of that. What your contract can do is stop waiting.

There is a second silence with the same shape, and it is the operator's. An operator who takes the tickets and never calls `commit` freezes the pot exactly as effectively as a beacon that never publishes, and the guard that covers the first would not have covered the second: a refund gated on a committed round is a refund the operator can withhold by not committing. That is why `initialize` writes `refund_round` before the operator has done anything else.

```python
    @arc4.abimethod
    def refund(self, index: UInt64) -> UInt64:
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
```

`refund` hands back the ticket as well as the box, and takes the ticket out of the pot as it goes, so the pot always states what the contract still owes a winner who might yet exist. It asks nothing about `target_round`, which is what lets it cover both silences with one deadline: before a commit that deadline is the end of the entry window, and after one it is the end of the draw window.

Figure 19-1 draws both futures: the committed lottery, and the one whose operator never commits. The empty stretch between `commit` and `target_round` is the lead, and nothing succeeds there: `enter` is refused because a target exists, `draw` because the round it reads has not arrived, and `refund` because the deadline it waits on has not passed.

![Figure 19-1. The lottery's lifecycle on one round axis. The second timeline is the same contract when the operator never commits: the deadline `initialize` wrote is the only one, so the way out does not depend on anybody turning up.](figures/lottery-windows.svg)

The two exits cannot both be open. `draw` is legal in `(target, refund_round]` and `refund` is legal after `refund_round`, so the round check alone separates them going forward; `drawn` is what separates them going backward, because a lottery drawn at `target + 5` would otherwise become refundable at `target + 301` and pay everybody a second time out of an account that no longer has the money. `commit` moving `refund_round` does not open a gap either: it is refused once the first deadline has passed, so it can only replace a deadline still in the future, and the replacement is at least sixteen rounds further out than the round it was written in.

::: {.gotcha #exit-windows-must-not-overlap topic="Arithmetic and time" title="Two settlement paths gated only on state can both be open at once"}
A contract that pays out on success and refunds on failure needs the two to be mutually exclusive at every round, and a flag is only half of it. Gate the success path on a deadline it must beat and the failure path on the same deadline having passed, then gate the failure path on the success flag as well: the deadline separates them for a caller arriving late, and the flag separates them for a caller arriving after a success that already happened. Miss the flag and the contract pays twice; miss the deadline and a slow success path can run against an account that has already been refunded. Neither shows up in a happy-path test, because a happy-path test never asks for both.
:::

The draw window is 300 rounds, and the ceiling on it is the beacon's memory rather than anybody's patience. The deployed beacon stops answering for a round about 1,500 rounds after it published, measured by asking, and after that the value is gone for good: a window longer than that would leave entrants waiting on evidence that no longer exists. Three hundred rounds is about a quarter of an hour on a public network, well inside that, and long enough that a draw nobody is watching for still gets called.

## Nobody Changes the Program

One method is left, and it is the one nobody calls:

```python
    @arc4.baremethod(allow_actions=["UpdateApplication", "DeleteApplication"])
    def reject_lifecycle(self) -> None:
        assert False, "the lottery is immutable"
```

An operator who can replace the program between the commit and the draw is an operator who picks the winner, and one who can delete the application can empty its account with the entrants' boxes still in it. Chapter 24 covers what approving either action grants. Here the answer is nothing, permanently, and it costs one bare method to say so.

## One Line Between LocalNet and TestNet

The lottery reads whatever application id it was initialised with. That is the whole portability story: on LocalNet the id names a stub in this project, on TestNet it names application 600011887, and the contract is byte-identical in both cases. In `scripts/localnet_helpers.py`:

```python
# 0 means "deploy the stub in smart_contracts/beacon_stub/ and use that".
# 600011887 is the ARC-21 beacon on TestNet; 1615566206 is the MainNet one.
BEACON_APP_ID = 0
```

The stub implements ARC-21's two mandatory methods over global state, plus one that ARC-21 does not have:

```python
from algopy import (
    ARC4Contract,
    Bytes,
    Global,
    GlobalState,
    Txn,
    UInt64,
    arc4,
    op,
)

BEACON_VALUE_SIZE = 32


class BeaconStub(ARC4Contract):
    def __init__(self) -> None:
        self.value = GlobalState(Bytes(b""), key=b"v")
        self.published_for = GlobalState(UInt64(0), key=b"r")

    @arc4.abimethod
    def publish(self, rnd: UInt64, value: Bytes) -> None:
        assert Txn.sender == Global.creator_address, "publisher only"
        assert value.length == UInt64(BEACON_VALUE_SIZE), "value is 32 bytes"
        self.value.value = value
        self.published_for.value = rnd

    @arc4.abimethod(readonly=True)
    def get(self, rnd: UInt64, user_data: Bytes) -> Bytes:
        if self.published_for.value != rnd:
            return Bytes(b"")
        if user_data.length == UInt64(0):
            return self.value.value
        return op.sha3_256(self.value.value + user_data)

    @arc4.abimethod(readonly=True)
    def must_get(self, rnd: UInt64, user_data: Bytes) -> Bytes:
        assert self.published_for.value == rnd, "no value for that round"
        return self.get(rnd, user_data)
```

`publish` is the reason the stub exists, and it is a knob production does not have. The lottery never calls `must_get`; the stub carries it so that a client pointed at the stub meets the same two methods as one pointed at the real beacon. Table 19-5 is what each environment can and cannot teach.

: Table 19-5. What each chain is good for

| What differs | LocalNet stub | TestNet beacon |
|--------|-----------------------|--------------------------------|
| Rounds | One per submitted transaction, milliseconds | Real, about 2.75 seconds; a lead of 16 to 23 rounds is 44 to 63 seconds |
| Values | You publish them, so results repeat exactly | Genuinely unpredictable |
| Silence | You can ask for it | You cannot |

Silence is the row that matters. The stub is not a fallback for readers without a TestNet account: it is the only way to run the refund path, and a lottery that has never been tested against a silent beacon has never been tested against the thing most likely to go wrong with it.

Running against TestNet takes the one-line change above plus a funded account, and it is written up in the project's `README.md` with the environment variables and the lines of output that change. **The build does not run it.** `validate.py --examples` runs against LocalNet, so committing a TestNet run to the build would mean committing a funded mnemonic, and a mnemonic does not belong in a test suite. The wait is the smaller cost: the run reaches its target in the sixteen to twenty-three rounds `commit` rounds up to, about a minute at TestNet's pace. Gating the *refund* path would be the expensive one, since that means sitting out the whole three-hundred-round draw window.

What was checked against the live beacon, using a read-only `simulate` that needs no funding and submits nothing --- and it is exactly what `draw` depends on:

- Application 600011887 answers `get(uint64,byte[])byte[]` with 32 bytes for a past round that is a multiple of eight.
- It answers with an empty slice for a round in the future.
- It stops answering about 1,500 rounds back.

## What the Network Refuses

Fifty-one tests ship with the project: twelve that read the source and the compiled spec, and thirty-nine that deploy and play. Twenty-nine of the thirty-nine turn on a refusal, and each one takes an otherwise valid call and removes one guard's worth of honesty from it.

That ratio is the shape of a contract holding other people's money. The happy path is two tests, the draw that happens and the draw that never does. Twenty-nine of the rest are transactions the network must not accept, and the remaining eight check what a passing draw cannot show: that anybody may call it, that the target round is a multiple of eight, that it fits the default opcode budget. Read the middle column of Table 19-6 first and predict the right-hand one. The messages were written so that you can; one you cannot predict from is one to rewrite.

: Table 19-6. The guards on money and time, and the refusal that proves each

| Guard | Refused message | What it stops |
|----------------|---------------------|-------------------------|
| Creator-only initialisation | `operator only` | A stranger naming the beacon |
| One-time initialisation | `already initialised` | The beacon being swapped after tickets sell |
| Creator-only commit | `operator only` | A stranger closing entries |
| One-time commit | `already committed` | A second target round replacing the first |
| Entries close at commit | `entries are closed` | Buying a ticket after the deadline is known |
| Entries close on the clock | `entry window closed` | An operator holding tickets open forever, and a late commit against a map the refunds have shrunk |
| Exact payment | `pay the ticket price plus the box` | A pot that is not entries times price |
| Payment receiver | `pay the lottery, not someone else` | An entry the contract was not paid for |
| Payment sender | `pay for your own ticket` | An entry bought with a bystander's payment |
| Group size | `expected payment + app call` | A third transaction appended to the pair |
| Draw needs a commit | `nothing committed yet` | Drawing before entries closed |
| Draw needs the round | `target round is future` | Drawing before the value exists |
| Draw needs a value | `beacon published nothing` | Treating an empty slice as randomness |
| Draw runs once | `already drawn` | Paying the pot twice |
| Draw window closes | `draw window closed` | A draw racing the refunds |
| Sweep needs a draw | `no draw yet` | Dismantling a live lottery |
| Refund needs the deadline | `draw still possible` | An entrant withdrawing mid-lottery |
| Refund needs no draw | `the draw already happened` | Refunding a lottery that already paid |
| Both exits delete | `no such entry` | Claiming the same entry twice |
| Lifecycle closed | `the lottery is immutable` | Replacing the program under the entrants |

Seven more guards bound the arguments rather than the money: a zero beacon id, a ticket priced at nothing, a ticket priced above the overflow bound, a lead under sixteen rounds, a lead over a thousand, a commit with nobody in it, and an entry before `initialize` has run. Each has a test of its own. Of the contract's twenty-seven distinct assertion messages, twenty-six are reached by a test; the exception is the ten-thousand-entry ceiling, which costs ten thousand transactions to reach.

Three properties have no refusal to point at, because a contract that gets them wrong still works. An inner fee that is not zero drains the application account a thousand microAlgo at a time, and the easiest one to leave out is the beacon call's, because it is the only inner transaction here that is not an `itxn.Payment`. A `draw` that took an argument would look exactly like this one until somebody passed a different value. A method marked `readonly` that moves money is answered by simulation and moves nothing, and every client believes it. Those are asserted against the source and the compiled ARC-56 spec instead, which is what `tests/test_contract_shape.py` is for.

## Exercises

1. **(Apply)** In `scripts/run_lottery.py`, set `TICKET_PRICE` to `500_000` and `DRAWN_ENTRANTS` to nine.
   (a) Before rerunning, write down the pot, the application account's balance and minimum balance immediately after the draw, and how much comes back per sweep.
   (b) Rerun the workflow and check all three against the transcript.
   (c) Say which of the three the beacon value can change.
   (d) Pin one of them: write the test that fails if `sweep` can run twice for the same index, using the message Table 19-6 says it must produce.

2. **(Analyze)** `enter` asserts `ticket.amount == due` rather than `>=`. Work out what breaks under `>=`, in order: which state variable stops being true first, which later method reads it, and what a lottery with one generous entrant pays out. Then say when `>=` *would* be right for a payment that funds a box, and what a contract has to do with the excess for that to be safe.

3. **(Analyze)** Delete `draw`'s `Global.round <= self.refund_round.value` check and leave everything else alone. Give the sequence of calls that now pays out more than the entrants put in, timed in rounds relative to `target`, name the account that ends short and say by how much. Then do the same for the other deletion: keep the window check and remove `refund`'s `drawn == 0`.

4. **(Evaluate)** The operator commits with `lead=16` and the beacon then misses that round, so 300 rounds later everyone refunds. Evaluate three responses: raise `MIN_LEAD_ROUNDS`, raise `DRAW_WINDOW_ROUNDS`, or have `commit` name two target rounds and let `draw` accept either. Judge each on what it costs an entrant, what it costs the operator, what it does to the lead range Chapter 18 computed, and what happens when the beacon is down for a day rather than a round. Say which you would ship and what evidence would change your mind.

5. **(Evaluate)** This lottery runs once per deployment: after the last sweep the contract is inert, 349,500 microAlgo of schema minimum balance is still locked in the operator's account, and the 100,000 seeded into the application account can never be signed for again because the contract refuses `DeleteApplication`. That is 449,500 microAlgo per lottery, split across two accounts. Compare running rounds back to back in one application against deploying a fresh one per round, on the operator's locked balance, what an entrant has to check before buying a ticket, what an auditor has to read, and what state a second round would have to reset. More than one field is a candidate for the reset that is a security decision rather than a bookkeeping one. Pick one, argue for it against the others, and say what an operator could do if it reset wrongly.

6. **(Create)** Give the lottery a prize split: seventy per cent to a first place and thirty to a second, with the two winners distinct. You have thirty-two bytes of beacon value and have spent eight of them.
   (a) Write the guards on `draw`'s replacement.
   (b) Write the arithmetic that picks two different indices from one beacon value.
   (c) Write both payments.
   (d) State the fee the call now needs.
   (e) Say what your code does when only one entry exists.
   (f) Say where that check belongs so the answer is decided at `commit` rather than at `draw`.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can recompute a draw's winner off chain from the beacon value and the entry count, and say why a losing entrant being able to do the same is what makes the result a result rather than a claim
- [ ] I can say which account pays an application's global schema and which pays its boxes, collect a box's minimum balance from the account that causes it, return it when the box goes, and say why the delete is the double-claim guard rather than an accounting step
- [ ] I can read an ARC-21 beacon from inside a contract, state the fee the call needs and where each thousand microAlgo of it goes, and say why the method that reads it takes no arguments
- [ ] I can build two settlement paths that cannot both be open, and name the two separate guards that keep them apart in each direction
- [ ] I can point one contract at a stub on one chain and a deployed application on another with a single configured id, and say which failure paths only the stub can run

## Mastery Checkpoint
That is the end of Part IV. The checklist above asks whether you followed the chapters. The Mastery Checkpoint printed on the next page asks something harder: whether you can build a thing this part did not show you. It is a small program with a stated acceptance test, and a fallback if you stall.
