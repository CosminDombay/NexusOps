# Operational Runtime Experience

NexusOps treats runtime visibility as an operational product surface, not a side effect of execution. Jobs remain the atomic runtime authority, while workflows, deployments, profiles, packages, and automations explain why work was requested and how related work fits together.

## Ownership Boundaries

- Job: atomic execution unit and persisted SSH/action runtime authority.
- Workflow: orchestration visibility coordinator for ordered or grouped execution.
- Deployment: stateful application lifecycle coordinator for Docker Compose operations.
- Profile: reusable orchestration recipe that resolves into package/action/raw-command execution.
- Package: reusable executable definition that resolves into Jobs.
- Automation: scheduling and triggering layer for operational work.

Domains may add context, summaries, and timelines, but they should not invent independent execution truth when a Job already owns that runtime detail.

## Activity Timeline

Runtime activity is represented with a shared operational timeline shape. Timeline entries are built from existing persisted runtime data and correlation metadata so backend APIs can explain execution without requiring websocket infrastructure.

Current timeline sources include:

- job execution lifecycle and output events
- workflow run and step state
- deployment execution and target execution state
- profile workflow-backed execution metadata
- automation-triggered runtime metadata

Timeline entries should preserve correlation identifiers, status, timestamps, duration, target context, job links, and human-readable operational reasoning when available.

## Runtime Explainability

Backend services are responsible for describing operational reasons such as:

- execution failed
- execution skipped
- execution cancelled
- execution degraded
- eligibility blocked execution

Frontend views should render those reasons consistently instead of reinterpreting backend state. The shared frontend runtime helpers and timeline component keep status labels, duration formatting, event ordering, and metadata display aligned across Jobs, Workflows, and Deployments.

## Cancellation Semantics

Cancellation should be modeled as intent plus lifecycle state. Orchestration domains should propagate cancellation to owned child work where possible and then summarize the final state from runtime-owned records.

Expected behavior:

- workflows mark active/pending steps coherently
- deployments stop scheduling further target work once cancellation is observed
- profile execution preserves `stop_on_failure` and cancellation-aware step summaries
- jobs remain the lowest-level runtime cancellation authority

## Future Streaming Readiness

The current model intentionally remains polling/read-refresh friendly. The timeline and runtime metadata conventions prepare NexusOps for future live updates by standardizing event shape and correlation first, without adding event buses, distributed workers, or websocket infrastructure during this pass.

## Validation Notes

Runtime changes should be validated with:

- backend tests for lifecycle aggregation and runtime metadata
- frontend lint/build for shared runtime components
- manual review of Jobs, Workflows, and Deployments pages
- migration head checks when runtime persistence models change
