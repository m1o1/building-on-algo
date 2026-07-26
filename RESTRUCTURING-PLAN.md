# Building on Algorand — Restructuring Plan

**A need-based architecture: 236 micro-examples, 14 concept chapters, 7 project chapters, 1 capstone**

Prepared by the algorand-expert, teaching-pro, and publishing-pro agents, synthesized and arbitrated.
Toolchain baseline verified 2026-07-24: puyapy 5.8.1 / algorand-python 3.5.0 / algokit-utils 4.2.3 / AVM v12 / consensus v41.
§2.1's line-count measurements were taken on puyapy 5.9.0, released since; Phase 0 re-takes the pin (§12).

---

## 0. The one-paragraph version

You asked for a book you can read as "a chapter with multiple self-contained tiny examples, each demonstrating one concept, then a project chapter to tie everything together," with the recipes dissolved into need-shaped chapters rather than exiled to an appendix. That book exists inside the current one — it is just inverted. The current book is seven project chapters resting on no conceptual substrate, with the substrate exiled to `A1-cookbook.md`: 65 recipes across 17 topic sections, zero exercises, zero prediction prompts, sitting roughly 400 pages after the point of need. This plan turns it right side up. It defines a taxonomy of **fourteen developer needs**, populates them with **236 micro-examples** (104 of which already exist in the book as code and only need re-cutting; 38 more exist as prose with no runnable code), organizes those needs into **14 concept chapters** that alternate with the **7 existing projects**, and dissolves the cookbook, the patterns chapter, and the gotchas appendix into that structure without dropping a single recipe. The projects keep their code unchanged; they lose 20–35% of their prose, which moves into the concept chapters that should have taught it first. Every one of those 236 examples is a complete, buildable program — no fragments, no ellipses, no "assume the surrounding contract" — which is the constraint you set and the one that most shapes everything downstream (§2.1). Estimated result: ~508 pages, up from ~380, with the added pages being almost entirely the on-ramp you said was missing (§2.3 shows the arithmetic).

---

## 1. Diagnosis: why the current shape resists the reading style you described

Four measurements, not opinions.

**The substrate was extracted and exiled.** Every conceptual building block a reader needs is in the book somewhere. 104 of the 236 examples in the catalog below already exist as working code, and 38 more are asserted in prose with no code to run. But they are distributed as: recipes in an appendix nobody reaches until after the material is needed; prose patterns in Chapter 8, which arrives *after* the four projects that use those patterns; and inline digressions inside project chapters, where a reader looking for "how do I opt a contract into an ASA" cannot find them.

**Chapter mass is wildly uneven, and the imbalance tracks the inversion.** Current bytes:

| Ch | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | A1 | A2 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| KB | 37.7 | 69.0 | 71.7 | 80.7 | 85.7 | 33.4 | 86.7 | 35.3 | 82.2 | 69.3 | 46.8 | 7.6 |

The three largest chapters (04, 05, 07) are large precisely because they stop mid-project to teach a concept: ch05 pauses for 171 lines to build a TWAP oracle, ch07 pauses for 211 lines on "A Simplified Staking Contract" and 123 more on "The Reward Accumulator Pattern." That is concept material trapped in a project.

**There is no junior version of the whole game.** The reader's first complete, deployable artifact arrives roughly 2,000 lines in. The 6-line `HelloAlgorand` at `01:22–29` is never deployed, never called, and never made to fail. Perkins' framing applies exactly: the book teaches elements before it plays a whole game.

**The engagement devices exist but are not distributed.** Chapter 2's three "check your understanding" prompts all fall before line 904, leaving 660 consecutive lines with zero. `## Before You Continue` appears in 7 of 10 chapters, ranging 3–8 items, phrased as topics rather than testable claims. There are **zero diagrams in the entire book**, against a multimedia effect size of d=1.67 — the single largest unclaimed pedagogical gain available.

One correction to my own earlier framing, which publishing-pro caught: **table numbering is not absent.** The convention already exists (`Table 6-2. Provenance checks used by verify_pool`, caption above, in-text reference on the preceding line) and is correctly applied in ch04, ch06, ch07, and ch10 — 9 of 36 tables are numbered. The job is to finish it, not invent it. Similarly, broken cookbook cross-references number **8, not hundreds**; all eight are enumerated in §7.4.

---

## 2. The design rules

These are the contracts everything downstream obeys. They come from teaching-pro, with technical constraints from algorand-expert and formatting constraints from publishing-pro.

### 2.1 The Granularity Rule and the Completeness Contract

An example earns a numbered slot **if and only if it passes all three tests**:

1. **The Surprise Test.** A competent Python programmer would get it wrong on the first try, or would not think to do it at all. `x = UInt64(1)` fails this. `arc4.Struct` needing `.copy()` passes it.
2. **The Single-Failure Test.** There is exactly one way to misunderstand it. Three failure modes means three examples, not one example with three warnings.
3. **The Naming Test.** It can be named in one sentence containing no "and." If you need an "and," it is two examples.

#### The Completeness Contract

Passing the Granularity Rule earns the slot. This contract governs what goes in it, and it is the constraint that most changes the shape of the book:

> **Every numbered example is a complete, buildable, runnable program.** No fragments. No ellipses. No "assume the surrounding contract." The thing on the page is the thing on disk is the thing CI compiles.

This is a stronger rule than "the code is correct," and it forbids three things the current book does freely: showing a method body without its class, showing a class without its imports, and eliding a section with `# ...`. A reader who copies an example into a file must be able to build it. If they cannot, the example was a fragment wearing an example's costume.

**The cost is real and it is paid in lines.** A method body demonstrating one idea is 3 lines; the smallest complete program containing that method is 11. Measured, not estimated — this compiles under puyapy 5.9.0 targeting AVM v12, and 11 lines is the floor:

```python
from algopy import ARC4Contract, UInt64
from algopy.arc4 import abimethod


class Counter(ARC4Contract):
    count: UInt64

    @abimethod
    def increment(self) -> UInt64:
        self.count += UInt64(1)
        return self.count
```

Four more probes were built and compiled to find the real ceiling: a creator-only guard (11 lines), an inner payment with `fee=UInt64(0)` (13), a `BoxMap` guestbook with write and read (15), and a grouped-payment check with group-size validation (13). **A realistic complete example is 11–15 lines.** That is the number the budgets in §2.3 are set from, and it is why the v1 budgets — ≤20 Core and ≤12 Extended — could not survive: the Extended budget was below the floor for a program containing nothing at all.

#### The four execution modes

Every example declares exactly one mode in its front matter, and the mode determines what CI does with it:

| Mode | What the example is | How it is verified |
|---|---|---|
| `unit` | A contract plus a test that exercises it | `pytest` under `algopy_testing_context()` |
| `localnet` | A contract plus a deploy-and-call script | Deployed to LocalNet, assertions on the result |
| `compile` | A contract that demonstrates a construct with no interesting runtime | `puyapy` exits 0 |
| `compile-fail` | **The compiler error is the demonstration** | `puyapy` exits non-zero *and* stderr matches a declared string |

`compile-fail` is the mode that pays for itself. The missing-`.copy()` mistake was on the v1 danger list and was demoted in §6 for being a compile error rather than an exploit — but a compile error the reader has watched happen, with the exact message they will later see at 11pm, is worth more than a warning box. Measured: a 12-line complete program reproduces it, and the message is stable enough to assert on:

```
error: mutable reference to ARC-4-encoded value must be copied using
       .copy() when being assigned to another variable
```

Every `compile-fail` example carries that expected string in its front matter, and §11.3's `--examples` target asserts it. This means the book's error messages cannot silently rot across a compiler upgrade — the mechanism that catches a changed message is the same one that catches a broken contract.

#### Two consequences worth naming now

**A `unit` example is two files but one printed artifact.** The contract is printed; the test lives on disk and only its load-bearing assertion is quoted inline. A complete test for the creator-only guard is 13 measured lines, and printing both would put a "micro" example at 24 lines and re-teach pytest fourteen times. The reader is told once, in Chapter 7, that every example ships with its test and where to find them.

**`examples/` is a package, not a folder of loose files.** Compiling a bare `.py` outside a package root emits `warning: could not determine algopy version`, and the version pin is exactly the thing the book is asserting. The tree gets a `pyproject.toml` pinning the toolchain baseline, which §12 Phase 0 stands up before any example is written.

### 2.2 The micro-example anatomy — six slots, fixed order

```
1. The question         "How do I stop anyone but the creator from calling this?"
2. The code             a complete program, 11–35 lines, one concept
3. The load-bearing line "The `Txn.sender == Global.creator_address` check is the whole
                          example; without it every other line is decoration."
4. Why you'd want this   one or two sentences of motivation
5. The wrong variant     the plausible mistake, shown and named
6. Predict               "What happens if the caller is the app account itself?"
```

Slots **1–3 are mandatory on every example.** Slots 4–6 are conditional — uniform maximal scaffolding is the redundancy effect (d=0.86 *against*), and this audience is expertise-reversal-prone. The rule is: **maximally scaffold the AVM, maximally unscaffold the Python.**

**Slot 5 is mandatory on every example that appears on the danger list (§6).** An example may be incomplete; it may never be exploitable.

Slot 1 doubles as the index key. Every example also carries a `finder:` line — a task-phrased restatement ("opt my contract into an asset so it can hold it") that generates Appendix D.

### 2.3 Two tiers, to control page count

236 examples at full anatomy is a 700–900 page book. Tiering keeps the coverage and controls the mass:

| Tier | Slots | Budget | Count |
|---|---|---|---|
| **Core** | 1–3 mandatory, 4–6 as warranted; slot 5 mandatory if on the danger list | ≤200 words, ≤35 printed lines | 157 |
| **Extended** | 1–3 only | ≤60 words, ≤20 printed lines | 79 |

Extended examples are not second-class; they are the ones where the code *is* the explanation. Every example on the danger list, every threshold concept, every example named in a project's Handoff table, and the first example of every cluster is Core.

**The line budgets are set by the Completeness Contract, not by taste.** §2.1 measured the floor at 11 lines and a realistic complete example at 11–15. Extended at ≤20 leaves five lines of headroom over the measured typical case, which is enough for a second method or a small struct and not enough for a second idea — the budget does the Single-Failure Test's enforcement work. Core at ≤35 is deliberately loose against the same measurement, because the examples that need it are the ones carrying slot 5, and a wrong variant shown next to the right one is legitimately two programs' worth of lines.

**One risk this creates, and where it gets measured.** Some examples now on the Extended list will not fit in 20 complete lines — the ones whose idea only exists in the presence of a struct definition, or that need two methods to show a contrast. Each of those has exactly two legal outcomes: **merge** into an adjacent example that already pays the setup cost, or **promote** to Core and accept the page. Neither is a silent overrun. §12's Phase 4 measures how many examples take this path; if it is more than about fifteen, the 157/79 split is wrong and gets re-cut rather than argued about.

**Two hard caps.** No chapter carries more than **26 examples** (the load Chapter 4 carries; §14.1 records why the cap exists and §12's rebalancing pass enforces it), and no cluster carries more than 6. A chapter that exceeds either after drafting is split or demoted, never simply allowed to run long.

Page arithmetic, which §0's estimate resolves to:

| Component | Arithmetic | Pages |
|---|---|---|
| Core examples | 157 × ~0.65pp | ~102 |
| Extended examples | 79 × ~0.35pp | ~28 |
| Concept-chapter apparatus | 14 ch × ~7pp (Problem, capabilities, figure, Mini-Build, gotchas, retrieval, exercises, handoff) | ~98 |
| Project chapters | ~311pp today × 0.72 (the midpoint of the 20–35% prose cut) | ~225 |
| Appendices, front and back matter | A–D plus What's Next, Glossary, Bibliography | ~55 |
| | **Total** | **~508** |

The per-example page figures rose from ~0.55/~0.25 to ~0.65/~0.35 when the Completeness Contract landed: the imports, the class line, and the blank lines that a fragment omits are real ink, and at 236 examples they total roughly 24 pages. That is the price of the contract, stated plainly. It buys a book in which no reader ever types an example and gets a `NameError`.

The ~380-page starting point and the ~508-page result differ almost entirely in the concept-chapter rows: ~228 pages of on-ramp that does not exist today, against ~100 pages recovered — ~86 from the project-prose cut and ~14 from the three deleted files.

### 2.4 The concept-chapter shape

```markdown
# Chapter N. <Need, phrased as a capability>

## The Problem                  ½ page, ONE named concrete failure
## What You'll Be Able To Do    4–7 verb-first capabilities
[FIGURE: anchor diagram]        BEFORE any code — pre-training, d=0.46
## The Mini-Build, Broken       the finished artifact, shown running and then failing
## <Cluster 1..5>               4–6 examples each; each cluster fixes or explains
                                one part of the broken artifact
## The Mini-Build, Fixed        ≤15 lines of diff, NOT a re-listing
## What Bites People Here       3–6 gotchas, marked `::: {.gotcha}` → generates Appendix C
## Retrieval                    6–10 one-liners, 40% drawn from EARLIER chapters
## Exercises                    5, one per rung: Trace → Parsons → Debug → Compare → Extend
## Before You Continue          exactly 5 first-person testable claims
## Handoff: What Project N Needs 3-column table: example | where it appears | predict
```

**The Mini-Build is non-negotiable.** teaching-pro's override, and I agree: *"Without the Mini-Build this restructure produces an annotated cookbook, not a book."* Each Mini-Build is the junior version of its Part's project — 30–90 lines of contract, deployable to LocalNet, and designed so the reader can break it.

**It runs twice, and that is the point.** Showing the finished artifact first and *failing* it is Perkins' junior version of the whole game plus productive failure (Kapur, d=0.36): the reader meets the artifact before the elements, watches it break for a reason they cannot yet name, and then spends the chapter acquiring exactly the vocabulary that names it. Each cluster closes by stating which part of the break it has just explained. The second appearance is a **diff, capped at 15 lines** — re-listing the whole contract is the redundancy effect (d=0.86 *against*) and doubles the chapter's code mass for nothing.

This resolves an apparent conflict with §2.6's 50-line code-block cap. The cap is on a **single fenced block**, not on the artifact. A 90-line Mini-Build is presented as two or three fences with prose between them — which is what the reader needs anyway, since an unbroken 90-line fence is the exact defect §2.6 exists to prevent.

**`## Run It First!` stays a project-chapter device.** A concept chapter has no single artifact to run first. In project chapters it gets a hard contract (§8.3): ≤60 lines, one paragraph, one bash fence, a numbered output-checkpoint table, one pointer to the project directory. It is currently 138–433 lines per chapter, ~1,500 lines book-wide, with no defined contract at all; in ch06 it is 45% of the chapter. This is the single largest chapter-balance lever in the book and nobody had noticed it.

### 2.5 The project-chapter shape (minimal change)

```markdown
# Chapter N. Project: <Name>

## What You're Building
## What You Need First          NEW — {{ex:}} prerequisites, with predict prompts
## Run It First                 ≤60 lines, contracted
## <existing sections, unchanged code>
## <re-teachings converted to back-references>
## Exercises                    NEW — 4–6, laddered Debug → Compare → Extend → Create,
                                at least 2 at Bloom's Evaluate or Create
## Before You Continue          NEW — exactly 5 first-person testable claims
```

**Project code does not change.** What changes is prose: material that teaches a mechanic for the first time becomes a back-reference — *"we built `mul_div` in {{ex:mul-div-subroutine}}; here is where it earns its keep"* — and material that is a concept wearing a project costume moves out (§8).

**Two ladders, not one.** §2.6's five rungs are the *concept*-chapter ladder, and its lowest two rungs are wrong for a project chapter: a reader who has just assembled a 400-line AMM does not need a Trace exercise, and asking for one is textbook expertise reversal. Project chapters therefore run a shifted four-rung ladder — **Debug → Compare → Extend → Create** — which starts one rung above where the concept chapters end and terminates at Create, the only place in the book where a reader is asked to design rather than modify. This is also what makes the Chapter 22 capstone reachable rather than a cliff.

### 2.6 House rules the build can check

- No more than ~120 consecutive lines without a prompt, table, figure, callout, or exercise.
- Any single fenced code block capped at **50 lines**. (ch04 currently has 524 lines in two blocks — ~33% of the chapter.) This caps the *fence*, not the artifact: a longer Mini-Build or project listing is split across fences with prose between them (§2.4).
- Code lines capped at 85 characters, *enforced* (today `fvextra`'s `breaklines` silently wraps, so the rule is invisible) — with the per-fence opt-out and the `text`/`json`/`teal` exemption defined in §11.3, since Falcon keys, pairing-point literals, and ARC-56 JSON have no legal wrap point.
- **Concept** chapters use exactly five exercises, one per rung: **Trace → Parsons → Debug → Compare → Extend.** Rung 1 (Trace) is non-negotiable in every concept chapter. **Project** chapters use four rungs, **Debug → Compare → Extend → Create**, 4–6 exercises, at least two at Evaluate or Create (§2.5). Today there are four inconsistent schemes; ch03 has 5 exercises and no trace rung while ch04 has 9 with a `**(Trace)**` opener — a measurable scaffolding inversion, since ch04 is the *later* chapter.
- `## Before You Continue` closes **every** chapter of both kinds, as exactly **5 first-person testable claims** ("I can explain why a `BoxMap` key prefix changes the MBR"), not 3–8 topic names. In concept chapters it sits immediately before the Handoff table; in project chapters it is the last section.
---

## 3. The fourteen needs

The organizing question is not "what is this AVM feature?" but "what does a decentralized app need to do?" Each need is phrased as a builder's question. The `X` group is cross-cutting material that attaches to whichever need earns it.

| # | Need | Builder's question | Examples |
|---|---|---|---|
| N0 | Speaking the AVM's language | "What are the types, and where do they bite?" | 24 |
| N1 | Being callable | "How does the outside world reach my code?" | 16 |
| N2 | Remembering things | "Where do I put data?" | 26 |
| N3 | Moving value | "How does my contract hold and send money?" | 19 |
| N4 | Proving who's calling | "How do I know this caller is allowed?" | 12 |
| N5 | Composing with other contracts | "How do I call, read, and deploy other apps?" | 14 |
| N6 | Paying for it | "Who pays for storage, fees, and compute?" | 22 |
| N7 | Reacting to time | "How do I express deadlines and accrual?" | 9 |
| N8 | Failing safely | "How do I fail loudly, early, and completely?" | 12 |
| N9 | Math that doesn't lie | "How do I do arithmetic with no floats and hard overflow?" | 15 |
| N10 | Talking to the outside world | "How do clients, indexers, and simulators see my app?" | 18 |
| N11 | Upgrading and retiring | "What happens after v1?" | 11 |
| N12 | Signing without a contract | "What can a Logic Signature do that an app can't?" | 16 |
| N13 | Cryptography | "What can the AVM prove?" | 13 |
| X | Cross-cutting | scratch, gload, incentives, testing, debugging | 9 |
|  | **Total** | | **236** |

### 3.1 Four ordering errors, and the fixes

**Error 1 — the first project is separated from the need it is mostly made of.** A token vesting contract's terminal act is an inner asset transfer. Every mechanic for that lives in N3: the application account, the inner payment, `fee=UInt64(0)`, opting the contract into an ASA, sending an ASA, the opt-in gate. An earlier draft of this plan put N3 *after* the vesting project — which is the exact defect the restructure exists to remove, at four times the volume of the next-worst instance. **Fix: N3 moves in front of the vesting project, as Chapter 6.**

**Error 2 — time and math were also placed late.** Both teaching-pro and publishing-pro independently produced a linear order that put N7 and N9 after the first project. Same reason it is wrong: a vesting contract is time arithmetic plus `mul_div`. `N9-03` (`op.mulw`), `N9-06` (a reusable `mul_div` subroutine) and `N7-05` (linear vesting between two rounds) are its load-bearing mechanics. (`N7-04`, elapsed-time accrual, is *not* among them despite sounding like it — it is the TWAP primitive and belongs with the pricing math in Chapter 12.) **Fix: N9 and N7 become Chapter 5, immediately before Moving Value and two chapters before the vesting project.** The AMM-specific half of N9 — fixed-point scaling, round-toward-the-pool, `bsqrt`, basis points, the first-depositor attack — splits out into Chapter 12, immediately before the AMM (§4.1).

**Error 3 — N10 cannot sit entirely at the end.** Compile-to-ARC-56 (`N10-01`), typed clients (`N10-03`) and `AlgorandClient` setup (`N10-04`) are needed from Chapter 1 onward — you cannot even run the Chapter 1 Mini-Build without them. Simulate (`N10-15/16/17`) is needed by Chapter 7, which is where failure and inspection are taught. Only events, indexer history, and observability belong late. **Fix: N10 is split across Chapters 1, 2, 3, 7, 9, and 17, with only `N10-09..14` deferred to Chapter 21.**

**Error 4 — N2 does not fit one chapter, by teaching-pro's own Naming Test.** Their need question for N2 was *"Where do I put data, and what if it grows?"* That contains an "and." By their own rule it is two needs: fixed-shape state (global/local, schema fixed at create) and growable state (boxes, MBR arithmetic, sizing). **Fix: N2 splits into Chapters 3 and 4.**

### 3.2 The resulting reading order

```
N0 → N1 → N2a → N2b → N9a+N7 → N3 → N8 → [PROJECT: vesting]
   → N4 → N6 → [PROJECT: NFT vesting]
   → N9b → [PROJECT: AMM] → N5 → [PROJECT: factory] → [PROJECT: farming]
   → N12 → [PROJECT: limit order book]
   → N13 → [PROJECT: ZK voting]
   → N10b+N11 → [CAPSTONE]
```

---

## 4. The new table of contents

Rhythm, reading `C` = concept, `P` = project:

```
Part I    C C C C C C C P
Part II   C C P
Part III  C P C P P
Part IV   C P C P
Part V    C ★
```

Every project is now preceded by a concept chapter, which is the reading experience you described. There is exactly one exception — Chapter 16, the farm — and §4.3 explains why it is deliberate.

| # | Kind | Title | Ex | Mini-Build / Source |
|---|---|---|---|---|
| | | **PART I — FOUNDATIONS** | | |
| 1 | C | The Algorand Mental Model | 8 | *A Greeter You Can Break* |
| 2 | C | Contracts That Exist and Respond | 19 | *A Counter With an API* |
| 3 | C | Remembering Things: Global and Local State | 20 | *A Registry of Members* |
| 4 | C | Data That Grows: Box Storage | 26 | *A Guestbook That Grows* |
| 5 | C | Numbers and Time You Can Trust | 18 | *An Accrual Meter* |
| 6 | C | Moving Value: Assets, Payments, and Groups | 22 | *A Tip Jar* |
| 7 | C | Proving It Works: Tests, Simulation, and Failure | 13 | *A Vesting Contract That Fails* |
| 8 | **P** | **Project: A Token Vesting Contract** | — | was ch02 + ch03 |
| | | **PART II — VALUE IN MOTION** | | |
| 9 | C | Proving Who's Calling: Authorization | 15 | *Pay-to-Post* |
| 10 | C | Paying For It: MBR, Fees, Resources, and Budget | 19 | *A Fee Splitter That Never Loses a Microalgo* |
| 11 | **P** | **Project: Transferable Vesting with NFTs** | — | was ch04 |
| | | **PART III — AUTOMATED MARKET MAKING** | | |
| 12 | C | Numbers That Price Things | 11 | *A Two-Sided Price Quote* |
| 13 | **P** | **Project: A Constant Product AMM** | — | was ch05 |
| 14 | C | Contracts That Talk to Contracts | 15 | *A Two-Contract Handshake* |
| 15 | **P** | **Project: AMM Factory and Pool Provenance** | — | was ch06 |
| 16 | **P** | **Project: Yield Farming with Staking Rewards** | — | was ch07 |
| | | **PART IV — THE SECOND EXECUTION MODEL** | | |
| 17 | C | Signing Without a Contract: Logic Signatures | 18 | *A One-Shot Withdrawal LogicSig* |
| 18 | **P** | **Project: A Delegated Limit Order Book** | — | was ch09 |
| 19 | C | Cryptography on the AVM | 15 | *A Commitment You Can Open* |
| 20 | **P** | **Project: Private Governance Voting with ZK Proofs** | — | was ch10 |
| | | **PART V — SHIPPING** | | |
| 21 | C | Shipping and Surviving: Events, Upgrades, and Retirement | 17 | *Ship the Guestbook to TestNet* |
| 22 | ★ | Capstone: Build Something Nobody Told You To Build | — | new |

**Appendices:** A — Setting Up Your Environment (ch01's 242-line setup section, the fastest-dating content in the book) · B — AVM Limits, Protocol Constants, and the Consensus Surface (promoted from the cookbook tail, expanded with ch10's crypto opcode costs and box I/O constants, plus a two-page survey of the consensus-layer surface the book never builds on — incentives, proposer payouts, key registration, heartbeats, state proofs — and a one-page tear-out limits card as the PDF's final page) · C — Gotchas by Topic (**generated**) · D — The Example Finder (**generated**, indexes all 236) · then What's Next, Glossary, Bibliography.

**Deleted:** `A1-cookbook.md`, `08-common-patterns-and-idioms.md`, `A2-gotchas.md`. Every byte of all three has a destination (§7).

### 4.1 Why the math splits across Chapter 5 and Chapter 12

Chapter 5 carries the arithmetic the *vesting* project needs — no floats, overflow panics, `mulw`, `divw`, `divmodw`, `mul_div`, and the two guards (`N8-07` division by zero, `N8-08` subtraction underflow) that every one of those divisions requires. Putting the guards anywhere later means the reader writes unguarded division for a full chapter.

Chapter 12 carries the arithmetic the *AMM* needs — fixed-point scaling, round-toward-the-pool, `bsqrt`, basis points, canonical asset-pair ordering, dust and the last withdrawer, the first-depositor donation attack, impermanent loss, and the TWAP accrual primitive. An earlier draft kept all of N9 in Chapter 5, seven chapters upstream of the AMM. That is a long way to carry pricing math you have no use for yet, and it left the most math-dense project in the book as the only project with no concept chapter in front of it.

The TWAP move is the single best structural gain in the plan. The TWAP oracle is currently 171 lines stranded mid-project in ch05, and it is time-weighted accumulation — `N7-04` wearing a costume. publishing-pro flagged that the book teaches oracle *production* in ch05 and oracle *consumption* in ch07, 33KB apart. Chapter 12 precedes both, so both back-reference one source.

### 4.2 Why Part I runs seven concept chapters before the first project — and the alternative I rejected

Seven concept chapters, ~126 examples, roughly 118 pages before Chapter 8's vesting project. That is a long on-ramp and it is the plan's main risk. Three things mitigate it: Chapter 1 is deliberately tiny (8 examples), every one of the seven ends in a deployable Mini-Build, and **Chapter 7's Mini-Build is the simplified vesting contract that currently opens ch02** — complete with the payout inner transaction it needs to be a real vesting contract, which it only is because Moving Value now precedes it. The reader arrives at Chapter 8 having already deployed and broken a junior version of the thing.

Two alternatives were considered and rejected. Moving the vesting project earlier, to right after Chapter 4, is worse: a Chapter-4 reader has no arithmetic, no time, no inner transactions, and no authorization, so the project would have to re-teach four needs instead of one. And keeping Part I at six chapters by leaving N3 after the project — the earlier draft — fails for the reason in §3.1.

If the on-ramp proves too long in the Chapter 3 pilot (§12, Phase 4), the correct remedy is **demotion, not reordering**: move more Chapter 2, 3, and 4 examples from Core to Extended. Chapters 2 and 4 are already close to half Extended, and that is deliberate — it is where the tier boundary is doing the most work.

### 4.3 Why Chapters 15 and 16 are adjacent projects

The factory, the pool, and the farm are one continuous protocol, and Part III is deliberately project-dense because splitting them with a concept chapter would break the only extended composition narrative in the book. Chapter 14 sits between the AMM and the factory because cross-contract calls are exactly what the factory introduces and what the farm's reward reads depend on. Chapter 14 therefore carries **two** Handoff tables, one to Chapter 15 and one to Chapter 16 — the mechanism is many-to-many precisely so that a project never has to be adjacent to its concept chapter to be fed by it.

### 4.4 Signalling concept vs. project — three reinforcing devices, no icons

publishing-pro's recommendation, adopted:

1. **Title convention** — `Project: <Name>`. Survives the mdbook sidebar, the PDF TOC, PDF bookmarks, running heads, full-text search, and a phone screen.
2. **Filename convention** — `NN-c-slug.md` / `NN-p-slug.md`. Drives `build.py` and CSS; nothing gets renamed twice.
3. **Chapter-opener banner** — a typographic block, distinct fill in HTML, distinct rule in print.

Deliberately *not*: icons (they die in B&W and in mdbook's plain-text sidebar) and part-level segregation of all concepts from all projects (it destroys the rhythm, which is the whole point).
---

## 5. The catalog: 236 micro-examples

Columns: **Ex** = stable slug (`D-` prefix dropped for readability; the source tag is `{#ex-...}`). **Ch** = destination chapter. **T** = tier (C = Core, E = Extended). **Src** = `code` the example already exists as working code somewhere in the book and needs re-cutting; `prose` the idea is stated but no runnable code exists; `new` net-new. **!** marks the danger list (§6) — slot 5, the wrong variant, is mandatory. **T!** marks a threshold concept, each of which must also get a diagram.


### N0 — Speaking the AVM's language  (24 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N0-01 | The AVM has two stack types, and that is the whole type system | 2 | C | code |  |
| N0-02 | `String` is not `Bytes` | 2 | C | new |  |
| N0-03 | Slicing and indexing raw bytes | 2 | E | new |  |
| N0-04 | `itob` / `btoi` round trip | 2 | C | prose |  |
| N0-05 | `BigUInt` when the number goes past 64 bits | 5 | C | code |  |
| N0-06 | What `BigUInt` costs you | 5 | E | new |  |
| N0-07 | `arc4.UInt64` vs `UInt64`: the boundary | 2 | C | code |  |
| N0-08 | `.as_uint64()`, not `.native` | 2 | C | prose |  |
| N0-09 | `arc4.Bool` and bit-packing | 2 | E | new |  |
| N0-10 | Returning an `arc4.Tuple` | 2 | E | new |  |
| N0-11 | Declaring an `arc4.Struct` | 3 | C | code |  |
| N0-12 | Why an `arc4.Struct` needs `.copy()` | 3 | C | new |  |
| N0-13 | Native `Struct` vs `arc4.Struct` | 3 | C | new |  |
| N0-14 | Frozen and keyword-only native structs | 3 | E | new |  |
| N0-15 | `arc4.StaticArray` | 2 | E | code |  |
| N0-16 | `arc4.DynamicArray` | 2 | E | code |  |
| N0-17 | Native `Array` has value semantics | 4 | E | new |  |
| N0-18 | `ReferenceArray` has reference semantics | 4 | E | new |  |
| N0-19 | `ImmutableArray` and `.freeze()` | 4 | E | new |  |
| N0-20 | `FixedArray` | 4 | E | new |  |
| N0-21 | `arc4.encode` / `arc4.decode`, and what `validate=False` costs you | 2 | C | new |  |
| N0-22 | `zero_bytes()` | 4 | E | new |  |
| N0-23 | `size_of()` | 4 | E | new |  |
| N0-24 | The reference types: `Account`, `Asset`, `Application` | 1 | C | prose |  |

### N1 — Being callable  (16 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N1-01 | The smallest deployable contract | 1 | C | code |  |
| N1-02 | `__init__` sets create-time defaults | 3 | C | code |  |
| N1-03 | `__init__` takes no arguments — use a create method | 3 | C | new |  |
| N1-04 | `create=` allow / require / disallow | 2 | C | new | **!10** |
| N1-05 | Bare methods | 2 | C | code |  |
| N1-06 | `readonly=True` | 2 | E | code |  |
| N1-07 | The six on-completion actions | 2 | C | prose |  |
| N1-08 | An opt-in handler | 3 | C | code |  |
| N1-09 | A close-out handler | 3 | E | prose |  |
| N1-10 | A failing clear-state program still removes the account's local state | 3 | C | prose | **!8** |
| N1-11 | Method selectors are the routing key | 2 | C | prose |  |
| N1-12 | Overloading by ABI name | 2 | E | new |  |
| N1-13 | `default_args` | 2 | E | new |  |
| N1-14 | Resource arguments are ARC-4 values now, not foreign-array indexes | 10 | C | new |  |
| N1-15 | `validate_encoding="unsafe_disabled"` and the `.validate()` call you now owe | 3 | C | new | **!16** |
| N1-16 | What an `ARC4Contract` actually compiles into | 1 | C | code | **T!** |

### N2 — Remembering things  (26 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N2-01 | `GlobalState[T]` | 3 | C | code |  |
| N2-02 | `.get(default=)` | 3 | C | code |  |
| N2-03 | `.maybe()` | 3 | C | code |  |
| N2-04 | `bool()` and `del` | 3 | E | code |  |
| N2-05 | `LocalState[T]` | 3 | C | code |  |
| N2-06 | The schema is fixed at create time, forever | 3 | C | new |  |
| N2-07 | `GlobalMap[K, V]` | 3 | E | new |  |
| N2-08 | `LocalMap[K, V]` | 3 | E | new |  |
| N2-09 | Why storage has tiers at all | 3 | C | prose |  |
| N2-10 | `Box[T]` | 4 | C | code |  |
| N2-11 | `Box.maybe()` and `.get(default=)` | 4 | E | new |  |
| N2-12 | `BoxMap[K, V]` | 4 | C | code |  |
| N2-13 | What a `BoxMap` box is actually named | 4 | C | prose |  |
| N2-14 | `BoxMap.box(key)` | 4 | E | new |  |
| N2-15 | A raw byte box with an explicit size | 4 | C | code |  |
| N2-16 | `Box.replace()` | 4 | C | code |  |
| N2-17 | `Box.extract()` | 4 | C | code |  |
| N2-18 | `Box.length` | 4 | E | code |  |
| N2-19 | `Box.resize()` | 4 | E | new |  |
| N2-20 | `Box.splice()` | 4 | E | new |  |
| N2-21 | Deleting a box | 4 | C | code |  |
| N2-22 | A growable list in one box, and when to key it by index instead | 4 | C | prose |  |
| N2-24 | Composite box keys | 4 | C | code |  |
| N2-25 | Canonical ordering for symmetric keys | 12 | C | code |  |
| N2-26 | Iterating a `BoxMap` is not free | 4 | C | prose | **!17** |
| N2-27 | Global vs box vs client-side merkle root | 19 | E | new |  |

### N3 — Moving value  (19 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N3-01 | The application account | 6 | C | code | **T!** |
| N3-02 | An inner payment | 6 | C | code | **T!** |
| N3-03 | Every inner transaction takes `fee=UInt64(0)` | 6 | C | code | **!1** |
| N3-04 | Require a payment in the same group | 6 | C | code | **!4** |
| N3-05 | Require an asset transfer, and check `xfer_asset` | 6 | C | code | **!5** |
| N3-06 | A contract opts itself into an ASA | 6 | C | code |  |
| N3-07 | Send an ASA | 6 | C | code |  |
| N3-08 | Create an ASA from inside a contract | 6 | C | code |  |
| N3-09 | The four ASA authority roles | 6 | C | prose |  |
| N3-10 | A clawback transfer | 6 | E | code |  |
| N3-11 | Freeze a holding | 6 | E | new |  |
| N3-12 | Permanently renounce a role | 6 | E | new |  |
| N3-13 | The opt-in gate, eager | 6 | C | code |  |
| N3-14 | The opt-in gate, lazy | 6 | E | code |  |
| N3-15 | The opt-in gate, contract-initiated | 6 | E | code |  |
| N3-16 | Never use `balance` as your ledger | 6 | C | code | **!6** |
| N3-17 | ASA close-out to recover MBR | 6 | E | code |  |
| N3-18 | Paying out of the payload | 6 | C | code |  |
| N3-19 | Two asset arguments that are secretly the same asset | 6 | C | new | **!21** |

### N4 — Proving who's calling  (12 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N4-01 | Creator-only | 9 | C | code |  |
| N4-02 | A stored admin | 9 | C | code |  |
| N4-03 | Two-step admin transfer | 9 | C | new |  |
| N4-04 | Role sets with a `GlobalMap` | 9 | E | new |  |
| N4-05 | Owner-of-a-record checks | 9 | C | prose |  |
| N4-06 | `Global.caller_application_id` | 9 | C | new |  |
| N4-07 | `Global.caller_application_address` | 9 | E | new |  |
| N4-08 | Reject inner-call reentry into an admin path | 9 | C | new |  |
| N4-09 | Signature-gated authorization | 9 | E | new |  |
| N4-10 | Bound the group size | 6 | C | code | **!20** |
| N4-11 | Position-relative group introspection | 6 | E | new |  |
| N4-12 | The checks that are NOT your job in a stateful contract | 9 | C | prose | **!15** |

### N5 — Composing with other contracts  (14 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N5-01 | Call another app, typed | 14 | C | code |  |
| N5-02 | Call another app by signature string | 14 | C | code | **!18** |
| N5-03 | `itxn.abi_call` is a *builder*, not an alias for `arc4.abi_call` | 14 | C | prose |  |
| N5-04 | Read another app's global state | 14 | C | code |  |
| N5-05 | Read another app's local state | 14 | E | code |  |
| N5-06 | Cross-contract reads see intra-group writes | 14 | C | new | **T!** |
| N5-07 | Read app parameters | 14 | E | new |  |
| N5-08 | Stage several inner transactions and submit them as a group | 14 | C | new |  |
| N5-09 | `itxn.submit_txns(...)` | 14 | E | new |  |
| N5-10 | Compile another contract at build time | 14 | C | code |  |
| N5-11 | Deploy a child contract | 14 | C | code |  |
| N5-12 | Fund the child before it needs MBR | 14 | C | new |  |
| N5-13 | The inner-transaction depth limit | 14 | E | new |  |
| N5-14 | Opcode budget pools across the app calls in a group; fees pool across the whole group | 14 | C | prose |  |

### N6 — Paying for it  (22 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N6-01 | The account MBR floor | 4 | C | prose | **T!** |
| N6-02 | Box MBR arithmetic | 4 | C | code |  |
| N6-03 | The `BoxMap` prefix trap | 4 | C | code |  |
| N6-04 | State-schema MBR | 10 | E | prose |  |
| N6-05 | Charge the user for the box they create | 10 | C | code |  |
| N6-06 | Refund the MBR to the funder, not the caller | 10 | C | code | **!9** |
| N6-07 | `Global.min_txn_fee` | 10 | E | prose |  |
| N6-08 | Fee pooling, wrong and right | 10 | C | code |  |
| N6-09 | Sponsored fees (the relayer pattern) | 10 | C | code |  |
| N6-10 | Measure your opcode budget | 10 | C | code |  |
| N6-11 | `ensure_budget()` | 10 | C | code |  |
| N6-12 | Choosing an `OpUpFeeSource` | 10 | C | prose | **!7** |
| N6-13 | Client-side op-up padding | 10 | C | code |  |
| N6-14 | `@subroutine(inline=)` | 10 | E | new |  |
| N6-15 | Program size and extra pages | 10 | E | new |  |
| N6-16 | Resource availability, in one paragraph | 10 | C | prose |  |
| N6-17 | Legacy foreign arrays | 10 | E | new |  |
| N6-18 | The unified `txn.Access` list (consensus v41) | 10 | C | prose |  |
| N6-19 | `BytesPerBoxReference` is now 2,048 | 4 | E | new |  |
| N6-20 | Automatic resource population | 4 | E | code |  |
| N6-21 | When auto-population fails | 10 | C | code |  |
| N6-22 | What a loop costs you | 10 | E | new |  |

### N7 — Reacting to time  (9 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N7-01 | Rounds vs wall-clock | 5 | C | prose |  |
| N7-02 | Deadlines with `latest_timestamp` | 5 | C | new |  |
| N7-03 | Never use `Txn.last_valid` as a clock | 5 | C | new | **!14** |
| N7-04 | Elapsed-time accrual (the TWAP primitive) | 12 | C | code |  |
| N7-05 | Linear vesting between two rounds | 5 | C | code |  |
| N7-06 | A cliff before the linear portion | 5 | C | new |  |
| N7-07 | Rate limiting per account | 5 | E | new |  |
| N7-08 | Reading a past block's fields | 5 | E | new |  |
| N7-09 | The block seed is not safe randomness | 5 | C | new | **!13** |

### N8 — Failing safely  (12 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N8-01 | `assert` with a message | 1 | C | code |  |
| N8-02 | Where the assert message actually goes | 7 | C | prose |  |
| N8-03 | `logged_assert()` | 7 | E | prose |  |
| N8-04 | `logged_err()` | 7 | E | new |  |
| N8-05 | `op.err()` | 7 | E | new |  |
| N8-06 | Validate at the boundary | 7 | C | prose |  |
| N8-07 | Guard division by zero | 5 | C | new | **!11** |
| N8-08 | Subtraction underflow is a panic, not a negative | 5 | C | new | **!12** |
| N8-09 | The initialize-once guard | 9 | C | code |  |
| N8-10 | A pause switch | 9 | E | new |  |
| N8-11 | Fail the whole group, not half of it | 6 | C | prose | **T!** |
| N8-12 | There is no reentrancy on Algorand | 7 | C | prose |  |

### N9 — Math that doesn't lie  (15 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N9-01 | There are no floats | 5 | C | prose |  |
| N9-02 | Overflow panics | 5 | C | new |  |
| N9-03 | `op.mulw` | 5 | C | code |  |
| N9-04 | `op.divw` | 5 | E | new |  |
| N9-05 | `op.divmodw` | 5 | E | code |  |
| N9-06 | A reusable `mul_div` subroutine | 5 | C | code |  |
| N9-07 | The `BigUInt` alternative | 12 | E | code |  |
| N9-08 | Fixed-point scaling | 12 | C | code |  |
| N9-09 | Round toward the pool | 12 | C | code |  |
| N9-10 | Dust and the last withdrawer | 12 | C | new |  |
| N9-11 | `op.bsqrt` | 12 | C | prose |  |
| N9-12 | Basis points | 12 | E | new |  |
| N9-13 | The first-depositor donation attack, and the minimum-liquidity lock | 12 | C | new | **!22** |
| N9-14 | Impermanent loss, arithmetically | 12 | E | prose |  |
| N9-15 | Quoting a price client-side without re-implementing the contract | 12 | C | prose |  |

### N10 — Talking to the outside world  (18 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N10-01 | Compile to TEAL and ARC-56 | 1 | C | code |  |
| N10-02 | What is in an ARC-56 app spec | 2 | E | new |  |
| N10-03 | Generate a typed client | 1 | C | code |  |
| N10-04 | `AlgorandClient` and account setup | 1 | C | code |  |
| N10-05 | `AppFactory.deploy()` is idempotent — and when that is wrong | 3 | C | code |  |
| N10-06 | A typed method call | 1 | C | code |  |
| N10-07 | A client-side atomic group | 9 | C | code |  |
| N10-08 | Reading a return value | 7 | E | new |  |
| N10-09 | `op.log()` and the log budget | 21 | C | new |  |
| N10-10 | Declare an ARC-28 event | 21 | C | code |  |
| N10-11 | `arc4.emit()` | 21 | C | code |  |
| N10-12 | Untyped emit | 21 | E | new |  |
| N10-13 | Parse events client-side | 21 | C | code |  |
| N10-14 | Indexer event history | 21 | E | code |  |
| N10-15 | Simulate instead of submit | 7 | C | code |  |
| N10-16 | Simulate with extra opcode budget | 7 | C | new |  |
| N10-17 | Simulate with unnamed resources and an execution trace | 7 | C | new |  |
| N10-18 | Template variables | 17 | C | code |  |

### N11 — Upgrading and retiring  (11 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N11-01 | Immutable by default | 21 | C | code |  |
| N11-02 | An admin-gated update method | 21 | C | prose | **!19** |
| N11-03 | Deleting an app | 21 | C | new |  |
| N11-04 | Sweep before delete | 21 | C | new |  |
| N11-05 | `AppParamsGet.app_version` | 21 | E | new |  |
| N11-06 | `reject_version` on an inner call | 21 | C | new |  |
| N11-07 | `op.GTxn.reject_version` | 21 | E | new |  |
| N11-08 | `avm_version=` targeting | 21 | E | new |  |
| N11-09 | Migration by proxy state read | 21 | C | new |  |
| N11-10 | Migration by user-pull | 21 | E | new |  |
| N11-11 | Schema headroom as a migration strategy | 21 | E | new |  |

### N12 — Signing without a contract  (16 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N12-01 | What a LogicSig is | 17 | C | code | **T!** |
| N12-02 | Contract account vs delegated | 17 | C | code |  |
| N12-03 | The seven mandatory checks | 17 | C | code | **!2** |
| N12-04 | These checks are LogicSig-only | 17 | C | prose |  |
| N12-05 | A safe minimal escrow | 17 | C | code |  |
| N12-06 | A template-parameterised LogicSig | 17 | C | code |  |
| N12-07 | `compile_logicsig()` and `.account` | 17 | E | new |  |
| N12-08 | Binding a LogicSig to an app call | 17 | C | code |  |
| N12-09 | App-id-only binding authorizes every method | 17 | C | prose | **!3** |
| N12-10 | Client: sign and use a delegated LogicSig | 17 | C | code |  |
| N12-11 | Client: fund and spend a contract account | 17 | E | code |  |
| N12-12 | The LogicSig budget is 20,000 per program, and pools to len(group) x 20,000 | 17 | C | code |  |
| N12-13 | Rekeying an account | 17 | C | code |  |
| N12-14 | Rekey to a LogicSig and back | 17 | E | new |  |
| N12-15 | A lease is what makes a LogicSig one-shot | 17 | C | new |  |
| N12-16 | LogicSig arguments are not covered by the signature | 17 | C | new | **!23** |

### N13 — Cryptography  (13 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| N13-01 | Hash functions and what they cost | 19 | C | code |  |
| N13-02 | A commitment | 19 | C | new |  |
| N13-03 | `ed25519verify_bare` | 19 | C | code |  |
| N13-04 | `_bare` vs non-bare: domain separation | 19 | C | new |  |
| N13-05 | `ecdsa_verify` | 19 | E | new |  |
| N13-06 | `ecdsa_pk_recover` | 19 | C | code |  |
| N13-07 | `ecdsa_pk_decompress` | 19 | E | new |  |
| N13-08 | `vrf_verify` and randomness beacons | 19 | C | code |  |
| N13-09 | A merkle inclusion proof | 19 | C | new |  |
| N13-10 | `mimc` | 19 | C | code |  |
| N13-11 | EC point add and scalar mul | 19 | E | code |  |
| N13-12 | A pairing check costs more than one program's budget — where the extra comes from | 19 | C | code |  |
| N13-13 | `falcon_verify` | 19 | E | code |  |

### X — Cross-cutting  (9 examples)

| Ex | Question | Ch | T | Src | |
|---|---|---|---|---|---|
| X-01 | Scratch space | 9 | E | prose |  |
| X-02 | `op.gload_uint64` / `op.gload_bytes` | 9 | E | prose |  |
| X-03 | `op.gaid` | 14 | C | prose |  |
| X-04 | `op.JsonRef` | 19 | E | new |  |
| X-11 | `acct_total_boxes` / `acct_total_box_bytes` | 10 | E | new |  |
| X-12 | `acct_auth_addr` | 17 | C | new |  |
| X-13 | Unit-testing with `algorand-python-testing` | 7 | C | code |  |
| X-14 | Negative testing with simulate | 7 | C | code |  |
| X-15 | Reading a `LogicError` back to a source line | 7 | C | new |  |

**Totals:** 157 Core, 79 Extended, 236 examples. Source: 104 already exist as code, 38 exist as prose only, 94 net-new.


#### Per-chapter check

| Ch | Needs drawn on | Core | Ext | Total |
|---|---|---|---|---|
| 1 | N0, N1, N10, N8 | 8 | 0 | 8 |
| 2 | N0, N1, N10 | 10 | 9 | 19 |
| 3 | N0, N1, N10, N2 | 15 | 5 | 20 |
| 4 | N0, N2, N6 | 13 | 13 | 26 |
| 5 | N0, N7, N8, N9 | 13 | 5 | 18 |
| 6 | N3, N4, N8 | 15 | 7 | 22 |
| 7 | N10, N8, X | 9 | 4 | 13 |
| 9 | N10, N4, N8, X | 9 | 6 | 15 |
| 10 | N1, N6, X | 12 | 7 | 19 |
| 12 | N2, N7, N9 | 8 | 3 | 11 |
| 14 | N5, X | 11 | 4 | 15 |
| 17 | N10, N12, X | 15 | 3 | 18 |
| 19 | N13, N2, X | 9 | 6 | 15 |
| 21 | N10, N11 | 10 | 7 | 17 |
| | | **157** | **79** | **236** |
---

## 6. The danger list — twenty-three examples that may never be shown wrong

algorand-expert's governing rule for the whole restructure: **an example may be incomplete, but it may never be exploitable.** A micro-example is, by design, stripped down. The risk of 236 stripped-down examples is that a reader copies one into production. These twenty-three are the ones where stripping down produces a live vulnerability, so each carries a mandatory slot 5 (the wrong variant, shown and named) and each is Core.

| ! | The mistake | Owned by | Ch |
|---|---|---|---|
| 1 | Any inner transaction without `fee=UInt64(0)` | N3-03 | 6 |
| 2 | A LogicSig missing any of the seven mandatory checks | N12-03 | 17 |
| 3 | A delegated LogicSig scoped only by app id | N12-09 | 17 |
| 4 | A grouped payment with no receiver check | N3-04 | 6 |
| 5 | A grouped asset transfer with no `xfer_asset` check | N3-05 | 6 |
| 6 | Using `balance` as accounting | N3-16 | 6 |
| 7 | `OpUpFeeSource.AppAccount` unguarded — a drain vector | N6-12 | 10 |
| 8 | Balances held only in local state (clear-state removes it either way) | N1-10 | 3 |
| 9 | Refunding MBR to `Txn.sender` rather than the funder | N6-06 | 10 |
| 10 | `create="allow"` on a mutating method | N1-04 | 2 |
| 11 | Division with no zero guard — a fail-closed DoS | N8-07 | 5 |
| 12 | Subtraction with no underflow guard — a fail-closed DoS | N8-08 | 5 |
| 13 | Block seed used as randomness | N7-09 | 5 |
| 14 | `Txn.last_valid` used as a clock | N7-03 | 5 |
| 15 | **LogicSig checks applied to a stateful contract** | N4-12 | 9 |
| 16 | `validate_encoding="unsafe_disabled"` on untrusted input, with no `.validate()` call | N1-15 | 3 |
| 17 | Unbounded loops | N2-26 | 4 |
| 18 | A cross-contract call to an app id taken from an argument | N5-02 | 14 |
| 19 | `UpdateApplication` / `DeleteApplication` reachable by anyone | N11-02 | 21 |
| 20 | A method that reads a group position without validating the group's size | N4-10 | 6 |
| 21 | Two asset arguments that are secretly the same asset | N3-19 | 6 |
| 22 | The first-depositor donation attack on an empty pool | N9-13 | 12 |
| 23 | Trusting LogicSig arguments, which the signature does not cover | N12-16 | 17 |

Four notes on the list's composition, all of which changed it from the twenty-item version:

**Items 11 and 12 are denial of service, not theft, and the prose must say so.** An unguarded division by zero does not let an attacker extract value; it panics, the transaction fails, and the group is rejected. The AVM fails closed. The danger is that a contract holding funds becomes *permanently* uncallable on some input path — a Chapter 5 reader who has just learned that `//` panics needs to hear the consequence stated as "your users' money is stuck," not "your users' money is gone." Miscategorizing these as extraction vectors is the kind of error that teaches readers to distrust the rest of the list.

**Two items were demoted off the list to plain `.gotcha` entries.** A missing `.copy()` on an `arc4.Struct` (was item 10) is a puyapy **compile error** under algorand-python 3.x value semantics, not a runtime vulnerability — the compiler refuses the program. Op-up padding without a distinct `note` (was item 11) is rejected at submission as a duplicate transaction ID; nothing reaches the AVM. Both are real and both stay in the book; neither belongs on a list whose entire authority rests on every item being exploitable.

**Five items were added.** Unauthorized `UpdateApplication`/`DeleteApplication` (19) is the single highest-impact omission in the original list — an app with no update guard can be replaced wholesale with an attacker's bytecode, which subsumes every other item here. Group-size validation (20) is what makes items 4 and 5 complete: checking `gtxn[0]` is worthless if the attacker can append a transaction and shift the index. Two-assets-that-are-one (21) is the ~\$3M Tinyman V1 exploit, reduced to its six-line core. The first-depositor donation attack (22) makes the AMM's minimum-liquidity lock legible instead of arbitrary. And LogicSig arguments (23) closes the gap that makes item 2's seven checks *sufficient* rather than merely necessary — the signature covers the program, never the arguments.

**Item 15 is the inverse failure, and the one the book is currently *exposed to*.** `A1-cookbook.md` §11.3 presents close/rekey checking as prose without saying it is LogicSig-only, which invites a reader to sprinkle `close_remainder_to` assertions across a stateful contract, restricting their users' wallets for zero security benefit. The fix has two halves: §11.3 becomes a runnable LogicSig example (N12-03) *and* an explicit counter-example (N4-12).

The seven-check LogicSig block should be published **once**, as a named subroutine, which every later LogicSig example calls on line one. Repeating it inline seven times guarantees one copy drifts.

### 6.1 The seventeen things that cannot be made small

Fourteen of these stay in project chapters, and the concept chapters should not attempt them: constant-product swap · LP add/remove · TWAP oracle *as a complete contract* (the primitive is N7-04 and does move out) · reward-per-token accounting · a full vesting schedule · a limit-order book · a keeper bot · a ZK verifier · factory plus provenance · multi-hop routing · complete ARC-3/19/69 metadata · a complete upgrade-and-migration · algo-less intermediary topology · a production test harness.

Three of the seventeen do **not** belong in a project chapter, and the earlier draft was wrong to send them there. End-to-end resource-limit debugging is a skill, not an artifact; it is Chapter 7's subject and its Mini-Build, not a project's. Heartbeat and participation operations, and state-proof verification, are consensus-layer surface the book never builds on — no project uses them, and inventing a project that does would be worse than not covering them. The latter two become **survey-only material in Appendix B** (the consensus surface), which is exactly what Appendix B was expanded to hold (§4); resource-limit debugging goes to Chapter 7 instead. What the three share is only that no project chapter should carry them.

This also resolves a three-way contradiction the verification pass caught: the reward accumulator appeared in §6.1 as un-shrinkable, in §7.2 as a pattern to dissolve, and in §8.1 as material moving *out* of the farming project. **It stays where it is** — in Chapter 16's project prose. Reward-per-token accounting is 123 lines of interlocking invariants whose correctness argument is the whole point; cut into micro-examples it becomes six fragments none of which is the idea. Diagram 10 (two stakers on a timeline) carries the conceptual load instead.

---

## 7. Dissolution: where every existing byte goes

### 7.1 `A1-cookbook.md` — all 65 recipes, no survivors, no losses

The cookbook holds **65 recipes across 17 topic sections** (the Preface undercounts it as "50+"). Verdicts: **CUT 4** (2.1, 3.4, 12.3, 15.4), **MERGE 5** (7.5→7.4, 11.4→9.3, 12.2→12.1, 15.2 demoted into 15.1, 9.2 re-aimed and folded), **SPLIT 14 recipes into 38 examples** (they fail the Single-Failure Test as written). Net: 65 − 4 − 5 = **56 surviving recipes**, of which 14 split into 38, yielding 42 + 38 = **80 micro-examples** drawn from the cookbook alone — a third of the catalog.

(The earlier draft's arithmetic double-counted 2.1 in both the CUT and MERGE columns and included ch08's pattern 1E, which is a §7.2 item and not a cookbook recipe at all.)

**The Completeness Contract raises the bar on every SPLIT in this table.** Under a fragment regime, splitting one recipe into four examples costs four code blocks of three lines each. Under §2.1 it costs four complete programs — four sets of imports, four class definitions, four entries in `examples/`, four CI compilations. The Single-Failure Test still decides whether a split is *correct*, and none of the 14 splits above were made for any other reason. But where a split was marginal, the tie now breaks toward keeping one example and letting it carry a second method, because a 22-line program showing two related failures costs the reader less than two 13-line programs showing one each. The 38 figure is therefore a ceiling to be re-checked during Phase 5, not a target to hit.

| Cookbook § | Recipes | Destination chapter |
|---|---|---|
| 1 Contract basics | 1.1–1.4 | 2 |
| 2 ABI routing | 2.2–2.4 (2.1 cut) | 2 |
| 3 Types and arithmetic | 3.1–3.3 (3.4 cut) | 5 |
| 4 Global state | 4.1–4.3 | 3 |
| 5 Local state | 5.1–5.2 | 3 |
| 6 Boxes | 6.1–6.5 | 4 |
| 7 ASAs | 7.1–7.4 (7.5 merged into 7.4) | 6 |
| 8 Inner transactions | 8.1, 8.2, 8.4 | 6 |
| 8.3 app-creates-app | 8.3 | 14 |
| 9 Atomic groups | 9.1, 9.3 (+11.4 merged in; 9.2 re-aimed) | 6 |
| 10 LogicSigs | 10.1–10.5 | 17 |
| 11 Authorization | 11.1–11.2 | 9 |
| 11.3 close/rekey | 11.3 | 17 **and** 9 (as counter-example) |
| 12 Subroutines | 12.1 (+12.2 merged; 12.3 cut) | 10 |
| 13 ARC-4 boundary | 13.1–13.3 | 2, 3 |
| 14 Cryptography | 14.1–14.5 | 19 |
| 15 Budget | 15.1 (+15.2 demoted in; 15.4 cut), 15.3 | 10 |
| 16 Compile and deploy | 16.1–16.2 | 2 |
| 16.3–16.5 | 16.3–16.5 | 7, 21 |
| 17.1 ASA close-out | 17.1 | 6 |
| 17.2 rekeying | 17.2 | 17 |
| *Quick Reference: AVM Limits* | — | **Appendix B**, expanded |

**Highest-priority technical fixes to make during the move** (section numbers here are the *cookbook's*, not this plan's): recipe 13.2 is missing a `.copy()`; 6.5 leads with manual box references when algokit-utils 4.x auto-populates them; 15.1's `OpUpFeeSource` choice is a drain vector as written; 8.2 conflates `arc4.abi_call` and `itxn.abi_call`, which are genuinely different APIs and the book never says so.

**Promote out of the appendix and give prominent placement:** 8.4 fee pooling, 10.3 the group-bound LogicSig (it must appear *before* 10.1's unbound form), 13.1 the ARC-4 boundary, 16.3 typed clients.

**Why not "a recipes section at the end of each chapter"?** Because reference mode and narrative mode want *different artifacts, not different chapters.* Narrative is schema construction — sequential, high intrinsic load, needs motivation. Reference is retrieval by cue — random access, near-zero intrinsic load, where prose is noise. A per-chapter recipe section reinstates the same defect at smaller scale and forces ~200 arbitrary "is this a teaching example or a recipe?" adjudications. Replaced instead by two **generated** artifacts: Appendix D (The Example Finder) and Appendix B (AVM Limits).

### 7.2 `08-common-patterns-and-idioms.md` — 12 prose patterns → 22 micro-examples

| Pattern | Becomes | Ch |
|---|---|---|
| 1 Fee subsidization | N6-08, N6-09 (variant 1E cut) | 10 |
| 2 Fund-then-call | N3-04, N6-05 | 6, 10 |
| 3 Escrow contract account | N3-01, N12-05 | 6, 17 |
| 4 MBR funding as part of user operations | N6-02, N6-05 | 4, 10 |
| 5 MBR refund on cleanup | N6-06 — **with a security fix: refund the *funder*, not `Txn.sender`** | 10 |
| 6 Canonical asset ordering | N2-25 | 12 |
| 7 Opt-in gate | N3-13, N3-14, N3-15 | 6 |
| 8 Subroutine extraction | N6-14 | 10 |
| 9 Opcode budget management | N6-10, N6-11, N6-12, N6-13 | 10 |
| 10 ARC-28 events | N10-10, N10-11, N10-13 | 21 |
| 11 Reserve tracking vs balance reading | N3-16 — **promote, this is danger-list item 6** | 6 |
| 12 Client-side quote calculation | N9-15 | 12 |

Two changes from the earlier draft. Canonical asset ordering (pattern 6) moves from the box chapter to Chapter 12, where it is actually load-bearing — it is a *pricing* invariant, and teaching it eight chapters before the pool that depends on it was ordering it by mechanism rather than by need. And client-side quote calculation (pattern 12) is no longer a homeless "project sidebar"; it is now catalog entry N9-15 in Chapter 12, alongside the on-chain math it must agree with, which is the entire pedagogical point of the pairing.

Plus three decision tables that survive as tables: storage tier selection, who-pays, and LogicSig-vs-contract (the last collapses ch09's and ch10's two near-duplicate matrices into one `{{tbl:logicsig-vs-contract}}`).

### 7.3 `A2-gotchas.md` — distributed *and* kept, by generating it

Each gotcha is written **once**, in the concept-chapter `## What Bites People Here` section that earns it, marked up as:

```markdown
::: {.gotcha #box-prefix-mbr topic="Box storage"}
The `BoxMap` key prefix counts toward the box name length, and therefore toward MBR.
:::
```

`build.py` then generates **Appendix C: Gotchas by Topic**, grouped by `topic=`, each entry back-linked (`→ Ch 4, Example 4-3`). One source, two placements, zero drift. Topic → owning chapter: global and local state → 3 · box storage → 4 · arithmetic and time → 5 · inner transactions, ASAs, groups → 6 · testing and simulation → 7 · authorization → 9 · resource references, MBR, budget → 4, 10 · pricing math → 12 · cross-contract calls → 14 · LogicSigs → 17 · cryptography → 19 · compilation, tooling, and shipping → 2, 7, 21 · security → distributed to the owning chapters.

### 7.4 The eight broken cookbook cross-references

Each becomes an `{{ex:}}` reference, which is then immune to renumbering:

1. `03-a-token-vesting-contract.md:636` — "The Cookbook (Recipe 6.5) shows this" → `{{ex:box-io-budget-refs}}`
2. `03:1134` — "See Cookbook recipe 16.3" → `{{ex:generate-typed-client}}`
3. `03:1150` — "Practice with the Cookbook … recipes: 1.2, 3.3, 6.2, 8.1, 11.1" → five `{{ex:}}` refs
4. `04-nfts.md:1556` — "recipes 7.1, 7.5, 6.4, 9.1" → four refs
5. `05-a-constant-product-amm.md:331` — "See Cookbook section 8.3" → `{{ex:app-creates-app}}`
6. `05:1421` — "recipes: 3.2–3.3, 4.3, 7.2, 8.4, 12.1" → five refs
7. `07-yield-farming.md:1666` — "recipes: 4.3, 6.2, 6.4, 13.2, 8.4" → five refs
8. `F2-preface.md:45, 61` — the cookbook description and the typed-client pointer

Three grep patterns cover every spelling in the repo: `[Cc]ookbook` · `[Rr]ecipe[s]?\s*[:(]?\s*\d+\.\d+` · `[Ss]ection\s+\d+\.\d+`. The three "Practice with the Cookbook" callouts survive, renamed simply "Practice."

---

## 8. What changes inside the seven project chapters

You said the projects should not need to change much. They do not — **no project's contract code changes at all.** Three things change in their prose.

### 8.1 Concept material moves out

| Project | Moves out | To |
|---|---|---|
| Ch 8 (was ch02 + ch03) | the simplified vesting contract that opens ch02 — it becomes Chapter 7's Mini-Build | 7 |
| Ch 13 (was ch05, 85.7KB → ~62KB) | TWAP oracle (171 lines) → the accrual primitive N7-04 and the scaling math; impermanent loss → N9-14 | 5, 12 |
| Ch 16 (was ch07, 86.7KB → ~68KB) | "A Simplified Staking Contract" (211 lines) | 9 |
| Ch 18 (was ch09, 82.2KB) | Part 1 — LogicSig fundamentals (281 lines) | 17 |
| Ch 20 (was ch10, 69.3KB) | Parts 1–3 — crypto fundamentals | 19 |
| Ch 1 (was ch01) | the 242-line environment setup section | Appendix A |

Three rows the earlier draft had, now struck. The **reward accumulator** stays in Chapter 16 (§6.1 explains why). **Client-side quote calculation** is not exiled to the shipping chapter; it is N9-15 in Chapter 12, and Chapter 13 keeps a short sidebar pointing at it. **Impermanent loss** previously had a destination but no container — Chapter 12 now gives it one.

Chapter 15 (was ch06) has ~200 lines duplicated from ch05. **Do not merge the chapters.** Replace the duplication with `{{ex:}}` cross-references plus one sentence: *"the pool behaves exactly as it did in Chapter 13 because it **is** the same contract."* That is pedagogically better than the duplication, not merely shorter.

### 8.2 Re-teachings become back-references

Wherever a project currently introduces a mechanic for the first time, it now says where the reader met it: *"we built `mul_div` in {{ex:mul-div-subroutine}}; this is where it earns its keep."* This is the single change that makes the restructure pay off — otherwise the concept chapters are pure addition and the book just gets longer.

The mechanical test for whether this has been done is §11.3's check 8: a project chapter may not contain a section heading that matches an existing example's display title. If Chapter 13 still has a heading called "Fixed-Point Scaling," it is still teaching, and Chapter 12 already did.

### 8.3 Two new blocks per project chapter

**`## What You Need First`** — the reciprocal of the concept chapter's Handoff table. Three columns: the `{{ex:}}` prerequisite, one line on what it does for this project, and a predict prompt. This block is what makes the concept→project rhythm *functional* rather than merely visual.

**`## Run It First`** — contracted to ≤60 lines: one paragraph of framing, one bash fence, a numbered output-checkpoint table, one pointer to the project directory. Currently these run 138–433 lines with no defined shape; in ch06 the section is 45% of the chapter. Also renamed from `## Run It First!` (the exclamation mark violates the book's own heading rules).

Plus the two closing blocks §2.5 adds to every project chapter: `## Exercises` on the Debug → Compare → Extend → Create ladder, and `## Before You Continue`.

### 8.4 The Handoff mechanism

Every concept chapter ends with:

```markdown
## Handoff: What Chapter 8 Needs

| You built | Where it shows up | Predict |
|---|---|---|
| {{ex:mul-div-subroutine}} | `vesting.py`, `claimable_amount()` | What happens if `elapsed > duration`? |
| {{ex:linear-vesting-window}} | `vesting.py`, the accrual loop | Which direction does this round? |
```

The project chapter's `## What You Need First` block is generated from the union of the Handoff tables pointing at it, so the two can never disagree. `build.py` validates that every Handoff row's `{{ex:}}` slug resolves and that every project chapter is the target of at least one Handoff.

The relation is **many-to-many in both directions**: Chapter 14 carries two Handoff tables (to Chapters 15 and 16), and Chapter 8 is fed by seven concept chapters. Adjacency is a nicety, not the mechanism.

---

## 9. Diagrams — the largest single unclaimed gain

The book has **zero diagrams**. Multimedia effect size is d=1.67; the pre-training effect (a diagram placed *before* the code it explains) is d=0.46; graphic organizers are d=1.24. Nothing else in this plan buys as much per hour of work, and — importantly — **this work is completely independent of the restructure**, which is why it is scheduled before it (§12, Phase 2).

Ranked, with the format each one actually wants and its v2 chapter:

| # | Diagram | Type | Format | Ch |
|---|---|---|---|---|
| 1 | The notional machine: what runs where | data-flow + sequence | Mermaid | 1 |
| 2 | Atomic group, all-or-nothing | swimlane | Mermaid | 6 |
| 3 | "Where does this data go?" | decision tree | **SVG** | 4 |
| 4 | The MBR slab | quantity layout | **SVG** | 4 |
| 5 | The contract is an account, and it can send | sequence | Mermaid | 6 |
| 6 | Anatomy of a failed simulate trace | annotated artifact | **SVG** | 7 |
| 7 | The six OnCompletes | state machine | Mermaid | 2 |
| 8 | Who pays | stacked bar | **SVG** | 10 |
| 9 | The constant product curve | cartesian | **SVG** | 12 |
| 10 | Reward-per-token with two stakers | timeline | **SVG** | 16 |
| 11 | An ABI call on the wire | memory layout | **SVG** | 2 |
| 12 | LogicSig, two modes | comparison | Mermaid | 17 |
| 13 | The book's dependency graph | graphic organizer | Mermaid | front matter |
| 14 | Packed box layout | memory layout | **SVG** | 4 |
| 15 | The provenance trust graph | graph | Mermaid | 15 |
| 16 | State commits only if the whole group approves | swimlane, extends #2 | Mermaid | 6 |

Three placements changed against the v1 chapter map, each for the same reason — a diagram belongs in the chapter where the concept is *introduced*, not where it is most used.

**Diagram 4, the MBR slab, moves to Chapter 4.** MBR first bites in the box chapter, where the reader is computing `2,500 + 400 × (name_len + size)` by hand and needs to see what that number *is*. Chapter 10 back-references it rather than drawing it a second time — putting the slab in Chapter 10 would mean six chapters of MBR arithmetic done against an unillustrated abstraction.

**Diagram 2, atomic groups, moves to Chapter 6.** Groups are introduced in "Moving Value: Assets, Payments, and Groups," not in the authorization chapter that later validates them.

**Diagram 3, the storage decision tree, moves to Chapter 4.** The tree's branches are global / local / box, so it cannot be drawn before the box tier exists. It becomes Chapter 4's anchor figure — placed before any code, per the pre-training rule — and Chapter 3 gets a one-line forward pointer instead of a truncated two-branch version of the same tree.

That concentration is deliberate but worth watching: Chapter 4 now carries three figures and Chapter 6 carries three. If Chapter 6 feels crowded in drafting, **merge 5 into 16** — "the contract is an account, it can send, and none of it commits unless the group approves" is arguably one idea shown twice.

The seven **threshold concepts** — contract-as-validator-not-program · state commits only if the whole group approves · the contract has an account and it is not the caller · inner transactions make your contract a sender · atomic groups are one unit and can see each other's writes · MBR *locks* Algo rather than spending it · a LogicSig's address **is** its program hash — currently have a diagram between them of exactly zero. With diagram 16 added and diagram 5 retitled to carry the inner-transaction-as-sender idea explicitly, diagrams 1, 2, 4, 5, 12, and 16 cover all seven.

---

## 10. Gaps this restructure exposes but does not by itself fix

1. **Debugging is taught nowhere.** This is the largest *skill* gap in the book: no PC-to-source mapping, no anatomy of a simulate trace, no failure taxonomy, and — related — **no modeling of uncertainty anywhere in the book.** Every author voice is confident. Chapter 7 exists to fix this; X-15 and diagram 6 are its centre.
2. **`ch02`'s `## Tests That Fail` is not productive failure.** None of the four tests actually fail; Gap 1 asserts `> 0` and passes, and line 1111 concedes the overflow case cannot be tested. Chapter 7's Mini-Build — the vesting contract, shown broken and then fixed — must contain tests that genuinely fail and then get fixed.
3. **Every project chapter now gets a project directory** — *resolved, per your decision 3.* `projects/` currently has chapter2 through chapter7 and stops, so Chapters 18 and 20 ship without runnable code and Chapter 22 has nowhere to put its harness. Three directories get created in Phase 6 (§12): `projects/chapter9/limit-order-book`, `projects/chapter10/zk-voting`, and `projects/chapter22/`. They keep the **existing old-number scheme** — the directories on disk today are `chapter2`…`chapter7`, and the manifest's `code:` field carries the mapping to the new chapter numbers, so nothing renames and no link breaks. A slug rename to the new numbering is optional Phase 6 cleanup and explicitly not required. Cost is unequal and worth stating: the ZK voting directory is the expensive one (a Groth16 verifier plus committed circuit artifacts and a proving key), the limit-order book needs a keeper bot to be demonstrable at all, and `chapter22/` contains **no contract at all** by design (§15.8). The new `book.yaml` manifest's `code:` field makes a missing directory a build error rather than a thing nobody noticed.
4. **No capstone** — *resolved.* Chapter 22 is specified in full in **§15**: three deliverables, three directions with a de-scoping ladder, a six-dimension rubric, an adversary test, and an acceptance harness that ships tests without an implementation.
5. **Editorial debt** (publishing-pro's list, minus the two items you ruled out of scope): no copyright page (F1 is a liability disclaimer with no copyright line, edition statement, or ISBN, despite the repo's `Copyright (c) 2026 m1o1`; the AI-disclosure belongs here); no Foreword; no lists of figures, tables, or examples; no "How to Use This Book" reading paths; no index; no colophon. The Preface is missing How to Contact Us and Acknowledgments, and its "Test Helpers and Client-Side Code" section is chapter content sitting in front matter — it moves to Chapter 7. The dated version-baseline block in the Preface is genuinely well done — keep it, just single-source the date. *Struck per your decision 4:* the missing title page and the author line. The cover stays the first page and `author:` stays as it is.
6. **Live bugs found while surveying.** pandoc's `-N` numbers `A1-cookbook` as **Chapter 11** because there is no `\appendix` break. `metadata.yaml` says "March 2026" while the Preface says "May 14, 2026." The 85-character code-line rule is invisible because `fvextra`'s `breaklines` wraps silently. Numbered code callouts (`# <1>`) are used nowhere — all annotation is inline comments, which push lines past 85 characters and are not screen-reader-friendly. Two competing sectioning idioms (`## Pattern N:` and `## Part N:`) need a stated replacement rule. There are zero deep-linkable anchors book-wide.
7. **Callout styling.** Seventeen distinct callout labels currently render identically. This is the biggest reader-facing formatting gap. Consolidate to eight — four standard (Note, Tip, Warning, Caution) and four pedagogical (Check Your Understanding, Design Decision, Try It Yourself, Practice) — plus `.gotcha`, with real CSS and matching LaTeX environments.
8. **The bibliography is 2KB** for a book whose citations are almost entirely inline hyperlinks, which vanish in print.
---

## 11. Mechanics: how 236 examples stay numbered, referenced, and buildable

The restructure only survives contact with editing if numbering, cross-references, and figures are all generated rather than typed. This section is publishing-pro's design, adopted whole with two additions from algorand-expert (the `code:` field, the compile guard).

### 11.1 Dual-identity numbering — a stable slug in source, a computed number in output

Every numbered element carries a slug that never changes and a display number that is never written down. In the chapter source:

```markdown
### Example {#ex-asa-optin-self}. Opting a contract into an ASA
finder: opt my contract into an asset so it can hold it
```

and in prose, anywhere in the book:

```markdown
We built this in {{ex:asa-optin-self}} and it is the same call here.
```

which resolves at build time to `Example 6-14`. **Prose never contains a number.** That single rule is what makes the phased migration of §12 affordable — a chapter can move from position 9 to position 17 without a single edit to any sentence in the book.

Five namespaces, all resolved the same way:

| Namespace | Points at | Resolves to |
|---|---|---|
| `{{ex:slug}}` | a micro-example | `Example 6-14` |
| `{{tbl:slug}}` | a table | `Table 10-2` |
| `{{fig:slug}}` | a figure | `Figure 3-1` |
| `{{ch:slug}}` | a chapter | `Chapter 12` |
| `{{part:slug}}` | a part | `Part III` |

`{{fig:}}` is the **only** figure namespace. An earlier draft of §11.4 wrote `{{figure:}}` for the same thing; two spellings for one namespace is exactly the drift this whole mechanism exists to prevent, and the resolver should hard-fail on `{{figure:` rather than silently accepting both.

The resolver is two passes over `chapters/`, added to `build.py`:

1. **Pass 1 — collect.** Walk the chapters in manifest order. For every `{#slug}` anchor, record `(slug, kind, chapter_position, ordinal_within_chapter, display_title, finder_line, tier)`. Write `build/xref.json`.
2. **Pass 2 — substitute.** Rewrite every `{{ns:slug}}` into its display string plus the renderer-appropriate link (`#ex-asa-optin-self` for mdbook, `\ref{}`/`\hyperref` for LaTeX), emitting to `build/resolved/`.

**Both renderers consume `build/resolved/`, not `chapters/`.** This is the one structural change to `build.py`'s data flow, and it is what lets the same source produce a correctly hyperlinked HTML site and a correctly cross-referenced PDF. Set `no-section-label = true` in `mdbook/book.toml` so mdbook's own numbering never competes with the computed numbers.

`build/xref.json` is also the input to three generators: the Example Finder (Appendix D), Gotchas by Topic (Appendix C), and the Lists of Examples, Figures, and Tables. **The List of Examples is not optional.** The PDF builds with `--toc-depth=2`, so H3 example headings never reach the printed table of contents; without a generated list, 236 examples are invisible to a reader holding the book.

### 11.2 The manifest: `chapters/book.yaml`

`PART_BREAKS`, `FRONT_MATTER`, `BACK_MATTER`, and `_chapter_sort_key`'s filename-prefix ordering all get replaced by one declarative file. Ordering becomes explicit rather than lexical, which is the precondition for reordering chapters at all.

```yaml
front:
  - {file: F1-legal-notice.md}
  - {file: F2-preface.md}

parts:
  - id: foundations
    title: Foundations
    chapters:
      - {file: 01-c-mental-model.md,        kind: concept}
      - {file: 02-c-callable-contracts.md,  kind: concept}
      - {file: 03-c-state.md,               kind: concept}
      - {file: 04-c-boxes.md,               kind: concept}
      - {file: 05-c-numbers-and-time.md,    kind: concept}
      - {file: 06-c-moving-value.md,        kind: concept}
      - {file: 07-c-proving-it-works.md,    kind: concept}
      - {file: 08-p-token-vesting.md,       kind: project,
         code: projects/chapter3/token-vesting}
  # ... parts II–V
  #   - {file: 18-p-limit-order-book.md, kind: project,
  #      code: projects/chapter9/limit-order-book}
  #   - {file: 20-p-zk-voting.md,        kind: project,
  #      code: projects/chapter10/zk-voting}
  #   - {file: 22-x-capstone.md,         kind: capstone,
  #      code: projects/chapter22}

examples:
  root: examples/            # a package, not a folder — see below
  manifest: examples/index.yaml

appendices:
  - {file: A1-environment.md}
  - {file: A2-avm-limits.md}
  - {file: A3-gotchas.md,        generated: true}
  - {file: A4-example-finder.md, generated: true}

back:
  - {file: Z1-whats-next.md}
  - {file: Z2-glossary.md}
  - {file: Z3-bibliography.md}
```

Three fields earn their keep. `kind: concept|project|capstone` drives the chapter-opener banner, the CSS class, and the LaTeX rule — §4.4's signalling falls out of the manifest for free rather than being hand-applied 22 times. `code:` links a project chapter to its directory, and every project chapter now has one (§10 gap 3): the three that do not exist on disk yet — `projects/chapter9/limit-order-book`, `projects/chapter10/zk-voting`, `projects/chapter22` — are created in Phase 6, and until they are, the manifest makes their absence a build error rather than a thing nobody noticed. Note the directory names keep the **old** chapter numbering; the manifest is where the old-to-new mapping lives, which is what lets the chapters renumber without a single directory rename. `generated: true` marks files that `build.py` writes and that a human must never edit; the build should overwrite them unconditionally and CI should fail if they are dirty in git after a build.

#### `examples/` — the tree the Completeness Contract requires

The contract in §2.1 says the thing on the page is the thing on disk. That needs a place on disk, and it needs to be a **Python package with a `pyproject.toml`**, not a folder of loose files — compiling a bare `.py` outside a package root makes puyapy emit `warning: could not determine algopy version`, and the version pin is precisely what the book is asserting.

```
examples/
  pyproject.toml              pins puyapy / algorand-python / algokit-utils / testing
  index.yaml                  slug → path, tier, mode, chapter  (generates Appendix D)
  ch04_boxes/
    box_map_write.py          the printed artifact
    box_map_write_test.py     mode: unit — on disk, not printed (§2.1)
    missing_copy.py           mode: compile-fail
```

`index.yaml` carries one entry per example, and the `mode` and `expect` fields are what make CI able to check the book rather than just build it:

```yaml
- slug: struct-missing-copy
  path: ch03_state/missing_copy.py
  tier: core
  mode: compile-fail
  chapter: 3
  expect: "must be copied using .copy()"
```

At 236 examples with tests, this is roughly 470 files. That is the honest cost of the contract, and it is why `index.yaml` is generated from front matter in the chapter source rather than hand-maintained — a hand-maintained index of 470 files drifts within a month.

### 11.3 Eleven build-time validations

Added to `scripts/validate.py` as a new `--structure` target, wired into `--all`. Checks 1–8 are cheap regex-and-lookup checks over `chapters/` plus `build/xref.json`; 9–11 arrive with the Completeness Contract and the capstone:

| # | Check | Fails when | Severity |
|---|---|---|---|
| 1 | Unknown slug | `{{ns:slug}}` has no matching `{#slug}` anchor | error |
| 2 | Duplicate slug | the same `{#slug}` is defined twice | error |
| 3 | Orphan number | a `{{tbl:}}` or `{{fig:}}` target has zero in-text references | **warning** |
| 4 | Cookbook residue | `[Cc]ookbook` or `[Rr]ecipe\s*\d+\.\d+` survives anywhere in `chapters/` | error |
| 5 | Appendix-in-chapter | `^## Appendix [A-Z]` appears inside a chapter file | error |
| 6 | Untagged fence | a code fence has no language tag | error |
| 7 | Long code line | a line inside a non-exempt fence exceeds 85 characters | error |
| 8 | Project re-teaching | a project chapter has a section heading matching an existing example's display title | warning |
| 9 | **Print/disk drift** | a printed example fence differs by one byte from its file in `examples/` | error |
| 10 | **Tier overrun** | a Core example exceeds 35 printed lines, or an Extended one exceeds 20 | error |
| 11 | **Capstone leak** | Chapter 22 names a mechanic with no resolving `{{ex:}}` slug | error |

**Check 3 was over-scoped in the earlier draft and would have failed the build on correct books.** Applied to `{{ex:}}` it demands that all 236 examples be referenced from prose, which is wrong on its face: an Extended example in the middle of a cluster is read in sequence and referred to by nobody, and that is the design. Scope the check to tables and figures, where an unreferenced number really is an editing bug, and count a Handoff-table row as a satisfying reference for `{{ex:}}` targets. Emit a warning, never an error — the useful signal is a *rising* orphan count between drafts, not a binary.

**Check 7 needs two escapes to be enforceable at all.** Today `fvextra`'s `breaklines` silently wraps over-long lines, so the 85-character rule has been unenforceable and therefore unenforced; making it a hard error is right, but some content has no legal wrap point. Exempt `text`, `json`, and `teal` fences wholesale — Falcon public keys, BN254 pairing-point literals, and ARC-56 JSON cannot be broken without becoming wrong — and give every other fence a per-fence opt-out (```` ```python {.nowrap} ````) that a human must type deliberately. An opt-out that requires an explicit annotation stays visible in review; a silent wrap does not.

**Check 8 is new, and it is the mechanical test for §8.2.** The whole restructure fails quietly if the concept chapters get written and the project chapters keep teaching the same material anyway — the book would simply be longer. If Chapter 13 contains a heading "Fixed-Point Scaling" and there is an example whose display title is "Fixed-point scaling," the project chapter is re-teaching and should be back-referencing. Fuzzy title matching produces false positives, hence warning severity, but it is the only automated check in this plan that measures whether the restructure actually happened.

**Check 9 is the Completeness Contract's enforcement, and it is the reason the contract is worth anything.** Examples are not typed into chapters; they are *transcluded* from `examples/` by slug, and check 9 verifies the transclusion is exact. Without it, a fix applied to a file on disk never reaches the page, and the book quietly reverts to shipping stale code with a CI badge saying otherwise — which is worse than not having the harness, because it looks verified.

**Check 10 makes the §2.3 budgets real rather than aspirational.** §2.3 predicts some Extended examples will not fit in 20 complete lines and must merge or promote. Check 10 is what forces that decision to be made instead of quietly skipped, and its failure count during Phase 4 is the measurement §2.3 asks for.

**Check 11 enforces §15.1's hard constraint: the capstone introduces no new Algorand surface.** Every mechanic Chapter 22 names must resolve to an example the reader has already run. This check will fail on its first run — that is its purpose. Each failure means either a mechanic that needs an example added to the right concept chapter, or a sentence in Chapter 22 that is teaching when it should be referring.

Checks 9–11 need the code to actually build, so they ride along with a second new target, **`validate.py --examples`**, which walks `examples/index.yaml` and dispatches by mode: `compile` and `compile-fail` run puyapy (the latter asserting a non-zero exit *and* the declared `expect` substring in stderr), `unit` runs pytest, `localnet` runs against a LocalNet the CI job stands up. This is the slowest target in the suite by a wide margin — 236 puyapy invocations — so it runs on the full-build job rather than on every commit, and takes a `--changed-only` flag driven by git for local use.

Check 4 stays *off* until Phase 5 completes, then flips on permanently and makes regression impossible. Check 5 exists because ch09 and ch10 currently contain `## Appendix A/B/C` headings that will collide with the book's real appendices once those are numbered.

**Five checks beyond the eleven, added by the phases that needed them.** The heading above says eleven because eleven is what §11.3 specified; the harness now runs sixteen, and the extra five are recorded here so the count in the code and the count in the plan stop disagreeing. **Check 12** (Phase 1) guards the callout vocabulary, because pandoc's LaTeX writer silently drops a Div it has no environment for while the HTML renderer boxes anything at all — a mistyped class would render as a callout in one output and as bare prose in the other, with nothing to report it. It also parses every `.gotcha`'s attributes the way the harvester does and insists nothing is left over, since `GOTCHA_ATTR_RE`'s `[^"]*` value pattern cannot express an escaped inner quote and truncates the title without a word; check 14 cannot catch that, because both sides of its comparison are generated from the same truncation. **Check 13** (Phase 2) requires every figure to be drawn, rendered to both SVG and PDF, and placed exactly once. **Check 14** (Phase 3) fails when the generated gotcha appendix has drifted from the callouts it was harvested from. **Checks 15 and 16** (Phase 5a) are §2.6's two house rules, which were honoured by hand until then: the 50-line single-fence cap, and the ~120-line prompt-density floor. Check 15 reports as an error in chapters written under the rule and as a warning in the ones that predate it, and it decides which is which from the chapter's own content — a restructured chapter shows its artifact broken before it fixes it, so a `## The Mini-Build` heading is the marker, and unlike a manifest flag it cannot go stale. Check 16 is a warning everywhere, permanently: the plan says "~120", and a hard error on an approximate rule teaches authors to pad rather than to engage.

**Check 1 was also tightened in Phase 5a**, closing the `build.py`/`validate.py` disagreement that Phase 4 recorded as finding 2. An `{{ex:slug}}` prints a *number*, and a number exists only where a caption mints one, so validating that reference against `examples/index.yaml` — as the original check did — let a slug pass validation and then kill the build. The build's stricter rule wins: an `ex` reference must resolve to a `{#ex:slug}` anchor in `chapters/`. The reciprocal is now checked too, and it is the more interesting half — a caption that mints `{#ex:slug}` for a slug the index has never heard of numbers a program CI does not compile, which is precisely the drift the Completeness Contract exists to prevent, wearing the costume of a correctly formatted book. `{{include-ex:}}` still resolves against the index, because transclusion is what *places* the file and cannot require the anchor it is about to help mint.

**One toolchain note surfaced while building the probes in §2.1.** puyapy's `--target-avm-version` **defaults to 11**, and its accepted range now runs to 13, while `scripts/validate.py` pins `TARGET_AVM_VERSION = "12"`. The `examples/` harness must pass the flag explicitly rather than inherit the default, or the book will silently verify its examples against an AVM one version below the one it claims. puyapy 5.9.0 is also now released against the plan's 5.8.1 baseline; Phase 0 is where the pin gets re-taken and the whole §0 baseline line updated with it.

### 11.4 Figures: pre-render to static assets, commit them

Neither renderer can draw a diagram at build time in the form the plan needs. Pandoc/xelatex cannot render Mermaid at all, and `mdbook-mermaid` is client-side JavaScript — so a Mermaid block that renders beautifully in HTML produces a code listing in the PDF. The fix is to render once, ahead of time, and commit the output.

```
figures/
  src/*.mmd            Mermaid sources (hand-edited)
  src/*.svg            hand-drawn SVG (diagrams 3, 4, 6, 8, 9, 10, 11, 14)
  theme.json           greys + line-style only; no hue-only distinctions
  out/*.svg            → mdbook          COMMITTED
  out/*.pdf            → xelatex         COMMITTED
  out/.hashes.json     content hashes, to skip unchanged renders
```

A new target, `python3 build.py figures`, renders `src/` into `out/`. It hashes sources so that unchanged diagrams are skipped — `mmdc` spawns a headless Chromium and is slow enough that an unconditional re-render would make the ordinary build painful. **If `mmdc` is absent, warn and continue**; a contributor without Node must still be able to build the book, because the outputs are committed.

**Both inputs take the same path to PDF: render to SVG first, then `rsvg-convert -f pdf`.** The earlier draft had Mermaid going straight to PDF via `mmdc -o out.pdf`, which does not produce what a book needs — `mmdc`'s PDF output is a Puppeteer page print, so it carries page margins and a page-sized bounding box rather than a tight one around the diagram. `\includegraphics` then scales the whitespace along with the drawing. So: `mmdc → out/*.svg` for Mermaid, a straight copy for hand-drawn SVG, and then one uniform `rsvg-convert -f pdf` pass over every SVG in `out/`. One conversion path, tight bounding boxes, no per-format special cases.

**The mdbook path needs a copy step that does not exist today.** `build.py:313` does `shutil.rmtree(SRC_DIR)` on every build and then writes only chapter files and the cover into `mdbook/src/` — so any relative path from a chapter to `../figures/` escapes the book root and mdbook silently drops the image. The fix is three lines: after the `rmtree`, copy `figures/out/*.svg` into `mdbook/src/figures/`, and have the resolver emit **book-root-relative** `![](figures/<slug>.svg)` rather than a `../` path. For the LaTeX target, emit `\includegraphics{<slug>.pdf}` and add `--resource-path=.:figures/out` to the pandoc invocation, so the path resolution lives in one flag instead of in every chapter.

Two deliberate choices. **PDF, not PNG,** for the LaTeX assets: `graphicx` cannot consume SVG, and PNG goes soft at the 8pt type these diagrams carry. **Greyscale-plus-line-style theming,** because the print edition is black and white and any diagram whose meaning lives in hue is a diagram that fails for half its readers.

Chapters reference figures only as `{{fig:amm-swap-flow}}`, never as a path or an image tag. One reference syntax, two renderers, no per-chapter conditionals.

### 11.5 PDF fixes to land alongside

Five small items, all currently visible defects:

- `\appendix` before the first appendix. Today pandoc's `-N` numbers `A1-cookbook.md` as **Chapter 11** — the appendix is presented to the reader as a chapter of the book.
- `\floatplacement{figure}{H}` so the sixteen new figures land where the prose puts them, not three pages later.
- `\listoffigures` and `\listoftables` after the TOC, plus the generated List of Examples.
- Single-source the baseline date. `metadata.yaml` says March 2026; the Preface says May 14, 2026. Put it in `metadata.yaml` and have the Preface interpolate it.
- `\chaptermark` short titles capped at 48 characters, so running heads stop overflowing on the longer project-chapter titles.

(This was six items; the author line is struck per your decision 4, along with the title page in §10 gap 5.)

---

## 12. The phased migration

Seven phases. Each one ends with a book that builds, and the first three deliver value **without touching chapter order at all** — which is what makes this plan safe to stop halfway.

### Phase 0 — Guardrails (no reader-visible change)

Stand up `chapters/book.yaml` and switch `build.py` to read ordering from it. Do the `NN-c-`/`NN-p-` filename rename **once, now**, even though numbers will change later, so that no file is renamed twice. Add the eleven validations from §11.3 to `scripts/validate.py` (check 4 registered but disabled; checks 9–11 registered and vacuously passing until there is anything to check). Wire `validate.py --all --structure` into CI.

**Also stand up `examples/` and its compile harness, before a single example is written.** The `pyproject.toml`, the `index.yaml` schema, the transclusion step in `build.py`, and the `validate.py --examples` target with all four execution modes. Prove it end to end on three seed examples — one `compile`, one `unit`, one `compile-fail` — and confirm the `compile-fail` seed genuinely fails for the declared reason rather than for a typo. Re-take the toolchain pin here too: the plan's baseline is puyapy 5.8.1 and 5.9.0 is out, and `--target-avm-version` must be passed explicitly because puyapy defaults to 11 while the repo targets 12 (§11.3).

This ordering is deliberate. The harness is worth roughly nothing built in Phase 5 and everything built in Phase 0 — an example written before the harness exists is an example nobody ever compiled, and 236 of those is the exact failure the Completeness Contract exists to prevent.

Success criterion: the built PDF and HTML are byte-identical to today's output, **except** for the `\appendix` fix, which corrects the Cookbook's chapter numbering; and `validate.py --examples` passes on the three seeds.

### Phase 1 — Apparatus, and the one action that makes everything after it cheap

Build the two-pass xref resolver. Then, before anything else:

> **Convert every chapter reference in prose to `{{ch:slug}}`.**

This is the single highest-leverage action in the whole migration. Renumbering churn is the main cost of this plan — every "Chapter 3" and "see Chapter 5" in the book's prose would otherwise have to be found and corrected by hand, twice, across five phases of reordering, with no way to verify completeness. Convert first and renumbering becomes free forever after. `Z1-whats-next.md` alone hard-codes Chapter 5 and Chapter 10; the project chapters hard-code many more.

Also in Phase 1: number the remaining 27 tables to the existing convention; add `\listoffigures`/`\listoftables`; rename ch09/ch10's internal `## Appendix A/B/C` sections so they stop colliding; give the Preface its missing **How to Contact Us** and **Acknowledgments**; and consolidate the 17 callout labels down to 8 plus `.gotcha`, with actual distinct styling rather than 17 labels that render identically.

### Phase 2 — Diagrams, into the *existing* chapters

Ship the `figures/` pipeline of §11.4 and draw all sixteen diagrams of §9 — into the book as it stands today, at chapter numbers that have not moved. This is deliberately placed before the restructure because it is the **largest single quality gain available (d=1.67), it is completely independent of chapter order, and it is the phase most likely to be worth doing even if the restructure is never finished.** A reader of the current book with sixteen good diagrams in it is materially better served than one without.

### Phase 3 — Extract, don't reorder

Still no chapter renumbering. Extract Appendix A (ch01's 242-line setup section) and Appendix B (the cookbook's AVM Limits tail, expanded). Add `::: {.gotcha}` markers throughout and generate Appendix C from them, then delete `A2-gotchas.md`. Apply the ≤60-line `## Run It First` contract to all seven project chapters — this alone recovers roughly 1,000 lines and rebalances ch06, where the section is 45% of the chapter. De-duplicate ch06's ~200 lines that restate ch05's pool contract, replacing them with `{{ex:}}` references.

At the end of Phase 3 the book is meaningfully better, the chapter numbers are unchanged, and every subsequent phase is optional.

### Phase 4 — Pilot exactly one concept chapter

Write **Chapter 3, "Remembering Things: Global and Local State"** — 20 examples, the *A Registry of Members* Mini-Build shown broken and then fixed, the gotcha markers, the Retrieval block, the five-rung exercise ladder, `## Before You Continue`, and the Handoff table. One chapter, complete, to the full §2.4 shape.

The pilot exists to produce a number: **hours per concept chapter, measured rather than estimated.** It also tests five assumptions that the rest of the plan rests on — that the six-slot anatomy reads well at Core tier, that the Core/Extended boundary lands in the right place, that the Mini-Build is genuinely buildable at 30–90 lines, that the broken-then-fixed framing survives a reader who does not yet have the vocabulary to name the break, and — new with the Completeness Contract — **how many Extended examples cannot be made complete inside 20 lines.** Chapter 3 is the right chapter to measure that on, because state examples are the ones most likely to need a struct definition they cannot borrow from a neighbour.

Record the check-10 failure count. If more than about two of Chapter 3's twenty examples have to merge or promote, extrapolate: the same rate across 236 puts the number above fifteen, and §2.3 says that means the 157/79 split gets re-cut rather than defended. Do not start Phase 5 before reading the pilot back cold.

#### Phase 4 results — measured, not estimated

Chapter 3 shipped with **21 numbered examples** (twenty planned, plus the broken registry, which had to be captioned once it became the target of a cross-reference), 24 registered example files counting the two Slot-5 wrong variants and the unit test, and five gotchas.

**The measurement the phase existed to produce: the check-10 failure count is zero.** Not one Extended example exceeded its 20-line budget. Nothing merged, nothing was promoted to Core, and no example needed a struct definition it could not afford to carry. §2.3's threshold for re-cutting the split was "more than about two"; the observed rate is 0/21. **The 157/79 split survives Phase 4 and gets defended rather than re-cut.** The prediction that state examples would be the hardest case is now evidence in the split's favour, since they were the chapter chosen precisely because they were expected to fail.

The four other assumptions also held: the six-slot anatomy reads well at Core tier, the Mini-Build landed at 56 lines (inside the 30–90 band and inside the 90-line minibuild tier, which check 10 enforces rather than exempts), and the broken-then-fixed framing survives a reader with no vocabulary for the break — the chapter opens with a console session showing `members()` returning a confident wrong number, which needs no vocabulary at all to read as wrong.

**Eleven findings the pilot produced, in the order they will matter to Phase 5:**

1. **The three-agent review is not optional for a concept chapter, and this is the most important finding here.** Nine substantive technical errors survived a clean `validate --structure`, a clean `validate --examples`, and a clean compile of all 24 example files. Among them: local-state MBR attributed to the wrong account, `OnSchemaBreak.ReplaceApp` described as leaving the old application standing, a missing-key abort attributed to the AVM rather than to PuyaPy's generated assertion, and a `GlobalMap` presented as an unbounded per-account store when it draws from the same 64-pair global budget as everything else. **The validators check form; only the agents checked truth.** Budget the review into every Phase 5 chapter rather than treating it as a final polish.
2. **`build.py` and `validate.py` disagree about `{{ex:}}`.** `validate.py` check 1 resolves an `ex` reference against `examples/index.yaml`; `build.py`'s `_ref()` requires a caption anchor in the chapters and exits hard without one. A slug can therefore pass validation and break the build. Reconcile in Phase 5 — the build's rule is the correct one, so validate should adopt it.
3. **A `.gotcha` `title=` containing escaped inner quotes is silently truncated.** `GOTCHA_ATTR_RE` uses `[^"]*`, so `title="a \"quoted\" thing"` harvests as `a \` and becomes that heading in the generated appendix. `validate.py` cannot see it because the attribute still parses as *a* title. Add a check.
4. **`script` mode is byte-compile-only**, a deliberate narrowing of the earlier plan text. Every other mode except `compile-fail` genuinely compiles the example.
5. **Slot-5 wrong variants get their own `index.yaml` entries**, both at `tier: extended`, so the Core budget cannot be evaded by splitting an example into a right half and a wrong half.
6. **`minibuild: 90` is a tier, not an exemption.** Check 10 bounds the Mini-Build like anything else.
7. **`finder:` has no implementation** anywhere in the toolchain — it exists only in §2.2 and §11.1. Chapter 3 carries its twenty finder directives as `<!-- finder: … -->` HTML comments, invisible in both renderers and harvestable the moment Phase 6's Example Finder generator exists.
8. **§2.6's 50-line single-fence cap and the ~120-consecutive-lines-without-a-prompt rule are still unimplemented** as checks and were honoured by hand.
9. **Two of Chapter 3's gotchas overlap `03-p-token-vesting.md`** (`#schema-is-immutable`, `#clear-state-always-succeeds`). De-duplicate when that project chapter gets its Phase 5 edit; the concept chapter should keep them.
10. **`build.py` had a latent caption bug** that only an *example* caption could expose — the book had never numbered one before. Fixed during the pilot. Expect more of these: Phase 4 is the first chapter to exercise the full §2.4 shape, so it is the first to touch several code paths at all.
11. **Deferred to Phase 5 by choice, not oversight** — restructuring the pilot mid-commit would have destroyed the measurement. Swap clusters 1 and 2 so the two-slab model precedes struct packing; give `state-schema-fixed` and `factory-deploy-idempotent` their own `## Schema, Fixed at Creation` section; move `unsafe-decoding` to the ARC-4/ABI chapter where it belongs; add a second figure tracing one account's slab across opt-in → award → ClearState; distribute the Retrieval prompts to cluster heads instead of one terminal block; add an answers appendix. Also reconcile the exercise labels: §2.4 mandates Trace → Parsons → Debug → Compare → Extend, the existing book uses (Recall)/(Apply)/(Analyze)/(Create), and Chapter 3 follows the plan. One of the two has to migrate, and that decision belongs to 5a, not here.

**On hours per concept chapter.** The pilot did not produce a clean wall-clock number, because authoring was interleaved with building the Phase 0–3 machinery the chapter runs on and with fixing tooling the chapter was the first to exercise. The honest reading is that the *marginal* chapter is much cheaper than this one, and that the review-and-correct cycle — not the drafting — is the part that will dominate Phase 5. Phase 5a's first chapter is the one to time.

### Phase 5 — The remaining concept chapters, one part per release

5a: Part I (Chapters 1, 2, 4, 5, 6, 7) — the on-ramp, and the phase that delivers the reading experience you asked for.
5b: Part II (9, 10). 5c: Part III (12, 14). 5d: Part IV (17, 19). 5e: Part V (21).

**Every sub-phase ends the same way, and this is the step that is easiest to skip and most expensive to skip.** 5a, 5b, 5c, 5d, and 5e each finish by editing the project chapter that closes their Part: convert its first-teaching prose to `{{ex:}}` back-references (§8.2) and regenerate its `## What You Need First` block from the Handoff tables just written (§8.4). **A Part is not done until its project chapter no longer teaches anything for the first time** — check 8 is how you find out whether it does. Skipping this leaves the book strictly longer than it started with none of the benefit, which is the single most likely way this plan fails in practice.

Chapter renumbering also happens here, and it is safe because of Phase 1. As each destination chapter is written, the corresponding recipes are deleted from `A1-cookbook.md` and the corresponding patterns from `08-common-patterns-and-idioms.md`; when both files are empty they are deleted, and **build check 4 flips on** — after which no `Cookbook` or `recipe N.M` reference can ever re-enter the book.

**Project directories are not renamed.** `projects/chapter3/token-vesting` stays where it is even though its chapter becomes Chapter 8. The manifest's `code:` field carries the mapping. Renaming directories would break every path in the projects' own READMEs, scripts, and tests for a purely cosmetic gain.

#### Phase 5a progress — the pilot's debts, paid first

5a opened by paying what Phase 4 deferred rather than by drafting, and that ordering was right: the deferred items were all *structural*, and every one of them would have had to be re-applied to Chapter 1 as well if Chapter 1 had been written first.

**The cold read-back happened, and it earned its place in the phase gate.** Ten findings, one of them severe enough to have shipped a wrong mental model: the chapter conflated two different absences in state reads. `.get(default=…)` covers a key that was never written *inside a slab that exists*; it does nothing for an account with no slab at all, because reading the local state of an account that has not opted in is a ledger error raised before any default can apply. The broken Mini-Build fails both ways, the chapter's fix narrative addressed one, and no validator can see the difference. Two absences, two fixes, and they are now named as such in three places.

**All ten findings are applied, plus the six structural items Phase 4 finding 11 deferred.** Chapter 3's clusters were reordered so the two-slab model precedes struct packing; `## Schema, Fixed at Creation` was split out as its own section, which fixed a topical misfiling and a §2.3 cap violation at the same time (a straight merge into The Global Slab would have been seven examples, and the hard cap is six); `unsafe-decoding` and its wrong variant were cut and parked, because validating an untrusted ARC-4 argument is an ABI topic wearing a state costume and belongs in Chapter 2; a second figure was drawn tracing one account's slab across opt-in → award → ClearState; the aboutitis around schema breaks was replaced with a real `deploy()` transcript and a decision table, both verified against the `algokit_utils` source rather than recalled; and the Parsons exercise was re-based from `join` to `award`, because the fixed registry's `join` has two body statements and the exercise asked the reader to order three.

**Two constraints were discovered while applying the findings, and both are Phase 5b's inheritance.** A cross-reference to a chapter that does not exist yet cannot be written, because check 1 resolves it and fails — so the resource-availability paragraph refers to its future chapter in prose instead of by `{{ch:}}`, and that is a debt to collect when the chapter lands. And an example may be registered without being placed, which is what makes parking legal: check 3's orphan rule is scoped to `tbl:` and `fig:` only, so the two parked examples stay in CI's compile set while waiting for a chapter to live in.

**The toolchain was hardened before any new chapter was written**, which is the same reasoning that put the harness in Phase 0. Findings 2, 3, and 8 are closed: check 1 now enforces the build's stricter `{{ex:}}` rule in both directions, check 12 now catches a gotcha title the harvester would silently truncate, and checks 15 and 16 make §2.6's two house rules machine-checked instead of hand-honoured. The first run of 15 and 16 is itself a measurement: **17 fences over the 50-line cap and 13 stretches over the density floor, every one of them in a chapter Phases 5b–5e have not reached yet.** Zero in Chapter 3. The restructured shape does not produce these defects; the un-restructured one produces them at roughly one per forty pages.

#### Phase 5a progress — Chapter 1, the on-ramp's on-ramp

**Chapter 1 is written to the full §2.4 shape: eight assigned examples, eleven registered files, nine numbered placements.** The three extra registrations are the pair that bookends the chapter (`greeter-broken` is numbered and captioned; `greeter-fixed` is registered and compiled but never transcluded, because the Mini-Build, Fixed is a diff of at most fifteen lines, not a re-listing) and `reference-types-wrong`, transcluded bare with no caption. That bare-transclusion convention is Chapter 3's precedent and it was deliberately kept when an editorial review asked to caption it: a wrong variant that carries an example number reads as something to learn rather than something to recognize.

**The chapter is organized around one artifact that fails three ways, and the three failures are the chapter's spine.** A greeter with a messageless `assert` (pc 78), an unbounded ABI return that overruns the 1,024-byte log budget (pc 106), and an admin guard that compares `Txn.sender` against the application's own address, which no sender can ever be (pc 115). Every concept section closes with one line naming which of the three it repairs. The byte arithmetic behind the second — 4 bytes of ARC-4 return prefix, a 2-byte length header, 7 bytes of `"Hello, "`, and an 1,100-byte name, against a 1,024-byte ceiling — is derived in the chapter rather than asserted, and the program counters were obtained by compiling the contract, not by recall.

**The single most valuable structural change came from a review, not from drafting: one hundred-line section became three.** `A Program That Only Says No`, `Four Accounts, and Only Two of Them Can Sign`, and `What ARC4Contract Writes for You` each now own exactly one of the three failures. The §2.4 shape's implicit claim — that a cluster explains one part of the broken artifact — turns out to be load-bearing in a way the pilot did not expose, because Chapter 3's broken registry fails in ways that are harder to separate.

**Four technical defects were caught by re-reviewing prose written in the same session, three of them in a passage that had just been added to fix an earlier finding.** The lifecycle passage claimed the approval program sees ledger state as of the start of the block (it sees state as of each opcode, including writes by earlier transactions in the same group, which is what makes atomic groups useful rather than merely tidy) and that it runs once (it is evaluated at pool admission by the submitting node, which is where the chapter's own immediate `LogicError` comes from, and again by every node validating the block). A sentence claimed the hand-written router never checks the OnComplete; it does — its real looseness is that it never checks `Txn.application_id != 0`. And `ensure_funded_from_environment` was described as conditional when it is not: it checks `DISPENSER_MNEMONIC` first on every network and otherwise falls back to a KMD lookup, so off LocalNet with no mnemonic you get a connection failure rather than a clean refusal. **The rule this validates is CLAUDE.md's: a substantive fix is itself a substantive change and gets re-reviewed.**

**A fifth defect was caught only by rasterizing the PDF and looking at it.** The anchor diagram carried the label "Inner transactions / up to 16 per call" — the widely-repeated wrong number — one page after the corrected prose explained that the pool is 256 per group and one call may spend all of it. No check in `validate.py` compares a figure's baked-in text against the chapter body, and none reasonably can. **Add "render it and read it" to the phase gate for any chapter whose figures carry numbers.**

**Also settled empirically, because two plausible APIs differ by transposition:** a *generated* typed factory spells creation `send.create.bare()`, an *untyped* `AppFactory` spells it `send.bare.create()`, and getting it backwards raises `AttributeError` rather than anything informative. Both forms appear in this book — the testing chapter uses the untyped one correctly — so the chapter now names the distinction rather than leaving it as a trap. Relatedly, `result.tx_id` is `None` for any readonly call, so example code uses `result.tx_ids[0]`, which is correct in both cases.

**State at the end of the Chapter 1 slice:** `20 files, 35 examples, 89 anchors, 145 references — 0 errors`, and `35 passed, 0 failed, 0 skipped` on the example compile set. The only Chapter-1-attributable warnings are two deliberate check-13 zero-placement warnings, for figures drawn for Chapters 4 and 6 and left unplaced as visible markers of outstanding work.

**One review finding was declined and is recorded here rather than silently dropped:** teaching-pro asked for runnable examples inside the three prose-only sections. That is a real pedagogical improvement and it would put Chapter 1 at eleven numbered examples against the plan's allocation of eight. Re-allocating is a decision about the book's shape, not a drafting choice, and it belongs to the author.

#### Phase 5a progress — Chapter 2, the boundary

**Chapter 2 is written to the same §2.4 shape: twenty-one numbered examples across five concept clusters, twenty-three registered files, one figure.** The two unnumbered registrations are the usual bookend pair — `counter-broken` is numbered and captioned, `counter-fixed` is registered and compiled but appears only as a diff — plus the three `*_wrong.py` variants transcluded bare, following the Chapter 1 convention. Two examples migrated in from `examples/ch03_state/` (`unsafe_decoding`, `unsafe_decoding_wrong`), paying the pilot's finding 11 debt: they were always ARC-4/ABI material parked in the state chapter.

**The broken artifact is a counter that only counted in simulation, and its three failures are the chapter's spine**, exactly as Chapter 1's greeter was. `bump` marked `readonly=True` so every conforming client answers it with a simulation and the write is never submitted; `describe` returning `Bytes`, so a generated client decodes `byte[]` into a list of integers rather than a label and a number; and `reset` carrying `create="allow"`, which deletes the application-ID check and lets a stranger create a fresh app, reset that one, and be told it worked — with the creator-only guard inside passing, because at app ID 0 the caller is the creator. Each concept section closes with one line naming which failure it repairs, and the third one is found in an ARC-56 JSON file rather than in TEAL, which is the section's actual point.

**The cluster boundaries moved once, during review, and the move was the chapter's most valuable structural change.** `readonly-method` began in the reachability cluster on the theory that `readonly` gates what a caller may do. It does not — it is advice a client reads out of the app spec, which is the *next* cluster's whole subject. Moving it turned `## How the Router Picks` into `## The File a Client Reads Before It Calls` and gave the cluster a real argument: addressing, permission, defaults, and then the spec read end-to-end, with the counter's third bug falling out of the last of those. The heading rename also cleared publishing-pro's finding that four consecutive `## What ...` headings, two of them adjacent, had stopped carrying information.

**Three technical defects were caught by re-reviewing prose written in the same session, and all three were byte-level.** A first pass explained the `byte[]` → `(string,uint64)` cost as "the tuple spends two more," which double-counts: `byte[]` is itself length-prefixed, so 2 bytes of overhead against the tuple's 4, over identical 14-byte payloads, is a delta of two. A new `string[]` decomposition fence said element offsets are counted from the *end* of the offset list; the base is its *start*, which is the only reading under which `0004` resolves to absolute index 6. And an exercise cited a multiplication-only example as authority for a claim about addition — repaired not by softening the exercise but by adding the generalization to the concept section, after the expert verified empirically that `+` aborts (`OverflowError: + overflows`) rather than wrapping.

**One earlier claim was retracted outright.** The chapter had been drafted on the belief that Python clients submit readonly calls as real transactions and only TypeScript simulates them. algokit-utils-py 4.2.3 implements the readonly branch in `_TransactionSender.call` (`applications/app_client.py:1185-1189`, simulate at 1200-1236); the Python/TypeScript difference is ergonomic, not a capability gap. The composer path is the escape hatch — `client.new_group().<method>().send()` bypasses the branch and submits for real — and that fact now lives in the readonly gotcha, framed as a smell rather than a technique.

**Two findings were declined and are recorded here rather than silently dropped.** teaching-pro asked to reorder `default-args` ahead of `readonly-method` inside cluster 5; the cluster's opening paragraph announces its own order honestly and the change would trade one defensible sequence for another, so the order stands. publishing-pro asked for a book-wide normalization of handoff-table separator widths, which is an editorial decision about every chapter rather than about this one, and belongs to the author.

**State at the end of the Chapter 2 slice:** `21 files, 58 examples, 113 anchors, 181 references — 0 errors, 53 warnings` with none attributable to `02-c-contracts.md`, `58 passed, 0 failed, 0 skipped` on the example compile set, 37 passing unit tests, 51 gotchas harvested, and concat, mdbook and PDF all building clean. The chapter's pages were rasterized and read, per the Chapter 1 gate: the ARC-4 layout table's four overfull-hbox warnings are gone, and the router figure's labels match the prose around it.

**Still outstanding in 5a:** Chapters 4, 5, 6, and 7, and the closing edit to the project chapter that ends Part I. The phase is not done, and the honest read on pace is that the review-and-correct cycle dominates, exactly as the Phase 4 note predicted.

#### Phase 5a progress — Chapter 4, data that grows

**Chapter 4 is the box chapter, and its spine is a fact the book had previously stated backwards: box I/O is two independent budgets, and both of them sum across the whole group.** A box reference grants 2,048 bytes at consensus v41, and that allowance is checked twice — once as a read budget charged before the program runs, as the full size of every referenced box that exists whether or not a byte is read, and once as a write budget accumulated in a single running `dirtyBytes` counter as the program mutates. The two are never added to each other, which is why a read-modify-write of one 1,500-byte box fits on one reference. An earlier draft claimed the write budget does not sum across boxes. It does, and it sums across the group as well; the claim was a blocking factual error and it is now sourced to `data/transactions/logic/box.go` in the expert's knowledge base rather than left as prose anybody has to trust.

**The chapter's second correction is about why `box_extract` and `box_replace` exist at all.** They are usually explained as a budget optimization, and they are not: `maxStringSize` is 4,096, so `box_get` and `box_put` cannot touch a box larger than that under any budget, failing with `<op> produced a too big (N) byte-array`. It is a reach limit. The budget benefit is real but secondary, and the derived number that makes the design legible — 32,768 ÷ 2,048 = 16, exactly the v41 `Access` cap — now appears in the text rather than being left for the reader to notice.

**Two parallel agent reviews ran against the drafted chapter, and both returned work.** The walkthrough compiled all twenty-four contracts clean, verified every MBR and budget figure in the prose, and confirmed each protocol constant at v41 — and still found six revisions, one of them blocking. The blocking one is the most instructive: the chapter's elision list for the corrected-guestbook diff named five things and omitted the sixth, the import line, which changes in both directions. A reader reconstructing the fixed contract from the diff alone gets `Name "BoxMap" is not defined` and has no way to know that is the chapter's fault rather than theirs. Transcluded examples cannot drift from their files; a diff plus a hand-written elision list can, and did. That is now a standing verification step in the expert agent, phrased as an instruction to rebuild every diff from the chapter alone and compile it.

**The other five walkthrough findings were all cases of the book printing an error it had never actually seen.** `URLTokenBaseHTTPError` is a JavaScript class and cannot appear in a Python transcript; the type is `AlgodHTTPError`. `algokit_utils.LogicError` does not render as `LogicError: <message>` — it renders as `Txn {id} had error '{message}' at PC {pc} and Source Line {n}:` followed by a TEAL trace, so both transcripts were reformatted to the real shape with the trace elided under an explicit marker, and the chapter says once that it trims to `.message` in prose thereafter. The `fixed_array` example's 34,600-microAlgo total was right but its derivation was invented, describing two 32-byte box names where the boxes are named `b"b"` and by the array itself. `sized_types.py` produced an unannounced `expression result is ignored` warning. And the `assert self.data` before a `.length` call was justified on grounds the compiler already covers — PuyaPy emits its own existence check, so the assertion buys a sentence, not a guard, and now says so.

**The security audit returned eight blocking failures, and how they were answered is the more interesting record.** Six were fixed in code. Every one was the same class of defect: an example stripped down to teach one operation, with no caller check, where the operation spends the *application's* money. `box_raw_sized.allocate` let any stranger convert 13.1 Algo of the contract's balance into an unusable box for the price of one fee, permanently, since `create` on an existing box of a different size fails outright. `boxmap_composite_key` took the season as a caller argument, which is an unbounded box-creation vector wearing a composite key's clothing — the season is now derived from `Global.round`, which preserves the teaching point and removes the vector. `sized_types.reset` destroyed a record for anyone who asked. `box_replace` had no ownership model over a shared packed box, and `box_list_append` had no cap; the latter's `MAX_ENTRIES = 64` is now derived arithmetic — the 2,048-byte write budget over 32-byte entries — rather than a round number, so the log fills with a sentence instead of a budget error.

**Two of the eight were answered in prose rather than in code, deliberately, and this is a decision worth recording rather than burying.** The audit asked that `guestbook_fixed` be rekeyed by `Txn.sender` to enforce one signature per attendee and bound box creation. That is the right fix for a production contract and the wrong fix for this chapter: an `Account` key is 32 bytes, so the MBR becomes 31,700 rather than 22,100, invalidating arithmetic the chapter verifies in four places and a table, and it costs the indexed reads that the whole of Correction three is built around. So the docstring's false promise was retracted — the broken guestbook now says the desk checks names off, not the chain — and the vector, its cost, and its one-line fix are named explicitly in the closing prose. The reader is told the contract does not enforce the rule, why this version does not, and exactly what to change if they are building the real thing. A finding answered honestly in prose is not a finding dropped.

**The eighth, the missing MBR pre-flight across ten single-concept examples, was answered once instead of ten times.** A four-line balance guard in front of a three-line method buries the line the reader is meant to be reading, and adding it everywhere would blow every tier budget in the chapter. One paragraph now says so plainly, immediately after the example that *does* carry the guard: the omission is a presentation choice, not a pattern, every one of those examples needs the guard before it goes near a network anybody cares about, and the corrected guestbook is the form to copy. Where an example omits something for some other reason, it says so on the line.

**Three non-blocking observations were recorded and not acted on.** `guestbook_broken.py`'s `del` on a nonexistent box succeeds silently, which is a small consistency gap against the `retire` discussion. More significantly, `validation/manifest.json` covers `ch04_nft` and nothing from this chapter, so compilation is the only gate the boxes examples pass — and compilation catches none of F1 through F8. That is a coverage gap rather than a chapter defect, and it is the kind of finding the amended publishing-pro rule now insists be reported as such: when a defect is found by hand that a checker could have found, the finding is the missing check.

**The publishing-pro agent file was amended in ten places during this slice, which is the largest change to an agent file since Phase 0.** The substantive ones: cross-references are now documented as this book actually does them — slugs resolved at build time, with `BANNED_REF_RE` hard-blocking the long-form namespaces at `build.py:324` — rather than as generic O'Reilly forms; figure captions are specified as two to three full sentences living in `figures/index.yaml`, table captions as inline noun phrases with no terminal period, and the opposite conventions are explained rather than merely asserted; second person is stated as an absolute with the authorial "we" named as the single most common voice slip, complete with the greps that find it; the house caps are tabulated with their values, their enforcing script, and their check numbers; column widths are documented as coming from separator dash counts, which is why lopsided tables render square; and a new Elision Integrity section codifies the four checks that would have caught the blocking finding above.

**State at the end of the Chapter 4 slice:** `22 files, 86 examples, 147 anchors, 225 references — 0 errors, 52 warnings` with none attributable to `04-c-boxes.md`, `86 passed, 0 failed, 0 skipped` on the example compile set, 37 passing unit tests, 57 gotchas harvested, and concat, mdbook and PDF all building clean. The chapter's pages were rasterized at 110 dpi and read, per the gate established in Chapter 1: the reformatted `LogicError` transcripts, the `AlgodHTTPError` line, the six-item elision paragraph, and the two-currencies table with its proportioned columns all render as intended.

**Still outstanding in 5a:** Chapters 5, 6, and 7, and the closing edit to the project chapter that ends Part I. Creating `06-c-moving-value.md` will let this chapter's `{{ch:moving-value}}` pointer be restored; it is the one deliberate dangling reference left in place.

#### Phase 5a progress — Chapter 5, arithmetic that refuses

**Chapter 5 is the arithmetic and clock chapter, and its spine is that the AVM's characteristic failure is refusal rather than a wrong answer.** There is no float, no negative number, no wraparound and no NaN: a subtraction below zero, a product past 2^64-1 and a division by zero all end the transaction, which means the risk a reader must learn to see is not corruption but a contract that becomes permanently uncallable on a path nobody tested. The chapter's named failure — a vesting calculator that pays nothing for eighty-nine days and then everything at once — carries four defects in nine lines, and the fourth is the one that never aborts, which is exactly what makes it the dangerous one. Three are wrong lines and one is a guard that was never written, and the chapter says so in those terms because the missing guard is both the harder kind to find and the more common kind to ship.

**Two parallel review agents ran against the drafted chapter, both on Opus, and between them they returned six blocking findings.** The most serious was an overflow the chapter had itself invited. `{{ex:linear-vesting}}` computed the release as `(total * (now - start)) // (end - start)`, which is the form every reference implementation uses and which overflows, on the chapter's own ninety-day schedule, for any `total` at or above 6,518,286,428,268 — about six and a half million tokens at six decimals, an ordinary grant. Worse, it overflows only in the back half of the term, so a contract configured with it works, pays out for weeks and then aborts on every call forever. The example is now the wide form, `op.mulw` into `op.divw`, written out in place because one example file does not import another.

**Applying that fix required a reconciliation that was nearly missed and is worth recording.** The narrow expression is quoted in the chapter's prose as the load-bearing line, is one of three implementations Exercise 1 asks the reader to contrast, and is asserted against in the shipped unit test. The resolution was to verify from the anchor map that `{{ex:mul-div}}` already precedes `{{ex:linear-vesting}}` — so the reader has `mulw` and `divw` in hand — then rewrite the prose to name the wide pair as load-bearing and keep the narrow form present as the named-and-rejected alternative, which is precisely what Exercise 1 needs. `vested(1_000_000, 0, 2_830_000, 943_333)` still returns 333,333, so the test needed no change; `vested(7_000_000_000_000, …)` now returns an answer where it previously raised `OverflowError: * overflows`. Exercise 1's premise was also corrected: it said a grant of 250 million tokens at six decimals and then wrote `total` as 250,000,000,000, three orders of magnitude short of its own sentence.

**Two of the findings were about numbers the book asserted without evaluating, which is now a checklist item rather than a habit.** A "comfortably inside sixty-four bits" claim and a "dangerous at 10^12" claim had both survived a full review round while being wrong by two orders of magnitude. The expert agent's pre-completion checklist gained four items in response: evaluate every fits-in-64-bits claim numerically against `MAX_UINT64` and record the threshold in the file; prove the failing opcode is actually reachable in every deliberate-failure example; attribute every transcript to chain or emulator and never use an AVM failure string as an assert message; and fund the MBR, or explicitly scope it out, in every box-creating example.

**The largest knowledge-base correction was a retraction.** The expert agent had recorded that `op.Block.blk_timestamp(Global.round - 1)` "fails intermittently in production." It does not fail intermittently; it never succeeds, anywhere, on the first call, on LocalNet and MainNet alike. The readable window's ceiling is `Txn.first_valid - 1`, and algosdk sets `first_valid` from algod's last **committed** round, so a transaction cannot be included before `first_valid + 1` and `Global.round - 1` is therefore at minimum one round above the ceiling. Any expression built on `Global.round` is the wrong shape for that argument. The correct forms are `Txn.first_valid - 1` or `Txn.first_valid_time`, and the retraction is written into the file as a retraction, with its date, so a future agent recognises the wrong claim rather than re-deriving it.

**Three other facts were nailed down against sources rather than recalled.** AlgoKit Utils' validity window is ten rounds on MainNet and TestNet and one thousand — the protocol maximum — on LocalNet, which is why the `Txn.last_valid`-as-a-clock defect is exercised at full strength by everyone's test suite and passes anyway: the tests assert that a call returned, not that it returned the right number. ARC-21 defines two mandatory methods and two optional search variants, not the four-method interface the agent file had claimed, and it says nothing at all about publication cadence, retention or value width — those are properties of a deployment, and the chapter now draws that boundary. And the emulator diverges from the chain on five arithmetic cases rather than four, because `//` by zero and `%` by zero both collapse into a plain CPython `ZeroDivisionError` in `algopy_testing`; a `pytest.raises` test therefore passes, which means a "failing test run" transcript for one of those cases depicts a run that does not happen.

**The security audit's remaining findings were all bounds that were assumed rather than enforced.** `commit_reveal` committed to a future round with a floor on the lead and no ceiling, so a caller could name a round beyond the beacon's retention and strand the draw; it now carries `MAX_LEAD_ROUNDS`. `rate_limit` used `maybe()`'s default of zero as a stand-in for "never called", which collides with the real value round zero and refuses every new account until round 100 with a message that is a lie — the guard now sits inside the `if seen` branch. The invariant behind the commit-reveal ordering is stated in one sentence rather than left implicit: the target round must not yet exist when the last entry is accepted.

**Two findings were deliberately not applied as written, and both deviations are structural rather than editorial.** The walkthrough asked for a context line in the Mini-Build diff to disambiguate where the new `configure` guard lands; adding it makes the diff sixteen lines and §2.4 caps it at fifteen. The elision list is the designed mechanism for what a diff cannot show, so the disambiguation went there instead. The security audit asked for a comment in `commit_reveal.ready()` noting that it does not check beacon retention; after `MAX_LEAD_ROUNDS` and its assert, the file sits at exactly the thirty-five-line Core tier budget and there was no room. That one is recorded as an unapplied non-blocking finding rather than quietly absorbed.

**The chapter's forward references follow Chapter 3's precedent and are a debt, not a decision.** A `{{ch:}}` pointer to a chapter that does not exist yet is a hard build failure, not a warning — `build.py concat` exits non-zero on it — so the two pointers to `moving-value` and the two to `pricing-math` are written in prose. The moving-value pair comes back the moment `06-c-moving-value.md` lands, which is the next slice; the pricing-math pair waits for Part II. This is now the second slice to incur that debt and the mechanism should be recorded plainly: the reference cannot be written early, so the chapter that lands later must go back for it.

**State at the end of the Chapter 5 slice:** `23 files, 108 examples, 171 anchors, 259 references — 0 errors, 52 warnings`, with none of the warnings attributable to `05-c-numbers-and-time.md`; `108 passed, 0 failed, 0 skipped` on the example compile set; 37 passing unit tests in `tests/` plus 6 in `examples/ch05_numbers_time/`; 62 gotchas harvested, five of them new from this chapter; and concat, mdbook and PDF all building clean. The chapter's pages were rasterized and read per the gate established in Chapter 1: the four-clocks anchor diagram, the fifteen-line corrected diff with its seven-item elision paragraph, and the rate-limit sentinel discussion all render as intended.

### Phase 6 — Finish

The Example Finder, a real index, the Foreword, "How to Use This Book," the mastery checkpoints, and the typographic concept/project treatment.

Also the three missing project directories, which the manifest has been reporting as absent since Phase 0 and which are now in scope rather than conditional (§10 gap 3). They are not equal in cost and should not be scheduled as though they are:

| Directory | Contents | Cost |
|---|---|---|
| `projects/chapter9/limit-order-book` | Contract, deploy script, **and a keeper bot** — a limit-order book that nobody matches orders on cannot be demonstrated at all, so the off-chain half is not optional here | Medium |
| `projects/chapter10/zk-voting` | Groth16 verifier, committed circuit artifacts, proving and verifying keys, a proof-generation script | **High** — the most expensive single item in Phase 6, and the one most likely to be deferred |
| `projects/chapter22` | Acceptance tests only, **no implementation** (§15.8): `test_universal.py` plus three per-direction suites | Medium, and the most reusable artifact in the book |

Then Chapter 22 itself, written last because check 11 can only run once every concept chapter's examples exist to resolve against.

If Phase 6 has to be cut short, cut the ZK directory first and ship Chapter 20 with a pointer to an external reference implementation. Do not cut `projects/chapter22` — the capstone chapter without its harness is a specification with no way to check whether you met it.

---

## 13. Risks and open decisions

### 13.1 The three real risks

**The on-ramp is seven chapters long.** ~118 pages before the first project, one chapter longer than the earlier draft because Moving Value had to come before the vesting project rather than after it (§3.1). This is the plan's biggest bet, and §4.2 explains why every reordering fix is worse. The mitigation is already built in — seven deployable Mini-Builds, a deliberately tiny Chapter 1, and Chapter 7 ending on the junior version of the vesting contract itself, payout inner transaction included. The measurement comes from Phase 4. If it reads long, **demote Core examples to Extended; do not reorder.** Demotion is a local edit; reordering reintroduces the ordering error that motivated the whole restructure.

**The Core/Extended boundary is a judgment call.** 157/79 is derived from the tier rules of §2.3, not from data. It directly sets the page count (~130 pages of examples under the completeness budgets), so getting it wrong in the pessimistic direction produces a 600-page book. The tier field lives in the manifest, so re-tiering is a metadata change, not a rewrite — which is the point of putting it there.

**Effort is dominated by the 94 new examples, and the Completeness Contract raised the floor on all 236.** Of the 236, **104 already exist as working code** and need re-cutting and re-framing, not authoring; **38 exist as prose** and need code written to match claims already made; **94 are new** and need to be written, compiled, and verified. The first 104 are cheap and low-risk *as prose*, but no longer cheap as artifacts: every one of them must now become a complete file in `examples/` with a mode and, for `unit` mode, a test — so the "re-cutting" bucket carries real work it did not carry in the earlier draft. The 94 are still the actual project. Any effort estimate that treats all 236 alike will be wrong by a factor of two.

### 13.2 Decisions taken

You answered the four open questions; here is what each one changed.

**1. Seven concept chapters before the first project is acceptable — conditional on complete, buildable examples throughout.** The condition is the larger half of the answer and it is now §2.1's Completeness Contract. Consequences, all live in this document: the tier budgets moved from ≤20/≤12 lines to **≤35/≤20**, because 11 lines is the measured floor for a program containing nothing and the old Extended budget was below it; per-example page costs rose from ~0.55/~0.25 to ~0.65/~0.35, taking the book from ~484 to **~508 pages**; `examples/` becomes a real package of roughly 470 files (§11.2); `validate.py` gains an `--examples` target and three checks (§11.3); Phase 0 grows the harness (§12); and the 38-example cookbook split target in §7.1 becomes a ceiling to re-check rather than a number to hit, because a split now costs four complete programs instead of four fragments.

  The one thing this does *not* change is the on-ramp length. Seven chapters stands, and the remedy if Phase 4 says it reads long is still demotion, never reordering (§13.1).

**2. The capstone is in scope and is now specified in full — §15.** Three deliverables, of which the load-bearing one is **assertion coverage** rather than line coverage; three directions (streaming subscriptions, sealed-bid commit–reveal auction, multisig treasury with a spending policy) each drawing on four-plus chapters across three-plus Parts and each with one genuinely hard part the book has not solved; a six-dimension self-administered rubric; the adversary test (write the exploit before the fix); a de-scoping ladder so a stalled reader drops a rung instead of quitting; and an acceptance harness that ships tests with **no reference implementation**. The hard constraint — no new Algorand surface — is enforced by check 11, not by good intentions.

**3. Every project chapter gets a project directory.** Three get created in Phase 6: `projects/chapter9/limit-order-book`, `projects/chapter10/zk-voting`, and `projects/chapter22`. They keep the existing old-number directory scheme and the manifest carries the mapping, so no path in any existing README, script, or test breaks. §12 Phase 6 prices them individually and says which to cut first if effort runs out (the ZK one) and which never to cut (the capstone harness).

**4. Author line and title page are out of scope.** Struck from §10 gap 5 and from §11.5's PDF list, which drops from six items to five. The cover stays the first page and `author:` stays as it is. Everything else in the editorial-debt list — the copyright page, the reading paths, the index, the lists of figures and tables — stands, since none of those were what you ruled out.

### 13.3 If effort is constrained — each agent's shortlist

**teaching-pro, in order:** diagrams 1–6 → the Mini-Build in every concept chapter → `## Retrieval` with 40% interleaving from earlier chapters → a `## Reading a Failure` section (debugging is taught nowhere in the book, the largest *skill* gap) → fix the ch03/ch04 exercise-scaffolding inversion and cap code blocks at 50 lines → the `## Handoff` tables.

**publishing-pro, in order:** (1) convert chapter references to `{{ch:slug}}` and stand up the xref resolver; (2) ship the diagram pipeline; (3) number the 27 unnumbered tables; (4) build Chapter 3 as the pilot.

They agree on the essentials and the overlap is the answer: **if only two things happen, make them the xref conversion and the diagrams.** The first makes everything else affordable; the second is the largest unclaimed pedagogical gain in the book, and neither one requires committing to the restructure at all.
---

## 14. The verification pass — what the plan got wrong before you read it

A first version of this plan proposed 237 examples across 21 chapters. Before delivering it, I ran it back through two of the three agents as adversarial reviewers, with the plan itself as the artifact under review rather than the book. They found enough to change the structure, so the audit is recorded here rather than quietly absorbed — partly because it is evidence about how much to trust the remaining numbers, and partly because two of the corrections are the most load-bearing decisions in the document.

### 14.1 The three structural changes

**Moving Value moved in front of the vesting project.** This is the largest single correction and it came from teaching-pro applying the plan's own §3.1 rule to the plan itself: *"if those needs come after the project, the project has to re-teach them, which is exactly the defect the restructure exists to remove."* The v1 order put N3 — the application account, inner payments, `fee=UInt64(0)`, ASA opt-in, sending an ASA — *after* Chapter 7's vesting project. A vesting contract's terminal act is an inner asset transfer, so v1 committed the exact error it had already caught once for time and math, at roughly four times the volume.

It also silently broke §4.2's load-bearing mitigation. That section claimed the last concept chapter before the project ended in a junior version of the vesting contract; in v1 that chapter had no inner transaction, no ASA, and no application account. teaching-pro's phrasing: *"a vesting contract that never pays out is not a junior version of a vesting contract; it is a timer."* Moving N3 to Chapter 6 makes Chapter 7's Mini-Build genuinely buildable and costs one chapter of on-ramp, which §13.1 now prices honestly.

**The AMM got a concept chapter.** v1 kept all of N9 in one early chapter, seven chapters upstream of the pool that needs it, which left the most math-dense project in the book as the only project with no concept chapter in front of it. Splitting N9 into vesting arithmetic (Chapter 5) and pricing math (Chapter 12) fixed that and incidentally gave homes to two pieces of §8.1 material — impermanent loss and client-side quoting — that v1 had marked for removal without saying where they landed.

**The catalog was rebalanced twice.** The first regeneration under the new chapter map put 37 examples in the box chapter and 7 in the pricing chapter. The per-chapter cap in §2.3 exists because of that failure; after a second pass the spread is 8–26 with most chapters at 13–22.

### 14.2 Six technical claims that were false

algorand-expert caught these in the v1 catalog. Each would have shipped as a confidently-worded example.

| Claim in v1 | Correction |
|---|---|
| `op.sumhash512` is available | AVM **v13**; not callable on MainNet at consensus v41. Deleted from the catalog. |
| Opcode budget pools across the transaction group | It pools across the **app call** transactions in the group. *Fees* pool across the whole group. Two different mechanisms, and v1 merged them. |
| `ec_pairing_check` requires a LogicSig | It does not. It is available to applications; the constraint is budget, not program type. |
| The LogicSig budget is a flat 20,000 | 20,000 **per program**, pooling to `len(group) × 20,000` since consensus v39. Without this the Chapter 20 ZK verifier reads as arithmetically impossible. |
| A clear-state program always succeeds | It can fail. The account's local state is removed either way — which is the actual danger, and a more interesting one. |
| `resource_encoding="index"` is the puya 5.x default | `"value"` is the 5.0 default; `"index"` is the opt-out that restores 4.x selectors. |

The fourth and fifth of these were load-bearing on danger-list items, which is why the list was rebuilt rather than patched.

### 14.3 The danger list was wrong in both directions

Two items were not exploitable and five real classes were missing; §6 carries the details. The principle the rebuild enforced: the list's authority comes entirely from every item being genuinely exploitable, so a compile error sitting on it (the missing `.copy()`) costs more credibility than it buys safety.

The most consequential addition is unauthorized `UpdateApplication`/`DeleteApplication`, which subsumes every other item on the list — an attacker who can replace your bytecode does not need any of the other twenty-two.

### 14.4 What I did not adopt

**A shorter on-ramp.** Both reviewers noted seven concept chapters before the first project is long. Neither produced an ordering that was better, and §4.2 records both rejected alternatives. The remedy stays demotion rather than reordering, and Phase 4 is where the question gets answered with a measurement instead of an argument.

**Splitting the box chapter.** At 26 examples Chapter 4 is the heaviest in the book, and the obvious fix is to split it. I did not, because the split lands between "boxes" and "box MBR arithmetic," and separating a storage mechanism from its cost model is how the current book produced the confusion this plan is trying to remove. It carries the cap instead, and if it breaks in drafting, the box-sizing cluster demotes to Extended.

**Merging the two adjacent Part III projects.** The factory and the farm are one protocol and one narrative; §4.3 explains why the missing concept chapter between them is deliberate and how Chapter 14's two Handoff tables cover it.

### 14.5 What is still soft

Three numbers in this plan are derived rather than measured, and you should read them as estimates: the Core/Extended split (157/79, §2.3), the page arithmetic that follows from it (~508, §2.3), and the 20–35% prose reduction in the project chapters (§8.1), which is the least defensible of the three because it was estimated from reading section headings rather than from doing the cut. Phase 4 produces real numbers for the first two. The third only resolves when a project chapter is actually edited, which is the closing step of each Phase 5 sub-phase.

One number that *is* measured, and is worth separating from the three above: the Completeness Contract's line budgets. §2.1's 11-line floor and 11–15-line typical case come from five complete probe programs written and compiled under puyapy 5.9.0 against AVM v12, plus one 13-line pytest file that runs and passes and two `compile-fail` probes that fail with the declared message. The budgets in §2.3 are set from those measurements rather than from judgment, which is why they are the only quantitative claim in this document I would defend without a pilot.

The example catalog itself is the most reliable part of the document: 104 of the 236 entries point at code that exists in the repository today, and those were checked against it.
---

## 15. The capstone, specified

You asked me to elaborate on Chapter 22. This section is that elaboration, and it is written at implementation depth because the capstone is the one chapter whose failure mode is invisible until it ships: a capstone that is secretly just an eighth project teaches nothing new, and a capstone that is a blank page with the word "good luck" on it teaches nothing at all. The distance between those two failures is narrow and the whole design lives inside it.

### 15.1 Why a capstone, and why nothing in it is new

By the end of Chapter 21 the reader has built seven contracts. Every one of them was built from a specification I wrote, with my solution on the following page. That is Bloom's Apply and Analyze, exhaustively. It is not Create, and the gap between "I can follow a well-written spec for a vesting contract" and "I can look at a business problem and decide what goes in a box" is the gap where most self-taught smart-contract developers actually stall — not on syntax, and not on any individual mechanic, but on the layout decision that comes before either.

Transfer is the only real test of the preceding 21 chapters, and transfer requires a problem the book did not solve first.

**The hard constraint that makes this work: the capstone introduces no new Algorand surface.** Not one opcode, not one storage primitive, not one lifecycle operation that has not already appeared as a numbered example with its own slot in the catalog. This is what separates a capstone from a twenty-second chapter of content. Everything the reader needs, they have already read, run, and — because of the Completeness Contract — compiled.

That constraint is enforced mechanically, not by good intentions. §11.3 gains a validation: **every mechanic named anywhere in Chapter 22 must resolve to an existing `{{ex:}}` slug.** If drafting the capstone reveals a mechanic with no example behind it, the correct response is to add the example to the right concept chapter, not to explain it in Chapter 22. The check will fail until you do.

### 15.2 The shape of the chapter

Chapter 22 is roughly 14 pages and it is a **specification and a rubric, not a tutorial**. The only code in the entire chapter is the acceptance-harness skeleton in §15.8. This is deliberate and it is the first thing a reader will notice, which is why the chapter opens by saying so.

```markdown
# Chapter 22. Capstone: Build Something Nobody Told You To Build

## What This Chapter Is Not      ½ page — there is no solution, and why
## The Contract With Yourself    the three deliverables (§15.3)
## Choosing                      three directions + bring-your-own (§15.4)
## The Rubric                    six dimensions, self-administered (§15.5)
## The Adversary Test            write the exploit before the fix (§15.6)
## When You Get Stuck            the de-scoping ladder (§15.7)
## Acceptance Harness            the only code in the chapter (§15.8)
## What "Done" Looks Like        ½ page
```

There is no `## Before You Continue`, and it is the only chapter in the book without one. Every other chapter closes by asking the reader to confirm they absorbed what I told them. This one closes by asking them to judge their own work against a rubric, which is the same instrument aimed the other direction — and putting my five testable claims after it would undercut the entire point of the chapter in about forty words.

### 15.3 The three deliverables

The reader is asked for exactly three artifacts, and the second is the one that matters:

**1. A contract that compiles under the pinned toolchain.** The `pyproject.toml` from `examples/` is reused verbatim, so "it compiles" means the same thing in Chapter 22 that it meant in Chapter 2.

**2. A test suite in which every `assert` in the contract has a test that triggers it.** Not line coverage. Not branch coverage. **Assertion coverage**: for each `assert` in the contract, a test exists that makes that specific assertion fail and confirms the transaction is rejected. This is the single most transferable habit the book can leave a reader with, and it is stated here rather than in Chapter 7 because Chapter 7 can only demonstrate it on my contract, where the asserts are ones I chose. On the reader's own contract, applying the rule forces the question *why is this assert here* on every line that has one — and the asserts that turn out to be untriggerable are, without exception, either dead code or a misunderstanding of the AVM. Both are worth finding.

**3. A one-page prose threat model.** Who can call each method. What each one assumes about the group it arrives in. What happens if that assumption is false. Prose, not a table — a table lets the reader fill cells without thinking, and the whole exercise is the thinking.

### 15.4 The three directions

Each direction is roughly 150–300 lines of contract, draws on **at least four concept chapters across at least three Parts**, and has one genuinely hard part that the book has not solved anywhere. That last property is what makes it a capstone; the reader will get all the way to it on competence and then have to design.

**A. Streaming subscriptions.** A contract where a subscriber funds a stream and a recipient withdraws continuously-accrued value, with either party able to stop it.

| Draws on | For |
|---|---|
| Ch 4 (boxes) | one box per subscriber, keyed by address |
| Ch 5 (numbers and time) | elapsed-time accrual, and the rounding decision |
| Ch 6 (moving value) | the inner payment, and the opt-in gate |
| Ch 9 (authorization) | who may cancel, and can both parties? |
| Ch 10 (MBR and fees) | who pays the box MBR and who reclaims it |
| Ch 21 (shipping) | who may update or delete a contract that is holding a stranger's balance |

*The hard part:* cancellation mid-period. The reader must decide whether a partial period accrues, who eats the rounding dust, and — the part that catches almost everyone — what happens to the stream's box when the balance reaches exactly zero at the same moment the subscriber cancels. There is no correct answer in the book because there is no single correct answer; there is only a decision the reader has to make explicitly and then defend in their threat model.

**B. Sealed-bid auction with commit–reveal.** Bidders commit to a hashed bid, reveal after the window closes, highest revealed bid wins.

| Draws on | For |
|---|---|
| Ch 19 (cryptography) | hash commitments, and why the bidder's address must be inside the preimage |
| Ch 4 (boxes) | one box per bid |
| Ch 5 (numbers and time) | two windows, and what "closed" means at a boundary |
| Ch 6 (moving value) | ASA settlement to the winner |
| Ch 10 (MBR and fees) | refunding losers — to the *funder*, which is danger item 9 |

*The hard part:* the bidder who commits and never reveals. Their deposit is locked, their box is occupying MBR the contract paid for, and any sweep mechanism the reader designs has to not become a way to censor a legitimate reveal that arrives one round late. Every naive design here is either a griefing vector or a fund lock, and discovering that on your own is worth more than reading about it.

**C. Multisig treasury with a spending policy.** *N*-of-*M* approval, plus per-period spending caps by asset.

| Draws on | For |
|---|---|
| Ch 17 (LogicSigs) | delegated signing and the seven mandatory checks |
| Ch 6 and Ch 9 | group validation, and validating group *size* (danger item 20) |
| Ch 5 (numbers and time) | rate-limit windows, and what happens across a window boundary |
| Ch 21 (shipping) | danger item 19 — who may update or delete this thing |

*The hard part:* changing the policy without creating a backdoor. A policy that can be changed by the same *N*-of-*M* that spends is a policy that can be changed to 1-of-*M* by *N* signers and then drained by one. A policy that cannot be changed at all is a contract that cannot survive a lost key. The reader has to build the middle, and the middle involves a time delay they have to reason about themselves.

**Bring your own,** subject to one condition: the reader must name the four source chapters before writing a line. If they cannot name four, the project is too small; if they can name eleven, it is too big and §15.7 applies. This condition is the whole guardrail, and it works because naming the chapters requires having already decided the data layout.

### 15.5 The rubric

Six dimensions, self-administered, with an *adequate* and a *solid* band. There is no numeric score — a score invites optimizing the number, and this instrument exists to direct attention, not to grade.

| Dimension | Adequate | Solid |
|---|---|---|
| **Correctness** | The happy path works on LocalNet | Every method has a test that makes it fail for the right reason |
| **Safety** | You ran the danger list against your contract | You found something, fixed it, and kept the test that catches it |
| **Resource discipline** | It does not run out of budget | You know your MBR to the microalgo and who paid it |
| **Failure behavior** | Failures reject rather than corrupt | No failure can permanently lock funds, including yours |
| **Legibility** | Methods are named for what they do | A reader can find the authorization check on every method without searching |
| **Lifecycle** | It can be deployed | Update and delete are gated, or explicitly disabled, and you can say which and why |

The Safety row's *solid* band is phrased the way it is on purpose. **If you ran the twenty-three-item danger list against 250 lines of your own first-ever independent contract and found nothing, you ran it wrong.** Every first draft has at least one. The rubric says so out loud because a reader who scores themselves *solid* on an empty finding has learned the opposite of the intended lesson.

### 15.6 The adversary test

One instruction, and it inverts the reader's instinct:

> When you find a vulnerability, do not fix it. **Write the exploit first**, as a failing test named `test_attack_<what>`, and watch it succeed against your contract. Then fix it, and watch the same test fail.

This is the habit that separates people who have read about security from people who do it. A fix applied without a reproduction is a fix you cannot prove and cannot keep — six months later someone refactors it away and nothing catches them.

The chapter seeds three attacks that work against almost every first draft, so the reader's first `test_attack_` is one they were handed rather than one they had to imagine:

1. **Call every method as an account that should not be allowed to.** Not just the obvious admin ones — every method. The one that gets people is the method that seemed harmless.
2. **Append one extra transaction to the group.** Most first drafts validate the transaction at index 0 and never check `Global.group_size`. Danger item 20.
3. **Pass the same asset twice where two distinct assets are expected.** Danger item 21, and the same class of bug as the Tinyman V1 exploit.

Each of the three points at the numbered example that explains the mechanic, so a reader who does not immediately see why the attack works has a two-page trip rather than a search.

### 15.7 When you get stuck: the de-scoping ladder

The realistic failure mode of a capstone is not a wrong answer, it is abandonment — the reader stalls at 70%, the project sits, and the book ends on a failure the reader attributes to themselves. So each direction ships three rungs, and the chapter tells the reader in advance that dropping a rung is a normal move rather than a defeat:

| Direction | Minimum | Spec | Stretch |
|---|---|---|---|
| **A. Streaming** | One stream, ALGO only, no cancellation | Many streams, ASA support, either party cancels | Multiple recipients, transferable stream position |
| **B. Auction** | One item, ALGO bids, no-reveal forfeits deposit | ASA settlement, reveal window, loser refunds | Multiple concurrent auctions, second-price settlement |
| **C. Treasury** | 2-of-3, fixed policy, ALGO only | *N*-of-*M*, per-asset caps, time-delayed policy change | Delegated LogicSig spending under the cap |

The **minimum** rung is genuinely complete — it deploys, it works, it can be tested and defended against the rubric. A reader who finishes the minimum rung has done the thing the capstone exists for.

And one diagnostic, which is the most useful sentence in the section:

> **If you don't know where to start, you are missing a data-layout decision, not a code idea. Draw the boxes first.** What is one box? What is its key? What is in it? Who pays for it and who gets that payment back? You cannot write a line of this until those four answers exist, and once they exist most of the contract writes itself.

### 15.8 `projects/chapter22/` — acceptance tests, no implementation

The capstone gets a project directory like every other project chapter (§10 gap 3), but it contains **no contract**. Shipping a reference implementation would convert the capstone into the eighth project overnight — the reader would read it, and everything above would be theater.

What it contains instead is an acceptance harness written **against an ARC-56 interface rather than an implementation**. It takes an app id, reads the ARC-56 JSON the reader's own build emitted, and asserts on behavior:

```python
# projects/chapter22/tests/conftest.py  (skeleton — the chapter's only code)

@pytest.fixture(scope="session")
def app_id(request) -> int:
    """Your app id. Pass with: pytest --app-id=1234"""
    return int(request.config.getoption("--app-id"))


@pytest.fixture(scope="session")
def spec(request) -> ApplicationSpecification:
    """Your ARC-56 spec, emitted by your own build."""
    return ApplicationSpecification.from_json(
        Path(request.config.getoption("--arc56")).read_text()
    )
```

Three per-direction suites (`test_streaming.py`, `test_auction.py`, `test_treasury.py`) assert the behaviors the specs promise, so a reader who took direction A gets a real pass/fail on direction A's semantics without ever being shown direction A's code.

And one shared suite, `test_universal.py`, which runs against **any** submission including bring-your-own:

1. Every creator-only method rejects a non-creator.
2. `UpdateApplication` and `DeleteApplication` are gated, or unreachable by route, or refused via `RejectVersion`.
3. Every method rejects an unexpected extra transaction appended to its group.
4. Every inner transaction sets `fee=UInt64(0)`.
5. Box MBR is refunded to the account that funded it, not to `Txn.sender`.
6. No method succeeds when a resource is passed twice where two distinct resources are expected.

That list is the danger list, executable. It is the most reusable artifact in the entire book: it is not specific to the capstone, not specific to any of the three directions, and not specific to this book — it runs against any Algorand application with an ARC-56 spec. A reader who takes nothing else from Chapter 22 and keeps only `test_universal.py` has gotten their money's worth, and the chapter says that in as many words.

### 15.9 What this costs to build

| Item | Effort |
|---|---|
| Chapter 22 prose | ~14 pages, no new technical research |
| `test_universal.py` | The six checks, generic over ARC-56 — the bulk of the work |
| Three per-direction suites | ~150 lines each, written against the specs above |
| The `{{ex:}}` resolution check (§11.3) | Small, but it will fail on the first run and that is its job |

No reference implementations, which is what keeps this the cheapest chapter in the plan to build and the most expensive one to get wrong.
