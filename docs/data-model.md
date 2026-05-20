# Data model

Companion to [`architecture.md`](../architecture.md). Defines **persisted tables**, **API objects** (not stored), types, and business rationale.

**Scale:** Driven by diligence data shape (architecture §2.2); implementation rules in §2.4.

Implementation schemas: [`schemas/`](../schemas/) (Pydantic).

---

## Entity relationship (persisted tables)

```mermaid
erDiagram
  datasets ||--o{ dataset_rows : contains
  datasets ||--o{ cleaning_sessions : "cleaned via"
  dataset_rows ||--o{ cell_values : "has cells"
  cleaning_sessions ||--o{ audit_log_entries : "change log"
  dataset_rows ||--o{ audit_log_entries : "which row"

  datasets {
    string id PK
    string name
    datetime uploaded_at
    string original_path
    json period_columns
  }

  dataset_rows {
    string id PK
    string dataset_id FK
    int row_index
    string dimension_a
    string dimension_b
    string dimension_c
  }

  cell_values {
    string dataset_row_id PK_FK
    string period PK
    float value
  }

  cleaning_sessions {
    string id PK
    string dataset_id FK
    string current_step
    json completed_steps
    datetime created_at
    datetime updated_at
  }

  audit_log_entries {
    string id PK
    string session_id FK
    string submit_id
    string pattern
    string dataset_row_id FK
    string period
    float value_before
    float value_after
    datetime created_at
  }
```

**Not in the database:** `Proposal` (see [API objects](#api-objects-not-database-tables)).

---

## What is persisted vs computed

| Name | Stored in DB? | What it is |
|------|---------------|------------|
| `datasets` | Yes | Uploaded file metadata |
| `dataset_rows` | Yes | Each CSV line (A, B, C, …) |
| `cell_values` | Yes | **The dataset being cleaned** — current number in each month cell |
| `cleaning_sessions` | Yes | Progress: which step the analyst is on |
| `audit_log_entries` | Yes | Each **cell** changed; `submit_id` groups one Submit |
| `Proposal` | **No** (default) | Suggestion shown in UI before Submit |

---

## `cell_values` — is this the cleaned data?

**Yes.** Think of it as the **live Excel sheet** the product works on.

| Moment | What `cell_values` holds |
|--------|---------------------------|
| Right after upload | Copy of the file (same numbers as CSV) |
| After some accepts | Mix: cleaned cells updated, untouched cells unchanged |
| After all steps | Fully cleaned working dataset for **export** |

- **Original CSV on disk** = never edited (audit baseline).
- **`cell_values`** = what detectors and export use **now**.

---

## Audit — one table

**`audit_log_entries`** is the full audit log: one row per cell that changed.

| Field | Purpose |
|-------|---------|
| `submit_id` | Same UUID on every cell from **one Submit click** — group in the UI |
| `pattern` | Which step (negatives, refunds, double booking) |
| `value_before` / `value_after` | Proof of what changed |

**“Did we finish Refunds?”** → `cleaning_sessions.completed_steps` (workflow), not a separate batch table.

**“Which cells changed?”** → query `audit_log_entries` (optionally `WHERE submit_id = ?`).

---

## `Proposal` — why a schema but not a DB table?

A proposal is a **preview**, not a fact.

| | Proposal | After Submit |
|--|----------|--------------|
| Meaning | “We **suggest** this fix” | “We **did** this fix” |
| Stored? | Computed when you open the step | `cell_values` + `audit_log_entries` |
| If data changes | Throw away and recompute | Audit is permanent |

**Pydantic `Proposal`** types the API response for `GET /proposals`. It is a **DTO**, not a persisted entity.

---

## Field types and rationale

| Field | Python / Pydantic | SQL | Why |
|-------|-------------------|-----|-----|
| `id` (all tables) | `UUID` | `TEXT` | Globally unique, safe in APIs |
| `submit_id` | `UUID` | `TEXT` | Groups cells from one Submit (not a FK) |
| `name` | `str` | `TEXT` | File name from upload |
| `uploaded_at`, `created_at`, … | `datetime` (UTC) | `TIMESTAMPTZ` | Audit ordering, resume |
| `original_path` | `str` | `TEXT` | Path or storage key to immutable CSV |
| `period_columns` | `list[str]` | `JSON` | Ordered month headers; same for all rows |
| `row_index` | `int` ≥ 0 | `INTEGER` | Stable line number in original file |
| `dimension_*` | `str \| None` | `TEXT` nullable | A/B/C may be empty |
| `period` | `str` | `TEXT` | `YYYYMM` label; matches CSV headers |
| `value`, `value_before`, `value_after` | `float` | `REAL` | Revenue numbers |
| `current_step`, `pattern` | `CleaningPattern` enum | `TEXT` | Pipeline steps |

**Proposal IDs:** `str`, generated per step for the accept payload — not a DB primary key.

---

## API objects (not database tables)

| Model | Used on |
|-------|---------|
| `Proposal` | `GET .../proposals` |
| `CellChange` | Proposals, Submit response, audit |
| `AcceptRequest` / `AcceptResponse` | `POST .../accept` |
| `AuditLogResponse` | `GET .../audit` |

See [`schemas/api.py`](../schemas/api.py) and [`schemas/database.py`](../schemas/database.py).

---

## `cleaning_sessions` — why it exists

Tracks **workflow**, not numbers.

- `current_step` — resume (“you’re on Refunds”)
- `completed_steps` — which patterns were already submitted

One session ≈ one analyst cleaning one dataset until done (v1).

---

## Table reference (quick)

### `datasets`
Uploaded file. `period_columns` defines which columns are months.

### `dataset_rows`
Identity of each transaction line (dimensions + `row_index`).

### `cell_values`
Composite PK `(dataset_row_id, period)`. **Current revenue grid.**

### `cleaning_sessions`
`current_step` + `completed_steps` for pipeline UI and resume.

### `audit_log_entries`
One row per changed cell. `submit_id` ties rows to the same Submit.
