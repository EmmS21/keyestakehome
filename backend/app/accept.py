"""Apply accepted proposals to the working grid and audit log."""

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.app import proposals as proposals_logic
from backend.app.exceptions import ProposalNotFoundError, SessionConflictError
from backend.app.sessions import get_session
from schemas.api import AppliedCellChange, Proposal
from schemas.types import CleaningPattern

_VALUE_EPSILON = 1e-9


@dataclass(frozen=True)
class AcceptResult:
    submit_id: UUID
    changes: list[AppliedCellChange]


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _session_versions_match(expected: datetime, actual: datetime) -> bool:
    return _as_utc(expected) == _as_utc(actual)


def _read_cell_value(
    conn: sqlite3.Connection, dataset_row_id: UUID, period: str
) -> float:
    row = conn.execute(
        """
        SELECT value FROM cell_values
        WHERE dataset_row_id = ? AND period = ?
        """,
        (str(dataset_row_id), period),
    ).fetchone()
    if row is None:
        raise ProposalNotFoundError(
            f"missing cell for row {dataset_row_id} period {period}"
        )
    return float(row["value"])


def _apply_proposal(
    conn: sqlite3.Connection,
    *,
    session_id: UUID,
    submit_id: UUID,
    pattern: CleaningPattern,
    proposal: Proposal,
    created_at: datetime,
    changes: list[AppliedCellChange],
) -> None:
    for cell_change in proposal.changes:
        value_before = _read_cell_value(
            conn, proposal.dataset_row_id, cell_change.period
        )
        value_after = cell_change.value_after
        if abs(value_before - value_after) < _VALUE_EPSILON:
            continue

        conn.execute(
            """
            UPDATE cell_values SET value = ?
            WHERE dataset_row_id = ? AND period = ?
            """,
            (value_after, str(proposal.dataset_row_id), cell_change.period),
        )
        conn.execute(
            """
            INSERT INTO audit_log_entries (
                id, session_id, submit_id, pattern, dataset_row_id,
                period, value_before, value_after, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                str(session_id),
                str(submit_id),
                pattern.value,
                str(proposal.dataset_row_id),
                cell_change.period,
                value_before,
                value_after,
                created_at.isoformat(),
            ),
        )
        changes.append(
            AppliedCellChange(
                dataset_row_id=proposal.dataset_row_id,
                period=cell_change.period,
                value_before=value_before,
                value_after=value_after,
            )
        )


def accept_proposals(
    conn: sqlite3.Connection,
    session_id: UUID,
    pattern: CleaningPattern,
    proposal_ids: list[str],
    *,
    session_updated_at: datetime,
) -> AcceptResult:
    """
    Apply selected proposals for one pattern.
    Empty proposal_ids updates session timestamp only; no cell or audit writes.
    """
    session = get_session(conn, session_id)
    if not _session_versions_match(session_updated_at, session.updated_at):
        raise SessionConflictError(session_id)

    proposals_by_id = proposals_logic.resolve_proposals_for_accept(
        conn, session_id, pattern, proposal_ids
    )

    submit_id = uuid4()
    now = datetime.now(UTC)
    changes: list[AppliedCellChange] = []

    try:
        seen: set[str] = set()
        for proposal_id in proposal_ids:
            if proposal_id in seen:
                continue
            seen.add(proposal_id)
            _apply_proposal(
                conn,
                session_id=session_id,
                submit_id=submit_id,
                pattern=pattern,
                proposal=proposals_by_id[proposal_id],
                created_at=now,
                changes=changes,
            )

        conn.execute(
            """
            UPDATE cleaning_sessions SET updated_at = ?
            WHERE id = ?
            """,
            (now.isoformat(), str(session_id)),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return AcceptResult(submit_id=submit_id, changes=changes)
