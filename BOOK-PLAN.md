# Building on Algorand — Comparative Analysis and Replacement Plan

*Scope: pedagogy, flow, and information conveyance only. Technical accuracy was not
assessed. All line numbers reference the two source files as of this analysis:
`Building-on-Algorand.md` (13,865 lines, "book 1") and `building-on-algorand-2.md`
(24,368 lines, "book 2").*

---

## 1. Executive Summary

The two books are not competitors; they are two stages of the same manuscript. Book 2
contains book 1's seven project chapters nearly verbatim (70–90% line-identical per
chapter) and wraps them in a new spine: ~10 concept chapters, each teaching one
mechanism through a small broken-then-repaired build, plus serious learning apparatus
(Handoff tables, Retrieval sections, Mastery Checkpoints, a generated Example Finder
and Gotchas appendix, CI-enforced example modes).

**The verdict: book 2's architecture wins, and it wins for exactly the reasons the
owner cares about** — concepts taught before projects need them, small complete
examples that compound, engineered "nothing out of nowhere" bridges. Book 1's projects
were forced to teach everything inline; roughly 40–50% of their prose is "what is X"
material that book 2 correctly extracted into concept chapters.

But book 2 is an unfinished merge, not a finished book. Its four failure classes:

1. **The opening contradicts the owner's goal.** Dev setup was exiled to Appendix A,
   yet Chapter 1 says "Deploy it:" (line 698) ~300 lines before telling the reader
   where setup lives (line 989). The book's own promise — "nothing is used before the
   chapter that introduces it" (line 549) — is falsified by its first runnable command.
2. **The retained projects were renumbered, not re-integrated.** The Limit Order Book
   keeps a full ~290-line LogicSig primer immediately after an entire LogicSig chapter
   (18961 vs 18212); ZK Voting re-teaches crypto costs, ZK theory, and Falcon that
   Chapter 21 just taught, and mis-anchors its recap to "Chapter 20" (21062); the AMM
   body re-derives x·y=k after Chapter 12 already had the reader repair an AMM quote
   (12858–12867); Chapter 8 still says "the next chapter extends the vesting contract
   with NFTs" when the next chapter is actually "Proving Who's Calling" (8869); stale
   `projects/chapterN/` paths from book 1's numbering appear in all six retained
   projects; "What's Next" omits the Lottery — the one project the rewrite added.
3. **Chapter openings explain the problem before the goal.** Every concept chapter
   opens with a failure vignette about an anonymous third party ("a team," "a
   creator," "a company") — elaborated for 30–50 lines, often using untaught
   mechanics as narrative fact — while the chapter's goal gets one sentence and the
   "by the end you will be able to" objectives are buried after the wreckage (ch1:
   incident 628–652, objectives 658, build starts 668; ch3: goal one sentence at
   2326, ClearState disaster from 2330; ch5: goal at 4306, "three things the AVM
   does not have" immediately after, four defects inventoried at 4314 before any
   code; ch6: postmortem 5366–5374 before Example 6-1). A typical programming book
   inverts this: state what the reader will build and its requirements, then let the
   problem emerge from the reader's own first attempt.
4. **Local prose defects.** Diff-narration instead of full corrected listings
   (4151–4169, 5226–5246), 350–400-word single-paragraph "mega-gotchas" (5546, 7493),
   forward references to Chapter 7 inside earlier Retrieval sections (3113, 5288),
   off-theme sections (ch4's array tour, ch10's legacy foreign-array material), and an
   aphorism density (~one "X is not Y, it is Z" per paragraph) that dilutes its own
   best lines.

**The replacement is therefore a revision program on book 2, not a third book**: move
setup into the spine as a true Chapter 1, finish the integration of the retained
projects (delta-recaps instead of primers, reciprocal Handoff tables everywhere,
regenerated numbering), rebuild the first project as a delta from the testing
chapter's contract, and apply a short editorial rulebook. Book 1 contributes its
remaining unique assets: the failing-tests-as-spec device, the naive-farm-then-
accumulator arc (already carried over), the Tinyman case study, and its Cookbook's
decision tables (to be distributed inline).

---

## 2. How the Two Books Relate

Diff results per shared project chapter (changed lines / combined total):
vesting 927/2469, NFT 472/3048, AMM 517/2723, factory 785/1799, yield 477/3277,
LOB 317/2947, ZK 442/2178. The changes are almost entirely additive stitching — "Run
It First" reformatted, "What You Need First" tables added (4 of 6 projects), "Mastery
Checkpoint" pointers appended — not rewrites of the teaching bodies.

Book 2 additionally has build infrastructure the plan must preserve: numbered examples
with CI-enforced execution modes (`compile`, `compile-fail`, `unit`, `script`,
`localnet`), deliberate broken "variation" examples, a generated Example Finder keyed
by task, a generated Gotchas appendix with drift-checking, and the companion
STUDY-GUIDE.md / EXAMPLES.md / PROJECTS.md files generated from the same source.

---

## 3. Book 1 Assessment

### Strengths (what it contributes to the replacement)

- **The projects themselves and the extend-the-previous-project pattern.** The
  Ch3→Ch4 delta framing (explicit "key differences" list at 3378–3384, Tables 4-1/4-2)
  and the AMM→Factory→Farming arc with explicit backward/forward transitions are the
  book's best structural ideas. Both survive into book 2.
- **Decision-layer inline teaching.** The local-state ClearState trapdoor sequence
  (2769–2783), wide-arithmetic worked example (2884–2890), inner-fee attack rationale
  (2582–2595), schedule-ID-vs-NFT-ID design reasoning (3686), mint-then-deliver
  coordination (3936–3952), revocation walkthrough Table 4-2 — model pedagogy that
  only lands inside a build that needs it.
- **Build-the-wrong-thing-first at project scale.** The yield-farming chapter's naive
  farm → three failures → accumulator-with-trace-tables sequence (7601–7933) is the
  strongest sustained teaching in either book.
- **The failing-tests-as-spec device** (Testing chapter, 1681–1908): each gap gets a
  test + consequence + pointer to the chapter that fixes it. The best invention in
  book 1's front matter, and the natural bridge from a testing chapter into a project.
- **Case-study grounding.** Tinyman V1 (5973–5979): date, dollar amount, root cause,
  lesson. Keep and imitate.
- **Reference apparatus.** The Cookbook's decision callouts (box vs BoxMap vs local
  state, 12518; local-state-vs-box, 12475) and the consolidated Gotchas sheet.

### Weaknesses (what the replacement must not inherit)

- **Two chapters of preparation for seven project chapters.** Concepts arrive
  mid-project with insufficient groundwork: the testing chapter's first real contract
  uses ~10 untaught constructs (788–953); `struct.pack(">Q", ...)` box keys are never
  taught (3427); "Pattern 2 in Chapter 8" is cited five chapters early (3801);
  Patterns chapter ships the book's first LogicSig code a chapter before LogicSigs
  are taught (9149).
- **Front-loaded theory.** ~325 lines of concept before keyboard contact in ch1; the
  chapter is "a concepts essay and a lab joined with no transition" (325).
- **Run It First bloat.** 180–430-line client-code walls (2247–2351, 5005–5168,
  6455–6836, 7424–7570) that use untaught machinery and, in the factory chapter,
  repeat the AMM chapter's workflow verbatim.
- **Broken runnable-checkpoint promise.** Outline pseudo-tests with undefined helpers
  in the vesting, AMM, factory, and farming chapters (3084–3257, 6171–6177,
  8828–8927); LOB keeper/tests are admitted skeletons (10577, 10823).
- **Re-derivation.** AVM integer math derived three times (Ch3, 5600–5625, 7850+);
  cross-contract mechanics split across Ch6 asides and Ch7's composition section.
- **Misplaced reference material.** The Patterns chapter interrupts the arc and is
  70% review; TWAP state is declared 700 lines before the TWAP section (5307).

---

## 4. Book 2 Assessment

### Strengths (the architecture to keep)

- **Build-first mental model.** Chapter 1 teaches the machine as the diagnosis of a
  broken Greeter's three failures, with a fix-diff and re-run transcript as payoff.
  Decisively better than book 1's theory essay.
- **The broken-first concept-chapter template**, executed with discipline across all
  ten concept chapters: narrative failure vignette → complete deliberately-wrong
  contract → "Predict: N decisions are wrong" commitment → real failure transcript →
  concept sections that each return to the running example → repair diff → apparatus.
- **Load-bearing chapter chaining.** Ch4 opens on ch3's ceiling (3166); ch5
  retroactively names ch4's early rule (4302); ch12's second defect is wrong *because*
  it obeys ch5's floor rule, which was directional (12024) — concepts compound rather
  than reset.
- **Engineered project handoffs.** The Calculator *is* the vesting math; ch7's example
  *is* ch8's contract in miniature (6670); Handoff tables map example numbers to
  project decisions with predict prompts, and the best "What You Need First" tables
  are their reciprocal (NFT 10549, Factory 14847). Ch8 can truthfully say "almost
  nothing here is new" (7643) — the owner's brief, achieved.
- **Just-in-time mid-book concept chapters.** Authorization (ch9), costs (ch10),
  pricing math (ch12), cross-contract calls (ch14) each sit immediately before the
  project that consumes them; ch9/ch10 argue in-text why the first project genuinely
  didn't need them yet (8931, 9691) — the deferral is engineered.
- **The Lottery (ch17→18) is the cleanest concept→project pairing in either book** and
  fills book 1's difficulty cliff between the DeFi arc and the LOB/ZK capstones.
- **Apparatus that is learning science, not decoration.** Backward-reaching Retrieval;
  five-rung exercise ladders (Trace→Parsons→Debug→Compare→Extend) whose Exercise 5s
  are designed productive failures closed by the next chapter's Handoff; Mastery
  Checkpoints as transfer tasks with fallbacks and diagnostic pointers; the Example
  Finder indexed by task; generated Gotchas with drift-check; the Foreword's
  verification-harness trust argument.
- **Ring composition closer.** Ch23 reopens the ch4 Guestbook as an operator's
  concern; the final insight ("the update path is the only one of the three that
  bootstraps itself," 22587) lands the book.
- **A memorable voice** whose aphorisms do retention work: "statistics may walk away;
  liabilities may not" (3033); "a proportion is a multiplication that has not been
  divided yet" (5272); "The payment is real. The accounting is fiction" (5854); "An
  application id supplied by the caller is not an integration, it is an instruction"
  (14287).

### Weaknesses (the revision program's target list)

1. **Setup placement and wiring** (see Executive Summary; also the Part I blurb
   promises setup inside a Part that doesn't contain it, 609).
2. **Unfinished project integration**: LOB Part 1 double-teaching (18961); missing
   "What You Need First" in LOB and ZK (Handoff tables at 18888 and 20964 dangle); ZK
   recap mis-anchored (21062); ZK re-tables opcode prices ch21 just taught (21086 vs
   20492); Falcon taught twice, needed ~zero times (20839 vs 21697); AMM body primer
   redundancy (12858); ch8's stale next-chapter pointer (8869) and old directory
   numbering in all six retained projects; "What's Next" omits the Lottery (24148).
3. **Ch8 builds from `algokit init` scaffold** (7758) instead of as a delta from
   ch7's `simple_vesting_fixed.py` — the rewrite's own logic argues for the delta;
   its "What You Need First" table duplicates ch6/ch7 Handoff rows nearly verbatim
   (7737–7750); four re-teaching passages (immutability sermon 7946, ClearState
   re-tell 8133, ARC-56 re-explain 7926, ch1-level deploy hand-holding 7898); no
   runnable checkpoint between `claim` and the tests (8386→8557).
4. **Sequencing slips**: Retrieval questions citing Chapter 7 before it (3113, 5288,
   2504, 3683); ch9 uses `ensure_budget` 700 lines before ch10 teaches budget (9432);
   ch2's Counter uses `self.count` global state with no "this is ch3's subject" note
   (1295, 2167); ch14's broken payroll uses `compile_contract` ~370 lines before its
   teaching section (14136 vs 14507).
5. **Prose-density defects**: diff-narration passages requiring mental reassembly
   (4169, 5246); mega-gotcha walls (5546, 7493, 6903); the Preface's quotation-
   conventions wall (431–433); six consecutive warning callouts reading as a defect
   log (ZK, 21466-region); exercise prose carrying four or five nested demands
   (2275–2285, 2291); aphorism density ~1/paragraph.
6. **Off-theme or misplaced sections**: ch4's array-types tour ("Nothing here changes
   the guestbook," 4146); ch10's "What It May Touch" legacy foreign-array and
   consensus-v41 material (10289–10392); ch12's on-chain impermanent-loss contract
   nobody would deploy (12571); ch2's low-narrative type-system trek (1352–1846).
7. **Events taught only at the end**: the Lottery ships 27 assertion messages and a
   refusal table with no events; ch23 names "pause" the common omission but never
   shows one (22391).
8. **Two concept chapters back-to-back (ch9+ch10)** is the one place the
   concept/project rhythm stalls.
9. **Goal-less openings** (see Executive Summary §1.3): the broken-first template as
   executed puts the incident before the commission. The reader is a spectator at a
   stranger's postmortem — complete with mechanics not yet taught — before being told
   what they themselves are building or why. Related flow tic: withheld-reveal
   riddles that span section boundaries ("four accounts, and only two of them can
   ever sign" dropped at 626, answered at 782; ch2's third failure opened at 1349 and
   resolved ~640 lines later at 1988).

---

## 5. Head-to-Head Summary

| Dimension | Book 1 | Book 2 |
|---|---|---|
| Opening | Theory essay + setup + hello world in one chapter; hands-on delayed | Build-first Greeter; superior, but setup exiled to appendix with broken wiring |
| Concept coverage | Inline, mid-project, frequently used-before-taught | Dedicated broken-first chapters, just-in-time before each project |
| Project chapters | Carry double duty (teach + build); strong decision-layer teaching | Same bodies, now reading as assembly — where integration was finished |
| Flow devices | Forward refs to unintroduced taxonomies (Patterns, Cookbook) | Handoff/WYNF reciprocal tables, labeled IOUs — where applied |
| Runnability | Real checkpoints early; pseudo-test outlines late | CI-enforced example modes; same pseudo-test residue in retained projects |
| Difficulty curve | Cliff between farming and LOB/ZK | Lottery bridges it; LogicSig/crypto chapters pre-teach capstones |
| Apparatus | Bloom exercises, checklists, Cookbook, Gotchas | Adds Retrieval, Handoffs, Mastery Checkpoints, Example Finder, generated Gotchas |
| Voice | Plain, occasionally flat | Distinctive and memorable; over-dense in places |
| Integrity | Self-consistent numbering | Stale paths, wrong next-chapter pointers, mis-anchored recaps |

---

## 6. Design Principles for the Replacement

1. **Classic opening, minimal footprint.** Setup is Chapter 1 in the spine — empty
   directory to deployed-and-called contract — because the reader must execute it
   before anything else. The deep reference (troubleshooting, connecting to deployed
   apps, version pinning) stays in a slim appendix.
2. **Concept chapters own the "what is X" layer; projects own the decision layer.**
   Projects may recap via tables citing example numbers; they may never re-teach.
   ZK Voting's Part-1-recap style (honest, delta-only, adds chapter-specific math) is
   the model; LOB's Part 1 is the anti-model.
3. **Goal before problem — the chapter-opening contract.** Every concept chapter
   (and Ch 2) opens in this fixed order:
   - **(a) Bridge** — one short paragraph connecting from the previous chapter's
     ceiling (book 2 already does this well; keep it).
   - **(b) The commission** — what *the reader* will build this chapter and its
     requirements, as a short 3–5 item spec ("You're going to build a tip jar. It
     must: accept tips; credit the tipper who actually paid; let the creator — and
     only the creator — withdraw."). The artifact belongs to the reader from
     sentence one, not to "a team."
   - **(c) The objectives** — the "by the end of this chapter you will be able to"
     list, moved *above* any failure material.
   - **(d) The first attempt** — the broken contract, framed as *our* naive first
     pass at the stated spec ("here is the way anyone coming from Python would
     write it"), with the Predict prompt. Failure transcripts and
     concepts-as-diagnosis proceed from there, unchanged.
   The broken-first machinery (commitment, transcripts, repair diff, re-run) is
   preserved intact — only the order of purpose and problem changes. Third-party
   incident narratives ("six weeks later the jar holds 33.3 Algo...") are kept but
   **relocated after the code**, recast as the consequence of shipping the reader's
   own first pass — or compressed into short asides. They may not be the reader's
   first contact with the chapter's mechanics, and they may not use untaught
   machinery as load-bearing plot.
4. **No cliffhangers across section boundaries.** A withheld reveal must resolve
   within the section that poses it (kills the four-accounts riddle at 626 and the
   640-line suspense at 1349→1988). Curiosity gaps are opened by the reader's own
   prediction, not by the narrator withholding an answer.
5. **Every chapter ends runnable.** No outline pseudo-tests; book 1's NFT-chapter
   complete-suite standard applies everywhere. Run It First sections are ≤ ~30 lines
   of commands + a checkpoint table + predictions — never a second tutorial.
6. **Forward references are labeled IOUs; Retrieval reaches only backward.**
7. **The dependency graph is honest.** If a project deliberately omits a prior
   chapter's mechanism (farm skipping the factory check), the text says so and an
   exercise restores it.
8. **One client style** (typed clients) except where field-level control is itself
   the lesson (LogicSig groups), and then labeled as such.
9. **Numbering, paths, and cross-references are generated and CI-checked** — extend
   the existing drift-checker to directory names, "next chapter" sentences, and
   recap-anchor targets, so the renumbering-residue class of defect cannot recur.
10. **Aphorism budget.** Thin by roughly a third; keep chapter-thesis lines.
11. **Gotchas are structured**: bolded one-line rule, then ≤ ~120 words, one idea
    each. No 400-word single-paragraph slabs.

---

## 7. The Replacement Outline

Twenty-four chapters in seven parts. Each part ends with its Mastery Checkpoint
**printed at the part boundary** (not pointed to in back matter). Sources: "B2 chN"
= book 2 chapter; "B1" = book 1 material to import.

**The chapter-opening contract (Principle 3) applies to every concept chapter and
Ch 2** — bridge → commission (the reader's build + 3–5 requirement spec) →
objectives → first attempt. This is a retrofit of all existing openings, not new
writing: the material already exists in each chapter; it moves. The heaviest
retrofits are ch1/2/3/5/6 openings (B2 615–668, 1243–1300, 2321–2350, 4298–4335,
5356–5395), where the third-party incident currently precedes both the commission
and the objectives; ch9, ch12, and ch17 need the same reorder in lighter form.
Project chapters already open goal-first ("Run It First" + what-you-will-build) and
need no change beyond the fixes listed per chapter.

### Part I — Foundations

**Ch 1. From Zero to Deployed** *(new position; source: B2 Appendix A + B1 ch1 setup
section)*
Install → LocalNet → scaffold → the smallest contract → compile → deploy → call →
run the tests → the named loop (edit, compile, deploy, interact, test) → the three
debugging habits. Ends with the reader having run everything the book will assume.
Slim Appendix A retains troubleshooting/reference only.

**Ch 2. The Algorand Mental Model** *(B2 ch1, minus the toolchain walkthrough that
moved to Ch 1)*
The broken Greeter; accounts, MBR, atomicity, budgets as diagnosis; fix-diff and
re-run. Fixes: apply the opening contract — the Greeter is *the reader's* first
contract with a stated spec (greet strangers; reject empty names with a readable
error; stay deletable by its admin), objectives moved above the failure material,
and the team's three-day-support-thread / undeletable-app story recast as the
consequence of shipping the naive version, told after the reader has seen and
predicted on the code; "Deploy it" now follows Ch 1 naturally; drop the
four-accounts riddle teaser (626) — state it as fact where the four accounts are
taught (782); cut typed-vs-untyped factory transposition trivia (1096); move the
quotation-conventions wall out of the Preface to beside the first transcript here.

**Ch 3. Contracts That Exist and Respond** *(B2 ch2)*
Counter; ABI methods, routing, the two stack types, ARC-4 boundary, app spec.
Fixes: one-line note that `self.count` is Ch 4's subject; compress the type-tour
middle (1352–1846) by moving deep ARC-4 offset/hexdump material to the encoding
discussion in Part II where box keys make it load-bearing; split overloaded
exercises into single-demand items; shorten the 640-line suspense on the third
failure (1349→1988).

**Ch 4. Remembering Things: Global and Local State** *(B2 ch3)*
Registry. Keep essentially as-is — the strongest concept chapter. Fix: reframe
Retrieval Q8's Chapter-7 forward reference as a labeled preview.

**Ch 5. Data That Grows: Box Storage** *(B2 ch4)*
Guestbook. Fixes: move the array-types section (4029–4146) out — to Part II where
`.copy()` first bites in the vesting data model; split the I/O-budget section with a
worked-example breather; print the full corrected contract after the repair diff.

**Ch 6. Arithmetic That Refuses: Numbers and Time** *(B2 ch5)*
Calculator — literally the vesting math. Fixes: full corrected listing instead of
diff-narration (5246); reframe Retrieval Q10's Chapter-7 reference.

**Ch 7. Moving Value: Assets, Payments, and Groups** *(B2 ch6)*
Tip Jar. Fixes: break the spendable-balance mega-gotcha (5546) into bullets; trim
the asset-authorities taxonomy (6223–6316) to what clawback in Part II will need,
with an IOU; cut the elided-code inventory paragraph (6419).

**Ch 8. Proving It Works: Tests, Simulation, and Failure** *(B2 ch7 + B1's
failing-tests-as-spec framing)*
Single-beneficiary vesting with three surviving defects; assert messages; simulate;
tests from requirements, not from code. Add a short **"Saying What Happened"**
subsection introducing events/`arc4.emit` at basic altitude (the material ch23
deepens) — this fixes the events-arrive-too-late gap and gives the Lottery's
refusal table a consumer story. Fixes: compress the logged_assert compiler-trivia
digression (6903); break the simulate-raises mega-gotcha (7493) into bullets; trim
Example 7-11's API-reference material.

*Part I Mastery Checkpoint (Foundations), printed here.*

### Part II — Value Under Management

**Ch 9. Project: A Token Vesting Contract** *(B2 ch8, restructured)*
**Build as the delta from Ch 8's contract**: boxes replace globals, multi-beneficiary
replaces one, revoke/cleanup/queries are added — dramatizing what "production
version" means and cutting ~a third of the chapter. Fixes: shrink "What You Need
First" to the rows not already in Ch 7/8 Handoffs; delete the four re-teaching
passages (7946, 8133, 7926, 7898); add a runnable checkpoint after `claim`; smooth
legacy voice seams (8254, 8525); Run It First to ≤30 lines + checkpoint table; keep
the divmodw≡divw proof with its Exercise 3 anchor.

**Ch 10. Proving Who's Calling** *(B2 ch9)*
Pay-to-Post Board. Fixes: strip `ensure_budget` from Example 9-12 (or move that
example after Ch 11); give the scratch-space pair an authorization payload or cut
it; split the 9269 overload paragraph.

**Ch 11. Paying For It: Minimum Balance, Fees, and Budget** *(B2 ch10)*
Fee Splitter. Fixes: cut "What It May Touch" legacy foreign-array example and
consensus-v41 material to Appendix B; drop the `inline=` example; relocate the
padding-contract digression after `ensure_budget` is taught. To soften the
two-concept-chapters-in-a-row stall: open with a two-sentence bridge naming the NFT
project as the payoff, and consider merging Ch 10's group-proof section here if
Part II ever needs shortening.

**Ch 12. Project: NFT Vesting** *(B2 ch11 — the best-stitched retained project)*
Keep the delta-list opening and reciprocal Table 11-2. Fixes: split the 95-line
mint+deliver block into mint → the opt-in problem → deliver; introduce `deliver_nft`
with its reason before its code; trim Run It First; keep the complete runnable test
suite as the book-wide standard.

*Part II Mastery Checkpoint (Value in Motion), printed here.*

### Part III — Building a DEX

**Ch 13. Numbers That Price Things** *(B2 ch12)*
Two-sided Quote engine; direction and scale; every division picks a winner; prices
over time (TWAP math lives here). Fixes: demote the impermanent-loss contract
(12571) to client-side code/prose; trim the overflow-horizon numerics (12565); cut
the Vestige/Folks name-drop (12381).

**Ch 14. Project: A Constant Product AMM** *(B2 ch13)*
Fixes: cut the "never used a DEX" primer and x·y=k re-derivation — cite Ch 13's
examples instead (the WYNF table already knows how); keep both LocalNet checkpoints
(the book's best build cadence); TWAP becomes an explicitly optional hardening
section that *implements* Ch 13's math (removing the dead-state forward declaration
defect); keep Tinyman; replace outline tests with a small real suite; one client
style throughout.

**Ch 15. Contracts That Talk to Contracts** *(B2 ch14)*
Payroll parent/worker. Fixes: move the atomicity gotcha beside Example 14-11; add a
one-line signpost where the broken payroll uses `compile_contract` before its
teaching section; drop the duplicated 80-line diff-then-full-listing repair (keep
the full listing).

**Ch 16. Project: AMM Factory and Pool Provenance** *(B2 ch15 — best integration in
the book; imitate it elsewhere)*
Fixes from book 1's findings: restore at least one mid-chapter runnable checkpoint
(the guided-tour format currently has none); cut Run It First's repeat of the AMM
liquidity/swap workflow; replace source-grepping "shape tests" with behavior tests;
ground the seed-payment MBR numbers by deriving them (Ch 11 makes this a one-liner).

**Ch 17. Project: Yield Farming** *(B2 ch16)*
Keep the naive-farm → three failures → accumulator-with-trace-tables arc untouched —
it is the best sustained teaching in either book. Fixes: explain `arc4.Struct`/
`.copy()` at first use (or inherit it from the relocated array section in Ch 9's
data model); consolidate the four overflow re-litigations into one audit table plus
pointers; add an exercise restoring the Ch 16 factory check (making the honest
dependency note actionable); real tests.

*Part III Mastery Checkpoint (Building a DEX), printed here.*

### Part IV — Chance

**Ch 18. A Number Nobody Can Predict** *(B2 ch17)*
Raffle; the three-properties rubric. Fixes: trim exercise sprawl (17622–17636);
move the multiple-of-eight rounding explanation after the beacon introduction.

**Ch 19. Project: A Lottery That Pays Out or Gives Back** *(B2 ch18)*
Keep whole — the cleanest concept→project pairing in either book, and the difficulty
bridge book 1 lacked. Fixes: regenerate stale paths; move one ticket-purchase code
example ahead of the three cost tables; add a two-line event emission now that Ch 8
introduced events.

*Part IV Mastery Checkpoint (Randomness and Fair Draws), printed here.*

### Part V — Stateless Programs

**Ch 20. Signing Without a Key** *(B2 ch19 — best-paced chapter in the manuscript)*
Allowance; two binding modes; the guards a LogicSig cannot ship without; "Four
Programs With One Hole Each." Keep essentially as-is; fix stale example paths.

**Ch 21. Project: Delegated Limit Order Book** *(B2 ch20, restructured)*
The one mandatory surgery: **compress Part 1 to a ZK-style delta-recap** (genesis-
hash forms, group binding, the eight-item checklist Ch 20 defers to it) — ~290 lines
→ ~60. Write the missing "What You Need First" receiving Ch 20's Handoff. Resolve
the "this is discouraged" framing (9691-era) into "when this architecture is right"
— one paragraph, once. Deduplicate the thrice-made selector-binding argument. Make
keeper/tests complete or scope to one fully worked helper plus the real suite. Cut
the packed-binary sub-technique to a sidebar (it contradicts its own advice).

*Part V Mastery Checkpoint (Logic Signatures), printed here.*

### Part VI — Cryptography

**Ch 22. Proving Things Without Revealing Them** *(B2 ch21)*
Sealed bid; primitives priced; "The Check That Gates Nothing" (keep — the best
passage in the manuscript). Fixes: compress the VRF section to a Ch 18 pointer plus
the price delta; single home for Falcon (here, briefly — or in What's Next — but
not both); merge the fee-scaling paragraph and its echo gotcha.

**Ch 23. Project: Private Governance Voting with ZK Proofs** *(B2 ch22,
restructured)*
Keep the two-track (runnable Python / illustrative Go) design and its honest
expectation-setting. Fixes: Parts 2–3 become delta-recaps citing Ch 22 examples;
re-anchor the recap to Ch 22 (not "Chapter 20"); write the missing "What You Need
First"; move Part 6 (Falcon/post-quantum essay) to What's Next; consolidate the
scattered warning callouts into one "production hardening" section built on the
existing checklist; move box-iteration (Part 5) before the tests so tests sit
beside the code they exercise.

*Part VI Mastery Checkpoint (Cryptography and ZK), printed here.*

### Part VII — Shipping

**Ch 24. Shipping and Surviving** *(B2 ch23)*
The Guestbook, revisited as an operator's contract: events (deepened, now that Ch 8
introduced them), error codes, upgrade/freeze/delete, and the closing insight about
what cannot be added after deployment. Fixes: add the pause example the chapter
itself calls the common omission; restructure Example 23-4's rule-cramming
docstring into prose; fix stale paths.

*Part VII Mastery Checkpoint (Shipping), printed here.*

### Back Matter

- **Appendix A: Environment Reference** — slim: troubleshooting, connecting to
  already-deployed contracts, version pinning. (The walkthrough moved to Ch 1.)
- **Appendix B: AVM Limits and Protocol Parameters** — as-is; absorbs the legacy
  foreign-array / consensus-v41 material cut from Ch 11.
- **Appendix C: Gotchas by Topic** — keep generation + drift-check; dedupe twin
  entries (inner-fee 23186/23351, overflow 23129/23147); rewrite the ~4 entries that
  don't stand alone outside their project; drop the circular "From Appendix A/B"
  entries.
- **Appendix D: The Example Finder** — keep; add topic grouping above the
  alphabetical listing for findability; rewrite the handful of clever-but-unfindable
  rows.
- **What's Next** — include the Lottery in the recap; absorbs the Falcon/post-quantum
  essay; keep the accomplishment-replay paragraph style (model: B1 13677).
- **Glossary, Bibliography, Colophon** — keep; drop stray oddities (e.g. "VibeKit").
- *No separate Cookbook*: book 1's Cookbook decision tables (box vs BoxMap vs local
  state; when-to-use callouts) are promoted inline into the concept chapters at the
  point of decision; the Example Finder is the single lookup surface. The Patterns
  chapter likewise stays dissolved (book 2 already did this) — no pattern may exist
  only in a reference chapter.

---

## 8. Cross-Cutting Work Items (the editorial sweep)

1. Generate and CI-check all `projects/` and `examples/` directory names, "next
   chapter" sentences, and recap anchors against the spine (kills the entire
   renumbering-residue defect class: 7647, 8869, 10502, 17681, 18575, 21062, 22476,
   24148).
2. Full-listing rule: every repair diff is followed by (or links to) the complete
   corrected contract.
3. Mega-gotcha teardown: 5546, 7493, 6903, 9269, 9997, 20698 — structured bullets.
4. Retrieval audit: no question references a later chapter (3113, 5288, 2504, 3683).
5. Aphorism thinning pass (~⅓), preserving chapter-thesis lines.
6. Exercise de-nesting: one demand per lettered item (2275–2285, 2291, 3128).
7. Test-suite completion: vesting (from Ch 8's suite), AMM, factory, farming, LOB —
   to the NFT chapter's complete-runnable standard; delete source-grep shape tests.
8. Client-style unification (typed), with labeled raw-SDK exceptions in Ch 20–21.
9. Preface conventions wall (431–433) relocated beside the first transcript.
10. Part-blurb accuracy pass (609's setup promise; Part IV/V blurbs after
    renumbering).
11. **Chapter-opening retrofit** (Principle 3): for each concept chapter and Ch 2 —
    write the 3–5 item commission spec; hoist the "by the end" objectives above all
    failure material; reframe the broken listing as the reader's first pass at the
    spec; relocate third-party incident narratives after the code and strip untaught
    mechanics from any that remain ahead of their teaching section. The spec box
    also becomes the re-run's acceptance list at chapter end — the repair is checked
    against the same requirements the opening stated, closing the loop.
12. **Cliffhanger audit** (Principle 4): no unresolved reveal may cross a section
    boundary (626→782, 1349→1988 are the known instances; sweep for others).

## 9. Suggested Execution Order

1. **Spine surgery** (structure only): move setup to Ch 1; renumber; print
   checkpoints at part ends; regenerate companions (PROJECTS.md, EXAMPLES.md,
   STUDY-GUIDE.md).
2. **Integration debt**: LOB Part 1 compression; ZK recap re-anchor + delta-recaps;
   missing WYNF tables; AMM primer cut; Ch 9-as-delta rebuild.
3. **Editorial sweep** (§8), one pass per rule, whole book.
4. **Runnability debt**: complete the test suites; verify every chapter's end-state
   runs; extend CI to the new checks (§8.1).
5. **Polish**: voice seams in retained projects, exercise de-nesting, apparatus
   dedupe.

Items 1–2 change what the reader experiences; 3–5 change whether the book keeps its
own promises. Nothing here requires new chapters to be written from scratch — the
replacement is book 2, finished.
