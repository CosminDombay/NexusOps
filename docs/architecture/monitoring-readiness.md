# Monitoring Readiness

NexusOps monitoring is an observability readiness layer. It answers one operational question:

Is this managed node observable enough for operators to trust its telemetry?

It does not replace Prometheus, Loki, or Grafana. Those systems remain the advanced metrics, logs, and dashboard tools.

## Readiness States

Monitoring reduces node observability to five states:

- Healthy: metrics and logs are available and fresh.
- Partial: either metrics or logs are available, but not both.
- Missing: telemetry is configured but unavailable.
- Stale: Prometheus has a target, but recent metrics are not available.
- Unknown: NexusOps lacks a canonical monitoring target or enough snapshot data.

The API still stores internal values such as `monitoring_ready`, `monitoring_partial`, `monitoring_missing`, and `stale_metrics`, but operator-facing UI should show the simplified state names.

## 2026-05-23 Review Note

The monitoring architecture is snapshot-first. A current working-tree change adds Prometheus target discovery and Grafana dashboard lookup helpers around overview rendering. Before merging that direction, keep the boundary clear:

- explicit refresh actions may query Prometheus, Loki, and Grafana, then persist runtime snapshot data
- overview reads should prefer persisted snapshots and bounded database work
- Grafana dashboard links should come from configured integration metadata or refresh-produced snapshot metadata, not repeated dashboard searches during normal page loads

This keeps Monitoring useful on large inventories and prevents provider timeouts from making the overview page slow or flaky.

## Endpoint Metadata

Managed nodes can carry explicit monitoring endpoint metadata:

- `monitoring_interface`: `lan`, `tailscale`, `localhost`, or `docker`
- `monitoring_target`: canonical Prometheus instance target, for example `100.90.80.15:9100`
- `monitoring_strategy`: `host`, `container`, or `host_container`

NexusOps should not discover monitoring targets by hostname permutations or broad PromQL regex selectors during ordinary overview rendering. Reconciliation uses the canonical target exactly as stored, or values found during explicit refresh workflows.

## Host vs Container Observability

Host observability checks:

- node_exporter target exists
- node_exporter scrape is reachable
- promtail/log ingestion is visible
- metrics are recent

Container observability checks:

- Docker runtime is available when container telemetry is expected
- cAdvisor target exists when configured
- cAdvisor scrape is running

cAdvisor is container telemetry. It is not a mandatory host exporter, and host observability can be healthy without cAdvisor.

## PromQL Rules

Prometheus queries must remain simple and exact:

- `up{instance="target"}`
- `node_boot_time_seconds{instance="target"}`

Do not build `instance=~"..."` regex selectors or hostname discovery queries in NexusOps. Operators should configure the canonical scrape target instead.

## Runtime Snapshot Integration

Monitoring overview reads persisted runtime snapshots. It does not perform live Prometheus or Loki reconciliation during rendering.

Explicit monitoring refreshes may query telemetry providers, then update:

- runtime snapshot monitoring state
- readiness reasons
- remediation guidance
- technical details
- freshness timestamps

This keeps pages responsive while preserving a clear refresh path.

## Operator Errors

Operator-facing UI should show normalized reasons such as:

- monitoring target missing
- metrics unavailable
- node_exporter missing
- logs missing
- telemetry stale
- cAdvisor not running

Raw HTTP, Loki, Prometheus, parser, or stack trace details may be retained as technical details, but should not be shown as primary operator guidance.
