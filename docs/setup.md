# Setup and Run Guide

This document consolidates setup and execution instructions for the BUDD-e LiDAR pipeline.

## 1) Environment
- Linux/WSL with GPU
- ROS Noetic (only for bag extraction)
- Python 3.8 venv
- OpenPCDet under `external/openpcdet`

Quick setup:
```bash
source /opt/ros/noetic/setup.bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```

If OpenPCDet optional dataset imports fail, apply the patch:
```bash
scripts/setup_env.sh --apply-openpcdet-patch
```

## 2) Input Data
- Bags live in `data/raw/rosbags/`
- LiDAR topic: `/rslidar_points`
- Inventory: `docs/rosbag_inventory.txt`

## 3) End-to-End Pipeline (recommended)
Use the main entrypoint:
```bash
source .venv/bin/activate
scripts/run_pipeline.sh \
  --bag data/raw/rosbags/_2023-06-27-16-15-39.bag \
  --topic /rslidar_points \
  --model-config configs/pcdet/pointrcnn_iou_budde.yaml \
  --model-ckpt external/openpcdet/ckpts/pointrcnn_iou_kitti.pth
```

## 4) Optional: Map-frame stabilization (TF)
If your bag contains `/tf` and `/tf_static`, you can transform frames and labels to a fixed map frame.
Disable with `--no-map-frame` in `scripts/run_pipeline.sh`.

Manual transforms:
```bash
source /opt/ros/noetic/setup.bash
python3 scripts/transform_bins_tf.py \
  --bag data/raw/rosbags/_2023-06-27-16-50-08.bag \
  --frames-csv data/interim/2023-06-27-16-50-08/frames.csv \
  --in-dir data/interim/2023-06-27-16-50-08 \
  --out-dir data/interim/2023-06-27-16-50-08_map \
  --source-frame rslidar \
  --target-frame map

python3 scripts/transform_labels_tf.py \
  --bag data/raw/rosbags/_2023-06-27-16-50-08.bag \
  --frames-csv data/interim/2023-06-27-16-50-08/frames.csv \
  --pred data/processed/2023-06-27-16-50-08/pointrcnn_iou/ped_tracks_pointrcnn_iou_2023-06-27-16-50-08.jsonl \
  --out data/processed/2023-06-27-16-50-08/pointrcnn_iou/ped_tracks_pointrcnn_iou_map_2023-06-27-16-50-08.jsonl \
  --source-frame rslidar \
  --target-frame map
```

## 5) Upload to Segments.ai
Use `scripts/upload_tracks.sh` with a split size (recommended 1500):
```bash
source .venv/bin/activate
scripts/upload_tracks.sh \
  --config configs/upload_tracks/default.yaml \
  --bag-id 2023-06-27-16-15-39 \
  --model-name pointrcnn_iou \
  --split-size 1500 \
  --dataset Mahi_j/budd-e \
  --pcd-dir data/interim/2023-06-27-16-15-39_map_pcd \
  --frames-csv data/interim/2023-06-27-16-15-39_map/frames.csv \
  --pred data/processed/2023-06-27-16-15-39/pointrcnn_iou/ped_tracks_pointrcnn_iou_map_2023-06-27-16-15-39.jsonl \
  --sample-name 2023-06-27-16-15-39_pointrcnn_iou_map
```

## 6) Notes
- ROS bags are not stored in git; place them under `data/raw/rosbags/`.
- Use `docs/rosbag_inventory.txt` to verify expected bag names.
