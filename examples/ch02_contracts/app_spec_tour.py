"""Print the parts of an ARC-56 app spec that a client actually uses."""

import json
import sys
from pathlib import Path


def main(path: str) -> None:
    spec = json.loads(Path(path).read_text())
    print(f"{spec['name']}: global schema {spec['state']['schema']['global']}")
    print(f"bare actions: {spec['bareActions']}")
    for m in spec["methods"]:
        args = ",".join(a["type"] for a in m["args"])
        ro = " readonly" if m["readonly"] else ""
        print(f"  {m['name']}({args}){m['returns']['type']}{ro} {m['actions']}")


if __name__ == "__main__":
    main(sys.argv[1])
