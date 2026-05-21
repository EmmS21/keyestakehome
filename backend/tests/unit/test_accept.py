"""Unit tests for accept proposals (POST .../accept brain)."""

from uuid import uuid4

import pytest

from backend.app import accept as accept_logic
from backend.app import datasets as datasets_logic
from backend.app import proposals as proposals_logic
from backend.app import sessions as sessions_logic
from backend.app.exceptions import ProposalNotFoundError, SessionNotFoundError
from schemas.types import CleaningPattern

VALID_CSV = """\
A,B,C,202401,202402,202403,202404,202405
Dog,China,Line,100,-200,0,50,30
Dog,Shine,Lime,0,50,-100,25,10
Cat,USA,Retail,0,200,-200,10,10
Bird,UK,Online,200,-200,5,5,5
,,,100,0,42,55,48
"""


def _write_csv(tmp_path, filename: str, content: str):
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


def _ingest_sample_session(conn, tmp_uploads, tmp_path):
    csv_file = _write_csv(tmp_path, "sample.csv", VALID_CSV)
    dataset = datasets_logic.ingest_dataset(
        conn,
        uploads_dir=tmp_uploads,
        source_path=csv_file,
        name="sample.csv",
    )
    session, _ = sessions_logic.start_or_resume_session(conn, dataset.id)
    return dataset, session


def _cell_value(conn, dataset_row_id, period: str) -> float:
    row = conn.execute(
        """
        SELECT value FROM cell_values
        WHERE dataset_row_id = ? AND period = ?
        """,
        (str(dataset_row_id), period),
    ).fetchone()
    assert row is not None
    return float(row["value"])


def _audit_rows(conn, session_id):
    return conn.execute(
        """
        SELECT id, session_id, submit_id, pattern, dataset_row_id,
               period, value_before, value_after, created_at
        FROM audit_log_entries
        WHERE session_id = ?
        ORDER BY created_at, period
        """,
        (str(session_id),),
    ).fetchall()


def _audit_count(conn, session_id) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM audit_log_entries WHERE session_id = ?",
        (str(session_id),),
    ).fetchone()
    return int(row["c"])


def test_accept_one_checked_row_updates_cells_writes_audit_and_returns_changes(
    tmp_db, tmp_uploads, tmp_path
):
    conn, _ = tmp_db
    _, session = _ingest_sample_session(conn, tmp_uploads, tmp_path)

    negatives = proposals_logic.list_all_proposals(
        conn, session.id, CleaningPattern.NEGATIVES
    )
    dog_china = next(
        p for p in negatives if p.dimension_a == "Dog" and p.dimension_b == "China"
    )

    result = accept_logic.accept_proposals(
        conn,
        session.id,
        CleaningPattern.NEGATIVES,
        [dog_china.id],
    )

    assert len(result.changes) == 1
    change = result.changes[0]
    assert change.period == "202402"
    assert change.value_before == -200.0
    assert change.value_after == 0.0
    assert _cell_value(conn, dog_china.dataset_row_id, "202402") == 0.0

    audit = _audit_rows(conn, session.id)
    assert len(audit) == 1
    assert audit[0]["submit_id"] == str(result.submit_id)
    assert audit[0]["pattern"] == CleaningPattern.NEGATIVES.value
    assert audit[0]["dataset_row_id"] == str(dog_china.dataset_row_id)
    assert audit[0]["period"] == "202402"
    assert audit[0]["value_before"] == -200.0
    assert audit[0]["value_after"] == 0.0


def test_accept_only_checked_rows_change_unchecked_rows_stay_unchanged(
    tmp_db, tmp_uploads, tmp_path
):
    conn, _ = tmp_db
    _, session = _ingest_sample_session(conn, tmp_uploads, tmp_path)

    negatives = proposals_logic.list_all_proposals(
        conn, session.id, CleaningPattern.NEGATIVES
    )
    assert len(negatives) == 4
    selected = negatives[0]
    unselected = negatives[1]

    before_unselected = {
        cell.period: _cell_value(conn, unselected.dataset_row_id, cell.period)
        for cell in unselected.changes
    }

    result = accept_logic.accept_proposals(
        conn,
        session.id,
        CleaningPattern.NEGATIVES,
        [selected.id],
    )

    assert len(result.changes) == len(selected.changes)
    for period, value in before_unselected.items():
        assert _cell_value(conn, unselected.dataset_row_id, period) == value


def test_accept_empty_selection_leaves_grid_unchanged_and_writes_no_audit(
    tmp_db, tmp_uploads, tmp_path
):
    conn, _ = tmp_db
    dataset, session = _ingest_sample_session(conn, tmp_uploads, tmp_path)

    snapshot = {
        (str(row.id), cell.period): cell.value
        for row in datasets_logic.list_rows(conn, dataset.id)
        for cell in datasets_logic.list_cell_values(conn, row.id)
    }

    result = accept_logic.accept_proposals(
        conn, session.id, CleaningPattern.NEGATIVES, []
    )

    assert result.changes == []
    assert _audit_count(conn, session.id) == 0

    for row in datasets_logic.list_rows(conn, dataset.id):
        for cell in datasets_logic.list_cell_values(conn, row.id):
            key = (str(row.id), cell.period)
            assert cell.value == snapshot[key]


def test_accept_wrong_or_unknown_proposal_id_raises_without_writes(
    tmp_db, tmp_uploads, tmp_path
):
    conn, _ = tmp_db
    _, session = _ingest_sample_session(conn, tmp_uploads, tmp_path)

    negatives = proposals_logic.list_all_proposals(
        conn, session.id, CleaningPattern.NEGATIVES
    )
    wrong_pattern_id = next(
        p.id
        for p in proposals_logic.list_all_proposals(
            conn, session.id, CleaningPattern.REFUNDS
        )
    )

    with pytest.raises(ProposalNotFoundError):
        accept_logic.accept_proposals(
            conn,
            session.id,
            CleaningPattern.NEGATIVES,
            [wrong_pattern_id],
        )

    assert _audit_count(conn, session.id) == 0
    assert _cell_value(conn, negatives[0].dataset_row_id, negatives[0].changes[0].period) == (
        negatives[0].changes[0].value_before
    )


def test_accept_missing_session_raises(tmp_db):
    conn, _ = tmp_db
    with pytest.raises(SessionNotFoundError):
        accept_logic.accept_proposals(
            conn, uuid4(), CleaningPattern.NEGATIVES, []
        )
