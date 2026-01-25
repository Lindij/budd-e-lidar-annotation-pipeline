#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/setup_env.sh cuda
  scripts/setup_env.sh ros
  scripts/setup_env.sh openpcdet
  scripts/setup_env.sh check
  scripts/setup_env.sh all
EOF
}

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

setup_cuda() {
  CUDA_VER="12-1"
  CUDA_KEYRING_DEB="cuda-keyring_1.1-1_all.deb"
  CUDA_KEYRING_URL="https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/${CUDA_KEYRING_DEB}"

  sudo apt update
  sudo apt install -y wget gnupg lsb-release

  tmp_dir="$(mktemp -d)"
  trap 'rm -rf "${tmp_dir}"' EXIT

  wget -q "${CUDA_KEYRING_URL}" -O "${tmp_dir}/${CUDA_KEYRING_DEB}"
  sudo dpkg -i "${tmp_dir}/${CUDA_KEYRING_DEB}"

  sudo apt update
  sudo apt install -y "cuda-toolkit-${CUDA_VER}"

  if ! grep -q "/usr/local/cuda/bin" "${HOME}/.bashrc"; then
    echo "export PATH=/usr/local/cuda/bin:\$PATH" >> "${HOME}/.bashrc"
  fi
  if ! grep -q "/usr/local/cuda/lib64" "${HOME}/.bashrc"; then
    echo "export LD_LIBRARY_PATH=/usr/local/cuda/lib64:\$LD_LIBRARY_PATH" >> "${HOME}/.bashrc"
  fi
}

setup_ros() {
  sudo apt update
  sudo apt install -y curl gnupg2 lsb-release

  codename="$(lsb_release -sc)"
  echo "deb http://packages.ros.org/ros/ubuntu ${codename} main" | sudo tee /etc/apt/sources.list.d/ros1-latest.list >/dev/null

  curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.asc | sudo apt-key add -

  sudo apt update
  sudo apt install -y \
    ros-noetic-ros-base \
    python3-rosdep \
    python3-rosinstall \
    python3-rosinstall-generator \
    python3-wstool \
    build-essential

  sudo rosdep init || true
  rosdep update

  if ! grep -q "source /opt/ros/noetic/setup.bash" "${HOME}/.bashrc"; then
    echo "source /opt/ros/noetic/setup.bash" >> "${HOME}/.bashrc"
  fi
}

setup_openpcdet() {
  export CUDA_HOME=/usr/local/cuda
  VENV_PYTHON="${repo_root}/.venv/bin/python"
  OPENPCDET_DIR="${repo_root}/external/openpcdet"
  "${VENV_PYTHON}" -m pip install --no-build-isolation -e "${OPENPCDET_DIR}"
}

check_openpcdet() {
  "${repo_root}/.venv/bin/python" - <<'PY'
import importlib
import sys

mods = ["torch", "pcdet"]
missing = []
for m in mods:
    try:
        importlib.import_module(m)
    except Exception as exc:
        missing.append((m, str(exc)))

if missing:
    for m, err in missing:
        print(f"Missing {m}: {err}")
    sys.exit(1)

print("OpenPCDet environment OK.")
PY
}

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

case "$1" in
  cuda) setup_cuda ;;
  ros) setup_ros ;;
  openpcdet) setup_openpcdet ;;
  check) check_openpcdet ;;
  all) setup_cuda; setup_ros; setup_openpcdet; check_openpcdet ;;
  -h|--help) usage ;;
  *) usage; exit 1 ;;
esac
