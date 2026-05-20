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

## Cleaning workspace (navigation)

See [`architecture.md`](../architecture.md) §4.1.1 and [`backend/tobuild.md`](../backend/tobuild.md).

| Behavior | Implementation |
|----------|----------------|
| Default | No anomaly tab selected; no Before/After |
| Open a pattern | User clicks sidebar tab → `GET .../proposals` |
| Tab badges | Prefetch `total_count` per pattern (3 proposal calls or a future summary endpoint); style tab when count > 0 |
| Submit, nothing checked | `POST .../accept` with `[]` → show “nothing changed”; clear panel; deselect all tabs |
| Submit, some checked | Apply fixes; success message; clear panel; deselect tabs; refresh counts (all patterns if working copy changed) |
| Order | Sidebar order = negatives → refunds → double booking (display only). User may accept in any order. |
| After Submit | **Do not** auto-switch to the next tab |

### Suggested client state

```ts
activePattern: 'negatives' | 'refunds' | 'double_booking' | null
patternCounts: Record<CleaningPattern, number>
selectedProposalIds: string[]  // reset when activePattern changes or after Submit
```

Backend session has **no** `current_step` — only `session_id` for API calls and audit.
