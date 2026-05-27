#!/usr/bin/env bash
set -euo pipefail

BUILD=true
PULL=false
CREATE_ENV=false
RUN_HEALTHCHECK=true
EXPOSE_DATABASE=false

usage() {
  cat <<'USAGE'
Usage: scripts/deploy.sh [options]

Options:
  --no-build          Start existing images without rebuilding
  --pull              Pull newer base images before building/starting
  --create-env        Create .env from .env.example when missing
  --expose-database   Expose PostgreSQL on the host using docker-compose.db-port.yml
  --skip-healthcheck  Do not run scripts/healthcheck.sh after deployment
  -h, --help          Show this help
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-build)
      BUILD=false
      shift
      ;;
    --pull)
      PULL=true
      shift
      ;;
    --create-env)
      CREATE_ENV=true
      shift
      ;;
    --expose-database)
      EXPOSE_DATABASE=true
      shift
      ;;
    --skip-healthcheck)
      RUN_HEALTHCHECK=false
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

cd "$REPO_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required for deployment." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  if [[ "$CREATE_ENV" != "true" ]]; then
    echo ".env is required for deployment. Create it first, or rerun with --create-env for local/dev stacks." >&2
    exit 1
  fi
  cp "$REPO_ROOT/.env.example" "$ENV_FILE"
  echo "Created .env from .env.example. Review secrets before using this beyond local/dev."
fi

compose_args=(compose)
if [[ "$EXPOSE_DATABASE" == true ]]; then
  compose_args+=(-f docker-compose.yml -f docker-compose.db-port.yml)
fi

docker "${compose_args[@]}" config --quiet

if [[ "$PULL" == true ]]; then
  docker "${compose_args[@]}" pull --ignore-buildable
fi

up_args=(up -d)
if [[ "$BUILD" == true ]]; then
  up_args+=(--build)
fi

docker "${compose_args[@]}" "${up_args[@]}"

if [[ "$RUN_HEALTHCHECK" == true ]]; then
  "$REPO_ROOT/scripts/healthcheck.sh"
fi
