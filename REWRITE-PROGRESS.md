# Book Rewrite — Working Ledger

Working state for the full rewrite executing BOOK-PLAN.md §7 (Replacement Outline)
+ §9 (execution order) under RULEBOOK.md. This file is the cross-session memory:
update it whenever a phase or chapter changes state. Delete when the rewrite ships.

## What is happening

`chapters/` (book 1, 10 chapters) is being replaced by the finished form of book 2
(`/home/andrew/coding/boa/building-on-algorand-2.md`, split per chapter in
`build/resolved/`): 24 chapters in 7 parts, new Ch 1 "From Zero to Deployed",
every other chapter = B2 chapter + 1, with BOOK-PLAN's per-chapter fixes and the
§8 editorial sweep applied.

## Source materials

- `build/resolved/*.md` — book 2 split per chapter, listings inlined (SOURCE for all rewrites)
- `/home/andrew/coding/boa/EXAMPLES.md` — authoritative example catalog: number → disk path → CI mode → finder line
- `/home/andrew/coding/boa/STUDY-GUIDE.md`, `PROJECTS.md` — B2 companions (regeneration descoped for now)
- `chapters/` book-1 text: recoverable from git history (replaced by this rewrite)
- Book 1 unique assets to import: failing-tests-as-spec (B1 ch2), Cookbook decision tables (B1 A1 → inline), Tinyman case study (already in B2 ch13)

## The spine (canonical; scripts/spine.py is the machine-readable copy)

| New | File | Source (build/resolved/) | B2 ch | Kind | Part |
|-----|------|--------------------------|-------|------|------|
| 1 | 01-from-zero-to-deployed.md | (new; from A1-setup + B1 ch1 setup) | — | Concept | I Foundations |
| 2 | 02-the-algorand-mental-model.md | 01-c-mental-model.md | 1 | Concept | I |
| 3 | 03-contracts-that-exist-and-respond.md | 02-c-contracts.md | 2 | Concept | I |
| 4 | 04-remembering-things.md | 03-c-state.md | 3 | Concept | I |
| 5 | 05-data-that-grows.md | 04-c-boxes.md | 4 | Concept | I |
| 6 | 06-arithmetic-that-refuses.md | 05-c-numbers-and-time.md | 5 | Concept | I |
| 7 | 07-moving-value.md | 06-c-moving-value.md | 6 | Concept | I |
| 8 | 08-proving-it-works.md | 07-c-proving-it-works.md | 7 | Concept | I |
| — | 08z-checkpoint-foundations.md | A6-checkpoints §I | — | Checkpoint | I end |
| 9 | 09-a-token-vesting-contract.md | 03-p-token-vesting.md | 8 | Project | II Value Under Management |
| 10 | 10-proving-whos-calling.md | 09-c-authorization.md | 9 | Concept | II |
| 11 | 11-paying-for-it.md | 10-c-paying-for-it.md | 10 | Concept | II |
| 12 | 12-nft-vesting.md | 04-p-nfts.md | 11 | Project | II |
| — | 12z-checkpoint-value-under-management.md | A6 §II | — | Checkpoint | II end |
| 13 | 13-numbers-that-price-things.md | 12-c-pricing.md | 12 | Concept | III Building a DEX |
| 14 | 14-a-constant-product-amm.md | 05-p-amm.md | 13 | Project | III |
| 15 | 15-contracts-that-talk-to-contracts.md | 14-c-composition.md | 14 | Concept | III |
| 16 | 16-amm-factory-and-pool-provenance.md | 06-p-amm-factory.md | 15 | Project | III |
| 17 | 17-yield-farming.md | 07-p-yield-farming.md | 16 | Project | III |
| — | 17z-checkpoint-building-a-dex.md | A6 §III | — | Checkpoint | III end |
| 18 | 18-a-number-nobody-can-predict.md | 08-c-randomness.md | 17 | Concept | IV Chance |
| 19 | 19-a-lottery-that-pays-out-or-gives-back.md | 08-p-lottery.md | 18 | Project | IV |
| — | 19z-checkpoint-chance.md | A6 §IV | — | Checkpoint | IV end |
| 20 | 20-signing-without-a-key.md | 17-c-logicsigs.md | 19 | Concept | V Stateless Programs |
| 21 | 21-delegated-limit-order-book.md | 09-p-limit-order-book.md | 20 | Project | V |
| — | 21z-checkpoint-stateless-programs.md | A6 §V | — | Checkpoint | V end |
| 22 | 22-proving-things-without-revealing-them.md | 19-c-cryptography.md | 21 | Concept | VI Cryptography |
| 23 | 23-private-governance-voting.md | 10-p-zk-voting.md | 22 | Project | VI |
| — | 23z-checkpoint-cryptography.md | A6 §VI | — | Checkpoint | VI end |
| 24 | 24-shipping-and-surviving.md | 21-c-shipping.md | 23 | Concept | VII Shipping |
| — | 24z-checkpoint-shipping.md | A6 §VII | — | Checkpoint | VII end |

Front matter: F1-legal-notice (←F1), F2-foreword (←F3-foreword), F3-preface (←F2-preface),
F4-how-to-use (←F4). Appendices: A1-environment-reference (←A1-setup, slimmed in P2),
A2-avm-limits (←A2, absorbs Ch 11 legacy cuts), A3-gotchas (GENERATED from inline callouts),
A4-example-finder (GENERATED; was B2's A5). Back: Z1-whats-next (+Lottery +Falcon essay),
Z2-glossary, Z3-bibliography, Z4-colophon.

## Standing decisions

1. **Renumbering**: new chapter = B2 chapter + 1, mechanical via scripts (Chapter N,
   Examples?/Tables?/Figures? N-M). Appendix letters unchanged (C=gotchas, D=finder).
2. **Stable code paths** (PUB-6 by construction): `examples/<topic>/` and
   `projects/<name>/` carry NO chapter numbers. Renames:
   ch01_mental_model→mental_model, ch02_contracts→contracts, ch03_state→state,
   ch04_boxes→boxes, ch05_numbers_time→numbers_time, ch06_moving_value→moving_value,
   ch07_proving_it_works→proving_it_works, ch08_randomness→randomness,
   ch09_authorization→authorization, ch10_resources→costs, ch12_pricing→pricing,
   ch14_composition→composition, ch17_logicsigs→logicsigs, ch19_cryptography→cryptography,
   ch21_shipping→shipping, + new setup/ for Ch 1.
   projects/chapterN/<name> → projects/<name>; chapter10/zk-voting → governance-voting
   (matches B2's own newer references). Drift = CI check, not naming convention.
3. **Example sources are re-extracted from chapter text** (the .py files were deleted;
   only pycache remains). Each example caption gains a machine-readable comment:
   `<!-- example: <path> mode=compile|compile-fail|unit|script|localnet -->` so
   chapters are the single source of truth; extractor + per-mode CI in scripts/.
4. **Figures**: 25 referenced figures/*.svg never existed here. Placeholders first
   (build stays green), real diagrams in Phase 6.
5. **Admonitions**: source uses pandoc fenced divs `::: {.gotcha #id topic=".." title=".."}`
   (8 classes: gotcha, note, warning, tip, tryit, check, setup, spec). build.py converts
   to styled HTML blocks for mdbook; PDF styling via Lua filter in Phase 8.
6. **Chapter titles** keep B2's wording; kind badge (Concept/Project) via \BOAchapterkind.
7. **Part blurbs** rewritten for new membership (in first-of-part chapter files, PDF-only,
   as before). Part numbers I–VII map 1:1 old→new; membership shifts reviewed manually.
8. Checkpoints retitled to new part names; printed at part ends as unnumbered pages.
9. Reviews: 3-agent per CLAUDE.md, batched per part after content stabilizes.
   LocalNet is running (algokit sandbox up) — walkthroughs feasible.

## Phase status

- [x] Phase 0: Survey + plan (this file)
- [x] Phase 1: Spine surgery (task #1) — DONE: new spine live in chapters/ (43 files),
      renumbering + path remaps applied, checkpoints at part ends, part blurbs written,
      build.py spine-driven with fenced-div callouts, placeholder figures/, drift-checker
      scripts/check_book.py wired into tests (tests/test_book_integrity.py, KNOWN_DEBT
      allowlist = 3 forward-retrieval refs + 2 missing WYNF tables), 38 tests green,
      mdbook builds. NOTE: untracked projects (limit-order-book, governance-voting,
      lottery) lost .py sources (pycache + generated typed clients survive — clients
      give the lost contracts' ABI for reconstruction in Phase 5).
- [ ] Phase 2: Ch 1 authored + Ch 2 rewired (task #2)
- [ ] Phase 3: Integration debt: Ch 9 delta, LOB, ZK, AMM, events thread (task #3)
- [ ] Phase 4: Editorial sweep, all chapters (task #4)
- [ ] Phase 5: Examples tree + check_book.py + regenerate A3/A4 (task #5)
- [ ] Phase 6: Figures (task #6)
- [ ] Phase 7: 3-agent reviews per part (task #7)
- [ ] Phase 8: Final builds + matter + CLAUDE.md (task #8)

## Phase 3 state (mine + agents)

- Events thread DONE: ch8 §"Saying What Happened" + Example 8-16 (Claimed on
  SimpleVesting) + Retrieval Q11 + Handoff row; ch19 draw emits Won + rationale ¶;
  ch24 bridge ¶ acknowledges ch8/ch19. **P5 must**: add the emit + struct to
  examples/proving_it_works/simple_vesting_fixed.py derivative (simple_vesting_events.py),
  to projects/token-vesting contract + regen artifacts, and to projects/lottery contract.
- Ch 9 delta rebuild DONE (text level): explicit kept/changed/new delta list in opening;
  WYNF shrunk 41→27 rows (ch7/ch8 rows replaced by Table 7-1/8-2 pointers); 4 re-teaching
  passages cut (ARC-56, immutability sermon, ClearState re-tell + twin gotcha, deploy
  hand-holding compressed); post-claim runnable checkpoint added (two refusal probes);
  Claimed event carried into claim listing; Appendix-A refs rewired to Ch 1; client-style
  note reframed as labeled PUB-5 exception (generic = teaching register, typed = project).
  **P5 must**: token-vesting contract.py gains Claimed struct + emit (+ artifact regen +
  test touching the log); verify test_initialize probes (LogicError import path) in walkthrough.
- Subagent results (LANDED, verified green):
  - ch23 ZK: WYNF added (E7 cleared+pruned), recap re-anchored to ch22, Parts 2-3
    delta-recaps, Falcon essay → Z1 §"The Post-Quantum Road" (+Lottery in Z1 recap),
    warnings → "Production Hardening" section, box-iteration before tests, ch22
    Falcon compressed to one ¶. FOLLOW-UPS: F3-preface line ~75 stale ("Falcon-based
    post-quantum roadmap" claim re ch23) → P8; Table 23-1 privacy-wording tension → P7
    walkthrough.
  - ch4: PED-1 retrofit (spec box, story→consequence, acceptance close). Clean.
  - ch6: PED-1 retrofit + NEW Example 6-22 (full corrected calculator listing);
    extracted to examples/numbers_time/vesting_calc_fixed.py ✓ compiles.
  - ch14 AMM: primer cut→13-citations, TWAP now optional section (state out of main
    build), real test listings (diffed verbatim vs project suite), typed client
    everywhere, 5 assert messages aligned with project contract, stale factory refs
    fixed. FOLLOW-UPS: projects/constant-product-amm has stale "Chapter 5" strings
    (script print + pyproject description) → P5; ch14 walkthrough → P7.
- Subagents still running: ch21 LOB, ch7 retrofit, examples-extraction (8 targets),
  2× figure authors (25 SVGs).
- Ch 11 DONE (mine): NFT-payoff bridge + spec box + objectives before the splitter
  story (story relocated post-transcript as consequence), inline= example cut,
  legacy foreign-array + consensus-v41 → A2 §"Legacy Resource Addressing"
  (+ examples/costs/legacy_foreign_array.py ✓ compiles), padding-contract digression
  moved after group-padding, examples renumbered 1..16 (A4 placeholder patched).
- scripts/compile_examples.py: per-example CI harness (modes from chapter annotations
  + file headers; cache in build/example-cache.json). All present examples green.
- scripts/generate_appendices.py WRITTEN, NOT YET RUN (waiting for chapter texts to
  stabilize; then regenerate A3/A4 + wire drift test into test_book_integrity).
- Front matter (mine, DONE): F4 setup pointer → Ch 1; F3 stale ch23-Falcon line fixed;
  F3 conventions wall (PUB-12) cut to a pointer — essentials absorbed into ch2's
  transcript note; F2 foreword harness ¶ rewritten to name real checks; PUB-14
  manifest: validation/manifest.json now has "book_promises" (4 promise→check pairs).
  REMAINING F-matter (P8): F3 line ~85 "Chapters 21 and 23 are guided outlines /
  their directories are complete" — verify truth after ch21 agent + P5 project-source
  rebuild; F3 validated-baseline table check (ALG-16); Z4 colophon "VibeKit" oddity
  check per plan.
- LANDED since: ch7 retrofit (spec box, postmortem→consequence, spendable-balance
  mega-gotcha teardown, authorities trim + verified ch12 IOU, acceptance close).
  ch21 LOB (−405 lines): Part 1 → 49-line delta-recap + Table 21-3 checklist,
  WYNF Table 21-2 (E7 cleared; KNOWN_DEBT now EMPTY), one "when this architecture
  is right" ¶, selector-binding deduped, keeper = one worked helper + Table 21-7
  test-coverage rows, packed-binary → sidebar + contract REWRITTEN to arc4.Struct
  + ARC-28 events (compile-verified; sources in scratchpad lob_check/ for P5
  project rebuild). Extraction agent: ALL example targets done incl. tip_jar_fixed
  — harness fully green (0 failed/missing/orphans); global_counter now mode=unit
  (ch4's "runs in CI" literally true); assert_message_home mode=compile.
- Checker: 0 errors. Remaining W2: counter_fixed (extract after ch3 agent lands),
  keeper.py (P5 project rebuild).
- F-matter: colophon rewritten truthfully (real harness, no resolver claims);
  glossary VibeKit entry dropped; preface ch21 "packed binary" claim removed.
- PDF pipeline FIXED and GREEN: two causes — (a) SVG inclusion (no rsvg-convert):
  build.py now pre-converts figures via cairosvg (uv group "pdf") + Lua filter
  path rewrite; (b) pandoc 3.7 dropped --syntax-highlighting → --highlight-style.
  `uv run --group pdf python3 build.py pdf` builds the full 43-file book (2.7MB).
  Cosmetic-only warning: 🚀 emoji in ch9 transcript has no DejaVu Mono glyph.
- Phase 7 review protocol drafted at scratchpad/review-briefs.md (per-part 3-agent
  prompts + change summaries + walkthrough/security-audit priorities).
- LANDED wave 3/4 (all verified, no coordinator fixes needed unless noted):
  ch20 verify-only (fixed 2 stale dotted imports + four-vs-eight enumeration;
  flagged examples/logicsigs/contract_account.py → I extracted it, compiles ✓;
  recorded ch20's PED-1 deviation in scratchpad/review-log.md); ch12 (mint →
  opt-in-problem → deliver split, deliver_nft reason-before-code, RIF trimmed);
  ch13 (spec box retrofit, IL Example 13-12 demoted to client-side float —
  P5: extract as script NOT contract; overflow-horizon trimmed keeping ch14's
  two cited anchors; Vestige/Folks cut; NO renumbering — all 13-* citations
  stable). check_book gained "examples.ch" stale-string rule (caught 1 in ch6,
  fixed).
- RATE-LIMIT EVENT: session limit killed 9 agents mid-flight (~12:0x); user said
  continue after reset; all resumed via SendMessage (context intact). ch19's
  edits verified complete by me (no report; ticket-purchase move + PUB-4 ✓).
- LANDED wave 3/4 (continued): ch15 (diff dropped/full listing kept, atomicity
  gotcha beside Example 15-11, compile_contract IOU, spec box + acceptance);
  ch18 (spec box, rounding-slab moved after beacon intro, exercises de-nested
  to lettered items); ch5 (spec box + story-as-consequence, array section →
  scratch, I/O breather with worked 52nd-signature numbers, NEW Example 5-24 =
  guestbook_fixed full listing byte-identical to disk); ch10 (spec box +
  consequence + acceptance replay, ensure_budget KEPT behind labeled
  IOU note (1,900-unit ed25519verify_bare — genuinely needs it), scratch pair
  now Gatekeeper/Protected with app-id-pinned authorization (compile-verified),
  GlobalMap wall → bullets, exercises de-nested, fixed stale "Part I ended"
  bridge); ch3 (recovered own mid-edit state: Figure 3-1 restored; spec box;
  suspense killed in-section; type-tour compressed → scratch; kept 3-4/3-12/13
  as ch5-load-bearing; acceptance close; exercises de-nested with (i)-(vi)
  relabeling).
- Ch9 INTEGRATION DONE (mine): new section "What the Box Actually Holds:
  Bytes, Keys, and Copies" after The Data Model — three-decisions framing;
  head/tail hexdump anatomy + Bid offset predict (ch3 material); Example 9-1
  key_prefix_itob; Examples 9-2..9-5 array types + Table 9-3 (ch5 material,
  ch5-specific ties reworded); closing promises ch17 citation. All 5 examples
  extracted to examples/boxes/ and compile ✓. Ch17 launched with the anchor
  names (Example 9-2, Table 9-3, section title).
- LANDED (final wave): ch22 (VRF → ch18 pointer + price delta, fee-scaling
  gotcha dissolved into single home, spec box; PED-1(d) waived — survey chapter,
  recorded); ch24 (Example 24-7 pausable guestbook — compile+ARC-56-verified,
  PauseToggled event; 24-4 docstring → prose list; renumbered 24-7..9→24-8..10
  + A3/A4 patched; new Exercise 5 folds pause into final listing — omission
  acknowledged; PuyaPy 5.9.0→5.8.1 claim aligned by me in ch24+A3); ch16
  (checkpoint script create_first_pool.py validated LIVE on LocalNet with real
  transcripts, RIF repeat cut → Table 14-1 citation, behavior test listed
  byte-identical to project suite, seed MBR itemized + empirically confirmed
  482,300/400,000, new Table 16-3 → old 3,4 shifted). Ch9 Table 9-3 collision
  (mine) fixed → build-sequence table now 9-4.
- P5 additions: projects/amm-factory stale "Chapter 6" strings (README,
  pyproject, run_amm_factory.py final print — reader-visible); consider
  shipping create_first_pool.py in the project.
- Extraction FULLY COMPLETE: counter_fixed.py reconstructed with ARC-56
  fidelity checks (reset create-list empty, bump readonly=False — matches
  chapter's proof lines). Harness: 0 failed/missing/orphans. Only W2 left:
  keeper.py (LOB rebuild in flight).
- P5 PROJECT REBUILDS LAUNCHED (algorand-expert agents): LOB (from scratchpad
  lob_check/ sources + keeper per Part 5 + Table 21-7 tests + LocalNet
  validation); lottery (from ch19 listings + Won event; old artifacts = ground
  truth minus event; run_lottery per Table 19-1; tests incl. off-chain winner
  recomputation); token-vesting Claimed event + artifact regen + event-log test
  + stale-string sweep across the six intact projects. Governance-voting
  rebuild QUEUED (launch when a slot frees — heaviest, ZK deps; brief: ch23 as
  spec, surviving arc56/teal for GovernanceVoting/VerifierAnchor/
  CommitmentHelper as ground truth, tests per ch23's Production Hardening +
  workflow per Table 23-1 checkpoints).
- FIGURES COMPLETE (Phase 6 done): all 25 real, rasterize-inspected, style-
  consistent; chapter-won judgment calls documented; ch2 three-vs-four
  transcript/caption mismatch fixed (prose now says three).
- Token-vesting/strings agent LANDED: Claimed event in project contract +
  artifacts (selector c2a3d5f7 verified on-chain in logs) + event-decode test;
  12 project tests green; full stale-string sweep table applied across six
  projects INCLUDING a live bug (lp-farming localnet_helpers parents[4]→[3] —
  broken by the P1 dir moves; now fixed). Suggested-params-cache TxID collision
  fixed via note=os.urandom(8) per the chapter's own gotcha.
- CRITICAL FINDINGS (added to algorand-expert Verified API Ground Truth,
  2026-07-31 section): set_timestamp_offset(0) FREEZES LocalNet's clock
  (unfixable except `algokit localnet reset`); ch17 taught that helper — its
  agent has been messaged to fix the chapter + the create="require"-vs-
  bare-create contradiction (ch17:666 vs :1438, also in lp-farming tests).
  **OUR SANDBOX LOCALNET CLOCK IS CURRENTLY FROZEN ~34 YEARS AHEAD** — run
  `algokit localnet reset` AFTER the in-flight rebuild agents finish, then
  re-run: lp-farming suite (expect create-mode failures until ch17-aligned
  tests land), nft-vesting (2 fails), simple-vesting (3 fails),
  constant-product-amm (1 fail: negative test needs
  populate_app_call_resources=False) — all suspected clock artifacts except
  the two named real defects.
- GOVERNANCE-VOTING REBUILT: sources recovered byte-identical from GIT HISTORY
  (old path projects/chapter10/zk-voting, commit ba41981) — not reconstruction;
  arc56 ABI/state identical to surviving artifacts (only toolchain-version
  artifacts differ); 36 project tests green (+8 new: MiMC padding, double-
  reveal, 6 ABI-pinning); workflow prints all Table 23-1 rows incl. the
  previously-never-printed LogicSig budget (142,955 measured); verifier TEAL
  committed-frozen at the chapter's 3,464 bytes (5.9.0 build) with --force to
  regen. Chapter aligned by me: run_zk_voting → run_governance_voting (line 27),
  test_governance_voting.py → test_zk_voting.py (2 spots); forwarding alias
  removed. OPEN ITEMS: (a) chapter listings are a strict subset of the shipped
  contract (schema 6+1 vs 7+2, set_verifier/record_bound_proof beyond
  listings) — pre-existing, README-documented, judge in Part VI review;
  (b) AVM-target inconsistency: amm-factory+lottery pin v12, token-vesting/
  lp-farming/governance default v11 — A2's gotcha claims "the projects in this
  book set it in .algokit.toml"; P8: add the pin to the three (+ artifact
  regen, no LocalNet needed) to make the claim true.
- Git-history recovery hint sent to lottery + LOB agents.
- Part I 3-agent REVIEWS RUNNING (algorand-expert, teaching-pro,
  publishing-pro; protocol in scratchpad/review-briefs.md; deviations ledger in
  scratchpad/review-log.md).
- LOB PROJECT REBUILT: contracts byte-identical to chapter listings; keeper/
  helpers/tests verbatim where the chapter lists them; 35 tests green (9
  LocalNet + 26 static), Table 21-7 names match exactly; walkthrough blocks
  assembled verbatim and run clean; expiry flakiness fixed with commented
  20-round headroom; round-based → frozen clock irrelevant. I sharpened three
  Table 21-7 rows to the verified refusal reality (LogicSig last_valid bound
  fires for expiry, two-fill path for overfill, asset_close_to on the axfer
  side). CHECKER NOW FULLY CLEAN: 0 errors, 0 warnings.
- P8 item: root README.md chapter list is still book-1 numbering — rewrite
  against the new spine.
- PHASE 4 COMPLETE: ch17 landed (create-mode fix factory.send.create.create(),
  reset_localnet_time purged + one-way-offset gotcha, real suite listings,
  overflow audit table, factory-check Exercise 5, ch9 anchors redeemed).
  Ch15 handoff cell aligned ("defers to its final exercise").
- LOTTERY REBUILT: reconstruction proved byte-identical to git history before
  adopting it; Won-event-only artifact diff (8 opcodes, prefix d29c5c0a);
  51 tests green; all Table 19-1 rows + event line. Ch19 fixed by me: 223→231
  (emit costs 8; noted simulate reports 2,100 vs AVM's 1,400) + Won row in
  Table 19-1.
- APPENDICES GENERATED + DRIFT-LOCKED: A3 (97 gotchas) + A4 (236 finder rows)
  from inline sources; test_generated_appendices_in_sync added; 39 tests green.
- LOCALNET RESET DONE (fresh clock). lp-farming sync agent running (ch17's
  enumerated deltas + post-reset re-runs of nft-vesting/simple-vesting/
  token-vesting + constant-product-amm populate_app_call_resources=False fix +
  --target-avm-version=12 pins for 3 projects).
- TEACHING-PRO PART I REVIEW: all fixes applied EXCEPT H5 (ch3 third-failure
  transcript — needs algorand-expert-verified content; pending its Part I
  report). Applied: B1 ch8 full retrofit (evidence commission + reader-owned
  reframes + acceptance close vs suite) + H8 events transcript (real bytes
  c2a3d5f7/151f7c75); B2 preface map regenerated (24 chapters, Ch1 added,
  Part I/II boundary fixed, 4 appendices + checkpoint sentence, guided-builds
  ¶ updated); H11 conventions split described honestly + 9-kinds → real
  8-kinds incl. commission; H1 ch2 spoiler → symptom-only + labeled pointer;
  H2 ch2 pre-commission diagnostics neutralized; H3 conventions → note div
  AFTER analysis ¶; H4 predicts ×3 ch1 + ×2 ch2 + 1 combined checkbox ch1;
  H6 habits: F4 now points at ch1's triple + 2 additions, spends in ch2
  (habit one applied); H7 loop-closes: ch8-Ex5 row in Table 9-2, ch4-Ex5 in
  ch7 bridge, ch3-Ex5 in ch6 386-¶ (ch2-Ex5 close SKIPPED — no precise home;
  logged as open); H9 ch24 echoes (¶103 → delta framing, objective rewritten,
  Q2 tagged From-Ch8); H10 08z pointers + ch3/ch8; ch4 retrieval header.
  Open from review: H5; ch5 habit-two spend (skipped — weak anchor); ch2/ch5
  exercise splits + ch7 Ex5 upgrade (logged, low priority).
- PART I REVIEWS ALL IN; blockers fixed by me:
  - algorand-expert: B2 baseline → 5.8.1/3.5.0 (F3 + ch5); B3 ch2 inner-call
    sender absolute corrected (A→B inner app call: B sees A's app address;
    labeled ch15 IOU); H1 ch3 rename-selector claim fixed (name= pinning);
    H2 registry_fixed .native → .as_uint64() (compiles); H3/H4 ch4 bills
    itemized (634,500 creator / 150,000 opt-in / 62 ceiling); H5 ch7 balance
    declared authoritative in correction four. Verified-correct list recorded
    in its report (do not re-litigate).
  - publishing-pro: B1 PDF callouts — tcolorbox BOAcallout env in metadata +
    CALLOUT_PDF_FILTER lua in build.py (verify on next pdf build); B2 mdBook
    table captions → <p class="table-caption"> + CSS; B3 part-intro-*.md pages
    now generated into SUMMARY (7 ✓); B4 appendix headings "Appendix X: ... {-}"
    (generator + A1/A2 by hand); B5 F3 contributor commands corrected; H1
    promises narrowed (F2:15, F3 examples claim, F4:53) + .github/workflows/
    validate.yml ADDED (pytest + check_book + harness) + manifest chapters/
    coverage renumbered to new spine + harness pins --target-avm-version 12
    (26/26 green); H6 F3 client-style ¶ inverted to typed-first; H7 F3 block-
    role taxonomy (incl. banned "Outline") replaced with the numbered-example/
    annotation system; metadata date → July 2026.
  - Part I polish agent RUNNING: gotcha splits/trims, exercise de-nesting to
    ch3 standard, corrected-listing Examples 2-10/3-22/4-21/7-25 (ch8 =
    recorded PUB-3 deviation), unnumbered-listing framing, acceptance ¶s →
    lists, apparatus normalization (ch1 → \BOAkind{Setup} + spec trim),
    aphorism cuts, ch3 third-failure success transcript.
  - Judged-acceptable (logged, not fixed): ch8 commission placed after the
    "Evidence" orientation section (PED-1 CI clause satisfied — objectives
    precede first transcript); metadata author field left "Generated with
    Claude" (user's call).
- PART II TEACHING REVIEW in; my quick fixes applied (all green): B1 ch9 wrong
  trailing checkpoint section DELETED + book-wide sweep of "Mastery Checkpoints
  appendix" → "printed on the next page" (6 chapters); B2/H13 next-chapter
  sentences fixed (ch9 → 10/11-then-12 deferral, ch12 → ch13 register-change);
  B3 delta list corrected (divmodw → Changed with deviation note; asserts →
  new "Not yet done, on purpose" bucket, honestly closed via stranger-tests
  since no exercise adds messages; struct mapping precision); H1b fourth
  "genuinely new" bullet + 1389 exception clause; H9 WYNF prose names the
  ch8-Ex5 exception + row HOISTED to first + Example 2-5 miscite merged into
  the richer 3-14 row; H10 four-year framing fixed (schedule length is an
  argument; four-year = ch8's default; testing ¶ → multi-month); H5 both
  predicts fixed (Bid-offset answered in place; overflow predict moved above
  its reveal with in-place confirmation).
- QUEUED for Part II polish agents (launch after Part II algorand+publishing
  land): general agent — H1a/H2 array-section split-to-point-of-use (with
  9-1..9-5/Table 9-3 renumber ripple incl. ch17's citations), H6 ch10
  commission hoist + Figure 10-1 relocation, H8 exercise-anchor Handoff rows
  (10-1/11-1 + ch12 mirror), H11 ch12 concept repoints (105/288/543/675),
  H12 ch12 NFT/ARC-3 primers → felt-problem form, suggestions (WYNF 28-row
  split framing, ch12 opening voice, 12z heading match); algorand-expert
  evidence agent — H3 third checkpoint after revoke + real transcripts for
  all three ch9 checkpoints, H4 probe-two script, H7 ch11 splitter re-run +
  requirement-by-requirement close (real held() transcript), verify my
  recomputed 12-month threshold framing.
- PART II PUBLISHING REVIEW in. Quick fixes by me: B3 capitalization regression
  (my sweep's lowercase "the" ×6) fixed; ch12/ch17 H1 headings → colon form
  (spine match); ch17:1680 wrong next-chapter sentence → ch18 randomness
  (last of its class per the reviewer's sweep). Verified-passing list recorded
  in its report (PUB-4 both RIFs, PUB-13 reciprocity, dashes, fences, captions).
- BOTH Part II fix agents launched: general polish (work order at
  scratchpad/part2-polish-brief.md — array-section split-to-use w/ renumber
  ripple, gotcha surgery ×4 + 7 trims, Examples 10-17/11-17 corrected
  listings, ch11 de-nesting + spec close, client-note relocation, we-sweep,
  formatting, ch10 commission hoist, ch12 primer recast + repoints, handoff
  loop-close rows, exercise label/order + pointer updates, ch9 reader-owned
  opening) and algorand-expert evidence agent (ship test_vesting_unit.py +
  fix fourteen-count citations empirically, print the 4 test helpers working,
  real transcripts for ch9's checkpoints + NEW third checkpoint after revoke,
  grouped create_schedule client call, ch11 splitter acceptance re-run with
  real held() numbers, verify overflow framing).
- OPEN POLICY ITEMS (for P8/user, from publishing RB1-RB3): (1) PUB-3
  majority-practice — 12 of 15 repair diffs still use pointer-plus-elision;
  ch5/6/10/11/20 now model the listing form; either finish the sweep or amend
  PUB-3 per META-1. (2) PUB-7 budget exceeded by 39 of 100 gotchas book-wide
  (Part I polish agent covers Part I's; Part II agents cover Part II's; parts
  III-VII pending). (3) PUB-1 annotation coverage 11% — Part II extraction
  pilot NOT yet assigned (RB1; candidate for a dedicated wave). (4) Suggested
  checker additions: tests/-path resolution + exercise-label linting.
- PART II TECHNICAL REVIEW in (33 listings compiled clean; assembly matches
  projects; MBR/fee/overflow arithmetic verified; error strings exact except
  one). My fixes applied: B4 test-static claims (ch9+ch12 "still runs the"),
  B6 ch12 user-summary now mint→coordinate→deliver, B7 ch12 inner-call
  decision ¶ added beside claim (holder-is-holder defended + cost named),
  H1 8,192→2,048-page reality ×2, H2 fee string → "(needs 1mA more)" (ch11 +
  ch19), H3 Example 11-4 gains funder assert per ch10's categorical gotcha,
  H4-partial (line-228 handled via B6; delta-list deliver_nft bullet → polish
  agent's ch12 zone), H6 → REMAINS for follow-up, gatekeeper method-pin
  sentence added (ch10), padded-calls wording, Table 9-1 row wording.
  CRITICAL: set_timestamp_offset(N) is PER-BLOCK (year-per-block poisoning
  observed) — ground truth updated; both LocalNet agents told to normalize
  offset to 1 in fixtures/teardowns (never 0).
- FOLLOW-UP TASK QUEUED (small evidence-type agent when a slot frees):
  ch12+projects/nft-vesting carry the Claimed event forward (like
  token-vesting; H5/ALG-15) + acknowledge-or-message ch12's six bare asserts
  (silent ALG-13) + H6 asymmetry clause citing ch9's fourth-question argument
  + H4 delta-list deliver_nft bullet if polish agent's run misses it.
- LP-FARMING SYNC agent LANDED: all four tasks done. Full project matrix green
  in clock-safe order (simple-vesting 15 / nft-vesting 14 / token-vesting 33 /
  constant-product-amm 12 / governance-voting 36 / lp-farming 10; node left at
  offset 1). The "clock artifact" failures were REAL bugs: nft-vesting claim
  helper needed a note (TxID dedup), simple-vesting imposter needed tokens
  before the admin check could be reached — both fixed. normalize_localnet_time
  (offset=1) + advance parks-at-1 implemented and poison-tested (366-day
  standing offset → suite still green, node back to 1). AVM-12 pin added to
  token-vesting/lp-farming/governance __main__.py (byte-identical TEAL,
  pragma 12). NEW ground truth: time-jumped LocalNet never comes back —
  wall-clock suites BEFORE offset-jumpers or reset between (recorded in
  agent file). REMAINING ALG-16 spread (out of scope, P8): constant-product-
  amm, nft-vesting, simple-vesting, limit-order-book still pragma 11.
- CHAPTER-SYNC FOLLOW-UP agent launched (ch17 items 1-4: normalization rule,
  conftest note, import block, honest accumulator numbers 30,951/25,695;
  ch14 items 5-6: import block + populate-disabled claim; ch12: Claimed event
  into project+chapter, deliver_nft delta bullet, six assert messages,
  fourth-question clause, printed-suite alignment).
- PART I POLISH agent LANDED: all 8 items done (5 gotcha splits + 11 trims;
  ch2-8 exercises de-nested to lettered standard, zero compounds; Examples
  2-10/3-22/4-21/7-25 added byte-identical to disk (ch8 = recorded PUB-3
  deviation with in-text acknowledgment); variation-framing for unnumbered
  listings; acceptance ¶s → numbered lists + new Tables 5-3/5-4 (old ch5 3/4
  → 5-5/5-6); ch1 → \BOAkind{Setup} + spec trimmed to 3; aphorism cuts;
  ch3 third-failure success transcript 1067-vs-1042). A3=103 entries,
  A4=239 rows, all gates green. NOTE: whoever finishes last re-runs
  generate_appendices before central build.
- Parts IV-VII 3-agent review panel LAUNCHED (files ch18-24z + A1/A2/A3/A4 +
  Z1-Z4 split across roles; briefs emphasize delta-recap verification,
  checkpoint apparatus, generated-appendix quality, ALG-10/11/12/15).
- PART III TEACHING REVIEW in — items HELD for consolidated fix wave after
  its sibling tech+pub reviews land. Summary: B1/B2 ch17 composition section
  re-teaches ch15 (compress ~60%, fix "operated in isolation" claim);
  B3 ch17 Exercise 4 contradicts ch6's block-seed refutation (invert into
  the ch18 bridge); H1/H2 ch13/ch15 DEFECT-comments spoil predicts;
  H3 ch15 headline defect before commission; H4 ch17 predict t=50 vs trace
  t=100; H5-H9 missing transcripts/checkpoints (ch15 ×2 + build step, ch13
  repair re-run, ch14 third checkpoint after :765, ch17 lifecycle checkpoint
  + naive-farm failure trace table from the stranded :1591 numbers);
  H10 ch15:700 handoff row names farm not factory; H11 ch16 manual-encoding
  delta sentence; H12 ch16 WYNF 15-11 predict unanswered (+sentence after
  :337); H13 TWAP-optional labels (16:930 exercise, 17:1355 clause, 14:823
  claim); H14 loop-close naming (13:828 + 16:85 clauses); H15 ch17 Table
  17-2 + Table 16-4/Example 9-2 rows; H16 ch14:811 reentrancy re-teach →
  clause + ch17:1336 gains (Example 8-7); H17 ch17 inner-ceilings gotcha
  DELETE (15's material, unused here); H18 accumulator printed numbers need
  block-count adjudication (route to expert); + suggestions list (17z pointer
  to Table 16-4, verify_pool whole-listing pointer, RIF-prediction settles,
  16:922/17:1693 exercise cross-naming, 13:789 retag, 14 IL dedupe).
  Verified-sound list recorded (PED-12 clean, both retrofit orders correct,
  ch16 checkpoint = model).
- PART II POLISH agent LANDED: all 15 items (array section split to three
  landing points — 9-5→9-3 renumber, two examples compressed to Table 9-3 rows
  with files as intentional harness-covered orphans; gotcha surgery complete
  incl. new #inner-rekey-yours-to-not-set + ch20 twin trim; Examples
  10-17/11-17 byte-identical; ch11 de-nested + spec close; we-sweep zero
  remaining; ch10 commission hoisted + Figure 10-1 relocated; ch12 primers
  recast + repoints to ch5/6/7; loop-close rows in Tables 10-1/11-1/12-2;
  Bloom reorders with pointer updates ch9→Ex5, ch12→Ex8). Cross-chapter:
  ch17:117 citation reworded to three landing points; ch5:914 IOU repointed to
  "beside the claim method". Deviations logged (review-log 5 & 6). NOTE ch20
  #logicsig-params-are-compile-time 156w → fold into Parts IV-VII fix wave.
- PART III PUBLISHING review in; merged fix work order STAGED at
  scratchpad/part3-fix-brief.md (A: evidence items incl. transcripts,
  checkpoints, client unification, TWAP landing listing, Example 13-13/15-14
  numbering; B: 25 editorial items; C: technical addendum pending).
- PARTS IV-VII TEACHING + PUBLISHING reviews in; merged fix work order STAGED
  at scratchpad/part47-fix-brief.md (28 teaching items + 17 publishing items
  + 6 evidence items; tech addendum pending). Launch order per part: evidence
  agent FIRST, then editorial (same-file conflicts; ch23 facts must be
  adjudicated before its editorial rewrites). Coordinator rulings recorded in
  the brief: 23:950 Recall→Evaluate (teaching-pro wins), 20:644 add third
  backward question, A2-gotcha harvest via generator extension (option 1,
  lower-risk than relocating callouts into polished ch11), ch19 close-template
  adopted book-wide (ch12/14/16/17 added to part3 brief item 26; ch21/23 in
  part47 brief item 38).
- PART III + PARTS IV-VII TECH reviews in; both briefs now COMPLETE
  (part3-fix-brief C-addendum: 23 items; part47-fix-brief tech addendum:
  T1-T20). Notable tech findings: ch17 Ex4 shipped the block-seed
  anti-pattern with a false rationale (inverted to diagnosis); 197-day
  multiplier is 2495 not 2500; test-static compiles nothing (4 sites);
  ch13's four phantom-test claims → real drivers into examples/pricing/;
  A2 Table B-4 wrong in 5/8 rows (ec_* is v10, falcon_verify v12,
  RejectVersion is an exclusive floor); LOB pause guard has no lever →
  deleted; LOB fill fee 3,000 not 4,000; `>=` MBR payments strand excess →
  `==`; ch23 ships MORE than it admits (set_verifier + record_bound_proof
  are real and tested — chapter reframed to surface them); 6 dead puya doc
  links in Part III + 23 book-wide (sweep agent ledgered below).
- CHAPTER-SYNC follow-up DONE: ch17 normalization rules as three named
  disciplines + conftest note + import block synced; ch17 accumulator
  walkthrough now EMPIRICALLY MEASURED (alice 30,951 / bob 25,695 / head
  dust 1,754; 30,951+25,695+1,754 = 58,400 exact; block-granularity
  explained) — supersedes part3 brief C.6/T3-H1, Part III agent will skip;
  ch14 import block + populate_app_call_resources=False explanation landed
  (overlaps C.8/T3-H3 — Part III agent must re-read before editing);
  ch12+nft-vesting: Claimed event (selector c2a3d5f7 verified) + event test
  (suite now 15), six asserts messaged both sides, fourth-question ALG-6
  clause, printed suite rewritten verbatim-from-working-files (~305 lines);
  nft-vesting advance_time upgraded to clock-checking version (sibling
  pattern; order-independent). Gates at its finish: check_book 0/0, root 39,
  nft-vesting 15, lp-farming 10, AMM 12. NOTE: projects artifacts/ are
  gitignored — readers/CI must `algokit project run build`.
- PART II EVIDENCE agent DONE — Part II is now fully review-fixed. Landed:
  tests/test_vesting_unit.py (21 real unit tests; ch9 citations now say
  twenty-one; Exercise 5's both-mutations claim verified empirically and
  mutation-checked non-vacuous); the four printed LocalNet helpers now run
  (4 real defects fixed in printed code: idempotent deploy → bare create +
  os.urandom note, missing static_fee 2,000, missing beneficiary opt-in →
  5th helper onboard_beneficiary, double-claim test moved past full vest);
  3 real checkpoint transcripts (full algokit-utils 4.2.3 error shape,
  new post-revoke checkpoint 3); probe-two grouped create_schedule call
  printed; ch11 splitter acceptance re-run real (held 1,000,001, dust 21,
  "Four for four"); overflow framing verified exact. token-vesting suite
  now 36 (9 shape + 6 LocalNet + 21 unit), stable ×3. Toolchain bug in
  agent KB: algorand-python-testing 1.1.0 baremethod AttributeError →
  workaround active_txn_overrides on_completion NoOp. token-vesting
  advance_time upgraded to clock-checking version (4th project on the
  pattern); coordinator added the one-clause acknowledgment after ch9's
  #localnet-time-needs-blocks gotcha (naive = fresh-node shape; shipped
  helper reads the clock back; forward pointer to ch17's rules).
- EV-A DONE (Parts IV-V evidence): ch22's two transcripts real (VRF via
  go-algorand's crypto_test.go vector; 9,000-fee run has exactly 8 inners;
  gates-nothing 37,637 confirmed on-chain, closing sentence corrected —
  receiver is template-pinned so the harm is scheduled draining, not
  redirection); ch21 compile checkpoints validated (real TMPL_ parse error
  reproduced); A2 Table B-4 re-derived (5 wrong rows), RejectVersion fixed
  (exclusive floor), Table B-2 +3 ec rows (review's g2 msm 10,600 corrected
  to 7,200+270); LOB: 29 bare asserts eliminated, pause/admin/fee_bps AND
  initialize deleted (schema 1 int 0 bytes, ABI 4 sigs), fill fee 3,000
  (incl. scripts/keeper.py), MBR == , suite 37 (28 static + 9 LocalNet),
  --target-avm-version=12 pin ADDED (was silently v11; A2 gotcha reworded —
  pin lives in smart_contracts/__main__.py); ch18 Example 18-4 group-size
  guard added; 19z design check: buildable, 4 wording adjustments recorded
  in brief for editorial. LogicSig asserts stay bare (no ARC-56 sidecar —
  verified) with acknowledging paragraph.
- EV-B DONE (Part VI evidence): ADJUDICATION — project ships the trustless
  path (real PLONK proof through the real 3,464-byte AlgoPlonk LogicSig,
  142,955/160,000 measured; Go needed only to change the statement). ch23
  reframed: new "What Runs and What You Complete" section (admonitions
  10→5), record_bound_proof printed as Example 23-1 (finder line, no
  extract), test-outline block (~185 lines) → Table 23-6 from the real
  suite, TABLE RENUMBER old 23-6/23-7/23-8 → 23-7/23-8/23-9; 23 asserts
  messaged; commit MBR == (+ under/over test); compiler-provenance caveat
  (5.9.0 = 3,464 vs pinned 5.8.1 = 3,483, different address); one budget
  figure (~143,000); size-pooling sentence (4 txns for size, 8 for budget);
  padding-gap named; Exercise 5 retargeted to hardening the generated
  verifier (replayed proof can rekey the verifier account — verified
  griefing path); ch23 now 947 lines; suite 40 (20 static + 20 on-chain).
- Coordinator: G2-encoding + ec-costs + size-pooling facts added to
  algorand-expert KB ("AVM cryptography opcode facts"); pragma-12 gap now
  3 projects (constant-product-amm, nft-vesting, simple-vesting — LOB
  fixed by EV-A); root pytest gate = 38 + test_generated_appendices_in_sync
  expected-fail until coordinator regenerates after last chapter editor.
- PARTS IV-VII EDITORIAL agent LAUNCHED (items 1-45 + T5/T10/T11/T12/T16/
  T19 + post-evidence adjustments section in brief; scope ch18-24, four
  checkpoints, Z1/Z2/Z4, F3/F4, A1/A2, two new figures, generator EDIT
  (no run), manifest renames; projects frozen for it).
- PART III EVIDENCE agent DONE: all transcripts real (ch15 payroll pair —
  worker `balance 0 below min 109700`, impostor settle 25000000; ch13
  repair re-run product +999,997 feeding "Five for five"; ch14 third
  checkpoint from real run 990099009/499999999/491048836 with min()-penalty
  + two-floors prose; ch17 lifecycle checkpoint 6,422-of-6,424 two-floors
  derivation; ch17 naive-trace = NEW Table 17-3 → old 17-3..17-8 RENUMBERED
  17-4..17-9); ch17 Exercise 4 inverted to 4-part (Debug) reject-the-PR;
  multiplier 2495 + ALG-4 clause; 9 new examples/pricing/ files CI-wired
  (13-13 two_sided_quote, 13-9 quote_client script-mode, 13-10
  first_depositor, 13-11 price_accrual + tests + 2 compile-mode foils) —
  all four ch13 test claims now TRUE; ch14 asserts messaged + 7 messages
  aligned to project + swap/remove restructured to project shape (inner
  transfers after writes), :391 dead assert dropped with comment; ch17
  client unification done — ch14:254 promise STANDS (fee is 3,000 not
  review's 4,000 — initialize has 2 inner opt-ins); Example 15-14 numbered;
  ch16 lifecycle-stance section + measured Ex-6 numbers (1,357/1,988/2,048/
  +224 oracle delta); Vault waiver cites Example 7-8 (ch14 has no numbered
  examples — review corrected); TWAP oracle prints as ONE UNNUMBERED block
  (recorded deviation: numbering would create the only numbered example
  with no CI mode). Suites: AMM 12+7, factory 9+6, farm 10+5; compile 26
  ran 0 failed; check_book 0/0.
- OPERATIONAL: shared LocalNet dev clock now ~3 years ahead of wall time
  (lp-farming workflow re-runs). Offset parked at 1 s/block. Wall-clock
  suites (token/nft-vesting) have clock-checking helpers and survive; never
  reset while agents run.
- PART III EDITORIAL agent DONE (all B 1-26 + C-(ED) items; gates green;
  template harmonization landed ch12/14/16/17 — Summary/learned-to/Features
  tables deleted (each chapter's last table, numbering stays dense), Further
  Reading folded to first-citation points; ch16 exercise ladder remade
  monotonic (old 6→4 as Evaluate, relabels recorded); gotcha inventory:
  deleted #inner-txn-ceilings, added #clearstate-cannot-send-inners +
  #schema-for-future-fields, edited #spot-price-is-manipulable +
  #lp-token-optin-first — appendix regen pending; fixed evidence residue
  "Tables 17-3..17-5" → 17-4..17-6; NOTE ch14/16/17 retain pre-existing
  we/our outside edited regions — optional register sweep, Phase 8 call).
- COORDINATOR closed the pragma item: --target-avm-version=12 pinned in
  constant-product-amm, nft-vesting, simple-vesting (__main__.py, lottery's
  comment form); artifacts rebuilt, pragmas verified 12; suites 12/15/15.
  simple-vesting's naive advance_time upgraded to the clock-checking sibling
  pattern (5th project) — its 2 time-dependent tests failed on the shared
  3-years-ahead LocalNet until then; no chapter prints that helper (drift-
  free). ALL 9 PROJECTS now pin AVM 12.
- COORDINATOR closed the inline-code filter item: INLINE_CODE_PDF_FILTER
  added to build.py (Code handler; \allowbreak after ._/:-=,( in spans
  >=15 chars, full TeX escaping, no hyphens ever) + wired into the pdf
  command; \emergencystretch=2em added to metadata.yaml preamble.
  Verified: narrow-measure xelatex test breaks at legal points; residual
  overfulls only at pathological 6cm measure (no-glue mono tiling), fine at
  the book's 470pt. Z4:9's colophon claim now TRUE. Remaining P8 PDF check:
  confirm textwidth figure during the real build.
- PARTS IV-VII EDITORIAL agent DONE (all 45 editorial + 6 [ED] tech items;
  notable: 19z rebuilt as random-assignment checkpoint w/ EV-A's 4
  adjustments (fallback corrected to 3 addresses/slot — 128-byte K+V
  ceiling); ch24 + ch19 + ch20 + ch23 commissions added; ch22 commission
  closed item-by-item w/ priced-tour waiver named in-text; ch21/23 "Part N"
  headings renamed descriptive (TOC collision gone); ch23 tables cascaded to
  dense 23-1..23-9 + SC-vs-LS table moved to A2 as NEW Table B-4 (old B-4
  AVM-versions → B-5; B-1/2/3 meanings preserved for frozen ch11/22/23
  refs); template harmonization ch21/23; generator extended (A1/A2 harvest
  as "From Appendix X", {-} on all appendix headings) + A4 uncaptioned-note;
  manifest renamed to topic paths; figures fig-21-1-hybrid-architecture.svg
  + fig-23-1-proof-group.svg authored; Z2 +8 entries; F/Z promise absolutes
  → F2 hedge. Deliberate notes: ch20 PED-1 deviation stands acknowledged;
  no silent breaks).
- PHASE 7 COMPLETE. Coordinator close-out: F4:19 sibling absolute hedged
  (reworded twice — first draft claimed a finder "path column" that does
  not exist; corrected to the # path header-comment fact); appendices
  REGENERATED (A3 108 gotchas incl. 3 from Appendix B; A4 243 rows); FULL
  GATES GREEN: check_book 0/0 across 43 files, compile harness 0 failed,
  root pytest 39/39 (appendix-sync now passes); mdbook build clean (no {-}
  leaks, new figures embedded).
- PHASE 8 progress: README rewritten to the 24-chapter/7-part spine (parts
  + 9-project table + repo layout + honest validation section); full PDF
  BUILT with the new inline-code filter (3.5 MB, 27 figures, exit 0) — one
  missing-glyph warning fixed (ch1 transcript 🚀 trimmed); Z4 colophon
  corrected to MEASURED values (469.75pt measure, 13.6pt baseline, via
  \showthe under the book's class+geometry+font; was 470.4/12.65).
- SWEEP agent DONE: 13 puya .html links fixed across 6 files (5 from the
  verified map + 6 derived and curl-verified 200: lg-arc4/structure/types/
  data-structures/opcode-budget → language-guide/<name>/, api-algopy.html →
  api/algopy/algopy/); Uniswap v4 whitepaper link → uniswap.org/
  whitepaper-v4.pdf; 19 distinct URLs GET-checked, rest alive (pera 403 =
  bot protection, left); register sweep ch13-17: 24 prose rewrites, we/our
  now 0 except ch14:142 (code comment matching shipped project source —
  legitimate survivor). Gates green.
- FINAL BUILDS: mdbook + concat rebuilt from final state; final PDF built.
- Agents in flight: none. PHASE 8 COMPLETE — final PDF rebuilt clean (no
  glyph warnings), final gates 0/0 + 39/39. THE REWRITE IS DONE. Nothing is
  committed; committing/pushing is the user's call. This file is the full
  record and can be deleted when the rewrite ships. NEXT when both
  land: coordinator regenerates appendices, full gates, mdbook build, then
  Phase 8 (final builds, README respine, 3 remaining pragma pins,
  walkthrough/security passes, dead-link sweep, inline-code Lua filter,
  final summary). NEXT after each evidence agent lands: launch its
  editorial counterpart (Part III B+(ED) items; Parts IV-VII editorial
  items 1-45 + (ED) tech items) — editorial NEVER concurrent with evidence
  on the same files. After the last chapter-editing agent: regenerate
  appendices + full gates.
- P8-pre additions (coordinator): book-wide dead-link sweep agent
  (23 stale algorandfoundation.github.io/puya/*.html hits across
  09/12/14/16/17/21/23/Z3 — Part III's 6 fixed in-wave with verified
  replacements; consider CI link-check); go-algorand master changed the
  box read-budget error format (future-revision watch only, book pins
  4.7.x and is correct).
- P8 additions (coordinator): implement inline-code break Lua filter in
  build.py (Z4:9 promises it; PDF needs it) or cut Z4:9 sentence; verify
  Z4:9's "470.4pt measure" against \showthe\textwidth during PDF build.
- P7 note from ch3: PUB-11 lettered-exercise format renders differently in
  mdbook vs pandoc — eyeball in central build. P5: extract counter_fixed.py
  (ch3) after its text settles.
- P5 additions found by agents: projects/constant-product-amm stale "Chapter 5"
  strings; P5 must rebuild lost project sources (limit-order-book, governance-voting,
  lottery) from chapters + typed-client ABIs; token-vesting + lottery contracts gain
  events (+ artifact regen); simple_vesting trio DONE (examples/proving_it_works/
  broken+fixed+events + 7-test suite, all green).

## Review list (flags found during mechanical passes — resolve in editorial phases)

- "Appendix A" setup pointers → rewire to Ch 1: 02 (was 01-c) lines ~388, ~526;
  09 (was 03-p) lines ~125, ~1236; F4-how-to-use line ~49.
- Part-membership sentences: 23 "Part N" refs — audit each against new membership.
- Old part titles in prose/checkpoints ("Value in Motion", "Randomness and Fair Draws",
  "Logic Signatures and Stateless Programs", "Cryptography and Zero-Knowledge Proofs").
- Preface conventions wall → move beside first transcript in Ch 2 (PUB-12).
- F4 "Do Appendix A first; every chapter after Chapter 1 assumes LocalNet" → Ch 1 wording.
- validation/manifest.json "chapter" fields still book-1 numbered → renumber in P5.
- tests/, projects/ internal READMEs may carry old paths → sweep in P5.

## Recorded rule deviations (durable copy; RULEBOOK requires the review to record deliberate breaks)

in-text acknowledgment still stands.

1. **ch20 / PED-1 + PED-4 (opening order)** — no `::: {.spec}` commission box;
   the "allowance that could not be cancelled" story precedes objectives.
   BOOK-PLAN §7 deliberately preserves this chapter ("keep essentially as-is —
   best-paced chapter in the manuscript") and gave it no retrofit item.
   Recorded by the ch20 verification agent; left unfixed on plan authority.

2. **ch9 / PUB-5 (one client style)** — teaching scripts use the generic client
   while Ch 1/2 and the project's tests use typed clients. Acknowledged in-text
   ("A note on client style" ¶, now placed directly before the first generic-client script): watching the transaction get
   assembled is the lesson; typed clients populate references invisibly. The
   project's suite shows the typed register.

3. **A2 appendix / PUB-1 (numbered examples)** — the legacy foreign-array
   listing in Appendix B is unnumbered (appendix reference material outside the
   chapter numbering scheme) but still CI-enforced via its
   `<!-- example: examples/costs/legacy_foreign_array.py mode=compile -->`
   annotation + file header. The [GEN] intent (compiles on every commit) holds.

4. **ch17 / PED-16 dependency omission** — the farm deliberately skips the
   Ch 16 factory-provenance check; text says so; wave-4 ch17 agent adds the
   restoring exercise (per plan §7). Verify after it lands.

5. **ch9 / content compression** — Examples for ReferenceArray/ImmutableArray
   compressed to Table 9-3 rows + contrast sentences (scratch-slot detail and
   the expression-result-ignored predict dropped; files remain harness-covered
   as chapter-orphans by design). Intentional, per Part II teaching review H1.

6. **ch9 / lone H3 "What the Box Actually Holds"** — kept as an H3 over the
   pre-claim landing so ch17's citation stays true. Structural oddity accepted.

7. **ch14 / PUB-1 (numbered examples carry CI modes)** — the TWAP oracle
   prints as one complete but UNNUMBERED listing ("The Oracle in One
   Piece"): it is a class-body fragment, so it cannot carry a CI mode, and
   numbering it would create the book's only numbered example without an
   enforcing check (the PUB-14 failure). Recorded by the Part III evidence
   agent, 2026-07-31.
