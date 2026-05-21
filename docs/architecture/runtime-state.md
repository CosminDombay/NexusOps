# Runtime State

NexusOps derives node runtime state on the backend so frontend pages do not invent their own readiness rules.

The runtime-state layer separates three concerns:

- Provider lifecycle state: whether the infrastructure provider is reachable and the guest exists.
- SSH orchestration state: whether NexusOps can execute Jobs-backed work against the inventory node.
- Monitoring state: whether telemetry is present, partial, missing, or stale.

Provider lifecycle actions such as start, stop, shutdown, and reboot depend on provider availability and guest existence. They do not depend on SSH availability.

SSH-backed actions such as shell access, Jobs, deployments, profiles, package execution, and identity replication depend on SSH readiness and active inventory management.

Monitoring readiness is independent from provider and SSH state. It is derived from persisted observability snapshots: canonical monitoring target availability, node_exporter scrape state, log ingestion visibility, telemetry freshness, and optional container telemetry readiness.

Monitoring uses simplified states only: Healthy, Partial, Missing, Stale, and Unknown. Advanced metrics and log exploration remain in Prometheus, Loki, and Grafana.

Inventory records survive provider disconnects, disabled integrations, missing guests, and stale synchronization. Those conditions should be represented as degraded or stale runtime reasons instead of deleting or hiding the inventory record.

The canonical backend shape is `NodeRuntimeState`, exposed on inventory and provider read models through `runtime_state`.
