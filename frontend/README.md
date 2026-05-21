# Frontend (Next.js)

App Router UI for the data cleaning tool. Point the dev server at the FastAPI backend (`NEXT_PUBLIC_API_URL`, default `http://127.0.0.1:8000`).

## Run locally

```bash
# Terminal 1 — API (repo root)
uvicorn backend.app.main:app --reload

# Terminal 2 — UI
cd frontend
cp .env.local.example .env.local   # optional if default URL is fine
npm install
npm run dev
```

Open http://127.0.0.1:3000

## E2E tests (Playwright)

Requires the API running on port 8000.

```bash
cd frontend
npm install
npx playwright install chromium
npm run test:e2e
```

Coverage includes: explorer upload and navigation, workspace patterns/submit/audit, session resume after reload and in a new browser context. Helpers live in `e2e/helpers.ts`.

## Layout

| Path | Purpose |
|------|---------|
| `app/` | Routes, layouts (`page.tsx`, `layout.tsx`) |
| `src/components/` | UI: tables, sidebar, proposal cards |
| `src/lib/` | API client, types shared with backend responses |
| `public/` | Static assets |

## Wireframes

Low-fidelity UI reference: [`docs/design/wireframes/cleaning-workspace.html`](../docs/design/wireframes/cleaning-workspace.html).

API reference: [`backend/README.md`](../backend/README.md) · Swagger UI at `http://127.0.0.1:8000/docs` (with backend running).
