# Building on Algorand - Book Repository

## Source of Truth

**`Building-on-Algorand.md`** is the single canonical source for the book. All edits go here. The mdbook chapters and PDF are derived outputs.

## Build Commands

```bash
# Build the mdbook (static HTML site) - outputs to mdbook/book/
python3 build_mdbook.py

# Build the PDF (requires xelatex)
bash build.sh
```

## Workflow

1. Edit `Building-on-Algorand.md`
2. Run `python3 build_mdbook.py` to regenerate the HTML site
3. Never edit files under `mdbook/src/` directly -- they are overwritten on each build

## Project Structure

- `Building-on-Algorand.md` -- The complete book manuscript
- `build_mdbook.py` -- Splits the manuscript into chapters and builds the mdbook
- `build.sh` -- Builds the PDF via pandoc + xelatex
- `.claude/agents/` -- Specialized review agents (see below)

## Agent-Based Quality Assurance

Three specialized agents live in `.claude/agents/`. **Every substantive change to the book must be reviewed by all three agents before it is considered complete.** Trivial fixes (typos, formatting-only) can skip this process at the user's discretion.

### The Agents

| Agent | Role | When It Catches Problems |
|-------|------|--------------------------|
| **algorand-expert** | Algorand distinguished engineer. Verifies technical correctness of all code, AVM details, ecosystem references, and security claims. | Wrong opcode budgets, incorrect MBR math, outdated API usage, insecure contract patterns, inaccurate ecosystem claims |
| **teaching-pro** | Learning scientist. Evaluates whether content actually teaches effectively using evidence-based pedagogy (Making Learning Whole, Cognitive Load Theory, Bloom's Taxonomy). | Elementitis, aboutitis, missing junior versions, cognitive overload, poorly graduated exercises, missing transfer opportunities |
| **publishing-pro** | Technical book editor. Ensures professional publishing standards -- structure, typography, code formatting, admonitions, cross-references, and editorial voice. | Inconsistent heading levels, stacked admonitions, missing cross-references, code lines >85 chars, broken chapter structure |

### Review Workflow for Book Changes

When making changes to `Building-on-Algorand.md`, follow this process:

#### 1. Make the edit
Edit the manuscript as requested. All changes go in `Building-on-Algorand.md`.

#### 2. Run the three-agent review
After the edit is drafted, run all three agents **in parallel** against the changed section(s). Each agent should review the specific content that was added or modified, with enough surrounding context to evaluate it properly.

Prompt each agent with:
- The changed content (and surrounding context)
- What the change is trying to accomplish
- A request for a structured review per the agent's specialty

#### 3. Synthesize and apply feedback
Collect the reviews from all three agents. Look for:
- **Blocking issues** -- Technical errors (algorand-expert), security problems (algorand-expert). These must be fixed.
- **High-value improvements** -- Pedagogical issues from teaching-pro, structural problems from publishing-pro. Apply these unless they conflict with the author's intent.
- **Suggestions** -- Nice-to-have improvements. Present these to the user for decision.

If fixes from step 3 are themselves substantive, run a targeted re-review with the most relevant agent(s).

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

Apply all revisions to the manuscript. If revisions are substantive, re-run the relevant review agent(s) from step 2.

This step can be skipped for trivial changes (typos, formatting) at the user's discretion.

#### 5. Security audit of all contract code
After the walkthrough passes, use the **algorand-expert** agent to audit every smart contract in the changed chapter(s) for the common Algorand vulnerability classes. The agent must check for **all** of the following:

**Transaction field validation:**
- [ ] `close_remainder_to` / `asset_close_to` checked against `Global.zero_address` on every incoming transfer
- [ ] `rekey_to` checked against `Global.zero_address` on every incoming transaction
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
- [ ] Accumulators updated BEFORE any balance mutation (the update-before-mutate invariant)
- [ ] No code path where state is partially updated (e.g., balance changed but accumulator not updated)
- [ ] Box creation/deletion paired with correct MBR funding/refunding

**Economic exploits:**
- [ ] No flash-loan-style attacks possible (single-group manipulation)
- [ ] Oracle values (TWAP, spot prices) resistant to single-block manipulation
- [ ] Reward distribution cannot exceed the deposited reward pool
- [ ] Rounding dust always favors the contract, not the user

**Contract lifecycle:**
- [ ] Immutability enforced (update/delete rejected)
- [ ] Initialization can only happen once
- [ ] No state accessible before initialization

The agent should return a checklist with pass/fail for each item and a description of any failing checks with suggested fixes. **All checks must pass before the chapter is considered complete.** Any failing check is a blocking issue that must be fixed in the manuscript.

This step can be skipped for changes that do not include smart contract code.

#### 6. Build
Run `python3 build_mdbook.py` to regenerate the HTML site and verify the output.

### Agent Invocation Examples

Review a specific section after editing it:
```
Agent(subagent_type="algorand-expert", prompt="Review this section for technical correctness: [content]")
Agent(subagent_type="teaching-pro", prompt="Evaluate the pedagogical effectiveness of this section: [content]")
Agent(subagent_type="publishing-pro", prompt="Check this section against publishing standards: [content]")
```

For large changes spanning multiple sections, give each agent the full scope of the change. For small targeted edits, provide the changed paragraph(s) plus a few paragraphs of context on each side.

### When Agents Disagree

- **algorand-expert wins** on Algorand technical correctness (code, AVM behavior, protocol facts)
- **teaching-pro wins** on pedagogical structure (how to sequence and present information)
- **publishing-pro wins** on formatting and editorial standards
- When two agents give conflicting advice on the same dimension, flag the conflict for the user to resolve

