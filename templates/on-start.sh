#!/usr/bin/env bash
set -Eeuo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-/workspace}"
BOOTSTRAP_ROOT="${BOOTSTRAP_ROOT:-$WORKSPACE_ROOT/bootstrap}"
BOOTSTRAP_REPO="${BOOTSTRAP_REPO:?BOOTSTRAP_REPO is required}"
BOOTSTRAP_REF="${BOOTSTRAP_REF:-}"

mkdir -p "$WORKSPACE_ROOT"

if [[ -d "$BOOTSTRAP_ROOT/.git" ]]; then
  git -C "$BOOTSTRAP_ROOT" fetch --all --tags
else
  rm -rf "$BOOTSTRAP_ROOT"
  git clone "$BOOTSTRAP_REPO" "$BOOTSTRAP_ROOT"
fi

if [[ -n "$BOOTSTRAP_REF" ]]; then
  git -C "$BOOTSTRAP_ROOT" checkout "$BOOTSTRAP_REF"
fi

chmod +x "$BOOTSTRAP_ROOT/bootstrap.sh"
find "$BOOTSTRAP_ROOT/bin" -maxdepth 1 -type f -exec chmod +x {} \;

nohup bash "$BOOTSTRAP_ROOT/bootstrap.sh" >/dev/null 2>&1 &
echo "bootstrap launched in background; logs: $BOOTSTRAP_ROOT/bootstrap.log"
