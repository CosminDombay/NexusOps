#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$REPO_ROOT/.venv}"
FRONTEND_DIR="$REPO_ROOT/frontend"
CACHE_DIR="$REPO_ROOT/.runner-cache"

mkdir -p "$CACHE_DIR"

file_hash() {
  sha256sum "$@" | sha256sum | awk '{print $1}'
}

ensure_backend_deps() {
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "Python 3 is required for backend dependency setup." >&2
    exit 1
  fi

  local requirements_file="$REPO_ROOT/requirements.txt"
  local marker_file="$CACHE_DIR/backend-requirements.sha256"
  local current_hash
  current_hash="$(file_hash "$requirements_file")"

  if [[ -d "$VENV_DIR" && -f "$marker_file" && "$(cat "$marker_file")" == "$current_hash" ]]; then
    echo "Backend dependencies are already current."
    return
  fi

  echo "Installing backend dependencies..."
  if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  "$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
  "$VENV_DIR/bin/python" -m pip install -r "$requirements_file"
  printf '%s\n' "$current_hash" > "$marker_file"
}

ensure_frontend_deps() {
  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    echo "Native Linux node/npm is required for frontend dependency setup." >&2
    exit 1
  fi

  local package_file="$FRONTEND_DIR/package.json"
  local lock_file="$FRONTEND_DIR/package-lock.json"
  local marker_file="$CACHE_DIR/frontend-dependencies.sha256"
  local current_hash

  if [[ -f "$lock_file" ]]; then
    current_hash="$(file_hash "$package_file" "$lock_file")"
  else
    current_hash="$(file_hash "$package_file")"
  fi

  if [[ -d "$FRONTEND_DIR/node_modules" && -f "$marker_file" && "$(cat "$marker_file")" == "$current_hash" ]]; then
    echo "Frontend dependencies are already current."
    return
  fi

  echo "Installing frontend dependencies..."
  if [[ -f "$lock_file" ]]; then
    (cd "$FRONTEND_DIR" && npm ci)
  else
    (cd "$FRONTEND_DIR" && npm install)
  fi
  printf '%s\n' "$current_hash" > "$marker_file"
}

cd "$REPO_ROOT"
ensure_backend_deps
ensure_frontend_deps
