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

CREATE TABLE IF NOT EXISTS cleaning_sessions (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cleaning_sessions_dataset
    ON cleaning_sessions(dataset_id);

CREATE TABLE IF NOT EXISTS audit_log_entries (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES cleaning_sessions(id),
    submit_id TEXT NOT NULL,
    pattern TEXT NOT NULL,
    dataset_row_id TEXT NOT NULL REFERENCES dataset_rows(id),
    period TEXT NOT NULL,
    value_before REAL NOT NULL,
    value_after REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_session
    ON audit_log_entries(session_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_submit
    ON audit_log_entries(session_id, submit_id);
CREATE INDEX IF NOT EXISTS idx_audit_row
    ON audit_log_entries(dataset_row_id);

CREATE TABLE IF NOT EXISTS export_events (
    id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL REFERENCES datasets(id),
    session_id TEXT NOT NULL REFERENCES cleaning_sessions(id),
    exported_at TEXT NOT NULL,
    session_updated_at TEXT NOT NULL,
    audit_entry_count INTEGER NOT NULL,
    export_number INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_export_events_dataset
    ON export_events(dataset_id, exported_at);
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
