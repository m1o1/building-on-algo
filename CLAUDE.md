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

