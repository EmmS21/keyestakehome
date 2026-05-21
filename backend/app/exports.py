"""Record CSV export events for audit and version retracing."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app.sessions import start_or_resume_session


@dataclass(frozen=True)
class ExportEventRecord:
    id: UUID
    dataset_id: UUID
    session_id: UUID
    exported_at: datetime
    session_updated_at: datetime
    audit_entry_count: int
    export_number: int


def _audit_entry_count(conn: sqlite3.Connection, session_id: UUID) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM audit_log_entries
        WHERE session_id = ?
        """,
        (str(session_id),),
    ).fetchone()
    return int(row["c"])


def _next_export_number(conn: sqlite3.Connection, dataset_id: UUID) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM export_events
        WHERE dataset_id = ?
        """,
        (str(dataset_id),),
    ).fetchone()
    return int(row["c"]) + 1


def record_export(conn: sqlite3.Connection, dataset_id: UUID) -> ExportEventRecord:
    """
    Log that a CSV was downloaded for this dataset.

    Snapshots session_updated_at and audit_entry_count so exports can be tied
    to a point in the cleaning history (which accepts were already applied).
    """
    session, _ = start_or_resume_session(conn, dataset_id)
    exported_at = datetime.now(UTC)
    event_id = uuid4()
    audit_count = _audit_entry_count(conn, session.id)
    export_number = _next_export_number(conn, dataset_id)

    conn.execute(
        """
        INSERT INTO export_events (
            id, dataset_id, session_id, exported_at,
            session_updated_at, audit_entry_count, export_number
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(event_id),
            str(dataset_id),
            str(session.id),
            exported_at.isoformat(),
            session.updated_at.isoformat(),
            audit_count,
            export_number,
        ),
    )
    conn.commit()

    return ExportEventRecord(
        id=event_id,
        dataset_id=dataset_id,
        session_id=session.id,
        exported_at=exported_at,
        session_updated_at=session.updated_at,
        audit_entry_count=audit_count,
        export_number=export_number,
    )


def list_exports_for_dataset(
    conn: sqlite3.Connection, dataset_id: UUID
) -> list[ExportEventRecord]:
    """All exports for a dataset, oldest first."""
    rows = conn.execute(
        """
        SELECT id, dataset_id, session_id, exported_at,
               session_updated_at, audit_entry_count, export_number
        FROM export_events
        WHERE dataset_id = ?
        ORDER BY exported_at ASC
        """,
        (str(dataset_id),),
    ).fetchall()
    return [
        ExportEventRecord(
            id=UUID(r["id"]),
            dataset_id=UUID(r["dataset_id"]),
            session_id=UUID(r["session_id"]),
            exported_at=datetime.fromisoformat(r["exported_at"]),
            session_updated_at=datetime.fromisoformat(r["session_updated_at"]),
            audit_entry_count=int(r["audit_entry_count"]),
            export_number=int(r["export_number"]),
        )
        for r in rows
    ]
