"""Paginated audit log for a cleaning session."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from backend.app.sessions import get_session
from schemas.api import AuditLogEntryView
from schemas.types import CleaningPattern


@dataclass(frozen=True)
class AuditLogPage:
    entries: list[AuditLogEntryView]
    total_count: int
    limit: int
    offset: int


def _row_to_entry(row: sqlite3.Row) -> AuditLogEntryView:
    return AuditLogEntryView(
        id=UUID(row["id"]),
        submit_id=UUID(row["submit_id"]),
        pattern=CleaningPattern(row["pattern"]),
        dataset_row_id=UUID(row["dataset_row_id"]),
        period=row["period"],
        value_before=float(row["value_before"]),
        value_after=float(row["value_after"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def list_audit(
    conn: sqlite3.Connection,
    session_id: UUID,
    *,
    limit: int,
    offset: int,
) -> AuditLogPage:
    get_session(conn, session_id)

    count_row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM audit_log_entries
        WHERE session_id = ?
        """,
        (str(session_id),),
    ).fetchone()
    total_count = int(count_row["c"])

    rows = conn.execute(
        """
        SELECT id, submit_id, pattern, dataset_row_id,
               period, value_before, value_after, created_at
        FROM audit_log_entries
        WHERE session_id = ?
        ORDER BY created_at ASC, period ASC
        LIMIT ? OFFSET ?
        """,
        (str(session_id), limit, offset),
    ).fetchall()

    return AuditLogPage(
        entries=[_row_to_entry(row) for row in rows],
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
