"""Unit tests for audit log listing (GET .../audit brain)."""

from uuid import uuid4

import pytest

from backend.app import accept as accept_logic
from backend.app import audit as audit_logic
from backend.app import datasets as datasets_logic
from backend.app import proposals as proposals_logic
from backend.app import sessions as sessions_logic
from backend.app.exceptions import SessionNotFoundError
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


def _ingest_sample_session(conn, tmp_uploads, tmp_path, filename: str = "sample.csv"):
    csv_file = _write_csv(tmp_path, filename, VALID_CSV)
    dataset = datasets_logic.ingest_dataset(
        conn,
        uploads_dir=tmp_uploads,
        source_path=csv_file,
        name=filename,
    )
    session, _ = sessions_logic.start_or_resume_session(conn, dataset.id)
    return dataset, session


def test_list_audit_empty_when_nothing_accepted_yet(tmp_db, tmp_uploads, tmp_path):
    conn, _ = tmp_db
    _, session = _ingest_sample_session(conn, tmp_uploads, tmp_path)

    page = audit_logic.list_audit(conn, session.id, limit=10, offset=0)

    assert page.entries == []
    assert page.total_count == 0


def test_list_audit_shows_what_accept_saved(tmp_db, tmp_uploads, tmp_path):
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
        session_updated_at=session.updated_at,
    )

    page = audit_logic.list_audit(conn, session.id, limit=10, offset=0)

    assert page.total_count == 1
    assert len(page.entries) == 1
    entry = page.entries[0]
    assert entry.submit_id == result.submit_id
    assert entry.pattern == CleaningPattern.NEGATIVES
    assert entry.dataset_row_id == dog_china.dataset_row_id
    assert entry.period == "202402"
    assert entry.value_before == -200.0
    assert entry.value_after == 0.0
    assert result.changes[0].value_before == entry.value_before
    assert result.changes[0].value_after == entry.value_after


def test_list_audit_pagination(tmp_db, tmp_uploads, tmp_path):
    conn, _ = tmp_db
    _, session = _ingest_sample_session(conn, tmp_uploads, tmp_path)

    negatives = proposals_logic.list_all_proposals(
        conn, session.id, CleaningPattern.NEGATIVES
    )
    accept_logic.accept_proposals(
        conn,
        session.id,
        CleaningPattern.NEGATIVES,
        [p.id for p in negatives],
        session_updated_at=session.updated_at,
    )

    page1 = audit_logic.list_audit(conn, session.id, limit=2, offset=0)
    assert page1.total_count == 4
    assert len(page1.entries) == 2

    page2 = audit_logic.list_audit(conn, session.id, limit=2, offset=2)
    assert page2.total_count == 4
    assert len(page2.entries) == 2

    past_end = audit_logic.list_audit(conn, session.id, limit=10, offset=10)
    assert past_end.total_count == 4
    assert past_end.entries == []


def test_list_audit_only_this_sessions_changes(tmp_db, tmp_uploads, tmp_path):
    conn, _ = tmp_db
    _, session_a = _ingest_sample_session(conn, tmp_uploads, tmp_path, "a.csv")
    _, session_b = _ingest_sample_session(conn, tmp_uploads, tmp_path, "b.csv")

    negatives = proposals_logic.list_all_proposals(
        conn, session_a.id, CleaningPattern.NEGATIVES
    )
    accept_logic.accept_proposals(
        conn,
        session_a.id,
        CleaningPattern.NEGATIVES,
        [negatives[0].id],
        session_updated_at=session_a.updated_at,
    )

    audit_a = audit_logic.list_audit(conn, session_a.id, limit=10, offset=0)
    audit_b = audit_logic.list_audit(conn, session_b.id, limit=10, offset=0)

    assert audit_a.total_count == 1
    assert audit_b.entries == []
    assert audit_b.total_count == 0

    with pytest.raises(SessionNotFoundError):
        audit_logic.list_audit(conn, uuid4(), limit=10, offset=0)
