#!/usr/bin/env python3
import argparse
from pathlib import Path

import numpy as np


def load_bin(path: Path) -> np.ndarray:
    return np.fromfile(path, dtype=np.float32).reshape(-1, 4)


def coords_to_view(coords: np.ndarray) -> np.ndarray:
    return coords.view(np.dtype((np.void, coords.dtype.itemsize * coords.shape[1]))).reshape(-1)


def voxelize(points: np.ndarray, voxel_size: float) -> np.ndarray:
    return np.floor(points[:, :3] / voxel_size).astype(np.int32)


def build_static_voxels(files, voxel_size, min_frames, min_ratio):
    counts = {}
    total = 0

    for path in files:
        points = load_bin(path)
        if points.size == 0:
            total += 1
            continue
        coords = voxelize(points, voxel_size)
        uniq = np.unique(coords, axis=0)
        for c in uniq:
            key = (int(c[0]), int(c[1]), int(c[2]))
            counts[key] = counts.get(key, 0) + 1
        total += 1

    if total == 0:
        return np.zeros((0, 3), dtype=np.int32), total

    ratio_thresh = int(np.ceil(min_ratio * total)) if min_ratio > 0 else 0
    thresh = max(min_frames, ratio_thresh)

    static_coords = [k for k, v in counts.items() if v >= thresh]
    if not static_coords:
        return np.zeros((0, 3), dtype=np.int32), total
    return np.array(static_coords, dtype=np.int32), total


def main():
    parser = argparse.ArgumentParser(description="Filter static points using voxel persistence")
    parser.add_argument("--in-dir", required=True, help="Input directory of .bin frames")
    parser.add_argument("--out-dir", required=True, help="Output directory for filtered .bin frames")
    parser.add_argument("--voxel-size", type=float, default=0.2, help="Voxel size in meters")
    parser.add_argument(
        "--static-min-frames",
        type=int,
        default=50,
        help="Min frames a voxel must appear to be considered static",
    )
    parser.add_argument(
        "--static-min-ratio",
        type=float,
        default=0.6,
        help="Min ratio of frames a voxel must appear (0 disables)",
    )
    parser.add_argument(
        "--build-max-frames",
        type=int,
        default=0,
        help="Max frames to use when building static map (0 = all)",
    )
    parser.add_argument("--build-stride", type=int, default=1, help="Stride for static map building")
    parser.add_argument("--write-static-npz", default="", help="Optional .npz to save static voxels")
    args = parser.parse_args()

    in_dir = Path(args.in_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(in_dir.glob("*.bin"))
    build_files = files[:: args.build_stride]
    if args.build_max_frames:
        build_files = build_files[: args.build_max_frames]

    static_coords, total_used = build_static_voxels(
        build_files, args.voxel_size, args.static_min_frames, args.static_min_ratio
    )

    if args.write_static_npz:
        np.savez(
            args.write_static_npz,
            static_coords=static_coords,
            voxel_size=args.voxel_size,
            total_frames=total_used,
        )

    if static_coords.size == 0:
        print("No static voxels found; copying frames unchanged.")
        for path in files:
            out_path = out_dir / path.name
            if out_path.exists():
                continue
            data = load_bin(path)
            data.astype(np.float32).tofile(out_path)
        return

    static_view = coords_to_view(static_coords)

    for i, path in enumerate(files):
        points = load_bin(path)
        if points.size == 0:
            out_path = out_dir / path.name
            points.astype(np.float32).tofile(out_path)
            continue

        coords = voxelize(points, args.voxel_size)
        coords_view = coords_to_view(coords)
        is_static = np.isin(coords_view, static_view)
        filtered = points[~is_static]

        out_path = out_dir / path.name
        filtered.astype(np.float32).tofile(out_path)

        if (i + 1) % 100 == 0 or i == len(files) - 1:
            print(f"Filtered {i + 1}/{len(files)} (kept {filtered.shape[0]}/{points.shape[0]})")


if __name__ == "__main__":
    main()
