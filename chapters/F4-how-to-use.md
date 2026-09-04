\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# How to Use This Book {-}

The Preface says what is in the book. This says what to do with it.

## Read It in Order, or Don't {-}

The default path is straight through. Nothing is used before the chapter that introduces it, and each project chapter spends the concepts of the chapters immediately above it. A reader starting at page one and finishing at the last never has to look anything up.

Three other paths work, and each costs something specific.

**You have shipped on another chain and want the differences.** Read Chapter 2, Chapter 3, Chapter 11 and Chapter 10, in that order, then go to whichever project interests you. Those four carry the things that are genuinely different here: no reentrancy, no `msg.sender` that means what you think, a minimum balance that rises under a running contract, and an opcode budget that is spent rather than metered. Skipping them and reading a project chapter first produces working code and a wrong model.

**You need one mechanism today.** Appendix D indexes every numbered example by the task it performs, phrased the way you would ask for it ("opt my contract into an asset so it can hold it"). Look up the task, read that example, and follow its cross-references backwards if the surrounding code assumes something you do not have. Examples that live on disk under `examples/` open with a comment line naming their file, so you can run one before deciding whether it is the one you meant; that set is growing toward the full example list.

**You are auditing rather than building.** Read Appendix C, which collects every gotcha in the book grouped by topic, then Chapter 10 and Chapter 24. Appendix B is the one-page reference of every limit and cost.

The one path that does not work is starting at a project chapter. Their contracts run from 235 to 516 lines before the client code around them, they assume the concept chapters above them, and they will teach you an idiom without teaching you what it is for.

## The Two Kinds of Chapter {-}

A **concept chapter** takes one thing an application needs to do --- remember something, hold data that grows, move value, prove who is calling --- and works out how to do it on Algorand. It opens on the need and the point where the obvious answer runs out, then works through it. Most chapters carry one small contract from a first pass to a finished one; a few have no single artifact and are a tour of a toolkit instead. The examples throughout are complete programs, not fragments; those carrying a source annotation are verified in their declared modes, and the annotated set is growing toward the full example list. Hazards are marked where you would hit them rather than collected at the end.

A **project chapter** builds one program end to end. It re-teaches nothing; where it needs a mechanic it points back at the example that built it. Every project chapter that ships with a directory under `projects/` can be run before it is read, and the chapter's first section tells you how.

## The Apparatus, and What Each Part Is For {-}

Six devices recur. They are not decoration, and skipping them changes what you retain.

A ***Predict*** prompt in italics stops you before a result and asks what you expect. Answering it wrong is the point: a prediction you had to commit to is what makes the correction stick. Do not read past one without an answer, even a bad one.

***Retrieval*** closes every concept chapter with six to eleven questions to answer from memory, with the book shut. About three in ten reach back into earlier chapters, and those are the ones that do the work --- recalling something you learned four chapters ago is what stops it decaying.

***Exercises*** run five rungs in concept chapters, in order: **Trace** (execute code by hand), **Parsons** (put scrambled lines in a working order), **Debug** (find the defect), **Compare** (evaluate designs against stated criteria), and **Extend** (build something the chapter did not). Project chapters start higher, because a reader who has just assembled a four-hundred-line AMM does not need to trace one: they are labelled by what they ask of you --- **Apply**, **Analyze**, **Evaluate**, **Create** --- and every one of them ends at modification or design rather than at reading. Most exercises have an answer you can check by running something; the Compare and Analyze ones do not, and are worth writing down anyway.

***Before You Continue*** is five first-person claims at the end of each chapter (Chapter 1's, fittingly, is a checklist of things your machine can prove instead). Read them as a gate: if you cannot make one of them honestly, reread the section that teaches it before the next chapter assumes it.

***Gotchas*** mark behaviour that reliably surprises people the first time. Every one of them is in Appendix C as well as in the chapter where it bites, so you can find one again without remembering which chapter it was in.

***Mastery checkpoints*** close each Part. A chapter checklist asks whether you followed the chapter; a checkpoint asks whether you can build something the Part did not show you. If a checkpoint's task is out of reach, the Part is not finished, whatever the individual checklists said.

## Running the Code {-}

Chapter 1 takes an empty directory to a deployed contract. Do it first; every chapter after it assumes a working LocalNet, and Appendix A is the reference when something in the environment refuses.

Two directories hold runnable code, and they are different things:

- `examples/` holds the complete programs behind annotated numbered examples, each verified by the harness in its declared mode; the annotated set is growing toward the full example list. Where a chapter's example carries an annotation, that file is what it shows.
- `projects/` holds the full project builds, one directory per project chapter, each with its own `pyproject.toml`, tests, and deploy scripts. Companion projects that left the spine live under `advanced/` instead.

Everything is validated against the toolchain baseline the Preface pins. When a walkthrough behaves differently from the text, check the versions before checking your typing.

## When Something Fails {-}

A failing contract on Algorand tells you more than most runtimes do. Chapter 1 names three habits for when a step refuses --- read the error before touching anything, ask the chain what it actually thinks, and know which commands destroy state --- and they stay in force for the whole book. Two more become available once the book has taught their machinery:

- Reach for `simulate` before adding print statements (Chapter 8). It runs a transaction group against real state and returns the trace without committing anything.
- When the failure is about money rather than logic, it is almost always the minimum balance (Chapter 11 explains who is billed for what).
