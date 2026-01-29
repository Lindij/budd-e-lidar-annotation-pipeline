#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path
from typing import Dict, List

import time

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


def load_frame_times(frames_csv: Path) -> Dict[int, float]:
    times: Dict[int, float] = {}
    for line in frames_csv.read_text().splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 2:
            continue
        frame_idx = int(parts[0])
        stamp = float(parts[1])
        times[frame_idx] = stamp
    return times


def load_predictions(pred_jsonl: Path) -> Dict[int, List[Dict]]:
    frames: Dict[int, List[Dict]] = {}
    with pred_jsonl.open("r") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            frame_id = int(rec["frame_id"])
            if "boxes_lidar" in rec:
                frames[frame_id] = [
                    {"box": box, "label": lab, "score": score}
                    for box, lab, score in zip(rec["boxes_lidar"], rec["labels"], rec["scores"])
                ]
            else:
                frames.setdefault(frame_id, []).append(
                    {
                        "box": rec["box_lidar"],
                        "label": rec.get("label", "Pedestrian"),
                        "score": rec.get("score", 1.0),
                        "track_id": rec.get("track_id"),
                    }
                )
    return frames


def upload_asset_with_retry(client: SegmentsClient, pcd_path: Path, max_retries: int = 5) -> str:
    for attempt in range(1, max_retries + 1):
        try:
            with pcd_path.open("rb") as f:
                asset = client.upload_asset(f, filename=pcd_path.name)
            return asset.url
        except Exception as exc:
            msg = " ".join(
                [str(exc), str(getattr(exc, "message", "")), repr(getattr(exc, "args", ""))]
            ).lower()
            if "throttled" in msg or "429" in msg:
                if attempt == max_retries:
                    raise
                time.sleep(2 * attempt)
                continue
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload PCD sequence + prelabels to Segments.ai")
    parser.add_argument("--dataset", required=True, help="Dataset identifier (owner/name)")
    parser.add_argument("--pcd-dir", required=True, help="Directory with .pcd sequence")
    parser.add_argument("--frames-csv", required=True, help="frames.csv for timestamps")
    parser.add_argument("--pred", required=True, help="predictions.jsonl (all classes)")
    parser.add_argument("--sample-name", required=True, help="Sample name in Segments.ai")
    parser.add_argument("--labelset", default="prelabels", help="Labelset name for predictions")
    parser.add_argument("--max-frames", type=int, default=0, help="Max frames to upload (0 = all)")
    parser.add_argument("--stride", type=int, default=1, help="Upload every Nth frame")
    parser.add_argument("--start-frame", type=int, default=0, help="Start frame index (0-based)")
    parser.add_argument("--label-map", default="", help="JSON map of label name -> dataset category")
    parser.add_argument("--overwrite-labels", action="store_true", help="Overwrite existing labels")
    parser.add_argument("--allow-empty", action="store_true", help="Allow empty label upload when no annotations match")
    args = parser.parse_args()

    load_env()
    client = SegmentsClient()

    dataset = client.get_dataset(args.dataset)
    if dataset.task_type != "pointcloud-cuboid-sequence":
        raise SystemExit(f"Dataset task_type must be pointcloud-cuboid-sequence (got {dataset.task_type})")

    if not dataset.task_attributes or not dataset.task_attributes.categories:
        raise SystemExit("Dataset has no label categories. Define labels in Segments.ai first.")

    category_map = {c.name: c.id for c in dataset.task_attributes.categories}
    label_map = {}
    if args.label_map:
        label_map = json.loads(args.label_map)

    pcd_dir = Path(args.pcd_dir)
    frames_csv = Path(args.frames_csv)
    pred_jsonl = Path(args.pred)

    frame_times = load_frame_times(frames_csv)
    predictions = load_predictions(pred_jsonl)

    pcd_files = sorted(pcd_dir.glob("*.pcd"))
    if args.start_frame:
        pcd_files = pcd_files[args.start_frame :]
    if args.max_frames:
        pcd_files = pcd_files[: args.max_frames * args.stride : args.stride]
    else:
        pcd_files = pcd_files[:: args.stride]

    existing = client.get_samples(args.dataset, name=args.sample_name)
    if existing:
        sample = existing[0]
        frames = getattr(sample.attributes, "frames", [])
        if not frames:
            raise SystemExit(f"Existing sample {args.sample_name} has no frames to label.")
        print(f"Using existing sample: {sample.uuid}")
    else:
        print(f"Uploading {len(pcd_files)} frames to Segments.ai...")
        frames = []
        for idx, pcd_path in enumerate(pcd_files):
            asset_url = upload_asset_with_retry(client, pcd_path)
            frame_id = int(pcd_path.stem)
            frames.append(
                {
                    "pcd": {"url": asset_url, "type": "pcd"},
                    "timestamp": frame_times.get(frame_id),
                    "name": pcd_path.name,
                }
            )
            if (idx + 1) % 50 == 0 or idx == len(pcd_files) - 1:
                print(f"Uploaded {idx + 1}/{len(pcd_files)}")

        sample = None
        for attempt in range(1, 6):
            try:
                sample = client.add_sample(
                    dataset_identifier=args.dataset,
                    name=args.sample_name,
                    attributes={"frames": frames},
                )
                break
            except Exception as exc:
                msg = " ".join(
                    [str(exc), str(getattr(exc, "message", "")), repr(getattr(exc, "args", ""))]
                ).lower()
                if "throttled" in msg or "429" in msg:
                    if attempt == 5:
                        raise
                    time.sleep(2 * attempt)
                    continue
                raise
        if sample is None:
            raise SystemExit("Failed to create sample after retries.")
        print(f"Created sample: {sample.uuid}")

    # Ensure labelset exists
    labelsets = client.get_labelsets(args.dataset)
    if not any(ls.name == args.labelset for ls in labelsets):
        client.add_labelset(args.dataset, args.labelset, description="Model prelabels")
        print(f"Created labelset: {args.labelset}")

    # Build sequence cuboid labels
    label_frames = []
    ann_id = 1
    matched = 0
    skipped = 0
    for frame in frames:
        if isinstance(frame, dict):
            frame_name = frame["name"]
            frame_ts = frame.get("timestamp")
        else:
            frame_name = getattr(frame, "name", None)
            frame_ts = getattr(frame, "timestamp", None)
        if not frame_name:
            continue
        frame_id = int(Path(frame_name).stem)
        anns = []
        for item in predictions.get(frame_id, []):
            label = label_map.get(item["label"], item["label"])
            if label not in category_map:
                skipped += 1
                continue
            x, y, z, dx, dy, dz, yaw = item["box"]
            track_id = item.get("track_id")
            if track_id is None:
                track_id = ann_id
            else:
                track_id = int(track_id)
            anns.append(
                {
                    "id": ann_id,
                    "track_id": track_id,
                    "category_id": category_map[label],
                    "position": {"x": x, "y": y, "z": z},
                    "dimensions": {"x": dx, "y": dy, "z": dz},
                    "yaw": yaw,
                    "type": "cuboid",
                }
            )
            ann_id += 1
            matched += 1
        label_frames.append({"annotations": anns, "timestamp": frame_ts})

    if matched == 0 and not args.allow_empty:
        raise SystemExit("No annotations matched dataset categories. Check category names or use --label-map.")

    if args.overwrite_labels:
        try:
            client.update_label(sample.uuid, args.labelset, {"frames": label_frames})
        except Exception:
            client.add_label(sample.uuid, args.labelset, {"frames": label_frames})
    else:
        client.add_label(sample.uuid, args.labelset, {"frames": label_frames})
    print(f"Annotations matched={matched} skipped={skipped}")
    print("Uploaded prelabels.")


if __name__ == "__main__":
    main()
