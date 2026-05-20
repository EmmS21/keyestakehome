# Build guide — backend, frontend, unit tests

How the app works after the **manual navigation** decision. Full product context: [`architecture.md`](../architecture.md).

Run unit tests: `pytest backend/tests/unit -v`

---

## Product rules (locked)

| Rule | Who enforces |
|------|----------------|
| Analyst **clicks** an anomaly tab to work on it | **Frontend** |
| Default: **no tab selected**; no Before/After until they click | **Frontend** |
| Submit with **nothing checked** → no cell updates; show “nothing changed”; clear review UI; tabs **unselected** | **Frontend** (message/UI) + **Backend** (`changes: []`) |
| Submit does **not** switch tabs or “advance” the session | **Frontend** + **Backend** (no step fields on session) |
| Analyst may **accept any pattern in any order** (e.g. refunds before negatives) | **Backend** allows any `pattern` on proposals/accept |
| Fixing cells changes what **later** detectors see on the working copy | **Backend** (data); order of **clicks** is free |
| Sidebar shows which patterns **have issues** (e.g. color) | **Frontend** using `total_count` from API |

**Pipeline order** is still real for **data** (accept negative → refund count may drop), not for **forcing** which tab is active.

---

## Backend

### `cleaning_sessions` (simplified)

```sql
cleaning_sessions (
  id          TEXT PRIMARY KEY,
  dataset_id  TEXT NOT NULL REFERENCES datasets(id),
  created_at  TIMESTAMPTZ NOT NULL,
  updated_at  TIMESTAMPTZ NOT NULL
)
```

No `current_step`. No `completed_steps`. Session = “this dataset is being cleaned” + resume id for audit.

### Accept (no step update)

```
onSubmit(sessionId, pattern, selectedProposalIds):
  1. Load proposals for (session, pattern)
  2. BEGIN
  3. submit_id = new UUID
  4. For each selected proposal → UPDATE cell_values + INSERT audit_log_entries
  5. UPDATE cleaning_sessions SET updated_at = now()   -- only timestamp
  6. COMMIT
  7. Return { submitId, changes[] }
```

Empty `proposal_ids` → step 4 skipped → `changes: []`. No audit rows unless you later choose to log “0 accepted” (v1: **no audit rows** when nothing changed).

### Proposals

- `GET /sessions/{id}/steps/{pattern}/proposals` — works for **any** pattern anytime.
- No 409 for “wrong step.”
- Detector always reads current `cell_values`.

### Optional: pattern counts for tab badges

Not a separate v1 requirement. Frontend can call proposals with `limit=1` (or `limit=0` if supported) per pattern and read `total_count`, or add later:

`GET /sessions/{id}/pattern-counts` → `{ "negatives": 3, "refunds": 1, "double_booking": 0 }`.

---

## Frontend

### Client state (not in DB)

| State | Meaning |
|-------|---------|
| `activePattern` | `null` or `negatives` / `refunds` / `double_booking` |
| `patternCounts` | `{ negatives: number, refunds: number, double_booking: number }` from API |
| Selection | Checked proposal ids for the **active** pattern only |

### Workspace open

1. `POST /datasets/{id}/sessions` → `session_id`
2. Prefetch counts (3× `GET .../proposals?limit=1&offset=0` per pattern, use `total_count`) → set tab colors/badges
3. `activePattern = null` → main area: short prompt (“Select an anomaly to review”), **no** Before/After

### User clicks a tab

1. `activePattern = that pattern`
2. `GET .../proposals?limit=10&offset=0`
3. Show Before/After + checkboxes

### User clicks Submit

**Nothing checked:**

- `POST .../accept` with `{ "proposal_ids": [] }`
- Response `changes: []`
- UI: “Nothing changed” (or similar)
- Hide Before/After; `activePattern = null`; clear checkboxes
- Refresh `patternCounts` for that pattern (still has issues until they fix or data unchanged)

**Some checked:**

- `POST .../accept` with selected ids
- Show success + summary from `changes`
- Hide Before/After; `activePattern = null` (same default as empty submit, unless you choose to keep tab selected — **default is unselected**)
- Refresh counts for that pattern (and optionally others, since working copy changed)

### Tab styling (example)

| `total_count` | Tab |
|---------------|-----|
| `> 0` | Accent / “has issues” (e.g. amber dot) |
| `0` | Muted / “clean for this detector” |

Order in sidebar: still `negatives` → `refunds` → `double_booking` (display only, from `PIPELINE_STEPS`).

### Resume later

- Same session via `POST .../sessions`
- Prefetch counts again; `activePattern = null`

---

## Unit tests — plain English (per endpoint)

Unit tests check the **brain** behind each route. No HTTP.

### `POST /datasets`

- Read CSV: dimensions vs months, parse rows, reject bad files.

### `GET /datasets`

- Almost nothing (list from DB later).

### `POST /datasets/{id}/sessions`

- Create or return a session linked to the dataset.
- **Do not** test “starts on negatives” or step advancement.

### `GET .../proposals`

- Negatives / refunds / double booking detectors find the right cells.
- One proposal per row; pagination + `total_count`.
- **Any pattern** can be requested (no step guard).
- Pipeline **data** test: after applying negative fixes on a row, refund detector returns fewer issues.

### `POST .../accept`

- Selected rows update cells; unselected do not.
- Return exact `changes`; audit one row per cell when `changes` non-empty.
- Empty selection → `changes: []`, grid unchanged, **no** session step fields to update.
- Bad proposal id → error.

### `GET .../audit`

- Paginate and format log entries.

### `GET .../export`

- One CSV line with cleaned values.

### `GET /health`

- No unit tests.

---

## What we removed from earlier docs

- Auto-advance to next anomaly after Submit
- `current_step` / `completed_steps` on session
- Server 409 “wrong step” on proposals/accept
- “Continue” button as required server concept (UI-only if you want empty-pattern messaging on a tab)
- Forward-only **navigation** (still true that **re-editing** a past step is out of scope for v1 if you don’t reload that tab’s proposals after submit)
