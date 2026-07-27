-- keeptogether.lua -- an example caption stays on the page with its listing.
--
-- `build.py`'s `_caption()` sets an example caption as a bold lead-in
-- paragraph rather than as pandoc's `: caption` syntax, because against a code
-- block that syntax makes the paragraph ABOVE the caption into a definition
-- list term. The consequence is that the caption and the listing it names are
-- two independent blocks as far as TeX is concerned, and TeX will happily end
-- a page on the caption and start the next one with the code. That is a defect
-- the reader feels and no log line reports: a caption is a label, and a label
-- at the foot of a page names nothing.
--
-- `\nopagebreak` BETWEEN THE TWO IS THE OBVIOUS FIX AND DOES NOTHING. It was
-- tried first, on the reasoning that `\penalty10000` after the caption makes
-- the break at the penalty cost 10000 and the break at the glue that follows
-- illegal, since TeX only breaks at glue preceded by a non-discardable item.
-- That reasoning is correct and irrelevant, because the glue after the caption
-- is not where the break happens. Pandoc's `Shaded` is framed.sty's
-- `snugshade`, and `\MakeFramed` opens by inserting its own breakpoints --
-- `\penalty-30`, then `\penalty\z@`, then `\penalty1800` (framed.sty lines
-- 299-316) -- guarded only by `\if@nobreak`. Those sit after anything this
-- filter can emit, so the page builder still has three legal breaks to choose
-- from between the caption and the code. Measured on the built PDF: the
-- `\nopagebreak` variant moved not one of the six stranded captions, and left
-- all four page-makeup statistics -- broken page-ends, mid-identifier page
-- turns, stranded captions, empty callout header bars -- at exactly the
-- figures they had without it.
--
-- So the fix has to reserve room rather than forbid a break, and it has to do
-- it BEFORE the caption. `\Needspace*{5\baselineskip}` asks whether five lines
-- fit in what is left of the page and, if not, breaks now -- putting the
-- caption at the top of the next page with its listing under it. The starred
-- form is the deterministic one: plain `\needspace` only nudges the page
-- builder with a stretchable skip, and `\Needspace` without the star pads the
-- short page with `\vfil` before breaking, which trades a stranded caption for
-- a page of white space.
--
-- Five, not two or ten. framed itself ejects when fewer than `2\baselineskip`
-- remain, so anything at or below two is already handled and would change
-- nothing; ten would break pages that had room for a caption and half its
-- listing.
--
-- WHAT FIVE ACTUALLY BUYS IS ONE LINE OF CODE AT THE TIGHTEST SITE, not four.
-- The arithmetic that says four runs the wrong way: `\Needspace*` counts
-- `\baselineskip` at body size, while what gets spent inside the reservation
-- is the caption paragraph, the `snugshade` frame's own padding, and then code
-- lines set at `\small`. Measured on the shipped PDF, across all 137 caption
-- sites, the number of lines sharing the page with the caption below it runs
-- 1, 2, 2, 3, 3, 3, 3, 3, 4, 4, ... -- the tightest is p196
-- (`Example 5-20. A cliff before the linear part`), which carries the caption
-- and exactly one line, `from algopy import ARC4Contract, UInt64, arc4, op,
-- subroutine`. Read the guarantee as *at least one line of code and usually
-- three*. That is still enough for the caption to be doing its job -- a label
-- with a line of its listing under it names something -- but "roughly four" is
-- a claim the artifact does not support, and a maintainer who raises the
-- reservation expecting to protect four lines will be surprised twice. If four
-- is genuinely wanted, `7\baselineskip` is the place to start, and it has to
-- be re-measured rather than reasoned about.
--
-- `\Needspace*` IS NOT INERT WHEN IT DECLINES TO BREAK. `\@sneedsp@` expands
-- to `\par \penalty-100` BEFORE it compares `\pagegoal-\pagetotal` against the
-- reservation (needspace.sty v1.3d), so the `\par` and the penalty fire at all
-- 137 sites and not only at the handful where the space test bites. A penalty
-- of -100 is a *bonus*: at every example caption in the book, TeX is now paid
-- a little to end the page just above it. That is the mechanism behind this
-- filter's share of the vertical redistribution, and it is why the price shows
-- up on pages that have no stranded caption anywhere near them. Seven pages
-- were rasterised before accepting it (p155 -59pt, p244 -52.6, p166 -46.7,
-- p226 -45.5, p191 and p196 -27.5, p250 -25.4); all read as ordinary
-- interparagraph loosening.
--
-- SCOPED TO `Example` CAPTIONS ON PURPOSE. A figure caption is already inside
-- pandoc's `figure` environment with the graphic, and a table caption is
-- inside the `longtable` with its rows; neither can be separated from what it
-- names, so neither needs this and neither should be touched.
--
-- MEASURED on a matched pair built from the same source, this filter off the
-- pandoc argv against this filter on and nothing else changed
-- (`/tmp/r18w/measure_nokeep.sh` against the shipped build): six captions
-- cured, none introduced. Without it, pages 108, 130, 133, 177, 226 and 277
-- each end on the caption of Examples 3-12, 4-4, 4-6, 5-3, 6-12 and 7-14
-- respectively; with it, `scripts/pagescan.py` returns zero. The price was
-- `Underfull \vbox` 196 -> 205 and no change at all to `Overfull \hbox`,
-- `Underfull \hbox`, page count or errors (51 / 43 / 670 / 0), nor to the
-- other three page-makeup statistics (8 broken page-ends, 9 benign
-- ident-split candidates, 0 empty callout header bars in both). That is
-- exactly the expected shape, because this decides where pages end and not
-- where lines do.
--
-- THE PRICE IS NOW ZERO, AND NOT BECAUSE THIS FILTER CHANGED. The book sets
-- `\raggedbottom` in `chapters/metadata.yaml`; the class default for a
-- `twoside` document is `\flushbottom` (`report.cls:729-733`), and it was
-- `\flushbottom` that generated the `Underfull \vbox` reports in the first
-- place -- a page short of its full height had to make the height up out of
-- stretchable glue, and the output routine reported the shortfall. Under
-- `\raggedbottom` the output-active population is empty. A matched pair reads
-- 208 boxes on the flush build and 75 on the ragged one, and those 75 are the
-- same non-output-active residue present in both, so the flush figure
-- decomposes exactly as 133 + 75. **The 196 -> 205 step cannot be reproduced
-- on the shipped configuration**: both arms of it now report the same 75. Do
-- not go looking for the nine boxes and do not read their absence as this
-- filter having become free -- what it costs is unchanged, and the instrument
-- that used to price it has stopped resolving. Every `Underfull \vbox` figure
-- in this repository, in any file, is `\flushbottom`-era for the same reason.
-- The four statistics in the tuple above are also from an older tree; they
-- read 29 / 42 / 674 / 0 today, and neither arm of this comparison has been
-- rebuilt since, so the tuple stands as the record of a matched pair rather
-- than as a current measurement. The current shipped book's pagescan line is
-- `broken page-ends 6 | ident-split candidates 10 | stranded captions 0 |
-- empty callout bars 0`.
--
-- 137 `\Needspace*` are emitted against the book's 137
-- anchored example captions, and the two counts match because every one of
-- those captions is followed by a fence -- which is the invariant worth
-- checking, rather than the coincidence of two equal numbers.
--
-- COUNT IT WITH `grep -cxF '\Needspace*{5\baselineskip}'` AND NOT WITH
-- `grep -c Needspace`, which returns 138 because the preamble carries a
-- comment mentioning the macro. **The `-F` is not a convenience.** This
-- comment carried `grep -c '^\Needspace\*{5\\baselineskip}$'` for several
-- rounds, quoted as the command that returns 137, and it returns **0**: GNU
-- grep's BRE has no `\N` escape, and an undefined escape is the bare
-- character, so the pattern hunts for a line beginning `Needspace` with no
-- backslash in front of it and finds none. Verified on a two-line fixture
-- rather than argued about --
--
--   printf '\\Needspace*{5\\baselineskip}\n' > /tmp/nd.txt
--   grep -c '^\Needspace\*{5\\baselineskip}$' /tmp/nd.txt   # 0
--   grep -cxF '\Needspace*{5\baselineskip}'   /tmp/nd.txt   # 1
--
-- and the general rule is worth more than the fix: **a counting command
-- recorded in a comment is a claim, and a claim that silently returns zero
-- reads exactly like a mechanism that is not firing.** Anyone who ran the old
-- form would have concluded this filter emits nothing at all. Escape-heavy
-- LaTeX literals belong in `-F`, where there are no escapes to get wrong.
-- Count the captions from the anchors --
-- `grep -rc '{#ex:' chapters/` -- and not from `grep -r '^Example: '`, which
-- also returned 138 for months because one prose sentence in chapter 9 began
-- with the word and carried no anchor. Two different off-by-ones, in
-- opposite files, arriving at the same wrong number from opposite directions:
-- 138 looked corroborated because two independent counts agreed, and neither
-- was counting captions. `validate.py` check 22 now refuses the second one.
--
-- TWO OF THE SIX ARE THIS BOOK'S OWN DOING, not TeX's. With `codebreak.lua`'s
-- `Para` handler also off -- a build with neither page-makeup mechanism --
-- only five captions strand, at pages 108, 130, 133, 195 and 226. Scoping
-- `\brokenpenalty` moves Example 5-19 off the foot of p195 and puts Examples
-- 5-3 and 7-14 onto the feet of p177 and p277, so the six this filter cures
-- are five pre-existing defects plus one net new one that the other mechanism
-- created. Both filters are still worth their price and the shipped book has
-- none of the six, but the honest statement of the pair is that these two
-- mechanisms are coupled through page makeup: neither can be evaluated on a
-- build where the other is on, and the one that pays is not the one that
-- caused it. `scripts/codebreak.lua`'s table carries the same row.
--
-- Re-derive it on a fresh pair rather than reusing an old build directory:
-- the control has to be at the *current* source or it answers a question
-- about an older manuscript. And remove the filter by dropping the single
-- `--lua-filter=path` token -- it is one token in this argv, so the
-- delete-the-token-and-its-neighbour idiom silently removes `figures.lua`
-- as well.

local CAPTION_LABEL = "^Example %d+%-%d+%.$"
local RESERVE = "\\Needspace*{5\\baselineskip}"

-- The caption may be followed by the `<!-- finder: ... -->` comment the book
-- uses to mark what an example demonstrates. That reaches here as an HTML
-- `RawBlock` and the LaTeX writer drops it, so it sits between the caption and
-- the listing in the AST while contributing nothing to the page. Skipping over
-- any block that writes nothing in this format keeps the adjacency test about
-- what the reader sees rather than about what the AST happens to hold.
local function writes_nothing(block)
  return block.t == "RawBlock" and block.format ~= "latex" and block.format ~= "tex"
end

local function is_example_caption(block)
  if block.t ~= "Para" then
    return false
  end
  local first = block.content[1]
  if first == nil or first.t ~= "Strong" then
    return false
  end
  return pandoc.utils.stringify(first):match(CAPTION_LABEL) ~= nil
end

function Blocks(blocks)
  if FORMAT ~= "latex" then
    return nil
  end
  local out = pandoc.List()
  local changed = false
  for i, block in ipairs(blocks) do
    if is_example_caption(block) then
      local j = i + 1
      while blocks[j] ~= nil and writes_nothing(blocks[j]) do
        j = j + 1
      end
      if blocks[j] ~= nil and blocks[j].t == "CodeBlock" then
        out:insert(pandoc.RawBlock("latex", RESERVE))
        changed = true
      end
    end
    out:insert(block)
  end
  if not changed then
    return nil
  end
  return out
end
