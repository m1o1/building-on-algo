\newpage

\part{Cryptography}

Part VI prices the AVM's cryptographic opcodes and puts them to work. Chapter 22 is a cost survey: a sealed-bid commitment scheme on hashes and signature checks, and the failure that makes an expensive check worthless. The private-governance voting project that used to assemble those primitives is companion material, pointed at the end of this chapter; Part VII is shipping.

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# Proving Things Without Revealing Them

A contract that checks `Txn.sender` learns who signed. Everything in this chapter is about learning something *else*: that a value was fixed before it was revealed, that a key you have never seen approved a message, that an address is one of ten thousand on a list you are not storing, or that a computation was performed correctly by somebody who will not show you the inputs.

None of that needs new trust. It needs primitives, and the AVM has them. It also prices them, and the prices shape the design.

## A Sealed Bid on a Public Chain
A DAO auctions a batch of tokens. Bids go into a contract, the highest wins, and the settlement is verifiable because that is the point of doing it on chain.

A bid has to be two things at once. It has to bind, so nobody can change it after seeing what else came in, and it has to stay hidden until bidding closes, so nobody can price theirs against it. Writing it to the chain in the clear buys the first and forfeits the second: every bid is public the moment it lands, and reading the current highest before placing yours is not an exploit, it is the interface.

Hiding the bids in a private database trades that for its mirror image. Nobody reads a bid early, and nobody can verify the winner either.

Neither half is negotiable, so what goes on chain has to bind without being readable --- and the AVM has the primitive for it, at a cost small enough that the auction is the easy case rather than the hard one.

::: {.spec title="Your commission: a sealed-bid auction that settles in public"}
The DAO's next auction runs on chain end to end, and the cryptography is your job. It must:

1. Take bids that bind the moment they land and stay unreadable until the close
2. Check each bidder's approval --- signed off chain by the DAO's KYC provider --- without letting a signature for one operation authorise another
3. Admit any of ten thousand approved addresses while storing 32 bytes, not the list
4. Run every check inside an opcode budget its caller can afford, with the fee known before submission
5. Never mistake the cost of a check for what it proves

Five requirements. The first four are priced primitives and the chapter takes them in order --- a priced tour rather than one running build, deliberately, because the assembly is saved for the Part VI checkpoint; the fifth is a discipline, and the closing section is a contract that has everything except it.
:::

By the end of this chapter you will be able to:

- Choose a hash for what it costs and what it is for, and say why the Ethereum-compatible one is not the default here
- Say what a commitment costs to make and to check, and why proving one changes which hash you reach for
- Verify a signature made off chain, say what it does and does not prove, and separate domains so one signature cannot authorise two operations
- Recover a signer's key from an ECDSA signature, Ethereum-style
- Prove membership of a large set while storing 32 bytes, and price the verification honestly
- Price the on-chain check of a VRF proof, and say why the bill appears only when a call is actually submitted
- Say what a `BN254g1` pairing check costs, why naming the other group changes the price, and where extra budget comes from

## The Prices
Every primitive in this chapter is priced, and the prices differ by more than an order of magnitude. That decides, before anything else does, which of them can run in an application call at all. Table B-2 in Appendix B is the whole set on one page.

**Example 22-1.** Three hashes, three prices

<!-- finder: choose a hash by what it costs -->

```python
from algopy import ARC4Contract, Bytes, arc4, op


class Hashes(ARC4Contract):
    """Three hashes, three prices, and one of them is the default for a reason.

    `sha512_256` is Algorand's own: addresses, transaction ids and merkle
    nodes all use it. `keccak256` exists for Ethereum compatibility and costs
    nearly three times as much -- so reaching for it out of habit is a bill
    for interoperability you may not need.
    """

    @arc4.abimethod(readonly=True)
    def native(self, data: Bytes) -> Bytes:
        return op.sha512_256(data)          # 45

    @arc4.abimethod(readonly=True)
    def bitcoin_style(self, data: Bytes) -> Bytes:
        return op.sha256(data)              # 35

    @arc4.abimethod(readonly=True)
    def ethereum_style(self, data: Bytes) -> Bytes:
        return op.keccak256(data)           # 130
```

`sha512_256` is Algorand's native hash, used by addresses, transaction ids and merkle nodes alike, and it costs 45 units. `sha256` costs 35. `keccak256` costs 130, which is nearly three times the native one, and it exists so that hashes computed on Ethereum match hashes computed here.

*Predict: you are writing a contract with no Ethereum integration and no external requirement about hash algorithms. Which of the three should you reach for, and what is the cost of reaching for the wrong one in a loop of forty iterations?*

The answer is `sha512_256`, and the reason people do not is habit: a developer arriving from Solidity types `keccak256` without thinking, because there it is the default and the only one. Here it is a bill for compatibility with a chain you are not talking to. Forty iterations is 5,200 units against 1,800. An application call has 700, so both need `ensure_budget` and one needs a good deal more of it.

::: {.gotcha #keccak-is-not-the-default topic="Cryptography" title="`keccak256` is for Ethereum compatibility, not for hashing"}
It costs 130 units against `sha512_256`'s 45 and `sha256`'s 35, and buys nothing unless a digest has to match one computed on Ethereum: verifying an Ethereum signature, checking a merkle root produced by an Ethereum contract, deriving an Ethereum address. For anything internal to your own contract, the native hash is nearly three times cheaper and is what the rest of the protocol already uses.
:::

## Committing to a Value
Chapter 18 built the primitive that closes the auction: `sha512_256(value || nonce)` stored now, the value and the nonce supplied later, one comparison deciding whether they agree. Example 18-2 is the whole of it, and the nonce is what stops a small set of plausible bids being enumerated against the digest.

What this chapter adds is the price, and the fact that the hash is a choice rather than a given. Committing costs one hash to make and one to check, so at 45 units the auction never notices. It stops being free the moment a commitment has to be *proved* correct rather than merely checked, because a zero-knowledge circuit pays for every bit of the hash inside the proof system. That is why a circuit prefers `mimc` even though the native hash is cheaper on chain, and why Example 22-8 is the example that prices a budget rather than an opcode. Example 22-5, further on, is the same primitive one level up: a commitment to a whole set instead of to a single value.

## Verifying a Signature the Chain Never Saw
An oracle attesting to a price, a game server signing a result, a KYC provider signing an approval: the authority a contract acts on does not always originate on the chain. Making it arrive as a transaction costs an account, a fee and a round, for a fact that has already been signed.

**Example 22-2.** An off-chain approval

<!-- finder: check a signature made by a key that never signed a transaction -->

```python
from algopy import (ARC4Contract, Bytes, OpUpFeeSource, UInt64, arc4,
                    ensure_budget, op)


class OffchainApproval(ARC4Contract):
    """Verify a signature the chain never saw being made.

    The signer is offline. They sign a message with an Ed25519 key, somebody
    else submits it, and the contract checks it -- so authority is proven by
    the signature rather than by who sent the transaction.
    """

    @arc4.abimethod(readonly=True)
    def approved(self, message: Bytes, sig: Bytes, pubkey: Bytes) -> bool:
        # 1900 units against an application call's 700, so the budget has
        # to be raised before the opcode is reached.
        ensure_budget(UInt64(2_000), OpUpFeeSource.GroupCredit)
        return op.ed25519verify_bare(message, sig, pubkey)
```

`ed25519verify_bare` takes a message, a signature and a public key, and returns whether they agree. The signer never sent a transaction, never paid a fee, and may not have an Algorand account at all.

It costs 1,900 units, which is nearly three times an application call's entire 700-unit budget. Every use of it needs `ensure_budget` or a group with room in it.

What a signature proves is narrower than it looks.

*Predict: a signature over `amount` verifies against the KYC provider's key. Write down what that establishes --- and what a second method that verifies the same bytes would accept.*

**Example 22-3.** The same key, two meanings

<!-- finder: stop a signature being valid for something it was not meant for -->

```python
from algopy import (ARC4Contract, Bytes, OpUpFeeSource, UInt64, arc4,
                    ensure_budget, op)


class TwoKindsOfMessage(ARC4Contract):
    """A signature proves who signed. It does not prove what they meant.

    `ed25519verify` (not `_bare`) prepends "ProgData" and the program hash
    before verifying, which is domain separation built into the opcode. With
    `_bare` you get the raw message and must separate domains yourself --
    otherwise a signature collected for one purpose is valid for another.
    """

    @arc4.abimethod(readonly=True)
    def withdraw_approved(self, amount: Bytes, sig: Bytes, key: Bytes) -> bool:
        # The prefix is what stops this signature also authorising a refund.
        ensure_budget(UInt64(2_000), OpUpFeeSource.GroupCredit)
        return op.ed25519verify_bare(Bytes(b"withdraw:") + amount, sig, key)

    @arc4.abimethod(readonly=True)
    def refund_approved(self, amount: Bytes, sig: Bytes, key: Bytes) -> bool:
        ensure_budget(UInt64(2_000), OpUpFeeSource.GroupCredit)
        return op.ed25519verify_bare(Bytes(b"refund:") + amount, sig, key)
```

A signature proves that the holder of a key signed *these bytes*. It does not say what the bytes meant. If your withdraw path verifies `sig` over `amount`, and your refund path verifies `sig` over `amount`, then a signature collected for one is valid for the other, and whichever pays more is the one the attacker submits.

The repair is a prefix. `b"withdraw:" + amount` and `b"refund:" + amount` are different messages, so a signature over one is not a signature over the other. That is domain separation, and it is why the non-`_bare` `ed25519verify` prepends `"ProgData"` and the program hash before verifying: it separates domains for you, at the cost of only being usable in the context that hash refers to.

::: {.gotcha #signature-does-not-prove-intent topic="Cryptography" title="A signature proves who signed, never what they meant"}
Verification tells you a key produced a signature over some bytes. It says nothing about which of your code paths those bytes were intended for, so any two paths verifying a signature over the same message accept each other's signatures. Prefix every signed message with a domain string naming the operation, and include anything that scopes it --- the application id, a nonce, an expiry --- inside the signed bytes rather than beside them.
:::

**Example 22-4.** Recovering the signer

<!-- finder: derive a signer's key from an ECDSA signature -->

```python
from algopy import (ARC4Contract, Bytes, OpUpFeeSource, UInt64, arc4,
                    ensure_budget, op)


class EthereumBridge(ARC4Contract):
    """Recover the signer's key from a signature, Ethereum-style.

    `ecdsa_pk_recover` returns the public key that produced a signature,
    which is how Ethereum identifies signers -- there is no key in the
    message, only a signature the key can be derived from.
    """

    @arc4.abimethod(readonly=True)
    def signer_of(
        self, digest: Bytes, recovery: UInt64, r: Bytes, s: Bytes
    ) -> Bytes:
        ensure_budget(UInt64(2_200), OpUpFeeSource.GroupCredit)
        # 2000 units, flat across curves. Returns (x, y), 32 bytes each --
        # an Ethereum address is the last 20 bytes of keccak256(x || y).
        x, y = op.ecdsa_pk_recover(op.ECDSA.Secp256k1, digest, recovery, r, s)
        return op.keccak256(x + y)[12:]
```

Ethereum does not put public keys in messages. It puts a signature and a recovery id, and derives the key, which is why an Ethereum address is a hash of a key nobody transmitted. `ecdsa_pk_recover` does the same derivation on the AVM at 2,000 units, flat across curves, and the last twenty bytes of `keccak256(x || y)` are the Ethereum address that signed. This is the one place `keccak256` is the right call rather than a habit.

## Proving Membership Without Storing the Set
*Predict: an allowlist of ten thousand addresses, and the contract stores 32 bytes. Say what the claimant must supply instead, and roughly how much of it.*

**Example 22-5.** A merkle inclusion proof

<!-- finder: prove an address is on a list you are not storing -->

```python
from algopy import (ARC4Contract, Bytes, Global, GlobalState, OpUpFeeSource,
                    Txn, UInt64, arc4, ensure_budget, op, urange)


class Allowlist(ARC4Contract):
    """Prove membership of a large set while storing one 32-byte root."""

    def __init__(self) -> None:
        self.root = GlobalState(Bytes())

    @arc4.abimethod
    def set_root(self, root: Bytes) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert root.length == 32, "root must be 32 bytes"
        self.root.value = root

    @arc4.abimethod
    def includes(self, leaf: Bytes, path: Bytes, index: UInt64) -> bool:
        # 1,482-1,496 units over 14 levels, depending on the path -- the
        # loop, the slice and the concatenations cost as much as the hashes.
        # The caller pays for the op-ups: three minimum fees, not one.
        ensure_budget(UInt64(2_000), OpUpFeeSource.GroupCredit)
        node = op.sha512_256(Bytes(b"\x00") + leaf)
        cursor = index
        for i in urange(path.length // 32):
            sibling = path[i * 32 : i * 32 + 32]
            # The pair's order is a bit of `index`: hashing it the other way
            # round produces a different root for the same set.
            if cursor % 2 == 0:
                node = op.sha512_256(Bytes(b"\x01") + node + sibling)
            else:
                node = op.sha512_256(Bytes(b"\x01") + sibling + node)
            cursor = cursor // 2
        return node == self.root.value
```

An allowlist of ten thousand addresses is 320,000 bytes, which exceeds a single box's 32,768-byte ceiling and so takes ten of them; by Chapter 11's formula, `10 x 2,500 + 400 x (320,000 + 80)` is **128.06 Algo** of minimum balance. A merkle root is 32 bytes. The claimant supplies the path, the contract recomputes the root, and storage stops scaling with the set.

Three details decide whether that example is sound. The root is a trusted input, and whoever can rotate it can silently invalidate every proof built against the old one. The leaf is hashed with a `\x00` prefix and internal nodes with `\x01`, which stops a claimant passing an internal node as a leaf and proving membership of something that was never in the tree. And the order of each pair is determined by a bit of the index rather than by sorting, because a tree built one way and verified the other produces a different root for the same set.

Verification costs one hash per level plus one for the leaf, fifteen for ten thousand leaves, but the hashes are not the bill. Measured over fourteen levels, the method costs between **1,482 and 1,496** units, because the loop, the slice, the two concatenations and the comparison each cost about as much as the `sha512_256` they surround; the exact figure depends on the path, since the loop's two branches differ by one unit per level. Counting only the hashes gives 675 and the wrong conclusion: this does not *nearly* fit in an application call's 700, it is more than double it, and the method raises its budget before it starts.

Raising it is not free, the caller pays, and the amount is not fixed. `ensure_budget` issues op-up inner calls, `OpUpFeeSource.GroupCredit` says they come out of the group's fee credit rather than the application's balance, and there is no credit unless somebody supplies it. Measured: this method needs a `static_fee` of **3,000**, three minimum fees covering the call and each op-up, and at 1,000 or 2,000 it fails with `group fee 0.0A too small (needs 1mA more)` at the `itxn_submit`. The contract gives no hint of that client-side requirement, and it is the first thing that goes wrong.

The bill also scales. Example 22-8 asks for a budget proportional to its input, so a longer input needs more op-ups and therefore more fee: measured, its minimum workable fee runs 2,000 at 32 bytes, 5,000 at 128 and 9,000 at 256. A fixed request is a ceiling you will meet instead, which is why Example 22-5's flat 2,000 bounds it to about fifteen levels.

## Randomness You Can Check
Chapter 18 derived the three properties a fair draw needs, disqualified the folk sources against them, and shipped its raffle on the ARC-21 beacon --- ending on the one gap a beacon read leaves open: a published value and a chosen one look the same until the operator's proof is checked. This section is that check, priced.

**Example 22-6.** A VRF beacon

<!-- finder: get randomness that nobody chose and everybody can verify -->

```python
from algopy import (ARC4Contract, Bytes, OpUpFeeSource, UInt64, arc4,
                    ensure_budget, op)


class Beacon(ARC4Contract):
    """Randomness nobody chose, proven rather than trusted.

    The output is fixed by the key and the seed, and the proof shows the
    key's holder computed it honestly -- checking it is what separates an
    operator who drew the value from one who chose it.
    """

    @arc4.abimethod(readonly=True)
    def draw(self, seed: Bytes, proof: Bytes, pubkey: Bytes) -> Bytes:
        # 5700 units, the most expensive verification op that is not a
        # pairing check.
        ensure_budget(UInt64(6_000), OpUpFeeSource.GroupCredit)
        output, verified = op.vrf_verify(
            op.VrfVerify.VrfAlgorand, seed, proof, pubkey
        )
        assert verified, "vrf proof did not verify"
        return output
```

`vrf_verify` checks the proof at 5,700 units --- the most expensive verification in this chapter that is not a pairing check, and the reason the method asks for 6,000 before touching the opcode. The contract is not trusting the beacon operator to have drawn fairly; it is checking that they did.

The price a consumer actually feels is the fee, and it depends on something the source does not mention: whether anybody submits the call. One proof, one method, two ways of asking.

```console
>>> # a published proof, checked read-only and then for real
>>> bytes(beacon.draw(seed, proof, key).abi_return) == published_output
True
>>> readonly.inner_txns          # simulate: 320,000 spare units, no fee
0
>>> caller_sees(submit(beacon.draw, static_fee=8_000))
group fee 0.0A too small (needs 1mA more)
>>> submit(beacon.draw, static_fee=9_000).inner_txns
8
```

Read-only, `draw` answers a client that set no fee at all: Chapter 5's simulate runs it with 320,000 spare opcode units, so the request for 6,000 is already met and `ensure_budget` issues nothing --- zero inner transactions, and the answer is the same 64 bytes either way. Submitted, that same request becomes eight op-up inner calls, nine application calls where the client saw one, and nine minimum fees: a `static_fee` of **9,000** against the merkle proof's 3,000. Eight thousand is refused, which is what makes 9,000 a measurement rather than a guess. A method sized by `ensure_budget` runs free right up until something submits it, so submit it once before trusting the numbers a client hands back.

## The Primitives Underneath a Proof
**Example 22-7.** Curve arithmetic

<!-- finder: add and multiply points on BN254 -->

```python
from algopy import (ARC4Contract, Bytes, OpUpFeeSource, UInt64, arc4,
                    ensure_budget, op)


class CurveArithmetic(ARC4Contract):
    """Point addition and scalar multiplication on BN254.

    These are the primitives a verifier is built from. Addition is cheap;
    scalar multiplication is not, and a pairing check is in another bracket
    again -- which is what decides where a verifier can run.
    """

    @arc4.abimethod(readonly=True)
    def add_points(self, a: Bytes, b: Bytes) -> Bytes:
        return op.EllipticCurve.add(op.EC.BN254g1, a, b)

    @arc4.abimethod(readonly=True)
    def scale(self, point: Bytes, scalar: Bytes) -> Bytes:
        # 1810 units on BN254g1, against an application call's 700 -- so the
        # budget has to be raised before the opcode is reached, not after.
        ensure_budget(UInt64(2_000), OpUpFeeSource.GroupCredit)
        return op.EllipticCurve.scalar_mul(op.EC.BN254g1, point, scalar)
```

A zero-knowledge verifier is not one opcode. It is point additions, scalar multiplications and a pairing check, assembled into a circuit-specific routine. Addition is cheap; scalar multiplication on BN254g1 is 1,810 units and on g2 is 3,430; and the pairing check is where the arithmetic stops fitting.

**Example 22-8.** A SNARK-friendly hash

<!-- finder: the hash that is expensive here and cheap inside a proof -->

```python
from algopy import (ARC4Contract, Bytes, OpUpFeeSource, UInt64, arc4,
                    ensure_budget, op)


class SnarkFriendly(ARC4Contract):
    """A hash chosen to be cheap inside a proof, not cheap on chain.

    MiMC costs more per byte on the AVM than sha512_256 does. It is used
    anyway because the expensive side is the circuit: proving knowledge of a
    sha256 preimage takes orders of magnitude more constraints than proving
    a MiMC one, so the cost moves off the prover and onto the verifier.
    """

    @arc4.abimethod
    def digest(self, data: Bytes) -> Bytes:
        # Two constraints the other hashes do not have. The input must be a
        # multiple of 32 bytes, and each 32-byte block must be a valid BN254
        # field element -- 32 bytes of 0xff is not, and fails with
        # `invalid mimc input invalid fr.Element encoding`.
        assert data.length > 0, "mimc input cannot be empty"
        assert data.length % 32 == 0, "mimc input must be a multiple of 32"
        # Base 10 plus 550 per 32-byte chunk, so the request has to scale
        # with the input: a fixed 2,000 covers 96 bytes and fails at 128.
        # Whoever calls this supplies the fee for the op-ups as well.
        ensure_budget(
            UInt64(700) + (data.length // 32) * UInt64(600),
            OpUpFeeSource.GroupCredit,
        )
        return op.mimc(op.MiMCConfigurations.BN254Mp110, data)
```

MiMC costs 10 units plus 550 for each 32 bytes, which for anything but a very short input is worse than `sha512_256`; a 64-byte input is 1,110 against an application call's 700. It also takes an input the other hashes do not: the length must be a multiple of 32, and every 32-byte block must be a valid BN254 field element, so thirty-two bytes of `0xff` fails with `invalid mimc input invalid fr.Element encoding` rather than hashing. It is used anyway, because the AVM is not where the expensive work happens. Proving knowledge of a `sha256` preimage takes an enormous circuit; proving a MiMC one takes a small one. The cost moves off the prover and onto the verifier, and the verifier is the cheap side.

## Where the Budget Comes From
*Predict: a LogicSig has 20,000 opcode units and the cheapest useful pairing check costs more than that. Before reading on, say what could possibly make it runnable, given that the program cannot be made shorter.*

**Example 22-9.** A verifier that needs a group

<!-- finder: see why a pairing check needs companion transactions -->

```python
from algopy import (Account, Global, TemplateVar, TransactionType, Txn, UInt64,
                    logicsig, op)


@logicsig
def verifier() -> bool:
    """A pairing check does not fit in one program's budget.

    `ec_pairing_check` costs 8,000 plus 7,400 per chunk of its SECOND
    operand, where a chunk is the point size of the group you named. Under
    `BN254g1` that is 64 bytes against an operand holding 128-byte G2 points
    -- two chunks a pair, so one pair is 22,800, already over a LogicSig's
    20,000 before any of this program's own logic. Under `BN254g2` the same
    product is 15,400 and fits.

    The budget pools across the group at 20,000 per transaction, so the fix
    is transactions rather than optimisation. That is why a verifier arrives
    with companions that do nothing.
    """
    return (
        # The guards first, and they are not decoration: a program that
        # authorises a payment on the strength of a pairing check over
        # CALLER-SUPPLIED arguments is a blank cheque, because anyone can
        # supply a satisfying pair. The next section is where that is argued.
        Txn.type_enum == TransactionType.Payment
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        and Txn.receiver == TemplateVar[Account]("BENEFICIARY")
        and Txn.amount <= UInt64(100_000)
        and Txn.last_valid <= TemplateVar[UInt64]("EXPIRY")
        # LogicSig arguments are `arg`, not `application_args` -- a payment
        # carries no application arguments at all.
        and op.EllipticCurve.pairing_check(op.EC.BN254g1, op.arg(0), op.arg(1))
    )
```

`ec_pairing_check` costs 8,000 units plus 7,400 per chunk of its **second** operand, and the chunk has two moving parts. The count is measured over that second operand; the size of a chunk is the point size of the group you *name*. Name `BN254g1` and you have named the 64-byte group while the second operand holds the 128-byte G2 points, two chunks per pair. So each pair adds 14,800 to the 8,000 base: one pair is 22,800, and a Groth16 verification's four pairs are 67,200.

A LogicSig has 20,000.

So the smallest pairing check on `BN254g1` overruns a program running on its own, before a single line of the surrounding logic is counted. Under `BN254g2` the same one-pair check is 15,400 and fits, with 4,600 units to spare; the constraint is real but it is about `BN254g1`, not about pairing checks.

Naming the other group is not a workaround so much as a different accounting. `BN254g2` swaps the operands and computes the same product (the opcode exchanges them and calls the same routine), but now you have named the 128-byte group while the second operand holds the 64-byte G1 points, so a single chunk covers *two* pairings. Four pairs become two chunks: 22,800 rather than 67,200, a three-fold saving for naming a different constant. One pair is 15,400 either way you count it, which fits in a LogicSig alone.

Even so, the group is where the headroom comes from once a real verifier is assembled around the check. The LogicSig budget pools across the group at 20,000 per transaction, and *every* transaction contributes whether or not it carries a LogicSig. A verifier that needs 67,200 units needs a group of at least four, and in practice more once the program around the pairing check is counted, which is why a proof transaction arrives with companions that do nothing but exist. The padding is a protocol requirement rather than a trick, and it is why the fee for verifying a proof on chain is quoted in transaction counts.

::: {.gotcha #pairing-check-exceeds-one-program topic="Cryptography" title="A `BN254g1` pairing check does not fit in one program's budget"}
BN254 `ec_pairing_check` is 8,000 plus 7,400 per chunk of its second operand, where a chunk is the point size of the group you named. Under `BN254g1` you named the 64-byte group and the second operand holds 128-byte G2 points, so one pair is two chunks: 22,800, already over a LogicSig's 20,000 and thirty times an application call's 700, before any surrounding code. No rearrangement of that code helps; the opcode alone exceeds the budget.

Two things do. Naming `BN254g2` puts the 64-byte G1 points in the counted operand against a 128-byte chunk, so one chunk covers two pairings --- one pair drops to 15,400 and four pairs to 22,800 against `BN254g1`'s 67,200. And the budget itself comes from the group: `len(group) x 20,000` for LogicSigs, with every transaction contributing.
:::

**Example 22-10.** Post-quantum verification

<!-- finder: verify a signature a quantum computer is not expected to forge -->

```python
from algopy import (ARC4Contract, Box, Bytes, Global, OpUpFeeSource, Txn,
                    UInt64, arc4, ensure_budget, op)


class PostQuantum(ARC4Contract):
    """Falcon verification, with the key in a box because it fits nowhere else:
    1,793 bytes is over the 128-byte ceiling on a global state value, and key
    plus signature is over the 2,048-byte cap on application arguments."""

    def __init__(self) -> None:
        self.pubkey = Box(Bytes, key=b"pk")

    @arc4.abimethod
    def set_pubkey(self, pubkey: Bytes) -> None:
        assert Txn.sender == Global.creator_address, "creator only"
        assert pubkey.length == 1793, "falcon-1024 keys are 1793 bytes"
        self.pubkey.value = pubkey

    @arc4.abimethod
    def verify(self, message: Bytes, sig: Bytes) -> bool:
        ensure_budget(UInt64(1_800), OpUpFeeSource.GroupCredit)
        return op.falcon_verify(message, sig, self.pubkey.value)
```

Ed25519 and ECDSA rest on discrete logarithms, which a large enough quantum computer solves; Falcon rests on lattice problems, which it does not --- What's Next maps where the protocol already runs Falcon and the roadmap past it. At 1,700 units it is *cheaper* to verify than Ed25519's 1,900; the cost is in the key and signature sizes rather than the verification, which is not the trade most people assume.

Those sizes decide the shape of the method. A Falcon-1024 public key is 1,793 bytes and a signature 1,232. Together they are 3,025 against a 2,048-byte cap on *all* of a transaction's application arguments, so a method taking both as arguments cannot be called at all: `tx.ApplicationArgs total length is too long`. The key goes in a **box** (1,793 bytes is also over global state's 128-byte combined key-plus-value ceiling, so state is not an option either), which leaves the signature in the arguments with 808 bytes left for the message. The box is not free: at Chapter 11's rate it raises the application account's minimum balance by 720,500 microAlgo, where the global-state version would have cost nothing extra and not worked. A LogicSig is the other way out, where size pooling gives the group `len(group) x 1,000` bytes to work with.

## The Check That Gates Nothing
Example 22-9 authorises a payment when a pairing check succeeds. The check is real (8,000 units plus 7,400 per 64-byte chunk of its second operand, so no less than 22,800), and the program pins the guards a LogicSig cannot ship without: type, `close_remainder_to`, `rekey_to`, a fee cap, receiver, amount, and expiry.

```python
    return (
        Txn.type_enum == TransactionType.Payment
        and Txn.close_remainder_to == Global.zero_address
        and Txn.rekey_to == Global.zero_address
        and Txn.fee <= Global.min_txn_fee * UInt64(10)
        and Txn.receiver == TemplateVar[Account]("BENEFICIARY")
        and Txn.amount <= UInt64(100_000)
        and Txn.last_valid <= TemplateVar[UInt64]("EXPIRY")
        and op.EllipticCurve.pairing_check(op.EC.BN254g1, op.arg(0), op.arg(1))
    )
```

*Every field is bounded and the receiver cannot be changed. Who can make this pay out?*

Anyone. `op.arg(0)` and `op.arg(1)` are supplied by whoever submits the transaction, and a pairing check is not a proof of anything on its own: it tests whether a product of pairings equals one. Feed it `[G1, -G1]` against `[G2, G2]` and the product is `e(G1,G2) · e(-G1,G2)`, which is exactly one. Both are generator points anybody can write down.

```console
>>> # nothing here is secret: two generators and one negation
>>> args = [G1 + neg(G1), G2 + G2]            # 128 bytes, then 256
>>> caller_sees(submit(payment, args, group_of=1))
rejected by logic err=pc=101 dynamic cost budget exceeded,
executing ec_pairing_check: local program cost was 34
>>> submit(payment, args, group_of=2).lsig_budget_consumed
37637
>>> beneficiary_balance_after - beneficiary_balance_before
100000
```

Two pairs is 8,000 plus four chunks of 7,400, so the check alone is 37,600 and the program around it costs 37. That overruns one program's 20,000, and the overrun is the only obstacle the design presents: it is answered by a single companion transaction, exactly the one an honest caller would have sent. The second attempt confirms an identity, approves the payment, and moves 100,000 microAlgo out of the escrow. The receiver is pinned, so nobody redirects the money --- but the condition this escrow was funded to enforce has turned out not to exist, and the balance now leaves 100,000 at a time on a schedule chosen by whoever is willing to pay the fees.

The check is doing real cryptography and gating nothing. The failure is not in the mathematics. A verifier proves a statement *about a specific instance* --- this proof, over this public input, against this verifying key. Those inputs have to be pinned by something the submitter does not control: a verifying key baked into the program as a template variable, and a public input bound to the transaction rather than passed beside it. A pairing check over two caller-supplied blobs proves that the caller can do arithmetic.

A LogicSig's arguments are chosen by whoever submits the transaction --- they are `arg`, not a field the program author pinned --- and this is that rule in its most expensive form. **The cost of a check is not evidence that it constrains anything.** A 37,600-unit operation over attacker-chosen inputs is an expensive way to return true.

## The Commission, Item by Item
Every requirement the DAO set now has an example and a bill beside it:

1. Bids that bind on landing and stay sealed until the close --- Example 18-2's commitment under this chapter's pricing, one 45-unit hash to make and one to check.
2. The KYC approval --- Example 22-2's off-chain signature, with Example 22-3's prefix keeping an approval for one operation from authorising another.
3. Ten thousand approved addresses held as 32 bytes --- Example 22-5's merkle root, each claimant carrying their own path.
4. A budget the caller can afford, at a fee known before submission --- the arithmetic that ran through every listing: `ensure_budget` buys opcodes with inner calls, the caller funds them, and 3,000 microAlgo for the merkle proof against 9,000 for the VRF check are measurements, not guesses.
5. Never mistaking the cost of a check for what it proves --- the discipline the last section spent 37,637 units demonstrating: a check gates something only when its inputs are pinned by somebody other than the submitter.

What the chapter has not done is assemble those pieces into the auction --- the escrow, the close, the reveal deadline, the settlement. That assembly is the Part VI checkpoint's job, and it is deliberately yours.

## Retrieval
Answer these from memory before moving on. Three of them reach back into earlier chapters on purpose.

1. Which of `sha256`, `sha512_256` and `keccak256` is cheapest, which is Algorand's own, and when is the expensive one the right choice?
2. What does the nonce in a commitment do, and what can an attacker do without it?
3. A signature verifies. What have you learned, and what have you not?
4. Why does an Ethereum address need `ecdsa_pk_recover` rather than a public key in the message?
5. Why are leaves and internal nodes hashed with different prefixes in a merkle tree?
6. Example 22-6's `draw` is readonly and answers a client that set no fee. Say why it can, and what the fee becomes --- and why --- once the same call is submitted.
7. A one-pair pairing check costs 22,800 under `BN254g1` and 15,400 under `BN254g2`, for the same product. Explain the difference, and say where extra budget comes from when you need it.
8. *(From Chapter 11)* An application call has 700 opcode units. Name the two ways a method gets more, and say who pays in each.
9. A group of eight carries one LogicSig. How many units does that program have, and how many of the eight had to carry a signature for that to be true?
10. *(From Chapter 5)* Price ten thousand 32-byte allowlist entries as boxes, then as a merkle root, and say what the root cannot do that the boxes can.

## Exercises
1. **(Trace)** A contract verifies `ed25519verify_bare(amount, sig, oracle_key)` in both `withdraw` and `emergency_withdraw`, where the second skips a time lock. Walk through what an attacker with one legitimately obtained withdraw signature can do. Then say what changes if the signed message includes the application id but not the operation name.

2. **(Parsons)** Below are seven statements. Five form the body of `includes` in Example 22-5, whose signature is `includes(leaf: Bytes, path: Bytes, index: UInt64) -> bool`; two do not belong.

   ```text
   (1) ensure_budget(UInt64(2_000), OpUpFeeSource.GroupCredit)

   (2) node = op.sha512_256(Bytes(b"\x00") + leaf)

   (3) node = op.sha512_256(leaf)

   (4) cursor = index

   (5) for i in urange(path.length // 32):
           sibling = path[i * 32 : i * 32 + 32]
           if cursor % 2 == 0:
               node = op.sha512_256(Bytes(b"\x01") + node + sibling)
           else:
               node = op.sha512_256(Bytes(b"\x01") + sibling + node)
           cursor = cursor // 2

   (6) for i in urange(path.length // 32):
           sibling = path[i * 32 : i * 32 + 32]
           node = op.sha512_256(Bytes(b"\x01") + node + sibling)

   (7) return node == self.root.value
   ```

   (a) Select the five and order them. Three of the five may be written in any order among themselves and all three are still pinned ahead of the loop: name them, and say what pins each one, given that only two of the three are pinned by a name the loop reads.

   (b) The two rejects are wrong in different ways and are found at different times. One of them fails against almost every honest proof, so the first test written turns it up. The other verifies every honest proof, as long as the tree off chain is built to match it, and additionally accepts a claimant who was never in the tree. Say which is which, describe the bytes that claimant hands over as a leaf, and say what the two prefixes in Example 22-5 do to those bytes.

   (c) A caller who sends this method a minimum fee gets an error rather than an answer. Say what the fee has to be instead, which of the five lines is spending it, and what would have to change for that number to move.

3. **(Debug)** A team ships a commit-reveal auction. Commitments are `sha512_256(amount)`. The auction works, and then one bidder starts winning by exactly one microAlgo every time. Explain the mechanism precisely, and say why adding a nonce to the *reveal* rather than the *commitment* would not fix it.

4. **(Compare)** In both of these the cost is not where you would look for it.

   **A lottery's source of randomness.** Compare the hash of a future block seed, a commit-reveal among the participants, and a VRF beacon, on who can manipulate the result, what it costs, what happens if a participant goes offline, and what a verifier has to trust. Name a case that forces each.

   **A verifier's pairing immediate.** A Groth16 verifier needs one four-pair pairing check, six scalar multiplications on g1, and eight point additions. Work out the total opcode cost twice, once naming `BN254g1` for the pairing check and once naming `BN254g2`, then the minimum group size each needs, and say what that implies for the fee a user pays to submit one proof. Then say why the choice of immediate changes the price at all, given that both compute the same product.

   Then both together: say where somebody reading the deployed program would find each price, and which of the two is not written there at all.

5. **(Extend)** Example 22-5 proves membership. Extend it to prove membership *and* that the claimant has not claimed before, without storing one box per claimant. Say where the state lives, what it costs, and what the merkle tree can and cannot do for the second half.

## Before You Continue
- [ ] I can choose a hash by cost and say why `keccak256` is not the default
- [ ] I can say what a commitment costs to make and to check, and why proving one changes which hash I reach for
- [ ] I can verify an off-chain signature, say exactly what it proves, and recover a signer's key from an ECDSA one
- [ ] I can prove set membership without storing the set, and say what checking a VRF proof costs and who pays it
- [ ] I can say why a pairing check needs a group, and why naming the other curve group changes its price

## Further Reading: Private Governance Voting

The project that used to follow this chapter assembled every primitive above into a private governance vote: voters proved they were eligible and that their ballot was well-formed, without revealing who they were or how they voted. It pulled in AlgoPlonk, a Go/gnark proving path, and a LogicSig verifier whose group exists mostly to buy opcode budget --- the same trade `ensure_budget` makes here, priced at group scale.

That project is out of place on this book's arc (foundations → custody → DEX → randomness → shipping). The manuscript and the runnable AlgoKit project are companion material:

- `advanced/private-governance/23-private-governance-voting.md`
- `advanced/governance-voting/`

They keep the old Chapter 23 numbering so internal references still resolve. This chapter does not assume you have built them. The assembly this chapter *does* ask of you is the Part VI checkpoint: a sealed-bid auction you can afford to run, priced from the tables you just used.

Part VII is next, and it does not need a verifier. Chapter 24 is what an operator needs from a contract that already works: a log, an error code, a pause, and a lifecycle stance chosen before you freeze it.

## Mastery Checkpoint
That is the end of Part VI. The checklist above asks whether you followed the chapter. The Mastery Checkpoint printed on the next page asks something harder: whether you can build a thing this part did not show you. It is a small program with a stated acceptance test, and a fallback if you stall.
