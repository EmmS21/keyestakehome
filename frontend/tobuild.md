# Build guide — frontend

Implementation checklist for the cleaning UI. **Wireframe source of truth (layout & states):** [`docs/design/wireframes/cleaning-workspace.html`](../docs/design/wireframes/cleaning-workspace.html). Product rules: [`architecture.md`](../architecture.md). API: backend [`README.md`](../backend/README.md) · Swagger `http://127.0.0.1:8000/docs`.

Run backend: `uvicorn backend.app.main:app --reload` (repo root). Set `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`.

---

## Wireframe → pages map

| Artboard | Route | Page / state | Build under |
|----------|-------|--------------|-------------|
| **1** | `/` | Explorer — empty (upload CTA, no rows) | § Page: File Explorer |
| **2** | `/` | Explorer — loaded (dataset table + Clean) | § Page: File Explorer |
| **3** | `/` | Explorer — upload error banner | § Page: File Explorer |
| **4** | `/clean/[datasetId]` | Workspace — **idle** (no tab selected; audit toggle closed) | § Page: Cleaning Workspace |
| **5** | `/clean/[datasetId]` | Workspace — **pattern open** (Before \| After tables, infinite scroll) | § Page: Cleaning Workspace |
| **6** | `/clean/[datasetId]` | Workspace — **empty pattern** (tab open, `total_count === 0`) | § Page: Cleaning Workspace |
| **7** | `/clean/[datasetId]` | Workspace — **idle + toast** (after Submit) | § Page: Cleaning Workspace |
| **8** | `/clean/[datasetId]` | Workspace — **audit sidebar open** (with rows) | § Page: Cleaning Workspace |
| **9** | `/clean/[datasetId]` | Workspace — **audit sidebar open** (empty) | § Page: Cleaning Workspace |

**Implementation order (wireframe note):** start with artboards **4** and **5**, then 6–9, then Explorer 1–3.

---

## Product rules (locked)

| Rule | Owner |
|------|--------|
| Analyst **clicks** an anomaly tab to work on it | Frontend |
| Default: **no tab selected**; no Before/After until click | Frontend |
| Three patterns always visible in sidebar (order: negatives → refunds → double booking) | Frontend |
| Submit with **nothing checked** → no cell updates; toast **“Nothing changed”**; clear review UI; tabs unselected | Frontend + Backend (`changes: []`) |
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
| `activePattern` | Memory | `null` default; **not** persisted across refresh |
| `patternCounts` | Memory | Refetch on workspace load and after Submit |
| `selectedProposalIds` | Memory + **sessionStorage** | See § Selection persistence |
| `proposals`, `offset`, `hasMore` | Memory | Append on infinite scroll; refetch when tab opens |
| `auditOpen` | Memory (optional) | Sidebar hidden by default (artboard 4) |
| `auditEntries`, `auditOffset` | Memory | Infinite scroll in audit sidebar |

### sessionStorage keys

Persist **in-progress checkbox selection only** (not submitted work).

```ts
// Key: `cleaning-selection:${datasetId}:${pattern}`
// Value: JSON string[] of proposal ids
```

| Event | Action |
|-------|--------|
| Toggle checkbox | Write array to sessionStorage |
| Select all / none (loaded rows) | Update sessionStorage |
| Switch tab | Load key for that pattern; do not carry ids across patterns |
| **Load more** proposals (infinite scroll) | **Keep** selection; merge new rows into list |
| Successful Submit | Clear key for that pattern |
| Workspace unmount / leave route | Keys remain until tab close (`sessionStorage` scope) |

On tab open: after first `GET .../proposals`, restore checks from sessionStorage **only for ids still in the loaded list**.

---

## Visibility & edge cases (subset)

Use this as a QA matrix; full manual tests at bottom.

### File Explorer (`/`)

| # | Condition | Visible UI |
|---|-----------|------------|
| E1 | Initial load, `GET /datasets` empty | Artboard **1**: upload zone prominent; “No datasets yet…” |
| E2 | Datasets returned | Artboard **2**: table + secondary upload in header |
| E3 | `GET /datasets` loading | Table skeleton or spinner; disable Clean until row known |
| E4 | `GET /datasets` failed | Error banner; retry affordance |
| E5 | Upload in flight | Upload zone loading style (wireframe CSS `.loading`) |
| E6 | Upload 4xx (validation) | Artboard **3**: inline `banner.error` with server `detail`; list unchanged |
| E7 | Upload network error | Error banner; allow retry |
| E8 | Invalid `datasetId` on Clean N/A | N/A here — navigation only with listed ids |

### Cleaning workspace — shell & sidebar

| # | Condition | Visible UI |
|---|-----------|------------|
| W1 | Mount / refresh | Artboard **4**: idle main; **no** active tab; prefetch badges |
| W2 | `POST /sessions` loading | Full-page or shell skeleton; sidebar disabled |
| W3 | `POST /sessions` 404 | Redirect to `/` |
| W4 | `total_count > 0` | Badge with count; tab not `.muted` |
| W5 | `total_count === 0` | Muted tab + muted badge `0` (artboard 4, 6) |
| W6 | Counts not yet loaded | Tabs visible without badge or placeholder `—` (avoid flash of wrong active state) |
| W7 | User clicks tab | That tab `.active`; main leaves idle (artboard 5 or 6) |
| W8 | User clicks same tab again | No-op or refetch (optional); stay on pattern |
| W9 | User clicks another tab | Switch pattern; load proposals from offset 0; restore sessionStorage for new pattern |

### Cleaning workspace — proposals (artboard 5)

| # | Condition | Visible UI |
|---|-----------|------------|
| P1 | Proposals loading (first page) | Skeleton in compare area (wireframe `.skeleton-table`) |
| P2 | `total_count > 0`, rows on page | Before \| After tables; header `N rows with issues` uses `total_count` |
| P3 | `total_count === 0`, tab open | Artboard **6**: “Nothing to clean for this pattern”; no Submit |
| P4 | More pages available | Infinite scroll: append rows; “Loading more…” while fetching |
| P5 | All proposals loaded | “End of list — all N rows loaded” (wireframe `list-end-marker`) |
| P6 | Before table | Checkbox column; anomaly cells highlighted (dark) |
| P7 | After table | No checkbox; fix cells highlighted (gray + outline) |
| P8 | Row checked | `row-checked` styling on both table rows |
| P9 | Select all / none | Affects **currently loaded** rows only |
| P10 | Scroll Before/After | Panels stay in sync (implementation detail) |

### Cleaning workspace — Submit & toast (artboard 7)

| # | Condition | Visible UI |
|---|-----------|------------|
| S1 | Submit, zero checkboxes | Toast **“Nothing changed”**; idle; counts unchanged |
| S2 | Submit, some checked, success | Toast **“Applied N changes”** (`N = changes.length`); idle; badges refresh |
| S3 | Toast visible | Idle prompt hidden (`.has-toast`); overlay on main |
| S4 | Toast auto-close | ~5s countdown; then dismiss |
| S5 | Toast × click | Dismiss immediately |
| S6 | Submit 409 stale session | Error toast; refetch proposals for pattern user had open |
| S7 | Submit 400 bad proposal id | Error toast; refetch proposals |
| S8 | Submit 404 session | Redirect to explorer |
| S9 | Submit network error | Error toast; **keep** tab + selection for retry |
| S10 | After any successful Submit | `activePattern = null`; clear compare UI; clear sessionStorage for that pattern |

### Cleaning workspace — audit sidebar (artboards 8–9)

| # | Condition | Visible UI |
|---|-----------|------------|
| A1 | Default | Sidebar hidden; toggle `aria-pressed="false"` |
| A2 | Toggle on | Right sidebar 340px; toggle filled/active (artboard 8) |
| A3 | Toggle or header × | Hide sidebar; main expands |
| A4 | First open, fetch | Table headers; loading row if empty fetch |
| A5 | Entries exist | Columns: time, pattern, row label, period, before → after |
| A6 | Scroll to end | “End of audit log — all N changes loaded” |
| A7 | No entries | Artboard **9**: “No changes yet” (not an error) |
| A8 | Load more while scrolling | “Loading more…” in tbody |
| A9 | Footer hint | “Scroll up for newer entries” when data present |

### Cross-cutting

| # | Condition | Expected behavior |
|---|-----------|-------------------|
| X1 | Refresh on `/clean/[id]` | Same session via POST; idle UI; counts from server |
| X2 | sessionStorage after refresh | Restored when user reopens same tab (loaded ids only) |
| X3 | Accept negatives then open refunds | Refund count may drop (pipeline); badges reflect refetch |
| X4 | Audit open during Submit | Sidebar can stay open; new rows appear on next audit fetch |
| X5 | Deep link `/clean/[badId]` | 404 → explorer |

---

## Build checklist by page

### Shared / setup

- [x] Next.js app (`package.json`, `next.config`, `tsconfig`)
- [x] `NEXT_PUBLIC_API_URL`
- [x] API client in `src/lib/api.ts` (explorer + workspace)
- [x] Shared types: `CleaningPattern`, `Proposal`, `AcceptRequest`, `AuditEntry`, etc. (`src/lib/types.ts`)
- [x] App chrome: header styles, buttons, banners (toast + `list-end-marker` with workspace)
- [x] Wireframe link in dev README (already in `frontend/README.md`)
- [x] Playwright E2E harness (`playwright.config.ts`, `e2e/explorer.spec.ts`, `e2e/workspace.spec.ts`)

---

### Page: File Explorer — route `/` (artboards 1–3)

**Layout:** `app/page.tsx` + `src/components/ExplorerPage.tsx`

- [x] **1 — Empty:** title “Data Cleaning Tool”; primary upload zone; empty copy when no datasets
- [x] **2 — Loaded:** `GET /datasets` → table columns Name, Rows, Uploaded, **Status**; **Clean** per row
- [x] **2 — Loaded:** header **Upload CSV** when table visible + upload zone
- [x] **3 — Error:** error `banner` above upload (server `detail`)
- [x] Upload: `POST /datasets` multipart `file`; `.csv` only in copy
- [x] Upload errors: empty file, no rows, no periods, invalid numeric → show server message (E6)
- [x] Duplicate filename blocked (client + API 409)
- [x] **Status:** Unchanged / Modified via audit log (`POST` session + `GET` audit `total_count`)
- [x] **Clean** → `router.push(/clean/${datasetId})`
- [x] **Export** per row → `GET /datasets/{id}/export` (working copy CSV download)
- [x] Loading / failure states (E3–E4, E5–E7)
- [x] E2E: `e2e/explorer.spec.ts` (3 specs: empty state, upload, navigate to clean)

---

### Page: Cleaning Workspace — route `/clean/[datasetId]` (artboards 4–9)

**Layout:** `app/clean/[datasetId]/page.tsx` + child components under `src/components/`

#### Shell & header (all workspace artboards)

- [x] Mount: `POST /datasets/{id}/sessions` → `session_id` (W2–W3)
- [x] Prefetch: 3× `GET .../proposals?limit=1&offset=0` → `patternCounts` (W4–W6)
- [x] Header: `← Explorer` link, dataset **name**, **Audit log** toggle (clipboard icon + label)
- [x] Audit toggle: `aria-pressed`, `aria-label`, filled style when open (A1–A2)

#### Sidebar — anomaly tabs (artboards 4–7)

- [x] Three equal-height tabs: Negative values, Refunds, Double booking (W1)
- [x] Badge from `total_count`; muted tab when `0` (W4–W5)
- [x] **Idle:** no `.active` tab (artboard 4)
- [x] Tab click → set `activePattern`; fetch proposals `limit=10&offset=0` (W7, W9)

#### Main panel — idle (artboards 4, 7)

- [x] **4 — Idle:** centered “Select an anomaly to review”; no tables; no Submit (W1)
- [x] `activePattern = null` on load, refresh, and after successful Submit (S10)
- [x] **7 — Toast:** overlay on idle main; hide idle prompt while toast visible (S3–S5)
- [x] Toast variants: “Nothing changed” | “Applied N changes” | error message (S1–S2, S6–S9)

#### Main panel — pattern open (artboards 5–6)

- [x] **5 — Header:** pattern title + subtitle `{total_count} rows with issues`
- [x] Toolbar: **Select all** / **Select none** (loaded rows only) (P9)
- [x] **5 — Compare:** side-by-side **BEFORE** | **AFTER** tables (not card list)
- [x] Dimension columns + period columns from proposal payload
- [x] Before: checkbox column; highlight anomaly cells (P6)
- [x] After: no checkbox; highlight fix cells (P7)
- [x] Row hover / checked styles (P8)
- [x] Legend line + **Submit** button (submit-row)
- [x] **6 — Empty:** “Nothing to clean for this pattern”; hide Submit (P3)
- [x] Infinite scroll: increase `offset`, append proposals (P4–P5)
- [x] Sync scroll between Before/After panels (P10)
- [x] Store `session_updated_at` from proposals response

#### Selection (artboard 5)

- [x] One checkbox per proposal row (= all cell fixes on that row)
- [x] sessionStorage read/write per § Client state
- [x] Do **not** clear selection when loading more rows (only on tab switch / Submit)

#### Submit flow (artboards 5 → 7)

- [x] `POST .../accept` body: `{ proposal_ids, session_updated_at }`
- [x] Empty `proposal_ids` → S1
- [x] Success → S2, S10; refetch all three pattern counts
- [x] 409 / 400 / 404 / network → S6–S9

#### Audit sidebar (artboards 8–9)

- [x] Collapsible right panel ~340px; hidden by default (A1)
- [x] `GET /sessions/{id}/audit?limit&offset` on open and on scroll (A4–A8)
- [x] Table columns per wireframe (A5)
- [x] Empty: “No changes yet” (A7)
- [x] End marker when all entries loaded (A6)
- [x] Footer: “Scroll up for newer entries” when non-empty (A9)
- [x] Close via toggle or × in sidebar header (A3)

- [x] E2E: `e2e/workspace.spec.ts` (8 specs: idle, pattern, submit, selection, empty, audit, redirect)

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
| `GET` | `/sessions/{id}/audit` | Paginated audit (`limit`/`offset`; UI uses infinite scroll) |

Patterns: `negatives` | `refunds` | `double_booking` (not `done`).

---

## Out of scope (v1)

- Auth / multi-user
- Full deal grid in browser (only proposal rows shown)
- ~~CSV export download~~ (explorer Export button + `GET /datasets/{id}/export`)
- Auto-advance to next tab after Submit
- Persist `activePattern`, audit open state, or scroll position in URL
- Tutorial copy for detectors
- Separate `/audit` route (audit lives in workspace sidebar per wireframe)

---

## Manual test plan

- [ ] Upload `data/sample.csv` → appears in explorer (artboard 2)
- [ ] Clean → artboard 4 idle; three badges; no Before/After
- [ ] Open negatives → artboard 5; check rows; refresh → checks restored for loaded ids
- [ ] Scroll load more → selection kept; end marker when done
- [ ] Submit none → “Nothing changed” toast; idle (artboard 7 variant)
- [ ] Submit some → “Applied N changes”; counts update; idle
- [ ] Open audit → rows match accepts (artboard 8); empty on new session (artboard 9)
- [ ] Accept negatives → refunds count may drop
- [ ] Refresh workspace → same session; idle; audit still on server
- [ ] Stale `session_updated_at` → 409 → error toast + proposal refetch
