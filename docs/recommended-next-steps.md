# NexusOps Recommended Next Steps

Created: 2026-05-23

## Priority Roadmap

1. Add CI first:
   - frontend lint
   - frontend build
   - backend tests
   - Alembic single-head validation
   - Alembic upgrade validation
   - generated-artifact hygiene checks

2. Add durable audit tables/events for infrastructure mutations and remote access.

3. Replace WebSocket query JWT authentication with short-lived scoped remote-access tokens.

4. Move provisioning, deployments, and bulk operations into WorkflowRun-backed async execution.

5. Add idempotency keys for provisioning and deployment operations.

6. Add PostgreSQL migration validation and basic frontend tests.

7. Add production startup safety checks for secrets, CORS, and master key configuration.

## Notes

These items came from the project review performed on 2026-05-23. They are intended as future hardening and delivery priorities before broadening destructive infrastructure capabilities.

## Review Findings Added on 2026-05-23

Source document: `docs/project-review-2026-05-23-monitoring-inventory.md`

1. Move monitoring validation into durable WorkflowRun-backed async execution with bounded concurrency, retry jitter, per-node timeout budgets, and persisted run history.

2. Persist monitoring validation attempts as operational events or WorkflowRuns so operators can inspect method, duration, result, and failure class per node.

3. Rename or deprecate legacy node-level Prometheus fields such as `prometheus_target_health` once API compatibility allows it. Prometheus is a provider-level health check, not a per-node row signal.

4. Clarify Grafana provider UI semantics. Grafana is currently a configured jump-link provider, not a render-time API dependency. Either label it as configured or add optional background reachability checks.

5. Store structured exporter/service failure reasons instead of collapsing TCP failure, SSH auth failure, missing service, inactive service, and command failure into `unavailable`.

6. Audit internal Inventory callers after the managed-only default filter change. Historical/discovery reads must request `include_unmanaged=true` explicitly, and execution flows must continue to exclude unmanaged nodes.

7. Remove unused monitoring compatibility fields such as `advanced_metrics_url`, `container_metrics_url`, `prometheus_url`, and `loki_url` after the frontend no longer depends on them.
