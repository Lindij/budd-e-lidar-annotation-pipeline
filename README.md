# BUDD-e LiDAR Pedestrian Annotation Pipeline

LiDAR-only pipeline to extract point clouds from ROS1 bag files, run pretrained 3D detection, and upload pedestrian prelabels for review in Segments.ai. The output target is 3D pedestrian cuboids for indoor hospital data.

## Current Status
- ROS bag ingestion working (topic: `/rslidar_points`).
- OpenPCDet installed and CUDA-enabled.
- Inference tested with **PointRCNN-IoU (KITTI pretrained)** and **PointPillars**.
- Prelabels uploaded to Segments.ai (pointcloud cuboid sequence).
- Default prelabeling uses simple interpolation (no motion/static filtering).

## Repository Layout
```
data/
  raw/rosbags/                        # ROS1 bag files (not tracked)
  interim/<bag_id>/                   # Extracted .bin frames + frames.csv
  interim/<bag_id>_pcd/               # PCD sequence for Segments.ai
  processed/<bag_id>/<model>/         # Model outputs + tracks
configs/
  pcdet/                              # Custom OpenPCDet configs
  upload_tracks/                      # Segments.ai upload presets
docs/
external/openpcdet/
reports/report.tex
src/
  ingest/                             # Bag → point clouds
  inference/                          # OpenPCDet inference
  export/                             # PCD + Segments.ai upload
  tools/                              # Tracking, filtering, pipeline entry points
scripts/
  run_pipeline.sh                     # Main orchestration (single entrypoint)
  upload_tracks.sh                    # Upload with split support
  manage_datasets.sh                  # List/create datasets
  transform_bins_tf.py                # Map-frame bin transform (optional)
  transform_labels_tf.py              # Map-frame label transform (optional)
  experimental/                       # Ad hoc utilities (unsupported)
```

## Requirements
- ROS Noetic (WSL or Linux) for bag extraction
- CUDA-capable GPU (WSL OK)
- Python 3.8 venv
- OpenPCDet (in `external/openpcdet`)
- Segments.ai account + API key (for upload)

## Setup (quick)
```bash
source /opt/ros/noetic/setup.bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```
For multi-machine setup, see `docs/setup_parallel.md`.

### OpenPCDet patch (optional datasets)
OpenPCDet may import optional datasets (e.g., Argo2) that are not installed. Apply this patch to avoid
hard dependency failures:
```bash
scripts/setup_env.sh --apply-openpcdet-patch
```

### Model checkpoints
Download the PointRCNN-IoU KITTI checkpoint:
```bash
scripts/setup_models.sh --pointrcnn-iou
```

## End-to-End Pipeline (CLI)
The single supported entrypoint is `scripts/run_pipeline.sh` (it wraps the Python pipeline and adds
static filtering, tracking, upload, and map-frame transforms).
```bash
source .venv/bin/activate
scripts/run_pipeline.sh \
  --bag data/raw/rosbags/_2023-06-27-16-15-39.bag \
  --topic /rslidar_points \
  --model-config configs/pcdet/pointrcnn_iou_budde.yaml \
  --model-ckpt external/openpcdet/ckpts/pointrcnn_iou_kitti.pth
```

### Notes
- ROS bags are not tracked in git.
- Segments.ai has a frame limit per sequence (1500). Use `scripts/upload_tracks.sh --split-size 1500`.
- Default tracking uses simple interpolation (no motion model, no static filtering).
- Map-frame transforms are optional and controlled by `--map-frame/--no-map-frame`.

### TF-based frame stabilization (optional)
If your bag contains TF (`/tf` and `/tf_static`) from the LiDAR frame to a map frame, you can
transform frames and labels to a fixed coordinate system after inference. Disable with
`--no-map-frame` in `scripts/run_pipeline.sh`.

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
Then run `src/export/bin_to_pcd_sequence.py` on the `_map` directory and upload with the `_map` labels.

## Models Tested
- **PointRCNN-IoU (KITTI pretrained)**  
  Config: `configs/pcdet/pointrcnn_iou_budde.yaml`  
  Checkpoint: `external/openpcdet/ckpts/pointrcnn_iou_kitti.pth`
- **PointPillars (KITTI pretrained)**  
  Config: `external/openpcdet/tools/cfgs/kitti_models/pointpillar.yaml`  
  Checkpoint: `external/openpcdet/ckpts/pointpillar_kitti.pth`

## Model Catalogue
See `docs/model_catalogue.md` for recommended OpenPCDet models to test in this setup.

### Suggested Next Models
- CenterPoint (KITTI pretrained)
- PV-RCNN (KITTI pretrained)
- Indoor-focused models (if available)

## Segments.ai Upload (split samples)
1) Put API key in `.env`:
```
SEGMENTS_API_KEY=YOUR_KEY
```
2) Upload with split size 1500:
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

## Key Outputs
- `data/interim/<bag_id>/` — `.bin` frames and `frames.csv`
- `data/interim/<bag_id>_pcd/` — `.pcd` sequence
- `data/processed/<bag_id>/<model>/predictions_<model>_<bag_id>.jsonl`
- `data/processed/<bag_id>/<model>/ped_tracks_<model>_<bag_id>.jsonl`

## Reports
- `reports/report.tex`
