#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$REPO_ROOT/.venv}"

cd "$REPO_ROOT"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 is required for backend CI." >&2
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools wheel
"$VENV_DIR/bin/python" -m pip install -r "$REPO_ROOT/requirements.txt"

export DEBUG=false
export CORS_ORIGINS="${CORS_ORIGINS:-[\"http://localhost:5173\",\"http://127.0.0.1:5173\"]}"
if [[ -z "${NEXUSOPS_MASTER_KEY:-}" ]]; then
  export NEXUSOPS_MASTER_KEY="$("$VENV_DIR/bin/python" - <<'PY'
from base64 import urlsafe_b64encode
from os import urandom
print(urlsafe_b64encode(urandom(32)).decode("ascii"))
PY
)"
fi

"$VENV_DIR/bin/python" -m pytest backend/tests -q
"$VENV_DIR/bin/python" -m alembic -c alembic.ini heads
"$VENV_DIR/bin/python" scripts/check_artifact_hygiene.py
