"""Read back what `algokit project run build` left on disk."""

import base64
import json
from pathlib import Path

SPEC = Path("smart_contracts/artifacts/greeter/Greeter.arc56.json")


def main() -> None:
    spec = json.loads(SPEC.read_text())
    teal = base64.b64decode(spec["source"]["approval"]).decode()
    print(f"{spec['name']}: {len(teal.splitlines())} lines of approval TEAL")
    for method in spec["methods"]:
        args = ",".join(arg["type"] for arg in method["args"])
        print(f"  {method['name']}({args}){method['returns']['type']}")
    for entry in spec["sourceInfo"]["approval"]["sourceInfo"]:
        if "errorMessage" in entry:
            print(f"  pc {entry['pc'][0]} -> {entry['errorMessage']}")


if __name__ == "__main__":
    main()
