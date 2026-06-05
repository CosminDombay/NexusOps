# NexusOps Architecture

For the latest living platform state, validation status, and technical debt, see `docs/architecture/current-state.md`.

Focused operational references:

- `docs/api.md`: compact API surface overview.
- `docs/architecture/orchestration-semantics.md`: orchestration ownership and lifecycle terminology.
- `docs/architecture/operational-runtime-experience.md`: runtime timeline, explainability, and cancellation semantics.
- `docs/architecture/security-hardening-and-service-decomposition.md`: transition guards, command safety, secret redaction, and decomposition notes.
- `docs/architecture/component-usage-and-deployments.md`: practical component usage and deployment setup guide.

## Folder Structure

```text
NexusOps/
  backend/
    app/
      api/v1/routes/        API versioning and HTTP route modules
      adapters/             Provider and protocol interfaces
      common/               Shared schemas and repository base types
      core/                 Configuration and logging
      db/                   SQLAlchemy base and async sessions
      modules/              Business modules in the modular monolith
    migrations/             Alembic environment and versions
    tests/                  Backend tests
  frontend/
    src/
      app/                  React application shell and routing
      components/           Shared UI components
      features/             Feature-oriented frontend modules
      lib/                  API clients and shared utilities
      styles/               Global styling
  infra/                    Local development infrastructure
```

## Backend Organization

Each backend domain module is structured around the same boundary:

- `models.py` contains SQLAlchemy persistence models.
- `schemas.py` contains Pydantic API contracts when needed.
- `repository.py` owns database access.
- `service.py` owns application workflow orchestration.

API routes call services, services coordinate repositories and adapters, repositories use SQLAlchemy sessions, and adapters hide external systems such as Proxmox, SSH, and Docker.

## Frontend Organization

The frontend is organized by feature rather than technical layer. Pages for inventory, provisioning, deployments, packages, monitoring, profiles, and jobs live under `src/features`. Shared shell components and API clients remain outside feature folders.

## Suggested Database Entities

- `Server`: CMDB inventory record, Linux host connection state, provider linkage, lifecycle state, and synchronization status.
- `VirtualMachine`: VM request and Proxmox provider mapping.
- `ProvisioningBlueprint`: NexusOps-side provisioning preset around a Proxmox VM or LXC template.
- `DeploymentExecution`: deployment runtime instance for an orchestration run.
- `DeploymentTargetExecution`: per-node deployment runtime state and output summary.
- `CommandExecution`: legacy placeholder for old command audit concepts; active remote execution uses `Job`.
- `Deployment`: Docker Compose project definition and target configuration.
- `PackageDefinitionRecord`: persisted package template, including custom packages and editable built-in overrides.
- `InfrastructureProfileRecord`: persisted profile template, including custom profiles and editable built-in overrides.
- `Integration`: persisted provider/monitoring integration metadata and connection-test configuration.
- `PackageInstallation`: package automation execution record.
- Monitoring readiness records: derived telemetry availability, stale metrics, exporter detection, and provider health.
- `StandardizationProfile`: reusable users/groups profile.
- `Job`: persisted SSH command/action execution state, output, exit code, and timestamps.

## Infrastructure Adapter Interfaces

- `ProxmoxAdapter`: hypervisor, VM, LXC, provisioning, and controlled lifecycle boundary.
- `SshAdapter`: remote execution and file transfer boundary.
- `DockerComposeAdapter`: deployment boundary for managed hosts.
- `JobExecutor`: background dispatch boundary.

These contracts keep external system details out of service and API layers, which makes later replacement, testing, and mocking straightforward.

## Current Orchestration Flow

NexusOps now uses Inventory as the execution abstraction:

```text
Managed node Inventory -> Jobs / Deployments / Identity / Remote Access / Monitoring -> adapters -> managed infrastructure
```

Proxmox remains a provider discovery and lifecycle-control layer. Hypervisors, VMs, LXCs, and future physical hosts become distinct managed nodes before NexusOps operates on them. Jobs and operational actions execute only against inventory-managed records.

Provisioning follows the same authority boundary:

```text
Provisioning blueprint
  -> Proxmox VM template clone/cloud-init or LXC template create
  -> Inventory registration
  -> optional profile/package bootstrap
  -> Jobs
  -> SSH adapter
  -> inventory-managed Linux host
```

Blueprints are NexusOps UI/API presets; provider-side VM and LXC templates still live in Proxmox.

Deployments follow the same runtime separation:

```text
Deployment definition
  -> Compose validation / dry-run preview
  -> DeploymentExecution
  -> DeploymentTargetExecution per node
  -> Jobs
  -> SSH adapter
  -> inventory-managed Linux host
```

Deployment environment secrets and execution/sudo credentials are separate. Credential-backed env refs render into `.env` at execution time, while execution credentials feed SSH/sudo for Docker commands when needed. Runtime reads include stale state, runtime age, failure reason, missing services, and container state. Deleting a deployment record does not yet remove machine-side Compose services; discovery/adoption and explicit destructive removal remain future work.

Monitoring follows the same managed-node convergence:

```text
Telemetry provider integrations
  -> Prometheus/Loki/Grafana readiness checks
  -> per-node observability state
  -> Monitoring board and managed-node pages
```

Grafana is optional deep-analysis tooling. NexusOps does not own Grafana dashboard generation or dashboard-per-node lifecycle.

Identity follows the same orchestration boundary:

```text
Access profile / group preset / permission preset
  -> Identity replication
  -> Jobs
  -> SSH adapter
  -> inventory-managed Linux host
```

Identity is not centralized authentication. It is Linux user, group, SSH key, sudoers.d, and filesystem permission orchestration with guided presets and advanced Linux controls. Discovered users/groups can be adopted into managed records, and selected password/SSH-password credentials can be passed through Jobs for sudo-backed replication.

## Inventory Synchronization Flow

```text
Proxmox discovery
  -> hypervisor/VM/LXC synchronization status
  -> automatic hypervisor reconciliation and optional guest import
  -> Inventory provider linkage
  -> reconciliation status
  -> Jobs / Packages / Profiles / Deployments / Monitoring / Identity
```

Inventory lifecycle and infrastructure lifecycle are separate concerns. Deleting, archiving, or decommissioning an Inventory record removes it from active NexusOps orchestration by default; provider-side destructive operations must remain explicit and provider-specific.

## Template Automation Flow

Packages and profiles are reusable operational templates:

```text
Built-in system template
  -> optional persisted editable override
  -> optional clone into user-managed template
  -> execution-time variable resolution
  -> Jobs
  -> SSH adapter
  -> inventory-managed Linux host
```

Built-in defaults remain recoverable. Editing a built-in package/profile creates or updates a persisted working copy with metadata such as `is_builtin`, `is_modified`, `base_version`, `source_template_id`, and `modified_at`. Resetting a built-in discards that override and restores the code-defined default without altering Jobs history.

Template variables use simple `{{ variable_name }}` substitution only. NexusOps intentionally does not implement Jinja, arbitrary Python templating, Terraform runtime, Ansible runtime, or a workflow engine in this phase.
