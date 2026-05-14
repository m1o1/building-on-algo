# Validation Harness

This directory records the current validation surface for the book repository.
The manifest is intentionally explicit about what is covered and what still
needs compile extraction, executable repros, or full LocalNet walkthrough
extraction.

## Prerequisites

- Python 3.12
- uv

## Status Meanings

- `active`: runnable and enforced in this worktree.
- `pending-pr`: tracked in another PR or issue, but not present here yet.
- `pending-extraction`: listed as a planned target, but no runnable extraction
  or smoke script exists yet.

In `coverage_summary`, `active` means a chapter has at least one runnable
validation target in this worktree. It does not mean the chapter is fully
validated; always read `pending_gaps` for remaining work.

## Commands

Validate the manifest itself:

```bash
uv run --group test python scripts/validate.py --manifest
```

Install and run the unit suite with uv:

```bash
uv run --group test python -m pytest tests -q
```

Compile extracted contracts with PuyaPy:

```bash
uv run --group compile python scripts/validate.py --compile
```

Run the harness checks together:

```bash
uv run --group test --group compile python scripts/validate.py --all
```

This runs the manifest check, unit tests, active PuyaPy compile checks, and a
LocalNet smoke status check. If `algokit` is not installed, the LocalNet status
check is reported as skipped.

Use strict mode when the goal is to fail on any pending coverage gap:

```bash
uv run --group test --group compile python scripts/validate.py --all --strict
```

The compile step writes artifacts to a temporary directory so generated TEAL,
source maps, and ARC-56 specs do not dirty the working tree.

## Current Scope

- Active extracted contract compile checks: shortened token vesting and private
  voting fixtures.
- Active unit tests: vesting arithmetic/immutability and voting MiMC/auth checks.
- Pending high-risk flows are listed with their tracking issue/PR so each one
  can be promoted to `active` as the corresponding executable repro lands.
- LocalNet walkthroughs are explicitly tracked as `pending-extraction` until
  each project chapter has a complete extracted smoke script.
