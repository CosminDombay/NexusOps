#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ENV_FILE="$REPO_ROOT/.env"

export PUPPETEER_SKIP_DOWNLOAD="${PUPPETEER_SKIP_DOWNLOAD:-true}"

dotenv_escape() {
  local value="$1"
  value="${value//\'/\'\\\'\'}"
  printf "'%s'" "$value"
}

get_dotenv_value() {
  local key="$1"
  [[ -f "$ENV_FILE" ]] || return 0
  local line value
  line="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" "$ENV_FILE" | tail -n 1 || true)"
  [[ -n "$line" ]] || return 0
  value="${line#*=}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  if [[ "$value" == \"*\" && "$value" == *\" ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "$value" == \'*\' && "$value" == *\' ]]; then
    value="${value:1:${#value}-2}"
  fi
  printf '%s' "$value"
}

set_dotenv_value() {
  local key="$1"
  local value="$2"
  local entry temp_file
  entry="$key=$(dotenv_escape "$value")"
  touch "$ENV_FILE"
  if grep -qE "^[[:space:]]*${key}[[:space:]]*=" "$ENV_FILE"; then
    temp_file="$(mktemp)"
    awk -v key="$key" -v entry="$entry" '
      BEGIN { updated = 0 }
      $0 ~ "^[[:space:]]*" key "[[:space:]]*=" { print entry; updated = 1; next }
      { print }
      END { if (!updated) print entry }
    ' "$ENV_FILE" > "$temp_file"
    mv "$temp_file" "$ENV_FILE"
  else
    printf '%s\n' "$entry" >> "$ENV_FILE"
  fi
}

generate_fernet_key() {
  "$REPO_ROOT/.venv/bin/python" - <<'PY'
from base64 import urlsafe_b64encode
from os import urandom
print(urlsafe_b64encode(urandom(32)).decode("ascii"))
PY
}

cd "$REPO_ROOT"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python 3 is required. Install python3 and python3-venv, then rerun this script." >&2
  exit 1
fi

if [[ ! -d "$REPO_ROOT/.venv" ]]; then
  "$PYTHON_BIN" -m venv "$REPO_ROOT/.venv"
fi

"$REPO_ROOT/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
"$REPO_ROOT/.venv/bin/python" -m pip install -r "$REPO_ROOT/requirements.txt"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$REPO_ROOT/.env.example" "$ENV_FILE"
  echo "Created .env from .env.example."
  set_dotenv_value DATABASE_URL "postgresql+asyncpg://nexusops:nexusops@localhost:5432/nexusops"
  set_dotenv_value CORS_ORIGINS "[\"http://localhost:5173\",\"http://127.0.0.1:5173\"]"
  set_dotenv_value VITE_API_BASE_URL "http://localhost:8000/api/v1"
fi

if [[ -z "$(get_dotenv_value NEXUSOPS_MASTER_KEY)" ]]; then
  set_dotenv_value NEXUSOPS_MASTER_KEY "$(generate_fernet_key)"
  echo "Generated local NEXUSOPS_MASTER_KEY in .env."
fi

if grep -q '^CORS_ORIGINS="\["' "$ENV_FILE"; then
  set_dotenv_value CORS_ORIGINS "[\"http://localhost:5173\",\"http://127.0.0.1:5173\"]"
fi

if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
  (cd "$FRONTEND_DIR" && npm ci)
else
  echo "Native Linux node/npm was not found; skipping frontend dependency installation." >&2
fi

echo "NexusOps local environment is ready."
echo "Python: $REPO_ROOT/.venv/bin/python"
