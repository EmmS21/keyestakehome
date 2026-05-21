"""Shared FastAPI dependencies."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = REPO_ROOT / "backend" / "data" / "app.db"
DEFAULT_UPLOADS_DIR = REPO_ROOT / "uploads"


def get_db_path() -> Path:
    return DEFAULT_DB_PATH


def get_uploads_dir() -> Path:
    return DEFAULT_UPLOADS_DIR
