#!/usr/bin/env python3
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: truncate_predictions.py <jsonl_path> <max_frame_id_exclusive>")
        return 2
    path = Path(sys.argv[1])
    cutoff = int(sys.argv[2])
    kept = 0
    with path.open("r", encoding="utf-8") as f_in:
        lines = []
        for line in f_in:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec["frame_id"] < cutoff:
                lines.append(line)
                kept += 1
    with path.open("w", encoding="utf-8") as f_out:
        f_out.writelines(lines)
    print(f"Kept {kept} frames < {cutoff}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
