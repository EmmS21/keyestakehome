"""SQLite connection and schema initialization."""

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS datasets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    original_path TEXT NOT NULL,
    period_columns TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dataset_rows (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(id),
    row_index INTEGER NOT NULL,
    dimension_a TEXT,
    dimension_b TEXT,
    dimension_c TEXT
);

CREATE TABLE IF NOT EXISTS cell_values (
    dataset_row_id TEXT NOT NULL REFERENCES dataset_rows(id),
    period TEXT NOT NULL,
    value REAL NOT NULL,
    PRIMARY KEY (dataset_row_id, period)
);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    conn.commit()
