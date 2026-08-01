"""The book's spine: one table every numbering-dependent tool reads.

Chapter numbers, filenames, kinds, and part boundaries live here and only here.
build.py derives part breaks from it; scripts/check_book.py verifies the
manuscript against it. Code paths (examples/<topic>/, projects/<name>/) carry no
chapter numbers by design, so renumbering can never strand them.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Chapter:
    number: int | None  # None for unnumbered interstitials (checkpoints)
    filename: str
    title: str
    kind: str  # "concept" | "project" | "checkpoint"
    part: int  # 1-7


@dataclass(frozen=True)
class Part:
    number: int
    roman: str
    title: str


PARTS = [
    Part(1, "I", "Foundations"),
    Part(2, "II", "Value Under Management"),
    Part(3, "III", "Building a DEX"),
    Part(4, "IV", "Chance"),
    Part(5, "V", "Stateless Programs"),
    Part(6, "VI", "Cryptography"),
    Part(7, "VII", "Shipping"),
]

CHAPTERS = [
    Chapter(1, "01-from-zero-to-deployed.md", "From Zero to Deployed", "concept", 1),
    Chapter(2, "02-the-algorand-mental-model.md", "The Algorand Mental Model", "concept", 1),
    Chapter(3, "03-contracts-that-exist-and-respond.md", "Contracts That Exist and Respond", "concept", 1),
    Chapter(4, "04-remembering-things.md", "Remembering Things: Global and Local State", "concept", 1),
    Chapter(5, "05-data-that-grows.md", "Data That Grows: Box Storage", "concept", 1),
    Chapter(6, "06-arithmetic-that-refuses.md", "Arithmetic That Refuses: Numbers and Time", "concept", 1),
    Chapter(7, "07-moving-value.md", "Moving Value: Assets, Payments, and Groups", "concept", 1),
    Chapter(8, "08-proving-it-works.md", "Proving It Works: Tests, Simulation, and Failure", "concept", 1),
    Chapter(None, "08z-checkpoint-foundations.md", "Mastery Checkpoint: Foundations", "checkpoint", 1),
    Chapter(9, "09-a-token-vesting-contract.md", "A Token Vesting Contract", "project", 2),
    Chapter(10, "10-proving-whos-calling.md", "Proving Who's Calling", "concept", 2),
    Chapter(11, "11-paying-for-it.md", "Paying For It: Minimum Balance, Fees, and Budget", "concept", 2),
    Chapter(12, "12-nft-vesting.md", "NFTs: Extending the Vesting Contract with Transferability", "project", 2),
    Chapter(None, "12z-checkpoint-value-under-management.md", "Mastery Checkpoint: Value Under Management", "checkpoint", 2),
    Chapter(13, "13-numbers-that-price-things.md", "Numbers That Price Things", "concept", 3),
    Chapter(14, "14-a-constant-product-amm.md", "A Constant Product AMM", "project", 3),
    Chapter(15, "15-contracts-that-talk-to-contracts.md", "Contracts That Talk to Contracts", "concept", 3),
    Chapter(16, "16-amm-factory-and-pool-provenance.md", "AMM Factory and Pool Provenance", "project", 3),
    Chapter(17, "17-yield-farming.md", "Yield Farming: Extending the AMM with Staking Rewards", "project", 3),
    Chapter(None, "17z-checkpoint-building-a-dex.md", "Mastery Checkpoint: Building a DEX", "checkpoint", 3),
    Chapter(18, "18-a-number-nobody-can-predict.md", "A Number Nobody Can Predict", "concept", 4),
    Chapter(19, "19-a-lottery-that-pays-out-or-gives-back.md", "A Lottery That Pays Out or Gives Back", "project", 4),
    Chapter(None, "19z-checkpoint-chance.md", "Mastery Checkpoint: Chance", "checkpoint", 4),
    Chapter(20, "20-signing-without-a-key.md", "Signing Without a Key", "concept", 5),
    Chapter(21, "21-delegated-limit-order-book.md", "Delegated Limit Order Book with LogicSig Agents", "project", 5),
    Chapter(None, "21z-checkpoint-stateless-programs.md", "Mastery Checkpoint: Stateless Programs", "checkpoint", 5),
    Chapter(22, "22-proving-things-without-revealing-them.md", "Proving Things Without Revealing Them", "concept", 6),
    Chapter(23, "23-private-governance-voting.md", "Private Governance Voting with Zero-Knowledge Proofs", "project", 6),
    Chapter(None, "23z-checkpoint-cryptography.md", "Mastery Checkpoint: Cryptography", "checkpoint", 6),
    Chapter(24, "24-shipping-and-surviving.md", "Shipping and Surviving", "concept", 7),
    Chapter(None, "24z-checkpoint-shipping.md", "Mastery Checkpoint: Shipping", "checkpoint", 7),
]

FRONT_MATTER = ["F1-legal-notice.md", "F2-foreword.md", "F3-preface.md", "F4-how-to-use.md"]
APPENDICES = ["A1-environment-reference.md", "A2-avm-limits.md", "A3-gotchas.md", "A4-example-finder.md"]
BACK_MATTER = ["Z1-whats-next.md", "Z2-glossary.md", "Z3-bibliography.md", "Z4-colophon.md"]

# Appendix letter as printed in the text ("Appendix C") -> filename
APPENDIX_LETTERS = {
    "A": "A1-environment-reference.md",
    "B": "A2-avm-limits.md",
    "C": "A3-gotchas.md",
    "D": "A4-example-finder.md",
}


def numbered() -> list[Chapter]:
    return [c for c in CHAPTERS if c.number is not None]


def by_number(n: int) -> Chapter:
    return next(c for c in CHAPTERS if c.number == n)


def first_of_part(part: int) -> Chapter:
    return next(c for c in CHAPTERS if c.part == part and c.number is not None)


def part_of(part: int) -> Part:
    return PARTS[part - 1]
