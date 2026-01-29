#!/usr/bin/env python3
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, Tuple

import math
from bisect import bisect_right
from collections import defaultdict
from typing import Dict, List, Tuple

import rosbag


def quaternion_matrix(q):
    x, y, z, w = q
    n = x * x + y * y + z * z + w * w
    if n < 1e-12:
        return [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ]
    s = 2.0 / n
    xs, ys, zs = x * s, y * s, z * s
    wx, wy, wz = w * xs, w * ys, w * zs
    xx, xy, xz = x * xs, x * ys, x * zs
    yy, yz, zz = y * ys, y * zs, z * zs
    return [
        [1.0 - (yy + zz), xy - wz, xz + wy, 0.0],
        [xy + wz, 1.0 - (xx + zz), yz - wx, 0.0],
        [xz - wy, yz + wx, 1.0 - (xx + yy), 0.0],
        [0.0, 0.0, 0.0, 1.0],
    ]


def build_transform_matrix(transform):
    q = transform.rotation
    t = transform.translation
    mat = quaternion_matrix([q.x, q.y, q.z, q.w])
    mat[0][3], mat[1][3], mat[2][3] = t.x, t.y, t.z
    return mat


def transform_box(box, mat):
    x, y, z, dx, dy, dz, yaw = box
    pos = mat[:3, :3].dot([x, y, z]) + mat[:3, 3]
    heading = mat[:3, :3].dot([math.cos(yaw), math.sin(yaw), 0.0])
    new_yaw = float(math.atan2(heading[1], heading[0]))
    return [float(pos[0]), float(pos[1]), float(pos[2]), dx, dy, dz, new_yaw]


class TFStore:
    def __init__(self):
        self.dynamic: Dict[Tuple[str, str], List[Tuple[float, List[List[float]]]]] = defaultdict(list)
        self.static: Dict[Tuple[str, str], List[List[float]]] = {}

    def add_transform(self, transform, is_static: bool) -> None:
        parent = transform.header.frame_id
        child = transform.child_frame_id
        mat = build_transform_matrix(transform.transform)
        if is_static:
            self.static[(parent, child)] = mat
        else:
            stamp = transform.header.stamp.to_sec()
            self.dynamic[(parent, child)].append((stamp, mat))

    def finalize(self) -> None:
        for key in self.dynamic:
            self.dynamic[key].sort(key=lambda item: item[0])

    def get(self, parent: str, child: str, stamp: float):
        if (parent, child) in self.static:
            return self.static[(parent, child)]
        series = self.dynamic.get((parent, child))
        if not series:
            return None
        stamps = [s for s, _ in series]
        idx = bisect_right(stamps, stamp) - 1
        if idx < 0:
            return series[0][1]
        return series[idx][1]

    def lookup(self, target: str, source: str, stamp: float):
        if target == source:
            return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]

        edges = set(list(self.dynamic.keys()) + list(self.static.keys()))
        neighbors = defaultdict(list)
        for parent, child in edges:
            neighbors[parent].append(child)
            neighbors[child].append(parent)

        import numpy as np
        from collections import deque

        q = deque()
        visited = set()
        q.append((source, np.eye(4)))
        visited.add(source)

        while q:
            frame, mat_source_frame = q.popleft()
            if frame == target:
                return mat_source_frame
            for nbr in neighbors.get(frame, []):
                if nbr in visited:
                    continue
                if frame == nbr:
                    continue
                if (frame, nbr) in edges:
                    t_parent_child = self.get(frame, nbr, stamp)
                    if t_parent_child is None:
                        continue
                    mat_source_nbr = mat_source_frame @ np.linalg.inv(t_parent_child)
                else:
                    t_parent_child = self.get(nbr, frame, stamp)
                    if t_parent_child is None:
                        continue
                    mat_source_nbr = mat_source_frame @ t_parent_child
                visited.add(nbr)
                q.append((nbr, mat_source_nbr))
        return None

def load_frame_times(frames_csv: Path) -> Dict[int, float]:
    times = {}
    with frames_csv.open("r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)
        for row in reader:
            if len(row) < 2:
                continue
            frame_id = int(row[0])
            stamp = float(row[1])
            times[frame_id] = stamp
    return times


def main() -> int:
    parser = argparse.ArgumentParser(description="Transform prediction boxes using TF to a target frame")
    parser.add_argument("--bag", required=True, help="Path to ROS bag")
    parser.add_argument("--frames-csv", required=True, help="frames.csv with timestamps")
    parser.add_argument("--pred", required=True, help="Input predictions/tracks JSONL")
    parser.add_argument("--out", required=True, help="Output JSONL path")
    parser.add_argument("--target-frame", default="map", help="Target frame")
    parser.add_argument("--source-frame", default="", help="Override source frame (default: use TF from bag)")
    parser.add_argument("--tf-topic", default="/tf", help="TF topic")
    parser.add_argument("--tf-static-topic", default="/tf_static", help="Static TF topic")
    parser.add_argument("--tf-timeout", type=float, default=0.1, help="TF lookup timeout (s)")
    parser.add_argument("--skip-missing", action="store_true", help="Skip frames with missing TF")
    args = parser.parse_args()

    frames_csv = Path(args.frames_csv)
    pred_path = Path(args.pred)
    out_path = Path(args.out)

    frame_times = load_frame_times(frames_csv)

    store = TFStore()
    with rosbag.Bag(str(args.bag), "r") as bag:
        for topic, msg, _ in bag.read_messages(topics=[args.tf_topic, args.tf_static_topic]):
            is_static = topic == args.tf_static_topic
            for transform in msg.transforms:
                store.add_transform(transform, is_static=is_static)
    store.finalize()

    missing_tf = 0
    transformed = 0

    def lookup_transform(source_frame: str, stamp: float):
        return store.lookup(args.target_frame, source_frame, stamp)

    with pred_path.open("r", encoding="utf-8") as f_in, out_path.open("w", encoding="utf-8") as f_out:
        for line in f_in:
            if not line.strip():
                continue
            rec = json.loads(line)
            frame_id = int(rec.get("frame_id", -1))
            stamp = rec.get("stamp")
            if stamp is None:
                stamp = frame_times.get(frame_id)
            if stamp is None:
                if args.skip_missing:
                    continue
                f_out.write(json.dumps(rec) + "\n")
                continue

            if not args.source_frame:
                raise SystemExit("--source-frame is required when transforming labels")
            source_frame = args.source_frame

            transform = lookup_transform(source_frame, float(stamp))
            if transform is None:
                missing_tf += 1
                if args.skip_missing:
                    continue
                f_out.write(json.dumps(rec) + "\n")
                continue

            mat = transform

            if "boxes_lidar" in rec:
                rec["boxes_lidar"] = [transform_box(box, mat) for box in rec["boxes_lidar"]]
            else:
                rec["box_lidar"] = transform_box(rec["box_lidar"], mat)
            f_out.write(json.dumps(rec) + "\n")
            transformed += 1

    print(f"Transformed records: {transformed}")
    print(f"Missing TF lookups: {missing_tf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
