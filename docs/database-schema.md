# Database schema

Persisted tables and API DTOs. Behavior and scale: [`architecture.md`](../architecture.md). Code: [`schemas/database.py`](../schemas/database.py), [`schemas/api.py`](../schemas/api.py).

## Entity-relationship

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

## Storage

```mermaid
flowchart TB
  subgraph disk["Immutable (disk)"]
    CSV["original_path — CSV never edited"]
  end

  subgraph db["Database"]
    meta["datasets · dataset_rows"]
    working["cell_values"]
    workflow["cleaning_sessions"]
    audit["audit_log_entries"]
  end

  subgraph runtime["Computed"]
    prop["Proposal · ProposalsResponse"]
    det["Detectors"]
  end

  CSV -->|"upload"| working
  meta --> working
  working --> det
  det --> prop
  prop -->|"POST accept"| working
  prop -->|"POST accept"| audit
  workflow -.-> prop
```

## Working grid

```mermaid
stateDiagram-v2
  [*] --> Uploaded: ingest CSV
  Uploaded --> InProgress: accept fixes
  InProgress --> InProgress: more accepts
  InProgress --> ReadyForExport: all steps done

  note right of Uploaded
    Matches CSV; file on disk unchanged
  end note

  note right of InProgress
    Mix of cleaned and untouched cells
  end note

  note right of ReadyForExport
    Export uses cell_values
  end note
```

## Accept flow

```mermaid
sequenceDiagram
  actor Analyst
  participant API
  participant Detectors
  participant CV as cell_values
  participant Audit as audit_log_entries

  Analyst->>API: GET /proposals
  API->>CV: read grid
  API->>Detectors: run pattern
  Detectors-->>API: suggestions
  API-->>Analyst: Proposal[]

  Analyst->>API: POST /accept
  API->>CV: UPDATE changed cells
  API->>Audit: INSERT per changed cell
  API-->>Analyst: AcceptResponse
```

## Audit

```mermaid
flowchart TB
  CS["cleaning_sessions.completed_steps"]
  AL["audit_log_entries"]
  Submit --> SID["submit_id"]
  SID --> AL
  AL --> SG["GROUP BY submit_id"]
  pattern["pattern"] --> AL
```

## API models

Not persisted. `Proposal.id` is a step-scoped accept key, not a DB PK.

```mermaid
classDiagram
  direction TB

  class CellChange {
    +str period
    +float value_before
    +float value_after
  }

  class Proposal {
    +str id
    +CleaningPattern pattern
    +UUID dataset_row_id
    +int row_index
    +list~CellChange~ changes
  }

  class ProposalsResponse {
    +CleaningPattern pattern
    +list~Proposal~ proposals
    +int total_count
    +int limit
    +int offset
  }

  class AcceptRequest {
    +list~str~ proposal_ids
  }

  class AppliedCellChange {
    +UUID dataset_row_id
    +str period
    +float value_before
    +float value_after
  }

  class AcceptResponse {
    +UUID submit_id
    +list~AppliedCellChange~ changes
  }

  class AuditLogEntryView {
    +UUID id
    +UUID submit_id
    +CleaningPattern pattern
    +UUID dataset_row_id
    +str period
    +float value_before
    +float value_after
    +datetime created_at
  }

  class AuditLogResponse {
    +list~AuditLogEntryView~ entries
    +int total_count
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
