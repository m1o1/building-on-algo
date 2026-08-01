\newpage

```{=latex}
\renewcommand{\BOAchapterkind}{}
```

# Colophon {-}

The text of this book is set in DejaVu Serif, headings in DejaVu Sans, and code in DejaVu Sans Mono, at 11pt on a 13.6pt baseline across a 469.75pt measure. Inline code never hyphenates: a hyphen inside a quoted identifier or an error string is a character no tool printed, and a reader has no way to tell it from one that was. Removing the hyphen costs break opportunities, so a pandoc Lua filter supplies them at the points where an identifier can legally split.

The print edition is produced by pandoc through XeLaTeX; the web edition by the same sources through mdBook, via `build.py`. The spine --- chapter numbers, filenames, kinds, part boundaries --- lives in one machine-readable table (`scripts/spine.py`) from which the build derives its structure, and a drift-checker reads the whole manuscript against it on every commit: every cross-reference, example and table number, code path, Handoff table's receiving side, and the rule that no retrieval question reaches forward. Numbers are typed in the source, but they cannot silently rot; a renumbering that leaves residue fails the build.

The figures are hand-authored SVG, rendered as-is for the web and converted for print.

Examples carrying a source annotation are complete programs under `examples/`, each declaring the mode that verifies it --- compiled, expected-to-fail, byte-compiled, unit-tested, or run end to end against LocalNet --- and a harness runs each in its declared mode; the annotated set is growing toward the full example list. Fenced transcripts were captured from programs that ran against a local Algorand node, not typed from memory. The gotcha appendix and the Example Finder are generated from the inline sources, and a test fails when they drift. `validation/manifest.json` maps every promise the front matter makes to the check that enforces it, and every check exists because the defect it looks for reached a draft first.

The cover was generated with Grok. The manuscript was written with Claude, under human direction, on a repository whose history records what each round of review found.
