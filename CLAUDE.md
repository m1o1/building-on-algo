# Building on Algorand - Book Repository

## Source of Truth

**`chapters/`** is the canonical source for the book. Each chapter is a separate `.md` file. The mdbook HTML site and PDF are derived outputs.

- `chapters/metadata.yaml` -- Pandoc YAML frontmatter (title, fonts, LaTeX config)
- `chapters/F*.md` -- Front matter (Legal Notice, Preface)
- `chapters/01-*.md` through `chapters/09-*.md` -- Numbered chapters
- `chapters/A*.md` -- Appendices (Cookbook, Gotchas)
- `chapters/Z*.md` -- Back matter (What's Next, Glossary, Bibliography)

## Build Commands

```bash
# Build the mdbook (static HTML site) - outputs to mdbook/book/
python3 build.py mdbook

# Build the PDF (requires pandoc + xelatex)
python3 build.py pdf

# Build both
python3 build.py all

# Reconstruct single Building-on-Algorand.md from chapters
python3 build.py concat
```

## Workflow

1. Edit the relevant file in `chapters/`
2. Run `python3 build.py mdbook` to regenerate the HTML site
3. Never edit files under `mdbook/src/` directly -- they are overwritten on each build

## Project Structure

- `chapters/` -- Chapter source files (the canonical book content)
- `build.py` -- Unified build script (mdbook, pdf, concat)
- `.claude/agents/` -- Specialized review agents and their knowledge bases (see below)

## Agent-Based Quality Assurance

Four specialized agents live in `.claude/agents/`, alongside two knowledge-base files that are read, not run. **Every substantive change to the book must be reviewed by the three specialist agents, and every round of fixes must then be reviewed by `diff-reviewer`, before the change is considered complete.**

"Trivial" is not a category the author of a change gets to assign to their own work. A change is trivial only if it touches no code fence, no number, no identifier, no error string, no cross-reference and no figure. A typo fix inside a `::: {.gotcha}` callout is not trivial; a whitespace change in a `.mmd` figure source is not trivial. When in doubt, run the review.

### The Agents

| Agent | Role | When It Catches Problems |
|-------|------|--------------------------|
| **algorand-expert** | Algorand distinguished engineer. Verifies technical correctness of all code, AVM details, ecosystem references, and security claims. | Wrong opcode budgets, incorrect MBR math, outdated API usage, insecure contract patterns, inaccurate ecosystem claims |
| **teaching-pro** | Learning scientist. Evaluates whether content actually teaches effectively using evidence-based pedagogy (Making Learning Whole, Cognitive Load Theory, Bloom's Taxonomy). | Elementitis, aboutitis, missing junior versions, cognitive overload, poorly graduated exercises, missing transfer opportunities |
| **publishing-pro** | Technical book editor. Ensures professional publishing standards -- structure, typography, code formatting, admonitions, cross-references, and editorial voice. | Inconsistent heading levels, stacked admonitions, missing cross-references, code lines >85 chars, broken chapter structure |
| **diff-reviewer** | Change reviewer. Its unit of work is a diff, not a chapter. Runs *after* fixes, and asks what the fix broke, what it left half-done, and what it asserted without checking. | Defects introduced by fixes, regressions in neighbouring text, one-of-N corrections that leave contradictions standing, fixes that outrun their evidence |

The fourth agent exists because of a measured pattern: across three separate rounds recorded in `RESTRUCTURING-PLAN.md` (`:1211`, `:1229`, and Phase 5a), the largest residual defect class was **defects introduced by fixes**. The mechanism is that no agent ever reviews the *change* -- only the resulting text. Prose written an hour ago to fix finding #3 is, on the next pass, just prose, indistinguishable from prose that has already survived a review. `diff-reviewer` is the only agent whose input is `git diff`.

### The Knowledge-Base Files

These are not agents. They are read by agents, never spawned as one — their frontmatter carries no `tools:` or `model:` key and their descriptions say so, because they sit in `.claude/agents/` and would otherwise look registrable.

| File | Read it when |
|------|--------------|
| `algorand-verified-facts.md` | **`algorand-expert` reads this first, always, before any review, walkthrough, audit or code change.** Empirically verified facts, dated and versioned. Later dated entries supersede earlier ones. This is the file that grows. |
| `algorand-reference.md` | On demand only -- node hardware sizing, public endpoints, Indexer schema, MainNet addresses, governance history. Never for a chapter review. |

### Review Workflow for Book Changes

When making changes to chapter files in `chapters/`, follow this process:

#### 0. Run unit tests for any code changes
Before proceeding with reviews, if the change involves contract code or test code, run the unit tests to catch compilation errors and regressions early:

```bash
# From the repository root:
uv run --group test python -m pytest tests -q 2>&1 | head -80
```

If tests fail, fix the code before moving to the review step. Do not proceed with agent reviews on code that does not pass tests.

#### 1. Make the edit
Edit the relevant chapter file in `chapters/`.

#### 2. Run the three-agent review
After the edit is drafted, run the three specialist agents (algorand-expert, teaching-pro, publishing-pro) **in parallel** against the changed section(s). Each agent should review the specific content that was added or modified, with enough surrounding context to evaluate it properly. `diff-reviewer` does not run here -- it runs in step 3a, after the fixes exist.

Prompt each agent with:
- The changed content (and surrounding context)
- What the change is trying to accomplish
- A request for a structured review per the agent's specialty

#### 3. Synthesize and apply feedback
Collect the reviews from all three agents. Look for:
- **Blocking issues** -- Technical errors (algorand-expert), security problems (algorand-expert). These must be fixed.
- **High-value improvements** -- Pedagogical issues from teaching-pro, structural problems from publishing-pro. Apply these unless they conflict with the author's intent.
- **Suggestions** -- Nice-to-have improvements. Present these to the user for decision.

#### 3a. Review the fixes themselves (mandatory, not conditional)

Once the fixes from step 3 are applied, run **diff-reviewer** against the diff they produced. This step is **not** conditional on the fixes seeming substantive, and it is not the fixer's call to skip: the actor that just wrote a fix is the worst-placed party to judge whether it needs review, and the recorded failures were all fixes that felt small at the time.

```bash
git diff              # uncommitted fixes -- this is the usual case
git diff <phase-base>..HEAD   # a whole phase's worth of change
```

Give diff-reviewer the base revision explicitly if it is anything other than `HEAD`. Its blocking findings are fixed before the phase gate; fixing them produces a new diff, which is reviewed the same way. Two consecutive clean passes end the loop.

**Continuous agent improvement:** Any time a review or walkthrough catches a mistake made by the algorand-expert agent, ask: "What could be added to the agent so it gets this right the first time?" Identify the root cause (missing knowledge, unchecked assumption, skipped verification step) and record a concrete prevention rule — a newly verified fact goes in `.claude/agents/algorand-verified-facts.md` (dated, with the toolchain version, naming anything it supersedes); a procedural rule goes in the Pre-completion Verification Checklist or the Code Style Philosophy section of `.claude/agents/algorand-expert.md`. This compounds over time: each mistake makes the agent permanently better.

#### 4. Validate code with a walkthrough test
After reviews are incorporated, use the **algorand-expert** agent to perform an end-to-end walkthrough validation of the chapter. The agent must:

1. Create a fresh AlgoKit project in a **temporary directory** (e.g., `/tmp/chapter-validation-<name>/`)
2. Follow the chapter from beginning to end, **step by step**, exactly as a reader would -- scaffolding, writing contract code, compiling, deploying, and running every script
3. **Assume nothing that is not written in the chapter.** If the chapter says "add this method," the agent adds only that method. If an import is missing, that is a bug in the chapter.
4. Compile after each code addition. If it fails, report the exact error and the revision needed.
5. Run every deployment/test script shown in the chapter. If it fails or produces unexpected output, report the gap.
6. Test all main user flows end-to-end (e.g., deploy → initialize → stake → claim → extend → unstake for the farming chapter).

The agent should return a structured report:
- **Passes**: Steps that worked as written
- **Revisions needed**: Exact list of gaps, missing imports, wrong APIs, compilation errors, or unclear instructions -- with suggested fixes

Apply all revisions to the chapter file, then **run diff-reviewer over the diff those revisions produced, exactly as in step 3a.** This is not conditional on the revisions seeming substantive. Walkthrough fixes are the most defect-dense text in the whole process — they are written under time pressure, against a failure the author has just seen, and they are the least-reviewed prose in the repository at the moment they are written. If the revisions also changed the substance of what a chapter teaches or claims, re-run the relevant specialist agent(s) from step 2 as well.

**Knowledge base update requirement:** When the walkthrough discovers a compilation error or incorrect API usage, the algorand-expert agent must add the correct information to `.claude/agents/algorand-verified-facts.md`, under a dated heading that names the toolchain version. This prevents future reviews from re-introducing the same error. The entry should include both the wrong form (so future agents recognize it) and the correct form (so they know the fix). If the error reveals a pattern (e.g., a PuyaPy 5.x breaking change from 4.x), document the pattern, not just the individual instance. If the new entry contradicts an existing one, say explicitly which entry it supersedes and where that entry is -- an append-only knowledge base eventually returns whatever the reader was hoping to find.

**This step is not skippable for any chapter containing runnable code.** The recorded reason is `RESTRUCTURING-PLAN.md:1319`: "The three-agent review passed, and then the walkthrough found thirteen more defects, four of them factual." A chapter that passes three specialist reviews can still be a chapter nobody has executed. The three reviews read the code; the walkthrough runs it, and those find different things.

The walkthrough may be skipped only for changes that touch no code fence, no command, no file path and no example -- prose-only edits to narrative sections. If the change touches an `{{ex:}}` reference, a fence, or anything under `examples/` or `projects/`, it runs.

#### 4a. Render it and read it
For any chapter whose figures carry numbers -- MBR costs, opcode budgets, byte counts, group sizes, fee amounts -- rasterize the built pages and look at them before calling the chapter done:

```bash
python3 build.py pdf
pdftoppm -png -r 100 -f <first> -l <last> Building-on-Algorand.pdf /tmp/vpage
```

Then read the images. `RESTRUCTURING-PLAN.md:1213` records why: "A fifth defect was caught only by rasterizing the PDF and looking at it." Figure text lives in `figures/src/*.mmd` and `figures/src/*.svg`, which no validator parses and no agent reads unless told to, so a figure can carry a number that the prose one page away has already corrected -- and the figure is the thing the reader looks at.

**A figure's quoted strings are held to the manuscript's standard, not to a lower one.** Every error message, JSON key and API response body rendered inside a figure must be greppable out of go-algorand or the installed client source exactly as prose must be -- grep the *format string*, since `%d`/`%s` mean the literal you are looking for is never the literal you saw. The recorded instance is `figures/src/simulate-trace.svg`, which rendered a simulate `failure-message` twice in successive rounds without the `transaction {id}: ` prefix that every such message carries, while the prose on the facing page had just been corrected to include it. Nothing flagged the contradiction because nothing reads both.

**`figures/out/` is build output.** Edit `figures/src/` only, then re-run `python3 build.py figures` -- the SVG *and* the PDF in `out/` are both regenerated and both are tracked. Hand-editing `figures/out/*.svg` appears to work, because the HTML build picks it up; the PDF does not change, so the print edition ships the old string while the web edition ships the new one. That has happened once already. **The two outputs are not equally reproducible, and `git status` is the wrong instrument on the PDF.** A comment-only edit to `figures/src/router-decision.mmd` re-rendered to a byte-identical `.svg` -- it did not appear in `git status` at all -- while the `.pdf` came back different, in one 285-byte Flate object that decompresses to cairo's `/Producer` and `/CreationDate`, with the `/MediaBox` and the content stream identical. So every re-render dirties its PDF whether or not the drawing moved. Prove "this edit changed nothing" on the SVG. The stamp that decides whether a re-render happens is also not one formula: `.mmd` sources hash as `sha256(src + b"\0" + theme.json + b"\0")` and only `.svg` sources as `sha256(src + b"\0")` (`build.py:826-832`, `:908`), so hand-checking a `.mmd` with the simple form reports a mismatch on a perfectly current file.

**A figure's type size is a page measurement, and the source cannot tell you what it is.** Every figure is scaled down to the 470.4pt text width and never scaled up, so a drawing authored at a comfortable 12px can reach the reader at 6.6pt with nothing in the source having changed. The house floor is 8pt *on the page*; for a hand-authored SVG that is `font_px >= width_px / 58.8`. Two instruments cover the two failure modes, and both have met this file's injection bar: `python3 scripts/figfloor.py` reads the built figure PDFs and reports each one's smallest on-page glyph, and `python3 scripts/figcollide.py` renders each figure twice — shapes stripped, then text stripped — and reports glyphs drawn on top of a rule, which is the defect the floor harness is blind to (`sha512_256` rendered as `$ha512_256` while the floor harness reported `ok 8.44pt` on that same render). Both run clean across all 21 figures as of 2026-07-27. **The full geometry — the width/height trade, the mermaid constants that contradict `theme.json`, and the measuring-instrument bug that produced one entirely fictional finding — lives in `.claude/agents/publishing-pro.md` under Figures and Diagrams.** Read it before redrawing anything; every rule in it was paid for by a round.

**A change to where lines end is measured by TeX's own overflow statistic and by nothing else; a change to where pages end is not measured by it at all.** The one number that says whether a *horizontal* change -- a separator set, a hyphenation setting, a font option, anything deciding where a line breaks -- helped is the count of `Overfull \hbox ... in paragraph at lines N--M` in the xelatex log, keyed *per paragraph* and diffed against a control build. A *vertical* change is a different question with a different instrument: `\brokenpenalty`, `\Needspace`, `\nopagebreak`, `widowpenalty` and float placement move no line ending, so their `Overfull \hbox` diff is empty by construction, and reading that emptiness as "no effect" is exactly how a variant that stranded two callouts got shipped. Judge those on the page scan of the built PDF -- page-ends on a broken line, mid-identifier page turns, stranded captions, bare callout header bars -- with `Underfull \vbox` used only to pick pages worth rasterizing. Aggregate counts alone hide the interesting case, which is a change that repairs thirty paragraphs and breaks seven; the per-paragraph diff is what surfaces the seven. The recorded failure is a proxy that counted words falling past the text block: that population is dominated by pre-existing code-fence overflow, so gains and losses cancel and every new inline-code overrun is invisible in it. A hyphenated-line-end count fails the same way and for the same reason.

`build.py pdf` does not keep the log, so measuring means generating the `.tex` and running xelatex directly:

```bash
# same pandoc invocation, -o book.tex --standalone, minus --pdf-engine
# then, with figures/out/. and building-on-algo.jpg beside it:
xelatex -interaction=nonstopmode -file-line-error book.tex   # three passes
grep -c '^Overfull \\hbox' book.log
```

**Run the page scan with `python3 scripts/pagescan.py <pdf> [<pdf> ...]`, which defines all four statistics in its own header and prints the sites under each count.** Two rules travel with it, both learned by breaking them. First, **print every row for every variant, including the rows you have an argument for not needing** — a table isolating `\brokenpenalty` omitted the stranded-caption row on the reasoning that captions belong to `keeptogether.lua`, and that is precisely the row `\brokenpenalty` moved: it cures one stranded caption and creates two, which stayed invisible for several rounds because the other filter cured all six downstream. When one mechanism is measured with another switched off, the second one's row is the likeliest to move and the least likely to be looked at. Second, **`Underfull \vbox` is two statistics wearing one name.** `book.log` carries `... has occurred while \output is active`, which is a page and is followed by that page's folio, and `... detected at line N`, which is a box inside a paragraph with no page identity at all. Only the first can be attributed to a page, so a gained/lost-per-page breakdown comes off that subset and the `grep -c` total does not equal it. On the current matched pair those run 104 → 126 and 78 → 79 against a total of 182 → 205; joining "182 → 205" to "twenty-nine gaining and seven losing" in one sentence gives arithmetic that does not close, and a reviewer re-deriving it got eight losses by attributing `detected at line` boxes to the next folio. Separate the two populations before counting either.

**There is a fourth vertical defect that none of the four page-scan statistics sees, and its fingerprint is arithmetic rather than visual.** A page of prose whose interparagraph gaps are all *exactly equal* and all far larger than the leading is not a coincidence and is not a float doing something clever — it is `\flushbottom` dividing a short page's missing height evenly among whatever glue can stretch. `report.cls:729-733` runs `\raggedbottom` only when `twoside` is off; this book sets `twoside`, so the class default is `\flushbottom`, and pandoc's `\parskip 6pt plus 2pt minus 1pt` is the only stretchable glue on an ordinary prose page. Printed folio 147 was the demonstration: Figure 4-3 is 402.9pt tall and pinned by `\floatplacement{figure}{H}`, so when it would not fit TeX broke above it and handed the output routine **400.9pt** of slack for three paragraphs to absorb — all three gaps came out at **exactly 156.0pt** against a 15.6pt baseline. Twenty-six pages carried a gap over 80pt, six of them more than one. `\raggedbottom` in `metadata.yaml` is the repair: its glue is inserted by `\@makecol`, which runs *after* the page builder has already chosen the break, so it moves no line and no page break. Measured 674 pages before and after, with the page scan unchanged at 6/10/0/0; output-active `Underfull \vbox` went 133 → 0 and pages carrying a gap over 80pt went 26 → 4, the four survivors (printed folios 382, 228, 45 and 20) all legitimate. **Exactly-equal large inter-paragraph gaps are the fingerprint of this and of nothing else** — so the way to look for it is to measure the gaps on a page, not to look at it, because a uniform stretch is exactly what the eye reads as intentional spacing.

**The slack figure read 421pt here for one round, and it was wrong by a subtraction.** Measure it rather than compute it: the last word on printed folio 147 sits at baseline 710.2 under `\flushbottom` and 309.3 under `\raggedbottom`, so 400.9pt is what relocated. The arithmetic check is `3 × (156.0 − 22.4) = 400.8`, where 22.4pt is the page's own natural paragraph gap — 15.6pt of baseline plus the 6pt `\parskip` — and the ragged build shows exactly three gaps of 22.4pt where the three 156.0pt voids were. The 421 came from `3 × (156.0 − 15.6)`, subtracting the *baselineskip* where the *natural paragraph gap* belongs and so counting the `\parskip` as slack three times over. Everything else in the demonstration reproduces exactly, which is the hazard: **a derived number sitting inside a demonstration whose every other number checks out inherits the demonstration's credibility without having earned it.** Derive it from two measurements of the same page, never from the gap size and the leading.

**It is not free, and calling it free was an overclaim.** This entry said `\raggedbottom` "is free in the only sense that matters" on the strength of the `\@makecol` timing argument, which is sound as far as it goes: no line moves, no page break moves, and no *page* gets worse. The cost is one level up, at the **spread**, and it is exactly what `\if@twoside \else \raggedbottom \fi` guards — the class turns `\raggedbottom` off for two-sided documents precisely because a reader of a two-page spread sees both feet at once. Relocating folio 147's 400.9pt to the foot of the page puts a half-empty verso against a full recto. Measured on the two builds, restricted to the 203 spreads where `\flushbottom` produced two full pages (both flush feet ≥ 700pt, so the flush arm has no mismatch there by construction, measured 0): `\raggedbottom` leaves **58** of those spreads with feet more than one line apart, median 43.6pt across the 58, worst 521.0pt at folios 380/381. **Those numbers read 196 / 53 / 40.2 / 511.2 for a round because the pairing was wrong, and the reason is a trap this whole file can fall into: in this book the printed folio is the pdf page index minus one**, so pairing pages by index parity pairs a recto with the verso overleaf rather than a verso with its facing recto. Pair by printed folio, even with odd. `.claude/agents/publishing-pro.md` carries the full re-derivation recipe and the failure analysis. The trade is still right for this book — a page with three 156pt voids in it is unreadable in a way an uneven spread is not — but it is a trade, and the honest form is that `\raggedbottom` moves a defect from the page to the spread and shrinks it, not that it removes one for nothing. **Whenever a repair is described as costless, name the level the measurement was taken at**; this one was measured per page and was costless per page.

Diff the two logs by paragraph, remembering that any preamble change offsets every body line number in one of them, and that a filter which *inserts* nodes shifts them unpredictably -- in that case key on the offending line's text from the log body rather than on line numbers. Report page count and LaTeX error count alongside, since a fix that buys margin with a 671st page or a hyperref warning is not a fix. Re-measured on the current tree, 2026-07-27, whole book: `Overfull \hbox` **80** with neither mechanism, **94** with `HyphenChar=None` alone, **29** with `HyphenChar=None` plus `codebreak.lua`; `Underfull \hbox` **88 / 104 / 42**; **674 pages** and zero errors in all three variants. Produce the two stripped variants with `/tmp/r20w/measure_var.sh <tag> <nohyphen> <nocodebreak>`; the three build directories those numbers came off are `/tmp/r20w/neither`, `/tmp/r20w/hyphenonly` and `/tmp/meas/r20ragged`. **These superseded a recorded 102 / 116 / 51 and 89 / 105 / 43 at 670 pages**, which were correct for the tree they were taken on and became stale the moment the manuscript moved — the point of naming the build directories is that the next person can re-derive rather than inherit.

**Measure one mechanism at a time, and check that the build you are calling the control is one.** An earlier version of this paragraph recorded the middle term as 74, which is the figure for `HyphenChar=None` plus a since-deleted `\_` hook -- two mechanisms, labelled as one. The mislabelling inverted the sign of the step and made `codebreak.lua` look like optional polish on top of a hyphen-kill that had already paid for itself; the truth is that `HyphenChar=None` alone *costs* 14 overfull boxes (15 new, 1 repaired) and the filter is what pays for it. **That step survived the re-measurement above unchanged**: on the old tree it was 102 → 116 and on the current one 80 → 94, the same +14 against a baseline that moved by 22, which is the strongest available evidence that the step is a property of the mechanism rather than of the manuscript. Anyone who deleted the filter on the strength of the recorded 74 would have shipped a book worse than the control while reading a note that said they had improved it. `diff A/book.tex B/book.tex` should return exactly the lines the mechanism under test is responsible for -- one changed `\setmonofont` line, in that case -- and if it returns more, the variant is not isolated and its number belongs to something else.

**Removing a break opportunity can only create overfull boxes, never repair one.** That is a monotonicity argument, not a measurement, and it is the cheapest sanity check available on any number produced here: a variant that removes breaks and reports *fewer* overfull boxes than its control has not found a clever optimum, it has been mislabelled. Apply it before believing a surprising result. Reasoning about which direction a change *can* move a statistic catches a bad build in seconds, where re-running the harness takes twenty minutes and reproduces the same mistake if the variant is wrong.

**Know what the mechanism does not reach, so a residual overrun is not mistaken for a regression in it.** `codebreak.lua` sees pandoc `Code` inlines and nothing else. Classified by mapping each box's `lines N--M` back onto `book.tex`, the residual 29 is **13 table cells** (7 of them carrying a `\texttt` span), **11 prose paragraphs carrying a `\texttt` span**, **4 `in alignment`** rather than `in paragraph`, and **1 table-of-contents entry**. Every one of them is a monospace or tabular problem; there is not a single box of ordinary prose with no code in it, and there are **zero bibliography URLs**.

**That last count replaces a recorded "21 of the residual 51 are bibliography URLs or `\href` link text", which was never true and is worth keeping as a cautionary entry rather than deleting.** Two independent instruments kill it. Source mapping of the 80-box control returns exactly one box whose source contains an `\href` at all, and that box is the mono-in-prose paragraph "The load-bearing line is `class Smallest(ARC4Contract)`…", which merely has a link somewhere else in its span. And the geometry forbids it: all 161 `\href{}{}` link texts in the book were measured, the longest is **63 characters** (`algorand.co/blog/technical-brief-quantum-resistant-transactions`), only two exceed 60, and each is preceded by ordinary breakable space — so a link sets in well under 400pt against a 470.4pt `\linewidth` and cannot overrun a line on its own. No source change explains a 21 → 0 collapse either. **The likely cause is the instrument, and it is the one the original entry warned about in the same sentence**: a link reaches `book.log` as `[][]` with the scheme swallowed — but so does an `in alignment` box, so does a table-of-contents entry, and so does any box whose leading material is boxes rather than glyphs, so reading the log's *rendered context* cannot tell them apart. **Classify an overfull box by mapping its `lines N--M` onto `book.tex`. Never by reading the log's rendering of it.** A grep of the log for `http` returns 0 here and proves nothing, for the same reason.

Twenty-nine lines carry an underscored identifier in plain prose *outside* any backticks, which neither mechanism touches; the repair there is backticks in the chapter, at the source. That figure is 29 lines and 39 occurrences across 12 files, counted over `chapters/*.md` with fenced blocks skipped, inline `` ` `` spans blanked, and the identifier matched as `[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]+` — **the method is part of the number**, and this entry now has two supersessions that prove the point in opposite directions. The figure that stood here first was 63, with no method recorded: no counting rule reproduces it, so it could never be checked for movement and had to be discarded rather than corrected. The figure that stood here second was 45 lines / 57 occurrences, *with* the method above recorded beside it — so when the manuscript moved, re-running the stated method returned 29 / 39 and the entry could simply be updated. **A number with its method attached is maintainable; a number without one is only ever replaceable.** And a long identifier inside a fence is governed by `fvextra`'s `breaklines`, not by any of this.

Then still rasterize and read the affected pages. The statistic says a line fits; only looking says the break lands somewhere a reader can follow -- and a break that is legal for TeX can still be illegal for the language. The recorded instance is `codebreak.lua` splitting `//` across a line boundary, which reassembles as two ordinary divisions rather than one floor division: the box fitted, the overflow count improved, and the page said something false about the code. The statistic cannot see that class of defect at all.

#### 5. Security audit of all contract code
After the walkthrough passes, use the **algorand-expert** agent to audit every smart contract in the changed chapter(s) for the common Algorand vulnerability classes. The agent must check for **all** of the following:

**Transaction field validation (LogicSigs ONLY -- skip for stateful smart contracts):**
- [ ] `close_remainder_to` / `asset_close_to` checked against `Global.zero_address` (LogicSig security checklist)
- [ ] `rekey_to` checked against `Global.zero_address` (LogicSig security checklist)
- NOTE: These checks do NOT apply to stateful smart contracts. Inner transactions default these fields to the zero address. Asserting them on incoming group transactions just restricts the user's wallet for no security benefit.

**Transaction group validation (stateful contracts):**
- [ ] Group size validated where applicable (prevent unexpected extra transactions)

**Authorization:**
- [ ] Every privileged method has an explicit caller check (admin-only, holder-only, etc.)
- [ ] No method is callable by arbitrary accounts when it should not be
- [ ] `Txn.sender` verified against the expected party for every state-changing operation

**Inner transaction safety:**
- [ ] All inner transaction fees set to `fee=UInt64(0)` (caller covers via fee pooling)
- [ ] No inner transactions that could drain the contract's Algo balance via fees

**Arithmetic safety:**
- [ ] All multiplications that can exceed UInt64 use `mulw` or `BigUInt`
- [ ] All divisions use floor-toward-pool (rounding favors the contract, never the user)
- [ ] Division-by-zero guarded where applicable
- [ ] Overflow bounds proven or asserted for accumulated values

**Asset verification:**
- [ ] Every incoming asset transfer verified against the expected ASA ID
- [ ] LP tokens, reward tokens, etc. verified against stored/cross-contract-read IDs

**State consistency:**
- [ ] Accumulators (reward-per-token, TWAP cumulatives) updated BEFORE computing user-specific values (algorithmic correctness -- the global accumulator must reflect current state before individual positions are calculated against it). This is NOT a reentrancy guard -- Algorand has no reentrancy. It is a mathematical ordering requirement.
- [ ] No code path where state is partially updated (e.g., balance changed but accumulator not updated)
- [ ] Box creation/deletion paired with correct MBR funding/refunding
- NOTE: Do NOT enforce checks-effects-interactions ordering for reentrancy prevention. Algorand's AVM has no reentrancy (inner transactions don't trigger callbacks). Write state in whatever order is clearest to read.

**Economic exploits:**
- [ ] No flash-loan-style attacks possible (single-group manipulation)
- [ ] Oracle values (TWAP, spot prices) resistant to single-block manipulation
- [ ] Reward distribution cannot exceed the deposited reward pool
- [ ] Rounding dust always favors the contract, not the user

**Contract lifecycle:**
- [ ] Immutability enforced (update/delete rejected)
- [ ] Initialization can only happen once
- [ ] No state accessible before initialization

The agent should return a checklist with pass/fail for each item and a description of any failing checks with suggested fixes. **All checks must pass before the chapter is considered complete.** Any failing check is a blocking issue that must be fixed in the chapter file.

This step can be skipped for changes that do not include smart contract code. Its fixes go through diff-reviewer like every other fix — `RESTRUCTURING-PLAN.md:1323` records a security audit that "found one blocking vulnerability the earlier round had missed, in an example whose subject was safety," so this is not a step whose output can be assumed sound because of what the step is about.

#### 6. Validate and build

```bash
python3 scripts/validate.py --structure          # fast; must report 0 errors
python3 build.py mdbook                          # regenerate the HTML site
```

`validate.py --structure` is the cheapest gate in the repository and the only mechanical check on cross-references, anchors, example manifests, house line/fence caps and prompt density. **It must report `0 errors` before a phase is considered done.** Warnings are advisory, but the *count* is a tripwire: record it, and if it goes up, find out which change raised it before moving on. The current baseline is `0 errors, 38 warnings`.

The full example gate exceeds the two-minute tool timeout and must be backgrounded:

```bash
nohup timeout 2400 uv run --group test python scripts/validate.py --examples \
  > /tmp/examples_gate.log 2>&1 &
```

Note what these validators do *not* cover, because it defines what the agents are for: nothing parses markdown tables, nothing reads `projects/`, and nothing verifies that an identifier named in running text exists in the code the passage is about. `build.py` reference-resolves `chapters/*.md` only. **The validators check form; only the agents check truth** (`RESTRUCTURING-PLAN.md:1166`).

Five checks are narrow exceptions to that, added 2026-07-27 because the same defect family kept surviving four review rounds.

**Check 17** is the only validator that reads `figures/src/` and chapter prose together: it harvests every `transaction {id}`, `Transaction {id}` and `Txn {id}` from both, flattening XML so a transcript wrapped across three `<text>` elements still parses, and errors if one elided ID is shown with two different applications, two different failure messages, or two different program counters. A transaction ID is globally unique, so that is a contradiction rather than a style question, and it is one no human reviewer catches because the two sites are chapters apart and one of them is a figure. It reads `chapters/` and `figures/src/` and nothing else — `projects/`, `examples/` and `tests/` are code, where the same contradiction would be a test failure rather than a rendering defect.

**Check 18** errors on a Go format string (`%d`, `%s`, `%v`, `%w`, `%#x`) inside a backtick span in chapter prose, on the same anywhere in a `figures/src/` file — figures have no inline-code markup, so the backtick heuristic that works for prose would let every figure through — and on the `{TXID}` placeholder in either, since the manuscript's spelling is `{id}` and mixing the two defeats the grep that audits prefix coverage. Shell parameter expansions, percent-encoded runs and strftime patterns are excluded by construction rather than by luck, and each is stripped *per run* rather than per line — an earlier version skipped the whole line on any strftime hit, so a single `%Y-%m-%d` in a caption silenced both this check and the `{TXID}` check for everything else on that line. An exclusion that widens to the line is a hole.

**Check 19** enforces the elided-trace marker along four dimensions. *Presence:* every `LogicError` transcript inside a fence carries exactly one `    ... 10 lines of TEAL trace ...`. *Finality:* that marker is the transcript's last non-blank line, since a marker above the message says the wrong block was cut. *Position:* a fenced line ending on `... and Source Line <n>:` is followed immediately by the marker, because that trailing colon is the exception promising the trace that comes next, so a fence that ends there ends mid-sentence. A line ending on a bare `... at PC <n>:` fires the same check but takes the *opposite* fix: that is the spelling algokit-utils uses when it has no source map, and `logic_error.py:83-84` emits it on exactly the branch (`line_no is None`) whose `trace()` returns the "Could not determine TEAL source line" advisory (`:89-95`) rather than any TEAL — so there is no reachable state in which that shape is followed by a trace, and the repair is to restore the `and Source Line <n>:` clause the book's factory path always produces, never to append the marker. *Spelling:* any line matching `...` followed by `TEAL trace` is byte-identical to the marker. It is the only check that reads a fenced line for what it *says*, and the only one that goes through `_fence_blocks` to do it. Checks 6, 7 and 15 look at fences too, but only at the language tag, the length of each line and the number of them; check 9 reads a fence's whole body, but only to compare it, whitespace-normalised, against the example sources on disk. Check 16 is the counterexample rather than the exception: it walks `text.split("\n")` with no fence awareness at all, so `PROMPT_LINE_RE` currently matches twelve lines *inside* fences — a piped `| python -m json.tool` in two project chapters, and ten pytest-report and simulate-trace gutter lines in `07-c-proving-it-works.md` — and each silently resets the density counter. That is a defect in check 16, not a second reader of fenced meaning, and it is why check 19 was built on `_fence_blocks` from the start.

Presence and finality are conditional on the check having recognised a transcript; position and spelling run over every fenced line whether or not one was recognised. The two boundary rules that decide recognition were both established by running the widened check over the corpus rather than by reasoning about it. A transcript *opens* on `LogicError:` as the line's first non-space text or on a pytest report's `E   LogicError:` — `except LogicError as err:` and `from ... import LogicError` are Python source rather than output, and a raw algod string quoted without the Python exception around it (`chapters/07-c-proving-it-works.md:522`) opens nothing either, because the ten TEAL lines are a client-side artifact algokit-utils appends from a source map it kept, so that fence is right to carry no marker and demanding one there is a false positive. A transcript *ends* at the next opener, the next prompt line (`>>>`, `$`, `In [n]:`), or the end of the fence; without the prompt boundary, finality would fire on the three transcripts — in two REPL fences — that continue with a further command after the marker.

**Check 20** errors on a heading or a list with no blank line above it. Pandoc's markdown, unlike CommonMark, lets neither one interrupt a paragraph: with no blank line, a `### ...` line is simply the paragraph's last line, and a `- item` is simply more of its last sentence. A swallowed heading renders as body prose, appears in no table of contents, sets no running head and carries no anchor for a cross-reference to land on; a swallowed list arrives as one run-on paragraph with stray hyphens or digits where the bullets were. Every other structural check here reads the block list pandoc already parsed — which is precisely the list this defect removes the element from — so the check has to read the raw line.

It covers ATX headings, Setext underlines, and list items at any indent, and it excuses a block element only where pandoc genuinely parses it: under a heading, under a table row, under a callout fence, and under a closing code fence, all of which end their own block. **The heading carve-out matters and was checked rather than assumed** — a list directly beneath a heading parses fine, and seven of the book's fifteen `## Exercises` sections are exactly that shape and all correct. Seven is the right count and *the concept chapters* is the wrong name for them: there are **eight** concept chapters, `01-c` through `08-c`, and the shape holds in the first seven only because `08-c-patterns.md:646` happens to put a blank line between the heading and the list. Nothing enforces that blank line, so the set is seven files today and could be eight tomorrow without anything being wrong — cite the count, never the category. Without it the check reported thirteen on the corpus it was written against, seven of them these false ones, and a check that is 54% noise gets switched off within a round.

**Every carve-out is a claim about pandoc, so run it through pandoc.** The first version of this check excused a list under `>` on the stated grounds that a blockquote "closes its own block", and scoped headings to ATX on the stated grounds that "Setext has the opposite blank-line rule". Both statements were written from memory and both are false. `printf 'Intro.\n\n> quoted\n- item one\n' | pandoc -t html` lazily continues the list *into* the blockquote and sets the bullets as literal hyphens — the exact defect the check exists to catch, unconditionally suppressed. `printf 'Intro para.\nHeading text\n============\n' | pandoc -t html` swallows the Setext heading identically to an ATX one and prints the underline as body text; the `-` form is worse, because it sets as an em dash and is invisible even to a reader looking for it. A third and a fourth shape were wrong in the other direction: a heading or list directly after a closing fence was reported, though pandoc parses both, and a four-space-indented list after a paragraph was not reported, though pandoc swallows it. All four shapes occur zero times in the corpus, so correcting them moved no count — which is the point. **A carve-out you cannot produce the transcript for is a hole you have not measured**, and it will be trusted by the next person who widens the check. The comment in `scripts/validate.py` now carries the command beside each one.

Run over all 24 chapters it found six instances, every one present at `d845ff3`: the heading at `chapters/10-p-zk-voting.md:597`, a "Production Verifier Binding Checklist" folded into the paragraph above it and absent from the TOC ever since, plus five lists in `07-p-yield-farming.md`, `08-c-patterns.md`, `09-p-limit-order-book.md` and `10-p-zk-voting.md` (two). Six hits is the argument for the check rather than against it: the rendered page looks like prose that was always prose, which is why five review rounds and a rasterize-and-read pass all walked past them. **Keep the two zk-voting discoveries the right way round**, because the lesson below depends on which found which: the *heading* at `:597` is what check 20's heading branch reported, and the *list* at `:569` — the **seven** bullets under "The generated LogicSig verifier:", `d845ff3` lines 569–575 — is what rasterizing an unrelated page turned up. The check found the heading; the reader's eye found the list.

**Check 24 is check 20 run backwards, and it exists because fixing a check-20 hit can create one.** Check 20 asks what sits *above* a block element; check 24 asks what sits *below* a list item. Pandoc will not let a list interrupt a paragraph, which is check 20's defect — and it will lazily continue a list *into* the non-blank line beneath it, which is this one. A paragraph written directly under a bullet does not become a paragraph; it becomes more of that bullet, typeset indented inside it, with no marker on the page saying so. That is how `chapters/F2-preface.md:60` shipped: a `{{fig:book-map}}` placement directly under the last bullet of the list above it, absorbed into the bullet.

The carve-outs are indented lines (a deliberate item continuation, and the one shape skipped rather than flagged), `` ``` ``/`~~~` fences, `:::` div **closers only**, ATX headings and Setext underlines — the last two skipped only to avoid double-reporting, since check 20 already fires on them from the other side. **`|` is deliberately *not* carved out here, and that asymmetry with check 20 is the whole subtlety.** A table following a *paragraph* closes its own block, so check 20 excuses it; a table following a *list* is lazily continued into the bullet, so check 24 must not. The two checks have different carve-out sets for the same character because the block above it is different, and copying one set to the other opens a hole in whichever direction you copied.

**A fenced div is not symmetrical, and this check's first version assumed it was — in all three places it is documented at once.** `validate.py`, `publishing-pro.md` and this file each said `:::` closes a list the way a code fence does, each carved it out unconditionally by shape, and each cited `10-p-zk-voting.md:478` as the evidence. Pandoc contradicts it, and the direction depends on which end of the div the delimiter is: `printf -- '::: {.note}\n- item one\n:::\nAfter.\n' | pandoc -t html` yields `<div class="note"><ul><li>item one</li></ul></div><p>After.</p>`, but `printf -- '- item one\n- item two\n::: {.gotcha}\nBody.\n:::\n' | pandoc -t html` yields `<li>item two ::: {.gotcha} Body. :::</li>`. The corpus instance is a *closer*, and a closer is safe because the list was already inside the div. An *opener* under a bullet is destroyed: the div never opens, its attributes set as literal text on the page, and the entire callout body is absorbed into the last list item — a worse surface than the paragraph case the check was written for, and one the carve-out was confirmed silent on by injection. The check now tracks div nesting, flags openers with their own message, and excuses closers; a bare `:::` at depth zero is an opener in pandoc and is treated as one. **Generalise past the check: a delimiter whose two ends are spelled the same is not therefore interchangeable, and carving it out by shape carves out both ends.** The single citation that "proved" the carve-out was a closer, so it could never have exposed the opener — **one confirming instance of the safe direction is not evidence about the other direction.**

An indented continuation is skipped but does **not** end the list context: `printf -- '- item one\n  continued\nunindented para\n'` puts all three lines in one bullet, so a `continue` that also cleared the in-list flag would blind the check to the next unindented paragraph. Zero corpus instances; closed anyway, because nothing else detects it.

Injection-tested to this file's standard rather than a convenient one. Over `git archive HEAD chapters` at `1c6c974` it reports **one** problem, `F2-preface.md:60`, the sentence that produced the check. That is one hit and not two — `10-p-zk-voting.md:478` is a div closer, which is correct markdown, so nothing is reported there and nothing is suppressed there either. The earlier wording here counted it as a hit the carve-out removed, which read as two hits for one defect and, worse, made the hole sound measured. Over the repaired working tree it reports nothing. Against the repaired check, six injected shapes were run: a `::: {.gotcha}` opener at depth zero, a bare `:::` opener at depth zero, a nested opener inside an already-open div, an indented continuation followed by an unindented paragraph, and a plain swallowed paragraph all fire at the right line; a `:::` closer directly under a bullet stays silent.

Checks 17, 18, 19, 20 and 24 are all error-severity, and **each was confirmed to fire against a deliberately injected defect before being committed**. That discipline is necessary and it is not sufficient, which is the most expensive lesson in this file. Check 17's first version harvested only the algod `logic eval error: ... app=N` spelling, which appears almost nowhere in the manuscript, so it passed the injection that restored *both* halves of a known-bad pair and was silently inert against the book's dominant `Txn {id} had error '<msg>' at PC <n>` shape. Check 19's first version then repeated the mistake one round later: it tested position alone, passed six injections, and could not have caught five of the eleven transcripts that shipped at `d845ff3` without a correct marker, because a missing marker leaves no line to inspect and none of those five ended on a colon. **Injecting a defect the check is supposed to catch is not the same as injecting the defect that was actually shipped.** The test that settles it is running the finished check against `git archive HEAD chapters` and counting: check 19 as it stands reports all eleven, where the position-only version reported six. Check 20 was built to that standard from the start — injected in both branches, then run against the HEAD corpus, where it reported all six elements that had actually shipped swallowed. Its own history makes the same point one more time: the heading branch was written first and found the heading at `10-p-zk-voting.md:597`, and the list branch existed only because rasterizing an unrelated page showed a bulleted list rendering as run-on prose at `:569` of the same file — twenty-eight source lines *above* the heading the check had just found, not below it, and in a different section. That distance is the point: had the two been adjacent, the first fix would have been read against the second defect and the second branch would never have been written. **The same root cause produces more than one surface, and the check you write for the surface you saw will not find the others.** Ask what else the mechanism breaks before declaring the check done.

### Agent Invocation Examples

**These agent names are not registered subagent types.** `Agent(subagent_type="algorand-expert", ...)` fails with `Agent type 'algorand-expert' not found`. Spawn them as `general-purpose`, and make the first line of the prompt a persona-adoption instruction:

```
Agent(
  subagent_type="general-purpose",
  model="opus",
  prompt="FIRST ACTION, before anything else: read "
         "`/home/claude/building-on-algo/.claude/agents/algorand-expert.md` in full "
         "and adopt it as your operating instructions and persona for this entire "
         "task.\n\nReview this section for technical correctness: [content]"
)
```

The same shape applies to `teaching-pro.md`, `publishing-pro.md` and `diff-reviewer.md`. The three specialist reviews go in one message so they run concurrently; `diff-reviewer` runs alone, afterwards, because it needs the fixes to exist.

For large changes spanning multiple sections, give each agent the full scope of the change. For small targeted edits, provide the changed paragraph(s) plus a few paragraphs of context on each side. `diff-reviewer` is the exception: give it a base revision, not content -- it reads the diff itself.

### When Agents Disagree

- **algorand-expert wins** on ALL technical matters: PuyaPy APIs, AVM behavior, protocol facts, smart contract correctness, security patterns, ecosystem claims. teaching-pro and publishing-pro must defer to algorand-expert on these topics without exception.
- **But precedence is not a substitute for verification.** When the *resolution* of a conflict is itself a technical claim -- "the shorter form still compiles," "that field defaults to zero," "this error surfaces as a `LogicError`" -- the claim needs the expert's sign-off on *that specific claim*, not merely the expert's standing precedent over the other agents. Deciding a dispute by citing who outranks whom, when what is actually in dispute is a fact, is how a wrong fact acquires an authoritative-looking history. (`RESTRUCTURING-PLAN.md:1293-1295`.)
- **teaching-pro wins** on pedagogical structure (how to sequence and present information)
- **publishing-pro wins** on formatting and editorial standards
- **diff-reviewer does not outrank anyone on subject matter.** It owns one question -- what this change did -- and routes everything else: a technical finding to algorand-expert, a pedagogical one to teaching-pro, a formatting one to publishing-pro. It does not overrule a specialist's judgement on that specialist's own dimension. Where it *is* decisive is on regressions: if it demonstrates that a change broke something that previously passed, that is a fact about the repository, not an opinion about the content, and it stands until someone shows the demonstration wrong.
- When two agents give conflicting advice on the same dimension, flag the conflict for the user to resolve
- **Empirical compile-testing** (`algokit compile py`) should be used when: (a) two algorand-expert agents disagree and no official documentation settles it, or (b) a proposed fix reverses a previous fix (thrashing). See `.claude/agents/algorand-verified-facts.md` for already-settled facts -- and note that a grep hit there is not verification, since it may land on a superseded entry. Read the surrounding dated section.
