# Operational Readiness

NexusOps readiness is intentionally split into independent signals:

- Provider readiness: provider and guest lifecycle visibility.
- SSH readiness: whether NexusOps can run Jobs-backed orchestration.
- Monitoring readiness: whether the node is observable through configured telemetry providers.
- Inventory readiness: whether the managed-node record is active, managed, synchronized, stale, or retained without provider confirmation.
- Credential readiness: whether the node has enough configured metadata or selected execution credentials for SSH, sudo fallback, Docker discovery, Jobs, Packages, Profiles, Deployments, and Identity replication.

No single signal should mask the others. A VM can be stopped but still eligible for provider start. A node can be SSH-unreachable but still eligible for provider lifecycle actions. A node can be observable even when SSH is unavailable.

## Monitoring Readiness

Monitoring readiness is limited to operational observability:

- host metrics target reachable
- host metrics recent
- logs visible
- optional container telemetry running when expected

The readiness output is reduced to Healthy, Partial, Missing, Stale, or Unknown. The UI should pair these states with short remediation guidance rather than raw provider exceptions.

## Refresh Boundaries

Normal pages read snapshots. Explicit refresh flows update snapshots:

- health check refreshes SSH state
- provider discovery refreshes provider state
- monitoring refresh validates telemetry readiness
- inventory refresh backfills lightweight derived state
- Host Detail credential readiness is a safe configuration signal. It does not prove a password is correct or mutate the host; it tells the operator whether NexusOps has enough metadata to attempt the workflow.

This keeps operator navigation responsive and avoids request-bound infrastructure reconciliation.
