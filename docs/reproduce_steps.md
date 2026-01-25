# Reproduction Steps (BUDD-e LiDAR -> 3D boxes -> Segments.ai)

This file captures the exact steps we executed in this repo to go from a ROS bag to 3D bounding boxes and upload them to Segments.ai.
All paths are workspace-relative to `/mnt/d/BUDD-e database`.

## 0) Environment assumptions
- WSL / Linux, GPU present
- Python venv: `.venv`
- CUDA installed and visible to PyTorch
- ROS1 Noetic installed (only needed for bag extraction)

Activate the venv:
```
source .venv/bin/activate
```

## 1) OpenPCDet setup
OpenPCDet is vendored under `external/openpcdet` and was built in-place.

(If you need to rebuild later, follow `external/openpcdet/docs/INSTALL.md`.)

## 2) Input data
- ROS bags live in `data/raw/rosbags/`
- LiDAR topic: `/rslidar_points`

Example bag used:
- `data/raw/rosbags/File_2023-06-27-16-15-39.bag`

## 3) Extract point clouds from bag to OpenPCDet .bin
This step converts PointCloud2 to OpenPCDet .bin files + `frames.csv`.

Command:
```
./.venv/bin/python src/ingest/rosbag_to_pcdet.py \
  --bag data/raw/rosbags/File_2023-06-27-16-15-39.bag \
  --topic /rslidar_points \
  --out-dir data/interim/pcdet_demo
```

Outputs:
- `data/interim/pcdet_demo/000000.bin` ...
- `data/interim/pcdet_demo/frames.csv`

## 4) Convert .bin -> .pcd sequence
Segments.ai needs PCD for pointcloud sequence.

Command:
```
./.venv/bin/python src/export/bin_to_pcd_sequence.py \
  --in-dir data/interim/pcdet_demo \
  --out-dir data/interim/pcdet_demo_pcd
```

Outputs:
- `data/interim/pcdet_demo_pcd/000000.pcd` ...

## 5) Model 1: PointPillars (KITTI pretrained)
This was the first model used and produced pedestrian-only prelabels.

Config + checkpoint:
- `external/openpcdet/tools/cfgs/kitti_models/pointpillar.yaml`
- `external/openpcdet/ckpts/pointpillar_kitti.pth`

Inference:
```
./.venv/bin/python src/inference/pcdet_infer_dir.py \
  --cfg-file external/openpcdet/tools/cfgs/kitti_models/pointpillar.yaml \
  --ckpt external/openpcdet/ckpts/pointpillar_kitti.pth \
  --data-path data/interim/pcdet_demo \
  --ext .bin \
  --out data/labels/pcdet_demo/predictions.jsonl
```

Filter pedestrians:
```
./.venv/bin/python src/export/export_pedestrians.py \
  --pred data/labels/pcdet_demo/predictions.jsonl \
  --frames data/interim/pcdet_demo/frames.csv \
  --score 0.3 \
  --out-jsonl data/labels/pcdet_demo/pedestrians.jsonl \
  --out-csv data/labels/pcdet_demo/pedestrians.csv \
  --label Pedestrian
```

## 6) Model 2: PointRCNN-IoU (KITTI pretrained)
This model produced better boxes but is slower.

### 6.1 Download checkpoint
Use gdown (already in venv):
```
./.venv/bin/python -m gdown --id 1V0vNZ3lAHpEEt0MlT80eL2f41K2tHm_D \
  -O external/openpcdet/ckpts/pointrcnn_iou_kitti.pth
```

### 6.2 Create a custom config to reduce NUM_POINTS
PointRCNN requires 16384 points by default; our frames have fewer.
We cloned the config and reduced `NUM_POINTS['test']` to 10000.

Created file:
- `external/openpcdet/tools/cfgs/kitti_models/pointrcnn_iou_budde.yaml`

(Contents are identical to `pointrcnn_iou.yaml` except `NUM_POINTS: test=10000`.)

### 6.3 Run inference (can be resumed)
Initial inference:
```
./.venv/bin/python src/inference/pcdet_infer_dir.py \
  --cfg-file external/openpcdet/tools/cfgs/kitti_models/pointrcnn_iou_budde.yaml \
  --ckpt external/openpcdet/ckpts/pointrcnn_iou_kitti.pth \
  --data-path data/interim/pcdet_demo \
  --ext .bin \
  --out data/labels/pcdet_pointrcnn_iou/predictions.jsonl
```

Resume inference from a specific frame index (if needed):
```
./.venv/bin/python src/inference/pcdet_infer_dir.py \
  --cfg-file external/openpcdet/tools/cfgs/kitti_models/pointrcnn_iou_budde.yaml \
  --ckpt external/openpcdet/ckpts/pointrcnn_iou_kitti.pth \
  --data-path data/interim/pcdet_demo \
  --ext .bin \
  --out data/labels/pcdet_pointrcnn_iou/predictions.jsonl \
  --start-index <N>
```

## 7) Segments.ai setup
Create datasets (separate per model so labelsets are clean).

### 7.1 Create datasets
```
./.venv/bin/python tools/segments_create_dataset.py \
  --name budd-e_pointpillar \
  --description "BUDD-e PointPillars prelabels"

./.venv/bin/python tools/segments_create_dataset.py \
  --name budd-e_pointrcnn_iou \
  --description "BUDD-e PointRCNN-IoU prelabels"
```

Datasets created:
- `Mahi_j/budd-e_pointpillar`
- `Mahi_j/budd-e_pointrcnn_iou`

### 7.2 Upload PointPillars samples (pedestrian-only)
We split into 5 samples of 300 frames each.

```
./.venv/bin/python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointpillar \
  --pcd-dir data/interim/pcdet_demo_pcd \
  --frames-csv data/interim/pcdet_demo/frames.csv \
  --pred data/labels/pcdet_demo/pedestrians.jsonl \
  --sample-name budd-e_ped_0000_0299 \
  --labelset prelabels \
  --max-frames 300 \
  --start-frame 0 \
  --overwrite-labels

./.venv/bin/python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointpillar \
  --pcd-dir data/interim/pcdet_demo_pcd \
  --frames-csv data/interim/pcdet_demo/frames.csv \
  --pred data/labels/pcdet_demo/pedestrians.jsonl \
  --sample-name budd-e_ped_0300_0599 \
  --labelset prelabels \
  --max-frames 300 \
  --start-frame 300 \
  --overwrite-labels \
  --allow-empty

./.venv/bin/python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointpillar \
  --pcd-dir data/interim/pcdet_demo_pcd \
  --frames-csv data/interim/pcdet_demo/frames.csv \
  --pred data/labels/pcdet_demo/pedestrians.jsonl \
  --sample-name budd-e_ped_0600_0899 \
  --labelset prelabels \
  --max-frames 300 \
  --start-frame 600 \
  --overwrite-labels

./.venv/bin/python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointpillar \
  --pcd-dir data/interim/pcdet_demo_pcd \
  --frames-csv data/interim/pcdet_demo/frames.csv \
  --pred data/labels/pcdet_demo/pedestrians.jsonl \
  --sample-name budd-e_ped_0900_1199 \
  --labelset prelabels \
  --max-frames 300 \
  --start-frame 900 \
  --overwrite-labels

./.venv/bin/python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointpillar \
  --pcd-dir data/interim/pcdet_demo_pcd \
  --frames-csv data/interim/pcdet_demo/frames.csv \
  --pred data/labels/pcdet_demo/pedestrians.jsonl \
  --sample-name budd-e_ped_1200_1499 \
  --labelset prelabels \
  --max-frames 300 \
  --start-frame 1200 \
  --overwrite-labels
```

### 7.3 Upload PointRCNN-IoU samples (all classes)
We split into 50-frame chunks for usability:

```
./.venv/bin/python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointrcnn_iou \
  --pcd-dir data/interim/pcdet_demo_pcd \
  --frames-csv data/interim/pcdet_demo/frames.csv \
  --pred data/labels/pcdet_pointrcnn_iou/predictions.jsonl \
  --sample-name budd-e_pointrcnn_iou_0000_0049 \
  --labelset prelabels \
  --max-frames 50 \
  --start-frame 0 \
  --overwrite-labels

./.venv/bin/python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointrcnn_iou \
  --pcd-dir data/interim/pcdet_demo_pcd \
  --frames-csv data/interim/pcdet_demo/frames.csv \
  --pred data/labels/pcdet_pointrcnn_iou/predictions.jsonl \
  --sample-name budd-e_pointrcnn_iou_0050_0099 \
  --labelset prelabels \
  --max-frames 50 \
  --start-frame 50 \
  --overwrite-labels

./.venv/bin/python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointrcnn_iou \
  --pcd-dir data/interim/pcdet_demo_pcd \
  --frames-csv data/interim/pcdet_demo/frames.csv \
  --pred data/labels/pcdet_pointrcnn_iou/predictions.jsonl \
  --sample-name budd-e_pointrcnn_iou_0100_0149 \
  --labelset prelabels \
  --max-frames 50 \
  --start-frame 100 \
  --overwrite-labels

./.venv/bin/python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointrcnn_iou \
  --pcd-dir data/interim/pcdet_demo_pcd \
  --frames-csv data/interim/pcdet_demo/frames.csv \
  --pred data/labels/pcdet_pointrcnn_iou/predictions.jsonl \
  --sample-name budd-e_pointrcnn_iou_0150_0199 \
  --labelset prelabels \
  --max-frames 50 \
  --start-frame 150 \
  --overwrite-labels

./.venv/bin/python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointrcnn_iou \
  --pcd-dir data/interim/pcdet_demo_pcd \
  --frames-csv data/interim/pcdet_demo/frames.csv \
  --pred data/labels/pcdet_pointrcnn_iou/predictions.jsonl \
  --sample-name budd-e_pointrcnn_iou_0200_0249 \
  --labelset prelabels \
  --max-frames 50 \
  --start-frame 200 \
  --overwrite-labels

./.venv/bin/python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointrcnn_iou \
  --pcd-dir data/interim/pcdet_demo_pcd \
  --frames-csv data/interim/pcdet_demo/frames.csv \
  --pred data/labels/pcdet_pointrcnn_iou/predictions.jsonl \
  --sample-name budd-e_pointrcnn_iou_0250_0299 \
  --labelset prelabels \
  --max-frames 50 \
  --start-frame 250 \
  --overwrite-labels

./.venv/bin/python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointrcnn_iou \
  --pcd-dir data/interim/pcdet_demo_pcd \
  --frames-csv data/interim/pcdet_demo/frames.csv \
  --pred data/labels/pcdet_pointrcnn_iou/predictions.jsonl \
  --sample-name budd-e_pointrcnn_iou_0300_0323 \
  --labelset prelabels \
  --max-frames 24 \
  --start-frame 300 \
  --overwrite-labels \
  --allow-empty
```

## 8) Notes / changes made to code
- `src/export/segments_upload_sequence.py` now reuses existing samples (if they already exist) instead of failing.
- `src/export/segments_upload_sequence.py` supports `--allow-empty` when no annotations match.

## 9) Quick sanity links (Segments.ai)
Datasets:
- `Mahi_j/budd-e_pointpillar`
- `Mahi_j/budd-e_pointrcnn_iou`

Labelset to view prelabels in each dataset: `prelabels`
