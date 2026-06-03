# NexusOps Project Review up to 2026-05-23

> Historical snapshot: this review has been superseded by `docs/architecture/current-state.md`, `docs/api.md`, and later stabilization notes. It is kept for traceability of the May 2026 review.

## Executive Summary

NexusOps has grown into a broad local control-plane MVP for infrastructure orchestration. The core architecture remains sound: FastAPI modules expose versioned APIs, services own workflows, repositories own persistence, adapters isolate external infrastructure, and the frontend stays feature-oriented under React/Vite.

The platform is no longer just inventory, Proxmox visibility, and Jobs. It now includes local auth/RBAC, managed-node inventory, Proxmox hypervisor/VM/LXC discovery, VM and LXC provisioning foundations, Jobs, packages, profiles, workflows, scheduled automations, Docker Compose deployments, remote access, Linux identity orchestration, credentials, integrations, runtime snapshots, and monitoring readiness.

The main risks identified at the time were operational hardening, not basic architecture:

- long-running operations still need deeper workflow-backed async execution
- monitoring overview must stay snapshot-first and avoid live provider discovery during normal rendering
- secrets handling is encrypted local MVP storage, not a production vault
- idempotency, rollback, fine-grained permissions, frontend tests, and deeper PostgreSQL-backed coverage remain incomplete

## Validation Results

Original May validation is superseded. Current living validation is tracked in `docs/architecture/current-state.md` and `docs/development.md`.

As of 2026-06-03:

- `cd frontend && npm run lint`: passed
- `cd frontend && npm run build`: passed
- `DEBUG=false .venv/bin/python -m pytest backend/tests -q`: passed with 147 tests
- CI covers backend quality, backend tests, PostgreSQL Alembic upgrade/downgrade smoke validation, frontend lint/build, and artifact hygiene.

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

- Completed after this review: backend tests no longer depend on live Proxmox for the previously failing inventory import path.
- Completed after this review: CI now enforces frontend lint/build, backend tests, Alembic validation, and generated-artifact hygiene.
- Mostly completed after this review: durable audit persistence exists for major operational surfaces; audit reporting, retention, and richer operator-facing filtering still need improvement.

### High

- Long-running orchestration still runs too much work inside request/response or in-process queues. Provisioning, package/profile execution, identity replication, deployments, and bulk jobs should become WorkflowRun-backed async operations.
- Monitoring overview should remain snapshot-first. Any live Prometheus target discovery or Grafana dashboard lookup should happen in explicit refresh paths that persist snapshots.
- Proxmox lifecycle actions accept tasks but do not consistently poll and persist task completion/status logs outside provisioning flows.
- Provisioning and deployments need idempotency keys to prevent duplicate VMs or repeated deploys from retries/double clicks.
- Secrets handling lacks production vault features: rotation, last-used metadata, usage graph, scoped access, and audit.
- Updated 2026-05-26: Remote shell WebSocket auth now uses short-lived, one-time scoped remote-access tokens instead of the active JWT.

### Medium

- Updated 2026-05-26: Refresh-token rotation and reuse detection are implemented with persisted token session families.
- RBAC is coarse. Fine-grained permissions, API keys, and service accounts are future work.
- Provisioning needs stronger preflight validation for VMID availability, IP conflicts, storage existence, cloud-init readiness, and blueprint compatibility.
- LXC support needs deeper readiness checks for network, gateway, DNS, storage, template metadata, and SSH readiness.
- Deployment logs are fetched on demand and are not first-class indexed records.
- Profile deployment steps need richer execution context before profiles can fully orchestrate machine setup plus app delivery.
- Integration records are runtime sources for Proxmox and monitoring, but future adapters still need the same treatment.
- No frontend test framework is configured.
- Basic PostgreSQL migration behavior is validated in CI; broader PostgreSQL-backed service/integration tests remain future work.

### Low

- Navigation and page grouping can be clearer now that the product surface is large.
- Several pages need better empty states, filtering, copy buttons, and progress timelines.
- Provisioning should become a guided wizard with a final review screen.
- Job and deployment log viewing needs search, copy, wrapping controls, and better timestamp context.
- Older sprint docs preserve historical limitations that are now obsolete; the current-state docs should remain the source of truth.

## Recommended Fix Order

1. Completed after this review: Proxmox test isolation no longer blocks backend validation.
2. Completed after this review: CI now covers lint, build, backend tests, Alembic upgrade validation, and artifact hygiene.
3. Completed/guarded after this review: monitoring overview remains snapshot-first; keep regression coverage around refresh boundaries.
4. Move provisioning and deployment execution into explicit WorkflowRun-backed async paths.
5. Partially completed after this review: durable audit/event records exist for major operations; improve reporting, retention, and workflow linkage.
6. Add idempotency keys for provisioning and deployments.
7. Completed after this review: WebSocket JWT query auth was replaced with short-lived scoped remote-access tokens.
8. Expand credential metadata with usage tracking, rotation workflows, and last-used fields.

## Safety Boundary

NexusOps can mutate local platform state, execute Jobs against Inventory-managed hosts, request limited Proxmox guest lifecycle actions, provision from Proxmox templates, run Docker Compose deployments through SSH, mediate shell/file access, and replicate non-root Linux identity state.

It should still not expose arbitrary SSH targets, raw provider consoles, ISO installers, Terraform/Ansible execution, root account ownership, broad provider-side deletion, or SSO/federated identity until the audit, workflow, permission, and secret-management layers are stronger.
