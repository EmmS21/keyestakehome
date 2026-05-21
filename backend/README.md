# Backend (FastAPI)

Deal revenue grid cleaning API: upload CSV, detect anomalies, accept fixes, audit trail.

Run from the **repository root** so `schemas/` imports resolve:

```bash
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Default base URL: `http://127.0.0.1:8000`

## API documentation (OpenAPI / Swagger)

FastAPI generates interactive docs from route handlers and Pydantic models in `schemas/api.py`:

| URL | UI |
|-----|-----|
| [`/docs`](http://127.0.0.1:8000/docs) | Swagger UI — try requests in the browser |
| [`/redoc`](http://127.0.0.1:8000/redoc) | ReDoc — readable reference |
| [`/openapi.json`](http://127.0.0.1:8000/openapi.json) | OpenAPI 3 schema (import into Postman, etc.) |

## Endpoints

| Method | Path | Status | Description |
|--------|------|--------|-------------|
| `GET` | `/health` | 200 | Liveness probe |
| `GET` | `/datasets` | 200 | List uploaded datasets (`id`, `name`, `period_columns`, `row_count`, `uploaded_at`) |
| `POST` | `/datasets` | 201 / 409 | Upload CSV — multipart field **`file`**; **409** if `name` already exists |
| `POST` | `/datasets/{dataset_id}/sessions` | 201 / 200 | **Create** or **resume** cleaning session (one session per dataset) |
| `GET` | `/sessions/{session_id}/steps/{pattern}/proposals` | 200 | Paginated proposals + `total_count`. Query: `limit` (default 10), `offset` (default 0) |
| `POST` | `/sessions/{session_id}/steps/{pattern}/accept` | 200 | Apply selected proposals. Body: `proposal_ids`, `session_updated_at` |
| `GET` | `/sessions/{session_id}/audit` | 200 | Paginated audit log. Query: `limit`, `offset` |

### Path parameters

- **`pattern`**: `negatives` | `refunds` | `double_booking` (`done` is invalid for proposals/accept)

### Request / response notes

**Upload (`POST /datasets`)**

- Field name: `file`
- Errors: 400 for empty file, no data rows, no period columns, invalid numeric cell (structured `detail` for bad values)

**Sessions (`POST /datasets/{id}/sessions`)**

- Returns `{ session_id, dataset_id, created_at, updated_at }`
- **201** when new; **200** when reusing existing session for that dataset

**Proposals (`GET .../proposals`)**

- Response includes `session_updated_at` — client must send this back on accept
- `proposals[]`: per-row fixes with `changes[]` (`period`, `value_before`, `value_after`)
- `total_count`: full count for the pattern (all rows scanned server-side)

**Accept (`POST .../accept`)**

```json
{
  "proposal_ids": ["negatives:row-uuid", "..."],
  "session_updated_at": "2026-05-20T12:00:00+00:00"
}
```

- Empty `proposal_ids` → `changes: []`, no cell or audit writes; session `updated_at` still bumps
- Success: `{ "submit_id", "changes": [{ "dataset_row_id", "period", "value_before", "value_after" }] }`
- **409** if `session_updated_at` does not match DB (reload proposals)
- **400** if proposal id invalid
- **404** if session not found

**Audit (`GET .../audit`)**

- `entries[]`: `pattern`, `submit_id`, row, period, before/after, `created_at`

## Product rules (server)

| Rule | Behavior |
|------|----------|
| Manual navigation | Any `pattern` allowed on proposals/accept; no `current_step` on session |
| Working copy | `cell_values` updated in place on accept |
| Audit | One row per changed cell; grouped by `submit_id` per Submit click |
| Detectors | Run on current `cell_values`; order of user clicks is free, but fixes affect later counts |
| Resume | Same `session_id` per dataset via `POST .../sessions` |

Frontend owns tab selection, idle default UI, and submit UX. See [`architecture.md`](../architecture.md) and [`frontend/tobuild.md`](../frontend/tobuild.md).

## Persistence

- SQLite: `backend/data/app.db` (created on startup)
- Uploads: `uploads/` at repo root (gitignored)
- Tables: `datasets`, `dataset_rows`, `cell_values`, `cleaning_sessions`, `audit_log_entries` — see [`docs/database-schema.md`](../docs/database-schema.md)

## Layout

| Path | Purpose |
|------|---------|
| `app/main.py` | FastAPI app, OpenAPI metadata, router registration |
| `app/dependencies.py` | Shared `Depends()` helpers (paths, etc.) |
| `app/routers/` | HTTP routes |
| `app/datasets.py` | Ingest, list, DB access |
| `app/proposals.py` | Detectors + pagination |
| `app/accept.py` | Apply fixes + audit |
| `app/audit.py` | Audit log queries |
| `app/sessions.py` | Session start/resume |
| `app/db/` | SQLite connection and schema init |
| `tests/unit/` | Service-layer tests (no HTTP) |

## Tests

```bash
pytest backend/tests/unit -v
```

From repo root with venv active. Unit tests target service logic, not HTTP routes.
