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
    parser = argparse.ArgumentParser(description="Create Segments.ai dataset for pointcloud cuboid sequence")
    parser.add_argument("--name", required=True, help="Dataset name (no owner, just name)")
    parser.add_argument("--description", default="BUDD-e pointcloud cuboid labels", help="Dataset description")
    args = parser.parse_args()

    load_env()
    client = SegmentsClient()

    task_attributes = {
        "format_version": "0.1",
        "categories": [
            {"name": "Car", "id": 1},
            {"name": "Pedestrian", "id": 2},
            {"name": "Cyclist", "id": 3},
        ],
    }

    dataset = client.add_dataset(
        name=args.name,
        description=args.description,
        task_type="pointcloud-cuboid-sequence",
        task_attributes=task_attributes,
    )

    print(f"Created dataset: {dataset.full_name}")


if __name__ == "__main__":
    main()
