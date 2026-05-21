# Database schema

Persisted tables and API DTOs. Product context: [`README.md`](../README.md). Code: [`schemas/database.py`](../schemas/database.py), [`schemas/api.py`](../schemas/api.py).

## Entity-relationship

Composite PK on `cell_values`: `(dataset_row_id, period)`. Keys shown on relationship lines only (GitHub Mermaid does not reliably render PK/FK on attributes).

```mermaid
erDiagram
  datasets ||--o{ dataset_rows : contains
  datasets ||--o{ cleaning_sessions : cleaned_via
  dataset_rows ||--o{ cell_values : has_cells
  cleaning_sessions ||--o{ audit_log_entries : change_log
  cleaning_sessions ||--o{ export_events : downloads
  datasets ||--o{ export_events : exported_from
  dataset_rows ||--o{ audit_log_entries : which_row

  datasets {
    string id
    string name
    datetime uploaded_at
    string original_path
    string period_columns
  }

  dataset_rows {
    string id
    string dataset_id
    int row_index
    string dimension_a
    string dimension_b
    string dimension_c
  }

  cell_values {
    string dataset_row_id
    string period
    number value
  }

  cleaning_sessions {
    string id
    string dataset_id
    datetime created_at
    datetime updated_at
  }

  audit_log_entries {
    string id
    string session_id
    string submit_id
    string pattern
    string dataset_row_id
    string period
    number value_before
    number value_after
    datetime created_at
  }

  export_events {
    string id
    string dataset_id
    string session_id
    datetime exported_at
    datetime session_updated_at
    int audit_entry_count
    int export_number
  }
```

## Storage

```mermaid
flowchart TB
  subgraph disk["Immutable disk"]
    CSV["original_path CSV"]
  end

  subgraph db["Database"]
    meta["datasets and dataset_rows"]
    working["cell_values"]
    workflow["cleaning_sessions"]
    audit["audit_log_entries"]
  end

  subgraph runtime["Computed"]
    prop["Proposal and ProposalsResponse"]
    det["Detectors"]
  end

  CSV -->|upload| working
  meta --> working
  working --> det
  det --> prop
  prop -->|POST accept| working
  prop -->|POST accept| audit
  workflow -.-> prop
```

## Working grid

```mermaid
stateDiagram-v2
  [*] --> Uploaded
  Uploaded --> InProgress
  InProgress --> ReadyForExport

  note right of Uploaded
    Ingest CSV
    Matches file on disk
  end note

  note right of InProgress
    Accept fixes
    Mix of cleaned and untouched cells
  end note

  note right of ReadyForExport
    User exports when ready
    Uses cell_values
  end note
```

## Accept flow

```mermaid
sequenceDiagram
  participant Analyst
  participant API
  participant Detectors
  participant CV as cell_values
  participant Audit as audit_log_entries

  Analyst->>API: GET proposals
  API->>CV: read grid
  API->>Detectors: run pattern
  Detectors-->>API: suggestions
  API-->>Analyst: proposals list

  Analyst->>API: POST accept
  API->>CV: UPDATE changed cells
  API->>Audit: INSERT per changed cell
  API-->>Analyst: AcceptResponse
```

## Audit

```mermaid
flowchart TB
  AL[audit_log_entries]
  EX[export_events]
  Submit --> SID[submit_id]
  SID --> AL
  AL --> SG[group by submit_id]
  pattern --> AL
  Download["GET export"] --> EX
  EX -->|audit_entry_count + session_updated_at| Version[version snapshot]
```

**Cell changes** (`audit_log_entries`): one row per accepted cell, grouped by `submit_id`.

**Exports** (`export_events`): one row per CSV download — `exported_at`, `export_number`, plus snapshots `session_updated_at` and `audit_entry_count` so downloads can be matched to how much cleaning had happened. Analyst identity is not stored in v1.

## UI vs database

| Concern | Stored in DB | Stored in frontend |
|---------|--------------|-------------------|
| Which tab is open | No | `activePattern` (nullable) |
| Which patterns have issues | No (computed) | `patternCounts` from `GET .../proposals` `total_count` |
| Checkbox selection | No | Per active pattern |
| Working cell values | `cell_values` | — |
| Change history | `audit_log_entries` | — |
| CSV downloads | `export_events` | — |

## API models

Not persisted. `Proposal.id` is a step-scoped accept key, not a DB PK.

```mermaid
classDiagram
  class CellChange {
    period
    value_before
    value_after
  }

  class Proposal {
    id
    pattern
    dataset_row_id
    row_index
    changes
  }

  class ProposalsResponse {
    pattern
    proposals
    total_count
    limit
    offset
  }

  class AcceptRequest {
    proposal_ids
  }

  class AppliedCellChange {
    dataset_row_id
    period
    value_before
    value_after
  }

  class AcceptResponse {
    submit_id
    changes
  }

  class AuditLogEntryView {
    id
    submit_id
    pattern
    dataset_row_id
    period
    value_before
    value_after
    created_at
  }

  class AuditLogResponse {
    entries
    total_count
  }

  Proposal *-- CellChange
  ProposalsResponse o-- Proposal
  AcceptResponse *-- AppliedCellChange
  AuditLogResponse o-- AuditLogEntryView
```

## Field mapping

| Field | Pydantic | SQL | Notes |
|-------|----------|-----|-------|
| `id` | `UUID` | `TEXT` | All tables |
| `submit_id` | `UUID` | `TEXT` | Groups one Submit; not a FK |
| `uploaded_at`, `created_at`, … | `datetime` | `TIMESTAMPTZ` | UTC |
| `original_path` | `str` | `TEXT` | Immutable CSV key |
| `period_columns` | `list[str]` | `JSON` | Ordered month headers |
| `row_index` | `int` ≥ 0 | `INTEGER` | Line in original file |
| `dimension_*` | `str \| None` | `TEXT` | Nullable |
| `period` | `str` | `TEXT` | `YYYYMM` |
| `value`, `value_before`, `value_after` | `float` | `REAL` | |
| `pattern` (audit only) | `CleaningPattern` | `TEXT` | Which anomaly type was accepted |
