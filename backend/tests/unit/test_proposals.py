"""Unit tests for proposals listing (GET .../proposals brain)."""

from uuid import uuid4

import pytest

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


def test_list_proposals_detects_negatives_refunds_and_double_booking_on_sample_csv(
    tmp_db, tmp_uploads, tmp_path
):
    conn, _ = tmp_db
    dataset, session = _ingest_sample_session(conn, tmp_uploads, tmp_path)

    negatives = proposals_logic.list_proposals(
        conn, session.id, CleaningPattern.NEGATIVES, limit=50, offset=0
    )
    assert negatives.total_count == 4
    dog_china = next(p for p in negatives.proposals if p.dimension_a == "Dog" and p.dimension_b == "China")
    assert len(dog_china.changes) == 1
    assert dog_china.changes[0].period == "202402"
    assert dog_china.changes[0].value_before == -200.0
    assert dog_china.changes[0].value_after == 0.0

    refunds = proposals_logic.list_proposals(
        conn, session.id, CleaningPattern.REFUNDS, limit=50, offset=0
    )
    assert refunds.total_count == 5
    cat = next(p for p in refunds.proposals if p.dimension_a == "Cat")
    assert {c.period for c in cat.changes} == {"202401", "202402", "202403"}
    assert all(c.value_after == 0.0 for c in cat.changes)

    double = proposals_logic.list_proposals(
        conn, session.id, CleaningPattern.DOUBLE_BOOKING, limit=50, offset=0
    )
    assert double.total_count == 2
    blank = next(p for p in double.proposals if p.dimension_a is None)
    by_period = {c.period: (c.value_before, c.value_after) for c in blank.changes}
    assert by_period["202401"] == (100.0, 50.0)
    assert by_period["202402"] == (0.0, 50.0)
    dog_china_dbl = next(
        p for p in double.proposals if p.dimension_a == "Dog" and p.dimension_b == "China"
    )
    assert {c.period for c in dog_china_dbl.changes} == {"202402", "202403"}
    assert dog_china_dbl.changes[0].value_after == -100.0


def test_list_proposals_pagination_returns_pages_with_stable_total_count(
    tmp_db, tmp_uploads, tmp_path
):
    conn, _ = tmp_db
    _, session = _ingest_sample_session(conn, tmp_uploads, tmp_path)

    page1 = proposals_logic.list_proposals(
        conn, session.id, CleaningPattern.NEGATIVES, limit=2, offset=0
    )
    assert page1.total_count == 4
    assert len(page1.proposals) == 2
    assert page1.limit == 2
    assert page1.offset == 0

    page2 = proposals_logic.list_proposals(
        conn, session.id, CleaningPattern.NEGATIVES, limit=2, offset=2
    )
    assert page2.total_count == 4
    assert len(page2.proposals) == 2

    past_end = proposals_logic.list_proposals(
        conn, session.id, CleaningPattern.NEGATIVES, limit=10, offset=10
    )
    assert past_end.total_count == 4
    assert past_end.proposals == []


def test_list_proposals_refund_count_drops_after_working_copy_is_updated(
    tmp_db, tmp_uploads, tmp_path
):
    conn, _ = tmp_db
    dataset, session = _ingest_sample_session(conn, tmp_uploads, tmp_path)

    before = proposals_logic.list_proposals(
        conn, session.id, CleaningPattern.REFUNDS, limit=50, offset=0
    )
    assert before.total_count == 5

    bird = next(
        r
        for r in datasets_logic.list_rows(conn, dataset.id)
        if r.dimension_a == "Bird"
    )
    conn.execute(
        """
        UPDATE cell_values SET value = ?
        WHERE dataset_row_id = ? AND period = ?
        """,
        (0.0, str(bird.id), "202401"),
    )
    conn.commit()

    bird_before = next(p for p in before.proposals if p.dimension_a == "Bird")
    assert "202402" in {c.period for c in bird_before.changes}

    after = proposals_logic.list_proposals(
        conn, session.id, CleaningPattern.REFUNDS, limit=50, offset=0
    )
    bird_after = next(p for p in after.proposals if p.dimension_a == "Bird")
    assert "202402" not in {c.period for c in bird_after.changes}


def test_list_proposals_missing_session_raises(tmp_db):
    conn, _ = tmp_db
    with pytest.raises(SessionNotFoundError):
        proposals_logic.list_proposals(
            conn, uuid4(), CleaningPattern.NEGATIVES, limit=10, offset=0
        )
