#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/setup_models.sh [--pointrcnn-iou]

Downloads model checkpoints into external/openpcdet/ckpts (not tracked).

Options:
  --pointrcnn-iou   Download PointRCNN-IoU KITTI checkpoint
EOF
}

download_pointrcnn_iou=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pointrcnn-iou) download_pointrcnn_iou=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
  esac
done

if (( download_pointrcnn_iou == 0 )); then
  usage
  exit 1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ckpt_dir="${repo_root}/external/openpcdet/ckpts"
mkdir -p "$ckpt_dir"

if (( download_pointrcnn_iou )); then
  url="https://github.com/open-mmlab/OpenPCDet/releases/download/v0.6.0/pointrcnn_iou_kitti.pth"
  out="${ckpt_dir}/pointrcnn_iou_kitti.pth"
  if [[ -f "$out" ]]; then
    echo "Checkpoint already exists: $out"
  else
    echo "Downloading: $url"
    curl -L "$url" -o "$out"
  fi
fi
