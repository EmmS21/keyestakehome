"""Unit tests for session start/resume (POST /datasets/{id}/sessions brain)."""

from uuid import uuid4

import pytest

from backend.app import datasets as datasets_logic
from backend.app import sessions as sessions_logic
from backend.app.exceptions import DatasetNotFoundError

VALID_CSV = """\
A,B,C,202401,202402,202403,202404,202405
Dog,China,Line,100,-200,0,50,30
"""


def _write_csv(tmp_path, filename: str, content: str):
    path = tmp_path / filename
    path.write_text(content, encoding="utf-8")
    return path


def _session_count(conn, dataset_id) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM cleaning_sessions WHERE dataset_id = ?",
        (str(dataset_id),),
    ).fetchone()
    return int(row["c"])


def test_start_session_creates_once_then_resume_returns_same_session(
    tmp_db, tmp_uploads, tmp_path
):
    conn, _ = tmp_db
    csv_file = _write_csv(tmp_path, "sample.csv", VALID_CSV)
    dataset = datasets_logic.ingest_dataset(
        conn,
        uploads_dir=tmp_uploads,
        source_path=csv_file,
        name="sample.csv",
    )

    first, created_first = sessions_logic.start_or_resume_session(conn, dataset.id)
    assert created_first is True
    assert first.dataset_id == dataset.id
    assert first.created_at <= first.updated_at
    assert _session_count(conn, dataset.id) == 1

    second, created_second = sessions_logic.start_or_resume_session(conn, dataset.id)
    assert created_second is False
    assert second.id == first.id
    assert second.dataset_id == dataset.id
    assert second.created_at == first.created_at
    assert second.updated_at == first.updated_at
    assert _session_count(conn, dataset.id) == 1


def test_start_session_missing_dataset_raises(tmp_db):
    conn, _ = tmp_db
    with pytest.raises(DatasetNotFoundError):
        sessions_logic.start_or_resume_session(conn, uuid4())
