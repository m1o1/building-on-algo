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

Then read the images. `RESTRUCTURING-PLAN.md:1213` records why: "A fifth defect was caught only by rasterizing the PDF and looking at it." Figure text lives in `figures/src/*.mmd`, which no validator parses and no agent reads unless told to, so a figure can carry a number that the prose one page away has already corrected -- and the figure is the thing the reader looks at.

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

Note what these validators do *not* cover, because it defines what the agents are for: nothing parses markdown tables, nothing reads `projects/`, nothing checks a figure's contents against the prose beside it, and nothing verifies that an identifier named in running text exists in the code the passage is about. `build.py` reference-resolves `chapters/*.md` only. **The validators check form; only the agents check truth** (`RESTRUCTURING-PLAN.md:1166`).

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
