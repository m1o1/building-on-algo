-- figures.lua — point the LaTeX writer at the PDF copy of each figure.
--
-- Chapters never name a file. build.py's resolver expands {{include-fig:slug}}
-- into a single image paragraph pointing at figures/<slug>.svg, because that is
-- the file the HTML edition serves. LaTeX cannot use it: graphicx has no SVG
-- reader, and the vector PDF beside it is what \includegraphics wants. Rather
-- than emit different Markdown per renderer — which would mean the two editions
-- no longer build from the same resolved source — the swap happens here, in the
-- one place that only the PDF pass runs through.
--
-- The directory is dropped along with the extension. pandoc is invoked with
-- --resource-path=.:figures/out, so a bare <slug>.pdf resolves, and the emitted
-- \includegraphics carries no path that would break if figures/ ever moved.

local function basename(path)
  return path:match("([^/]+)$") or path
end

function Image(img)
  local src = img.src
  if src:match("^figures/[%w%-]+%.svg$") then
    img.src = basename(src):gsub("%.svg$", ".pdf")
  end
  return img
end
