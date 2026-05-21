# Build guide — frontend

Implementation checklist for the cleaning UI. Product context: [`architecture.md`](../architecture.md). API reference: backend [`README.md`](../backend/README.md) and live **Swagger** at `http://127.0.0.1:8000/docs`.

Run backend: `uvicorn backend.app.main:app --reload` (from repo root). Set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`.

---

## Product rules (locked)

| Rule | Owner |
|------|--------|
| Analyst **clicks** an anomaly tab to work on it | Frontend |
| Default: **no tab selected**; no Before/After until click | Frontend |
| Three patterns always visible in sidebar (display order: negatives → refunds → double booking) | Frontend |
| Submit with **nothing checked** → no cell updates; “Nothing changed”; clear review UI; tabs unselected | Frontend + Backend (`changes: []`) |
| Submit does **not** auto-switch tabs or advance session | Frontend |
| Any pattern may be opened/accepted in any order | Backend |
| Tab badges from `total_count` (prefetch or after accept) | Frontend |
| After successful Submit, refresh counts for **all three** patterns | Frontend |
| Checkbox selection **before Submit** survives refresh via `sessionStorage` | Frontend |
| Working copy + audit persist on server; resume via `dataset_id` in URL | Backend |

---

## Routes

| Route | Purpose |
|-------|---------|
| `/` | File explorer: upload, list datasets, **Clean** |
| `/clean/[datasetId]` | Cleaning workspace (required for refresh/resume) |

On workspace mount: `POST /datasets/{datasetId}/sessions` → `session_id` (200 resume / 201 create).

---

## Client state

| State | Storage | Notes |
|-------|---------|--------|
| `sessionId`, `datasetId` | URL (`datasetId`) + memory after POST sessions | Resume = same POST |
| `sessionUpdatedAt` | Memory | From latest `GET .../proposals`; send on accept |
| `activePattern` | Memory | `null` default; not persisted across refresh |
| `patternCounts` | Memory | Refetch on workspace load and after Submit |
| `selectedProposalIds` | Memory + **sessionStorage** | See § Selection persistence |
| `proposals`, `offset`, `limit` | Memory | Refetch when tab opens / paginates |

### sessionStorage keys

Persist **in-progress checkbox selection only** (not submitted work).

```ts
// Key: `cleaning-selection:${datasetId}:${pattern}`
// Value: JSON string[] of proposal ids
```

| Event | Action |
|-------|--------|
| Toggle checkbox | Write array to sessionStorage |
| Select all / none (page) | Update sessionStorage |
| Switch tab | Load new key for that pattern; do not carry ids across patterns |
| Change proposal page | **Clear** selection + remove key for that pattern (avoid cross-page submit) |
| Successful Submit | Clear key for that pattern |
| Workspace unmount / leave route | Optional: keep keys until tab close (sessionStorage scope) |

On tab open: after `GET .../proposals`, read sessionStorage for `(datasetId, pattern)` and restore checks **only for ids still present on the current page**.

---

## Build progress

### Setup

- [ ] Next.js app (`package.json`, `next.config`, `tsconfig`)
- [ ] `NEXT_PUBLIC_API_URL`
- [ ] API client in `src/lib/api.ts` (types aligned with `schemas/api.py`)
- [ ] Shared types: `CleaningPattern`, `Proposal`, `AcceptRequest`, etc.

### Journey 1 — File explorer (`/`)

- [ ] `GET /datasets` on load — list name, row_count, uploaded_at
- [ ] Upload CSV — `POST /datasets` multipart `file`
- [ ] Upload errors: empty file, no rows, no periods, invalid numeric (show server detail)
- [ ] Row click + **Clean** → navigate to `/clean/[datasetId]`

### Journey 2 — Workspace shell (`/clean/[datasetId]`)

- [ ] Mount: `POST /datasets/{id}/sessions` → store `session_id`
- [ ] Prefetch counts: 3× `GET /sessions/{id}/steps/{pattern}/proposals?limit=1&offset=0` → `patternCounts`
- [ ] Sidebar: three tabs, badges when `total_count > 0`, muted when `0`
- [ ] **Idle main panel:** “Select an anomaly to review” — no tables, no Submit
- [ ] `activePattern = null` on load and after refresh
- [ ] Header: dataset name, link back to explorer, **Audit** entry point

### Journey 3 — Open pattern

- [ ] Tab click → `activePattern = pattern`
- [ ] `GET .../proposals?limit=10&offset=0` → store `session_updated_at`
- [ ] Main: pattern title + `total_count`
- [ ] Proposal cards: dimensions + Before/After + highlight changed cells
- [ ] Empty pattern: “Nothing to clean for this pattern” when `total_count === 0`
- [ ] Pagination: next/prev; **clear selection** on page change

### Journey 4 — Selection

- [ ] One checkbox per proposal row (= all cell fixes on that row)
- [ ] Select all / Select none — **current page only**
- [ ] Restore from sessionStorage after proposals load (filter to ids on page)
- [ ] Write sessionStorage on every selection change

### Journey 5 — Submit

- [ ] Submit sends `{ proposal_ids, session_updated_at }`
- [ ] **Nothing checked:** `proposal_ids: []` → toast “Nothing changed”; `changes: []`
- [ ] **Some checked:** success + summary from `changes.length` (optional detail list)
- [ ] On success: clear panel, `activePattern = null`, clear selection + sessionStorage for pattern, refresh **all three** counts, store new session timestamp from response flow (refetch proposals next open)
- [ ] **409:** message + refetch proposals for pattern user had open
- [ ] **400** bad proposal id: error + refetch
- [ ] **404:** redirect to explorer
- [ ] Network error: keep tab + selection for retry

### Journey 6 — Refresh / resume

- [ ] Refresh on `/clean/[datasetId]`: POST sessions → same `session_id`; prefetch counts; idle UI
- [ ] Checkbox state: restore from sessionStorage if user reopens same tab (same page)
- [ ] Submitted work: always from server (`cell_values`, audit) — not sessionStorage

### Journey 7 — Audit

- [ ] `GET /sessions/{id}/audit?limit&offset` — paginated table
- [ ] Columns: time, pattern, row, period, before → after; optional group by `submit_id`

---

## UI reference (ASCII)

**Idle (no tab selected):**

```text
┌──────────────────────────────────────────────────────────────┐
│  [← Explorer]   sample.csv                    [Audit]         │
├──────────────┬───────────────────────────────────────────────┤
│  ● Negatives (3)  │  Select an anomaly to review            │
│  ● Refunds (1)    │                                         │
│  ○ Double booking │                                         │
└──────────────┴───────────────────────────────────────────────┘
```

**Tab open:**

```text
│  Negative values · 12 proposals    [Select all] [Select none]  Page 1 → │
│  ☑ Row 1 · Dog / China / Line     Before | After (highlighted cells)      │
│  ☐ Row 4 · ...                                                            │
│  [ Submit ]                                                               │
```

---

## API quick reference

| Method | Path | Use |
|--------|------|-----|
| `GET` | `/health` | Liveness |
| `GET` | `/datasets` | Explorer list |
| `POST` | `/datasets` | Upload CSV (`file`) |
| `POST` | `/datasets/{id}/sessions` | Start/resume cleaning |
| `GET` | `/sessions/{id}/steps/{pattern}/proposals` | `?limit&offset` + `total_count` |
| `POST` | `/sessions/{id}/steps/{pattern}/accept` | Body: `proposal_ids`, `session_updated_at` |
| `GET` | `/sessions/{id}/audit` | Paginated audit |

Patterns: `negatives` | `refunds` | `double_booking` (not `done`).

---

## Out of scope (v1)

- Auth / multi-user
- Full grid in browser
- CSV export download
- Auto-advance to next tab after Submit
- Persist `activePattern` or pagination in URL
- Tutorial copy for detectors

---

## Testing (manual)

- [ ] Upload `data/sample.csv` → appears in list
- [ ] Clean → three tabs with counts; idle main
- [ ] Open negatives → check rows → refresh → checks restored on same page/tab
- [ ] Submit none → “Nothing changed”; idle; counts unchanged
- [ ] Submit some → success; counts update; audit has rows
- [ ] Accept negatives → refunds count may drop (pipeline data)
- [ ] Refresh workspace → same session; idle; prior accepts still in audit
- [ ] 409: stale `session_updated_at` → reload proposals
