# NexusOps API Overview

Current date: 03.06.2026

NexusOps exposes its backend API under `/api/v1` by default. The prefix is configurable through `API_V1_PREFIX`.

OpenAPI is available at `/api/v1/openapi.json` and Swagger UI at `/docs` when `ENABLE_OPENAPI=true` or the app is not running in production. In production, set `ENABLE_OPENAPI=false` if public API documentation should be hidden.

## Authentication

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/logout-all`
- `GET /api/v1/auth/me`
- `GET/POST/PUT /api/v1/auth/users`
- `POST /api/v1/auth/users/{user_id}/reset-password`

Access tokens are short lived. Refresh tokens are persisted as hashed sessions, rotate on refresh, and support token-family replay detection. Frontend auth currently stores tokens in session-scoped browser storage; httpOnly refresh-cookie transport remains a future hardening item.

## Core Inventory And Providers

- `GET/POST/PUT/DELETE /api/v1/servers`
- inventory lifecycle actions: archive, restore, decommission, unmanage
- inventory health and bulk health checks
- Proxmox import, synchronization, reconciliation, and stale-record self-sanitize actions
- `GET /api/v1/proxmox/dashboard`
- Proxmox nodes, VMs, storage, cluster summary, guest status, and guarded lifecycle actions

Inventory is the control-plane target boundary. Jobs, deployments, identity, monitoring, remote access, packages, profiles, workflows, and automations operate against Inventory-managed hosts.

## Jobs And Runtime Execution

- `GET /api/v1/jobs`
- `GET /api/v1/jobs/{job_id}`
- `POST /api/v1/jobs/execute`
- `POST /api/v1/jobs/execute/bulk`
- `POST /api/v1/jobs/{job_id}/cancel`
- `GET /api/v1/jobs/actions`
- custom action CRUD and execution

Jobs execute over SSH through Inventory targets. They persist redacted command display, actual command metadata, stdout, stderr, exit code, status, correlation ID, command policy, and activity events.

## Credentials, Variables, And Integrations

- `GET/POST/PUT/DELETE /api/v1/credentials`
- `GET/POST/PUT/DELETE /api/v1/variables`
- `GET/POST/PUT/DELETE /api/v1/integrations`
- integration test and provider sync endpoints

Credential APIs never return decrypted secrets. Runtime services resolve credentials server-side and redact injected values from job/deployment history.

## Provisioning

- VM provisioning under `/api/v1/vms`
- LXC provisioning foundations under `/api/v1/vms/lxc`
- provisioning blueprints
- provisioning batch requests
- template and provider metadata endpoints

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

## Deployments

- `GET/POST/PUT/DELETE /api/v1/deployments`
- deploy, redeploy, restart, stop
- status, runtime refresh, and logs

Docker Compose deployments persist definitions, revisions, targets, executions, target executions, runtime state, and redacted credential-backed env injection. Runtime refresh reconciles observed Docker state into persisted deployment target state.

## Identity

- Linux user CRUD/adopt/discovery/replication
- Linux group CRUD/adopt/discovery/member inspection/replication
- SSH key deployment/revocation
- permission template CRUD/replication
- access profiles, group presets, and permission presets

Identity is Linux infrastructure orchestration, not platform login federation. It uses Jobs for SSH execution, supports discovered user/group adoption, passes selected password/SSH-password credentials into sudo-backed replication, and excludes the `root` account from orchestration.

## Remote Access

- `POST /api/v1/remote-access/hosts/{server_id}/shell-token`
- `WebSocket /api/v1/remote-access/hosts/{server_id}/shell`
- file list/read/write endpoints
- trusted host-key approval endpoint

Remote Access only targets Inventory-managed hosts. Shell WebSockets use short-lived, one-time, server-scoped tokens instead of long-lived auth JWT query tokens. File writes are hash-checked and operator writes are path-limited.

## Monitoring And Runtime State

- `GET /api/v1/monitoring/overview`
- provider health endpoints
- per-server metrics and validation attempts
- monitoring validation refresh actions
- `/api/v1/runtime-state` snapshot and refresh visibility

Monitoring is snapshot-first during ordinary page rendering. Explicit refresh flows update snapshots and validation attempts.

## Audit

- `GET /api/v1/audit-events`

Audit events are admin-only and record authentication, infrastructure mutations, credentials, provisioning, jobs, deployments, identity actions, remote access, monitoring validation, workflows, and operational failures. Failed job/audit outcomes are emitted at error log severity.
