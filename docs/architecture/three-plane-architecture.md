# NexusOps Three-Plane Architecture

Created: 2026-08-19

Target architecture for separating the three concerns that currently intercalate
across the platform, and for introducing Terraform/Ansible as execution backends.

## The goal this serves

Templatize a machine completely — users, groups, containers, services, packages,
everything it needs. Deploy it fully from that template. Then operate it from the
UI, so that touching the infrastructure by hand is rarely needed.

Today the platform can do all three, but each capability is split across modules
that also do the other two. `packages` holds both a catalog and an executor.
`deployments` holds a definition, a deploy action, and live container status.
`identity` holds desired users, the replication that creates them, and the
discovery that reads them back. There is no single object that says "this is what
a machine should be", and therefore no way to ask "is this machine still what we
said it should be".

## The three planes

### Planning — what should exist

Pure desired state. Nothing in this plane touches infrastructure.

- **Machine Template** — the new aggregate root. Composes a base image or Proxmox
  template, disks and network, identity sets, packages, containers/services,
  monitoring expectations, and access policy into one versioned object.
- **Component catalogs** — packages, compose/container definitions, identity sets
  (users, groups, permissions), access profiles, provisioning blueprints. These
  already exist; they become Planning-owned and referenced by templates.
- **Parameters** — typed variable schemas with defaults, validation, and
  credential-backed secret references.
- **Versioning** — templates are immutable once published; editing produces a new
  version. Deployments record the exact version they realised.

Planning can render and validate a template without any target, which is what
makes a meaningful preview possible.

### Deployment — making it real, once

Turns desired state into an outcome. Owns the act of change, not the definition
and not the ongoing state.

- **Render** — Template + parameters + target → `ExecutionPlan`.
- **Preview** — the plan, plus a diff against the target's current state when the
  target already exists.
- **Execute** — hand the plan to executors; track every step.
- **Register** — write the resulting machine into Operations, carrying a link back
  to the template and version that produced it.

### Operations — what is actually there, and day-2 work

- **Inventory** of real machines and their live state.
- **Drift** — current observed state versus the template version the machine was
  deployed from. This is the payoff of the separation: it is only expressible once
  desired state and observed state are distinct objects.
- **Access** — shell, files, logs, metrics, monitoring.
- **Day-2 changes** — service restarts, user additions, package updates. Every one
  of these offers two routes: an immediate ad-hoc action, or an edit to the
  template followed by a redeploy. The second route is the one the UI should make
  attractive, because it is the one that keeps drift at zero.
- **Resources** — nodes, hypervisors, storage, lifecycle.

## The connective tissue: ExecutionPlan

One provider-neutral contract sits between Planning and every executor. This is
what makes Terraform and Ansible pluggable rather than a rewrite.

```
ExecutionPlan
  plan_id
  target:      TargetRef          # existing machine, or a spec for a new one
  source:      TemplateRef        # template id + version that produced this
  steps:       [ExecutionStep]

ExecutionStep
  step_id
  kind:        provision | identity | package | container | service | file | command | validate
  desired:     typed payload      # declarative, provider-neutral
  depends_on:  [step_id]
  executor:    ssh | ansible | terraform | proxmox
  idempotency_key
  rollback:    optional step
```

Steps describe *what should be true*, not the commands that make it true. Each
executor knows how to realise the kinds it supports:

| Executor     | Realises                                        |
| ------------ | ----------------------------------------------- |
| `proxmox`    | `provision` (clone, cloud-init, disks, network)  |
| `terraform`  | `provision`, and later other providers           |
| `ansible`    | `identity`, `package`, `service`, `file`         |
| `ssh`        | all kinds — the existing path, and the fallback  |

A capability matrix declares which executor handles which kind, so a template can
be realised by whichever engine is available without changing the template.

The same `ExecutionPlan` object serves both UI audiences: a plain-language summary
for the operator who wants "add a web server", and the expanded step list with
rendered commands or generated HCL/playbooks for the engineer who wants to see
exactly what will run.

## Delivery: incremental strangler

Every phase leaves the platform deployable and green. No long-lived branch.

**Phase 1 — the contract, behind the existing behaviour.**
Introduce `ExecutionPlan` and a renderer. Wrap today's job runtime as
`SshExecutor`. Route existing package/profile/action execution through
plan → executor. No user-visible change; this is the seam everything else hangs
off. Prerequisite for all later phases.

**Phase 2 — Planning plane.**
New `backend/app/planning/` package. Introduce `MachineTemplate` composing
existing catalogs by reference, plus versioning and validation. Existing catalogs
move under Planning; their execution halves stay put for now.

**Phase 3 — Deployment plane.**
Move provisioning, deployments, and profile-apply behind the plan pipeline.
`WorkflowRun` becomes the single execution record for every kind of change.
Add idempotency keys and preview/diff.

**Phase 4 — Operations plane.**
Consolidate inventory, runtime_state, monitoring, and remote_access. Add drift
detection: render the observed plan from a machine, diff against its template
version.

**Phase 5 — `AnsibleExecutor`.**
Highest-value second executor. Identity, packages, services, and files are exactly
what Ansible is best at, and they are the steps most repeated across machines.

**Phase 6 — `TerraformExecutor`.**
Provisioning first, then whatever providers follow.

**Phase 7 — UI rebuild.**
Can start once Phase 2 and 3 APIs are shaped, and proceed in parallel with 4–6.

## Foundational prerequisite: durable execution

The current queue is in-process asyncio tasks with no persistence
(`backend/app/workers/queue/service.py`). A restart abandons in-flight work —
mitigated as of 2026-08-19 by startup reconciliation, but only by marking the
work stale, not by resuming it.

Terraform applies and Ansible playbooks run for minutes, not seconds. Before
Phase 5, execution needs to become durable and resumable, and to survive a
restart or move between processes. This also lifts the current single-instance
ceiling, which the in-process scheduler and rate limiter share.

This is the one item that blocks the engine work, and it is worth doing during
Phase 3 rather than discovering it in Phase 5.

## UI principles

The brief is "understandable for an average user, technical enough for users with
a real background". One pattern serves both, and the `ExecutionPlan` makes it
natural:

- **Three top-level areas** — Plan, Deploy, Operate. Everything belongs to exactly
  one; anything that seems to belong to two is a sign the domain split is wrong
  there.
- **Progressive disclosure over separate modes.** Every action shows a
  plain-language summary by default, with the rendered plan, commands, playbook,
  or HCL one click away. Not a "simple mode" and an "advanced mode" — the same
  object at two zoom levels.
- **Preview before every change.** The diff is the trust-building surface; it is
  what lets an operator act without reaching for the terminal.
- **Drift is a first-class status**, visible on every machine, with "reconcile"
  as the primary action.

## What this replaces

| Today                               | Becomes                                     |
| ----------------------------------- | ------------------------------------------- |
| `packages`, `profiles` (definition) | Planning: component catalogs                |
| `provisioning` blueprints           | Planning: templates                         |
| `deployments` (definition half)     | Planning: container/service components      |
| `identity` (desired half)           | Planning: identity sets                     |
| `jobs`, `workflows`                 | Deployment: plan execution + record         |
| `provisioning` (execution half)     | Deployment: `provision` steps               |
| `deployments` (deploy half)         | Deployment: `container` steps               |
| `identity` (replication half)       | Deployment: `identity` steps                |
| `inventory`, `runtime_state`        | Operations: machines and live state         |
| `monitoring`, `remote_access`       | Operations: observability and access        |
| `credentials`, `variables`, `audit` | Shared platform services, used by all three |
