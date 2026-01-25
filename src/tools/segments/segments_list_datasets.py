#!/usr/bin/env python3
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
    load_env()
    client = SegmentsClient()
    datasets = client.get_datasets()
    for ds in datasets:
        print(f"{ds.full_name} | task_type={ds.task_type} | name={ds.name}")


if __name__ == "__main__":
    main()
