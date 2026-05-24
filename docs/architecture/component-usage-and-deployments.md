# Component Usage And Deployment Guide

This guide explains how the main NexusOps operational components fit together and how to use them to prepare, deploy, inspect, and troubleshoot infrastructure work.

## Core Flow

Most operational work follows this path:

1. Add or import inventory-managed hosts.
2. Configure credentials and integrations as needed.
3. Define reusable packages, profiles, or deployment definitions.
4. Execute work through Jobs, Profiles, Workflows, Deployments, or Automations.
5. Review job output, workflow steps, deployment target history, and runtime timelines.

Jobs are the runtime execution authority. Higher-level domains coordinate, schedule, group, or explain work, but executable host operations should resolve back into Jobs.

## Inventory

Inventory is the target abstraction for operational work. A host must be inventory-managed before Jobs, Packages, Profiles, Deployments, Identity actions, or Remote Access should operate against it.

Setup checklist:

- create or import the host
- set management state to managed
- configure SSH host, port, user, and authentication metadata
- attach credential references when password, SSH key, or secret-backed execution is needed
- verify the host appears in target selectors and host detail views

## Credentials

Credentials store encrypted values used by operational components. They can hold SSH passwords, SSH keys, API tokens, environment secrets, and provider tokens.

Use credentials for:

- SSH execution against inventory hosts
- Docker Compose environment variables
- Proxmox provider integration records
- package/profile variables that should not be typed into commands directly

Credential values are masked in API responses. Keep local environment keys and `.env` files out of commits.

## Jobs And Host Tools

Jobs execute predefined actions or raw commands against inventory hosts. They capture status, stdout, stderr, exit code, runtime metadata, output events, and duration.

Use Jobs for:

- diagnostics
- one-off commands
- predefined operational actions
- package/profile/deployment execution history
- troubleshooting lower-level runtime failures

After execution, inspect the job result viewer and timeline before looking at higher-level orchestration summaries.

## Packages

Packages define reusable installation or configuration commands with optional variables. Built-in packages can be cloned or reset to defaults, while custom packages are user-managed.

Use packages when a single reusable executable unit should run against one host, such as installing Docker Engine, Tailscale, Node Exporter, Promtail, Fail2Ban, or UFW.

Setup checklist:

- choose a built-in package or create a custom package
- define variables for values that differ per execution
- keep template substitution simple with `{{ variable_name }}`
- execute through the package page, profile step, provisioning bootstrap, or automation

## Profiles

Profiles are reusable orchestration recipes made of package, action, and raw-command steps. They preserve variable resolution, credential handling, bulk execution behavior, and `stop_on_failure` semantics.

Use profiles when multiple steps should be applied together, such as a base Linux server setup, Docker host setup, monitoring node setup, or development VM bootstrap.

Operational notes:

- profile steps still execute through Jobs internally
- optional workflow-backed execution can provide workflow and step visibility
- profile execution should be reviewed through job links, profile summaries, and workflow timeline when present

## Workflows

Workflows coordinate operational visibility across steps. They are not a replacement for Jobs; they explain ordered work and step state.

Use workflows when you need:

- lifecycle visibility for grouped execution
- step-level status tracking
- linked job visibility
- operational timeline review
- future-friendly orchestration traceability

## Deployments

Docker Compose deployments coordinate stateful application lifecycle operations across one or more inventory targets.

Use deployments for:

- deploy
- redeploy
- restart
- stop
- status
- logs

Setup checklist:

- create the deployment definition
- provide Docker Compose content or the expected deployment payload
- configure deployment variables and secret-backed environment values
- add target inventory hosts
- run deploy or redeploy
- review deployment execution, per-target history, linked jobs, and timeline

Deployment operations should preserve revision history, target execution records, status aggregation, and Jobs runtime ownership.

## Automations

Automations schedule or trigger operational work. They can run predefined actions, custom actions, packages, or profiles.

Use automations for recurring operational tasks where manual execution would be repetitive. Review automation execution visibility together with linked Jobs and any profile/workflow metadata.

## Monitoring And Runtime State

Monitoring and runtime state surfaces provide readiness and operational context. Use them before and after execution to understand whether a node is eligible, stale, degraded, or missing expected exporters/logging.

Operational readiness should be interpreted from backend-provided state and blockers rather than frontend-only guesses.

## Deployment Troubleshooting

When a deployment fails:

1. Open the deployment execution and target execution history.
2. Follow linked job records for stdout, stderr, and exit code.
3. Check the operational timeline for ordering, duration, skipped steps, and cancellation.
4. Verify inventory SSH metadata and credentials.
5. Validate Docker availability on the target host.
6. Check credential-backed environment variables and rendered Compose inputs.
7. Re-run status or logs before redeploying.

When a profile or package fails, start from the linked job output and then review the higher-level profile or workflow summary.
