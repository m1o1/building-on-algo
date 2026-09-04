\newpage

\part{Chance}

Nothing on a public ledger is secret and nothing in a deterministic machine is random. Part IV builds fair draws anyway. Chapter 18 derives the three properties a usable random number must have and the beacon pattern that delivers them; Chapter 19 spends them on a lottery that pays a winner or gives everyone their money back.

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# A Number Nobody Can Predict

A raffle picks a winner. A mint decides which of five hundred images a buyer gets. A matchmaker pairs two players out of a queue, and a governance process draws a review committee from a list of candidates. Four products, one shared requirement, and it is the first requirement in this book that nothing you have written so far can meet.

There is no `random()` on the AVM and there cannot be one. Every node runs your program and every node has to reach the same answer, so whatever a contract computes is a function of values already on the chain, and any value already on the chain is one somebody could have read. Randomness has to arrive from outside that function. Getting it there, and proving afterwards that it arrived honestly, is what this chapter is about.

## Three Properties, and the Middle One Is Hard
Write down what a draw has to be before writing any code. Two of the three are easy to satisfy and one is not, and every failed design in this area fails the same one.

**Nobody chose it.** The number is not the raffle operator's pick, not the winner's, and not the block proposer's. This rules out an operator who calls `set_winner`, and it rules out any input a participant supplies alone.

**Nobody could predict it in time to act on it.** By the moment the last entry is accepted, the number must not exist yet. Predictability is not about secrecy in general; it is about secrecy up to one deadline, and a value that becomes knowable a second before that deadline is as useless as one that was published a week early.

**Anybody can check it afterwards.** Given the same public record, a losing entrant can recompute the outcome and get the same answer. Without this the draw is a claim rather than a result, and disputes have nowhere to go.

*Predict: before reading on, find a value already on the chain that satisfies all three, or convince yourself that no value already on the chain can.*

::: {.spec title="Your commission: a raffle that draws a winner nobody chose"}
The contract you build this chapter sells tickets and then picks one of its ticket holders. It must:

1. Sell tickets at a fixed price, to anyone, each ticket paying for the storage it creates
2. Close entries against a round that does not exist yet, so the winning number is born after the last ticket is sold
3. Draw the winner from a value that passes all three properties, and pay the whole pot exactly once
4. Let anybody at all settle the draw, and gain nothing by being the one who does

Four requirements, four methods. At the end of the chapter you will run the finished raffle against this list.
:::

By the end of this chapter you will be able to:

- Test a proposed source of randomness against those three properties, and say which one it fails
- Show that a block seed fails the second, by computing a contract's answer before the transaction that asks for it exists
- Commit to a value without revealing it, and say what the nonce is for and what breaks without one
- Close entries against a round that does not exist yet, and say why the lead is a range rather than a number
- Read the ARC-21 randomness beacon from inside a contract, and choose between its two methods on grounds your users will feel
- Say what a verifiable random function adds, what it costs, and why the chain's own seed cannot be checked on chain

## The Block Seed Everyone Reaches For First
Every Algorand block carries a 32-byte seed. It is different every round, it is produced by the consensus protocol rather than by any participant, and a contract can read it with one opcode. If you arrive from another chain you have almost certainly used a block hash this way, because it is the folk source of randomness nearly everywhere.

Chapter 6 settled the objection people usually raise about it. The seed is a verifiable random function of the previous seed under the proposer's key, so a proposer can compute it and cannot select it, and the window arithmetic there gives the other half: a contract may read rounds from `last_valid - 1001` up to `first_valid - 1`, which is `1001 - (last_valid - first_valid)` rounds ending strictly below the transaction's own first valid round.

Read those two facts together and the problem is not about proposers at all. **The highest round a contract can reach is one the caller can download before building the transaction that reaches for it.**

Every design from here on rests on a hash. A hash is *binding*, because nobody can find a second input with the same digest, and *hiding*, because the digest says nothing about its input that guessing the input and checking would not have told you. `sha512_256` is Algorand's own and is the one to reach for; what each hash costs, and when a dearer one earns its price, is Chapter 22's subject.

The failure is easier to watch on a mint --- sixty-four discrete tiers, one of them obviously worth stealing --- and your raffle inherits it unchanged.

**Example 18-1.** A mint tier drawn from a block seed

<!-- finder: draw an outcome from a block seed and watch a caller choose it -->

```python
from algopy import ARC4Contract, Bytes, GlobalState, Txn, UInt64, arc4, op

TIERS = 64  # tier 0 is the jackpot


class NaiveMint(ARC4Contract):
    """Assign a mint tier from a block seed. Every input is public."""

    def __init__(self) -> None:
        self.minted = GlobalState(UInt64(0))

    @arc4.abimethod
    def mint(self, ticket: Bytes) -> UInt64:
        assert ticket.length <= UInt64(32), "ticket too long"
        # A block seed is 32 bytes of verifiable randomness, and it is
        # mixed here with two values the contract did not choose. None
        # of that matters: the seed is committed and public before this
        # transaction is built, so the answer is a pure function of
        # three things the caller already has.
        seed = op.Block.blk_seed(Txn.first_valid - UInt64(1))
        digest = op.sha512_256(seed + Txn.sender.bytes + ticket)
        self.minted.value += UInt64(1)
        return op.btoi(op.extract(digest, 24, 8)) % UInt64(TIERS)
```

This is the careful version rather than a straw man. The seed is hashed rather than used raw, the caller's own address is mixed in so that two accounts minting against one block get different tiers, and the ticket bytes let a buyer feel they contributed something. It compiles, it deploys, and it returns a number between 0 and 63 that looks like a draw.

*Predict: the driver beside this example downloads one block, does arithmetic in Python, and only then sends the call. Say what it can print that would settle the question, and what it would have to do next to turn prediction into theft.*

```console
>>> # 64 mint tiers, and tier 0 is the jackpot.
>>> L = algod.status()["last-round"]     # mint reads block L - 1
>>> seed = block_seed(L - 1)             # committed, and public
>>> predicted = tier(seed, player, b"first")
>>> mint(b"first").abi_return == predicted
True
>>> # One block later, so a new seed. Search tickets for tier 0.
>>> L = algod.status()["last-round"]
>>> ticket = search(block_seed(L - 1), player)
>>> transactions_sent_while_searching
0
>>> mint(ticket).abi_return              # chosen, not drawn
0
```

The first half fetches the seed of the round `mint` will read, computes the contract's answer from it, and submits the call only afterwards. That already disqualifies the design, because a caller who can compute the outcome can decline to send when the outcome is bad, and declining costs nothing.

The rest is worse. `search` walks candidate tickets until it finds one whose tier is 0, and it does that entirely in Python: no transaction, no fee, no node involvement, nothing on chain for anybody to notice. One ticket in sixty-four wins. The jackpot then arrives on the attacker's single submitted transaction, and on chain that transaction is indistinguishable from an honest mint.

Nothing in the attack depends on standing. An account created seconds earlier and funded with two Algo does the same thing and wins the same way, so there is no early-adopter advantage to remove and no allowlist to tighten. The ticket argument makes the search convenient rather than possible: take it away and the attacker still chooses whether to send, and still chooses which of their accounts sends. Mixing in something *you* choose and keep to yourself is not available either: a contract has no secrets, since its global state, its box contents and its program are all readable.

::: {.gotcha #salting-a-public-seed topic="Arithmetic and time" title="Hashing a public seed with the caller does not make it unpredictable"}
`sha512_256(seed || sender || salt)` looks like the repair, and it fixes something real: two accounts minting against the same block now get different answers, so one entrant's result no longer leaks another's. It does nothing about the attack that matters. The seed is public before the transaction exists, the sender and the salt are the caller's, so the whole expression is a function the caller can evaluate off chain --- and every extra input they control is one more dimension to search: fresh addresses, or salts at sixty-four tries on average for a one-in-sixty-four outcome. The only repair is to move the value's birth to after the deadline. Commit to a future round, close entries, then read that round's value once it exists.
:::

Example 6-17 in Chapter 6 is the same failure in four lines, without the mixing that makes this version look defensible. Neither can be rescued by choosing a different round: every round `op.Block` will accept is a round that is already committed and already public.

The two neighbouring temptations fail earlier than that. A transaction's id is a hash of its own fields, so the sender computed it, and chose it, before anybody else saw it: that fails the first property outright and the second with it. A block's timestamp is a number the proposer writes, and the protocol checks it loosely enough that Chapter 6 tells you not to treat it as a measurement --- so it is neither unchosen nor hard to predict. Neither is a draw. Both are values somebody picked.

## Committing to Something You Have Not Shown
Moving a value's birth to after the deadline needs a way to bind somebody to a choice before that choice can be read. The primitive is a commitment: a hash stored now, an opening supplied later, and one comparison deciding whether the two agree.

*Predict: a party must be unable to change their number after seeing everybody else's, and unable to withhold it forever. Say what has to be submitted at each of those two moments, and what the contract holds in between.*

**Example 18-2.** A sealed bid

<!-- finder: fix a value now and reveal it later, verifiably -->

```python
from algopy import ARC4Contract, Bytes, GlobalState, arc4, op


class SealedBid(ARC4Contract):
    """Commit to a value now, reveal it later, and be held to it.

    The commitment is a hash. It says nothing about the value until the
    opening is supplied, and once supplied it admits exactly one value --
    which is what makes a sealed-bid auction possible without a trusted
    party holding the bids.
    """

    def __init__(self) -> None:
        self.commitment = GlobalState(Bytes())

    @arc4.abimethod
    def commit(self, digest: Bytes) -> None:
        assert self.commitment.value.length == 0, "already committed"
        self.commitment.value = digest

    @arc4.abimethod
    def reveal(self, amount: arc4.UInt64, nonce: Bytes) -> None:
        # The nonce is not decoration. Without it a bid is drawn from a small
        # set and the commitment is broken by hashing every candidate.
        assert nonce.length >= 32, "nonce must be unguessable"
        assert op.sha512_256(amount.bytes + nonce) == self.commitment.value
```

A party submits `sha512_256(value || nonce)`, which reveals nothing about the value; when the deadline passes they submit the value and the nonce, and the contract checks the hash. The two hash properties are what make that work: binding stops the value being changed afterwards, and hiding stops it being read before. One slot and one commitment, written as a sealed bid because an auction is where most people first meet the primitive. Chapter 22 returns to that auction and prices it; Chapter 23 keys the same shape by voter --- one box per sealed *ballot*, so everyone can commit at once; and the auction itself is never assembled for you: it is the Part VI Mastery Checkpoint's commission, deliberately yours.

The nonce is the part people leave out, and without it the scheme breaks completely. Bid amounts come from a small set: round numbers, in a known range, with a known number of decimals. An attacker who wants to know your bid hashes every plausible amount and compares. With a 32-byte nonce there is nothing to enumerate.

::: {.gotcha #commitment-without-a-nonce topic="Cryptography" title="A commitment to a low-entropy value is not hiding anything"}
`sha512_256(amount)` is a lookup table away from being plaintext when `amount` is one of a few thousand plausible numbers. The commitment hides a value only if the value is unguessable, so commit to `value || nonce` with at least 32 bytes of nonce and treat the nonce as a secret until the reveal.

The same reasoning applies to any commitment over a small domain: a vote among four options, a yes/no, a choice of counterparty. If it can be enumerated, hash it with something that cannot.
:::

A commitment gets you a draw as well as an auction, and this is where most teams start: every entrant commits to 32 random bytes, everyone reveals after entries close, and the winner comes from the exclusive-or of the revealed values. Nobody chose the result, since one honest contributor is enough to scramble it, and anybody can check it. What it fails is delivery. The last account to reveal sees every other value and can compute the outcome before deciding whether to reveal at all, so an entrant who dislikes the answer simply goes quiet and the draw stalls. Deposits forfeited on non-reveal reduce that to a price rather than removing it, and the price is worth paying whenever the prize is larger than the deposit.

**So the value everybody depends on should not be anybody's to withhold.** Commit to a *round* instead of to a secret.

## Naming a Round That Does Not Exist Yet
Chapter 6 built that shape as Example 6-16: `enter` counts entrants while the draw is open, `commit` fixes a target round between sixteen and a thousand rounds ahead and refuses every entry after it, and `ready` reports whether the target round has passed. The raffle at the end of this chapter re-implements that shape rather than importing it, and adds two things to it: the beacon call itself, and a pot to pay out.

*Predict: suppose entries were still accepted after `commit` names the target round. Say what a late entrant could do that an early one could not, and name the exact moment at which that stops being an advantage and becomes one.*

The security property is entirely in the ordering, and it is the one thing to carry out of this chapter into every draw you ever build. **The value the outcome depends on must not exist at the moment the last entrant is bound to depending on it.** Two rounds in the timeline decide that: the round the last entry is accepted, and the round the target's value is born. Keep the first strictly before the second and the draw is sound; let them meet and it is not.

Closing entries at `commit` is the strict version of that rule and it is the one to write, because it needs one guard instead of two. The looser version, in which entries stay open until the target round arrives, is sound on paper but makes the contract compare against a round rather than against a flag, on every entry, forever. Name a round that has already passed and no version is sound: its value is published, and whoever calls `commit` has read it.

The upper bound is a product decision rather than a protocol fact. It bounds how long entrants' money sits in a contract with no way out, and a thousand rounds is roughly three-quarters of an hour.

Example 6-16 stops at establishing the target round and fetches nothing, because there is no safe way to fetch a value from the block. What goes in that slot is a randomness beacon.

## Asking the Beacon
You have a target round and nothing to read from it. A randomness beacon is an application that fills that slot: it publishes unpredictable values on a schedule of its own and answers questions about rounds that have passed. ARC-21 is the interface, and it is small. Two mandatory methods, `get(uint64,byte[])byte[]` and `must_get(uint64,byte[])byte[]`, both taking a round and a caller-supplied byte string the standard says nothing further about.

Read the ARC for the interface and the deployed contract's own documentation for everything else. Publishing on multiples of eight, retaining roughly the last fifteen hundred rounds, and folding that byte string into the answer so two consumers reading one round get different values are all properties of the beacon the Foundation runs rather than of the standard, and a different deployment could choose differently. The two live deployments are application `600011887` on TestNet and `1615566206` on MainNet, and both implement exactly the two mandatory methods.

The publishing schedule reaches back into `commit`. The raffle's `commit` rounds its target up to the next multiple of eight, and what that removes is a window of refusals rather than a wait for the value: the beacon *stores* on multiples of eight and *answers* for every round at or below the newest stored one, so a target that is not a multiple leaves one to seven rounds in which the draw's round guard is already open and the read still comes back empty --- `beacon has nothing there`, until the next multiple lands. Rounding up to the multiple closes that window, and it can only lengthen the lead, which is why it rounds up rather than down. It also means the lead is a range.

::: {.gotcha #beacon-lead-is-a-range topic="Arithmetic and time" title="A sixteen-round lead is really sixteen to twenty-three rounds"}
`commit(lead=16)` rounded up to the next multiple of eight gives an effective lead of 16 to 23 rounds, never exactly 16, and which one you get depends on where the chain happened to be. Anything that quotes the lead to a user, times out on it, or computes a deadline from it has to carry the whole range: at two and three-quarter seconds a round that is between forty-four and sixty-three seconds, and a client that shows the low end will show a countdown that finishes before the draw does. Write the modulus and the minimum as named constants beside each other, so that whoever changes one is looking at the other.
:::

Two things come back empty and they are not the same problem. A round above the newest stored round has nothing *yet*, which is what a draw settled too eagerly sees. A round about fifteen hundred rounds back has nothing *any more*, which is what a draw settled too late sees. Both arrive as the same empty slice, so a contract that wants to tell its user which one they are looking at has to work it out from the distance between the target round and `Global.round`.

*Predict: your contract calls the beacon and the beacon has nothing for the round you asked about. Two methods, two behaviours. Say what each one should do, and which of the two failures your user could act on.*

**Example 18-3.** Reading a beacon value

<!-- finder: read a randomness beacon from inside a contract -->

```python
from algopy import ARC4Contract, Bytes, Global, GlobalState, Txn, UInt64, arc4


class BeaconReader(ARC4Contract):
    """Read one ARC-21 beacon value, by each of the two mandatory methods."""

    def __init__(self) -> None:
        self.beacon = GlobalState(UInt64(0))

    @arc4.abimethod
    def set_beacon(self, app_id: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.beacon.value == UInt64(0), "beacon already set"
        self.beacon.value = app_id

    @arc4.abimethod
    def value_at(self, rnd: UInt64) -> Bytes:
        assert rnd < Global.round, "that round has not happened yet"
        value, _txn = arc4.abi_call[arc4.DynamicBytes](
            "get(uint64,byte[])byte[]", arc4.UInt64(rnd),
            arc4.DynamicBytes(b""), app_id=self.beacon.value, fee=0)
        # Absence arrives as an empty slice, so it is a value to branch on.
        assert value.native.length == UInt64(32), "beacon has nothing there"
        return value.native

    @arc4.abimethod
    def value_at_strict(self, rnd: UInt64) -> Bytes:
        assert rnd < Global.round, "that round has not happened yet"
        value, _txn = arc4.abi_call[arc4.DynamicBytes](
            "must_get(uint64,byte[])byte[]", arc4.UInt64(rnd),
            arc4.DynamicBytes(b""), app_id=self.beacon.value, fee=0)
        return value.native
```

The call is Chapter 15's `arc4.abi_call` by signature string, because there is no beacon source to import. Both methods take the same round, and the transcript asks both of them for a round the beacon never published.

```console
>>> # the beacon has a value for `target` and none for `missing`
>>> bytes(reader.value_at(target).abi_return) == published_value
True
>>> caller_sees(reader.value_at(missing))  # get, then this assert
beacon has nothing there
>>> caller_sees(reader.value_at_strict(missing))     # must_get
inner tx 0 failed: logic eval error: assert failed pc=198
```

The two answers are not interchangeable.

`get` returns absence as an empty byte string. That is a value, so the calling contract branches on it and raises its own assertion, and the user is told `beacon has nothing there` --- a sentence written by the person who wrote the contract the user called.

`must_get` asserts inside the beacon, and the beacon's message does not survive the trip. What comes back is `assert failed pc=198` wrapped in `inner tx 0 failed`: a program counter into a program the user has never heard of. The sentence the beacon's author wrote is left behind in the beacon's own ARC-56 specification, which is not the specification the client raising this error is holding. Nothing in the returned string says which of the two programs the 198 belongs to.

**That asymmetry only exists across an application call.** Call the beacon directly from a client and `must_get` reports its own assertion perfectly well, which is exactly why the choice looks like a style question right up until the first support ticket. The consequence for ARC-21 is a rule: an on-chain consumer calls `get` and raises its own assertion against the empty result; `must_get` is for a client calling the beacon directly, where the message survives.

::: {.gotcha #must-get-loses-the-message topic="Cross-contract calls" title="A callee's assert message does not survive an inner application call"}
When your contract calls another application and the callee's own `assert` fires, what reaches your user is `inner tx 0 failed: logic eval error: assert failed pc=<n>`. The callee's ARC-56 message is not in it, and the program counter is an offset into the callee rather than into anything the caller's specification can explain. The same failure raised by a direct client call to the callee is fully described, so this cannot be found by testing the callee. If the callee offers a variant that returns absence as a value, take it --- an error you can name is worth more than one you have to explain.
:::

Two costs come with the read and neither is large. `fee=0` on the inner call puts its fee on the caller through fee pooling, so a submitted read needs a `static_fee` of 2,000: one minimum fee for the outer call, one for the inner. And the whole method consumes 131 opcode units against the 1,400 available, because the pool gains 700 for the call itself and another 700 for each inner transaction that is *itself an application call*. An inner payment adds nothing. No `ensure_budget`, no op-ups.

The reference list stays short because of a design decision in the beacon rather than in your contract. The deployed one keeps its values in global state, so a consumer declares the beacon's application id and nothing else. A box-backed beacon would make every consumer declare a box it does not own and cannot name reliably.

## What Verification Buys, and What It Cannot
A beacon that publishes whatever it likes satisfies the third property only in a bookkeeping sense: everybody can recompute the outcome from the published value, and nobody can tell whether the value was drawn or chosen. What closes that gap is a verifiable random function. The operator holds a key, the value is that key applied to the round, and it comes with a proof that anybody --- including a contract --- can check.

`vrf_verify` does the checking, at 5,700 opcode units, which is more than eight times an application call's entire budget. Chapter 22 builds a beacon around it as Example 22-6 and prices the consequences: a method sized by `ensure_budget` runs for nothing when a client asks it read-only, and needs a `static_fee` of 9,000 the moment anything submits it.

*Predict: the operator computes the value, dislikes it, and says nothing at all. Name what your contract can still do, given that no assertion inside it can make somebody else's application speak.*

**Verification bounds the operator to one value per round and no more.** It does not compel them to publish. Withholding is the residual power in every beacon design, and an operator who exercises it leaves a draw with nothing to read and no way to re-commit. The defence a production draw actually carries is an exit: a deadline after which the draw is abandoned and the entrants get their money back, which the lottery project builds. Running against more than one beacon, or allowing a re-commit after a timeout, are the alternatives, and each buys a different thing.

One more thing rules out the shortcut. The chain's own block seed is a VRF output, so it is fair to ask why a contract cannot verify that instead of trusting a beacon. It cannot, because the proof is not there. A block header carries the seed and no proof of it, and no opcode returns one. A beacon publishes the proof that consensus does not.

## The Raffle, Start to Finish
A raffle needs all five: entries, a commitment to a round, the beacon read, the fee that read costs, and the choice of `get` over `must_get`. Entrants buy a ticket, the operator closes entries against a round that does not exist yet, and once that round has passed anybody at all can settle the draw.

**Example 18-4.** A raffle that enters, commits, draws and pays

<!-- finder: run a raffle from entry to payout -->

```python
from algopy import (Account, ARC4Contract, BoxMap, Global, GlobalState, Txn,
                    UInt64, arc4, gtxn, itxn, op)

BEACON_ROUND_MODULUS = 8      # the deployed beacon stores on multiples of 8 and
                              # answers no round above its newest stored one
MIN_LEAD_ROUNDS = 16          # rounded up, so the lead is really 16 to 23
MAX_LEAD_ROUNDS = 1_000       # how long an entrant's money may be locked up
ENTRY_BOX_MBR = 18_900        # 2,500 + 400 x (1 + 8 name, 32 value)
TICKET_PRICE = 100_000


class Raffle(ARC4Contract):
    """Enter, close entries against a future round, then draw."""

    def __init__(self) -> None:
        self.beacon = GlobalState(UInt64(0))
        self.target_round = GlobalState(UInt64(0))
        self.entrants = GlobalState(UInt64(0))
        self.pot = GlobalState(UInt64(0))
        self.winner = GlobalState(Account())
        self.entry = BoxMap(UInt64, arc4.Address, key_prefix=b"e")

    @arc4.abimethod
    def configure(self, beacon: UInt64) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.beacon.value == UInt64(0), "already configured"
        self.beacon.value = beacon

    @arc4.abimethod
    def enter(self, ticket: gtxn.PaymentTransaction) -> UInt64:
        assert Global.group_size == UInt64(2), "expected payment + app call"
        assert self.beacon.value != UInt64(0), "no beacon configured"
        assert self.target_round.value == UInt64(0), "entries are closed"
        assert ticket.receiver == Global.current_application_address, "not ours"
        assert ticket.amount == UInt64(TICKET_PRICE), "wrong ticket price"
        assert ticket.sender == Txn.sender, "pay for your own ticket"
        index = self.entrants.value
        self.entry[index] = arc4.Address(Txn.sender)
        self.entrants.value = index + UInt64(1)
        self.pot.value += UInt64(TICKET_PRICE - ENTRY_BOX_MBR)
        return index

    @arc4.abimethod
    def commit(self, lead: UInt64) -> UInt64:
        assert Txn.sender == Global.creator_address, "creator only"
        assert self.beacon.value != UInt64(0), "no beacon configured"
        assert self.target_round.value == UInt64(0), "already committed"
        assert self.entrants.value > UInt64(0), "nobody entered"
        assert lead >= UInt64(MIN_LEAD_ROUNDS), "too close to predict"
        assert lead <= UInt64(MAX_LEAD_ROUNDS), "lead is too long"
        # Round UP to a publish round: that can only lengthen the lead.
        raw = Global.round + lead
        m = UInt64(BEACON_ROUND_MODULUS)
        self.target_round.value = raw + (m - raw % m) % m
        return self.target_round.value

    @arc4.abimethod
    def draw(self) -> arc4.Address:
        assert self.target_round.value != UInt64(0), "nothing committed yet"
        assert self.winner.value == Global.zero_address, "already drawn"
        assert Global.round > self.target_round.value, "target round has not passed"
        # `get`, not `must_get`: the callee's message dies in an inner call.
        value, _txn = arc4.abi_call[arc4.DynamicBytes](
            "get(uint64,byte[])byte[]", arc4.UInt64(self.target_round.value),
            arc4.DynamicBytes(b""), app_id=self.beacon.value, fee=0)
        assert value.native.length == UInt64(32), "beacon has nothing there"
        digest = op.sha512_256(value.native)
        # `entrants` cannot be zero here: `commit` refused a draw with none,
        # and `enter` has been closed since, so the modulo cannot divide by
        # zero. Add a path that DELETES an entry and that argument is gone.
        index = op.btoi(op.extract(digest, 24, 8)) % self.entrants.value
        self.winner.value = self.entry[index].native
        itxn.Payment(receiver=self.winner.value, amount=self.pot.value,
                     fee=0).submit()
        self.pot.value = UInt64(0)
        return arc4.Address(self.winner.value)
```

`enter` asks Chapter 7's four questions, narrowed the way Example 10-16 narrowed them: an Algo payment has no asset to check, which leaves who paid, who they paid, and how much. The group-size assertion above them is what makes the other three worth writing --- pin the pair at two transactions and a third cannot be appended to reuse a payment these checks have already approved. A box costs 2,500 plus 400 a byte, which for a one-byte prefix, an eight-byte key and a 32-byte address is 18,900 microAlgo, and Chapter 11 established who is billed: the application account holds the box, so the application account pays, and a contract that does not charge for its boxes is funding strangers. The rest of the ticket goes to the pot, which is why `pot` is a counter rather than a balance. The account also holds every box's minimum balance, and Chapter 7 made the general point that an application's balance is not its ledger.

`draw` is callable by anybody. That is deliberate and it is what a permissionless settlement looks like: the money goes to the entrant the beacon picked, never to the caller, so the only thing an unexpected caller can do is pay the fee on your behalf. `winner` starts at the zero address and is written once, which turns the second call into a refusal rather than a second payment.

The beacon's 32 bytes become an entrant by way of `op.btoi(op.extract(digest, 24, 8)) % self.entrants.value` --- the last eight bytes of a hash of the beacon value, read as a number, reduced by the count. That is the mapping everybody writes; Exercise 4 asks how far from uniform it really is.

**The fee is 3,000 and the contract does not say so anywhere.** One minimum fee for the call, one for the beacon read, one for the payment to the winner, both inner transactions carrying `fee=0`. The driver checks that 2,000 is refused, and it has to publish a beacon value first to see that: fee credit is charged as each inner transaction submits rather than against the group up front, so at 2,000 the beacon read still goes through on the one spare fee and the shortfall does not appear until the payment.

The application account's own 100,000 floor is the deployer's to fund. Until that happens the first `enter` is refused by the ledger for a balance below the minimum, because the ticket brings the account to 100,000 and the box it pays for needs 118,900.

*Predict: five tickets at 100,000 microAlgo each, and one winner. Say what the winner receives, and why it is not 500,000.*

```console
>>> # five tickets at 100,000 microAlgo, one box each
>>> raffle.send.enter(pay(100_000)).abi_return   # the fifth entry
4
>>> caller_sees(raffle.draw())                # before any commit
nothing committed yet
>>> target = raffle.send.commit(lead=16).abi_return
>>> target % 8, 16 <= target - committed_at <= 23
(0, True)
>>> caller_sees(raffle.enter(pay(100_000)))   # after the commit
entries are closed
>>> caller_sees(raffle.draw())            # target round is ahead
target round has not passed
>>> # rounds pass, and the beacon publishes for the target round
>>> raffle.send.draw().abi_return == entrants[3]
True
>>> winner_balance_after - winner_balance_before   # the whole pot
405500
>>> caller_sees(raffle.draw())                    # a second time
already drawn
```

That transcript is the opening commission, run in order: tickets sold at one price, entries closed against a round that did not yet exist, and a draw anybody could have settled that paid exactly once. Three of the four refusals are a property defending itself. `entries are closed` keeps the last entrant from knowing the target round before they commit to depending on it. `target round has not passed` keeps the draw from reading a round the beacon cannot have published. `nothing committed yet` keeps a draw from happening against no round at all. The fourth, `already drawn`, is bookkeeping: it turns a repeated call into a refusal rather than a second payment. The pot arrives whole at 405,500 --- five tickets of 100,000 microAlgo, less the 18,900 each entrant's box costs.

::: {.gotcha #draw-fee-is-invisible-in-the-source topic="Resource references, MBR, and budget" title="A method that makes inner transactions carries a fee its own source never states"}
`fee=0` on an inner transaction means the caller pays for it, so a method making two inner transactions needs three minimum fees on the outer call and there is nothing in the contract that says three. A client written from the contract alone sends one, and the failure it gets back is `group fee 0.0A too small (needs 1mA more)` at whichever `itxn_submit` ran out --- which is not necessarily the first one, because the credit is checked as each inner transaction submits rather than against the whole group before the program runs. A method whose first inner transaction succeeds and whose second fails is underpaid rather than broken. Count the inner transactions on every path, take the largest, and send that many fees.
:::

## Retrieval
Answer these from memory before moving on. Three of them reach back into earlier chapters on purpose.

1. Name the three properties a draw has to have, and say which one a block seed fails.
2. A contract hashes the block seed together with the caller's address and a caller-supplied salt. Name what that fixes and what it does not, and say what the extra inputs cost the attacker.
3. What does the nonce in a commitment do, and what is the attack when it is missing?
4. Every entrant commits to 32 random bytes and reveals after entries close. Which of the three properties does that satisfy, and what goes wrong at reveal time?
5. `commit(lead=16)` against the deployed beacon. What is the effective lead, and why is it not sixteen?
6. Your contract reads a beacon and the beacon has nothing for that round. What does the user see under `get`, and what do they see under `must_get`?
7. *(From Chapter 6)* `blk_timestamp(Global.round - 1)` compiles. Name the one circumstance in which it succeeds, and say why algosdk and AlgoKit Utils make that circumstance unreachable.
8. *(From Chapter 7)* What does `fee=0` on an inner transaction mean, and who ends up paying?
9. *(From Chapter 11)* A raffle stores one entrant per box. Which account is billed, and what does that force `enter` to require?
10. Why can a contract not verify the block seed's own VRF proof?

## Exercises

1. **(Trace)** Walk Example 18-1's transcript as a timeline.

   (a) For each of the five values the attack turns on --- the round `mint` will read, that round's seed, the tier for a given ticket, the winning ticket, and the tier the contract returns --- say at which step the attacker first knows it and at which step the chain first knows it.

   (b) Name the single moment at which the outcome becomes knowable to the caller, and say how many of the attacker's transactions the chain has seen by then.

   (c) The mint has 64 tiers and the attacker wants tier 0. Work out the expected number of tickets tried before one wins, recompute it for 4 tiers, and say whether fewer tiers makes the design safer, more dangerous, or neither.

2. **(Parsons)** Below are seven statements. Five of them form the body of a `commit` method that closes entries and names a target round; two do not belong. `self.target_round` and `self.entrants` are `GlobalState(UInt64)`, and `MIN_LEAD_ROUNDS` and `BEACON_ROUND_MODULUS` are module constants.

   ```python
   @arc4.abimethod
   def commit(self, lead: UInt64) -> UInt64:
       ...
   ```

   The statements: (1) `assert Txn.sender == Global.creator_address, "creator only"`; (2) `assert self.target_round.value == UInt64(0), "already committed"`; (3) `assert self.entrants.value > UInt64(0), "nobody entered"`; (4) `assert lead >= UInt64(MIN_LEAD_ROUNDS), "too close to predict"`; (5) `raw = Global.round + lead`; (6) `raw = Global.round - lead`; (7) `self.target_round.value = raw - raw % UInt64(BEACON_ROUND_MODULUS)`.

   (a) Select the five that belong and order them.
   (b) Add the one line the set is missing.
   (c) Reject (6) is the whole chapter backwards: say who exploits it and what they read before calling `commit`.
   (d) Reject (7) rounds down instead of up and passes every test you would think to write: say how many rounds it can quietly remove from the lead.

3. **(Debug)** A raffle has been running for a month. Entries close, the operator commits, the target round passes, and `draw` fails with `beacon has nothing there`. It has happened twice in thirty draws, both times on a draw nobody settled for a day or two, and both times the raffle was left stuck: `commit` refuses to run again once `target_round` is set, and `draw` has nothing to read.

   (a) Write down every reason a beacon can have no value for a round that has passed. There are at least three, and they need different fixes.

   (b) Say which of your reasons fits a failure rate of two in thirty that only ever hits slow settlements, and compute the beacon's retention window in minutes to convict it.

   (c) Give the smallest change to the contract that would have let those two draws settle, and say why a bare `reset` method is not it.

4. **(Compare)** The beacon hands your contract 32 bytes and you need a winner out of `n` entrants. Example 18-4 takes the last eight bytes as a `uint64` and reduces them modulo `n`, which is not the only option and is not unbiased.

   (a) Compare that mapping against two alternatives --- rejecting and rehashing whenever the value falls in the short tail that would skew the result, and reducing the whole 32 bytes as a `BigUInt` with Chapter 6's wide arithmetic --- on opcode cost, on worst-case iterations, and on what a losing entrant must recompute to check the answer.

   (b) Do the arithmetic before arguing: reducing 2^64^ values modulo `n` leaves the most likely entrant with `ceil(2^64^ / n)` of them and the least likely with `floor(2^64^ / n)`. Express the bias as the ratio of those two, then evaluate it for `n = 5`, for `n = 2^40^` and for `n = 2^63^ + 1` --- one of the three is exactly 1, and it is worth working out what makes it different.

   (c) Name the change to the *prize* rather than to `n` that would make the unbiased mappings worth their price.

5. **(Extend)** Example 18-4 pays the whole pot to one entrant and keeps every box forever. Extend it so that the operator can retire a settled raffle: delete the entry boxes, recover their minimum balance, and open the contract for a new round of entries. Three decisions come before any code, and each has a wrong answer that looks right.

   (a) Decide who may retire a raffle, and what stops that power being used mid-draw.

   (b) Decide where the recovered box minimum balance goes, given that the entrants paid it.

   (c) Decide what must be true of `winner` and `pot` before a retirement may proceed.

   (d) Write the method, then write down the sequence of calls that would drain the contract if you had got (c) wrong. Chapter 19 builds its own version; finish yours before you read it.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can state the three properties a draw must have and test any proposed source against them, and I can say which property a block seed, a transaction id and a block timestamp each fail.
- [ ] I can explain why hashing a public seed with the caller's address does not make it unpredictable, and describe the search an attacker runs and what it costs them.
- [ ] I can write a commitment over `value || nonce`, say what the nonce is for, and name the failure mode of a draw built on participant reveals.
- [ ] I can close entries against a future round, compute the effective lead from the minimum and the beacon's publishing modulus, and say what verifying the beacon's proof does and does not buy me.
- [ ] I can build a raffle whose `enter` charges for its own box, whose `commit` names a round that does not exist yet, and whose `draw` anybody may call and only pays once, and I can state the fee each of its calls needs.

## Handoff: The Draw the Lottery Project Inherits
Chapter 19 builds a lottery that sells tickets, closes them against a round nobody has seen, and then has two endings: a winner paid, or every ticket handed back on the day the beacon says nothing at all. Table 18-1 lists what it takes from here, and what to predict before you read it.

: Table 18-1. What Chapter 19 draws on from this chapter

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| Example 18-4 | The whole shape: enter, commit, draw, pay | The project has a second ending this raffle does not. Say what the contract owes each entrant when the draw has become impossible, and what state has to record that the draw never happened. |
| Example 18-3 | Every read of the randomness beacon | The project points one configured application id at a stub on LocalNet and at the deployed beacon on TestNet, with the contract byte-identical either way. Say what has to be true of the stub for that to hold. |
| Example 6-16 | The target-round commitment, re-implemented from it | The project's `commit` writes a second round as well as the target. Say what a deadline fixed at commit time gives the entrants that one computed later does not. |
| The lead range | The window a draw is allowed to happen in | A `commit(lead=16)` and a draw window three hundred rounds wide. Work out the earliest and the latest round a draw can land on, then say what a countdown should show an entrant instead of either end of the lead. |
| The third property, checkability | The winner derivation, and the test that recomputes it off chain | A losing entrant has to be able to redo the draw. List every value they need for that, and say where each one is readable from once the raffle has settled. |
