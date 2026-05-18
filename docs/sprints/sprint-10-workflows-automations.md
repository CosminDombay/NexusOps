# Sprint 10 - Workflow Engine and Scheduled Automations

## Objective

Sprint 10 establishes the persistent orchestration foundation for NexusOps:

- workflow runs
- workflow steps
- workflow logs
- scheduled automations
- in-process async task dispatch
- APScheduler startup/shutdown
- frontend workflow and automation visibility

## Implemented

- Added `workflow_runs` and `workflow_steps`.
- Added Workflow status lifecycle:
  - pending
  - queued
  - running
  - success
  - failed
  - cancelled
- Added WorkflowStep status lifecycle:
  - pending
  - running
  - success
  - failed
  - skipped
- Added workflow list/detail API:
  - `GET /api/v1/workflows`
  - `GET /api/v1/workflows/{id}`
- Added workflow service operations:
  - create/start/complete/fail/cancel workflow
  - add/start/complete/fail step
  - append step logs
- Added `automations` persistence.
- Added automation API:
  - `GET /api/v1/automations`
  - `POST /api/v1/automations`
  - `PUT /api/v1/automations/{id}`
  - `DELETE /api/v1/automations/{id}`
  - `POST /api/v1/automations/{id}/run`
  - `POST /api/v1/automations/{id}/enable`
  - `POST /api/v1/automations/{id}/disable`
- Added initial supported automation operations:
  - predefined action
  - custom operational action
  - package execution
  - profile execution
- Added custom operational action persistence and API support.
- Added custom action create/update/delete UI on Jobs.
- Added automation edit and delete controls.
- Added APScheduler-backed startup/shutdown foundation.
- Hardened scheduler startup against APScheduler versions where next-run metadata is unavailable before scheduler start.
- Added in-process async task queue.
- Added frontend Workflows page.
- Added workflow target hostnames in workflow step/run views.
- Added frontend Automations page.
- Added Operations navigation links for Workflows and Automations.
- Added host detail tab links for Automations and Workflows.

## Current Execution Flow

```text
Automation trigger
  -> WorkflowRun created
  -> WorkflowRun marked queued
  -> async task submitted
  -> WorkflowRun marked running
  -> WorkflowStep created per target host
  -> Job/Profile/Package service executes
  -> WorkflowStep stores logs/job IDs
  -> WorkflowRun completes or fails
```

## Deliberate MVP Boundaries

- No Celery.
- No Redis.
- No WebSockets.
- No DAG/branching engine.
- No nested workflows.
- No arbitrary raw-command automations yet; operators can use custom operational actions as the reusable command/script wrapper.
- No deployment automations yet.
- Existing direct provisioning/profile/package/deployment endpoints still need deeper async workflow refactors.

## Follow-Up Work

- Move direct provisioning request execution fully into WorkflowRun background execution.
- Move direct deployment operations fully into WorkflowRun background execution.
- Add workflow IDs to provisioning/deployment/profile/package API responses.
- Add polling links from domain pages into workflow detail views.
- Add retry semantics.
- Add cancellation semantics for long-running provider/SSH work where technically possible.
- Add workflow filtering by target host and type.
