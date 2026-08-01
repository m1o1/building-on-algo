# book-example: mode=script
"""Turn a program counter back into the Python line that emitted it.

algokit-utils gives you a pc and, if you hold the app spec, a message.
It never reads the `.puya.map` PuyaPy writes next to the bytecode, so
the last hop --- pc to Python source line --- is yours to make.
"""

import json
import sys
from pathlib import Path

from algosdk.source_map import SourceMap


def explain_pc(puya_map: Path, python_root: Path, pc: int) -> str:
    raw = json.loads(puya_map.read_text())
    line_index = SourceMap(raw).get_line_for_pc(pc)
    if line_index is None:
        return f"pc={pc}: no mapping"

    # `sources` is relative to the map file; line numbers are 0-based.
    source = (python_root / raw["sources"][0]).resolve()
    statement = source.read_text().splitlines()[line_index].strip()
    event = raw.get("pc_events", {}).get(str(pc), {})
    parts = [f"{source.name}:{line_index + 1}", statement]
    if event.get("op"):
        parts.append(f"op={event['op']}")
    if event.get("error"):
        parts.append(f"error={event['error']!r}")
    return f"pc={pc}  " + "  |  ".join(parts)


if __name__ == "__main__":
    print(explain_pc(Path(sys.argv[1]), Path(sys.argv[1]).parent,
                     int(sys.argv[2])))
