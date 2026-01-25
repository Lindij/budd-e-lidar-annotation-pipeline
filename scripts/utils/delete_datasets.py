#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

import requests


def load_env(path: str = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        if key and key not in os.environ:
            os.environ[key] = val


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete Segments.ai datasets")
    parser.add_argument("datasets", nargs="+", help="Dataset identifiers (owner/name)")
    args = parser.parse_args()

    load_env()
    for ds in args.datasets:
        api_key = os.environ.get("SEGMENTS_API_KEY")
        if not api_key:
            raise SystemExit("SEGMENTS_API_KEY is not set")
        url = f"https://api.segments.ai/datasets/{ds}/"
        resp = requests.delete(url, headers={"Authorization": f"APIKey {api_key}"})
        if resp.status_code not in (204, 200):
            raise SystemExit(f"Failed to delete {ds}: {resp.status_code} {resp.text}")
        print(f"Deleted {ds}", flush=True)


if __name__ == "__main__":
    main()
