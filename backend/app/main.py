"""FastAPI application entrypoint."""

from pathlib import Path

from fastapi import FastAPI

from backend.app.db.connection import connect, init_db
from backend.app.routers import datasets, sessions

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "backend" / "data" / "app.db"

app = FastAPI(
    title="Data Cleaning Tool API",
    description=(
        "Upload deal revenue CSVs, detect anomalies (negatives, refunds, double booking), "
        "accept proposed fixes, and read an audit trail.\n\n"
        "**Interactive docs:** [/docs](/docs) (Swagger UI) · [/redoc](/redoc) · "
        "[/openapi.json](/openapi.json)\n\n"
        "Sessions are keyed by dataset (one cleaning run per dataset). "
        "The UI chooses which pattern to review; the server does not enforce step order."
    ),
    version="0.1.0",
    openapi_tags=[
        {
            "name": "datasets",
            "description": "Upload CSV files and list datasets for the file explorer.",
        },
        {
            "name": "sessions",
            "description": (
                "Cleaning workspace: proposals per pattern, accept selected fixes, audit log. "
                "Requires a session_id from POST /datasets/{dataset_id}/sessions."
            ),
        },
        {
            "name": "health",
            "description": "Liveness check.",
        },
    ],
)

app.include_router(datasets.router)
app.include_router(sessions.router)


@app.on_event("startup")
def on_startup() -> None:
    conn = connect(DB_PATH)
    try:
        init_db(conn)
    finally:
        conn.close()


@app.get(
    "/health",
    tags=["health"],
    summary="Health check",
    response_description="Service is running",
)
def health() -> dict[str, str]:
    """Liveness probe for deploys and local dev."""
    return {"status": "ok"}
