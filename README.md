# Data Cleaning Tool

Take-home: upload deal revenue grids, clean anomalies step-by-step (negatives → refunds → double booking), audit every change.

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
