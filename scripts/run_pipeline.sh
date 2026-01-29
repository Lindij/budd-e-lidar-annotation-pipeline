#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/run_pipeline.sh --bag <path> --model-config <yaml> --model-ckpt <pth> [options]

Options:
  --config <path>              Pipeline config yaml (default: configs/pipeline.yaml)
  --no-config                  Disable config defaults
  --topic <topic>               ROS topic (default: /rslidar_points)
  --track                        Enable tracking + interpolation
  --track-max-age <n>            Max missed frames (default: 30)
  --track-interp <n>             Interpolate up to N frames (default: 30)
  --track-dist <m>               Max XY distance (default: 0.5)
  --track-use-motion             Enable motion model
  --map-frame                    Transform frames/labels to map frame (default: on)
  --no-map-frame                 Disable map-frame transform
  --map-source-frame <frame>     Source frame for TF (default: rslidar)
  --map-target-frame <frame>     Target frame for TF (default: map)
  --map-labels <path>            Override labels to transform (default: predictions or track output)
  --skip-pcd                     Skip .pcd conversion
  --static-filter                Run static filtering before inference
  --static-voxel <m>             Voxel size (default: 0.2)
  --static-min-frames <n>        Min frames for static voxel (default: 50)
  --static-min-ratio <r>         Min ratio for static voxel (default: 0.6)
  --static-build-max <n>         Max frames to build static map (default: 0)
  --static-build-stride <n>      Stride for static map (default: 1)
  --upload                        Upload via Segments.ai
  --segments-dataset <id>        Dataset owner/name
  --segments-sample <name>       Sample name (default: bag_id_model)
  --segments-labelset <name>     Labelset (default: prelabels)
  --segments-max-frames <n>      Max frames to upload (default: 0)
  --segments-start-frame <n>     Start frame (default: 0)
  --segments-stride <n>          Upload stride (default: 1)
EOF
}

bag=""
topic="/rslidar_points"
model_config=""
model_ckpt=""
track=0
track_max_age=30
track_interp=30
track_dist=0.5
track_use_motion=0
map_frame=1
map_source_frame="rslidar"
map_target_frame="map"
map_labels_override=""
skip_pcd=0
static_filter=0
static_voxel=0.2
static_min_frames=50
static_min_ratio=0.6
static_build_max=0
static_build_stride=1
upload=0
segments_dataset=""
segments_sample=""
segments_labelset="prelabels"
segments_max_frames=0
segments_start_frame=0
segments_stride=1
config_path="configs/pipeline.yaml"
config_enabled=1
topic_set=0
model_config_set=0
model_ckpt_set=0
track_set=0
track_max_age_set=0
track_interp_set=0
track_dist_set=0
track_use_motion_set=0
map_frame_set=0
map_source_frame_set=0
map_target_frame_set=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) config_path="$2"; shift 2 ;;
    --no-config) config_enabled=0; shift ;;
    --bag) bag="$2"; shift 2 ;;
    --topic) topic="$2"; topic_set=1; shift 2 ;;
    --model-config) model_config="$2"; model_config_set=1; shift 2 ;;
    --model-ckpt) model_ckpt="$2"; model_ckpt_set=1; shift 2 ;;
    --track) track=1; track_set=1; shift ;;
    --track-max-age) track_max_age="$2"; track_max_age_set=1; shift 2 ;;
    --track-interp) track_interp="$2"; track_interp_set=1; shift 2 ;;
    --track-dist) track_dist="$2"; track_dist_set=1; shift 2 ;;
    --track-use-motion) track_use_motion=1; track_use_motion_set=1; shift ;;
    --map-frame) map_frame=1; map_frame_set=1; shift ;;
    --no-map-frame) map_frame=0; map_frame_set=1; shift ;;
    --map-source-frame) map_source_frame="$2"; map_source_frame_set=1; shift 2 ;;
    --map-target-frame) map_target_frame="$2"; map_target_frame_set=1; shift 2 ;;
    --map-labels) map_labels_override="$2"; shift 2 ;;
    --skip-pcd) skip_pcd=1; shift ;;
    --static-filter) static_filter=1; shift ;;
    --static-voxel) static_voxel="$2"; shift 2 ;;
    --static-min-frames) static_min_frames="$2"; shift 2 ;;
    --static-min-ratio) static_min_ratio="$2"; shift 2 ;;
    --static-build-max) static_build_max="$2"; shift 2 ;;
    --static-build-stride) static_build_stride="$2"; shift 2 ;;
    --upload) upload=1; shift ;;
    --segments-dataset) segments_dataset="$2"; shift 2 ;;
    --segments-sample) segments_sample="$2"; shift 2 ;;
    --segments-labelset) segments_labelset="$2"; shift 2 ;;
    --segments-max-frames) segments_max_frames="$2"; shift 2 ;;
    --segments-start-frame) segments_start_frame="$2"; shift 2 ;;
    --segments-stride) segments_stride="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

if (( config_enabled )) && [[ -f "$config_path" ]]; then
  eval "$(
    python3 - "$config_path" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = {}
for line in path.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or ":" not in line:
        continue
    key, val = line.split(":", 1)
    key = key.strip()
    val = val.strip().strip('"').strip("'")
    data[key] = val

def to_bool(val):
    return str(val).lower() in ("1", "true", "yes", "on")

print(f"cfg_topic='{data.get('topic','')}'")
print(f"cfg_model_config='{data.get('model_config','')}'")
print(f"cfg_model_ckpt='{data.get('model_ckpt','')}'")
print(f"cfg_track_enabled={'1' if to_bool(data.get('track_enabled','')) else '0'}")
print(f"cfg_track_max_age='{data.get('track_max_age','')}'")
print(f"cfg_track_interpolate='{data.get('track_interpolate','')}'")
print(f"cfg_track_dist='{data.get('track_dist','')}'")
print(f"cfg_track_use_motion={'1' if to_bool(data.get('track_use_motion','')) else '0'}")
print(f"cfg_map_frame_enabled={'1' if to_bool(data.get('map_frame_enabled','')) else '0'}")
print(f"cfg_map_source_frame='{data.get('map_source_frame','')}'")
print(f"cfg_map_target_frame='{data.get('map_target_frame','')}'")
PY
  )"

  if (( ! topic_set )) && [[ -n "${cfg_topic:-}" ]]; then topic="$cfg_topic"; fi
  if (( ! model_config_set )) && [[ -n "${cfg_model_config:-}" ]]; then model_config="$cfg_model_config"; fi
  if (( ! model_ckpt_set )) && [[ -n "${cfg_model_ckpt:-}" ]]; then model_ckpt="$cfg_model_ckpt"; fi
  if (( ! track_set )) && [[ -n "${cfg_track_enabled:-}" ]]; then track="$cfg_track_enabled"; fi
  if (( ! track_max_age_set )) && [[ -n "${cfg_track_max_age:-}" ]]; then track_max_age="$cfg_track_max_age"; fi
  if (( ! track_interp_set )) && [[ -n "${cfg_track_interpolate:-}" ]]; then track_interp="$cfg_track_interpolate"; fi
  if (( ! track_dist_set )) && [[ -n "${cfg_track_dist:-}" ]]; then track_dist="$cfg_track_dist"; fi
  if (( ! track_use_motion_set )) && [[ -n "${cfg_track_use_motion:-}" ]]; then track_use_motion="$cfg_track_use_motion"; fi
  if (( ! map_frame_set )) && [[ -n "${cfg_map_frame_enabled:-}" ]]; then map_frame="$cfg_map_frame_enabled"; fi
  if (( ! map_source_frame_set )) && [[ -n "${cfg_map_source_frame:-}" ]]; then map_source_frame="$cfg_map_source_frame"; fi
  if (( ! map_target_frame_set )) && [[ -n "${cfg_map_target_frame:-}" ]]; then map_target_frame="$cfg_map_target_frame"; fi
fi

if [[ -z "$bag" || -z "$model_config" || -z "$model_ckpt" ]]; then
  echo "Missing required args." >&2
  usage
  exit 1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

bag_base="$(basename "$bag")"
bag_id="${bag_base%.bag}"
bag_id="${bag_id#_}"
if [[ "$bag_id" == File_* ]]; then
  bag_id="${bag_id#File_}"
fi

cfg_stem="$(basename "$model_config")"
cfg_stem="${cfg_stem%.yaml}"
cfg_stem="${cfg_stem,,}"
model_name="$cfg_stem"
if [[ "$cfg_stem" == *pointrcnn_iou* ]]; then
  model_name="pointrcnn_iou"
elif [[ "$cfg_stem" == *pointpillar* || "$cfg_stem" == *pointpillars* ]]; then
  model_name="pointpillars"
elif [[ "$cfg_stem" == *centerpoint* ]]; then
  model_name="centerpoint"
elif [[ "$cfg_stem" == *pv_rcnn* || "$cfg_stem" == *pvrcnn* ]]; then
  model_name="pv_rcnn"
elif [[ "$cfg_stem" == *parta2* ]]; then
  model_name="parta2"
fi

pcdet_dir="data/interim/${bag_id}"
moving_dir="data/interim/${bag_id}_moving"
map_dir="data/interim/${bag_id}_map"
map_pcd_dir="data/interim/${bag_id}_map_pcd"

python="./.venv/bin/python"

if (( static_filter )); then
  # Extract only, then build static map and run inference on moving points.
  "$python" src/tools/pipeline/run_pipeline.py \
    --bag "$bag" \
    --topic "$topic" \
    --pcdet-dir "$pcdet_dir" \
    --model-config "$model_config" \
    --model-ckpt "$model_ckpt" \
    --skip-infer \
    --skip-pcd

  "$python" src/tools/filtering/filter_static_points.py \
    --in-dir "$pcdet_dir" \
    --out-dir "$moving_dir" \
    --voxel-size "$static_voxel" \
    --static-min-frames "$static_min_frames" \
    --static-min-ratio "$static_min_ratio" \
    --build-max-frames "$static_build_max" \
    --build-stride "$static_build_stride" \
    --write-static-npz "data/interim/static_map_${bag_id}.npz"

  cp -f "${pcdet_dir}/frames.csv" "${moving_dir}/frames.csv"

  cmd=("$python" src/tools/pipeline/run_pipeline.py
    --bag "$bag"
    --topic "$topic"
    --pcdet-dir "$moving_dir"
    --model-config "$model_config"
    --model-ckpt "$model_ckpt"
    --skip-extract
    --skip-pcd
  )
else
  cmd=("$python" src/tools/pipeline/run_pipeline.py
    --bag "$bag"
    --topic "$topic"
    --model-config "$model_config"
    --model-ckpt "$model_ckpt"
  )
  if (( skip_pcd )); then
    cmd+=(--skip-pcd)
  fi
fi

if (( track )); then
  cmd+=(--track --track-max-age "$track_max_age" --track-interp "$track_interp" --track-dist "$track_dist")
  if (( track_use_motion )); then
    cmd+=(--track-use-motion)
  fi
fi

if (( upload )); then
  if (( static_filter )); then
    echo "Static filter + upload should use upload_tracks.sh (PCD from base, labels from moving)." >&2
    exit 1
  fi
  if [[ -z "$segments_dataset" ]]; then
    echo "--segments-dataset is required when --upload is set." >&2
    exit 1
  fi
  cmd+=(--upload --segments-dataset "$segments_dataset" --segments-labelset "$segments_labelset")
  cmd+=(--segments-max-frames "$segments_max_frames" --segments-start-frame "$segments_start_frame" --segments-stride "$segments_stride")
  if [[ -n "$segments_sample" ]]; then
    cmd+=(--segments-sample "$segments_sample")
  fi
fi

printf "+ %q " "${cmd[@]}"
printf "\n"
"${cmd[@]}"

if (( map_frame )); then
  pred_path="${map_labels_override}"
  if [[ -z "$pred_path" ]]; then
    if (( track )); then
      pred_path="data/processed/${bag_id}/${model_name}/ped_tracks_${model_name}_${bag_id}.jsonl"
    else
      pred_path="data/processed/${bag_id}/${model_name}/predictions_${model_name}_${bag_id}.jsonl"
    fi
  fi

  pred_base="${pred_path%.jsonl}"
  if [[ "$pred_base" == *"_${bag_id}" ]]; then
    map_pred_out="${pred_base%_${bag_id}}_map_${bag_id}.jsonl"
  else
    map_pred_out="${pred_base}_map.jsonl"
  fi

  echo "+ map-frame transform (bins + labels)"
  bash -lc "source /opt/ros/noetic/setup.bash; python3 scripts/transform_bins_tf.py \
    --bag \"$bag\" \
    --frames-csv \"${pcdet_dir}/frames.csv\" \
    --in-dir \"${pcdet_dir}\" \
    --out-dir \"${map_dir}\" \
    --source-frame \"$map_source_frame\" \
    --target-frame \"$map_target_frame\""

  cp -f "${pcdet_dir}/frames.csv" "${map_dir}/frames.csv"

  bash -lc "source /opt/ros/noetic/setup.bash; python3 scripts/transform_labels_tf.py \
    --bag \"$bag\" \
    --frames-csv \"${pcdet_dir}/frames.csv\" \
    --pred \"$pred_path\" \
    --out \"$map_pred_out\" \
    --source-frame \"$map_source_frame\" \
    --target-frame \"$map_target_frame\""

  "$python" src/export/bin_to_pcd_sequence.py \
    --in-dir "${map_dir}" \
    --out-dir "${map_pcd_dir}"
fi
