#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export BOOTSTRAP_ROOT="${BOOTSTRAP_ROOT:-$SCRIPT_DIR}"
export WORKSPACE_ROOT="${WORKSPACE_ROOT:-/workspace}"
export COMFYUI_ROOT="${COMFYUI_ROOT:-$WORKSPACE_ROOT/ComfyUI}"
export HF_HOME="${HF_HOME:-$WORKSPACE_ROOT/.cache/huggingface}"
export HF_HUB_CACHE="${HF_HUB_CACHE:-$HF_HOME/hub}"
export LOG_DIR="${LOG_DIR:-$WORKSPACE_ROOT/logs}"
export BOOTSTRAP_LOG_FILE="${BOOTSTRAP_LOG_FILE:-$BOOTSTRAP_ROOT/bootstrap.log}"
export BOOTSTRAP_VENV="${BOOTSTRAP_VENV:-$BOOTSTRAP_ROOT/.bootstrap-venv}"

mkdir -p "$BOOTSTRAP_ROOT" "$HF_HOME" "$HF_HUB_CACHE" "$LOG_DIR"

exec > >(tee -a "$BOOTSTRAP_LOG_FILE") 2>&1

echo "[$(date -Iseconds)] bootstrap starting"
echo "BOOTSTRAP_ROOT=$BOOTSTRAP_ROOT"
echo "WORKSPACE_ROOT=$WORKSPACE_ROOT"
echo "COMFYUI_ROOT=$COMFYUI_ROOT"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="$(command -v python)"
else
  echo "Python is required but was not found" >&2
  exit 1
fi

if [[ ! -x "$BOOTSTRAP_VENV/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$BOOTSTRAP_VENV"
fi

VENV_PYTHON="$BOOTSTRAP_VENV/bin/python"
"$VENV_PYTHON" -m pip install --disable-pip-version-check --upgrade pip setuptools wheel
"$VENV_PYTHON" -m pip install --disable-pip-version-check -r "$BOOTSTRAP_ROOT/config/python-requirements.lock"

exec "$VENV_PYTHON" "$BOOTSTRAP_ROOT/bootstrap/bootstrap.py" --repo-root "$BOOTSTRAP_ROOT" bootstrap "$@"
