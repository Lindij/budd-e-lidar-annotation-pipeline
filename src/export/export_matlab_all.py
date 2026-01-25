#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path

import numpy as np
from scipy.io import savemat


def load_frame_times(frames_csv):
    times = {}
    with open(frames_csv, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            times[int(row["frame_idx"])] = float(row["stamp"])
    return times


def main():
    parser = argparse.ArgumentParser(description="Export all predictions to MATLAB .mat")
    parser.add_argument("--pred", required=True, help="Input predictions.jsonl")
    parser.add_argument("--frames", required=True, help="frames.csv with timestamps")
    parser.add_argument("--out", required=True, help="Output .mat file")
    args = parser.parse_args()

    frame_times = load_frame_times(args.frames)

    frame_ids = []
    stamps = []
    boxes = []
    scores = []
    labels = []

    with open(args.pred, "r") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            frame_id = int(rec["frame_id"])
            stamp = frame_times.get(frame_id, float("nan"))
            for box, score, label in zip(rec["boxes_lidar"], rec["scores"], rec["labels"]):
                frame_ids.append(frame_id)
                stamps.append(stamp)
                boxes.append(box)
                scores.append(score)
                labels.append(label)

    data = {
        "frame_id": np.array(frame_ids, dtype=np.int32),
        "stamp": np.array(stamps, dtype=np.float64),
        "boxes_lidar": np.array(boxes, dtype=np.float32),  # [x,y,z,dx,dy,dz,yaw]
        "scores": np.array(scores, dtype=np.float32),
        "labels": np.array(labels, dtype=object),
    }

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    savemat(out_path, data, do_compression=True)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
