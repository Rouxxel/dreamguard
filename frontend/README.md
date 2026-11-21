# DreamGuard Dashboard

React + Vite + TypeScript dashboard for the DreamGuard backend.

| Page | What it shows |
|---|---|
| **Live** | Simulator cameras (MJPEG), run controls (scripted / replay; live Dream-1 is locked while paid calls are disabled), fault injection, safety metrics, risk per chunk, decision feed with the reasons for each decision, joint targets vs limits |
| **Sessions** | Recorded sessions with their metrics; step through every decision; replay a session through the guard |
| **Safety profile** | The active limits (read-only) |

Live data arrives on the backend WebSocket (`/ws/events`); REST calls use TanStack Query.

## Development

Requires Node 22 and a running backend (`cd backend && python main.py`).

```powershell
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api and /ws to http://127.0.0.1:8000)
```

Set `DREAMGUARD_BACKEND` to proxy to another backend URL.

## Checks

```powershell
npm run typecheck
npm run lint
npm test
npm run build        # dist/, served by the backend at http://127.0.0.1:8000/dashboard/
```

## API types

`src/api/schema.d.ts` is generated from the backend's OpenAPI schema. After changing the API:

```powershell
cd backend; python export_openapi.py      # writes frontend/openapi.json
cd ../frontend; npm run gen:api           # regenerates src/api/schema.d.ts
```

A backend test fails when `frontend/openapi.json` no longer matches the API.

## Dependencies

Versions are pinned exactly and were at least 7 days old when chosen. TypeScript stays on 5.9
(`typescript-eslint` and `openapi-typescript` do not support newer majors yet) and `jsdom` on 29
(newer majors require Node 22.22+).
