#!/usr/bin/env bash
set -Eeuo pipefail

EXPOSE_DATABASE=false
SKIP_TESTS=false
NO_START=false

usage() {
  cat <<'USAGE'
Usage: ./setup-docker.sh [options]

Deploy NexusOps as a Docker Compose stack with PostgreSQL included.

Options:
  --expose-database   Expose PostgreSQL on the host using docker-compose.db-port.yml
  --skip-tests        Skip backend/frontend tests before deployment
  --no-start          Validate and build without starting containers
  -h, --help          Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --expose-database)
      EXPOSE_DATABASE=true
      shift
      ;;
    --skip-tests)
      SKIP_TESTS=true
      shift
      ;;
    --no-start)
      NO_START=true
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
REPO_ROOT="$SCRIPT_DIR"
REPORT_DIR="$REPO_ROOT/deployment-reports"
REPORT_FILE="$REPORT_DIR/docker-$(date +%Y%m%d-%H%M%S).log"
ENV_FILE="$REPO_ROOT/.env"

mkdir -p "$REPORT_DIR"
exec > >(tee -a "$REPORT_FILE") 2>&1

finish() {
  local status=$?
  if [[ $status -eq 0 ]]; then
    echo "Deployment script completed successfully."
  else
    echo "Deployment script failed with exit code $status."
  fi
  echo "Report: $REPORT_FILE"
}
trap finish EXIT

run_step() {
  local label="$1"
  shift
  echo
  echo "==> $label"
  "$@"
}

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

echo "NexusOps Docker Compose deployment"
echo "Started: $(date -Is)"
echo "Report: $REPORT_FILE"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required. Install Docker Engine and the Docker Compose plugin, then rerun this script." >&2
  exit 1
fi

echo
echo "==> Prepare local .env for Docker deployment"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$REPO_ROOT/.env.example" "$ENV_FILE"
  echo "Created .env from .env.example. Edit production secrets before using this outside local testing."
fi
if [[ -z "$(get_dotenv_value NEXUSOPS_MASTER_KEY)" ]]; then
  set_dotenv_value NEXUSOPS_MASTER_KEY "$(generate_fernet_key)"
  echo "Generated local NEXUSOPS_MASTER_KEY in .env."
fi

if [[ "$SKIP_TESTS" != true ]]; then
  run_step "Run backend tests, Alembic head check, and artifact hygiene" "$REPO_ROOT/scripts/ci-backend.sh"
  run_step "Run frontend lint and production build" "$REPO_ROOT/scripts/ci-frontend.sh"
else
  echo "Skipping tests by request."
fi

compose_files=(-f docker-compose.yml)
if [[ "$EXPOSE_DATABASE" == true ]]; then
  compose_files+=(-f docker-compose.db-port.yml)
fi

run_step "Validate Docker Compose configuration" docker compose "${compose_files[@]}" config --quiet
run_step "Build Docker images" docker compose "${compose_files[@]}" build

if [[ "$NO_START" == true ]]; then
  echo "Docker images built. Start later with: docker compose ${compose_files[*]} up -d"
  exit 0
fi

run_step "Start Docker Compose stack" docker compose "${compose_files[@]}" up -d
run_step "Show Docker Compose status" docker compose "${compose_files[@]}" ps

echo
echo "NexusOps Docker stack is starting."
echo "Frontend: http://localhost:${FRONTEND_PORT:-5173}"
echo "Backend:  http://localhost:${BACKEND_PORT:-8000}/api/v1"
