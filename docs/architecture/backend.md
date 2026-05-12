# Backend Architecture

## Overview

The backend is a FastAPI application organized as a modular monolith. Business domains live under `backend/app/modules`, while shared platform concerns live under `backend/app/core`, `backend/app/db`, `backend/app/common`, and `backend/app/adapters`.

## FastAPI Application

Application construction happens in `backend/app/main.py`.

Responsibilities:

- configure structured logging
- create the FastAPI app
- configure CORS
- register the versioned API router
- expose OpenAPI under the configured API prefix

The API prefix is controlled by `settings.api_v1_prefix`, currently defaulting to `/api/v1`.

## API Routing

The main versioned router is `backend/app/api/v1/router.py`.

Current routing pattern:

- `health` is imported from `backend/app/api/v1/routes/health.py`
- domain routers are imported from module folders
- module routers are the canonical source of domain API behavior

Current implemented domain routes include:

- `/api/v1/servers` for inventory
- `/api/v1/proxmox` for read-only Proxmox visibility

Placeholder routers exist for future modules such as provisioning, deployments, packages, monitoring, profiles, jobs, and execution, but they do not yet implement real workflows.

## Module Organization

Backend modules follow a consistent shape:

```text
backend/app/modules/<domain>/
  models.py
  schemas.py
  repository.py
  service.py
  router.py
  tasks.py
```

Not every file is fully implemented yet. Inventory is the first complete database-backed module. Proxmox is implemented as a read-only external integration module.

## Repository-Service Pattern

Inventory follows the primary repository-service architecture:

- `router.py` handles HTTP concerns and maps domain exceptions to HTTP responses.
- `service.py` owns workflow orchestration and business rules.
- `repository.py` owns persistence queries.
- `schemas.py` defines Pydantic request/response contracts.
- `models.py` defines SQLAlchemy persistence models.

This keeps HTTP logic, business logic, and database access separate.

## Async SQLAlchemy

Database access uses SQLAlchemy asyncio.

Key files:

- `backend/app/db/base.py`
- `backend/app/db/session.py`

`session.py` creates an async engine from `settings.database_url` and exposes `get_db_session()` as a FastAPI dependency. Repositories receive an `AsyncSession` and execute SQLAlchemy statements asynchronously.

Inventory commits are currently performed in the service layer after repository operations. This keeps transaction control close to workflow orchestration.

## Migrations

Alembic is configured at the repository root through `alembic.ini` and migration code under `backend/migrations`.

The current migration creates the `servers` table and related indexes/constraints.

Important migration characteristics:

- imports model metadata in `backend/migrations/env.py`
- uses async migration execution
- targets `Base.metadata`
- supports PostgreSQL enum types for server environment and status

## Configuration

Configuration is defined in `backend/app/core/config.py` using Pydantic Settings.

Configuration sources:

- environment variables
- `.env` file when present
- defaults in the settings class

Important settings include:

- `API_V1_PREFIX`
- `CORS_ORIGINS`
- `DATABASE_URL`
- `PROXMOX_API_URL`
- `PROXMOX_TOKEN_ID`
- `PROXMOX_TOKEN_SECRET`
- `PROXMOX_VERIFY_SSL`
- `PROXMOX_TIMEOUT_SECONDS`

Proxmox secrets are not committed. They should be supplied by local environment variables or an ignored `.env`.

## Structured Logging

Logging is configured in `backend/app/core/logging.py` with `structlog`.

The inventory service and Proxmox adapter use structured log events for successful operations and failure paths.

## Proxmox Backend Flow

```mermaid
sequenceDiagram
  participant UI as Frontend
  participant API as FastAPI Router
  participant Service as ProxmoxService
  participant Adapter as HttpProxmoxAdapter
  participant PVE as Proxmox API

  UI->>API: GET /api/v1/proxmox/dashboard
  API->>Service: get_dashboard()
  Service->>Adapter: get_nodes()
  Adapter->>PVE: GET /nodes
  PVE-->>Adapter: node data
  Service->>Adapter: list_vms()
  Adapter->>PVE: GET /cluster/resources?type=vm
  PVE-->>Adapter: VM data
  Service-->>API: normalized dashboard response
  API-->>UI: JSON
```

## Current Backend Boundaries

The backend currently mutates only NexusOps-owned database state. Infrastructure integrations, including Proxmox, are read-only.
