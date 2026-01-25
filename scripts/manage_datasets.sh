#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/manage_datasets.sh list
  scripts/manage_datasets.sh create --name <name> [--description <text>]
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

cmd="$1"
shift

case "$cmd" in
  list)
    ./.venv/bin/python src/tools/segments/segments_list_datasets.py
    ;;
  create)
    name=""
    description="BUDD-e pointcloud cuboid labels"
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --name) name="$2"; shift 2 ;;
        --description) description="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
      esac
    done
    if [[ -z "$name" ]]; then
      echo "--name is required" >&2
      exit 1
    fi
    ./.venv/bin/python src/tools/segments/segments_create_dataset.py --name "$name" --description "$description"
    ;;
  *)
    usage
    exit 1
    ;;
esac
