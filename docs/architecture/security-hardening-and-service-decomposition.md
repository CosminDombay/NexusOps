# Security Hardening And Service Decomposition

This note records the incremental refactor and hardening pass for NexusOps orchestration services. The pass preserves the current API contracts, database schema, and lightweight runtime architecture.

## Goals

- reduce service god-object pressure
- centralize lifecycle transition rules
- harden command execution boundaries
- redact secrets before persistence
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

## JSON Field Review

The following JSON fields remain intentionally flexible for now, but have TODO markers for future typed-column migration:

- `jobs.runtime_metadata`
- `jobs.output_events`
- `workflow_runs.context_json`
- `workflow_runs.result_summary`
- `workflow_steps.metadata_json`
- `deployment_executions.result_summary`

Recommended future typed columns include execution owner, correlation ID, target counters, job linkage, stable runtime metadata keys, and high-volume runtime event storage.

## Remaining Technical Debt

- Move helper classes into dedicated files once decomposition pressure increases.
- Replace local execution owner markers with distributed execution leases.
- Add duplicate execution prevention for deployments and profile runs.
- Add typed runtime event persistence before websocket or event-stream work.
- Expand transition tests for deployment target/revision execution states.
- Install backend dev tooling locally so Ruff can run outside CI.

## Validation

The hardening pass was validated with:

- backend test suite
- backend import compilation
- frontend lint
- frontend build/typecheck
- Alembic single-head check
- whitespace hygiene check

No destructive migrations were introduced.
