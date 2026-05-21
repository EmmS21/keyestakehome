"""Proposal listing for a cleaning session and pattern."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from backend.app import datasets as datasets_logic
from backend.app import detectors
from backend.app.exceptions import ProposalNotFoundError, SessionNotFoundError
from backend.app.sessions import get_session
from schemas.api import Proposal
from schemas.database import DatasetRow
from schemas.types import CleaningPattern


@dataclass(frozen=True)
class ProposalsPage:
    pattern: CleaningPattern
    session_updated_at: datetime
    proposals: list[Proposal]
    total_count: int
    limit: int
    offset: int


def _candidate_rows(
    conn: sqlite3.Connection, dataset_id: UUID, pattern: CleaningPattern
) -> list[DatasetRow] | None:
    """None = scan all rows in chunks; list = pre-filtered row set."""
    if pattern == CleaningPattern.NEGATIVES:
        return datasets_logic.list_rows_with_negative_cells(conn, dataset_id)
    return None


def _proposal_from_row(
    row: DatasetRow,
    period_columns: list[str],
    periods: dict[str, float],
    pattern: CleaningPattern,
) -> Proposal | None:
    changes = detectors.detect_for_pattern(pattern, period_columns, periods)
    if not changes:
        return None
    return Proposal(
        id=detectors.proposal_id(pattern, row.id),
        pattern=pattern,
        dataset_row_id=row.id,
        row_index=row.row_index,
        dimension_a=row.dimension_a,
        dimension_b=row.dimension_b,
        dimension_c=row.dimension_c,
        changes=changes,
    )


def _build_proposals(
    conn: sqlite3.Connection,
    dataset_id: UUID,
    period_columns: list[str],
    pattern: CleaningPattern,
) -> list[Proposal]:
    proposals: list[Proposal] = []
    candidates = _candidate_rows(conn, dataset_id, pattern)
    for chunk in datasets_logic.iter_row_chunks(
        conn, dataset_id, rows=candidates
    ):
        periods_by_row = datasets_logic.load_periods_for_rows(
            conn, [row.id for row in chunk], period_columns
        )
        for row in chunk:
            proposal = _proposal_from_row(
                row,
                period_columns,
                periods_by_row[row.id],
                pattern,
            )
            if proposal is not None:
                proposals.append(proposal)
    return proposals


def list_all_proposals(
    conn: sqlite3.Connection,
    session_id: UUID,
    pattern: CleaningPattern,
) -> list[Proposal]:
    """All proposals for a session/pattern."""
    session = get_session(conn, session_id)
    dataset = datasets_logic.get_dataset(conn, session.dataset_id)
    return _build_proposals(conn, dataset.id, dataset.period_columns, pattern)


def _parse_proposal_id(proposal_id: str, pattern: CleaningPattern) -> UUID | None:
    prefix, row_id_str = proposal_id.split(":", 1)
    if prefix != pattern.value:
        return None
    try:
        return UUID(row_id_str)
    except ValueError:
        return None


def resolve_proposals_for_accept(
    conn: sqlite3.Connection,
    session_id: UUID,
    pattern: CleaningPattern,
    proposal_ids: list[str],
) -> dict[str, Proposal]:
    """
    Map proposal ids to proposals for accept.
    Includes rows no longer flagged (e.g. already fixed) so accept can no-op cleanly.
    """
    session = get_session(conn, session_id)
    dataset = datasets_logic.get_dataset(conn, session.dataset_id)
    current = {p.id: p for p in _build_proposals(conn, dataset.id, dataset.period_columns, pattern)}
    resolved: dict[str, Proposal] = {}
    for proposal_id in proposal_ids:
        if proposal_id in current:
            resolved[proposal_id] = current[proposal_id]
            continue
        row_id = _parse_proposal_id(proposal_id, pattern)
        if row_id is None:
            raise ProposalNotFoundError(proposal_id)
        row = datasets_logic.get_dataset_row(conn, row_id)
        if row is None or row.dataset_id != dataset.id:
            raise ProposalNotFoundError(proposal_id)
        periods_by_row = datasets_logic.load_periods_for_rows(
            conn, [row_id], dataset.period_columns
        )
        proposal = _proposal_from_row(
            row, dataset.period_columns, periods_by_row[row_id], pattern
        )
        if proposal is None:
            proposal = Proposal(
                id=proposal_id,
                pattern=pattern,
                dataset_row_id=row.id,
                row_index=row.row_index,
                dimension_a=row.dimension_a,
                dimension_b=row.dimension_b,
                dimension_c=row.dimension_c,
                changes=[],
            )
        resolved[proposal_id] = proposal
    return resolved


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
        session_updated_at=session.updated_at,
        proposals=page,
        total_count=total_count,
        limit=limit,
        offset=offset,
    )
