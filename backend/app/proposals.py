"""Proposal listing for a cleaning session and pattern."""

import sqlite3
from dataclasses import dataclass
from uuid import UUID

from backend.app import datasets as datasets_logic
from backend.app import detectors
from backend.app.exceptions import SessionNotFoundError
from backend.app.sessions import get_session
from schemas.api import Proposal
from schemas.types import CleaningPattern


@dataclass(frozen=True)
class ProposalsPage:
    pattern: CleaningPattern
    proposals: list[Proposal]
    total_count: int
    limit: int
    offset: int


def _row_period_values(
    conn: sqlite3.Connection, dataset_row_id: UUID
) -> list[tuple[str, float]]:
    cells = datasets_logic.list_cell_values(conn, dataset_row_id)
    return [(cell.period, cell.value) for cell in cells]


def _build_proposals(
    conn: sqlite3.Connection,
    dataset_id: UUID,
    period_columns: list[str],
    pattern: CleaningPattern,
) -> list[Proposal]:
    proposals: list[Proposal] = []
    for row in datasets_logic.list_rows(conn, dataset_id):
        values = _row_period_values(conn, row.id)
        periods = detectors._period_map(period_columns, values)
        changes = detectors.detect_for_pattern(pattern, period_columns, periods)
        if not changes:
            continue
        proposals.append(
            Proposal(
                id=detectors.proposal_id(pattern, row.id),
                pattern=pattern,
                dataset_row_id=row.id,
                row_index=row.row_index,
                dimension_a=row.dimension_a,
                dimension_b=row.dimension_b,
                dimension_c=row.dimension_c,
                changes=changes,
            )
        )
    return proposals


def list_all_proposals(
    conn: sqlite3.Connection,
    session_id: UUID,
    pattern: CleaningPattern,
) -> list[Proposal]:
    """All proposals for a session/pattern (used by accept to resolve proposal_ids)."""
    session = get_session(conn, session_id)
    dataset = datasets_logic.get_dataset(conn, session.dataset_id)
    return _build_proposals(conn, dataset.id, dataset.period_columns, pattern)


def list_proposals(
    conn: sqlite3.Connection,
    session_id: UUID,
    pattern: CleaningPattern,
    *,
    limit: int,
    offset: int,
) -> ProposalsPage:
    session = get_session(conn, session_id)
    dataset = datasets_logic.get_dataset(conn, session.dataset_id)
    all_proposals = _build_proposals(
        conn, dataset.id, dataset.period_columns, pattern
    )
    total_count = len(all_proposals)
    page = all_proposals[offset : offset + limit]
    return ProposalsPage(
        pattern=pattern,
        proposals=page,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
