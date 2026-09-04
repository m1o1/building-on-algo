# Companion / advanced material

This directory holds teaching content that used to sit in the main book
spine and was split out so *Building on Algorand* can stay on the core
smart-contract / DeFi path: foundations → custody → DEX → randomness →
shipping.

It is **not** a finished companion manuscript. The files here are the
preserved chapters and AlgoKit projects, marked out-of-spine so they are
not lost and so CI can still compile the projects. A later companion
volume can typeset them; this repository's reader-facing book does not.

## Why these left the spine

**Delegated LogicSigs (Part V, formerly Chapters 20–21).** A delegated
LogicSig is a signature a user cannot revoke. Production wallets such as
Pera will not let a user sign one. Teaching a pattern readers largely
cannot use in production — and that is easy to get dangerously wrong —
is not worth the page budget in the main book. Contract-account
LogicSigs (the program *is* the account; nobody signs a delegation) still
get a brief pointer in Chapter 20 of the main spine, because Chapter 22
uses that shape as a budget vehicle.

**Private governance voting (formerly Chapter 23).** The AlgoPlonk / ZK
voting project sits off the book's arc. Pairing-curve depth, optional
Go/gnark paths, and a privacy-governance product belong in an advanced
cryptography volume, not between a lottery and shipping. Chapter 22
stays in the main book as a cost survey of AVM cryptographic opcodes.

## Contents

| Path | What it is |
|------|------------|
| `stateless-programs/20-signing-without-a-key.md` | Former Chapter 20 (full LogicSig course) |
| `stateless-programs/21-delegated-limit-order-book.md` | Former Chapter 21 (LOB project chapter) |
| `stateless-programs/21z-checkpoint-stateless-programs.md` | Former Part V mastery checkpoint |
| `limit-order-book/` | AlgoKit project for the LOB (was `projects/limit-order-book/`) |
| `private-governance/23-private-governance-voting.md` | Former Chapter 23 (ZK voting project chapter) |
| `governance-voting/` | AlgoKit project for the vote (was `projects/governance-voting/`) |

The main book's Chapter 20 is a short pointer here. Chapter 22's closing
section points at the voting material. Chapter numbers 21 and 23 are
deliberately unused in the spine so cross-references in this directory
still match the filenames.

Figures referenced by the preserved chapters (`figures/logicsig-modes.svg`,
`figures/fig-21-1-hybrid-architecture.svg`, `figures/fig-23-1-proof-group.svg`)
remain at the repository root.

Root-level unit tests for the voting fixture (`tests/test_voting.py`,
`tests/contracts/voting.py`) still run in CI so this split does not
orphan coverage.
