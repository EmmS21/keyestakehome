# Backend (FastAPI)

Run from the **repository root** so `schemas/` imports resolve:

```bash
pip install -r requirements.txt
uvicorn backend.app.main:app --reload
```

Health check: `GET http://127.0.0.1:8000/health`

Unit tests: `pytest backend/tests/unit -v` (from repo root, venv active)

Upload: `POST http://127.0.0.1:8000/datasets` (multipart field `file`)

## Layout

| Path | Purpose |
|------|---------|
| `app/main.py` | FastAPI app, middleware, router registration |
| `app/routers/` | HTTP routes (`datasets`, `sessions`, …) |
| `app/services/` | Detectors, ingest, export, accept/submit logic |
| `app/repositories/` | DB queries (datasets, cell_values, audit, …) |
| `app/db/` | Engine, sessions, migrations |
| `tests/unit/` | Detector and pure logic tests |
| `tests/integration/` | Upload → pipeline → audit flows |

Uploaded CSVs go to `uploads/` at repo root (gitignored).

Build plan and unit-test intent: [`tobuild.md`](tobuild.md).