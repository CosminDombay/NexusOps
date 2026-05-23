# NexusOps Project Review - 2026-05-23 Monitoring and Inventory Pass

## Summary

This review covers the current NexusOps tree after the monitoring refactor and Inventory/Infrastructure boundary correction on 2026-05-23.

NexusOps remains a modular monolith infrastructure orchestration platform. The backend is organized around FastAPI modules, service/repository boundaries, SQLAlchemy persistence, Alembic migrations, and adapter-backed infrastructure integrations. The frontend remains feature-oriented under React, TypeScript, Vite, Tailwind, Axios, and React Router.

The important product boundary is now clearer:

- Inventory is the managed-node CMDB and operational source of truth.
- Infrastructure discovery shows unmanaged provider-discovered assets.
- Monitoring validates managed Inventory nodes only.
- Grafana remains the observability interface.
- NexusOps only validates monitoring availability, exporter/service state, stale snapshots, and Grafana jump links.

## Implemented In This Pass

- Added persisted monitoring snapshots with `MonitoringSnapshot`, `MonitoringState`, and `MonitoringComponentStatus`.
- Added Alembic migration `20260523_0029_monitoring_snapshots.py`.
- Added monitoring validation APIs:
  - `POST /api/v1/monitoring/validate`
  - `POST /api/v1/monitoring/servers/{server_id}/validate`
- Added background monitoring validation through the scheduler and in-process task queue.
- Refactored Monitoring overview to read persisted snapshots only.
- Removed live Grafana/Prometheus/Loki queries from frontend render paths.
- Added local component validation for managed nodes:
  - `node_exporter`
  - `promtail`
  - `cAdvisor`
- Added validation methods:
  - TCP port checks
  - SSH `systemctl is-active`
  - `docker ps --format '{{.Names}} {{.Image}}' | grep -i -- 'cadvisor'` fallback for cAdvisor
- Added configurable Grafana jump links from integration templates and node metadata.
- Moved Prometheus into provider-level monitoring health instead of per-node display.
- Corrected Inventory default listing to show only managed active nodes.
- Added explicit `include_unmanaged=true` for discovery/admin-style reads.
- Ensured Monitoring uses the managed Inventory list, so unmanaged discovered devices are ignored.

## Current Project Tree

```text
NexusOps
+-- backend
|   +-- app
|   |   +-- adapters
|   |   |   +-- docker
|   |   |   +-- proxmox
|   |   |   +-- ssh
|   |   +-- api
|   |   |   +-- v1
|   |   +-- common
|   |   +-- core
|   |   +-- db
|   |   +-- jobs
|   |   +-- modules
|   |   |   +-- auth
|   |   |   +-- automations
|   |   |   +-- credentials
|   |   |   +-- deployments
|   |   |   +-- execution
|   |   |   +-- identity
|   |   |   +-- integrations
|   |   |   +-- inventory
|   |   |   +-- jobs
|   |   |   +-- monitoring
|   |   |   +-- packages
|   |   |   +-- profiles
|   |   |   +-- provisioning
|   |   |   +-- proxmox
|   |   |   +-- remote_access
|   |   |   +-- runtime_state
|   |   |   +-- variables
|   |   |   +-- workflows
|   |   +-- templates
|   |   +-- workers
|   +-- migrations
|   |   +-- versions
|   +-- tests
+-- docs
|   +-- architecture
|   +-- sprints
|   +-- api
|   +-- diagrams
|   +-- workflows
+-- frontend
|   +-- public
|   +-- src
|   |   +-- app
|   |   +-- assets
|   |   +-- components
|   |   +-- features
|   |   |   +-- auth
|   |   |   +-- automations
|   |   |   +-- credentials
|   |   |   +-- deployments
|   |   |   +-- identity
|   |   |   +-- inventory
|   |   |   +-- jobs
|   |   |   +-- monitoring
|   |   |   +-- packages
|   |   |   +-- profiles
|   |   |   +-- provisioning
|   |   |   +-- proxmox
|   |   |   +-- remote-access
|   |   |   +-- runtime-state
|   |   |   +-- settings
|   |   |   +-- workflows
|   |   +-- lib
|   |   +-- styles
+-- infra
+-- scripts
+-- screenshots
```

## Review Findings

### High - Monitoring validation is sequential and in-process

`MonitoringService.validate_all` loops through managed nodes one at a time, and the scheduler dispatches the job through the in-process queue.

References:

- `backend/app/modules/monitoring/service.py:115`
- `backend/app/modules/monitoring/tasks.py:15`
- `backend/app/workers/scheduler/service.py:66`

Risk:

This is acceptable for the current lab estate, but it can overrun the configured interval as node count grows or SSH checks hang near timeout. It also disappears if the API process is down or restarted mid-run.

Recommended fix:

Move validation into WorkflowRun-backed or durable worker execution with bounded concurrency, per-node timeout budgets, retry jitter, and persisted run history.

### High - Monitoring validation is not yet audited as an operational run

The snapshot table stores state, and runtime refresh status stores the latest broad status, but validation runs are not durable operational events with per-node step history.

References:

- `backend/app/modules/monitoring/service.py:128`
- `backend/app/modules/monitoring/service.py:232`

Risk:

Operators can see current state but cannot inspect a historical timeline of monitoring validation attempts, methods used, and per-node failure changes.

Recommended fix:

Persist validation attempts as WorkflowRuns or monitoring validation events with per-node method, result, duration, error class, and triggering source.

### Medium - Prometheus provider health is intentionally lightweight, but the legacy field name is misleading

Prometheus is now provider-level, but the persisted/API compatibility field is still named `prometheus_target_health`.

References:

- `backend/app/modules/monitoring/models.py:79`
- `backend/app/modules/monitoring/schemas.py:49`
- `backend/app/modules/monitoring/service.py:224`

Risk:

Future developers may mistake this for per-node Prometheus scrape target validation. The frontend no longer renders it per node, but the name remains a conceptual trap.

Recommended fix:

Rename or supersede this with provider-level snapshot fields such as `prometheus_health_status`, then deprecate node-level `prometheus_target_health` after API compatibility is no longer needed.

### Medium - Grafana provider card means configured link, not validated API availability

Grafana remains deliberately out of render-time validation. The provider card treats configured Grafana as reachable because the app only needs to generate a jump link.

References:

- `backend/app/modules/monitoring/service.py:167`
- `frontend/src/features/monitoring/MonitoringPage.tsx:73`

Risk:

The word "reachable" can overstate what NexusOps knows. A configured Grafana URL may still be down, behind auth, or routed differently.

Recommended fix:

Either label Grafana as "configured" in the UI or add an optional background Grafana reachability check that does not block page rendering.

### Medium - Exporter failure reasons are coarse

TCP failures, SSH auth failures, missing services, inactive services, and command execution errors all collapse into `unavailable`.

References:

- `backend/app/modules/monitoring/service.py:307`
- `backend/app/modules/monitoring/service.py:330`
- `backend/app/modules/monitoring/service.py:352`
- `backend/app/modules/monitoring/service.py:375`

Risk:

The UI tells the operator what is down, but not why. This slows repair because "port closed", "SSH auth failed", and "systemctl inactive" imply different actions.

Recommended fix:

Store structured component details per service: method, checked port, SSH attempted, exit code, stderr category, and short operator-facing reason.

### Medium - Inventory default filtering changed correctly, but historical/discovery reads need explicit intent

Inventory list now hides unmanaged/discovered records unless `include_unmanaged=true` is passed.

References:

- `backend/app/modules/inventory/repository.py:77`
- `backend/app/modules/inventory/repository.py:115`
- `backend/app/modules/inventory/router.py:67`

Risk:

This is the desired product behavior, but internal consumers that expect full history must now request both `include_inactive=true` and `include_unmanaged=true` where appropriate.

Recommended fix:

Audit internal callers and keep tests around Inventory, Infrastructure discovery, Monitoring, Jobs, Deployments, Remote Access, and Automations so unmanaged nodes never become execution targets accidentally.

### Low - Monitoring schemas still expose legacy dashboard fields

The monitoring response still carries compatibility fields such as `prometheus_url`, `loki_url`, `advanced_metrics_url`, and `container_metrics_url`.

References:

- `backend/app/modules/monitoring/schemas.py:36`
- `frontend/src/features/monitoring/types/monitoring.ts:24`

Risk:

These names imply deeper dashboard rendering or provider exploration than NexusOps now supports.

Recommended fix:

Deprecate unused fields after frontend and host-detail consumers are fully aligned around snapshot health and `open_grafana_url`.

## Validation Results

Completed during this review pass:

- `backend/tests/test_monitoring.py`: passed
- `frontend npm run lint`: passed
- `frontend npm run build`: passed

Full-suite validation should be rerun before merge/push if more code changes are added after this document.

## Recommended Next Fix Order

1. Add CI with frontend lint/build, backend tests, Alembic single-head validation, Alembic upgrade validation, and artifact hygiene checks.
2. Move monitoring validation runs into durable WorkflowRun-backed async execution.
3. Add structured monitoring failure reasons per component.
4. Rename or deprecate legacy node-level Prometheus fields.
5. Clarify Grafana provider UI as "configured link" or add an optional background health check.
6. Add durable audit events for monitoring validation, infrastructure mutations, remote access, provisioning, deployments, and identity operations.
7. Replace remote shell query JWT with short-lived scoped remote-access tokens.
8. Add idempotency keys for provisioning and deployment operations.
