\newpage

# Contracts That Exist and Respond

{{ch:mental-model}} got a contract onto a network and got a value back out of it. That is existence. This chapter is about the other half: the boundary. Every application call is a handful of bytes arriving at a program that has never met the caller, and everything your contract knows about that call it learns by decoding those bytes. What the caller may hand you, what you may hand back, and --- the part that surprises people --- *which of your methods they can reach at all* are three separate questions, decided by three separate mechanisms. Get any of them wrong and the compiler will not tell you, the client will not tell you, and the chain will do exactly what you asked.

## The Problem
Here is a failure with a name: **the counter that only counted in simulation.**

A team ships a public counter. One method to create it with a label, one to increment, one to read, one to describe itself. It is thirty-eight lines and there is nothing clever in it. The client wrapper is generated from the app spec, the integration test passes, and the dashboard wires up in an afternoon. Every visitor who clicks the button is told they are visitor number one. Somebody files a ticket about it; somebody else closes it as a caching problem. Everyone moves on.

Three weeks later somebody asks the network directly --- not through the dashboard, just a plain read of the application's global state --- and the counter says zero. It has said zero since the day it was deployed, and every one of those visitors was told the exact truth about a count that was never written.

The increment method was declared `readonly=True`. That flag is not a promise the *compiler* enforces, and it is not one the *AVM* enforces either; it is a promise you make to *callers*, and every conforming client takes it at face value by answering the call with a simulation instead of a transaction. A simulation runs the real program against the real ledger and throws the result away. So the number the caller saw was correct --- it is genuinely what the count *would* have been --- and the ledger never heard the question.

That is one bug. The same thirty-eight lines hold two more, and neither is a typo either. The `describe` method returns raw bytes, so the generated client hands back a list of integers rather than the label and the number it was built from --- a wrong answer that never crashes. And the `reset` method carries `create="allow"`, which means a stranger can aim it at application ID zero, create a brand-new counter of their own, reset *that* one, and be told it worked. The creator-only check inside it passes, because at application ID zero the creator is whoever is doing the creating.

Three failures, three decorator arguments and return types behaving exactly as documented. Nothing in this chapter is about finding mistakes in code. It is about the fact that the boundary has rules, and the rules are not visible from inside the method body.

## What You'll Be Able to Do
By the end of this chapter you will be able to:

- Predict the exact bytes that cross the wire for any ABI argument or return value, and read a client's decoded result back to the type that produced it
- Convert between native AVM values and their ARC-4 encodings at the one place conversion belongs --- the method boundary --- and explain why arithmetic on an ARC-4 integer does not compile
- Decide, for each method you write, which on-completion actions it answers to, whether it may run at application ID zero, and whether a client may simulate it instead of submitting it
- Say what a method selector is derived from, and predict which edits to a Python method break every existing caller and which change nothing
- Validate an ARC-4 argument that arrived from someone you do not trust, and name what PuyaPy checks on your behalf by default
- Read an ARC-56 app spec and answer, without opening a line of generated TEAL, which of a contract's methods a stranger can reach and when

{{fig:router-decision}} is the machine that answers that last question. PuyaPy generates it for you from the decorators you write, and it asks its questions in a fixed order. Before you look at it, write down where you would put the check that decides whether the application already exists --- first, last, or somewhere in between. Then read the figure. The router asks that question *after* it has filtered on the on-completion action, and after it has already matched any method that opted out of the check altogether. This chapter's third failure lives entirely inside that second gap.

{{include-fig:router-decision}}

## The Mini-Build, Broken
Here is the counter, as shipped. {{ex:counter-broken}} is complete and deployable --- it compiles, it runs on LocalNet, and it contains three decisions that are wrong.

Example: A counter with an API, as shipped {#ex:counter-broken}

<!-- finder: see a contract with a few methods a generated client can call -->

{{include-ex:counter-broken}}

*Predict: three decisions in that contract are wrong. Write your three down now, in whatever words you have --- you are not expected to be right yet. Check them against the diff at the end of the chapter.*

Every method does something defensible; the question is whether it does the thing its name promises. Deploy it and drive it through the generated client. The counter has just been created, so the ledger has it at zero.

```python
>>> counter.send.describe().abi_return
[118, 105, 115, 105, 116, 115, 0, 0, 0, 0, 0, 0, 0, 0]
```

That is the first failure and it is worth staring at. Nothing errored. The method returned, the client decoded the return value, and what came back was fourteen integers. They are not wrong --- `118, 105, 115, 105, 116, 115` is `visits` in UTF-8 and the eight zeros after it are the number zero, big-endian. The bytes are perfect. The *type* is `byte[]`, and a `byte[]` is a list of bytes, so a list of bytes is what any conforming decoder must produce. There is no smarter client that would have guessed.

Now the second failure.

```python
>>> counter.send.bump().abi_return
1
>>> counter.send.bump().abi_return
1
>>> counter.send.current().abi_return
0
```

Nothing was written. `bump` is marked `readonly=True`, so the client answered the call with a simulation: it ran the real program against a ledger where the count is zero, computed one, threw the write away, and reported one. The second call started from zero again. `current()` --- also readonly, also simulated, but honest, because it writes nothing --- reports the ledger's actual zero. Two methods, the same mechanism, and only one of them is lying. Every visitor really was told they were visitor number one.

The third failure produces no transcript at all, which is exactly why it is the dangerous one. `reset` declares `create="allow"`, and to see what that costs you have to look at where the router puts it. You will find it in "What Makes a Method Reachable" and "The File a Client Reads Before It Calls," later in this chapter.

## Two Types, and Nothing Else
The broken counter's `describe` is one expression long: `self.label.bytes + op.itob(self.count)`. Two conversions and a concatenation, and it is the seed of the chapter's first failure. Before you can see why, you need the rule underneath it. {{ch:mental-model}} stated the surface of that rule: there is no floating point, and there are two types, `uint64` and `bytes`. That is true and it is not yet useful, because the consequence people actually need is this --- the AVM has *one* stack with *two value types* on it, a value never implicitly converts from one to the other, and every conversion you will ever write moves a value across that line by hand.

Example: The two value types, and moving between them {#ex:stack-types}

<!-- finder: know what the AVM will and will not let me do to a value -->

{{include-ex:stack-types}}

The load-bearing line is `high, low = op.mulw(a, b)`. Ordinary `*` fails the transaction when the product exceeds 64 bits --- it does not wrap, which is a mercy --- and `mulw` is the escape hatch that returns the 128-bit result as two 64-bit words. You will meet it again the first time you price anything. The no-wraparound rule is not special to multiplication: `+` and `-` abort the same way when the result leaves the range, and there is no `mulw` equivalent standing by to catch them.

Text is where the two value types get confusing, because Python offers three types that all look like strings.

Example: String, arc4.String, and Bytes {#ex:string-vs-bytes}

<!-- finder: choose between the three text types -->

{{include-ex:string-vs-bytes}}

The load-bearing line is `return s.bytes.length`. `algopy.String` supports neither `len()` nor indexing, and the docstring says why: *"due to the lack of UTF-8 support in the AVM, indexing and length operations are not currently supported."* The AVM counts bytes. A character is a concept it has never heard of. What separates the three types is one thing each: `String` is UTF-8 text with no length prefix, `arc4.String` is the same text behind a two-byte big-endian length prefix, and `Bytes` is the raw form underneath both, with no prefix and no promise that the contents are text at all.

*Predict: `join("héllo", "wörld")` returns a `String`. What does `length` report for it, and is that the answer a user would expect?*

Raw bytes slice, and the result of indexing one is not a number. This is the machinery a caller would need if they wanted to make sense of the broken counter's fourteen integers on their own: take the last eight bytes, turn them into a number, and read what is left as text.

Example: Slicing and indexing raw bytes {#ex:slice-bytes}

<!-- finder: pull one field out of the middle of a byte string -->

{{include-ex:slice-bytes}}

The load-bearing line is `return op.btoi(b[i])`. `b[i]` is a `Bytes` of length one, not a `UInt64` --- indexing a byte string gives you a shorter byte string, because a byte string is the only thing a byte string contains. `btoi` is what moves it across to the other type.

That leaves the conversion you will write most often.

Example: itob and btoi, the exact round trip {#ex:itob-btoi}

<!-- finder: put a number into a key, or get one back out of a byte string -->

{{include-ex:itob-btoi}}

The load-bearing line is `return prefix + op.itob(n)`. `itob` always produces exactly eight bytes --- the number seven becomes `00 00 00 00 00 00 00 07`, never the single byte `07` --- and it is that fixed width, not the encoding, that makes it safe. A key built as prefix-plus-`itob` can always be taken apart again, because the number is always the last eight bytes. A variable-width encoding would leave you guessing.

*What this section repairs in the counter:* the expression, not the method. `self.label.bytes + op.itob(self.count)` is now readable as exactly what it is --- two byte strings concatenated, one of them produced by the fixed-width conversion you just met --- and it is perfectly legal. The compiler had no objection to raise and it was right not to. The mistake is one level up, at the boundary, which is where the next section goes.

## Crossing the ARC-4 Boundary
An `arc4.UInt64` is not a number. It is an eight-byte encoding of a number, living on the byte stack, and the single most common early error is forgetting that.

Example: Converting at the edge, and only at the edge {#ex:arc4-boundary}

<!-- finder: do arithmetic with an ARC-4 argument -->

{{include-ex:arc4-boundary}}

The load-bearing line is `total: UInt64 = a.as_uint64() + b.as_uint64()`. Convert once on the way in, do the work in native types, convert once on the way out. Nothing between those two lines needs to know that ARC-4 exists. The alternative is to skip the boundary entirely: PuyaPy accepts native `UInt64`, `String` and `Bytes` directly as ABI argument and return types, encoding them as `uint64`, `string` and `byte[]` --- so `add` and `add_native` above put *identical* argument and return types on the wire, and neither body is any harder to read than the other. Only the ABI name differs. That is enough to make them two distinct selectors, `fe6bdf69` and `5d767951`, for a reason "The File a Client Reads Before It Calls" gets to later in this chapter; give the second one `name="add"` and a caller genuinely cannot tell them apart.

Try it without the conversion and the compiler stops you:

{{include-ex:arc4-boundary-wrong}}

```text
error: Unsupported left operand type for + ("UIntN[Literal[64]]")
error: Returning Any from function declared to return "UIntN[Literal[64]]"
```

Every ARC-4 type unwraps, and the method you call depends on which type it is.

Example: Unwrapping every ARC-4 type {#ex:as-uint64}

<!-- finder: get the native value out of an ARC-4 one -->

{{include-ex:as-uint64}}

The load-bearing line is `return n.as_uint64()`. Integer types --- `arc4.UInt64`, `arc4.UInt8`, `arc4.UInt512` and the rest --- moved from `.native` to `as_uint64()` and `as_biguint()`. `.native` still exists and still works, but it is marked deprecated, and here is the trap: **PuyaPy does not warn you.** The compiler is silent. The only tool that will tell you is mypy with the deprecation error code switched on:

```console
$ python3 -m mypy --enable-error-code deprecated as_uint64.py
```

Everything that is not an integer kept `.native` and kept it undeprecated: `arc4.String.native` gives an `algopy.String`, `arc4.Address.native` an `Account`, `arc4.Bool.native` a plain `bool`, `arc4.DynamicBytes.native` a `Bytes`. Arrays are the exception in the other direction --- `StaticArray` and `DynamicArray` have `to_native`, not `native`.

Going the other way, from loose bytes into an ARC-4 value, is where trust enters the chapter.

Example: from_bytes reinterprets; validate checks {#ex:from-bytes-validate}

<!-- finder: treat raw bytes as an ARC-4 value safely -->

{{include-ex:from-bytes-validate}}

The load-bearing line is `text.validate()`. `from_bytes` is documented as performing no validation, and it means it: it relabels a byte string as an ARC-4 value and emits no opcodes at all. Hand it `b"\x00\x05"` --- a length prefix claiming five bytes follow, with nothing behind it --- and the call succeeds. The lie surfaces later, somewhere else, in a method that had nothing to do with the decision.

For arguments that arrive through the ABI rather than as loose bytes, PuyaPy inserts that validation for you on every method, by default. You can turn it off, and there is a real reason to: validation costs opcode budget, and on a hot method with a large struct argument it can cost more than the method body.

Example: Turning off argument validation, and paying for it yourself {#ex:unsafe-decoding}

<!-- finder: cut the cost of argument validation on a method that is over budget -->

{{include-ex:unsafe-decoding}}

The load-bearing line is `@arc4.abimethod(validate_encoding="unsafe_disabled")` immediately above `bid.validate()`. The decorator argument does not make the check unnecessary; it makes the check *yours*, and moves it to a line you choose. Drop that one line and the contract still compiles, still deploys, and still passes every test written with well-formed inputs:

{{include-ex:unsafe-decoding-wrong}}

Hold on to that one for a moment. What a caller can actually *do* with an unvalidated struct depends on how ARC-4 lays a struct out, and the next section is where that layout gets pinned down.

*What this section repairs in the counter:* `describe` returns `Bytes`, which is the untyped floor of the whole type system --- a value with no shape and no promises. Everything in this section has been about the difference between bytes that *are* something and bytes that merely *encode* something. The counter's description is bytes that merely encode, when it should be bytes that are. This section names the mistake; it does not yet have the type that fixes it. The next one does.

## Values with Shape
ARC-4 gives the wire a type system, and its layout rules are worth knowing precisely, because two of them are counter-intuitive enough to cost real money in storage.

Example: Bools pack, but only next to each other {#ex:bool-packing}

<!-- finder: find out what several flags cost me -->

{{include-ex:bool-packing}}

The load-bearing line is `return Flags(on, off, on, off, on, off, on, off)`. Eight `arc4.Bool` values in a row occupy one byte --- alternating true and false is literally `0xaa`. But the packing only applies while they are adjacent. Put anything between two bools and each one is rounded up to its own byte.

Table: What ARC-4 actually puts on the wire {#tbl:arc4-layout}

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

Read rows four and five of {{tbl:arc4-layout}} together. The same three values, reordered, cost nine bytes or ten depending on whether the two bools touch. That is a one-byte difference in a tuple and a factor-of-eight difference in a struct with sixteen flags in it.

The last three rows are all doing the same trick, and it is the one rule that explains every remaining row in the table. Anything whose size the type does not fix --- a string, a growable array --- cannot sit inline, because the field after it would have no fixed address. So it is split: a fixed-width *offset* goes in the head, where the field would have been, and the bytes themselves go in the tail. Here is the `string[]` row taken apart:

```text
0002              two elements
0004  0007        where element 0 and element 1 begin, counted
                  from the start of this offset list
0001  61          element 0: a length prefix of 1, then "a"
0002  6262        element 1: a length prefix of 2, then "bb"
```

Two bytes of count, four bytes of offsets, seven bytes of actual content. Every reader of that value trusts the offsets before it looks at anything else.

*Predict: an unvalidated `Bid` is laid out the same way --- the `uint64` inline, then an offset pointing at the array. A caller with validation disabled writes that offset by hand and puts a number there that points past the end of what they sent. Say what `bid.rounds` reads.*

Returning several values at once needs no wrapper type and no encoding of your own.

Example: Returning several typed values at once {#ex:tuple-return}

<!-- finder: give the client more than one thing back from a single call -->

{{include-ex:tuple-return}}

The load-bearing line is the return type, `arc4.Tuple[arc4.String, arc4.UInt64, arc4.Bool]`. That type is the whole contract with the caller: the generated client decodes it into three values of three types, without being told anything else. This is the shape the broken counter's `describe` should have had from the first line of it.

Arrays come in two kinds and the difference is one field.

Example: A fixed-length array {#ex:static-array}

<!-- finder: hold exactly N of something where N never changes -->

{{include-ex:static-array}}

Example: An array that grows {#ex:dynamic-array}

<!-- finder: hold a list when the length is not known in advance -->

{{include-ex:dynamic-array}}

The load-bearing difference is the length prefix. A `StaticArray` has none --- its length is in its type, so three `uint64`s are twenty-four bytes and nothing else, and the AVM can compute the offset of element *i* without reading anything. A `DynamicArray` carries a two-byte count in front, which is what lets you `append` to it and what forces every reader to consult that count first. Fixed is cheaper; growable is possible; there is no third option and no way to have both.

*What this section repairs in the counter:* the first of the three failures. `describe` becomes `arc4.Tuple[arc4.String, arc4.UInt64]`. Eighteen bytes on the wire instead of sixteen, and on the far side of the wire, `['visits', 1]` instead of a list of integers. The `byte[]` was already spending two bytes of overhead, a length prefix of its own; the tuple spends four --- a head offset saying where the string starts, and the string's own length prefix. Both carry the same fourteen bytes of payload, so the tuple costs two bytes more, and those two bytes are the entire difference between a value a client can decode and one it cannot.

## What Makes a Method Reachable
Everything so far has been about the *contents* of a call. This section is about whether the call reaches your method at all, which is decided before your method body runs and by things you write above it.

{{ch:mental-model}} introduced the six on-completion actions and showed them as a lifecycle in {{fig:oncompletes}}. Here they are as a routing decision.

Example: The five actions a method can answer to {#ex:allow-actions}

<!-- finder: run a method on opt-in or delete rather than on an ordinary call -->

{{include-ex:allow-actions}}

The load-bearing line is `@arc4.abimethod(allow_actions=["OptIn"])`. A method that does not say otherwise answers `NoOp` and only `NoOp` --- the default is `("NoOp",)` --- so a caller who sends an OptIn transaction to your ordinary method does not get a permissive fallback; they get a rejection from the router. Note the count: five actions, not six. ClearState is deliberately unroutable here, because it runs the *clear state program*, a separate program that this decorator has no reach into. There is no argument you can pass that will let an `abimethod` see a clear-state call. {{ch:state}} takes that gap as its subject.

A call that carries no arguments at all has no selector to match, and needs a different kind of method.

Example: Bare methods, for calls with no arguments {#ex:bare-methods}

<!-- finder: handle a call that arrives with no arguments at all -->

{{include-ex:bare-methods}}

The load-bearing line is `@arc4.baremethod(create="require")`. A bare method is selected by its on-completion action alone, which means there can be at most one per action --- the stubs say so outright: *"There can be only one bare method on a contract for each given On-Completion Action."* This is what `send.bare.create()` calls, and it is why the cheapest possible deployment is a bare create: no selector, no arguments, no encoding.

Now the decorator argument that the counter got wrong.

Example: create, and the three answers to "may this run at ID zero?" {#ex:create-modes}

<!-- finder: restrict a method to creation, or keep it out of creation entirely -->

{{include-ex:create-modes}}

The load-bearing line is `@arc4.abimethod(create="require")`. The stub documentation is exact about what the three values do: *"'require' means it must be zero, 'disallow' requires it must be non-zero, and 'allow' disables the validation."* Two of those add a check. The third *removes* one, and there is no fourth option that adds a different check instead.

Here is what removing it looks like:

{{include-ex:create-modes-wrong}}

The creator-only assertion in that method is not a typo, is not misspelled, and does not help. A stranger sends this method against application ID zero. The router does not check the ID, because it was told not to. The AVM creates a new application from the same program, runs `__init__`, and evaluates `Txn.sender == Global.creator_address` --- which is *true*, because the sender is creating the application and is therefore its creator. The method succeeds. The caller is charged for a new application, gets a receipt, and is told the reset worked. Your counter is untouched and nobody has any reason to look at it.

*Predict: the guard is `Txn.sender == Global.creator_address`. Rewrite it so that it cannot pass at application ID zero --- then check {{fig:router-decision}} and say whether your rewrite is a fix or a patch over one.*

*What this section repairs in the counter:* one of the three failures. `reset` loses `create="allow"` and falls back to the default `disallow`, which puts an application-ID check back in front of it --- the check the router had been told to skip.

## The File a Client Reads Before It Calls
Reachability is decided in the router. Everything else a caller needs is decided in a file. A generated client does not guess and does not introspect the program: every fact it has about your contract comes out of the ARC-56 app spec that PuyaPy emits beside the compiled artifact, and every fact in that spec comes from something you wrote above a method. This section reads that file from the outside in --- how a call is addressed, what the client is permitted to do with it, where the client finds arguments you never handed it, and what the whole spec looks like when you open it yourself. That last part is the payoff: the spec does not only carry what the router left alone, it also records what the router decided, which is how this section ends by finding the counter's third bug in a JSON file with no debugger and no TEAL.

Addressing comes first. {{ch:mental-model}} said a method selector is the first four bytes of `SHA-512/256` of the method's signature, and showed a contract checking one by hand. What it did not say is what goes *into* that signature, and that turns out to be the thing that decides whether your next refactor breaks every caller you have.

Example: What a selector is derived from {#ex:method-selector}

<!-- finder: find out whether renaming a method or changing an argument type breaks deployed callers -->

{{include-ex:method-selector}}

The load-bearing line is `return arc4.arc4_signature("bump()uint64")`, and it is load-bearing because of what is *not* in the string. A signature is the ABI name and the ABI argument types and the return type. It is not the Python method name, not the parameter names, not the docstring, not the order of decorators. Rename the Python method and the selector does not move. Change a parameter from `arc4.UInt64` to `arc4.UInt32` and the selector moves, every deployed caller now sends four bytes that match nothing, and the router answers `err` --- with no message, because there is nothing to say.

Since the ABI name and the Python name are separate, they do not have to agree.

Example: Two Python methods, one ABI name {#ex:abi-name-overload}

<!-- finder: expose two ways to call the same operation -->

{{include-ex:abi-name-overload}}

The load-bearing line is `@arc4.abimethod(name="add")` on both. `add(uint64)uint64` hashes to `ff9a73d6` and `add(uint64,uint64)uint64` to `fe6bdf69`, so there is no ambiguity to resolve --- the arguments are part of the signature, so overloading is free. Python needs the two methods to have different names; the ABI does not care what those names are.

Addressing tells a client *which* method. One more field in the same spec tells it *how* to place the call --- and it is the field the counter's `bump` misused.

Example: readonly, and what it actually promises {#ex:readonly-method}

<!-- finder: offer a getter clients can call without paying a fee -->

{{include-ex:readonly-method}}

The load-bearing line is `@arc4.abimethod(readonly=True)`. The stub docstring is one sentence: *"If True, then this method can be used via dry-run / simulate."* That is a permission granted to callers, and it is worth being precise about what is and is not enforced. The compiler does not stop a readonly method from writing state. The AVM does not stop it either --- if you submit a readonly method as a real transaction it runs and its writes commit, exactly like any other method. What happens is that clients read the flag out of the app spec and stop submitting. The write is not blocked; the transaction that would have carried it is never sent.

The other thing a caller reads out of the app spec is where to find arguments it was not given.

Example: Telling the client where to find an argument {#ex:default-args}

<!-- finder: save a client a lookup it would otherwise do before every call -->

{{include-ex:default-args}}

The load-bearing line is `default_args={"who": "get_owner", "since": "count"}`, and there are three forms it can take, of which the example shows two: the name of a readonly method on the same contract, the name of a global state key, or a compile-time constant. The third form has a sharp edge --- the constant must be of the *exact* parameter type, so a parameter typed `arc4.UInt64` needs `{"limit": arc4.UInt64(10)}` and rejects `{"limit": 10}` with `error: unexpected argument type`. All three surface in the app spec as a `defaultValue` on the argument, and all three are advice to the client. The comment in the example is the whole security posture: the client fills these in, and the contract still has to check them.

Selector, readonly flag, default values: three facts, one file. It is worth opening that file directly, because a client is the only thing that normally reads it and there is nothing stopping you.

Example: Reading an app spec the way a client does {#ex:app-spec-tour}

<!-- finder: read an app spec and see what a contract exposes -->

{{include-ex:app-spec-tour}}

The load-bearing line is `print(f"  {m['name']}({args}){m['returns']['type']}{ro} {m['actions']}")`. Three things per method: the signature the selector is computed from, whether it claims to be readonly, and the actions it answers to. Run it against the broken counter:

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

`reset` is the only method with a non-empty list on *both* sides. Every other method is either a creation method or an ordinary one. `reset` is both, and that is not a subtlety hidden in the generated TEAL --- it is right there in a JSON file, in a client-facing artifact, in nineteen lines of Python that anyone can run against any contract on the network.

If you do open the TEAL, the same fact is visible as a matter of position. This is the router PuyaPy generated for the broken counter, lightly trimmed:

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

`reset` is matched at the top, above `txn ApplicationID`. Every other method is matched below it, on one side or the other of that branch. This is {{fig:router-decision}} rendered as opcodes: the router filters on arguments and on-completion, matches the selectors that opted out of the ID check, and only then asks whether the application exists. A method that declares `create="allow"` is answered before the question is put.

*What this section repairs in the counter:* one failure, and one thing that is not a failure at all. `bump` loses `readonly=True` and becomes an ordinary method, so the client submits it and the count actually moves; `current` and `describe` keep the flag, correctly, because they write nothing and the promise is one they can keep. The thing that is not a failure is the last five lines of that app spec listing --- what this section really repairs is your ability to *find* the `reset` bug next time, in a contract you did not write, without a debugger and without reading TEAL.

## The Mini-Build, Fixed
Three failures, three edits, and not one of them touches a method body's logic. The corrected contract is on disk at `examples/ch02_contracts/counter_fixed.py` and compiles in CI; here is the diff that matters.

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

Deploy a fresh one --- so the ledger has it at zero again --- and drive it the same way:

```python
>>> counter.send.bump().abi_return
1
>>> counter.send.current().abi_return
1
>>> counter.send.describe().abi_return
['visits', 1]
```

The count moved. The read agrees with the write. The description is a label and a number.

**Correction one: `bump` is not readonly.** One decorator argument, deleted. `bump` writes state, so it can never honestly claim the flag, and the client goes back to submitting a transaction --- which costs a fee and takes a round, both of which were always the price of changing something.

**Correction two: `describe` returns a shape.** `Bytes` became `arc4.Tuple[arc4.String, arc4.UInt64]`, which costs two bytes on the wire and buys the client the ability to decode. Note what did *not* change: the method is still readonly, correctly, because it still writes nothing. `readonly` was never the problem on this method; only on `bump`.

**Correction three: `reset` accepts the default.** `create="allow"` deleted, which puts it back on `disallow` and restores an application-ID assertion in front of it. The creator-only check inside the body is now doing the job it was written for, because it can no longer be evaluated in a context where everyone is the creator.

The proof is in the app spec, and it is one line of it:

```text
BROKEN:  reset()void   {'create': ['NoOp'], 'call': ['NoOp']}
FIXED:   reset()void   {'create': [],       'call': ['NoOp']}
```

An empty list where there used to be one. That is the entire difference between a method a stranger can aim at a contract that does not exist yet and a method that can only be called on yours.

## What Bites People Here
Five, in the order you are likely to meet them: two that happen outside your method body --- one in the client, one in the router --- and three that the encoding does without your types saying so out loud.

::: {.gotcha #readonly-methods-are-simulated-not-sent topic="Testing and simulation" title="A method marked readonly is answered by simulation, so anything it writes is silently discarded"}
`readonly=True` is a permission granted to callers, not a restriction imposed on you: the compiler does not stop a readonly method from writing state, and if you submit one as a real transaction its writes commit normally. What happens instead is that every conforming client reads the flag out of the app spec and answers the call with `simulate` --- no fee, no round, no ledger change --- and reports the returned value as though it had happened. A readonly method that mutates therefore produces correct-looking answers forever while changing nothing, and the discrepancy only appears when somebody reads the chain directly. The rule is mechanical: if the method body can reach an assignment to state or an inner transaction, it is not readonly. The simulation is a client-side courtesy and a caller can decline it --- `counter.new_group().bump().send()` builds a real group and submits it --- but reaching for that to make a readonly method write is a sign the flag is on the wrong method.
:::

::: {.gotcha #create-allow-routes-before-the-id-check topic="Authorization" title="create=allow removes the application-ID check, and at ID zero every caller is the creator"}
The three values of `create` are not three flavours of the same check. `"require"` asserts the application ID is zero and `"disallow"` asserts it is non-zero; `"allow"` deletes the assertion, and the generated router matches such a method *above* the `txn ApplicationID` branch entirely. A caller can therefore send it against application ID zero, which creates a fresh application from your program, runs `__init__`, and executes the method against empty state. Any guard of the form `Txn.sender == Global.creator_address` passes there, because the sender is the one doing the creating. Use `"allow"` only for a method genuinely designed to run in both worlds, and if you cannot say in one sentence what it should do at ID zero, you want `"disallow"`.
:::

::: {.gotcha #from-bytes-reinterprets-without-checking topic="Compilation, tooling, and shipping" title="from_bytes relabels bytes as an ARC-4 value and verifies nothing; validate is the check it skipped"}
`arc4.String.from_bytes(raw)` emits no opcodes and performs no validation --- the stub documentation says so --- so a length prefix that disagrees with the payload behind it sails through and fails somewhere else, later, in code that had nothing to do with the decision. PuyaPy does insert argument validation on ABI methods by default, which is why this mostly bites on values you assembled yourself from boxes, logs, or arguments to a method carrying `validate_encoding="unsafe_disabled"`. Where you have disabled it for opcode budget, `.validate()` is not optional; it is the same check, moved to a line you chose.
:::

::: {.gotcha #arc4-bools-only-pack-when-adjacent topic="Resource references, MBR, and budget" title="ARC-4 bools share a byte only while they are adjacent, so field order changes the size"}
Eight `arc4.Bool` values in a row occupy one byte. Put any non-bool field between two of them and each is rounded up to a byte of its own: `(bool,bool,uint64)` encodes in nine bytes and `(bool,uint64,bool)` in ten, for the same three values. In a tuple that is one byte. In a struct with sixteen flags interleaved with other fields it is fourteen wasted bytes on every read and every write, and in box storage those bytes are priced at 400 microAlgos each, forever. Group your bools.
:::

::: {.gotcha #byte-array-return-is-not-text topic="Compilation, tooling, and shipping" title="A byte[] return arrives at the client as a list of integers, and no decoder will guess otherwise"}
Returning `Bytes` from an ABI method gives the method a `byte[]` return type, and a conforming client decodes `byte[]` into a list of integers --- because that is what the type means. Text that you concatenated by hand comes back as `[118, 105, 115, ...]`, and the caller has no way to know it was ever meant to be read. This never raises: it is a wrong answer that succeeds. If the value has structure, say so in the return type --- `arc4.String`, a tuple, a struct --- and let the encoding carry the meaning instead of a comment in your codebase.
:::

## Retrieval
Answer these from memory before moving on. Three of them reach back into {{ch:mental-model}} on purpose.

1. The AVM has one stack and two value types on it. Name the two, say which one carries an `arc4.UInt64`, and use that to explain why `a + b` does not compile when both are `arc4.UInt64`.
2. A method is declared with no `allow_actions` argument. Which on-completion actions will it answer to?
3. Name the three parts of the string a method selector is hashed from. Then name two things about the Python method that are deliberately not in it, and say what that buys you when you refactor.
4. Which of the three `create` values *removes* a check rather than adding one, and what is the check?
5. A method carries `readonly=True` and its body assigns to global state. Say what the caller is told, what the ledger holds afterwards, and which of the compiler, the AVM and the client produced that outcome.
6. `from_bytes` and `validate`: which one costs opcodes, and which one can silently succeed on nonsense?
7. Why does `(bool,uint64,bool)` encode to more bytes than `(bool,bool,uint64)`?
8. *(From {{ch:mental-model}})* An ABI return value is a log entry. What limit does that put on how much a method can return?
9. *(From {{ch:mental-model}})* There is no private method on an ARC-4 contract. What does that imply about a method you added "just for the admin script"?
10. *(From {{ch:mental-model}})* A call to `bump` is submitted in an atomic group alongside a payment, and the payment fails. Say what the count reads afterwards, and why that answer needs no work from you.

## Exercises
1. **(Trace)** Take the broken counter and trace a single application call through {{fig:router-decision}}, writing down the answer at each question. The call carries one argument, `0x19c02cb3`, its on-completion is NoOp, and its application ID field is zero. Say which method runs, what `Global.creator_address` evaluates to during it, whether the assertion inside it passes, and what the caller is charged. Then do the same trace against the fixed counter and name the exact question at which the two traces diverge.

2. **(Parsons)** Below are six statements. Four of them form the body of a `describe` method that returns the label, the count, and whether the counter has ever been bumped; two do not belong in it at all. The decorator and signature are given, so syntax will not do your ordering for you.

   ```python
   @arc4.abimethod(readonly=True)
   def describe(self) -> arc4.Tuple[arc4.String, arc4.UInt64, arc4.Bool]:
       ...
   ```

   The statements: (a) `label = arc4.String(self.label)`; (b) `n = arc4.UInt64(self.count)`; (c) `return arc4.Tuple((label, n, ever))`; (d) `self.count += UInt64(1)`; (e) `ever = arc4.Bool(self.count > UInt64(0))`; (f) `return self.label.bytes + op.itob(self.count)`.

   Select the four that belong and order them. Only one of the four is forced into its position by dataflow --- name it, say what forces it there, and say why the other three can be written in any of six orders without changing what the method does. Then take the two you rejected. One of them compiles and produces a contract that is wrong in a way this chapter named; the other never gets past the compiler. Say which is which before you say why. For the one that compiles, name the failure and describe what a caller would see. For the one that does not, name the type it hands back, name the type the signature promised, and give the compiler's complaint in words.

3. **(Debug)** A contract ships with `@arc4.abimethod(readonly=True)` on a method named `claim` that transfers an asset to the caller. The team's integration tests all pass. The dashboard shows successful claims. Support tickets arrive saying users never received anything. Explain what each of the three observations is actually reporting, say why the integration test passing is not evidence of anything here, and describe the single smallest change to the *test* --- not the contract --- that would have caught this before shipping.

4. **(Compare)** You need a method that takes a user's display name and stores it. Compare three parameter types --- `arc4.String`, `algopy.String`, and `Bytes` --- on four axes: the ABI signature the method ends up with, whether PuyaPy validates the argument's encoding on entry, what you have to do to the value before you can ask how long it is, and what a caller who sends malformed bytes can make happen. Two of the three produce the *same* ABI signature; name them and say why that matters for a caller who was compiled against the other one. Then state the one requirement that would force each of the three.

5. **(Extend)** Extend the fixed counter with a `bump_many(n: arc4.UInt64)` method that increments by `n`, subject to two rules: the count must never exceed one million, and the method must reject `n = 0` rather than silently doing nothing. Write it. Then answer three questions about what you wrote: which on-completion actions does it answer to and did you have to say so; is it readonly and how do you know; and if you later decide to change the parameter to `arc4.UInt32` to save wire bytes, what happens to every client already deployed against it? One detail is worth thinking about before you write the assertion: {{ex:stack-types}} says what the AVM does when arithmetic leaves the range of a `uint64`, and the rule there is the same one that governs addition. Say what it does, then say whether `self.count + n <= UInt64(1_000_000)` is a bound that fails the way you intended, or whether you need to rearrange it so that the assertion you wrote --- and the message you attached to it --- is what the caller actually sees. Note that `mulw`, the escape hatch from that example, is no help here: it widens a multiplication, and this is an addition.

## Before You Continue
You should be able to check off all five of these:

- [ ] I can state what `readonly=True` promises, who enforces it, and what happens to a write inside a method that claims it falsely.
- [ ] I can name the three values of `create`, say which one removes a check, and explain why a creator-only guard does not protect a method that uses it.
- [ ] I can predict the encoded byte length of a small ARC-4 tuple, including the case where reordering its fields changes the answer.
- [ ] I can say what a method selector is computed from, and decide whether a given refactor of a Python method breaks deployed callers.
- [ ] I can read an ARC-56 app spec and list, for each method, its signature, whether clients will simulate it, and which application IDs it can be called against.

## Handoff: What the Vesting Project Needs
{{ch:token-vesting}} builds a real token vesting contract, and every method in it makes the decisions this chapter has been about --- who may call it, at which application IDs, and what shape the answer takes. {{tbl:contracts-handoff}} lists the examples it leans on, and what to predict before you read it.

Table: Examples from this chapter that the vesting project depends on {#tbl:contracts-handoff}

| From this chapter | Where it appears in the project | Predict before you read it |
|-------------------|---------------------------------|----------------------------|
| {{ex:create-modes}} | The vesting contract's `create` method, which captures the admin and the asset | Configuration happens exactly once. Which `create` value makes that the router's job rather than a flag you maintain? |
| {{ex:arc4-boundary}} | Every method that takes an amount or a round number as an argument | How many conversions belong in a method that does arithmetic on two numeric arguments, and where do they go? |
| {{ex:readonly-method}} | `get_claimable()`, which a wallet polls before showing a claim button | A wallet polls this many times a second. What must the method avoid doing for those calls to cost nothing? |
| {{ex:tuple-return}} | `get_vesting_info()`, which returns a beneficiary's whole schedule in one call | Six fields, one call. What return type makes a generated client hand back six named values rather than a blob? |
| {{ex:allow-actions}} | The contract's deliberate refusal to be updated or deleted while it holds anyone's tokens | It holds assets it owes to people. Which two on-completion actions must it never accept, and how do you say so? |
