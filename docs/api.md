# NexusOps API Overview

Current date: 2026-06-13

NexusOps exposes its backend API under `/api/v1` by default. The prefix is configurable through `API_V1_PREFIX`.

OpenAPI is available at `/api/v1/openapi.json` and Swagger UI at `/docs` when `ENABLE_OPENAPI=true` or the app is not running in production. In production, set `ENABLE_OPENAPI=false` if public API documentation should be hidden.

This overview was refreshed against the versioned router map and feature routes on 2026-06-13. It remains a compact operator/developer guide rather than a generated endpoint reference; use Swagger/OpenAPI for request and response schemas.

## Authentication

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/logout-all`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/users`
- `POST /api/v1/auth/users`
- `PUT /api/v1/auth/users/{user_id}`
- `POST /api/v1/auth/users/{user_id}/reset-password`

Access tokens are short lived. Refresh tokens are persisted as hashed sessions, rotate on refresh, and support token-family replay detection. Frontend auth currently stores tokens in session-scoped browser storage; httpOnly refresh-cookie transport remains a future hardening item.

## Core Inventory And Providers

- `GET/POST/PUT/DELETE /api/v1/servers`
- inventory lifecycle actions:
  - `POST /api/v1/servers/{server_id}/archive`
  - `POST /api/v1/servers/{server_id}/restore`
  - `POST /api/v1/servers/{server_id}/decommission`
  - `POST /api/v1/servers/{server_id}/unmanage`
- inventory health and host inspection:
  - `GET /api/v1/servers/health-summary`
  - `POST /api/v1/servers/{server_id}/health-check`
  - `POST /api/v1/servers/health-check/bulk`
  - `GET /api/v1/servers/{server_id}/system`
  - `GET /api/v1/servers/{server_id}/network`
  - `GET /api/v1/servers/{server_id}/docker`
- Proxmox inventory import and reconciliation:
  - `POST /api/v1/servers/sync/proxmox/import`
  - `POST /api/v1/servers/sync/proxmox/reconcile`
- `POST /api/v1/proxmox/inventory/sanitize-discovered?dry_run=true` previews stale discovered guest cleanup before deletion
- `GET /api/v1/servers/{server_id}/readiness` reports managed-state, SSH, sudo fallback, credential-reference, and Docker operation readiness
- `GET /api/v1/proxmox/dashboard`
- `GET /api/v1/proxmox/nodes`
- `GET /api/v1/proxmox/nodes/{node_name}`
- `GET /api/v1/proxmox/vms`
- `GET /api/v1/proxmox/storage`
- `GET /api/v1/proxmox/vms/{node}/{vm_type}/{vm_id}/status`
- `GET /api/v1/proxmox/cluster/summary`
- `POST /api/v1/proxmox/hosts/sync`
- `POST /api/v1/proxmox/guests/sync`
- guarded Proxmox guest lifecycle actions:
  - `POST /api/v1/proxmox/vms/{vm_id}/start`
  - `POST /api/v1/proxmox/vms/{vm_id}/stop`
  - `POST /api/v1/proxmox/vms/{vm_id}/reboot`
  - `POST /api/v1/proxmox/vms/{vm_id}/shutdown`

Inventory is the control-plane target boundary. Jobs, deployments, identity, monitoring, remote access, packages, profiles, workflows, and automations operate against Inventory-managed hosts.

## Jobs And Runtime Execution

- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/execute`
- `POST /api/v1/jobs/execute/bulk`
- `POST /api/v1/jobs/{job_id}/cancel`
- `GET /api/v1/jobs/actions`
- `POST /api/v1/jobs/actions/execute`
- custom action CRUD and execution

Jobs execute over SSH through Inventory targets. They persist redacted command display, actual command metadata, stdout, stderr, exit code, status, correlation ID, command policy, and activity events.

Raw Jobs and operational actions can carry an explicit `credential_ref` for execution/sudo use. This is separate from template or environment secret references and is resolved server-side into the SSH/Jobs runtime.

## Credentials, Variables, And Integrations

- `GET/POST/PUT/DELETE /api/v1/credentials`
- `GET/POST /api/v1/variables`
- `GET/POST/PUT/DELETE /api/v1/integrations`
- integration test and provider sync endpoints:
  - `POST /api/v1/integrations/{integration_id}/test`
  - `POST /api/v1/integrations/{integration_id}/sync/proxmox-hosts`
  - `POST /api/v1/integrations/{integration_id}/sync/proxmox-guests`

Credential APIs never return decrypted secrets. Runtime services resolve credentials server-side and redact injected values from job/deployment history.

## Provisioning

- VM provisioning under `/api/v1/vms`
- LXC provisioning foundations use the same `/api/v1/vms` create endpoint with `provisioning_type="lxc"`
- `GET /api/v1/vms/templates`
- provisioning blueprints under `/api/v1/vms/blueprints`
- provisioning batch requests under `/api/v1/vms/batches`

Provisioning uses Proxmox templates/cloud-init only. It registers Inventory before optional profile/package bootstrap execution.

## Packages, Profiles, Workflows, And Automations

- `GET/POST/PUT/DELETE /api/v1/packages`
- package clone/reset/execute and bulk apply actions
- `GET/POST/PUT/DELETE /api/v1/profiles`
- profile clone/reset/apply and bulk apply actions
- `GET /api/v1/workflows`
- `GET /api/v1/workflows/{workflow_run_id}`
- `GET/POST/PUT/DELETE /api/v1/automations`
- automation enable, disable, and run-now actions

Packages and profiles resolve into Jobs. Automations create WorkflowRuns and dispatch through existing service pipelines.

Profiles can include package, action, deployment, raw command, Identity user, Identity group, and Identity permission steps. Identity profile steps reference managed Identity records and execute through the existing Identity -> Jobs -> SSH path.

Package, profile, and automation execution can carry an execution/sudo credential reference where privileged Linux commands need sudo. Automations persist this reference so unattended scheduled runs use the same execution credential.

## Deployments

- `GET/POST/PUT/DELETE /api/v1/deployments`
- `POST /api/v1/deployments/validate`
- `GET /api/v1/deployments/{deployment_id}/dry-run`
- deploy, redeploy, restart, stop
- status, runtime refresh, and logs

Docker Compose deployments persist definitions, revisions, targets, executions, target executions, runtime state, and redacted credential-backed env injection. Runtime refresh reconciles observed Docker state into persisted deployment target state.

Deployment validation and dry-run preview expose Compose validation, service names, selected targets, remote deployment paths, env keys, credential-backed env keys, execution/sudo credential presence, and redacted generated commands. Deployment reads include runtime stale markers, runtime age, failure reason, per-target container state, missing services, health, and sync drift.

## Identity

- Linux user CRUD/adopt/discovery/replication
- Linux group CRUD/adopt/discovery/member inspection/replication
- SSH key deployment/revocation
- permission template CRUD/replication
- access profiles, group presets, and permission presets

Identity is Linux infrastructure orchestration, not platform login federation. It uses Jobs for SSH execution, supports discovered user/group adoption, stores optional account password credential references for managed Linux users, passes selected password/SSH-password credentials into sudo-backed replication, and excludes the `root` account from orchestration.

## Remote Access

- `POST /api/v1/remote-access/hosts/{server_id}/shell-token`
- `WebSocket /api/v1/remote-access/hosts/{server_id}/shell`
- file list/read/write endpoints
- trusted host-key approval endpoint

Remote Access only targets Inventory-managed hosts. Shell WebSockets use short-lived, one-time, server-scoped tokens instead of long-lived auth JWT query tokens. File writes are hash-checked and operator writes are path-limited.

## Monitoring And Runtime State

- `GET /api/v1/monitoring/overview`
- `GET /api/v1/monitoring/prometheus/health`
- per-server metrics and validation attempts
- monitoring validation refresh actions:
  - `POST /api/v1/monitoring/validate`
  - `POST /api/v1/monitoring/servers/{server_id}/validate`
- runtime refresh visibility and manual refresh:
  - `GET /api/v1/runtime-state/refresh-status`
  - `POST /api/v1/runtime-state/refresh/inventory`
  - `POST /api/v1/runtime-state/refresh/all`

Monitoring is snapshot-first during ordinary page rendering. Explicit refresh flows update snapshots and validation attempts.

Runtime-state endpoints report refresh status and trigger backend-owned refresh tasks for inventory and deployment snapshots. They are intended to keep frontend pages polling normalized persisted state instead of performing live infrastructure checks during ordinary rendering.

## Audit

- `GET /api/v1/audit-events`

Audit events are admin-only and record authentication, infrastructure mutations, credentials, provisioning, jobs, deployments, identity actions, remote access, monitoring validation, workflows, and operational failures. Failed job/audit outcomes are emitted at error log severity.
