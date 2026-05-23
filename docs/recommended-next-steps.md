# NexusOps Recommended Next Steps

Created: 2026-05-23

## Priority Roadmap

1. Completed on 2026-05-23: add CI foundations:
   - frontend lint
   - frontend build
   - backend tests
   - Alembic single-head validation
   - Alembic upgrade validation
   - generated-artifact hygiene checks

2. Completed on 2026-05-23: add durable audit tables/events for infrastructure mutations, authentication, credentials, provisioning, deployments, inventory reconciliation, remote access, workflows, monitoring validation, and package/profile execution.

3. Replace WebSocket query JWT authentication with short-lived scoped remote-access tokens.

4. Move provisioning, deployments, and bulk operations into WorkflowRun-backed async execution.

5. Add idempotency keys for provisioning and deployment operations.

6. Partially completed on 2026-05-23: add PostgreSQL Alembic validation in CI. Basic frontend tests still need to be added.

7. Add production startup safety checks for secrets, CORS, and master key configuration.

## Notes

These items came from the project review performed on 2026-05-23. They are intended as future hardening and delivery priorities before broadening destructive infrastructure capabilities.

## Review Findings Added on 2026-05-23

Source document: `docs/project-review-2026-05-23-monitoring-inventory.md`

1. Partially completed: monitoring validation now has persisted attempt history, audit events, bounded per-node checks, and resilient snapshot preservation. A full WorkflowRun-backed execution model remains future work.

2. Completed: monitoring validation attempts persist method, duration, result, component state, structured failure reason, and audit-event linkage per node.

3. Rename or deprecate legacy node-level Prometheus fields such as `prometheus_target_health` once API compatibility allows it. Prometheus is a provider-level health check, not a per-node row signal.

4. Clarify Grafana provider UI semantics. Grafana is currently a configured jump-link provider, not a render-time API dependency. Either label it as configured or add optional background reachability checks.

5. Completed: exporter/service validation now stores structured failure reasons such as `tcp_unreachable`, `ssh_auth_failed`, `service_inactive`, `docker_unavailable`, `command_timeout`, and `exporter_missing`.

6. Audit internal Inventory callers after the managed-only default filter change. Historical/discovery reads must request `include_unmanaged=true` explicitly, and execution flows must continue to exclude unmanaged nodes.

7. Remove unused monitoring compatibility fields such as `advanced_metrics_url`, `container_metrics_url`, `prometheus_url`, and `loki_url` after the frontend no longer depends on them.
