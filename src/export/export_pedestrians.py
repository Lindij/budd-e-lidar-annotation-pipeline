#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path


def load_frame_times(frames_csv):
    times = {}
    with open(frames_csv, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            times[int(row["frame_idx"])] = float(row["stamp"])
    return times


def main():
    parser = argparse.ArgumentParser(description="Filter predictions to pedestrians and export")
    parser.add_argument("--pred", required=True, help="Input predictions.jsonl")
    parser.add_argument("--frames", required=True, help="frames.csv with timestamps")
    parser.add_argument("--score", type=float, default=0.3, help="Score threshold")
    parser.add_argument("--out-jsonl", required=True, help="Output JSONL")
    parser.add_argument("--out-csv", required=True, help="Output CSV")
    parser.add_argument("--label", default="Pedestrian", help="Label name to keep")
    args = parser.parse_args()

    frame_times = load_frame_times(args.frames)
    out_jsonl = Path(args.out_jsonl)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    with open(args.pred, "r") as f_in, open(out_jsonl, "w") as f_out, open(out_csv, "w", newline="") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(["frame_id", "stamp", "label", "score", "x", "y", "z", "dx", "dy", "dz", "yaw"])

        for line in f_in:
            if not line.strip():
                continue
            rec = json.loads(line)
            frame_id = rec["frame_id"]
            stamp = frame_times.get(frame_id)
            if stamp is None:
                continue

            for box, score, label in zip(rec["boxes_lidar"], rec["scores"], rec["labels"]):
                if label != args.label:
                    continue
                if score < args.score:
                    continue
                out_rec = {
                    "frame_id": frame_id,
                    "stamp": stamp,
                    "label": label,
                    "score": score,
                    "box_lidar": box,
                }
                f_out.write(json.dumps(out_rec) + "\n")
                writer.writerow([frame_id, f"{stamp:.6f}", label, f"{score:.4f}"] + box)

    print(f"Wrote {out_jsonl}")
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()
