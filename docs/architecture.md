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

- `Server`: Linux host inventory and connection state.
- `VirtualMachine`: VM request and Proxmox provider mapping.
- `CommandExecution`: legacy placeholder for command audit concepts.
- `Deployment`: Docker Compose project definition and state.
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
