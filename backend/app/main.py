"""FastAPI application entrypoint."""

from pathlib import Path

from fastapi import FastAPI

from backend.app.db.connection import connect, init_db
from backend.app.routers import datasets

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "backend" / "data" / "app.db"

app = FastAPI(
    title="Data Cleaning Tool",
    description="Deal revenue grid cleaning API",
    version="0.1.0",
)

app.include_router(datasets.router)


@app.on_event("startup")
def on_startup() -> None:
    conn = connect(DB_PATH)
    try:
        init_db(conn)
    finally:
        conn.close()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
