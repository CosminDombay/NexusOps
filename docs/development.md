# Development Notes

## Local Services

- Frontend dev server: `cd frontend && npm run dev`
- Backend API: `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000`
- PostgreSQL: `docker compose -f infra/docker-compose.dev.yml up -d postgres`

Typical local startup after schema changes:

```powershell
docker compose -f infra/docker-compose.dev.yml up -d postgres
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

If the browser reports a CORS/API failure but `/api/v1/health` works, check PostgreSQL first. Database connection failures surface as `500` responses from data-backed endpoints and can look like CORS failures in the browser.

## Validation

- Frontend build and TypeScript: `cd frontend && npm run build`
- Frontend lint: `cd frontend && npm run lint`
- Backend tests: `.venv\Scripts\python.exe -m pytest backend\tests`
- Migrations: set `DATABASE_URL`, then run `.venv\Scripts\python.exe -m alembic upgrade head`

## Architecture

- Backend module routers are the canonical API surface under `backend/app/modules/*/router.py`.
- Shared API wiring belongs in `backend/app/api/v1/router.py`.
- Infrastructure boundaries live under `backend/app/adapters/` as abstract contracts only until provider implementations are added.
