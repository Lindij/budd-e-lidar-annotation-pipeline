#!/usr/bin/env python3
import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Track:
    track_id: int
    last_box: list
    last_frame: int
    last_center: tuple
    last_stamp: float
    vx: float = 0.0
    vy: float = 0.0
    hits: int = 0
    missed: int = 0


def load_frame_times(frames_csv):
    if not frames_csv:
        return {}
    times = {}
    with open(frames_csv, "r", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            times[int(row["frame_idx"])] = float(row["stamp"])
    return times


def box_center_xy(box):
    return float(box[0]), float(box[1])


def dist_xy(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return (dx * dx + dy * dy) ** 0.5


def match_tracks(tracks, detections, dist_thresh, frame_id, frame_time, use_motion, motion_max_gap):
    pairs = []
    for ti, trk in enumerate(tracks):
        t_center = trk.last_center
        if t_center is None:
            t_center = box_center_xy(trk.last_box)
        if use_motion:
            missing_frames = frame_id - trk.last_frame
            if missing_frames > 0 and missing_frames <= motion_max_gap:
                dt = frame_time - trk.last_stamp
                if dt > 0:
                    t_center = (t_center[0] + trk.vx * dt, t_center[1] + trk.vy * dt)
        for di, det in enumerate(detections):
            d_center = box_center_xy(det["box_lidar"])
            d = dist_xy(t_center, d_center)
            if d <= dist_thresh:
                pairs.append((d, ti, di))

    pairs.sort(key=lambda x: x[0])
    assigned_tracks = set()
    assigned_dets = set()
    matches = []

    for d, ti, di in pairs:
        if ti in assigned_tracks or di in assigned_dets:
            continue
        assigned_tracks.add(ti)
        assigned_dets.add(di)
        matches.append((ti, di))

    return matches, assigned_tracks, assigned_dets


def main():
    parser = argparse.ArgumentParser(
        description="Simple pedestrian tracking by greedy center-distance matching"
    )
    parser.add_argument("--pred", required=True, help="Input predictions.jsonl")
    parser.add_argument("--frames", help="frames.csv with timestamps")
    parser.add_argument("--label", default="Pedestrian", help="Label name to keep")
    parser.add_argument("--score", type=float, default=0.3, help="Score threshold")
    parser.add_argument(
        "--dist-thresh",
        type=float,
        default=1.5,
        help="Max XY distance (meters) to associate detections",
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=3,
        help="Max missed frames before a track is dropped",
    )
    parser.add_argument("--out-jsonl", required=True, help="Output JSONL with track_id")
    parser.add_argument("--out-csv", required=True, help="Output CSV with track_id")
    parser.add_argument(
        "--interpolate-max-gap",
        type=int,
        default=0,
        help="Fill gaps up to N missing frames per track (0 = disabled)",
    )
    parser.add_argument(
        "--use-motion",
        action="store_true",
        help="Use a constant-velocity motion model for association",
    )
    parser.add_argument(
        "--motion-max-gap",
        type=int,
        default=10,
        help="Only use motion prediction up to N missing frames",
    )
    args = parser.parse_args()

    frame_times = load_frame_times(args.frames)

    frames = []
    with open(args.pred, "r") as f_in:
        for line in f_in:
            if not line.strip():
                continue
            rec = json.loads(line)
            frames.append(rec)

    frames.sort(key=lambda r: r["frame_id"])

    out_jsonl = Path(args.out_jsonl)
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    tracks = []
    next_track_id = 1

    all_dets = []

    for rec in frames:
        frame_id = int(rec["frame_id"])
        stamp = frame_times.get(frame_id)

        detections = []
        for box, score, label in zip(rec["boxes_lidar"], rec["scores"], rec["labels"]):
            if label != args.label or float(score) < args.score:
                continue
            detections.append(
                {
                    "frame_id": frame_id,
                    "label": label,
                    "score": float(score),
                    "box_lidar": box,
                }
            )

        frame_time = stamp if stamp is not None else float(frame_id)
        matches, assigned_tracks, assigned_dets = match_tracks(
            tracks,
            detections,
            args.dist_thresh,
            frame_id,
            frame_time,
            args.use_motion,
            args.motion_max_gap,
        )

        # Update matched tracks
        for ti, di in matches:
            det = detections[di]
            trk = tracks[ti]
            det_center = box_center_xy(det["box_lidar"])
            if trk.last_stamp is not None:
                dt = frame_time - trk.last_stamp
                if dt > 0:
                    trk.vx = (det_center[0] - trk.last_center[0]) / dt
                    trk.vy = (det_center[1] - trk.last_center[1]) / dt
            trk.last_box = det["box_lidar"]
            trk.last_center = det_center
            trk.last_frame = frame_id
            trk.last_stamp = frame_time
            trk.hits += 1
            trk.missed = 0
            det["track_id"] = trk.track_id

        # New tracks for unmatched detections
        for di, det in enumerate(detections):
            if di in assigned_dets:
                continue
            det["track_id"] = next_track_id
            tracks.append(
                Track(
                    track_id=next_track_id,
                    last_box=det["box_lidar"],
                    last_frame=frame_id,
                    last_center=box_center_xy(det["box_lidar"]),
                    last_stamp=frame_time,
                    hits=1,
                    missed=0,
                )
            )
            next_track_id += 1

        # Age unmatched tracks
        for ti, trk in enumerate(tracks):
            if ti in assigned_tracks:
                continue
            missed = frame_id - trk.last_frame
            trk.missed = max(trk.missed, missed)

        tracks = [t for t in tracks if t.missed <= args.max_age]

        for det in detections:
            det["stamp"] = stamp
            det["interpolated"] = False
            all_dets.append(det)

    if args.interpolate_max_gap > 0:
        by_track = {}
        for det in all_dets:
            by_track.setdefault(det["track_id"], []).append(det)

        for track_id, dets in by_track.items():
            dets.sort(key=lambda d: d["frame_id"])
            for a, b in zip(dets[:-1], dets[1:]):
                gap = b["frame_id"] - a["frame_id"]
                if gap <= 1 or gap - 1 > args.interpolate_max_gap:
                    continue
                a_time = a.get("stamp")
                b_time = b.get("stamp")
                if a_time is None:
                    a_time = a["frame_id"]
                if b_time is None:
                    b_time = b["frame_id"]
                if b_time == a_time:
                    continue
                for f_id in range(a["frame_id"] + 1, b["frame_id"]):
                    t = frame_times.get(f_id, f_id)
                    alpha = (t - a_time) / float(b_time - a_time)
                    interp_box = [
                        a_v + (b_v - a_v) * alpha
                        for a_v, b_v in zip(a["box_lidar"], b["box_lidar"])
                    ]
                    stamp = frame_times.get(f_id)
                    all_dets.append(
                        {
                            "frame_id": f_id,
                            "stamp": stamp,
                            "track_id": track_id,
                            "label": a["label"],
                            "score": min(a["score"], b["score"]),
                            "box_lidar": interp_box,
                            "interpolated": True,
                        }
                    )

    all_dets.sort(key=lambda d: (d["frame_id"], d["track_id"]))

    with open(out_jsonl, "w") as f_out, open(out_csv, "w", newline="") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(
            [
                "frame_id",
                "stamp",
                "track_id",
                "label",
                "score",
                "x",
                "y",
                "z",
                "dx",
                "dy",
                "dz",
                "yaw",
                "interpolated",
            ]
        )
        for det in all_dets:
            out_rec = {
                "frame_id": det["frame_id"],
                "stamp": det.get("stamp"),
                "track_id": det["track_id"],
                "label": det["label"],
                "score": det["score"],
                "box_lidar": det["box_lidar"],
                "interpolated": det.get("interpolated", False),
            }
            f_out.write(json.dumps(out_rec) + "\n")
            writer.writerow(
                [
                    det["frame_id"],
                    f"{det['stamp']:.6f}" if det.get("stamp") is not None else "",
                    det["track_id"],
                    det["label"],
                    f"{det['score']:.4f}",
                ]
                + det["box_lidar"]
                + [1 if det.get("interpolated") else 0]
            )

    print(f"Wrote {out_jsonl}")
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()
