# Data Cleaning Tool — Architecture

Design document for the take-home: what we build, for whom, and why. This is the mental model before implementation.

---

## 1. Problem statement

Analysts upload **transaction-style datasets** (dimension columns + time-series revenue columns). The tool detects known anomaly **patterns**, proposes **fixes**, and lets the user **accept all, some, or none** of the proposals for the **current pattern**. On Submit, the server updates only changed cells in the working copy and appends an **audit log** entry per change. The next pattern runs on that updated state in **fixed pipeline order**, because upstream cleaning can change what downstream detectors see.

The product is an end-to-end system: upload → pick dataset → clean step-by-step → persist progress → audit what changed. Deal extracts can be **large** (many rows × many periods); the full grid stays on the **server** ([Keye](https://www.keye.co/)-style diligence: raw files in, audit-ready outputs out).

---

## 2. End user

### 2.1 Primary persona

**Private equity diligence analyst** preparing revenue or transaction extracts for analysis. This is the only user we design for.

| Trait | Implication for the product |
|--------|------------------------------|
| Knows what negatives, refunds, and double bookings mean | No explanatory copy in the UI; pattern names and highlights are enough |
| Trusts algorithms but not blindly | Subset selection (not only all/none); can skip a step entirely |
| Works in sessions, sometimes interrupted | Persist working copy + session state; resume later |
| Needs defensibility | Audit log: what changed, when, which pattern, which rows/cells |
| Cares about totals / netting | Fixes should preserve intent where stated (e.g. double booking splits sum) |

We **do not** assume they write code or configure detection rules. They **do** assume responsibility for which proposals to accept.

### 2.2 Nature of the data (why we design this way)

Diligence data in this space ([Keye](https://www.keye.co/) — raw deal files → cleaned, auditable outputs) has a consistent shape and set of constraints. Our architecture follows from that, not from “take-home size.”

| Property of the data | What it implies for the product |
|----------------------|----------------------------------|
| **Raw exports** from portfolio companies (Excel/CSV): customer, product, geo, **monthly revenue columns** | Wide grids: few dimension cols, many period cols (`202401`, `202402`, …). |
| **High row counts** per deal (transaction / customer lines), **many periods** | Files are **long × wide**; total cell count is large even when anomalies are sparse. |
| **One row ≈ one business line**; fixes are **per row / per cell** | Detectors scan row-by-row; accepts patch specific cells; no cross-row magic in v1. |
| **Anomalies are sparse, detection is not** | Refunds and double-booking require reading **all periods on a row**; we must scan the full grid on the server, not sample detection. |
| **Human sign-off** on each anomaly class, **audit-grade trail** | Immutable upload + append-only change log + Excel-ready export; analyst must see **what** changed, not just a “cleaned” blob. |
| **Interrupted workflows** (days per deal) | Persist working copy and step; resume without re-upload. |

**In one line:** deal revenue grids are **large, wide, and defensibility-critical** — so the server holds truth, the UI sees pages and deltas, and every accept is logged.

### 2.3 Explicit assumptions beyond the brief

1. **One human, one dataset at a time** — no real-time collaboration.
2. **Deal-scale by default** — per §2.2; not optimized for tiny demo files only.
3. **Schema is stable per file** — leading columns are dimensions (`A`, `B`, `C`, …); remaining columns are periods (`YYYYMM` or similar labels).
4. **Each row is independent** — detectors run per row; cross-row rules out of scope ([`docs/limitations.md`](docs/limitations.md)).
5. **Pipeline order is visible, not enforced** — sidebar lists patterns in recommended order (negatives → refunds → double booking); the analyst may open and accept **any** pattern in any order. Fixing cells still changes what other detectors see on the working copy.
6. **“Clean” is idempotent for a finished dataset** — re-running on already-cleaned data may yield zero proposals (empty state is valid).
7. **One anomaly at a time in the UI** — the user views exactly **one** pattern when they choose a tab. Default: **no tab selected** (no Before/After). Tabs stay visible; the frontend indicates which patterns have issues (e.g. color/badge from `total_count`).

### 2.4 Non-negotiables (scale)

Technical rules that follow from §2.2. v1 scope — not deferred.

| Rule | Why (tied to the data) |
|------|-------------------------|
| **Full grid on server only** | Grids are too large for the browser; diligence tools process raw files server-side. |
| **Streamed upload → batched DB insert** | Deal CSVs can exceed comfortable RAM on ingest. |
| **Chunked detectors** | Must scan every row eventually; chunking avoids loading the whole deal into memory at once. |
| **Paginated proposals** + `total_count` | Analysts need **context** (a page of examples) and **scope** (how many issues exist) — not every Before/After at once. |
| **Delta Submit** | Most cells unchanged; only accepted fixes should drive writes. |
| **Paginated audit** | Trail grows per deal over days; fits “what did we change?” without huge responses. |
| **Streamed export** | Output is the same wide CSV shape analysts expect in Excel. |
| **Working copy in DB** (`cell_values`) | Large grid + multi-day sessions; truth cannot live in process memory. |

**Out of scope for v1:** job queues, sharding, read replicas, proposal cache tables. Known design boundaries: [`docs/limitations.md`](docs/limitations.md).

---

## 3. Data model

### 3.1 Logical shape

```
Row {
  dimensions: { A, B, C, ... }   // categorical / keys
  periods: { "202401": number, "202402": number, ... }
}
```

- **Numeric columns** = all period columns (not dimensions).
- **Working copy** = mutable dataset updated only when the user submits accepts for a pattern (whichever tab they used).
- **Original upload** = immutable reference for audit (“before” at upload time; per-step “before” is state at step entry).

### 3.2 Sample data

See `data/sample.csv` for dev and demos.

Layout: dimension columns `A`, `B`, `C`, then month columns (`202401`, `202402`, …).

---

## 4. Anomaly patterns (given — we implement, not redefine)

All detection rules come from the brief. We **do not** invent or document alternate logic (including refunds). The UI never explains refund vs negative; it only shows proposals from these rules.

| Pattern | Detection (given) | Proposed fix (from brief / diagrams) |
|---------|-------------------|--------------------------------------|
| **Negative values** | Any period value `< 0` | Set cell to `0` |
| **Refunds** | Any **N** consecutive periods where **sum == 0** | Set those N cells to `0` (netting out) |
| **Double booking** | `avg(M_i, M_{i+1}) == M_i / 2` (signature: spike + empty/zero neighbor) | Replace both cells with their average; **sum preserved** |

**Note:** Refund vs negative is a **detector distinction**, not something the user configures. Detectors always run on the **current** working copy, so accepted fixes on one pattern affect proposals on another.

### 4.1 Pipeline order (data dependency, not navigation)

Recommended **sidebar order** (for display only):

```
Negative values → Refunds → Double booking
```

**Why order still matters for data (example from diagram):**

- If `-200` is accepted → `0`, a pair like `200` + `-200` may **no longer** sum to zero → refund proposals for that row can **disappear**.
- The analyst may still open **Refunds** before **Negatives**; the server does not block it. They see proposals based on whatever is in `cell_values` today.

### 4.1.1 Navigation and one anomaly at a time (UI)

- Sidebar lists all patterns (in recommended order). **Nothing is selected by default.**
- User **clicks** a tab to open that pattern → main panel loads Before/After for that pattern only.
- **Submit does not change tabs.** After Submit, the UI clears the review panel and leaves tabs unselected (default).
- **Submit with none checked:** working copy unchanged; show a short “nothing changed” message; no Before/After until they pick a tab again.
- Frontend uses `total_count` per pattern (from proposals API) for tab styling (e.g. color when issues exist).
- Backend serves `GET .../proposals?pattern=...` for **any** pattern; no server-side “current step” or auto-advance.

### 4.2 What the user checks off (one checkbox per table row)

Matches the diagram: each **dataset row** shown in Before/After gets **one checkbox**. Checking it means “apply every highlighted fix on this row for the current pattern.”

| Pattern | What we find on that row | What accept does |
|---------|--------------------------|------------------|
| **Negative values** | Any month cells `< 0` | Set each of those cells to `0` |
| **Refunds** | Whatever the given rule flags on that row (N consecutive periods, sum = 0) | Set those periods to `0` per brief |
| **Double booking** | Whatever the given rule flags on that row (adjacent pair) | Set both to their average |

Each proposal stores: which dataset row, which cells change, before/after values, highlight info.

**Refunds:** implement `N consecutive periods where sum == 0` as provided — no extra spec in this doc.

---

## 5. Core user journeys

### 5.1 Happy path

1. User uploads file(s) → appear in a **file explorer** list.
2. User selects a dataset → **Clean** (no need to know anomalies exist upfront).
3. Tool loads data, initializes working copy, opens cleaning workspace. Sidebar shows all patterns; tabs may show which have issues; **no tab selected** yet.
4. User **clicks** e.g. **Negative values** → main area: **Before | After** for a **page of proposals** (`total_count` shows how many exist).
5. User selects proposals (subset / all / none) via **checkboxes** on each row plus **Select all** / **Select none**.
6. User **Submit** → apply accepted proposals to working copy → feedback → review panel clears; tabs unselected (user picks next tab when ready).
7. User may click **Refunds** or **Double booking** in any order; repeat review/submit.
8. User can leave and return; **audit log** shows cell-level changes per pattern.

### 5.2 Empty / complete states

- **No proposals for a pattern (when tab open):** calm empty state on that tab (“Nothing to clean for this pattern”).
- **Export:** available when the user wants the current working copy (not gated on “all steps done” in the DB).

### 5.3 Reject / partial accept

- **Submit with none selected** = no cell updates; UI “nothing changed”; working copy unchanged; **no** auto-switch tab; optional refresh of that pattern’s `total_count`.
- **Subset** = only selected proposals applied.

---

## 6. Features we will build (and why)

### 6.1 Must-have (take-home scope)

| Feature | Why |
|---------|-----|
| **File upload + explorer** | Entry point; matches “select dataset then clean” |
| **Cleaning workspace** | Single place for before/after review |
| **Pattern sidebar (ordered)** | All tabs visible; user picks; badges from `total_count` |
| **Before / After comparison** | User validates proposals with context |
| **Highlight affected cells** | “See the option to see” — visual diff |
| **Proposal list (paginated)** | Context without rendering every issue; `total_count` shows full scope |
| **Select all / none / subset** | Expert workflow; avoids blind bulk accept |
| **Submit accept** | Commits to working copy; triggers downstream recalculation on next step |
| **Step completion feedback** | User knows submit worked before moving on |
| **Working copy + persistence** | Resume after a week; upstream/downstream consistency |
| **Audit log** | Who changed what, per pattern, per session — defensibility |
| **Three detectors + fixes** | Core assignment value |

### 6.2 Should-have if time permits

| Feature | Why |
|---------|-----|
| **Row context in proposals** | Show dimension columns so “Dog / China / Line” is identifiable |
| **Counts per pattern** | “12 proposals” in sidebar without loading all rows |
| **Export cleaned file** | Closes the loop for analysts |
| **Tab issue indicators** | Sidebar: color/badge when `total_count` > 0 |

### 6.3 Won’t build in v1 (document as assumptions)

- Multi-user auth / roles
- Editing detection formulas in UI
- Undo beyond “don’t accept” (optional: single-step undo later)
- Bulk upload scheduling, API integrations
- Statistical confidence or ML explanations

---

## 7. UI architecture (logical components)

```
┌─────────────────────────────────────────────────────────────┐
│  App                                                         │
│  ┌──────────────┐  ┌──────────────────────────────────────┐ │
│  │ FileExplorer │  │ CleaningWorkspace                     │ │
│  │ - uploads    │  │ ┌─────────┐ ┌──────────────────────┐ │ │
│  │ - Clean CTA  │  │ │Pattern  │ │ ProposalReview       │ │ │
│  └──────────────┘  │ │Nav      │ │ - BeforeTable        │ │ │
│                    │ │(ordered)│ │ - AfterTable         │ │ │
│                    │ │         │ │ - Selection controls │ │ │
│                    │ │         │ │ - Submit + feedback│ │ │
│                    │ └─────────┘ └──────────────────────┘ │ │
│                    │ ┌────────────────────────────────────┐ │ │
│                    │ │ AuditLog (drawer or tab)           │ │ │
│                    │ └────────────────────────────────────┘ │ │
│                    └──────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 7.1 Proposal list (paginated)

Goal: readable UI on large files — not “only detect five issues.”

- Server runs detectors over **all rows** (chunked); stores or computes full proposal list with `total_count`.
- UI requests `limit` / `offset` (default page size e.g. 10); optional “load more.”
- Within a page, prefer diverse examples (different dimensions / period windows) when cheap.

### 7.2 Before / After tables

- **Before:** values from working copy at **step start** (highlight anomalous cells).
- **After:** preview if **all selected proposals** in view were applied — or per-proposal preview row-by-row (simpler: one pair of tables per proposal card).

Side-by-side Before/After tables per dataset row, with a **checkbox** on each row (diagram uses ✕ when selected).

### 7.3 Selection UX

- **Checkbox per dataset row** (checked = accept that row’s fixes for this pattern).
- **Select all** | **Select none** for the rows on screen.
- **Submit** applies only checked rows for the **current pattern**.

---

## 8. Backend / state architecture

### 8.1 Two layers: materialized state + audit deltas

We store changes in **two places**, for different jobs:

| Layer | What it is | Used for |
|-------|------------|----------|
| **Working state** (`cell_values`) | Current value of every cell (updated in place on accept) | Running detectors on the next pattern; export |
| **Audit log** (`audit_log_entries`) | Append-only record of each cell change | “What did we change last week?”; defensibility; resume narrative |

This is **not** “only store deltas instead of data.” Detectors need the **full current grid** per row. What stays efficient at scale:

- **Writes on accept:** `UPDATE` only cells that changed (not rewrite the whole file).
- **Audit:** one row per changed cell (delta trail).
- **Reads to UI:** never send the full dataset after upload — only **paginated proposals** + paginated audit.

Original upload stays **immutable** on disk for reference; working state lives in the DB.

### 8.2 Data model (tables)

Full ER diagram, field types, and business rationale: [`docs/database-schema.md`](docs/database-schema.md).  
Pydantic schemas: [`schemas/`](schemas/).

```sql
-- Uploaded file metadata
datasets (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  uploaded_at   TIMESTAMPTZ NOT NULL,
  original_path TEXT NOT NULL,   -- immutable CSV
  period_columns JSON NOT NULL   -- e.g. ["202401","202402",...]
)

-- One row per CSV line; dimensions stable across the session
dataset_rows (
  id            TEXT PRIMARY KEY,
  dataset_id    TEXT NOT NULL REFERENCES datasets(id),
  row_index     INTEGER NOT NULL,
  dimension_a   TEXT,
  dimension_b   TEXT,
  dimension_c   TEXT
  -- or dimensions JSON if column count varies
)

-- Materialized working copy: one row per (dataset row × period)
-- Starts as upload values; only touched cells UPDATE on accept
cell_values (
  dataset_row_id  TEXT NOT NULL REFERENCES dataset_rows(id),
  period          TEXT NOT NULL,   -- e.g. "202402"
  value           REAL NOT NULL,
  PRIMARY KEY (dataset_row_id, period)
)

-- One cleaning run per open of the tool (which tab is active is UI-only)
cleaning_sessions (
  id              TEXT PRIMARY KEY,
  dataset_id      TEXT NOT NULL REFERENCES datasets(id),
  created_at      TIMESTAMPTZ NOT NULL,
  updated_at      TIMESTAMPTZ NOT NULL
)

-- Append-only audit: one row per cell changed
-- submit_id groups all cells from one Submit click (same UUID on each row)
audit_log_entries (
  id               TEXT PRIMARY KEY,
  session_id       TEXT NOT NULL REFERENCES cleaning_sessions(id),
  submit_id        TEXT NOT NULL,
  pattern          TEXT NOT NULL,
  dataset_row_id   TEXT NOT NULL REFERENCES dataset_rows(id),
  period           TEXT NOT NULL,
  value_before     REAL NOT NULL,
  value_after      REAL NOT NULL,
  created_at       TIMESTAMPTZ NOT NULL
)

CREATE INDEX idx_audit_session ON audit_log_entries(session_id, created_at);
CREATE INDEX idx_audit_submit ON audit_log_entries(session_id, submit_id);
CREATE INDEX idx_audit_row ON audit_log_entries(dataset_row_id);
```

**Proposals** are not stored long-term by default — computed from `cell_values` + pattern rules, cached per step if useful. Each proposal gets a stable `id` for the accept payload.

### 8.3 Apply accept (single pattern)

```
onSubmit(sessionId, pattern, selectedProposalIds):
  1. Load proposals for (session, pattern) — server already computed before/after
  2. BEGIN TRANSACTION
  3. submit_id = new UUID (shared by all cells from this Submit)
  4. For each selected proposal:
       For each cell in proposal:
         - read value_before from cell_values
         - UPDATE cell_values SET value = value_after WHERE (row_id, period)
         - INSERT audit_log_entries (..., submit_id, value_before, value_after)
  5. UPDATE cleaning_sessions SET updated_at = now()
  6. COMMIT
  7. Return { submitId, changes[] } — only cells that were updated (see §8.4)
```

**Important:** Do not pre-apply unaccepted proposals when computing the next pattern’s proposals.

### 8.4 Update only what changed; send only what changed

**Optimization focus:** we optimize the **write path** and **API payloads**, not “everything” at once.

| Path | Priority | What we do |
|------|----------|------------|
| **Writes** (Submit) | **High** | `UPDATE` only accepted cells in `cell_values`; append matching rows to `audit_log_entries` |
| **Transfer** (browser ↔ server) | **High** | Never send the full dataset after upload; exchange **deltas** only |
| **Reads** (detectors) | Medium | Server scans full grid **in chunks** from DB; UI gets **paginated** proposals only |

Detectors must read the whole working grid; accepts only touch changed cells. Cost of Submit scales with **# of accepts**, not file size.

**On Submit — request (client → server):**

```json
{ "proposalIds": ["prop-1", "prop-7"] }
```

Intent only. Server resolves before/after from stored proposals.

**On Submit — response (server → client):**

```json
{
  "submitId": "550e8400-e29b-41d4-a716-446655440000",
  "changes": [
    { "rowId": "row-2", "period": "202403", "valueBefore": -100, "valueAfter": 0 }
  ]
}
```

`changes` is the same delta written to `audit_log_entries`. No full table in the response.

**Other reads to the UI:**

| Endpoint | Sends |
|----------|--------|
| `GET .../proposals?limit&offset` | Paginated proposals + `total_count` |
| `GET .../audit` | Paginated `changes` (audit log) |
| Export | Full cleaned file only when user explicitly downloads |

**Storage:** materialized `cell_values` for current state + append-only audit for history — not audit-only replay on every read.

### 8.5 Scale — how §2.4 maps to implementation

| Non-negotiable | Implementation |
|----------------|----------------|
| Server-only grid | All routes above; no “sync dataset” endpoint |
| Streamed ingest | `POST /datasets` streams CSV → batch insert (e.g. 1k–5k rows) |
| Chunked detectors | `for chunk in load_rows(dataset_id, cursor): detect(chunk)`; accumulate proposal IDs + `total_count` |
| Paginated proposals | `GET .../proposals?limit=10&offset=0` returns page + `total_count` |
| Delta Submit | §8.3–8.4 unchanged |
| Paginated audit | `GET .../audit?limit&offset` |
| Streamed export | `GET .../export` writes CSV via cursor over `cell_values` ⨝ `dataset_rows` |
| DB working copy | `cell_values` table; detectors read via SQL, not app-global dict |

### 8.6 Persistence & resume

- **SQLite** (or Postgres) for tables above; original CSV on disk.
- On reopen: resume `cleaning_sessions` for the dataset; frontend prefetches `total_count` per pattern; no tab selected until the user clicks.
- Audit UI: `GET /sessions/:id/audit` → paginated `audit_log_entries` (group by `submit_id` in UI if needed).

Enough for an analyst returning a week later: audit shows pattern, row, period, before → after, and submit time.

---

## 9. API surface (minimal)

| Method | Purpose |
|--------|---------|
| `POST /datasets` | Upload |
| `GET /datasets` | List (explorer) |
| `POST /datasets/:id/sessions` | Start or resume cleaning |
| `GET /sessions/:id/steps/:pattern/proposals` | `?limit&offset` → proposals page + `total_count` |
| `POST /sessions/:id/steps/:pattern/accept` | In: `{ proposalIds }`. Out: `{ submitId, changes[] }`. Persists cell updates + audit |
| `GET /sessions/:id/audit` | Paginated change log (`changes` / `audit_log_entries`) |
| `GET /datasets/:id/export` | Optional cleaned download |

---

## 10. Tech stack 

- **Frontend:** React (or Next.js) — tables + sidebar + client state (`activePattern`, pattern counts, selection)
- **Backend:** Node or Python — CSV parse, detectors, persistence
- **Storage:** SQLite + file store for uploads

---

## 11. Testing strategy (lightweight)

- **Unit:** each detector on fixed row vectors (negative, refund pair, double booking case from screenshot).
- **Integration:** pipeline order — accept negative → refund count changes.
- **E2E (optional):** upload sample → accept subset on step 1 → audit entry exists.

---

## 12. Locked decisions

| Topic | Decision |
|-------|----------|
| **User** | PE diligence analyst only |
| **Selection** | Checkbox per dataset row + Select all / none |
| **One anomaly at a time** | Main panel shows one pattern when a tab is selected; default none selected |
| **Navigation** | User clicks tabs; Submit does not auto-switch; any pattern may be accepted in any order |
| **Tab indicators** | Frontend uses `total_count` per pattern (not `completed_steps` in DB) |
| **Detection rules** | Use brief as-is (negatives, refunds, double booking); no redefinition here |
| **State + history** | `cell_values` = materialized working copy; `audit_log_entries` = append-only deltas |
| **Scale** | §2.2 data nature → §2.4 non-negotiables (stream ingest, chunk detectors, paginate API) |
| **Optimization** | Writes + transfer: patch cells; API sends/receives deltas only |
| **Accept** | In: `proposalIds`. Out: `{ submitId, changes[] }`. Server applies updates |
| **Re-clean a step** | v1: no dedicated “reopen completed step” flow; user can click a tab again and accept new fixes if proposals still exist |

---

## 13. Build order (implementation sequence)

1. Streamed upload → batched insert `dataset_rows` + `cell_values`  
2. `cleaning_sessions` + DB-backed working copy  
3. Negative detector + fix + apply  
4. Cleaning UI shell (explorer → workspace)  
5. Before/After proposal card + submit + feedback  
6. Refund detector (on working copy)  
7. Double booking detector  
8. Sidebar + tab counts/badges + manual navigation  
9. Audit log UI + export  

---

## 14. Success criteria for the take-home

- Upload and select a dataset without prior knowledge of anomalies.  
- See **highlighted** before/after proposals per pattern (paginated; `total_count` visible).  
- Select all / none / subset and submit.  
- Demonstrate **ordering effect** (negative accept changes refund proposals).  
- Return later: persisted state + readable audit of changes.  
- Expert UI: no tutorial copy; pattern names sufficient.

---

## Appendix A — Diagram mapping

**Image 1 (pipeline + UI):**

- Left: `negative_value_algo` → `refund_algo` → `final_step` → working copy  
- Center: sidebar patterns + Before/After tables + submit  
- Right: with/without acceptance affecting refund detection  

**Image 2 (double booking):**

- Detection: `avg(M_i, M_{i+1}) == M_i / 2`  
- Fix: both cells → average; sum unchanged  

---

## Appendix B — Debugging checklist (for later)

When behavior surprises us during build, track hypotheses in a shared markdown checklist (per your preference): persistence vs detector vs apply logic vs pipeline order vs UI selection state.
