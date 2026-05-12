# Development Notes

## Local Services

- Frontend dev server: `cd frontend && npm run dev`
- Backend API: `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
- PostgreSQL: `docker compose -f infra/docker-compose.dev.yml up -d postgres`

## Validation

- Frontend build and TypeScript: `cd frontend && npm run build`
- Frontend lint: `cd frontend && npm run lint`
- Backend tests: `.venv\Scripts\python.exe -m pytest backend\tests`
- Migrations: set `DATABASE_URL`, then run `.venv\Scripts\python.exe -m alembic upgrade head`

## Architecture

- Backend module routers are the canonical API surface under `backend/app/modules/*/router.py`.
- Shared API wiring belongs in `backend/app/api/v1/router.py`.
- Infrastructure boundaries live under `backend/app/adapters/` as abstract contracts only until provider implementations are added.
