# Security Hardening And Service Decomposition

This note records the incremental refactor and hardening pass for NexusOps orchestration services. The pass preserves the current API contracts, modular monolith boundaries, and lightweight runtime architecture while adding production-aware safety foundations.

## Goals

- reduce service god-object pressure
- centralize lifecycle transition rules
- harden command execution boundaries
- redact secrets before persistence
- add production startup guardrails
- rotate refresh tokens and persist session metadata
- replace remote shell JWT query authentication with scoped one-time tokens
- add SSH host-key trust foundations
- add baseline public-exposure protections for future Tailscale Funnel use
- keep orchestration behavior stable
- document remaining production-readiness work

## Service Decomposition

The pass keeps the existing service entry points intact while extracting responsibility-focused helpers:

- `ProfileExecutionService` coordinates profile apply flow.
- `WorkflowTransitionManager` owns workflow and step transition timestamp behavior.
- `WorkflowSummaryBuilder` owns workflow derived read-model summaries.
- `DeploymentStatusRollupService` owns deployment status aggregation.
- `DeploymentExecutionCoordinator` marks local deployment execution ownership.

The services still expose the same public methods. The helper classes are intentionally lightweight so larger file-level decomposition can happen later without changing API behavior.

## Production Configuration Guardrails

`backend/app/core/config.py` now treats `development`, `staging`, and `production` as explicit environments.

Development remains homelab-friendly and emits structured startup warnings for unsafe local defaults. Production startup fails if:

- `SECRET_KEY` is still the default value
- `DEBUG=true`
- `NEXUSOPS_MASTER_KEY` is missing
- Proxmox TLS verification is disabled
- the bootstrap admin password looks like a default credential

`CORS_ORIGINS` accepts either JSON array syntax or comma-separated origins. `ENABLE_OPENAPI=false` can hide Swagger/OpenAPI in production.

## Session Security

Refresh tokens now have persisted session metadata in `refresh_token_sessions`:

- token ID and family ID
- token hash
- issued and expiry timestamps
- revoked and last-used timestamps
- inactivity tracking
- optional source IP and user agent

Every refresh rotates the refresh token and revokes the previous token. Reuse of a revoked token is treated as replay and revokes the whole token family. Access tokens include a session ID, so current-session logout can invalidate the session without forcing every other session to log out. `/auth/logout-all` remains available for full account session revocation.

The frontend still uses the existing token-storage abstraction to preserve the current UX. This keeps a clean migration path toward httpOnly refresh cookies later.

## Lifecycle Transition Guards

Workflow and deployment transitions now use centralized validators:

- `VALID_WORKFLOW_TRANSITIONS`
- `VALID_WORKFLOW_STEP_TRANSITIONS`
- `VALID_DEPLOYMENT_TRANSITIONS`

Invalid transitions such as `success -> running`, `cancelled -> success`, and `failed -> queued` are rejected through explicit domain exceptions.

Jobs already had runtime transition validation. This pass brings workflows and deployments closer to the same lifecycle discipline.

## Command Execution Hardening

`SafeCommandBuilder` provides shared command validation and variable interpolation safety.

Current protections:

- rejects dangerous shell-control tokens in interpolated variable values
- detects `;`, `&&`, `||`, `$(`, backticks, and newline chaining
- shell-quotes safe interpolated values
- preserves legitimate package and deployment scripts
- logs rejected unsafe interpolation attempts

This keeps built-in operational scripts usable while narrowing the highest-risk injection path: user-provided variables inserted into shell templates.

`CommandPolicyEngine` adds a lightweight policy result for command governance:

- `allowed`
- `approval_required`
- `denied`

The current rules detect destructive patterns such as `rm -rf`, `mkfs`, `shutdown`, `reboot`, `docker system prune`, and `terraform destroy`. Approval hooks are intentionally minimal for now and can be expanded without changing the Jobs API shape.

Raw job requests no longer trust client-supplied redaction. Server-side execution flows may still pass redacted command snapshots when they generated them internally after resolving secrets. Jobs now also store immutable execution metadata: actual command, display command, command hash, command policy result, initiator metadata, correlation ID, and append-only `job_execution_events`.

Custom operational action create/update/delete routes are admin-only. Operators can still execute approved actions.

## Secret Redaction

`SecretSanitizer`, `redact_sensitive_text()`, and `redact_sensitive_value()` centralize redaction.

Redaction now applies before persistence for:

- job stdout/stderr/output events
- audit metadata and audit errors
- workflow logs, errors, and metadata
- deployment revision output and redacted environment snapshots
- deployment target execution output and error messages

Sensitive values include common token/password/API-key shapes, bearer tokens, SSH private keys, and explicit credential values resolved during execution.

## Runtime Safety

Deployment executions now carry a lightweight local execution owner marker in `result_summary`. This is not a distributed lock. It is a preparatory marker for future execution leases and multi-worker safety.

Jobs remain the atomic runtime authority. Profiles, packages, workflows, automations, and deployments continue to delegate host execution through Jobs.

## Remote Access Hardening

Remote shell WebSockets no longer use the active JWT as the query token. The frontend now requests a one-time remote-access token before opening the shell. The token is:

- short-lived
- one-time use
- bound to user, server, operation, role, and session
- consumed during WebSocket authentication

Remote-access token metadata is persisted in `remote_access_tokens` for auditability and future cleanup jobs.

SSH host-key handling no longer uses Paramiko `AutoAddPolicy`. Remote access has a trust-on-first-use fingerprint foundation:

- first accepted fingerprints are stored on the Inventory server record
- later mismatches fail the connection
- manual fingerprint approval is available through the remote-access service API
- host-key approval is audited

The lower-level Jobs SSH adapter also rejects unknown host keys unless local trust-on-first-use is enabled for development.

## Public Exposure Readiness

The backend now adds baseline protections suitable for later Tailscale Funnel exposure:

- login rate limiting
- API burst limiting
- shell-token rate limiting
- security headers: CSP, HSTS in production, `X-Frame-Options`, and `X-Content-Type-Options`
- structured rate-limit logging

The limiter is intentionally in-process. It is a foundation for controlled deployments, not a distributed edge-rate-limit system.

## JSON Field Review

The following JSON fields remain intentionally flexible for now, but have TODO markers for future typed-column migration:

- `jobs.runtime_metadata`
- `jobs.output_events`
- `job_execution_events`
- `refresh_token_sessions`
- `remote_access_tokens`
- `workflow_runs.context_json`
- `workflow_runs.result_summary`
- `workflow_steps.metadata_json`
- `deployment_executions.result_summary`

Recommended future typed columns include execution owner, correlation ID, target counters, job linkage, stable runtime metadata keys, and high-volume runtime event storage.

## Remaining Technical Debt

- Move helper classes into dedicated files once decomposition pressure increases.
- Replace local execution owner markers with distributed execution leases.
- Add duplicate execution prevention for deployments and profile runs.
- Expand typed runtime event persistence before websocket or event-stream work.
- Expand transition tests for deployment target/revision execution states.
- Install backend dev tooling locally so Ruff can run outside CI.
- Add a cleanup task for expired refresh sessions and remote-access tokens.
- Add a fuller approval workflow for `approval_required` command policy decisions.

## Validation

The hardening pass was validated with:

- backend test suite
- backend import compilation
- frontend lint
- frontend build/typecheck
- Alembic single-head check
- whitespace hygiene check

No destructive migrations were introduced.
