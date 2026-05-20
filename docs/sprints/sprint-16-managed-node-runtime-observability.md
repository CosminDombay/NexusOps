# Sprint 16 - Managed Node Runtime and Observability

Date: 2026-05-20

## Summary

This sprint moved NexusOps from module-specific operational pages toward a unified managed-node control plane. Proxmox hypervisors, VMs, LXCs, and future physical hosts now share the same Inventory-centered operational model, while deployments, automations, workflows, and monitoring gained stronger runtime/readiness visibility.

## Completed

- Proxmox hypervisor hosts are first-class `node_type=hypervisor` Inventory records.
- Active Proxmox integrations can discover and reconcile hypervisor nodes, guest VMs, and LXC containers.
- Host decommission/archive/reactivation removes nodes from active orchestration while preserving historical queryability.
- LXC containers are represented as `node_type=lxc` managed nodes with provider metadata, lifecycle state, readiness state, and provisioning foundations.
- Unified managed-node operations now converge overview, metrics, terminal, files, deployments, jobs, workflows, packages, profiles, identity, provider metadata, lifecycle state, and readiness signals.
- Automations and workflows expose runtime state, targets, last/next run, execution counts, durations, recent execution history, current step, linked jobs, and failure summaries.
- Deployments now separate definitions from runtime executions and per-target executions.
- Multi-target deployment fanout is supported through sequential per-target Jobs with `success`, `failed`, and `partial_success` rollups.
- Operational UX now favors page-header actions, drawers, collapsible action sections, runtime badges, status pills, and compact operational toolbars.
- Monitoring was refactored away from Grafana dashboard assumptions into infrastructure observability readiness.
- Prometheus, Loki, and Grafana are treated as telemetry providers and deep-analysis tools, not visualization objects managed by NexusOps.

## Migrations

- `20260520_0024_lxc_provisioning_metadata.py`
  - Adds LXC provisioning metadata needed to track container provisioning and managed-node linkage.
- `20260520_0025_deployment_runtime_executions.py`
  - Adds deployment execution and deployment target execution tables for multi-target runtime visibility.

## Architecture Notes

The primary operational object is now the managed node:

```text
provider discovery/provisioning -> Inventory managed node -> Jobs/Deployments/Identity/Monitoring/Remote Access
```

Proxmox remains a provider integration. Raw Proxmox objects are not direct orchestration targets. NexusOps reconciles provider objects into Inventory records and then executes through the managed-node architecture.

Deployment runtime now follows this shape:

```text
Deployment definition -> DeploymentExecution -> DeploymentTargetExecution -> Job -> SSH adapter
```

Monitoring readiness now follows this shape:

```text
Telemetry providers -> readiness checks -> per-node observability state -> managed-node and Monitoring UI
```

## Remaining Work

- Move long-running provisioning, identity, package/profile execution, and deployments into deeper workflow-backed async execution.
- Add richer LXC readiness validation for interfaces, gateway reachability, DNS, SSH polling, storage discovery, and template metadata.
- Add Proxmox integration endpoint replacement/failover workflows.
- Add first-class audit records for infrastructure actions and destructive operations.
- Add CI coverage for Alembic migrations, LXC provisioning, hypervisor reconciliation, deployment target executions, and monitoring readiness derivation.

## Validation

- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `.venv\Scripts\python.exe -m pytest backend\tests`

Latest local run: frontend lint passed, frontend build passed, backend tests passed with 96 tests.
