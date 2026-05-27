#!/usr/bin/env bash
set -euo pipefail

BUILD=false
DETACHED=false
EXPOSE_DATABASE=false

usage() {
  cat <<'USAGE'
Usage: scripts/start-docker.sh [options]

Options:
  --build             Build images before starting
  -d, --detached      Start containers in the background
  --expose-database   Expose PostgreSQL on the host using docker-compose.db-port.yml
  -h, --help          Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build)
      BUILD=true
      shift
      ;;
    -d|--detached)
      DETACHED=true
      shift
      ;;
    --expose-database)
      EXPOSE_DATABASE=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"

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
  python3 - <<'PY'
from base64 import urlsafe_b64encode
from os import urandom
print(urlsafe_b64encode(urandom(32)).decode("ascii"))
PY
}

cd "$REPO_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Engine in the LXC container or enable Docker access for this environment." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$REPO_ROOT/.env.example" "$ENV_FILE"
  echo "Created .env from .env.example. Edit admin/password values if needed."
fi

if [[ -z "$(get_dotenv_value NEXUSOPS_MASTER_KEY)" ]]; then
  set_dotenv_value NEXUSOPS_MASTER_KEY "$(generate_fernet_key)"
  echo "Generated local NEXUSOPS_MASTER_KEY in .env."
fi

compose_args=(compose)
if [[ "$EXPOSE_DATABASE" == true ]]; then
  compose_args+=(-f docker-compose.yml -f docker-compose.db-port.yml)
fi
compose_args+=(up)
if [[ "$BUILD" == true ]]; then
  compose_args+=(--build)
fi
if [[ "$DETACHED" == true ]]; then
  compose_args+=(-d)
fi

docker "${compose_args[@]}"
