#!/usr/bin/env python3
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT / "data" / "processed"


def model_from_name(name: str) -> str:
    lower = name.lower()
    if "pointpillar" in lower:
        return "pointpillars"
    if "pointrcnn_iou" in lower:
        return "pointrcnn_iou"
    if "centerpoint" in lower:
        return "centerpoint"
    if "pv_rcnn" in lower or "pvrcnn" in lower:
        return "pv_rcnn"
    if "parta2" in lower:
        return "parta2"
    return "unknown"


def safe_move(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise SystemExit(f"Refusing to overwrite existing file: {dst}")
    shutil.move(str(src), str(dst))


def main() -> None:
    if not PROCESSED_DIR.exists():
        raise SystemExit(f"Missing: {PROCESSED_DIR}")

    for bag_dir in PROCESSED_DIR.iterdir():
        if not bag_dir.is_dir():
            continue
        # Skip already-model-scoped dirs
        if any(p.is_dir() for p in bag_dir.iterdir()):
            continue
        files = [p for p in bag_dir.iterdir() if p.is_file()]
        if not files:
            continue

        for path in files:
            model = model_from_name(path.name)
            target = bag_dir / model / path.name
            safe_move(path, target)

    print("Organized processed outputs into model subfolders.")


if __name__ == "__main__":
    main()
