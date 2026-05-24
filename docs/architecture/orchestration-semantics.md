# Orchestration Semantics

NexusOps uses a lightweight orchestration control-plane model. The domains should remain cohesive and avoid competing ownership of execution runtime state.

## Domain Hierarchy

- Job: atomic execution unit. Owns SSH transport execution, output capture, exit code, runtime metadata, cancellation intent, and output events.
- Workflow: orchestration coordinator. Owns multi-step visibility, step ordering, linked job references, and user-facing timeline semantics.
- Deployment: stateful application lifecycle orchestration. Owns compose content, deployment targets, revisions, target execution history, and deployment status rollups.
- Profile: reusable orchestration recipe. Owns profile step resolution and sequencing, then delegates execution to packages, deployments, or jobs.
- Package: reusable executable definition. Owns package command and variable resolution, then delegates execution to jobs.
- Automation: scheduling and triggering layer. Owns schedules and trigger context, then coordinates execution through workflows.

## Runtime Ownership

Jobs are the runtime source of truth for command execution. Workflow, deployment, profile, package, and automation services may reference jobs, summarize jobs, and expose linked job IDs, but they should not duplicate transport lifecycle semantics.

Workflows are the visibility source of truth for coordinated orchestration runs. Automations should create workflow runs for scheduled work. Profiles may create workflow runs when a workflow service is provided, while preserving direct job execution internally.

Deployments may maintain deployment-specific execution and revision records because they represent stateful application lifecycle history. Those records should summarize job-backed execution rather than replace job runtime authority.

## Lifecycle Vocabulary

Use shared lifecycle predicates from `backend/app/modules/orchestration/semantics.py` when translating domain statuses into operational meaning.

- Pending: accepted but not actively executing.
- Active: queued, dispatched, running, or domain-specific in-progress state.
- Success: completed successfully, including legacy `completed` where applicable.
- Failure: failed terminal states.
- Cancelled: explicitly cancelled terminal states.
- Stale: execution lost ownership or exceeded runtime expectations.

Domain-specific status names may remain when they carry product meaning, such as deployment `draft`, `deploying`, `running`, `stopped`, `partial_success`, and `degraded`. Translation into runtime meaning should be centralized.

## Metadata and Events

Runtime metadata should consistently include:

- `execution_origin`
- `operation_type`
- `correlation_id` when available
- `target_hostname` and `target_server_id` when available
- `transport` for transport-owned execution

Output events remain owned by job runtime. Other domains should store references and summaries, not reimplement stream semantics.

## Guardrails

- Do not add distributed workers, external brokers, or cloud orchestrators to solve local cohesion problems.
- Do not make packages or profiles bypass the Jobs runtime.
- Do not make automations execute work without workflow visibility.
- Do not use workflows as a replacement for deployment revision history.
- Prefer small semantic helpers over broad abstraction layers.
