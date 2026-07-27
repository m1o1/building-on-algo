-- codebreak.lua -- break opportunities inside inline code, PDF edition only.
--
-- `chapters/metadata.yaml` sets `HyphenChar=None` on the monospace font,
-- because a hyphen TeX inserts inside `smart_contracts/artifacts/` is a
-- character the tool never printed and the reader cannot tell it from one that
-- was. Removing hyphenation removes the only break opportunity a long
-- identifier had, so without something in its place a line containing one
-- overflows the right margin instead.
--
-- This filter supplies the replacement: after each separator the identifier
-- already contains, insert `\discretionary{}{}{}` -- a break that prints
-- nothing on either side of it. Every character on the page is still a
-- character the tool printed, and a reader rejoining the two halves gets the
-- original string back exactly.
--
-- SEPARATORS ARE `.`, `_` AND `/`, AND DELIBERATELY NOT `-`. Breaking after a
-- real hyphen is lossless on reassembly too -- `algorand-python-testing` split
-- after either hyphen rejoins correctly -- but it is indistinguishable on the
-- page from the invented hyphen `HyphenChar=None` exists to prevent, so the
-- reader has to guess. `.`, `_` and `/` are not line-break conventions in any
-- typesetting tradition, so a break after one of them is unambiguous.
--
-- THE ACCEPTED PRICE, three sites named -- and *named* is not *all*. Of the
-- residual 51 overfull boxes, 14 contain a monospace span; these three sites
-- are five of those 14, picked because each shows a different reason the
-- filter cannot help. The other nine are ordinary residue, four of them wide
-- (`ImmutableArray` and `ReferenceArray` at 48.04pt each,
-- `gtxn.PaymentTransaction(0)` at 46.67pt, `self.joining_fee.maybe()` at
-- 42.95pt). Read the list below as an illustration, never as a bound on what
-- is left. The three: `GlobalState(UInt64)` (51.62pt) has no separator at all;
-- `algorand-python-testing` (26.01pt) has only hyphens, which are excluded
-- above; and the chapter-7 exercise-2 statement list, which the filter
-- improves greatly without repairing. That third one is one paragraph carrying
-- several boxes, and the honest way to state it is as a count and a list,
-- because any single pairing of a before-figure with an after-figure is
-- invented:
--
--     neither mechanism      4 boxes   113.24 / 81.61 / 284.18 / 158.47 pt
--     `HyphenChar=None` only 5 boxes   those four, plus 144.70 pt
--     both                   3 boxes     0.62 /  33.14 /  39.40 pt
--
-- Record that site as improved, never as fixed. Note also that the middle row
-- is the "read the middle term" argument in miniature and at one site: taking
-- hyphenation away adds a fifth box here rather than removing any of the four.
--
-- Measured 2026-07-27 over the whole book, xelatex `Overfull \hbox` count:
-- 102 with neither mechanism, 116 with `HyphenChar=None` alone, 51 with both.
-- Underfull 89 / 105 / 43. Page count 670 in all three, zero LaTeX errors,
-- zero hyperref "Token not allowed in a PDF string" warnings.
--
-- READ THE MIDDLE TERM BEFORE TOUCHING EITHER MECHANISM. Turning hyphenation
-- off *costs* 14 overfull boxes on its own (15 new, 1 repaired, per-paragraph);
-- it is not a free win that this filter then polishes. The filter is what pays
-- for it and then halves the baseline underneath. Removing the filter and
-- keeping `HyphenChar=None` ships a book measurably worse than doing neither.
--
-- Re-measure with that same statistic if this file changes; a hyphen count or
-- a word-position proxy will not show what this affects. Of that residual 51,
-- 21 are bibliography URLs or `\href` link text, which reach LaTeX as `Link`
-- and `Str` rather than `Code` and so never enter this filter at all; 14 carry
-- a monospace span, 4 are `in alignment`, and 12 are ordinary prose or table
-- cells. The URLs are the next target and need a different mechanism -- but
-- they are 41%, a plurality and not a majority, so fixing them leaves thirty
-- boxes standing. Classify by hand off `book.log` if you re-derive this: a
-- regex misses `dev.algorand.co` on the TLD and misses the resource-table
-- links entirely, because those reach the log as `[][]` with the scheme
-- swallowed. Doing it by regex returns 10, and 10 would change the plan.
--
-- Splitting the element into several `Code` inlines rather than emitting raw
-- LaTeX leaves pandoc's own escaping in charge of the text, so a span
-- containing `#`, `%`, `$`, `{` or a backslash needs no special handling here.

-- THE BREAK MUST NOT LAND ON A PAGE BOUNDARY, and that is this file's job
-- too, because the break is this file's doing. A line break inside an
-- identifier the reader scans past; a page turn inside one is a lookup. Five
-- sites did exactly that: `Txn.first_` / `valid_time`, `assert Txn.` /
-- `sender == ...`, `opt_` / `in_to_asset`, `get_` / `vesting_info`, and
-- `smart_contracts/token_vesting/` / `contract.py:`.
--
-- TeX's knob for this is `\brokenpenalty`, which it adds after any line that
-- ends in a discretionary break; LaTeX leaves it at 100, cheap enough that
-- TeX will happily end a page on one of the breaks inserted below. Setting it
-- to 10000 in `chapters/metadata.yaml` was tried first and is the wrong fix,
-- for a reason worth keeping: `\brokenpenalty` cannot tell one of these
-- breaks from an ordinary prose hyphen. The book has twenty hyphenated
-- page-ends, of which five are the defect above and fifteen are correct
-- typography, and forbidding all twenty puts the displaced material
-- somewhere. Measured, it went here:
--
--                              control   global bp   paragraph-scoped
--     page-ends on a break        20         (0)            8
--     mid-identifier page turns    5         (0)            0
--     callouts cut to a bare
--       header bar at page foot    1         (2)            0
--     captions stranded at a
--       page foot                  5         (--)           6
--
-- (All three columns are built PDFs with `scripts/keeptogether.lua` absent,
-- so the comparison isolates this mechanism. Produce them with
-- `python3 scripts/pagescan.py ctl=<pdf> scoped=<pdf>`, which defines all
-- four statistics in its own header.)
--
-- THE FOURTH ROW IS A COST OF THIS MECHANISM AND WAS MISSING FROM THIS TABLE
-- FOR SEVERAL ROUNDS. Both this comment and `publishing-pro.md` said the
-- scoped setting "introduces none", on the reasoning that stranded captions
-- belong to `keeptogether.lua` and so were not this table's business. That is
-- true of the *cure* and false of the *cause*: moving 716 paragraphs' worth of
-- material around changes where pages end, and where pages end is what strands
-- a caption. Isolated -- both arms with `keeptogether.lua` off, the only
-- difference being the `Para` handler below -- the scoped setting moves
-- Example 5-19 off the foot of p195 and strands Examples 5-3 and 7-14 on p177
-- and p277, so five real stranded captions become six. `keeptogether.lua`
-- then cures all six, which is why the shipped book has none and why this cost
-- was invisible in every scan of the shipped book. A maintainer who keeps this
-- filter and drops that one gets six, not five, and until now would have read
-- a comment here promising none. When a mechanism is measured with a second
-- mechanism switched off, the row that second mechanism owns is the one most
-- likely to be moved and least likely to be looked at.
--
-- THE PARENTHESISED COLUMN IS FROM AN OLDER SOURCE STATE and the other two
-- were re-derived on the current one; the global variant has not been rebuilt
-- since. At the round-16 source the control column read 21 / 5 / 1, so the
-- one-page drift is in the outer column and the argument is untouched -- but
-- do not quote 0 / 0 / 2 as a current measurement, and rebuild it before
-- using it to decide anything. The five sites themselves were re-confirmed
-- present in the current control at PDF pages 171, 264, 286, 312 and 318.
-- The scan that produces the middle row reports 13 candidates on the control
-- and 9 on the shipped book; the five are what remains after discarding
-- sentence-final periods before a code fence, which is the bulk of both.
-- `scripts/pagescan.py` is that scan, and it prints the candidate sites under
-- the count precisely so the discarding is done by reading and not by
-- subtracting a remembered number.
--
-- So the blunt setting fixed five sites, introduced two stranded callouts,
-- and left a third standing; the scoped one fixes the same five sites and
-- cures the pre-existing callout, at the cost of the caption row above. Both
-- are identical on Overfull \hbox, Underfull \hbox, page count and errors
-- (51 / 43 / 670 / 0), and the scoped one was marginally better on
-- Underfull \vbox as well, 194 against 195 -- BOTH OF THOSE TWO FIGURES ARE
-- FROM THE SAME OLDER SOURCE STATE as the parenthesised column, and the
-- global variant has not been rebuilt since. The current source's scoped
-- build with `keeptogether.lua` off reads 196, so nobody re-measuring will
-- reproduce 194 and nobody should read the difference as a regression. The
-- pair is quoted here for the method lesson below and for nothing else.
--
-- THAT LAST NUMBER IS WHY THIS ENTRY EXISTS. An earlier round compared the
-- two variants on `Underfull \vbox` alone, read 192 against 195, called a
-- three-box difference not worth the code, and shipped the global setting --
-- whose two stranded callouts that statistic cannot see. The variants differ
-- by well under one percent on the aggregate and by *everything* on the page.
-- Compare typography variants on the artifact the reader holds; an aggregate
-- is a search tool for finding pages to look at, never the comparison itself.
-- (An earlier draft of this paragraph put the gap at 1.5%, which is the
-- arithmetic of the 192-against-195 reading it exists to repudiate -- the
-- discredited number's conclusion quoted inside the sentence discrediting it.
-- Percentages outlive the measurements they came from more quietly than
-- counts do, because a count invites the question "off which build?" and a
-- percentage does not.)
local BROKENPENALTY_OPEN = "\\begingroup\\brokenpenalty=10000"
local BROKENPENALTY_CLOSE = "\\par\\endgroup"

local SEPARATORS = "._/"
local DISCRETIONARY = "\\discretionary{}{}{}"

-- Spans shorter than this cannot overflow a line on their own, and splitting
-- them only adds nodes for TeX to consider. It is compared against `#text`,
-- which is a count of bytes rather than of characters; every inline code span
-- in this book is ASCII, so the two are the same number here, and a span that
-- was not would only be measured generously and split anyway.
local MIN_LENGTH = 12

function Code(el)
  if FORMAT ~= "latex" then
    return nil
  end
  local text = el.text
  if #text < MIN_LENGTH then
    return nil
  end

  -- Classes and key-values go on every fragment; only the id stays on the
  -- first. The two travel differently. An id is a name for one thing, so
  -- repeating it across the fragments would name several -- whereas a class is
  -- what the span *is*, and every fragment is still part of that same span.
  --
  -- The failure mode of getting this backwards is worth stating exactly,
  -- because it is not the one you would guess. Dropping the class from the
  -- tail fragments can set the first piece of an identifier in one face and
  -- the rest of it in another:
  --
  --     \VERB|\NormalTok{some\_}|\discretionary{}{}{}\texttt{long\_}...
  --
  -- BUT ONLY A RECOGNISED LANGUAGE CLASS DOES THAT, not attribution in
  -- general. `pandoc -t latex` on each shape, run rather than recalled:
  --
  --     `x_y`{.python}     ->  \VERB|\NormalTok{x\_y}|
  --     `x_y`{.notalang}   ->  \texttt{x\_y}
  --     `x_y`{#myid}       ->  \texttt{x\_y}
  --     `x_y`{key=val}     ->  \texttt{x\_y}
  --     `x_y`              ->  \texttt{x\_y}
  --
  -- So the two-face split needs a class skylighting actually knows; an id, an
  -- unrecognised class and a key-value are all indistinguishable from a bare
  -- span in this writer. That narrows the live hazard without changing what
  -- the code should do: classes still go on every fragment, because when one
  -- of them *is* a language the split is real, and the id still stays on the
  -- first, because the filter should not depend on the writer choosing to emit
  -- no label for it.
  --
  -- No inline code element in the book carries an id, class or key-value pair
  -- today, so this is a trap rather than a live defect -- but it fires the
  -- first time one carries a language class, and silently.
  local first_attr = el.attr
  local rest_attr = pandoc.Attr("", el.attr.classes, el.attr.attributes)
  local emitted_first = false
  local function fragment(s)
    if emitted_first then
      return pandoc.Code(s, rest_attr)
    end
    emitted_first = true
    return pandoc.Code(s, first_attr)
  end

  local parts, buffer = {}, ""
  for i = 1, #text do
    local char = text:sub(i, i)
    buffer = buffer .. char
    -- No break after the final character: it would offer TeX the chance to
    -- strand the whole span on the next line for nothing.
    --
    -- No break between two adjacent separators either. `//` is Python's floor
    -- division, and splitting it leaves a `/` at one line end and a `/` at the
    -- next line's start, which reassembles as two ordinary divisions -- a
    -- different operator with a different result, and floor-division rounding
    -- is a security property in the vesting and AMM chapters. `...` would set
    -- `..`, which is not the book's elision marker, and `://` would set
    -- `http:/`.
    local next_char = text:sub(i + 1, i + 1)
    if SEPARATORS:find(char, 1, true) and i < #text
       and not SEPARATORS:find(next_char, 1, true) then
      table.insert(parts, fragment(buffer))
      table.insert(parts, pandoc.RawInline("latex", DISCRETIONARY))
      buffer = ""
    end
  end

  if #parts == 0 then
    return nil
  end
  if buffer ~= "" then
    table.insert(parts, fragment(buffer))
  end
  return parts
end

-- The scoping half of the mechanism described at the top of this file: wrap
-- only the paragraphs `Code()` actually touched, so `\brokenpenalty` applies
-- to this filter's breaks and to no ordinary prose hyphen anywhere else.
--
-- `Para` and not `Plain`. `Plain` is what pandoc uses for a tight list item, a
-- table cell and a caption -- contexts where a `\par\endgroup` is either
-- ineffective or actively wrong, and where the enclosing environment already
-- governs the page break. Restricting to `Para` is exactly the exclusion set
-- the measured variant used (`\begin`, `\end`, `\chapter`, `\section`,
-- `\subsection`, `\subsubsection`, `\paragraph`, `\item`, `\caption`,
-- `\hypertarget`, `\bookmark`), which is what produced the 9 / 0 / 0 column.
--
-- Detection walks for the raw inline rather than re-scanning the text, so the
-- two halves cannot drift: whatever `Code()` decided to split is what gets
-- wrapped. Pandoc's traversal is bottom-up, so `Code` has already run by the
-- time this sees the paragraph.
function Para(el)
  if FORMAT ~= "latex" then
    return nil
  end
  local found = false
  pandoc.walk_block(el, {
    RawInline = function(r)
      if r.format == "latex" and r.text == DISCRETIONARY then
        found = true
      end
      return nil
    end,
  })
  if not found then
    return nil
  end
  return {
    pandoc.RawBlock("latex", BROKENPENALTY_OPEN),
    el,
    pandoc.RawBlock("latex", BROKENPENALTY_CLOSE),
  }
end
