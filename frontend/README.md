# Frontend (Next.js)

Folders are laid out for the **App Router** convention. You do **not** need `create-next-app` to create this tree — but when you add dependencies, either:

1. Run `npx create-next-app@latest .` **inside this directory** (it will merge with existing folders), or  
2. Add `package.json`, `next.config.ts`, and `tsconfig.json` manually.

Point the dev server at the FastAPI backend (e.g. `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`).

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
