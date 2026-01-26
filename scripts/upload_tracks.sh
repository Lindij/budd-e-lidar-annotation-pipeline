#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/upload_tracks.sh --config <config.(sh|yaml)> [options]

Options:
  --config <path>        Bash config file to source (required)
  --bag-id <id>          Bag id for template configs
  --model-name <name>    Model name for template configs
  --split-size <n>       Split into chunks of n frames (0 = no split)
  --sample-name <name>   Override sample name/prefix from config
  --dataset <id>         Override dataset (owner/name)
  --pcd-dir <path>       Override PCD directory
  --frames-csv <path>    Override frames.csv path
  --pred <path>          Override prediction JSONL path
  --labelset <name>      Override labelset name (default: tracks)
  --start-frame <n>      Start frame index (default: 0)
  --max-frames <n>       Max frames to upload (0 = all)
  --no-allow-empty       Disable --allow-empty
EOF
}

config=""
bag_id=""
model_name=""
split_size=0
sample_name_override=""
dataset_override=""
pcd_dir_override=""
frames_csv_override=""
pred_override=""
labelset_override=""
start_frame=0
max_frames=0
allow_empty=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config) config="$2"; shift 2 ;;
    --bag-id) bag_id="$2"; shift 2 ;;
    --model-name) model_name="$2"; shift 2 ;;
    --split-size) split_size="$2"; shift 2 ;;
    --sample-name) sample_name_override="$2"; shift 2 ;;
    --dataset) dataset_override="$2"; shift 2 ;;
    --pcd-dir) pcd_dir_override="$2"; shift 2 ;;
    --frames-csv) frames_csv_override="$2"; shift 2 ;;
    --pred) pred_override="$2"; shift 2 ;;
    --labelset) labelset_override="$2"; shift 2 ;;
    --start-frame) start_frame="$2"; shift 2 ;;
    --max-frames) max_frames="$2"; shift 2 ;;
    --no-allow-empty) allow_empty=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

if [[ -z "$config" ]]; then
  echo "Missing --config" >&2
  usage
  exit 1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ ! -f "$config" ]]; then
  echo "Config not found: $config" >&2
  exit 1
fi

if [[ "$config" == *.yaml || "$config" == *.yml ]]; then
  eval "$(
    python3 - "$config" "$bag_id" "$model_name" <<'PY'
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
bag_id = sys.argv[2]
model_name = sys.argv[3]
data = {}
for line in cfg_path.read_text().splitlines():
    line = line.strip()
    if not line or line.startswith("#") or ":" not in line:
        continue
    key, val = line.split(":", 1)
    key = key.strip()
    val = val.strip().strip('"').strip("'")
    data[key] = val

def expand(value: str) -> str:
    return value.format(bag_id=bag_id, model_name=model_name)

dataset = data.get("dataset", "")
model_cfg = data.get("model_name", "")
labelset = data.get("labelset", "tracks")
pcd_dir = data.get("pcd_dir_template", "")
frames_csv = data.get("frames_csv_template", "")
pred = data.get("pred_template", "")
sample_prefix = data.get("sample_prefix_template", "")

if not bag_id and ("{bag_id}" in pcd_dir or "{bag_id}" in frames_csv or "{bag_id}" in pred or "{bag_id}" in sample_prefix):
    raise SystemExit("Missing --bag-id for template config")
if not model_name:
    model_name = model_cfg
if not model_name and ("{model_name}" in pred or "{model_name}" in sample_prefix):
    raise SystemExit("Missing --model-name for template config")

pcd_dir = expand(pcd_dir) if pcd_dir else ""
frames_csv = expand(frames_csv) if frames_csv else ""
pred = expand(pred) if pred else ""
sample_prefix = expand(sample_prefix) if sample_prefix else ""

print(f'dataset=\"{dataset}\"')
print(f'labelset=\"{labelset}\"')
print(f'pcd_dir=\"{pcd_dir}\"')
print(f'frames_csv=\"{frames_csv}\"')
print(f'pred=\"{pred}\"')
print(f'sample_prefix=\"{sample_prefix}\"')
PY
  )"
else
  # shellcheck source=/dev/null
  source "$config"
fi

dataset="${dataset_override:-${dataset:-}}"
pcd_dir="${pcd_dir_override:-${pcd_dir:-}}"
frames_csv="${frames_csv_override:-${frames_csv:-}}"
pred="${pred_override:-${pred:-}}"
labelset="${labelset_override:-${labelset:-tracks}}"
sample_prefix="${sample_name_override:-${sample_prefix:-${sample_name:-}}}"

if [[ -z "$dataset" || -z "$pcd_dir" || -z "$frames_csv" || -z "$pred" || -z "$sample_prefix" ]]; then
  echo "Config must define dataset, pcd_dir, frames_csv, pred, and sample_prefix (or sample_name)." >&2
  exit 1
fi

python_bin="./.venv/bin/python"

allow_empty_flag=""
if [[ "$allow_empty" -eq 1 ]]; then
  allow_empty_flag="--allow-empty"
fi

total_lines=$(wc -l < "$frames_csv")
total_frames=$((total_lines - 1))
if (( total_frames < 0 )); then
  total_frames=0
fi

if (( max_frames > 0 )); then
  total_frames="$max_frames"
fi

if (( split_size <= 0 )); then
  "$python_bin" src/export/segments_upload_sequence.py \
    --dataset "$dataset" \
    --pcd-dir "$pcd_dir" \
    --frames-csv "$frames_csv" \
    --pred "$pred" \
    --sample-name "$sample_prefix" \
    --labelset "$labelset" \
    --start-frame "$start_frame" \
    --max-frames "$total_frames" \
    --overwrite-labels \
    $allow_empty_flag
  exit 0
fi

remaining="$total_frames"
current_start="$start_frame"

while (( remaining > 0 )); do
  if (( remaining > split_size )); then
    chunk_size="$split_size"
  else
    chunk_size="$remaining"
  fi
  chunk_end=$((current_start + chunk_size - 1))
  start_tag=$(printf "%04d" "$current_start")
  end_tag=$(printf "%04d" "$chunk_end")
  sample_name="${sample_prefix}_${start_tag}_${end_tag}"

  "$python_bin" src/export/segments_upload_sequence.py \
    --dataset "$dataset" \
    --pcd-dir "$pcd_dir" \
    --frames-csv "$frames_csv" \
    --pred "$pred" \
    --sample-name "$sample_name" \
    --labelset "$labelset" \
    --start-frame "$current_start" \
    --max-frames "$chunk_size" \
    --overwrite-labels \
    $allow_empty_flag

  remaining=$((remaining - chunk_size))
  current_start=$((current_start + chunk_size))
done
