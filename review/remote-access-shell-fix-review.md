# Remote Access Shell Fix Review

## 1. Failure Context

The Access tab shell was opening a browser WebSocket to the backend remote shell route and then immediately reporting:

```text
Shell connection failed.
Shell session closed.
```

In the Docker production-style frontend build, `VITE_API_BASE_URL` is `/api/v1`, so the shell WebSocket uses the same frontend origin and reaches the backend through `frontend/nginx.conf`.

## 2. Root Cause

The Nginx `/api/` proxy handled normal HTTP requests, but it did not forward WebSocket upgrade headers. REST API calls could keep working while WebSocket handshakes failed before the terminal reached the connected state.

## 3. Code Written

### `frontend/nginx.conf`

Added the standard WebSocket connection mapping before the server block:

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    '' close;
}
```

Updated the `/api/` proxy to support WebSocket upgrades and long-lived shell sessions:

```nginx
location /api/ {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection $connection_upgrade;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_buffering off;
}
```

### `frontend/src/features/remote-access/components/ShellPanel.tsx`

Kept the existing error path, but made close events visible in the terminal:

```tsx
ws.onclose = (event) => {
  setStatus((current) => (current === 'error' ? 'error' : 'closed'));
  const reason = event.reason ? ` ${event.reason}` : '';
  const code = event.code ? ` (code ${event.code})` : '';
  terminal.current?.writeln(`\r\nShell session closed${code}.${reason}`);
};
```

This helps distinguish proxy-level handshake failures from backend/SSH failures such as policy close codes, host key mismatch, missing credentials, or target SSH refusal.

## 4. Review Notes

- The backend route remains `/api/v1/remote-access/hosts/{server_id}/shell`.
- The frontend WebSocket URL builder remains unchanged; with Docker it correctly targets `/api/v1/...` on the frontend origin and relies on Nginx proxying.
- No database models or Alembic migrations were changed.
- The change is intentionally scoped to the remote shell transport path and terminal diagnostics.

## 5. Validation Targets

- `cd frontend && npm run lint` - passed
- `cd frontend && npm run build` - passed
- `DEBUG=false .venv/bin/python -m pytest backend/tests/test_remote_access.py` - passed, 9 tests
- `docker run --rm --entrypoint nginx --add-host backend:127.0.0.1 -v "$PWD/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" nginx:1.27-alpine -t` - passed
- Manual smoke test: rebuild/restart the frontend container, open a managed host Access tab, click Connect, and confirm the terminal reaches `Connected.` or reports a specific backend close code/reason.
