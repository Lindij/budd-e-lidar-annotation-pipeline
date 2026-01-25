#!/usr/bin/env python3
import argparse
import os
from pathlib import Path

from segments import SegmentsClient


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
    parser = argparse.ArgumentParser(description="Show Segments.ai dataset info")
    parser.add_argument("--dataset", required=True, help="Dataset identifier (owner/name)")
    args = parser.parse_args()

    load_env()
    client = SegmentsClient()
    ds = client.get_dataset(args.dataset)
    print(f"dataset: {ds.full_name}")
    print(f"task_type: {ds.task_type}")
    if ds.task_attributes and ds.task_attributes.categories:
        print("categories:")
        for cat in ds.task_attributes.categories:
            print(f"  - {cat.id}: {cat.name}")
    else:
        print("categories: <none>")

    labelsets = client.get_labelsets(args.dataset)
    print("labelsets:")
    for ls in labelsets:
        print(f"  - {ls.name}")


if __name__ == "__main__":
    main()
