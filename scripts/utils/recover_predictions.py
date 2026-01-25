#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def missing_ranges(missing):
    if not missing:
        return []
    ranges = []
    start = prev = missing[0]
    for val in missing[1:]:
        if val == prev + 1:
            prev = val
            continue
        ranges.append((start, prev))
        start = prev = val
    ranges.append((start, prev))
    return ranges


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: recover_predictions.py <jsonl_path> <expected_frames>")
        return 2
    path = Path(sys.argv[1])
    expected = int(sys.argv[2])
    text = path.read_bytes().replace(b"\x00", b"").decode("utf-8", errors="ignore")
    text = text.replace("}{", "}\n{")
    records = {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        records[rec["frame_id"]] = line

    missing = [i for i in range(expected) if i not in records]
    with path.open("w", encoding="utf-8") as f:
        for frame_id in sorted(records):
            f.write(records[frame_id] + "\n")

    if missing:
        ranges = missing_ranges(missing)
        print(f"Missing {len(missing)} frames.")
        print("Ranges:")
        for start, end in ranges:
            print(f"{start}-{end}")
        return 1
    print(f"Recovered {len(records)} frames.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
