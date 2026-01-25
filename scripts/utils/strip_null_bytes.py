#!/usr/bin/env python3
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: strip_null_bytes.py <file_path>")
        return 2
    path = Path(sys.argv[1])
    data = path.read_bytes()
    cleaned = data.replace(b"\x00", b"")
    if cleaned != data:
        path.write_bytes(cleaned)
        print("Null bytes removed.")
    else:
        print("No null bytes found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
