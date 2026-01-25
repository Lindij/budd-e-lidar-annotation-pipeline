#!/usr/bin/env python3
import argparse
import csv
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import rosbag


def quaternion_matrix(q):
    x, y, z, w = q
    n = x * x + y * y + z * z + w * w
    if n < 1e-12:
        return np.eye(4)
    s = 2.0 / n
    xs, ys, zs = x * s, y * s, z * s
    wx, wy, wz = w * xs, w * ys, w * zs
    xx, xy, xz = x * xs, x * ys, x * zs
    yy, yz, zz = y * ys, y * zs, z * zs
    mat = np.array(
        [
            [1.0 - (yy + zz), xy - wz, xz + wy, 0.0],
            [xy + wz, 1.0 - (xx + zz), yz - wx, 0.0],
            [xz - wy, yz + wx, 1.0 - (xx + yy), 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    return mat


def build_transform_matrix(transform):
    q = transform.rotation
    t = transform.translation
    mat = quaternion_matrix([q.x, q.y, q.z, q.w])
    mat[:3, 3] = [t.x, t.y, t.z]
    return mat


class TFStore:
    def __init__(self):
        self.dynamic: Dict[Tuple[str, str], List[Tuple[float, np.ndarray]]] = defaultdict(list)
        self.static: Dict[Tuple[str, str], np.ndarray] = {}

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
            return np.eye(4)

        edges = set(list(self.dynamic.keys()) + list(self.static.keys()))
        neighbors = defaultdict(list)
        for parent, child in edges:
            neighbors[parent].append(child)
            neighbors[child].append(parent)

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
    parser = argparse.ArgumentParser(description="Transform .bin frames into a target TF frame")
    parser.add_argument("--bag", required=True, help="Path to ROS bag")
    parser.add_argument("--frames-csv", required=True, help="frames.csv with timestamps")
    parser.add_argument("--in-dir", required=True, help="Input .bin directory")
    parser.add_argument("--out-dir", required=True, help="Output .bin directory")
    parser.add_argument("--source-frame", required=True, help="Source frame (e.g., rslidar)")
    parser.add_argument("--target-frame", default="map", help="Target frame")
    parser.add_argument("--tf-topic", default="/tf", help="TF topic")
    parser.add_argument("--tf-static-topic", default="/tf_static", help="Static TF topic")
    parser.add_argument("--skip-missing", action="store_true", help="Skip frames with missing TF")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    frame_times = load_frame_times(Path(args.frames_csv))

    store = TFStore()
    with rosbag.Bag(str(args.bag), "r") as bag:
        for topic, msg, _ in bag.read_messages(topics=[args.tf_topic, args.tf_static_topic]):
            is_static = topic == args.tf_static_topic
            for transform in msg.transforms:
                store.add_transform(transform, is_static=is_static)
    store.finalize()

    missing = 0
    total = 0
    for bin_path in sorted(in_dir.glob("*.bin")):
        frame_id = int(bin_path.stem)
        stamp = frame_times.get(frame_id)
        if stamp is None:
            if args.skip_missing:
                continue
            raise SystemExit(f"Missing timestamp for frame {frame_id}")

        mat = store.lookup(args.target_frame, args.source_frame, stamp)
        if mat is None:
            missing += 1
            if args.skip_missing:
                continue
            raise SystemExit(f"Missing TF for frame {frame_id} at {stamp}")

        points = np.fromfile(bin_path, dtype=np.float32).reshape(-1, 4)
        if points.size:
            xyz = points[:, :3]
            xyz = (xyz @ mat[:3, :3].T) + mat[:3, 3]
            points[:, :3] = xyz
        points.astype(np.float32).tofile(out_dir / bin_path.name)
        total += 1
        if total % 100 == 0:
            print(f"Transformed {total} frames")

    print(f"Done. Frames={total}, missing_tf={missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
