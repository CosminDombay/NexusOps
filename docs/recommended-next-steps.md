# NexusOps Recommended Next Steps

Created: 2026-05-23

Updated: 2026-06-21

## Priority Roadmap

1. Completed on 2026-05-23: add CI foundations:
   - frontend lint
   - frontend build
   - backend tests
   - Alembic single-head validation
   - Alembic upgrade validation
   - generated-artifact hygiene checks

2. Completed on 2026-05-23: add durable audit tables/events for infrastructure mutations, authentication, credentials, provisioning, deployments, inventory reconciliation, remote access, workflows, monitoring validation, and package/profile execution.

3. Completed on 2026-05-26: replace WebSocket query JWT authentication with short-lived scoped remote-access tokens.

4. Move provisioning, deployments, and bulk operations into WorkflowRun-backed async execution.

5. Add idempotency keys for provisioning and deployment operations.

6. Partially completed on 2026-05-23: add PostgreSQL Alembic validation in CI. Basic frontend tests still need to be added.

7. Completed on 2026-05-26: add production startup safety checks for secrets, CORS, master key configuration, Proxmox TLS verification, default admin credentials, and OpenAPI exposure.

8. Completed on 2026-05-26: add refresh-token rotation, persisted token sessions, token-family reuse detection, and current-session/logout-all invalidation.

9. Completed on 2026-05-26: add SSH host-key trust-on-first-use foundations, stored fingerprints, mismatch blocking, and audited manual approval.

10. Completed on 2026-05-26: add command governance foundations, admin-only custom action CRUD, immutable execution intent metadata, and append-only job execution events.

11. Completed on 2026-05-26: add baseline rate limiting and security headers for future public exposure.

12. Prepare deployment runbooks for Docker Compose and on-prem LXC/VM installation.

13. Add a controlled update workflow:
   - database backup before update
   - image rebuild or pull
   - Alembic migration validation
   - service restart
   - `/api/v1/health` smoke check
   - login, inventory, jobs/actions, Proxmox dashboard, and monitoring smoke checks where configured

14. Add frontend tests for the highest-risk workflows:
   - login/session restore/logout
   - inventory target selection
   - jobs action execution form behavior
   - deployment create/edit/operation flows
   - remote-access token initiation guardrails

15. Move provisioning, deployments, and bulk operations deeper into WorkflowRun-backed async execution.

16. Add feature-specific smoke suites for the current stabilization phase:
   - Identity discovery/adopt/sync and sudo credential propagation
   - Docker deployment create/edit/preview/deploy/runtime refresh/log visibility
   - Execution/sudo credential selectors for Jobs, Packages, Profiles, Automations, and Deployments
   - Inventory import/re-import/stale-record self-sanitize dry-run/apply
   - Host Detail credential readiness
   - Auth login/session restore/logout

17. Improve Identity operator UX around target-first workflows:
   - per-host user/group matrix
   - visible host-origin and drift state
   - separate account-password and execution/sudo credential controls
   - clearer disabled-action prerequisites

18. Completed on 2026-06-04: improve Docker deployment runtime diagnostics:
   - stale observed state marker
   - desired versus observed status split
   - first failure line and suggested remediation
   - runtime age and per-target failure reason

19. Completed on 2026-06-04: add execution/sudo credential selectors across Jobs, Packages, Profiles, Automations, and Deployments so privileged commands can use a selected password/SSH-password credential while application/env secrets stay separate.

20. Completed on 2026-06-04: add deployment preflight validation and dry-run previews with redacted generated commands.

21. Completed on 2026-06-04: add inventory credential readiness signals on Host Detail / Node Management.

22. Completed on 2026-06-04: add dry-run preview before Proxmox discovered-record self-sanitize.

23. Add Docker Compose discovery, adoption, and destructive machine-side removal:
   - scan nodes for existing Compose projects/configurations
   - adopt discovered projects into NexusOps-managed deployments
   - manage adopted deployments through Deployments and per-node Deployment views
   - keep "Delete NexusOps record" separate from "Remove from machine"
   - support Compose down and optional remote file/env cleanup
   - mark orphaned/stale deployment records when expected files or containers are missing

24. Add runtime event filtering by correlation ID and target for deployment, job, workflow, and scheduler diagnostics.

25. Completed on 2026-06-18: stabilize deployment drafts, package uninstall execution, sidebar scrolling, credential/search/manual Trash validation, and profile builder ergonomics for validation.

26. Completed on 2026-06-21: simplify the first demo use case to a Docker demo host:
   - base utilities
   - optional secondary disk
   - Docker Engine
   - Identity step for `cerberus` Docker access
   - Portainer, cAdvisor, and demo Nginx deployment
   - final Jobs-backed validation

27. Before any release/demo capture, run one full remote development/test-server pass of `USECASE-001 Demo Bootstrap` and record:
   - provisioning completion
   - profile step Jobs
   - deployment runtime state
   - final validation Job output
   - reachable Portainer, cAdvisor, and demo web URLs

## Notes

These items came from the project review performed on 2026-05-23. They are intended as future hardening and delivery priorities before broadening destructive infrastructure capabilities.

The 2026-05-26 hardening pass intentionally stayed practical for a homelab/on-prem orchestrator. Remaining future work is mostly depth rather than foundation: httpOnly refresh-cookie migration, a fuller command approval UI, expired-token cleanup jobs, distributed runtime leases, and frontend tests.

The 2026-05-27 preparation pass adds deployment guidance and keeps automated container updates intentionally operator-triggered until backup, rollback, and smoke-test automation are in place.

The 2026-06-03 stabilization pass prioritizes manual findings over new feature breadth. Identity users/groups management and Docker deployment runtime clarity are the main product-stabilization tracks; backlog items believed fixed should remain `Needs testing` until manually confirmed.

The 2026-06-04 stabilization pass added execution/sudo credential consistency, deployment validation/dry-run previews, runtime stale/failure diagnostics, Host Detail credential readiness, and self-sanitize dry-run preview. These improvements are implementation-complete but remain in manual `Needs testing` status until the staging pipeline and operator tests confirm them.

The 2026-06-18 stabilization pass validated enough of the deployment/package/credential/manual Trash path to support a controlled demo, but full unattended provisioning plus profile/package/deployment bootstrap still needs one clean end-to-end run in the remote test environment.

The 2026-06-21 documentation pass keeps the first demo deliberately small. Use the broader platform documentation for product background, and use local `USECASE.md` and `USECASE-001-RUNBOOK.md` files only as checkout-local demo recipes.

## Review Findings Added on 2026-05-23

1. Partially completed: monitoring validation now has persisted attempt history, audit events, bounded per-node checks, and resilient snapshot preservation. A full WorkflowRun-backed execution model remains future work.

2. Completed: monitoring validation attempts persist method, duration, result, component state, structured failure reason, and audit-event linkage per node.

3. Rename or deprecate legacy node-level Prometheus fields such as `prometheus_target_health` once API compatibility allows it. Prometheus is a provider-level health check, not a per-node row signal.

4. Clarify Grafana provider UI semantics. Grafana is currently a configured jump-link provider, not a render-time API dependency. Either label it as configured or add optional background reachability checks.

5. Completed: exporter/service validation now stores structured failure reasons such as `tcp_unreachable`, `ssh_auth_failed`, `service_inactive`, `docker_unavailable`, `command_timeout`, and `exporter_missing`.

6. Audit internal Inventory callers after the managed-only default filter change. Historical/discovery reads must request `include_unmanaged=true` explicitly, and execution flows must continue to exclude unmanaged nodes.

7. Remove unused monitoring compatibility fields such as `advanced_metrics_url`, `container_metrics_url`, `prometheus_url`, and `loki_url` after the frontend no longer depends on them.
