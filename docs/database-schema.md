# Database schema

Persisted tables and API DTOs. Behavior and scale: [`architecture.md`](../architecture.md). Code: [`schemas/database.py`](../schemas/database.py), [`schemas/api.py`](../schemas/api.py).

## Entity-relationship

Composite PK on `cell_values`: `(dataset_row_id, period)`. Keys shown on relationship lines only (GitHub Mermaid does not reliably render PK/FK on attributes).

```mermaid
erDiagram
  datasets ||--o{ dataset_rows : contains
  datasets ||--o{ cleaning_sessions : cleaned_via
  dataset_rows ||--o{ cell_values : has_cells
  cleaning_sessions ||--o{ audit_log_entries : change_log
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
    string current_step
    string completed_steps
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
    All steps done
    Export uses cell_values
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
  CS[cleaning_sessions completed_steps]
  AL[audit_log_entries]
  Submit --> SID[submit_id]
  SID --> AL
  AL --> SG[group by submit_id]
  pattern --> AL
```

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
| `current_step`, `pattern` | `CleaningPattern` | `TEXT` | |
