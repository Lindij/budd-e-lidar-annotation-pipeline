# Colab Instructions: OpenPCDet Inference + Tracking + Upload

These instructions show how to run the BUDD-e pipeline in Google Colab using Google Drive for storage. The fastest setup is to copy data from Drive to Colab's local `/content` during runtime, run inference there, then copy outputs back to Drive.

## 0) Prerequisites

- A Google account with Google Drive.
- A Colab notebook with GPU runtime enabled.
- Your dataset files in Drive:
  - `data/interim/pcdet_demo/` with `.bin` frames and `frames.csv`
  - `external/openpcdet/ckpts/pointrcnn_iou_kitti.pth` (or another model)
- This repo available in Drive or GitHub.

## 1) Start a Colab notebook with GPU

1. Open a new Colab notebook.
2. Runtime → Change runtime type → GPU.
3. (Optional) Check GPU:
   ```bash
   !nvidia-smi
   ```

## 2) Mount Google Drive

```python
from google.colab import drive
drive.mount('/content/drive')
```

Assume your repo is in Drive at:
```
/content/drive/MyDrive/BUDD-e database
```

Adjust paths below if yours is different.

## 3) Copy data to local SSD (recommended)

This is much faster than running on Drive directly.

```bash
!mkdir -p /content/budd-e
!rsync -a "/content/drive/MyDrive/BUDD-e database/data/interim/pcdet_demo/" /content/budd-e/pcdet_demo/
!cp "/content/drive/MyDrive/BUDD-e database/data/interim/pcdet_demo/frames.csv" /content/budd-e/frames.csv
```

If you also want to run the static filter:
```bash
!mkdir -p /content/budd-e/pcdet_demo_moving
```

## 4) Clone repo to Colab (or copy from Drive)

Option A: clone from GitHub (if repo is public)
```bash
!git clone https://github.com/<ORG>/<REPO>.git /content/budd-e/repo
```

Option B: copy from Drive
```bash
!rsync -a "/content/drive/MyDrive/BUDD-e database/" /content/budd-e/repo/
```

## 5) Install dependencies

Colab uses Python 3.10+. OpenPCDet may require specific versions.
Use the repo’s OpenPCDet instructions as reference. Example:

```bash
%cd /content/budd-e/repo/external/openpcdet

# Install requirements
!pip install -r requirements.txt

# Install spconv and other dependencies (version-sensitive)
# If this fails, follow OpenPCDet docs for Colab or build from source.

# Build OpenPCDet
!python setup.py develop
```

If you see CUDA errors, restart runtime and retry.

## 6) Run inference

Example using PointRCNN-IoU:

```bash
%cd /content/budd-e/repo

!python src/inference/pcdet_infer_dir.py \
  --cfg-file configs/pcdet/pointrcnn_iou_budde.yaml \
  --ckpt external/openpcdet/ckpts/pointrcnn_iou_kitti.pth \
  --data-path /content/budd-e/pcdet_demo \
  --ext .bin \
  --out /content/budd-e/predictions.jsonl \
  --log-interval 50
```

## 7) (Optional) Static-map filtering + inference

Static filtering (builds a static voxel map, removes static points):
```bash
!python src/tools/filtering/filter_static_points.py \
  --in-dir /content/budd-e/pcdet_demo \
  --out-dir /content/budd-e/pcdet_demo_moving \
  --voxel-size 0.2 \
  --static-min-frames 50 \
  --static-min-ratio 0.6 \
  --build-max-frames 0 \
  --build-stride 1 \
  --write-static-npz /content/budd-e/static_map.npz
```

Then run inference on filtered frames:
```bash
!python src/inference/pcdet_infer_dir.py \
  --cfg-file configs/pcdet/pointrcnn_iou_budde.yaml \
  --ckpt external/openpcdet/ckpts/pointrcnn_iou_kitti.pth \
  --data-path /content/budd-e/pcdet_demo_moving \
  --ext .bin \
  --out /content/budd-e/predictions_moving.jsonl \
  --log-interval 50
```

## 8) Run tracking + interpolation

```bash
!python src/tools/tracking/track_pedestrians.py \
  --pred /content/budd-e/predictions.jsonl \
  --frames /content/budd-e/frames.csv \
  --label Pedestrian \
  --score 0.3 \
  --dist-thresh 0.5 \
  --max-age 20 \
  --use-motion \
  --motion-max-gap 20 \
  --interpolate-max-gap 20 \
  --out-jsonl /content/budd-e/ped_tracks_interp.jsonl \
  --out-csv /content/budd-e/ped_tracks_interp.csv
```

If using the static-filtered predictions:
```bash
!python src/tools/tracking/track_pedestrians.py \
  --pred /content/budd-e/predictions_moving.jsonl \
  --frames /content/budd-e/frames.csv \
  --label Pedestrian \
  --score 0.3 \
  --dist-thresh 0.5 \
  --max-age 20 \
  --use-motion \
  --motion-max-gap 20 \
  --interpolate-max-gap 20 \
  --out-jsonl /content/budd-e/ped_tracks_interp_static.jsonl \
  --out-csv /content/budd-e/ped_tracks_interp_static.csv
```

## 9) Copy outputs back to Drive

```bash
!mkdir -p "/content/drive/MyDrive/BUDD-e database/data/processed/pcdet_demo/pointrcnn_iou"
!cp /content/budd-e/predictions.jsonl "/content/drive/MyDrive/BUDD-e database/data/processed/pcdet_demo/pointrcnn_iou/predictions_pointrcnn_iou_pcdet_demo.jsonl"
!cp /content/budd-e/ped_tracks_interp.jsonl "/content/drive/MyDrive/BUDD-e database/data/processed/pcdet_demo/pointrcnn_iou/ped_tracks_pointrcnn_iou_pcdet_demo.jsonl"
!cp /content/budd-e/ped_tracks_interp.csv "/content/drive/MyDrive/BUDD-e database/data/processed/pcdet_demo/pointrcnn_iou/ped_tracks_pointrcnn_iou_pcdet_demo.csv"
```

For static filtered output:
```bash
!cp /content/budd-e/predictions_moving.jsonl "/content/drive/MyDrive/BUDD-e database/data/processed/pcdet_demo/pointrcnn_iou/predictions_moving_pointrcnn_iou_pcdet_demo.jsonl"
!cp /content/budd-e/ped_tracks_interp_static.jsonl "/content/drive/MyDrive/BUDD-e database/data/processed/pcdet_demo/pointrcnn_iou/ped_tracks_interp_static_pointrcnn_iou_pcdet_demo.jsonl"
!cp /content/budd-e/ped_tracks_interp_static.csv "/content/drive/MyDrive/BUDD-e database/data/processed/pcdet_demo/pointrcnn_iou/ped_tracks_interp_static_pointrcnn_iou_pcdet_demo.csv"
!cp /content/budd-e/static_map.npz "/content/drive/MyDrive/BUDD-e database/data/interim/"
```

## 10) Upload to Segments.ai (optional)

Set the API key in the environment:
```bash
import os
os.environ["SEGMENTS_API_KEY"] = "YOUR_KEY_HERE"
```

Then run:
```bash
!python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointrcnn_iou_motion_static \
  --pcd-dir "/content/drive/MyDrive/BUDD-e database/data/interim/pcdet_demo_pcd" \
  --frames-csv "/content/drive/MyDrive/BUDD-e database/data/interim/pcdet_demo/frames.csv" \
  --pred /content/budd-e/ped_tracks_interp_static.jsonl \
  --sample-name budd-e_pointrcnn_iou_motion_static_0000_1499 \
  --labelset tracks \
  --max-frames 1500 \
  --start-frame 0 \
  --overwrite-labels \
  --allow-empty
```

Repeat for the second split:
```bash
!python src/export/segments_upload_sequence.py \
  --dataset Mahi_j/budd-e_pointrcnn_iou_motion_static \
  --pcd-dir "/content/drive/MyDrive/BUDD-e database/data/interim/pcdet_demo_pcd" \
  --frames-csv "/content/drive/MyDrive/BUDD-e database/data/interim/pcdet_demo/frames.csv" \
  --pred /content/budd-e/ped_tracks_interp_static.jsonl \
  --sample-name budd-e_pointrcnn_iou_motion_static_1500_2559 \
  --labelset tracks \
  --max-frames 1060 \
  --start-frame 1500 \
  --overwrite-labels \
  --allow-empty
```

## 11) Troubleshooting

- If inference logs stop after model load, increase runtime, ensure GPU is active, and retry.
- If Google Drive I/O is slow, copy data to `/content` before running inference.
- If OpenPCDet build fails, restart runtime and re-run the install steps.
