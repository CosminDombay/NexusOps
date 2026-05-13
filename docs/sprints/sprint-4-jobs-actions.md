# Sprint 4: Jobs, SSH Execution, and Operational Actions

## Goal

Implement the first operational orchestration backbone for NexusOps.

This sprint moves the platform beyond visibility by allowing inventory-managed Linux hosts to receive SSH-backed commands and predefined operational actions while preserving centralized job history.

## Backend Implementation

Implemented under:

```text
backend/app/modules/jobs/
backend/app/adapters/ssh/
```

Jobs backend capabilities:

- persisted `jobs` table
- job status lifecycle:
  - pending
  - running
  - success
  - failed
  - cancelled
- raw command execution endpoint
- job history endpoint
- job detail endpoint
- placeholder cancel endpoint
- operational action registry
- operational action execution endpoint

SSH execution capabilities:

- Paramiko-backed command execution
- key authentication
- password authentication
- stdout/stderr/exit code capture
- command timeout configuration

## API Endpoints

Jobs endpoints:

```text
GET /api/v1/jobs
GET /api/v1/jobs/{job_id}
POST /api/v1/jobs/execute
POST /api/v1/jobs/{job_id}/cancel
GET /api/v1/jobs/actions
POST /api/v1/jobs/actions/execute
```

## Operational Actions

Initial predefined actions:

- Check System Uptime
- Check Disk Usage
- Check Memory Usage
- Check Docker Containers
- Check Docker Service
- Restart Docker Service
- Install Docker Engine
- Install Tailscale
- Install Node Exporter

Actions are intentionally lightweight command/script definitions. They reuse the Jobs execution pipeline instead of introducing a separate automation engine.

## Frontend Implementation

Implemented under:

```text
frontend/src/features/jobs/
```

The Jobs page now includes:

- target inventory host selector
- predefined operational action selector
- destructive action confirmation
- raw command runner
- job history table/cards
- stdout/stderr result viewer

## Architecture Decision

Inventory remains the orchestration abstraction layer:

```text
Inventory -> Jobs / Actions -> SSH -> Host
```

Proxmox remains a discovery/provider layer. NexusOps does not execute directly against raw Proxmox VM entries.

## Non-Goals

Not implemented in this sprint:

- authentication/RBAC
- Ansible
- Terraform
- provisioning
- realtime websocket updates
- Celery/Redis/background workers
- Docker Compose uploads
- monitoring ingestion
- encrypted secret vaults
- workflow chaining

## Validation

Validation covered:

- backend tests
- frontend lint
- frontend build
- Alembic migration execution
- local API smoke tests for `/api/v1/jobs`

## Status

Sprint 4 is implemented as the first real orchestration capability. Future modules should reuse Jobs and operational actions instead of implementing standalone SSH execution paths.
