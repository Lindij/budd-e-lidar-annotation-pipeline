#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]


def run(cmd):
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def infer_model_name(model_config: str) -> str:
    stem = Path(model_config).stem.lower()
    if "pointrcnn_iou" in stem:
        return "pointrcnn_iou"
    if "pointpillar" in stem or "pointpillars" in stem:
        return "pointpillars"
    if "centerpoint" in stem:
        return "centerpoint"
    if "pv_rcnn" in stem or "pvrcnn" in stem:
        return "pv_rcnn"
    if "parta2" in stem:
        return "parta2"
    return stem


def main():
    parser = argparse.ArgumentParser(description="End-to-end BUDD-e LiDAR pipeline")
    parser.add_argument("--bag", required=True, help="Path to ROS bag")
    parser.add_argument("--bag-id", default="", help="Bag ID (default: derived from filename)")
    parser.add_argument("--topic", default="/rslidar_points", help="PointCloud2 topic")
    parser.add_argument("--pcdet-dir", default="", help="Output .bin dir")
    parser.add_argument("--pcd-dir", default="", help="Output .pcd dir")
    parser.add_argument("--model-config", required=True, help="OpenPCDet config yaml")
    parser.add_argument("--model-ckpt", required=True, help="OpenPCDet checkpoint")
    parser.add_argument("--model-name", default="", help="Model name for output folders")
    parser.add_argument("--pred-out", default="", help="Predictions JSONL")
    parser.add_argument("--label-filter", default="", help="Filter label name (e.g. Pedestrian)")
    parser.add_argument("--label-out", default="", help="Filtered JSONL")
    parser.add_argument("--track", action="store_true", help="Run tracking + interpolation")
    parser.add_argument("--track-max-age", type=int, default=30, help="Max missed frames before drop")
    parser.add_argument("--track-interp", type=int, default=30, help="Interpolate up to N missing frames")
    parser.add_argument("--track-dist", type=float, default=1.5, help="Max XY distance for association")
    parser.add_argument("--track-use-motion", action="store_true", help="Use motion model in tracking")
    parser.add_argument("--upload", action="store_true", help="Upload to Segments.ai")
    parser.add_argument("--segments-dataset", default="", help="Segments.ai dataset (owner/name)")
    parser.add_argument("--segments-sample", default="", help="Segments.ai sample name")
    parser.add_argument("--segments-labelset", default="prelabels", help="Segments.ai labelset")
    parser.add_argument("--segments-max-frames", type=int, default=0, help="Max frames to upload")
    parser.add_argument("--segments-start-frame", type=int, default=0, help="Start frame index")
    parser.add_argument("--segments-stride", type=int, default=1, help="Upload stride")
    parser.add_argument("--skip-extract", action="store_true", help="Skip rosbag extraction")
    parser.add_argument("--skip-infer", action="store_true", help="Skip inference")
    parser.add_argument("--skip-pcd", action="store_true", help="Skip .pcd conversion")
    args = parser.parse_args()

    python = sys.executable

    bag_path = Path(args.bag)
    bag_id = args.bag_id or bag_path.stem.lstrip("_")
    if bag_id.startswith("File_"):
        bag_id = bag_id[len("File_") :]
    pcdet_dir = Path(args.pcdet_dir) if args.pcdet_dir else ROOT / "data" / "interim" / bag_id
    pcd_dir = Path(args.pcd_dir) if args.pcd_dir else ROOT / "data" / "interim" / f"{bag_id}_pcd"
    model_name = args.model_name or infer_model_name(args.model_config)
    processed_dir = ROOT / "data" / "processed" / bag_id / model_name
    processed_dir.mkdir(parents=True, exist_ok=True)
    pred_out = (
        Path(args.pred_out)
        if args.pred_out
        else processed_dir / f"predictions_{model_name}_{bag_id}.jsonl"
    )
    label_out = (
        Path(args.label_out)
        if args.label_out
        else processed_dir / f"pedestrians_{model_name}_{bag_id}.jsonl"
    )
    segments_sample = args.segments_sample or f"{bag_id}_{model_name}"

    if not args.skip_extract:
        run(
            [
                python,
                str(ROOT / "src/ingest/rosbag_to_pcdet.py"),
                "--bag",
                str(bag_path),
                "--topic",
                args.topic,
                "--out-dir",
                str(pcdet_dir),
            ]
        )

    if not args.skip_infer:
        run(
            [
                python,
                str(ROOT / "src/inference/pcdet_infer_dir.py"),
                "--cfg-file",
                args.model_config,
                "--ckpt",
                args.model_ckpt,
                "--data-path",
                str(pcdet_dir),
                "--ext",
                ".bin",
                "--out",
                str(pred_out),
            ]
        )

    if args.label_filter:
        run(
            [
                python,
                str(ROOT / "src/export/export_pedestrians.py"),
                "--pred",
                str(pred_out),
                "--frames",
                str(pcdet_dir / "frames.csv"),
                "--score",
                "0.3",
                "--out-jsonl",
                str(label_out),
                "--out-csv",
                str(label_out.with_suffix(".csv")),
                "--label",
                args.label_filter,
            ]
        )

    if args.track:
        pred_for_track = label_out if args.label_filter else pred_out
        track_out = processed_dir / f"ped_tracks_{model_name}_{bag_id}.jsonl"
        cmd = [
            python,
            str(ROOT / "src/tools/tracking/track_pedestrians.py"),
            "--pred",
            str(pred_for_track),
            "--frames",
            str(pcdet_dir / "frames.csv"),
            "--label",
            "Pedestrian",
            "--score",
            "0.3",
            "--dist-thresh",
            str(args.track_dist),
            "--max-age",
            str(args.track_max_age),
            "--interpolate-max-gap",
            str(args.track_interp),
            "--out-jsonl",
            str(track_out),
            "--out-csv",
            str(track_out.with_suffix(".csv")),
        ]
        if args.track_use_motion:
            cmd.append("--use-motion")
        run(cmd)

    if not args.skip_pcd:
        run(
            [
                python,
                str(ROOT / "src/export/bin_to_pcd_sequence.py"),
                "--in-dir",
                str(pcdet_dir),
                "--out-dir",
                str(pcd_dir),
            ]
        )

    if args.upload:
        if not args.segments_dataset:
            raise SystemExit("--segments-dataset is required when --upload is set")
        pred_for_upload = args.label_out if args.label_filter else args.pred_out
        if args.track:
            pred_for_upload = str((processed_dir / f"ped_tracks_{model_name}_{bag_id}.jsonl"))
        run(
            [
                python,
                str(ROOT / "src/export/segments_upload_sequence.py"),
                "--dataset",
                args.segments_dataset,
                "--pcd-dir",
                str(pcd_dir),
                "--frames-csv",
                str(pcdet_dir / "frames.csv"),
                "--pred",
                str(pred_for_upload),
                "--sample-name",
                segments_sample,
                "--labelset",
                args.segments_labelset,
                "--max-frames",
                str(args.segments_max_frames),
                "--start-frame",
                str(args.segments_start_frame),
                "--stride",
                str(args.segments_stride),
                "--overwrite-labels",
            ]
        )


if __name__ == "__main__":
    main()
