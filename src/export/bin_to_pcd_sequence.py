#!/usr/bin/env python3
import argparse
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser(description="Convert OpenPCDet .bin frames to PCD sequence")
    parser.add_argument("--in-dir", required=True, help="Input directory of .bin frames")
    parser.add_argument("--out-dir", required=True, help="Output directory for .pcd frames")
    parser.add_argument("--max-frames", type=int, default=0, help="Max frames to convert (0 = all)")
    args = parser.parse_args()

    try:
        import open3d as o3d
    except Exception as exc:
        raise SystemExit("open3d is not installed. Run: python -m pip install open3d") from exc

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.glob("*.bin"))
    if args.max_frames:
        files = files[:args.max_frames]

    for i, path in enumerate(files):
        points = np.fromfile(path, dtype=np.float32).reshape(-1, 4)
        pc = o3d.geometry.PointCloud()
        pc.points = o3d.utility.Vector3dVector(points[:, :3])
        if points.shape[1] >= 4:
            # Store intensity as grayscale in colors for compatibility.
            intensity = points[:, 3].astype(np.float64)
            if intensity.size > 0:
                max_val = float(intensity.max())
                if max_val > 1.0:
                    intensity = intensity / max_val
            colors = np.repeat(intensity.reshape(-1, 1), 3, axis=1)
            pc.colors = o3d.utility.Vector3dVector(colors)

        out_path = out_dir / (path.stem + ".pcd")
        o3d.io.write_point_cloud(str(out_path), pc, write_ascii=False, compressed=False)
        if (i + 1) % 100 == 0 or i == len(files) - 1:
            print(f"Converted {i + 1}/{len(files)}")


if __name__ == "__main__":
    main()
