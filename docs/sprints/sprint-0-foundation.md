# Sprint 0: Foundation

## Goal

Create the initial NexusOps platform foundation: project structure, backend/frontend scaffolding, development infrastructure, architecture boundaries, and tooling.

## Implemented Work

### Repository Structure

The project was organized into:

- `backend/` for FastAPI and domain modules
- `frontend/` for React/Vite/TypeScript
- `infra/` for local infrastructure
- `docs/` for architecture and workflow documentation

### Backend Foundation

The backend established:

- FastAPI app factory and startup wiring
- versioned `/api/v1` router
- CORS middleware
- Pydantic Settings configuration
- structured logging with `structlog`
- async SQLAlchemy base/session setup
- Alembic migration environment
- modular monolith folder layout
- shared repository base
- placeholder domain modules

### Frontend Foundation

The frontend established:

- React with TypeScript
- Vite
- TailwindCSS
- React Router
- shared app layout
- shared page header
- feature-oriented folder structure
- Axios API client

### Infrastructure Foundation

Local development infrastructure includes Docker Compose support for PostgreSQL and frontend/backend containers.

### Tooling Stabilization

Stabilization work added:

- ESLint 9 flat config
- Prettier config
- `.editorconfig`
- improved `.gitignore`
- cleanup of generated artifacts
- lightweight developer notes in `docs/development.md`

## Architecture Decisions

- Use a modular monolith rather than microservices.
- Keep domain modules self-contained.
- Use repository-service separation for database-backed workflows.
- Use adapters for external infrastructure boundaries.
- Keep frontend code feature-based rather than purely layer-based.
- Keep Proxmox and other infrastructure integrations behind backend APIs.

## Validation

Foundation validation includes:

- backend tests
- frontend lint
- frontend build
- backend startup
- Alembic migration execution

## Status

Sprint 0 is complete as a working foundation. Several domain modules remain placeholders by design.
