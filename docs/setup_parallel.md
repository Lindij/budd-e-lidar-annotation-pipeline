# Parallel System Setup (Detailed)

This guide recreates the project environment on a second machine so multiple rosbags can be processed in parallel. Rosbags are not tracked in git; copy them separately.

## 1) Clone and basic tools
```bash
git clone <repo_url> budd-e
cd budd-e
```

## 2) ROS Noetic (WSL/Linux)
Make sure ROS Noetic is installed and available:
```bash
source /opt/ros/noetic/setup.bash
```

## 3) Python venv + dependencies
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
```
Install project Python requirements (if you maintain a requirements file, install it here).

## 4) OpenPCDet
OpenPCDet should exist in `external/openpcdet`. Follow the OpenPCDet install guide for your system and CUDA version. You need:
- CUDA toolkit matching your GPU
- `spconv` and OpenPCDet compiled

Verify:
```bash
source .venv/bin/activate
python -c "import pcdet; print(pcdet.__file__)"
```

Apply the optional datasets patch to avoid missing dependency errors:
```bash
scripts/setup_env.sh --apply-openpcdet-patch
```

Download the default model checkpoint:
```bash
scripts/setup_models.sh --pointrcnn-iou
```

## 5) Segments.ai API key
Create `.env` in repo root:
```
SEGMENTS_API_KEY=YOUR_KEY
```

## 6) Copy rosbags (not tracked in git)
Place bags in:
```
data/raw/rosbags/
```
Example:
```
data/raw/rosbags/_2023-06-27-16-50-08.bag
```

## 7) Run pipeline (extract + infer + PCD)
This produces `.bin` frames, predictions, and `.pcd` sequence.
```bash
source /opt/ros/noetic/setup.bash
source .venv/bin/activate
scripts/run_pipeline.sh \
  --bag data/raw/rosbags/_2023-06-27-16-50-08.bag \
  --topic /rslidar_points \
  --model-config configs/pcdet/pointrcnn_iou_budde.yaml \
  --model-ckpt external/openpcdet/ckpts/pointrcnn_iou_kitti.pth
```

Outputs:
```
data/interim/<bag_id>/
data/interim/<bag_id>_pcd/
data/processed/<bag_id>/<model>/
```

## 7b) Default: TF-based frame stabilization (no re-inference)
If TF is recorded in the bag (`/tf`, `/tf_static`), the pipeline transforms frames and labels to a fixed map frame.
Disable with `--no-map-frame` in `scripts/run_pipeline.sh`.
```bash
source /opt/ros/noetic/setup.bash
python3 scripts/utils/transform_bins_tf.py \
  --bag data/raw/rosbags/_2023-06-27-16-50-08.bag \
  --frames-csv data/interim/<bag_id>/frames.csv \
  --in-dir data/interim/<bag_id> \
  --out-dir data/interim/<bag_id>_map \
  --source-frame rslidar \
  --target-frame map

python3 scripts/utils/transform_labels_tf.py \
  --bag data/raw/rosbags/_2023-06-27-16-50-08.bag \
  --frames-csv data/interim/<bag_id>/frames.csv \
  --pred data/processed/<bag_id>/<model>/ped_tracks_<model>_<bag_id>.jsonl \
  --out data/processed/<bag_id>/<model>/ped_tracks_<model>_map_<bag_id>.jsonl \
  --source-frame rslidar \
  --target-frame map
```
Then run `src/export/bin_to_pcd_sequence.py` on the `_map` directory and upload with the `_map` labels.

## 8) Simple interpolation (no motion/static)
```bash
source .venv/bin/activate
./.venv/bin/python src/tools/tracking/track_pedestrians.py \
  --pred data/processed/<bag_id>/<model>/predictions_<model>_<bag_id>.jsonl \
  --frames data/interim/<bag_id>/frames.csv \
  --label Pedestrian \
  --score 0.3 \
  --dist-thresh 0.5 \
  --max-age 30 \
  --interpolate-max-gap 30 \
  --out-jsonl data/processed/<bag_id>/<model>/ped_tracks_<model>_interp_nomotion_<bag_id>.jsonl \
  --out-csv data/processed/<bag_id>/<model>/ped_tracks_<model>_interp_nomotion_<bag_id>.csv
```

## 9) Upload to Segments.ai (split size 1500)
```bash
source .venv/bin/activate
scripts/upload_tracks.sh \
  --config configs/upload_tracks/default.yaml \
  --bag-id <bag_id> \
  --model-name <model_name> \
  --split-size 1500 \
  --dataset Mahi_j/budd-e \
  --pcd-dir data/interim/<bag_id>_pcd \
  --frames-csv data/interim/<bag_id>/frames.csv \
  --pred data/processed/<bag_id>/<model>/ped_tracks_<model>_interp_nomotion_<bag_id>.jsonl \
  --sample-name <bag_id>_<model>
```

## 10) Common issues
- `ModuleNotFoundError: rosbag`: ensure `source /opt/ros/noetic/setup.bash` is active when extracting.
- Slow inference: run in chunks with `src/inference/pcdet_infer_dir.py --start-index`.
- Segments.ai limit: keep split size at 1500 frames.
