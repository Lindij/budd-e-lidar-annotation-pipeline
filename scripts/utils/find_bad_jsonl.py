#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: find_bad_jsonl.py <jsonl_path>")
        return 2
    path = Path(sys.argv[1])
    with path.open("r", encoding="utf-8") as f:
        for idx, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"Bad line {idx}: {exc}")
                print(line[:200])
                return 1
    print("No bad lines detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
