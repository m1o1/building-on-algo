--- Map the book's callout classes onto LaTeX environments.
--
-- Pandoc's LaTeX writer ignores Div classes: `::: {.warning}` renders as bare
-- body text, indistinguishable from the paragraph before it. This filter turns
-- each known class into a matching tcolorbox environment, defined in
-- chapters/metadata.yaml.
--
-- An unknown class is an error rather than a silent pass-through. A typo like
-- `::: {.warnign}` would otherwise produce a callout that looks exactly like
-- ordinary prose in the PDF and exactly like a callout in the HTML, which is
-- the worst of both -- the two renderers would disagree and nothing would say
-- so. scripts/validate.py check 12 catches this earlier; this is the backstop
-- for anyone who runs pandoc directly.

local CALLOUTS = {
  note    = "calloutnote",
  tip     = "callouttip",
  warning = "calloutwarning",
  gotcha  = "calloutgotcha",
  setup   = "calloutsetup",
  spec    = "calloutspec",
  version = "calloutversion",
  check   = "calloutcheck",
  tryit   = "callouttryit",
}

function Div(el)
  for _, class in ipairs(el.classes) do
    local env = CALLOUTS[class]
    if env then
      -- The Div itself is dropped and its content spliced between the raw
      -- markers, so nothing is left for the filter to match a second time.
      local blocks = {pandoc.RawBlock("latex", "\\begin{" .. env .. "}")}
      for _, block in ipairs(el.content) do
        table.insert(blocks, block)
      end
      table.insert(blocks, pandoc.RawBlock("latex", "\\end{" .. env .. "}"))
      return blocks
    end
  end
  return nil
end
