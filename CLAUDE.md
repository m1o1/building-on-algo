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

#### 4. Build
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

