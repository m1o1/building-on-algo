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
-- listing. Five puts the caption and roughly four lines of code together,
-- which is enough for the caption to be doing its job when the reader meets
-- it. Code sets at `\small`, so those four lines are a little less than four
-- `\baselineskip` of real estate -- the reservation is slightly generous,
-- deliberately.
--
-- SCOPED TO `Example` CAPTIONS ON PURPOSE. A figure caption is already inside
-- pandoc's `figure` environment with the graphic, and a table caption is
-- inside the `longtable` with its rows; neither can be separated from what it
-- names, so neither needs this and neither should be touched.

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
