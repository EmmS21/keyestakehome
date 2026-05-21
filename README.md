# Data Cleaning Tool

Take-home: upload deal revenue grids, review anomaly proposals (negatives → refunds → double booking), accept fixes with an audit trail, export cleaned CSV.

**Persona:** private equity diligence analyst. They know what negatives, refunds, and double bookings mean; the UI uses pattern names and cell highlights only (no tutorial copy). They work in interrupted sessions and need defensibility — every accepted cell is logged.

## How it works

1. **Upload** CSV on the file explorer (`/`).
2. **Clean** opens the workspace (`/clean/[datasetId]`). Sidebar lists three patterns; **no tab is selected** until the analyst clicks one.
3. **Review** Before | After tables for a paginated page of proposals (`total_count` shows full scope).
4. **Submit** applies checked rows for that pattern only; working copy and audit update; UI returns to idle (no auto tab switch).
5. **Resume** later — same session per dataset; audit and working copy persist on the server.
6. **Export** downloads the current `cell_values` grid; each download is recorded in `export_events`.

Deal grids are **large and wide** (many rows × many period columns). The full grid stays on the server; the browser gets paginated proposals and audit entries only. See [`docs/limitations.md`](docs/limitations.md) for intentional v1 boundaries.

### Anomaly patterns (from brief)

| Pattern | Detection | Fix |
|---------|-----------|-----|
| **Negative values** | Any period `< 0` | Set to `0` |
| **Refunds** | N consecutive periods with sum `== 0` | Set those cells to `0` |
| **Double booking** | `avg(M_i, M_{i+1}) == M_i / 2` | Both cells → average (sum preserved) |

Sidebar order is **display-only** (negatives → refunds → double booking). The analyst may open patterns in any order; accepted fixes change what downstream detectors see on the working copy.

Sample data: [`data/sample.csv`](data/sample.csv).

## Why we track exports

When an analyst downloads a cleaned CSV, the organization needs to answer:

- **Who downloaded what?** — v1 stores *when* and *which version* of the grid was exported, not *who* (no auth yet). See [`docs/limitations.md`](docs/limitations.md).
- **What version was that file?** — Each export is tied to the cleaning session and snapshots `session_updated_at` plus `audit_entry_count` (how many accepted cell changes were already on the record). Together with `audit_log_entries` (per-cell before/after on Submit), you can retrace what state the exported file reflected.

Cell-level changes stay in the audit log; export timestamps live in `export_events` (separate from per-cell audit rows).

## Quick start

**Backend** (from repo root):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

- API docs: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/health  

**Frontend:**

```bash
cd frontend
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
npm install
npm run dev
```

Open http://127.0.0.1:3000. Details: [`frontend/README.md`](frontend/README.md).

**Tests:**

```bash
pytest backend/tests/unit -v          # backend (repo root, venv active)
cd frontend && npm run test:e2e       # Playwright (API must be running)
```

## Repository layout

```
keyestakehome/
├── README.md
├── requirements.txt         # Python deps (backend + schemas)
│
├── docs/
│   ├── database-schema.md   # ER diagram, storage layers, API DTOs
│   ├── limitations.md       # v1 scope boundaries
│   └── design/              # Wireframes (cleaning-workspace.html)
│
├── schemas/                 # Pydantic: DB tables + API DTOs
├── data/sample.csv          # Dev / demo CSV
├── backend/                 # FastAPI — see backend/README.md
├── frontend/                # Next.js — see frontend/README.md
└── uploads/                 # Runtime CSV storage (gitignored)
```

## Design docs

| Doc | Contents |
|-----|----------|
| [`backend/README.md`](backend/README.md) | Endpoints, request/response notes, server product rules |
| [`docs/database-schema.md`](docs/database-schema.md) | ER diagram, storage/flow views, field mapping |
| [`docs/limitations.md`](docs/limitations.md) | Intentional v1 boundaries and assumptions |
| [`docs/design/wireframes/cleaning-workspace.html`](docs/design/wireframes/cleaning-workspace.html) | Low-fidelity UI reference |

## Tech stack

- **Frontend:** Next.js (App Router), React
- **Backend:** Python, FastAPI
- **Storage:** SQLite (`backend/data/app.db`) + immutable uploads on disk
- **Schemas:** Pydantic in [`schemas/`](schemas/)

## Success criteria

- Upload and clean without prior knowledge of which anomalies exist.
- Highlighted before/after proposals per pattern (paginated; `total_count` visible).
- Select all / none / subset and submit; empty submit leaves working copy unchanged.
- Demonstrate ordering effect (e.g. accepting negatives can reduce refund proposals).
- Return later with persisted working copy and readable audit log.
- Export working copy with export events for version tracing.
