# NexusOps Project Review up to 2026-05-20

## Executive Summary

NexusOps is now clearly evolving into an infrastructure operational control plane. Inventory is no longer just a CMDB table; it is the managed-node authority used by Proxmox, Jobs, Deployments, Monitoring, Identity, Remote Access, Automations, and Workflows.

The biggest architectural correction in this slice was clarifying that Proxmox host management means the hypervisor nodes themselves, not guest VM lifecycle. Hypervisors, VMs, and LXCs now have distinct managed-node identities and should stay visually and behaviorally separate across the platform.

## Current Strengths

- The modular monolith structure is still holding well.
- Repository-service separation remains the right backend pattern for database-backed modules.
- Provider adapters remain separate from orchestration services.
- Inventory is the correct execution boundary for Jobs, Deployments, Identity, Remote Access, and Monitoring.
- Proxmox integrations now support a stronger provider-to-inventory reconciliation path.
- Managed-node pages reduce fragmentation by converging metrics, shell, files, jobs, deployments, workflows, packages, profiles, identity, lifecycle, and provider metadata.
- Deployment runtime is much healthier now that definitions, executions, and per-target executions are separate concepts.
- Automations and workflows now expose operational state instead of feeling like static configuration records.
- Monitoring has the right product direction: readiness and infrastructure awareness, not Grafana dashboard management.

## Important Architecture Boundaries

- Proxmox is a provider layer, not the primary orchestration model.
- Raw provider objects should become managed Inventory nodes before NexusOps operates on them.
- Hypervisor hosts, VMs, and LXCs must remain separate node types.
- SSH access is a readiness/capability signal, not a requirement for provider discovery.
- Grafana is optional deep-analysis tooling, not a required dashboard-per-node dependency.
- Deployment and automation runtime history should converge around execution records, not page-local status fields.

## Recently Completed Areas

- First-class Proxmox hypervisor node management.
- LXC discovery/provisioning/lifecycle foundations.
- Unified managed-node operational view.
- Automation and workflow runtime visibility.
- Multi-target deployment runtime and per-target execution tracking.
- Operational UX cleanup with standardized action placement and collapsible action surfaces.
- Monitoring readiness refactor with Prometheus/Loki/Grafana treated as telemetry providers.
- Alembic migrations for LXC provisioning metadata and deployment runtime execution tables.

## Current Risks

- Long-running execution is still mostly request/response or in-process async; the architecture is ready for a background worker, but one is not implemented yet.
- Proxmox live behavior depends on provider API availability and local integration credentials.
- SSH/password/key readiness can fail independently from provider discovery, so UI copy must keep those states separate.
- Deployment fanout is sequential in the MVP. It records per-target state, but it is not yet a distributed queue.
- Monitoring readiness is operational, not a full telemetry database or log explorer.
- Frontend still has no test framework.
- Migration validation is still manual rather than CI-backed.

## Recommended Next Steps

- Add CI for frontend lint/build, backend tests, and Alembic migration checks.
- Move provisioning and deployments into workflow-backed background execution.
- Add stronger LXC readiness checks for networking, DNS, gateway, SSH polling, and storage/template compatibility.
- Add Proxmox integration replacement/failover workflows.
- Add audit persistence for provider lifecycle operations and decommission/archive flows.
- Add frontend tests for managed-node pages, deployment target state, and monitoring readiness.
