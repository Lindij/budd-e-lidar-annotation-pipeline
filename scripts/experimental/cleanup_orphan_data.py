#!/usr/bin/env python3
import argparse
import shutil
from pathlib import Path


def bag_id_from_name(name: str) -> str:
    base = name
    for suffix in ("_map_pcd", "_map", "_pcd", "_moving"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    if base.startswith("static_map_"):
        base = base[len("static_map_") :]
    return base


def collect_bag_ids(raw_dir: Path) -> set:
    bag_ids = set()
    for bag in raw_dir.glob("*.bag"):
        bag_id = bag.stem.lstrip("_")
        if bag_id.startswith("File_"):
            bag_id = bag_id[len("File_") :]
        bag_ids.add(bag_id)
    return bag_ids


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove interim/processed entries not in raw rosbags")
    parser.add_argument("--raw-dir", default="data/raw/rosbags", help="Raw rosbags directory")
    parser.add_argument("--interim-dir", default="data/interim", help="Interim directory")
    parser.add_argument("--processed-dir", default="data/processed", help="Processed directory")
    args = parser.parse_args()

    raw_dir = Path(args.raw_dir)
    interim_dir = Path(args.interim_dir)
    processed_dir = Path(args.processed_dir)

    bag_ids = collect_bag_ids(raw_dir)
    removed = []

    if interim_dir.exists():
        for entry in interim_dir.iterdir():
            base = bag_id_from_name(entry.stem)
            if base and base not in bag_ids:
                remove_path(entry)
                removed.append(str(entry))

    if processed_dir.exists():
        for entry in processed_dir.iterdir():
            if entry.is_dir() and entry.name not in bag_ids:
                remove_path(entry)
                removed.append(str(entry))

    if removed:
        print("Removed:")
        for item in removed:
            print(f"  {item}")
    else:
        print("Nothing removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
