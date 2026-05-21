"""Unit tests for dataset CSV export (GET /datasets/{id}/export brain)."""

from uuid import uuid4

import pytest

from backend.app import accept as accept_logic
from backend.app import datasets as datasets_logic
from backend.app import exports as exports_logic
from backend.app import proposals as proposals_logic
from backend.app import sessions as sessions_logic
from backend.app.exceptions import DatasetNotFoundError
from schemas.types import CleaningPattern

VALID_CSV = """\
A,B,C,202401,202402,202403,202404,202405
Dog,China,Line,100,-200,0,50,30
Dog,Shine,Lime,0,50,-100,25,10
"""


def _write_csv(tmp_path, filename: str, content: str):
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


def test_export_unknown_dataset_raises_not_found(tmp_db):
    conn, _ = tmp_db
    missing_id = uuid4()
    with pytest.raises(DatasetNotFoundError):
        datasets_logic.export_dataset_csv(conn, missing_id)


def test_export_matches_ingested_grid(tmp_db, tmp_uploads, tmp_path):
    conn, _ = tmp_db
    csv_file = _write_csv(tmp_path, "deal.csv", VALID_CSV)
    dataset = datasets_logic.ingest_dataset(
        conn,
        uploads_dir=tmp_uploads,
        source_path=csv_file,
        name="deal.csv",
    )

    name, text = datasets_logic.export_dataset_csv(conn, dataset.id)
    assert name == "deal.csv"
    lines = text.strip().splitlines()
    assert lines[0] == "A,B,C,202401,202402,202403,202404,202405"
    assert "Dog,China,Line,100,-200,0,50,30" in lines

    events = exports_logic.list_exports_for_dataset(conn, dataset.id)
    assert len(events) == 1
    assert events[0].export_number == 1
    assert events[0].audit_entry_count == 0


def test_export_reflects_accepted_cell_changes(tmp_db, tmp_uploads, tmp_path):
    conn, _ = tmp_db
    csv_file = _write_csv(tmp_path, "deal.csv", VALID_CSV)
    dataset = datasets_logic.ingest_dataset(
        conn,
        uploads_dir=tmp_uploads,
        source_path=csv_file,
        name="deal.csv",
    )
    session, _ = sessions_logic.start_or_resume_session(conn, dataset.id)
    negatives = proposals_logic.list_all_proposals(
        conn, session.id, CleaningPattern.NEGATIVES
    )
    accept_logic.accept_proposals(
        conn,
        session.id,
        CleaningPattern.NEGATIVES,
        [negatives[0].id],
        session_updated_at=session.updated_at,
    )

    _, text = datasets_logic.export_dataset_csv(conn, dataset.id)
    assert "-200" not in text.splitlines()[1]

    events = exports_logic.list_exports_for_dataset(conn, dataset.id)
    assert len(events) == 1
    assert events[0].audit_entry_count == 1


def test_second_export_increments_export_number(tmp_db, tmp_uploads, tmp_path):
    conn, _ = tmp_db
    csv_file = _write_csv(tmp_path, "deal.csv", VALID_CSV)
    dataset = datasets_logic.ingest_dataset(
        conn,
        uploads_dir=tmp_uploads,
        source_path=csv_file,
        name="deal.csv",
    )

    datasets_logic.export_dataset_csv(conn, dataset.id)
    datasets_logic.export_dataset_csv(conn, dataset.id)

    events = exports_logic.list_exports_for_dataset(conn, dataset.id)
    assert [e.export_number for e in events] == [1, 2]
    assert events[0].exported_at <= events[1].exported_at
