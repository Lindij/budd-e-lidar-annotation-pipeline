#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

bag_id="2023-06-27-16-15-39"
model_name="pointrcnn_iou"

./.venv/bin/python src/tools/tracking/track_pedestrians.py \
  --pred "data/processed/${bag_id}/${model_name}/predictions_pointrcnn_iou_${bag_id}.jsonl" \
  --frames "data/interim/${bag_id}/frames.csv" \
  --label Pedestrian \
  --score 0.3 \
  --dist-thresh 0.5 \
  --max-age 30 \
  --interpolate-max-gap 30 \
  --out-jsonl "data/processed/${bag_id}/${model_name}/ped_tracks_pointrcnn_iou_interp_nomotion_${bag_id}.jsonl" \
  --out-csv "data/processed/${bag_id}/${model_name}/ped_tracks_pointrcnn_iou_interp_nomotion_${bag_id}.csv"
