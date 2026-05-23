# Monitoring Readiness

NexusOps monitoring is a lightweight operational validation layer. It does not replace Prometheus, Loki, or Grafana.

Grafana remains the dedicated observability interface. NexusOps only validates that managed Inventory nodes have expected monitoring components available and gives operators a Grafana jump link.

## Scope

NexusOps monitoring should do:

- validate monitoring availability
- verify node-local exporter/service state
- display persisted monitoring health state
- provide Grafana jump links

NexusOps monitoring should not do:

- embed Grafana panels
- recreate Grafana dashboards
- query Loki during page rendering
- query Prometheus during page rendering
- parse dashboards
- render custom metrics charts
- depend on the Grafana API during page rendering

## Snapshot Model

Monitoring state is persisted per managed node in `monitoring_snapshots`.

Each snapshot tracks:

- `node_exporter_status`
- `promtail_status`
- `cadvisor_status`
- provider-level Prometheus health compatibility field
- `last_validated_at`
- `last_successful_check_at`
- `stale_after`
- `grafana_url`
- validation details

Node monitoring states are:

- `monitored`
- `partial`
- `unmonitored`
- `stale`
- `unknown`

## Node Validation

Per-node rows are based only on the local monitoring components NexusOps expects on managed nodes:

- `node_exporter`
- `promtail`
- `cAdvisor`

Allowed validation methods:

- TCP reachability checks
- HTTP reachability checks for provider health
- SSH `systemctl is-active` checks where Inventory SSH metadata is available
- cAdvisor Docker fallback with `docker ps --format '{{.Names}} {{.Image}}' | grep -i -- 'cadvisor'`

NexusOps does not scrape metrics to decide node row health. It checks service availability and records the result.

## Provider Validation

Prometheus and Grafana are displayed above the node list as monitoring providers.

Prometheus is a general monitoring infrastructure health check. It is not rendered as a per-node row signal.

Grafana is primarily a configured jump-link provider. NexusOps generates URLs from integration config and node metadata without querying the Grafana API during rendering.

## Inventory Boundary

Monitoring reads managed Inventory nodes only.

Unmanaged provider-discovered devices belong in Infrastructure discovery. They should not appear in the managed Inventory list and should not be monitored by the Monitoring page until imported or otherwise marked managed.

## Staleness and Failure Handling

If validation cannot reach monitoring infrastructure or a node component:

- preserve the last known snapshot
- update the component/provider status from the validation attempt
- mark snapshots stale after the configured window
- avoid Inventory or frontend crashes

Provider outages should degrade monitoring state but must not block the Inventory, Infrastructure, Jobs, or Remote Access pages.

## Grafana Links

Grafana URLs are generated from:

- Grafana base URL integration config
- dashboard path or UID templates
- node metadata such as hostname, provider node, IP address, and monitoring target

This gives operators one action per node: Open Grafana.

## Known Follow-Ups

- Move monitoring validation into durable WorkflowRun-backed async execution.
- Add bounded concurrency and retry jitter for validation jobs.
- Persist per-node validation attempts as operational events.
- Store structured failure reasons for TCP, SSH, systemctl, Docker, and provider checks.
- Rename or deprecate legacy `prometheus_target_health` fields now that Prometheus is provider-level.
- Clarify Grafana provider UI as configured jump-link availability or add optional background Grafana reachability checks.
