\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{\BOAkind{Concept}}
```
# Contracts That Exist and Respond

Chapter 2 got a contract onto a network and got a value back out of it. Every application call after that is a handful of bytes arriving at a program that has never met the caller, and everything your contract knows about the call it learns by decoding those bytes. Get that wrong and the compiler will not tell you, the client will not tell you, and the chain will do exactly what you asked.

## Making a Contract a Stranger Can Call
A contract earns its keep when somebody who has never seen your source can call it. Three things have to be true for that, and not one of them is decided inside a method body. The application has to exist, so there is an ID to aim at. The call has to reach the method the caller meant, out of however many you wrote. And the bytes have to decode at both ends: arguments into values your body can use, the return value into something the caller's client can name.

The toolchain hands you all three. ARC-4 fixes the encoding, so your contract and a caller's client agree on what a `uint64` looks like on the wire with nothing negotiated between them. Subclassing `ARC4Contract` generates a router that reads the first application argument and dispatches on it. And the compiler writes an ARC-56 app spec beside the compiled program, out of which `algokit generate client` builds a typed class carrying your methods.

All three are settled *above* the method body, in decorator arguments and in a JSON file, and nothing checks that what you declared there is what the body does. That gap --- between what a method declares and what its body does --- is where every failure in this chapter lives.

::: {.spec title="Your commission: a public counter with an API"}
The contract you build this chapter is a visit counter for a dashboard --- the first contract you write whose callers are other people's programs. It must:

1. Be created with a label its creator chooses: non-empty, at most 32 bytes
2. Let anyone bump the count and get the new value back
3. Let anyone read the current count without paying a fee
4. Describe itself --- label and count together --- in a form a generated client can decode
5. Let the creator, and only the creator, reset the count to zero

Five requirements, five methods. At the end of the chapter you will re-run the finished counter against this list.
:::

By the end of this chapter you will be able to:

- Predict the exact bytes that cross the wire for any ABI argument or return value, and read a client's decoded result back to the type that produced it
- Convert between native AVM values and their ARC-4 encodings at the one place conversion belongs --- the method boundary --- and explain why arithmetic on an ARC-4 integer does not compile
- Decide, for each method you write, which on-completion actions it answers to, whether it may run at application ID zero, and whether a client may simulate it instead of submitting it
- Say what a method selector is derived from, and predict which edits to a Python method break every existing caller and which change nothing
- Validate an ARC-4 argument that arrived from someone you do not trust, and name what PuyaPy checks on your behalf by default
- Read an ARC-56 app spec and answer, without opening a line of generated TEAL, which of a contract's methods a stranger can reach and when

## Building the Counter
Here is that commission, as anyone coming from Python would first write it --- complete, and in full.

**Example 3-1.** A counter with an API, as first written

<!-- finder: see a contract with a few methods a generated client can call -->

```python
from algopy import ARC4Contract, Bytes, Global, String, Txn, UInt64, arc4, op

# A label longer than this makes `describe` awkward to read and costs the
# creator global-state bytes for nothing.
MAX_LABEL_BYTES = 32


class Counter(ARC4Contract):
    """A public counter with a label the creator chooses at creation."""

    def __init__(self) -> None:
        self.count = UInt64(0)
        self.label = String("visits")

    @arc4.abimethod(create="require")
    def create(self, label: arc4.String) -> None:
        text = label.native
        assert text.bytes.length > UInt64(0), "create: label must not be empty"
        assert text.bytes.length <= UInt64(MAX_LABEL_BYTES), "create: label too long"
        self.label = text

    @arc4.abimethod(readonly=True)
    def bump(self) -> arc4.UInt64:
        self.count += UInt64(1)
        return arc4.UInt64(self.count)

    @arc4.abimethod(readonly=True)
    def current(self) -> arc4.UInt64:
        return arc4.UInt64(self.count)

    @arc4.abimethod(readonly=True)
    def describe(self) -> Bytes:
        return self.label.bytes + op.itob(self.count)

    @arc4.abimethod(create="allow")
    def reset(self) -> None:
        assert Txn.sender == Global.creator_address, "reset: creator only"
        self.count = UInt64(0)
```

Example 3-1 is complete and deployable: it compiles, it runs on LocalNet, every method does something defensible, and three of its decisions are wrong. None of the three will error. Two answer wrongly in ways you can watch, and the third waits for a stranger.

*Predict: three decisions in that contract are wrong. Write your three down now, in whatever words you have; you are not expected to be right yet. Check them against the diff at the end of the chapter.*

The two assignments in `__init__` are *global state*: where those values live, what they cost, and who can delete them is Chapter 4's subject --- for now it is enough that they survive between calls.

Deploy it and drive it through the generated client. The counter has just been created, so the ledger has it at zero.

```python
>>> counter.send.describe().abi_return
[118, 105, 115, 105, 116, 115, 0, 0, 0, 0, 0, 0, 0, 0]
```

That is the first failure. Nothing errored. The method returned, the client decoded the return value, and what came back was fourteen integers. They are not wrong: `118, 105, 115, 105, 116, 115` is `visits` in UTF-8 and the eight zeros after it are the number zero, big-endian. The bytes are perfect. The *type* is `byte[]`, and a `byte[]` is a list of bytes, so a list of bytes is what any conforming decoder must produce. There is no smarter client that would have guessed.

Now the second failure.

```python
>>> counter.send.bump().abi_return
1
>>> counter.send.bump().abi_return
1
>>> counter.send.current().abi_return
0
```

Nothing was written. `bump` is marked `readonly=True` --- requirement 3 said reading must cost nothing, and `readonly` reads like the flag for that, applied one method too far. What the flag actually tells clients is that they may answer the call with a simulation instead of a transaction, and every conforming client does: it ran the real program against a ledger where the count is zero, computed one, threw the write away, and reported one. The second call started from zero again. `current()` is also readonly and also simulated, but honest, because it writes nothing: it reports the ledger's actual zero. Two methods, the same mechanism, and only one of them is lying.

The third failure produces no transcript at all. `reset` declares `create="allow"` --- chosen because allowing sounds like the setting that cannot get in anyone's way --- and `"allow"` is not a permission added; it is a check removed. Every ordinary method is fronted by a router assertion that the call's application ID is not zero: that the call is aimed at an application that exists. `reset` opted out. So a stranger can send `reset` with the application ID field set to zero, and at ID zero an application call means *create one*: the AVM instantiates a brand-new counter from your program, runs `__init__`, and then runs the method. The guard inside it, `Txn.sender == Global.creator_address`, passes, because the sender is the one doing the creating. The stranger has not touched your counter. They have minted one of their own, reset it, and been told it worked --- and every line of your code behaved exactly as written. "What Makes a Method Reachable" shows the router making this decision, and "The File a Client Reads Before It Calls" shows the one line of JSON that advertises it.

Now ship Example 3-1 anyway, and watch what the three failures cost once other people depend on the contract. The dashboard wires up in an afternoon, and every visitor who clicks the button is told they are visitor number one. Somebody files a ticket about it; somebody else closes it as a caching problem, because the number comes straight off the chain and the chain cannot be wrong. Three weeks later somebody asks the network directly --- not through the dashboard but with a plain read of the application's global state --- and the counter says zero. It has said zero since the day it was deployed, and every one of those visitors was told the exact truth about a count that was never written.

The other two failures bill differently. Fourteen integers are at least *visibly* wrong, so the integrator on the far side stops trusting your types and ships a shim that slices the last eight bytes off by hand --- a second copy of your encoding, in a codebase you cannot see, that will break silently the day the layout changes. And the `reset` hole costs nothing until it costs trust: nobody experiences it as a bug, because for the stranger who uses it, it works. It sits advertised in a client-facing JSON file for anyone who reads app specs.

Nothing in Example 3-1 is a typo. Each failure is a declaration behaving exactly as documented, and not one of them is visible from inside the method body it governs. The rest of this chapter walks that boundary from the bottom up: the two value types everything rests on, the ARC-4 layer that gives bytes a shape, the router that decides what a call can reach, and the app spec that writes those decisions down where a client --- or a stranger --- can read them.

## Two Types, and Nothing Else
The broken counter's `describe` is one expression long: `self.label.bytes + op.itob(self.count)`. Two conversions and a concatenation, and the seed of the first failure. Chapter 2 stated the surface of the rule underneath it: there is no floating point, and there are two types, `uint64` and `bytes`. The consequence: the AVM has *one* stack with *two value types* on it, a value never implicitly converts from one to the other, and every conversion you will ever write moves a value across that line by hand.

**Example 3-2.** The two value types, and moving between them

<!-- finder: know what the AVM will and will not let me do to a value -->

```python
from algopy import ARC4Contract, Bytes, UInt64, arc4, op


class StackTypes(ARC4Contract):
    """Every value the AVM holds is a uint64 or a byte string. That is all."""

    @arc4.abimethod
    def numeric(self, a: UInt64, b: UInt64) -> UInt64:
        # Both operands are uint64 values. A product that does not fit in
        # 64 bits is a runtime failure, not a wraparound.
        return a * b

    @arc4.abimethod
    def bytewise(self, a: Bytes, b: Bytes) -> UInt64:
        # Byte strings concatenate and report a length. They do not add.
        return (a + b).length

    @arc4.abimethod
    def wide(self, a: UInt64, b: UInt64) -> Bytes:
        # When a product will not fit in a uint64 it has to become bytes.
        # `mulw` returns the high and low 64-bit words.
        high, low = op.mulw(a, b)
        return op.itob(high) + op.itob(low)
```

The key line is `high, low = op.mulw(a, b)`. Ordinary `*` fails the transaction when the product exceeds 64 bits; it does not wrap. `mulw` is the escape hatch that returns the 128-bit result as two 64-bit words, and you will meet it again the first time you price anything. The no-wraparound rule is not special to multiplication: `+` and `-` abort the same way when the result leaves the range, and there is no `mulw` equivalent standing by to catch them.

Text is where the two value types get confusing, because Python offers three types that all look like strings.

**Example 3-3.** String, arc4.String, and Bytes

<!-- finder: choose between the three text types -->

```python
from algopy import ARC4Contract, Bytes, String, UInt64, arc4


class Text(ARC4Contract):
    """Three ways to hold text, and the one difference that separates them."""

    @arc4.abimethod
    def length(self, s: String) -> UInt64:
        # `String` supports neither `len()` nor indexing: the AVM has no UTF-8
        # support, so the only honest answer is a count of bytes.
        return s.bytes.length

    @arc4.abimethod
    def join(self, a: String, b: String) -> String:
        # Concatenation is cheap precisely because a `String` carries no
        # length prefix that would have to be rewritten.
        return a + " " + b

    @arc4.abimethod
    def to_arc4(self, s: String) -> arc4.String:
        # `arc4.String` is the same UTF-8 text with a two-byte big-endian
        # length prefix in front of it. That prefix is the whole difference.
        return arc4.String(s)

    @arc4.abimethod
    def raw(self, s: String) -> Bytes:
        # `Bytes` is the untyped form underneath both: no prefix, no promise
        # that the contents are text at all.
        return s.bytes
```

The line that matters is `return s.bytes.length`. `algopy.String` supports neither `len()` nor indexing, and the docstring says why: *"due to the lack of UTF-8 support in the AVM, indexing and length operations are not currently supported."* The AVM counts bytes. A character is a concept it has never heard of. One thing separates each of the three types: `String` is UTF-8 text with no length prefix, `arc4.String` is the same text behind a two-byte big-endian length prefix, and `Bytes` is the raw form underneath both, with no prefix and no promise that the contents are text at all.

*Predict: `join("héllo", "wörld")` returns a `String`. What does `length` report for it, and is that the answer a user would expect?*

Raw bytes slice, and the result of indexing one is not a number. This is the machinery a caller would need if they wanted to make sense of the broken counter's fourteen integers on their own: take the last eight bytes, turn them into a number, and read what is left as text.

**Example 3-4.** Slicing and indexing raw bytes

<!-- finder: pull one field out of the middle of a byte string -->

```python
from algopy import ARC4Contract, Bytes, UInt64, arc4, op


class Slices(ARC4Contract):
    """Raw bytes slice the way Python slices, and index to a one-byte Bytes."""

    @arc4.abimethod
    def head(self, b: Bytes) -> Bytes:
        return b[:4]

    @arc4.abimethod
    def tail(self, b: Bytes) -> Bytes:
        return b[-4:]

    @arc4.abimethod
    def byte_at(self, b: Bytes, i: UInt64) -> UInt64:
        # `b[i]` is a Bytes of length one, not a number. `btoi` reads it as one.
        return op.btoi(b[i])
```

`return op.btoi(b[i])` is where it goes wrong. `b[i]` is a `Bytes` of length one, not a `UInt64`. Indexing a byte string gives you a shorter byte string, because a byte string is the only thing a byte string contains. `btoi` is what moves it across to the other type.

That leaves the conversion you will write most often.

**Example 3-5.** itob and btoi, the exact round trip

<!-- finder: turn a number into exactly eight bytes and read it back -->

```python
from algopy import ARC4Contract, Bytes, UInt64, arc4, op


class RoundTrip(ARC4Contract):
    """Turn a number into a byte string and back without losing it."""

    @arc4.abimethod
    def encode(self, n: UInt64) -> Bytes:
        # `itob` always produces exactly eight bytes, big-endian, zero-padded.
        # The number 7 becomes 00 00 00 00 00 00 00 07, not the byte 07.
        return op.itob(n)

    @arc4.abimethod
    def decode(self, raw: Bytes) -> UInt64:
        # `btoi` reads at most eight bytes and rejects anything longer.
        assert raw.length <= UInt64(8), "decode: at most eight bytes"
        return op.btoi(raw)

    @arc4.abimethod
    def round_trips(self, n: UInt64) -> bool:
        # The round trip is exact for every value a uint64 can hold: nothing
        # is lost in either direction.
        return op.btoi(op.itob(n)) == n
```

The line to watch is `return op.itob(n)`. `itob` always produces exactly eight bytes: the number seven becomes `00 00 00 00 00 00 00 07`, never the single byte `07`. That fixed width is why the round trip through `btoi` is exact for every value a `uint64` can hold, and it is why the transcript's number field was eight zeros rather than none.

For the counter, this clears the expression rather than the method. `self.label.bytes + op.itob(self.count)` is two byte strings concatenated, one of them produced by the fixed-width conversion you just met, and it is perfectly legal. The compiler had no objection to raise and it was right not to. The mistake is one level up, at the boundary.

## Crossing the ARC-4 Boundary
An `arc4.UInt64` is not a number. It is an eight-byte encoding of a number, living on the byte stack, and the single most common early error is forgetting that.

**Example 3-6.** Converting at the edge, and only at the edge

<!-- finder: do arithmetic with an ARC-4 argument -->

```python
from algopy import ARC4Contract, UInt64, arc4


class Boundary(ARC4Contract):
    """`arc4.UInt64` is wire format. `UInt64` is a number. Convert at the edge."""

    @arc4.abimethod
    def add(self, a: arc4.UInt64, b: arc4.UInt64) -> arc4.UInt64:
        # Cross the boundary once on the way in...
        total: UInt64 = a.as_uint64() + b.as_uint64()
        # ...do the arithmetic in native types, and cross back once on the
        # way out. Nothing in between needs to know about ARC-4 at all.
        return arc4.UInt64(total)

    @arc4.abimethod
    def add_native(self, a: UInt64, b: UInt64) -> UInt64:
        # Or skip the boundary: PuyaPy encodes native `UInt64` as `uint64` in
        # the ABI too, so this method's argument and return types on the wire
        # are identical to `add`, with no conversions in the body. The ABI
        # name is part of the signature, so the selectors still differ:
        # fe6bdf69 for `add`, 5d767951 for this one.
        return a + b
```

The key line is `total: UInt64 = a.as_uint64() + b.as_uint64()`. Convert once on the way in, do the work in native types, convert once on the way out. Nothing between those two lines needs to know that ARC-4 exists. The alternative is to skip the boundary entirely: PuyaPy accepts native `UInt64`, `String` and `Bytes` directly as ABI argument and return types, encoding them as `uint64`, `string` and `byte[]`. So `add` and `add_native` above put *identical* argument and return types on the wire, and neither body is any harder to read than the other. Only the ABI name differs. That is enough to make them two distinct selectors, `fe6bdf69` and `5d767951`, for a reason "The File a Client Reads Before It Calls" takes up; give the second one `name="add"` and a caller cannot tell them apart.

Try it without the conversion --- a variation of Example 3-6's `add`, with the unwrapping deleted --- and the compiler stops you:

```python
from algopy import ARC4Contract, arc4


class Boundary(ARC4Contract):
    @arc4.abimethod
    def add(self, a: arc4.UInt64, b: arc4.UInt64) -> arc4.UInt64:
        # An ARC-4 value is an encoding, not a number. It has no `+`.
        return a + b
```

```text
error: Unsupported left operand type for + ("UIntN[Literal[64]]")
error: Returning Any from function declared to return "UIntN[Literal[64]]"
```

Every ARC-4 type unwraps, and the method you call depends on which type it is.

**Example 3-7.** Unwrapping every ARC-4 type

<!-- finder: get the native value out of an ARC-4 one -->

```python
from algopy import Account, ARC4Contract, BigUInt, String, UInt64, arc4


class Unwrap(ARC4Contract):
    """Every ARC-4 type unwraps. The method you call depends on the type."""

    @arc4.abimethod
    def small(self, n: arc4.UInt64) -> UInt64:
        # Integers up to 64 bits: `as_uint64()`. The `.native` property still
        # exists and still works, but it is deprecated in favour of this.
        return n.as_uint64()

    @arc4.abimethod
    def large(self, n: arc4.UInt512) -> BigUInt:
        # Wider integers do not fit in a uint64, so they unwrap to
        # `BigUInt`, which is carried as a byte string.
        return n.as_biguint()

    @arc4.abimethod
    def text(self, s: arc4.String) -> String:
        # Everything that is not an integer keeps `.native`, undeprecated.
        return s.native

    @arc4.abimethod
    def who(self, a: arc4.Address) -> Account:
        return a.native

    @arc4.abimethod
    def flag(self, b: arc4.Bool) -> bool:
        return b.native
```

The line that matters is `return n.as_uint64()`. Integer types (`arc4.UInt64`, `arc4.UInt8`, `arc4.UInt512` and the rest) moved from `.native` to `as_uint64()` and `as_biguint()`. `.native` still exists and still works, but it is marked deprecated, and **PuyaPy does not warn you.** The compiler is silent. The only tool that will tell you is mypy with the deprecation error code switched on:

```console
$ python3 -m mypy --enable-error-code deprecated as_uint64.py
```

Everything that is not an integer kept `.native` and kept it undeprecated: `arc4.String.native` gives an `algopy.String`, `arc4.Address.native` an `Account`, `arc4.Bool.native` a plain `bool`, `arc4.DynamicBytes.native` a `Bytes`. Arrays are the exception in the other direction: `StaticArray` and `DynamicArray` have `to_native`, not `native`.

Going the other way, from loose bytes into an ARC-4 value, is where trust starts to matter.

**Example 3-8.** from_bytes reinterprets; validate checks

<!-- finder: treat raw bytes as an ARC-4 value safely -->

```python
from algopy import ARC4Contract, Bytes, UInt64, arc4


class Decoding(ARC4Contract):
    """`from_bytes` reinterprets. It does not check. `validate` checks."""

    @arc4.abimethod
    def size(self, raw: Bytes) -> UInt64:
        # `from_bytes` is free: it relabels the bytes as an ARC-4 value and
        # performs no checking whatsoever. If `raw` is b"\x00\x05" with no
        # payload behind it, this call still succeeds...
        text = arc4.String.from_bytes(raw)
        # ...and the failure surfaces here, or later, or not at all.
        return text.bytes.length

    @arc4.abimethod
    def checked_size(self, raw: Bytes) -> UInt64:
        text = arc4.String.from_bytes(raw)
        # `validate` is the check `from_bytes` skipped: it rejects a length
        # prefix that disagrees with the bytes that follow it.
        text.validate()
        return text.native.bytes.length

    @arc4.abimethod
    def encode(self, n: arc4.UInt64) -> Bytes:
        # The other direction is always safe, because the value was already
        # a well-formed ARC-4 encoding.
        return n.bytes
```

`text.validate()` is the one that matters. `from_bytes` is documented as performing no validation: it relabels a byte string as an ARC-4 value and emits no opcodes at all. Hand it `b"\x00\x05"`, a length prefix claiming five bytes follow with nothing behind it, and the call succeeds. The lie surfaces later, somewhere else, in a method that had nothing to do with the decision.

For arguments that arrive through the ABI rather than as loose bytes, PuyaPy inserts that validation for you on every method, by default. You can turn it off, and there is a real reason to: validation costs opcode budget, and on a hot method with a large struct argument it can cost more than the method body.

**Example 3-9.** Turning off argument validation, and paying for it yourself

<!-- finder: cut the cost of argument validation on a method that is over budget -->

```python
from algopy import ARC4Contract, GlobalState, arc4


class Bid(arc4.Struct):
    amount: arc4.UInt64
    rounds: arc4.DynamicArray[arc4.UInt64]


class Auction(ARC4Contract):
    def __init__(self) -> None:
        self.best = GlobalState(arc4.UInt64(0))

    @arc4.abimethod(validate_encoding="unsafe_disabled")
    def submit(self, bid: Bid) -> None:
        bid.validate()
        assert bid.amount > self.best.value, "bid too low"
        self.best.value = bid.amount
```

The line to watch is `@arc4.abimethod(validate_encoding="unsafe_disabled")` immediately above `bid.validate()`. The decorator argument does not make the check unnecessary; it makes the check *yours*, and moves it to a line you choose. Delete that one line and nothing objects: the contract still compiles, still deploys, and still passes every test written with well-formed inputs, because well-formed inputs are the one thing that cannot expose a missing validation.

::: {.gotcha #from-bytes-reinterprets-without-checking topic="Compilation, tooling, and shipping" title="from_bytes relabels bytes as an ARC-4 value and verifies nothing; validate is the check it skipped"}
`arc4.String.from_bytes(raw)` emits no opcodes and performs no validation, as the stub documentation says, so a length prefix that disagrees with the payload behind it sails through and fails somewhere else, later, in code that had nothing to do with the decision. PuyaPy does insert argument validation on ABI methods by default, which is why this mostly bites on values you assembled yourself from boxes, logs, or arguments to a method carrying `validate_encoding="unsafe_disabled"`. Where you have disabled it for opcode budget, `.validate()` is not optional; it is the same check, moved to a line you chose.
:::

In the counter, `describe` returns `Bytes`, the untyped floor of the whole type system: a value with no shape and no promises. The distinction between bytes that *are* something and bytes that merely *encode* something is the counter's mistake in general form.

## Values with Shape
ARC-4 gives the wire a type system. Two of its layout rules are counter-intuitive enough to cost real money in storage.

**Example 3-10.** Bools pack, but only next to each other

<!-- finder: find out what several flags cost me -->

```python
import typing

from algopy import ARC4Contract, arc4

Flags: typing.TypeAlias = arc4.StaticArray[arc4.Bool, typing.Literal[8]]


class Packed(ARC4Contract):
    """Adjacent ARC-4 bools share a byte. Bools with a gap between them cannot."""

    @arc4.abimethod
    def flags(self) -> Flags:
        # Eight bools in one byte: on, off, on, off... encodes as 0xaa.
        on, off = arc4.Bool(True), arc4.Bool(False)
        return Flags(on, off, on, off, on, off, on, off)

    @arc4.abimethod
    def paired(self) -> arc4.Tuple[arc4.Bool, arc4.Bool, arc4.UInt64]:
        # Nine bytes: the two bools pack into one, then the uint64 follows.
        return arc4.Tuple((arc4.Bool(True), arc4.Bool(True), arc4.UInt64(7)))
```

The key line is `return Flags(on, off, on, off, on, off, on, off)`. Eight `arc4.Bool` values in a row occupy one byte: alternating true and false is literally `0xaa`. But the packing only applies while they are adjacent. Put anything between two bools and each one is rounded up to its own byte.

: Table 3-1. What ARC-4 actually puts on the wire

| Value | Type | Encoded bytes | Size |
|---------------------|-----------------------------|-------------------------------------------|-------|
| alternating true/false | `bool[8]` | `aa` | 1 |
| all true | `bool[9]` | `ff80` | 2 |
| true, true, false | `(bool,bool,bool)` | `c0` | 1 |
| true, true, 7 | `(bool,bool,uint64)` | `c0 0000000000000007` | 9 |
| true, 7, true | `(bool,uint64,bool)` | `80 0000000000000007 80` | *10* |
| `"hello"` | `string` | `0005 68656c6c6f` | 7 |
| `['a', 'bb']` | `string[]` | `0002 0004 0007 0001 61 0002 6262` | 13 |
| `['visits', 7]` | `(string,uint64)` | `000a 0000000000000007 0006 766973697473` | 18 |

Rows four and five of Table 3-1 carry the same three values, reordered: nine bytes or ten, depending on whether the two bools touch. That is a one-byte difference in a tuple and a factor-of-eight difference in a struct with sixteen flags in it.

::: {.gotcha #arc4-bools-only-pack-when-adjacent topic="Resource references, MBR, and budget" title="ARC-4 bools share a byte only while they are adjacent, so field order changes the size"}
Eight `arc4.Bool` values in a row occupy one byte. Put any non-bool field between two of them and each is rounded up to a byte of its own: `(bool,bool,uint64)` encodes in nine bytes and `(bool,uint64,bool)` in ten, for the same three values. In a tuple that is one byte. In a struct with sixteen flags interleaved with other fields it is fourteen wasted bytes on every read and every write, and in box storage those bytes are priced at 400 microAlgos each, forever. Group your bools.
:::

The last three rows share one rule. Anything whose size the type does not fix --- a string, a growable array --- cannot sit inline, because the field after it would have no fixed address. So the encoding splits it: a fixed-width *offset* stands in the head, where the field would have been, and the bytes themselves go to the tail, which is how `['a', 'bb']`, three bytes of text, comes to cost thirteen on the wire. The byte-level anatomy of that layout --- what the offsets look like, and what a caller who writes them by hand can aim at a reader who trusts them --- becomes load-bearing when box keys arrive; Chapter 9's data model prints it in full.

Returning several values at once needs no wrapper type and no encoding of your own.

**Example 3-11.** Returning several typed values at once

<!-- finder: give the client more than one thing back from a single call -->

```python
from algopy import ARC4Contract, Global, UInt64, arc4


class Status(ARC4Contract):
    """One call, several values, each one still typed on the far side."""

    def __init__(self) -> None:
        self.count = UInt64(0)

    @arc4.abimethod(readonly=True)
    def snapshot(self) -> arc4.Tuple[arc4.String, arc4.UInt64, arc4.Bool]:
        return arc4.Tuple(
            (
                arc4.String("visits"),
                arc4.UInt64(self.count),
                arc4.Bool(self.count > UInt64(0)),
            )
        )
```

The line that matters is the return type, `arc4.Tuple[arc4.String, arc4.UInt64, arc4.Bool]`. That type is the whole contract with the caller: the generated client decodes it into three values of three types, without being told anything else. This is the shape the broken counter's `describe` should have had from the start.

And that is the fix for the counter's first failure. `describe` becomes `arc4.Tuple[arc4.String, arc4.UInt64]`. Eighteen bytes on the wire instead of sixteen, and on the far side of the wire, `['visits', 1]` instead of a list of integers. The `byte[]` was already spending two bytes of overhead, a length prefix of its own; the tuple spends four: a head offset saying where the string starts, and the string's own length prefix. Both carry the same fourteen bytes of payload, so the tuple costs two bytes more, and those two bytes are the entire difference between a value a client can decode and one it cannot.

::: {.gotcha #byte-array-return-is-not-text topic="Compilation, tooling, and shipping" title="A byte[] return arrives at the client as a list of integers, and no decoder will guess otherwise"}
Returning `Bytes` from an ABI method gives the method a `byte[]` return type, and a conforming client decodes `byte[]` into a list of integers, because that is what the type means. Text that you concatenated by hand comes back as `[118, 105, 115, ...]`, and the caller has no way to know it was ever meant to be read. This never raises: it is a wrong answer that succeeds. If the value has structure, say so in the return type (`arc4.String`, a tuple, a struct) and let the encoding carry the meaning instead of a comment in your codebase.
:::

Arrays come in two kinds and the difference is one field. Nothing in the counter returns one; the first contract in this book that does is Chapter 5's guestbook, which hands back a page of signers as an array that grows.

**Example 3-12.** A fixed-length array

<!-- finder: hold exactly N of something where N never changes -->

```python
import typing

from algopy import ARC4Contract, UInt64, arc4

Scores: typing.TypeAlias = arc4.StaticArray[arc4.UInt64, typing.Literal[3]]


class Fixed(ARC4Contract):
    """A fixed-length array has no length prefix, so its size is known."""

    @arc4.abimethod
    def make(self) -> Scores:
        return Scores(arc4.UInt64(10), arc4.UInt64(20), arc4.UInt64(30))

    @arc4.abimethod
    def total(self, s: Scores) -> UInt64:
        # Twenty-four bytes on the wire: three uint64s and nothing else.
        return s[0].as_uint64() + s[1].as_uint64() + s[2].as_uint64()
```

**Example 3-13.** An array that grows

<!-- finder: hold a list when the length is not known in advance -->

```python
import typing

from algopy import ARC4Contract, UInt64, arc4

Names: typing.TypeAlias = arc4.DynamicArray[arc4.String]


class Growable(ARC4Contract):
    """A dynamic array carries its own length, so it can be appended to."""

    @arc4.abimethod
    def make(self, first: arc4.String) -> Names:
        names = Names()
        names.append(first)
        names.append(arc4.String("anon"))
        return names

    @arc4.abimethod
    def count(self, names: Names) -> UInt64:
        return names.length
```

The difference that matters is the length prefix. A `StaticArray` has none: its length is in its type, so three `uint64`s are twenty-four bytes and nothing else, and the AVM can compute the offset of element *i* without reading anything. A `DynamicArray` carries a two-byte count in front, which is what lets you `append` to it and what forces every reader to consult that count first. Fixed is cheaper; growable is possible; there is no third option and no way to have both.

## What Makes a Method Reachable
Everything so far has been about the *contents* of a call. Whether the call reaches your method at all is decided before your method body runs, by things you write above it.

Chapter 2 introduced the six on-completion actions and showed them as a lifecycle in Figure 2-2. Here they are as a routing decision. PuyaPy generates the router from the decorators you write, and Figure 3-1 is that machine, asking its questions in a fixed order. Before reading it, write down where you would put the check that decides whether the application already exists: first, last, or somewhere in between. The router asks it *after* filtering on the on-completion action --- and after it has already matched any method that opted out of the check altogether, which is the gap the counter's `reset` lives in.

![Figure 3-1. How the generated router chooses, in the order it asks. A method that declares `create=allow` is matched before the application-ID question is ever asked, which puts it on both sides of that question at once.](figures/router-decision.svg)

**Example 3-14.** The five actions a method can answer to

<!-- finder: run a method on opt-in or delete rather than on an ordinary call -->

```python
from algopy import ARC4Contract, Global, Txn, UInt64, arc4

# ClearState is the sixth on-completion action and it is deliberately absent
# below: it runs the clear-state program, not this one, so no decorator here
# can route it, refuse it, or even see it.


class Lifecycle(ARC4Contract):
    """The five on-completion actions a method can be routed to."""

    def __init__(self) -> None:
        self.members = UInt64(0)

    @arc4.abimethod
    def touch(self) -> UInt64:
        return self.members  # NoOp: the default, and every ordinary call

    @arc4.abimethod(allow_actions=["OptIn"])
    def join(self) -> None:
        self.members += UInt64(1)

    @arc4.abimethod(allow_actions=["CloseOut"])
    def leave(self) -> None:
        assert self.members > UInt64(0), "leave: nobody is opted in"
        self.members -= UInt64(1)

    @arc4.abimethod(allow_actions=["UpdateApplication"])
    def upgrade(self) -> None:
        assert Txn.sender == Global.creator_address, "upgrade: creator only"

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def shut_down(self) -> None:
        assert Txn.sender == Global.creator_address, "shut_down: creator only"
```

`@arc4.abimethod(allow_actions=["OptIn"])` is what opens the door. A method that does not say otherwise answers `NoOp` and only `NoOp` (the default is `("NoOp",)`), so a caller who sends an OptIn transaction to your ordinary method does not get a permissive fallback; they get a rejection from the router. Five actions, not six. ClearState is deliberately unroutable here, because it runs the *clear state program*, a separate program that this decorator has no reach into. There is no argument you can pass that will let an `abimethod` see a clear-state call. Chapter 4 takes that gap as its subject.

A call that carries no arguments at all has no selector to match, and needs a different kind of method.

**Example 3-15.** Bare methods, for calls with no arguments

<!-- finder: handle a call that arrives with no arguments at all -->

```python
from algopy import ARC4Contract, Global, Txn, UInt64, arc4


class Bare(ARC4Contract):
    """A bare method answers a call that carries no arguments at all."""

    def __init__(self) -> None:
        self.opted_in = UInt64(0)

    @arc4.baremethod(create="require")
    def create(self) -> None:
        # No selector, no arguments. This is what `send.bare.create()` calls,
        # and it is why the cheapest possible deploy is a bare create.
        pass

    @arc4.baremethod(allow_actions=["OptIn"])
    def opt_in(self) -> None:
        self.opted_in += UInt64(1)

    @arc4.baremethod(allow_actions=["DeleteApplication"])
    def delete(self) -> None:
        assert Txn.sender == Global.creator_address, "delete: creator only"

    @arc4.abimethod(readonly=True)
    def members(self) -> UInt64:
        return self.opted_in
```

The line to watch is `@arc4.baremethod(create="require")`. A bare method is selected by its on-completion action alone, which means there can be at most one per action. The stubs say so outright: *"There can be only one bare method on a contract for each given On-Completion Action."* This is what `send.bare.create()` calls, and it is why the cheapest possible deployment is a bare create: no selector, no arguments, no encoding.

Now the decorator argument that the counter got wrong.

**Example 3-16.** create, and the three answers to "may this run at ID zero?"

<!-- finder: restrict a method to creation, or keep it out of creation entirely -->

```python
from algopy import ARC4Contract, Global, String, Txn, UInt64, arc4


class Modes(ARC4Contract):
    """`create` decides which application IDs a method will answer to."""

    def __init__(self) -> None:
        self.count = UInt64(0)
        self.label = String("visits")

    @arc4.abimethod(create="require")
    def create(self, label: arc4.String) -> None:
        # "require": the router asserts the application ID is zero, so this
        # method exists only for the transaction that brings the app into
        # being. It can never be called again.
        self.label = label.native

    @arc4.abimethod
    def bump(self) -> UInt64:
        # "disallow" is the default, and it is the one you want by default:
        # the router asserts the application ID is NOT zero.
        self.count += UInt64(1)
        return self.count

    @arc4.abimethod
    def reset(self) -> None:
        assert Txn.sender == Global.creator_address, "reset: creator only"
        self.count = UInt64(0)
```

The key line is `@arc4.abimethod(create="require")`. The stub documentation is exact about what the three values do: *"'require' means it must be zero, 'disallow' requires it must be non-zero, and 'allow' disables the validation."* Two of those add a check. The third *removes* one, and there is no fourth option that adds a different check instead.

Here is what removing it looks like --- a variation of Example 3-16's `reset`, with `create="allow"` written in:

```python
from algopy import ARC4Contract, Global, Txn, UInt64, arc4


class Modes(ARC4Contract):
    def __init__(self) -> None:
        self.count = UInt64(0)

    @arc4.abimethod(create="allow")
    def reset(self) -> None:
        # "allow" removes the application-ID check entirely. A caller who
        # sends this against application ID 0 creates a brand new app, runs
        # __init__, resets that one, and is told it worked.
        assert Txn.sender == Global.creator_address, "reset: creator only"
        self.count = UInt64(0)
```

That is the counter's third failure, mechanised. The stranger's transaction carries application ID zero; the router was told not to ask; the AVM creates a fresh application from the same program, runs `__init__`, and only then evaluates the guard --- in a world where the sender is, truthfully, the creator. The method succeeds. The caller is charged for a new application, gets a receipt, and is told the reset worked. Your counter is untouched and nobody has any reason to look at it.

Watch it happen. Deploy the broken counter, then let a stranger send `reset` with the application ID field at zero, through a factory of their own:

```python
>>> counter.app_id
1042
>>> stranger_counter, _ = factory.send.create.reset()
>>> stranger_counter.app_id
1067
>>> counter.send.current().abi_return
0
```

No error anywhere, and the receipt names an application that did not exist a moment ago: the stranger has minted and reset a counter of their own, while yours still answers at 1042, holding the same zero it has held since deployment.

*Predict: the guard is `Txn.sender == Global.creator_address`. Rewrite it so that it cannot pass at application ID zero; then check Figure 3-1 and say whether your rewrite is a fix or a patch over one.*

This is the fix for another of the counter's failures: `reset` loses `create="allow"` and falls back to the default `disallow`, which puts an application-ID check back in front of it, the check the router had been told to skip.

::: {.gotcha #create-allow-routes-before-the-id-check topic="Authorization" title="create=allow removes the application-ID check, and at ID zero every caller is the creator"}
The three values of `create` are not three flavours of the same check. `"require"` asserts the application ID is zero and `"disallow"` asserts it is non-zero; `"allow"` deletes the assertion, and the generated router matches such a method *above* the `txn ApplicationID` branch entirely. A caller can therefore send it against application ID zero, which creates a fresh application from your program, runs `__init__`, and executes the method against empty state. Any guard of the form `Txn.sender == Global.creator_address` passes there, because the sender is the one doing the creating. Use `"allow"` only for a method genuinely designed to run in both worlds, and if you cannot say in one sentence what it should do at ID zero, you want `"disallow"`.
:::

## The File a Client Reads Before It Calls
Reachability is decided in the router. Everything else a caller needs is decided in a file. A generated client does not guess and does not introspect the program: every fact it has about your contract comes out of the ARC-56 app spec that PuyaPy emits beside the compiled artifact, and every fact in that spec comes from something you wrote above a method. The spec does not only carry what the router left alone; it also records what the router decided, which is what puts the counter's third bug in a JSON file, findable with no debugger and no TEAL.

Addressing comes first. Chapter 2 said a method selector is the first four bytes of `SHA-512/256` of the method's signature, and showed a contract checking one by hand. What goes *into* that signature is what decides whether your next refactor breaks every caller you have.

**Example 3-17.** What a selector is derived from

<!-- finder: find out whether renaming a method or changing an argument type breaks deployed callers -->

```python
from algopy import ARC4Contract, Bytes, UInt64, arc4, gtxn


class Selectors(ARC4Contract):
    """A selector is four bytes of a hash of the method's written signature."""

    def __init__(self) -> None:
        self.count = UInt64(0)

    @arc4.abimethod
    def bump(self) -> UInt64:
        self.count += UInt64(1)
        return self.count

    @arc4.abimethod(readonly=True)
    def selector_of_bump(self) -> Bytes:
        # sha512_256("bump()uint64"), first four bytes, resolved at compile
        # time. The signature string is the name and the ABI types, nothing
        # else: rename the Python method and the selector is unchanged, but
        # change an argument type and every existing caller breaks.
        return arc4.arc4_signature("bump()uint64")

    @arc4.abimethod
    def only_beside_bump(self, other: gtxn.ApplicationCallTransaction) -> None:
        # Routing is a byte comparison against argument zero, which means you
        # can do the same comparison yourself when you need to.
        assert other.num_app_args > UInt64(0), "grouped call has no selector"
        assert other.app_args(0) == arc4.arc4_signature(
            "bump()uint64"
        ), "grouped call is not bump()"
```

What matters in `return arc4.arc4_signature("bump()uint64")` is what is *not* in the string. A signature is the ABI name and the ABI argument types and the return type. It is not the parameter names, not the docstring, not the order of decorators --- and the Python method name is in it only *by default*, because the ABI name defaults to it. Pin the ABI name with `name=` and a rename of the Python method moves nothing; leave it unpinned and the rename changes the signature, the selector moves, and every deployed caller now sends four bytes that match nothing --- the router answers `err`, with no message, because there is nothing to say. The same happens if you change a parameter from `arc4.UInt64` to `arc4.UInt32`, with no `name=` to save you.

Since the ABI name and the Python name are separate, they do not have to agree.

**Example 3-18.** Two Python methods, one ABI name

<!-- finder: expose two ways to call the same operation -->

```python
from algopy import ARC4Contract, arc4


class Adder(ARC4Contract):
    """Two Python methods, one ABI name, two selectors."""

    @arc4.abimethod(name="add")
    def add_one(self, a: arc4.UInt64) -> arc4.UInt64:
        # add(uint64)uint64 -> selector ff9a73d6
        return arc4.UInt64(a.as_uint64() + 1)

    @arc4.abimethod(name="add")
    def add_two(self, a: arc4.UInt64, b: arc4.UInt64) -> arc4.UInt64:
        # add(uint64,uint64)uint64 -> selector fe6bdf69
        return arc4.UInt64(a.as_uint64() + b.as_uint64())
```

`@arc4.abimethod(name="add")` appears on both. `add(uint64)uint64` hashes to `ff9a73d6` and `add(uint64,uint64)uint64` to `fe6bdf69`, so there is no ambiguity to resolve: the arguments are part of the signature, so overloading is free. Python needs the two methods to have different names; the ABI does not care what those names are.

Addressing tells a client *which* method. One more field in the same spec tells it *how* to place the call, and it is the field the counter's `bump` misused.

**Example 3-19.** readonly, and what it actually promises

<!-- finder: offer a getter clients can call without paying a fee -->

```python
from algopy import ARC4Contract, UInt64, arc4


class Meter(ARC4Contract):
    """`readonly=True` is a promise to the caller, not a rule for you."""

    def __init__(self) -> None:
        self.count = UInt64(0)

    @arc4.abimethod
    def bump(self) -> UInt64:
        self.count += UInt64(1)
        return self.count

    @arc4.abimethod(readonly=True)
    def current(self) -> UInt64:
        # Marked readonly, so clients answer this by simulating rather than
        # submitting: no fee, no round to wait for, no ledger change.
        return self.count
```

The line to watch is `@arc4.abimethod(readonly=True)`. The stub docstring is one sentence: *"If True, then this method can be used via dry-run / simulate."* That is a permission granted to callers, not a restriction on you. The compiler does not stop a readonly method from writing state. The AVM does not stop it either: if you submit a readonly method as a real transaction it runs and its writes commit, exactly like any other method. What happens instead is that clients read the flag out of the app spec and stop submitting. The write is not blocked; the transaction that would have carried it is never sent. The simulation is a client-side courtesy a caller can decline --- `counter.new_group().bump().send()` builds a real group and submits it --- but reaching for that to make a readonly method write is a sign the flag is on the wrong method.

::: {.gotcha #readonly-methods-are-simulated-not-sent topic="Testing and simulation" title="A method marked readonly is answered by simulation, so anything it writes is silently discarded"}
`readonly=True` is a permission granted to callers, not a restriction imposed on you: the compiler does not stop a readonly method from writing state, and if you submit one as a real transaction its writes commit normally. Instead, every conforming client reads the flag out of the app spec and answers the call with `simulate`, with no fee, no round and no ledger change, then reports the returned value as though it had happened. A readonly method that mutates therefore produces correct-looking answers forever while changing nothing, and the discrepancy only appears when somebody reads the chain directly. The rule is mechanical: if the method body can reach an assignment to state or an inner transaction, it is not readonly.
:::

The other thing a caller reads out of the app spec is where to find arguments it was not given.

**Example 3-20.** Telling the client where to find an argument

<!-- finder: save a client a lookup it would otherwise do before every call -->

```python
from algopy import ARC4Contract, Txn, UInt64, arc4


class Defaults(ARC4Contract):
    """Tell the client where to find an argument the caller did not supply."""

    def __init__(self) -> None:
        self.count = UInt64(0)
        self.owner = Txn.sender

    @arc4.abimethod(readonly=True)
    def get_owner(self) -> arc4.Address:
        return arc4.Address(self.owner)

    @arc4.abimethod(default_args={"who": "get_owner", "since": "count"})
    def snapshot(self, who: arc4.Address, since: arc4.UInt64) -> UInt64:
        # The client fills these in. The contract still has to check them.
        assert who.native == self.owner, "snapshot: not the owner"
        assert since.as_uint64() <= self.count, "snapshot: since is ahead"
        return self.count - since.as_uint64()
```

The key line is `default_args={"who": "get_owner", "since": "count"}`, and there are three forms it can take, of which the example shows two: the name of a readonly method on the same contract, the name of a global state key, or a compile-time constant. The third form has a sharp edge: the constant must be of the *exact* parameter type, so a parameter typed `arc4.UInt64` needs `{"limit": arc4.UInt64(10)}` and rejects `{"limit": 10}` with `error: unexpected argument type`. All three surface in the app spec as a `defaultValue` on the argument, and all three are advice to the client. The client fills these in, and the contract still has to check them.

Selector, readonly flag, default values: three facts, one file. A client is the only thing that normally reads it, and there is nothing stopping you from opening it yourself.

**Example 3-21.** Reading an app spec the way a client does

<!-- finder: read an app spec and see what a contract exposes -->

```python
"""Print the parts of an ARC-56 app spec that a client actually uses."""

import json
import sys
from pathlib import Path


def main(path: str) -> None:
    spec = json.loads(Path(path).read_text())
    print(f"{spec['name']}: global schema {spec['state']['schema']['global']}")
    print(f"bare actions: {spec['bareActions']}")
    for m in spec["methods"]:
        args = ",".join(a["type"] for a in m["args"])
        ro = " readonly" if m["readonly"] else ""
        print(f"  {m['name']}({args}){m['returns']['type']}{ro} {m['actions']}")


if __name__ == "__main__":
    main(sys.argv[1])
```

The line that matters is `print(f"  {m['name']}({args}){m['returns']['type']}{ro} {m['actions']}")`. Three things per method: the signature the selector is computed from, whether it claims to be readonly, and the actions it answers to. Run it against the broken counter:

```console
$ python3 app_spec_tour.py counter_broken.arc56.json
Counter: global schema {'ints': 1, 'bytes': 1}
bare actions: {'create': [], 'call': []}
  create(string)void {'create': ['NoOp'], 'call': []}
  bump()uint64 readonly {'create': [], 'call': ['NoOp']}
  current()uint64 readonly {'create': [], 'call': ['NoOp']}
  describe()byte[] readonly {'create': [], 'call': ['NoOp']}
  reset()void {'create': ['NoOp'], 'call': ['NoOp']}
```

*Predict: four of those five lines are unremarkable. One of them says something no other method on the contract says. Find it before reading on.*

`reset` is the only method with a non-empty list on *both* sides. Every other method is either a creation method or an ordinary one. `reset` is both, and that is not a subtlety hidden in the generated TEAL: it is right there in a JSON file, in a client-facing artifact, in nineteen lines of Python that anyone can run against any contract on the network.

If you do open the TEAL, the same fact is visible as a matter of position. Compiled, the broken counter's router reads like this, lightly trimmed:

```teal
main_after_if_else@2:
    txn OnCompletion
    !
    assert
    pushbytes 0x19c02cb3 // method "reset()void"
    txna ApplicationArgs 0
    match reset

main_switch_case_next@5:
    txn ApplicationID
    bz main_create_NoOp@11
    pushbytess 0xe761a739 0x97018cbb 0x1f89817e
    txna ApplicationArgs 0
    match bump current describe
    err

main_create_NoOp@11:
    pushbytes 0x20df3a54 // method "create(string)void"
    txna ApplicationArgs 0
    match create
    err
```

`reset` is matched at the top, above `txn ApplicationID`. Every other method is matched below it, on one side or the other of that branch. This is Figure 3-1 rendered as opcodes: the router filters on arguments and on-completion, matches the selectors that opted out of the ID check, and only then asks whether the application exists. A method that declares `create="allow"` is answered before the question is put.

In the counter, `bump` loses `readonly=True` and becomes an ordinary method, so the client submits it and the count actually moves; `current` and `describe` keep the flag, correctly, because they write nothing and the promise is one they can keep. The greater gain is the last five lines of that app spec listing: the ability to *find* the `reset` bug next time, in a contract you did not write, without a debugger and without reading TEAL.

## Completing the Counter
Three failures, three edits, and not one of them touches a method body's logic. Here is the diff that matters; the whole corrected contract follows as Example 3-22.

```diff
-from algopy import ARC4Contract, Bytes, Global, String, Txn, UInt64, arc4, op
+from algopy import ARC4Contract, Global, String, Txn, UInt64, arc4
-    @arc4.abimethod(readonly=True)
+    @arc4.abimethod
     def bump(self) -> arc4.UInt64:
-    @arc4.abimethod(readonly=True)
-    def describe(self) -> Bytes:
-        return self.label.bytes + op.itob(self.count)
+    @arc4.abimethod(readonly=True)
+    def describe(self) -> arc4.Tuple[arc4.String, arc4.UInt64]:
+        return arc4.Tuple((arc4.String(self.label), arc4.UInt64(self.count)))
-    @arc4.abimethod(create="allow")
+    @arc4.abimethod
     def reset(self) -> None:
```

**Example 3-22.** The counter, corrected

<!-- example: examples/contracts/counter_fixed.py mode=compile -->
<!-- finder: see the counter with all three defects fixed -->

```python
from algopy import ARC4Contract, Global, String, Txn, UInt64, arc4

# A label longer than this makes `describe` awkward to read and costs the
# creator global-state bytes for nothing.
MAX_LABEL_BYTES = 32


class Counter(ARC4Contract):
    """A public counter with a label the creator chooses at creation.

    The three corrections over the first draft: `bump` writes state, so it
    no longer claims `readonly` and the client submits a real transaction;
    `describe` returns a typed tuple a generated client can decode instead
    of raw bytes; and `reset` accepts the default `create="disallow"`, so
    it can only be aimed at a counter that already exists.
    """

    def __init__(self) -> None:
        self.count = UInt64(0)
        self.label = String("visits")

    @arc4.abimethod(create="require")
    def create(self, label: arc4.String) -> None:
        text = label.native
        assert text.bytes.length > UInt64(0), "create: label must not be empty"
        assert text.bytes.length <= UInt64(MAX_LABEL_BYTES), "create: label too long"
        self.label = text

    @arc4.abimethod
    def bump(self) -> arc4.UInt64:
        self.count += UInt64(1)
        return arc4.UInt64(self.count)

    @arc4.abimethod(readonly=True)
    def current(self) -> arc4.UInt64:
        return arc4.UInt64(self.count)

    @arc4.abimethod(readonly=True)
    def describe(self) -> arc4.Tuple[arc4.String, arc4.UInt64]:
        return arc4.Tuple((arc4.String(self.label), arc4.UInt64(self.count)))

    @arc4.abimethod
    def reset(self) -> None:
        assert Txn.sender == Global.creator_address, "reset: creator only"
        self.count = UInt64(0)
```

Deploy a fresh one, so the ledger has it at zero again, and drive it the same way:

```python
>>> counter.send.bump().abi_return
1
>>> counter.send.current().abi_return
1
>>> counter.send.describe().abi_return
['visits', 1]
```

The count moved. The read agrees with the write. The description is a label and a number.

**Correction one: `bump` is not readonly.** One decorator argument, deleted. `bump` writes state, so it can never honestly claim the flag, and the client goes back to submitting a transaction, which costs a fee and takes a round; both were always the price of changing something.

**Correction two: `describe` returns a shape.** `Bytes` became `arc4.Tuple[arc4.String, arc4.UInt64]`, which costs two bytes on the wire and buys the client the ability to decode. What did *not* change: the method is still readonly, correctly, because it still writes nothing. `readonly` was never the problem on this method; only on `bump`.

**Correction three: `reset` accepts the default.** `create="allow"` deleted, which puts it back on `disallow` and restores an application-ID assertion in front of it. The creator-only check inside the body is now doing the job it was written for, because it can no longer be evaluated in a context where everyone is the creator.

The proof is one line of the app spec:

```text
BROKEN:  reset()void   {'create': ['NoOp'], 'call': ['NoOp']}
FIXED:   reset()void   {'create': [],       'call': ['NoOp']}
```

An empty list where there used to be one. That is the entire difference between a method a stranger can aim at a contract that does not exist yet and a method that can only be called on yours.

Against the commission:

1. A label the creator chooses, validated at creation --- yes, and that requirement was never in danger; `create="require"` was right from the first pass.
2. Anyone may bump and get the new value back --- yes, now that the client actually submits it: the count moved, and the read agrees with the write.
3. Anyone may read the count without paying a fee --- yes: `current` keeps `readonly=True`, and keeps it honestly, because it writes nothing.
4. A description a generated client can decode --- yes: `['visits', 1]`, a label and a number, not fourteen integers.
5. Only the creator may reset --- yes, and only against a counter that already exists, which is the half of the requirement the first pass gave away.

Five for five, and the dashboard's number is now the ledger's number.

## Retrieval
Answer these from memory before moving on. Three of them reach back into Chapter 2 on purpose.

1. The AVM has one stack and two value types on it. Name the two, say which one carries an `arc4.UInt64`, and use that to explain why `a + b` does not compile when both are `arc4.UInt64`.
2. A method is declared with no `allow_actions` argument. Which on-completion actions will it answer to?
3. Name the three parts of the string a method selector is hashed from. Then name two things about the Python method that are deliberately not in it, and say what that buys you when you refactor.
4. Which of the three `create` values *removes* a check rather than adding one, and what is the check?
5. A method carries `readonly=True` and its body assigns to global state. Say what the caller is told, what the ledger holds afterwards, and which of the compiler, the AVM and the client produced that outcome.
6. `from_bytes` and `validate`: which one costs opcodes, and which one can silently succeed on nonsense?
7. Why does `(bool,uint64,bool)` encode to more bytes than `(bool,bool,uint64)`?
8. *(From Chapter 2)* An ABI return value is a log entry. What limit does that put on how much a method can return?
9. *(From Chapter 2)* There is no private method on an ARC-4 contract. What does that imply about a method you added "just for the admin script"?
10. *(From Chapter 2)* A call to `bump` is submitted in an atomic group alongside a payment, and the payment fails. Say what the count reads afterwards, and why that answer needs no work from you.

## Exercises
1. Take the broken counter and trace a single application call through Figure 3-1. The call carries one argument, `0x19c02cb3`; its on-completion is NoOp; its application ID field is zero.

   a. **(Trace)** Write down the router's answer at each question in the figure, and name the method that runs.

   b. **(Trace)** State what `Global.creator_address` evaluates to while that method runs, and whether the assertion inside it passes.

   c. **(Trace)** Say what the caller is charged.

   d. **(Trace)** Run the same trace against the fixed counter and name the exact question at which the two traces diverge.

2. Below are six statements. Four of them form the body of a `describe` method that returns the label, the count, and whether the counter has ever been bumped; two do not belong in it at all. The decorator and signature are given, so syntax will not do your ordering for you.

   ```python
   @arc4.abimethod(readonly=True)
   def describe(self) -> arc4.Tuple[arc4.String, arc4.UInt64, arc4.Bool]:
       ...
   ```

   The statements: (i) `label = arc4.String(self.label)`; (ii) `n = arc4.UInt64(self.count)`; (iii) `return arc4.Tuple((label, n, ever))`; (iv) `self.count += UInt64(1)`; (v) `ever = arc4.Bool(self.count > UInt64(0))`; (vi) `return self.label.bytes + op.itob(self.count)`.

   a. **(Parsons)** Select the four that belong and put them in a working order.

   b. **(Parsons)** Only one of the four is forced into its position by dataflow. Name it, and say what forces it there.

   c. **(Parsons)** Say why the other three can be written in any of the six possible orders without changing what the method does.

   d. **(Debug)** Of the two you rejected, one compiles into a contract that is wrong in a way this chapter named; the other never gets past the compiler. Say which is which.

   e. **(Debug)** For the one that compiles, name the failure and describe what a caller would see.

   f. **(Debug)** For the one that does not, name the type it hands back, the type the signature promised, and give the compiler's complaint in words.

3. A contract ships with `@arc4.abimethod(readonly=True)` on a method named `claim` that transfers an asset to the caller. The team's integration tests all pass. The dashboard shows successful claims. Support tickets arrive saying users never received anything.

   a. **(Debug)** Explain what each of the three observations --- passing tests, successful dashboard claims, empty wallets --- is actually reporting.

   b. **(Debug)** Say why the integration tests passing is not evidence of anything here.

   c. **(Debug)** Describe the single smallest change to the *test* --- not the contract --- that would have caught this before shipping.

4. You need a method that takes a user's display name and stores it, and there are three parameter types that could carry it: `arc4.String`, `algopy.String`, and `Bytes`.

   a. **(Compare)** Compare the three on four axes: the ABI signature the method ends up with; whether PuyaPy validates the argument's encoding on entry; what you must do to the value before you can ask how long it is; and what a caller who sends malformed bytes can make happen.

   b. **(Compare)** Two of the three produce the *same* ABI signature. Name them, and say why that matters for a caller who was compiled against the other one.

   c. **(Compare)** State the one requirement that would force each of the three.

5. Extend the fixed counter with a `bump_many(n: arc4.UInt64)` method that increments by `n`, subject to two rules: the count must never exceed one million, and `n = 0` is rejected rather than silently doing nothing.

   a. **(Trace)** Example 3-2 says what the AVM does when a multiplication leaves the range of a `uint64`, and the same rule governs addition. State it. (`mulw`, the escape hatch in that example, widens a multiplication; it is no help to an addition.)

   b. **(Debug)** Decide whether `assert self.count + n.as_uint64() <= UInt64(1_000_000)` fails the way you intend for every value of `n`, or whether some callers are shown a different failure than the message you attached. Rearrange the bound if you need to.

   c. **(Extend)** Write the method.

   d. **(Trace)** Say which on-completion actions it answers to, and whether you had to say so.

   e. **(Trace)** Say whether it is readonly, and how you know.

   f. **(Compare)** You later change the parameter to `arc4.UInt32` to save wire bytes. Say what happens to every client already deployed against the old signature.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can state what `readonly=True` promises, who enforces it, and what happens to a write inside a method that claims it falsely.
- [ ] I can name the three values of `create`, say which one removes a check, and explain why a creator-only guard does not protect a method that uses it.
- [ ] I can predict the encoded byte length of a small ARC-4 tuple, including the case where reordering its fields changes the answer.
- [ ] I can say what a method selector is computed from, and decide whether a given refactor of a Python method breaks deployed callers.
- [ ] I can read an ARC-56 app spec and list, for each method, its signature, whether clients will simulate it, and which application IDs it can be called against.

## Handoff: The Methods the Vesting Project Exposes
Chapter 9 builds a real token vesting contract, and every method in it makes the decisions this chapter has been about: who may call it, at which application IDs, and what shape the answer takes. Table 3-2 lists the examples it leans on, and what to predict before you read it.

: Table 3-2. Examples from this chapter that the vesting project depends on

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| Example 3-16 | The vesting contract's `create` method, which captures the admin and the asset | Configuration happens exactly once. Which `create` value makes that the router's job rather than a flag you maintain? |
| Example 3-6 | Every method that takes an amount or a round number as an argument | How many conversions belong in a method that does arithmetic on two numeric arguments, and where do they go? |
| Example 3-19 | `get_claimable()`, which a wallet polls before showing a claim button | A wallet polls this many times a second. What must the method avoid doing for those calls to cost nothing? |
| Example 3-11 | `get_vesting_info()`, which returns a beneficiary's whole schedule in one call | Six fields, one call. What return type makes a generated client hand back six named values rather than a blob? |
| Example 3-14 | The contract's deliberate refusal to be updated or deleted while it holds anyone's tokens | It holds assets it owes to people. Which two on-completion actions must it never accept, and how do you say so? |
