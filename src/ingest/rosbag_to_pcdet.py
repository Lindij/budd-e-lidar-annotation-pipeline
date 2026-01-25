#!/usr/bin/env python3
import argparse
import csv
from pathlib import Path

import numpy as np
import rosbag
from sensor_msgs import point_cloud2 as pc2


def normalize_intensity(intensity):
    if intensity.size == 0:
        return intensity
    max_val = float(np.max(intensity))
    if max_val > 1.0:
        return intensity / max_val
    return intensity


def read_points(msg, use_intensity):
    fields = ["x", "y", "z"]
    if use_intensity:
        fields.append("intensity")
    pts = np.array(list(pc2.read_points(msg, field_names=fields, skip_nans=True)))
    if pts.size == 0:
        return np.empty((0, 4), dtype=np.float32)
    if use_intensity:
        intensity = normalize_intensity(pts[:, 3].astype(np.float32))
        pts = np.column_stack((pts[:, 0], pts[:, 1], pts[:, 2], intensity))
    else:
        zeros = np.zeros((pts.shape[0], 1), dtype=np.float32)
        pts = np.column_stack((pts[:, 0], pts[:, 1], pts[:, 2], zeros))
    return pts.astype(np.float32)


def build_transform_matrix(transform):
    from tf.transformations import quaternion_matrix

    q = transform.rotation
    t = transform.translation
    mat = quaternion_matrix([q.x, q.y, q.z, q.w])
    mat[:3, 3] = [t.x, t.y, t.z]
    return mat


def transform_points(points, mat):
    if points.size == 0:
        return points
    xyz = points[:, :3]
    xyz = (xyz @ mat[:3, :3].T) + mat[:3, 3]
    points[:, :3] = xyz
    return points


def main():
    parser = argparse.ArgumentParser(description="Extract PointCloud2 to OpenPCDet .bin files")
    parser.add_argument("--bag", required=True, help="Path to ROS bag")
    parser.add_argument("--topic", default="/rslidar_points", help="PointCloud2 topic")
    parser.add_argument("--out-dir", default="data/interim/pcdet_demo", help="Output directory")
    parser.add_argument("--max-frames", type=int, default=0, help="Max frames to export (0 = all)")
    parser.add_argument("--stride", type=int, default=1, help="Keep every Nth frame")
    parser.add_argument("--lidar-height", type=float, default=None, help="LiDAR height (m) above ground")
    parser.add_argument("--model-height", type=float, default=1.6, help="Model expected height (m)")
    parser.add_argument("--no-intensity", action="store_true", help="Ignore intensity channel")
    parser.add_argument("--use-tf", action="store_true", help="Transform points to target frame using /tf")
    parser.add_argument("--tf-topic", default="/tf", help="TF topic (default: /tf)")
    parser.add_argument("--tf-static-topic", default="/tf_static", help="Static TF topic")
    parser.add_argument("--target-frame", default="map", help="Target frame (e.g. map)")
    parser.add_argument("--source-frame", default="", help="Override source frame (default: msg.header.frame_id)")
    parser.add_argument("--tf-timeout", type=float, default=0.1, help="TF lookup timeout (s)")
    args = parser.parse_args()

    bag_path = Path(args.bag)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    z_shift = 0.0
    if args.lidar_height is not None:
        z_shift = args.lidar_height - args.model_height

    meta_path = out_dir / "frames.csv"
    with rosbag.Bag(str(bag_path), "r") as bag, open(meta_path, "w", newline="") as meta:
        writer = csv.writer(meta)
        writer.writerow(
            ["frame_idx", "stamp", "num_points", "bag", "topic", "z_shift", "target_frame", "source_frame"]
        )

        tf_buffer = None
        if args.use_tf:
            import rospy
            import tf2_ros

            bag_start = bag.get_start_time()
            bag_end = bag.get_end_time()
            cache = max(1.0, bag_end - bag_start + 10.0)
            tf_buffer = tf2_ros.Buffer(cache_time=rospy.Duration.from_sec(cache))

            for _, msg, _ in bag.read_messages(topics=[args.tf_topic, args.tf_static_topic]):
                is_static = msg._connection_header.get("topic") == args.tf_static_topic
                for transform in msg.transforms:
                    if is_static:
                        tf_buffer.set_transform_static(transform, "bag")
                    else:
                        tf_buffer.set_transform(transform, "bag")

        frame_idx = 0
        kept = 0
        for _, msg, _ in bag.read_messages(topics=[args.topic]):
            if frame_idx % args.stride != 0:
                frame_idx += 1
                continue

            pts = read_points(msg, use_intensity=not args.no_intensity)
            if pts.size == 0:
                frame_idx += 1
                continue

            source_frame = args.source_frame or msg.header.frame_id
            if args.use_tf and tf_buffer is not None:
                import rospy

                try:
                    transform = tf_buffer.lookup_transform(
                        args.target_frame,
                        source_frame,
                        msg.header.stamp,
                        rospy.Duration.from_sec(args.tf_timeout),
                    )
                except Exception:
                    frame_idx += 1
                    continue
                mat = build_transform_matrix(transform.transform)
                pts = transform_points(pts, mat)

            if z_shift != 0.0:
                pts[:, 2] += z_shift

            out_name = f"{kept:06d}.bin"
            out_path = out_dir / out_name
            pts.tofile(str(out_path))

            stamp = msg.header.stamp.to_sec()
            writer.writerow(
                [
                    kept,
                    f"{stamp:.6f}",
                    pts.shape[0],
                    bag_path.name,
                    args.topic,
                    z_shift,
                    args.target_frame if args.use_tf else "",
                    source_frame,
                ]
            )

            kept += 1
            frame_idx += 1
            if args.max_frames and kept >= args.max_frames:
                break

    print(f"Wrote {kept} frames to {out_dir}")
    print(f"Metadata: {meta_path}")


if __name__ == "__main__":
    main()
