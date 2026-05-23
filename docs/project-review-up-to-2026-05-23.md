# NexusOps Project Review up to 2026-05-23

> Update: this review has been superseded for the monitoring and Inventory boundary by `docs/project-review-2026-05-23-monitoring-inventory.md`. The newer review reflects the snapshot-only monitoring refactor, managed-only Inventory default, and current validation results.

## Executive Summary

NexusOps has grown into a broad local control-plane MVP for infrastructure orchestration. The core architecture remains sound: FastAPI modules expose versioned APIs, services own workflows, repositories own persistence, adapters isolate external infrastructure, and the frontend stays feature-oriented under React/Vite.

The platform is no longer just inventory, Proxmox visibility, and Jobs. It now includes local auth/RBAC, managed-node inventory, Proxmox hypervisor/VM/LXC discovery, VM and LXC provisioning foundations, Jobs, packages, profiles, workflows, scheduled automations, Docker Compose deployments, remote access, Linux identity orchestration, credentials, integrations, runtime snapshots, and monitoring readiness.

The main risks are operational hardening, not basic architecture:

- one backend test currently reaches live Proxmox infrastructure
- long-running operations still need deeper workflow-backed async execution
- monitoring overview must stay snapshot-first and avoid live provider discovery during normal rendering
- secrets handling is encrypted local MVP storage, not a production vault
- audit, idempotency, rollback, CI, and PostgreSQL migration validation remain incomplete

## Validation Results

- `cd frontend && npm run lint`: passed
- `cd frontend && npm run build`: passed
- `.venv\Scripts\python.exe -m pytest backend\tests`: failed with 107 passed and 1 failed

Failing backend test:

```text
backend/tests/test_inventory.py::test_inventory_import_restores_archived_proxmox_record
```

Root cause:

The test calls `/api/v1/servers/sync/proxmox/import`, which reaches `ProxmoxService.list_vms()` and the configured real Proxmox API endpoint. On this machine it timed out against `hellgate.himalayan-chimaera.ts.net:8006`.

Required fix:

Override the Proxmox dependency or inject a fake adapter/service in the test. Unit and API tests must never depend on live infrastructure unless explicitly marked as integration tests.

## What Is Working

- Backend modular monolith structure is intact and coherent.
- Frontend route-level lazy loading and feature folders are in place.
- Local auth/RBAC is implemented with admin/operator/viewer boundaries.
- Inventory is a managed-node CMDB for hypervisors, VMs, LXCs, and physical hosts.
- Proxmox discovery, import, reconciliation, and controlled lifecycle boundaries are established.
- VM provisioning uses Proxmox templates and cloud-init.
- LXC provisioning and lifecycle foundations are wired into Inventory.
- Jobs remain the execution backbone for SSH commands, packages, profiles, deployments, and identity replication.
- Credential references are resolved server-side and sensitive runtime values are redacted in persisted command history.
- Docker Compose deployments have definition, execution, target execution, and partial-success state.
- Remote access is bounded by Inventory and RBAC.
- Linux identity is correctly treated as host orchestration, not centralized authentication.
- Monitoring readiness models Prometheus/Loki/Grafana as telemetry providers rather than owned dashboard systems.

## Findings That Need Fixing

### Critical

- Backend tests leak to real Proxmox infrastructure. This makes CI unreliable and can accidentally hit live systems from test runs.
- There is no CI pipeline enforcing frontend lint, frontend build, backend tests, Alembic migration validation, and generated-artifact checks.
- Destructive and long-running operations lack full audit persistence. Proxmox actions, provisioning, deployments, remote access, and identity replication need durable audit records.

### High

- Long-running orchestration still runs too much work inside request/response or in-process queues. Provisioning, package/profile execution, identity replication, deployments, and bulk jobs should become WorkflowRun-backed async operations.
- Monitoring overview should remain snapshot-first. Any live Prometheus target discovery or Grafana dashboard lookup should happen in explicit refresh paths that persist snapshots.
- Proxmox lifecycle actions accept tasks but do not consistently poll and persist task completion/status logs outside provisioning flows.
- Provisioning and deployments need idempotency keys to prevent duplicate VMs or repeated deploys from retries/double clicks.
- Secrets handling lacks production vault features: rotation, last-used metadata, usage graph, scoped access, and audit.
- Remote shell WebSocket auth uses the active JWT as a query parameter. This needs a short-lived scoped remote-access token.

### Medium

- Refresh-token rotation and reuse detection are not implemented.
- RBAC is coarse. Fine-grained permissions, API keys, and service accounts are future work.
- Provisioning needs stronger preflight validation for VMID availability, IP conflicts, storage existence, cloud-init readiness, and blueprint compatibility.
- LXC support needs deeper readiness checks for network, gateway, DNS, storage, template metadata, and SSH readiness.
- Deployment logs are fetched on demand and are not first-class indexed records.
- Profile deployment steps need richer execution context before profiles can fully orchestrate machine setup plus app delivery.
- Integration records are runtime sources for Proxmox and monitoring, but future adapters still need the same treatment.
- No frontend test framework is configured.
- Backend service tests use SQLite; migration behavior is not validated against PostgreSQL in automation.

### Low

- Navigation and page grouping can be clearer now that the product surface is large.
- Several pages need better empty states, filtering, copy buttons, and progress timelines.
- Provisioning should become a guided wizard with a final review screen.
- Job and deployment log viewing needs search, copy, wrapping controls, and better timestamp context.
- Older sprint docs preserve historical limitations that are now obsolete; the current-state docs should remain the source of truth.

## Recommended Fix Order

1. Fix Proxmox test isolation and add a regression test around fake provider injection.
2. Add CI for lint, build, backend tests, Alembic upgrade validation, and artifact hygiene.
3. Protect the monitoring snapshot boundary before merging monitoring discovery/dashboard changes.
4. Move provisioning and deployment execution into explicit WorkflowRun-backed async paths.
5. Add durable audit tables/events for infrastructure, provisioning, deployment, identity, and remote access operations.
6. Add idempotency keys for provisioning and deployments.
7. Replace WebSocket JWT query auth with short-lived scoped remote-access tokens.
8. Expand credential metadata with usage tracking, rotation workflows, and last-used fields.

## Safety Boundary

NexusOps can mutate local platform state, execute Jobs against Inventory-managed hosts, request limited Proxmox guest lifecycle actions, provision from Proxmox templates, run Docker Compose deployments through SSH, mediate shell/file access, and replicate non-root Linux identity state.

It should still not expose arbitrary SSH targets, raw provider consoles, ISO installers, Terraform/Ansible execution, root account ownership, broad provider-side deletion, or SSO/federated identity until the audit, workflow, permission, and secret-management layers are stronger.
