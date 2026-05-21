# Data Cleaning Tool

Take-home: upload deal revenue grids, clean anomalies step-by-step (negatives → refunds → double booking), audit every change.

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

**Frontend** — see [`frontend/README.md`](frontend/README.md). Initialize Next.js when ready (`create-next-app` or manual `package.json`).

## Repository layout

```
keyestakehome/
├── README.md
├── architecture.md          # System design, API, build order
├── requirements.txt         # Python deps (backend + schemas)
│
├── docs/
│   ├── database-schema.md   # ER diagram, storage layers, API DTOs
│   └── limitations.md       # v1 scope boundaries
│
├── schemas/                 # Pydantic: DB tables + API DTOs
│   ├── types.py
│   ├── database.py
│   └── api.py
│
├── data/                    # Sample CSV for dev/demos
│   └── sample.csv
│
├── backend/                 # FastAPI
│   ├── app/
│   │   ├── main.py
│   │   ├── dependencies.py
│   │   ├── datasets.py
│   │   ├── routers/
│   │   └── db/
│   └── tests/
│       ├── unit/
│       └── integration/
│
├── frontend/                # Next.js (folders ready; init deps when needed)
│   ├── app/
│   ├── src/components/
│   ├── src/lib/
│   └── public/
│
├── scripts/                 # Dev helpers (seed, etc.)
└── uploads/                 # Runtime CSV storage (gitignored)
```

## Design docs

| Doc | Contents |
|-----|----------|
| [`architecture.md`](architecture.md) | Persona, scale rules, detectors, API surface |
| [`docs/database-schema.md`](docs/database-schema.md) | ER diagram, storage/flow views, field mapping |
| [`docs/limitations.md`](docs/limitations.md) | Intentional v1 boundaries |
