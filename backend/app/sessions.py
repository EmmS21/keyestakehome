"""Cleaning session start and resume."""

import sqlite3
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.exceptions import DatasetNotFoundError
from schemas.database import CleaningSession


def _row_to_session(row: sqlite3.Row) -> CleaningSession:
    return CleaningSession(
        id=UUID(row["id"]),
        dataset_id=UUID(row["dataset_id"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def find_session_by_dataset(
    conn: sqlite3.Connection, dataset_id: UUID
) -> CleaningSession | None:
    row = conn.execute(
        """
        SELECT id, dataset_id, created_at, updated_at
        FROM cleaning_sessions
        WHERE dataset_id = ?
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (str(dataset_id),),
    ).fetchone()
    if row is None:
        return None
    return _row_to_session(row)


def start_or_resume_session(
    conn: sqlite3.Connection, dataset_id: UUID
) -> tuple[CleaningSession, bool]:
    """
    Return (session, created).
    created is True when a new row was inserted, False when an existing session was reused.
    """
    exists = conn.execute(
        "SELECT 1 FROM datasets WHERE id = ?",
        (str(dataset_id),),
    ).fetchone()
    if exists is None:
        raise DatasetNotFoundError(dataset_id)

    existing = find_session_by_dataset(conn, dataset_id)
    if existing is not None:
        return existing, False

    now = datetime.now(UTC)
    session_id = uuid4()
    conn.execute(
        """
        INSERT INTO cleaning_sessions (id, dataset_id, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (str(session_id), str(dataset_id), now.isoformat(), now.isoformat()),
    )
    conn.commit()
    session = find_session_by_dataset(conn, dataset_id)
    assert session is not None
    return session, True
