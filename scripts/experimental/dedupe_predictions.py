#!/usr/bin/env python3
import json
from pathlib import Path
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: dedupe_predictions.py <jsonl_path> <expected_frames>")
        return 2
    path = Path(sys.argv[1])
    expected = int(sys.argv[2])
    records = {}
    bad_lines = 0
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
                records[rec["frame_id"]] = line
                continue
            except json.JSONDecodeError:
                bad_lines += 1

            # Recover from concatenated JSON objects on one line.
            chunks = line.replace("}{", "}\n{").splitlines()
            for chunk in chunks:
                if not chunk.strip():
                    continue
                try:
                    rec = json.loads(chunk)
                except json.JSONDecodeError:
                    bad_lines += 1
                    continue
                records[rec["frame_id"]] = chunk + "\n"
    missing = [i for i in range(expected) if i not in records]
    if missing:
        print(f"Missing frames: {missing[:10]} (total {len(missing)})")
        print(f"Bad lines skipped: {bad_lines}")
        return 1
    with path.open("w", encoding="utf-8") as f:
        for frame_id in sorted(records):
            f.write(records[frame_id])
    print(f"Deduped to {len(records)} frames: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
