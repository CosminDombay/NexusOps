# NexusOps Architecture

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
- `CommandExecution`: legacy placeholder for command audit concepts.
- `Deployment`: Docker Compose project definition and state.
- `PackageDefinitionRecord`: persisted package template, including custom packages and editable built-in overrides.
- `InfrastructureProfileRecord`: persisted profile template, including custom profiles and editable built-in overrides.
- `Integration`: persisted provider/monitoring integration metadata and connection-test configuration.
- `PackageInstallation`: package automation execution record.
- `MetricSample`: collected monitoring metric.
- `StandardizationProfile`: reusable users/groups profile.
- `Job`: persisted SSH command/action execution state, output, exit code, and timestamps.

## Infrastructure Adapter Interfaces

- `ProxmoxAdapter`: VM lifecycle boundary.
- `SshAdapter`: remote execution and file transfer boundary.
- `DockerComposeAdapter`: deployment boundary for managed hosts.
- `JobExecutor`: background dispatch boundary.

These contracts keep external system details out of service and API layers, which makes later replacement, testing, and mocking straightforward.

## Current Orchestration Flow

NexusOps now uses Inventory as the execution abstraction:

```text
Inventory -> Jobs / Operational Actions -> SSH adapter -> managed Linux host
```

Proxmox remains a provider discovery and lifecycle-control layer. Jobs and operational actions execute only against inventory-managed servers.

Identity follows the same orchestration boundary:

```text
Access profile / group preset / permission preset
  -> Identity replication
  -> Jobs
  -> SSH adapter
  -> inventory-managed Linux host
```

Identity is not centralized authentication. It is Linux user, group, SSH key, sudoers.d, and filesystem permission orchestration with guided presets and advanced Linux controls.

## Inventory Synchronization Flow

```text
Proxmox discovery
  -> managed/unmanaged synchronization status
  -> optional operator import
  -> Inventory provider linkage
  -> reconciliation status
  -> Jobs / Packages / Profiles
```

Inventory lifecycle and infrastructure lifecycle are separate concerns. Deleting or archiving an Inventory record does not destroy a Proxmox VM.

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
