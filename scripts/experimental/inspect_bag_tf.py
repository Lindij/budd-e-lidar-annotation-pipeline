#!/usr/bin/env python3
import argparse
from collections import Counter
from pathlib import Path

import rosbag


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect TF availability and point cloud frames in a ROS bag")
    parser.add_argument("--bag", required=True, help="Path to ROS bag")
    parser.add_argument("--lidar-topic", default="/rslidar_points", help="PointCloud2 topic to inspect")
    parser.add_argument("--max-tf", type=int, default=200, help="Max TF messages to scan")
    args = parser.parse_args()

    bag_path = Path(args.bag)
    if not bag_path.exists():
        raise SystemExit(f"Bag not found: {bag_path}")

    topics = set()
    tf_frames = Counter()
    tf_static_frames = Counter()
    lidar_frame = None

    with rosbag.Bag(str(bag_path), "r") as bag:
        for topic, _, _ in bag.read_messages():
            topics.add(topic)

        for _, msg, _ in bag.read_messages(topics=[args.lidar_topic]):
            lidar_frame = msg.header.frame_id
            break

        tf_count = 0
        for _, msg, _ in bag.read_messages(topics=["/tf"]):
            for tr in msg.transforms:
                tf_frames[(tr.header.frame_id, tr.child_frame_id)] += 1
            tf_count += 1
            if tf_count >= args.max_tf:
                break

        tf_static_count = 0
        for _, msg, _ in bag.read_messages(topics=["/tf_static"]):
            for tr in msg.transforms:
                tf_static_frames[(tr.header.frame_id, tr.child_frame_id)] += 1
            tf_static_count += 1
            if tf_static_count >= args.max_tf:
                break

    print(f"Bag: {bag_path}")
    print(f"Has /tf: {'/tf' in topics}")
    print(f"Has /tf_static: {'/tf_static' in topics}")
    print(f"PointCloud topic: {args.lidar_topic}")
    print(f"PointCloud frame_id: {lidar_frame}")

    if tf_frames:
        print("Sample /tf frames (parent -> child):")
        for (parent, child), count in tf_frames.most_common(10):
            print(f"  {parent} -> {child} ({count})")
    if tf_static_frames:
        print("Sample /tf_static frames (parent -> child):")
        for (parent, child), count in tf_static_frames.most_common(10):
            print(f"  {parent} -> {child} ({count})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
