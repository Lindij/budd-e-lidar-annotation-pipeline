#!/usr/bin/env python3
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw" / "rosbags"
INTERIM_DIR = ROOT / "data" / "interim"
LABELS_DIR = ROOT / "data" / "labels"
PROCESSED_DIR = ROOT / "data" / "processed"
DOCS_DIR = ROOT / "docs"


def bag_id_from_name(name: str) -> str:
    base = Path(name).stem
    if base.startswith("File_"):
        base = base[len("File_") :]
    if base.startswith("_"):
        base = base[1:]
    return base


def safe_move(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise SystemExit(f"Refusing to overwrite existing file: {dst}")
    shutil.move(str(src), str(dst))


def main() -> None:
    if not RAW_DIR.exists():
        raise SystemExit(f"Missing: {RAW_DIR}")

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Remove .mat files in raw rosbags
    for mat in RAW_DIR.glob("*.mat"):
        mat.unlink()

    # Remove duplicate File_*.bag to keep _YYYY... naming
    for bag in RAW_DIR.glob("File_*.bag"):
        bag.unlink()

    # Rename/move interim folders for the first bag that already has outputs
    existing_bags = sorted(RAW_DIR.glob("*.bag"))
    if not existing_bags:
        raise SystemExit("No .bag files found after cleanup.")

    # Assume existing outputs correspond to the first bag timestamp
    bag_id = bag_id_from_name(existing_bags[0].name)

    # Move interim folders
    pcdet_demo = INTERIM_DIR / "pcdet_demo"
    if pcdet_demo.exists():
        safe_move(pcdet_demo, INTERIM_DIR / bag_id)
    pcdet_demo_pcd = INTERIM_DIR / "pcdet_demo_pcd"
    if pcdet_demo_pcd.exists():
        safe_move(pcdet_demo_pcd, INTERIM_DIR / f"{bag_id}_pcd")
    pcdet_demo_moving = INTERIM_DIR / "pcdet_demo_moving"
    if pcdet_demo_moving.exists():
        safe_move(pcdet_demo_moving, INTERIM_DIR / f"{bag_id}_moving")

    static_map = INTERIM_DIR / "static_map.npz"
    if static_map.exists():
        safe_move(static_map, INTERIM_DIR / f"static_map_{bag_id}.npz")

    # Move model outputs to processed/bag_id
    out_dir = PROCESSED_DIR / bag_id
    out_dir.mkdir(parents=True, exist_ok=True)

    pcdet_demo_labels = LABELS_DIR / "pcdet_demo"
    if pcdet_demo_labels.exists():
        for path in pcdet_demo_labels.iterdir():
            if path.is_file():
                if path.name == "predictions.jsonl":
                    dst = out_dir / f"predictions_pointpillars_{bag_id}.jsonl"
                elif path.name == "pedestrians.jsonl":
                    dst = out_dir / f"pedestrians_pointpillars_{bag_id}.jsonl"
                elif path.name == "predictions_all.mat":
                    dst = out_dir / f"predictions_pointpillars_all_{bag_id}.mat"
                else:
                    dst = out_dir / f"{path.stem}_{bag_id}{path.suffix}"
                safe_move(path, dst)
        pcdet_demo_labels.rmdir()

    pcdet_rcnn = LABELS_DIR / "pcdet_pointrcnn_iou"
    if pcdet_rcnn.exists():
        for path in pcdet_rcnn.iterdir():
            if not path.is_file():
                continue
            name = path.name
            if name == "predictions.jsonl":
                dst = out_dir / f"predictions_pointrcnn_iou_{bag_id}.jsonl"
            elif name == "predictions_moving.jsonl":
                dst = out_dir / f"predictions_pointrcnn_iou_moving_{bag_id}.jsonl"
            elif name == "predictions_moving_test.jsonl":
                dst = out_dir / f"predictions_pointrcnn_iou_moving_test_{bag_id}.jsonl"
            elif name == "ped_tracks.jsonl":
                dst = out_dir / f"ped_tracks_pointrcnn_iou_{bag_id}.jsonl"
            elif name == "ped_tracks.csv":
                dst = out_dir / f"ped_tracks_pointrcnn_iou_{bag_id}.csv"
            elif name == "ped_tracks_interp.jsonl":
                dst = out_dir / f"ped_tracks_pointrcnn_iou_interp_{bag_id}.jsonl"
            elif name == "ped_tracks_interp.csv":
                dst = out_dir / f"ped_tracks_pointrcnn_iou_interp_{bag_id}.csv"
            elif name == "ped_tracks_interp_static.jsonl":
                dst = out_dir / f"ped_tracks_pointrcnn_iou_interp_static_{bag_id}.jsonl"
            elif name == "ped_tracks_interp_static.csv":
                dst = out_dir / f"ped_tracks_pointrcnn_iou_interp_static_{bag_id}.csv"
            else:
                dst = out_dir / f"{path.stem}_{bag_id}{path.suffix}"
            safe_move(path, dst)
        pcdet_rcnn.rmdir()

    if LABELS_DIR.exists() and not any(LABELS_DIR.iterdir()):
        LABELS_DIR.rmdir()

    # Update rosbag inventory
    inventory_path = DOCS_DIR / "rosbag_inventory.txt"
    lines = ["# ROS bag inventory (path + size)"]
    for bag in sorted(RAW_DIR.glob("*.bag")):
        size_gb = bag.stat().st_size / (1024**3)
        lines.append(f"- {bag.name} | path: {bag} | size: {size_gb:.2f} GB")
    inventory_path.write_text("\n".join(lines) + "\n")

    print(f"Organized outputs under {out_dir}")
    print(f"Updated {inventory_path}")


if __name__ == "__main__":
    main()
