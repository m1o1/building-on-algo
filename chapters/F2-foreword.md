\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Foreword {-}

There is a particular kind of documentation gap that opens up around a platform good enough to attract serious engineers and young enough not to have a canon yet. Algorand has been in that gap for a while. The reference documentation is accurate and complete, the compiler is genuinely good, and there was still no single place that took an engineer who had shipped production systems in some other stack and walked them from the account model to a working automated market maker without either patronising them or skipping the parts that bite.

This book is an attempt at that place. It was written to be read in order by someone who already knows how to program and does not yet know why their contract's minimum balance went up while it was running.

It was also generated with an AI system, working under direction, and the honest thing is to say so at the front and then say what was done about it.

What was done about it is a verification harness, and it is the reason to trust anything here. Every promise in these two paragraphs is enforced by a named check in the repository's `validation/manifest.json`, not by an author's assurance. Examples carrying a source annotation are complete programs in the repository, each declaring how it is verified --- compiled, expected-to-fail, byte-compiled, unit-tested, or run end to end --- and the harness runs each in its declared mode; the annotated set is growing toward the full example list, and an annotated example that stopped compiling fails the suite rather than sitting in the text looking correct.

Transcripts --- the blocks that show what a program printed --- were captured from programs that ran on a local Algorand node, not typed from memory, and each project ships a runnable workflow and test suite that reproduce its chapter's flows against LocalNet. A drift-checker reads the whole manuscript on every run of the suite: chapter numbers, example and table references, code paths, the reciprocity of Handoff and receiving tables, and the rule that no retrieval question reaches forward. The gotcha appendix and the Example Finder are generated from the inline sources and cannot drift from them, because a test fails when they do.

None of that makes the book correct. It makes a specific and common failure mode expensive: prose that is plausible, confident, well-formatted and false. That failure mode is the one an AI-assisted technical book is most exposed to, and the exposure was treated here as the central engineering problem rather than as a disclaimer.

What the harness does not do is audit a contract. The programs here are teaching material. They are correct as far as their tests reach and they have not been through a professional security review, and the difference between those two things is the difference between a contract that works and a contract that survives contact with someone who wants your money. The book says this in several places because it is the single most important thing in it.

Read it with a node running. Break the examples on purpose --- the chapters are built assuming you will, and several of them break things for you first. And when something behaves differently from the page, check the toolchain versions in the Preface before you check your typing; this platform moves, and a book is a photograph.

--- m1o1
