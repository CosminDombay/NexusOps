# Runtime Snapshot Stabilization

NexusOps now separates runtime reconciliation from ordinary UI rendering.

Inventory, target selection, and monitoring overview reads consume `node_runtime_snapshots`. These snapshots contain provider state, SSH state, monitoring state, orchestration state, eligibility flags, degraded/stale reasons, warnings, and freshness timestamps.

Live infrastructure checks are reserved for explicit refresh paths:

- inventory health checks update SSH-derived snapshot fields
- Proxmox discovery/lifecycle reads update provider-derived snapshot fields
- direct server monitoring refreshes use explicit canonical monitoring targets and update monitoring-derived snapshot fields
- `/api/v1/runtime-state/refresh/inventory` backfills lightweight inventory-derived snapshots without SSH, Prometheus, Loki, or provider calls

This keeps inventory and monitoring page rendering bounded to database reads and avoids per-row SSH checks, provider polling, or Prometheus/Loki query storms during normal navigation.

Monitoring overview is snapshot-driven. It must not discover Prometheus instances, build hostname regex selectors, or run deep telemetry query chains while rendering.

Version 1 intentionally does not add queues, distributed workers, websockets, or external cache infrastructure. The snapshot tables provide the persistence contract those systems can use later.

## Current Review Notes

As of the 2026-05-23 review, the snapshot architecture remains the desired boundary. If monitoring needs automatic target/dashboard discovery, implement it as an explicit refresh operation that writes snapshot fields, readiness reasons, and technical details. Do not let normal overview rendering depend on live provider availability.

This same rule should extend to Proxmox-heavy inventory paths: tests and ordinary reads should use injected adapters or persisted state instead of reaching live provider endpoints unless the endpoint is explicitly a provider refresh/action endpoint.
