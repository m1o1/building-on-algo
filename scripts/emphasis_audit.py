# Counts mid-paragraph bold spans -- the emphasis budget's unit -- and the
# sections carrying more than one. Run from the repo root.
#   run-in heads   (bold opening a line, or a list item) are NOT emphasis
#   table cells    (lines beginning `|`) are NOT emphasis
#   fenced code    is skipped entirely
# `--level 2` counts a section as `##` and deeper folded into it; `--level 9`
# treats every heading as its own section. The two disagree, which is the
# point: quote the level with the number.
import re, sys, pathlib, collections
level = int(sys.argv[sys.argv.index('--level')+1]) if '--level' in sys.argv else 2
BOLD = re.compile(r'\*\*(.+?)\*\*')
tot = 0; sec = collections.Counter()
for f in sorted(pathlib.Path('chapters').glob('*.md')):
    cur = f.name + " [preamble]"; infence = False
    for ln, line in enumerate(f.read_text().splitlines(), 1):
        if line.startswith('```'): infence = not infence; continue
        if infence: continue
        m = re.match(r'(#+)\s', line)
        if m:
            if len(m.group(1)) <= level: cur = f"{f.name}:{ln} {line.strip()[:56]}"
            continue
        if line.lstrip().startswith('|'): continue
        for b in BOLD.finditer(line):
            if re.fullmatch(r'\s*(?:[-*]\s+|\d+\.\s+)?', line[:b.start()]): continue
            tot += 1; sec[cur] += 1
multi = {k: v for k, v in sec.items() if v > 1}
print(f"level<={level}: {tot} mid-paragraph bold spans; "
      f"{len(multi)} sections carry more than one, holding {sum(multi.values())} of them")
for k, v in sorted(multi.items(), key=lambda x: -x[1])[:5]: print("  %2d  %s" % (v, k))
