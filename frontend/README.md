# Frontend (Next.js)

Folders are laid out for the **App Router** convention. You do **not** need `create-next-app` to create this tree — but when you add dependencies, either:

1. Run `npx create-next-app@latest .` **inside this directory** (it will merge with existing folders), or  
2. Add `package.json`, `next.config.ts`, and `tsconfig.json` manually.

Point the dev server at the FastAPI backend (e.g. `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`).

## Layout

| Path | Purpose |
|------|---------|
| `app/` | Routes, layouts (`page.tsx`, `layout.tsx`) |
| `src/components/` | UI: tables, sidebar, proposal cards |
| `src/lib/` | API client, types shared with backend responses |
| `public/` | Static assets |

## Build guide

Implementation checklist and UX rules: [`tobuild.md`](tobuild.md).

Low-fidelity wireframes: [`docs/design/wireframes/cleaning-workspace.html`](../docs/design/wireframes/cleaning-workspace.html).

API reference: [`backend/README.md`](../backend/README.md) · Swagger UI at `http://127.0.0.1:8000/docs` (with backend running).
