"""Paginated audit timeline: cell alterations and CSV download events."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from backend.app.sessions import get_session
from schemas.api import (
    AuditAlterationEntry,
    AuditDownloadEntry,
    AuditEventFilter,
    AuditTimelineEntry,
)
from schemas.types import CleaningPattern


@dataclass(frozen=True)
class AuditLogPage:
    entries: list[AuditTimelineEntry]
    total_count: int
    limit: int
    offset: int


def _alteration_row_to_entry(row: sqlite3.Row) -> AuditAlterationEntry:
    return AuditAlterationEntry(
        id=UUID(row["id"]),
        submit_id=UUID(row["submit_id"]),
        pattern=CleaningPattern(row["pattern"]),
        dataset_row_id=UUID(row["dataset_row_id"]),
        period=row["period"],
        value_before=float(row["value_before"]),
        value_after=float(row["value_after"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _download_row_to_entry(row: sqlite3.Row) -> AuditDownloadEntry:
    return AuditDownloadEntry(
        id=UUID(row["id"]),
        created_at=datetime.fromisoformat(row["exported_at"]),
        export_number=int(row["export_number"]),
        audit_entry_count=int(row["audit_entry_count"]),
    )


def _load_timeline(
    conn: sqlite3.Connection,
    session_id: UUID,
    *,
    event_filter: AuditEventFilter,
) -> list[AuditTimelineEntry]:
    items: list[AuditTimelineEntry] = []

    if event_filter in ("all", "alteration"):
        rows = conn.execute(
            """
            SELECT id, submit_id, pattern, dataset_row_id,
                   period, value_before, value_after, created_at
            FROM audit_log_entries
            WHERE session_id = ?
            ORDER BY created_at ASC, period ASC
            """,
            (str(session_id),),
        ).fetchall()
        items.extend(_alteration_row_to_entry(row) for row in rows)

    if event_filter in ("all", "download"):
        rows = conn.execute(
            """
            SELECT id, exported_at, export_number, audit_entry_count
            FROM export_events
            WHERE session_id = ?
            ORDER BY exported_at ASC
            """,
            (str(session_id),),
        ).fetchall()
        items.extend(_download_row_to_entry(row) for row in rows)

    items.sort(key=lambda e: (e.created_at, e.kind, str(e.id)))
    return items


def list_audit(
    conn: sqlite3.Connection,
    session_id: UUID,
    *,
    limit: int,
    offset: int,
    event_filter: AuditEventFilter = "all",
) -> AuditLogPage:
    get_session(conn, session_id)

    timeline = _load_timeline(conn, session_id, event_filter=event_filter)
    total_count = len(timeline)
    page = timeline[offset : offset + limit]

    return AuditLogPage(
        entries=page,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
