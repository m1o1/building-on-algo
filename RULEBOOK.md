# Building on Algorand — Authoring Rulebook

Three rule sets, distilled from the comparative analysis of both manuscripts (see
`BOOK-PLAN.md`). Every rule exists because one of the two books either violated it
and paid for it, or followed it and visibly benefited. Rules are numbered for
citation in reviews (e.g., "this section violates PED-1").

**Enforcement tags.** [GEN] — guaranteed by generation from a single source of
truth; the rule cannot be violated without breaking the build. [CI] — mechanically
checkable per commit; add a linter. [REVIEW] — requires editorial judgment; belongs
on the chapter-review checklist.

**How to use.** A new or revised chapter gates through PED (design), then PUB
(production), then ALG (domain review). A rule that blocks good writing in a
specific place may be broken deliberately — but the text must acknowledge the
break the way book 2 does ("Nothing here changes the guestbook"), and the review
must record it. Silent violations are the only forbidden kind.

---

## Part 1 — Publishing (PUB): the manuscript as an artifact

**PUB-1. Every listing the reader is meant to learn from is a numbered example
with a declared CI mode** (`compile`, `compile-fail`, `unit`, `script`,
`localnet`) and compiles or runs on every commit. No load-bearing unnumbered
code. [GEN]
*Origin: book 2's example system; the defect class it prevents is book 1's
pseudo-tests.*

**PUB-2. Every chapter ends runnable.** No outline tests, no undefined helpers,
no "left as an exercise" scaffolding in the main path. If the chapter builds it,
the reader can run it. [CI]
*Origin: book 1's vesting/AMM/factory/farming test outlines and LOB keeper
skeletons.*

**PUB-3. A repair diff is always followed by the complete corrected listing** (or
an explicit pointer to its numbered example). Never require the reader to
reassemble a program from a diff plus prose. [CI — every diff block must be
followed by a listing reference]
*Origin: book 2's diff-narration passages (ch4, ch5).*

**PUB-4. "Run It First" is ≤ ~30 lines of commands, a checkpoint table, and
prediction prompts.** It is a demo with predictions, never a second tutorial, and
never uses machinery the chapter hasn't taught unless behind a "plumbing, not
ideas" label. [REVIEW]
*Origin: book 1's 180–430-line Run It First walls; the factory chapter's verbatim
repeat of the AMM workflow.*

**PUB-5. One client style** (typed clients) throughout. Raw SDK appears only
where field-level control is itself the lesson (LogicSig groups), and is labeled
as the exception when it does. [REVIEW]
*Origin: two client dialects inside book 1's AMM chapter.*

**PUB-6. Chapter numbers, project/example paths, "next chapter" sentences, recap
anchors, and part blurbs are generated from the spine** and drift-checked. A
renumbering can never leave residue. [GEN]
*Origin: book 2's stale `projects/chapterN/` paths, the wrong next-chapter
pointer (8869), the mis-anchored ZK recap (21062), the What's-Next recap that
omits its own Lottery project (24148).*

**PUB-7. Gotcha format:** bolded one-line rule, then ≤ ~120 words, one idea per
gotcha. The consolidated appendix is generated from the inline callouts; every
entry must stand alone out of chapter context; no near-duplicate entries across
topics. [GEN for collection; CI for length; REVIEW for standalone-ness]
*Origin: the 350–400-word mega-gotcha slabs (5546, 7493); the twin and
non-standalone appendix entries.*

**PUB-8. Reference material lives at point of need or in an appendix — never as
a mid-arc chapter.** Decision tables (box vs BoxMap vs local state) appear inline
where the decision is made; the Example Finder is the single lookup surface; no
Patterns or Cookbook chapter may interrupt the build arc. [REVIEW]
*Origin: book 1's Patterns chapter — 70% review, and its one new construct
(LogicSig) used before taught.*

**PUB-9. Aphorism budget: about one per section, not one per paragraph.** Keep
the chapter-thesis lines ("statistics may walk away; liabilities may not");
delete the rest. The style is a spice, not a sauce. [REVIEW]
*Origin: book 2's density diluting its own best lines.*

**PUB-10. No paragraph carries more than one mechanism.** Enumerations of costs,
guards, or steps become lists or tables past three items. [REVIEW]
*Origin: the 9269-style overload paragraphs; the spendable-balance wall.*

**PUB-11. Exercises make one demand per lettered item** and carry their ladder
rung label (Trace / Parsons / Debug / Compare / Extend). [CI for labels; REVIEW
for scope]
*Origin: book 2's four-demands-in-one exercises (2275–2285, 2291, 3128).*

**PUB-12. Conventions are explained beside their first use**, not in front
matter. Front matter tells the reader how to read the book, not how to parse
error-message ellipses they haven't seen yet. [REVIEW]
*Origin: the Preface conventions wall (431–433).*

**PUB-13. Apparatus is printed where it is used.** Mastery Checkpoints at part
boundaries, not pointed to in back matter; Handoff tables at chapter ends; the
receiving "What You Need First" table at project starts — both sides must exist
or neither. [CI — a Handoff without a receiving table fails the build]
*Origin: book 2's dangling Handoffs into LOB and ZK Voting.*

**PUB-14. A promise the book makes about itself is a test the repo runs.**
"Nothing is used before the chapter that introduces it," "a project chapter
re-teaches nothing," "every example compiles" — each such sentence in front
matter must name (in a build manifest, not in prose) the check that enforces it,
or be cut. [GEN]
*Origin: book 2's line 549 promise, falsified by its own first runnable command.*

**PUB-15. Case studies are anchored:** a real incident cited with date, amount,
root cause, and the lesson in one paragraph. Unanchored scare stories are cut.
[REVIEW]
*Origin: the Tinyman V1 treatment (book 1, 5973–5979) — the model.*

---

## Part 2 — Pedagogy (PED): how anything is taught

**PED-1. Goal before problem — the chapter-opening contract.** Every concept
chapter opens in this fixed order: (a) **bridge** from the previous chapter's
ceiling; (b) **commission** — what *the reader* builds this chapter, as a 3–5
item requirement spec; (c) **objectives** — the "by the end" list; (d) **first
attempt** — the naive version of the reader's own build. Failure material may
not precede the commission. [CI — objectives block must precede the first
failure transcript; REVIEW for the rest]
*Origin: the owner's core critique — book 2 explains a problem happening before
saying what is being attempted (ch1: incident at 628, objectives at 658, build
at 668).*

**PED-2. Broken-first, reader-owned.** The first listing is the reader's own
plausible first pass at the stated spec — "the way anyone coming from Python
would write it" — never an anonymous team's shipped disaster. Concepts are
taught as diagnosis of failures the reader has watched happen; the chapter ends
by re-running the repaired build against the opening spec, which doubles as the
acceptance list. [REVIEW]
*Origin: book 2's broken-first template (its greatest strength) minus its
spectator framing (its flow defect).*

**PED-3. Prediction before revelation.** Before each reveal the reader commits
to a specific, checkable prediction in writing ("N of these decisions are wrong
— mark them"). A prediction the reader had to commit to is what makes the
correction stick. [REVIEW]
*Origin: book 2's Predict prompts and its own stated rationale (571).*

**PED-4. War stories are consequences, not introductions.** Third-party incident
narratives appear after the reader has seen and predicted on the code, framed as
"ship this and six weeks later..." They may never carry untaught mechanics as
load-bearing plot. [REVIEW]
*Origin: the ch3 ClearState story using close-out semantics before any teaching.*

**PED-5. No cliffhangers across section boundaries.** A withheld reveal resolves
within the section that poses it. Curiosity comes from the reader's committed
prediction, not the narrator's withholding. [REVIEW]
*Origin: the four-accounts riddle (626→782); ch2's 640-line suspense
(1349→1988).*

**PED-6. Concept chapters own "what is X"; projects own "why X here."** A
project recaps by citing example numbers ("that is Example 3-7 being paid for
rather than described") and may never re-teach. The delta-recap (ZK Voting's
Part 1 style) is the ceiling for retained primers; a from-zero primer after a
concept chapter is a build failure. [REVIEW; CI can flag re-defined terms]
*Origin: book 1's projects carrying 40–50% "what is X" prose; book 2's LOB
retaining a full LogicSig primer after an entire LogicSig chapter.*

**PED-7. Just-in-time placement.** A concept chapter sits immediately before the
first project that consumes it. If a concept is deliberately deferred past a
project that could have used it, the text says so and says why ("Chapter 4 said
a box costs minimum balance and moved on... Each left an invoice on the
table"). [REVIEW]
*Origin: book 2's ch9/ch10 engineered deferrals — the model.*

**PED-8. Concepts compound; debts are named when paid.** Each chapter opens on
the previous one's ceiling, and a rule planted early is explicitly redeemed
("That was never a fact about balances; it was this chapter's one arithmetic
rule arriving early"). A concept taught and never spent is cut. [REVIEW]

**PED-9. WHY before HOW, or say why not.** Every mechanism gets a felt problem
before its API. A section that does not serve the running example must say so in
its first paragraph and name the chapter that needs it — or move there. [REVIEW]
*Origin: book 2's honest "Nothing here changes the guestbook" (4146) — honesty
kept the trust; the section still moved.*

**PED-10. Small-yet-complete, then assembly.** One running example per concept
chapter: minimal, deployable, motivated by a witnessed failure. A project
chapter is the assembly of taught parts and should be able to truthfully claim
"almost nothing here is new" — and when a project extends a previous one, it
opens with an explicit delta list and builds as the delta, not from scratch.
[REVIEW]
*Origin: book 2's ch8 claim (7643); its missed delta-build from ch7's contract;
book 1's NFT-chapter delta list (3378–3384).*

**PED-11. Runnable payoff cadence.** At least one mid-chapter compile/deploy
checkpoint per chapter; every failure and every fix shows its transcript. A
chapter section that adds three or more methods with no run in between is
over budget. [REVIEW]
*Origin: book 1's AMM two-checkpoint cadence (the model); its factory chapter's
zero checkpoints (the defect); book 2 ch8's blind stretch after `claim`.*

**PED-12. Retrieval reaches only backward, at least two chapters back when
possible.** Never quiz the reader on a chapter they haven't read. [CI —
retrieval questions carry chapter tags]
*Origin: book 2's Retrieval questions citing Chapter 7 from Chapters 3–5.*

**PED-13. The exercise ladder ends in a designed productive failure.** The final
exercise asks for something the current chapter cannot quite do; the next
chapter's Handoff closes the loop by naming it ("You wrote down what the
contract must verify... Which of your checks does the project actually make?").
[REVIEW]
*Origin: book 2's Exercise-5 → Handoff row 6 pattern — its best anti-"out of
nowhere" device.*

**PED-14. Handoff/receiving reciprocity.** Every concept chapter ends with a
Handoff table mapping its examples to the decisions of the next project, with a
predict column; every project opens with the receiving table. (Enforcement under
PUB-13.) [REVIEW for content quality]

**PED-15. Part boundaries are transfer tests.** Each part ends with a Mastery
Checkpoint that is a novel task (not any artifact in the book), with an
acceptance checklist, a fallback ("a smaller version finished teaches more than
a full version abandoned"), and diagnostic pointers back into chapters. [REVIEW]

**PED-16. The dependency graph is honest.** If a project deliberately omits a
prior chapter's mechanism (the farm skipping the factory check), the text says
so, and an exercise restores it. [REVIEW]

**PED-17. Build the wrong thing first at project scale when failure is cheap.**
The naive-farm → three-failures → accumulator arc is the template: let the
reader watch the simple design break under a trace table before deriving the
real one. Reserve it for cases where the failure demonstrates in a page.
[REVIEW]

---

## Part 3 — Algorand expertise (ALG): what must be taught, when, and how

**ALG-1. The concept spine is a dependency order, and it is fixed:** mental
model (a contract is a validator asked a question) → ABI/routing/the two stack
types → state ownership (global/local) → boxes → integer arithmetic and time →
value movement (app account, inner transactions, groups) → testing/simulate →
authorization → costs (MBR/fees/budget/resources) → pricing math →
cross-contract calls → randomness → LogicSigs → cryptography → lifecycle and
operations. No example may use a concept ahead of its slot except as a labeled
IOU. [CI — each example declares its concept dependencies; the spine orders
them]

**ALG-2. Every cost is taught at the moment of first payment.** MBR when the
first box is created; inner-transaction fees when the first inner transaction
fires; opcode budget when the first loop grows; reference/access lists when the
first transaction must declare what it touches. Costs stated without a bill the
reader just paid don't stick. [REVIEW]
*Origin: book 2 ch10's "each left an invoice on the table" — the model.*

**ALG-3. The four-accounts discipline.** Before any guard is written, the reader
can name sender, creator, application address, and referenced account — and
knows only two can sign. Every authorization example states which account it
trusts and why. The unsatisfiable `Txn.sender == app address` guard is taught
as the canonical fatal example. [REVIEW]

**ALG-4. Every division names its winner.** All pricing/proportion math states
its rounding direction and defends it (floor favors the contract); every
subtraction is guarded where the value is *established*, not where it is used;
multiply-before-divide is the default ordering and deviations are argued.
Wide math (`mulw`/`divw`, `BigUInt`) is taught once, in the arithmetic slot, and
thereafter cited. [REVIEW]
*Origin: the "every division picks a winner" chapter; book 1 re-deriving this
in three chapters.*

**ALG-5. Storage choice is an ownership question.** Global vs local vs box is
decided by asking who can destroy the data; the ClearState trapdoor ("local
state belongs to the account, not the application") must be taught before any
local state holds a liability. "Statistics may walk away; liabilities may not"
is the load-bearing rule. [REVIEW]

**ALG-6. Receiving is evidence; sending is authorization plus fees.** Every
deposit method answers the four questions a grouped payment does not answer for
itself (right receiver, right asset, right amount, right payer) — or explicitly
names the question it deliberately does not ask and argues why that is safe
here. Every inner transaction states who pays its fee. [REVIEW]
*Origin: the tip jar's four defects; ch8's "fourth question deliberately not
asked" paragraph — the model.*

**ALG-7. Opt-in before transfer, always.** No asset moves in any example before
the receiving account's opt-in is shown or cited; contract-held assets teach
the mint → coordinate → deliver two-step as the standard pattern. [REVIEW]

**ALG-8. Contract balances are not ledgers.** Any contract holding value keeps
its own accounting state (reserves) and never does arithmetic on its raw
account balance; the spendable-vs-balance distinction and MBR floor are taught
with the first held Algo. [REVIEW]

**ALG-9. The four clocks.** Any time-dependent example names which of the four
"now"-shaped values it reads and why the other three are wrong; caller-chosen
fields (`Txn.last_valid`) are never trusted as time. [REVIEW]

**ALG-10. Randomness has three properties, and designs are tested against the
rubric.** Unpredictable, unbiasable, verifiable — the block seed fails it, the
commit-to-a-future-round beacon pattern passes it, and **every design that
waits on an external party ships an exit path for that party's silence** (the
beacon-never-speaks refund). [REVIEW]

**ALG-11. A LogicSig is made unsafe by the checks it lacks.** Every LogicSig
example carries the full guard checklist (fee bound, rekey-to, close-to, asset
close-to, lease/expiry, group binding) or explicitly names the guard it omits
and the attack that omission invites. Arguments are unsigned and never trusted.
Delegation examples show revocation (rekey or expiry) or state that there is
none. [REVIEW — checklist is mechanical enough to lint listing-side]

**ALG-12. Cryptography is priced, not just explained.** Every cryptographic
opcode example carries its opcode/fee bill, and every verification example is
tested for the gates-nothing failure: does this expensive check actually
constrain who can do what? "The cost of a check is not evidence that it
constrains anything." [REVIEW]

**ALG-13. Every assert carries a message a stranger can act on** ("the person
who most needs the message is not you; it is the integrator"). The
error-surface path (program counter → TEAL → source map) is taught once, early,
and cited thereafter. [CI — bare asserts fail the linter; REVIEW for message
quality]

**ALG-14. Simulate before print-debugging; negative tests assert the reason.**
A test that only proves "it failed" is not a negative test; it must check the
failure is the intended refusal. Tests derive from requirements, not from the
code ("a test that asserts what the code does can never disagree with the
code"). [REVIEW]

**ALG-15. Every contract takes an explicit lifecycle stance.** Immutable,
updatable, or deletable — stated, guarded, and defended in every project; the
things that cannot be added after deployment (events, error codes, an update
path) are taught as the reason the stance must be chosen up front. Operational
surface (events, pause, error codes) is introduced mid-book and deepened at
shipping time, not first met in the final chapter. [REVIEW]

**ALG-16. One validated baseline.** Toolchain versions are pinned, dated, and
stated once in front matter; examples never mix idioms from different toolchain
eras; the book delimits the protocol surface it does not build on so omissions
read as scoping, not gaps. [GEN for the version table; REVIEW for idiom drift]

---

## Coda: the meta-rule

**META-1.** When a rule and a chapter conflict, one of them is wrong — and it is
not automatically the chapter. Rules earn their place by citing the failure
they prevent; a rule that starts blocking demonstrably good teaching gets
amended here, with its history kept. This file is part of the manuscript's
source, reviewed like code.
