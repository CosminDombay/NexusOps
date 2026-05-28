#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_ROOT="${OUTPUT_ROOT:-$REPO_ROOT/debug-bundles}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT_DIR="$OUTPUT_ROOT/$TIMESTAMP"

mkdir -p "$OUTPUT_DIR"
cd "$REPO_ROOT"

run_capture() {
  local name="$1"
  shift

  {
    echo "\$ $*"
    "$@"
  } >"$OUTPUT_DIR/$name" 2>&1 || true
}

run_sql() {
  local name="$1"
  local sql="$2"

  {
    echo "$sql"
    docker compose exec -T postgres psql -U "${POSTGRES_USER:-nexusops}" -d "${POSTGRES_DB:-nexusops}" -c "$sql"
  } >"$OUTPUT_DIR/$name" 2>&1 || true
}

run_capture docker-compose-ps.txt docker compose ps
run_capture backend-logs.txt docker compose logs --tail=500 backend
run_capture frontend-logs.txt docker compose logs --tail=300 frontend
run_capture postgres-logs.txt docker compose logs --tail=200 postgres
run_capture healthcheck.txt "$REPO_ROOT/scripts/healthcheck.sh"

run_sql inventory-proxmox.tsv "
select id, hostname, ip_address, vmid, external_id, managed, lifecycle_state, sync_status, provider_type, updated_at
from servers
where provider = 'proxmox'
order by updated_at desc;
"

run_sql provisioning-failures.tsv "
select id, vm_name, new_vm_id, static_ip_cidr, status, error_message, created_at, updated_at
from provisioning_requests
order by created_at desc
limit 25;
"

run_sql integrations.tsv "
select id, name, provider_type, enabled, status, last_error, updated_at
from integrations
order by updated_at desc;
"

tar -C "$OUTPUT_ROOT" -czf "$OUTPUT_DIR.tar.gz" "$TIMESTAMP"

echo "Debug bundle written to $OUTPUT_DIR.tar.gz"
